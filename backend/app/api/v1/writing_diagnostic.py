"""
Writing Diagnostic Module endpoints.

Provides the writing-specific diagnostic flow:
  - GET  /writing/prompts?task_type=  → Task 1 / Task 2 prompts
  - POST /writing/essays              → start a writing essay (resume-aware)
  - POST /writing/essays/{id}/save    → auto-save the essay body
  - POST /writing/essays/{id}/complete→ finalize the essay
  - POST /writing/essays/{id}/score   → apply manual IELTS scoring
  - POST /writing/essays/{id}/ai      → future AI evaluation scaffold
  - GET  /writing/essays/{id}         → fetch the stored essay report
  - GET  /writing/essays              → list a user's stored essays

Everything is deterministic (NO AI) except the optional /ai scaffold, and all
operations are owner-scoped.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_writing_diagnostic_service
from app.core.exceptions import NotFoundError, ValidationError
from app.models.writing_diagnostic import (
    EssayComplete,
    EssaySave,
    EssayStart,
    ManualScoreSubmit,
)
from app.services.writing_diagnostic_service import WritingDiagnosticService

router = APIRouter()


@router.get(
    "/prompts",
    response_model=dict,
    summary="Get writing prompts (Task 1 / Task 2)",
)
async def get_prompts(
    task_type: Optional[str] = Query(None, regex="^(task_1|task_2)$"),
    user_id: str = Depends(get_current_user),
    service: WritingDiagnosticService = Depends(get_writing_diagnostic_service),
):
    """Return all active writing prompts, optionally filtered by task type."""
    try:
        return service.get_prompts(task_type)
    except ValidationError:
        raise


@router.post(
    "/essays",
    response_model=dict,
    status_code=201,
    summary="Start a writing essay",
)
async def start_essay(
    data: EssayStart,
    user_id: str = Depends(get_current_user),
    service: WritingDiagnosticService = Depends(get_writing_diagnostic_service),
):
    """Start a new writing essay for a prompt (resume-aware)."""
    try:
        return service.start_essay(user_id, data.prompt_id)
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/essays/{essay_id}/save",
    response_model=dict,
    summary="Auto-save the essay body",
)
async def auto_save(
    essay_id: str,
    data: EssaySave,
    user_id: str = Depends(get_current_user),
    service: WritingDiagnosticService = Depends(get_writing_diagnostic_service),
):
    """Auto-save the essay body and update live word count + time."""
    try:
        return service.auto_save(
            user_id, essay_id, data.essay_text, data.time_seconds_spent
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/essays/{essay_id}/complete",
    response_model=dict,
    summary="Complete a writing essay",
)
async def complete_essay(
    essay_id: str,
    data: EssayComplete,
    user_id: str = Depends(get_current_user),
    service: WritingDiagnosticService = Depends(get_writing_diagnostic_service),
):
    """Finalize the essay and mark it as completed."""
    try:
        return service.complete_essay(
            user_id, essay_id, data.time_seconds_spent
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/essays/{essay_id}/score",
    response_model=dict,
    summary="Apply manual IELTS writing scoring",
)
async def submit_score(
    essay_id: str,
    data: ManualScoreSubmit,
    user_id: str = Depends(get_current_user),
    service: WritingDiagnosticService = Depends(get_writing_diagnostic_service),
):
    """Apply manual IELTS scoring across the four criteria and store the result."""
    try:
        return service.submit_manual_score(
            user_id,
            essay_id,
            {
                "task_response": data.task_response,
                "coherence_cohesion": data.coherence_cohesion,
                "lexical_resource": data.lexical_resource,
                "grammatical_range": data.grammatical_range,
            },
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/essays/{essay_id}/ai",
    response_model=dict,
    summary="Run (or scaffold) AI evaluation of the essay",
)
async def ai_evaluate(
    essay_id: str,
    user_id: str = Depends(get_current_user),
    service: WritingDiagnosticService = Depends(get_writing_diagnostic_service),
):
    """Architecture scaffold for future AI evaluation (returns placeholder if no provider)."""
    try:
        return service.ai_evaluate(user_id, essay_id)
    except (NotFoundError, ValidationError):
        raise


@router.get(
    "/essays/{essay_id}",
    response_model=dict,
    summary="Get the stored essay report",
)
async def get_report(
    essay_id: str,
    user_id: str = Depends(get_current_user),
    service: WritingDiagnosticService = Depends(get_writing_diagnostic_service),
):
    """Fetch the stored writing essay and its report."""
    try:
        return service.get_report(user_id, essay_id)
    except NotFoundError:
        raise


@router.get(
    "/essays",
    response_model=dict,
    summary="List a user's stored writing essays",
)
async def list_essays(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    service: WritingDiagnosticService = Depends(get_writing_diagnostic_service),
):
    """List the current user's stored writing essays/results."""
    return service.list_essays(user_id, limit)
