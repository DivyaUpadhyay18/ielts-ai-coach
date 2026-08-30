"""
Repository for the Resource Management domain.

Provides full data-access for the resource catalog including:
- Advanced catalog listing with filters, sorting, pagination
- CRUD operations
- Search, stats, sub-skills, sources
- User interaction tracking (views, completions, bookmarks)
- Bulk operations (create, update, delete)
- Verification workflow
- Community suggestion approval
- Admin analytics
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class ResourceRepository(BaseRepository):
    """Data access for the resources table and related user interactions."""

    table_name = "resources"
    _ownable = False  # resources is a public catalog, not user-owned

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Catalog queries
    # ------------------------------------------------------------------
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
        sort_by: str = "popularity",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List resources from the catalog with comprehensive filters."""
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
            query = query.ilike("title", f"%{search}%")

        # Sorting
        sort_map = {
            "name": "title",
            "rating": "rating",
            "popularity": "popularity_score",
            "time": "estimated_time",
            "duration": "estimated_time",
            "created": "created_at",
        }
        sort_col = sort_map.get(sort_by, "popularity_score")
        query = query.order(sort_col, desc=(sort_order == "desc"))

        query = query.range(offset, offset + limit - 1)

        result = self._execute(query)
        return result.data or []

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
        """Search resources with multiple filter criteria."""
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
            query = query.ilike("title", f"%{search}%")

        query = query.order("popularity_score", desc=True)
        query = query.range(offset, offset + limit - 1)

        result = self._execute(query)
        return result.data or []

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the resource catalog."""
        total_result = self._table().select("*", count="exact").execute()
        total = total_result.count or 0

        by_type: Dict[str, int] = {}
        type_result = self._table().select("type").execute()
        for row in (type_result.data or []):
            t = row.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        by_skill: Dict[str, int] = {}
        skill_result = self._table().select("skill").execute()
        for row in (skill_result.data or []):
            s = row.get("skill", "unknown")
            by_skill[s] = by_skill.get(s, 0) + 1

        by_difficulty: Dict[str, int] = {}
        diff_result = self._table().select("difficulty").execute()
        for row in (diff_result.data or []):
            d = row.get("difficulty", "unknown")
            by_difficulty[d] = by_difficulty.get(d, 0) + 1

        rating_result = self._table().select("rating").execute()
        ratings = [r.get("rating") for r in (rating_result.data or []) if r.get("rating") is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else None

        free_result = self._table().select("*", count="exact").eq("is_free", True).execute()
        free_count = free_result.count or 0

        verified_result = self._table().select("*", count="exact").eq("verified", True).execute()
        verified_count = verified_result.count or 0

        official_result = self._table().select("*", count="exact").eq("official", True).execute()
        official_count = official_result.count or 0

        return {
            "total_resources": total,
            "by_type": by_type,
            "by_skill": by_skill,
            "by_difficulty": by_difficulty,
            "avg_rating": avg_rating,
            "free_count": free_count,
            "verified_count": verified_count,
            "official_count": official_count,
        }

    def get_by_skill(self, skill: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get resources filtered by skill."""
        query = self._table().select("*").eq("skill", skill).order("popularity_score", desc=True).limit(limit)
        result = self._execute(query)
        return result.data or []

    def get_by_type(self, resource_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get resources filtered by type."""
        query = self._table().select("*").eq("type", resource_type).order("popularity_score", desc=True).limit(limit)
        result = self._execute(query)
        return result.data or []

    def get_verified(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get verified resources."""
        query = self._table().select("*").eq("verified", True).order("popularity_score", desc=True).limit(limit)
        result = self._execute(query)
        return result.data or []

    def get_official(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get official resources."""
        query = self._table().select("*").eq("official", True).order("popularity_score", desc=True).limit(limit)
        result = self._execute(query)
        return result.data or []

    def get_free(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get free resources."""
        query = self._table().select("*").eq("is_free", True).order("popularity_score", desc=True).limit(limit)
        result = self._execute(query)
        return result.data or []

    def get_sub_skills(self, skill: str) -> List[str]:
        """Get all unique sub-skills for a given skill."""
        query = self._table().select("sub_skill").eq("skill", skill).not_.is_("sub_skill", "null")
        result = self._execute(query)
        sub_skills = set()
        for row in (result.data or []):
            ss = row.get("sub_skill")
            if ss:
                sub_skills.add(ss)
        return sorted(sub_skills)

    def get_sources(self) -> List[str]:
        """Get all unique resource sources for filtering."""
        query = self._table().select("source").not_.is_("source", "null")
        result = self._execute(query)
        sources = set()
        for row in (result.data or []):
            s = row.get("source")
            if s:
                sources.add(s)
        return sorted(sources)

    # ------------------------------------------------------------------
    # User interaction tracking
    # ------------------------------------------------------------------
    def get_bookmarked(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get a user's bookmarked resources with resource details."""
        query = (
            self.db.table("resource_bookmarks")
            .select("resource_id, created_at, resources(*)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self._execute(query, "get_bookmarked")
        if not result.data:
            return []
        bookmarks = []
        for row in result.data:
            resource = row.get("resources")
            if resource:
                resource = dict(resource)
                resource["bookmarked_at"] = row.get("created_at")
                bookmarks.append(resource)
        return bookmarks

    def get_completed(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get a user's completed resources."""
        query = (
            self.db.table("resource_completions")
            .select("resource_id, completed_at, resources(*)")
            .eq("user_id", user_id)
            .order("completed_at", desc=True)
            .limit(limit)
        )
        result = self._execute(query, "get_completed")
        if not result.data:
            return []
        completed = []
        for row in result.data:
            resource = row.get("resources")
            if resource:
                resource = dict(resource)
                resource["completed_at"] = row.get("completed_at")
                completed.append(resource)
        return completed

    def get_recently_viewed(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get a user's recently viewed resources."""
        query = (
            self.db.table("resource_views")
            .select("resource_id, viewed_at, resources(*)")
            .eq("user_id", user_id)
            .order("viewed_at", desc=True)
            .limit(limit)
        )
        result = self._execute(query, "get_recently_viewed")
        if not result.data:
            return []
        viewed = []
        for row in result.data:
            resource = row.get("resources")
            if resource:
                resource = dict(resource)
                resource["viewed_at"] = row.get("viewed_at")
                viewed.append(resource)
        return viewed

    def get_bookmarked_ids(self, user_id: str) -> List[str]:
        """Get a user's bookmarked resource IDs."""
        query = (
            self.db.table("resource_bookmarks")
            .select("resource_id")
            .eq("user_id", user_id)
        )
        result = self._execute(query, "get_bookmarked_ids")
        return [row.get("resource_id") for row in (result.data or [])]

    def record_view(self, user_id: str, resource_id: str) -> None:
        """Record that a user viewed a resource."""
        resource = self.get_by_id(resource_id)
        new_count = int(resource.get("view_count") or 0) + 1
        self._table().update({"view_count": new_count}).eq(self.id_column, resource_id).execute()
        payload = {"user_id": user_id, "resource_id": resource_id}
        self.db.table("resource_views").insert(payload).execute()

    def record_completion(self, user_id: str, resource_id: str) -> None:
        """Record that a user completed a resource."""
        existing = (
            self.db.table("resource_completions")
            .select("id")
            .eq("user_id", user_id)
            .eq("resource_id", resource_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return
        payload = {"user_id": user_id, "resource_id": resource_id}
        self.db.table("resource_completions").insert(payload).execute()

    def increment_popularity(self, resource_id: str) -> Dict[str, Any]:
        """Increment the popularity score of a resource."""
        resource = self.get_by_id(resource_id)
        new_score = int(resource.get("popularity_score") or 0) + 1
        query = (
            self._table()
            .update({"popularity_score": new_score})
            .eq(self.id_column, resource_id)
        )
        result = self._execute(query, "increment popularity")
        if not result.data:
            raise NotFoundError("Resource not found")
        return result.data[0]

    def increment_rating(self, resource_id: str, rating: float) -> Dict[str, Any]:
        """Update the rating of a resource (averages with existing)."""
        resource = self.get_by_id(resource_id)
        current_rating = resource.get("rating")
        if current_rating is None:
            new_rating = rating
        else:
            new_rating = round((float(current_rating) + rating) / 2, 2)
        query = (
            self._table()
            .update({"rating": new_rating})
            .eq(self.id_column, resource_id)
        )
        result = self._execute(query, "update rating")
        if not result.data:
            raise NotFoundError("Resource not found")
        return result.data[0]

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------
    def bulk_create(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Bulk create resources. Returns created resources."""
        if not resources:
            return []
        query = self._table().insert(resources)
        result = self._execute(query, "bulk create resources")
        return result.data or []

    def bulk_update(self, updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Bulk update resources. Each item must have an 'id' key."""
        if not updates:
            return []
        updated = []
        for item in updates:
            resource_id = item.get("id")
            if not resource_id:
                raise ValidationError("Each bulk update item must have an 'id' field")
            update_data = {k: v for k, v in item.items() if k != "id"}
            if not update_data:
                continue
            query = (
                self._table()
                .update(update_data)
                .eq(self.id_column, resource_id)
            )
            result = self._execute(query, f"bulk update resource {resource_id}")
            if result.data:
                updated.append(result.data[0])
        return updated

    def bulk_delete(self, resource_ids: List[str]) -> Dict[str, Any]:
        """Bulk delete resources by IDs. Returns summary."""
        if not resource_ids:
            return {"deleted": 0, "not_found": []}
        deleted = 0
        not_found = []
        for resource_id in resource_ids:
            query = self._table().delete().eq(self.id_column, resource_id)
            result = self._execute(query, f"bulk delete resource {resource_id}")
            if result.data:
                deleted += 1
            else:
                not_found.append(resource_id)
        return {"deleted": deleted, "not_found": not_found}

    # ------------------------------------------------------------------
    # Verification workflow
    # ------------------------------------------------------------------
    def verify_resource(self, resource_id: str, admin_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Mark a resource as verified by an admin."""
        self.get_by_id(resource_id)
        update_data = {"verified": True}
        query = (
            self._table()
            .update(update_data)
            .eq(self.id_column, resource_id)
        )
        result = self._execute(query, "verify resource")
        if not result.data:
            raise NotFoundError("Resource not found")
        log_payload = {
            "resource_id": resource_id,
            "admin_id": admin_id,
            "action": "verified",
            "notes": notes or "",
        }
        self.db.table("resource_verification_log").insert(log_payload).execute()
        return result.data[0]

    def unverify_resource(self, resource_id: str, admin_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Remove verification status from a resource."""
        self.get_by_id(resource_id)
        update_data = {"verified": False}
        query = (
            self._table()
            .update(update_data)
            .eq(self.id_column, resource_id)
        )
        result = self._execute(query, "unverify resource")
        if not result.data:
            raise NotFoundError("Resource not found")
        log_payload = {
            "resource_id": resource_id,
            "admin_id": admin_id,
            "action": "unverified",
            "notes": notes or "",
        }
        self.db.table("resource_verification_log").insert(log_payload).execute()
        return result.data[0]

    def get_verification_log(self, resource_id: str) -> List[Dict[str, Any]]:
        """Get the verification log for a resource."""
        query = (
            self.db.table("resource_verification_log")
            .select("*")
            .eq("resource_id", resource_id)
            .order("created_at", desc=True)
        )
        result = self._execute(query, "get verification log")
        return result.data or []

# ------------------------------------------------------------------
    # Community suggestion submission & voting
    # ------------------------------------------------------------------
    def create_suggestion(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a community resource suggestion (status forced to pending)."""
        payload = {**data, "user_id": user_id, "status": "pending", "votes": 0}
        query = self.db.table("resource_suggestions").insert(payload)
        result = self._execute(query, "create suggestion")
        if not result.data:
            raise ConflictError("Failed to create suggestion")
        return result.data[0]

    def get_user_suggestions(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get the current user's own suggestions."""
        query = (
            self.db.table("resource_suggestions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        result = self._execute(query, "get user suggestions")
        return result.data or []

    def get_community_suggestions(
        self,
        category: Optional[str] = None,
        skill: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get approved suggestions for the community browse page."""
        query = self.db.table("resource_suggestions").select("*").eq("status", "approved")
        if category:
            query = query.eq("category", category)
        if skill:
            query = query.eq("skill", skill)
        query = query.order("votes", desc=True).order("created_at", desc=True).range(offset, offset + limit - 1)
        result = self._execute(query, "get community suggestions")
        return result.data or []

    def get_suggestion_vote(self, user_id: str, suggestion_id: str) -> bool:
        """Check whether a user has voted on a suggestion."""
        query = (
            self.db.table("resource_suggestion_votes")
            .select("id")
            .eq("user_id", user_id)
            .eq("suggestion_id", suggestion_id)
            .limit(1)
        )
        result = self._execute(query, "check suggestion vote")
        return bool(result.data)

    def vote_suggestion(self, user_id: str, suggestion_id: str) -> Dict[str, Any]:
        """Cast a vote on a suggestion (idempotent, prevents double-voting)."""
        self.get_suggestion_by_id(suggestion_id)
        existing = self.get_suggestion_vote(user_id, suggestion_id)
        if existing:
            suggestion = self.get_suggestion_by_id(suggestion_id)
            return {
                "suggestion_id": suggestion_id,
                "votes": suggestion.get("votes", 0),
                "voted": True,
            }
        query = self.db.table("resource_suggestion_votes").insert(
            {"user_id": user_id, "suggestion_id": suggestion_id}
        )
        result = self._execute(query, "vote suggestion")
        if not result.data:
            raise ConflictError("Failed to vote on suggestion")
        suggestion = self.get_suggestion_by_id(suggestion_id)
        return {
            "suggestion_id": suggestion_id,
            "votes": suggestion.get("votes", 0),
            "voted": True,
        }

    def unvote_suggestion(self, user_id: str, suggestion_id: str) -> Dict[str, Any]:
        """Remove a vote from a suggestion."""
        self.get_suggestion_by_id(suggestion_id)
        query = (
            self.db.table("resource_suggestion_votes")
            .delete()
            .eq("user_id", user_id)
            .eq("suggestion_id", suggestion_id)
        )
        result = self._execute(query, "unvote suggestion")
        suggestion = self.get_suggestion_by_id(suggestion_id)
        return {
            "suggestion_id": suggestion_id,
            "votes": suggestion.get("votes", 0),
            "voted": bool(result.data),
        }

    def update_suggestion(self, suggestion_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a suggestion (admin edit)."""
        self.get_suggestion_by_id(suggestion_id)
        query = self.db.table("resource_suggestions").update(data).eq("id", suggestion_id)
        result = self._execute(query, "update suggestion")
        if not result.data:
            raise NotFoundError("Suggestion not found")
        return result.data[0]

    # ------------------------------------------------------------------
    # Community suggestion approval
    # ------------------------------------------------------------------
    def get_suggestions(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get community resource suggestions for admin review."""
        query = self.db.table("resource_suggestions").select("*")
        if status:
            query = query.eq("status", status)
        query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
        result = self._execute(query, "get suggestions")
        return result.data or []

    def approve_suggestion(self, suggestion_id: str, admin_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Approve a community suggestion and create the resource."""
        suggestion = self.get_suggestion_by_id(suggestion_id)
        resource_data = {
            "title": suggestion.get("title"),
            "description": suggestion.get("description"),
            "type": suggestion.get("type"),
            "source": suggestion.get("source"),
            "author": suggestion.get("author"),
            "url": suggestion.get("url"),
            "thumbnail": suggestion.get("thumbnail"),
            "skill": suggestion.get("skill"),
            "sub_skill": suggestion.get("sub_skill"),
            "minimum_band": suggestion.get("minimum_band"),
            "maximum_band": suggestion.get("maximum_band"),
            "difficulty": suggestion.get("difficulty"),
            "estimated_time": suggestion.get("estimated_time"),
            "tags": suggestion.get("tags", []),
            "language": suggestion.get("language", "en"),
            "verified": suggestion.get("verified", False),
            "official": suggestion.get("official", False),
            "is_free": suggestion.get("is_free", True),
            "rating": suggestion.get("rating"),
            "popularity_score": suggestion.get("popularity_score", 0),
        }
        created = self.create(resource_data)
        update_data = {
            "status": "approved",
            "approved_by": admin_id,
            "approved_at": "now()",
            "admin_notes": notes or "",
            "resource_id": created.get("id"),
        }
        self.db.table("resource_suggestions").update(update_data).eq("id", suggestion_id).execute()
        return created

    def reject_suggestion(self, suggestion_id: str, admin_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Reject a community suggestion."""
        self.get_suggestion_by_id(suggestion_id)
        update_data = {
            "status": "rejected",
            "rejected_by": admin_id,
            "rejected_at": "now()",
            "admin_notes": notes or "",
        }
        result = self.db.table("resource_suggestions").update(update_data).eq("id", suggestion_id).execute()
        if not result.data:
            raise NotFoundError("Suggestion not found")
        return result.data[0]

    def get_suggestion_by_id(self, suggestion_id: str) -> Dict[str, Any]:
        """Get a single suggestion by ID."""
        query = self.db.table("resource_suggestions").select("*").eq("id", suggestion_id)
        result = self._execute(query, "get suggestion")
        if not result.data:
            raise NotFoundError("Suggestion not found")
        return result.data[0]

    # ------------------------------------------------------------------
    # Admin analytics
    # ------------------------------------------------------------------
    def get_admin_analytics(self) -> Dict[str, Any]:
        """Get analytics data for the admin dashboard."""
        total_result = self._table().select("*", count="exact").execute()
        total_resources = total_result.count or 0

        published_result = self._table().select("*", count="exact").eq("is_published", True).execute()
        published_count = published_result.count or 0

        unpublished_result = self._table().select("*", count="exact").eq("is_published", False).execute()
        unpublished_count = unpublished_result.count or 0

        verified_result = self._table().select("*", count="exact").eq("verified", True).execute()
        verified_count = verified_result.count or 0

        unverified_result = self._table().select("*", count="exact").eq("verified", False).execute()
        unverified_count = unverified_result.count or 0

        free_result = self._table().select("*", count="exact").eq("is_free", True).execute()
        free_count = free_result.count or 0

        paid_result = self._table().select("*", count="exact").eq("is_free", False).execute()
        paid_count = paid_result.count or 0

        by_type: Dict[str, int] = {}
        type_result = self._table().select("type").execute()
        for row in (type_result.data or []):
            t = row.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        by_skill: Dict[str, int] = {}
        skill_result = self._table().select("skill").execute()
        for row in (skill_result.data or []):
            s = row.get("skill", "unknown")
            by_skill[s] = by_skill.get(s, 0) + 1

        rating_result = self._table().select("rating").execute()
        ratings = [r.get("rating") for r in (rating_result.data or []) if r.get("rating") is not None]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        view_result = self._table().select("view_count").execute()
        total_views = sum(int(r.get("view_count") or 0) for r in (view_result.data or []))

        completion_result = self.db.table("resource_completions").select("*", count="exact").execute()
        total_completions = completion_result.count or 0

        bookmark_result = self.db.table("resource_bookmarks").select("*", count="exact").execute()
        total_bookmarks = bookmark_result.count or 0

        pending_suggestions_result = self.db.table("resource_suggestions").select("*", count="exact").eq("status", "pending").execute()
        pending_suggestions = pending_suggestions_result.count or 0

        top_by_views = (
            self._table()
            .select("*")
            .order("view_count", desc=True)
            .limit(10)
            .execute()
        )

        top_by_rating = (
            self._table()
            .select("*")
            .not_.is_("rating", "null")
            .order("rating", desc=True)
            .limit(10)
            .execute()
        )

        return {
            "total_resources": total_resources,
            "published_count": published_count,
            "unpublished_count": unpublished_count,
            "verified_count": verified_count,
            "unverified_count": unverified_count,
            "free_count": free_count,
            "paid_count": paid_count,
            "by_type": by_type,
            "by_skill": by_skill,
            "avg_rating": avg_rating,
            "total_views": total_views,
            "total_completions": total_completions,
            "total_bookmarks": total_bookmarks,
            "pending_suggestions": pending_suggestions,
            "top_by_views": top_by_views.data or [],
            "top_by_rating": top_by_rating.data or [],
        }

    def get_resource_analytics(self, resource_id: str) -> Dict[str, Any]:
        """Get detailed analytics for a single resource."""
        resource = self.get_by_id(resource_id)

        views_result = self.db.table("resource_views").select("*", count="exact").eq("resource_id", resource_id).execute()
        total_views = views_result.count or 0

        completions_result = self.db.table("resource_completions").select("*", count="exact").eq("resource_id", resource_id).execute()
        total_completions = completions_result.count or 0

        bookmarks_result = self.db.table("resource_bookmarks").select("*", count="exact").eq("resource_id", resource_id).execute()
        total_bookmarks = bookmarks_result.count or 0

        likes_result = self.db.table("resource_likes").select("*", count="exact").eq("resource_id", resource_id).execute()
        total_likes = likes_result.count or 0

        ratings_result = self.db.table("resource_ratings").select("rating").eq("resource_id", resource_id).execute()
        ratings = [r.get("rating") for r in (ratings_result.data or []) if r.get("rating") is not None]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
        rating_count = len(ratings)

        completion_rate = round((total_completions / total_views * 100), 2) if total_views > 0 else 0.0
        drop_off_rate = round((1 - total_completions / total_views) * 100, 2) if total_views > 0 else 0.0

        return {
            "resource": resource,
            "views": total_views,
            "completions": total_completions,
            "bookmarks": total_bookmarks,
            "likes": total_likes,
            "avg_rating": avg_rating,
            "rating_count": rating_count,
            "completion_rate": completion_rate,
            "drop_off_rate": drop_off_rate,
        }
