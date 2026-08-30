"""
Resource Quality Scoring API endpoints.

Provides:
  # ─── User Feedback ────────────────────────────────────────────
  - POST   /feedback                          → submit feedback (broken link, better resource, correction, rating)
  - GET    /feedback                          → list my feedback
  - GET    /feedback/{feedback_id}            → get a feedback entry
  - DELETE /feedback/{feedback_id}            → withdraw feedback

  # ─── Quality Scores ───────────────────────────────────────────
  - GET    /resources/{resource_id}/scores    → get quality scores for a resource
  - GET    /resources/{resource_id}/breakdown → get detailed score breakdown
  - POST   /resources/{resource_id}/recompute → recompute scores for a resource
  - GET    /leaderboard                       → quality leaderboard
  - POST   /recompute-all                     → recompute all scores (batch)

  # ─── Admin Moderation ────────────────────────────────────────
  - GET    /admin/queue                       → moderation queue
  - GET    /admin/feedback/{feedback_id}/log  → moderation log
  - POST   /admin/feedback/{feedback_id}/moderate → moderate feedback

  # ─── Stats ────────────────────────────────────────────────────
  - GET    /stats                             → quality system statistics
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_resource_quality_repo
from app.models.resource_quality import (
    ResourceFeedbackCreate,
    ResourceFeedbackResponse,
    ResourceFeedbackListResponse,
    ModerationAction,
    ModerationLogResponse,
    ModerationQueueResponse,
    ResourceQualityScoresResponse,
    ResourceQualityLeaderboardItem,
    ResourceQualityLeaderboardResponse,
    QualityScoreBreakdown,
    ResourceQualityStatsResponse,
)
from app.repositories.resource_quality_repo import ResourceQualityRepository

router = APIRouter()


# ─── User Feedback ───────────────────────────────────────────────────────────

@router.post(
    "/feedback",
    response_model=ResourceFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit resource feedback",
)
async def submit_feedback(
    data: ResourceFeedbackCreate,
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Submit feedback on a resource (broken link, better resource, correction, or rating)."""
    # Validate feedback type-specific required fields
    ft = data.feedback_type
    if ft == "broken_link" and not (data.title and data.description):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="broken_link feedback requires title and description",
        )
    if ft == "better_resource" and not (data.suggested_url and data.suggested_title):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="better_resource feedback requires suggested_url and suggested_title",
        )
    if ft == "correction" and not (data.field_name and data.suggested_value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="correction feedback requires field_name and suggested_value",
        )
    if ft == "rating" and data.rating is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rating feedback requires a rating value (1-5)",
        )

    return repo.submit_feedback(
        user_id=user_id,
        resource_id=data.resource_id,
        feedback_type=data.feedback_type,
        title=data.title,
        description=data.description,
        suggested_url=data.suggested_url,
        suggested_title=data.suggested_title,
        field_name=data.field_name,
        suggested_value=data.suggested_value,
        reason=data.reason,
        rating=data.rating,
    )


