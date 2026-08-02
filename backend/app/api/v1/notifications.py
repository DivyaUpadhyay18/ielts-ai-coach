"""
Notification CRUD endpoints.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from typing import Dict, List, Optional

from app.api.deps import get_current_user, get_notification_repo, get_user_repo
from app.models.notification import (
    NotificationCreate,
    NotificationUpdate,
    NotificationResponse,
    NotificationPreferencesUpdate,
)
from app.repositories.notification_repo import NotificationRepository
from app.repositories.user_repo import UserRepository

router = APIRouter()


@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="List notifications",
)
async def list_notifications(
    unread_only: bool = Query(False),
    type: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repo),
):
    """List notifications for the current user, newest first."""
    return repo.list_for_user(
        user_id=user_id,
        unread_only=unread_only,
        type=type,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=NotificationResponse,
    status_code=201,
    summary="Create a notification",
)
async def create_notification(
    data: NotificationCreate,
    user_id: str = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repo),
):
    """Create a new notification for the current user."""
    payload = data.model_dump()
    return repo.create(user_id, payload)


@router.get(
    "/unread-count",
    response_model=Dict[str, int],
    summary="Get unread notification count",
)
async def get_unread_count(
    user_id: str = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repo),
):
    """Return the number of unread notifications for the current user."""
    return {"count": repo.unread_count(user_id)}


@router.post(
    "/read-all",
    response_model=Dict[str, int],
    summary="Mark all notifications as read",
)
async def mark_all_read(
    user_id: str = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repo),
):
    """Mark all of the current user's notifications as read."""
    count = repo.mark_all_as_read(user_id)
    return {"updated": count}


@router.patch(
    "/preferences",
    response_model=Dict,
    summary="Update notification preferences",
)
async def update_notification_preferences(
    data: NotificationPreferencesUpdate,
    user_id: str = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
):
    """Update the current user's notification preferences (stored on user.preferences)."""
    payload = data.model_dump(exclude_none=True)
    updated = user_repo.update_preferences(user_id, payload)
    prefs = updated.get("preferences") or {}
    return {"preferences": prefs.get("notifications", {})}


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Get a notification by ID",
)
async def get_notification(
    notification_id: str,
    user_id: str = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repo),
):
    """Fetch a single notification (scoped to the current user)."""
    return repo.get_by_id(notification_id, user_id=user_id)


@router.patch(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Update a notification",
)
async def update_notification(
    notification_id: str,
    data: NotificationUpdate,
    user_id: str = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repo),
):
    """Update a notification (mark read, update body/metadata)."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_by_id(notification_id, user_id=user_id)

    # If marking as read, set read_at.
    if payload.get("is_read") is True:
        payload["read_at"] = datetime.utcnow().isoformat()

    return repo.update(notification_id, payload, user_id=user_id)


@router.delete(
    "/{notification_id}",
    status_code=204,
    summary="Delete a notification",
)
async def delete_notification(
    notification_id: str,
    user_id: str = Depends(get_current_user),
    repo: NotificationRepository = Depends(get_notification_repo),
):
    """Delete a notification (scoped to the current user)."""
    repo.delete(notification_id, user_id=user_id)
    return None