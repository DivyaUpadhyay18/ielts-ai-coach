"""
Repository for the StudyPlan domain entity.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class StudyPlanRepository(BaseRepository):
    """Data access for the study_plans table."""

    table_name = "study_plans"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    def create(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new study plan for a user.

        The version is auto-assigned: the next version number after the
        user's highest existing version.
        """
        payload = dict(data)
        payload["user_id"] = user_id

        # Auto-increment version for this user.
        existing = self.list(user_id=user_id, order_by="version", descending=True, limit=1)
        next_version = 1
        if existing:
            next_version = int(existing[0].get("version", 0)) + 1
        payload["version"] = next_version

        query = self._table().insert(payload)
        result = self._execute(query, "create study plan")
        if not result.data:
            raise ConflictError("Failed to create study plan")
        return result.data[0]

    def get_active(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the user's active study plan, if any."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .eq("status", "active")
            .limit(1)
        )
        result = self._execute(query)
        if not result.data:
            return None
        return result.data[0]

    def archive_active(self, user_id: str) -> None:
        """
        Set the user's active study plan(s) to archived.
        Called before creating a new plan or when deactivating.
        """
        query = (
            self._table()
            .update({"status": "archived"})
            .eq(self.user_id_column, user_id)
            .eq("status", "active")
        )
        self._execute(query)

    def list_versions(self, user_id: str) -> List[Dict[str, Any]]:
        """List all study plans for a user, newest version first."""
        return self.list(
            user_id=user_id,
            order_by="version",
            descending=True,
        )

    def get_by_version(self, user_id: str, version: int) -> Dict[str, Any]:
        """Fetch a specific version of a user's study plan."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .eq("version", version)
            .limit(1)
        )
        result = self._execute(query)
        if not result.data:
            raise NotFoundError("Study plan not found")
        return result.data[0]