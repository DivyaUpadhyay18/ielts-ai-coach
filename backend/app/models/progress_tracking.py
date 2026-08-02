"""
Pydantic schemas for the Progress Tracking domain.

Backs the study_sessions / daily_stats / progress_state tables and the
progress-tracking API surface. XP levels follow the gamification curve
(level_n_required_xp = 100 * n^1.35).
"""
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

# The six IELTS skill domains tracked in study sessions.
PROGRESS_SKILLS = ("reading", "listening", "writing", "speaking", "vocabulary", "grammar")
STUDY_SESSION_TYPES = (
    "mission", "task", "writing", "speaking", "reading", "listening",
    "vocabulary", "grammar", "assessment", "mock_test", "resource",
)
STUDY_SOURCE_TYPES = ("mission", "task", "assessment", "manual", "resource")


class StudySessionCreate(BaseModel):
    """Schema for logging a study session."""
    activity_date: Optional[date] = None  # defaults to today
    skill: Optional[str] = None
    session_type: str = Field("mission", pattern="^(mission|task|writing|speaking|reading|listening|vocabulary|grammar|assessment|mock_test|resource)$")
    minutes: int = Field(..., ge=1, le=600)
    xp_earned: int = Field(0, ge=0)
    source_type: str = Field("mission", pattern="^(mission|task|assessment|manual|resource)$")
    source_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class StudySessionResponse(BaseModel):
    """Schema for a logged study session."""
    id: str
    user_id: str
    activity_date: date
    skill: Optional[str] = None
    session_type: str = "mission"
    minutes: int
    xp_earned: int = 0
    source_type: str = "mission"
    source_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class StreakInfo(BaseModel):
    """Current and longest activity streak."""
    current: int = 0
    longest: int = 0
    at_risk: bool = False
    last_active_date: Optional[date] = None
    note: str = ""


class XPInfo(BaseModel):
    """Lifetime XP and level info (derived from the XP curve)."""
    today: int = 0
    daily_target: int = 100
    level: int = 1
    level_progress: float = 0.0  # 0.0–1.0 to next level
    total: int = 0
    note: str = ""


class PeriodProgress(BaseModel):
    """Progress within a period (day/week/month)."""
    period_start: date
    period_end: date
    minutes: int = 0
    tasks_completed: int = 0
    xp_earned: int = 0
    target_minutes: int = 0
    target_tasks: int = 0
    percent: int = 0


class DailyProgress(PeriodProgress):
    """Alias-friendly: a day's totals (kept for symmetry)."""
    pass


class WeeklyProgress(PeriodProgress):
    """A week's totals."""
    pass


class MonthlyProgress(PeriodProgress):
    """A month's totals."""
    pass


class ChartPoint(BaseModel):
    """A single point on a progress chart."""
    date: Optional[date] = None
    label: str = ""
    minutes: int = 0
    tasks: int = 0
    xp: int = 0


class RecentHistoryItem(BaseModel):
    """A single entry in the recent-history feed."""
    id: str
    date: date
    title: str = ""
    skill: Optional[str] = None
    session_type: str = "mission"
    minutes: int = 0
    xp: int = 0


class ProgressOverviewResponse(BaseModel):
    """Aggregated progress-tracking overview for the dashboard."""
    xp: XPInfo
    streak: StreakInfo
    study_time: Dict[str, Any]
    daily: DailyProgress
    weekly: WeeklyProgress
    monthly: MonthlyProgress
    total_minutes: int = 0
    total_tasks: int = 0
    total_xp: int = 0


class ChartsResponse(BaseModel):
    """Chart series data for the analytics page + dashboard."""
    daily_series: List[ChartPoint] = Field(default_factory=list)  # last 7 days
    monthly_series: List[ChartPoint] = Field(default_factory=list)  # last 30 days
    skill_totals: Dict[str, Dict[str, int]] = Field(default_factory=dict)


class HistoryResponse(BaseModel):
    """Recent history list."""
    items: List[RecentHistoryItem] = Field(default_factory=list)

