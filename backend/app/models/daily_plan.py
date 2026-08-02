"""
Pydantic schemas for the DailyPlan domain entity.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

DAILY_PLAN_STATUSES = ("scheduled", "in_progress", "completed", "missed", "rolled_forward")


class DailyPlanCreate(BaseModel):
    """Schema for creating a daily plan."""
    study_plan_id: str
    plan_date: date
    status: str = Field("scheduled", pattern="^(scheduled|in_progress|completed|missed|rolled_forward)$")
    is_rest_day: bool = False
    phase_index: Optional[int] = Field(None, ge=0)
    is_revision_day: bool = False
    is_mock_day: bool = False
    xp_reward: int = Field(0, ge=0)

    @field_validator("plan_date")
    @classmethod
    def validate_plan_date(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("plan_date must be in the future")
        return v


class DailyPlanUpdate(BaseModel):
    """Schema for partial update of a daily plan."""
    status: Optional[str] = Field(None, pattern="^(scheduled|in_progress|completed|missed|rolled_forward)$")
    is_rest_day: Optional[bool] = None
    phase_index: Optional[int] = Field(None, ge=0)
    is_revision_day: Optional[bool] = None
    is_mock_day: Optional[bool] = None
    xp_reward: Optional[int] = Field(None, ge=0)


class DailyPlanResponse(BaseModel):
    """Schema for a daily plan response."""
    id: str
    user_id: str
    study_plan_id: str
    plan_date: date
    total_tasks: int = 0
    completed_tasks: int = 0
    total_minutes: int = 0
    completed_minutes: int = 0
    status: str = "scheduled"
    is_rest_day: bool = False
    phase_index: Optional[int] = None
    is_revision_day: bool = False
    is_mock_day: bool = False
    xp_reward: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

