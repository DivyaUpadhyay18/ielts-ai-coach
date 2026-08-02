"""
Pydantic schemas for the Exam Countdown module.

The countdown module computes real-time metrics about the user's exam
timeline: days/weeks remaining, study hours (planned vs completed),
completion percentage, and preparation intensity.
"""
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field

INTENSITY_LEVELS = ("normal", "focused", "intensive", "final")


class StudyHoursData(BaseModel):
    """Study hours breakdown."""
    planned: float = Field(0.0, ge=0)
    completed: float = Field(0.0, ge=0)
    remaining: float = Field(0.0, ge=0)


class ExamCountdownResponse(BaseModel):
    """Full countdown payload returned by GET /countdown."""
    exam_date: str
    today: str
    days_remaining: int = Field(0, ge=0)
    weeks_remaining: int = Field(0, ge=0)
    study_hours: StudyHoursData = Field(default_factory=StudyHoursData)
    completion_percentage: float = Field(0.0, ge=0, le=100)
    intensity: str = Field("normal", pattern="^(normal|focused|intensive|final)$")
    has_active_plan: bool = False
    study_plan_id: Optional[str] = None
    study_plan_version: int = 0


class ExamDateUpdateRequest(BaseModel):
    """Request to update the exam date."""
    exam_date: date
    auto_regenerate: bool = True


class ExamDateUpdateResponse(BaseModel):
    """Response after updating the exam date."""
    exam_date: str
    previous_exam_date: Optional[str] = None
    regenerated: bool = False
    new_study_plan_id: Optional[str] = None
    new_study_plan_version: Optional[int] = None
    message: str
