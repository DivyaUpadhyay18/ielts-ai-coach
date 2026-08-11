"""
Pydantic schemas for the Recommendation Engine domain.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    """Schema for recommendation request parameters."""
    skill: Optional[str] = None
    sub_skill: Optional[str] = None
    resource_type: Optional[str] = None
    limit: int = Field(10, ge=1, le=50)
    include_completed: bool = False
    only_verified: bool = True


class RecommendationResponse(BaseModel):
    """Schema for recommendation response."""
    user_id: str
    run_date: str
    current_band: float
    target_band: float
    weakest_skill: Optional[str]
    today_mission_skill: Optional[str]
    sub_skill: Optional[str]
    estimated_time: int
    remaining_days: Optional[int]
    recommendations: List[Dict[str, Any]]
    ranking_algorithm: str
    metadata: Dict[str, Any]


class RecommendationLogResponse(BaseModel):
    """Schema for recommendation log entry."""
    id: str
    user_id: str
    run_date: str
    current_band: Optional[float]
    target_band: Optional[float]
    weakest_skill: Optional[str]
    today_mission_skill: Optional[str]
    sub_skill: Optional[str]
    estimated_time: Optional[int]
    remaining_days: Optional[int]
    resource_count: int
    top_resource_id: Optional[str]
    top_score: Optional[float]
    metadata: Optional[Dict[str, Any]]
    created_at: Optional[datetime]


class RecommendationTrackRequest(BaseModel):
    """Schema for tracking recommendation interaction."""
    user_id: str
    resource_id: str
    recommendation_log_id: Optional[str] = None
    action: str = Field(..., description="Action: viewed, clicked, completed")
    session_id: Optional[str] = None
