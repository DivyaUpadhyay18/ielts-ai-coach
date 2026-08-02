"""
Pydantic schemas for the Achievement domain entity.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator

ACHIEVEMENT_CATEGORIES = ("streak", "tasks", "assessments", "band", "general")


class AchievementCreate(BaseModel):
    """Schema for creating an achievement catalog entry."""
    code: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: str = Field("general", pattern="^(streak|tasks|assessments|band|general)$")
    icon: Optional[str] = None
    points: int = Field(10, ge=0)
    criteria: Optional[Dict[str, Any]] = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Code cannot be empty")
        return stripped.lower().replace(" ", "_")

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped


class AchievementUpdate(BaseModel):
    """Schema for partial update of an achievement."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, pattern="^(streak|tasks|assessments|band|general)$")
    icon: Optional[str] = None
    points: Optional[int] = Field(None, ge=0)
    criteria: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AchievementResponse(BaseModel):
    """Schema for an achievement catalog entry."""
    id: str
    code: str
    title: str
    description: Optional[str] = None
    category: str = "general"
    icon: Optional[str] = None
    points: int = 10
    criteria: Optional[Dict[str, Any]] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class UserAchievementResponse(BaseModel):
    """Schema for an achievement earned by a user."""
    id: str
    user_id: str
    achievement_id: str
    achievement: Optional[AchievementResponse] = None
    earned_at: Optional[datetime] = None
    meta: Optional[Dict[str, Any]] = None


class AwardAchievementRequest(BaseModel):
    """Schema for awarding an achievement to the current user."""
    achievement_id: str
    meta: Optional[Dict[str, Any]] = None

