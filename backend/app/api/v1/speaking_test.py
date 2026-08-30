"""
Speaking Test Workspace API endpoints.

A full IELTS Speaking mock exam across Part 1, Part 2, and Part 3:
  - GET  /prompts                          → list prompts (filter by part)
  - GET  /prompts/{id}                     → single prompt
  - POST /start                            → start/resume test session
  - GET  /session                          → get current in-progress session
  - GET  /sessions                         → list past sessions
  - GET  /sessions/{id}                    → get session with responses
  - GET  /sessions/{id}/responses          → list responses for a session
  - POST /sessions/{id}/advance            → advance to next part
  - POST /sessions/{id}/complete           → complete the test
  - POST /sessions/{id}/abandon            → abandon the test
  - POST /responses                        → start a per-question response
  - GET  /responses/{id}                   → get a response
  - POST /responses/{id}/save             → save recording metadata
  - POST /responses/{id}/complete          → mark response as done
  - DELETE /responses/{id}                 → delete (re-record)
  - POST /upload                           → upload audio to storage
  - GET  /progress                        → current test progress (resume)

All operations are owner-scoped (user_id from JWT). No AI evaluation.
"""

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from app.api.deps import (
    get_current_user,
    get_speaking_audio_pipeline_service,
    get_speaking_test_service,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.models.speaking_audio import (
    SpeakingAudioSubmitRequest,
    SpeakingEvaluationListResponse,
    SpeakingEvaluationResponse,
)
from app.models.speaking_test import (
    AudioUploadResponse,
    ResponseStartRequest,
    SpeakingTestProgressResponse,
    SpeakingTestPrompt,
    SpeakingTestPromptsResponse,
    SpeakingTestResponseListResponse,
    SpeakingTestResponseResponse,
    SpeakingTestResponseSaveRequest,
    SpeakingTestSessionListResponse,
    SpeakingTestSessionResponse,
)
from app.services.speaking_audio_pipeline import SpeakingAudioPipelineService
from app.services.speaking_test_service import SpeakingTestService
from app.services.speech_to_text_service import validate_audio_file

router = APIRouter()


def _service() -> SpeakingTestService:
    """Local factory matching the deps.py singleton pattern."""
    from app.db.session import db_session
    return SpeakingTestService(db_session)


# ---------------------------------------------------------------------------
# Prompts (question bank — reuses speaking_prompts)
# ---------------------------------------------------------------------------
@router.get(
    "/prompts",
    response_model=SpeakingTestPromptsResponse,
    summary="List speaking test prompts (Part 1 / 2 / 3)",
)
async def get_prompts(
    part: str | None = Query(None, regex="^(part_1|part_2|part_3)$"),
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Return all active speaking prompts, optionally filtered by part."""
    return service.get_prompts(part)


@router.get(
    "/prompts/{prompt_id}",
    response_model=SpeakingTestPrompt,
    summary="Get a single speaking prompt",
)
async def get_prompt(
    prompt_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Fetch a single speaking prompt by ID."""
    try:
        return service.get_prompt(prompt_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking prompt not found",
        )


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------
@router.post(
    "/start",
    response_model=SpeakingTestSessionResponse,
    summary="Start or resume a speaking test session",
)
async def start_test(
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Start a new test session or resume the existing in-progress one."""
    return service.start_test(user_id)


@router.get(
    "/session",
    response_model=SpeakingTestSessionResponse,
    summary="Get current in-progress session (resume)",
)
async def get_current_session(
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Fetch the user's current in-progress test session with responses."""
    session = service.get_current_session(user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active speaking test session",
        )
    return session


@router.get(
    "/sessions",
    response_model=SpeakingTestSessionListResponse,
    summary="List all speaking test sessions",
)
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """List the current user's test sessions (most recent first)."""
    return service.list_sessions(user_id, limit)


@router.get(
    "/sessions/{session_id}",
    response_model=SpeakingTestSessionResponse,
    summary="Get a speaking test session with responses",
)
async def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Fetch a session with all its responses (owner-scoped)."""
    try:
        return service.get_session(user_id, session_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test session not found",
        )


@router.get(
    "/sessions/{session_id}/responses",
    response_model=SpeakingTestResponseListResponse,
    summary="List all responses for a session",
)
async def list_responses_route(
    session_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """List all responses recorded for a session."""
    try:
        return service.list_responses(user_id, session_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test session not found",
        )


@router.post(
    "/sessions/{session_id}/advance",
    response_model=SpeakingTestSessionResponse,
    summary="Advance to the next speaking part",
)
async def advance_part(
    session_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Advance the session from the current part to the next (Part 1→2→3)."""
    try:
        return service.advance_part(user_id, session_id)
    except ValidationError:
        raise
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test session not found",
        )


@router.post(
    "/sessions/{session_id}/complete",
    response_model=SpeakingTestSessionResponse,
    summary="Complete the speaking test",
)
async def complete_test(
    session_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Mark the test as completed and log progress."""
    try:
        return service.complete_test(user_id, session_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test session not found",
        )


@router.post(
    "/sessions/{session_id}/abandon",
    response_model=SpeakingTestSessionResponse,
    summary="Abandon the speaking test (save for later)",
)
async def abandon_test(
    session_id: str,
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Mark the session as abandoned so it doesn't show as in-progress."""
    try:
        return service.abandon_test(user_id, session_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test session not found",
        )


# ---------------------------------------------------------------------------
# Response lifecycle
# ---------------------------------------------------------------------------
@router.post(
    "/responses",
    response_model=SpeakingTestResponseResponse,
    summary="Start a per-question response",
)
async def start_response(
    data: ResponseStartRequest,
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Start (or resume) a recorded response for a specific prompt."""
    return service.start_response(user_id, data.session_id, data.prompt_id, data.part)


@router.get(
    "/responses/{response_id}",
    response_model=SpeakingTestResponseResponse,
    summary="Get a single response",
)
async def get_response(
    response_id: str,
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Fetch a single recorded response (owner-scoped)."""
    try:
        return service.get_response(user_id, session_id, response_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test response not found",
        )


@router.post(
    "/responses/{response_id}/save",
    response_model=SpeakingTestResponseResponse,
    summary="Save recording metadata (auto-save + explicit save)",
)
async def save_response(
    response_id: str,
    data: SpeakingTestResponseSaveRequest,
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Save the audio URL, duration, transcript, and saved flag for a response."""
    try:
        return service.save_response(
            user_id,
            session_id,
            response_id,
            data.audio_url,
            data.duration_seconds,
            data.transcript,
            data.is_saved,
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test response not found",
        )


@router.post(
    "/responses/{response_id}/complete",
    response_model=SpeakingTestResponseResponse,
    summary="Mark a response as complete",
)
async def complete_response(
    response_id: str,
    session_id: str = Query(...),
    data: SpeakingTestResponseSaveRequest | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
    pipeline: SpeakingAudioPipelineService = Depends(get_speaking_audio_pipeline_service),
):
    """Finalize a response (save metadata + mark as done) and, when a
    recording was uploaded, submit it to the audio processing pipeline so the
    transcript is generated asynchronously."""
    try:
        saved = service.save_response(
            user_id,
            session_id,
            response_id,
            data.audio_url if data else "",
            data.duration_seconds if data else 0,
            data.transcript if data else "",
            is_saved=True,
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test response not found",
        )

    # Kick off the audio processing pipeline (async transcription).
    if saved and saved.get("audio_url"):
        try:
            pipeline.submit_response(
                user_id,
                response_id,
                session_id,
                saved.get("audio_url") or "",
                int(saved.get("duration_seconds") or 0),
                background_tasks=background_tasks,
            )
        except (ValidationError, NotFoundError):
            # The response is still complete; pipeline issues are non-fatal.
            pass
    return saved


@router.delete(
    "/responses/{response_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a response (re-record)",
)
async def delete_response(
    response_id: str,
    session_id: str = Query(...),
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Delete a recorded response so it can be re-recorded."""
    try:
        service.delete_response(user_id, session_id, response_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test response not found",
        )


# ---------------------------------------------------------------------------
# Audio upload
# ---------------------------------------------------------------------------
@router.post(
    "/upload",
    response_model=AudioUploadResponse,
    summary="Upload an audio blob to storage",
)
async def upload_audio(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Upload a recorded audio blob to Supabase Storage; returns the public URL.

    Validates the file type and size before it is stored; raises a 400
    ValidationError envelope for rejected uploads.
    """
    import uuid as _uuid
    data = await file.read()
    # Validate file type + size (raises ValidationError → 400 envelope).
    ext = validate_audio_file(file.filename or "", file.content_type, len(data))
    filename = f"{_uuid.uuid4().hex}.{ext}"
    try:
        return service.upload_audio(user_id, filename, data)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Audio storage is not available",
        )


# ---------------------------------------------------------------------------
# Progress (resume)
# ---------------------------------------------------------------------------
@router.get(
    "/progress",
    response_model=SpeakingTestProgressResponse,
    summary="Get current speaking test progress (for resume)",
)
async def get_progress(
    user_id: str = Depends(get_current_user),
    service: SpeakingTestService = Depends(get_speaking_test_service),
):
    """Return the user's current test progress across all three parts."""
    return service.get_progress(user_id)


# ---------------------------------------------------------------------------
# Audio processing pipeline (transcription)
# ---------------------------------------------------------------------------
@router.post(
    "/responses/{response_id}/submit",
    response_model=SpeakingEvaluationResponse,
    summary="Submit a response's recording to the audio processing pipeline",
)
async def submit_response_audio(
    response_id: str,
    data: SpeakingAudioSubmitRequest,
    session_id: str = Query(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: str = Depends(get_current_user),
    pipeline: SpeakingAudioPipelineService = Depends(get_speaking_audio_pipeline_service),
):
    """Submit the recording for this response to the pipeline. Transcription
    runs asynchronously — poll GET /responses/{id}/evaluation for status."""
    try:
        return pipeline.submit_response(
            user_id,
            response_id,
            session_id,
            data.audio_url,
            data.duration_seconds,
            background_tasks=background_tasks,
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking test response not found",
        )
    except ValidationError:
        raise


@router.get(
    "/responses/{response_id}/evaluation",
    response_model=SpeakingEvaluationResponse,
    summary="Get the evaluation record for a response",
)
async def get_response_evaluation(
    response_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: str = Depends(get_current_user),
    pipeline: SpeakingAudioPipelineService = Depends(get_speaking_audio_pipeline_service),
):
    """Fetch the evaluation for a response.

    Once transcription is ``completed`` (transcript present), the first read
    lazily enqueues the AI Speaking evaluation (Phase 10) so the assessment is
    ready on the next poll.
    """
    try:
        return pipeline.ensure_evaluation_by_response(
            user_id, response_id, background_tasks=background_tasks
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No evaluation record for this response",
        )


@router.get(
    "/evaluations",
    response_model=SpeakingEvaluationListResponse,
    summary="List the user's speaking evaluations",
)
async def list_evaluations(
    limit: int = Query(50, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    pipeline: SpeakingAudioPipelineService = Depends(get_speaking_audio_pipeline_service),
):
    """List the current user's audio evaluations (most recent first)."""
    return pipeline.list_evaluations(user_id, limit)


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=SpeakingEvaluationResponse,
    summary="Get a single speaking evaluation",
)
async def get_evaluation(
    evaluation_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: str = Depends(get_current_user),
    pipeline: SpeakingAudioPipelineService = Depends(get_speaking_audio_pipeline_service),
):
    """Fetch a single evaluation.

    Lazily enqueues the AI Speaking evaluation (Phase 10) when transcription is
    complete but the assessment has not yet been generated.
    """
    try:
        return pipeline.ensure_evaluation(
            user_id, evaluation_id, background_tasks=background_tasks
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking evaluation not found",
        )


@router.post(
    "/evaluations/{evaluation_id}/retry",
    response_model=SpeakingEvaluationResponse,
    summary="Retry a failed transcription",
)
async def retry_evaluation(
    evaluation_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: str = Depends(get_current_user),
    pipeline: SpeakingAudioPipelineService = Depends(get_speaking_audio_pipeline_service),
):
    """Re-enqueue a failed evaluation for transcription (no re-upload)."""
    try:
        return pipeline.retry_evaluation(
            user_id, evaluation_id, background_tasks=background_tasks
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking evaluation not found",
        )
    except ValidationError:
        raise


@router.post(
    "/evaluations/{evaluation_id}/evaluate",
    response_model=SpeakingEvaluationResponse,
    summary="Generate the AI Speaking evaluation for a transcribed response",
)
async def evaluate_transcript(
    evaluation_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: str = Depends(get_current_user),
    pipeline: SpeakingAudioPipelineService = Depends(get_speaking_audio_pipeline_service),
):
    """Run the AI Speaking evaluation on this response's transcript.

    Transcription must be ``completed`` before an assessment can be generated.
    The evaluation is owner-scoped and idempotent: re-running it after a band is
    already present is a no-op returning the existing assessment.
    """
    try:
        return await pipeline.evaluate_transcript(
            user_id, evaluation_id, background_tasks=background_tasks
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking evaluation not found",
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc) or "Transcript is required before evaluation",
        )
