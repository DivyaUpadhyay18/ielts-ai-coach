"""
Repository for the User domain entity.
"""
from typing import Any, Dict, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Data access for the users table."""

    table_name = "users"
    _ownable = False  # users are keyed by their own id, not a user_id column

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetch the full profile for a user."""
        query = (
            self._table()
            .select("*")
            .eq(self.id_column, user_id)
        )
        result = self._execute(query)
        if not result.data:
            raise NotFoundError("User not found")
        return result.data[0]

    def update_profile(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update profile fields for a user."""
        query = self._table().update(data).eq(self.id_column, user_id)
        result = self._execute(query)
        if not result.data:
            raise NotFoundError("User not found")
        return result.data[0]

    def update_goals(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update the user's IELTS goals (band targets, exam date, module)."""
        query = self._table().update(data).eq(self.id_column, user_id)
        result = self._execute(query)
        if not result.data:
            raise NotFoundError("User not found")
        return result.data[0]

    def update_preferences(self, user_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge notification preferences into the user's preferences JSONB column.

        The stored shape is:
            preferences: {"notifications": {...}}
        """
        # Fetch current preferences first to do a proper merge.
        current = self.get_profile(user_id)
        current_prefs = current.get("preferences") or {}

        # Merge notification preferences into a nested "notifications" key.
        notif_prefs = current_prefs.get("notifications") or {}
        for key, value in preferences.items():
            if value is not None:
                notif_prefs[key] = value
        current_prefs["notifications"] = notif_prefs

        query = self._table().update({"preferences": current_prefs}).eq(self.id_column, user_id)
        result = self._execute(query)
        if not result.data:
            raise NotFoundError("User not found")
        return result.data[0]