"""
Repository for the Achievement domain entity.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class AchievementRepository(BaseRepository):
    """Data access for the achievements catalog and user_achievements tables."""

    table_name = "achievements"
    _ownable = False  # achievements is a shared catalog, not user-owned

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Catalog CRUD
    # ------------------------------------------------------------------
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new achievement catalog entry."""
        query = self._table().insert(data)
        result = self._execute(query, "create achievement")
        if not result.data:
            raise ConflictError("Failed to create achievement")
        return result.data[0]

    def list_catalog(
        self,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """List achievement catalog entries with optional filters."""
        query = self._table().select("*")

        if category:
            query = query.eq("category", category)
        if is_active is not None:
            query = query.eq("is_active", is_active)

        query = query.order("category").order("points", desc=True)

        result = self._execute(query)
        return result.data or []

    def get_by_code(self, code: str) -> Dict[str, Any]:
        """Fetch an achievement by its unique code."""
        query = self._table().select("*").eq("code", code).limit(1)
        result = self._execute(query)
        if not result.data:
            raise NotFoundError("Achievement not found")
        return result.data[0]

    # ------------------------------------------------------------------
    # User achievements
    # ------------------------------------------------------------------
    def award(self, user_id: str, achievement_id: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Award an achievement to a user.

        Raises ConflictError if the user already has this achievement.
        """
        # Ensure the achievement exists.
        self.get_by_id(achievement_id)

        payload = {
            "user_id": user_id,
            "achievement_id": achievement_id,
            "meta": meta or {},
        }
        query = self.db.table("user_achievements").insert(payload)
        result = self._execute(query, "award achievement")
        if not result.data:
            raise ConflictError("Achievement already awarded to this user")
        return result.data[0]

    def list_user_achievements(self, user_id: str) -> List[Dict[str, Any]]:
        """List all achievements earned by a user, with catalog details."""
        query = (
            self.db.table("user_achievements")
            .select("id, achievement_id, earned_at, meta, achievements(*)")
            .eq("user_id", user_id)
            .order("earned_at", desc=True)
        )
        result = self._execute(query, "list user achievements")
        if not result.data:
            return []

        achievements = []
        for row in result.data:
            catalog = row.get("achievements")
            if catalog:
                catalog = dict(catalog)
                catalog["earned_at"] = row.get("earned_at")
                catalog["user_achievement_id"] = row.get("id")
                catalog["award_meta"] = row.get("meta")
                achievements.append(catalog)
        return achievements

    def has_achievement(self, user_id: str, achievement_id: str) -> bool:
        """Check whether a user has already earned an achievement."""
        query = (
            self.db.table("user_achievements")
            .select("id")
            .eq("user_id", user_id)
            .eq("achievement_id", achievement_id)
            .limit(1)
        )
        result = self._execute(query)
        return bool(result.data)

    def count_user_achievements(self, user_id: str) -> int:
        """Count how many achievements a user has earned."""
        query = (
            self.db.table("user_achievements")
            .select("*", count="exact")
            .eq("user_id", user_id)
        )
        result = self._execute(query)
        return result.count or 0

    def delete_user_achievement(self, user_id: str, user_achievement_id: str) -> None:
        """Remove an achievement from a user (admin/un-earn)."""
        query = (
            self.db.table("user_achievements")
            .delete()
            .eq("id", user_achievement_id)
            .eq("user_id", user_id)
        )
        result = self._execute(query, "remove user achievement")
        if not result.data:
            raise NotFoundError("User achievement not found")