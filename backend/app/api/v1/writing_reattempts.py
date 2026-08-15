"""
Writing Reattempt Mode API endpoints.

Provides endpoints for the reattempt workflow:
  - POST /api/v1/writing-reattempts/{submission_id}/start
  - POST /api/v1/writing-reattempts/{submission_id}/evaluate
  - GET  /api/v1/writing-reattempts/{submission_id}/compare
  - GET  /api/v1/writing-reattempts
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_current_user,
    get_writing_attempt_service,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.services.writing_attempt_service import WritingAttemptService

router = APIRouter()


@router.post(
    "/{submission_id}/start",
    summary="Start a reattempt for a previously-evaluated submission",
    response_model=dict[str, Any],
)
async def start_reattempt(
    submission_id: str,
    user_id: str = Depends(get_current_user),
    attempt_service: WritingAttemptService = Depends(get_writing_attempt_service),
):
    """
    Start a reattempt for a previously-evaluated writing submission.

    Creates a new draft that reuses the original prompt, with the same task
    type and word/time limits. The new submission is tracked as attempt N
    in the writing_attempts table for later comparison.
    """
    try:
        result = attempt_service.start_reattempt(user_id, submission_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original submission not found",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return result


@router.post(
    "/{submission_id}/evaluate",
    summary="Evaluate a reattempt submission",
    response_model=dict[str, Any],
)
async def evaluate_reattempt(
    submission_id: str,
    user_id: str = Depends(get_current_user),
    attempt_service: WritingAttemptService = Depends(get_writing_attempt_service),
):
    """
    Evaluate a reattempt submission and compute the comparison with the
    original attempt.

    Returns:
      - The evaluation result for this attempt
      - A comparison of attempt 1 vs this attempt (band, criteria, time, words)
      - Bonus XP if improvement is detected
    """
    try:
        result = await attempt_service.evaluate_reattempt(user_id, submission_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission or attempt record not found",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return result


@router.get(
    "/{submission_id}/compare",
    summary="Compare reattempt with original",
    response_model=dict[str, Any],
)
async def compare_attempts(
    submission_id: str,
    user_id: str = Depends(get_current_user),
    attempt_service: WritingAttemptService = Depends(get_writing_attempt_service),
):
    """
    Fetch the comparison between the original attempt and this attempt.

    Shows band delta, per-criterion deltas, word count, and writing time.
    """
    try:
        result = attempt_service.get_attempt_comparison(user_id, submission_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt record not found",
        )
    if not result.get("compared"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("reason", "Cannot compare attempts"),
        )
    return result


@router.get(
    "",
    summary="List all writing attempt groups for the current user",
    response_model=dict[str, Any],
)
async def list_attempts(
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    attempt_service: WritingAttemptService = Depends(get_writing_attempt_service),
):
    """
    List the user's writing attempt groups (each group contains all
    attempts for a single original submission).
    """
    return attempt_service.list_user_attempts(user_id, limit=limit)
