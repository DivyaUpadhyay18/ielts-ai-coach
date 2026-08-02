"""
Pydantic schemas for the Adaptive Scheduler domain.

The Adaptive Scheduler is the deterministic heart of the app: it runs at
midnight or on app open, checks yesterday's completions / missed tasks /
remaining days / completion rate, and rebalances the study plan. Every
change is recorded with a reason string, so users always see exactly what
changed and why.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

TRIGGER_TYPES = ("midnight", "app_open", "manual")
ADJUSTMENT_ACTIONS = ("rescheduled", "carried_forward", "deprioritized", "spread", "merged", "kept", "split")


class SchedulerMetrics(BaseModel):
    """Metrics captured for a scheduler run."""
    total_pending: int = 0
    completed_yesterday: int = 0
    missed_yesterday: int = 0
    carried_forward: int = 0
    rescheduled: int = 0
    deprioritized: int = 0
    merged: int = 0
    days_remaining: int = 0
    completion_rate: float = Field(0.0, ge=0, le=1)
    previous_workload_minutes: int = Field(0, ge=0)
    new_workload_minutes: int = Field(0, ge=0)
    workload_percent: float = Field(0.0, ge=0)
    overload_factor: float = Field(1.0, ge=0)
    adjustment_count: int = Field(0, ge=0)
    streak_saver_mode: bool = False
    consecutive_missed_days: int = Field(0, ge=0)


class SchedulerAdjustmentResponse(BaseModel):
    """A single audited schedule adjustment ("what changed & why")."""
    id: str
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    task_title: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    action: str = "carried_forward"
    reason: str
    priority_delta: int = Field(0, ge=-5, le=5)


class SchedulerRunResponse(BaseModel):
    """A single scheduler run record."""
    id: str
    user_id: str
    study_plan_id: Optional[str] = None
    trigger_type: str = "midnight"
    run_date: date
    metrics: SchedulerMetrics = Field(default_factory=SchedulerMetrics)
    summary: Optional[str] = None
    created_at: Optional[datetime] = None


class SchedulerRunDetailResponse(SchedulerRunResponse):
    """A scheduler run with its full adjustment history."""
    adjustments: List[SchedulerAdjustmentResponse] = Field(default_factory=list)


class SchedulerExplainResponse(BaseModel):
    """Dry-run preview: what the scheduler WOULD change and why."""
    would_change: bool
    metrics: SchedulerMetrics = Field(default_factory=SchedulerMetrics)
    adjustments: List[SchedulerAdjustmentResponse] = Field(default_factory=list)
    note: str = ""

    @property
    def change_count(self) -> int:
        return self.metrics.adjustment_count

