"""
Achievement catalog and user achievement endpoints.
"""
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.api.deps import get_current_user, get_achievement_repo
from app.models.achievement import (
    AchievementCreate,
    AchievementUpdate,
    AchievementResponse,
    UserAchievementResponse,
    AwardAchievementRequest,
)
from app.repositories.achievement_repo import AchievementRepository

router = APIRouter()


@router.get(
    "",
    response_model=List[AchievementResponse],
    summary="List achievement catalog",
)
async def list_achievements(
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    repo: AchievementRepository = Depends(get_achievement_repo),
):
    """List all achievements from the catalog with optional filters."""
    return repo.list_catalog(category=category, is_active=is_active)


@router.post(
    "",
    response_model=AchievementResponse,
    status_code=201,
    summary="Create an achievement (admin)",
)
async def create_achievement(
    data: AchievementCreate,
    repo: AchievementRepository = Depends(get_achievement_repo),
):
    """Create a new achievement catalog entry. Admin-only in production."""
    payload = data.model_dump()
    return repo.create(payload)


@router.get(
    "/me",
    response_model=List[AchievementResponse],
    summary="List my earned achievements",
)
async def list_my_achievements(
    user_id: str = Depends(get_current_user),
    repo: AchievementRepository = Depends(get_achievement_repo),
):
    """List all achievements earned by the current user."""
    return repo.list_user_achievements(user_id)


@router.post(
    "/me/award",
    response_model=UserAchievementResponse,
    status_code=201,
    summary="Award an achievement to me",
)
async def award_achievement(
    data: AwardAchievementRequest,
    user_id: str = Depends(get_current_user),
    repo: AchievementRepository = Depends(get_achievement_repo),
):
    """Award an achievement to the current user."""
    result = repo.award(user_id, data.achievement_id, data.meta)
    # Attach catalog details for the response.
    achievement = repo.get_by_id(data.achievement_id)
    return {
        **result,
        "achievement": achievement,
    }


@router.delete(
    "/me/{user_achievement_id}",
    status_code=204,
    summary="Remove an earned achievement",
)
async def remove_my_achievement(
    user_achievement_id: str,
    user_id: str = Depends(get_current_user),
    repo: AchievementRepository = Depends(get_achievement_repo),
):
    """Remove an achievement earned by the current user."""
    repo.delete_user_achievement(user_id, user_achievement_id)
    return None


@router.get(
    "/{achievement_id}",
    response_model=AchievementResponse,
    summary="Get an achievement by ID",
)
async def get_achievement(
    achievement_id: str,
    repo: AchievementRepository = Depends(get_achievement_repo),
):
    """Fetch a single achievement from the catalog."""
    return repo.get_by_id(achievement_id)


@router.patch(
    "/{achievement_id}",
    response_model=AchievementResponse,
    summary="Update an achievement (admin)",
)
async def update_achievement(
    achievement_id: str,
    data: AchievementUpdate,
    repo: AchievementRepository = Depends(get_achievement_repo),
):
    """Update an achievement catalog entry. Admin-only in production."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_by_id(achievement_id)
    return repo.update(achievement_id, payload)


@router.delete(
    "/{achievement_id}",
    status_code=204,
    summary="Delete an achievement (admin)",
)
async def delete_achievement(
    achievement_id: str,
    repo: AchievementRepository = Depends(get_achievement_repo),
):
    """Delete an achievement from the catalog. Admin-only in production."""
    repo.delete(achievement_id)
    return None