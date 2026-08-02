"""
Adaptive Scheduler endpoints.

Exposes the deterministic rollover engine:
  POST /api/v1/scheduler/run     — execute a rollover (midnight / app_open / manual)
  GET  /api/v1/scheduler/latest  — most recent run + its adjustments
  GET  /api/v1/scheduler/runs    — paginated run history
  GET  /api/v1/scheduler/explain — dry-run preview (nothing written)
  GET  /api/v1/scheduler/runs/{run_id} — a single run + its adjustments
"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from typing import Dict, List, Optional

from app.api.deps import (
    get_current_user,
    get_scheduler_repo,
    get_scheduler_service,
)
from app.models.scheduler import (
    SchedulerAdjustmentResponse,
    SchedulerExplainResponse,
    SchedulerMetrics,
    SchedulerRunDetailResponse,
    SchedulerRunResponse,
)
from app.repositories.scheduler_repo import SchedulerRepository
from app.services.adaptive_scheduler import AdaptiveSchedulerService

router = APIRouter()


@router.post(
    "/run",
    response_model=dict,
    summary="Run the adaptive scheduler",
)
async def run_scheduler(
    trigger_type: str = Query("app_open", pattern="^(midnight|app_open|manual)$"),
    run_date: Optional[date] = Query(None, description="Simulate a run for a specific date"),
    user_id: str = Depends(get_current_user),
    scheduler: AdaptiveSchedulerService = Depends(get_scheduler_service),
):
    """
    Execute a deterministic scheduler rollover for the current user.

    Detects missed/overdue tasks, carries them forward (preserving protection
    windows), recalculates daily workload within safe limits, and persists a
    full audit trail of every change plus a human-readable summary.
    """
    return scheduler.run(
        user_id,
        trigger_type=trigger_type,
        run_date=run_date,
        persist=True,
    )


@router.get(
    "/latest",
    response_model=dict,
    summary="Get the latest scheduler run",
)
async def get_latest_run(
    user_id: str = Depends(get_current_user),
    scheduler: AdaptiveSchedulerService = Depends(get_scheduler_service),
):
    """Fetch the most recent persisted scheduler run with its adjustments."""
    latest = scheduler.get_latest(user_id)
    if latest is None:
        return {
            "run": None,
            "metrics": SchedulerMetrics().model_dump(),
            "adjustments": [],
            "summary": "No scheduler runs yet.",
        }
    return latest


@router.get(
    "/runs",
    response_model=List[dict],
    summary="List scheduler run history",
)
async def list_runs(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    scheduler: AdaptiveSchedulerService = Depends(get_scheduler_service),
):
    """List the user's scheduler run history, newest first."""
    return scheduler.list_runs(user_id, limit=limit)


@router.get(
    "/runs/{run_id}",
    response_model=dict,
    summary="Get a scheduler run with adjustments",
)
async def get_run_detail(
    run_id: str,
    user_id: str = Depends(get_current_user),
    scheduler: AdaptiveSchedulerService = Depends(get_scheduler_service),
):
    """Fetch a single scheduler run with its full adjustment history."""
    return scheduler.get_run_detail(run_id, user_id)


@router.get(
    "/explain",
    response_model=dict,
    summary="Dry-run: preview what the scheduler would change",
)
async def explain_scheduler(
    run_date: Optional[date] = Query(None),
    user_id: str = Depends(get_current_user),
    scheduler: AdaptiveSchedulerService = Depends(get_scheduler_service),
):
    """
    Preview what the scheduler WOULD change without writing anything.

    Returns the same metrics/adjustments shape as a real run but with
    `would_change` and a note that nothing was persisted.
    """
    return scheduler.explain(user_id, run_date=run_date)

