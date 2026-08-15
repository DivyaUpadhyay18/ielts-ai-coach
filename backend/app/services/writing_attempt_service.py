"""
Writing Reattempt Mode Service.

Provides the business logic for retrying a writing task after receiving an
evaluation.  The service:

  - Starts a reattempt from a previously-evaluated submission (reuses the
    same prompt, creates a new draft linked to the original via attempt_group)
  - Evaluates the new attempt
  - Compares attempt 1 vs attempt N (band, 4 criteria, time, word count)
  - Awards bonus XP for meaningful improvement (>=0.5 band overall or any
    criterion improving by >=0.5)
  - All operations are owner-scoped and degrade gracefully if the DB or
    mission system is unavailable.
"""
import logging
from datetime import date, datetime, timezone
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository
from app.repositories.writing_workspace_repo import WritingWorkspaceRepository
from app.services.writing_evaluation_engine import WritingEvaluationEngine
from app.services.writing_mission_service import WritingMissionService

logger = logging.getLogger(__name__)

# XP bonus thresholds.
IMPROVEMENT_BAND_THRESHOLD = 0.5  # band points needed to qualify for bonus
IMPROVEMENT_BONUS_XP = 50  # XP awarded for meaningful improvement

# Criterion keys in canonical display order.
CRITERIA_KEYS = (
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammatical_range_accuracy",
)

CRITERION_LABELS = {
    "task_response": "Task Response",
    "coherence_cohesion": "Coherence & Cohesion",
    "lexical_resource": "Lexical Resource",
    "grammatical_range_accuracy": "Grammar",
}


