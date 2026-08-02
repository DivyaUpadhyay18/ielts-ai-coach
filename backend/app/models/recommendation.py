"""
Pydantic schemas for the Intelligent Recommendation Engine.

Provides rule-based (NO AI) resource recommendations with full CRUD support
for recommendation tracking.

The ranking algorithm is documented inline and in RECOMMENDATION_ENGINE.md.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.resource_management import RESOURCE_TYPES, RESOURCE_SKILLS, ResourceResponse


class RecommendationRequest(BaseModel):
    """Schema for requesting resource recommendations."""
    user_id: Optional[str] = None
    skill: Optional[str] = Field(None, description="Specific skill to recommend for")
    sub_skill: Optional[str] = Field(None, description="Specific sub-skill to recommend for")
    resource_type: Optional[str] = Field(None, description="Filter by resource type (Video, PDF, Website, Quiz, Flashcard)")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of recommendations to return")
    include_completed: bool = Field(False, description="Include previously completed resources (for revision)")
    only_verified: bool = Field(True, description="Only recommend verified resources")

    @field_validator("skill")
    @classmethod
    def validate_skill(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        skills_upper = [s.capitalize() for s in RESOURCE_SKILLS]
        if v not in RESOURCE_SKILLS and v not in skills_upper:
            raise ValueError(f"skill must be one of: {', '.join(RESOURCE_SKILLS)}")
        # Normalize to capitalized form
        for s in RESOURCE_SKILLS:
            if s.lower() == v.lower():
                return s
        return v

    @field_validator("resource_type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        types_cap = [t.capitalize() for t in RESOURCE_TYPES]
        if v not in RESOURCE_TYPES and v not in types_cap:
            raise ValueError(f"resource_type must be one of: {', '.join(RESOURCE_TYPES)}")
        for t in RESOURCE_TYPES:
            if t.lower() == v.lower():
                return t
        return v


class RecommendationItem(BaseModel):
    """A single recommended resource with its relevance score and rationale."""
    resource: ResourceResponse
    score: float = Field(..., ge=0.0, le=100.0, description="Relevance score (0-100)")
    relevance_factors: Dict[str, Any] = Field(default_factory=dict, description="Breakdown of scoring factors")
    rationale: str = Field(..., description="Human-readable explanation for why this resource was recommended")


class RecommendationResponse(BaseModel):
    """Full response for a recommendation request."""
    user_id: str
    run_date: str
    current_band: Optional[float] = None
    target_band: Optional[float] = None
    weakest_skill: Optional[str] = None
    today_mission_skill: Optional[str] = None
    sub_skill: Optional[str] = None
    estimated_time: Optional[int] = None
    remaining_days: Optional[int] = None
    recommendations: List[RecommendationItem] = Field(default_factory=list)
    ranking_algorithm: str = Field(..., description="Name/version of the ranking algorithm used")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecommendationLogCreate(BaseModel):
    """Schema for logging a recommendation request."""
    user_id: str
    current_band: Optional[float] = None
    target_band: Optional[float] = None
    weakest_skill: Optional[str] = None
    today_mission_skill: Optional[str] = None
    sub_skill: Optional[str] = None
    estimated_time: Optional[int] = None
    remaining_days: Optional[int] = None
    resource_count: int = 0
    top_resource_id: Optional[str] = None
    top_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecommendationLogResponse(BaseModel):
    """Schema for a recommendation log response."""
    id: str
    user_id: str
    run_date: str
    current_band: Optional[float] = None
    target_band: Optional[float] = None
    weakest_skill: Optional[str] = None
    today_mission_skill: Optional[str] = None
    sub_skill: Optional[str] = None
    estimated_time: Optional[int] = None
    remaining_days: Optional[int] = None
    resource_count: int
    top_resource_id: Optional[str] = None
    top_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class RecommendationTrackRequest(BaseModel):
    """Schema for tracking user interaction with a recommended resource."""
    user_id: str
    resource_id: str
    recommendation_log_id: Optional[str] = None
    action: str = Field(..., description="One of: viewed, clicked, completed")
    session_id: Optional[str] = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = ("viewed", "clicked", "completed")
        if v not in allowed:
            raise ValueError(f"action must be one of: {', '.join(allowed)}")
        return v