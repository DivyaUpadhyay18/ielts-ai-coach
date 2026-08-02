"""
Deterministic Adaptive Scheduler service.

This is the core intelligence of IELTS AI Coach (per SCHEDULER.md). It runs
at midnight or on app open and rebalances a user's study plan based purely
on stored data:

  - Detects overdue (pending/in_progress) tasks scheduled before today
  - Marks them 'missed' and carries them forward as clones with lineage
  - Protects revision / mock / rest days from being overwritten
  - Keeps mock tests scheduled before or on the exam date
  - Recalculates daily workload (clamped to ~1.2x the user's base budget,
    up to 2x in the final 14-day crunch window)
  - Spreads daily overload (>1.5x) to the next available days
  - Drops the lowest-priority tasks on weekly overload (>1.3x)
  - Activates streak-saver mode after 3+ consecutive missed days
  - Records every change with a human-readable "reason" so the UI can show
    "what changed & why"
  - Is idempotent: a second run on the same date+trigger returns the
    existing run instead of double-carrying tasks

No AI, no randomness. Safe to run repeatedly.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.models.scheduler import SchedulerMetrics
from app.repositories.daily_plan_repo import DailyPlanRepository
from app.repositories.scheduler_repo import SchedulerRepository
from app.repositories.study_plan_repo import StudyPlanRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.services.schedule_history_service import schedule_history_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants (from SCHEDULER.md + study_plan_generator)
# ---------------------------------------------------------------------------
BASE_BUDGET_FACTOR_MIN = 0.5          # never drop below 50% of base budget
BASE_BUDGET_FACTOR_MAX = 1.2          # never exceed 120% of base budget
CRUNCH_BUDGET_FACTOR_MAX = 2.0        # final 14 days: allow up to 2x base
CRUNCH_DAYS = 14                      # final-stretch window
FINAL_REVISION_DAYS = 14              # protected final revision window
MAX_SHIFT_DAYS = 14                   # max days to look for a slot
MOCK_BEFORE_EXAM_GUARD_DAYS = 1       # mocks must land at least 1 day pre-exam
OVERLOAD_RATIO_THRESHOLD = 1.3        # weekly overload trigger
DAILY_OVERLOAD_RATIO_THRESHOLD = 1.5  # daily overload trigger
DEPRIORITIZE_PROPORTION = 0.2         # drop bottom 20% of non-required tasks
STREAK_SAVER_THRESHOLD = 3            # consecutive missed days to trigger saver
STREAK_SAVER_MIN_TASKS = 1            # minimum viable day task count
MIN_TASK_DURATION = 10                # smallest splittable task slice
SPLITTABLE_TASK_THRESHOLD = 30        # only tasks > 30min can be split

# Smart Carry Forward tuning
MERGE_SIMILAR_SKILLS = True           # merge tasks with same skill when possible
MAX_MERGE_DURATION = 60               # don't merge beyond 60 minutes
DIFFICULTY_WEIGHT = 1.5               # weight for difficulty in scoring
PRIORITY_WEIGHT = 2.0                 # weight for priority in scoring
REVISION_PROTECTION_BONUS = 3         # priority boost for revision tasks
MOCK_PROTECTION_BONUS = 4             # priority boost for mock tasks


class AdaptiveSchedulerService:
    """Deterministic, no-AI adaptive scheduler."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.study_plan_repo = StudyPlanRepository(db)
        self.daily_plan_repo = DailyPlanRepository(db)
        self.task_repo = TaskRepository(db)
        self.scheduler_repo = SchedulerRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def run(
        self,
        user_id: str,
        trigger_type: str = "midnight",
        run_date: Optional[date] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a full scheduler rollover for a user.

        If persist=False this is a dry-run ("explain" mode) — nothing is
        written and the returned payload reports what WOULD change.

        Idempotency: if a run already exists for (user, run_date, trigger_type)
        and persist=True, the existing run is returned instead of re-executing.
        """
        today = run_date or date.today()

        # ---- Idempotency guard (persisted runs only) --------------------
        if persist:
            existing = self._safe_get_run_for_date(user_id, today, trigger_type)
            if existing:
                logger.info(
                    "scheduler.run idempotent skip user=%s date=%s trigger=%s",
                    user_id, today.isoformat(), trigger_type,
                )
                return self._build_existing_run_response(existing, user_id)

        user = self._safe_get_profile(user_id)

        # ---- Guard: must have a future exam date to schedule against ------
        exam_raw = user.get("exam_date") if user else None
        exam_date = self._parse_date(exam_raw) if exam_raw else None
        if not exam_date:
            raise ValidationError(
                "Set your exam date in onboarding before the scheduler can rebalance your plan."
            )
        if exam_date < today:
            # Post-exam: no rescheduling — return neutral run.
            return self._build_neutral(user_id, today, trigger_type, "exam_date_passed")

        # ---- Load active plan (if any) -----------------------------------
        study_plan = self._safe_get_active_plan(user_id)
        study_plan_id = study_plan.get("id") if study_plan else None
        if not study_plan_id:
            return self._build_neutral(
                user_id, today, trigger_type, "no_active_plan",
                note="Generate a study plan first so the scheduler can keep it on track.",
                exam_date=exam_date,
            )

        # ---- Workload metrics --------------------------------------------
        base_budget = int((user or {}).get("daily_minutes_budget") or 60)
        days_remaining = max((exam_date - today).days, 0)

        adjustments: List[Dict[str, Any]] = []
        tp: Dict[str, Any] = {
            "total_pending": 0,
            "completed_yesterday": 0,
            "missed_yesterday": 0,
            "carried_forward": 0,
            "rescheduled": 0,
            "deprioritized": 0,
            "merged": 0,
        }
        tp["completed_yesterday"] = self._count_completed_on_day(user_id, today - timedelta(days=1))

        # ---- 1. Detect overdue tasks -------------------------------------
        overdue = self._safe_list_pending_before(user_id, today)
        tp["total_pending"] = len(
            self._safe_list_for_user(user_id=user_id, status="pending")
        )
        tp["missed_yesterday"] = len(overdue)

        # ---- Streak-saver detection (Section 9.4) ------------------------
        consecutive_missed = self._safe_count_consecutive_missed(user_id, today)
        streak_saver_mode = consecutive_missed >= STREAK_SAVER_THRESHOLD
        if streak_saver_mode:
            logger.info(
                "scheduler streak-saver activated user=%s consecutive_missed=%d",
                user_id, consecutive_missed,
            )

        # ---- 2. Smart Carry-forward overdue tasks ------------------------
        overdue_sorted = self._sort_by_priority(overdue)
        for task in overdue_sorted:
            action = self._smart_handle_overdue(
                user_id=user_id,
                task=task,
                today=today,
                exam_date=exam_date,
                base_budget=base_budget,
                streak_saver_mode=streak_saver_mode,
            )
            if action:
                adjustments.append(action)
                action_type = action.get("action")
                if action_type == "carried_forward":
                    tp["carried_forward"] = tp.get("carried_forward", 0) + 1
                elif action_type == "rescheduled":
                    tp["rescheduled"] = tp.get("rescheduled", 0) + 1
                elif action_type == "deprioritized":
                    tp["deprioritized"] = tp.get("deprioritized", 0) + 1
                elif action_type == "merged":
                    tp["merged"] = tp.get("merged", 0) + 1

        # ---- 3. Workload recalculation + overload mitigation -------------
        previous_workload = self._next_7d_workload(user_id, today)
        target_cap = (
            int(base_budget * CRUNCH_BUDGET_FACTOR_MAX)
            if days_remaining <= CRUNCH_DAYS
            else int(base_budget * BASE_BUDGET_FACTOR_MAX)
        )
        overload_factor = self._overload_factor(previous_workload, base_budget)

        new_workload, spread_actions = self._mitigate_overload(
            user_id=user_id,
            today=today,
            target_cap=target_cap,
            base_budget=base_budget,
            overload_factor=overload_factor,
            exam_date=exam_date,
        )
        adjustments.extend(spread_actions)
        tp["rescheduled"] = tp.get("rescheduled", 0) + len(spread_actions)

        # ---- 4. Completion-rate phase transition hint --------------------
        completion_rate = self._completion_rate(user_id, study_plan_id, today)

        # ---- 5. Summary + metrics ----------------------------------------
        tp["days_remaining"] = days_remaining
        tp["completion_rate"] = round(completion_rate, 3)
        tp["previous_workload_minutes"] = previous_workload
        tp["new_workload_minutes"] = new_workload
        tp["workload_percent"] = round(
            (new_workload / target_cap) * 100 if target_cap > 0 else 0, 1
        )
        tp["overload_factor"] = round(overload_factor, 2)
        tp["adjustment_count"] = len(adjustments)
        tp["streak_saver_mode"] = streak_saver_mode
        tp["consecutive_missed_days"] = consecutive_missed

        summary = self._summarize(tp, adjustments)

        if not persist:
            return {
                "would_change": len(adjustments) > 0,
                "metrics": SchedulerMetrics(**{k: v for k, v in tp.items() if k in SchedulerMetrics.model_fields}).model_dump(),
                "adjustments": self._serialize_adjustments(adjustments),
                "note": "Dry-run preview — nothing was written.",
            }

        # ---- Capture previous schedule snapshot BEFORE persisting changes ---
        previous_schedule = self._capture_schedule_snapshot(user_id, study_plan_id)

        # ---- 6. Persist run + adjustments --------------------------------
        run = self.scheduler_repo.create_run(
            user_id=user_id,
            study_plan_id=study_plan_id,
            trigger_type=trigger_type,
            run_date=today,
            metrics=tp,
            summary=summary,
        )
        run_id = run["id"]
        if adjustments:
            self.scheduler_repo.add_adjustments(user_id, run_id, adjustments)

        # ---- Capture new schedule snapshot AFTER changes are persisted ----
        new_schedule = self._capture_schedule_snapshot(user_id, study_plan_id)

        # ---- 7. Log to schedule history ----------------------------------
        try:
            await schedule_history_service.log_scheduler_run(
                user_id=user_id,
                run_id=run_id,
                previous_schedule=previous_schedule,
                new_schedule=new_schedule,
                metrics_before={"previous_workload_minutes": previous_workload},
                metrics_after={"new_workload_minutes": new_workload, "completion_rate": completion_rate},
                adjustments=adjustments,
                trigger_type=trigger_type,
                study_plan_id=study_plan_id,
            )
        except Exception as exc:
            logger.warning("schedule_history.log_scheduler_run failed user=%s: %s", user_id, exc)

        logger.info(
            "scheduler.run complete user=%s date=%s adjustments=%d workload=%d/%d",
            user_id, today.isoformat(), len(adjustments), new_workload, target_cap,
        )

        return {
            "run": run,
            "metrics": SchedulerMetrics(**{k: v for k, v in tp.items() if k in SchedulerMetrics.model_fields}).model_dump(),
            "adjustments": self._serialize_adjustments(adjustments),
            "summary": summary,
        }

    async def explain(self, user_id: str, run_date: Optional[date] = None) -> Dict[str, Any]:
        """Dry-run preview of what a scheduler run would change."""
        return await self.run(user_id, trigger_type="manual", run_date=run_date, persist=False)

    def get_latest(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the user's most recent persisted run (with adjustments)."""
        run = self._safe_get_latest_run(user_id)
        if not run:
            return None
        adjustments = self._safe_get_run_adjustments(run["id"])
        return {
            "run": run,
            "metrics": run.get("metrics") or {},
            "adjustments": self._serialize_adjustments(adjustments),
            "summary": run.get("summary"),
        }

    def list_runs(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """List the user's scheduler run history (without nested adjustments)."""
        return self._safe_list_runs(user_id, limit=limit)

    def get_run_detail(self, run_id: str, user_id: str) -> Dict[str, Any]:
        """Return a single run with its adjustments."""
        run = self.scheduler_repo.get_run(run_id, user_id)
        adjustments = self._safe_get_run_adjustments(run_id)
        return {
            "run": run,
            "metrics": run.get("metrics") or {},
            "adjustments": self._serialize_adjustments(adjustments),
            "summary": run.get("summary"),
        }

    # ------------------------------------------------------------------
    # Safe DB wrappers (return empty/None when db is None — for tests)
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

    def _safe_list_pending_before(self, user_id: str, before_date: date) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        return self.task_repo.list_pending_before(user_id, before_date)

    def _safe_list_for_user(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        return self.task_repo.list_for_user(user_id=user_id, status=status)

    def _safe_count_consecutive_missed(self, user_id: str, today: date) -> int:
        if self.db is None:
            return 0
        return self.task_repo.count_consecutive_missed_days(user_id, today)

    def _safe_get_run_for_date(self, user_id: str, run_date: date, trigger_type: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        return self.scheduler_repo.get_run_for_date(user_id, run_date, trigger_type)

    def _safe_get_latest_run(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        return self.scheduler_repo.get_latest_run(user_id)

    def _safe_get_run_adjustments(self, run_id: str) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        return self.scheduler_repo.get_run_adjustments(run_id)

    def _safe_list_runs(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        return self.scheduler_repo.list_runs(user_id, limit=limit)

    def _safe_list_for_date(self, user_id: str, day: date) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        return self.task_repo.list_for_date(user_id, day)

    def _capture_schedule_snapshot(self, user_id: str, study_plan_id: Optional[str]) -> Dict[str, Any]:
        """Capture a snapshot of the current schedule for history tracking."""
        if self.db is None:
            return {}
        
        try:
            # Get tasks for the next 7 days
            today = date.today()
            tasks = []
            for offset in range(7):
                day = today + timedelta(days=offset)
                day_tasks = self.task_repo.list_for_date(user_id, day)
                tasks.extend(day_tasks)
            
            return {
                "study_plan_id": study_plan_id,
                "captured_at": today.isoformat(),
                "tasks": [
                    {
                        "id": t.get("id"),
                        "title": t.get("title"),
                        "scheduled_date": t.get("scheduled_date"),
                        "status": t.get("status"),
                        "duration_minutes": t.get("duration_minutes"),
                        "priority": t.get("priority"),
                    }
                    for t in tasks
                ],
            }
        except Exception as exc:
            logger.warning("schedule_history._capture_schedule_snapshot failed user=%s: %s", user_id, exc)
            return {}

    def _build_existing_run_response(self, run: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Return an already-persisted run (idempotency path)."""
        adjustments = self._safe_get_run_adjustments(run["id"])
        return {
            "run": run,
            "metrics": run.get("metrics") or {},
            "adjustments": self._serialize_adjustments(adjustments),
            "summary": run.get("summary"),
            "idempotent": True,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_neutral(
        self,
        user_id: str,
        today: date,
        trigger_type: str,
        reason: str,
        note: str = "",
        exam_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Return a no-op run payload (not persisted — caller decides)."""
        metrics = SchedulerMetrics(days_remaining=0).model_dump()
        if reason == "no_active_plan" and exam_date is not None:
            metrics["days_remaining"] = max((exam_date - today).days, 0)
        return {
            "would_change": False,
            "metrics": metrics,
            "adjustments": [],
            "summary": reason,
            "note": note or f"Scheduler skipped: {reason.replace('_', ' ')}.",
        }

    # -- overload helpers --------------------------------------------------
    def _overload_factor(self, next_7d_minutes: int, base_budget: int) -> float:
        capacity = 7 * base_budget
        if capacity <= 0:
            return 1.0
        return min(max(next_7d_minutes / capacity, 0.5), 3.0)

    def _next_7d_workload(self, user_id: str, today: date) -> int:
        """Total pending minutes scheduled within today..today+6."""
        total = 0
        for offset in range(7):
            day_tasks = self._safe_list_for_date(user_id, today + timedelta(days=offset))
            total += sum(
                int(t.get("duration_minutes") or 0)
                for t in day_tasks
                if t.get("status") in ("pending", "in_progress")
            )
        return total

    def _count_completed_on_day(self, user_id: str, day: date) -> int:
        tasks = self._safe_list_for_date(user_id, day)
        return sum(1 for t in tasks if t.get("status") == "completed")

    def _completion_rate(self, user_id: str, study_plan_id: str, today: date) -> float:
        """Completion rate across all task rows in the active plan (excluding mocks)."""
        if self.db is None:
            return 0.0
        daily_plans = self.daily_plan_repo.list_for_study_plan(user_id, study_plan_id)
        if not daily_plans:
            return 0.0
        total = 0
        completed = 0
        for dp in daily_plans:
            tasks = self.task_repo.list_for_user(user_id=user_id, daily_plan_id=dp["id"])
            for t in tasks:
                if t.get("task_type") in ("full_mock", "mock_section"):
                    continue
                total += 1
                if t.get("status") == "completed":
                    completed += 1
        return (completed / total) if total > 0 else 0.0

    def _handle_overdue(
        self,
        user_id: str,
        task: Dict[str, Any],
        today: date,
        exam_date: date,
        base_budget: int,
        streak_saver_mode: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Decide what to do with a single overdue task:
          - Mock tasks are rescheduled (never dropped) before/on exam date.
          - In streak-saver mode, only the highest-priority overdue task is
            carried forward; the rest are deferred to avoid overwhelming the
            user.
          - Everything else is carried forward as a clone with bumped priority.
        Returns an adjustment dict (or None if nothing to do).
        """
        task_id = task.get("id")
        task_title = task.get("title", "Untitled task")
        original_date = self._parse_date(task.get("scheduled_date")) if task.get("scheduled_date") else today

        # Never carry a mock past the exam — reschedule before/on exam date.
        if task.get("task_type") in ("full_mock", "mock_section"):
            target = self._find_slot_before_exam(
                user_id=user_id,
                today=today + timedelta(days=1),
                exam_date=exam_date,
                preferred_duration=int(task.get("duration_minutes") or 45),
                base_budget=base_budget,
            )
            if target is None:
                # Keep it where it is; do not push past the exam.
                return {
                    "task_id": task_id,
                    "task_title": task_title,
                    "from_date": original_date,
                    "to_date": original_date,
                    "action": "kept",
                    "reason": "Mock test kept on its scheduled date so it does not collide with the exam window.",
                    "priority_delta": 0,
                }
            if self.db is not None:
                self.reschedule_for_date_safe(task_id, user_id, target)
            return {
                "task_id": task_id,
                "task_title": task_title,
                "from_date": original_date,
                "to_date": target,
                "action": "rescheduled",
                "reason": "Mock test rescheduled to an earlier protected-free day to stay before the exam.",
                "priority_delta": 0,
            }

        # Streak-saver mode: only carry the single highest-priority overdue
        # task (the first one, since overdue is sorted by priority desc).
        # Defer the rest — they'll be picked up on subsequent days.
        if streak_saver_mode:
            # The first overdue task (highest priority) is carried; the rest
            # are marked missed but NOT cloned, to avoid overwhelming the user.
            # We detect "first" by checking if this is the highest priority.
            # Since overdue_sorted is priority-desc, we carry only priority 5
            # (critical) tasks in streak-saver mode.
            task_priority = int(task.get("priority") or 1)
            if task_priority < 5:
                # Mark as missed but don't clone — it stays in the backlog.
                if self.db is not None:
                    self.task_repo.mark_missed(task_id, user_id)
                return {
                    "task_id": task_id,
                    "task_title": task_title,
                    "from_date": original_date,
                    "to_date": original_date,
                    "action": "deprioritized",
                    "reason": "Streak-saver mode: low-priority missed task deferred to avoid overwhelming you after multiple missed days.",
                    "priority_delta": 0,
                }

        # Standard overdue task — carry forward as a clone.
        target = self._find_next_available_slot(
            user_id=user_id,
            start=today,
            exam_date=exam_date,
            duration=int(task.get("duration_minutes") or 15),
            base_budget=base_budget,
            skip_protected=True,
        )
        if target is None:
            return {
                "task_id": task_id,
                "task_title": task_title,
                "from_date": original_date,
                "to_date": original_date,
                "action": "kept",
                "reason": "No available slot within 14 days; task kept on its original date rather than dropped.",
                "priority_delta": 0,
            }

        if self.db is not None:
            try:
                self.task_repo.carry_forward(task, user_id, target, priority_delta=1)
            except Exception as exc:
                logger.warning("scheduler carry_forward failed task=%s: %s", task_id, exc)
                return {
                    "task_id": task_id,
                    "task_title": task_title,
                    "from_date": original_date,
                    "to_date": original_date,
                    "action": "kept",
                    "reason": f"Could not carry task forward ({exc}); kept in place.",
                    "priority_delta": 0,
                }

        return {
            "task_id": task_id,
            "task_title": task_title,
            "from_date": original_date,
            "to_date": target,
            "action": "carried_forward",
            "reason": "Task was not completed; moved forward to the next available day.",
            "priority_delta": 1,
        }

    def _mitigate_overload(
        self,
        user_id: str,
        today: date,
        target_cap: int,
        base_budget: int,
        overload_factor: float,
        exam_date: date,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Two-stage overload mitigation:
          1. Daily overload (>1.5x): spread the 2 lowest-priority tasks on
             each overloaded day to the next available day.
          2. Weekly overload (>1.3x): drop the bottom 20% of non-required,
             non-mock tasks to later dates.

        Returns (new_workload, actions).
        """
        actions: List[Dict[str, Any]] = []

        # ---- Stage 1: Daily overload spreading ---------------------------
        daily_cap = int(base_budget * DAILY_OVERLOAD_RATIO_THRESHOLD)
        for offset in range(7):
            day = today + timedelta(days=offset)
            day_tasks = self._safe_list_for_date(user_id, day)
            pending = [t for t in day_tasks if t.get("status") in ("pending", "in_progress")]
            day_minutes = sum(int(t.get("duration_minutes") or 0) for t in pending)
            if day_minutes <= daily_cap:
                continue

            # Find the 2 lowest-priority non-mock, non-required tasks to spread.
            spreadable = [
                t for t in pending
                if not t.get("is_mandatory")
                and t.get("task_type") not in ("full_mock", "mock_section")
            ]
            spreadable.sort(key=lambda t: (int(t.get("priority") or 1),))
            to_spread = spreadable[:2]

            for t in to_spread:
                original_date = self._parse_date(t.get("scheduled_date")) if t.get("scheduled_date") else today
                target = self._find_next_available_slot(
                    user_id=user_id,
                    start=day + timedelta(days=1),
                    exam_date=exam_date,
                    duration=int(t.get("duration_minutes") or 15),
                    base_budget=base_budget,
                    skip_protected=True,
                )
                if target is None:
                    continue
                if self.db is not None:
                    self.reschedule_for_date_safe(t["id"], user_id, target, priority_delta=0)
                actions.append({
                    "task_id": t["id"],
                    "task_title": t.get("title", "Untitled task"),
                    "from_date": original_date,
                    "to_date": target,
                    "action": "spread",
                    "reason": "Daily workload exceeded 150% of your budget; task moved to the next available day.",
                    "priority_delta": 0,
                })

        # ---- Stage 2: Weekly overload deprioritization -------------------
        if overload_factor >= OVERLOAD_RATIO_THRESHOLD:
            # Gather all pending tasks in the next 7 days.
            candidates: List[Dict[str, Any]] = []
            for offset in range(7):
                day = today + timedelta(days=offset)
                for t in self._safe_list_for_date(user_id, day):
                    if t.get("status") in ("pending", "in_progress"):
                        candidates.append(t)

            # Drop the bottom ~20% of non-required, non-mock tasks.
            droppable = [
                t for t in candidates
                if not t.get("is_mandatory")
                and t.get("task_type") not in ("full_mock", "mock_section")
            ]
            droppable.sort(key=lambda t: (int(t.get("priority") or 1),))
            drop_count = max(1, int(len(droppable) * DEPRIORITIZE_PROPORTION)) if droppable else 0

            for t in droppable[:drop_count]:
                original_date = self._parse_date(t.get("scheduled_date")) if t.get("scheduled_date") else today
                target = self._find_next_available_slot(
                    user_id=user_id,
                    start=today + timedelta(days=7),
                    exam_date=exam_date,
                    duration=int(t.get("duration_minutes") or 15),
                    base_budget=base_budget,
                    skip_protected=True,
                )
                if target is None:
                    continue
                if self.db is not None:
                    self.reschedule_for_date_safe(t["id"], user_id, target, priority_delta=-1)
                actions.append({
                    "task_id": t["id"],
                    "task_title": t.get("title", "Untitled task"),
                    "from_date": original_date,
                    "to_date": target,
                    "action": "deprioritized",
                    "reason": "Weekly workload exceeded capacity; low-priority task moved to a later day.",
                    "priority_delta": -1,
                })

        return self._next_7d_workload(user_id, today), actions

    def _find_next_available_slot(
        self,
        user_id: str,
        start: date,
        exam_date: date,
        duration: int,
        base_budget: int,
        skip_protected: bool = True,
    ) -> Optional[date]:
        """Find the first non-protected day with enough remaining budget."""
        target = start
        attempts = 0
        while attempts < MAX_SHIFT_DAYS:
            if target > exam_date:
                return None
            day_status = self._day_type(user_id, target, exam_date)
            if skip_protected and day_status != "normal":
                target += timedelta(days=1)
                attempts += 1
                continue
            if self._remaining_budget_for_date(user_id, target, base_budget) >= duration:
                return target
            target += timedelta(days=1)
            attempts += 1
        return None

    def _find_slot_before_exam(
        self,
        user_id: str,
        today: date,
        exam_date: date,
        preferred_duration: int,
        base_budget: int,
    ) -> Optional[date]:
        """Find a slot strictly before the exam for a mock task."""
        return self._find_next_available_slot(
            user_id=user_id,
            start=today,
            exam_date=exam_date - timedelta(days=MOCK_BEFORE_EXAM_GUARD_DAYS),
            duration=preferred_duration,
            base_budget=base_budget,
            skip_protected=True,
        )

    def _day_type(
        self,
        user_id: str,
        day: date,
        exam_date: date,
    ) -> str:
        """
        Classify a day:
          'final_revision' — within the last FINAL_REVISION_DAYS before exam
          'mock'           — has a pending mock task scheduled
          'mock_prep'      — the day before a mock
          'mock_review'    — the day after a mock
          'rest'           — user's rest day of the week
          'normal'         — everything else
        """
        if day >= exam_date - timedelta(days=FINAL_REVISION_DAYS):
            # Only final revision if it's not itself a mock day.
            mocks = self._safe_list_for_date(user_id, day)
            if not any(t.get("task_type") in ("full_mock", "mock_section") for t in mocks):
                return "final_revision"

        # Mock day / adjacent days.
        pending_tasks = self._safe_list_for_date(user_id, day)
        is_mock_day = any(t.get("task_type") in ("full_mock", "mock_section") for t in pending_tasks)
        if is_mock_day:
            return "mock"

        # Check the day before / after for mocks.
        for delta in (-1, 1):
            check_day = day + timedelta(days=delta)
            if check_day > exam_date:
                continue
            day_tasks = self._safe_list_for_date(user_id, check_day)
            if any(t.get("task_type") in ("full_mock", "mock_section") for t in day_tasks):
                return "mock_prep" if delta == -1 else "mock_review"

        # Rest day — from user preferences if set (default: Sunday).
        rest_day = self._get_user_rest_day(user_id)
        if rest_day is not None and day.weekday() == rest_day:
            return "rest"

        return "normal"

    def _get_user_rest_day(self, user_id: str) -> Optional[int]:
        """
        Get the user's preferred rest day of the week (0=Monday ... 6=Sunday).

        Reads from preferences.rest_day if set; defaults to Sunday (6).
        Returns None if the user profile can't be loaded.
        """
        user = self._safe_get_profile(user_id)
        if not user:
            return 6  # default Sunday
        prefs = user.get("preferences") or {}
        rest_day = prefs.get("rest_day")
        if rest_day is not None and isinstance(rest_day, (int, str)):
            try:
                rd = int(rest_day)
                if 0 <= rd <= 6:
                    return rd
            except (ValueError, TypeError):
                pass
        return 6  # default Sunday

    def _remaining_budget_for_date(self, user_id: str, day: date, base_budget: int) -> int:
        """Remaining free minutes on a date based on already-scheduled tasks."""
        scheduled = sum(
            int(t.get("duration_minutes") or 0)
            for t in self._safe_list_for_date(user_id, day)
            if t.get("status") in ("pending", "in_progress")
        )
        return max(base_budget - scheduled, 0)

    # ------------------------------------------------------------------
    # Safe wrappers (screen for ownership before writing)
    # ------------------------------------------------------------------
    def reschedule_for_date_safe(
        self,
        task_id: str,
        user_id: str,
        target_date: date,
        priority_delta: int = 0,
    ) -> Dict[str, Any]:
        return self.task_repo.reschedule_for_date(task_id, user_id, target_date, priority_delta=priority_delta)

    # ------------------------------------------------------------------
    # Serialization / summary helpers
    # ------------------------------------------------------------------
    def _serialize_adjustments(self, adjustments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for a in adjustments:
            row = dict(a)
            for key in ("from_date", "to_date"):
                if row.get(key) is not None and hasattr(row[key], "isoformat"):
                    row[key] = row[key].isoformat()
            out.append(row)
        return out

    def _summarize(self, tp: Dict[str, Any], adjustments: List[Dict[str, Any]]) -> str:
        carried = tp.get("carried_forward", 0)
        rescheduled = tp.get("rescheduled", 0)
        deprioritized = tp.get("deprioritized", 0)
        merged = tp.get("merged", 0)
        missed = tp.get("missed_yesterday", 0)
        streak_saver = tp.get("streak_saver_mode", False)

        if streak_saver:
            return (
                f"You've missed {tp.get('consecutive_missed_days', 0)} days in a row. "
                "Streak-saver mode is on: only your most important tasks are carried forward "
                "so you can rebuild momentum without being overwhelmed."
            )

        if carried == 0 and rescheduled == 0 and deprioritized == 0 and merged == 0:
            if missed == 0:
                return "All tasks completed yesterday. Your plan is on track — no changes needed."
            return f"{missed} missed task(s) could not be moved within the safe window and were kept in place."

        parts = []
        if carried:
            parts.append(f"{carried} unfinished task(s) moved forward")
        if merged:
            parts.append(f"{merged} task(s) merged with similar skills to optimize your time")
        if rescheduled:
            parts.append(f"{rescheduled} task(s) rescheduled to balance your weekly load")
        if deprioritized:
            parts.append(f"{deprioritized} low-priority task(s) deferred")
        return ", ".join(parts) + ". Your workload stays within a safe daily budget."

    def _smart_handle_overdue(
        self,
        user_id: str,
        task: Dict[str, Any],
        today: date,
        exam_date: date,
        base_budget: int,
        streak_saver_mode: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Smart version of _handle_overdue that uses intelligent scoring,
        merging, and workload-aware slot selection.
        """
        task_id = task.get("id")
        task_title = task.get("title", "Untitled task")
        original_date = self._parse_date(task.get("scheduled_date")) if task.get("scheduled_date") else today

        # Mock tasks: always reschedule before exam (same as original logic)
        if task.get("task_type") in ("full_mock", "mock_section"):
            target = self._find_slot_before_exam(
                user_id=user_id,
                today=today + timedelta(days=1),
                exam_date=exam_date,
                preferred_duration=int(task.get("duration_minutes") or 45),
                base_budget=base_budget,
            )
            if target is None:
                return {
                    "task_id": task_id,
                    "task_title": task_title,
                    "from_date": original_date,
                    "to_date": original_date,
                    "action": "kept",
                    "reason": "Mock test kept on its scheduled date so it does not collide with the exam window.",
                    "priority_delta": 0,
                }
            if self.db is not None:
                self.reschedule_for_date_safe(task_id, user_id, target)
            return {
                "task_id": task_id,
                "task_title": task_title,
                "from_date": original_date,
                "to_date": target,
                "action": "rescheduled",
                "reason": "Mock test rescheduled to an earlier protected-free day to stay before the exam.",
                "priority_delta": 0,
            }

        # Streak-saver mode: only carry highest priority tasks
        if streak_saver_mode:
            task_priority = int(task.get("priority") or 1)
            if task_priority < 5:
                if self.db is not None:
                    self.task_repo.mark_missed(task_id, user_id)
                return {
                    "task_id": task_id,
                    "task_title": task_title,
                    "from_date": original_date,
                    "to_date": original_date,
                    "action": "deprioritized",
                    "reason": "Streak-saver mode: low-priority missed task deferred to avoid overwhelming you after multiple missed days.",
                    "priority_delta": 0,
                }

        # Use smart carry-forward for all other tasks
        return self._smart_carry_forward(
            user_id=user_id,
            task=task,
            today=today,
            exam_date=exam_date,
            base_budget=base_budget,
        )

    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)[:10]).date()

    @staticmethod
    def _sort_by_priority(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Overdue tasks: highest priority first, then earliest date."""
        return sorted(
            tasks,
            key=lambda t: (
                -(int(t.get("priority") or 1)),
                str(t.get("scheduled_date") or ""),
            ),
        )

    # ------------------------------------------------------------------
    # Smart Carry Forward: intelligent merging + scoring
    # ------------------------------------------------------------------
    def _calculate_task_score(self, task: Dict[str, Any], days_remaining: int) -> float:
        """
        Score a task based on importance, difficulty, and urgency.
        Higher score = more important to carry forward.
        """
        priority = int(task.get("priority") or 1)
        difficulty = int(task.get("difficulty") or 1)
        task_type = task.get("task_type", "")
        duration = int(task.get("duration_minutes") or 15)

        # Base score from priority and difficulty
        score = (priority * PRIORITY_WEIGHT) + (difficulty * DIFFICULTY_WEIGHT)

        # Protect revision tasks
        if task_type in ("revision", "review"):
            score += REVISION_PROTECTION_BONUS

        # Protect mock tests (highest priority)
        if task_type in ("full_mock", "mock_section"):
            score += MOCK_PROTECTION_BONUS

        # Urgency factor: tasks due sooner get a boost
        scheduled_date = self._parse_date(task.get("scheduled_date")) if task.get("scheduled_date") else None
        if scheduled_date:
            days_until_due = max((scheduled_date - date.today()).days, 0)
            if days_remaining > 0:
                urgency = 1 + (1 - days_until_due / days_remaining)
                score *= urgency

        return score

    def _find_mergeable_tasks(self, user_id: str, target_date: date, new_task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find tasks on target_date that can be merged with new_task.
        Merging criteria:
        - Same skill/category
        - Combined duration <= MAX_MERGE_DURATION
        - Both are non-mock, non-revision tasks
        """
        if not MERGE_SIMILAR_SKILLS:
            return []

        target_tasks = self._safe_list_for_date(user_id, target_date)
        new_skill = new_task.get("skill") or new_task.get("category")
        new_duration = int(new_task.get("duration_minutes") or 15)

        mergeable = []
        for task in target_tasks:
            if task.get("status") not in ("pending", "in_progress"):
                continue
            if task.get("task_type") in ("full_mock", "mock_section", "revision", "review"):
                continue
            if task.get("id") == new_task.get("id"):
                continue

            task_skill = task.get("skill") or task.get("category")
            if task_skill != new_skill:
                continue

            task_duration = int(task.get("duration_minutes") or 0)
            if new_duration + task_duration > MAX_MERGE_DURATION:
                continue

            mergeable.append(task)

        return mergeable

    def _merge_tasks(self, existing_task: Dict[str, Any], new_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two tasks into one combined task.
        Returns the merged task data.
        """
        existing_duration = int(existing_task.get("duration_minutes") or 0)
        new_duration = int(new_task.get("duration_minutes") or 0)
        combined_duration = min(existing_duration + new_duration, MAX_MERGE_DURATION)

        # Take the higher priority
        existing_priority = int(existing_task.get("priority") or 1)
        new_priority = int(new_task.get("priority") or 1)
        merged_priority = max(existing_priority, new_priority)

        # Combine titles
        existing_title = existing_task.get("title", "Task")
        new_title = new_task.get("title", "Task")
        if existing_title != new_title:
            merged_title = f"{existing_title} + {new_title}"
        else:
            merged_title = existing_title

        return {
            "duration_minutes": combined_duration,
            "priority": merged_priority,
            "title": merged_title,
            "merged": True,
            "merged_from": [existing_task.get("id"), new_task.get("id")],
        }

    def _split_large_task(self, task: Dict[str, Any], available_minutes: int) -> List[Dict[str, Any]]:
        """
        Split a large task into smaller chunks that fit within available_minutes.
        Only splits tasks > SPLITTABLE_TASK_THRESHOLD minutes.
        """
        duration = int(task.get("duration_minutes") or 0)
        if duration <= SPLITTABLE_TASK_THRESHOLD or duration <= available_minutes:
            return [task]

        if available_minutes < MIN_TASK_DURATION:
            return [task]  # Can't split meaningfully

        # Calculate how many chunks we need
        num_chunks = (duration + available_minutes - 1) // available_minutes
        chunk_duration = duration // num_chunks

        chunks = []
        for i in range(num_chunks):
            chunk = dict(task)
            chunk["id"] = f"{task.get('id')}_chunk_{i}"
            chunk["duration_minutes"] = chunk_duration
            chunk["title"] = f"{task.get('title', 'Task')} (Part {i + 1}/{num_chunks})"
            chunk["parent_task_id"] = task.get("id")
            chunks.append(chunk)

        return chunks

    def _smart_carry_forward(
        self,
        user_id: str,
        task: Dict[str, Any],
        today: date,
        exam_date: date,
        base_budget: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Intelligent carry-forward with merging, splitting, and scoring.
        Replaces simple _handle_overdue for non-mock tasks.
        """
        task_id = task.get("id")
        task_title = task.get("title", "Untitled task")
        original_date = self._parse_date(task.get("scheduled_date")) if task.get("scheduled_date") else today
        days_remaining = max((exam_date - today).days, 0)

        # Calculate task importance score
        task_score = self._calculate_task_score(task, days_remaining)

        # Find the best slot considering task importance
        target = self._find_best_slot_for_task(
            user_id=user_id,
            start=today,
            exam_date=exam_date,
            task=task,
            base_budget=base_budget,
            task_score=task_score,
        )

        if target is None:
            return {
                "task_id": task_id,
                "task_title": task_title,
                "from_date": original_date,
                "to_date": original_date,
                "action": "kept",
                "reason": "No suitable slot found within the remaining study period; task retained on original date.",
                "priority_delta": 0,
            }

        # Try to merge with existing tasks on target date
        mergeable = self._find_mergeable_tasks(user_id, target, task)
        merged = False
        if mergeable:
            # Merge with the highest-priority mergeable task
            merge_target = max(mergeable, key=lambda t: int(t.get("priority") or 1))
            if self.db is not None:
                try:
                    merged_data = self._merge_tasks(merge_target, task)
                    self.task_repo.update(merge_target["id"], user_id, merged_data)
                    # Mark the new task as merged (don't create duplicate)
                    merged = True
                    return {
                        "task_id": task_id,
                        "task_title": task_title,
                        "from_date": original_date,
                        "to_date": target,
                        "action": "merged",
                        "reason": f"Merged with '{merge_target.get('title')}' on {target.isoformat()} to optimize your study time.",
                        "priority_delta": 0,
                    }
                except Exception as exc:
                    logger.warning("scheduler merge failed task=%s: %s", task_id, exc)

        # Standard carry-forward (no merge)
        if self.db is not None:
            try:
                self.task_repo.carry_forward(task, user_id, target, priority_delta=1)
            except Exception as exc:
                logger.warning("scheduler carry_forward failed task=%s: %s", task_id, exc)
                return {
                    "task_id": task_id,
                    "task_title": task_title,
                    "from_date": original_date,
                    "to_date": original_date,
                    "action": "kept",
                    "reason": f"Could not carry task forward ({exc}); kept in place.",
                    "priority_delta": 0,
                }

        return {
            "task_id": task_id,
            "task_title": task_title,
            "from_date": original_date,
            "to_date": target,
            "action": "carried_forward",
            "reason": f"Task carried forward to {target.isoformat()} based on importance score and available workload.",
            "priority_delta": 1,
        }

    def _find_best_slot_for_task(
        self,
        user_id: str,
        start: date,
        exam_date: date,
        task: Dict[str, Any],
        base_budget: int,
        task_score: float,
    ) -> Optional[date]:
        """
        Find the optimal slot for a task considering:
        - Available budget
        - Day protection (revision, mock, rest)
        - Task importance score
        - Remaining days
        """
        target = start
        attempts = 0
        best_slot = None
        best_score = -1

        while attempts < MAX_SHIFT_DAYS:
            if target > exam_date:
                break

            day_status = self._day_type(user_id, target, exam_date)

            # Skip protected days unless task is high-scoring
            if day_status != "normal":
                if task_score < 10:  # Low-score tasks don't override protection
                    target += timedelta(days=1)
                    attempts += 1
                    continue

            remaining = self._remaining_budget_for_date(user_id, target, base_budget)
            duration = int(task.get("duration_minutes") or 15)

            if remaining >= duration:
                # Score this slot based on remaining capacity and urgency
                slot_score = task_score * (1 + remaining / base_budget)
                if slot_score > best_score:
                    best_score = slot_score
                    best_slot = target

                # If we have plenty of room, take it immediately
                if remaining >= duration * 1.5:
                    return target

            target += timedelta(days=1)
            attempts += 1

        return best_slot

    def _recalculate_workload(
        self,
        user_id: str,
        today: date,
        exam_date: date,
        base_budget: int,
        adjustments: List[Dict[str, Any]],
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Recalculate workload after carry-forwards and rebalance.
        Returns (new_workload, additional_adjustments).
        """
        days_remaining = max((exam_date - today).days, 0)
        target_cap = (
            int(base_budget * CRUNCH_BUDGET_FACTOR_MAX)
            if days_remaining <= CRUNCH_DAYS
            else int(base_budget * BASE_BUDGET_FACTOR_MAX)
        )

        # Calculate current workload
        current_workload = self._next_7d_workload(user_id, today)
        overload_factor = self._overload_factor(current_workload, base_budget)

        # If overloaded, apply mitigation
        if overload_factor >= DAILY_OVERLOAD_RATIO_THRESHOLD:
            _, spread_actions = self._mitigate_overload(
                user_id=user_id,
                today=today,
                target_cap=target_cap,
                base_budget=base_budget,
                overload_factor=overload_factor,
                exam_date=exam_date,
            )
            adjustments.extend(spread_actions)
            return self._next_7d_workload(user_id, today), spread_actions

        return current_workload, []

    def _protect_revision_and_mocks(self, user_id: str, today: date, exam_date: date) -> List[Dict[str, Any]]:
        """
        Ensure revision tasks and mock tests are protected during scheduling.
        Returns list of protection actions taken.
        """
        protections = []

        # Find revision tasks in the next 7 days
        for offset in range(7):
            day = today + timedelta(days=offset)
            tasks = self._safe_list_for_date(user_id, day)

            for task in tasks:
                task_type = task.get("task_type")
                if task_type not in ("revision", "review", "full_mock", "mock_section"):
                    continue

                # Boost priority to protect from being moved
                current_priority = int(task.get("priority") or 1)
                if task_type in ("full_mock", "mock_section"):
                    new_priority = min(current_priority + MOCK_PROTECTION_BONUS, 10)
                else:
                    new_priority = min(current_priority + REVISION_PROTECTION_BONUS, 10)

                if new_priority > current_priority:
                    if self.db is not None:
                        try:
                            self.task_repo.update_priority(task["id"], user_id, new_priority)
                            protections.append({
                                "task_id": task["id"],
                                "task_title": task.get("title", "Task"),
                                "action": "protected",
                                "reason": f"{task_type.title()} task protected with priority boost to prevent rescheduling.",
                                "priority_delta": new_priority - current_priority,
                            })
                        except Exception as exc:
                            logger.warning("scheduler protection failed task=%s: %s", task["id"], exc)

        return protections

    def _track_change_history(self, user_id: str, run_id: str, adjustments: List[Dict[str, Any]]) -> None:
        """
        Record all adjustments in the change history for audit trail.
        This is already handled by scheduler_repo.add_adjustments, but we
        can add additional metadata here if needed.
        """
        # Future: Add analytics, user notifications, etc.
        pass


# Singleton bound to the shared DB session.
from app.db.session import db_session

adaptive_scheduler = AdaptiveSchedulerService(db_session)