"""
Speaking Reattempt Mode API endpoints.

Provides the reattempt workflow for Speaking:
  - POST /api/v1/speaking-reattempts/{response_id}/start
      → start a reattempt from a previously-evaluated response
  - POST /api/v1/speaking-reattempts/{response_id}/evaluate
      → evaluate a reattempt and compute the comparison + bonus XP
  - GET  /api/v1/speaking-reattempts/{response_id}/compare
      → fetch the comparison between attempt 1 and the latest attempt
  - GET  /api/v1/speaking-reattempts
      → list all attempt groups for the current user

The user's original responses are never overwritten.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_speaking_reattempt_service
from app.core.exceptions import NotFoundError, ValidationError
from app.services.speaking_reattempt_service import SpeakingReattemptService


router = APIRouter()


@router.post(
    "/{response_id}/start",
    summary="Start a reattempt for a previously-evaluated speaking response",
)
async def start_reattempt(
    response_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingReattemptService = Depends(get_speaking_reattempt_service),
):
    """
    Start a reattempt for a previously-evaluated Speaking response.

    The reattempt reuses the same part and topic from the original response,
    creating a new draft that the student can record into.  The original
    response is never modified.
    """
    try:
        result = service.start_reattempt(user_id, response_id)
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{response_id}/evaluate",
    summary="Evaluate a reattempt and compute comparison + bonus XP",
)
async def evaluate_reattempt(
    response_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingReattemptService = Depends(get_speaking_reattempt_service),
):
    """
    Evaluate a reattempt response and compute the comparison with the original.

    Runs AI evaluation + error analysis on the reattempt transcript, compares
    all four criteria + metrics (band, duration, fillers, errors), and awards
    bonus XP if meaningful improvement is detected (>=0.5 band overall or any
    criterion improving by >=0.5).
    """
    try:
        result = await service.evaluate_reattempt(user_id, response_id)
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{response_id}/compare",
    summary="Compare attempt 1 vs the latest attempt",
)
async def get_attempt_comparison(
    response_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingReattemptService = Depends(get_speaking_reattempt_service),
):
    """
    Fetch the comparison between the original attempt and the latest attempt.

    Shows: overall band delta, per-criterion deltas, duration change,
    filler word change, error count change, plus AI-generated natural-language
    descriptions of what improved, what stayed the same, what became worse,
    and what to focus on next.
    """
    try:
        result = service.get_attempt_comparison(user_id, response_id)
        return result
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No comparison found for this response",
        )


@router.get(
    "",
    summary="List all speaking attempt groups for the current user",
)
async def list_speaking_reattempts(
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    service: SpeakingReattemptService = Depends(get_speaking_reattempt_service),
):
    """List all attempt groups for the current user (most recent first)."""
    return service.list_user_attempts(user_id, limit)
