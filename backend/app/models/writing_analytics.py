"""
Pydantic schemas for the Writing Progress Analytics API.

Every endpoint in ``app/api/v1/writing_analytics.py`` returns one of the
schemas defined here.  The schemas mirror the four official IELTS Writing
criteria and the analytics concepts requested by the product:

  - Writing Band History  (chronological overall-band trajectory)
  - Task 1 History        (Task 1 band trajectory)
  - Task 2 History        (Task 2 band trajectory)
  - Task Response / Coherence & Cohesion / Lexical Resource / Grammar
                          (per-criterion breakdown over time)
  - Average Word Count
  - Average Writing Time
  - Common Errors         (aggregated error-type frequency)
  - Improvement Rate      (linear-regression slope of band vs. order)
  - Strongest / Weakest Criterion
  - Trends                (chart data series)
  - Essays                (every submitted essay, with evaluation status)
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Criterion metadata
# ─────────────────────────────────────────────────────────────────────────────
# The four official IELTS Writing criteria, in display order.
CRITERION_KEYS = (
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammatical_range_accuracy",
)

# Human-readable labels for each criterion key.
CRITERION_LABELS: Dict[str, str] = {
    "task_response": "Task Response",
    "coherence_cohesion": "Coherence and Cohesion",
    "lexical_resource": "Lexical Resource",
    "grammatical_range_accuracy": "Grammatical Range and Accuracy",
}

# Friendly short names used in the UI.
CRITERION_SHORT_LABELS: Dict[str, str] = {
    "task_response": "Task Response",
    "coherence_cohesion": "Coherence & Cohesion",
    "lexical_resource": "Lexical Resource",
    "grammatical_range_accuracy": "Grammar",
}


# ─────────────────────────────────────────────────────────────────────────────
# Band history
# ─────────────────────────────────────────────────────────────────────────────
class WritingBandHistoryPoint(BaseModel):
    """One point in the chronological band history series."""

    submission_id: str
    date: str  # ISO date (created_at truncated to day)
    overall_band: Optional[float] = None
    task_type: str  # "task_1" | "task_2"
    confidence: Optional[float] = None
    word_count: int = 0
    title: Optional[str] = None
    is_estimate: bool = True


class WritingBandHistoryResponse(BaseModel):
    """Chronological overall-band history for all evaluated essays."""

    task_type: Optional[str] = None  # filter applied (None = both)
    total_essays: int
    points: List[WritingBandHistoryPoint] = []
    averages: Dict[str, Any] = Field(
        default_factory=lambda: {
            "overall_band": 0.0,
            "task1_band": 0.0,
            "task2_band": 0.0,
            "word_count": 0.0,
        }
    )
    trend: Optional[str] = None  # "improving" | "declining" | "stable" | None

# ─────────────────────────────────────────────────────────────────────────────
# Per-criterion breakdown (Task Response, C&C, LR, GRA)
# ─────────────────────────────────────────────────────────────────────────────
class CriterionHistoryPoint(BaseModel):
    """One point in a single criterion's band-history series."""

    date: str
    band: float
    label: str


class CriterionHistoryResponse(BaseModel):
    """Band history for a single criterion across all evaluated essays."""

    criterion: str
    label: str
    points: List[CriterionHistoryPoint] = []
    average_band: float = 0.0
    latest_band: Optional[float] = None


class CriterionBreakdownItem(BaseModel):
    """Average band per criterion, with latest score and trend."""

    criterion: str
    label: str
    average_band: float = 0.0
    latest_band: Optional[float] = None
    best_band: float = 0.0
    worst_band: float = 0.0
    submissions_count: int = 0
    trend: Optional[str] = None  # "improving" | "declining" | "stable"


class CriterionBreakdownResponse(BaseModel):
    """Per-criterion average, best, worst and trend across evaluated essays."""

    task_type: Optional[str] = None
    criteria: List[CriterionBreakdownItem] = []


# ─────────────────────────────────────────────────────────────────────────────
# Common errors (aggregated error-type frequency)
# ─────────────────────────────────────────────────────────────────────────────
class CommonError(BaseModel):
    """An aggregated error type with frequency and severity distribution."""

    error_type: str  # e.g. "Grammar", "Vocabulary", "Spelling"
    criterion: str  # which IELTS criterion it affects
    count: int
    percentage: float  # count / total_errors * 100
    severity_breakdown: Dict[str, int] = Field(
        default_factory=lambda: {"critical": 0, "major": 0, "minor": 0}
    )
    top_examples: List[str] = []


class CommonErrorsResponse(BaseModel):
    """Aggregated common errors across all evaluated essays."""

    total_errors: int
    total_unique_types: int
    limit: int
    errors: List[CommonError] = []
# ─────────────────────────────────────────────────────────────────────────────
# Writing metrics (averages)
# ─────────────────────────────────────────────────────────────────────────────
class WritingMetricsResponse(BaseModel):
    """Aggregate metrics: average band, word count, writing time, etc."""

    task_type: Optional[str] = None
    total_essays: int = 0
    evaluated_essays: int = 0
    average_band: Optional[float] = None
    average_word_count: float = 0.0
    average_writing_time_seconds: float = 0.0
    average_writing_time_minutes: float = 0.0
    average_confidence: Optional[float] = None
    average_task1_band: Optional[float] = None
    average_task2_band: Optional[float] = None
    total_word_count: int = 0
    total_writing_time_seconds: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Improvement rate
