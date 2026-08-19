"""
Tests for the Speaking Test Workspace service.

Validates:
  - Prompt fetching (all parts, single part, invalid part, sorting)
  - Prompt lookup (found, not found)
  - Session start (new session, resume existing)
  - Session retrieval, listing
  - Part advancement (Part 1→2→3, cannot exceed Part 3)
  - Test completion (marks session, logs progress)
  - Test abandon
  - Response lifecycle: start (create, resume), save, delete, get, list
  - Owner-scoping (response must belong to session)
  - Audio upload
  - Progress computation (resume helper)
"""
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.services.speaking_test_service import SpeakingTestService

# ─── Fixtures ────────────────────────────────────────────────────────────

def _make_service():
    """Create a SpeakingTestService with fully-mocked dependencies."""
    svc = SpeakingTestService(MagicMock())
    svc.repo = MagicMock()
    svc.storage = MagicMock()
    svc.prompt_repo = MagicMock()
    return svc


def _make_prompt(
    pid="prompt-1",
    part="part_1",
    title="Sample Question",
    prompt_text="Tell me about yourself.",
    prep=0,
    speak=60,
    difficulty=3,
):
    return {
        "id": pid,
        "part": part,
        "title": title,
        "prompt_text": prompt_text,
        "prep_time_seconds": prep,
        "speak_time_seconds": speak,
        "difficulty": difficulty,
        "topics": ["topic-a"],
        "follow_up": "Why?",
    }


def _make_session(sid="session-1", uid="user-123", part="part_1", status="in_progress"):
    return {
        "id": sid,
        "user_id": uid,
        "current_part": part,
        "status": status,
        "started_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:10:00Z",
        "completed_at": None,
    }


def _make_response(
    rid="resp-1",
    sid="session-1",
    uid="user-123",
    pid="prompt-1",
    part="part_1",
    title="Sample",
    audio_url="https://example.com/audio.webm",
    duration=60,
    transcript="Hello world.",
    is_saved=True,
):
    return {
        "id": rid,
        "session_id": sid,
        "user_id": uid,
        "prompt_id": pid,
        "part": part,
        "title": title,
        "prompt_text": "Tell me about yourself.",
        "prep_time_seconds": 0,
        "speak_time_seconds": 60,
        "audio_url": audio_url,
        "duration_seconds": duration,
        "transcript": transcript,
        "is_saved": is_saved,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:02:00Z",
    }


# ─── Prompts ─────────────────────────────────────────────────────────────

def test_get_prompts_all_parts():
    svc = _make_service()
    svc.repo.get_prompts = MagicMock(return_value=[
        _make_prompt("p1", "part_1", "Q1"),
        _make_prompt("p2", "part_2", "Q2", prep=60),
    ])
    result = svc.get_prompts(None)
    assert result["part"] == "all"
    assert result["total"] == 2
    assert result["prompts"][0]["id"] == "p1"
    assert result["prompts"][1]["prep_time_seconds"] == 60


def test_get_prompts_filtered_by_part():
    svc = _make_service()
    svc.repo.get_prompts = MagicMock(return_value=[
        _make_prompt("p1", "part_2", "Describe a place"),
    ])
    result = svc.get_prompts("part_2")
    assert result["part"] == "part_2"
    assert result["total"] == 1
    assert svc.repo.get_prompts.call_args[0][0] == "part_2"


def test_get_prompts_sorts_by_difficulty():
    svc = _make_service()
    svc.repo.get_prompts = MagicMock(return_value=[
        _make_prompt("hard", difficulty=5),
        _make_prompt("easy", difficulty=1),
        _make_prompt("mid", difficulty=3),
    ])
    result = svc.get_prompts(None)
    assert [p["id"] for p in result["prompts"]] == ["easy", "mid", "hard"]


def test_get_prompts_invalid_part_raises():
    svc = _make_service()
    with pytest.raises(ValidationError):
        svc.get_prompts("part_99")


def test_get_prompts_empty_bank():
    svc = _make_service()
    svc.repo.get_prompts.return_value = []
    result = svc.get_prompts(None)
    assert result["total"] == 0
    assert result["prompts"] == []


def test_get_prompt_found():
    svc = _make_service()
    svc.repo.get_prompt.return_value = _make_prompt("p1", title="My Q")
    result = svc.get_prompt("p1")
    assert result["id"] == "p1"
    assert result["title"] == "My Q"


