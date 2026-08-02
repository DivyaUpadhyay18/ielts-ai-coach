"""
Resource Management API endpoints.

Provides full CRUD for the resource catalog:
- GET /api/v1/resources - List catalog with filters
- GET /api/v1/resources/{resource_id} - Get by ID
- POST /api/v1/resources - Create resource
- PATCH /api/v1/resources/{resource_id} - Update resource
- DELETE /api/v1/resources/{resource_id} - Delete resource
- GET /api/v1/resources/search - Search resources
- GET /api/v1/resources/stats - Get catalog statistics
- GET /api/v1/resources/by-skill/{skill} - Get by skill
- GET /api/v1/resources/by-type/{type} - Get by type
- GET /api/v1/resources/verified - Get verified resources
- GET /api/v1/resources/official - Get official resources
- GET /api/v1/resources/free - Get free resources
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.api.deps import get_current_user, get_resource_management_repo
from app.models.resource_management import (
    ResourceCreate,
    ResourceResponse,
    ResourceSearchFilters,
    ResourceUpdate,
)
from app.repositories.resource_management_repo import ResourceRepository
from app.services.resource_management_service import ResourceManagementService

router = APIRouter()


@router.get(
    "",
    response_model=ResourceResponse,
    summary="List resources (catalog)",
)
async def list_resources(
    skill: Optional[str] = Query(None, description="Filter by skill"),
    type: Optional[str] = Query(None, description="Filter by resource type"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    minimum_band: Optional[float] = Query(None, ge=0.0, le=9.0, description="Minimum band score"),
    maximum_band: Optional[float] = Query(None, ge=0.0, le=9.0, description="Maximum band score"),
    is_free: Optional[bool] = Query(None, description="Filter by free status"),
    verified: Optional[bool] = Query(None, description="Filter by verified status"),
    official: Optional[bool] = Query(None, description="Filter by official status"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """List resources from the catalog with optional filter parameters."""
    items = repo.list_catalog(
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
    return items


@router.get(
    "/search",
    response_model=ResourceResponse,
    summary="Search resources",
)
async def search_resources(
    skill: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    minimum_band: Optional[float] = Query(None),
    maximum_band: Optional[float] = Query(None),
    is_free: Optional[bool] = Query(None),
    verified: Optional[bool] = Query(None),
    official: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Search resources with multiple filter criteria."""
    items = repo.search(
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
    return items


@router.get(
    "/stats",
    response_model=dict,
    summary="Get resource catalog statistics",
)
async def get_resource_stats(
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Get statistics about the resource catalog."""
    return repo.get_stats()


@router.get(
    "/by-skill/{skill}",
    response_model=ResourceResponse,
    summary="Get resources by skill",
)
async def get_resources_by_skill(
    skill: str,
    limit: int = Query(20, ge=1, le=100),
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Get resources filtered by skill."""
    return repo.get_by_skill(skill, limit=limit)


@router.get(
    "/by-type/{resource_type}",
    response_model=ResourceResponse,
    summary="Get resources by type",
)
async def get_resources_by_type(
    resource_type: str,
    limit: int = Query(20, ge=1, le=100),
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Get resources filtered by type."""
    return repo.get_by_type(resource_type, limit=limit)


@router.get(
    "/verified",
    response_model=ResourceResponse,
    summary="Get verified resources",
)
async def get_verified_resources(
    limit: int = Query(20, ge=1, le=100),
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Get verified resources."""
    return repo.get_verified(limit=limit)


@router.get(
    "/official",
    response_model=ResourceResponse,
    summary="Get official resources",
)
async def get_official_resources(
    limit: int = Query(20, ge=1, le=100),
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Get official resources."""
    return repo.get_official(limit=limit)


@router.get(
    "/free",
    response_model=ResourceResponse,
    summary="Get free resources",
)
async def get_free_resources(
    limit: int = Query(20, ge=1, le=100),
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Get free resources."""
    return repo.get_free(limit=limit)


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Get a resource by ID",
)
async def get_resource(
    resource_id: str,
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Fetch a single resource by ID."""
    return repo.get_by_id(resource_id)


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=201,
    summary="Create a resource",
)
async def create_resource(
    data: ResourceCreate,
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Create a new resource catalog entry."""
    return repo.create(data.model_dump())


@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Update a resource",
)
async def update_resource(
    resource_id: str,
    data: ResourceUpdate,
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Update a resource catalog entry."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_by_id(resource_id)
    return repo.update(resource_id, payload)


@router.delete(
    "/{resource_id}",
    status_code=204,
    summary="Delete a resource",
)
async def delete_resource(
    resource_id: str,
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Delete a resource from the catalog."""
    repo.delete(resource_id)
    return None


@router.post(
    "/{resource_id}/popularity",
    response_model=ResourceResponse,
    summary="Increment resource popularity",
)
async def increment_popularity(
    resource_id: str,
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Increment the popularity score of a resource."""
    return repo.increment_popularity(resource_id)


@router.post(
    "/{resource_id}/rating",
    response_model=ResourceResponse,
    summary="Update resource rating",
)
async def update_rating(
    resource_id: str,
    rating: float = Query(..., ge=0.0, le=5.0, description="New rating value"),
    repo: ResourceRepository = Depends(get_resource_management_repo),
):
    """Update the rating of a resource."""
    return repo.increment_rating(resource_id, rating)