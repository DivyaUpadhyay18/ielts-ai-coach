"""
Tests for the Speaking Practice Mode engine.

Validates:
  - start_session: prompt selection by mode, session creation
  - save_response: transcript + duration persistence
  - evaluate_session: AI evaluation integration, XP awarding, recommendation
  - get_session / list_sessions: owner-scoped retrieval
  - _select_prompt: mode-to-part mapping
  - _find_weakest_criterion: weakest band detection
  - _generate_next_recommendation: targeted advice
  - _count_fillers_in_issues: filler detection from error analysis
  - Error handling (session not found, wrong status, no transcript)
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.speaking_practice_mode_engine import (
    SpeakingPracticeModeEngine,
    PRACTICE_SESSION_XP,
    IMPROVEMENT_XP,
)
from app.core.exceptions import NotFoundError, ValidationError


@pytest.fixture
def engine():
    eng = SpeakingPracticeModeEngine(db=MagicMock())
    eng.repo = MagicMock()
    eng.progress_repo = MagicMock()
    eng.streak_repo = MagicMock()
    eng.ai_service = MagicMock()
    return eng


class TestStartSession:
    def test_start_session_quick_practice(self, engine):
        engine.repo.get_prompts.return_value = [
            {"id": "p1", "part": "part_1", "title": "Home Town",
             "prompt_text": "Tell me about your city", "prep_time_seconds": 0,
             "speak_time_seconds": 60},
        ]
        engine.db.execute.return_value = MagicMock(data=[
            {"id": "s1", "user_id": "u1", "practice_mode": "quick_practice",
             "part": "part_1", "title": "Home Town", "prompt_text": "Tell me about your city",
             "prep_time_seconds": 0, "speak_time_seconds": 60, "status": "in_progress"},
        ])
        result = engine.start_session("u1", "quick_practice")
        assert result["practice_mode"] == "quick_practice"
        assert result["part"] == "part_1"
        assert result["title"] == "Home Town"

    def test_start_session_part_2(self, engine):
        engine.repo.get_prompts.return_value = [
            {"id": "p2", "part": "part_2", "title": "A Journey",
             "prompt_text": "Describe a journey", "prep_time_seconds": 60,
             "speak_time_seconds": 120},
        ]
        engine.db.execute.return_value = MagicMock(data=[
            {"id": "s2", "user_id": "u1", "practice_mode": "part_2_practice",
             "part": "part_2", "title": "A Journey", "prompt_text": "Describe a journey",
             "prep_time_seconds": 60, "speak_time_seconds": 120, "status": "in_progress"},
        ])
        result = engine.start_session("u1", "part_2_practice")
        assert result["part"] == "part_2"
        assert result["prep_time_seconds"] == 60
        assert result["speak_time_seconds"] == 120

    def test_start_session_invalid_mode(self, engine):
        with pytest.raises(ValidationError):
            engine.start_session("u1", "invalid_mode")

    def test_start_session_no_prompts(self, engine):
        engine.repo.get_prompts.return_value = []
        engine.db.execute.return_value = MagicMock(data=[
            {"id": "s3", "user_id": "u1", "practice_mode": "quick_practice",
             "part": "part_1", "title": "", "prompt_text": "",
             "prep_time_seconds": 0, "speak_time_seconds": 60, "status": "in_progress"},
        ])
        result = engine.start_session("u1", "quick_practice")
        assert result["prompt_id"] is None
        assert result["title"] == ""


class TestSaveResponse:
    def test_save_response_updates_transcript(self, engine):
        engine._get_session = MagicMock(return_value={
            "id": "s1", "user_id": "u1", "status": "in_progress",
        })
        engine.db.execute.return_value = MagicMock(data=[
            {"id": "s1", "status": "in_progress", "transcript": "I went to the mountains.",
             "duration_seconds": 65, "audio_url": "http://audio"},
        ])
        result = engine.save_response("u1", "s1", "I went to the mountains.", 65, "http://audio")
        assert result["transcript"] == "I went to the mountains."
        assert result["duration_seconds"] == 65

    def test_save_response_not_found(self, engine):
        engine._get_session = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            engine.save_response("u1", "nonexistent", "test", 30)

    def test_save_response_wrong_status(self, engine):
        engine._get_session = MagicMock(return_value={
            "id": "s1", "user_id": "u1", "status": "evaluated",
        })
        with pytest.raises(ValidationError):
            engine.save_response("u1", "s1", "test", 30)


class TestEvaluateSession:
    @pytest.fixture
    def populated_engine(self, engine):
        engine._get_session = MagicMock(return_value={
            "id": "s1", "user_id": "u1", "status": "in_progress",
            "transcript": "I enjoy reading books in my free time.",
            "part": "part_1", "title": "Hobbies",
            "practice_mode": "fluency_practice",
            "created_at": "2025-01-01T00:00:00Z",
        })
        engine.ai_service.analyze_speaking = AsyncMock(return_value={
            "overall_band": 7.0,
            "fluency_coherence_band": 7.0,
            "lexical_resource_band": 6.5,
            "grammatical_range_band": 7.0,
            "pronunciation_band": 7.5,
            "feedback": "Good job!",
        })
        engine.ai_service.analyze_speaking_errors = AsyncMock(return_value={
            "issues": [
                {"issue_type": "Filler Words", "explanation": "um x3"},
                {"issue_type": "Grammar", "explanation": "tense error"},
            ],
        })
        engine.db.execute.return_value = MagicMock(data=[
            {"id": "s1", "user_id": "u1", "status": "evaluated",
             "overall_band": 7.0, "fluency_coherence_band": 7.0,
             "lexical_resource_band": 6.5, "grammatical_range_band": 7.0,
             "pronunciation_band": 7.5, "error_count": 2,
             "filler_words_count": 1, "feedback": "Good job!",
             "next_recommendation": "Practice fluency",
             "part": "part_1", "title": "Hobbies",
             "practice_mode": "fluency_practice",
             "created_at": "2025-01-01T00:00:00Z",
             "updated_at": "2025-01-01T00:05:00Z"},
        ])
        return engine

    def test_evaluate_session_success(self, populated_engine):
        result = asyncio.run(populated_engine.evaluate_session("u1", "s1"))
        assert result["evaluation"]["overall_band"] == 7.0
        assert result["error_analysis"]["issues"][0]["issue_type"] == "Filler Words"
        assert result["session"]["error_count"] == 2
        assert result["session"]["filler_words_count"] == 1
        assert result["xp_earned"] >= PRACTICE_SESSION_XP
        assert result["next_recommendation"] is not None

    def test_evaluate_session_not_found(self, engine):
        engine._get_session = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            asyncio.run(engine.evaluate_session("u1", "nonexistent"))

    def test_evaluate_session_wrong_status(self, engine):
        engine._get_session = MagicMock(return_value={
            "id": "s1", "user_id": "u1", "status": "evaluated",
            "transcript": "test",
        })
        with pytest.raises(ValidationError):
            asyncio.run(engine.evaluate_session("u1", "s1"))

    def test_evaluate_session_no_transcript(self, engine):
        engine._get_session = MagicMock(return_value={
            "id": "s1", "user_id": "u1", "status": "in_progress",
            "transcript": "",
        })
        with pytest.raises(ValidationError):
            asyncio.run(engine.evaluate_session("u1", "s1"))

    def test_evaluate_session_target_band_bonus(self, populated_engine):
        populated_engine.db.execute.return_value = MagicMock(data=[
            {"id": "s1", "user_id": "u1", "status": "evaluated",
             "overall_band": 7.5, "fluency_coherence_band": 7.0,
             "lexical_resource_band": 6.5, "grammatical_range_band": 7.0,
             "pronunciation_band": 7.5, "error_count": 2,
             "filler_words_count": 1, "feedback": "Good!",
             "next_recommendation": "Practice",
             "part": "part_1", "title": "Hobbies",
             "practice_mode": "fluency_practice",
             "created_at": "2025-01-01T00:00:00Z",
             "updated_at": "2025-01-01T00:05:00Z"},
        ])
        result = asyncio.run(populated_engine.evaluate_session("u1", "s1", target_band=7.0))
        assert result["xp_earned"] >= PRACTICE_SESSION_XP + IMPROVEMENT_XP


class TestPromptSelection:
    def test_mode_to_part_mapping(self, engine):
        engine.repo.get_prompts.return_value = [{"id": "p1", "part": "part_1"}]
        result = engine._select_prompt("part_1_practice", "part_1", "u1")
        assert result is not None and result["part"] == "part_1"

        engine.repo.get_prompts.return_value = [{"id": "p2", "part": "part_3"}]
        result = engine._select_prompt("part_3_practice", "part_3", "u1")
        assert result is not None and result["part"] == "part_3"

    def test_vocabulary_practice_falls_back(self, engine):
        engine.repo.get_prompts.side_effect = [["p1-prompt"], []]
        result = engine._select_prompt("vocabulary_practice", None, "u1")
        assert result is not None

    def test_wild_area_practice_uses_weakest(self, engine):
        engine._find_weakest_criterion = MagicMock(return_value="lexorcal_resource")
        engine.repo.get_prompts.return_value = [{"id": "p5"}]
        result = engine._select_prompt("weak_area_practice", None, "u1")
        assert result is not None


class TestFindWeakestCriterion:
    def test_no_data(self, engine):
        engine.db = None
        assert engine._find_weakest_criterion("u1") is None

    def test_finds_weakest(self, engine):
        engine.db = MagicMock()
        engine.db.execute.return_value = MagicMock(data=[
            {"fluency_coherence_band": 7.0, "lexical_resource_band": 5.5,
             "grammatical_range_band": 7.0, "pronunciation_band": 7.0},
            {"fluency_coherence_band": 7.0, "lexical_resource_band": 5.0,
             "grammatical_range_band": 7.0, "pronunciation_band": 7.0},
        ])
        result = engine._find_weakest_criterion("u1")
        assert result == "lexical_resource"

    def test_all_high_returns_none(self, engine):
        engine.db = MagicMock()
        engine.db.execute.return_value = MagicMock(data=[
            {"fluency_coherence_band": 8.5, "lexical_resource_band": 8.5,
             "grammatical_range_band": 8.5, "pronunciation_band": 8.5},
        ])
        result = engine._find_weakest_criterion("u1")
        assert result is None


class TestCountFillersInIssues:
    def test_counts_filler_issues(self, engine):
        issues = [
            {"issue_type": "Filler Words"},
            {"issue_type": "Grammar"},
            {"issue_type": "Filler Words"},
        ]
        assert engine._count_fillers_in_issues(issues) == 2

    def test_no_fillers(self, engine):
        assert engine._count_fillers_in_issues([]) == 0
        assert engine._count_fillers_in_issues([{"issue_type": "Grammar"}]) == 0


class TestGenerateNextRecommendation:
    def test_weakest_fluency(self, engine):
        ai_eval = {"fluency_coherence_band": 5.5, "lexical_resource_band": 7.0,
                   "grammatical_range_band": 7.0, "pronunciation_band": 7.0}
        ai_errors = {"issues": []}
        rec = engine._generate_next_recommendation(ai_eval, ai_errors, "quick_practice")
        assert "fluency" in rec.lower()

    def test_weakest_lexical(self, engine):
        ai_eval = {"fluency_coherence_band": 7.0, "lexical_resource_band": 5.0,
                   "grammatical_range_band": 7.0, "pronunciation_band": 7.0}
        ai_errors = {"issues": []}
        rec = engine._generate_next_recommendation(ai_eval, ai_errors, "quick_practice")
        assert "vocabulary" in rec.lower() or "synonym" in rec.lower()

    def test_recommendation_with_filler_advice(self, engine):
        ai_eval = {"fluency_coherence_band": 5.5, "lexical_resource_band": 6.0,
                   "grammatical_range_band": 6.0, "pronunciation_band": 6.0}
        ai_errors = {"issues": [{"issue_type": "Filler Words"}]}
        rec = engine._generate_next_recommendation(ai_eval, ai_errors, "fluency_practice")
        assert "um" in rec or "filler" in rec.lower()


class TestGetAndListSessions:
    def test_get_session_not_found(self, engine):
        engine._get_session = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            engine.get_session("u1", "nonexistent")

    def test_list_sessions_empty(self, engine):
        engine.db = None
        result = engine.list_sessions("u1", 10)
        assert result["total"] == 0
        assert result["results"] == []


class TestToSessionResponse:
    def test_projects_all_fields(self):
        session = {
            "id": "abc", "user_id": "u1", "practice_mode": "quick_practice",
            "prompt_id": "p1", "part": "part_1", "title": "Test",
            "prompt_text": "Question?", "prep_time_seconds": 0,
            "speak_time_seconds": 60, "audio_url": "", "duration_seconds": 65,
            "transcript": "answer", "overall_band": 7.0,
            "fluency_coherence_band": 7.0, "lexical_resource_band": 6.5,
            "grammatical_range_band": 7.0, "pronunciation_band": 7.5,
            "error_count": 2, "filler_words_count": 1,
            "feedback": "good", "next_recommendation": "practice more",
            "status": "evaluated", "mission_id": None,
            "created_at": "2025-01-01", "updated_at": "2025-01-01",
            "completed_at": None,
        }
        result = SpeakingPracticeModeEngine._to_session_response(session)
        assert result["id"] == "abc"
        assert result["overall_band"] == 7.0
        assert result["error_count"] == 2
        assert result["filler_words_count"] == 1
        assert result["status"] == "evaluated"
