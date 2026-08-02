"""
Pydantic schemas for the DailyMission domain entity.
"""
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

MISSION_SKILLS = ("reading", "listening", "writing", "speaking", "vocabulary", "grammar")
MISSION_STATUSES = ("pending", "completed", "skipped")


class DailyMissionUpdate(BaseModel):
    """Schema for updating a daily mission's status or completion."""
    status: Optional[str] = Field(None, pattern="^(pending|completed|skipped)$")
    completion_percent: Optional[int] = Field(None, ge=0, le=100)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MISSION_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(MISSION_STATUSES)}")
        return v


class DailyMissionResponse(BaseModel):
    """Schema for a single daily mission response."""
    id: str
    user_id: str
    mission_date: date
    skill: str
    title: str
    estimated_minutes: int
    xp_reward: int
    completion_percent: int = 0
    status: str = "pending"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DailyMissionSummary(BaseModel):
    """Aggregated summary for a day's missions."""
    mission_date: date
    total_missions: int = 0
    completed_missions: int = 0
    skipped_missions: int = 0
    pending_missions: int = 0
    total_estimated_minutes: int = 0
    total_xp_reward: int = 0
    earned_xp: int = 0
    completion_percent: int = 0


class DailyMissionListResponse(BaseModel):
    """Response containing a day's missions and summary."""
    missions: List[DailyMissionResponse] = Field(default_factory=list)
    summary: DailyMissionSummary


class DailyMissionGenerateResponse(BaseModel):
    """Response for bulk generation."""
    generated: int = 0
    skipped: int = 0
    date_range: str = ""