"""
Pydantic schemas for the Weekly AI Reports system.

Each weekly report aggregates a user's study activity for a given week into
a deterministic (NO AI) summary, achievements, progress metrics, estimated
band, and personalized suggestions.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WeeklyReportResponse(BaseModel):
    """Full weekly AI report payload returned to the frontend."""
    user_id: str
    week_start: str
    week_end: str
    generated_at: str
    summary: str
    achievements: List[str] = Field(default_factory=list)
    weakest_skill: Optional[str] = None
    strongest_skill: Optional[str] = None
    hours_studied: float = 0.0
    tasks_completed: int = 0
    streak: int = 0
    consistency: float = 0.0
    estimated_band: float = 0.0
    suggestions: List[str] = Field(default_factory=list)
    next_week_focus: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    formulas: Dict[str, str] = Field(default_factory=dict)
    previous_report: Optional[Dict[str, Any]] = None
    previous_week_band: Optional[float] = None


class WeeklyReportHistoryItem(BaseModel):
    """A single weekly report in history listing."""
    user_id: str
    week_start: str
    week_end: str
    generated_at: str
    estimated_band: float
    tasks_completed: int
    hours_studied: float
    consistency: float
    streak: int
    summary: str


class WeeklyReportHistoryResponse(BaseModel):
    """Paginated list of historical weekly reports."""
    items: List[WeeklyReportHistoryItem] = Field(default_factory=list)
    total: int = 0
    limit: int
    offset: int
