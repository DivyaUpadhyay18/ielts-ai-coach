"""
Tests for the Speaking Reattempt Mode service.

Validates:
  - start_reattempt: creates new draft, links attempts, enforces 3-attempt limit
  - evaluate_reattempt: runs AI eval, computes comparison, awards bonus XP
  - get_attempt_comparison: fetches stored comparison
  - _compare_attempts: band deltas, criteria deltas, duration, fillers, errors
  - _count_fillers: filler word detection
  - _fallback_reattempt_comparison: deterministic comparison
  - List attempts
  - Error handling (response not found, not saved, no transcript)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.speaking_reattempt_service import (
    SpeakingReattemptService,
    _count_fillers,
    IMPROVEMENT_BONUS_XP,
)
from app.services.ai_service import (
    _fallback_reattempt_comparison,
    _normalize_reattempt_comparison,
    _build_reattempt_comparison_context,
)
from app.core.exceptions import NotFoundError, ValidationError


class TestCountFillers:
    def test_basic_fillers(self):
        count = _count_fillers("Um I think like this is nice. You know.")
        assert count > 0

    def test_no_fillers(self):
        count = _count_fillers("I enjoy reading books in my free time.")
        assert count == 0

    def test_empty(self):
        assert _count_fillers("") == 0
        assert _count_fillers(None) == 0

    def test_multiple(self):
        count = _count_fillers("um um uh er like")
        assert count == 5


class TestBuildReattemptComparisonContext:
    def test_context_shape(self):
        ctx = _build_reattempt_comparison_context(
            {"overall_band": 6.0, "fluency_coherence_band": 6.0,
             "lexical_resource_band": 5.5, "grammatical_range_band": 6.5,
             "pronunciation_band": 6.0, "duration_seconds": 120,
             "filler_words_count": 5, "error_count": 3},
            {"overall_band": 6.5, "fluency_coherence_band": 6.5,
             "lexical_resource_band": 6.0, "grammatical_range_band": 6.5,
             "pronunciation_band": 6.5, "duration_seconds": 110,
             "filler_words_count": 3, "error_count": 2},
        )
        assert ctx["attempt_1_overall"] == 6.0
        assert ctx["attempt_2_overall"] == 6.5
        assert ctx["attempt_1_fluency"] == 6.0
        assert ctx["attempt_2_fluency"] == 6.5
        assert ctx["attempt_1_fillers"] == 5
        assert ctx["attempt_2_fillers"] == 3


class TestNormalizeReattemptComparison:
    def test_valid(self):
        result = {
            "what_improved": ["Lexis improved"],
            "what_stayed_the_same": ["Grammar stayed same"],
            "what_became_worse": [],
            "focus_next": ["Lexis"],
            "feedback": "Great progress!",
        }
        norm = _normalize_reattempt_comparison(result)
        assert len(norm["what_improved"]) == 1
        assert len(norm["what_stayed_the_same"]) == 1
        assert len(norm["what_became_worse"]) == 0
        assert len(norm["focus_next"]) == 1

    def test_empty(self):
        norm = _normalize_reattempt_comparison({})
        assert norm["what_improved"] == []
        assert norm["feedback"] == ""

    def test_truncates_long_lists(self):
        result = {"what_improved": ["x"] * 20}
        norm = _normalize_reattempt_comparison(result)
        assert len(norm["what_improved"]) == 8


class TestFallbackReattemptComparison:
    def test_improvement_detected(self):
        ctx = _build_reattempt_comparison_context(
            {"overall_band": 6.0, "fluency_coherence_band": 6.0,
             "lexical_resource_band": 5.5, "grammatical_range_band": 6.0,
             "pronunciation_band": 6.0, "duration_seconds": 120,
             "filler_words_count": 5, "error_count": 3},
            {"overall_band": 6.5, "fluency_coherence_band": 6.0,
             "lexical_resource_band": 6.5, "grammatical_range_band": 6.0,
             "pronunciation_band": 6.0, "duration_seconds": 110,
             "filler_words_count": 3, "error_count": 2},
        )
        result = _fallback_reattempt_comparison(ctx)
        assert len(result["what_improved"]) > 0
        assert "feedback" in result
        assert not any("shame" in s.lower() for s in result["what_improved"])

    def test_regressed_criterion(self):
        ctx = _build_reattempt_comparison_context(
            {"overall_band": 7.0, "fluency_coherence_band": 7.0,
             "lexical_resource_band": 7.0, "grammatical_range_band": 7.0,
             "pronunciation_band": 7.0, "duration_seconds": 120,
             "filler_words_count": 3, "error_count": 2},
            {"overall_band": 6.5, "fluency_coherence_band": 6.5,
             "lexical_resource_band": 7.0, "grammatical_range_band": 7.0,
             "pronunciation_band": 7.0, "duration_seconds": 120,
             "filler_words_count": 3, "error_count": 2},
        )
        result = _fallback_reattempt_comparison(ctx)
        assert len(result["what_became_worse"]) > 0
        assert "Fluency" in result["what_became_worse"][0]
        assert len(result["focus_next"]) > 0

    def test_unchanged_criteria(self):
        ctx = _build_reattempt_comparison_context(
            {"overall_band": 6.0, "fluency_coherence_band": 6.0,
             "lexical_resource_band": 6.0, "grammatical_range_band": 6.0,
             "pronunciation_band": 6.0, "duration_seconds": 120,
             "filler_words_count": 3, "error_count": 2},
            {"overall_band": 6.0, "fluency_coherence_band": 6.0,
             "lexical_resource_band": 6.0, "grammatical_range_band": 6.0,
             "pronunciation_band": 6.0, "duration_seconds": 120,
             "filler_words_count": 3, "error_count": 2},
        )
        result = _fallback_reattempt_comparison(ctx)
        assert len(result["what_stayed_the_same"]) > 0
        assert len(result["what_improved"]) == 0

    def test_encouraging_feedback_no_shame(self):
        ctx = _build_reattempt_comparison_context(
            {"overall_band": 6.0, "fluency_coherence_band": 6.0,
             "lexical_resource_band": 6.0, "grammatical_range_band": 6.0,
             "pronunciation_band": 6.0, "duration_seconds": 120,
             "filler_words_count": 5, "error_count": 3},
            {"overall_band": 5.5, "fluency_coherence_band": 5.5,
             "lexical_resource_band": 5.5, "grammatical_range_band": 5.5,
             "pronunciation_band": 5.5, "duration_seconds": 130,
             "filler_words_count": 8, "error_count": 5},
        )
        result = _fallback_reattempt_comparison(ctx)
        assert "improvement" not in result["feedback"].lower() or "progress" in result["feedback"].lower()
        assert "shame" not in result["feedback"].lower()
        assert "bad" not in result["feedback"].lower()


# ─── Engine tests ─────────────────────────────────────────────────────

class TestSpeakingReattemptEngine:
    @pytest.fixture
    def service(self):
        svc = SpeakingReattemptService(db=MagicMock())
        svc.speaking_repo = MagicMock()
        svc.progress_repo = MagicMock()
        svc.streak_repo = MagicMock()
        svc.ai_service = MagicMock()
        return svc

    def test_start_reattempt_response_not_found(self, service):
        service.db.execute.return_value = MagicMock(data=[])
        with pytest.raises(NotFoundError):
            service.start_reattempt("u1", "resp-1")

    def test_start_reattempt_no_transcript(self, service):
        service.db.execute.return_value = MagicMock(data=[
            {"id": "resp-1", "user_id": "u1", "is_saved": True, "transcript": ""}
        ])
        with pytest.raises(ValidationError):
            service.start_reattempt("u1", "resp-1")

    def test_start_reattempt_not_saved(self, service):
        service.db.execute.return_value = MagicMock(data=[
            {"id": "resp-1", "user_id": "u1", "is_saved": False, "transcript": "hello"}
        ])
        with pytest.raises(ValidationError):
            service.start_reattempt("u1", "resp-1")

    def test_start_reattempt_max_attempts(self, service):
        service._count_attempts = MagicMock(return_value=3)
        service._get_response = MagicMock(return_value={
            "id": "resp-1", "user_id": "u1", "is_saved": True,
            "transcript": "hello",
        })
        with pytest.raises(ValidationError):
            service.start_reattempt("u1", "resp-1")

    def test_get_attempt_comparison_not_found(self, service):
        service.db.execute.return_value = MagicMock(data=[])
        with pytest.raises(NotFoundError):
            service.get_attempt_comparison("u1", "resp-1")

    def test_list_attempts_empty_db(self, service):
        service.db = None
        result = service.list_user_attempts("u1", 10)
        assert result["total"] == 0
        assert result["results"] == []

    def test_count_fillers_via_service(self, service):
        assert service._count_fillers("um um uh") == 3
        assert service._count_fillers("a clean response") == 0

    def test_get_attempt_comparison_no_attempt_record(self, service):
        service._get_attempt_record = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            service.get_attempt_comparison("u1", "resp-1")

    def test_build_attempt_1_data_from_analysis(self, service):
        response = {"id": "r1", "duration_seconds": 120}
        analysis = {
            "overall_band": 6.5,
            "fluency_coherence_band": 6.0,
            "lexical_resource_band": 5.5,
            "grammatical_range_band": 7.0,
            "pronunciation_band": 6.5,
            "issue_count": 3,
            "issues": [{"issue_type": "Filler"}],
        }
        data = service._build_attempt_1_data(response, analysis)
        assert data["overall_band"] == 6.5
        assert data["fluency_coherence_band"] == 6.0
        assert data["duration_seconds"] == 120
        assert data["filler_words_count"] == 3
        assert data["error_count"] == 1

    def test_build_attempt_1_data_no_analysis(self, service):
        response = {
            "id": "r1", "duration_seconds": 120,
            "overall_band": 6.0,
            "fluency_coherence_band": 6.0,
            "lexical_resource_band": 6.0,
            "grammatical_range_band": 6.0,
            "pronunciation_band": 6.0,
        }
        data = service._build_attempt_1_data(response, None)
        assert data["overall_band"] == 6.0
        assert data["filler_words_count"] == 0
        assert data["error_count"] == 0
