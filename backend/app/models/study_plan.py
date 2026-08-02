"""
Pydantic schemas for the StudyPlan domain entity.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.user import validate_band

STUDY_PLAN_STATUSES = ("active", "archived", "completed")


class StudyPlanCreate(BaseModel):
    """Schema for creating a study plan."""
    version: int = Field(1, ge=1)
    title: str = Field(..., min_length=1, max_length=200)
    target_band: float = Field(..., ge=0, le=9)
    start_band: float = Field(..., ge=0, le=9)
    status: str = Field("active", pattern="^(active|archived|completed)$")
    total_weeks: int = Field(..., ge=2, le=52)
    source_diagnostic_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    @field_validator("target_band", "start_band")
    @classmethod
    def validate_bands(cls, v: float) -> float:
        return validate_band(v, "band")

    @field_validator("start_band")
    @classmethod
    def start_band_not_above_target(cls, v: float, info) -> float:
        target = info.data.get("target_band")
        if target is not None and v > target:
            raise ValueError("start_band must be less than or equal to target_band")
        return v

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped


class StudyPlanUpdate(BaseModel):
    """Schema for partial update of a study plan."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[str] = Field(None, pattern="^(active|archived|completed)$")
    total_weeks: Optional[int] = Field(None, ge=2, le=52)
    meta: Optional[Dict[str, Any]] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped


class StudyPlanResponse(BaseModel):
    """Schema for a study plan response."""
    id: str
    user_id: str
    version: int = 1
    title: str
    target_band: float
    start_band: float
    status: str = "active"
    total_weeks: int
    source_diagnostic_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

