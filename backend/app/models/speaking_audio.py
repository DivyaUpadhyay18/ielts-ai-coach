"""
Pydantic schemas for the Speaking Audio Processing Pipeline.

When a speaking response is submitted, one ``speaking_evaluations`` record is
created and processed asynchronously:
  queued → preparing → transcribing → completed  |  failed (retryable)

Tracked fields: audio_duration_seconds, file_size_bytes, transcript,
processing status, created_at / updated_at.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

SPEAKING_EVALUATION_STATUSES = (
    "queued",
    "preparing",
    "transcribing",
    "completed",
    "failed",
)


class SpeakingAudioSubmitRequest(BaseModel):
    """Request body for submitting a response's recording to the pipeline."""

    audio_url: str = Field(..., description="Preserved storage URL of the original recording")
    duration_seconds: int = Field(0, ge=0, description="Client-reported audio duration")


class SpeakingEvaluationResponse(BaseModel):
    id: str
    user_id: str
    response_id: str
    session_id: str | None = None
    part: str = "part_1"
    audio_url: str = ""
    audio_duration_seconds: int = 0
    file_size_bytes: int = 0
    transcript: str = ""
    provider: str = "openai_whisper"
    model: str = "whisper-1"
    status: str = "queued"
    error_message: str = ""
    retry_count: int = 0
    last_processed_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # AI Speaking Evaluation (Phase 10) — populated after transcription completes.
    # All optional so existing transcription records (pre-evaluation) still
    # serialise cleanly.
    overall_band: float | None = None
    confidence: float | None = None
    criteria: dict[str, Any] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    is_estimate: bool = True
    source: str = "pending"
    evaluated_at: datetime | None = None
    evaluation_version: int = 0


class SpeakingEvaluationListResponse(BaseModel):
    results: list[SpeakingEvaluationResponse] = Field(default_factory=list)
    total: int = 0


# ─── AI Speaking Evaluation (Phase 10) ────────────────────────────────────
# The four official IELTS Speaking band descriptors scored by the AI engine.
SPEAKING_CRITERIA_KEYS = (
    "fluency_coherence",
    "lexical_resource",
    "grammatical_range_accuracy",
    "pronunciation",
)

SPEAKING_CRITERIA_LABELS = {
    "fluency_coherence": "Fluency and Coherence",
    "lexical_resource": "Lexical Resource",
    "grammatical_range_accuracy": "Grammatical Range and Accuracy",
    "pronunciation": "Pronunciation",
}


class SpeakingEvaluationCriteriaItem(BaseModel):
    """A single IELTS Speaking criterion score + feedback."""

    band: float = 0.0
    label: str = ""
    strength: str = ""
    weakness: str = ""
    errors: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class SpeakingEvaluationCriteria(BaseModel):
    fluency_coherence: SpeakingEvaluationCriteriaItem = Field(
        default_factory=SpeakingEvaluationCriteriaItem
    )
    lexical_resource: SpeakingEvaluationCriteriaItem = Field(
        default_factory=SpeakingEvaluationCriteriaItem
    )
    grammatical_range_accuracy: SpeakingEvaluationCriteriaItem = Field(
        default_factory=SpeakingEvaluationCriteriaItem
    )
    pronunciation: SpeakingEvaluationCriteriaItem = Field(
        default_factory=SpeakingEvaluationCriteriaItem
    )






EVALUATION_STATUS_LABELS: dict[str, str] = {
    "queued": "Queued",
    "preparing": "Preparing audio",
    "transcribing": "Transcribing",
    "completed": "Completed",
    "failed": "Failed",
}
