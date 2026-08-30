"""
Weekly AI Reports API endpoints.

GET  /api/v1/weekly-reports          — get latest weekly report (generated if missing)
GET  /api/v1/weekly-reports/history    — get paginated history
GET  /api/v1/weekly-reports/{week_start} — get a specific week's report

Reports are deterministic (NO AI) and aggregate data from:
  - Diagnostic / Band Estimation (weakest/strongest skill, current band)
  - Progress Tracking (study hours, tasks completed)
  - Streak System (daily streak, consistency, perfect days)
  - Prediction Engine (estimated band)
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.models.weekly_report import WeeklyReportResponse, WeeklyReportHistoryResponse
from app.services.weekly_report_service import WeeklyReportService, weekly_report_service

router = APIRouter()


def get_weekly_report_service() -> WeeklyReportService:
    return weekly_report_service


@router.get(
    "",
    response_model=WeeklyReportResponse,
    summary="Get or generate the current week's AI report",
)
async def get_latest_weekly_report(
    force_regenerate: bool = Query(False, description="Force regenerate even if a report exists"),
    user_id: str = Depends(get_current_user),
    service: WeeklyReportService = Depends(get_weekly_report_service),
):
    """
    Fetch the latest weekly AI report for the current week.

    If no report exists for the current week, one is generated on-demand
    from the user's live study data.
    """
    today = date.today()
    return service.generate_report(user_id, run_date=today, force_regenerate=force_regenerate)


@router.get(
    "/history",
    response_model=WeeklyReportHistoryResponse,
    summary="Get weekly report history",
)
async def get_weekly_report_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: WeeklyReportService = Depends(get_weekly_report_service),
):
    """Return paginated history of previously generated weekly reports."""
    return service.get_history(user_id, limit=limit, offset=offset)


@router.get(
    "/{week_start}",
    response_model=WeeklyReportResponse,
    summary="Get a specific week's report",
)
async def get_weekly_report_by_date(
    week_start: str,
    force_regenerate: bool = Query(False, description="Force regenerate even if a report exists"),
    user_id: str = Depends(get_current_user),
    service: WeeklyReportService = Depends(get_weekly_report_service),
):
    """
    Fetch a weekly report for the week containing the given date.

    `week_start` is an ISO date (YYYY-MM-DD). The service resolves it to
    the Monday of that week.
    """
    try:
        parsed = date.fromisoformat(week_start[:10])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="week_start must be a valid ISO date (YYYY-MM-DD)",
        )

    return service.generate_report(user_id, run_date=parsed, force_regenerate=force_regenerate)
