"""
Exam Countdown API endpoints.

Provides:
  GET  /countdown           — full countdown metrics
  POST /countdown/exam-date — update exam date (auto-regenerates plan)
"""
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, status
from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.models.countdown import (
    ExamCountdownResponse,
    ExamDateUpdateRequest,
    ExamDateUpdateResponse,
)
from app.services.exam_countdown import exam_countdown_service

router = APIRouter()


@router.get(
    "",
    response_model=ExamCountdownResponse,
    summary="Get exam countdown metrics",
    responses={
        200: {"description": "Countdown metrics returned"},
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"},
        422: {"description": "Exam date not set"},
    },
)
async def get_countdown(
    user_id: str = Depends(get_current_user),
):
    """
    Compute and return the user's exam countdown metrics.

    Calculates days remaining, weeks remaining, study hours (planned vs
    completed), completion percentage, and preparation intensity level.
    """
    try:
        result = exam_countdown_service.get_countdown(user_id)
        return result
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


@router.post(
    "/exam-date",
    response_model=ExamDateUpdateResponse,
    summary="Update exam date (auto-regenerates study plan)",
    responses={
        200: {"description": "Exam date updated and plan regenerated"},
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"},
        422: {"description": "Invalid exam date"},
    },
)
async def update_exam_date(
    payload: ExamDateUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Update the user's exam date.

    When auto_regenerate is true (default), the active study plan is archived
    and a new one is generated for the updated timeline. All changes are
    stored in the database audit trail.
    """
    try:
        result = exam_countdown_service.update_exam_date(
            user_id=user_id,
            new_exam_date=payload.exam_date,
            auto_regenerate=payload.auto_regenerate,
        )
        return result
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
