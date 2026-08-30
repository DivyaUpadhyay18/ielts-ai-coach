"""
Pydantic schemas for the Writing Diagnostic Module.

This dedicated subsystem assesses IELTS Writing through authentic Task 1
(report/letter) and Task 2 (essay) prompts. Unlike the objective reading and
listening modules, writing is free-form: the user writes an essay that is
auto-saved as they type, timed, and scored manually across the four official
IELTS criteria.

It reuses the `diagnostic_attempts` lifecycle (resume support) while storing
writing-specific outcomes (essay text, word count, time, manual scores) in
`writing_essays` — satisfying the "store essays" requirement.

Architecture for future AI evaluation:
  - `grammar_feedback` and `vocabulary_feedback` JSONB columns are reserved
    placeholders for dedicated grammar/vocabulary analysis.
  - `ai_evaluation` JSONB is reserved for a full AI band assessment
    (Task Response, Coherence & Cohesion, Lexical Resource, Grammatical
    Range) powered by the existing `app.services.ai_service`.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# The two IELTS Writing tasks supported by this module.
WRITING_TASK_TYPES = ("task_1", "task_2")

# Essay lifecycle states.
ESSAY_STATUSES = ("in_progress", "completed")

# The four official IELTS Writing marking criteria.
WRITING_CRITERIA = (
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammatical_range",
)


# ---------------------------------------------------------------------------
# Prompts + question bank
# ---------------------------------------------------------------------------
class WritingPrompt(BaseModel):
    """A single IELTS-style writing prompt (Task 1 or Task 2)."""
    id: str
    task_type: str
    title: str
    prompt_text: str
    word_limit: int = 150
    time_limit_seconds: int = 1200
    difficulty: int = 3
    topics: Optional[List[str]] = None


class WritingPromptsResponse(BaseModel):
    """List of writing prompts for a task type."""
    task_type: str
    prompts: List[WritingPrompt] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Essay lifecycle
# ---------------------------------------------------------------------------
class EssayStart(BaseModel):
    """Start a new writing essay for a prompt."""
    prompt_id: str
    attempt_id: Optional[str] = None  # optional; service can create/reuse attempt


class EssaySave(BaseModel):
    """Auto-save the current essay content."""
    essay_text: str = ""
    time_seconds_spent: int = Field(0, ge=0)


class EssayComplete(BaseModel):
    """Finalize an essay (submit for scoring)."""
    time_seconds_spent: int = Field(0, ge=0)


# ---------------------------------------------------------------------------
# Manual scoring (the four IELTS criteria, 0-9 in 0.5 steps)
# ---------------------------------------------------------------------------
class ManualScoreSubmit(BaseModel):
    """Manual IELTS scoring across the four writing criteria."""
    task_response: float = Field(..., ge=0, le=9)
    coherence_cohesion: float = Field(..., ge=0, le=9)
    lexical_resource: float = Field(..., ge=0, le=9)
    grammatical_range: float = Field(..., ge=0, le=9)


# ---------------------------------------------------------------------------
# Essay / report
# ---------------------------------------------------------------------------
class WritingEssay(BaseModel):
    """A stored writing essay with its prompt and metrics."""
    id: str
    attempt_id: str
    user_id: str
    prompt_id: Optional[str] = None
    task_type: str = "task_2"
    title: str = ""
    essay_text: str = ""
    word_count: int = 0
    time_seconds_spent: int = 0
    status: str = "in_progress"
    # prompt snapshot
    prompt_text: Optional[str] = None
    word_limit: Optional[int] = None
    time_limit_seconds: Optional[int] = None
    # manual scores
    task_response: Optional[float] = None
    coherence_cohesion: Optional[float] = None
    lexical_resource: Optional[float] = None
    grammatical_range: Optional[float] = None
    overall_band: Optional[float] = None
    # AI placeholders (future)
    grammar_feedback: Dict[str, Any] = Field(default_factory=dict)
    vocabulary_feedback: Dict[str, Any] = Field(default_factory=dict)
    ai_evaluation: Dict[str, Any] = Field(default_factory=dict)
    saved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class WritingReportResponse(BaseModel):
    """
    Full writing diagnostic report for an essay.

    Includes the essay body, word count, time, manual IELTS scores, and the
    reserved AI placeholders (grammar, vocabulary, AI evaluation).
    """
    essay: WritingEssay
    is_scored: bool = False
    completed: bool = False


class WritingResultsListResponse(BaseModel):
    """List a user's stored writing essays/results."""
    results: List[WritingEssay] = Field(default_factory=list)
    total: int = 0
