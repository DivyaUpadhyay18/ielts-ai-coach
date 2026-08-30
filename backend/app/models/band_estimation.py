"""
Pydantic schemas for the Band Estimation Engine domain.

Deterministic (NO AI) engine that maps a user's skill-wise band scores
(reading, listening, writing, speaking, vocabulary, grammar) to:

  - Estimated Overall Band        (IELTS standard: mean of 4 skills, 0.5 steps)
  - Skill-wise Band               (per-skill, rounded to 0.5)
  - Confidence Score              (0–100 from dispersion + completeness)
  - Weakest Skills                (ascending)
  - Strongest Skills              (descending)
  - Explanations                  (why each score was assigned)
  - Stored results                (band_estimations history)

See BAND_ESTIMATION.md for the full formula reference.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# The 4 skills that officially make up the IELTS overall band.
OVERALL_SKILLS = ("reading", "listening", "writing", "speaking")

# All skills the engine accepts as input (the two extras are supporting /
# diagnostic inputs that influence explanations but not the overall average).
ALL_SKILLS = ("reading", "listening", "writing", "speaking", "vocabulary", "grammar")

# Confidence labels.
CONFIDENCE_LABELS = ("low", "medium", "high", "very_high")


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------
class BandEstimationInput(BaseModel):
    """Input to the band estimation engine — six skill-wise band scores (0–9)."""
    reading: float = Field(..., ge=0.0, le=9.0)
    listening: float = Field(..., ge=0.0, le=9.0)
    writing: float = Field(..., ge=0.0, le=9.0)
    speaking: float = Field(..., ge=0.0, le=9.0)
    vocabulary: float = Field(..., ge=0.0, le=9.0)
    grammar: float = Field(..., ge=0.0, le=9.0)

    @field_validator(
        "reading", "listening", "writing", "speaking", "vocabulary", "grammar"
    )
    @classmethod
    def _round_input(cls, v: float) -> float:
        """Round each input to the nearest 0.5 (IELTS band step)."""
        return round(v * 2) / 2


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------
class SkillBand(BaseModel):
    """A single skill's estimated band plus a human-readable explanation."""
    skill: str
    band: float  # 0.0–9.0 in 0.5 steps
    explanation: str


class BandEstimationResponse(BaseModel):
    """Full band estimation payload returned by the engine."""
    user_id: str
    generated_at: datetime
    run_date: str

    # Core outputs
    overall_band: float  # 0.0–9.0 in 0.5 steps
    confidence_score: float  # 0–100
    confidence_label: str  # low | medium | high | very_high

    # Skill-wise bands: {skill: band}
    skill_bands: Dict[str, float] = Field(default_factory=dict)

    # Weakest skills (ascending band order, then name)
    weakest_skills: List[str] = Field(default_factory=list)

    # Strongest skills (descending band order, then name)
    strongest_skills: List[str] = Field(default_factory=list)

    # Per-skill explanations: {skill: explanation_text}
    explanations: Dict[str, str] = Field(default_factory=dict)

    # Human-readable formula documentation
    formulas: Dict[str, str] = Field(default_factory=dict)

    # Raw input snapshot
    raw_input: Dict[str, float] = Field(default_factory=dict)


class BandEstimationHistoryItem(BaseModel):
    """A single historical band estimation snapshot."""
    id: str
    user_id: str
    run_date: str
    generated_at: datetime
    created_at: Optional[datetime] = None
    overall_band: float
    confidence_score: float
    confidence_label: str
    skill_bands: Dict[str, float] = Field(default_factory=dict)
    weakest_skills: List[str] = Field(default_factory=list)
    strongest_skills: List[str] = Field(default_factory=list)
    explanations: Dict[str, str] = Field(default_factory=dict)
    raw_input: Dict[str, Any] = Field(default_factory=dict)


class BandEstimationHistoryResponse(BaseModel):
    """Paginated list of historical band estimations."""
    items: List[BandEstimationHistoryItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0
