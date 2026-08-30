"""
Repository for the Mission Reflection domain.

Persists one reflection per completed daily mission (``mission_reflections``)
and exposes the owner-scoped primitives used by the ReflectionEngine:

  - ``create``            → insert a new reflection (UNIQUE(user, mission)).
  - ``get_for_mission``   → fetch the existing reflection for a mission (for
                            idempotent update-on-regenerate).
  - ``latest_for_user``   → feed read (newest first, owner-scoped).
  - ``count_for_user``    → totals (e.g. for dashboards).

All access is owner-scoped so users can never read/write each other's
reflections (IDOR-safe), matching every other repository.
"""
from typing import Any, Dict, List, Optional

from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class MissionReflectionRepository(BaseRepository):
    """Data access for the mission_reflections table."""

    table_name = "mission_reflections"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new mission reflection.

        Raises ``ConflictError`` when a reflection already exists for the same
        ``(user_id, mission_id)`` — the engine treats that as an idempotent
        signal to update the existing row instead.
        """
        return super().create(data)

    def update_for_mission(
        self, user_id: str, mission_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update the existing reflection for a (user, mission)."""
        existing = self.get_for_mission(user_id, mission_id)
        if not existing:
            # Let the engine fall back to create() via ConflictError.
            raise ConflictError("Reflection not found for update")
        return self.update(existing["id"], data, user_id=user_id)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get_for_mission(
        self, user_id: str, mission_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the reflection for a single (user, mission), if any."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .eq("mission_id", mission_id)
            .limit(1)
        )
        result = self._execute(query, "get mission reflection")
        if not result.data:
            return None
        return result.data[0]

    def latest_for_user(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        skill: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List the user's reflections, newest first. Optional skill filter."""
        filters = {"skill": skill} if skill else None
        return self.list(
            user_id=user_id,
            filters=filters,
            order_by="created_at",
            descending=True,
            limit=limit,
            offset=offset,
        )

    def count_for_user(self, user_id: str) -> int:
        """Total stored reflections for the user."""
        return self.count(user_id)
