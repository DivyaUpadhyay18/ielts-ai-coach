"""
Pydantic schemas for the Prediction Engine domain.

All predictions are deterministic — NO AI. Every metric is computed from
stored data (completed tasks, mock test scores, study time, streak, missed
days) using documented formulas. See PREDICTION_ENGINE.md for the full
formula reference.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums / constants
# ---------------------------------------------------------------------------
RISK_LEVELS = ("low", "medium", "high", "critical")
READINESS_LEVELS = ("on_track", "at_risk", "behind", "critical")


# ---------------------------------------------------------------------------
# Sub-blocks
# ---------------------------------------------------------------------------
class PredictionMetrics(BaseModel):
    """The raw input metrics that feed the prediction formulas."""
    total_tasks: int = 0
    completed_tasks: int = 0
    skipped_tasks: int = 0
    completion_rate: float = 0.0  # 0–100
    study_minutes: int = 0
    study_hours: float = 0.0
    daily_streak: int = 0
    longest_streak: int = 0
    missed_days: int = 0
    active_days: int = 0
    total_days_since_start: int = 0
    study_consistency: float = 0.0  # 0–100
    mock_test_count: int = 0
    latest_mock_band: Optional[float] = None
    average_mock_band: Optional[float] = None
    days_remaining: int = 0


class PredictionResponse(BaseModel):
    """Full prediction payload returned by GET /prediction."""
    user_id: str
    generated_at: datetime
    run_date: str

    # Core estimates
    preparation_percentage: float  # 0–100
    estimated_band: float  # 0.0–9.0 in 0.5 steps
    study_consistency: float  # 0–100
    completion_rate: float  # 0–100
    risk_level: str  # low | medium | high | critical
    readiness_score: float  # 0–100

    # Supporting context
    current_band: Optional[float] = None
    target_band: Optional[float] = None
    days_remaining: int = 0
    intensity: str = "normal"  # normal | focused | intensive | final

    # Raw metrics (for transparency)
    metrics: PredictionMetrics

    # Human-readable explanation of how each metric was derived
    formulas: Dict[str, str] = Field(default_factory=dict)

    # Actionable recommendations
    recommendations: List[str] = Field(default_factory=list)


class PredictionHistoryItem(BaseModel):
    """A single historical prediction snapshot."""
    id: str
    user_id: str
    run_date: str
    generated_at: datetime
    preparation_percentage: float
    estimated_band: float
    study_consistency: float
    completion_rate: float
    risk_level: str
    readiness_score: float
    metrics_json: Dict[str, Any] = Field(default_factory=dict)


class PredictionHistoryResponse(BaseModel):
    """Paginated list of historical predictions."""
    items: List[PredictionHistoryItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0
