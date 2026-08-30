"""
Diagnostic Test Framework endpoints.

Provides the full diagnostic lifecycle:
  - POST /attempts            → start (or resume) a diagnostic attempt
  - GET  /attempts/{id}       → resume a specific attempt
  - GET  /questions/{section} → randomized question bank for a section
  - POST /attempts/{id}/answers    → grade & save a single answer
  - POST /attempts/{id}/sections/{section}/complete → mark a section done
  - POST /attempts/{id}/complete   → finalize and compute the report
  - GET  /attempts/{id}/report     → fetch the diagnostic report

Everything is deterministic (NO AI) and owner-scoped.
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_diagnostic_service
from app.core.exceptions import NotFoundError, ValidationError
from app.models.diagnostic import (
    AnswerSubmit,
    DiagnosticAttemptCreate,
    SectionComplete,
)
from app.services.diagnostic_service import DiagnosticService

router = APIRouter()


@router.post(
    "/attempts",
    response_model=dict,
    status_code=201,
    summary="Start (or resume) a diagnostic attempt",
)
async def start_attempt(
    _: DiagnosticAttemptCreate,
    user_id: str = Depends(get_current_user),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    """
    Start a new diagnostic attempt. If the user already has an in-progress
    attempt, it is resumed instead (resume support).
    """
    return service.start_attempt(user_id)


@router.get(
    "/attempts/{attempt_id}",
    response_model=dict,
    summary="Resume a diagnostic attempt",
)
async def resume_attempt(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    """
    Resume a specific attempt, returning its current state plus the list of
    question ids already answered (so the client can restore progress).
    """
    try:
        return service.resume_attempt(attempt_id, user_id)
    except NotFoundError:
        raise


@router.get(
    "/questions/{section}",
    response_model=dict,
    summary="Get randomized questions for a section",
)
async def get_questions(
    section: str,
    user_id: str = Depends(get_current_user),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    """
    Return a randomized set of questions for the given section
    (reading, listening, writing, speaking, vocabulary, grammar).
    """
    try:
        return service.get_questions(section)
    except ValidationError:
        raise


@router.post(
    "/attempts/{attempt_id}/answers",
    response_model=dict,
    summary="Submit and grade an answer",
)
async def submit_answer(
    attempt_id: str,
    data: AnswerSubmit,
    user_id: str = Depends(get_current_user),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    """
    Grade and persist a single answer for a question within an attempt.
    Progress is saved immediately so the user can resume later.
    """
    try:
        return service.submit_answer(
            attempt_id,
            user_id,
            data.section,
            data.question_id,
            data.answer,
            data.time_taken_seconds,
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/attempts/{attempt_id}/sections/{section}/complete",
    response_model=dict,
    summary="Mark a section as completed",
)
async def complete_section(
    attempt_id: str,
    section: str,
    data: SectionComplete,
    user_id: str = Depends(get_current_user),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    """
    Mark a section as completed and advance to the next uncompleted section.
    """
    try:
        return service.complete_section(
            attempt_id, user_id, data.section, data.time_taken_seconds
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/attempts/{attempt_id}/complete",
    response_model=dict,
    summary="Complete the attempt and compute the report",
)
async def complete_attempt(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    """
    Finalize the attempt and compute the diagnostic report with the estimated
    IELTS level, per-skill bands, strengths, and weaknesses.
    """
    try:
        return service.complete_attempt(attempt_id, user_id)
    except (NotFoundError, ValidationError):
        raise


@router.get(
    "/attempts/{attempt_id}/report",
    response_model=dict,
    summary="Get the diagnostic report",
)
async def get_report(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    """
    Fetch the diagnostic report for an attempt (estimated IELTS level).
    """
    try:
        return service.get_report(attempt_id, user_id)
    except NotFoundError:
        raise
