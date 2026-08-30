"""
Pydantic schemas for the Vocabulary & Grammar Diagnostic Module.

This dedicated subsystem assesses two IELTS skill domains:
  - Vocabulary (fill_in_the_blanks, synonyms, antonyms)
  - Grammar    (sentence_correction, grammar_correction, tenses, articles,
                prepositions)

It reuses the `diagnostic_attempts` lifecycle (resume support) while storing
per-attempt outcomes (accuracy, grammar vs vocabulary accuracy, weak grammar
topics, weak vocabulary categories, time, difficulty, band) in
`vocab_grammar_diagnostic_results` — satisfying the "store results" requirement.

The framework remains deterministic (NO AI): all metrics are computed from the
user's answers.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Vocabulary question types (categories) assessed by this module.
VOCABULARY_QUESTION_TYPES = (
    "fill_in_the_blanks",
    "synonyms",
    "antonyms",
)

# Grammar question types (topics) assessed by this module.
GRAMMAR_QUESTION_TYPES = (
    "sentence_correction",
    "grammar_correction",
    "tenses",
    "articles",
    "prepositions",
)

# All supported question types.
ALL_QUESTION_TYPES = VOCABULARY_QUESTION_TYPES + GRAMMAR_QUESTION_TYPES

# Difficulty levels derived from the average question difficulty.
DIFFICULTY_LEVELS = ("Easy", "Moderate", "Hard")


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------
class VGQuestion(BaseModel):
    """A single vocabulary or grammar question."""
    id: str
    section: str  # 'vocabulary' | 'grammar'
    question_type: str
    prompt: str
    options: Optional[List[str]] = None
    difficulty: int = 3
    time_limit_seconds: int = 45
    skill_tag: Optional[str] = None


class VGBankResponse(BaseModel):
    """The vocabulary + grammar question bank (answer stripped)."""
    questions: List[VGQuestion] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------
class VGAnswerSubmit(BaseModel):
    """Submit an answer for a vocabulary or grammar question."""
    attempt_id: str
    question_id: str
    answer: Any = None
    time_taken_seconds: int = Field(0, ge=0)


class VGAnswerResult(BaseModel):
    """Result of grading a vocabulary/grammar answer."""
    question_id: str
    is_correct: bool
    correct_answer: Optional[Any] = None
    section: str
    question_type: str
    time_taken_seconds: int = 0


# ---------------------------------------------------------------------------
# Results / report
# ---------------------------------------------------------------------------
class VGTypeBreakdown(BaseModel):
    """Per-question-type performance."""
    question_type: str
    section: str
    total: int = 0
    correct: int = 0
    accuracy: float = 0.0
    avg_time_seconds: float = 0.0


class VGReportResponse(BaseModel):
    """
    Full vocabulary & grammar diagnostic report.

    Includes the auto-calculated metrics required by the module:
      - overall accuracy
      - grammar vs vocabulary accuracy
      - accuracy per question type
      - weak grammar topics
      - weak vocabulary categories
      - time
      - difficulty level
      - estimated IELTS band
    """
    attempt_id: str
    user_id: str
    total_questions: int = 0
    correct_answers: int = 0
    accuracy: float = 0.0
    grammar_accuracy: float = 0.0
    vocabulary_accuracy: float = 0.0
    total_time_seconds: int = 0
    band: float = 0.0
    difficulty_level: str = "Easy"
    type_breakdown: List[VGTypeBreakdown] = Field(default_factory=list)
    weak_grammar_topics: List[str] = Field(default_factory=list)
    weak_vocab_categories: List[str] = Field(default_factory=list)
    strong_types: List[str] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