def test_get_prompt_not_found():
    svc = _make_service()
    svc.repo.get_prompt.return_value = None
    with pytest.raises(NotFoundError):
        svc.get_prompt("p999")


# ─── Session lifecycle ───────────────────────────────────────────────────

def test_start_test_creates_new_session():
    svc = _make_service()
    svc.repo.get_active_session.return_value = None
    svc.repo.create_session.return_value = _make_session()
    result = svc.start_test("user-123")
    assert result["id"] == "session-1"
    assert result["status"] == "in_progress"
    assert result["current_part"] == "part_1"
    assert result["responses"] == []


def test_start_test_resumes_existing_session():
    svc = _make_service()
    existing = _make_session()
    svc.repo.get_active_session.return_value = existing
    svc.repo.create_session.return_value = _make_session("new")
    result = svc.start_test("user-123")
    assert result["id"] == "session-1"
    svc.repo.create_session.assert_not_called()


def test_get_session_found():
    svc = _make_service()
    svc.repo.get_session.return_value = _make_session()
    svc.repo.list_responses.return_value = []
    result = svc.get_session("user-123", "session-1")
    assert result["id"] == "session-1"
    assert result["responses"] == []


def test_get_session_not_found():
    svc = _make_service()
    svc.repo.get_session.return_value = None
    with pytest.raises(NotFoundError):
        svc.get_session("user-123", "session-999")


def test_list_sessions():
    svc = _make_service()
    svc.repo.list_sessions.return_value = [
        _make_session("s1"),
        _make_session("s2"),
    ]
    svc.repo.list_responses.return_value = []
    result = svc.list_sessions("user-123", limit=10)
    assert result["total"] == 2
    assert len(result["results"]) == 2


def test_get_current_session_returns_none_when_no_active():
    svc = _make_service()
    svc.repo.get_active_session.return_value = None
    assert svc.get_current_session("user-123") is None


def test_get_current_session_returns_session():
    svc = _make_service()
    svc.repo.get_active_session.return_value = _make_session()
    svc.repo.list_responses.return_value = []
    result = svc.get_current_session("user-123")
    assert result is not None
    assert result["id"] == "session-1"


# ─── Part advancement ────────────────────────────────────────────────────

def test_advance_part_part1_to_part2():
    svc = _make_service()
    svc.repo.get_session.return_value = _make_session(part="part_1")
    svc.repo.update_session.return_value = _make_session(part="part_2")
    svc.repo.list_responses.return_value = []
    result = svc.advance_part("user-123", "session-1")
    assert result["current_part"] == "part_2"
    svc.repo.update_session.assert_called_once()
    assert svc.repo.update_session.call_args[0][2]["current_part"] == "part_2"


def test_advance_part_part3_raises_validation():
    svc = _make_service()
    svc.repo.get_session.return_value = _make_session(part="part_3")
    with pytest.raises(ValidationError):
        svc.advance_part("user-123", "session-1")


def test_advance_part_session_not_found():
    svc = _make_service()
    svc.repo.get_session.return_value = None
    with pytest.raises(NotFoundError):
        svc.advance_part("user-123", "session-999")


# ─── Completion ──────────────────────────────────────────────────────────

def test_complete_test_marks_completed_and_logs_progress():
    svc = _make_service()
    svc.repo.get_session.return_value = _make_session()
    svc.repo.update_session.return_value = _make_session(part="part_3", status="completed")
    svc.repo.list_responses.return_value = [_make_response(duration=60)]
    svc.db.execute.return_value = {"data": [], "error": None}

    with patch.object(SpeakingTestService, "_log_progress") as mock_log:
        result = svc.complete_test("user-123", "session-1")
    assert result["status"] == "completed"
    assert result["current_part"] == "part_3"
    svc.repo.update_session.assert_called_once()
    update_data = svc.repo.update_session.call_args[0][2]
    assert update_data["status"] == "completed"
    assert update_data["current_part"] == "part_3"
    mock_log.assert_called_once_with("user-123", "session-1")


def test_complete_test_not_found():
    svc = _make_service()
    svc.repo.get_session.return_value = None
    with pytest.raises(NotFoundError):
        svc.complete_test("user-123", "session-999")


def test_complete_test_logs_progress_failure_does_not_crash():
    svc = _make_service()
    svc.repo.get_session.return_value = _make_session()
    svc.repo.update_session.return_value = _make_session(part="part_3", status="completed")
    svc.repo.list_responses.return_value = []

    with patch.object(
        SpeakingTestService, "_log_progress", side_effect=RuntimeError("DB down")
    ):
        result = svc.complete_test("user-123", "session-1")
    assert result["status"] == "completed"


