"""
Analytics API endpoints.

Provides:
  - POST /events          → track a single analytics event
  - POST /events/batch    → track multiple analytics events (max 50)
  - GET  /dashboard       → full analytics dashboard payload
  - GET  /summary         → high-level analytics summary
  - GET  /trends          → daily trend series
  - GET  /skills          → per-skill breakdown
  - GET  /resources/top   → top performing resources
  - GET  /resources/{resource_id} → per-resource analytics
  - GET  /events          → recent analytics events
  - POST /resources/{resource_id}/view       → record a resource view
  - POST /resources/{resource_id}/complete   → record a resource completion
  - POST /resources/{resource_id}/bookmark   → record a resource bookmark
  - DELETE /resources/{resource_id}/bookmark → remove a resource bookmark
  - POST /resources/{resource_id}/like       → toggle a resource like
  - POST /resources/{resource_id}/rate       → rate a resource (1-5)
  - POST /study-sessions                     → record a study session
All numbers are read from real stored data (analytics_events /
resource_analytics / user_analytics) — never client-side fabricated.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_analytics_repo
from app.models.analytics import (
    AnalyticsEventBatch,
    AnalyticsEventCreate,
    AnalyticsEventResponse,
    AnalyticsDashboardResponse,
    AnalyticsSummary,
    AnalyticsTrendPoint,
    SkillBreakdown,
    ResourcePerformanceItem,
    ResourceAnalyticsResponse,
    ResourceRatingCreate,
    ResourceRatingResponse,
    UserAnalyticsResponse,
)
from app.repositories.analytics_repo import AnalyticsRepository

router = APIRouter()


# ─── Event Tracking ──────────────────────────────────────────────────────────

@router.post(
    "/events",
    response_model=AnalyticsEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Track a single analytics event",
)
async def track_event(
    data: AnalyticsEventCreate,
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Append a single analytics event to the ledger."""
    return repo.track_event(
        user_id=user_id,
        event=data.event,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        properties=data.properties,
        session_id=data.session_id,
        timestamp=data.timestamp,
    )


