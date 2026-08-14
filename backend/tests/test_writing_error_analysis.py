"""
Tests for the Writing Error Analysis feature.

Deterministic — the AI path is mocked via ``httpx.AsyncClient``; offline paths
exercise the real rule-based detectors. Validates the nine error categories,
normalisation (type/severity/criterion), highlight offsets, the deterministic
fallback detectors, and the engine integration (storage + projection).
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services import ai_service
from app.services.ai_service import (
    AIService,
    _normalize_error_analysis,
    _normalize_error_type,
    _normalize_severity,
    _normalize_criterion,
)
from app.services.writing_evaluation_engine import WritingEvaluationEngine


# ─── Normalisation ────────────────────────────────────────────────────
class TestNormalization:
    def test_error_type_labels_complete(self):
        labels = set(ai_service.ERROR_TYPE_LABELS)
        expected = {
            "Grammar", "Vocabulary", "Spelling", "Punctuation",
            "Sentence Structure", "Cohesion", "Repetition", "Word Choice",
            "Task Response",
        }
        assert labels == expected

    def test_error_type_alias_mapping(self):
        assert _normalize_error_type("sentence_structure") == "Sentence Structure"
        assert _normalize_error_type("task-response") == "Task Response"
        assert _normalize_error_type("grammar") == "Grammar"
        assert _normalize_error_type(None) == "Grammar"  # default

    def test_severity_normalization(self):
        assert _normalize_severity("critical") == "critical"
        assert _normalize_severity("high") == "critical"
        assert _normalize_severity("medium") == "major"
        assert _normalize_severity("low") == "minor"
        assert _normalize_severity("spelling") == "minor"  # fallback default

    def test_criterion_normalization(self):
        assert _normalize_criterion("lexical_resource", "Grammar") == "lexical_resource"
        assert _normalize_criterion("Lexical Resource", "Grammar") == "lexical_resource"
        # Falls back to the canonical mapping for the error type.
        assert _normalize_criterion(None, "Grammar") == "grammatical_range_accuracy"
        assert _normalize_criterion(None, "Cohesion") == "coherence_cohesion"
        assert _normalize_criterion(None, "Task Response") == "task_response"

    def test_normalize_error_analysis_shapes_and_offsets(self):
        text = "The childs go to school. They study hard."
        raw = [
            {"original": "The childs", "error_type": "Grammar", "explanation": "wrong plural",
             "correction": "The children", "severity": "major", "criterion": "not-a-key"},
            {"original": "does not exist here", "error_type": "Spelling", "explanation": "x",
             "correction": "y", "severity": "minor"},
        ]
        result = _normalize_error_analysis(raw, text)
        assert len(result) == 2
        assert result[0]["error_type"] == "Grammar"
        # unknown criterion falls back to grammar mapping
        assert result[0]["criterion"] == "grammatical_range_accuracy"
        assert result[0]["start"] == text.find("The childs")
        assert result[0]["end"] == text.find("The childs") + len("The childs")
        # unmatched text -> offsets (0,0), still listed
        assert result[1]["start"] == 0 and result[1]["end"] == 0
        # invalid raw entries dropped
        assert _normalize_error_analysis([{"description": "no original"}], text) == []
        assert _normalize_error_analysis("not-a-list", text) == []

    def test_error_payload_truncates_long_fields(self):
        err = ai_service._error_payload(
            original="x" * 500, error_type="Grammar", explanation="e" * 800,
            correction="c" * 500, severity="major", criterion="grammatical_range_accuracy",
            start=-5, end=10,
        )
        assert len(err["original"]) == 400
        assert len(err["explanation"]) == 600
        assert len(err["correction"]) == 400
        assert err["start"] == 0  # clamped
# ─── Deterministic fallback detectors ─────────────────────────────────
class TestFallbackErrorAnalysis:
    def _svc(self):
        # No API key -> forces offline path.
        svc = AIService()
        svc.api_key = None
        return svc

    def test_task_response_under_word_count(self):
        svc = self._svc()
        essay = "This is a short essay."
        result = svc._fallback_error_analysis(essay, "task_2")
        types = {e["error_type"] for e in result}
        assert "Task Response" in types
        task_err = next(e for e in result if e["error_type"] == "Task Response")
        assert task_err["severity"] == "critical"
        assert task_err["criterion"] == "task_response"

    def test_spelling_detected(self):
        svc = self._svc()
        essay = "The goverment should invest in education. The goverment must act now."
        result = svc._fallback_error_analysis(essay, "task_2")
        assert any(e["error_type"] == "Spelling" and "goverment" in e["original"] for e in result)

    def test_repetition_detected(self):
        svc = self._svc()
        essay = (
            "The environment is important. The environment suffers. "
            "The environment needs care. The environment matters. "
            "The environment is vital for everyone."
        )
        result = svc._fallback_error_analysis(essay, "task_2")
        assert any(e["error_type"] == "Repetition" for e in result)

    def test_word_choice_detected(self):
        svc = self._svc()
        essay = "Some kids and stuff are involved. Kids need guidance."
        result = svc._fallback_error_analysis(essay, "task_2")
        assert any(e["error_type"] == "Word Choice" for e in result)

    def test_punctuation_detected(self):
        svc = self._svc()
        # Final sentence is missing its terminal full stop.
        essay = "Education is essential for children. It shapes their future"
        result = svc._fallback_error_analysis(essay, "task_2")
        assert any(e["error_type"] == "Punctuation" for e in result)

    def test_sentence_structure_detected(self):
        svc = self._svc()
        long_sentence = " ".join(["word"] * 60) + "."
        essay = f"Some other sentence here. {long_sentence} And more text."
        result = svc._fallback_error_analysis(essay, "task_2")
        assert any(e["error_type"] == "Sentence Structure" for e in result)

    def test_cohesion_detected_without_linkers(self):
        svc = self._svc()
        essay = (
            "The first reason is clear. The second point matters a lot. "
            "The third argument is strong. The final idea is important."
        )
        result = svc._fallback_error_analysis(essay, "task_2")
        assert any(e["error_type"] == "Cohesion" for e in result)

    def test_all_errors_have_required_fields(self):
        svc = self._svc()
        essay = (
            "The goverment must address this. The goverment must act. The goverment must change. "
            "The goverment must respond. The goverment must decide. Kids stuff included."
        )
        result = svc._fallback_error_analysis(essay, "task_2")
        for e in result:
            for key in ("id", "original", "error_type", "explanation", "correction",
                        "severity", "criterion", "start", "end"):
                assert key in e, f"missing {key}"


# ─── AI path with mocked httpx ────────────────────────────────────────
class TestAnalyzeWritingErrorsAI:
    async def _run(self, content):
        svc = AIService()
        svc.api_key = "test-key"
        with patch.object(ai_service, "AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"choices": [{"message": {"content": content}}]}
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            return await svc.analyze_writing_errors("The childs go.", "task_2", "prompt")

    def test_parses_valid_json(self):
        content = '{"errors": [{"original": "The childs", "error_type": "grammar", "explanation": "e", "correction": "The children", "severity": "high", "criterion": "grammatical_range_accuracy"}]}'
        result = asyncio.run(self._run(content))
        assert result["source"] == "ai"
        assert result["error_analysis"][0]["error_type"] == "Grammar"
        assert result["error_analysis"][0]["severity"] == "critical"  # high -> critical
        assert result["error_analysis"][0]["start"] == 0

    def test_handles_fence_and_errors_key(self):
        content = '```json\n{"errors": []}\n```'
        result = asyncio.run(self._run(content))
        assert result["error_analysis"] == []

    def test_ai_failure_uses_fallback(self):
        svc = AIService()
        svc.api_key = "test-key"
        with patch.object(ai_service, "AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=Exception("boom"))
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            result = asyncio.run(svc.analyze_writing_errors(
                "The goverment. The goverment. The goverment. The goverment. The goverment.", "task_2"))
            assert result["source"] == "deterministic_fallback"
            assert result["error_analysis"]  # non-empty fallback
# ─── Engine integration ───────────────────────────────────────────────
class TestEngineIntegration:
    @pytest.fixture
    def engine(self):
        eng = WritingEvaluationEngine(db=MagicMock())
        eng.db = MagicMock()
        eng.repo = MagicMock()
        eng.ai_service = MagicMock()
        return eng

    def test_evaluate_stores_error_analysis(self, engine):
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted", "task_type": "task_2",
            "essay_text": "The childs go to school.", "prompt_text": "",
            "word_count": 6, "ai_evaluation": None,
        }
        engine.repo.get_evaluation.return_value = None
        engine.repo.create_evaluation.return_value = {"id": "eval1", "status": "pending"}
        engine.ai_service.analyze_writing = AsyncMock(return_value={
            "criteria": {}, "overall_band": 6.0, "confidence": 0.7,
            "is_estimate": True, "word_count": 6, "source": "ai",
        })
        errors = [{
            "id": "err-1", "original": "The childs", "error_type": "Grammar",
            "explanation": "e", "correction": "The children", "severity": "major",
            "criterion": "grammatical_range_accuracy", "start": 0, "end": 10, "sentence": "",
        }]
        engine.ai_service.analyze_writing_errors = AsyncMock(return_value={
            "error_analysis": errors, "source": "deterministic_fallback",
        })
        engine.repo.update_evaluation.return_value = {
            "id": "eval1", "status": "evaluated", "overall_band": 6.0,
            "confidence": 0.7, "error_analysis": errors, "source": "deterministic_fallback",
        }

        result = asyncio.run(engine.evaluate_submission("user1", "sub1"))

        # The stored payload must include error_analysis.
        payload = engine.repo.update_evaluation.call_args[0][2]
        assert payload["error_analysis"] == errors
        # And it is projected into the response.
        assert result["error_analysis"] == errors

    def test_evaluate_error_analysis_failure_is_not_fatal(self, engine):
        engine.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted", "task_type": "task_2",
            "essay_text": "essay", "prompt_text": "", "word_count": 100,
        }
        engine.repo.get_evaluation.return_value = None
        engine.repo.create_evaluation.return_value = {"id": "eval1", "status": "pending"}
        engine.ai_service.analyze_writing = AsyncMock(return_value={
            "criteria": {}, "overall_band": 6.0, "confidence": 0.7,
            "is_estimate": True, "word_count": 100, "source": "ai",
        })
        engine.ai_service.analyze_writing_errors = AsyncMock(side_effect=Exception("boom"))
        engine.repo.update_evaluation.return_value = {"id": "eval1", "status": "evaluated"}

        result = asyncio.run(engine.evaluate_submission("user1", "sub1"))
        assert result["evaluation_status"] == "evaluated"
        assert result["error_analysis"] == []

    def test_to_response_projects_error_analysis(self):
        errors = [{
            "id": "err-1", "original": "text", "error_type": "Grammar",
            "explanation": "e", "correction": "c", "severity": "major",
            "criterion": "grammatical_range_accuracy", "start": 0, "end": 4, "sentence": "",
        }]
        evaluation = {
            "id": "eval1", "task_type": "task_2", "status": "evaluated",
            "overall_band": 6.5, "confidence": 0.8, "criteria_bands": {},
            "criteria_detail": {}, "word_count": 100, "is_estimate": True,
            "source": "ai", "error_analysis": errors,
        }
        result = WritingEvaluationEngine._to_response(evaluation)
        assert result["error_analysis"] == errors

    def test_to_response_defaults_empty_analysis(self):
        evaluation = {
            "id": "eval1", "task_type": "task_2", "status": "pending",
            "criteria_bands": {}, "criteria_detail": {}, "word_count": 0,
            "is_estimate": True, "source": "pending",
        }
        result = WritingEvaluationEngine._to_response(evaluation)
        assert result["error_analysis"] == []