"""
Writing Progress Analytics API endpoints.

Exposes the Writing Progress Analytics feature:

  - GET /api/v1/writing-analytics/dashboard           → single comprehensive payload
  - GET /api/v1/writing-analytics/band-history        → Writing Band History
  - GET /api/v1/writing-analytics/task1-history       → Task 1 History
  - GET /api/v1/writing-analytics/task2-history       → Task 2 History
  - GET /api/v1/writing-analytics/criterion-breakdown → Task Response / C&C / LR / Grammar
  - GET /api/v1/writing-analytics/criterion-history   → one criterion's band history
  - GET /api/v1/writing-analytics/common-errors       → Common Errors
  - GET /api/v1/writing-analytics/metrics             → average band / word count / writing time
  - GET /api/v1/writing-analytics/improvement-rate    → Improvement Rate
  - GET /api/v1/writing-analytics/strongest-criterion → Strongest Criterion
  - GET /api/v1/writing-analytics/weakest-criterion   → Weakest Criterion
  - GET /api/v1/writing-analytics/trends              → chart trend series
  - GET /api/v1/writing-analytics/essays              → every submitted essay
  - GET /api/v1/writing-analytics/improvement-report  → Band improvement report

All endpoints read real stored evaluation & submission data (never
client-fabricated).  All numbers are computed deterministically by the
:class:`WritingAnalyticsService`.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_writing_analytics_service
from app.models.writing_analytics import (
    BandImprovementReportResponse,
    CommonErrorsResponse,
    CriterionBreakdownResponse,
    CriterionHistoryResponse,
    WritingAnalyticsDashboardResponse,
    WritingBandHistoryResponse,
    WritingEssaysResponse,
    WritingImprovementRateResponse,
    WritingMetricsResponse,
    WritingTrendsResponse,
)
from app.services.writing_analytics_service import WritingAnalyticsService

router = APIRouter()


def _service() -> WritingAnalyticsService:
    return get_writing_analytics_service()


@router.get(
    "/dashboard",
    response_model=WritingAnalyticsDashboardResponse,
    summary="Get the full Writing Progress Analytics dashboard",
)
def get_dashboard(
    days: int = Query(90, ge=7, le=365),
    task_type: Optional[str] = Query(None, pattern="^(task_1|task_2)?$"),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Return the complete Writing Progress Analytics payload."""
    return service.get_dashboard(user_id, task_type=task_type, days=days)


