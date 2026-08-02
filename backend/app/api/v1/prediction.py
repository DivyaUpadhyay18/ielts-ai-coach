"""
API endpoint for the Prediction Engine.

GET  /prediction           — compute and return the current prediction
GET  /prediction/history   — return paginated prediction history
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_prediction_engine_service
from app.core.exceptions import NotFoundError, ValidationError
from app.services.prediction_engine import PredictionEngineService

router = APIRouter()


@router.get("", response_model=dict)
async def get_prediction(
    run_date: Optional[str] = Query(None, description="ISO date to compute prediction for (defaults to today)"),
    user_id: str = Depends(get_current_user),
    service: PredictionEngineService = Depends(get_prediction_engine_service),
):
    """
    Compute the user's exam-readiness prediction.

    Returns:
        - preparation_percentage: 0–100
        - estimated_band: 0.0–9.0 (0.5 steps)
        - study_consistency: 0–100
        - completion_rate: 0–100
        - risk_level: low | medium | high | critical
        - readiness_score: 0–100
        - metrics: raw input data
        - formulas: documented formula explanations
        - recommendations: actionable advice
    """
    parsed_date = None
    if run_date:
        try:
            parsed_date = date.fromisoformat(run_date[:10])
        except (ValueError, TypeError):
            raise ValidationError("run_date must be a valid ISO date (YYYY-MM-DD)")

    try:
        result = service.get_prediction(user_id, run_date=parsed_date)
        return result
    except NotFoundError:
        raise
    except ValidationError:
        raise


@router.get("/history", response_model=dict)
async def get_prediction_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: PredictionEngineService = Depends(get_prediction_engine_service),
):
    """
    Return paginated prediction history for the user.

    Each entry is a snapshot of the prediction at a given run_date.
    """
    return service.get_history(user_id, limit=limit, offset=offset)
