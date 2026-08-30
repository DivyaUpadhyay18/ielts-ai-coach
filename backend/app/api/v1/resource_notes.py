"""
API endpoints for Resource Notes, Highlights, and Revision Reminders.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.models.resource_note import (
    ResourceNoteCreate,
    ResourceNoteUpdate,
    ResourceNoteResponse,
    ResourceNoteListResponse,
    ResourceHighlightCreate,
    ResourceHighlightResponse,
    ResourceHighlightListResponse,
    RevisionReminderCreate,
    RevisionReminderUpdate,
    RevisionReminderResponse,
    RevisionReminderListResponse,
)
from app.repositories.resource_note_repo import ResourceNoteRepo

router = APIRouter()


# ─── Notes ───────────────────────────────────────────────────────────────────

@router.post("/notes", response_model=ResourceNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    note: ResourceNoteCreate,
    user_id: str = Depends(get_current_user),
):
    """Create a new note on a resource."""
    result = ResourceNoteRepo.create_note(
        user_id=user_id,
        resource_id=note.resource_id,
        content=note.content,
        color=note.color,
        is_highlighted=note.is_highlighted,
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create note")
    return result


@router.get("/notes", response_model=ResourceNoteListResponse)
async def list_notes(
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    search: Optional[str] = Query(None, description="Search notes by content"),
    user_id: str = Depends(get_current_user),
):
    """List notes for the current user."""
    notes = ResourceNoteRepo.list_notes(user_id, resource_id, search)
    return ResourceNoteListResponse(notes=notes, total=len(notes))


@router.get("/notes/{note_id}", response_model=ResourceNoteResponse)
async def get_note(
    note_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get a single note by ID."""
    note = ResourceNoteRepo.get_note(user_id, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.patch("/notes/{note_id}", response_model=ResourceNoteResponse)
async def update_note(
    note_id: str,
    note: ResourceNoteUpdate,
    user_id: str = Depends(get_current_user),
):
    """Update a note."""
    data = note.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = ResourceNoteRepo.update_note(user_id, note_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Note not found")
    return result


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete a note."""
    deleted = ResourceNoteRepo.delete_note(user_id, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")


# ─── Highlights ──────────────────────────────────────────────────────────────

@router.post("/highlights", response_model=ResourceHighlightResponse, status_code=status.HTTP_201_CREATED)
async def create_highlight(
    highlight: ResourceHighlightCreate,
    user_id: str = Depends(get_current_user),
):
    """Create a new highlight on a resource."""
    result = ResourceNoteRepo.create_highlight(
        user_id=user_id,
        resource_id=highlight.resource_id,
        selected_text=highlight.selected_text,
        color=highlight.color,
        note=highlight.note,
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create highlight")
    return result


@router.get("/highlights", response_model=ResourceHighlightListResponse)
async def list_highlights(
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    user_id: str = Depends(get_current_user),
):
    """List highlights for the current user."""
    highlights = ResourceNoteRepo.list_highlights(user_id, resource_id)
    return ResourceHighlightListResponse(highlights=highlights, total=len(highlights))


@router.delete("/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(
    highlight_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete a highlight."""
    deleted = ResourceNoteRepo.delete_highlight(user_id, highlight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Highlight not found")


# ─── Revision Reminders ──────────────────────────────────────────────────────

@router.post("/reminders", response_model=RevisionReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    reminder: RevisionReminderCreate,
    user_id: str = Depends(get_current_user),
):
    """Create a new revision reminder."""
    result = ResourceNoteRepo.create_reminder(
        user_id=user_id,
        resource_id=reminder.resource_id,
        reminder_date=reminder.reminder_date,
        title=reminder.title,
        note_id=reminder.note_id,
        reminder_time=str(reminder.reminder_time) if reminder.reminder_time else None,
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create reminder")
    return result


@router.get("/reminders", response_model=RevisionReminderListResponse)
async def list_reminders(
    upcoming_only: bool = Query(False, description="Only show upcoming reminders"),
    user_id: str = Depends(get_current_user),
):
    """List revision reminders for the current user."""
    reminders = ResourceNoteRepo.list_reminders(user_id, upcoming_only)
    return RevisionReminderListResponse(reminders=reminders, total=len(reminders))


@router.patch("/reminders/{reminder_id}", response_model=RevisionReminderResponse)
async def update_reminder(
    reminder_id: str,
    reminder: RevisionReminderUpdate,
    user_id: str = Depends(get_current_user),
):
    """Update a revision reminder."""
    data = reminder.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = ResourceNoteRepo.update_reminder(user_id, reminder_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return result


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(
    reminder_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete a revision reminder."""
    deleted = ResourceNoteRepo.delete_reminder(user_id, reminder_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reminder not found")


# ─── Stats ───────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_note_stats(
    user_id: str = Depends(get_current_user),
):
    """Get note, highlight, and reminder counts for the current user."""
    return {
        "notes_count": ResourceNoteRepo.get_note_count(user_id),
        "highlights_count": ResourceNoteRepo.get_highlight_count(user_id),
        "reminders_count": ResourceNoteRepo.get_reminder_count(user_id),
    }