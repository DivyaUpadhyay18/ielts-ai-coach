"""
Schedule History Service

Automatically logs all schedule changes and provides methods for
creating and querying schedule history entries.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.repositories.schedule_history_repo import ScheduleHistoryRepository
from app.repositories.scheduler_repo import SchedulerRepository
from app.models.schedule_history import ScheduleHistoryCreate


class ScheduleHistoryService:
    """Service for managing schedule history."""

    def __init__(self, db=None):
        self.history_repo = ScheduleHistoryRepository(db)
        self.scheduler_repo = SchedulerRepository(db)

    async def log_scheduler_run(
        self,
        user_id: str,
        run_id: str,
        previous_schedule: Dict[str, Any],
        new_schedule: Dict[str, Any],
        metrics_before: Dict[str, Any],
        metrics_after: Dict[str, Any],
        adjustments: List[Dict[str, Any]],
        trigger_type: str = "midnight",
        study_plan_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Log a scheduler run to history.
        
        Called automatically after each scheduler run to track changes.
        """
        # Generate summary from adjustments
        summary = self._generate_summary(adjustments)
        
        # Create history entry
        entry = await self.history_repo.create_entry(
            user_id=user_id,
            study_plan_id=study_plan_id,
            run_id=run_id,
            previous_schedule=previous_schedule,
            new_schedule=new_schedule,
            change_reason=self._generate_reason(trigger_type, adjustments),
            change_type="scheduler_run",
            trigger_type=trigger_type,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            summary=summary,
            adjustments_count=len(adjustments),
            tasks_affected=len(set(a.get("task_id") for a in adjustments if a.get("task_id"))),
        )
        
        return entry

    async def log_exam_date_update(
        self,
        user_id: str,
        previous_exam_date: str,
        new_exam_date: str,
        previous_schedule: Dict[str, Any],
        new_schedule: Dict[str, Any],
        metrics_before: Dict[str, Any],
        metrics_after: Dict[str, Any],
        study_plan_id: Optional[str] = None,
        auto_regenerated: bool = False,
    ) -> Dict[str, Any]:
        """Log an exam date update."""
        reason = f"Exam date changed from {previous_exam_date} to {new_exam_date}"
        if auto_regenerated:
            reason += " (study plan auto-regenerated)"
        
        entry = await self.history_repo.create_entry(
            user_id=user_id,
            study_plan_id=study_plan_id,
            previous_schedule=previous_schedule,
            new_schedule=new_schedule,
            change_reason=reason,
            change_type="exam_date_update",
            trigger_type="user",
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            summary=f"Exam date updated to {new_exam_date}",
            tasks_affected=self._count_affected_tasks(previous_schedule, new_schedule),
        )
        
        return entry

    async def log_manual_reschedule(
        self,
        user_id: str,
        task_id: str,
        task_title: str,
        from_date: str,
        to_date: str,
        reason: str,
        study_plan_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log a manual task reschedule."""
        entry = await self.history_repo.create_entry(
            user_id=user_id,
            study_plan_id=study_plan_id,
            previous_schedule={"task_id": task_id, "scheduled_date": from_date},
            new_schedule={"task_id": task_id, "scheduled_date": to_date},
            change_reason=reason,
            change_type="manual_reschedule",
            trigger_type="user",
            summary=f"Rescheduled: {task_title}",
            tasks_affected=1,
        )
        
        return entry

    async def log_study_plan_regeneration(
        self,
        user_id: str,
        previous_plan_id: str,
        new_plan_id: str,
        previous_schedule: Dict[str, Any],
        new_schedule: Dict[str, Any],
        reason: str,
        metrics_before: Optional[Dict[str, Any]] = None,
        metrics_after: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Log a study plan regeneration."""
        entry = await self.history_repo.create_entry(
            user_id=user_id,
            study_plan_id=new_plan_id,
            previous_schedule=previous_schedule,
            new_schedule=new_schedule,
            change_reason=reason,
            change_type="study_plan_regeneration",
            trigger_type="system",
            metrics_before=metrics_before or {},
            metrics_after=metrics_after or {},
            summary="Study plan regenerated",
            tasks_affected=self._count_affected_tasks(previous_schedule, new_schedule),
        )
        
        return entry

    async def get_user_history(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        change_type: Optional[str] = None,
        user_action: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Get schedule history for a user."""
        from app.models.schedule_history import ScheduleHistoryFilter
        
        filters = ScheduleHistoryFilter(
            change_type=change_type,
            user_action=user_action,
            limit=limit,
            offset=offset,
        )
        
        return await self.history_repo.list_history(user_id, filters)

    async def get_comparison(
        self,
        user_id: str,
        history_id_1: str,
        history_id_2: str,
    ) -> Optional[Dict[str, Any]]:
        """Get comparison between two history entries."""
        return await self.history_repo.get_comparison(user_id, history_id_1, history_id_2)

    async def update_user_action(
        self,
        history_id: str,
        user_id: str,
        action: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update user action on a history entry."""
        valid_actions = ["accepted", "rejected", "modified", "pending", "auto_applied"]
        if action not in valid_actions:
            raise ValueError(f"Invalid action. Must be one of: {', '.join(valid_actions)}")
        
        entry = await self.history_repo.update_user_action(
            history_id,
            user_id,
            action,
            notes,
        )
        
        if not entry:
            raise ValueError("Schedule history entry not found")
        
        return entry

    async def get_stats(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get schedule history statistics."""
        return await self.history_repo.get_stats(user_id, days)

    def _generate_summary(self, adjustments: List[Dict[str, Any]]) -> str:
        """Generate a human-readable summary from adjustments."""
        if not adjustments:
            return "No changes made"
        
        counts = {}
        for adj in adjustments:
            action = adj.get("action", "unknown")
            counts[action] = counts.get(action, 0) + 1
        
        parts = []
        for action, count in counts.items():
            parts.append(f"{count} {action.replace('_', ' ')}")
        
        return ", ".join(parts)

    def _generate_reason(self, trigger_type: str, adjustments: List[Dict[str, Any]]) -> str:
        """Generate a reason for the schedule change."""
        if trigger_type == "midnight":
            return "Overnight scheduler run - adjusted schedule based on yesterday's progress"
        elif trigger_type == "app_open":
            return "Schedule optimized on app open"
        elif trigger_type == "manual":
            return "Manual scheduler run"
        else:
            return f"Schedule adjusted ({trigger_type})"

    def _count_affected_tasks(
        self,
        previous_schedule: Dict[str, Any],
        new_schedule: Dict[str, Any],
    ) -> int:
        """Count the number of tasks affected by a schedule change."""
        prev_tasks = set()
        new_tasks = set()
        
        # Extract task IDs from schedules
        if "tasks" in previous_schedule:
            prev_tasks = {t.get("id") for t in previous_schedule["tasks"] if t.get("id")}
        if "tasks" in new_schedule:
            new_tasks = {t.get("id") for t in new_schedule["tasks"] if t.get("id")}
        
        # Return count of unique affected tasks
        return len(prev_tasks.union(new_tasks))


# Singleton instance
schedule_history_service = ScheduleHistoryService()