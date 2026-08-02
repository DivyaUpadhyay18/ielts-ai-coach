"""
Resource catalog and bookmark endpoints.
"""
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.api.deps import get_current_user, get_resource_repo
from app.models.resource import (
    ResourceCreate,
    ResourceUpdate,
    ResourceResponse,
    ResourceBookmarkCreate,
)
from app.repositories.resource_repo import ResourceRepository

router = APIRouter()


@router.get(
    "",
    response_model=List[ResourceResponse],
    summary="List resources (published catalog)",
)
async def list_resources(
    skill: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(0, ge=0),
    repo: ResourceRepository = Depends(get_resource_repo),
):
    """List published resources from the catalog with optional filter parameters."""
    return repo.list_catalog(
        skill=skill,
        type=type,
        module=module,
        difficulty=difficulty,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/bookmarks",
    response_model=List[ResourceResponse],
    summary="List my bookmarked resources",
)
async def list_my_bookmarks(
    user_id: str = Depends(get_current_user),
    repo: ResourceRepository = Depends(get_resource_repo),
):
    """List all resources the current user has bookmarked."""
    return repo.list_bookmarks(user_id)


@router.post(
    "/bookmarks",
    response_model=dict,
    status_code=201,
    summary="Bookmark a resource",
)
async def add_bookmark(
    data: ResourceBookmarkCreate,
    user_id: str = Depends(get_current_user),
    repo: ResourceRepository = Depends(get_resource_repo),
):
    """Bookmark a resource for the current user."""
    bookmark = repo.add_bookmark(user_id, data.resource_id)
    return bookmark


@router.delete(
    "/bookmarks/{resource_id}",
    status_code=204,
    summary="Remove a resource bookmark",
)
async def remove_bookmark(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: ResourceRepository = Depends(get_resource_repo),
):
    """Remove a bookmark for the current user."""
    repo.remove_bookmark(user_id, resource_id)
    return None


@router.post(
    "/{resource_id}/view",
    response_model=ResourceResponse,
    summary="Increment a resource view count",
)
async def increment_view(
    resource_id: str,
    repo: ResourceRepository = Depends(get_resource_repo),
):
    """Increment the view_count of a resource and return it."""
    repo.increment_view_count(resource_id)
    return repo.get_by_id(resource_id)


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Get a resource by ID",
)
async def get_resource(
    resource_id: str,
    repo: ResourceRepository = Depends(get_resource_repo),
):
    """Fetch a single resource from the catalog."""
    return repo.get_by_id(resource_id)


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=201,
    summary="Create a resource (admin)",
)
async def create_resource(
    data: ResourceCreate,
    repo: ResourceRepository = Depends(get_resource_repo),
):
    """Create a new resource catalog entry. Admin-only in production."""
    payload = data.model_dump()
    return repo.create(payload)


@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Update a resource (admin)",
)
async def update_resource(
    resource_id: str,
    data: ResourceUpdate,
    repo: ResourceRepository = Depends(get_resource_repo),
):
    """Update a resource catalog entry. Admin-only in production."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_by_id(resource_id)
    return repo.update(resource_id, payload)


@router.delete(
    "/{resource_id}",
    status_code=204,
    summary="Delete a resource (admin)",
)
async def delete_resource(
    resource_id: str,
    repo: ResourceRepository = Depends(get_resource_repo),
):
    """Delete a resource from the catalog. Admin-only in production."""
    repo.delete(resource_id)
    return None