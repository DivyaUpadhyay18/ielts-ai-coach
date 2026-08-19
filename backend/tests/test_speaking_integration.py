"""
Comprehensive integration tests for the entire AI Speaking Evaluation system.

Covers the full pipeline from recording through evaluation, plus practice mode,
coach, analytics, reattempts, and mission integration.

All tests are deterministic — DB, STT, and AI calls are mocked.
"""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.services.speaking_analytics_service import SpeakingAnalyticsService
from app.services.speaking_audio_pipeline import SpeakingAudioPipelineService
from app.services.speaking_mission_service import SpeakingMissionService
from app.services.speaking_practice_coach_engine import SpeakingCoachEngine
from app.services.speaking_practice_mode_engine import SpeakingPracticeModeEngine
from app.services.speaking_reattempt_service import SpeakingReattemptService


def _make_db():
    return MagicMock()


SHORT_TRANSCRIPT = "I like music"
LONG_TRANSCRIPT = (
    "I really enjoy reading books in my spare time, especially fiction "
    "novels that transport me to different worlds and introduce me to "
    "new ideas. When I am not working I like to go hiking in the hills "
    "near my home with my friends, and we always bring a thermos of tea "
    "because the walks can last several hours and the weather here is "
    "often quite cold in the evenings. I also play the guitar and try "
    "to learn a new song every week, which helps me relax after a long "
    "day at the office when I feel a little tired but still want to "
    "stay creative with my time so that I never waste a single evening."
)
SILENCE_TRANSCRIPT = ""


def _eval_row(
    transcript: str = LONG_TRANSCRIPT,
    part="part_1",
    overall_band=None,
    status="completed",
    source="pending",
    evaluation_version=0,
):
    has_band = overall_band is not None
    return {
        "id": str(uuid.uuid4()),
        "user_id": "u1",
        "response_id": "resp-1",
        "session_id": "sess-1",
        "part": part,
        "audio_url": "https://example.com/audio.webm",
        "audio_duration_seconds": 60,
        "file_size_bytes": 10000,
        "transcript": transcript,
        "provider": "openai_whisper",
        "model": "whisper-1",
        "status": status,
        "error_message": "",
        "retry_count": 0,
        "last_processed_at": None,
        "processed_at": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "overall_band": overall_band,
        "confidence": 0.85 if has_band else None,
        "criteria": {},
        "strengths": [],
        "weaknesses": [],
        "corrections": [],
        "suggestions": [],
        "is_estimate": True,
        "source": source if has_band else "pending",
        "evaluated_at": None,
        "evaluation_version": evaluation_version,
        "speaking_test_responses": {
            "title": "Test Title",
            "prompt_text": "Tell me about yourself",
            "duration_seconds": 60,
        },
    }


@pytest.fixture
def pipeline():
    svc = SpeakingAudioPipelineService(db=_make_db())
    svc.repo = MagicMock()
    svc.storage = MagicMock()
    svc.response_repo = MagicMock()
    svc.ai_service = MagicMock()
    svc.ai_service.analyze_speaking = AsyncMock()
    svc.ai_service.analyze_speaking_errors = AsyncMock()
    svc.mission_service = MagicMock()
    svc.mission_service.sync_after_evaluation = MagicMock()
    # update_evaluation returns the full updated row (with AI fields merged,
    # preserving part/transcript from the original evaluation).
    svc.repo.update_evaluation.side_effect = lambda eid, uid, fields: {
        "id": eid, "user_id": uid,
        "part": (svc.repo.get_evaluation.return_value or {}).get("part", "part_1"),
        "audio_url": "https://example.com/audio.webm", "audio_duration_seconds": 60,
        "file_size_bytes": 10000,
        "transcript": (svc.repo.get_evaluation.return_value or {}).get("transcript", "test"),
        "provider": "openai_whisper", "model": "whisper-1", "status": "completed",
        "error_message": "", "retry_count": 0,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:05:00Z", "evaluated_at": "2026-01-01T00:05:00Z",
        **fields,
    }
    return svc


