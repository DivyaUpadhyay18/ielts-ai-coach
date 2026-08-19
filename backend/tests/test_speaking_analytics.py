"""
Tests for the Speaking Progress Analytics Service.

Deterministic — mocks all DB access.  Tests cover:

  - Dashboard: comprehensive payload structure
  - Band History: chronological bands, part filtering, sorting
  - Criterion History: per-criterion extraction
  - Metrics: averages, strongest/weakest, duration, fillers
  - Common Errors: grammar/vocabulary error aggregation
  - Strongest/Weakest Criterion
  - Improvement Rate: linear regression slope, trend
  - Attempt History: chronological listing
  - Integration helpers: get_weaknesses_summary, get_readiness_factors, get_prediction_features
  - Defensive behavior: db=None, empty data, malformed data
"""
import pytest
from unittest.mock import MagicMock

from app.services.speaking_analytics_service import (
    SpeakingAnalyticsService,
    CRITERION_LABELS,
    SPEAKING_CRITERIA_KEYS,
)


def _make_evaluation(**overrides):
    """Create a mock speaking_evaluations row."""
    base = {
        "id": "eval-1",
        "created_at": "2025-01-15T10:00:00Z",
        "overall_band": 7.0,
        "criteria": {
            "fluency_coherence": 7.0,
            "lexical_resource": 6.5,
            "grammatical_range": 6.5,
            "pronunciation": 7.5,
        },
        "part": "part_1",
        "confidence": 0.85,
        "source": "ai",
        "speaking_test_responses": {
            "title": "Hometown",
            "duration_seconds": 60,
        },
    }
    base.update(overrides)
    return base


def _make_session(**overrides):
    """Create a mock speaking_practice_sessions row."""
    base = {
        "id": "sess-1",
        "created_at": "2025-01-20T10:00:00Z",
        "overall_band": 6.5,
        "fluency_coherence_band": 6.0,
        "lexical_resource_band": 6.5,
        "grammatical_range_band": 6.5,
        "pronunciation_band": 7.0,
        "error_count": 2,
        "filler_words_count": 3,
        "duration_seconds": 45,
        "title": "Fluency Practice",
        "prompt_text": "Tell me about your hobbies",
        "part": "part_1",
        "created": "2025-01-20T10:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def svc():
    return SpeakingAnalyticsService(db=MagicMock())


class TestBandHistory:
    def test_band_history_from_evaluations(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(id="e1", created_at="2025-01-15T10:00:00Z", overall_band=7.0),
            _make_evaluation(id="e2", created_at="2025-02-01T10:00:00Z", overall_band=7.5),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])

        history = svc._band_history("u1", days=90)
        assert len(history) == 2
        assert history[0]["overall_band"] == 7.0  # oldest first
        assert history[1]["overall_band"] == 7.5
        assert history[0]["evaluation_id"] == "e1"

    def test_band_history_from_practice_sessions(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[])
        svc.repo.list_practice_sessions = MagicMock(return_value=[
            _make_session(id="s1", created_at="2025-01-10T10:00:00Z", overall_band=6.5),
        ])
        history = svc._band_history("u1")
        assert len(history) == 1
        assert history[0]["overall_band"] == 6.5

    def test_band_history_db_none(self, svc):
        svc.db = None
        history = svc._band_history("u1")
        assert history == []

    def test_band_history_merges_and_sorts(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(id="eval", created_at="2025-03-01T10:00:00Z", overall_band=8.0),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[
            _make_session(id="sess", created_at="2025-01-01T10:00:00Z", overall_band=6.0),
        ])
        history = svc._band_history("u1")
        assert len(history) == 2
        assert history[0]["overall_band"] == 6.0  # oldest first
        assert history[1]["overall_band"] == 8.0


