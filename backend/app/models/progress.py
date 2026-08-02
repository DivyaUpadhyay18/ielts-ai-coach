"""
Pydantic schemas for the Progress domain entity.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.models.user import validate_band

PROGRESS_SOURCE_TYPES = ("diagnostic", "assessment", "mock_test")
PROGRESS_CRITERIA = (
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammar",
    "fluency_coherence",
    "pronunciation",
    "listening",
    "reading",
    "overall",
)


class ProgressCreate(BaseModel):
    """Schema for creating a progress record."""
    source_type: str = Field(..., pattern="^(diagnostic|assessment|mock_test)$")
    source_id: Optional[str] = None
    criterion: str = Field(
        ...,
        pattern="^(task_response|coherence_cohesion|lexical_resource|grammar|fluency_coherence|pronunciation|listening|reading|overall)$",
    )
    band_score: float = Field(..., ge=0, le=9)
    recorded_at: Optional[datetime] = None

    @field_validator("band_score")
    @classmethod
    def validate_band_step(cls, v: float) -> float:
        return validate_band(v, "band_score")


class ProgressUpdate(BaseModel):
    """Schema for partial update of a progress record."""
    band_score: Optional[float] = Field(None, ge=0, le=9)

    @field_validator("band_score")
    @classmethod
    def validate_band_step(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        return validate_band(v, "band_score")


class ProgressResponse(BaseModel):
    """Schema for a progress record response."""
    id: str
    user_id: str
    source_type: str
    source_id: Optional[str] = None
    criterion: str
    band_score: float
    recorded_at: Optional[datetime] = None


class ProgressTimelinePoint(BaseModel):
    """A single point on a band-score timeline."""
    recorded_at: datetime
    criterion: str
    band_score: float


class SkillGap(BaseModel):
    """Current vs target score for a criterion."""
    criterion: str
    label: str
    current: Optional[float] = None
    target: Optional[float] = None
    gap: Optional[float] = None
    last_assessment_date: Optional[datetime] = None

