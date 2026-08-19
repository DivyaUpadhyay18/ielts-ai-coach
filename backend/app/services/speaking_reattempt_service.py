"""
Speaking Reattempt Mode Service.

Provides the business logic for retrying a Speaking question after receiving
an evaluation.  The service:

  - Starts a reattempt from a previously-evaluated response (reuses the same
    prompt/part/topic, creates a new speaking_test_responses row linked to
    the original via attempt_group).
  - Evaluates the new attempt (runs AI evaluation + error analysis).
  - Compares attempt 1 vs attempt N (band, 4 criteria, time, fillers, errors).
  - Awards bonus XP for meaningful improvement (>=0.5 band overall or any
    criterion improving by >=0.5).
  - All operations are owner-scoped and degrade gracefully if the DB or
    mission system is unavailable.

The user's original responses are never overwritten.
"""
import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.speaking_test_repo import SpeakingTestRepository
from app.repositories.streak_repo import StreakRepository
from app.services.ai_service import (
    AIService,
    _SPEAKING_CRITERIA_KEYS,
    _SPEAKING_CRITERION_LABELS,
)
from app.services.speaking_mission_service import SpeakingMissionService

logger = logging.getLogger(__name__)

# XP bonus thresholds.
IMPROVEMENT_BAND_THRESHOLD = 0.5
IMPROVEMENT_BONUS_XP = 50


