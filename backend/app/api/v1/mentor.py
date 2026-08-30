"""
AI Mentor API endpoints.

The AI Mentor is an experienced IELTS tutor that coaches the student inside
their EXISTING study roadmap — it never generates a study plan from scratch.

Endpoints:
- GET    /api/v1/mentor/context          → the full learner-context snapshot
- POST   /api/v1/mentor/coach            → run a coaching session (by mode)
- POST   /api/v1/mentor/ask              → ask the mentor a grounded question
- GET    /api/v1/mentor/conversations     → conversation history
- GET    /api/v1/mentor/conversations/{id} → one conversation with messages
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_mentor_service
from app.models.mentor import (
    AskRequest,
    CoachRequest,
    CoachResponse,
    MentorContextResponse,
    MentorConversationListResponse,
    MentorConversationResponse,
)
from app.services.ai_mentor_service import AIMentorService

router = APIRouter()


@router.get(
    "/context",
    response_model=MentorContextResponse,
    summary="Get the learner context the AI Mentor understands",
)
def get_mentor_context(
    user_id: str = Depends(get_current_user),
    service: AIMentorService = Depends(get_mentor_service),
):
    """
    Return everything the AI Mentor knows about the student: profile,
    diagnostic results, current progress, study history, missed tasks,
    weakest/strongest skills, target band, exam date, and the current
    roadmap snapshot. This is a read-only snapshot.
    """
    return service.get_context(user_id)


@router.post(
    "/coach",
    response_model=CoachResponse,
    summary="Run an AI Mentor coaching session",
)
def run_coaching(
    data: CoachRequest,
    user_id: str = Depends(get_current_user),
    service: AIMentorService = Depends(get_mentor_service),
):
    """
    Coach the student for the requested mode:
      - daily_coaching   → today's session plan within the roadmap
      - roadmap_analysis → deep analysis of the existing roadmap
      - risk_check       → readiness / risk audit grounded in roadmap data
      - ask_mentor       → respond to an open question (grounded)

    The mentor ALWAYS analyses the EXISTING roadmap and never generates a
    study plan from scratch. Every response carries structured insights,
    directives (referencing real roadmap tasks) and a guardrails block.
    """
    return service.coach(user_id, mode=data.mode, message=data.message)


@router.post(
    "/ask",
    response_model=CoachResponse,
    summary="Ask the AI Mentor a question",
)
def ask_mentor(
    data: AskRequest,
    user_id: str = Depends(get_current_user),
    service: AIMentorService = Depends(get_mentor_service),
):
    """
    Ask the AI Mentor anything about your preparation. The answer is always
    grounded in your existing roadmap and learner context. If the question
    implies building a fresh plan, the mentor guides you to your roadmap
    instead of inventing one.
    """
    return service.ask(user_id, data.question)


@router.get(
    "/conversations",
    response_model=MentorConversationListResponse,
    summary="List AI Mentor conversations",
)
def list_conversations(
    mode: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: AIMentorService = Depends(get_mentor_service),
):
    """Return the student's AI Mentor conversation history (paginated)."""
    return service.list_conversations(user_id, mode=mode, limit=limit, offset=offset)


@router.get(
    "/conversations/{conversation_id}",
    response_model=MentorConversationResponse,
    summary="Get one AI Mentor conversation with its messages",
)
def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
    service: AIMentorService = Depends(get_mentor_service),
):
    """Return a single conversation including every user/mentor message."""
    return service.get_conversation(conversation_id, user_id)