"""
Band Estimation Engine API endpoints.

Provides a deterministic (NO AI) band estimation system:
- POST /api/v1/band-estimation - Estimate overall band from skill scores
- GET /api/v1/band-estimation/latest - Get latest estimation result
- GET /api/v1/band-estimation/history - Get estimation history

The engine maps user's skill-wise band scores (reading, listening, writing,
speaking, vocabulary, grammar) to:
  - Estimated Overall Band (mean of 4 official skills, 0.5 steps)
  - Skill-wise Band
  - Confidence Score (0-100)
  - Weakest Skills
  - Strongest Skills
  - Explanations (why each score was assigned)
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.api.deps import get_current_user, get_band_estimation_service
from app.models.band_estimation import (
    BandEstimationInput,
    BandEstimationResponse,
    BandEstimationHistoryResponse,
)
from app.services.band_estimation_service import BandEstimationService

router = APIRouter()


def get_service() -> BandEstimationService:
    return get_band_estimation_service()


@router.post(
    "",
    response_model=BandEstimationResponse,
    summary="Estimate IELTS band from skill scores",
)
async def estimate_band(
    data: BandEstimationInput,
    user_id: str = Depends(get_current_user),
    service: BandEstimationService = Depends(get_service),
):
    """
    Estimate your overall IELTS band score from skill-wise scores.

    Provide scores (0-9) for each skill:
    - **reading** - Reading comprehension score
    - **listening** - Listening comprehension score
    - **writing** - Writing task performance score
    - **speaking** - Speaking fluency score
    - **vocabulary** - Vocabulary breadth score
    - **grammar** - Grammar accuracy score

    The engine computes:
    - **Overall Band**: Mean of reading, listening, writing, speaking (rounded to 0.5)
    - **Confidence Score**: 0-100 based on score dispersion + input completeness
    - **Weakest/Strongest Skills**: Sorted ascending/descending
    - **Explanations**: Why each skill score was assigned

    Results are stored in the `band_estimations` table (one per user per day).
    """
    result = service.estimate(user_id=user_id, data=data)
    return result


@router.get(
    "/latest",
    response_model=dict,
    summary="Get latest band estimation",
)
async def get_latest_estimation(
    user_id: str = Depends(get_current_user),
    service: BandEstimationService = Depends(get_service),
):
    """Get the most recent band estimation for the current user."""
    result = service.get_latest(user_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No band estimation found. Run an estimation first.",
        )
    return result


@router.get(
    "/history",
    response_model=BandEstimationHistoryResponse,
    summary="Get band estimation history",
)
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: BandEstimationService = Depends(get_service),
):
    """Get the history of band estimations for the current user."""
    return service.get_history(user_id, limit=limit, offset=offset)