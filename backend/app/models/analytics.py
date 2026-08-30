"""
Pydantic schemas for the Analytics domain.

Backs the analytics_events / resource_analytics / user_analytics tables and
the analytics API surface. Tracks views, completions, bookmarks, likes,
ratings, study time, and derived metrics (completion %, success rate,
drop-off rate).
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Event Tracking ──────────────────────────────────────────────────────────

class AnalyticsEventCreate(BaseModel):
    """Schema for logging a single analytics event."""
    event: str = Field(..., min_length=1, max_length=100)
    entity_type: Optional[str] = Field(None, max_length=50)
    entity_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    timestamp: Optional[datetime] = None


class AnalyticsEventBatch(BaseModel):
    """Schema for batch event ingestion (max 50 per request)."""
    events: List[AnalyticsEventCreate] = Field(..., min_length=1, max_length=50)


class AnalyticsEventResponse(BaseModel):
    """Schema for a logged analytics event."""
    id: str
    user_id: Optional[str] = None
    event: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ─── Resource Analytics ──────────────────────────────────────────────────────

class ResourceAnalyticsResponse(BaseModel):
    """Schema for per-resource aggregate analytics."""
    resource_id: str
    view_count: int = 0
    bookmark_count: int = 0
    like_count: int = 0
    rating_sum: float = 0.0
    rating_count: int = 0
    completion_count: int = 0
    avg_rating: float = 0.0
    updated_at: Optional[datetime] = None


class ResourceLikeResponse(BaseModel):
    """Schema for a resource like."""
    id: str
    user_id: str
    resource_id: str
    created_at: Optional[datetime] = None


class ResourceRatingCreate(BaseModel):
    """Schema for rating a resource."""
    resource_id: str
    rating: int = Field(..., ge=1, le=5)


class ResourceRatingResponse(BaseModel):
    """Schema for a resource rating."""
    id: str
    user_id: str
    resource_id: str
    rating: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─── User Analytics ──────────────────────────────────────────────────────────

class UserAnalyticsResponse(BaseModel):
    """Schema for per-user aggregate analytics."""
    user_id: str
    total_views: int = 0
    total_completions: int = 0
    total_bookmarks: int = 0
    total_likes: int = 0
    total_ratings: int = 0
    total_study_minutes: int = 0
    total_tasks_completed: int = 0
    total_sessions: int = 0
    last_active_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─── Dashboard Analytics ─────────────────────────────────────────────────────

class AnalyticsTrendPoint(BaseModel):
    """A single point on an analytics trend chart."""
    date: str
    label: str = ""
    views: int = 0
    completions: int = 0
    bookmarks: int = 0
    likes: int = 0
    ratings: int = 0
    study_minutes: int = 0


class SkillBreakdown(BaseModel):
    """Per-skill analytics breakdown."""
    skill: str
    views: int = 0
    completions: int = 0
    bookmarks: int = 0
    likes: int = 0
    ratings: int = 0
    study_minutes: int = 0


class ResourcePerformanceItem(BaseModel):
    """Per-resource performance summary."""
    resource_id: str
    title: str = ""
    type: str = ""
    skill: str = ""
    views: int = 0
    bookmarks: int = 0
    likes: int = 0
    completions: int = 0
    avg_rating: float = 0.0
    rating_count: int = 0
    completion_rate: float = 0.0  # 0-100


class AnalyticsSummary(BaseModel):
    """High-level analytics summary for the dashboard."""
    total_views: int = 0
    total_completions: int = 0
    total_bookmarks: int = 0
    total_likes: int = 0
    total_ratings: int = 0
    total_study_minutes: int = 0
    total_tasks_completed: int = 0
    total_sessions: int = 0
    avg_study_time_per_session: float = 0.0
    completion_rate: float = 0.0  # 0-100
    success_rate: float = 0.0  # 0-100
    drop_off_rate: float = 0.0  # 0-100
    active_days: int = 0
    last_active_at: Optional[datetime] = None


class AnalyticsDashboardResponse(BaseModel):
    """Full analytics dashboard payload."""
    summary: AnalyticsSummary
    trends: List[AnalyticsTrendPoint] = Field(default_factory=list)  # last 30 days
    skill_breakdown: List[SkillBreakdown] = Field(default_factory=list)
    top_resources: List[ResourcePerformanceItem] = Field(default_factory=list)
    recent_events: List[AnalyticsEventResponse] = Field(default_factory=list)