"""
Pydantic schemas for the Resource Quality Scoring domain.

Backs the resource_feedback / resource_quality_scores / resource_moderation_log
tables and the resource-quality API surface. Supports:
  - User feedback: broken link reports, better resource suggestions, corrections, ratings
  - Admin moderation: approve/reject/resolve/dismiss feedback
  - Quality scoring: quality, popularity, completion, recommendation scores
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Feedback Types ──────────────────────────────────────────────────────────

FEEDBACK_TYPES = ("broken_link", "better_resource", "correction", "rating")
FEEDBACK_STATUS = ("pending", "approved", "rejected", "resolved", "dismissed")
FEEDBACK_PRIORITY = ("low", "normal", "high", "urgent")
MODERATION_ACTIONS = ("approved", "rejected", "resolved", "dismissed", "escalated", "commented")


# ─── Feedback Create ─────────────────────────────────────────────────────────

class BrokenLinkFeedbackCreate(BaseModel):
    """Schema for reporting a broken link."""
    resource_id: str
    feedback_type: str = Field("broken_link", pattern="^broken_link$")
    title: str = Field(..., min_length=1, max_length=300, description="Brief title of the issue")
    description: str = Field(..., min_length=1, max_length=2000, description="What's broken")


class BetterResourceFeedbackCreate(BaseModel):
    """Schema for suggesting a better resource."""
    resource_id: str
    feedback_type: str = Field("better_resource", pattern="^better_resource$")
    suggested_url: str = Field(..., min_length=1, max_length=2000, description="URL of the better resource")
    suggested_title: str = Field(..., min_length=1, max_length=300, description="Title of the better resource")
    reason: Optional[str] = Field(None, max_length=2000, description="Why this is better")

    @field_validator("suggested_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError("Suggested URL must start with https:// or http://")
        return v.strip()


class CorrectionFeedbackCreate(BaseModel):
    """Schema for suggesting a correction."""
    resource_id: str
    feedback_type: str = Field("correction", pattern="^correction$")
    field_name: str = Field(..., min_length=1, max_length=100, description="Field to correct (e.g., title, description, url)")
    suggested_value: str = Field(..., min_length=1, max_length=2000, description="Corrected value")
    reason: Optional[str] = Field(None, max_length=2000, description="Why this correction is needed")


class RatingFeedbackCreate(BaseModel):
    """Schema for submitting a rating as feedback."""
    resource_id: str
    feedback_type: str = Field("rating", pattern="^rating$")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")


class ResourceFeedbackCreate(BaseModel):
    """Unified schema for creating resource feedback. Accepts any feedback type."""
    resource_id: str
    feedback_type: str = Field(..., description="Type of feedback: broken_link, better_resource, correction, rating")
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    suggested_url: Optional[str] = Field(None, max_length=2000)
    suggested_title: Optional[str] = Field(None, max_length=300)
    field_name: Optional[str] = Field(None, max_length=100)
    suggested_value: Optional[str] = Field(None, max_length=2000)
    reason: Optional[str] = Field(None, max_length=2000)
    rating: Optional[int] = Field(None, ge=1, le=5)

    @field_validator("feedback_type")
    @classmethod
    def validate_feedback_type(cls, v: str) -> str:
        if v not in FEEDBACK_TYPES:
            raise ValueError(f"feedback_type must be one of: {', '.join(FEEDBACK_TYPES)}")
        return v

    @field_validator("suggested_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith(("https://", "http://")):
            raise ValueError("Suggested URL must start with https:// or http://")
        return v.strip()

    def model_dump(self, **kwargs):
        """Override to only include fields relevant to the feedback type."""
        data = super().model_dump(**kwargs)
        # Clean up None values for cleaner DB inserts
        return {k: v for k, v in data.items() if v is not None or k in ("resource_id", "feedback_type")}


# ─── Feedback Response ───────────────────────────────────────────────────────

class ResourceFeedbackResponse(BaseModel):
    """Schema for a feedback response."""
    id: str
    user_id: str
    resource_id: str
    feedback_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    suggested_url: Optional[str] = None
    suggested_title: Optional[str] = None
    field_name: Optional[str] = None
    suggested_value: Optional[str] = None
    reason: Optional[str] = None
    rating: Optional[int] = None
    status: str = "pending"
    priority: str = "normal"
    admin_notes: Optional[str] = None
    moderated_by: Optional[str] = None
    moderated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResourceFeedbackListResponse(BaseModel):
    """Paginated list of feedback."""
    items: List[ResourceFeedbackResponse]
    total: int
    limit: int
    offset: int


# ─── Moderation ──────────────────────────────────────────────────────────────

class ModerationAction(BaseModel):
    """Schema for admin moderation action."""
    action: str = Field(..., description="Action: approved, rejected, resolved, dismissed, escalated, commented")
    admin_notes: Optional[str] = Field(None, max_length=2000, description="Admin notes explaining the action")
    new_priority: Optional[str] = Field(None, description="Override priority: low, normal, high, urgent")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in MODERATION_ACTIONS:
            raise ValueError(f"action must be one of: {', '.join(MODERATION_ACTIONS)}")
        return v

    @field_validator("new_priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in FEEDBACK_PRIORITY:
            raise ValueError(f"new_priority must be one of: {', '.join(FEEDBACK_PRIORITY)}")
        return v


class ModerationLogResponse(BaseModel):
    """Schema for a moderation log entry."""
    id: str
    feedback_id: str
    admin_id: str
    action: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class ModerationQueueResponse(BaseModel):
    """Schema for the moderation queue."""
    items: List[ResourceFeedbackResponse]
    total: int
    pending_count: int
    high_priority_count: int
    broken_link_count: int
    correction_count: int
    suggestion_count: int


# ─── Quality Scores ──────────────────────────────────────────────────────────

class ResourceQualityScoresResponse(BaseModel):
    """Schema for per-resource quality scores."""
    resource_id: str
    quality_score: float = 0.0
    popularity_score: float = 0.0
    completion_score: float = 0.0
    recommendation_score: float = 0.0
    avg_rating: float = 0.0
    rating_count: int = 0
    view_count: int = 0
    bookmark_count: int = 0
    like_count: int = 0
    completion_count: int = 0
    broken_link_count: int = 0
    correction_count: int = 0
    suggestion_count: int = 0
    computed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResourceQualityLeaderboardItem(BaseModel):
    """Schema for a leaderboard entry."""
    resource_id: str
    title: str = ""
    type: str = ""
    skill: str = ""
    quality_score: float = 0.0
    popularity_score: float = 0.0
    completion_score: float = 0.0
    recommendation_score: float = 0.0
    avg_rating: float = 0.0
    rating_count: int = 0
    view_count: int = 0
    like_count: int = 0
    completion_count: int = 0


class ResourceQualityLeaderboardResponse(BaseModel):
    """Schema for the quality leaderboard."""
    items: List[ResourceQualityLeaderboardItem]
    total: int


class QualityScoreBreakdown(BaseModel):
    """Schema for a detailed score breakdown (transparency)."""
    resource_id: str
    quality_score: float = 0.0
    popularity_score: float = 0.0
    completion_score: float = 0.0
    recommendation_score: float = 0.0
    components: dict = Field(default_factory=dict, description="Detailed component breakdown")
    weights: dict = Field(default_factory=dict, description="Scoring weights used")
    computed_at: Optional[datetime] = None


# ─── Quality Stats ───────────────────────────────────────────────────────────

class ResourceQualityStatsResponse(BaseModel):
    """Schema for quality system statistics."""
    total_feedback: int = 0
    pending_feedback: int = 0
    approved_feedback: int = 0
    rejected_feedback: int = 0
    resolved_feedback: int = 0
    dismissed_feedback: int = 0
    broken_link_reports: int = 0
    correction_suggestions: int = 0
    better_resource_suggestions: int = 0
    rating_feedback: int = 0
    total_resources_scored: int = 0
    avg_quality_score: float = 0.0
    avg_popularity_score: float = 0.0
    avg_completion_score: float = 0.0
    avg_recommendation_score: float = 0.0