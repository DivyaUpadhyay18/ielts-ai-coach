"""
Pydantic schemas for the Learning Session domain.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SessionStartRequest(BaseModel):
    """Schema for starting a learning session."""
    mission_id: Optional[str] = None
    session_type: str = Field("learning_session", description="Type of session")
    skill_focus: Optional[str] = None


class SessionStartResponse(BaseModel):
    """Schema for session start response."""
    session_id: str
    mission_id: Optional[str]
    skill_focus: Optional[str]
    started_at: str
    estimated_duration: int
    resources: List[Dict[str, Any]]


class SessionNoteCreate(BaseModel):
    """Schema for creating a session note."""
    content: str
    resource_id: Optional[str] = None
    is_highlighted: bool = False
    color: str = "yellow"


class SessionNoteResponse(BaseModel):
    """Schema for session note response."""
    id: str
    user_id: str
    mission_id: Optional[str]
    resource_id: Optional[str]
    content: str
    is_highlighted: bool
    color: str
    created_at: str
    updated_at: str


class SessionBookmarkCreate(BaseModel):
    """Schema for creating a session bookmark."""
    resource_id: str
    note: Optional[str] = None


class SessionBookmarkResponse(BaseModel):
    """Schema for session bookmark response."""
    id: str
    user_id: str
    mission_id: Optional[str]
    resource_id: str
    note: Optional[str]
    created_at: str


class SessionStateResponse(BaseModel):
    """Schema for session state response."""
    id: str
    user_id: str
    mission_id: Optional[str]
    status: str
    progress_percent: float
    started_at: str
    completed_at: Optional[str]
    created_at: str
    updated_at: str


class SessionStateUpdate(BaseModel):
    """Schema for updating session progress."""
    progress_percent: float
    status: str


class SessionCompleteRequest(BaseModel):
    """Schema for completing a learning session."""
    actual_duration_minutes: Optional[int] = None
    notes: Optional[str] = None


class SessionCompleteResponse(BaseModel):
    """Schema for session completion response."""
    session_id: str
    mission_completed: bool
    xp_earned: int
    new_level: Optional[int]
    streak_updated: Optional[Dict[str, Any]]
    achievements_unlocked: Optional[List[Dict[str, Any]]]


class SessionHistoryResponse(BaseModel):
    """Schema for session history list."""
    sessions: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


class MissionWithSessionResponse(BaseModel):
    """Schema for mission with session state."""
    mission_id: str
    title: str
    session_state: Optional[SessionStateResponse]
