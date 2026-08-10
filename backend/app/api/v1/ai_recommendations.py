"""
AI Recommendations API endpoints.

GET  /api/v1/ai-recommendations    — get today's recommendations (generates if missing)
GET  /api/v1/ai-recommendations/history — get paginated history
GET  /api/v1/ai-recommendations/{week_start} — get a specific week's report
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.api.deps import get_current_user, get_ai_recommendations_service
from app.core.exceptions import NotFoundError
from app.models.weekly_report import WeeklyReportHistoryResponse
from app.services.ai_recommendations_service import AiRecommendationsService

router = APIRouter()


@router.get(
    "",
    response_model=dict,
    summary="Get today's AI recommendations",
)
async def get_ai_recommendations(
    force_regenerate: bool = Query(False, description="Force regenerate the report"),
    user_id: str = Depends(get_current_user),
    service: AiRecommendationsService = Depends(get_ai_recommendations_service),
):
    """
    Generate (or fetch cached) AI recommendations for the current day.

    Recommendations cover:
      - Study Order: which skills to study, in what priority
      - Revision Priorities: topics within weak skills
      - Extra Practice: targeted practice sessions per weak skill
      - Additional Resources: resource recommendations
      - Break Suggestions: when and how to rest
      - Time Management: daily budget allocation and scheduling tips
    """
    today = date.today()
    return service.get_recommendations(user_id, run_date=today, force_regenerate=force_regenerate)


@router.get(
    "/history",
    response_model=WeeklyReportHistoryResponse,
    summary="Get AI recommendation history",
)
async def get_ai_recommendations_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: AiRecommendationsService = Depends(get_ai_recommendations_service),
):
    """Return paginated history of previously generated AI recommendations."""
    return service.get_history(user_id, limit=limit, offset=offset)


@router.get(
    "/{week_start}",
    response_model=dict,
    summary="Get AI recommendations for a specific week",
)
async def get_ai_recommendations_by_date(
    week_start: str,
    force_regenerate: bool = Query(False, description="Force regenerate even if a report exists"),
    user_id: str = Depends(get_current_user),
    service: AiRecommendationsService = Depends(get_ai_recommendations_service),
):
    """
    Fetch AI recommendations for the week containing the given date.

    `week_start` is an ISO date (YYYY-MM-DD).
    """
    try:
        parsed = date.fromisoformat(week_start[:10])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="week_start must be a valid ISO date (YYYY-MM-DD)",
        )
    return service.get_recommendations(user_id, run_date=parsed, force_regenerate=force_regenerate)
