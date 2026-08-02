"""
Schedule History API endpoints.

Provides comprehensive tracking and comparison of schedule changes:
- GET /api/v1/schedule-history - List history with filters
- GET /api/v1/schedule-history/{history_id} - Get specific history entry
- GET /api/v1/schedule-history/compare/{id1}/{id2} - Compare two history entries
- POST /api/v1/schedule-history - Create history entry (internal)
- PATCH /api/v1/schedule-history/{history_id}/action - Update user action
- GET /api/v1/schedule-history/stats - Get history statistics
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from typing import Optional

from app.api.deps import get_current_user, get_schedule_history_repo, get_schedule_history_service
from app.models.schedule_history import (
    ScheduleHistoryEntry,
    ScheduleHistoryListResponse,
    ScheduleComparisonResponse,
    ScheduleHistoryCreate,
    ScheduleHistoryUpdate,
)
from app.repositories.schedule_history_repo import ScheduleHistoryRepository
from app.services.schedule_history_service import ScheduleHistoryService

router = APIRouter()


@router.get(
    "",
    response_model=ScheduleHistoryListResponse,
    summary="List schedule history with filters",
)
async def list_schedule_history(
    change_type: Optional[str] = Query(None, description="Filter by change type"),
    user_action: Optional[str] = Query(None, description="Filter by user action"),
    study_plan_id: Optional[str] = Query(None, description="Filter by study plan"),
    from_date: Optional[datetime] = Query(None, description="Filter from date"),
    to_date: Optional[datetime] = Query(None, description="Filter to date"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user_id: str = Depends(get_current_user),
    repo: ScheduleHistoryRepository = Depends(get_schedule_history_repo),
):
    """
    Get paginated schedule history for the current user.
    
    Supports filtering by:
    - change_type: scheduler_run, exam_date_update, manual_reschedule, etc.
    - user_action: accepted, rejected, modified, auto_applied
    - study_plan_id: specific study plan
    - Date range: from_date, to_date
    """
    from app.models.schedule_history import ScheduleHistoryFilter
    
    filters = ScheduleHistoryFilter(
        change_type=change_type,
        user_action=user_action,
        study_plan_id=study_plan_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    
    items, total = await repo.list_history(user_id, filters)
    
    return ScheduleHistoryListResponse(
        items=[ScheduleHistoryEntry(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{history_id}",
    response_model=ScheduleHistoryEntry,
    summary="Get specific schedule history entry",
)
async def get_schedule_history(
    history_id: str,
    user_id: str = Depends(get_current_user),
    repo: ScheduleHistoryRepository = Depends(get_schedule_history_repo),
):
    """Get a specific schedule history entry with full details."""
    entry = await repo.get_by_id(history_id, user_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule history entry not found",
        )
    return ScheduleHistoryEntry(**entry)


@router.get(
    "/compare/{history_id_1}/{history_id_2}",
    response_model=ScheduleComparisonResponse,
    summary="Compare two schedule history entries",
)
async def compare_schedule_history(
    history_id_1: str,
    history_id_2: str,
    user_id: str = Depends(get_current_user),
    repo: ScheduleHistoryRepository = Depends(get_schedule_history_repo),
):
    """
    Compare two schedule history entries to see what changed.
    
    Returns detailed comparison including:
    - Tasks added/removed/rescheduled
    - Workload changes
    - Completion rate changes
    """
    comparison = await repo.get_comparison(user_id, history_id_1, history_id_2)
    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both schedule history entries not found",
        )
    return ScheduleComparisonResponse(**comparison)


@router.patch(
    "/{history_id}/action",
    response_model=ScheduleHistoryEntry,
    summary="Update user action on history entry",
)
async def update_user_action(
    history_id: str,
    action_data: ScheduleHistoryUpdate,
    user_id: str = Depends(get_current_user),
    repo: ScheduleHistoryRepository = Depends(get_schedule_history_repo),
):
    """
    Update user action on a schedule history entry.
    
    Actions:
    - accepted: User accepted the schedule changes
    - rejected: User rejected the schedule changes
    - modified: User modified the suggested changes
    - pending: Waiting for user decision
    - auto_applied: Changes were applied automatically
    """
    valid_actions = ["accepted", "rejected", "modified", "pending", "auto_applied"]
    if action_data.user_action not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}",
        )
    
    entry = await repo.update_user_action(
        history_id,
        user_id,
        action_data.user_action,
        action_data.user_action_notes,
    )
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule history entry not found",
        )
    
    return ScheduleHistoryEntry(**entry)


@router.get(
    "/stats/summary",
    response_model=dict,
    summary="Get schedule history statistics",
)
async def get_history_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    user_id: str = Depends(get_current_user),
    repo: ScheduleHistoryRepository = Depends(get_schedule_history_repo),
):
    """Get statistics about schedule changes over the specified period."""
    stats = await repo.get_stats(user_id, days)
    return stats


@router.get(
    "/latest",
    response_model=Optional[ScheduleHistoryEntry],
    summary="Get latest schedule history entry",
)
async def get_latest_history(
    user_id: str = Depends(get_current_user),
    repo: ScheduleHistoryRepository = Depends(get_schedule_history_repo),
):
    """Get the most recent schedule history entry for the user."""
    latest = await repo.get_latest(user_id, limit=1)
    return ScheduleHistoryEntry(**latest[0]) if latest else None


@router.post(
    "/internal/create",
    response_model=ScheduleHistoryEntry,
    summary="Create schedule history entry (internal use)",
    include_in_schema=False,
)
async def create_history_entry(
    request: Request,
    user_id: str = Depends(get_current_user),
    service: ScheduleHistoryService = Depends(get_schedule_history_service),
):
    """
    Internal endpoint for creating schedule history entries.
    Called by the scheduler service, exam countdown service, and
    study plan generator when changes are made.
    """
    body = await request.json()
    create_data = ScheduleHistoryCreate(**body)
    
    entry = await service.history_repo.create_entry(
        user_id=user_id,
        study_plan_id=create_data.study_plan_id,
        run_id=create_data.run_id,
        previous_schedule=create_data.previous_schedule,
        new_schedule=create_data.new_schedule,
        change_reason=create_data.change_reason,
        change_type=create_data.change_type,
        trigger_type=create_data.trigger_type,
        metrics_before=create_data.metrics_before,
        metrics_after=create_data.metrics_after,
        summary=create_data.summary,
        adjustments_count=create_data.adjustments_count,
        tasks_affected=create_data.tasks_affected,
    )
    
    return ScheduleHistoryEntry(**entry)