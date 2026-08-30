"""
Reading Diagnostic Module endpoints.

Provides the reading-specific diagnostic flow:
  - GET  /reading/bank            → passages + questions grouped by passage
  - POST /reading/answers         → grade & save a single reading answer
  - POST /reading/attempts/{id}/complete → compute + store reading results
  - GET  /reading/attempts/{id}/report  → fetch the stored reading report
  - GET  /reading/results         → list a user's stored reading results

Everything is deterministic (NO AI) and owner-scoped.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_reading_diagnostic_service
from app.core.exceptions import NotFoundError, ValidationError
from app.models.reading_diagnostic import ReadingAnswerSubmit
from app.services.reading_diagnostic_service import ReadingDiagnosticService

router = APIRouter()


@router.get(
    "/bank",
    response_model=dict,
    summary="Get all reading passages and questions",
)
async def get_bank(
    user_id: str = Depends(get_current_user),
    service: ReadingDiagnosticService = Depends(get_reading_diagnostic_service),
):
    """Return all active reading passages with their questions (answer stripped)."""
    return service.get_bank()


@router.post(
    "/answers",
    response_model=dict,
    summary="Submit and grade a reading answer",
)
async def submit_answer(
    data: ReadingAnswerSubmit,
    user_id: str = Depends(get_current_user),
    service: ReadingDiagnosticService = Depends(get_reading_diagnostic_service),
):
    """Grade and persist a single reading answer for an attempt."""
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
    summary="Complete a reading diagnostic and store results",
)
async def complete_reading(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
    service: ReadingDiagnosticService = Depends(get_reading_diagnostic_service),
):
    """Compute, store, and return the reading diagnostic report."""
    try:
        return service.complete_reading(user_id, attempt_id)
    except (NotFoundError, ValidationError):
        raise


@router.get(
    "/attempts/{attempt_id}/report",
    response_model=dict,
    summary="Get the stored reading diagnostic report",
)
async def get_report(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
    service: ReadingDiagnosticService = Depends(get_reading_diagnostic_service),
):
    """Fetch the stored reading diagnostic report for an attempt."""
    try:
        return service.build_report(user_id, attempt_id)
    except NotFoundError:
        raise


@router.get(
    "/results",
    response_model=dict,
    summary="List a user's stored reading diagnostic results",
)
async def list_results(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    service: ReadingDiagnosticService = Depends(get_reading_diagnostic_service),
):
    """List the current user's stored reading diagnostic results."""
    return service.list_results(user_id, limit)
