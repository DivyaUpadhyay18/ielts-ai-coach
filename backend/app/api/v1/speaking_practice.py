"""
Speaking Practice Mode API endpoints.

Provides focused practice sessions for individual Speaking skills:

Modes:
  - quick_practice      → random question, any part
  - part_1_practice     → Part 1 questions (Introduction & Interview)
  - part_2_practice     → Part 2 cue cards (Individual Long Turn)
  - part_3_practice     → Part 3 discussion questions
  - vocabulary_practice → vocabulary-focused prompts
  - fluency_practice    → fluency-focused prompts
  - random_question     → random across all modes
  - weak_area_practice  → targets the user's weakest criterion

Endpoints:
  - POST /api/v1/speaking-practice/sessions          → start a new session
  - PATCH /api/v1/speaking-practice/sessions/{id}     → save a response
  - POST /api/v1/speaking-practice/sessions/{id}/evaluate → evaluate + feedback
  - GET  /api/v1/speaking-practice/sessions/{id}     → get a session
  - GET  /api/v1/speaking-practice/sessions          → list sessions

Integrated with:
  - Mission Engine (schedulable practice missions)
  - Resource Engine (recommendations)
  - Adaptive Scheduler (next exercise recommendation)
  - XP / progress tracking (award XP for completed sessions)

All operations are owner-scoped.  Previous sessions are never overwritten.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_speaking_practice_mode_engine
from app.core.exceptions import NotFoundError, ValidationError
from app.services.speaking_practice_mode_engine import SpeakingPracticeModeEngine


router = APIRouter()


@router.post(
    "/sessions",
    summary="Start a speaking practice session",
)
async def start_speaking_practice(
    practice_mode: str,
    target_band: float | None = None,
    user_id: str = Depends(get_current_user),
    engine: SpeakingPracticeModeEngine = Depends(get_speaking_practice_mode_engine),
):
    """
    Start a focused speaking practice session.

    Modes: quick_practice, part_1_practice, part_2_practice,
    part_3_practice, vocabulary_practice, fluency_practice,
    random_question, weak_area_practice.

    Selects a suitable question from the speaking_prompts bank based on
    the chosen mode and creates a practice session with appropriate
    timing.
    """
    try:
        return engine.start_session(user_id, practice_mode, target_band)
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.patch(
    "/sessions/{session_id}",
    summary="Save a practice response (transcript + duration)",
)
async def save_speaking_practice_response(
    session_id: str,
    transcript: str,
    duration_seconds: int = 0,
    audio_url: str = "",
    user_id: str = Depends(get_current_user),
    engine: SpeakingPracticeModeEngine = Depends(get_speaking_practice_mode_engine),
):
    """Save the user's recorded response to a practice session."""
    try:
        return engine.save_response(
            user_id, session_id, transcript, duration_seconds, audio_url
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.post(
    "/sessions/{session_id}/evaluate",
    summary="Evaluate a practice session and get feedback + next recommendation",
)
async def evaluate_speaking_practice(
    session_id: str,
    target_band: float | None = None,
    user_id: str = Depends(get_current_user),
    engine: SpeakingPracticeModeEngine = Depends(get_speaking_practice_mode_engine),
):
    """
    Evaluate a practice session's transcript and provide feedback + XP.

    Runs AI evaluation + error analysis, computes bands across all 4 criteria,
    counts errors and filler words, awards XP, and generates a next-exercise
    recommendation integrated with the Adaptive Scheduler and Resource Engine.
    """
    try:
        return await engine.evaluate_session(user_id, session_id, target_band)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.get(
    "/sessions/{session_id}",
    summary="Get a speaking practice session",
)
async def get_speaking_practice_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    engine: SpeakingPracticeModeEngine = Depends(get_speaking_practice_mode_engine),
):
    """Fetch a speaking practice session (owner-scoped)."""
    try:
        return engine.get_session(user_id, session_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Practice session not found",
        )


@router.get(
    "/sessions",
    summary="List speaking practice sessions",
)
async def list_speaking_practice_sessions(
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    engine: SpeakingPracticeModeEngine = Depends(get_speaking_practice_mode_engine),
):
    """List the current user's speaking practice sessions (most recent first)."""
    return engine.list_sessions(user_id, limit)