@router.get(
    "/band-history",
    response_model=WritingBandHistoryResponse,
    summary="Get Writing Band History",
)
def get_band_history(
    days: Optional[int] = Query(None, ge=7, le=365),
    task_type: Optional[str] = Query(None, pattern="^(task_1|task_2)?$"),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Chronological overall-band history for all evaluated essays."""
    return service.get_band_history(user_id, task_type=task_type, days=days)


@router.get(
    "/task1-history",
    response_model=WritingBandHistoryResponse,
    summary="Get Task 1 History",
)
def get_task1_history(
    days: Optional[int] = Query(None, ge=7, le=365),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Band history for Task 1 essays."""
    return service.get_task1_history(user_id, days=days)


@router.get(
    "/task2-history",
    response_model=WritingBandHistoryResponse,
    summary="Get Task 2 History",
)
def get_task2_history(
    days: Optional[int] = Query(None, ge=7, le=365),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Band history for Task 2 essays."""
    return service.get_task2_history(user_id, days=days)


@router.get(
    "/criterion-breakdown",
    response_model=CriterionBreakdownResponse,
    summary="Get per-criterion breakdown",
)
def get_criterion_breakdown(
    days: Optional[int] = Query(None, ge=7, le=365),
    task_type: Optional[str] = Query(None, pattern="^(task_1|task_2)?$"),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Average / latest / best / worst / trend for each IELTS criterion."""
    return service.get_criterion_breakdown(user_id, task_type=task_type, days=days)
@router.get(
    "/criterion-history",
    response_model=CriterionHistoryResponse,
    summary="Get one criterion's band history",
)
def get_criterion_history(
    criterion: str = Query(..., description="criterion key"),
    days: Optional[int] = Query(None, ge=7, le=365),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Band history for a single criterion."""
    return service.get_criterion_history(user_id, criterion, days=days)


@router.get(
    "/common-errors",
    response_model=CommonErrorsResponse,
    summary="Get common errors",
)
def get_common_errors(
    limit: int = Query(10, ge=1, le=30),
    days: Optional[int] = Query(None, ge=7, le=365),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Aggregated error-type frequency across all evaluated essays."""
    return service.get_common_errors(user_id, limit=limit, days=days)


@router.get(
    "/metrics",
    response_model=WritingMetricsResponse,
    summary="Get writing metrics (averages)",
)
def get_metrics(
    days: Optional[int] = Query(None, ge=7, le=365),
    task_type: Optional[str] = Query(None, pattern="^(task_1|task_2)?$"),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Average band, word count, writing time, confidence."""
    return service.get_metrics(user_id, task_type=task_type, days=days)


@router.get(
    "/improvement-rate",
    response_model=WritingImprovementRateResponse,
    summary="Get writing improvement rate",
)
def get_improvement_rate(
    days: Optional[int] = Query(None, ge=7, le=365),
    task_type: Optional[str] = Query(None, pattern="^(task_1|task_2)?$"),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Linear-regression slope of overall band vs. submission order."""
    return service.get_improvement_rate(user_id, task_type=task_type, days=days)


@router.get(
    "/strongest-criterion",
    response_model=dict,
    summary="Get the strongest criterion",
)
def get_strongest_criterion(
    days: Optional[int] = Query(None, ge=7, le=365),
    task_type: Optional[str] = Query(None, pattern="^(task_1|task_2)?$"),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """The criterion with the highest average band."""
    return service.get_strongest_criterion(user_id, task_type=task_type, days=days)


@router.get(
    "/weakest-criterion",
    response_model=dict,
    summary="Get the weakest criterion",
)
def get_weakest_criterion(
    days: Optional[int] = Query(None, ge=7, le=365),
    task_type: Optional[str] = Query(None, pattern="^(task_1|task_2)?$"),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """The criterion with the lowest average band."""
    return service.get_weakest_criterion(user_id, task_type=task_type, days=days)


@router.get(
    "/trends",
    response_model=WritingTrendsResponse,
    summary="Get writing trend series for charts",
)
def get_trends(
    days: int = Query(30, ge=7, le=365),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Daily trend series for band, word count and writing time."""
    return service.get_trends(user_id, days=days)


@router.get(
    "/essays",
    response_model=WritingEssaysResponse,
    summary="Get every submitted essay",
)
def get_essays(
    task_type: Optional[str] = Query(None, pattern="^(task_1|task_2)?$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Every submitted essay (draft + submitted) with evaluation status."""
    return service.get_essays(user_id, task_type=task_type, limit=limit, offset=offset)


@router.get(
    "/improvement-report",
    response_model=BandImprovementReportResponse,
    summary="Get a band improvement report (current vs. target criteria)",
)
def get_band_improvement_report(
    target_band: Optional[float] = Query(
        None, ge=0.0, le=9.0,
        description="Optional target band. If omitted, uses the user's profile target or current+1.0.",
    ),
    days: int = Query(90, ge=7, le=365),
    user_id: str = Depends(get_current_user),
    service: WritingAnalyticsService = Depends(_service),
):
    """Compare the student's current criterion bands against the target criterion
    bands needed to reach their target overall band.

    Returns per-criterion current → target comparisons with directional
    indicators, concise reasons, and the single biggest improvement highlighted.
    """
    return service.get_band_improvement_report(
        user_id, target_band=target_band, days=days
    )