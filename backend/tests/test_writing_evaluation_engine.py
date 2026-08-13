"""
Tests for the Writing Evaluation Engine.

Deterministic — mocks the AI service so no real API calls are made.
Validates the scoring algorithm, confidence computation, fallback analysis,
and the engine's business logic (owner-scoping, pending record creation,
AI evaluation flow, immutability).
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.writing_evaluation_engine import WritingEvaluationEngine
from app.services.ai_service import (
    AIService,
    _round_band,
    _compute_overall_band,
    _compute_confidence,
)
from app.core.exceptions import NotFoundError, ValidationError


# ─── Scoring algorithm unit tests ─────────────────────────────────────
class TestBandRounding:
    """Validate the IELTS band-rounding formula."""

    def test_round_to_half(self):
        assert _round_band(5.1) == 5.0
        assert _round_band(5.3) == 5.5
        assert _round_band(6.6) == 6.5
        assert _round_band(6.8) == 7.0

    def test_clamp_min(self):
        assert _round_band(-1) == 0.0

    def test_clamp_max(self):
        assert _round_band(10) == 9.0


class TestOverallBand:
    """
    Overall band formula:
      overall = round_to_half(mean(4 criteria))
    NOT a simple average without rounding.
    """

    def test_mean_of_four_clamped(self):
        bands = {
            "task_response": 6.0,
            "coherence_cohesion": 7.0,
            "lexical_resource": 6.5,
            "grammatical_range_accuracy": 6.5,
        }
        result = _compute_overall_band(bands, "task_2")
        expected = round((6.0 + 7.0 + 6.5 + 6.5) / 4 * 2) / 2
        assert result == expected

    def test_rounding_not_plain_average(self):
        """6.125 should round to 6.0, not stay 6.125."""
        bands = {
            "task_response": 6.0,
            "coherence_cohesion": 6.0,
            "lexical_resource": 6.0,
            "grammatical_range_accuracy": 6.5,
        }
        result = _compute_overall_band(bands, "task_2")
        assert result == 6.0

    def test_empty_bands(self):
        assert _compute_overall_band({}, "task_2") == 0.0

    def test_all_nines(self):
        bands = {
            "task_response": 9.0,
            "coherence_cohesion": 9.0,
            "lexical_resource": 9.0,
            "grammatical_range_accuracy": 9.0,
        }
        assert _compute_overall_band(bands, "task_2") == 9.0

    def test_task1_uses_achievement_label(self):
        """Overall band formula is the same for both task types."""
        bands = {
            "task_response": 7.0,
            "coherence_cohesion": 7.0,
            "lexical_resource": 7.0,
            "grammatical_range_accuracy": 7.0,
        }
        result = _compute_overall_band(bands, "task_1")
        assert result == 7.0


class TestConfidence:
    """Confidence is based on essay length and criterion spread."""

    def test_base_confidence(self):
        bands = {
            "task_response": 6.0,
            "coherence_cohesion": 6.0,
            "lexical_resource": 6.0,
            "grammatical_range_accuracy": 6.0,
        }
        c = _compute_confidence(bands, 50)
        assert 0.0 <= c <= 1.0
        assert c >= 0.7  # base is 0.7

    def test_short_essay_lower_confidence(self):
        bands = {
            "task_response": 6.0,
            "coherence_cohesion": 6.0,
            "lexical_resource": 6.0,
            "grammatical_range_accuracy": 6.0,
        }
        c_short = _compute_confidence(bands, 10)
        c_long = _compute_confidence(bands, 500)
        assert c_long >= c_short

    def test_wide_spread_lower_confidence(self):
        bands_narrow = {
            "task_response": 6.0,
            "coherence_cohesion": 6.0,
            "lexical_resource": 6.0,
            "grammatical_range_accuracy": 6.0,
        }
        bands_wide = {
            "task_response": 5.0,
            "coherence_cohesion": 7.0,
            "lexical_resource": 5.0,
            "grammatical_range_accuracy": 7.0,
        }
        c_narrow = _compute_confidence(bands_narrow, 200)
        c_wide = _compute_confidence(bands_wide, 200)
        assert c_wide <= c_narrow

    def test_confidence_clamped(self):
        bands = {
            "task_response": 9.0,
            "coherence_cohesion": 0.0,
            "lexical_resource": 9.0,
            "grammatical_range_accuracy": 0.0,
        }
        c = _compute_confidence(bands, 5000)
        assert 0.0 <= c <= 1.0


# ─── Fallback analysis (no AI key) ─────────────────────────────────────
class TestFallbackAnalysis:
    """The deterministic fallback used when OpenAI key is not configured."""

    def test_fallback_has_four_criteria(self):
        svc = AIService()
        svc.api_key = None  # force fallback
        result = svc._fallback_analysis(
            "This is a test essay with enough words to pass basic checks.", "task_2"
        )
        assert "criteria" in result
        assert result["criteria"]["task_response"]["label"] == "Task Response"
        assert result["is_estimate"] is True
        assert result["source"] == "deterministic_fallback"

    def test_fallback_task1_label(self):
        svc = AIService()
        svc.api_key = None
        result = svc._fallback_analysis("Test essay.", "task_1")
        assert result["criteria"]["task_response"]["label"] == "Task Achievement"

    def test_fallback_word_count(self):
        svc = AIService()
        svc.api_key = None
        text = "one two three four five six"
        result = svc._fallback_analysis(text, "task_2")
        assert result["word_count"] == 6

    def test_fallback_has_suggestions(self):
        svc = AIService()
        svc.api_key = None
        result = svc._fallback_analysis("Some essay text here.", "task_2")
        for c in result["criteria"].values():
            assert len(c["suggestions"]) > 0

    def test_fallback_overall_is_half_step(self):
        svc = AIService()
        svc.api_key = None
        result = svc._fallback_analysis("Some essay text here.", "task_2")
        assert result["overall_band"] % 0.5 == 0


# ─── Engine tests (mocked DB + AI) ─────────────────────────────────────
class TestWritingEvaluationEngine:
    """Validate the WritingEvaluationEngine business logic."""

    @pytest.fixture
    def engine(self):
        eng = WritingEvaluationEngine(db=MagicMock())
        eng.db = MagicMock()
        eng.repo = MagicMock()
        eng.ai_service = MagicMock()
        return eng

    def test_get_evaluation_not_found(self, engine):
        engine.repo.get_submission.return_value = None
        with pytest.raises(NotFoundError):
            engine.get_evaluation("user1", "sub1")

    def test_get_evaluation_no_record(self, engine):
        engine.repo.get_submission.return_value = {"id": "sub1", "status": "submitted"}
        engine.repo.get_evaluation.return_value = None
        with pytest.raises(NotFoundError):
            engine.get_evaluation("user1", "sub1")

    def test_get_evaluation_pending(self, engine):
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted",
        }
        engine.repo.get_evaluation.return_value = {
            "id": "eval1", "submission_id": "sub1", "task_type": "task_2",
            "status": "pending", "overall_band": None, "confidence": None,
            "criteria_bands": {}, "criteria_detail": {}, "word_count": 250,
            "is_estimate": True, "source": "pending",
        }
        result = engine.get_evaluation("user1", "sub1")
        assert result["evaluation_status"] == "pending"
        assert result["overall_band"] is None
        assert result["is_estimate"] is True

    def test_evaluate_submission_not_found(self, engine):
        engine.repo.get_submission.return_value = None
        with pytest.raises(NotFoundError):
            asyncio.run(engine.evaluate_submission("user1", "sub1"))

    def test_evaluate_submission_not_submitted(self, engine):
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "draft",
        }
        with pytest.raises(ValidationError):
            asyncio.run(engine.evaluate_submission("user1", "sub1"))

    def test_evaluate_submission_runs_ai_and_stores(self, engine):
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted", "task_type": "task_2",
            "essay_text": "essay text", "prompt_text": "prompt",
            "word_count": 250, "ai_evaluation": None,
        }
        engine.repo.get_evaluation.return_value = None
        engine.repo.create_evaluation.return_value = {
            "id": "eval1", "submission_id": "sub1", "task_type": "task_2",
            "status": "pending",
        }
        engine.ai_service.analyze_writing = AsyncMock(return_value={
            "task_type": "task_2",
            "criteria": {
                "task_response": {"band": 7.0, "label": "Task Response", "strength": "S1", "weakness": "W1", "errors": ["e1"], "suggestions": ["s1"]},
                "coherence_cohesion": {"band": 6.5, "label": "Coherence and Cohesion", "strength": "S2", "weakness": "W2", "errors": ["e2"], "suggestions": ["s2"]},
                "lexical_resource": {"band": 7.0, "label": "Lexical Resource", "strength": "S3", "weakness": "W3", "errors": [], "suggestions": ["s3"]},
                "grammatical_range_accuracy": {"band": 7.5, "label": "Grammatical Range and Accuracy", "strength": "S4", "weakness": "W4", "errors": [], "suggestions": ["s4"]},
            },
            "overall_band": 7.0,
            "confidence": 0.85,
            "is_estimate": True,
            "word_count": 250,
            "source": "ai",
            "strengths": ["S1"],
            "weaknesses": ["W1"],
            "errors": ["e1", "e2"],
            "suggestions": ["s1", "s2", "s3", "s4"],
        })
        engine.repo.update_evaluation.return_value = {
            "id": "eval1", "status": "evaluated", "overall_band": 7.0,
            "confidence": 0.85, "criteria_bands": {"task_response": 7.0},
            "criteria_detail": {}, "strengths": ["S1"], "weaknesses": ["W1"],
            "errors": ["e1", "e2"], "suggestions": ["s1","s2","s3","s4"],
            "word_count": 250, "is_estimate": True, "source": "ai",
        }

        result = asyncio.run(engine.evaluate_submission("user1", "sub1"))

        assert result["overall_band"] == 7.0
        assert result["is_estimate"] is True
        assert result["evaluation_status"] == "evaluated"
        engine.ai_service.analyze_writing.assert_called_once()
        engine.repo.create_evaluation.assert_called_once()
        engine.repo.update_evaluation.assert_called_once()
        engine.repo.update_submission.assert_called_once()

    def test_evaluate_submission_reuses_existing_evaluation(self, engine):
        """If an evaluation record already exists, don't create a new one."""
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted", "task_type": "task_2",
            "essay_text": "essay", "prompt_text": "", "word_count": 100,
        }
        engine.repo.get_evaluation.return_value = {
            "id": "existing", "status": "pending",
        }
        engine.ai_service.analyze_writing = AsyncMock(return_value={
            "criteria": {}, "overall_band": 6.5, "confidence": 0.8,
            "is_estimate": True, "word_count": 100, "source": "ai",
        })
        engine.repo.update_evaluation.return_value = {
            "id": "existing", "status": "evaluated", "overall_band": 6.5,
        }

        result = asyncio.run(engine.evaluate_submission("user1", "sub1"))
        assert result["overall_band"] == 6.5
        engine.repo.create_evaluation.assert_not_called()

    def test_list_evaluations_empty(self, engine):
        engine.repo.list_evaluations.return_value = []
        result = engine.get_user_evaluations("user1", 20)
        assert result["total"] == 0
        assert result["results"] == []

    def test_list_evaluations_with_data(self, engine):
        engine.repo.list_evaluations.return_value = [
            {
                "submission_id": "sub1", "task_type": "task_2",
                "status": "evaluated", "overall_band": 7.0,
                "confidence": 0.85, "word_count": 250,
                "created_at": "2025-01-01",
            },
            {
                "submission_id": "sub2", "task_type": "task_1",
                "status": "pending", "overall_band": None,
                "confidence": None, "word_count": 100,
                "created_at": "2025-01-02",
            },
        ]
        result = engine.get_user_evaluations("user1", 20)
        assert result["total"] == 2
        assert result["results"][0]["submission_id"] == "sub1"
        assert result["results"][0]["overall_band"] == 7.0
        assert result["results"][1]["evaluation_status"] == "pending"

    def test_to_response_with_full_evaluation(self, engine):
        """Test _to_response correctly projects a full evaluated record."""
        evaluation = {
            "id": "eval1", "task_type": "task_2",
            "status": "evaluated", "overall_band": 7.5,
            "confidence": 0.9,
            "criteria_bands": {"task_response": 7.0},
            "criteria_detail": {
                "task_response": {"band": 7.0, "label": "Task Response", "strength": "S", "weakness": "W", "errors": [], "suggestions": []},
                "coherence_cohesion": {"band": 7.5, "label": "Coherence and Cohesion", "strength": "S", "weakness": "W", "errors": [], "suggestions": []},
                "lexical_resource": {"band": 8.0, "label": "Lexical Resource", "strength": "S", "weakness": "W", "errors": [], "suggestions": []},
                "grammatical_range_accuracy": {"band": 7.5, "label": "Grammatical Range and Accuracy", "strength": "S", "weakness": "W", "errors": [], "suggestions": []},
            },
            "word_count": 250, "is_estimate": True, "source": "ai",
        }
        result = WritingEvaluationEngine._to_response(evaluation)
        assert result["overall_band"] == 7.5
        assert result["is_estimate"] is True
        assert result["evaluation_status"] == "evaluated"
        assert "task_response" in result["criteria"]
        assert result["criteria"]["task_response"]["label"] == "Task Response"

    def test_to_response_pending_record(self, engine):
        """Pending records should have overall_band=None and empty details."""
        evaluation = {
            "id": "eval1", "task_type": "task_2",
            "status": "pending", "overall_band": None,
            "confidence": None,
            "criteria_bands": {},
            "criteria_detail": {},
            "word_count": 0, "is_estimate": True, "source": "pending",
        }
        result = WritingEvaluationEngine._to_response(evaluation)
        assert result["overall_band"] is None
        assert result["confidence"] is None
        assert result["is_estimate"] is True
        assert result["evaluation_status"] == "pending"

    def test_to_response_is_always_estimate(self, engine):
        """is_estimate must always be True — AI bands are estimates, not official."""
        evaluation = {
            "id": "eval1", "task_type": "task_2",
            "status": "evaluated", "overall_band": 9.0,
            "confidence": 0.99, "criteria_bands": {}, "criteria_detail": {},
            "word_count": 250, "is_estimate": True, "source": "ai",
        }
        result = WritingEvaluationEngine._to_response(evaluation)
        assert result["is_estimate"] is True
        assert result["is_official"] is False
