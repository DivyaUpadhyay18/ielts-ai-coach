"""
Repository for the Resource domain entity.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class ResourceRepository(BaseRepository):
    """Data access for the resources table and user resource_bookmarks."""

    table_name = "resources"
    _ownable = False  # resources is a public catalog, not user-owned

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Catalog queries
    # ------------------------------------------------------------------
    def list_catalog(
        self,
        skill: Optional[str] = None,
        type: Optional[str] = None,
        module: Optional[str] = None,
        difficulty: Optional[str] = None,
        include_unpublished: bool = False,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List resources from the public catalog.

        By default, only published resources are returned. Pass
        include_unpublished=True (admin path) to include all.
        """
        query = self._table().select("*")

        if not include_unpublished:
            query = query.eq("is_published", True)

        if skill:
            query = query.eq("skill", skill)
        if type:
            query = query.eq("type", type)
        if module:
            query = query.eq("module", module)
        if difficulty:
            query = query.eq("difficulty", difficulty)

        if search:
            query = query.ilike("title", f"%{search}%")

        query = query.order("title")

        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)

        result = self._execute(query)
        return result.data or []

    def increment_view_count(self, resource_id: str) -> None:
        """Increment the view_count for a resource using read-modify-write."""
        resource = self.get_by_id(resource_id)
        new_count = int(resource.get("view_count") or 0) + 1
        query = (
            self._table()
            .update({"view_count": new_count})
            .eq(self.id_column, resource_id)
        )
        self._execute(query, "increment view count")

    # ------------------------------------------------------------------
    # Resource bookmarks
    # ------------------------------------------------------------------
    def add_bookmark(self, user_id: str, resource_id: str) -> Dict[str, Any]:
        """Bookmark a resource for a user."""
        payload = {
            "user_id": user_id,
            "resource_id": resource_id,
        }
        query = self.db.table("resource_bookmarks").insert(payload)
        result = self._execute(query, "add resource bookmark")
        if not result.data:
            raise ConflictError("Resource already bookmarked")
        return result.data[0]

    def remove_bookmark(self, user_id: str, resource_id: str) -> None:
        """Remove a bookmark for a user."""
        query = (
            self.db.table("resource_bookmarks")
            .delete()
            .eq("user_id", user_id)
            .eq("resource_id", resource_id)
        )
        result = self._execute(query, "remove resource bookmark")
        if not result.data:
            raise NotFoundError("Bookmark not found")

    def list_bookmarks(self, user_id: str) -> List[Dict[str, Any]]:
        """List a user's bookmarked resources with resource details."""
        query = (
            self.db.table("resource_bookmarks")
            .select("resource_id, created_at, resources(*)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )
        result = self._execute(query, "list resource bookmarks")
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

    def is_bookmarked(self, user_id: str, resource_id: str) -> bool:
        """Check whether a user has bookmarked a resource."""
        query = (
            self.db.table("resource_bookmarks")
            .select("resource_id")
            .eq("user_id", user_id)
            .eq("resource_id", resource_id)
            .limit(1)
        )
        result = self._execute(query)
        return bool(result.data)