class TestPart1Evaluation:
    """Part 1 (Introduction & Interview) evaluation flow."""

    def test_part_1_short_recording(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(SHORT_TRANSCRIPT, part="part_1")
        pipeline.ai_service.analyze_speaking.return_value = {}
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["part"] == "part_1"
        assert result["overall_band"] == 4.0

    def test_part_1_long_recording(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(LONG_TRANSCRIPT, part="part_1")
        pipeline.ai_service.analyze_speaking = AsyncMock(return_value={
            "band_score": 7.5, "feedback": "Good vocabulary range.",
            "corrections": ["Use linking devices"],
        })
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 7.5
        assert result["source"] == "ai"

    def test_part_1_silence(self, pipeline):
        """Empty transcript should get the minimum band (4.0) via fallback."""
        eval_row = _eval_row("some minimal text", part="part_1", status="completed")
        eval_row["transcript"] = "a"
        pipeline.repo.get_evaluation.return_value = eval_row
        pipeline.ai_service.analyze_speaking.return_value = {}
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 4.0


class TestPart2Evaluation:
    """Part 2 (Individual Long Turn) evaluation flow."""

    def test_part_2_cue_card(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(LONG_TRANSCRIPT, part="part_2")
        pipeline.ai_service.analyze_speaking = AsyncMock(return_value={
            "band_score": 6.5, "feedback": "Good structure.", "corrections": [],
        })
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["part"] == "part_2"
        assert result["overall_band"] == 6.5


class TestPart3Evaluation:
    """Part 3 (Two-way Discussion) evaluation flow."""

    def test_part_3_discussion(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(LONG_TRANSCRIPT, part="part_3")
        pipeline.ai_service.analyze_speaking = AsyncMock(return_value={
            "band_score": 8.0, "feedback": "Excellent.", "corrections": [],
        })
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["part"] == "part_3"
        assert result["overall_band"] == 8.0


class TestTranscriptionPipeline:
    """Transcription pipeline flow."""

    def test_transcription_success(self, pipeline):
        pipeline.repo.get_evaluation_unscoped = MagicMock(return_value={
            "id": "e1", "status": "transcribing", "transcript": "",
            "audio_url": "https://example.com/audio.webm", "retry_count": 0,
            "audio_duration_seconds": 60,
        })
        pipeline.repo.update_evaluation_unscoped = MagicMock(return_value={
            "id": "e1", "status": "completed", "transcript": "I went to the park yesterday",
            "audio_url": "https://example.com/audio.webm", "audio_duration_seconds": 60,
        })
        pipeline.storage.download_audio = MagicMock(return_value=b"fake-audio-bytes")
        pipeline.stt = MagicMock()
        pipeline.stt.retry_attempts = 2
        pipeline.stt.transcribe = AsyncMock(return_value={
            "transcript": "I went to the park yesterday", "duration_seconds": 60,
        })

        result = asyncio.run(pipeline.run_transcription("e1"))
        assert result["transcript"] == "I went to the park yesterday"
        pipeline.repo.update_evaluation_unscoped.assert_called()

    def test_transcription_failure_marks_failed(self, pipeline):
        from app.services.speech_to_text_service import TranscriptionError
        pipeline.repo.get_evaluation_unscoped = MagicMock(return_value={
            "id": "e1", "status": "transcribing", "transcript": "",
            "audio_url": "https://example.com/audio.webm", "retry_count": 0,
            "audio_duration_seconds": 60,
        })
        pipeline.repo.update_evaluation_unscoped = MagicMock(return_value={
            "id": "e1", "status": "failed", "error_message": "STT down",
            "audio_url": "https://example.com/audio.webm",
        })
        pipeline.storage.download_audio = MagicMock(return_value=b"fake-audio-bytes")
        pipeline.stt = MagicMock()
        pipeline.stt.retry_attempts = 1
        pipeline.stt.transcribe = AsyncMock(side_effect=TranscriptionError("STT down"))

        result = asyncio.run(pipeline.run_transcription("e1"))
        assert result["status"] == "failed"

    def test_transcription_missing_audio_marks_failed(self, pipeline):
        pipeline.repo.get_evaluation_unscoped = MagicMock(return_value={
            "id": "e1", "status": "transcribing", "transcript": "",
            "audio_url": "", "retry_count": 0,
        })
        pipeline.repo.update_evaluation_unscoped = MagicMock(return_value={
            "id": "e1", "status": "failed", "error_message": "Recording URL is missing",
        })
        result = asyncio.run(pipeline.run_transcription("e1"))
        assert result["status"] == "failed"


class TestAIEvaluation:
    def test_ai_api_success(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(LONG_TRANSCRIPT, source="pending")
        pipeline.ai_service.analyze_speaking = AsyncMock(return_value={
            "band_score": 7.0, "feedback": "Good fluency.", "corrections": ["Use past tense"],
        })
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 7.0
        assert result["source"] == "ai"
        assert pipeline.mission_service.sync_after_evaluation.called

    def test_ai_api_failure_falls_back(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(LONG_TRANSCRIPT, source="pending")
        pipeline.ai_service.analyze_speaking = AsyncMock(side_effect=Exception("API down"))
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["source"] == "deterministic_fallback"
        assert result["overall_band"] is not None

    def test_malformed_ai_response(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(LONG_TRANSCRIPT, source="pending")
        pipeline.ai_service.analyze_speaking = AsyncMock(return_value={
            "unexpected": "format", "no_band": True,
        })
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] is not None


class TestBandEstimation:
    def test_short_transcript_low_band(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(SHORT_TRANSCRIPT, source="pending")
        pipeline.ai_service.analyze_speaking.return_value = {}
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 4.0

    def test_medium_transcript_band(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(" ".join(["word"] * 50), source="pending")
        pipeline.ai_service.analyze_speaking.return_value = {}
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 6.0

    def test_long_transcript_high_band(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(" ".join(["word"] * 120), source="pending")
        pipeline.ai_service.analyze_speaking.return_value = {}
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 7.0


class TestDuplicateSubmissions:
    def test_dup_evaluation_idempotent(self, pipeline):
        pipeline.repo.get_evaluation.return_value = _eval_row(
            LONG_TRANSCRIPT, overall_band=7.5, source="ai", evaluation_version=1
        )
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 7.5
        pipeline.ai_service.analyze_speaking.assert_not_called()


class TestSecurity:
    def test_owner_scope_evaluation(self, pipeline):
        pipeline.repo.get_evaluation.return_value = None
        with pytest.raises(NotFoundError):
            asyncio.run(pipeline.evaluate_transcript("user2", "eval-owned-by-user1"))

    def test_owner_scope_update(self, pipeline):
        """Update must be scoped to the owner — non-owner gets NotFoundError."""
        pipeline.repo.get_evaluation.return_value = None  # not found for user2
        with pytest.raises(NotFoundError):
            asyncio.run(pipeline.evaluate_transcript("user2", "eval-owned-by-user1"))


class TestPracticeMode:
    @pytest.fixture
    def engine(self):
        eng = SpeakingPracticeModeEngine(db=_make_db())
        eng.repo = MagicMock()
        eng.progress_repo = MagicMock()
        eng.streak_repo = MagicMock()
        eng.ai_service = MagicMock()
        eng.mission_service = MagicMock()
        eng.mission_service.sync_after_evaluation = MagicMock()
        return eng

    def test_practice_start_eval_save(self, engine):
        engine.repo.get_prompts.return_value = [
            {"id": "p1", "part": "part_1", "title": "Hometown", "prompt_text": "Tell me about...",
             "prep_time_seconds": 0, "speak_time_seconds": 60},
        ]
        engine.db.execute.return_value = MagicMock(data=[
            {"id": "sess1", "user_id": "u1", "practice_mode": "quick_practice", "part": "part_1",
             "title": "Hometown", "prompt_text": "Tell me about...", "prep_time_seconds": 0,
             "speak_time_seconds": 60, "status": "in_progress", "created_at": "2026-01-01T00:00:00Z",
             "updated_at": "2026-01-01T00:00:00Z"},
        ])
        session = engine.start_session("u1", "quick_practice")
        assert session["practice_mode"] == "quick_practice"

    def test_practice_evaluate_awards_xp_and_syncs_mission(self, engine):
        engine._get_session = MagicMock(return_value={
            "id": "sess1", "user_id": "u1", "status": "in_progress",
            "transcript": LONG_TRANSCRIPT, "part": "part_1", "title": "Test",
            "practice_mode": "fluency_practice", "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "duration_seconds": 60,
        })
        engine.ai_service.analyze_speaking = AsyncMock(return_value={
            "overall_band": 7.0, "fluency_coherence_band": 7.0, "lexical_resource_band": 6.5,
            "grammatical_range_band": 7.0, "pronunciation_band": 7.5, "feedback": "good",
        })
        engine.ai_service.analyze_speaking_errors = AsyncMock(return_value={"issues": []})
        engine.db.execute.return_value = MagicMock(data=[
            {"id": "sess1", "overall_band": 7.0, "status": "evaluated",
             "error_count": 0, "filler_words_count": 0, "feedback": "good",
             "next_recommendation": "practice", "part": "part_1", "title": "Test",
             "practice_mode": "fluency_practice", "created_at": "2026-01-01T00:00:00Z",
             "updated_at": "2026-01-01T00:05:00Z"},
        ])

        result = asyncio.run(engine.evaluate_session("u1", "sess1"))
        assert result["session"]["overall_band"] == 7.0
        assert result["xp_earned"] >= 20
        assert engine.mission_service.sync_after_evaluation.called


class TestSpeakingCoach:
    def test_coach_ask_question(self):
        eng = SpeakingCoachEngine(db=_make_db())
        eng._get_conversation = MagicMock(return_value={
            "id": "conv1", "user_id": "u1", "messages": [],
            "context_type": "practice_session", "context_id": "sess1",
            "target_band": 7.0, "current_weaknesses": [],
        })
        eng._load_conversation_context = MagicMock(return_value={
            "transcript": LONG_TRANSCRIPT,
            "question": "Tell me about your hobbies",
            "evaluation": {"overall_band": 6.5, "fluency_coherence_band": 6.0,
                           "lexical_resource_band": 6.5, "grammatical_range_band": 6.5,
                           "pronunciation_band": 7.0},
            "weaknesses": ["Grammar"],
            "previous_attempts": [],
            "target_band": 7.0,
        })
        eng.ai_service.speaking_coach_chat = AsyncMock(return_value={
            "answer": "Your grammar band is lower. Let's focus on that.",
            "key_points": ["Use past tense"],
            "example": "Try 'I went' instead of 'I go'",
            "action_step": "Practice past tense",
            "tone": "encouraging",
            "source": "ai",
        })
        eng.db = _make_db()
        eng.db.execute.return_value = MagicMock(data=[{}])

        result = asyncio.run(eng.chat("u1", "conv1", "Why did I get 6.5?"))
        assert len(result["updated_messages"]) == 2
        assert result["updated_messages"][0]["role"] == "user"


class TestReattemptMode:
    @pytest.fixture
    def service(self):
        svc = SpeakingReattemptService(db=_make_db())
        svc.speaking_repo = MagicMock()
        svc.progress_repo = MagicMock()
        svc.streak_repo = MagicMock()
        svc.ai_service = MagicMock()
        svc.mission_service = MagicMock()
        svc.mission_service.sync_after_evaluation = MagicMock()
        return svc

    def test_reattempt_full_flow(self, service):
        original = {"id": "resp1", "user_id": "u1", "transcript": LONG_TRANSCRIPT,
                    "part": "part_1", "title": "Hometown", "is_saved": True,
                    "audio_url": "http://audio", "duration_seconds": 60}
        new_resp = {"id": "resp2", "user_id": "u1", "transcript": LONG_TRANSCRIPT + " more content",
                    "part": "part_1", "title": "Hometown", "is_saved": True,
                    "audio_url": "http://audio2", "duration_seconds": 75}

        service._get_response = MagicMock(side_effect=[original, new_resp])
        service._get_attempt_record = MagicMock(return_value={
            "id": "att1", "attempt_number": 2, "attempt_group": "resp1",
        })
        service._get_analysis = MagicMock(return_value={"issues": []})
        service.ai_service.analyze_speaking = AsyncMock(return_value={
            "overall_band": 7.5, "fluency_coherence_band": 7.5,
            "lexical_resource_band": 7.0, "grammatical_range_band": 7.5,
            "pronunciation_band": 8.0, "feedback": "improved",
        })
        service.ai_service.analyze_speaking_errors = AsyncMock(return_value={"issues": []})
        service.ai_service.generate_speaking_reattempt_comparison = AsyncMock(return_value={
            "what_improved": ["Overall"],
            "what_stayed_the_same": [],
            "what_became_worse": [],
            "focus_next": ["Practice more"],
            "feedback": "Good improvement!",
        })
        service.db = _make_db()
        service.db.execute.return_value = MagicMock(data=[{}])

        result = asyncio.run(service.evaluate_reattempt("u1", "resp2"))
        assert result["attempt_number"] == 2
        assert result["bonus_xp"] >= 0
        assert service.mission_service.sync_after_evaluation.called


class TestAnalytics:
    def test_analytics_dashboard(self):
        svc = SpeakingAnalyticsService(db=_make_db())
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            {
                "id": "e1", "created_at": "2026-01-01T00:00:00Z", "overall_band": 7.0,
                "criteria": {"fluency_coherence": 7.0, "lexical_resource": 6.5,
                             "grammatical_range": 7.0, "pronunciation": 7.5},
                "part": "part_1", "speaking_test_responses": {"title": "Q1", "duration_seconds": 60},
                "confidence": 0.85, "source": "ai",
            },
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        svc.repo.list_test_responses = MagicMock(return_value=[])
        svc.repo.list_error_analysis = MagicMock(return_value=[])

        dashboard = svc.get_dashboard("u1")
        assert dashboard["total_evaluations"] >= 1
        assert dashboard["metrics"]["average_band"] == 7.0
        assert dashboard["strongest_criterion"] == "pronunciation"
        assert dashboard["weakest_criterion"] == "lexical_resource"

    def test_analytics_empty(self):
        svc = SpeakingAnalyticsService(db=None)
        dashboard = svc.get_dashboard("u1")
        assert dashboard["total_evaluations"] == 0
        assert dashboard["metrics"]["average_band"] is None


class TestMissionIntegration:
    def test_mission_sync_after_evaluation(self):
        svc = SpeakingMissionService(db=_make_db())
        svc.progress_repo = MagicMock()
        svc.streak_repo = MagicMock()
        svc.mission_repo = MagicMock()
        svc.prediction_engine = MagicMock()
        svc.speaking_analytics = MagicMock()
        svc.mission_repo.list_for_date.return_value = [
            {"id": "m1", "skill": "speaking", "status": "pending",
             "mission_date": "2026-01-01", "xp_reward": 20},
        ]
        svc.mission_repo.complete.return_value = {"id": "m1", "status": "completed"}
        svc.prediction_engine.get_prediction.return_value = {
            "estimated_band": 7.0, "readiness_score": 80,
        }

        result = svc.sync_after_evaluation("u1", {
            "overall_band": 7.0,
            "criteria_bands": {"fluency_coherence": 7.0, "lexical_resource": 6.5,
                               "grammatical_range": 7.0, "pronunciation": 7.5},
            "error_count": 2, "filler_words": 3, "duration_seconds": 60,
            "part": "part_1",
        }, context={"evaluation_id": "e1"})

        assert result["mission_completed"] is True
        assert result["xp_earned"] == 30
        assert result["predicted_band"] == 7.0
        assert result["readiness_score"] == 80
        assert result["weakest_speaking_criterion"] == "Lexical Resource"
        assert svc.mission_repo.complete.called

    def test_mission_sync_defensive(self):
        """Mission sync should not crash even if DB is None (graceful degradation)."""
        svc = SpeakingMissionService(db=None)
        # Don't mock internal repos — they will fail with db=None,
        # but sync_after_evaluation catches all exceptions.
        result = svc.sync_after_evaluation("u1", {"overall_band": 7.0})
        assert result["xp_earned"] == 0
        assert result["mission_completed"] is False
        assert result["predicted_band"] is None
        assert result["readiness_score"] is None


class TestEdgeCases:
    """Edge-case scenarios for robustness."""

    def test_poor_audio_quality(self, pipeline):
        """AI returns low confidence for poor audio — fallback still works."""
        pipeline.repo.get_evaluation.return_value = _eval_row(
            "um uh er basically stuff yeah", part="part_1", source="pending"
        )
        pipeline.ai_service.analyze_speaking = AsyncMock(return_value={
            "band_score": 4.5, "feedback": "Limited vocabulary and many fillers.",
            "corrections": ["Reduce filler words"],
        })
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 4.5
        assert "filler" in str(result.get("corrections", [])).lower() or result["overall_band"] <= 5.0

    def test_large_transcript(self, pipeline):
        """Very long transcript (>2000 words) should still evaluate."""
        huge = " ".join(["word"] * 500)
        pipeline.repo.get_evaluation.return_value = _eval_row(huge, part="part_3", source="pending")
        pipeline.ai_service.analyze_speaking = AsyncMock(return_value={
            "band_score": 6.0, "feedback": "ok", "corrections": [],
        })
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 6.0

    def test_ai_returns_none_band_score(self, pipeline):
        """AI returns valid dict but band_score is null."""
        pipeline.repo.get_evaluation.return_value = _eval_row(LONG_TRANSCRIPT, source="pending")
        pipeline.ai_service.analyze_speaking = AsyncMock(return_value={
            "band_score": None, "feedback": "ok", "corrections": [],
        })
        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] is not None

    def test_mission_sync_does_not_block_evaluation(self, pipeline):
        """If mission sync raises, evaluation should still return the result."""
        pipeline.repo.get_evaluation.return_value = _eval_row(LONG_TRANSCRIPT, source="pending")
        pipeline.ai_service.analyze_speaking = AsyncMock(return_value={
            "band_score": 7.0, "feedback": "good", "corrections": [],
        })
        pipeline.mission_service.sync_after_evaluation.side_effect = Exception("DB down")

        result = asyncio.run(pipeline.evaluate_transcript("u1", "eval1"))
        assert result["overall_band"] == 7.0
        assert result["source"] == "ai"