class WritingAttemptService:
    """
    Service for the Writing Reattempt Mode lifecycle.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.writing_repo = WritingWorkspaceRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)
        self.streak_repo = StreakRepository(db)
        self.evaluation_engine = WritingEvaluationEngine(db)
        self.mission_service = WritingMissionService(db)

    # ------------------------------------------------------------------
    # Attempt lifecycle
    # ------------------------------------------------------------------
    def start_reattempt(
        self, user_id: str, original_submission_id: str
    ) -> dict[str, Any]:
        """
        Start a reattempt for a previously-evaluated submission.

        Creates a new draft submission that reuses the original prompt, and
        records a writing_attempts row linking the two.

        Raises:
            NotFoundError: if the original submission doesn't exist.
            ValidationError: if the original submission hasn't been evaluated.
        """
        original = self.writing_repo.get_submission(
            original_submission_id, user_id
        )
        if not original:
            raise NotFoundError("Original submission not found")
        if original.get("status") != "submitted":
            raise ValidationError(
                "Only submitted essays can be reattempted"
            )

        evaluation = self.writing_repo.get_evaluation(
            original_submission_id, user_id
        )
        if not evaluation or evaluation.get("status") != "evaluated":
            raise ValidationError(
                "The original submission must be evaluated before reattempting"
            )

        # Determine the attempt number.
        attempt_number = self._count_attempts(user_id, original_submission_id) + 1

        # Create a new draft for the reattempt (reuses the same prompt).
        new_submission = self.writing_repo.create_submission(
            user_id,
            {
                "prompt_id": original.get("prompt_id"),
                "task_type": original.get("task_type", "task_2"),
                "title": original.get("title", ""),
                "prompt_text": original.get("prompt_text", ""),
                "word_limit": original.get("word_limit", 250),
                "time_limit_seconds": original.get(
                    "time_limit_seconds", 2400
                ),
                "essay_text": "",
                "word_count": 0,
                "time_seconds_spent": 0,
                "status": "draft",
                "submission_summary": {},
            },
        )

        # Record the attempt link.
        self._create_attempt_record(
            user_id=user_id,
            attempt_group=original_submission_id,
            submission_id=new_submission["id"],
            attempt_number=attempt_number,
        )

        logger.info(
            "writing reattempt started user=%s original=%s attempt=%d",
            user_id, original_submission_id, attempt_number,
        )

        return {
            "submission": new_submission,
            "original_submission_id": original_submission_id,
            "attempt_number": attempt_number,
            "attempt_group": original_submission_id,
            "original_evaluation": evaluation,
        }

    async def evaluate_reattempt(
        self, user_id: str, submission_id: str
    ) -> dict[str, Any]:
        """
        Evaluate a reattempt submission and compute the comparison + bonus XP.
        """
        submission = self.writing_repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Reattempt submission not found")
        if submission.get("status") != "submitted":
            raise ValidationError("Submission must be submitted before evaluation")

        # Find the original attempt via the writing_attempts table.
        attempt_record = self._get_attempt_record(
            user_id, submission_id
        )
        if not attempt_record:
            raise NotFoundError("Attempt record not found")

        original_submission_id = attempt_record.get("attempt_group")
        attempt_number = attempt_record.get("attempt_number", 1)

        # Run the AI evaluation (delegates to WritingEvaluationEngine).
        evaluation = await self.evaluation_engine.evaluate_submission(
            user_id, submission_id,
            task_type=submission.get("task_type", "task_2"),
        )

        # Compute comparison and bonus XP.
        comparison = self._compare_attempts(
            user_id, original_submission_id, submission_id
        )

        bonus_xp = 0
        bonus_reason = None
        if comparison.get("improvement") and comparison["improvement"]:
            bonus_xp = IMPROVEMENT_BONUS_XP
            bonus_reason = "Meaningful improvement detected"
            # Award bonus XP via the streak/event ledger.
            self._award_bonus_xp(user_id, submission_id, bonus_xp, bonus_reason)

        # Update the attempt record with the new band + bonus info.
        self._update_attempt_record(
            user_id,
            attempt_record.get("id"),
            overall_band=evaluation.get("overall_band"),
            bonus_xp=bonus_xp,
            bonus_reason=bonus_reason,
        )

        return {
            "evaluation": evaluation,
            "comparison": comparison,
            "attempt_number": attempt_number,
            "bonus_xp": bonus_xp,
            "bonus_reason": bonus_reason,
        }

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------
    def get_attempt_comparison(
        self, user_id: str, submission_id: str
    ) -> dict[str, Any]:
        """
        Fetch the comparison between the original attempt and this attempt.

        Public endpoint — does not require the new attempt to be evaluated.
        """
        attempt_record = self._get_attempt_record(user_id, submission_id)
        if not attempt_record:
            raise NotFoundError("Attempt record not found")

        original_submission_id = attempt_record.get("attempt_group")
        return self._compare_attempts(
            user_id, original_submission_id, submission_id
        )

    def list_user_attempts(
        self, user_id: str, limit: int = 50
    ) -> dict[str, Any]:
        """List all writing attempt groups for a user (newest first)."""
        if self.db is None:
            return {"results": [], "total": 0}
        try:
            query = (
                self.db.table("writing_attempts")
                .select(
                    "*, original:writing_workspace_submissions!inner(*)"
                )
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
            )
            result = self.db.execute(
                query, "list writing attempts"
            )
            rows = result.data or []
        except Exception:  # noqa: BLE001
            return {"results": [], "total": 0}

        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            group_id = row.get("attempt_group")
            groups.setdefault(group_id, []).append(row)

        results = []
        for group_id, attempts in groups.items():
            attempts.sort(key=lambda a: a.get("attempt_number", 0))
            original = attempts[0].get("original") or {}
            results.append({
                "attempt_group": group_id,
                "title": original.get("title", ""),
                "task_type": original.get("task_type", "task_2"),
                "attempts": [
                    {
                        "submission_id": a.get("submission_id"),
                        "attempt_number": a.get("attempt_number"),
                        "overall_band": a.get("overall_band"),
                        "evaluated_at": a.get("evaluated_at"),
                        "bonus_xp": a.get("bonus_xp", 0),
                    }
                    for a in attempts
                ],
                "total_attempts": len(attempts),
            })

        return {"results": results, "total": len(results)}

    def _compare_attempts(
        self,
        user_id: str,
        original_submission_id: str,
        new_submission_id: str,
    ) -> dict[str, Any]:
        """Compare the original attempt vs the new attempt."""
        original_eval = self.writing_repo.get_evaluation(
            original_submission_id, user_id
        )
        new_eval = self.writing_repo.get_evaluation(
            new_submission_id, user_id
        )
        original_sub = self.writing_repo.get_submission(
            original_submission_id, user_id
        )
        new_sub = self.writing_repo.get_submission(
            new_submission_id, user_id
        )

        if not original_eval or not new_eval:
            return {"compared": False, "reason": "Missing evaluation data"}

        original_bands = original_eval.get("criteria_bands") or {}
        new_bands = new_eval.get("criteria_bands") or {}

        criteria_comparison = []
        for key in CRITERIA_KEYS:
            old_b = float(original_bands.get(key, 0.0))
            new_b = float(new_bands.get(key, 0.0))
            delta = round(new_b - old_b, 1)
            criteria_comparison.append({
                "criterion": key,
                "label": CRITERION_LABELS.get(key, key),
                "attempt_1_band": old_b,
                "attempt_2_band": new_b,
                "delta": delta,
                "improved": delta > 0,
            })

        old_overall = float(original_eval.get("overall_band") or 0.0)
        new_overall = float(new_eval.get("overall_band") or 0.0)
        overall_delta = round(new_overall - old_overall, 1)

        old_wc = int(original_sub.get("word_count") or 0) if original_sub else 0
        new_wc = int(new_sub.get("word_count") or 0) if new_sub else 0
        old_time = (
            int(original_sub.get("time_seconds_spent") or 0)
            if original_sub else 0
        )
        new_time = (
            int(new_sub.get("time_seconds_spent") or 0)
            if new_sub else 0
        )

        improved = (
            overall_delta >= IMPROVEMENT_BAND_THRESHOLD
            or any(
                c["delta"] >= IMPROVEMENT_BAND_THRESHOLD
                for c in criteria_comparison
            )
        )

        return {
            "compared": True,
            "original_submission_id": original_submission_id,
            "new_submission_id": new_submission_id,
            "overall_band": {
                "attempt_1": old_overall,
                "attempt_2": new_overall,
                "delta": overall_delta,
                "improved": overall_delta > 0,
            },
            "criteria": criteria_comparison,
            "word_count": {
                "attempt_1": old_wc,
                "attempt_2": new_wc,
                "delta": new_wc - old_wc,
            },
            "time_seconds": {
                "attempt_1": old_time,
                "attempt_2": new_time,
                "delta": new_time - old_time,
            },
            "improvement": improved,
        }

    # ------------------------------------------------------------------
    # Attempt record helpers
    # ------------------------------------------------------------------
    def _count_attempts(
        self, user_id: str, attempt_group: str
    ) -> int:
        """Count how many attempts exist for a given attempt group."""
        if self.db is None:
            return 0
        try:
            query = (
                self.db.table("writing_attempts")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("attempt_group", attempt_group)
            )
            result = self.db.execute(query, "count writing attempts")
            return result.count or 0
        except Exception:  # noqa: BLE001
            return 0

    def _create_attempt_record(
        self,
        user_id: str,
        attempt_group: str,
        submission_id: str,
        attempt_number: int,
    ) -> dict[str, Any] | None:
        """Insert a writing_attempts row linking an attempt to its group."""
        if self.db is None:
            return None
        try:
            payload = {
                "user_id": user_id,
                "attempt_group": attempt_group,
                "submission_id": submission_id,
                "attempt_number": attempt_number,
            }
            query = self.db.table("writing_attempts").insert(payload)
            result = self.db.execute(query, "create writing attempt record")
            if result.data:
                return result.data[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "failed to create attempt record user=%s: %s",
                user_id, exc,
            )
        return None

    def _get_attempt_record(
        self, user_id: str, submission_id: str
    ) -> dict[str, Any] | None:
        """Fetch the writing_attempts row for a given submission."""
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("writing_attempts")
                .select("*")
                .eq("user_id", user_id)
                .eq("submission_id", submission_id)
                .limit(1)
            )
            result = self.db.execute(query, "fetch writing attempt record")
            if result.data:
                return result.data[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "failed to fetch attempt record user=%s: %s",
                user_id, exc,
            )
        return None

    def _update_attempt_record(
        self,
        user_id: str,
        attempt_id: str,
        overall_band: float | None = None,
        bonus_xp: int = 0,
        bonus_reason: str | None = None,
    ) -> None:
        """Update an attempt record with evaluation results."""
        if self.db is None or not attempt_id:
            return
        try:
            payload: dict[str, Any] = {
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            }
            if overall_band is not None:
                payload["overall_band"] = overall_band
            if bonus_xp:
                payload["bonus_xp"] = bonus_xp
            if bonus_reason:
                payload["bonus_reason"] = bonus_reason
            query = (
                self.db.table("writing_attempts")
                .update(payload)
                .eq("id", attempt_id)
                .eq("user_id", user_id)
            )
            self.db.execute(query, "update writing attempt record")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "failed to update attempt record user=%s: %s",
                user_id, exc,
            )

    def _award_bonus_xp(
        self,
        user_id: str,
        submission_id: str,
        xp: int,
        reason: str,
    ) -> None:
        """Award bonus XP for improvement via the progress-tracking ledger."""
        try:
            self.progress_repo.log_session(
                user_id,
                {
                    "activity_date": date.today().isoformat(),  # noqa: DTZ011
                    "skill": "writing",
                    "session_type": "bonus",
                    "minutes": 0,
                    "xp_earned": xp,
                    "source_type": "writing_bonus",
                    "source_id": submission_id,
                    "meta": {"title": "Writing Improvement Bonus", "reason": reason},
                },
            )
            # Recompute streaks for the bonus.
            try:
                self.streak_repo.process_activity(
                    user_id, day=date.today()  # noqa: DTZ011
                )
            except Exception:  # noqa: BLE001, S110
                pass
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "failed to award bonus XP user=%s: %s", user_id, exc
            )