# ─────────────────────────────────────────────────────────────────────────────
class WritingImprovementRateResponse(BaseModel):
    """Linear-regression slope of overall_band vs. submission order."""

    task_type: Optional[str] = None
    total_essays: int = 0
    slope: float = 0.0  # band points per essay
    direction: str  # "improving" | "declining" | "stable"
    description: str
    band_change: float  # latest_band - first_band
    first_band: Optional[float] = None
    latest_band: Optional[float] = None
    r_squared: float = 0.0  # goodness of fit (0–1)


# ─────────────────────────────────────────────────────────────────────────────
# Strongest / weakest criterion
# ─────────────────────────────────────────────────────────────────────────────
class CriterionSummary(BaseModel):
    """A single criterion's aggregate summary for strongest/weakest comparison."""

    criterion: str
    label: str
    short_label: str
    average_band: float = 0.0
    latest_band: Optional[float] = None
    best_band: float = 0.0
    submissions_count: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Trends (chart data series)
# ─────────────────────────────────────────────────────────────────────────────
class WritingTrendPoint(BaseModel):
    """One data point in a trend series."""

    date: str
    label: str
    band: Optional[float] = None
    word_count: Optional[float] = None
    writing_time_minutes: Optional[float] = None
    essay_count: int = 0


class WritingTrendsResponse(BaseModel):
    """Trend series for charts (daily buckets over the requested window)."""

    days: int
    points: List[WritingTrendPoint] = []
    series: List[str] = Field(
        default_factory=lambda: [
            "band",
            "word_count",
            "writing_time_minutes",
        ]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Essays (every submitted essay)
# ─────────────────────────────────────────────────────────────────────────────
class EssayCriterionBand(BaseModel):
    """A single criterion band within an essay record."""

    key: str
    label: str
    band: float


class WritingEssayRecord(BaseModel):
    """A single submitted essay with its evaluation status and scores."""

    id: str  # submission_id
    evaluation_id: Optional[str] = None
    title: Optional[str] = None
    prompt_text: Optional[str] = None
    task_type: str
    task_label: str
    word_count: int = 0
    time_seconds_spent: int = 0
    status: str  # "draft" | "submitted"
    evaluation_status: str  # "pending" | "evaluated"
    overall_band: Optional[float] = None
    confidence: Optional[float] = None
    is_estimate: bool = True
    criteria: List[EssayCriterionBand] = []
    strengths: List[str] = []
    weaknesses: List[str] = []
    error_count: int = 0
    submitted_at: Optional[str] = None
    evaluated_at: Optional[str] = None
    created_at: Optional[str] = None


class WritingEssaysResponse(BaseModel):
    """Paginated list of every submitted essay."""

    results: List[WritingEssayRecord] = []
    total: int
    limit: int
    offset: int
# ─────────────────────────────────────────────────────────────────────────────
# Band improvement report (current vs. target criteria comparison)
# ─────────────────────────────────────────────────────────────────────────────
class CriterionImprovement(BaseModel):
    """Per-criterion band improvement comparison (current vs. target)."""

    criterion: str  # e.g. "task_response"
    label: str  # e.g. "Task Response" or "Grammar"
    current_band: float
    target_band: float
    change: float  # target_band - current_band
    direction: str  # "improving" | "maintained" | "declining"
    reason: str  # concise reason for the change


class BandImprovementReportResponse(BaseModel):
    """Band improvement report comparing current criterion bands to target bands."""

    user_id: str
    generated_at: str
    current_band: float
    target_band: float
    overall_improvement: float  # target_band - current_band
    task_type: Optional[str] = None
    total_evaluated_essays: int = 0
    criteria: List[CriterionImprovement] = []
    biggest_improvement: Optional[CriterionImprovement] = None


# ─────────────────────────────────────────────────────────────────────────────
# Comprehensive dashboard payload
# ─────────────────────────────────────────────────────────────────────────────
class WritingAnalyticsDashboardResponse(BaseModel):
    """Full Writing Progress Analytics dashboard payload.

    Aggregates every metric requested by the product into a single
    response so the frontend can render the complete analytics view
    with one API call.
    """

    user_id: str
    generated_at: str
    task_type: Optional[str] = None  # filter applied
    days: int

    # Summary metrics
    summary: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_essays": 0,
            "evaluated_essays": 0,
            "average_band": 0.0,
            "average_word_count": 0.0,
            "average_writing_time_seconds": 0.0,
            "average_writing_time_minutes": 0.0,
            "average_confidence": 0.0,
            "improvement_rate": 0.0,
            "improvement_direction": None,
            "strongest_criterion": None,
            "weakest_criterion": None,
        }
    )

    # Band history (all evaluated essays, chronological)
    band_history: List[WritingBandHistoryPoint] = []

    # Task 1 & Task 2 histories
    task1_history: List[WritingBandHistoryPoint] = []
    task2_history: List[WritingBandHistoryPoint] = []

    # Per-criterion breakdown
    criterion_breakdown: List[CriterionBreakdownItem] = []

    # Individual criterion histories (for charts)
    criterion_histories: List[CriterionHistoryResponse] = []

    # Common errors
    common_errors: List[CommonError] = []

    # Trend series for charts
    trends: List[WritingTrendPoint] = []

    # All essays
    essays: List[WritingEssayRecord] = []
    total_essays: int = 0

    # Metrics
    metrics: WritingMetricsResponse
    metrics_task1: WritingMetricsResponse
    metrics_task2: WritingMetricsResponse

    # Improvement rate
    improvement_rate: WritingImprovementRateResponse
    improvement_rate_task1: WritingImprovementRateResponse
    improvement_rate_task2: WritingImprovementRateResponse

    # Strongest & weakest criteria
    strongest_criterion: CriterionSummary
    weakest_criterion: CriterionSummary
