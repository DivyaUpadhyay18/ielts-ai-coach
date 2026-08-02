"""
Pydantic schemas for the Learning Session Mode.

Provides schemas for:
- Session start (fetch mission + recommended resources)
- Session state tracking (progress, notes, bookmarks)
- Session completion (XP, dashboard updates)
- Session history
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.daily_mission import DailyMissionResponse
from app.models.recommendation import ResourceResponse


class SessionStartResponse(BaseModel):
    """Response for starting a learning session."""
    user_id: str
    session_id: str
    mission: Optional[DailyMissionResponse] = None
    recommended_resource: Optional[ResourceResponse] = None
    related_resources: List[ResourceResponse] = Field(default_factory=list)
    previous_mistakes: List[PreviousMistake] = Field(default_factory=list)
    notes: List[SessionNote] = Field(default_factory=list)
    bookmarks: List[SessionBookmark] = Field(default_factory=list)
    progress_percent: int = 0
    estimated_time: int = 0
    xp_reward: int = 0
    current_band: Optional[float] = None
    target_band: Optional[float] = None
    remaining_days: Optional[int] = None
    created_at: Optional[datetime] = None


class PreviousMistake(BaseModel):
    """A previous mistake from the user's study history."""
    task_id: str
    task_title: str
    skill: str
    mistake_type: str
    description: str
    created_at: Optional[datetime] = None


class SessionNoteBase(BaseModel):
    """Base schema for session notes."""
    content: str = Field(..., min_length=1, max_length=5000)
    resource_id: Optional[str] = None


class SessionNoteCreate(SessionNoteBase):
    """Schema for creating a session note."""
    mission_id: Optional[str] = None
    session_id: Optional[str] = None


class SessionNoteUpdate(BaseModel):
    """Schema for updating a session note."""
    content: Optional[str] = Field(None, min_length=1, max_length=5000)


class SessionNote(SessionNoteBase):
    """Schema for a session note response."""
    id: str
    user_id: str
    mission_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SessionBookmarkBase(BaseModel):
    """Base schema for session bookmarks."""
    resource_id: str
    mission_id: Optional[str] = None
    session_id: Optional[str] = None


class SessionBookmarkCreate(SessionBookmarkBase):
    """Schema for creating a session bookmark."""
    pass


class SessionBookmark(BaseModel):
    """Schema for a session bookmark response."""
    id: str
    user_id: str
    resource_id: str
    mission_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: Optional[datetime] = None


class SessionStateUpdate(BaseModel):
    """Schema for updating session state."""
    progress_percent: Optional[int] = Field(None, ge=0, le=100)
    status: Optional[str] = Field(None, pattern="^(active|completed|abandoned)$")

    @field_validator("progress_percent")
    @classmethod
    def validate_progress(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("progress_percent must be between 0 and 100")
        return v


class SessionCompleteRequest(BaseModel):
    """Schema for completing a learning session."""
    session_id: str
    notes: Optional[List[str]] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    actual_duration_minutes: Optional[int] = Field(None, ge=0, le=300)


class SessionCompleteResponse(BaseModel):
    """Response for completing a learning session."""
    session_id: str
    mission_completed: bool
    xp_earned: int
    total_xp: int
    level: int
    level_progress: float
    streak_current: int
    streak_longest: int
    achievements_unlocked: List[str] = Field(default_factory=list)
    message: str


class SessionHistoryResponse(BaseModel):
    """Response for session history."""
    sessions: List[SessionStateHistory] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class SessionStateHistory(BaseModel):
    """Schema for historical session state."""
    id: str
    user_id: str
    mission_id: str
    session_id: Optional[str] = None
    status: str
    progress_percent: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes_count: int
    bookmarked_resources: int
    xp_earned: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MissionWithSessionResponse(BaseModel):
    """Response combining mission data with session state."""
    user_id: str
    mission: Optional[DailyMissionResponse] = None
    session: Optional[SessionStateHistory] = None
    recommended_resource: Optional[ResourceResponse] = None
    related_resources: List[ResourceResponse] = Field(default_factory=list)
    previous_mistakes: List[PreviousMistake] = Field(default_factory=list)
    notes: List[SessionNote] = Field(default_factory=list)
    bookmarks: List[SessionBookmark] = Field(default_factory=list)
    current_band: Optional[float] = None
    target_band: Optional[float] = None
    remaining_days: Optional[int] = None