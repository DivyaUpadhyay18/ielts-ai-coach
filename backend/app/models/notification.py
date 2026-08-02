"""
Pydantic schemas for the Notification domain entity.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator

NOTIFICATION_TYPES = ("ai_feedback", "reminder", "system", "gamification", "streak")


class NotificationCreate(BaseModel):
    """Schema for creating a notification."""
    type: str = Field(
        ...,
        pattern="^(ai_feedback|reminder|system|gamification|streak)$",
    )
    title: str = Field(..., min_length=1, max_length=300)
    body: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped


class NotificationUpdate(BaseModel):
    """Schema for partial update of a notification."""
    is_read: Optional[bool] = None
    body: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class NotificationResponse(BaseModel):
    """Schema for a notification response."""
    id: str
    user_id: str
    type: str
    title: str
    body: Optional[str] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences (stored on user.preferences)."""
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = Field(
        None, pattern="^([01]\\d|2[0-3]):[0-5]\\d$"
    )
    quiet_hours_end: Optional[str] = Field(
        None, pattern="^([01]\\d|2[0-3]):[0-5]\\d$"
    )
    subscribed_types: Optional[list] = None


class NotificationMarkReadResponse(BaseModel):
    """Schema for a mark-as-read response."""
    id: str
    is_read: bool = True
    read_at: Optional[datetime] = None

