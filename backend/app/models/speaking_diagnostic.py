"""
Pydantic schemas for the Speaking Diagnostic Module.

This dedicated subsystem assesses IELTS Speaking across the three official
parts:
  - Part 1 (Introduction & Interview)
  - Part 2 (Individual Long Turn with prep + speaking time)
  - Part 3 (Two-way Discussion)

Unlike objective reading/listening modules, speaking is free-form: the user
records their spoken response (captured client-side via MediaRecorder), the
audio asset URL is persisted, and the response is scored manually across the
four official IELTS Speaking criteria.

It reuses the `diagnostic_attempts` lifecycle (resume support) while storing
speaking-specific outcomes (audio_url, duration, transcript, manual scores,
AI placeholder) in `speaking_recordings` — satisfying the "store recordings"
requirement.

Architecture for future AI evaluation:
  - `ai_evaluation` JSONB is reserved for a full AI band assessment
    (Fluency & Coherence, Lexical Resource, Grammatical Range,
    Pronunciation) powered by the existing `app.services.ai_service`.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# The three IELTS Speaking parts supported by this module.
SPEAKING_PARTS = ("part_1", "part_2", "part_3")

# Recording lifecycle states.
RECORDING_STATUSES = ("in_progress", "completed")

# The four official IELTS Speaking marking criteria.
SPEAKING_CRITERIA = (
    "fluency_coherence",
    "lexical_resource",
    "grammatical_range",
    "pronunciation",
)


# ---------------------------------------------------------------------------
# Prompts + question bank
# ---------------------------------------------------------------------------
class SpeakingPrompt(BaseModel):
    """A single IELTS-style speaking prompt (Part 1, 2, or 3)."""
    id: str
    part: str
    title: str
    prompt_text: str
    prep_time_seconds: int = 0
    speak_time_seconds: int = 60
    difficulty: int = 3
    topics: Optional[List[str]] = None
    follow_up: Optional[str] = None


class SpeakingPromptsResponse(BaseModel):
    """List of speaking prompts for a part."""
    part: str
    prompts: List[SpeakingPrompt] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Recording lifecycle
# ---------------------------------------------------------------------------
class RecordingStart(BaseModel):
    """Start a new speaking recording for a prompt."""
    prompt_id: str
    attempt_id: Optional[str] = None  # optional; service can create/reuse attempt


class RecordingSave(BaseModel):
    """Save the recorded audio metadata + transcript for a recording."""
    audio_url: str = ""
    duration_seconds: int = Field(0, ge=0)
    transcript: str = ""


class RecordingComplete(BaseModel):
    """Finalize a recording (submit for scoring)."""
    duration_seconds: int = Field(0, ge=0)


# ---------------------------------------------------------------------------
# Manual scoring (the four IELTS criteria, 0-9 in 0.5 steps)
# ---------------------------------------------------------------------------
class ManualScoreSubmit(BaseModel):
    """Manual IELTS scoring across the four speaking criteria."""
    fluency_coherence: float = Field(..., ge=0, le=9)
    lexical_resource: float = Field(..., ge=0, le=9)
    grammatical_range: float = Field(..., ge=0, le=9)
    pronunciation: float = Field(..., ge=0, le=9)


# ---------------------------------------------------------------------------
# Recording / report
# ---------------------------------------------------------------------------
class SpeakingRecording(BaseModel):
    """A stored speaking recording with its prompt and metrics."""
    id: str
    attempt_id: str
    user_id: str
    prompt_id: Optional[str] = None
    part: str = "part_1"
    title: str = ""
    audio_url: str = ""
    duration_seconds: int = 0
    transcript: str = ""
    status: str = "in_progress"
    # prompt snapshot
    prompt_text: Optional[str] = None
    prep_time_seconds: Optional[int] = None
    speak_time_seconds: Optional[int] = None
    follow_up: Optional[str] = None
    # manual scores
    fluency_coherence: Optional[float] = None
    lexical_resource: Optional[float] = None
    grammatical_range: Optional[float] = None
    pronunciation: Optional[float] = None
    overall_band: Optional[float] = None
    # AI placeholder (future)
    ai_evaluation: Dict[str, Any] = Field(default_factory=dict)
    saved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SpeakingReportResponse(BaseModel):
    """
    Full speaking diagnostic report for a recording.

    Includes the stored audio, duration, transcript, manual IELTS scores, and
    the reserved AI placeholder (full AI band assessment).
    """
    recording: SpeakingRecording
    is_scored: bool = False
    completed: bool = False


class SpeakingResultsListResponse(BaseModel):
    """List a user's stored speaking recordings/results."""
    results: List[SpeakingRecording] = Field(default_factory=list)
    total: int = 0
