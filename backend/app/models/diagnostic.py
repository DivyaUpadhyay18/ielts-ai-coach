"""
Pydantic schemas for the Diagnostic Test Framework.

Covers the six IELTS skill domains (reading, listening, writing, speaking,
vocabulary, grammar) and the full diagnostic lifecycle:
  start -> answer -> section complete -> finish -> report.

The framework is deterministic (NO AI): levels are estimated from per-section
accuracy and stored as IELTS band scores (0.5 steps).
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# The six skill domains assessed by the diagnostic.
DIAGNOSTIC_SECTIONS = (
    "reading", "listening", "writing", "speaking", "vocabulary", "grammar"
)

# Ordered flow: reading -> listening -> writing -> speaking -> vocabulary -> grammar
SECTION_ORDER = list(DIAGNOSTIC_SECTIONS)

# Attempt lifecycle states.
ATTEMPT_STATUSES = ("in_progress", "completed", "abandoned")


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------
class DiagnosticQuestion(BaseModel):
    """A single question from the diagnostic question bank."""
    id: str
    section: str
    prompt: str
    options: Optional[List[str]] = None
    difficulty: int = 3
    weight: float = 1.0
    time_limit_seconds: int = 60
    skill_tag: Optional[str] = None


class QuestionBankResponse(BaseModel):
    """A randomized set of questions for a section."""
    section: str
    questions: List[DiagnosticQuestion] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Attempts
# ---------------------------------------------------------------------------
class DiagnosticAttemptCreate(BaseModel):
    """Schema for starting a new diagnostic attempt."""
    pass  # no required fields; service builds defaults


class AnswerSubmit(BaseModel):
    """Submit an answer for a single question."""
    question_id: str
    section: str = Field(..., pattern="^(reading|listening|writing|speaking|vocabulary|grammar)$")
    answer: Any = None
    time_taken_seconds: int = Field(0, ge=0)


class AnswerResult(BaseModel):
    """Result of grading a single answer."""
    question_id: str
    is_correct: bool
    score: float
    section: str


class SectionComplete(BaseModel):
    """Mark a section as completed for an attempt."""
    section: str = Field(..., pattern="^(reading|listening|writing|speaking|vocabulary|grammar)$")
    time_taken_seconds: int = Field(0, ge=0)


class DiagnosticAttemptResponse(BaseModel):
    """A diagnostic attempt with progress/state info."""
    id: str
    user_id: str
    status: str
    current_section: str
    sections_completed: List[str] = Field(default_factory=list)
    total_seconds_spent: int = 0
    section_seconds: Dict[str, int] = Field(default_factory=dict)
    last_activity_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    overall_band: Optional[float] = None
    skill_scores: Optional[Dict[str, float]] = None
    created_at: Optional[datetime] = None


class ResumeResponse(BaseModel):
    """Resume payload: attempt state + answered questions."""
    attempt: DiagnosticAttemptResponse
    answered_question_ids: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
class SkillScore(BaseModel):
    """Per-skill band score and accuracy."""
    section: str
    band: float
    accuracy: float  # 0-100


class DiagnosticReportResponse(BaseModel):
    """Full diagnostic report used to estimate IELTS level."""
    attempt_id: str
    user_id: str
    overall_band: float
    target_note: str
    skill_scores: List[SkillScore] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    total_time_seconds: int = 0
    completed_at: Optional[datetime] = None
    # Enhanced report fields
    recommended_focus_areas: List[str] = Field(default_factory=list)
    suggested_weekly_hours: int = 0
    suggested_exam_timeline_weeks: int = 0
    roadmap_preview: Optional[Dict[str, Any]] = None
