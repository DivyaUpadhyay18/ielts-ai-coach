"""
Resource Management Service.

Provides business logic for the resource catalog with full CRUD support.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.models.resource_management import ResourceCreate, ResourceUpdate
from app.repositories.resource_management_repo import ResourceRepository


class ResourceManagementService:
    """Service for managing resources."""

    def __init__(self, db=None):
        self.repo = ResourceRepository(db)

    async def list_catalog(
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
    ) -> tuple[List[Dict[str, Any]], int]:
        """List resources from the catalog with filters."""
        items = self.repo.list_catalog(
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
        total = len(items)
        return items, total

    def get_by_id(self, resource_id: str) -> Dict[str, Any]:
        """Get a resource by ID."""
        return self.repo.get_by_id(resource_id)

    def create(self, data: ResourceCreate) -> Dict[str, Any]:
        """Create a new resource."""
        payload = data.model_dump(exclude_none=True)
        return self.repo.create(payload)

    def update(self, resource_id: str, data: ResourceUpdate) -> Dict[str, Any]:
        """Update an existing resource."""
        payload = data.model_dump(exclude_none=True)
        if not payload:
            return self.repo.get_by_id(resource_id)
        return self.repo.update(resource_id, payload)

    def delete(self, resource_id: str) -> None:
        """Delete a resource."""
        self.repo.delete(resource_id)

    def get_by_skill(self, skill: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get resources filtered by skill."""
        return self.repo.get_by_skill(skill, limit=limit)

    def get_by_type(self, resource_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get resources filtered by type."""
        return self.repo.get_by_type(resource_type, limit=limit)

    def get_verified(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get verified resources."""
        return self.repo.get_verified(limit=limit)

    def get_official(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get official resources."""
        return self.repo.get_official(limit=limit)

    def get_free(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get free resources."""
        return self.repo.get_free(limit=limit)

    def get_by_difficulty(self, difficulty: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get resources filtered by difficulty."""
        return self.repo.get_by_difficulty(difficulty, limit=limit)

    def increment_popularity(self, resource_id: str) -> Dict[str, Any]:
        """Increment the popularity score of a resource."""
        return self.repo.increment_popularity(resource_id)

    def increment_rating(self, resource_id: str, new_rating: float) -> Dict[str, Any]:
        """Update the rating of a resource."""
        return self.repo.increment_rating(resource_id, new_rating)

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
    ) -> tuple[List[Dict[str, Any]], int]:
        """Search resources with multiple filters."""
        items = self.repo.search(
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
        total = len(items)
        return items, total

    def get_stats(self) -> Dict[str, Any]:
        """Get resource catalog statistics."""
        return self.repo.get_stats()


resource_management_service = ResourceManagementService()