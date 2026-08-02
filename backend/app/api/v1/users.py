"""
User profile endpoints: fetch profile, update profile, goals, and preferences.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_user_repo
from app.models.user import (
    UserProfileUpdate,
    UserGoalsUpdate,
    UserResponse,
)
from app.models.notification import NotificationPreferencesUpdate
from app.repositories.user_repo import UserRepository

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_my_profile(
    user_id: str = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
):
    """Fetch the authenticated user's full profile."""
    return repo.get_profile(user_id)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
async def update_my_profile(
    data: UserProfileUpdate,
    user_id: str = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
):
    """Update profile fields (full_name, avatar_url, country, timezone, preferences)."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_profile(user_id)

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    return repo.update_profile(user_id, payload)


@router.patch(
    "/me/goals",
    response_model=UserResponse,
    summary="Update current user IELTS goals",
)
async def update_my_goals(
    data: UserGoalsUpdate,
    user_id: str = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
):
    """Update IELTS goals: target_band, exam_date, module, daily budget, current_band."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_profile(user_id)

    # Convert date to ISO string for storage.
    if "exam_date" in payload and payload["exam_date"] is not None:
        payload["exam_date"] = payload["exam_date"].isoformat()

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    return repo.update_goals(user_id, payload)


@router.patch(
    "/me/preferences",
    response_model=dict,
    summary="Update user notification preferences",
)
async def update_my_preferences(
    data: NotificationPreferencesUpdate,
    user_id: str = Depends(get_current_user),
    repo: UserRepository = Depends(get_user_repo),
):
    """Update notification preferences (stored under user.preferences.notifications)."""
    payload = data.model_dump(exclude_none=True)
    updated = repo.update_preferences(user_id, payload)
    prefs = updated.get("preferences") or {}
    return {"preferences": prefs.get("notifications", {})}