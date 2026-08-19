"""
Tests for the Speaking Audio Processing Pipeline.

Validates:
  - Audio file validation (allowed extension, max size, empty)
  - Speech-to-text service (mock provider, missing key, provider errors)
  - Pipeline submission (creates evaluation, idempotent reuse, re-queue failed)
  - Owner-scoping (response must belong to the user/session)
  - Async transcription (success stores transcript; failure retries → failed)
  - Original recording is preserved across the lifecycle
  - Retry logic (only failed evaluations retryable)
  - Read helpers (get / get-by-response / list)
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.services.speaking_audio_pipeline import SpeakingAudioPipelineService
from app.services.speech_to_text_service import (
    SpeechToTextService,
    TranscriptionError,
    validate_audio_file,
)

PUBLIC_URL = (
    "https://abc.supabase.co/storage/v1/object/public/"
    "speaking-tests/u1/abc123.webm"
)


# ─── Fixtures ────────────────────────────────────────────────────────────

def _eval(
    eid="eval1",
    status="queued",
    transcript="",
    audio_url=PUBLIC_URL,
    retry_count=0,
    error_message="",
):
    return {
        "id": eid,
        "user_id": "u1",
        "response_id": "resp1",
        "session_id": "sess1",
        "part": "part_1",
        "audio_url": audio_url,
        "audio_duration_seconds": 60,
        "file_size_bytes": 1000,
        "transcript": transcript,
        "provider": "mock:whisper-1",
        "model": "whisper-1",
        "status": status,
        "error_message": error_message,
        "retry_count": retry_count,
        "last_processed_at": None,
        "processed_at": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _make_response():
    return {
        "id": "resp1",
        "session_id": "sess1",
        "user_id": "u1",
        "part": "part_1",
    }


def _make_pipeline(stt=None):
    svc = SpeakingAudioPipelineService(MagicMock(), stt_service=stt)
    svc.repo = MagicMock()
    svc.storage = MagicMock()
    svc.response_repo = MagicMock()
    if stt is None:
        stt = MagicMock()
    svc.stt = stt
    svc.stt.provider = "mock"
    svc.stt.model = "whisper-1"
    svc.stt.retry_attempts = 0
    return svc


# ─── File validation ────────────────────────────────────────────────────

def test_validate_audio_file_valid_webm():
    assert validate_audio_file("rec.webm", "audio/webm", 1000) == "webm"


def test_validate_audio_file_valid_via_mime():
    assert validate_audio_file("recording", "audio/wav", 5000) == "wav"


def test_validate_audio_file_rejects_bad_extension():
    with pytest.raises(ValidationError):
        validate_audio_file("rec.exe", "application/x-msdownload", 1000)


def test_validate_audio_file_rejects_too_large():
    # 26 MB exceeds the 25 MB default limit.
    with pytest.raises(ValidationError):
        validate_audio_file("rec.webm", "audio/webm", 26 * 1024 * 1024)


def test_validate_audio_file_rejects_empty():
    with pytest.raises(ValidationError):
        validate_audio_file("rec.webm", "audio/webm", 0)


# ─── Speech-to-text service ─────────────────────────────────────────────

def test_stt_mock_provider_returns_transcript():
    stt = SpeechToTextService()
    stt.provider = "mock"
    result = asyncio.run(stt.transcribe(b"\x00\x01audio", "rec.webm", "audio/webm"))
    assert result["transcript"]
    assert result["provider"].startswith("mock")


def test_stt_missing_key_raises():
    stt = SpeechToTextService()
    stt.provider = "openai"
    stt.api_key = None
    with pytest.raises(TranscriptionError):
        asyncio.run(stt.transcribe(b"audio", "rec.webm", "audio/webm"))


# ─── Pipeline: submission ───────────────────────────────────────────────

def test_submit_creates_evaluation_and_enqueues():
    svc = _make_pipeline()
    svc.response_repo.get_response.return_value = _make_response()
    svc.storage.parse_public_url.return_value = ("speaking-tests", "u1/abc123.webm")
    svc.storage.download_audio.return_value = b"\x00" * 1000
    svc.repo.get_evaluation_by_response.return_value = None
    svc.repo.create_evaluation.return_value = _eval()

    bg = MagicMock()
    result = svc.submit_response(
        "u1", "resp1", "sess1", PUBLIC_URL, 60, background_tasks=bg
    )

    svc.repo.create_evaluation.assert_called_once()
    # Original recording URL is preserved in the record.
    created = svc.repo.create_evaluation.call_args[0][0]
    assert created["audio_url"] == PUBLIC_URL
    assert created["status"] == "queued"
    assert created["file_size_bytes"] == 1000
    bg.add_task.assert_called_once()
    assert result["status"] == "queued"


def test_submit_reuses_existing_active_evaluation():
    svc = _make_pipeline()
    svc.response_repo.get_response.return_value = _make_response()
    existing = _eval(status="transcribing")
    svc.repo.get_evaluation_by_response.return_value = existing

    result = svc.submit_response("u1", "resp1", "sess1", PUBLIC_URL, 60)

    svc.repo.create_evaluation.assert_not_called()
    assert result["status"] == "transcribing"


def test_submit_requeues_failed_evaluation():
    svc = _make_pipeline()
    svc.response_repo.get_response.return_value = _make_response()
    svc.repo.get_evaluation_by_response.return_value = _eval(status="failed")
    svc.repo.update_evaluation.return_value = _eval(status="queued")

    bg = MagicMock()
    result = svc.submit_response("u1", "resp1", "sess1", PUBLIC_URL, 60, background_tasks=bg)

    svc.repo.create_evaluation.assert_not_called()
    svc.repo.update_evaluation.assert_called_once()
    bg.add_task.assert_called_once()
    assert result["status"] == "queued"


def test_submit_response_not_found():
    svc = _make_pipeline()
    svc.response_repo.get_response.return_value = None
    with pytest.raises(NotFoundError):
        svc.submit_response("u1", "resp1", "sess1", PUBLIC_URL, 60)


def test_submit_wrong_session_rejected():
    svc = _make_pipeline()
    svc.response_repo.get_response.return_value = {**_make_response(), "session_id": "other"}
    with pytest.raises(NotFoundError):
        svc.submit_response("u1", "resp1", "sess1", PUBLIC_URL, 60)


def test_submit_missing_audio_rejected():
    svc = _make_pipeline()
    svc.response_repo.get_response.return_value = _make_response()
    with pytest.raises(ValidationError):
        svc.submit_response("u1", "resp1", "sess1", "", 60)


def test_submit_non_storage_url_rejected():
    svc = _make_pipeline()
    svc.response_repo.get_response.return_value = _make_response()
    svc.storage.parse_public_url.return_value = None
    svc.repo.get_evaluation_by_response.return_value = None
    with pytest.raises(ValidationError):
        svc.submit_response("u1", "resp1", "sess1", "https://evil.example/x", 60)


# ─── Pipeline: async transcription ──────────────────────────────────────

def test_run_transcription_success_stores_transcript():
    svc = _make_pipeline()
    svc.repo.get_evaluation_unscoped.return_value = _eval(status="queued", audio_url=PUBLIC_URL)
    svc.storage.download_audio.return_value = b"\x00audio"
    svc.stt.transcribe = AsyncMock(return_value={
        "transcript": "Hello, this is a sample answer.",
        "duration_seconds": 5.5,
    })
    svc.repo.update_evaluation_unscoped.return_value = _eval(
        status="completed", transcript="Hello, this is a sample answer."
    )

    result = asyncio.run(svc.run_transcription("eval1"))

    assert result["status"] == "completed"
    assert result["transcript"] == "Hello, this is a sample answer."
    # The original recording URL is preserved.
    assert result["audio_url"] == PUBLIC_URL


def test_run_transcription_failure_marks_failed_and_preserves_audio():
    svc = _make_pipeline()
    svc.repo.get_evaluation_unscoped.return_value = _eval(status="queued", audio_url=PUBLIC_URL)
    svc.storage.download_audio.return_value = b"\x00audio"
    # Single attempt (retry_attempts=0) for a fast test.
    svc.stt.transcribe = AsyncMock(side_effect=TranscriptionError("boom"))
    svc.repo.update_evaluation_unscoped.return_value = _eval(
        status="failed", error_message="boom", retry_count=0
    )

    result = asyncio.run(svc.run_transcription("eval1"))

    assert result["status"] == "failed"
    assert result["error_message"] == "boom"
    assert result["audio_url"] == PUBLIC_URL  # original recording preserved


def test_run_transcription_download_missing_marks_failed():
    svc = _make_pipeline()
    svc.repo.get_evaluation_unscoped.return_value = _eval(status="queued", audio_url=PUBLIC_URL)
    svc.storage.download_audio.side_effect = NotFoundError("missing")
    svc.repo.update_evaluation_unscoped.return_value = _eval(status="failed", error_message="missing")

    result = asyncio.run(svc.run_transcription("eval1"))

    assert result["status"] == "failed"


# ─── Pipeline: retry ────────────────────────────────────────────────────

def test_retry_evaluation_requeues_failed():
    svc = _make_pipeline()
    svc.repo.get_evaluation.return_value = _eval(status="failed")
    svc.repo.update_evaluation.return_value = _eval(status="queued")
    bg = MagicMock()

    result = svc.retry_evaluation("u1", "eval1", background_tasks=bg)

    assert result["status"] == "queued"
    bg.add_task.assert_called_once()


def test_retry_evaluation_only_failed():
    svc = _make_pipeline()
    svc.repo.get_evaluation.return_value = _eval(status="completed")
    with pytest.raises(ValidationError):
        svc.retry_evaluation("u1", "eval1")


def test_retry_evaluation_not_found():
    svc = _make_pipeline()
    svc.repo.get_evaluation.return_value = None
    with pytest.raises(NotFoundError):
        svc.retry_evaluation("u1", "eval1")


# ─── Pipeline: reads ────────────────────────────────────────────────────

def test_get_evaluation_ok():
    svc = _make_pipeline()
    svc.repo.get_evaluation.return_value = _eval(status="completed")
    result = svc.get_evaluation("u1", "eval1")
    assert result["id"] == "eval1"


def test_get_evaluation_not_found():
    svc = _make_pipeline()
    svc.repo.get_evaluation.return_value = None
    with pytest.raises(NotFoundError):
        svc.get_evaluation("u1", "eval1")


def test_get_evaluation_by_response():
    svc = _make_pipeline()
    svc.repo.get_evaluation_by_response.return_value = _eval(status="transcribing")
    result = svc.get_evaluation_by_response("u1", "resp1")
    assert result["status"] == "transcribing"


def test_get_evaluation_by_response_not_found():
    svc = _make_pipeline()
    svc.repo.get_evaluation_by_response.return_value = None
    with pytest.raises(NotFoundError):
        svc.get_evaluation_by_response("u1", "resp1")


def test_list_evaluations():
    svc = _make_pipeline()
    svc.repo.list_evaluations.return_value = [_eval("e1"), _eval("e2", status="completed")]
    result = svc.list_evaluations("u1")
    assert result["total"] == 2
    assert len(result["results"]) == 2
# ─── AI Speaking Evaluation (Phase 10) ───────────────────────────────


def _transcribed_eval(**overrides):
    """An evaluation that has completed transcription (ready for AI scoring)."""
    data = {
        "id": "eval1",
        "user_id": "u1",
        "response_id": "resp1",
        "session_id": "sess1",
        "part": "part_1",
        "audio_url": PUBLIC_URL,
        "audio_duration_seconds": 60,
        "file_size_bytes": 1000,
        "transcript": (
            "I really enjoy reading books in my spare time, especially fiction "
            "novels that transport me to different worlds and introduce me to "
            "new ideas. When I am not working I like to go hiking in the hills "
            "near my home with my friends, and we always bring a thermos of tea "
            "because the walks can last several hours and the weather here is "
            "often quite cold in the evenings. I also play the guitar and try "
            "to learn a new song every week, which helps me relax after a long "
            "day at the office when I feel a little tired but still want to "
            "stay creative with my time so that I never waste a single evening."
        ),
        "provider": "mock:whisper-1",
        "model": "whisper-1",
        "status": "completed",
        "error_message": "",
        "retry_count": 0,
        "last_processed_at": "2026-01-01T00:00:00Z",
        "processed_at": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    data.update(overrides)
    return data


def _make_ai_pipeline():
    """Pipeline with a mocked AI service so no network calls happen."""
    svc = _make_pipeline()
    svc.ai_service = MagicMock()
    svc.ai_service.analyze_speaking = AsyncMock()
    # Echo back the computed fields dict so the projected response reflects the
    # real AI/fallback computation rather than a fixed override.
    svc.repo.update_evaluation.side_effect = lambda eid, uid, fields: fields
    return svc


def test_evaluate_transcript_success_with_ai():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = _transcribed_eval()
    svc.ai_service.analyze_speaking.return_value = {
        "band_score": 8.0,
        "feedback": "Strong overall performance with good range.",
        "corrections": ["Use 'moreover' to extend ideas"],
    }

    result = asyncio.run(svc.evaluate_transcript("u1", "eval1"))

    svc.ai_service.analyze_speaking.assert_awaited_once()
    svc.repo.update_evaluation.assert_called_once()
    assert result["overall_band"] == 8.0
    assert result["source"] == "ai"
    assert result["is_estimate"] is True
    assert len(result["criteria"]) == 4
    assert abs(result["criteria"]["fluency_coherence"]["band"] - 8.0) <= 0.5
    assert result["corrections"] == ["Use 'moreover' to extend ideas"]
    assert result["evaluation_version"] == 1


def test_evaluate_transcript_fallback_without_ai_result():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = _transcribed_eval()
    # AI service returns empty result -> deterministic fallback path.
    svc.ai_service.analyze_speaking.return_value = {}

    result = asyncio.run(svc.evaluate_transcript("u1", "eval1"))

    assert result["overall_band"] == 7.0
    assert result["source"] == "deterministic_fallback"
    assert result["confidence"] is not None
    for key in (
        "fluency_coherence",
        "lexical_resource",
        "grammatical_range_accuracy",
        "pronunciation",
    ):
        assert key in result["criteria"]


def test_evaluate_transcript_idempotent():
    """Re-evaluating an already-scored record must not call the AI again."""
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = _transcribed_eval(
        overall_band=7.5, source="ai", evaluation_version=1
    )

    result = asyncio.run(svc.evaluate_transcript("u1", "eval1"))

    svc.ai_service.analyze_speaking.assert_not_awaited()
    svc.repo.update_evaluation.assert_not_called()
    assert result["overall_band"] == 7.5
    assert result["evaluation_version"] == 1


def test_evaluate_transcript_requires_transcription():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = _eval(status="queued", transcript="")

    with pytest.raises(ValidationError):
        asyncio.run(svc.evaluate_transcript("u1", "eval1"))

    svc.ai_service.analyze_speaking.assert_not_awaited()
    svc.repo.update_evaluation.assert_not_called()


def test_evaluate_transcript_owner_scoped():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = None

    with pytest.raises(NotFoundError):
        asyncio.run(svc.evaluate_transcript("other_user", "eval1"))

    svc.ai_service.analyze_speaking.assert_not_awaited()


def test_evaluate_transcript_ai_exception_falls_back():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = _transcribed_eval()
    svc.ai_service.analyze_speaking.side_effect = RuntimeError("provider down")

    result = asyncio.run(svc.evaluate_transcript("u1", "eval1"))

    assert result["source"] == "deterministic_fallback"
    assert result["overall_band"] == 7.0


def test_ensure_evaluation_lazy_enqueue_on_read():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = _transcribed_eval()
    bg = MagicMock()

    result = svc.ensure_evaluation("u1", "eval1", background_tasks=bg)

    bg.add_task.assert_called_once_with(svc.evaluate_transcript, "u1", "eval1")
    # The pending record is returned immediately (not yet scored).
    assert "overall_band" in result
    assert result["overall_band"] is None


def test_ensure_evaluation_skips_when_already_scored():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = _transcribed_eval(
        overall_band=8.0, source="ai", evaluation_version=1
    )
    bg = MagicMock()

    result = svc.ensure_evaluation("u1", "eval1", background_tasks=bg)

    bg.add_task.assert_not_called()
    assert result["overall_band"] == 8.0


def test_ensure_evaluation_not_transcribed_skips_enqueue():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = _eval(status="queued", transcript="")
    bg = MagicMock()

    result = svc.ensure_evaluation("u1", "eval1", background_tasks=bg)

    bg.add_task.assert_not_called()


def test_ensure_evaluation_by_response_enqueue():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation_by_response.return_value = _transcribed_eval()
    bg = MagicMock()

    result = svc.ensure_evaluation_by_response("u1", "resp1", background_tasks=bg)

    bg.add_task.assert_called_once()
    assert result["overall_band"] is None


def test_evaluate_transcript_criteria_within_band_range():
    svc = _make_ai_pipeline()
    svc.repo.get_evaluation.return_value = _transcribed_eval()
    svc.ai_service.analyze_speaking.return_value = {}

    result = asyncio.run(svc.evaluate_transcript("u1", "eval1"))

    overall = result["overall_band"]
    for item in result["criteria"].values():
        assert abs(item["band"] - overall) <= 0.5
        assert 0.0 <= item["band"] <= 9.0
