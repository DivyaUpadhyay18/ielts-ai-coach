"""
Learning Session Mode API endpoints.

Provides interactive learning session functionality:
- Start a session with mission details + recommended resources
- Track session progress (progress bar)
- Add notes during session
- Bookmark resources during session
- Complete session (marks mission complete, earns XP, updates progress/streaks)

Endpoints:
  - POST /api/v1/learning-sessions/start     - Start a learning session
  - POST /api/v1/learning-sessions/{mission_id}/progress - Update progress
  - POST /api/v1/learning-sessions/{mission_id}/notes     - Add a note
  - POST /api/v1/learning-sessions/{mission_id}/bookmarks  - Bookmark a resource
  - POST /api/v1/learning-sessions/{mission_id}/complete  - Complete session
  - GET  /api/v1/learning-sessions/today     - Get today's session overview
  - GET  /api/v1/learning-sessions/history   - Get session history
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.api.deps import get_current_user
from app.models.learning_session import (
    SessionStartResponse,
    SessionStateUpdate,
    SessionNoteCreate,
    SessionBookmarkCreate,
    SessionCompleteRequest,
    SessionCompleteResponse,
    SessionHistoryResponse,
    MissionWithSessionResponse,
)
from app.services.learning_session_service import LearningSessionService

router = APIRouter()


def get_learning_session_service() -> LearningSessionService:
    from app.services.learning_session_service import learning_session_service
    return learning_session_service


@router.post(
    "/start",
    response_model=SessionStartResponse,
    summary="Start a learning session",
)
async def start_session(
    mission_id: Optional[str] = Query(None, description="Specific mission ID to start (optional)"),
    skill: Optional[str] = Query(None, description="Skill to start (optional, filters missions)"),
    user_id: str = Depends(get_current_user),
    service: LearningSessionService = Depends(get_learning_session_service),
):
    """
    Start a learning session for today's mission.

    Fetches:
    - Mission details (title, description, estimated time, XP reward)
    - Recommended resource (using the recommendation engine)
    - Related resources
    - Previous mistakes for your weakest skill
    - Existing notes and bookmarks
    - Current session progress

    If mission_id is not provided, the system picks the mission matching
    your weakest skill from today's missions.
    """
    return service.start_session(user_id=user_id, mission_id=mission_id, skill=skill)


@router.post(
    "/{mission_id}/progress",
    response_model=dict,
    summary="Update session progress",
)
async def update_session_progress(
    mission_id: str,
    data: SessionStateUpdate,
    user_id: str = Depends(get_current_user),
    service: LearningSessionService = Depends(get_learning_session_service),
):
    """Update the progress bar and status of the current learning session."""
    return service.update_session_progress(
        user_id=user_id,
        mission_id=mission_id,
        progress_percent=data.progress_percent,
        status=data.status,
    )


@router.post(
    "/{mission_id}/notes",
    response_model=dict,
    status_code=201,
    summary="Add a note to the session",
)
async def add_session_note(
    mission_id: str,
    data: SessionNoteCreate,
    user_id: str = Depends(get_current_user),
    service: LearningSessionService = Depends(get_learning_session_service),
):
    """Add a note during the learning session."""
    return service.add_note(
        user_id=user_id,
        content=data.content,
        mission_id=mission_id,
        resource_id=data.resource_id,
    )


@router.post(
    "/{mission_id}/bookmarks",
    response_model=dict,
    status_code=201,
    summary="Bookmark a resource during session",
)
async def add_session_bookmark(
    mission_id: str,
    data: SessionBookmarkCreate,
    user_id: str = Depends(get_current_user),
    service: LearningSessionService = Depends(get_learning_session_service),
):
    """Bookmark a resource during the learning session."""
    return service.add_bookmark(
        user_id=user_id,
        resource_id=data.resource_id,
        mission_id=mission_id,
    )


@router.post(
    "/{mission_id}/complete",
    response_model=SessionCompleteResponse,
    summary="Complete a learning session",
)
async def complete_session(
    mission_id: str,
    data: Optional[SessionCompleteRequest] = None,
    user_id: str = Depends(get_current_user),
    service: LearningSessionService = Depends(get_learning_session_service),
):
    """
    Mark a mission as complete and finalize the learning session.

    This triggers:
    1. Mission marked as completed
    2. XP logged to study sessions (progress tracking)
    3. Streaks updated (daily/weekly/monthly, perfect day, milestones)
    4. Session state marked as completed
    5. Achievements checked

    Returns XP earned, new level, streak info, and any unlocked achievements.
    """
    actual_duration = None
    notes = None
    if data:
        actual_duration = data.actual_duration_minutes
        notes = data.notes

    return service.complete_session(
        user_id=user_id,
        mission_id=mission_id,
        actual_duration_minutes=actual_duration,
        notes=notes,
    )


@router.get(
    "/today",
    response_model=dict,
    summary="Get today's session overview",
)
async def get_today_session_overview(
    user_id: str = Depends(get_current_user),
    service: LearningSessionService = Depends(get_learning_session_service),
):
    """Get an overview of today's missions and their session state."""
    return service.get_todays_session_overview(user_id=user_id)


@router.get(
    "/history",
    response_model=SessionHistoryResponse,
    summary="Get session history",
)
async def get_session_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: LearningSessionService = Depends(get_learning_session_service),
):
    """Get your learning session history."""
    return service.get_session_history(user_id=user_id, limit=limit, offset=offset)