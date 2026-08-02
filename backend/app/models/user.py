"""
Pydantic schemas for the User domain entity.
"""
from datetime import datetime, date
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator

import re

# ---------------------------------------------------------------------------
# Shared constants / validators
# ---------------------------------------------------------------------------
ALLOWED_BANDS = {0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9}


def validate_band(v: float, field_name: str) -> float:
    """Ensure a band score is a valid 0.5-step value between 0 and 9."""
    if v not in ALLOWED_BANDS:
        raise ValueError(f"{field_name} must be a valid IELTS band (0.0–9.0 in 0.5 steps)")
    return v


def validate_https_url(v: Optional[str]) -> Optional[str]:
    """Ensure a URL is HTTPS if provided."""
    if v is None or v == "":
        return v
    if not re.match(r"^https://", v):
        raise ValueError("URL must be an HTTPS URL")
    return v


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------
class UserProfileUpdate(BaseModel):
    """Partial update for the user's profile fields."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=120)
    avatar_url: Optional[str] = None
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    timezone: Optional[str] = Field(None, max_length=64)
    preferences: Optional[Dict[str, Any]] = None

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Full name cannot be empty")
        return stripped

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar(cls, v: Optional[str]) -> Optional[str]:
        return validate_https_url(v)

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.upper()


class UserGoalsUpdate(BaseModel):
    """Update the user's IELTS goals."""
    target_band: Optional[float] = Field(None, ge=0, le=9)
    exam_date: Optional[date] = None
    module: Optional[str] = Field(None, pattern="^(academic|general)$")
    daily_minutes_budget: Optional[int] = Field(None, ge=15, le=480)
    current_band: Optional[float] = Field(None, ge=0, le=9)

    @field_validator("target_band", "current_band")
    @classmethod
    def validate_band_step(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        return validate_band(v, "band")

    @field_validator("exam_date")
    @classmethod
    def validate_exam_date(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return v
        if v <= date.today():
            raise ValueError("Exam date must be in the future")
        return v


class UserResponse(BaseModel):
    """Full user profile response."""
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = "UTC"
    module: Optional[str] = "academic"
    plan: Optional[str] = "free"
    daily_minutes_budget: Optional[int] = 60
    target_band: Optional[float] = None
    current_band: Optional[float] = None
    exam_date: Optional[date] = None
    is_onboarding_complete: Optional[bool] = False
    onboarded_at: Optional[datetime] = None
    preferences: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

