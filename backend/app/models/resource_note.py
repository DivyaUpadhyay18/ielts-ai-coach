"""
Pydantic schemas for Resource Notes, Highlights, and Revision Reminders.
"""
from datetime import datetime, date, time
from typing import List, Optional
from pydantic import BaseModel, Field


# ─── Notes ───────────────────────────────────────────────────────────────────

class ResourceNoteCreate(BaseModel):
    """Schema for creating a note on a resource."""
    resource_id: str
    content: str = Field(..., min_length=1, max_length=5000)
    color: str = Field("yellow", pattern="^(yellow|green|blue|purple|pink|red)$")
    is_highlighted: bool = False


class ResourceNoteUpdate(BaseModel):
    """Schema for updating a note."""
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    color: Optional[str] = Field(None, pattern="^(yellow|green|blue|purple|pink|red)$")
    is_highlighted: Optional[bool] = None


class ResourceNoteResponse(BaseModel):
    """Schema for a note response."""
    id: str
    user_id: str
    resource_id: str
    content: str
    color: str
    is_highlighted: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResourceNoteListResponse(BaseModel):
    """Schema for a list of notes."""
    notes: List[ResourceNoteResponse]
    total: int


# ─── Highlights ──────────────────────────────────────────────────────────────

class ResourceHighlightCreate(BaseModel):
    """Schema for creating a highlight on a resource."""
    resource_id: str
    selected_text: str = Field(..., min_length=1, max_length=2000)
    color: str = Field("yellow", pattern="^(yellow|green|blue|purple|pink|red)$")
    note: Optional[str] = Field(None, max_length=2000)


class ResourceHighlightResponse(BaseModel):
    """Schema for a highlight response."""
    id: str
    user_id: str
    resource_id: str
    selected_text: str
    color: str
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class ResourceHighlightListResponse(BaseModel):
    """Schema for a list of highlights."""
    highlights: List[ResourceHighlightResponse]
    total: int


# ─── Revision Reminders ─────────────────────────────────────────────────────

class RevisionReminderCreate(BaseModel):
    """Schema for creating a revision reminder."""
    resource_id: str
    note_id: Optional[str] = None
    reminder_date: date
    reminder_time: Optional[time] = None
    title: str = Field(..., min_length=1, max_length=200)


class RevisionReminderUpdate(BaseModel):
    """Schema for updating a revision reminder."""
    reminder_date: Optional[date] = None
    reminder_time: Optional[time] = None
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    is_completed: Optional[bool] = None


class RevisionReminderResponse(BaseModel):
    """Schema for a revision reminder response."""
    id: str
    user_id: str
    resource_id: str
    note_id: Optional[str] = None
    reminder_date: date
    reminder_time: Optional[time] = None
    title: str
    is_completed: bool
    created_at: Optional[datetime] = None


class RevisionReminderListResponse(BaseModel):
    """Schema for a list of revision reminders."""
    reminders: List[RevisionReminderResponse]
    total: int