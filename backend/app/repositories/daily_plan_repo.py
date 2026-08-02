"""
Repository for the DailyPlan domain entity.
"""
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class DailyPlanRepository(BaseRepository):
    """Data access for the daily_plans table."""

    table_name = "daily_plans"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    def list_by_date_range(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Fetch daily plans for a user within a date range, ordered by date."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .gte("plan_date", start_date.isoformat())
            .lte("plan_date", end_date.isoformat())
            .order("plan_date")
        )
        result = self._execute(query)
        return result.data or []

    def get_by_date(self, user_id: str, plan_date: date) -> Optional[Dict[str, Any]]:
        """Fetch a user's daily plan for a specific date, if any."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .eq("plan_date", plan_date.isoformat())
            .limit(1)
        )
        result = self._execute(query)
        if not result.data:
            return None
        return result.data[0]

    def list_for_study_plan(self, user_id: str, study_plan_id: str) -> List[Dict[str, Any]]:
        """Fetch all daily plans belonging to a study plan, ordered by date."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .eq("study_plan_id", study_plan_id)
            .order("plan_date")
        )
        result = self._execute(query)
        return result.data or []

    def update_task_summary(self, daily_plan_id: str) -> Dict[str, Any]:
        """
        Recompute the total_tasks / completed_tasks / total_minutes /
        completed_minutes summary for a daily plan based on its tasks.
        """
        tasks_query = (
            self.db.table("tasks")
            .select("duration_minutes, status")
            .eq("daily_plan_id", daily_plan_id)
        )
        tasks_result = self.db.execute(tasks_query, "fetch tasks for daily plan summary")
        tasks = tasks_result.data or []

        total_tasks = len(tasks)
        completed_tasks = sum(
            1 for t in tasks if t.get("status") == "completed"
        )
        total_minutes = sum(int(t.get("duration_minutes") or 0) for t in tasks)
        completed_minutes = sum(
            int(t.get("duration_minutes") or 0)
            for t in tasks
            if t.get("status") == "completed"
        )

        # Determine plan status based on task progress.
        status = "scheduled"
        if total_tasks > 0 and completed_tasks == total_tasks:
            status = "completed"
        elif completed_tasks > 0:
            status = "in_progress"

        query = (
            self._table()
            .update({
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "total_minutes": total_minutes,
                "completed_minutes": completed_minutes,
                "status": status,
            })
            .eq(self.id_column, daily_plan_id)
        )
        result = self._execute(query, "update daily plan summary")
        if not result.data:
            raise NotFoundError("Daily plan not found")
        return result.data[0]