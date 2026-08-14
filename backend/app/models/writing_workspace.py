"""
Pydantic schemas for the Writing Workspace API.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ─── Submission CRUD ──────────────────────────────────────────────────
class SubmissionStart(BaseModel):
    """Request to start/resume a writing submission."""
    prompt_id: str


class SubmissionSave(BaseModel):
    """Request to auto-save a draft."""
    essay_text: str
    time_seconds_spent: Optional[int] = None


class SubmissionSubmit(BaseModel):
    """Request to submit a draft for evaluation."""
    time_seconds_spent: Optional[int] = None


class PromptResponse(BaseModel):
    """A single writing prompt."""
    id: str
    task_type: str
    title: str
    prompt_text: str
    word_limit: int
    time_limit_seconds: int
    difficulty: int
    topics: List[str] = []


class PromptsResponse(BaseModel):
    """List of writing prompts."""
    task_type: str
    prompts: List[PromptResponse]
    total: int


class WritingSubmissionSummary(BaseModel):
    """Pre-submission summary captured at submit time."""
    word_count: int
    word_limit: int
    time_seconds_spent: int
    time_limit_seconds: int
    meets_word_requirement: bool
    within_time_limit: bool
    warnings: List[str] = []
    submitted_at: Optional[str] = None


class SubmissionResponse(BaseModel):
    """A writing workspace submission."""
    id: str
    user_id: str
    prompt_id: Optional[str] = None
    task_type: str
    title: str
    prompt_text: Optional[str] = None
    word_limit: int
    time_limit_seconds: int
    essay_text: str
    word_count: int
    time_seconds_spent: int
    status: str
    is_locked: bool
    evaluation_status: Optional[str] = None
    submission_summary: Dict[str, Any] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None


class SubmissionListResponse(BaseModel):
    """List of submissions."""
    results: List[SubmissionResponse]
    total: int


# ─── Evaluation ───────────────────────────────────────────────────────
class WritingError(BaseModel):
    """
    A single detected issue within the essay.

    Carries the original text, category, explanation, suggested correction,
    severity, the IELTS criterion affected, and character offsets used by the
    UI to highlight the problematic section in the essay.

    ``correction`` fixes only this one issue — the essay is never rewritten
    automatically as a whole.
    """
    id: str
    original: str
    error_type: str
    explanation: str
    correction: str
    severity: str = "minor"  # critical | major | minor
    criterion: str = "grammatical_range_accuracy"
    start: int = 0
    end: int = 0
    sentence: str = ""


class CriterionEvaluation(BaseModel):
    """A single criterion evaluation."""
    band: float
    label: str
    strength: str
    weakness: str
    errors: List[str] = []
    suggestions: List[str] = []


class WritingCriteriaEvaluation(BaseModel):
    """All four criteria evaluations."""
    task_response: CriterionEvaluation
    coherence_cohesion: CriterionEvaluation
    lexical_resource: CriterionEvaluation
    grammatical_range_accuracy: CriterionEvaluation


class WritingEvaluationResponse(BaseModel):
    """
    Full evaluation response returned to the client.

    AI scoring is not implemented in this phase — pending records carry no
    bands and ``evaluation_status`` is 'pending'.  A future phase fills the
    criteria/bands and flips the status to 'evaluated'.
    """
    task_type: str
    criteria_bands: Dict[str, Any] = {}
    criteria_detail: Dict[str, Any] = {}
    overall_band: Optional[float] = None
    confidence: Optional[float] = None
    is_estimate: bool = True
    word_count: int = 0
    source: str = "pending"
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    errors: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None
    evaluated_at: Optional[str] = None
    evaluation_status: str = "pending"
    is_official: bool = False
    error_analysis: Optional[List[WritingError]] = None


class WritingEvaluationSummary(BaseModel):
    """Lightweight evaluation summary for lists."""
    submission_id: str
    overall_band: float
    confidence: float
    word_count: int
    task_type: str
    created_at: Optional[str] = None


class WritingEvaluationListResponse(BaseModel):
    """List of evaluation summaries."""
    results: List[WritingEvaluationSummary]
    total: int