@router.get(
    "/feedback",
    response_model=ResourceFeedbackListResponse,
    summary="List my feedback",
)
async def list_my_feedback(
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """List feedback submitted by the current user."""
    items = repo.list_user_feedback(
        user_id=user_id,
        resource_id=resource_id,
        feedback_type=feedback_type,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ResourceFeedbackListResponse(
        items=[ResourceFeedbackResponse(**i) for i in items],
        total=len(items),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/feedback/{feedback_id}",
    response_model=ResourceFeedbackResponse,
    summary="Get a feedback entry",
)
async def get_feedback(
    feedback_id: str,
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Get a single feedback entry by ID (must be your own)."""
    feedback = repo.get_feedback(feedback_id, user_id=user_id)
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    return feedback


@router.delete(
    "/feedback/{feedback_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw feedback",
)
async def delete_feedback(
    feedback_id: str,
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Withdraw (delete) your feedback."""
    deleted = repo.delete_feedback(feedback_id, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")


# ─── Quality Scores ──────────────────────────────────────────────────────────

@router.get(
    "/resources/{resource_id}/scores",
    response_model=ResourceQualityScoresResponse,
    summary="Get quality scores for a resource",
)
async def get_quality_scores(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Get the computed quality scores for a resource (computes on demand if missing)."""
    scores = repo.get_quality_scores(resource_id)
    return ResourceQualityScoresResponse(**scores)


@router.get(
    "/resources/{resource_id}/breakdown",
    response_model=QualityScoreBreakdown,
    summary="Get detailed score breakdown",
)
async def get_score_breakdown(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Get a detailed breakdown of how quality scores were computed (transparency)."""
    breakdown = repo.get_score_breakdown(resource_id)
    return QualityScoreBreakdown(**breakdown)


@router.post(
    "/resources/{resource_id}/recompute",
    response_model=ResourceQualityScoresResponse,
    summary="Recompute quality scores for a resource",
)
async def recompute_scores(
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Force recompute of quality scores for a resource."""
    scores = repo.compute_quality_scores(resource_id)
    return ResourceQualityScoresResponse(**scores)


@router.get(
    "/leaderboard",
    response_model=ResourceQualityLeaderboardResponse,
    summary="Get quality leaderboard",
)
async def get_leaderboard(
    sort_by: str = Query("recommendation_score", description="Sort by: recommendation_score, quality_score, popularity_score, completion_score"),
    limit: int = Query(20, ge=1, le=100),
    skill: Optional[str] = Query(None, description="Filter by skill"),
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Get the quality leaderboard (top resources by score)."""
    items = repo.get_leaderboard(sort_by=sort_by, limit=limit, skill=skill)
    return ResourceQualityLeaderboardResponse(
        items=[ResourceQualityLeaderboardItem(**i) for i in items],
        total=len(items),
    )


@router.post(
    "/recompute-all",
    summary="Recompute all quality scores (batch)",
)
async def recompute_all_scores(
    limit: int = Query(100, ge=1, le=1000, description="Max resources to recompute"),
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Batch recompute quality scores for all resources with analytics data."""
    return repo.recompute_all_scores(limit=limit)


# ─── Admin Moderation ────────────────────────────────────────────────────────

@router.get(
    "/admin/queue",
    response_model=ModerationQueueResponse,
    summary="Get moderation queue (admin)",
)
async def get_moderation_queue(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Get the moderation queue with summary stats. (Admin endpoint.)"""
    queue = repo.get_moderation_queue(
        status=status_filter,
        feedback_type=feedback_type,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    return ModerationQueueResponse(
        items=[ResourceFeedbackResponse(**i) for i in queue["items"]],
        total=queue["total"],
        pending_count=queue["pending_count"],
        high_priority_count=queue["high_priority_count"],
        broken_link_count=queue["broken_link_count"],
        correction_count=queue["correction_count"],
        suggestion_count=queue["suggestion_count"],
    )


@router.get(
    "/admin/feedback/{feedback_id}/log",
    response_model=List[ModerationLogResponse],
    summary="Get moderation log for a feedback entry (admin)",
)
async def get_moderation_log(
    feedback_id: str,
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Get the moderation audit trail for a feedback entry. (Admin endpoint.)"""
    return repo.get_moderation_log(feedback_id)


@router.post(
    "/admin/feedback/{feedback_id}/moderate",
    response_model=ResourceFeedbackResponse,
    summary="Moderate feedback (admin)",
)
async def moderate_feedback(
    feedback_id: str,
    data: ModerationAction,
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Perform a moderation action on feedback. (Admin endpoint.)

    Actions: approved, rejected, resolved, dismissed, escalated, commented.
    """
    return repo.moderate_feedback(
        feedback_id=feedback_id,
        admin_id=user_id,
        action=data.action,
        admin_notes=data.admin_notes,
        new_priority=data.new_priority,
    )


# ─── Stats ───────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=ResourceQualityStatsResponse,
    summary="Get quality system statistics",
)
async def get_quality_stats(
    user_id: str = Depends(get_current_user),
    repo: ResourceQualityRepository = Depends(get_resource_quality_repo),
):
    """Get system-wide quality statistics."""
    return ResourceQualityStatsResponse(**repo.get_quality_stats())