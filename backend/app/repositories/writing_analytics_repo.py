"""
Repository for the Writing Progress Analytics module.

Reads from the ``writing_evaluations`` and ``writing_workspace_submissions``
tables to power the Writing Progress Analytics feature.  All reads are
owner-scoped (no cross-user leakage) and return plain dicts so the service
layer can compute the analytics metrics.

Data access notes:
  - ``list_evaluations`` returns evaluated-evaluation rows with the 4-criteria
    bands, overall band, confidence, word count, strengths/weaknesses and the
    error analysis blob.
  - ``list_submissions`` returns every workspace submission (drafts and
    submitted essays) so the UI can "track every submitted essay".
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class WritingAnalyticsRepository(BaseRepository):
    """Data access for the writing evaluations / submissions tables."""

    table_name = "writing_evaluations"
    user_id_column = "user_id"
    _ownable = False

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Evaluated essays (analytics source of truth)
    # ------------------------------------------------------------------
    def list_evaluations(
        self,
        user_id: str,
        task_type: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
        days: Optional[int] = None,
        include_submission: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Return evaluated-evaluation rows for a user, newest first.

        When ``include_submission`` is true the associated submission row is
        nested under ``"submission"`` so callers can access title and writing
        time without a second query.
        """
        select = "*"
        if include_submission:
            select = "*, writing_workspace_submissions(*)"

        query = (
            self.db.table("writing_evaluations")
            .select(select)
            .eq("user_id", user_id)
            .eq("status", "evaluated")
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if task_type:
            query = query.eq("task_type", task_type)
        if days is not None and days > 0:
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            query = query.gte("created_at", cutoff)

        try:
            result = self.db.execute(query, "list writing evaluations for analytics")
            return result.data or []
        except Exception:
            # Fallback: evaluate without the join in case the FK relationship
            # is not exposed by the schema.
            return self._list_evaluations_fallback(
                user_id, task_type, limit, offset, days
            )

    def _list_evaluations_fallback(
        self,
        user_id: str,
        task_type: Optional[str],
        limit: int,
        offset: int,
        days: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Fallback query without the submission join."""
        query = (
            self.db.table("writing_evaluations")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "evaluated")
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if task_type:
            query = query.eq("task_type", task_type)
        if days is not None and days > 0:
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            query = query.gte("created_at", cutoff)
        try:
            result = self.db.execute(query, "list writing evaluations fallback")
            return result.data or []
        except Exception:
            return []

    def count_evaluations(
        self, user_id: str, task_type: Optional[str] = None
    ) -> int:
        """Count evaluated essays for a user (optional task filter)."""
        query = (
            self.db.table("writing_evaluations")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "evaluated")
        )
        if task_type:
            query = query.eq("task_type", task_type)
        try:
            result = self.db.execute(query, "count writing evaluations")
            return result.count or 0
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Every submitted essay (draft + submitted) for essay tracking
    # ------------------------------------------------------------------
    def list_submissions(
        self,
        user_id: str,
        task_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return every workspace submission, newest first."""
        query = (
            self.db.table("writing_workspace_submissions")
            .select("*, writing_evaluations(*)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if task_type:
            query = query.eq("task_type", task_type)
        try:
            result = self.db.execute(query, "list writing submissions for analytics")
            return result.data or []
        except Exception:
            return self._list_submissions_fallback(user_id, task_type, limit, offset)

    def _list_submissions_fallback(
        self,
        user_id: str,
        task_type: Optional[str],
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        query = (
            self.db.table("writing_workspace_submissions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if task_type:
            query = query.eq("task_type", task_type)
        try:
            result = self.db.execute(query, "list writing submissions fallback")
            return result.data or []
        except Exception:
            return []

    def count_submissions(
        self, user_id: str, task_type: Optional[str] = None
    ) -> int:
        """Count every workspace submission for a user."""
        query = (
            self.db.table("writing_workspace_submissions")
            .select("id", count="exact")
            .eq("user_id", user_id)
        )
        if task_type:
            query = query.eq("task_type", task_type)
        try:
            result = self.db.execute(query, "count writing submissions")
            return result.count or 0
        except Exception:
            return 0
            # is not exposed by the schema.
            return self._list_evaluations_fallback(
                user_id, task_type, limit, offset, days
            )