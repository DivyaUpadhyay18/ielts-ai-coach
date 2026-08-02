"""
Repository for the Adaptive Scheduler's history tables.

Persists every rollover run (schedule_runs) and the audited list of
adjustments (schedule_adjustments) so users can always see exactly what
the scheduler changed and why.
"""
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class SchedulerRepository(BaseRepository):
    """Data access for schedule_runs + schedule_adjustments."""

    table_name = "schedule_runs"
    _ownable = True

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # schedule_runs
    # ------------------------------------------------------------------
    def create_run(
        self,
        user_id: str,
        study_plan_id: Optional[str],
        trigger_type: str,
        run_date: date,
        metrics: Dict[str, Any],
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a scheduler run row."""
        payload = {
            "user_id": user_id,
            "trigger_type": trigger_type,
            "run_date": run_date.isoformat(),
            "metrics": metrics,
        }
        if study_plan_id:
            payload["study_plan_id"] = study_plan_id
        if summary:
            payload["summary"] = summary

        query = self._table().insert(payload)
        result = self._execute(query, "create scheduler run")
        if not result.data:
            raise NotFoundError("Failed to create scheduler run")
        return result.data[0]

    def list_runs(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List the user's scheduler runs, newest first."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .order("run_date", desc=True)
            .limit(limit)
            .offset(offset)
        )
        result = self._execute(query)
        return result.data or []

    def get_latest_run(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the user's most recent scheduler run, if any."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .order("run_date", desc=True)
            .limit(1)
        )
        result = self._execute(query)
        if not result.data:
            return None
        return result.data[0]

    def get_run_for_date(
        self,
        user_id: str,
        run_date: date,
        trigger_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a scheduler run for a specific date (idempotency check).

        If trigger_type is provided, only an exact match on both date and
        trigger is returned. Otherwise any run on that date is returned.
        """
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .eq("run_date", run_date.isoformat())
        )
        if trigger_type:
            query = query.eq("trigger_type", trigger_type)
        query = query.order("created_at", desc=True).limit(1)
        result = self._execute(query)
        if not result.data:
            return None
        return result.data[0]

    def get_run(self, run_id: str, user_id: str) -> Dict[str, Any]:
        """Fetch a single scheduler run (owner-scoped)."""
        return self.get_by_id(run_id, user_id=user_id)

    # ------------------------------------------------------------------
    # schedule_adjustments
    # ------------------------------------------------------------------
    def add_adjustments(
        self,
        user_id: str,
        run_id: str,
        adjustments: List[Dict[str, Any]],
    ) -> int:
        """Bulk insert adjustment rows for a run. Returns count inserted."""
        if not adjustments:
            return 0
        rows = []
        for adj in adjustments:
            row = {
                "run_id": run_id,
                "user_id": user_id,
                "action": adj.get("action", "carried_forward"),
                "reason": adj.get("reason", ""),
                "priority_delta": int(adj.get("priority_delta") or 0),
            }
            if adj.get("task_id"):
                row["task_id"] = adj["task_id"]
            if adj.get("task_title"):
                row["task_title"] = str(adj["task_title"])[:300]
            if adj.get("from_date"):
                row["from_date"] = adj["from_date"].isoformat() if hasattr(adj["from_date"], "isoformat") else str(adj["from_date"])
            if adj.get("to_date"):
                row["to_date"] = adj["to_date"].isoformat() if hasattr(adj["to_date"], "isoformat") else str(adj["to_date"])
            rows.append(row)

        query = self.db.table("schedule_adjustments").insert(rows)
        result = self._execute(query, "create schedule adjustments")
        return len(result.data or rows)

    def get_run_adjustments(self, run_id: str) -> List[Dict[str, Any]]:
        """Fetch all adjustments for a run, ordered by created_at."""
        query = (
            self.db.table("schedule_adjustments")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at")
        )
        result = self._execute(query)
        return result.data or []

    def list_adjustments(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch the user's recent adjustments across runs (newest first)."""
        query = (
            self.db.table("schedule_adjustments")
            .select("*")
            .eq(self.user_id_column, user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self._execute(query)
        return result.data or []

