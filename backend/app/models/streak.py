"""
Pydantic schemas for the Streak System domain.

Backs the extended progress_state columns, streak_freezes and
streak_events tables. All bonuses are deterministic (no AI):
milestone checkpoints, perfect-day bonus and freeze placeholders.
"""
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Freeze schemas
# ---------------------------------------------------------------------------
class StreakFreezeResponse(BaseModel):
    """A single streak freeze token."""
    id: str
    user_id: str
    period_type: str = "day"
    status: str = "available"
    granted_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    source: str = "placeholder"


class FreezeUseRequest(BaseModel):
    """Schema for using a streak freeze."""
    freeze_id: str


# ---------------------------------------------------------------------------
# Overview sub-blocks
# ---------------------------------------------------------------------------
class StreakLevelInfo(BaseModel):
    """Daily / weekly / monthly streak info block."""
    kind: str = "daily"
    current: int = 0
    longest: int = 0
    at_risk: bool = False
    last_active: Optional[date] = None
    target: int = 0  # milestones required to keep / extend the streak


class StreakBonusInfo(BaseModel):
    """XP bonus breakdown."""
    total_bonus_xp: int = 0
    perfect_day_xp: int = 0
    milestone_xp: int = 0
    perfect_day_count: int = 0


class PerfectDayInfo(BaseModel):
    """Perfect-day status for today."""
    achieved: bool = False
    bonus_xp: int = 25
    last_perfect_date: Optional[date] = None
    perfect_day_count: int = 0
    remaining_missions: int = 0


class CarryForwardInfo(BaseModel):
    """Carry-forward minute bank."""
    bank_minutes: int = 0
    cap_minutes: int = 120
    next_miss_covered: bool = False


class FreezeInfo(BaseModel):
    """Streak-freeze summary (placeholder system)."""
    available: int = 0
    used: int = 0
    can_use: bool = False
    note: str = ""


class NextMilestone(BaseModel):
    """Next XP / streak milestone."""
    label: str = ""
    target: int = 0
    current: int = 0
    remaining: int = 0
    xp_bonus: int = 0


class StreakEventItem(BaseModel):
    """A recorded bonus-award event."""
    id: str
    event_type: str = ""
    label: str = ""
    period_key: str = ""
    xp_awarded: int = 0
    created_at: Optional[datetime] = None


class StreakLinePoint(BaseModel):
    """A single point on a streak history line."""
    date: str = ""
    label: str = ""
    value: int = 0  # streak length at that date
    note: str = ""


# ---------------------------------------------------------------------------
# Overview response
# ---------------------------------------------------------------------------
class StreakOverviewResponse(BaseModel):
    """Full streak-system overview for the dashboard and streak center."""
    daily: StreakLevelInfo
    weekly: StreakLevelInfo
    monthly: StreakLevelInfo
    perfect_day: PerfectDayInfo
    carry_forward: CarryForwardInfo
    freezes: FreezeInfo
    bonuses: StreakBonusInfo
    next_milestones: List[NextMilestone] = Field(default_factory=list)
    history: List[StreakLinePoint] = Field(default_factory=list)
    last_streak_update: Optional[date] = None

