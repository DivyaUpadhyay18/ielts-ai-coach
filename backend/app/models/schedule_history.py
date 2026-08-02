"""
Pydantic schemas for Schedule History domain.

Tracks all changes to study schedules with full audit trail:
- Previous and new schedule snapshots
- Change reasons and types
- User actions and timestamps
- Metrics before/after changes
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScheduleHistoryEntry(BaseModel):
    """A single schedule history entry."""
    id: str
    user_id: str
    study_plan_id: Optional[str] = None
    run_id: Optional[str] = None
    
    # Schedule snapshots
    previous_schedule: Dict[str, Any] = Field(default_factory=dict)
    new_schedule: Dict[str, Any] = Field(default_factory=dict)
    
    # Change metadata
    change_reason: str
    change_type: str = "scheduler_run"
    
    # Trigger information
    trigger_type: Optional[str] = None
    
    # User action tracking
    user_action: Optional[str] = None
    user_action_at: Optional[datetime] = None
    user_action_notes: Optional[str] = None
    
    # Metrics snapshot
    metrics_before: Dict[str, Any] = Field(default_factory=dict)
    metrics_after: Dict[str, Any] = Field(default_factory=dict)
    
    # Summary and metadata
    summary: Optional[str] = None
    adjustments_count: int = 0
    tasks_affected: int = 0
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScheduleHistoryListResponse(BaseModel):
    """Paginated list of schedule history entries."""
    items: List[ScheduleHistoryEntry]
    total: int
    limit: int
    offset: int


class ScheduleComparisonResponse(BaseModel):
    """Comparison between two schedule history entries."""
    history_1_id: str
    history_2_id: str
    history_1_date: datetime
    history_2_date: datetime
    history_1_change_type: str
    history_2_change_type: str
    tasks_added: int
    tasks_removed: int
    tasks_rescheduled: int
    workload_change_minutes: int
    completion_rate_change: float


class ScheduleHistoryCreate(BaseModel):
    """Request to create a schedule history entry."""
    study_plan_id: Optional[str] = None
    run_id: Optional[str] = None
    previous_schedule: Dict[str, Any]
    new_schedule: Dict[str, Any]
    change_reason: str
    change_type: str = "scheduler_run"
    trigger_type: Optional[str] = None
    metrics_before: Dict[str, Any] = Field(default_factory=dict)
    metrics_after: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None
    adjustments_count: int = 0
    tasks_affected: int = 0


class ScheduleHistoryUpdate(BaseModel):
    """Request to update a schedule history entry (e.g., user action)."""
    user_action: str
    user_action_notes: Optional[str] = None


class ScheduleHistoryFilter(BaseModel):
    """Filters for querying schedule history."""
    change_type: Optional[str] = None
    user_action: Optional[str] = None
    study_plan_id: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)