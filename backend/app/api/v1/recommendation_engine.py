"""
Intelligent Recommendation Engine API endpoints.

Provides rule-based (NO AI) resource recommendations based on user context:
- Current/Target Band, Weakest Skill, Today's Mission, Sub-Skill
- Past Performance, Study History, Difficulty, Time, Exam Countdown
- Completed Resources (exclusion), Official Resource prioritization

Endpoints:
  - GET  /api/v1/recommendations            - Get recommendations
  - GET  /api/v1/recommendations/history    - Get recommendation history
  - POST /api/v1/recommendations/track      - Track user interaction with a recommendation
  - GET  /api/v1/recommendations/stats      - Get recommendation statistics

Ranking algorithm documented in RECOMMENDATION_ENGINE.md
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.api.deps import get_current_user
from app.models.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationLogResponse,
    RecommendationTrackRequest,
)
from app.services.recommendation_engine_service import RecommendationEngineService

router = APIRouter()


def get_recommendation_service() -> RecommendationEngineService:
    from app.services.recommendation_engine_service import recommendation_engine_service
    return recommendation_engine_service


@router.get(
    "",
    response_model=RecommendationResponse,
    summary="Get personalized resource recommendations",
)
async def get_recommendations(
    skill: Optional[str] = Query(None, description="Specific skill to recommend for"),
    sub_skill: Optional[str] = Query(None, description="Specific sub-skill to recommend for"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit: int = Query(10, ge=1, le=50, description="Maximum recommendations to return"),
    include_completed: bool = Query(False, description="Include previously completed resources"),
    only_verified: bool = Query(True, description="Only recommend verified resources"),
    user_id: str = Depends(get_current_user),
    service: RecommendationEngineService = Depends(get_recommendation_service),
):
    """
    Get personalized resource recommendations based on your IELTS profile.

    The recommendation engine considers:
    - Your current and target band scores
    - Your weakest skills (from onboarding)
    - Today's mission skill
    - Your study history and past performance
    - Remaining days until your exam
    - Your daily study time budget

    Returns resources ranked by relevance score (0-100).
    """
    return service.get_recommendations(
        user_id=user_id,
        skill=skill,
        sub_skill=sub_skill,
        resource_type=resource_type,
        limit=limit,
        include_completed=include_completed,
        only_verified=only_verified,
    )


@router.get(
    "/history",
    response_model=List[RecommendationLogResponse],
    summary="Get recommendation history",
)
async def get_recommendation_history(
    limit: int = Query(20, ge=1, le=100, description="Maximum logs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user_id: str = Depends(get_current_user),
    service: RecommendationEngineService = Depends(get_recommendation_service),
):
    """Get your history of recommendation requests."""
    logs = service.repo.get_recommendation_logs(user_id, limit=limit, offset=offset)
    return [
        {
            "id": log.get("id"),
            "user_id": log.get("user_id"),
            "run_date": log.get("run_date"),
            "current_band": log.get("current_band"),
            "target_band": log.get("target_band"),
            "weakest_skill": log.get("weakest_skill"),
            "today_mission_skill": log.get("today_mission_skill"),
            "sub_skill": log.get("sub_skill"),
            "estimated_time": log.get("estimated_time"),
            "remaining_days": log.get("remaining_days"),
            "resource_count": log.get("resource_count"),
            "top_resource_id": log.get("top_resource_id"),
            "top_score": log.get("top_score"),
            "metadata": log.get("metadata") or {},
            "created_at": log.get("created_at"),
        }
        for log in logs
    ]


@router.post(
    "/track",
    response_model=dict,
    status_code=201,
    summary="Track a recommendation interaction",
)
async def track_recommendation(
    data: RecommendationTrackRequest,
    user_id: str = Depends(get_current_user),
    service: RecommendationEngineService = Depends(get_recommendation_service),
):
    """
    Track user interaction with a recommended resource.

    Actions: 'viewed', 'clicked', 'completed'
    """
    result = service.repo.track_resource_view(
        user_id=data.user_id,
        resource_id=data.resource_id,
        recommendation_log_id=data.recommendation_log_id,
        action=data.action,
        session_id=data.session_id,
    )
    return result


@router.get(
    "/stats",
    response_model=dict,
    summary="Get recommendation statistics",
)
async def get_recommendation_stats(
    user_id: str = Depends(get_current_user),
    service: RecommendationEngineService = Depends(get_recommendation_service),
):
    """Get statistics about recommendations served to you."""
    logs = service.repo.get_recommendation_logs(user_id, limit=100)

    total_requests = len(logs)
    total_resources_recommended = sum(log.get("resource_count") or 0 for log in logs)
    by_skill: dict = {}

    for log in logs:
        skill = log.get("weakest_skill") or "unknown"
        if skill not in by_skill:
            by_skill[skill] = 0
        by_skill[skill] += 1

    return {
        "total_requests": total_requests,
        "total_resources_recommended": total_resources_recommended,
        "by_skill": by_skill,
    }