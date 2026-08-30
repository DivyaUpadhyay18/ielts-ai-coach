"""Pydantic schemas for the Mission Reflection domain.

A reflection is a structured, deterministic post-mortem stored once per
completed daily mission (Today's strengths / mistakes / areas to revise /
tomorrow's focus / confidence level / estimated improvement).
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReflectionData(BaseModel):
    """The six structured reflection fields produced by the ReflectionEngine."""
    strengths: List[str] = Field(default_factory=list, description="What went well today")
    mistakes: List[str] = Field(default_factory=list, description="What slipped today")
    areas_to_revise: List[str] = Field(default_factory=list, description="Skills/narrow topics to review")
    tomorrow_focus: str = Field(default="", description="One concrete, roadmap-grounded action for tomorrow")
    confidence_level: int = Field(default=5, ge=1, le=10, description="1-10 confidence in the predicted trajectory")
    estimated_improvement: float = Field(default=0.0, description="Projected band gain (0.25-band granularity)")
    estimated_improvement_text: str = Field(default="", description="Human-readable improvement summary")


class MissionReflectionResponse(BaseModel):
    """A stored mission reflection as exposed by the API."""
    id: str
    user_id: str
    mission_id: str
    mission_date: Optional[date] = None
    skill: str
    strengths: List[str] = Field(default_factory=list)
    mistakes: List[str] = Field(default_factory=list)
    areas_to_revise: List[str] = Field(default_factory=list)
    tomorrow_focus: str
    confidence_level: int
    estimated_improvement: float
    estimated_improvement_text: str
    context_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MissionReflectionListResponse(BaseModel):
    """Paginated list of mission reflections."""
    items: List[MissionReflectionResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0
