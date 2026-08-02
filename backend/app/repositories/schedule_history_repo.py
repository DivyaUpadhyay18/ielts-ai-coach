"""
Repository for Schedule History domain.

Provides data access methods for tracking and querying schedule changes.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.db.session import get_db
from app.models.schedule_history import ScheduleHistoryFilter


class ScheduleHistoryRepository:
    """Repository for schedule history operations."""

    def __init__(self, db=None):
        self.db = db or get_db()

    async def create_entry(
        self,
        user_id: str,
        previous_schedule: Dict[str, Any],
        new_schedule: Dict[str, Any],
        change_reason: str,
        change_type: str = "scheduler_run",
        study_plan_id: Optional[str] = None,
        run_id: Optional[str] = None,
        trigger_type: Optional[str] = None,
        metrics_before: Optional[Dict[str, Any]] = None,
        metrics_after: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
        adjustments_count: int = 0,
        tasks_affected: int = 0,
    ) -> Dict[str, Any]:
        """Create a new schedule history entry."""
        query = """
            INSERT INTO public.schedule_history (
                user_id, study_plan_id, run_id, previous_schedule, new_schedule,
                change_reason, change_type, trigger_type, metrics_before, metrics_after,
                summary, adjustments_count, tasks_affected
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
        """
        values = (
            user_id,
            study_plan_id,
            run_id,
            previous_schedule,
            new_schedule,
            change_reason,
            change_type,
            trigger_type,
            metrics_before or {},
            metrics_after or {},
            summary,
            adjustments_count,
            tasks_affected,
        )
        
        result = await self.db.fetchrow(query, *values)
        return dict(result) if result else None

    async def get_by_id(self, history_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a schedule history entry by ID."""
        query = """
            SELECT * FROM public.schedule_history
            WHERE id = $1 AND user_id = $2
        """
        result = await self.db.fetchrow(query, history_id, user_id)
        return dict(result) if result else None

    async def list_history(
        self,
        user_id: str,
        filters: ScheduleHistoryFilter,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List schedule history with filters and pagination."""
        # Build WHERE clause
        where_clauses = ["user_id = $1"]
        params = [user_id]
        param_index = 2

        if filters.change_type:
            where_clauses.append(f"change_type = ${param_index}")
            params.append(filters.change_type)
            param_index += 1

        if filters.user_action:
            where_clauses.append(f"user_action = ${param_index}")
            params.append(filters.user_action)
            param_index += 1

        if filters.study_plan_id:
            where_clauses.append(f"study_plan_id = ${param_index}")
            params.append(filters.study_plan_id)
            param_index += 1

        if filters.from_date:
            where_clauses.append(f"created_at >= ${param_index}")
            params.append(filters.from_date)
            param_index += 1

        if filters.to_date:
            where_clauses.append(f"created_at <= ${param_index}")
            params.append(filters.to_date)
            param_index += 1

        where_clause = " AND ".join(where_clauses)

        # Get total count
        count_query = f"""
            SELECT COUNT(*) FROM public.schedule_history
            WHERE {where_clause}
        """
        total = await self.db.fetchval(count_query, *params)

        # Get paginated results
        query = f"""
            SELECT * FROM public.schedule_history
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_index} OFFSET ${param_index + 1}
        """
        params.extend([filters.limit, filters.offset])
        
        results = await self.db.fetch(query, *params)
        items = [dict(row) for row in results]

        return items, total

    async def update_user_action(
        self,
        history_id: str,
        user_id: str,
        user_action: str,
        user_action_notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update user action on a schedule history entry."""
        query = """
            UPDATE public.schedule_history
            SET user_action = $1, user_action_at = NOW(), user_action_notes = $2
            WHERE id = $3 AND user_id = $4
            RETURNING *
        """
        result = await self.db.fetchrow(query, user_action, user_action_notes, history_id, user_id)
        return dict(result) if result else None

    async def get_comparison(
        self,
        user_id: str,
        history_id_1: str,
        history_id_2: str,
    ) -> Optional[Dict[str, Any]]:
        """Get comparison between two schedule history entries."""
        query = """
            SELECT * FROM public.get_schedule_comparison($1, $2, $3)
        """
        result = await self.db.fetchrow(query, user_id, history_id_1, history_id_2)
        return dict(result) if result else None

    async def get_latest(self, user_id: str, limit: int = 1) -> List[Dict[str, Any]]:
        """Get the latest schedule history entries."""
        query = """
            SELECT * FROM public.schedule_history
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        results = await self.db.fetch(query, user_id, limit)
        return [dict(row) for row in results]

    async def get_by_run_id(self, run_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get schedule history entry by run ID."""
        query = """
            SELECT * FROM public.schedule_history
            WHERE run_id = $1 AND user_id = $2
        """
        result = await self.db.fetchrow(query, run_id, user_id)
        return dict(result) if result else None

    async def get_stats(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get schedule history statistics."""
        query = """
            SELECT 
                COUNT(*) as total_changes,
                COUNT(CASE WHEN change_type = 'scheduler_run' THEN 1 END) as scheduler_runs,
                COUNT(CASE WHEN change_type = 'exam_date_update' THEN 1 END) as exam_date_updates,
                COUNT(CASE WHEN change_type = 'manual_reschedule' THEN 1 END) as manual_reschedules,
                COUNT(CASE WHEN change_type = 'study_plan_regeneration' THEN 1 END) as regenerations,
                COUNT(CASE WHEN user_action = 'accepted' THEN 1 END) as accepted,
                COUNT(CASE WHEN user_action = 'rejected' THEN 1 END) as rejected,
                COUNT(CASE WHEN user_action = 'modified' THEN 1 END) as modified,
                COUNT(CASE WHEN user_action = 'auto_applied' THEN 1 END) as auto_applied,
                SUM(adjustments_count) as total_adjustments,
                SUM(tasks_affected) as total_tasks_affected
            FROM public.schedule_history
            WHERE user_id = $1
            AND created_at >= NOW() - INTERVAL '1 day' * $2
        """
        result = await self.db.fetchrow(query, user_id, days)
        return dict(result) if result else {}

    async def delete_old_entries(self, user_id: str, older_than_days: int = 365) -> int:
        """Delete schedule history entries older than specified days."""
        query = """
            DELETE FROM public.schedule_history
            WHERE user_id = $1
            AND created_at < NOW() - INTERVAL '1 day' * $2
        """
        result = await self.db.execute(query, user_id, older_than_days)
        return result