# ─── Abandon ─────────────────────────────────────────────────────────────

def test_abandon_test():
    svc = _make_service()
    svc.repo.get_session.return_value = _make_session()
    svc.repo.update_session.return_value = _make_session(status="abandoned")
    svc.repo.list_responses.return_value = []
    result = svc.abandon_test("user-123", "session-1")
    assert result["status"] == "abandoned"
    assert svc.repo.update_session.call_args[0][2]["status"] == "abandoned"


def test_abandon_test_not_found():
    svc = _make_service()
    svc.repo.get_session.return_value = None
    with pytest.raises(NotFoundError):
        svc.abandon_test("user-123", "session-999")


# ─── Response lifecycle ──────────────────────────────────────────────────

def test_start_response_creates_new():
    svc = _make_service()
    prompt = _make_prompt("p1", "part_1")
    svc.repo.get_session.return_value = _make_session()
    svc.repo.get_prompt.return_value = prompt
    svc.repo.get_response_by_prompt.return_value = None
    svc.repo.create_response.return_value = _make_response()

    result = svc.start_response("user-123", "session-1", "p1", "part_1")
    assert result["id"] == "resp-1"
    svc.repo.create_response.assert_called_once()
    call_data = svc.repo.create_response.call_args[0][1]
    assert call_data["prompt_id"] == "p1"
    assert call_data["part"] == "part_1"


def test_start_response_resumes_existing():
    svc = _make_service()
    prompt = _make_prompt("p1", "part_1")
    existing = _make_response("resp-1", pid="p1", part="part_1")
    svc.repo.get_session.return_value = _make_session()
    svc.repo.get_prompt.return_value = prompt
    svc.repo.get_response_by_prompt.return_value = existing

    result = svc.start_response("user-123", "session-1", "p1", "part_1")
    assert result["id"] == "resp-1"
    svc.repo.create_response.assert_not_called()


def test_start_response_invalid_part():
    svc = _make_service()
    with pytest.raises(ValidationError):
        svc.start_response("user-123", "session-1", "p1", "part_99")


def test_start_response_session_not_found():
    svc = _make_service()
    svc.repo.get_session.return_value = _make_response()
    svc.repo.get_session.return_value = None
    with pytest.raises(NotFoundError):
        svc.start_response("user-123", "session-999", "p1", "part_1")


def test_start_response_prompt_not_found():
    svc = _make_service()
    svc.repo.get_session.return_value = _make_session()
    svc.repo.get_prompt.return_value = None
    with pytest.raises(NotFoundError):
        svc.start_response("user-123", "session-1", "p999", "part_1")


def test_save_response_updates_metadata():
    svc = _make_service()
    prompt = _make_prompt("p1")
    svc.repo.get_response.return_value = _make_response()
    svc.repo.update_response.return_value = _make_response(
        audio_url="https://example.com/new-audio.webm",
        duration=120,
        transcript="Updated transcript.",
        is_saved=True,
    )
    svc.repo.get_prompt.return_value = prompt

    result = svc.save_response(
        "user-123", "session-1", "resp-1",
        "https://example.com/new-audio.webm", 120, "Updated transcript.", True,
    )
    assert result["audio_url"] == "https://example.com/new-audio.webm"
    assert result["duration_seconds"] == 120
    assert result["is_saved"] is True
    call_data = svc.repo.update_response.call_args[0][2]
    assert call_data["audio_url"] == "https://example.com/new-audio.webm"
    assert call_data["is_saved"] is True


def test_save_response_not_found():
    svc = _make_service()
    svc.repo.get_response.return_value = None
    with pytest.raises(NotFoundError):
        svc.save_response("user-123", "session-1", "resp-999", "", 0, "", False)


def test_save_response_wrong_session():
    svc = _make_service()
    resp = _make_response(sid="other-session")
    svc.repo.get_response.return_value = resp
    with pytest.raises(NotFoundError):
        svc.save_response("user-123", "session-1", "resp-1", "", 0, "", False)


def test_delete_response():
    svc = _make_service()
    svc.repo.get_response.return_value = _make_response()
    svc.repo.delete_response = MagicMock()
    svc.delete_response("user-123", "session-1", "resp-1")
    svc.repo.delete_response.assert_called_once_with("resp-1", "user-123")


def test_delete_response_not_found():
    svc = _make_service()
    svc.repo.get_response.return_value = None
    with pytest.raises(NotFoundError):
        svc.delete_response("user-123", "session-1", "resp-999")


