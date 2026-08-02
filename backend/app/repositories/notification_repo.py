"""
Repository for the Notification domain entity.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    """Data access for the notifications table."""

    table_name = "notifications"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    def create(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new notification for a user."""
        payload = dict(data)
        payload["user_id"] = user_id
        query = self._table().insert(payload)
        result = self._execute(query, "create notification")
        if not result.data:
            raise NotFoundError("Failed to create notification")
        return result.data[0]

    def list_for_user(
        self,
        user_id: str,
        unread_only: bool = False,
        type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List notifications for a user with optional filters."""
        query = self._table().select("*").eq(self.user_id_column, user_id)

        if unread_only:
            query = query.eq("is_read", False)
        if type:
            query = query.eq("type", type)

        query = query.order("created_at", desc=True)

        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)

        result = self._execute(query)
        return result.data or []

    def mark_as_read(self, notification_id: str, user_id: str) -> Dict[str, Any]:
        """Mark a single notification as read."""
        now = datetime.now(timezone.utc).isoformat()
        query = (
            self._table()
            .update({"is_read": True, "read_at": now})
            .eq(self.id_column, notification_id)
            .eq(self.user_id_column, user_id)
        )
        result = self._execute(query, "mark notification as read")
        if not result.data:
            raise NotFoundError("Notification not found")
        return result.data[0]

    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all of a user's notifications as read. Returns count updated."""
        now = datetime.now(timezone.utc).isoformat()
        query = (
            self._table()
            .update({"is_read": True, "read_at": now})
            .eq(self.user_id_column, user_id)
            .eq("is_read", False)
        )
        result = self._execute(query, "mark all notifications as read")
        return len(result.data or [])

    def unread_count(self, user_id: str) -> int:
        """Count the user's unread notifications."""
        query = (
            self._table()
            .select("*", count="exact")
            .eq(self.user_id_column, user_id)
            .eq("is_read", False)
        )
        result = self._execute(query)
        return result.count or 0