"""
Pydantic schemas for the Motivation Engine domain.

The Motivation Engine writes personalized, professional, non-repetitive
motivational messages for key student moments. Every message is generated
deterministically from a professional template bank + the student's stored
learner context (profile, streak, missions, assessments, mocks, exam date),
then persisted idempotently per (user, moment, period_key).

Moments:
    mission_complete / missed_day / streak_7 / streak_30 /
    band_improvement / mock_test / exam_week / final_day
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MOTIVATION_MOMENTS = (
    "mission_complete",
    "missed_day",
    "streak_7",
    "streak_30",
    "band_improvement",
    "mock_test",
    "exam_week",
    "final_day",
    "general",
)

MOTIVATION_TONES = ("encouraging", "firm", "celebratory", "calm", "neutral")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class MotivationGenerateRequest(BaseModel):
    """
    Optional body for POST /motivation/{moment}.

    `context` lets callers inject event-specific facts (assessment band, mock
    band, streak length) that the engine would otherwise read from the ledger.
    Provided values take precedence over database reads.
    """

    context: Optional[Dict[str, Any]] = None


class MotivationMessageResponse(BaseModel):
    """A single persisted motivation message."""

    id: str
    user_id: str
    moment: str
    title: str
    body: str
    tone: str
    variant: str = ""
    period_key: str = ""
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class MotivationTodayResponse(BaseModel):
    """
    The message selected for the student today.

    Priority: final_day > exam_week > missed_day > mission_complete > generic.
    `server_date` is the engine's reference date so the client can label the
    message accurately.
    """

    server_date: str
    applied_moment: str
    message: MotivationMessageResponse


class MotivationListResponse(BaseModel):
    """Paginated motivation feed (newest first)."""

    items: List[MotivationMessageResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


class MotivationMomentCount(BaseModel):
    """Message count for a single moment."""

    moment: str
    count: int = 0


class MotivationOverviewResponse(BaseModel):
    """Per-moment totals plus the latest message."""

    total_messages: int = 0
    by_moment: List[MotivationMomentCount] = Field(default_factory=list)
    latest: Optional[MotivationMessageResponse] = None