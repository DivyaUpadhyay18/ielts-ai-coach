"""
Repository for the Resource Management domain.

Provides data access methods for the resources catalog.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class ResourceRepository(BaseRepository):
    """Repository for resource catalog operations."""

    table_name = "resources"
    id_column = "id"
    _ownable = False

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    def list_catalog(
        self,
        skill: Optional[str] = None,
        type: Optional[str] = None,
        difficulty: Optional[str] = None,
        minimum_band: Optional[float] = None,
        maximum_band: Optional[float] = None,
        is_free: Optional[bool] = None,
        verified: Optional[bool] = None,
        official: Optional[bool] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List resources from the catalog with optional filters."""
        query = self._table().select("*")

        if skill:
            query = query.eq("skill", skill)
        if type:
            query = query.eq("type", type)
        if difficulty:
            query = query.eq("difficulty", difficulty)
        if minimum_band is not None:
            query = query.gte("minimum_band", minimum_band)
        if maximum_band is not None:
            query = query.lte("maximum_band", maximum_band)
        if is_free is not None:
            query = query.eq("is_free", is_free)
        if verified is not None:
            query = query.eq("verified", verified)
        if official is not None:
            query = query.eq("official", official)
        if search:
            query = query.or_(
                f"title.ilike.%{search}%",
                f"description.ilike.%{search}%",
            )

        query = query.order("popularity_score", desc=True)

        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)

        result = self._execute(query)
        return result.data or []

    def get_by_skill(self, skill: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get resources filtered by skill."""
        query = (
            self._table()
            .select("*")
            .eq("skill", skill)
            .order("popularity_score", desc=True)
            .limit(limit)
        )
        result = self._execute(query)
        return result.data or []

    def get_by_type(self, resource_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get resources filtered by type."""
        query = (
            self._table()
            .select("*")
            .eq("type", resource_type)
            .order("popularity_score", desc=True)
            .limit(limit)
        )
        result = self._execute(query)
        return result.data or []

    def get_verified(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get verified resources."""
        query = (
            self._table()
            .select("*")
            .eq("verified", True)
            .order("rating", desc=True)
            .limit(limit)
        )
        result = self._execute(query)
        return result.data or []

    def get_official(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get official resources."""
        query = (
            self._table()
            .select("*")
            .eq("official", True)
            .order("popularity_score", desc=True)
            .limit(limit)
        )
        result = self._execute(query)
        return result.data or []

    def get_free(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get free resources."""
        query = (
            self._table()
            .select("*")
            .eq("is_free", True)
            .order("popularity_score", desc=True)
            .limit(limit)
        )
        result = self._execute(query)
        return result.data or []

    def get_by_difficulty(self, difficulty: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get resources filtered by difficulty."""
        query = (
            self._table()
            .select("*")
            .eq("difficulty", difficulty)
            .order("popularity_score", desc=True)
            .limit(limit)
        )
        result = self._execute(query)
        return result.data or []

    def increment_popularity(self, resource_id: str) -> Dict[str, Any]:
        """Increment the popularity score of a resource."""
        resource = self.get_by_id(resource_id)
        new_score = int(resource.get("popularity_score") or 0) + 1
        query = (
            self._table()
            .update({"popularity_score": new_score})
            .eq(self.id_column, resource_id)
        )
        self._execute(query, "increment popularity")
        return self.get_by_id(resource_id)

    def increment_rating(self, resource_id: str, new_rating: float) -> Dict[str, Any]:
        """Update the rating of a resource."""
        query = (
            self._table()
            .update({"rating": new_rating})
            .eq(self.id_column, resource_id)
        )
        self._execute(query, "update rating")
        return self.get_by_id(resource_id)

    def search(
        self,
        skill: Optional[str] = None,
        type: Optional[str] = None,
        difficulty: Optional[str] = None,
        minimum_band: Optional[float] = None,
        maximum_band: Optional[float] = None,
        is_free: Optional[bool] = None,
        verified: Optional[bool] = None,
        official: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Search resources with multiple filters."""
        return self.list_catalog(
            skill=skill,
            type=type,
            difficulty=difficulty,
            minimum_band=minimum_band,
            maximum_band=maximum_band,
            is_free=is_free,
            verified=verified,
            official=official,
            search=search,
            limit=limit,
            offset=offset,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get resource catalog statistics."""
        query = self._table().select("id, type, skill, difficulty, rating, is_free, verified, official")
        result = self._execute(query)
        items = result.data or []

        by_type: Dict[str, int] = {}
        by_skill: Dict[str, int] = {}
        by_difficulty: Dict[str, int] = {}
        total_rating = 0.0
        rating_count = 0
        free_count = 0
        verified_count = 0
        official_count = 0

        for item in items:
            t = item.get("type")
            if t:
                by_type[t] = by_type.get(t, 0) + 1

            s = item.get("skill")
            if s:
                by_skill[s] = by_skill.get(s, 0) + 1

            d = item.get("difficulty")
            if d:
                by_difficulty[d] = by_difficulty.get(d, 0) + 1

            r = item.get("rating")
            if r is not None:
                total_rating += float(r)
                rating_count += 1

            if item.get("is_free"):
                free_count += 1
            if item.get("verified"):
                verified_count += 1
            if item.get("official"):
                official_count += 1

        return {
            "total_resources": len(items),
            "by_type": by_type,
            "by_skill": by_skill,
            "by_difficulty": by_difficulty,
            "avg_rating": round(total_rating / rating_count, 2) if rating_count > 0 else None,
            "free_count": free_count,
            "verified_count": verified_count,
            "official_count": official_count,
        }