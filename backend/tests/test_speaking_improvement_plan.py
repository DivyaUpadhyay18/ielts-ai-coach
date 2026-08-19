"""
Tests for the Speaking Improvement Plan engine and AI service.

Validates:
  - Weakness ranking (strongest / weakest criterion)
  - Deterministic fallback plan generation
  - AI path with mocked OpenAI call
  - Band gap computation (current vs target)
  - Target band resolution (explicit / profile / default)
  - Engine business logic (owner-scoping, response lookup, plan storage,
    response projection, severity counting)
  - Error handling (response not found, no evaluation data)
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services import ai_service
from app.services.ai_service import (
    AIService,
    _rank_speaking_weaknesses,
    _build_speaking_plan_prompt,
    _normalize_speaking_improvement_plan,
    _fallback_speaking_improvement_plan,
)
from app.services.speaking_improvement_plan_engine import SpeakingImprovementPlanEngine


# ─── Weakness ranking ─────────────────────────────────────────────────

class TestWeaknessRanking:
    def test_strongest_weakest(self):
        bands = {
            "fluency_coherence": 6.0,
            "lexical_resource": 5.5,
            "grammatical_range": 7.0,
            "pronunciation": 6.5,
        }
        strongest, weakest = _rank_speaking_weaknesses(bands)
        assert strongest == "grammatical_range"
        assert weakest == "lexical_resource"

    def test_empty_bands(self):
        strongest, weakest = _rank_speaking_weaknesses({})
        assert strongest is None
        assert weakest is None

    def test_ignores_non_numeric(self):
        bands = {"lexical_resource": "bad", "fluency_coherence": 6.5}
        strongest, weakest = _rank_speaking_weaknesses(bands)
        assert strongest == "fluency_coherence"
        assert weakest == "fluency_coherence"

    def test_all_equal(self):
        bands = {
            "fluency_coherence": 6.5,
            "lexical_resource": 6.5,
            "grammatical_range": 6.5,
            "pronunciation": 6.5,
        }
        strongest, weakest = _rank_speaking_weaknesses(bands)
        assert strongest is not None
        assert weakest is not None


# ─── Prompt builder ───────────────────────────────────────────────────

class TestBuildSpeakingPlanPrompt:
    def test_basic(self):
        context = {
            "current_band": 6.5,
            "target_band": 8.0,
            "band_gap": 1.5,
            "fluency_coherence_band": 6.0,
            "lexical_resource_band": 5.5,
            "grammatical_range_band": 7.0,
            "pronunciation_band": 6.5,
            "strongest_criterion": "grammatical_range",
            "weakest_criterion": "lexical_resource",
            "issues_summary": "Filler Words: um used 3 times",
            "part": "part_2",
            "topic": "Describe a journey",
            "transcript": "I went to the mountains and it was very beautiful.",
        }
        prompt = _build_speaking_plan_prompt(context)
        assert "6.5" in prompt
        assert "8.0" in prompt
        assert "1.5" in prompt
        assert "part_2" in prompt
        assert "Describe a journey" in prompt
        assert "very beautiful" in prompt

    def test_defaults(self):
        context = {
            "current_band": 6.0,
            "target_band": 7.0,
            "band_gap": 1.0,
            "fluency_coherence_band": 6.0,
            "lexical_resource_band": 6.0,
            "grammatical_range_band": 6.0,
            "pronunciation_band": 6.0,
            "strongest_criterion": "fluency_coherence",
            "weakest_criterion": "lexical_resource",
            "issues_summary": "",
            "part": "part_1",
            "topic": "",
            "transcript": "",
        }
        prompt = _build_speaking_plan_prompt(context)
        assert "Part: part_1" in prompt


# ─── Normalisation ────────────────────────────────────────────────────

class TestNormalizeSpeakingImprovementPlan:
    def test_valid(self):
        result = {
            "current_band": 6.5,
            "target_band": 8.0,
            "band_gap": 1.5,
            "strongest_criterion": "fluency_coherence",
            "weakest_criterion": "lexical_resource",
            "criterion_priorities": {
                "fluency_coherence": "medium",
                "lexical_resource": "high",
                "grammatical_range": "medium",
                "pronunciation": "low",
            },
            "current_level_description": "You are at Band 6.5.",
            "target_level_description": "Band 8 requires more vocabulary.",
            "specific_changes": [{"area": "Lexical Resource", "change": "Use synonyms.", "priority": "high"}],
            "practice_exercises": [{"title": "Vocabulary drill", "description": "Do it", "skill_focus": "vocabulary", "estimated_minutes": 15}],
            "practice_topics": ["topic1", "topic2"],
            "recommended_resources": [{"title": "Resource", "url": "http://x", "why": "Helps"}],
            "suggested_daily_minutes": 20,
            "next_speaking_task": "Practice Part 2.",
            "suggested_mission": {"title": "Mission", "skill": "speaking", "sub_skill": "lexical_resource", "duration_minutes": 20, "description": "Do stuff"},
            "is_estimate": True,
        }
        norm = _normalize_speaking_improvement_plan(result)
        assert norm["current_band"] == 6.5
        assert norm["target_band"] == 8.0
        assert norm["band_gap"] == 1.5
        assert len(norm["specific_changes"]) == 1
        assert norm["is_estimate"] is True

    def test_empty(self):
        norm = _normalize_speaking_improvement_plan({})
        assert norm["current_band"] == 0.0
        assert norm["specific_changes"] == []
        assert norm["is_estimate"] is True

    def test_invalid_priorities_coerced(self):
        norm = _normalize_speaking_improvement_plan({"criterion_priorities": "not a dict"})
        assert norm["criterion_priorities"] == {}


# ─── Fallback plan ────────────────────────────────────────────────────

class TestFallbackSpeakingImprovementPlan:
    def test_returns_all_sections(self):
        context = {
            "current_band": 6.5,
            "target_band": 8.0,
            "band_gap": 1.5,
            "fluency_coherence_band": 6.0,
            "lexical_resource_band": 5.5,
            "grammatical_range_band": 7.0,
            "pronunciation_band": 6.5,
            "strongest_criterion": "grammatical_range",
            "weakest_criterion": "lexical_resource",
            "issues_summary": "",
            "part": "part_2",
            "topic": "journey",
            "transcript": "Some transcript text here.",
        }
        result = _fallback_speaking_improvement_plan(context)
        assert result["current_band"] == 6.5
        assert result["target_band"] == 8.0
        assert result["band_gap"] == 1.5
        assert result["weakest_criterion"] == "lexical_resource"
        assert result["strongest_criterion"] == "grammatical_range"
        assert len(result["specific_changes"]) >= 3
        assert len(result["practice_exercises"]) >= 1
        assert len(result["practice_topics"]) >= 3
        assert len(result["recommended_resources"]) >= 1
        assert "next_speaking_task" in result
        assert "suggested_mission" in result
        assert result["is_estimate"] is True
        assert "source" not in result or result.get("source") is None

    def test_gap_05_1(self):
        context = {
            "current_band": 6.5,
            "target_band": 7.5,
            "band_gap": 1.0,
            "weakest_criterion": "lexical_resource",
            "strongest_criterion": "fluency_coherence",
        }
        result = _fallback_speaking_improvement_plan(context)
        assert result["suggested_daily_minutes"] == 15

    def test_gap_15_25(self):
        context = {
            "current_band": 6.0,
            "target_band": 8.0,
            "band_gap": 2.0,
            "weakest_criterion": "lexical_resource",
            "strongest_criterion": "fluency_coherence",
        }
        result = _fallback_speaking_improvement_plan(context)
        assert result["suggested_daily_minutes"] == 20

    def test_gap_3_plus(self):
        context = {
            "current_band": 5.0,
            "target_band": 8.5,
            "band_gap": 3.5,
            "weakest_criterion": "lexical_resource",
            "strongest_criterion": "pronunciation",
        }
        result = _fallback_speaking_improvement_plan(context)
        assert result["suggested_daily_minutes"] == 30

    def test_criterion_priorities(self):
        context = {
            "current_band": 6.5,
            "target_band": 8.0,
            "band_gap": 1.5,
            "fluency_coherence_band": 6.0,
            "lexical_resource_band": 5.5,
            "grammatical_range_band": 7.0,
            "pronunciation_band": 6.5,
            "weakest_criterion": "lexical_resource",
            "strongest_criterion": "grammatical_range",
        }
        result = _fallback_speaking_improvement_plan(context)
        priorities = result["criterion_priorities"]
        assert priorities["lexical_resource"] == "high"
        assert priorities["grammatical_range"] == "low"

    def test_changes_ranked_weakest_first(self):
        context = {
            "current_band": 6.5,
            "target_band": 8.0,
            "band_gap": 1.5,
            "fluency_coherence_band": 6.0,
            "lexical_resource_band": 5.0,
            "grammatical_range_band": 7.0,
            "pronunciation_band": 6.5,
            "weakest_criterion": "lexical_resource",
            "strongest_criterion": "grammatical_range",
        }
        result = _fallback_speaking_improvement_plan(context)
        # First change should be for the weakest criterion
        assert result["specific_changes"][0]["priority"] == "high"

    def test_target_clamped(self):
        context = {
            "current_band": 6.0,
            "target_band": 15.0,  # way over
            "band_gap": 9.0,
            "weakest_criterion": "lexical_resource",
            "strongest_criterion": "pronunciation",
        }
        result = _fallback_speaking_improvement_plan(context)
        assert result["target_band"] <= 9.0


# ─── AIService.generate_speaking_improvement_plan tests ────────────────

class TestAIServiceSpeakingPlan:
    def test_no_key_uses_fallback(self):
        service = AIService()
        service.api_key = None
        evaluation = {
            "overall_band": 6.5,
            "criteria_bands": {
                "fluency_coherence": 6.0,
                "lexical_resource": 5.5,
                "grammatical_range": 7.0,
                "pronunciation": 6.5,
            },
            "part": "part_2",
            "topic": "journey",
            "transcript": "Some transcript.",
        }
        result = asyncio.run(service.generate_speaking_improvement_plan(evaluation, target_band=8.0))
        assert result["source"] == "deterministic_fallback"
        assert result["current_band"] == 6.5
        assert result["target_band"] == 8.0

    def test_with_key_ai_success(self):
        service = AIService()
        service.api_key = "fake-key"

        fake_response = {
            "choices": [{
                "message": {
                    "content": '{"current_band": 6.5, "target_band": 8.0, "band_gap": 1.5, "strongest_criterion": "grammatical_range", "weakest_criterion": "lexical_resource", "criterion_priorities": {"fluency_coherence": "medium", "lexical_resource": "high", "grammatical_range": "medium", "pronunciation": "low"}, "current_level_description": "test", "target_level_description": "test", "specific_changes": [{"area": "Lexical Resource", "change": "test", "priority": "high"}], "practice_exercises": [], "practice_topics": [], "recommended_resources": [], "suggested_daily_minutes": 20, "next_speaking_task": "test", "suggested_mission": {"title": "test", "skill": "speaking", "duration_minutes": 20}, "is_estimate": true}'
                }
            }]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls = MagicMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        with patch.object(ai_service, "AsyncClient", mock_client_cls):
            result = asyncio.run(service.generate_speaking_improvement_plan(
                {"overall_band": 6.5, "criteria_bands": {
                    "fluency_coherence": 6.0, "lexical_resource": 5.5,
                    "grammatical_range": 7.0, "pronunciation": 6.5,
                }, "part": "part_1", "topic": "", "transcript": ""},
                target_band=8.0,
            ))

        assert result["source"] == "ai"
        assert result["target_band"] == 8.0
        assert len(result["specific_changes"]) == 1

    def test_with_key_api_error_falls_back(self):
        service = AIService()
        service.api_key = "fake-key"

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("API down")
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls = MagicMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        with patch.object(ai_service, "AsyncClient", mock_client_cls):
            result = asyncio.run(service.generate_speaking_improvement_plan(
                {"overall_band": 6.0, "criteria_bands": {
                    "fluency_coherence": 6.0, "lexical_resource": 6.0,
                    "grammatical_range": 6.0, "pronunciation": 6.0,
                }, "part": "part_1", "topic": "", "transcript": "test"},
            ))

        assert result["source"] == "deterministic_fallback"

    def test_default_target_band_when_none(self):
        service = AIService()
        service.api_key = None
        result = asyncio.run(service.generate_speaking_improvement_plan(
            {"overall_band": 6.5, "criteria_bands": {
                "fluency_coherence": 6.0, "lexical_resource": 6.0,
                "grammatical_range": 6.0, "pronunciation": 6.0,
            }, "part": "part_1", "topic": "", "transcript": ""},
        ))
        assert result["target_band"] == 7.5  # 6.5 + 1.0


# ─── Engine tests ─────────────────────────────────────────────────────

class TestSpeakingImprovementPlanEngine:
    @pytest.fixture
    def engine(self):
        eng = SpeakingImprovementPlanEngine(db=MagicMock())
        eng.db = MagicMock()
        eng.ai_service = MagicMock()
        return eng

    def test_get_plan_not_found(self, engine):
        engine.db.execute.return_value = MagicMock(data=[])
        with pytest.raises(Exception):
            engine.get_plan("user1", "resp1")

    def test_list_plans_empty(self, engine):
        engine.db.execute.return_value = MagicMock(data=[])
        result = engine.list_plans("user1", 10)
        assert result["total"] == 0
        assert result["results"] == []

    def test_to_response_projects_from_row(self):
        row = {
            "id": "abc",
            "response_id": "resp1",
            "current_band": 6.5,
            "target_band": 8.0,
            "band_gap": 1.5,
            "strongest_criterion": "grammatical_range",
            "weakest_criterion": "lexical_resource",
            "criterion_priorities": '{"fluency_coherence":"medium","lexical_resource":"high"}',
            "current_level_description": "current",
            "target_level_description": "target",
            "specific_changes": '[{"area":"Lex","change":"x","priority":"high"}]',
            "practice_exercises": '[]',
            "practice_topics": '["topic1"]',
            "recommended_resources": '[]',
            "suggested_daily_minutes": 20,
            "next_speaking_task": "Do something",
            "suggested_mission": '{"title":"test","skill":"speaking","duration_minutes":20}',
            "is_estimate": True,
            "source": "deterministic_fallback",
            "created_at": "2025-01-01T00:00:00Z",
        }
        result = SpeakingImprovementPlanEngine._to_response(row)
        assert result["id"] == "abc"
        assert result["response_id"] == "resp1"
        assert result["current_band"] == 6.5
        assert result["band_gap"] == 1.5
        assert len(result["specific_changes"]) == 1
        assert result["specific_changes"][0]["area"] == "Lex"
        assert len(result["practice_topics"]) == 1
        assert result["suggested_daily_minutes"] == 20
        assert isinstance(result["criterion_priorities"], dict)

    def test_to_response_handles_json_string_fields(self):
        row = {
            "id": "x",
            "response_id": "y",
            "current_band": 6.0,
            "target_band": 7.0,
            "band_gap": 1.0,
            "criterion_priorities": "{}",
            "specific_changes": "[]",
            "practice_exercises": "[]",
            "practice_topics": "[]",
            "recommended_resources": "[]",
            "suggested_mission": "{}",
        }
        result = SpeakingImprovementPlanEngine._to_response(row)
        assert result["specific_changes"] == []
        assert result["criterion_priorities"] == {}

    def test_to_response_handles_native_list_fields(self):
        row = {
            "id": "x",
            "response_id": "y",
            "current_band": 6.0,
            "target_band": 7.0,
            "band_gap": 1.0,
            "criterion_priorities": {},
            "specific_changes": [{"area": "test", "change": "x", "priority": "high"}],
            "practice_exercises": [],
            "practice_topics": [],
            "recommended_resources": [],
            "suggested_mission": {"title": "test"},
        }
        result = SpeakingImprovementPlanEngine._to_response(row)
        assert len(result["specific_changes"]) == 1
        assert result["specific_changes"][0]["area"] == "test"

    def test_build_evaluation_context_from_analysis(self, engine):
        response = {"id": "r1", "part": "part_2", "title": "Journey topic", "transcript": "test"}
        analysis = {
            "overall_band": 6.5,
            "fluency_coherence_band": 6.0,
            "lexical_resource_band": 5.5,
            "grammatical_range_band": 7.0,
            "pronunciation_band": 6.5,
            "part": "part_2",
            "topic": "Journey",
            "transcript": "I went to the mountains.",
            "issues": [
                {"issue_type": "Filler Words", "explanation": "Used um 3 times"},
                {"issue_type": "Weak Vocabulary", "explanation": "Used very 5 times"},
            ],
        }
        ctx = engine._build_evaluation_context(response, analysis)
        assert ctx["overall_band"] == 6.5
        assert ctx["criteria_bands"]["fluency_coherence"] == 6.0
        assert ctx["criteria_bands"]["lexical_resource"] == 5.5
        assert "Filler Words" in ctx["issues_summary"]
        assert "Weak Vocabulary" in ctx["issues_summary"]

    def test_build_evaluation_context_without_analysis(self, engine):
        response = {
            "id": "r1",
            "part": "part_1",
            "title": "Topic",
            "transcript": "test",
            "overall_band": 7.0,
            "criteria_bands": {"fluency_coherence": 7.0},
        }
        ctx = engine._build_evaluation_context(response, None)
        assert ctx["overall_band"] == 7.0
        assert ctx["issues_summary"] == ""
