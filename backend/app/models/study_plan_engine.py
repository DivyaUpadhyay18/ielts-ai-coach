"""
Pydantic schemas for the Study Plan Generation Engine.

These schemas define the request/response contract for the deterministic
study-plan generator. The engine reads the user's profile (exam date,
current/target band, daily budget, weakest/strongest skills, module) and
produces a day-by-day plan stored in the canonical study_plans /
daily_plans / tasks tables.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.user import validate_band

PHASE_KEYS = ("foundation", "skill_building", "advanced", "mock_tests", "final_revision")

PHASE_WEIGHTS = {
    "foundation": 0.30,
    "skill_building": 0.30,
    "advanced": 0.20,
    "mock_tests": 0.15,
    "final_revision": 0.05,
}

ALL_SKILLS = ("reading", "listening", "writing", "speaking", "vocabulary", "grammar")


class StudyPlanGenerateRequest(BaseModel):
    """Input schema for generating a full study plan."""
    exam_date: date
    current_band: float = Field(..., ge=0, le=9)
    target_band: float = Field(..., ge=0, le=9)
    daily_minutes_budget: int = Field(60, ge=15, le=480)
    module: str = Field("academic", pattern="^(academic|general)$")
    weakest_skills: List[str] = Field(default_factory=list)
    strongest_skills: List[str] = Field(default_factory=list)
    start_date: Optional[date] = None

    @field_validator("current_band", "target_band")
    @classmethod
    def validate_bands(cls, v: float) -> float:
        return validate_band(v, "band")

    @field_validator("target_band")
    @classmethod
    def target_not_below_current(cls, v: float, info) -> float:
        current = info.data.get("current_band")
        if current is not None and v < current:
            raise ValueError("target_band must be >= current_band")
        return v

    @field_validator("exam_date")
    @classmethod
    def validate_exam_date(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("exam_date must be in the future")
        return v

    @field_validator("weakest_skills", "strongest_skills")
    @classmethod
    def validate_skills(cls, v: List[str]) -> List[str]:
        cleaned: List[str] = []
        for skill in v:
            norm = skill.strip().lower() if isinstance(skill, str) else ""
            if norm in ALL_SKILLS and norm not in cleaned:
                cleaned.append(norm)
        return cleaned


class GeneratedTask(BaseModel):
    """A single generated task within a day of the plan."""
    title: str
    skill: str
    task_type: str
    duration_minutes: int = Field(..., ge=1, le=240)
    priority: int = Field(1, ge=1, le=5)
    xp_reward: int = Field(0, ge=0)
    difficulty: int = Field(1, ge=1, le=5)
    is_mandatory: bool = False


class GeneratedDay(BaseModel):
    """A single day in the generated plan."""
    plan_date: date
    phase_index: int = Field(0, ge=0)
    is_revision_day: bool = False
    is_mock_day: bool = False
    is_rest_day: bool = False
    xp_reward: int = Field(0, ge=0)
    total_minutes: int = Field(0, ge=0)
    tasks: List[GeneratedTask] = Field(default_factory=list)


class PhaseBreakdown(BaseModel):
    """Summary of days allocated per phase."""
    key: str
    label: str
    weight: float = Field(..., ge=0, le=1)
    start_date: date
    end_date: date
    days: int = Field(..., ge=0)


class StudyPlanGenerateResponse(BaseModel):
    """Response from generating a study plan."""
    study_plan_id: str
    version: int = 1
    title: str
    target_band: float
    start_band: float
    total_weeks: int = Field(..., ge=2, le=52)
    start_date: date
    exam_date: date
    total_days: int = Field(..., ge=1)
    phase_breakdown: List[PhaseBreakdown] = Field(default_factory=list)
    days: List[GeneratedDay] = Field(default_factory=list)
    total_tasks: int = Field(0, ge=0)
    total_xp: int = Field(0, ge=0)
    generated_at: datetime


class StudyPlanDaysResponse(BaseModel):
    """Day-by-day view of an existing study plan."""
    study_plan_id: str
    version: int = 1
    title: str
    start_date: Optional[date] = None
    exam_date: Optional[date] = None
    days: List[GeneratedDay] = Field(default_factory=list)
    total_days: int = Field(0, ge=0)
    total_tasks: int = Field(0, ge=0)
    total_xp: int = Field(0, ge=0)

