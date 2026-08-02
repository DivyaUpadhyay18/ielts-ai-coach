"""
Pydantic models for onboarding and placeholder roadmap.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date, datetime

# Allowed IELTS band values (step 0.5)
ALLOWED_BANDS = {0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9}

SKILLS = [
    "writing",
    "speaking",
    "reading",
    "listening",
    "vocabulary",
    "grammar",
    "pronunciation",
    "coherence",
]


class OnboardingData(BaseModel):
    """Schema for onboarding form submission."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=64)
    module: str = Field("academic", pattern="^(academic|general)$")
    current_band: float = Field(..., ge=0, le=9)
    target_band: float = Field(..., ge=0, le=9)
    exam_date: date
    daily_minutes_budget: int = Field(60, ge=15, le=480)
    preferred_study_time: Optional[str] = Field(
        None, pattern="^(morning|afternoon|evening|night|anytime)$"
    )
    weakest_skill: List[str] = Field(default_factory=list)
    strongest_skill: List[str] = Field(default_factory=list)
    previous_ielts_attempt: bool = False

    @field_validator("current_band", "target_band")
    @classmethod
    def validate_band(cls, v: float) -> float:
        """Ensure band score is a valid 0.5-step value between 0 and 9."""
        if v not in ALLOWED_BANDS:
            raise ValueError("Band score must be a valid IELTS band (0.0–9.0 in 0.5 steps)")
        return v

    @field_validator("target_band")
    @classmethod
    def target_above_current(cls, v: float, info) -> float:
        """Target band must be >= current band."""
        current = info.data.get("current_band")
        if current is not None and v < current:
            raise ValueError("Target band must be greater than or equal to current band")
        return v

    @field_validator("exam_date")
    @classmethod
    def exam_date_in_future(cls, v: date) -> date:
        """Exam date must be in the future."""
        if v <= date.today():
            raise ValueError("Exam date must be in the future")
        return v

    @field_validator("weakest_skill", "strongest_skill")
    @classmethod
    def validate_skills(cls, v: List[str]) -> List[str]:
        """Validate skill names."""
        normalized = [s.lower().strip() for s in v]
        for skill in normalized:
            if skill not in SKILLS:
                raise ValueError(f"Unknown skill: {skill}")
        return normalized


class OnboardingStatus(BaseModel):
    """Schema for onboarding status response."""
    is_onboarding_complete: bool
    onboarded_at: Optional[datetime] = None
    has_roadmap: bool = False


class RoadmapTask(BaseModel):
    """A single task within a roadmap phase."""
    id: str = ""
    title: str
    skill: str
    duration_minutes: int
    status: str = "pending"


class RoadmapPhase(BaseModel):
    """A phase within the roadmap."""
    id: str = ""
    order_index: int
    title: str
    description: str
    status: str = "locked"  # locked | active | completed
    duration_days: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    tasks: List[RoadmapTask] = Field(default_factory=list)


class RoadmapResponse(BaseModel):
    """Schema for the full roadmap response."""
    id: str = ""
    version: int = 1
    title: str
    target_band: float
    start_band: float
    total_weeks: int
    estimated_achievement_date: Optional[date] = None
    confidence_score: int = 80
    phases: List[RoadmapPhase] = Field(default_factory=list)