def test_delete_response_wrong_session():
    svc = _make_service()
    resp = _make_response(sid="other-session")
    svc.repo.get_response.return_value = resp
    with pytest.raises(NotFoundError):
        svc.delete_response("user-123", "session-1", "resp-1")


def test_get_response_found():
    svc = _make_service()
    svc.repo.get_response.return_value = _make_response()
    svc.repo.get_prompt.return_value = _make_prompt("p1")
    result = svc.get_response("user-123", "session-1", "resp-1")
    assert result["id"] == "resp-1"


def test_get_response_not_found():
    svc = _make_service()
    svc.repo.get_response.return_value = None
    with pytest.raises(NotFoundError):
        svc.get_response("user-123", "session-1", "resp-999")


def test_get_response_wrong_session():
    svc = _make_service()
    resp = _make_response(sid="other-session")
    svc.repo.get_response.return_value = resp
    with pytest.raises(NotFoundError):
        svc.get_response("user-123", "session-1", "resp-1")


def test_list_responses():
    svc = _make_service()
    svc.repo.get_session.return_value = _make_session()
    svc.repo.list_responses.return_value = [
        _make_response("r1", part="part_1"),
        _make_response("r2", part="part_1"),
    ]
    svc.repo.get_prompt.return_value = _make_prompt("p1")

    result = svc.list_responses("user-123", "session-1")
    assert result["total"] == 2
    assert len(result["results"]) == 2


def test_list_responses_session_not_found():
    svc = _make_service()
    svc.repo.get_session.return_value = None
    with pytest.raises(NotFoundError):
        svc.list_responses("user-123", "session-999")


# ─── Audio upload ────────────────────────────────────────────────────────

def test_upload_audio():
    svc = _make_service()
    svc.storage.upload_audio.return_value = "https://cdn.example.com/audio.webm"
    data = b"fake-audio-data"
    result = svc.upload_audio("user-123", "test.webm", data)
    assert result["audio_url"] == "https://cdn.example.com/audio.webm"
    assert result["filename"] == "test.webm"
    assert result["size"] == len(data)
    svc.storage.upload_audio.assert_called_once_with("user-123", "test.webm", data)


def test_upload_audio_storage_failure():
    svc = _make_service()
    svc.storage.upload_audio.side_effect = NotFoundError("Audio storage not available")
    with pytest.raises(NotFoundError):
        svc.upload_audio("user-123", "test.webm", b"data")


# ─── Progress ────────────────────────────────────────────────────────────

def test_get_progress_no_active_session():
    svc = _make_service()
    svc.repo.get_active_session.return_value = None
    result = svc.get_progress("user-123")
    assert result["session"] is None
    assert result["total_responses"] == 0
    assert result["completed_parts"] == []


def test_get_progress_with_session():
    svc = _make_service()
    svc.repo.get_active_session.return_value = _make_session()
    svc.repo.list_responses.return_value = [
        _make_response("r1", part="part_1"),
        _make_response("r2", part="part_2"),
    ]
    svc.repo.get_prompts.return_value = [_make_prompt("p1"), _make_prompt("p2")]
    svc.repo.get_prompt.return_value = _make_prompt("p1")

    result = svc.get_progress("user-123")
    assert result["session"]["id"] == "session-1"
    assert result["total_responses"] == 2
    assert "part_1" in result["completed_parts"]
    assert "part_2" in result["completed_parts"]
    assert result["parts"]["part_1"]["completed"] == 1
    assert result["parts"]["part_1"]["total_prompts"] == 2


# ─── Internal helpers ────────────────────────────────────────────────────

def test_session_payload_includes_responses():
    svc = _make_service()
    svc.repo.list_responses.return_value = []
    result = svc._session_payload(_make_session(), "user-123", include_responses=True)
    assert result["responses"] == []


def test_response_payload_with_prompt():
    svc = _make_service()
    prompt = _make_prompt("p1", title="My Prompt")
    resp_row = _make_response(pid="p1", title="")
    result = svc._response_payload(resp_row, prompt)
    assert result["title"] == "My Prompt"
    assert result["prompt_text"] == "Tell me about yourself."


def test_response_payload_without_prompt_uses_row_data():
    svc = _make_service()
    resp_row = _make_response(title="Stored Title", pid=None)
    result = svc._response_payload(resp_row, None)
    assert result["title"] == "Stored Title"
    assert result["prompt_text"] == "Tell me about yourself."
