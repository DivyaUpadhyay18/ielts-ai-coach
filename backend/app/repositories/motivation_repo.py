"""
Repository for the Motivation Engine domain.

Persists motivation messages (`motivation_messages`) and exposes the
idempotent-delivery primitives used by the service:

  - `create_message`  → insert a message; the DB's UNIQUE
    (user_id, moment, period_key) prevents duplicate deliveries.
  - `count_for_moment` → how many messages a user has received for a moment.
    This drives the anti-repetition template rotation.
  - `list_for_user` / `get_for_period` → feed + today reads.
  - `overview` → per-moment totals.

All access is owner-scoped so users can never read/write each other's
motivation history (IDOR-safe), matching every other repository.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import ConflictError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class MotivationRepository(BaseRepository):
    """Data access for the motivation_messages table."""

    table_name = "motivation_messages"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def create_message(
        self,
        user_id: str,
        moment: str,
        period_key: str,
        title: str,
        body: str,
        tone: str,
        variant: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist a motivation message.

        Raises ConflictError when a message already exists for the same
        (user_id, moment, period_key) — the caller treats that as an idempotent
        no-op and returns the existing message.
        """
        payload = {
            "user_id": user_id,
            "moment": moment,
            "period_key": period_key,
            "title": title,
            "body": body,
            "tone": tone,
            "variant": variant or "",
            "context": context or {},
        }
        query = self._table().insert(payload)
        result = self._execute(query, "create motivation message")
        if not result.data:
            raise ConflictError("Failed to create motivation message")
        return result.data[0]

    def get_for_period(
        self, user_id: str, moment: str, period_key: str
    ) -> Optional[Dict[str, Any]]:
        """Return the existing message for (moment, period_key), if any."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .eq("moment", moment)
            .eq("period_key", period_key)
            .limit(1)
        )
        result = self._execute(query, "get motivation message for period")
        if not result.data:
            return None
        return result.data[0]

    def count_for_moment(self, user_id: str, moment: str) -> int:
        """How many messages the user has received for a moment."""
        query = (
            self._table()
            .select("id", count="exact")
            .eq(self.user_id_column, user_id)
            .eq("moment", moment)
        )
        result = self._execute(query, "count motivation messages for moment")
        return result.count or 0

    def total_for_user(self, user_id: str) -> int:
        """Total stored motivation messages for the user."""
        query = (
            self._table()
            .select("id", count="exact")
            .eq(self.user_id_column, user_id)
        )
        result = self._execute(query, "count motivation messages")
        return result.count or 0

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_for_user(
        self,
        user_id: str,
        moment: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List the user's motivation messages, newest first."""
        query = self._table().select("*").eq(self.user_id_column, user_id)
        if moment:
            query = query.eq("moment", moment)
        query = query.order("created_at", desc=True).limit(limit).offset(offset)
        result = self._execute(query, "list motivation messages")
        return result.data or []

    def counts_by_moment(self, user_id: str) -> Dict[str, int]:
        """Return {moment: message_count} for every known moment."""
        from app.models.motivation import MOTIVATION_MOMENTS

        counts: Dict[str, int] = {}
        for moment in MOTIVATION_MOMENTS:
            counts[moment] = self.count_for_moment(user_id, moment)
        return counts

    def latest_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return the user's most recent motivation message, if any."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        result = self._execute(query, "get latest motivation message")
        if not result.data:
            return None
        return result.data[0]