"""
Repository for the Task domain entity.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository):
    """Data access for the tasks table and task_resources join table."""

    table_name = "tasks"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------
    def create(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task for a user."""
        payload = dict(data)
        payload["user_id"] = user_id

        # Auto-assign order_index within the daily plan if not provided.
        if payload.get("order_index") is None and payload.get("daily_plan_id"):
            daily_plan_id = payload["daily_plan_id"]
            query = (
                self._table()
                .select("order_index")
                .eq("daily_plan_id", daily_plan_id)
                .not_.is_("order_index", "null")
                .order("order_index", desc=True)
                .limit(1)
            )
            result = self._execute(query, "compute next order index")
            max_index = result.data[0]["order_index"] if result.data else -1
            payload["order_index"] = int(max_index) + 1

        query = self._table().insert(payload)
        result = self._execute(query, "create task")
        if not result.data:
            raise ConflictError("Failed to create task")
        return result.data[0]

    def list_for_user(
        self,
        user_id: str,
        status: Optional[str] = None,
        skill: Optional[str] = None,
        scheduled_date: Optional[date] = None,
        study_plan_id: Optional[str] = None,
        daily_plan_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List tasks for a user with optional filters."""
        query = self._table().select("*").eq(self.user_id_column, user_id)

        if status:
            query = query.eq("status", status)
        if skill:
            query = query.eq("skill", skill)
        if scheduled_date:
            query = query.eq("scheduled_date", scheduled_date.isoformat())
        if study_plan_id:
            query = query.eq("study_plan_id", study_plan_id)
        if daily_plan_id:
            query = query.eq("daily_plan_id", daily_plan_id)

        query = query.order("scheduled_date", nullsfirst=True).order("order_index", nullsfirst=True)

        result = self._execute(query)
        return result.data or []

    def complete(self, task_id: str, user_id: str, duration_minutes: Optional[int] = None) -> Dict[str, Any]:
        """
        Mark a task as completed.

        Sets completed_at to now and records the actual duration if provided.
        Also refreshes the owning daily plan's task summary.
        """
        task = self.get_by_id(task_id, user_id=user_id)

        now = datetime.now(timezone.utc).isoformat()
        payload: Dict[str, Any] = {
            "status": "completed",
            "completed_at": now,
        }
        if duration_minutes is not None:
            # If the actual time differs, update duration_minutes too.
            if int(task.get("duration_minutes") or 0) != duration_minutes:
                payload["duration_minutes"] = duration_minutes

        query = (
            self._table()
            .update(payload)
            .eq(self.id_column, task_id)
            .eq(self.user_id_column, user_id)
        )
        result = self._execute(query, "complete task")
        if not result.data:
            raise NotFoundError("Task not found")
        updated = result.data[0]

        # Refresh the daily plan summary if this task belongs to one.
        if updated.get("daily_plan_id"):
            self.refresh_daily_plan_summary(updated["daily_plan_id"])

        return updated

    def refresh_daily_plan_summary(self, daily_plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Recompute the task summary columns on the owning daily plan.
        """
        tasks_query = (
            self._table()
            .select("duration_minutes, status")
            .eq("daily_plan_id", daily_plan_id)
        )
        tasks_result = self._execute(tasks_query, "fetch tasks for summary")
        tasks = tasks_result.data or []

        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        total_minutes = sum(int(t.get("duration_minutes") or 0) for t in tasks)
        completed_minutes = sum(
            int(t.get("duration_minutes") or 0)
            for t in tasks
            if t.get("status") == "completed"
        )

        status = "scheduled"
        if total_tasks > 0 and completed_tasks == total_tasks:
            status = "completed"
        elif completed_tasks > 0:
            status = "in_progress"

        query = (
            self.db.table("daily_plans")
            .update({
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "total_minutes": total_minutes,
                "completed_minutes": completed_minutes,
                "status": status,
            })
            .eq("id", daily_plan_id)
        )
        self._execute(query, "update daily plan summary")
        return None

    # ------------------------------------------------------------------
    # Scheduler support (carry-forward, lineage, missed detection)
    # ------------------------------------------------------------------
    def list_pending_before(self, user_id: str, before_date: date) -> List[Dict[str, Any]]:
        """
        Fetch tasks scheduled strictly before `before_date` that are still
        pending or in progress (not completed/missed/skipped/rescheduled).
        """
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .lt("scheduled_date", before_date.isoformat())
            .in_("status", ("pending", "in_progress"))
            .order("scheduled_date")
            .order("priority", desc=True)
        )
        result = self._execute(query, "list overdue tasks")
        return result.data or []

    def list_for_date(self, user_id: str, day: date) -> List[Dict[str, Any]]:
        """Fetch all tasks scheduled on a specific date (any status)."""
        return self.list_for_user(user_id=user_id, scheduled_date=day)

    def count_consecutive_missed_days(self, user_id: str, today: date) -> int:
        """
        Count consecutive days (ending yesterday) where the user had at
        least one task but completed none.

        Used by the streak-saver logic in the Adaptive Scheduler.
        """
        consecutive = 0
        # Walk backwards from yesterday; stop at the first day with a
        # completion or a day with no tasks at all.
        for offset in range(1, 31):  # cap at 30 days to bound the query
            day = today - timedelta(days=offset)
            tasks = self.list_for_date(user_id, day)
            if not tasks:
                # No tasks scheduled that day — not a miss, but also not
                # a completion. Stop the streak here.
                break
            completed = any(t.get("status") == "completed" for t in tasks)
            if completed:
                break
            consecutive += 1
        return consecutive

    def list_mock_tasks(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Fetch the user's mock test tasks (full_mock / mock_section) that are
        pending or completed, ordered by scheduled date.
        """
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .in_("task_type", ("full_mock", "mock_section"))
            .order("scheduled_date")
        )
        result = self._execute(query, "list mock tasks")
        return result.data or []

    def mark_missed(self, task_id: str, user_id: str, missed_at: Optional[str] = None) -> None:
        """
        Transition a task to 'missed' and stamp missed_at.
        The original task is preserved for lineage/audit.
        """
        now = missed_at or datetime.now(timezone.utc).isoformat()
        query = (
            self._table()
            .update({"status": "missed", "missed_at": now})
            .eq(self.id_column, task_id)
            .eq(self.user_id_column, user_id)
        )
        self._execute(query, "mark task as missed")

        # Refresh the owning daily plan summary if present.
        task = self.get_by_id(task_id, user_id=user_id)
        if task.get("daily_plan_id"):
            self.refresh_daily_plan_summary(task["daily_plan_id"])

    def carry_forward(
        self,
        task: Dict[str, Any],
        user_id: str,
        target_date: date,
        priority_delta: int = 1,
        reason: str = "carried forward from previous day",
    ) -> Dict[str, Any]:
        """
        Create a clone of an overdue task on `target_date` and stamp the
        original as 'missed' with lineage (source_task_id) pointing back.

        The clone keeps the study_plan / skill / task_type / duration, is
        marked pending, and gets a bumped priority so it surfaces earlier.
        """
        source_id = task.get("id") or task.get("source_task_id")
        new_priority = max(1, min(5, int(task.get("priority") or 1) + priority_delta))

        # The daily_plan association is intentionally dropped on carry-forward:
        # the clone is placed on a new date and will be re-summarized there.
        clone = self.create(
            user_id,
            {
                "study_plan_id": task.get("study_plan_id"),
                "phase_index": task.get("phase_index"),
                "title": task.get("title", "Untitled task"),
                "skill": task.get("skill", "general"),
                "task_type": task.get("task_type", "practice_test"),
                "content_payload": task.get("content_payload"),
                "resource_id": task.get("resource_id"),
                "duration_minutes": int(task.get("duration_minutes") or 15),
                "scheduled_date": target_date.isoformat(),
                "priority": new_priority,
                "status": "pending",
                "is_mandatory": bool(task.get("is_mandatory") or False),
                "order_index": task.get("order_index"),
                "xp_reward": int(task.get("xp_reward") or 10),
                "difficulty": int(task.get("difficulty") or 1),
                "week_index": task.get("week_index"),
                "source_task_id": source_id,
            },
        )

        # Mark the original as missed (idempotent).
        self.mark_missed(source_id, user_id)

        return clone

    def reschedule_for_date(
        self,
        task_id: str,
        user_id: str,
        target_date: date,
        priority_delta: int = 0,
    ) -> Dict[str, Any]:
        """
        Move an existing (non-overdue) task to a new date.
        Returns the updated task row.
        """
        now = datetime.now(timezone.utc).isoformat()
        payload: Dict[str, Any] = {
            "scheduled_date": target_date.isoformat(),
            "status": "pending",
        }
        if priority_delta:
            current = self.get_by_id(task_id, user_id=user_id)
            new_priority = max(1, min(5, int(current.get("priority") or 1) + priority_delta))
            payload["priority"] = new_priority
        payload["updated_at"] = now

        query = (
            self._table()
            .update(payload)
            .eq(self.id_column, task_id)
            .eq(self.user_id_column, user_id)
        )
        result = self._execute(query, "reschedule task")
        if not result.data:
            raise NotFoundError("Task not found")
        return result.data[0]

    # ------------------------------------------------------------------
    # Task-resource linking
    # ------------------------------------------------------------------
    def link_resource(self, task_id: str, resource_id: str, relation: str) -> Dict[str, Any]:
        """Attach a resource to a task via the task_resources join table."""
        payload = {
            "task_id": task_id,
            "resource_id": resource_id,
            "relation": relation,
        }
        query = self.db.table("task_resources").insert(payload)
        result = self._execute(query, "link resource to task")
        if not result.data:
            raise ConflictError("Failed to link resource to task")
        return result.data[0]

    def unlink_resource(self, task_id: str, resource_id: str) -> None:
        """Detach a resource from a task."""
        query = (
            self.db.table("task_resources")
            .delete()
            .eq("task_id", task_id)
            .eq("resource_id", resource_id)
        )
        result = self._execute(query, "unlink resource from task")
        if not result.data:
            raise NotFoundError("Resource link not found")

    def list_resources(self, task_id: str) -> List[Dict[str, Any]]:
        """List resources attached to a task (joined with resource details)."""
        query = (
            self.db.table("task_resources")
            .select("task_id, resource_id, relation, resources(*)")
            .eq("task_id", task_id)
        )
        result = self._execute(query, "list task resources")
        if not result.data:
            return []

        resources = []
        for row in result.data:
            resource = row.get("resources")
            if resource:
                resource = dict(resource)
                resource["relation"] = row.get("relation", "supplementary")
                resources.append(resource)
        return resources