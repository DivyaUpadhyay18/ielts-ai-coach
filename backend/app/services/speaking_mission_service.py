"""
Speaking Mission Integration Service.

Bridges the AI Speaking Evaluation (and the multi-step Speaking Practice Mission
flow) with the Mission System so that completing a speaking evaluation
automatically updates:

  - Mission progress  (marks the daily "Speaking Fluency Practice" mission complete)
  - XP & streak       (via ProgressTrackingRepository + StreakRepository)
  - Speaking performance (band history, per-criterion averages, improvement rate)
  - Predicted band     (feeds the latest speaking band into the PredictionEngine)
  - Readiness score    (updates the readiness_score used by the AI Mentor)
  - Weak-skill detection (updates per-skill bands for recommendation engine)
  - Resource recommendations (weak speaking criteria surface as targeted resources)
  - Adaptive schedule (speaking performance updates the daily plan)

The Speaking Practice Mission flow:

  Learn → Listen to Example → Understand Structure → Practice →
  Record → AI Evaluation → Review Feedback → Retry →
  Revision Notes → Complete Mission → Earn XP

All operations are defensive — if the mission system or progress tables are
not available, the evaluation is still stored and the service degrades
gracefully.

This service is called by:
  - SpeakingEvaluationEngine (after AI transcript evaluation)
  - SpeakingPracticeModeEngine (after practice session evaluation)
"""
import logging
from datetime import date
from typing import Any, Optional

from app.db.session import DatabaseSession
from app.repositories.daily_mission_repo import DailyMissionRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository
from app.services.prediction_engine import PredictionEngineService
from app.services.speaking_analytics_service import SpeakingAnalyticsService

logger = logging.getLogger(__name__)

# XP awarded for completing a speaking evaluation (mission reward).
SPEAKING_EVALUATION_XP = 30

# Minutes credited for the speaking mission (estimated effort).
SPEAKING_EVALUATION_MINUTES = 15

# Default speaking mission skill as defined in DailyMissionRepository.
SPEAKING_MISSION_SKILL = "speaking"

# Default speaking mission title (as defined in DailyMissionRepository templates).
SPEAKING_MISSION_TITLE = "Speaking Fluency Practice"


