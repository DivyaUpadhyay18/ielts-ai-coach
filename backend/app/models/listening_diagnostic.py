"""
Pydantic schemas for the Listening Diagnostic Module.

This dedicated subsystem assesses IELTS Listening through authentic audio
sections and five official question types:
  - Multiple Choice
  - Map
  - Form Completion
  - Sentence Completion
  - Matching

It reuses the `diagnostic_attempts` lifecycle (resume support) while storing
listening-specific outcomes (per-type accuracy, time, weak types, difficulty)
in `listening_diagnostic_results` — satisfying the "store results" requirement.

The framework remains deterministic (NO AI): accuracy, time, weak question
types, difficulty level, and an estimated IELTS listening band are computed
from the user's answers.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# The five IELTS Listening question types supported by this module.
LISTENING_QUESTION_TYPES = (
    "multiple_choice",
    "map",
    "form_completion",
    "sentence_completion",
    "matching",
)

# Difficulty levels derived from the average track/question difficulty.
DIFFICULTY_LEVELS = ("Easy", "Moderate", "Hard")


# ---------------------------------------------------------------------------
# Tracks + question bank
# ---------------------------------------------------------------------------
class ListeningTrack(BaseModel):
    """A single IELTS-style listening section / audio track."""
    id: str
    title: str
    description: Optional[str] = None
    audio_url: str
    section_number: int = 1
    difficulty: int = 3
    topics: Optional[List[str]] = None
    transcript: Optional[str] = None


class ListeningQuestion(BaseModel):
    """A listening question tied to an audio track."""
    id: str
    track_id: str
    question_type: str
    prompt: str
    options: Optional[List[str]] = None
    difficulty: int = 3
    time_limit_seconds: int = 90
    skill_tag: Optional[str] = None


class ListeningBankResponse(BaseModel):
    """Audio tracks plus their questions for the listening module."""
    tracks: List[ListeningTrack] = Field(default_factory=list)
    questions: List[ListeningQuestion] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------
class ListeningAnswerSubmit(BaseModel):
    """Submit an answer for a listening question."""
    attempt_id: str
    question_id: str
    answer: Any = None
    time_taken_seconds: int = Field(0, ge=0)


class ListeningAnswerResult(BaseModel):
    """Result of grading a listening answer."""
    question_id: str
    is_correct: bool
    correct_answer: Optional[Any] = None
    question_type: str
    time_taken_seconds: int = 0


# ---------------------------------------------------------------------------
# Results / report
# ---------------------------------------------------------------------------
class TypeBreakdown(BaseModel):
    """Per-question-type performance."""
    question_type: str
    total: int = 0
    correct: int = 0
    accuracy: float = 0.0
    avg_time_seconds: float = 0.0


class ListeningReportResponse(BaseModel):
    """
    Full listening diagnostic report.

    Includes the auto-calculated metrics required by the module:
      - accuracy (overall + per question type)
      - time (total + per question type)
      - weak question types
      - difficulty level
      - estimated IELTS listening band
    """
    attempt_id: str
    user_id: str
    total_questions: int = 0
    correct_answers: int = 0
    accuracy: float = 0.0
    total_time_seconds: int = 0
    listening_band: float = 0.0
    difficulty_level: str = "Easy"
    type_breakdown: List[TypeBreakdown] = Field(default_factory=list)
    weak_types: List[str] = Field(default_factory=list)
    strong_types: List[str] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
