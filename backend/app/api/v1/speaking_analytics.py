"""
Speaking Progress Analytics API endpoints.

Exposes Speaking Progress Analytics:

  - GET /api/v1/speaking-analytics/dashboard            → comprehensive dashboard
  - GET /api/v1/speaking-analytics/band-history         → Speaking Band History
  - GET /api/v1/speaking-analytics/criterion-history    → per-criterion band history
  - GET /api/v1/speaking-analytics/metrics              → aggregate metrics
  - GET /api/v1/speaking-analytics/common-errors        → Common Grammar/Vocabulary Errors
  - GET /api/v1/speaking-analytics/strongest-criterion  → Strongest Criterion
  - GET /api/v1/speaking-analytics/weakest-criterion    → Weakest Criterion
  - GET /api/v1/speaking-analytics/improvement-rate     → Improvement Rate
  - GET /api/v1/speaking-analytics/attempt-history      → Attempt History

All endpoints read real stored evaluation & session data (never client-fabricated).
All numbers are computed deterministically by the SpeakingAnalyticsService.

Integration:
  - Dashboard           → single comprehensive payload for /analytics page
  - AI Mentor           → weaknesses_summary() feeds mentor context
  - Readiness Score     → get_readiness_factors() provides band + trend
  - Band Prediction     → get_prediction_features() provides regression inputs
  - Adaptive Scheduler  → strongest/weakest criteria drive exercise selection
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_speaking_analytics_service
from app.models.speaking_test import (
    SpeakingAnalyticsDashboardResponse,
    SpeakingAttemptHistoryResponse,
    SpeakingBandHistoryResponse,
    SpeakingCommonErrorsResponse,
    SpeakingCriterionHistoryResponse,
    SpeakingImprovementRateResponse,
    SpeakingMetricsResponse,
)
from app.services.speaking_analytics_service import SpeakingAnalyticsService


router = APIRouter()


def _service() -> SpeakingAnalyticsService:
    return get_speaking_analytics_service()


@router.get(
    "/dashboard",
    response_model=SpeakingAnalyticsDashboardResponse,
    summary="Get the full Speaking Progress Analytics dashboard",
)
def get_dashboard(
    days: int = Query(90, ge=7, le=365),
    part: Optional[str] = Query(None, pattern="^(part_1|part_2|part_3)?$"),
    user_id: str = Depends(get_current_user),
    service: SpeakingAnalyticsService = Depends(_service),
):
    """Return the full Speaking Progress Analytics dashboard in one payload."""
    data = service.get_dashboard(user_id, days, part)
    return data


@router.get(
    "/band-history",
    response_model=SpeakingBandHistoryResponse,
    summary="Speaking Band History (chronological)",
)
def get_band_history(
    days: int = Query(90, ge=7, le=365),
    part: Optional[str] = Query(None, pattern="^(part_1|part_2|part_3)?$"),
    user_id: str = Depends(get_current_user),
    service: SpeakingAnalyticsService = Depends(_service),
):
    """Return chronological speaking band history (overall + per-criterion)."""
    return service.band_history(user_id, days, part)


@router.get(
    "/criterion-history",
    response_model=SpeakingCriterionHistoryResponse,
    summary="Per-criterion band history",
)
def get_criterion_history(
    criterion: str = Query("overall", pattern="^(overall|fluency_coherence|lexical_resource|grammatical_range|pronunciation)$"),
    days: int = Query(90, ge=7, le=365),
    part: Optional[str] = Query(None, pattern="^(part_1|part_2|part_3)?$"),
    user_id: str = Depends(get_current_user),
    service: SpeakingAnalyticsService = Depends(_service),
):
    """Return band history for a single criterion."""
    return service.criterion_history(user_id, criterion, days, part)


@router.get(
    "/metrics",
    response_model=SpeakingMetricsResponse,
    summary="Speaking aggregate metrics",
)
def get_metrics(
    days: int = Query(90, ge=7, le=365),
    part: Optional[str] = Query(None, pattern="^(part_1|part_2|part_3)?$"),
    user_id: str = Depends(get_current_user),
    service: SpeakingAnalyticsService = Depends(_service),
):
    """Return aggregate speaking metrics (averages, strongest/weakest, duration, fillers)."""
    return service.metrics(user_id, days, part)


@router.get(
    "/common-errors",
    response_model=SpeakingCommonErrorsResponse,
    summary="Common grammar and vocabulary errors",
)
def get_common_errors(
    days: int = Query(90, ge=7, le=365),
    user_id: str = Depends(get_current_user),
    service: SpeakingAnalyticsService = Depends(_service),
):
    """Return aggregated common grammar and vocabulary errors from error analysis."""
    return service.common_errors(user_id, days)


@router.get(
    "/strongest-criterion",
    summary="Strongest speaking criterion",
)
def get_strongest_criterion(
    days: int = Query(90, ge=7, le=365),
    part: Optional[str] = Query(None, pattern="^(part_1|part_2|part_3)?$"),
    user_id: str = Depends(get_current_user),
    service: SpeakingAnalyticsService = Depends(_service),
):
    """Return the user's strongest speaking criterion."""
    return service.strongest_criterion(user_id, days, part)


@router.get(
    "/weakest-criterion",
    summary="Weakest speaking criterion",
)
def get_weakest_criterion(
    days: int = Query(90, ge=7, le=365),
    part: Optional[str] = Query(None, pattern="^(part_1|part_2|part_3)?$"),
    user_id: str = Depends(get_current_user),
    service: SpeakingAnalyticsService = Depends(_service),
):
    """Return the user's weakest speaking criterion."""
    return service.weakest_criterion(user_id, days, part)


@router.get(
    "/improvement-rate",
    response_model=SpeakingImprovementRateResponse,
    summary="Speaking improvement rate (slope of band vs. order)",
)
def get_improvement_rate(
    criterion: str = Query("overall", pattern="^(overall|fluency_coherence|lexical_resource|grammatical_range|pronunciation)$"),
    days: int = Query(90, ge=7, le=365),
    part: Optional[str] = Query(None, pattern="^(part_1|part_2|part_3)?$"),
    user_id: str = Depends(get_current_user),
    service: SpeakingAnalyticsService = Depends(_service),
):
    """Compute the improvement rate (linear regression slope) for a criterion."""
    return service.improvement_rate(user_id, days, criterion, part)


@router.get(
    "/attempt-history",
    response_model=SpeakingAttemptHistoryResponse,
    summary="Speaking attempt history",
)
def get_attempt_history(
    days: int = Query(90, ge=7, le=365),
    user_id: str = Depends(get_current_user),
    service: SpeakingAnalyticsService = Depends(_service),
):
    """Return full attempt history with durations, errors, and fillers."""
    return service.attempt_history(user_id, days)
