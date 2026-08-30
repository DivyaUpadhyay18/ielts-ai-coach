"""
Pydantic schemas for the Reading Diagnostic Module.

This dedicated subsystem assesses IELTS Reading through authentic passages
and six official question types:
  - True / False / Not Given
  - Matching Headings
  - Multiple Choice
  - Sentence Completion
  - Summary Completion
  - Short Answer

It reuses the `diagnostic_attempts` lifecycle (resume support) while storing
reading-specific outcomes (per-type accuracy, time, weak types, difficulty)
in `reading_diagnostic_results` — satisfying the "store results" requirement.

The framework remains deterministic (NO AI): accuracy, time, weak question
types, difficulty level, and an estimated IELTS reading band are computed
from the user's answers.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# The six IELTS Reading question types supported by this module.
READING_QUESTION_TYPES = (
    "true_false_not_given",
    "matching_headings",
    "multiple_choice",
    "sentence_completion",
    "summary_completion",
    "short_answer",
)

# Difficulty levels derived from the average passage/question difficulty.
DIFFICULTY_LEVELS = ("Easy", "Moderate", "Hard")


# ---------------------------------------------------------------------------
# Passages + question bank
# ---------------------------------------------------------------------------
class ReadingPassage(BaseModel):
    """A single IELTS-style reading passage."""
    id: str
    title: str
    content: str
    difficulty: int = 3
    topics: Optional[List[str]] = None
    word_count: int = 0


class ReadingQuestion(BaseModel):
    """A reading question tied to a passage."""
    id: str
    passage_id: str
    question_type: str
    prompt: str
    options: Optional[List[str]] = None
    difficulty: int = 3
    time_limit_seconds: int = 90
    skill_tag: Optional[str] = None


class ReadingBankResponse(BaseModel):
    """Passages plus their questions for the reading module."""
    passages: List[ReadingPassage] = Field(default_factory=list)
    questions: List[ReadingQuestion] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------
class ReadingAnswerSubmit(BaseModel):
    """Submit an answer for a reading question."""
    attempt_id: str
    question_id: str
    answer: Any = None
    time_taken_seconds: int = Field(0, ge=0)


class ReadingAnswerResult(BaseModel):
    """Result of grading a reading answer."""
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


class ReadingReportResponse(BaseModel):
    """
    Full reading diagnostic report.

    Includes the auto-calculated metrics required by the module:
      - accuracy (overall + per question type)
      - time (total + per question type)
      - weak question types
      - difficulty level
      - estimated IELTS reading band
    """
    attempt_id: str
    user_id: str
    total_questions: int = 0
    correct_answers: int = 0
    accuracy: float = 0.0
    total_time_seconds: int = 0
    reading_band: float = 0.0
    difficulty_level: str = "Easy"
    type_breakdown: List[TypeBreakdown] = Field(default_factory=list)
    weak_types: List[str] = Field(default_factory=list)
    strong_types: List[str] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