@router.post(
    "/events/batch",
    response_model=List[AnalyticsEventResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Track multiple analytics events",
)
async def track_events_batch(
    data: AnalyticsEventBatch,
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Append multiple analytics events in a single batch (max 50)."""
    events = [ev.model_dump() for ev in data.events]
    return repo.track_events_batch(user_id, events)


# ─── Resource Interaction Tracking ───────────────────────────────────────────

@router.post(
    "/resources/{resource_id}/view",
    status_code=status.HTTP_200_OK,
    summary="Record a resource view",
)
async def record_resource_view(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Record that the current user viewed a resource."""
    repo.record_view(user_id, resource_id)
    return {"status": "viewed", "resource_id": resource_id}


@router.post(
    "/resources/{resource_id}/complete",
    status_code=status.HTTP_200_OK,
    summary="Record a resource completion",
)
async def record_resource_complete(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Record that the current user completed a resource."""
    repo.record_completion(user_id, resource_id)
    return {"status": "completed", "resource_id": resource_id}


@router.post(
    "/resources/{resource_id}/bookmark",
    status_code=status.HTTP_200_OK,
    summary="Record a resource bookmark",
)
async def record_resource_bookmark(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Record that the current user bookmarked a resource."""
    repo.record_bookmark(user_id, resource_id)
    return {"status": "bookmarked", "resource_id": resource_id}


@router.delete(
    "/resources/{resource_id}/bookmark",
    status_code=status.HTTP_200_OK,
    summary="Remove a resource bookmark",
)
async def remove_resource_bookmark(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Remove a bookmark from a resource."""
    repo.remove_bookmark(user_id, resource_id)
    return {"status": "unbookmarked", "resource_id": resource_id}


@router.post(
    "/resources/{resource_id}/like",
    status_code=status.HTTP_200_OK,
    summary="Toggle a like on a resource",
)
async def toggle_resource_like(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Toggle a like on a resource. Returns liked=true/false."""
    return repo.toggle_like(user_id, resource_id)


@router.post(
    "/resources/{resource_id}/rate",
    response_model=ResourceRatingResponse,
    status_code=status.HTTP_200_OK,
    summary="Rate a resource (1-5)",
)
async def rate_resource(
    resource_id: str,
    data: ResourceRatingCreate,
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Rate a resource on a 1-5 scale. Upserts on (user_id, resource_id)."""
    if data.resource_id != resource_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="resource_id in body must match path parameter",
        )
    return repo.rate_resource(user_id, resource_id, data.rating)


@router.post(
    "/study-sessions",
    status_code=status.HTTP_200_OK,
    summary="Record a study session",
)
async def record_study_session(
    minutes: int = Query(..., ge=1, le=600, description="Study minutes"),
    skill: Optional[str] = Query(None, description="Skill domain"),
    source_type: str = Query("task", description="Source type: task, mission, assessment, resource"),
    source_id: Optional[str] = Query(None, description="Source entity ID"),
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Record a study session for analytics aggregation."""
    repo.record_study_session(
        user_id=user_id,
        minutes=minutes,
        skill=skill,
        source_type=source_type,
        source_id=source_id,
    )
    return {"status": "recorded", "minutes": minutes, "skill": skill}


# ─── Reads / Dashboard ───────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=AnalyticsDashboardResponse,
    summary="Get full analytics dashboard",
)
async def get_analytics_dashboard(
    days: int = Query(30, ge=7, le=90, description="Number of days for trends"),
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Return the full analytics dashboard payload for the current user."""
    return AnalyticsDashboardResponse(**repo.get_dashboard(user_id, days=days))


@router.get(
    "/summary",
    response_model=AnalyticsSummary,
    summary="Get analytics summary",
)
async def get_analytics_summary(
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Return high-level analytics summary metrics."""
    dashboard = repo.get_dashboard(user_id, days=30)
    return AnalyticsSummary(**dashboard["summary"])


@router.get(
    "/trends",
    response_model=List[AnalyticsTrendPoint],
    summary="Get daily analytics trends",
)
async def get_analytics_trends(
    days: int = Query(30, ge=7, le=90),
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Return daily trend series for views, completions, bookmarks, likes, ratings, study minutes."""
    dashboard = repo.get_dashboard(user_id, days=days)
    return [AnalyticsTrendPoint(**t) for t in dashboard["trends"]]


@router.get(
    "/skills",
    response_model=List[SkillBreakdown],
    summary="Get per-skill analytics breakdown",
)
async def get_analytics_skills(
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Return per-skill analytics breakdown."""
    dashboard = repo.get_dashboard(user_id, days=30)
    return [SkillBreakdown(**s) for s in dashboard["skill_breakdown"]]


@router.get(
    "/resources/top",
    response_model=List[ResourcePerformanceItem],
    summary="Get top performing resources",
)
async def get_top_resources(
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Return top performing resources by views/completions."""
    dashboard = repo.get_dashboard(user_id, days=30)
    return [ResourcePerformanceItem(**r) for r in dashboard["top_resources"][:limit]]


@router.get(
    "/resources/{resource_id}",
    response_model=ResourceAnalyticsResponse,
    summary="Get per-resource analytics",
)
async def get_resource_analytics(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Return aggregate analytics for a single resource."""
    return ResourceAnalyticsResponse(**repo.get_resource_analytics(resource_id))


@router.get(
    "/events",
    response_model=List[AnalyticsEventResponse],
    summary="Get recent analytics events",
)
async def get_analytics_events(
    limit: int = Query(50, ge=1, le=200),
    event: Optional[str] = Query(None, description="Filter by event name"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Return recent analytics events for the current user."""
    return repo.get_user_events(
        user_id,
        limit=limit,
        event=event,
        entity_type=entity_type,
    )


@router.get(
    "/me",
    response_model=UserAnalyticsResponse,
    summary="Get current user's analytics counters",
)
async def get_my_analytics(
    user_id: str = Depends(get_current_user),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """Return the current user's aggregate analytics counters."""
    return UserAnalyticsResponse(**repo.get_user_analytics(user_id))