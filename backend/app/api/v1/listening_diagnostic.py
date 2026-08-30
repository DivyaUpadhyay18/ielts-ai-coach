"""
Listening Diagnostic Module endpoints.

Provides the listening-specific diagnostic flow:
  - GET  /listening/bank            → tracks + questions grouped by track
  - POST /listening/answers         → grade & save a single listening answer
  - POST /listening/attempts/{id}/complete → compute + store listening results
  - GET  /listening/attempts/{id}/report  → fetch the stored listening report
  - GET  /listening/results         → list a user's stored listening results

Everything is deterministic (NO AI) and owner-scoped.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_listening_diagnostic_service
from app.core.exceptions import NotFoundError, ValidationError
from app.models.listening_diagnostic import ListeningAnswerSubmit
from app.services.listening_diagnostic_service import ListeningDiagnosticService

router = APIRouter()


@router.get(
    "/bank",
    response_model=dict,
    summary="Get all listening tracks and questions",
)
async def get_bank(
    user_id: str = Depends(get_current_user),
    service: ListeningDiagnosticService = Depends(get_listening_diagnostic_service),
):
    """Return all active listening tracks with their questions (answer stripped)."""
    return service.get_bank()


@router.post(
    "/answers",
    response_model=dict,
    summary="Submit and grade a listening answer",
)
async def submit_answer(
    data: ListeningAnswerSubmit,
    user_id: str = Depends(get_current_user),
    service: ListeningDiagnosticService = Depends(get_listening_diagnostic_service),
):
    """Grade and persist a single listening answer for an attempt."""
    try:
        return service.submit_answer(
            user_id,
            data.attempt_id,
            data.question_id,
            data.answer,
            data.time_taken_seconds,
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/attempts/{attempt_id}/complete",
    response_model=dict,
    summary="Complete a listening diagnostic and store results",
)
async def complete_listening(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
    service: ListeningDiagnosticService = Depends(get_listening_diagnostic_service),
):
    """Compute, store, and return the listening diagnostic report."""
    try:
        return service.complete_listening(user_id, attempt_id)
    except (NotFoundError, ValidationError):
        raise


@router.get(
    "/attempts/{attempt_id}/report",
    response_model=dict,
    summary="Get the stored listening diagnostic report",
)
async def get_report(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
    service: ListeningDiagnosticService = Depends(get_listening_diagnostic_service),
):
    """Fetch the stored listening diagnostic report for an attempt."""
    try:
        return service.build_report(user_id, attempt_id)
    except NotFoundError:
        raise


@router.get(
    "/results",
    response_model=dict,
    summary="List a user's stored listening diagnostic results",
)
async def list_results(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    service: ListeningDiagnosticService = Depends(get_listening_diagnostic_service),
):
    """List the current user's stored listening diagnostic results."""
    return service.list_results(user_id, limit)
