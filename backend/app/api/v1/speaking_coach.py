"""
Speaking Interactive Coach API endpoints.

After evaluation, users can ask the AI Speaking Coach questions like:
  "Why did I get 6.5?"
  "How can I improve fluency?"
  "Was this answer too short?"
  "How could I answer this Part 2 question?"
  "What vocabulary should I use?"
  "Why was my grammar score low?"

Endpoints:
  - POST /api/v1/speaking-coach/sessions         → start a coaching conversation
  - POST /api/v1/speaking-coach/sessions/{id}/chat → ask a question
  - GET  /api/v1/speaking-coach/sessions/{id}     → get conversation + context
  - GET  /api/v1/speaking-coach/sessions          → list conversations

The coach uses the actual question, transcript, evaluation, previous attempts,
target band, and current weaknesses. All conversation history is stored.
Integrated with the AI Mentor for cross-context awareness.

All operations are owner-scoped (user_id from JWT).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Dict, List, Optional

from app.api.deps import get_current_user, get_speaking_coach_engine
from app.core.exceptions import NotFoundError, ValidationError
from app.services.speaking_practice_coach_engine import SpeakingCoachEngine


router = APIRouter()


@router.post(
    "/sessions",
    summary="Start a speaking coaching conversation",
)
async def start_speaking_coach_session(
    context_type: str = "practice_session",
    context_id: str = "",
    practice_mode: Optional[str] = None,
    part: Optional[str] = None,
    target_band: Optional[float] = None,
    transcript: str = "",
    question: str = "",
    evaluation: Optional[Dict[str, Any]] = None,
    error_analysis: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user),
    engine: SpeakingCoachEngine = Depends(get_speaking_coach_engine),
):
    """
    Start a coaching conversation for a practice session or test response.

    The context_type should match the table that holds the evaluated response:
    ``practice_session``, ``test_response``, or ``reattempt``.
    """
    try:
        return await engine.start_conversation(
            user_id, context_type, context_id, practice_mode, part,
            target_band, transcript, question, evaluation, error_analysis,
        )
    except (NotFoundError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.post(
    "/sessions/{session_id}/chat",
    summary="Ask the AI Speaking Coach a question",
)
async def speaking_coach_chat(
    session_id: str,
    question: str,
    user_id: str = Depends(get_current_user),
    engine: SpeakingCoachEngine = Depends(get_speaking_coach_engine),
):
    """
    Ask the AI Speaking Coach a question about your speaking performance.

    The coach uses your actual transcript, evaluation, previous attempts,
    target band, and current weaknesses to give a personalized, encouraging
    answer — never generic advice.
    """
    if not question or not question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty",
        )
    try:
        return await engine.chat(user_id, session_id, question)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coaching conversation not found",
        )


@router.get(
    "/sessions/{session_id}",
    summary="Get a speaking coach conversation with full context",
)
async def get_speaking_coach_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    engine: SpeakingCoachEngine = Depends(get_speaking_coach_engine),
):
    """Fetch a coaching conversation with full context (owner-scoped)."""
    try:
        return engine.get_conversation(user_id, session_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coaching conversation not found",
        )


@router.get(
    "/sessions",
    summary="List speaking coach conversations",
)
async def list_speaking_coach_sessions(
    limit: int = 50,
    context_id: Optional[str] = None,
    user_id: str = Depends(get_current_user),
    engine: SpeakingCoachEngine = Depends(get_speaking_coach_engine),
):
    """List the current user's coaching conversations (most recent first)."""
    return engine.list_conversations(user_id, limit, context_id)
