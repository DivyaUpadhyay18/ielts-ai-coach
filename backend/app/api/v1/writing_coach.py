"""
Writing Coach API endpoints.

Provides context-aware Q&A on the student's writing:
  - POST /api/v1/writing-coach/{submission_id}/ask     → ask a question
  - POST /api/v1/writing-coach/{submission_id}/ask-quick → inline (no history)
  - GET  /api/v1/writing-coach/conversations/{id}       → fetch conversation
  - GET  /api/v1/writing-coach/conversations            → list conversations
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_current_user,
    get_writing_coach_service,
)
from app.core.exceptions import NotFoundError
from app.services.writing_coach_service import WritingCoachService

router = APIRouter()


@router.post(
    "/{submission_id}/ask",
    response_model=dict[str, Any],
    summary="Ask the Writing Coach a question about your essay",
)
async def ask_coach(
    submission_id: str,
    question: str,
    user_id: str = Depends(get_current_user),
    coach: WritingCoachService = Depends(get_writing_coach_service),
):
    """
    Ask the Writing Coach a question grounded in your actual essay + evaluation.

    Examples:
      - "Why is this sentence wrong?"
      - "How can I improve my introduction?"
      - "Why is my Task Response low?"
      - "Give me a better way to express this idea."
      - "How can I improve my grammar?"

    The answer references specific text from your essay and your actual band
    feedback. The Q&A is stored in conversation history.
    """
    if not question or not question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must not be empty",
        )
    try:
        return await coach.ask(user_id, submission_id, question.strip())
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{submission_id}/ask-quick",
    response_model=dict[str, Any],
    summary="Ask a quick question (no history stored)",
)
async def ask_coach_quick(
    submission_id: str,
    question: str,
    user_id: str = Depends(get_current_user),
    coach: WritingCoachService = Depends(get_writing_coach_service),
):
    """Answer a question without persisting the conversation."""
    if not question or not question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must not be empty",
        )
    try:
        return await coach.ask_standalone(user_id, submission_id, question.strip())
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/conversations/{conversation_id}",
    response_model=dict[str, Any],
    summary="Get a coaching conversation with full message history",
)
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
    coach: WritingCoachService = Depends(get_writing_coach_service),
):
    """Fetch a coaching conversation and all its messages."""
    try:
        return coach.get_conversation(user_id, conversation_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coaching conversation not found",
        )


@router.get(
    "/conversations",
    response_model=dict[str, Any],
    summary="List coaching conversations for the current user",
)
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user),
    coach: WritingCoachService = Depends(get_writing_coach_service),
):
    """List the user's coaching conversations (newest first)."""
    return coach.list_conversations(user_id, limit=limit, offset=offset)
