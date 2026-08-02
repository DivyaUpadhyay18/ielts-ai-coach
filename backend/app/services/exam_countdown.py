"""
Exam Countdown service.

Computes real-time countdown metrics for a user's IELTS exam:
  - Days remaining until exam
  - Weeks remaining (rounded)
  - Study hours remaining (planned - completed)
  - Planned study hours (total scheduled task minutes / 60)
  - Completed study hours (total completed task minutes / 60)
  - Completion percentage (completed / planned)
  - Intensity level (normal / focused / intensive / final)

When the exam date changes, the service automatically triggers a study plan
regeneration via the StudyPlanGenerator and records the update in the
schedule_runs audit trail.

No AI. All calculations are deterministic from stored data.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.daily_plan_repo import DailyPlanRepository
from app.repositories.study_plan_repo import StudyPlanRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.services.schedule_history_service import schedule_history_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INTENSITY_FINAL_DAYS = 14        # < 14 days → "final"
INTENSITY_INTENSIVE_DAYS = 30    # < 30 days → "intensive"
INTENSITY_FOCUSED_DAYS = 60      # < 60 days → "focused"
# else → "normal"


class ExamCountdownService:
    """Deterministic exam countdown + auto-regeneration service."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.study_plan_repo = StudyPlanRepository(db)
        self.daily_plan_repo = DailyPlanRepository(db)
        self.task_repo = TaskRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_countdown(self, user_id: str, run_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Compute the full countdown payload for a user.

        Returns:
            {
                "exam_date": "2025-08-15",
                "today": "2025-06-02",
                "days_remaining": 74,
                "weeks_remaining": 11,
                "study_hours": {
                    "planned": 120.0,
                    "completed": 45.5,
                    "remaining": 74.5
                },
                "completion_percentage": 37.9,
                "intensity": "focused",
                "has_active_plan": true,
                "study_plan_id": "...",
                "study_plan_version": 1
            }
        """
        today = run_date or date.today()
        user = self._safe_get_profile(user_id)

        if not user:
            raise NotFoundError("User not found")

        exam_raw = user.get("exam_date")
        if not exam_raw:
            raise ValidationError(
                "Set your exam date in onboarding before the countdown can be computed."
            )

        exam_date = self._parse_date(exam_raw)
        days_remaining = max((exam_date - today).days, 0)
        weeks_remaining = round(days_remaining / 7) if days_remaining > 0 else 0

        # ---- Study hours from active plan --------------------------------
        study_plan = self._safe_get_active_plan(user_id)
        study_plan_id = study_plan.get("id") if study_plan else None
        study_plan_version = int(study_plan.get("version", 0)) if study_plan else 0

        planned_minutes = 0
        completed_minutes = 0

        if study_plan_id:
            planned_minutes, completed_minutes = self._compute_study_hours(
                user_id, study_plan_id
            )

        planned_hours = round(planned_minutes / 60.0, 1)
        completed_hours = round(completed_minutes / 60.0, 1)
        remaining_hours = round(max(planned_hours - completed_hours, 0.0), 1)

        completion_percentage = 0.0
        if planned_hours > 0:
            completion_percentage = round(
                (completed_hours / planned_hours) * 100, 1
            )
            completion_percentage = min(completion_percentage, 100.0)

        intensity = self._intensity(days_remaining)

        return {
            "exam_date": exam_date.isoformat(),
            "today": today.isoformat(),
            "days_remaining": days_remaining,
            "weeks_remaining": weeks_remaining,
            "study_hours": {
                "planned": planned_hours,
                "completed": completed_hours,
                "remaining": remaining_hours,
            },
            "completion_percentage": completion_percentage,
            "intensity": intensity,
            "has_active_plan": study_plan_id is not None,
            "study_plan_id": study_plan_id,
            "study_plan_version": study_plan_version,
        }

    def update_exam_date(
        self,
        user_id: str,
        new_exam_date: date,
        auto_regenerate: bool = True,
    ) -> Dict[str, Any]:
        """
        Update the user's exam date and optionally auto-regenerate the study plan.

        When auto_regenerate=True (default), the active study plan is archived
        and a new one is generated for the updated timeline. The regeneration
        is recorded in the schedule_runs audit trail.

        Returns:
            {
                "exam_date": "2025-09-20",
                "previous_exam_date": "2025-08-15",
                "regenerated": true,
                "new_study_plan_id": "...",
                "new_study_plan_version": 2,
                "message": "Exam date updated and study plan regenerated."
            }
        """
        today = date.today()
        if new_exam_date <= today:
            raise ValidationError("Exam date must be in the future.")

        user = self._safe_get_profile(user_id)
        if not user:
            raise NotFoundError("User not found")

        previous_exam_raw = user.get("exam_date")
        previous_exam_date = self._parse_date(previous_exam_raw) if previous_exam_raw else None

        # ---- Update the user's exam_date --------------------------------
        self.user_repo.update_goals(user_id, {"exam_date": new_exam_date.isoformat()})
        logger.info(
            "countdown.update_exam_date user=%s old=%s new=%s",
            user_id,
            previous_exam_date.isoformat() if previous_exam_date else None,
            new_exam_date.isoformat(),
        )

        result: Dict[str, Any] = {
            "exam_date": new_exam_date.isoformat(),
            "previous_exam_date": previous_exam_date.isoformat() if previous_exam_date else None,
            "regenerated": False,
            "new_study_plan_id": None,
            "new_study_plan_version": None,
            "message": "Exam date updated.",
        }

        # Capture schedule snapshot before changes
        previous_schedule = self._capture_schedule_snapshot(user_id)

        # ---- Auto-regenerate study plan if requested --------------------
        if auto_regenerate:
            regen_result = self._regenerate_plan_for_new_exam(
                user_id=user_id,
                user=user,
                new_exam_date=new_exam_date,
            )
            if regen_result:
                result["regenerated"] = True
                result["new_study_plan_id"] = regen_result.get("study_plan_id")
                result["new_study_plan_version"] = regen_result.get("version")
                result["message"] = "Exam date updated and study plan regenerated."

                # Capture new schedule snapshot after regeneration
                new_schedule = self._capture_schedule_snapshot(user_id)

                # Log to schedule history
                try:
                    asyncio.run(
                        schedule_history_service.log_exam_date_update(
                            user_id=user_id,
                            previous_exam_date=previous_exam_date.isoformat() if previous_exam_date else "N/A",
                            new_exam_date=new_exam_date.isoformat(),
                            previous_schedule=previous_schedule,
                            new_schedule=new_schedule,
                            metrics_before={},
                            metrics_after={},
                            study_plan_id=regen_result.get("study_plan_id"),
                            auto_regenerated=True,
                        )
                    )
                except Exception as exc:
                    logger.warning("schedule_history.log_exam_date_update failed user=%s: %s", user_id, exc)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _compute_study_hours(
        self, user_id: str, study_plan_id: str
    ) -> Tuple[int, int]:
        """
        Compute total planned and completed minutes across all tasks in the
        active study plan.

        Returns (planned_minutes, completed_minutes).
        """
        if self.db is None:
            return (0, 0)

        daily_plans = self.daily_plan_repo.list_for_study_plan(user_id, study_plan_id)
        if not daily_plans:
            return (0, 0)

        planned = 0
        completed = 0
        for dp in daily_plans:
            tasks = self.task_repo.list_for_user(
                user_id=user_id, daily_plan_id=dp["id"]
            )
            for t in tasks:
                duration = int(t.get("duration_minutes") or 0)
                planned += duration
                if t.get("status") == "completed":
                    completed += duration

        return (planned, completed)

    def _regenerate_plan_for_new_exam(
        self,
        user_id: str,
        user: Dict[str, Any],
        new_exam_date: date,
    ) -> Optional[Dict[str, Any]]:
        """
        Archive the active plan and generate a new one for the updated exam date.

        Delegates to StudyPlanGenerator. Returns the new plan dict or None
        if regeneration fails or there's insufficient profile data.
        """
        if self.db is None:
            return None

        try:
            from app.services.study_plan_generator import StudyPlanGenerator
            from app.models.study_plan_engine import StudyPlanGenerateRequest

            # Extract profile fields needed for regeneration.
            current_band = float(user.get("current_band") or 5.5)
            target_band = float(user.get("target_band") or 7.0)
            daily_budget = int(user.get("daily_minutes_budget") or 60)
            module = user.get("module") or "academic"

            # Extract weakest/strongest skills from preferences or meta.
            prefs = user.get("preferences") or {}
            weak = prefs.get("weakest_skills") or []
            strong = prefs.get("strongest_skills") or []

            # If no skill info, derive from band gap (generic).
            if not weak:
                weak = ["writing", "speaking"]
            if not strong:
                strong = ["reading", "listening"]

            request = StudyPlanGenerateRequest(
                exam_date=new_exam_date,
                target_band=target_band,
                current_band=current_band,
                daily_minutes_budget=daily_budget,
                module=module,
                weakest_skills=list(weak),
                strongest_skills=list(strong),
                start_date=date.today(),
            )

            generator = StudyPlanGenerator(self.db)
            result = generator.generate(user_id, request)
            return result

        except Exception as exc:
            logger.warning("countdown auto-regeneration failed user=%s: %s", user_id, exc)
            return None

    @staticmethod
    def _intensity(days_remaining: int) -> str:
        """Map remaining days to a preparation-intensity label."""
        if days_remaining < INTENSITY_FINAL_DAYS:
            return "final"
        if days_remaining < INTENSITY_INTENSIVE_DAYS:
            return "intensive"
        if days_remaining < INTENSITY_FOCUSED_DAYS:
            return "focused"
        return "normal"

    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)[:10]).date()

    def _capture_schedule_snapshot(self, user_id: str) -> Dict[str, Any]:
        """Capture a snapshot of the current schedule for history tracking."""
        if self.db is None:
            return {}

        try:
            study_plan = self._safe_get_active_plan(user_id)
            study_plan_id = study_plan.get("id") if study_plan else None
            if not study_plan_id:
                return {"study_plan_id": None, "tasks": []}

            daily_plans = self.daily_plan_repo.list_for_study_plan(user_id, study_plan_id)
            tasks = []
            for dp in daily_plans:
                day_tasks = self.task_repo.list_for_user(
                    user_id=user_id, daily_plan_id=dp["id"]
                )
                for t in day_tasks:
                    tasks.append({
                        "id": t.get("id"),
                        "title": t.get("title"),
                        "scheduled_date": t.get("scheduled_date"),
                        "status": t.get("status"),
                        "duration_minutes": t.get("duration_minutes"),
                        "priority": t.get("priority"),
                        "skill": t.get("skill"),
                        "task_type": t.get("task_type"),
                    })

            return {
                "study_plan_id": study_plan_id,
                "captured_at": date.today().isoformat(),
                "tasks": tasks,
            }
        except Exception as exc:
            logger.warning("schedule_history._capture_schedule_snapshot failed user=%s: %s", user_id, exc)
            return {}

    # ------------------------------------------------------------------
    # Safe DB wrappers
    # ------------------------------------------------------------------
    def _safe_get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.user_repo.get_profile(user_id)
        except NotFoundError:
            return None

    def _safe_get_active_plan(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        return self.study_plan_repo.get_active(user_id)


# Singleton bound to the shared DB session.
from app.db.session import db_session

exam_countdown_service = ExamCountdownService(db_session)