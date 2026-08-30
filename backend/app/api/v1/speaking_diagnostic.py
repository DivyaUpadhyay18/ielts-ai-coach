"""
Speaking Diagnostic Module endpoints.

Provides the speaking-specific diagnostic flow:
  - GET  /speaking/prompts?part=  → Part 1 / Part 2 / Part 3 prompts
  - POST /speaking/recordings     → start a speaking recording (resume-aware)
  - POST /speaking/recordings/{id}/save    → save recorded audio metadata + transcript
  - POST /speaking/recordings/{id}/complete→ finalize the recording
  - POST /speaking/recordings/{id}/score   → apply manual IELTS scoring
  - POST /speaking/recordings/{id}/ai      → future AI evaluation scaffold
  - GET  /speaking/recordings/{id}         → fetch the stored recording report
  - GET  /speaking/recordings              → list a user's stored recordings

Everything is deterministic (NO AI) except the optional /ai scaffold, and all
operations are owner-scoped.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_speaking_diagnostic_service
from app.core.exceptions import NotFoundError, ValidationError
from app.models.speaking_diagnostic import (
    ManualScoreSubmit,
    RecordingComplete,
    RecordingSave,
    RecordingStart,
)
from app.services.speaking_diagnostic_service import SpeakingDiagnosticService

router = APIRouter()


@router.get(
    "/prompts",
    response_model=dict,
    summary="Get speaking prompts (Part 1 / 2 / 3)",
)
async def get_prompts(
    part: Optional[str] = Query(None, regex="^(part_1|part_2|part_3)$"),
    user_id: str = Depends(get_current_user),
    service: SpeakingDiagnosticService = Depends(get_speaking_diagnostic_service),
):
    """Return all active speaking prompts, optionally filtered by part."""
    try:
        return service.get_prompts(part)
    except ValidationError:
        raise


@router.post(
    "/recordings",
    response_model=dict,
    status_code=201,
    summary="Start a speaking recording",
)
async def start_recording(
    data: RecordingStart,
    user_id: str = Depends(get_current_user),
    service: SpeakingDiagnosticService = Depends(get_speaking_diagnostic_service),
):
    """Start a new speaking recording for a prompt (resume-aware)."""
    try:
        return service.start_recording(user_id, data.prompt_id)
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/recordings/{recording_id}/save",
    response_model=dict,
    summary="Save the recorded audio metadata + transcript",
)
async def save_recording(
    recording_id: str,
    data: RecordingSave,
    user_id: str = Depends(get_current_user),
    service: SpeakingDiagnosticService = Depends(get_speaking_diagnostic_service),
):
    """Save the recorded audio URL, duration, and transcript."""
    try:
        return service.save_recording(
            user_id,
            recording_id,
            data.audio_url,
            data.duration_seconds,
            data.transcript,
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/recordings/{recording_id}/complete",
    response_model=dict,
    summary="Complete a speaking recording",
)
async def complete_recording(
    recording_id: str,
    data: RecordingComplete,
    user_id: str = Depends(get_current_user),
    service: SpeakingDiagnosticService = Depends(get_speaking_diagnostic_service),
):
    """Finalize the recording and mark it as completed."""
    try:
        return service.complete_recording(
            user_id, recording_id, data.duration_seconds
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/recordings/{recording_id}/score",
    response_model=dict,
    summary="Apply manual IELTS speaking scoring",
)
async def submit_score(
    recording_id: str,
    data: ManualScoreSubmit,
    user_id: str = Depends(get_current_user),
    service: SpeakingDiagnosticService = Depends(get_speaking_diagnostic_service),
):
    """Apply manual IELTS scoring across the four criteria and store the result."""
    try:
        return service.submit_manual_score(
            user_id,
            recording_id,
            {
                "fluency_coherence": data.fluency_coherence,
                "lexical_resource": data.lexical_resource,
                "grammatical_range": data.grammatical_range,
                "pronunciation": data.pronunciation,
            },
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/recordings/{recording_id}/ai",
    response_model=dict,
    summary="Run (or scaffold) AI evaluation of the speaking transcript",
)
async def ai_evaluate(
    recording_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingDiagnosticService = Depends(get_speaking_diagnostic_service),
):
    """Architecture scaffold for future AI evaluation (returns placeholder if no provider)."""
    try:
        return service.ai_evaluate(user_id, recording_id)
    except (NotFoundError, ValidationError):
        raise


@router.get(
    "/recordings/{recording_id}",
    response_model=dict,
    summary="Get the stored recording report",
)
async def get_report(
    recording_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingDiagnosticService = Depends(get_speaking_diagnostic_service),
):
    """Fetch the stored speaking recording and its report."""
    try:
        return service.get_report(user_id, recording_id)
    except NotFoundError:
        raise


@router.get(
    "/recordings",
    response_model=dict,
    summary="List a user's stored speaking recordings",
)
async def list_recordings(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    service: SpeakingDiagnosticService = Depends(get_speaking_diagnostic_service),
):
    """List the current user's stored speaking recordings/results."""
    return service.list_recordings(user_id, limit)
