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

    # ─── Enhanced Catalog with Advanced Filtering ─────────────────

    SORT_FIELDS = {
        "name": "title",
        "rating": "rating",
        "popularity": "popularity_score",
        "time": "estimated_time",
        "created": "created_at",
        "duration": "estimated_time",
    }

    def list_catalog_advanced(
        self,
        skill: Optional[str] = None,
        sub_skill: Optional[str] = None,
        type: Optional[str] = None,
        difficulty: Optional[str] = None,
        minimum_band: Optional[float] = None,
        maximum_band: Optional[float] = None,
        estimated_time_min: Optional[int] = None,
        estimated_time_max: Optional[int] = None,
        source: Optional[str] = None,
        is_free: Optional[bool] = None,
        verified: Optional[bool] = None,
        official: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = "popularity",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List resources with comprehensive filters and sorting."""
        query = self._table().select("*")

        if skill:
            query = query.eq("skill", skill)
        if sub_skill:
            query = query.eq("sub_skill", sub_skill)
        if type:
            query = query.eq("type", type)
        if difficulty:
            query = query.eq("difficulty", difficulty)
        if minimum_band is not None:
            query = query.gte("minimum_band", minimum_band)
        if maximum_band is not None:
            query = query.lte("maximum_band", maximum_band)
        if estimated_time_min is not None:
            query = query.gte("estimated_time", estimated_time_min)
        if estimated_time_max is not None:
            query = query.lte("estimated_time", estimated_time_max)
        if source:
            query = query.eq("source", source)
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

        sort_column = self.SORT_FIELDS.get(sort_by or "popularity", "popularity_score")
        if sort_order == "asc":
            query = query.order(sort_column)
        else:
            query = query.order(sort_column, desc=True)

        query = query.limit(limit).offset(offset)

        result = self._execute(query, "list catalog with advanced filters")
        return result.data or []

    def get_sub_skills(self, skill: str) -> List[str]:
        """Get all unique sub_skills for a given skill."""
        query = (
            self._table()
            .select("sub_skill")
            .eq("skill", skill)
            .neq("sub_skill", None)
            .order("sub_skill")
        )
        result = self._execute(query, "get sub-skills")
        return list(
            dict.fromkeys(
                row.get("sub_skill") for row in (result.data or [])
                if row.get("sub_skill")
            )
        )

    def get_sources(self) -> List[str]:
        """Get all unique sources."""
        query = (
            self._table()
            .select("source")
            .neq("source", None)
            .order("source")
        )
        result = self._execute(query, "get sources")
        return list(
            dict.fromkeys(
                row.get("source") for row in (result.data or [])
                if row.get("source")
            )
        )

    # ─── User-Specific Views ───────────────────────────────────────

    def record_view(self, user_id: str, resource_id: str) -> None:
        """Record that a user viewed a resource (for recently viewed tracking)."""
        payload = {
            "user_id": user_id,
            "resource_id": resource_id,
            "viewed": True,
        }
        query = self.db.table("recommendation_resource_view").upsert(
            payload,
            on_conflict="user_id:resource_id",
        )
        try:
            self._execute(query, "record resource view")
        except Exception:
            pass

    def record_completion(self, user_id: str, resource_id: str) -> None:
        """Record that a user completed a resource."""
        payload = {
            "user_id": user_id,
            "resource_id": resource_id,
            "viewed": True,
            "completed": True,
        }
        query = self.db.table("recommendation_resource_view").upsert(
            payload,
            on_conflict="user_id:resource_id",
        )
        try:
            self._execute(query, "record resource completion")
        except Exception:
            pass

    def get_bookmarked(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get a user's bookmarked resources with resource details."""
        query = (
            self.db.table("resource_bookmarks")
            .select("resource_id, created_at, resources(*)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self._execute(query, "get bookmarked resources")
        return [
            dict(row.get("resources") or {}, bookmarked_at=row.get("created_at"))
            for row in (result.data or [])
            if row.get("resources")
        ]

    def get_completed(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get a user's completed resources with resource details."""
        query = (
            self.db.table("recommendation_resource_view")
            .select("resource_id, completed_at, resources(*)")
            .eq("user_id", user_id)
            .eq("completed", True)
            .order("updated_at", desc=True)
            .limit(limit)
        )
        result = self._execute(query, "get completed resources")
        return [
            dict(row.get("resources") or {}, completed_at=row.get("completed_at"))
            for row in (result.data or [])
            if row.get("resources")
        ]

    def get_recently_viewed(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get a user's recently viewed resources with resource details."""
        query = (
            self.db.table("recommendation_resource_view")
            .select("resource_id, viewed, completed, updated_at, resources(*)")
            .eq("user_id", user_id)
            .eq("viewed", True)
            .order("updated_at", desc=True)
            .limit(limit)
        )
        result = self._execute(query, "get recently viewed resources")
        return [
            dict(row.get("resources") or {}, viewed=True, completed=row.get("completed", False))
            for row in (result.data or [])
            if row.get("resources")
        ]

    def get_bookmarked_ids(self, user_id: str) -> List[str]:
        """Get just the resource IDs that a user has bookmarked."""
        query = (
            self.db.table("resource_bookmarks")
            .select("resource_id")
            .eq("user_id", user_id)
        )
        result = self._execute(query, "get bookmarked resource IDs")
        return [row.get("resource_id") for row in (result.data or []) if row.get("resource_id")]

    def get_user_resource_flags(self, user_id: str) -> Dict[str, List[str]]:
        """Get all user resource flags (bookmarked, completed, viewed IDs)."""
        return {
            "bookmarked": self.get_bookmarked_ids(user_id),
            "completed": [],
            "viewed": [],
        }