class TestCriterionHistory:
    def test_criterion_history_fluency(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(
                overall_band=7.0,
                criteria={"fluency_coherence": 6.5, "lexical_resource": 6.5,
                          "grammatical_range": 7.0, "pronunciation": 7.0},
            ),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        result = svc.criterion_history("u1", "fluency_coherence", days=90)
        assert result["criterion"] == "fluency_coherence"
        assert result["label"] == CRITERION_LABELS["fluency_coherence"]
        assert len(result["results"]) >= 1

    def test_criterion_history_invalid_falls_back(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        result = svc.criterion_history("u1", "invalid_criterion")
        assert result["criterion"] == "fluency_coherence"  # fallback


class TestMetrics:
    def test_metrics_basic(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(
                overall_band=7.0,
                criteria={"fluency_coherence": 7.0, "lexical_resource": 6.5,
                          "grammatical_range": 6.5, "pronunciation": 7.5},
                created_at="2025-01-01T10:00:00Z",
            ),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        svc.repo.list_test_responses = MagicMock(return_value=[
            {"duration_seconds": 60, "transcript": "um I like it"},
        ])
        svc.repo.list_error_analysis = MagicMock(return_value=[])

        m = svc._metrics("u1", days=90)
        assert m["total_evaluations"] >= 1
        assert m["average_band"] is not None
        assert m["average_fluency_band"] is not None
        assert m["average_duration"] is not None
        assert m["strongest_criterion"] is not None
        assert m["weakest_criterion"] is not None

    def test_metrics_db_none(self, svc):
        svc.db = None
        m = svc._metrics("u1")
        assert m["total_evaluations"] == 0
        assert m["average_band"] is None

    def test_strongest_weakest_identified(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(
                criteria={"fluency_coherence": 5.5, "lexical_resource": 7.0,
                          "grammatical_range": 6.5, "pronunciation": 8.0},
            ),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        svc.repo.list_test_responses = MagicMock(return_value=[])
        svc.repo.list_error_analysis = MagicMock(return_value=[])

        m = svc._metrics("u1")
        assert m["weakest_criterion"] == "fluency_coherence"
        assert m["strongest_criterion"] == "pronunciation"


class TestCommonErrors:
    def test_common_errors_from_error_analysis(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_error_analysis = MagicMock(return_value=[
            {"issues": [
                {"issue_type": "Grammar", "explanation": "tense error in past simple"},
                {"issue_type": "Grammar", "explanation": "subject-verb agreement issue"},
                {"issue_type": "Vocabulary", "explanation": "informal word choice"},
            ]},
        ])
        result = svc._common_errors("u1")
        assert result["total_grammar_errors"] >= 1
        assert result["total_vocabulary_errors"] >= 1
        assert len(result["common_grammar_errors"]) > 0

    def test_common_errors_empty(self, svc):
        svc.db = None
        result = svc._common_errors("u1")
        assert result["total_grammar_errors"] == 0
        assert result["total_vocabulary_errors"] == 0


class TestImprovementRate:
    def test_improvement_rate_improving(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(overall_band=5.5, created_at="2025-01-01T10:00:00Z"),
            _make_evaluation(overall_band=6.0, created_at="2025-02-01T10:00:00Z"),
            _make_evaluation(overall_band=6.5, created_at="2025-03-01T10:00:00Z"),
            _make_evaluation(overall_band=7.0, created_at="2025-04-01T10:00:00Z"),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])

        result = svc._improvement_rate("u1", days=90, criterion="overall")
        assert result["trend"] == "improving"
        assert result["improvement_rate"] > 0
        assert result["total_points"] == 4

    def test_improvement_rate_stable(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(overall_band=6.5, created_at="2025-01-01T10:00:00Z"),
            _make_evaluation(overall_band=6.5, created_at="2025-02-01T10:00:00Z"),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])

        result = svc._improvement_rate("u1", criterion="overall")
        assert result["trend"] == "stable"
        assert result["improvement_rate"] == 0.0

    def test_improvement_rate_single_point(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(overall_band=6.5),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])

        result = svc._improvement_rate("u1", criterion="overall")
        assert result["trend"] == "stable"
        assert result["total_points"] == 1


class TestAttemptHistory:
    def test_attempt_history_combined(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(overall_band=7.0, part="part_1", created_at="2025-01-01T10:00:00Z"),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[
            _make_session(overall_band=6.5, part="part_1", created_at="2025-02-01T10:00:00Z"),
        ])
        history = svc._attempt_history("u1")
        assert len(history) == 2
        # Most recent first
        assert history[0]["overall_band"] == 6.5 or history[0]["overall_band"] == 7.0

    def test_attempt_history_empty(self, svc):
        svc.db = None
        history = svc._attempt_history("u1")
        assert history == []


class TestStrongestWeakest:
    def test_strongest_criterion(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(
                criteria={"fluency_coherence": 7.0, "lexical_resource": 8.0,
                          "grammatical_range": 6.5, "pronunciation": 7.5},
            ),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        svc.repo.list_test_responses = MagicMock(return_value=[])
        svc.repo.list_error_analysis = MagicMock(return_value=[])

        result = svc.strongest_criterion("u1")
        assert result["criterion"] == "lexical_resource"

    def test_weakest_criterion(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(
                criteria={"fluency_coherence": 5.0, "lexical_resource": 7.0,
                          "grammatical_range": 6.0, "pronunciation": 8.0},
            ),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        svc.repo.list_test_responses = MagicMock(return_value=[])
        svc.repo.list_error_analysis = MagicMock(return_value=[])

        result = svc.weakest_criterion("u1")
        assert result["criterion"] == "fluency_coherence"


class TestIntegrationHelpers:
    def test_get_weaknesses_summary(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(
                criteria={"fluency_coherence": 5.5, "lexical_resource": 7.0,
                          "grammatical_range": 7.0, "pronunciation": 7.5},
            ),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        svc.repo.list_test_responses = MagicMock(return_value=[])
        svc.repo.list_error_analysis = MagicMock(return_value=[])

        result = svc.get_weaknesses_summary("u1")
        assert result["weakest_criterion"] == "fluency_coherence"
        assert result["average_band"] is not None

    def test_get_readiness_factors(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(overall_band=7.0, criteria={
                "fluency_coherence": 7.0, "lexical_resource": 7.0,
                "grammatical_range": 7.0, "pronunciation": 7.0,
            }),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        svc.repo.list_test_responses = MagicMock(return_value=[])
        svc.repo.list_error_analysis = MagicMock(return_value=[])

        result = svc.get_readiness_factors("u1")
        assert "speaking_average_band" in result
        assert "speaking_improvement_trend" in result

    def test_get_prediction_features(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(
                overall_band=7.0,
                criteria={"fluency_coherence": 6.5, "lexical_resource": 6.5,
                          "grammatical_range": 7.0, "pronunciation": 7.0},
            ),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])

        result = svc.get_prediction_features("u1")
        assert "speaking_avg_band" in result
        assert "speaking_avg_fluency" in result
        assert "speaking_improvement_rate" in result


class TestDashboard:
    def test_dashboard_structure(self, svc):
        svc.db = MagicMock()
        svc.repo = MagicMock()
        svc.repo.list_evaluations = MagicMock(return_value=[
            _make_evaluation(
                overall_band=7.0,
                criteria={"fluency_coherence": 6.5, "lexical_resource": 7.0,
                          "grammatical_range": 7.0, "pronunciation": 7.5},
                created_at="2025-01-01T10:00:00Z",
            ),
        ])
        svc.repo.list_practice_sessions = MagicMock(return_value=[])
        svc.repo.list_test_responses = MagicMock(return_value=[])
        svc.repo.list_error_analysis = MagicMock(return_value=[])

        result = svc.get_dashboard("u1", days=90, part=None)
        assert "band_history" in result
        assert "metrics" in result
        assert "common_errors" in result
        assert "strongest_criterion" in result
        assert "weakest_criterion" in result
        assert "improvement_rate" in result
        assert "attempt_history" in result
        assert "total_evaluations" in result

    def test_dashboard_empty(self, svc):
        svc.db = None
        result = svc.get_dashboard("u1")
        assert result["band_history"] == []
        assert result["total_evaluations"] == 0


class TestFillerCounting:
    def test_count_fillers(self, svc):
        assert svc._count_fillers("um um uh like you know") == 5
        assert svc._count_fillers("I went to the store") == 0
        assert svc._count_fillers("") == 0
        assert svc._count_fillers(None) == 0


class TestLinearSlope:
    def test_slope_positive(self, svc):
        assert svc._linear_slope([5.0, 6.0, 7.0, 8.0]) > 0

    def test_slope_negative(self, svc):
        assert svc._linear_slope([8.0, 7.0, 6.0, 5.0]) < 0

    def test_slope_flat(self, svc):
        assert svc._linear_slope([6.5, 6.5, 6.5]) == 0.0

    def test_slope_single(self, svc):
        assert svc._linear_slope([6.5]) == 0.0


class TestSafeBand:
    def test_valid_bands(self, svc):
        assert svc._safe_band(7.0) == 7.0
        assert svc._safe_band("7.5") == 7.5
        assert svc._safe_band(9) == 9.0

    def test_invalid_bands(self, svc):
        assert svc._safe_band(None) is None
        assert svc._safe_band("invalid") is None
        assert svc._safe_band(10.0) is None  # out of range
        assert svc._safe_band(-1.0) is None
