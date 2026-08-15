"""
Writing Mission Integration Service.

Bridges the AI Writing Evaluation with the Mission System so that completing
a writing evaluation automatically updates:

  - Mission progress  (marks the daily "Writing Task Practice" mission complete)
  - XP & streak       (via ProgressTrackingRepository + StreakRepository)
  - Writing performance (band history, estimated band, readiness score)
  - Prediction engine (feeds the latest writing band into the deterministic
    prediction model so estimated_band / readiness_score reflect recent essays)
  - Weak-skill detection (updates the per-skill bands used by the
    Recommendation Engine and AI Recommendations Service)
  - Resource recommendations (weak writing criteria surface as targeted
    resource suggestions)
  - Adaptive schedule (writing performance updates the daily plan)

All operations are defensive — if the mission system or progress tables are
not available, the evaluation is still stored and the service degrades
gracefully.
"""
import logging
from datetime import date
from typing import Any

from app.db.session import DatabaseSession
from app.repositories.daily_mission_repo import DailyMissionRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository
from app.repositories.writing_workspace_repo import WritingWorkspaceRepository
from app.services.prediction_engine import PredictionEngineService
from app.services.writing_analytics_service import WritingAnalyticsService

logger = logging.getLogger(__name__)

# XP awarded for completing a writing evaluation (mission reward).
WRITING_EVALUATION_XP = 30

# Minutes credited for the writing mission (estimated effort).
WRITING_EVALUATION_MINUTES = 30

# Default writing mission title as defined in DailyMissionRepository.
WRITING_MISSION_TITLE = "Writing Task Practice"


class WritingMissionService:
    """
    Integrates AI Writing Evaluations with the Mission + Progress system.

    Called by WritingEvaluationEngine after an evaluation is stored.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.writing_repo = WritingWorkspaceRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)
        self.streak_repo = StreakRepository(db)
        self.mission_repo = DailyMissionRepository(db)
        self.prediction_engine = PredictionEngineService(db)
        self.writing_analytics = WritingAnalyticsService(db)

    def sync_after_evaluation(
        self,
        user_id: str,
        submission_id: str,
        evaluation: dict[str, Any],
    ) -> dict[str, Any]:
        """
        After a writing evaluation is stored, sync all downstream systems.

        This is a best-effort orchestrator — individual failures are logged
        but never propagated so the evaluation API always returns the result.
        """
        result: dict[str, Any] = {
            "xp_earned": 0,
            "mission_completed": False,
            "streak_bonus": 0,
            "predicted_band": None,
            "readiness_score": None,
            "weakest_skill": None,
        }

        # 1. Mark the daily writing mission as complete + log XP/streak.
        try:
            self._complete_writing_mission(user_id, evaluation)
            result["mission_completed"] = True
            result["xp_earned"] = WRITING_EVALUATION_XP
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "writing mission sync failed user=%s submission=%s: %s",
                user_id, submission_id, exc,
            )

        # 2. Log a study session for this writing evaluation (idempotent).
        try:
            evaluated_at = evaluation.get("evaluated_at") or ""
            activity_date = evaluated_at.split("T")[0] if evaluated_at else None
            self.progress_repo.log_session(
                user_id,
                {
                    "activity_date": activity_date or date.today().isoformat(),
                    "skill": "writing",
                    "session_type": "mock_test",
                    "minutes": int(
                        evaluation.get("word_count", 0) // 50 * 5
                        or evaluation.get("time_seconds_spent", 0) // 60
                        or WRITING_EVALUATION_MINUTES
                    ),
                    "xp_earned": WRITING_EVALUATION_XP,
                    "source_type": "writing_evaluation",
                    "source_id": submission_id,
                    "meta": {
                        "title": WRITING_MISSION_TITLE,
                        "overall_band": evaluation.get("overall_band"),
                        "confidence": evaluation.get("confidence"),
                        "task_type": evaluation.get("task_type", "task_2"),
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "writing session logging failed user=%s submission=%s: %s",
                user_id, submission_id, exc,
            )

        # 3. Compute updated prediction (estimated band, readiness score).
        try:
            prediction = self.prediction_engine.get_prediction(user_id)
            result["predicted_band"] = prediction.get("estimated_band")
            result["readiness_score"] = prediction.get("readiness_score")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "prediction recompute failed user=%s: %s", user_id, exc,
            )

        # 4. Detect weakest writing skill from the evaluation.
        try:
            result["weakest_skill"] = self._detect_weakest_skill(evaluation)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "weak skill detection failed user=%s: %s", user_id, exc,
            )

        # 5. Refresh writing analytics context (for mentor / recommendations).
        try:
            _ = self.writing_analytics.context_brief(user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "writing analytics refresh failed user=%s: %s",
                user_id, exc,
            )

        logger.info(
            "writing mission sync complete user=%s submission=%s band=%s xp=%s",
            user_id, submission_id,
            evaluation.get("overall_band"),
            result["xp_earned"],
        )
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _complete_writing_mission(
        self, user_id: str, evaluation: dict[str, Any]
    ) -> None:
        """
        Find today's pending/skipped 'Writing Task Practice' mission and
        mark it completed, then run the streak engine.
        """
        today = date.today()
        missions = self.mission_repo.list_for_date(user_id, today)

        writing_mission = None
        for m in missions:
            if m.get("skill") == "writing":
                writing_mission = m
                break

        if writing_mission is None:
            # Create the mission if it doesn't exist yet.
            self.mission_repo.generate_for_date(user_id, today)
            missions = self.mission_repo.list_for_date(user_id, today)
            for m in missions:
                if m.get("skill") == "writing":
                    writing_mission = m
                    break

        if writing_mission and writing_mission.get("status") != "completed":
            self.mission_repo.complete(writing_mission["id"], user_id)

            # Process streaks (best-effort).
            try:
                mission_date = writing_mission.get("mission_date")
                if mission_date and isinstance(mission_date, str):
                    mission_date = date.fromisoformat(mission_date[:10])
                else:
                    mission_date = today
                self.streak_repo.process_activity(user_id, day=mission_date)
            except Exception:  # noqa: BLE001
                logger.debug("streak processing skipped", exc_info=True)

    @staticmethod
    def _detect_weakest_skill(evaluation: dict[str, Any]) -> str | None:
        """
        Identify the weakest criterion from the evaluation's criteria_bands.

        Returns the criterion key with the lowest band, or None if no
        bands are available (e.g., pending evaluation).
        """
        bands = evaluation.get("criteria_bands") or {}
        if not bands:
            detail = evaluation.get("criteria_detail") or {}
            bands = {
                k: v.get("band", 0.0) if isinstance(v, dict) else 0.0
                for k, v in detail.items()
            }
        if not bands:
            return None

        criterion_labels = {
            "task_response": "Writing Task Response",
            "coherence_cohesion": "Writing Coherence & Cohesion",
            "lexical_resource": "Writing Lexical Resource",
            "grammatical_range_accuracy": "Writing Grammar",
        }

        weakest_key = min(bands, key=lambda k: bands[k])
        return criterion_labels.get(weakest_key, weakest_key)