class SpeakingMissionService:
    """
    Integrates AI Speaking Evaluations with the Mission + Progress system.

    Called by SpeakingEvaluationEngine and SpeakingPracticeModeEngine
    after an evaluation is stored.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.progress_repo = ProgressTrackingRepository(db)
        self.streak_repo = StreakRepository(db)
        self.mission_repo = DailyMissionRepository(db)
        self.prediction_engine = PredictionEngineService(db)
        self.speaking_analytics = SpeakingAnalyticsService(db)

    def sync_after_evaluation(
        self,
        user_id: str,
        evaluation: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        After a speaking evaluation is stored, sync all downstream systems.

        Called by:
          - SpeakingEvaluationEngine (full AI evaluation of a transcript)
          - SpeakingPracticeModeEngine (practice session evaluation)

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
            "weakest_speaking_criterion": None,
        }

        eval_id = context.get("evaluation_id") if context else None
        response_id = context.get("response_id") if context else None
        session_id = context.get("session_id") if context else None

        # 1. Mark the daily speaking mission as complete + log XP/streak.
        try:
            self._complete_speaking_mission(user_id, evaluation)
            result["mission_completed"] = True
            result["xp_earned"] = SPEAKING_EVALUATION_XP
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "speaking mission sync failed user=%s: %s",
                user_id, exc,
            )

        # 2. Log a study session for this speaking evaluation (idempotent).
        try:
            duration_sec = int(evaluation.get("duration_seconds", 0) or 0)
            minutes = max(1, duration_sec // 60) if duration_sec else SPEAKING_EVALUATION_MINUTES
            evaluated_at = evaluation.get("evaluated_at") or ""
            activity_date = evaluated_at.split("T")[0] if evaluated_at else None
            self.progress_repo.log_session(
                user_id,
                {
                    "activity_date": activity_date or date.today().isoformat(),
                    "skill": "speaking",
                    "session_type": "mock_test",
                    "minutes": minutes,
                    "xp_earned": SPEAKING_EVALUATION_XP,
                    "source_type": "speaking_evaluation",
                    "source_id": eval_id or response_id or session_id or "",
                    "meta": {
                        "title": evaluation.get("title") or SPEAKING_MISSION_TITLE,
                        "overall_band": evaluation.get("overall_band"),
                        "confidence": evaluation.get("confidence"),
                        "part": evaluation.get("part", "part_1"),
                        "error_count": evaluation.get("error_count", 0),
                        "filler_words": evaluation.get("filler_words", 0),
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "speaking session logging failed user=%s: %s",
                user_id, exc,
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

        # 4. Detect weakest speaking skill from the evaluation.
        try:
            result["weakest_speaking_criterion"] = self._detect_weakest_speaking_criterion(evaluation)
            result["weakest_skill"] = result["weakest_speaking_criterion"]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "weak speaking skill detection failed user=%s: %s",
                user_id, exc,
            )

        # 5. Refresh speaking analytics context (for mentor / recommendations).
        try:
            _ = self.speaking_analytics.dashboard_brief(user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "speaking analytics refresh failed user=%s: %s",
                user_id, exc,
            )

        logger.info(
            "speaking mission sync complete user=%s band=%s xp=%s",
            user_id,
            evaluation.get("overall_band"),
            result["xp_earned"],
        )
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _complete_speaking_mission(
        self, user_id: str, evaluation: dict[str, Any]
    ) -> None:
        """
        Find today's pending/skipped Speaking mission and mark it completed,
        then run the streak engine.
        """
        today = date.today()
        missions = self.mission_repo.list_for_date(user_id, today)

        speaking_mission = None
        for m in missions:
            if m.get("skill") == SPEAKING_MISSION_SKILL:
                speaking_mission = m
                break

        if speaking_mission is None:
            # Create missions for today if they don't exist yet.
            self.mission_repo.generate_for_date(user_id, today)
            missions = self.mission_repo.list_for_date(user_id, today)
            for m in missions:
                if m.get("skill") == SPEAKING_MISSION_SKILL:
                    speaking_mission = m
                    break

        if speaking_mission and speaking_mission.get("status") != "completed":
            self.mission_repo.complete(speaking_mission["id"], user_id)

            # Process streaks (best-effort).
            try:
                mission_date = speaking_mission.get("mission_date")
                if mission_date and isinstance(mission_date, str):
                    mission_date = date.fromisoformat(mission_date[:10])
                else:
                    mission_date = today
                self.streak_repo.process_activity(user_id, day=mission_date)
            except Exception:  # noqa: BLE001
                logger.debug("speaking streak processing skipped", exc_info=True)

    @staticmethod
    def _detect_weakest_speaking_criterion(
        evaluation: dict[str, Any],
    ) -> Optional[str]:
        """
        Identify the weakest criterion from the evaluation's bands.

        Checks for criteria_bands dict (new format), criteria_detail (legacy
        format), or individual criterion band keys.
        """
        bands = evaluation.get("criteria_bands") or {}
        if not bands:
            detail = evaluation.get("criteria_detail") or {}
            bands = {
                k: v.get("band", 0.0) if isinstance(v, dict) else 0.0
                for k, v in detail.items()
            }
        if not bands:
            # Try individual keys (speaking_practice_sessions format).
            bands = {
                "fluency_coherence": evaluation.get("fluency_coherence_band") or
                                     evaluation.get("fluency_coherence", 0.0),
                "lexical_resource": evaluation.get("lexical_resource_band") or
                                    evaluation.get("lexical_resource", 0.0),
                "grammatical_range": evaluation.get("grammatical_range_band") or
                                     evaluation.get("grammatical_range", 0.0),
                "pronunciation": evaluation.get("pronunciation_band") or
                                   evaluation.get("pronunciation", 0.0),
            }

        valid_bands = {k: float(v) for k, v in bands.items() if v is not None and float(v) > 0}
        if not valid_bands:
            return None

        criterion_labels = {
            "fluency_coherence": "Fluency & Coherence",
            "lexical_resource": "Lexical Resource",
            "grammatical_range": "Grammatical Range & Accuracy",
            "grammatical_range_accuracy": "Grammatical Range & Accuracy",
            "pronunciation": "Pronunciation",
        }

        weakest_key = min(valid_bands, key=lambda k: valid_bands[k])
        return criterion_labels.get(weakest_key, weakest_key)