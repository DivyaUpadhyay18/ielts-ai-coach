"""
Pydantic schemas for the Speaking Test Workspace API.

A full 3-part IELTS Speaking mock:
  - Part 1 (Introduction & Interview)
  - Part 2 (Individual Long Turn with 1-min prep + 2-min speak)
  - Part 3 (Two-way Discussion)

Each part has prompts from the shared speaking_prompts question bank.
Users progress question-by-question, recording audio for each response,
with prep/speaking timers, playback, delete/re-record, save, and continue.
Progress is auto-saved and the session resumes if the user leaves.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

SPEAKING_TEST_PARTS = ("part_1", "part_2", "part_3")

PART_LABELS = {
    "part_1": "Part 1 — Introduction & Interview",
    "part_2": "Part 2 — Individual Long Turn",
    "part_3": "Part 3 — Two-way Discussion",
}


class SpeakingTestPrompt(BaseModel):
    id: str
    part: str
    title: str
    prompt_text: str
    prep_time_seconds: int = 0
    speak_time_seconds: int = 60
    difficulty: int = 3
    topics: list[str] | None = None
    follow_up: str | None = None


class SpeakingTestPromptsResponse(BaseModel):
    part: str
    prompts: list[SpeakingTestPrompt] = Field(default_factory=list)
    total: int = 0


class SpeakingTestStartRequest(BaseModel):
    pass


class SpeakingTestSessionResponse(BaseModel):
    id: str
    user_id: str
    current_part: str = "part_1"
    status: str = "in_progress"
    started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    responses: list["SpeakingTestResponseResponse"] = Field(default_factory=list)


class ResponseStartRequest(BaseModel):
    prompt_id: str
    part: str = "part_1"


class SpeakingTestResponseResponse(BaseModel):
    id: str
    session_id: str
    user_id: str
    prompt_id: str | None = None
    part: str = "part_1"
    title: str = ""
    prompt_text: str = ""
    prep_time_seconds: int = 0
    speak_time_seconds: int = 60
    audio_url: str = ""
    duration_seconds: int = 0
    transcript: str = ""
    is_saved: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SpeakingTestResponseSaveRequest(BaseModel):
    audio_url: str = ""
    duration_seconds: int = Field(0, ge=0)
    transcript: str = ""
    is_saved: bool = False


class SpeakingTestProgressResponse(BaseModel):
    # session is None when there is no active in-progress test.
    session: SpeakingTestSessionResponse | None = None
    parts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    total_responses: int = 0
    completed_parts: list[str] = Field(default_factory=list)


class SpeakingTestSessionListResponse(BaseModel):
    results: list[SpeakingTestSessionResponse] = Field(default_factory=list)
    total: int = 0


class SpeakingTestResponseListResponse(BaseModel):
    results: list[SpeakingTestResponseResponse] = Field(default_factory=list)
    total: int = 0


class AudioUploadResponse(BaseModel):
    audio_url: str
    filename: str
    size: int


# ─────────────────────────────────────────────────────────────
# Speaking Reattempt Mode — "Improve My Speaking Band"
# ─────────────────────────────────────────────────────────────

class SpeakingAttemptResponse(BaseModel):
    id: str
    response_id: str
    attempt_number: int
    evaluated_at: str | None = None
    overall_band: float | None = None
    fluency_coherence_band: float | None = None
    lexical_resource_band: float | None = None
    grammatical_range_band: float | None = None
    pronunciation_band: float | None = None
    duration_seconds: int | None = None
    filler_words_count: int = 0
    error_count: int = 0
    bonus_xp: int = 0
    bonus_reason: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


class SpeakingCriterionComparison(BaseModel):
    criterion: str
    label: str
    attempt_1_band: float
    attempt_2_band: float
    delta: float
    improved: bool


class SpeakingAttemptComparison(BaseModel):
    """Comparison between attempt 1 and the latest attempt."""
    compared: bool
    reason: str | None = None
    original_response_id: str
    latest_response_id: str
    latest_attempt_number: int
    overall_band: dict
    criteria: list[SpeakingCriterionComparison]
    duration_seconds: dict
    filler_words: dict
    error_count: dict
    improved_criteria: list[str]
    worsened_criteria: list[str]
    unchanged_criteria: list[str]
    what_improved: list[str]
    what_stayed_the_same: list[str]
    what_became_worse: list[str]
    focus_next: list[str]
    bonus_xp: int
    bonus_reason: str | None = None


# ─────────────────────────────────────────────────────────────
# Speaking Practice Mode models
# ─────────────────────────────────────────────────────────────

from typing import Optional

SPEAKING_PRACTICE_MODES = (
    "quick_practice", "part_1_practice", "part_2_practice",
    "part_3_practice", "vocabulary_practice", "fluency_practice",
    "random_question", "weak_area_practice",
)


class SpeakingPracticeSessionCreate(BaseModel):
    """Request to start a speaking practice session."""
    practice_mode: str
    target_band: Optional[float] = None


class SpeakingPracticeSessionResponse(BaseModel):
    """A speaking practice session."""
    id: str
    user_id: str
    practice_mode: str
    prompt_id: str | None = None
    part: str
    title: str
    prompt_text: str
    prep_time_seconds: int = 0
    speak_time_seconds: int = 60
    audio_url: str = ""
    duration_seconds: int = 0
    transcript: str = ""
    overall_band: float | None = None
    fluency_coherence_band: float | None = None
    lexical_resource_band: float | None = None
    grammatical_range_band: float | None = None
    pronunciation_band: float | None = None
    error_count: int = 0
    filler_words_count: int = 0
    feedback: str | None = None
    next_recommendation: str | None = None
    status: str = "in_progress"
    mission_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None


# ─────────────────────────────────────────────────────────────
# Speaking Progress Analytics models
# ─────────────────────────────────────────────────────────────

class SpeakingBandHistoryPoint(BaseModel):
    """One point in the chronological speaking band history series."""
    evaluation_id: str
    date: str  # ISO date
    overall_band: Optional[float] = None
    fluency_coherence_band: Optional[float] = None
    lexical_resource_band: Optional[float] = None
    grammatical_range_band: Optional[float] = None
    pronunciation_band: Optional[float] = None
    part: str
    title: Optional[str] = None
    confidence: Optional[float] = None


class SpeakingBandHistoryResponse(BaseModel):
    """Speaking Band History response."""
    results: list[SpeakingBandHistoryPoint]
    total: int


class SpeakingCriterionHistoryPoint(BaseModel):
    """One point in a single criterion's history."""
    evaluation_id: str
    date: str
    band: Optional[float] = None
    part: str
    title: Optional[str] = None