class SpeakingReattemptService:
    """
    Service for the Speaking Reattempt Mode lifecycle.

    All operations are owner-scoped.  Previous attempts are never modified.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.speaking_repo = SpeakingTestRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)
        self.streak_repo = StreakRepository(db)
        self.ai_service: AIService = AIService()
        self.mission_service = SpeakingMissionService(db)

    # ------------------------------------------------------------------
    # Attempt lifecycle
    # ------------------------------------------------------------------
    def start_reattempt(
        self, user_id: str, original_response_id: str
    ) -> dict[str, Any]:
        """
        Start a reattempt for a previously-evaluated speaking response.

        Creates a new speaking_test_responses row that reuses the original
        part, topic, and prompt, and records a speaking_attempts row linking
        the two.

        Raises:
            NotFoundError: if the original response doesn't exist or isn't owned.
            ValidationError: if the original response has no transcript or
                isn't eligible for reattempt.
        """
        original = self._get_response(original_response_id, user_id)
        if not original:
            raise NotFoundError("Speaking response not found")

        transcript = original.get("transcript") or ""
        if not transcript.strip():
            raise ValidationError(
                "The original response must have a transcript to reattempt."
            )

        if not original.get("is_saved"):
            raise ValidationError(
                "Only saved responses can be reattempted."
            )

        # Count existing attempts for this group.
        attempt_count = self._count_attempts(user_id, original_response_id)
        attempt_number = attempt_count + 1
        if attempt_number > 3:
            raise ValidationError(
                "Maximum 3 reattempts allowed for this response."
            )

        # Create a new draft response reusing the original prompt.
        new_response = self._create_response_copy(user_id, original, attempt_number)

        # Record the attempt linking the two.
        self._create_attempt_record(
            user_id, original_response_id, new_response["id"], attempt_number
        )

        logger.info(
            "speaking reattempt started user=%s original=%s attempt=%d",
            user_id, original_response_id, attempt_number,
        )
        return {
            "original_response_id": original_response_id,
            "response_id": new_response["id"],
            "attempt_number": attempt_number,
            "part": new_response.get("part"),
            "topic": new_response.get("title"),
        }

    async def evaluate_reattempt(
        self, user_id: str, response_id: str
    ) -> dict[str, Any]:
        """
        Evaluate a reattempt response and compute the comparison + bonus XP.

        Runs the AI evaluation and error analysis on the reattempt's transcript,
        then compares it to the original attempt, awards bonus XP if
        meaningful improvement is detected, and updates the attempt record.
        """
        new_response = self._get_response(response_id, user_id)
        if not new_response:
            raise NotFoundError("Reattempt response not found")
        if not new_response.get("is_saved"):
            raise ValidationError("Response must be saved before evaluation")

        attempt_record = self._get_attempt_record(user_id, response_id)
        if not attempt_record:
            raise NotFoundError("Attempt record not found")

        original_response_id = attempt_record.get("attempt_group")
        attempt_number = attempt_record.get("attempt_number", 1)

        original_response = self._get_response(original_response_id, user_id)
        original_analysis = self._get_analysis(original_response_id, user_id)

        transcript = new_response.get("transcript") or ""

        # Run AI evaluation on the reattempt transcript.
        ai_eval = await self.ai_service.analyze_speaking(transcript)
        ai_errors = await self.ai_service.analyze_speaking_errors(
            transcript=transcript,
            part=new_response.get("part", "part_1"),
            topic=new_response.get("title", ""),
        )

        # Build the attempt evaluation data.
        attempt_2_data = {
            "overall_band": ai_eval.get("overall_band", 6.0),
            "fluency_coherence_band": ai_eval.get("fluency_coherence_band", 6.0),
            "lexical_resource_band": ai_eval.get("lexical_resource_band", 6.0),
            "grammatical_range_band": ai_eval.get("grammatical_range_band", 6.0),
            "pronunciation_band": ai_eval.get("pronunciation_band", 6.0),
            "duration_seconds": new_response.get("duration_seconds", 0),
            "filler_words_count": self._count_fillers(transcript),
            "error_count": len(ai_errors.get("issues", [])),
        }

        attempt_1_data = self._build_attempt_1_data(original_response, original_analysis)

        # Compute comparison + bonus XP.
        comparison = self._compare_attempts(
            user_id, attempt_1_data, attempt_2_data, response_id,
            original_response_id, attempt_number,
        )

        bonus_xp = 0
        bonus_reason = None
        if comparison.get("improvement"):
            bonus_xp = IMPROVEMENT_BONUS_XP
            bonus_reason = "Meaningful improvement detected"
            self._award_bonus_xp(user_id, response_id, bonus_xp, bonus_reason)

        # Update the attempt record.
        self._update_attempt_record(
            user_id,
            attempt_record.get("id"),
            attempt_data=attempt_2_data,
            bonus_xp=bonus_xp,
            bonus_reason=bonus_reason,
        )

        # Sync downstream systems: mission progress, XP, streak, prediction,
        # readiness score, weak-skill detection, and adaptive scheduling.
        await self._sync_mission_after_reattempt(
            user_id, ai_eval, comparison, response_id, attempt_number
        )

        return {
            "evaluation": ai_eval,
            "comparison": comparison,
            "attempt_number": attempt_number,
            "bonus_xp": bonus_xp,
            "bonus_reason": bonus_reason,
        }

    async def _sync_mission_after_reattempt(
        self,
        user_id: str,
        ai_eval: dict[str, Any],
        comparison: dict[str, Any],
        response_id: str,
        attempt_number: int,
    ) -> None:
        """Sync downstream systems after a reattempt evaluation."""
        try:
            evaluation = {
                **ai_eval,
                **{f"{k}_band": v for k, v in ai_eval.items() if k.endswith("_band")},
                "error_count": len(comparison.get("focus_next", [])),
            }
            self.mission_service.sync_after_evaluation(
                user_id,
                evaluation,
                context={
                    "evaluation_id": response_id,
                    "attempt_number": attempt_number,
                    "comparison": comparison,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "speaking reattempt mission sync skipped user=%s: %s",
                user_id, exc,
            )

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------
    def get_attempt_comparison(
        self, user_id: str, response_id: str
    ) -> dict[str, Any]:
        """
        Fetch the comparison between the original attempt and the latest attempt.

        Public endpoint — does not require re-evaluation.
        """
        attempt_record = self._get_attempt_record(user_id, response_id)
        if not attempt_record:
            raise NotFoundError("Attempt record not found")

        original_response_id = attempt_record.get("attempt_group")
        original_response = self._get_response(original_response_id, user_id)
        original_analysis = self._get_analysis(original_response_id, user_id)

        attempt_1_data = self._build_attempt_1_data(original_response, original_analysis)
        attempt_2_data = {
            "overall_band": attempt_record.get("overall_band", 0.0),
            "fluency_coherence_band": attempt_record.get("fluency_coherence_band", 0.0),
            "lexical_resource_band": attempt_record.get("lexical_resource_band", 0.0),
            "grammatical_range_band": attempt_record.get("grammatical_range_band", 0.0),
            "pronunciation_band": attempt_record.get("pronunciation_band", 0.0),
            "duration_seconds": attempt_record.get("duration_seconds", 0),
            "filler_words_count": attempt_record.get("filler_words_count", 0),
            "error_count": attempt_record.get("error_count", 0),
        }

        return self._compare_attempts(
            user_id, attempt_1_data, attempt_2_data,
            response_id, original_response_id,
            attempt_record.get("attempt_number", 1),
            use_stored=True,
        )

    def list_user_attempts(
        self, user_id: str, limit: int = 50
    ) -> dict[str, Any]:
        """List all speaking attempt groups for a user (newest first)."""
        if self.db is None:
            return {"results": [], "total": 0}
        try:
            query = (
                self.db.table("speaking_attempts")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
            )
            result = self.db.execute(query, "list speaking attempts")
            rows = result.data or []
        except Exception:
            return {"results": [], "total": 0}

        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            group_id = row.get("attempt_group")
            groups.setdefault(group_id, []).append(row)

        results = []
        for group_id, attempts in groups.items():
            attempts.sort(key=lambda a: a.get("attempt_number", 0))
            first = attempts[0]
            results.append({
                "attempt_group": group_id,
                "part": first.get("response") and isinstance(first.get("response"), dict)
                    and first["response"].get("part", "part_1"),
                "attempts": [
                    {
                        "response_id": a.get("response_id"),
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

    # ------------------------------------------------------------------
    # Internal comparison logic
    # ------------------------------------------------------------------
    def _compare_attempts(
        self,
        user_id: str,
        attempt_1_data: Dict[str, Any],
        attempt_2_data: Dict[str, Any],
        response_id: str,
        original_response_id: str,
        attempt_number: int,
        use_stored: bool = False,
    ) -> dict[str, Any]:
        """Compare two speaking attempts using criterion + metric deltas."""
        criteria_comparison = []
        improved_criteria = []
        worsened_criteria = []
        unchanged_criteria = []

        for key in _SPEAKING_CRITERIA_KEYS:
            old_b = float(attempt_1_data.get(key, 0.0) or 0.0)
            new_b = float(attempt_2_data.get(key, 0.0) or 0.0)
            delta = round(new_b - old_b, 1)
            label = _SPEAKING_CRITERION_LABELS.get(key, key)
            criteria_comparison.append({
                "criterion": key,
                "label": label,
                "attempt_1_band": old_b,
                "attempt_2_band": new_b,
                "delta": delta,
                "improved": delta > 0,
            })
            if delta > 0:
                improved_criteria.append(label)
            elif delta < 0:
                worsened_criteria.append(label)
            else:
                unchanged_criteria.append(label)

        old_overall = float(attempt_1_data.get("overall_band", 0.0) or 0.0)
        new_overall = float(attempt_2_data.get("overall_band", 0.0) or 0.0)
        overall_delta = round(new_overall - old_overall, 1)

        old_dur = int(attempt_1_data.get("duration_seconds", 0) or 0)
        new_dur = int(attempt_2_data.get("duration_seconds", 0) or 0)

        old_fillers = int(attempt_1_data.get("filler_words_count", 0) or 0)
        new_fillers = int(attempt_2_data.get("filler_words_count", 0) or 0)

        old_errors = int(attempt_1_data.get("error_count", 0) or 0)
        new_errors = int(attempt_2_data.get("error_count", 0) or 0)

        improved = (
            overall_delta >= IMPROVEMENT_BAND_THRESHOLD
            or any(
                c["delta"] >= IMPROVEMENT_BAND_THRESHOLD
                for c in criteria_comparison
            )
        )

        # Generate natural-language comparison via AI (with fallback).
        ai_comparison = asyncio_run_safe(
            self.ai_service.generate_speaking_reattempt_comparison(
                attempt_1_data, attempt_2_data
            )
        )

        return {
            "compared": True,
            "original_response_id": original_response_id,
            "latest_response_id": response_id,
            "latest_attempt_number": attempt_number,
            "overall_band": {
                "attempt_1": old_overall,
                "attempt_2": new_overall,
                "delta": overall_delta,
                "improved": overall_delta > 0,
            },
            "criteria": criteria_comparison,
            "duration_seconds": {
                "attempt_1": old_dur,
                "attempt_2": new_dur,
                "delta": new_dur - old_dur,
            },
            "filler_words": {
                "attempt_1": old_fillers,
                "attempt_2": new_fillers,
                "delta": new_fillers - old_fillers,
            },
            "error_count": {
                "attempt_1": old_errors,
                "attempt_2": new_errors,
                "delta": new_errors - old_errors,
            },
            "improved_criteria": improved_criteria,
            "worsened_criteria": worsened_criteria,
            "unchanged_criteria": unchanged_criteria,
            "what_improved": ai_comparison.get("what_improved", []),
            "what_stayed_the_same": ai_comparison.get("what_stayed_the_same", []),
            "what_became_worse": ai_comparison.get("what_became_worse", []),
            "focus_next": ai_comparison.get("focus_next", []),
            "bonus_xp": 0,
            "bonus_reason": None,
            "improvement": improved,
        }

    def _build_attempt_1_data(
        self,
        response: Optional[Dict[str, Any]],
        analysis: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build attempt-1 evaluation data from the response + its error analysis."""
        if analysis:
            return {
                "overall_band": analysis.get("overall_band", 6.0),
                "fluency_coherence_band": analysis.get("fluency_coherence_band", 6.0),
                "lexical_resource_band": analysis.get("lexical_resource_band", 6.0),
                "grammatical_range_band": analysis.get("grammatical_range_band", 6.0),
                "pronunciation_band": analysis.get("pronunciation_band", 6.0),
                "duration_seconds": response.get("duration_seconds", 0) if response else 0,
                "filler_words_count": analysis.get("issue_count", 0),
                "error_count": len(analysis.get("issues", []) or []),
            }
        return {
            "overall_band": float(response.get("overall_band", 6.0) or 6.0) if response else 6.0,
            "fluency_coherence_band": float(response.get("fluency_coherence_band", 6.0) or 6.0) if response else 6.0,
            "lexical_resource_band": float(response.get("lexical_resource_band", 6.0) or 6.0) if response else 6.0,
            "grammatical_range_band": float(response.get("grammatical_range_band", 6.0) or 6.0) if response else 6.0,
            "pronunciation_band": float(response.get("pronunciation_band", 6.0) or 6.0) if response else 6.0,
            "duration_seconds": response.get("duration_seconds", 0) if response else 0,
            "filler_words_count": 0,
            "error_count": 0,
        }

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    def _get_response(self, response_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a speaking_test_responses row (owner-scoped)."""
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("speaking_test_responses")
                .select("*")
                .eq("id", response_id)
                .eq("user_id", user_id)
                .limit(1)
            )
            result = self.db.execute(query, "fetch speaking response for reattempt")
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _get_analysis(
        self, response_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch the most recent speaking error analysis for a response."""
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("speaking_error_analysis")
                .select("*")
                .eq("response_id", response_id)
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(1)
            )
            result = self.db.execute(query, "fetch speaking error analysis")
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _count_attempts(self, user_id: str, attempt_group: str) -> int:
        """Count how many attempts exist for a given attempt group."""
        if self.db is None:
            return 0
        try:
            query = (
                self.db.table("speaking_attempts")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("attempt_group", attempt_group)
            )
            result = self.db.execute(query, "count speaking attempts")
            return result.count or 0
        except Exception:
            return 0

    def _create_response_copy(
        self, user_id: str, original: Dict[str, Any], attempt_number: int
    ) -> Dict[str, Any]:
        """Create a new speaking_test_responses row reusing the original prompt."""
        payload = {
            "user_id": user_id,
            "session_id": original.get("session_id"),
            "part": original.get("part", "part_1"),
            "title": original.get("title", ""),
            "prompt_id": original.get("prompt_id"),
            "audio_url": None,
            "transcript": original.get("transcript", ""),
            "duration_seconds": 0,
            "is_saved": False,
            "status": "draft",
            "attempt_number": attempt_number,
        }
        query = self.db.table("speaking_test_responses").insert(payload)
        result = self.db.execute(query, "create speaking reattempt response")
        if not result.data:
            raise NotFoundError("Failed to create reattempt response")
        return result.data[0]

    def _create_attempt_record(
        self,
        user_id: str,
        attempt_group: str,
        response_id: str,
        attempt_number: int,
    ) -> Optional[Dict[str, Any]]:
        """Insert a speaking_attempts row linking an attempt to its group."""
        if self.db is None:
            return None
        try:
            payload = {
                "user_id": user_id,
                "attempt_group": attempt_group,
                "response_id": response_id,
                "attempt_number": attempt_number,
            }
            query = self.db.table("speaking_attempts").insert(payload)
            result = self.db.execute(query, "create speaking attempt record")
            if result.data:
                return result.data[0]
        except Exception as exc:
            logger.warning("failed to create speaking attempt record user=%s: %s", user_id, exc)
        return None

    def _get_attempt_record(
        self, user_id: str, response_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch the speaking_attempts row for a given response."""
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("speaking_attempts")
                .select("*")
                .eq("user_id", user_id)
                .eq("response_id", response_id)
                .limit(1)
            )
            result = self.db.execute(query, "fetch speaking attempt record")
            if result.data:
                return result.data[0]
        except Exception as exc:
            logger.warning("failed to fetch speaking attempt record user=%s: %s", user_id, exc)
        return None

    def _update_attempt_record(
        self,
        user_id: str,
        attempt_id: str,
        attempt_data: Optional[Dict[str, Any]] = None,
        bonus_xp: int = 0,
        bonus_reason: Optional[str] = None,
    ) -> None:
        """Update an attempt record with evaluation results."""
        if self.db is None or not attempt_id:
            return
        try:
            payload: dict[str, Any] = {
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            }
            if attempt_data:
                payload["overall_band"] = attempt_data.get("overall_band")
                payload["fluency_coherence_band"] = attempt_data.get("fluency_coherence_band")
                payload["lexical_resource_band"] = attempt_data.get("lexical_resource_band")
                payload["grammatical_range_band"] = attempt_data.get("grammatical_range_band")
                payload["pronunciation_band"] = attempt_data.get("pronunciation_band")
                payload["duration_seconds"] = attempt_data.get("duration_seconds")
                payload["filler_words_count"] = attempt_data.get("filler_words_count", 0)
                payload["error_count"] = attempt_data.get("error_count", 0)
            if bonus_xp:
                payload["bonus_xp"] = bonus_xp
            if bonus_reason:
                payload["bonus_reason"] = bonus_reason
            query = (
                self.db.table("speaking_attempts")
                .update(payload)
                .eq("id", attempt_id)
                .eq("user_id", user_id)
            )
            self.db.execute(query, "update speaking attempt record")
        except Exception as exc:
            logger.warning("failed to update speaking attempt record user=%s: %s", user_id, exc)

    def _award_bonus_xp(
        self,
        user_id: str,
        response_id: str,
        xp: int,
        reason: str,
    ) -> None:
        """Award bonus XP for improvement via the progress-tracking ledger."""
        try:
            self.progress_repo.log_session(
                user_id,
                {
                    "activity_date": date.today().isoformat(),
                    "skill": "speaking",
                    "session_type": "bonus",
                    "minutes": 0,
                    "xp_earned": xp,
                    "source_type": "speaking_bonus",
                    "source_id": response_id,
                    "meta": {"title": "Speaking Improvement Bonus", "reason": reason},
                },
            )
            try:
                self.streak_repo.process_activity(
                    user_id, day=date.today()
                )
            except Exception:
                pass
        except Exception as exc:
            logger.warning("failed to award speaking bonus XP user=%s: %s", user_id, exc)

    @staticmethod
    def _count_fillers(transcript: str) -> int:
        """Count common filler words in a transcript."""
        import re
        if not transcript:
            return 0
        fillers = [
            "um", "uh", "er", "ah", "like", "you know", "i mean",
            "i think", "i guess", "well",
        ]
        count = 0
        lowered = transcript.lower()
        for filler in fillers:
            count += len(re.findall(rf"\b{re.escape(filler)}\b", lowered))
        return count


def _count_fillers(transcript: str) -> int:
    """Module-level filler counter (used by AI service)."""
    service = SpeakingReattemptService(db=None)
    return service._count_fillers(transcript)


def asyncio_run_safe(coro):
    """Run an async coroutine synchronously, returning {} on failure."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside a running event loop (e.g. inside asyncio.run).
            # Use a new loop in a separate thread.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        pass
    except Exception:
        return {}
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    except Exception:
        return {}
