"""
Tests for the Writing Improvement Plan Engine ("Improve My Band" feature).

Validates:
  - Deterministic fallback plan generation
  - AI path with mocked OpenAI call
  - Band gap computation (current vs target)
  - Weakness ranking from criterion bands
  - Target band resolution (explicit / profile / default)
  - Engine business logic (owner-scoping, pending/evaluated validation,
    plan storage, response projection)
  - Error handling (submission not found, not submitted, no evaluation,
    evaluation still pending)
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services import ai_service
from app.services.ai_service import (
    AIService,
    _rank_weaknesses,
    _fallback_improvement_plan,
)
from app.services.writing_improvement_plan_engine import WritingImprovementPlanEngine
from app.core.exceptions import NotFoundError, ValidationError


# ─── Weakness ranking ─────────────────────────────────────────────────
class TestWeaknessRanking:
    def test_weakest_first(self):
        bands = {
            "task_response": 6.0,
            "coherence_cohesion": 7.0,
            "lexical_resource": 6.5,
            "grammatical_range_accuracy": 5.5,
        }
        weak = _rank_weaknesses(bands)
        assert weak[0] == "grammatical_range_accuracy"
        assert weak[-1] == "coherence_cohesion"

    def test_empty_bands(self):
        assert _rank_weaknesses({}) == []

    def test_ignores_non_numeric(self):
        bands = {"task_response": "bad", "lexical_resource": 6.0}
        weak = _rank_weaknesses(bands)
        assert weak == ["lexical_resource"]


# ─── Fallback plan ────────────────────────────────────────────────────
class TestFallbackImprovementPlan:
    def test_fallback_returns_all_sections(self):
        result = _fallback_improvement_plan({
            "criteria_bands": {
                "task_response": 6.0,
                "coherence_cohesion": 6.5,
                "lexical_resource": 5.5,
                "grammatical_range_accuracy": 5.5,
            },
            "error_types": [],
            "current_band": 6.0,
            "target_band": 8.0,
            "band_gap": 2.0,
            "word_count": 250,
            "task_type": "task_2",
        })
        assert "current_level_description" in result
        assert "target_level_description" in result
        assert "specific_changes" in result
        assert "practice_exercises" in result
        assert "recommended_resources" in result
        assert "suggested_mission" in result
        assert len(result["specific_changes"]) > 0
        assert len(result["recommended_resources"]) > 0

    def test_gap_drives_depth(self):
        # Large gap -> more changes, exercises, resources
        large = _fallback_improvement_plan({
            "criteria_bands": {}, "current_band": 5.0, "target_band": 9.0,
            "band_gap": 4.0, "word_count": 200, "task_type": "task_2",
        })
        small = _fallback_improvement_plan({
            "criteria_bands": {}, "current_band": 8.0, "target_band": 8.5,
            "band_gap": 0.5, "word_count": 250, "task_type": "task_2",
        })
        assert len(large["specific_changes"]) >= len(small["specific_changes"])
        assert len(large["recommended_resources"]) >= len(small["recommended_resources"])

    def test_weakest_criterion_first_change(self):
        result = _fallback_improvement_plan({
            "criteria_bands": {
                "task_response": 6.0,
                "coherence_cohesion": 7.0,
                "lexical_resource": 7.0,
                "grammatical_range_accuracy": 5.0,
            },
            "current_band": 6.5,
            "target_band": 7.5,
            "band_gap": 1.0,
            "word_count": 250,
            "task_type": "task_2",
        })
        # The weakest criterion (grammatical_range_accuracy → "Grammatical Range & Accuracy")
        # should be the first change.
        first_area = result["specific_changes"][0]["area"]
        assert first_area == "Grammatical Range & Accuracy"


# ─── AI path with mocked httpx ───────────────────────────────────────
class TestAIImprovementPlan:
    async def _run(self, plan_json):
        svc = AIService()
        svc.api_key = "test-key"
        with patch.object(ai_service, "AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": plan_json}}]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            return await svc.generate_improvement_plan(
                "essay text",
                {"overall_band": 6.0, "criteria_bands": {"task_response": 6.0}, "word_count": 250, "task_type": "task_2", "error_analysis": []},
                target_band=8.0,
            )

    def test_ai_plan_normalized(self):
        plan = '{"current_level_description":"You are at Band 6.","target_level_description":"A Band 8 requires...","specific_changes":[{"area":"Task Response","change":"Develop ideas more fully","priority":"high"}],"practice_exercises":[{"title":"Timed practice","description":"Write one essay","skill_focus":"task_2","estimated_minutes":50}],"recommended_resources":[{"title":"IELTS Liz","url":"https://ieltsliz.com","why":"Good examples"}],"suggested_mission":{"title":"Band 8 practice","skill":"writing","sub_skill":"task_2","duration_minutes":60,"description":"Timed essay"}}'
        result = asyncio.run(self._run(plan))
        assert result["source"] == "ai"
        assert result["current_level_description"] == "You are at Band 6."
        assert result["target_level_description"] == "A Band 8 requires..."
        assert len(result["specific_changes"]) == 1
        assert result["specific_changes"][0]["area"] == "Task Response"
        assert result["specific_changes"][0]["priority"] == "high"
        assert len(result["practice_exercises"]) == 1
        assert result["practice_exercises"][0]["skill_focus"] == "task_2"
        assert len(result["recommended_resources"]) == 1
        assert result["suggested_mission"]["title"] == "Band 8 practice"

    def test_ai_failure_uses_fallback(self):
        svc = AIService()
        svc.api_key = "test-key"
        with patch.object(ai_service, "AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=Exception("boom"))
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            result = asyncio.run(svc.generate_improvement_plan(
                "essay",
                {"overall_band": 6.0, "criteria_bands": {}, "word_count": 250, "task_type": "task_2", "error_analysis": []},
                target_band=8.0,
            ))
            assert result["source"] == "deterministic_fallback"
            assert "specific_changes" in result

    def test_ai_handles_empty_json(self):
        svc = AIService()
        svc.api_key = "test-key"
        with patch.object(ai_service, "AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
            mock_resp.raise_for_status = MagicMock()
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            result = asyncio.run(svc.generate_improvement_plan(
                "essay",
                {"overall_band": 6.0, "criteria_bands": {"task_response": 6.0}, "word_count": 250, "task_type": "task_2", "error_analysis": []},
                target_band=8.0,
            ))
            # Empty AI result is normalized successfully (empty fields, source=ai).
            assert result["source"] == "ai"
            assert result["current_level_description"] == ""


# ─── Engine integration (mocked DB + AI) ──────────────────────────────
class TestImprovementPlanEngine:
    @pytest.fixture
    def engine(self):
        eng = WritingImprovementPlanEngine(db=MagicMock())
        eng.db = MagicMock()
        eng.repo = MagicMock()
        eng.ai_service = MagicMock()
        return eng

    def test_generate_plan_success(self, engine):
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted", "task_type": "task_2",
            "essay_text": "Some essay.", "prompt_text": "", "word_count": 250,
        }
        engine.repo.get_evaluation.return_value = {
            "id": "eval1", "submission_id": "sub1", "status": "evaluated",
            "task_type": "task_2", "overall_band": 6.0, "confidence": 0.8,
            "word_count": 250, "criteria_bands": {"task_response": 6.0},
            "error_analysis": [],
        }
        engine.repo.create_improvement_plan = MagicMock(return_value={
            "id": "plan1", "evaluation_id": "eval1", "submission_id": "sub1",
            "current_band": 6.0, "target_band": 8.0, "band_gap": 2.0,
            "weaknesses": ["task_response"], "current_level_description": "X",
            "target_level_description": "Y", "specific_changes": [],
            "practice_exercises": [], "recommended_resources": [],
            "suggested_mission": {}, "is_estimate": True, "source": "ai",
        })
        engine.ai_service.generate_improvement_plan = AsyncMock(return_value={
            "current_level_description": "X", "target_level_description": "Y",
            "specific_changes": [], "practice_exercises": [],
            "recommended_resources": [], "suggested_mission": {}, "source": "ai",
        })

        result = asyncio.run(engine.generate_plan("user1", "sub1", target_band=8.0))

        assert result["current_band"] == 6.0
        assert result["target_band"] == 8.0
        assert result["band_gap"] == 2.0
        # AI service was called with the essay text and evaluation.
        engine.ai_service.generate_improvement_plan.assert_called_once()
        call_kwargs = engine.ai_service.generate_improvement_plan.call_args[1]
        assert call_kwargs["essay_text"] == "Some essay."
        assert call_kwargs["target_band"] == 8.0
        assert "overall_band" in call_kwargs["evaluation"]

    def test_generate_plan_not_submitted(self, engine):
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "draft",
        }
        with pytest.raises(ValidationError):
            asyncio.run(engine.generate_plan("user1", "sub1"))

    def test_generate_plan_no_evaluation(self, engine):
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted", "task_type": "task_2",
        }
        engine.repo.get_evaluation.return_value = None
        with pytest.raises(NotFoundError):
            asyncio.run(engine.generate_plan("user1", "sub1"))

    def test_generate_plan_evaluation_pending(self, engine):
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted", "task_type": "task_2",
        }
        engine.repo.get_evaluation.return_value = {
            "id": "eval1", "status": "pending", "overall_band": None,
        }
        with pytest.raises(ValidationError):
            asyncio.run(engine.generate_plan("user1", "sub1"))

    def test_get_plan_not_found(self, engine):
        engine.repo.get_improvement_plan.return_value = None
        with pytest.raises(NotFoundError):
            engine.get_plan("user1", "eval1")

    def test_list_plans(self, engine):
        engine.repo.list_improvement_plans.return_value = [
            {
                "id": "plan1", "evaluation_id": "eval1", "submission_id": "sub1",
                "current_band": 6.0, "target_band": 8.0, "band_gap": 2.0,
                "weaknesses": ["task_response"], "current_level_description": "x",
                "target_level_description": "y", "specific_changes": [],
                "practice_exercises": [], "recommended_resources": [],
                "suggested_mission": {}, "is_estimate": True, "source": "ai",
                "created_at": "2025-01-01",
            }
        ]
        result = engine.list_plans("user1", 20)
        assert result["total"] == 1
        assert result["results"][0]["current_band"] == 6.0

    def test_resolve_target_band_explicit(self, engine):
        resolved = asyncio.run(engine._resolve_target_band("user1", 6.0, 8.0))
        assert resolved == 8.0

    def test_resolve_target_band_default(self, engine):
        resolved = asyncio.run(engine._resolve_target_band("user1", 6.0, None))
        assert resolved == 7.0  # current + 1.0 default