class SpeakingCriterionHistoryResponse(BaseModel):
    """Per-criterion band history."""
    criterion: str
    label: str
    results: list[SpeakingCriterionHistoryPoint]
    total: int


class SpeakingMetricsResponse(BaseModel):
    """Aggregate speaking metrics."""
    total_evaluations: int
    average_band: Optional[float] = None
    average_fluency_band: Optional[float] = None
    average_lexical_band: Optional[float] = None
    average_grammar_band: Optional[float] = None
    average_pronunciation_band: Optional[float] = None
    average_duration: Optional[float] = None
    average_filler_words: Optional[float] = None
    strongest_criterion: Optional[str] = None
    strongest_criterion_label: Optional[str] = None
    weakest_criterion: Optional[str] = None
    weakest_criterion_label: Optional[str] = None


class SpeakingCommonErrorsResponse(BaseModel):
    """Common grammar and vocabulary errors."""
    common_grammar_errors: list[dict[str, Any]]
    common_vocabulary_errors: list[dict[str, Any]]
    total_grammar_errors: int
    total_vocabulary_errors: int


class SpeakingImprovementRateResponse(BaseModel):
    """Improvement rate for a criterion or overall band."""
    criterion: str
    label: str
    improvement_rate: float
    total_points: int
    first_band: Optional[float] = None
    latest_band: Optional[float] = None
    trend: str  # "improving" | "declining" | "stable"


class SpeakingAttemptHistoryItem(BaseModel):
    """One attempt in the attempt history."""
    evaluation_id: str
    date: str
    overall_band: Optional[float] = None
    part: str
    title: Optional[str] = None
    error_count: int = 0
    filler_words: int = 0
    duration_seconds: int = 0
    confidence: Optional[float] = None
    source: Optional[str] = None


class SpeakingAttemptHistoryResponse(BaseModel):
    """Full attempt history."""
    results: list[SpeakingAttemptHistoryItem]
    total: int


class SpeakingAnalyticsDashboardResponse(BaseModel):
    """Comprehensive Speaking Progress Analytics dashboard."""
    band_history: list[SpeakingBandHistoryPoint]
    metrics: SpeakingMetricsResponse
    common_errors: SpeakingCommonErrorsResponse
    strongest_criterion: str
    weakest_criterion: str
    improvement_rate: SpeakingImprovementRateResponse
    attempt_history: list[SpeakingAttemptHistoryItem]
    total_evaluations: int
