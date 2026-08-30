"""
Tests for the Band Improvement Report feature.

Validates:
  - Band descriptor mapping (target criterion bands per overall band)
  - Direction classification (improving / maintained / declining)
  - Criterion reason extraction from evaluation weakness/suggestions text
  - Band rounding helper
  - get_band_improvement_report() end-to-end with mocked evaluation data
  - Empty-data fallback
  - Explicit target band resolution
  - Biggest-improvement identification
  - Overall improvement computation
"""
from unittest.mock import MagicMock

from app.services.writing_analytics_service import (
    BAND_CRITERION_TARGETS,
    CRITERIA_KEYS,
    WritingAnalyticsService,
    _criterion_reason,
    _direction,
    _round_band,
    _target_criterion_bands,
)

# ─── Band descriptor mapping ──────────────────────────────────────────

def test_band_criterion_targets_average_rounds_to_overall():
    for band, criteria in BAND_CRITERION_TARGETS.items():
        avg = sum(criteria.values()) / len(criteria)
        rounded = round(avg * 2) / 2
        assert rounded == band, (
            f"band {band}: avg {avg} -> {rounded} != {band}"
        )


def test_band_criterion_targets_cover_all_bands():
    expected = [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0]
    for b in expected:
        assert b in BAND_CRITERION_TARGETS


def test_band_criterion_targets_cover_all_criteria():
    for criteria in BAND_CRITERION_TARGETS.values():
        for key in CRITERIA_KEYS:
            assert key in criteria


def test_target_criterion_bands_known_band():
    result = _target_criterion_bands(7.0)
    assert result == BAND_CRITERION_TARGETS[7.0]
    assert result["grammatical_range_accuracy"] == 6.5


def test_target_criterion_bands_normalizes_non_half_band():
    """A non-half band should be rounded to the nearest 0.5 and use the mapping."""
    result = _target_criterion_bands(7.3)  # rounds to 7.5
    assert result == BAND_CRITERION_TARGETS[7.5]
    assert result["grammatical_range_accuracy"] == 7.0


def test_target_criterion_bands_fallback_for_unmapped():
    """A band outside the known set still returns all criteria at the rounded band."""
    # 1.0 is not in the mapping, so the fallback returns all criteria at 1.0.
    result = _target_criterion_bands(1.0)
    expected = {k: 1.0 for k in CRITERIA_KEYS}
    assert result == expected


# ─── Round band ───────────────────────────────────────────────────────

def test_round_band_normal():
    assert _round_band(6.375) == 6.5
    assert _round_band(6.875) == 7.0
    assert _round_band(6.0) == 6.0


def test_round_band_clamps():
    assert _round_band(-1.0) == 0.0
    assert _round_band(10.0) == 9.0


# ─── Direction ────────────────────────────────────────────────────────

def test_direction_improving():
    assert _direction(1.0) == "improving"
    assert _direction(0.5) == "improving"
    assert _direction(0.1) == "improving"


def test_direction_maintained():
    assert _direction(0.0) == "maintained"


def test_direction_declining():
    assert _direction(-0.5) == "declining"
    assert _direction(-1.0) == "declining"


# ─── Criterion reason ─────────────────────────────────────────────────

def test_criterion_reason_maintained():
    assert _criterion_reason("task_response", {}, "maintained") == "Maintained"


def test_criterion_reason_improving_keyword_match():
    detail = {
        "task_response": {
            "weakness": "Add more developed arguments and specific examples.",
            "suggestions": ["Fully address every part of the question.", "Develop your ideas with specific examples."],
        }
    }
    reason = _criterion_reason("task_response", detail, "improving")
    assert reason == "Stronger examples"


def test_criterion_reason_coherence_linking():
    detail = {
        "coherence_cohesion": {
            "weakness": "Improve paragraph structure and use a wider range of linking devices.",
            "suggestions": [],
        }
    }
    reason = _criterion_reason("coherence_cohesion", detail, "improving")
    assert reason == "Better paragraph linking"


def test_criterion_reason_grammar_errors():
    detail = {
        "grammatical_range_accuracy": {
            "weakness": "Reduce grammatical errors and proofread for accuracy.",
            "suggestions": ["Proofread for subject-verb agreement.",
                           "Practice complex sentences."],
        }
    }
    reason = _criterion_reason("grammatical_range_accuracy", detail, "improving")
    assert reason == "Fewer grammatical errors"


def test_criterion_reason_no_keyword_fallback():
    detail = {
        "lexical_resource": {
            "weakness": "Some issue not covered by keywords.",
            "suggestions": [],
        }
    }
    reason = _criterion_reason("lexical_resource", detail, "improving")
    assert reason == "Improved lexical resource"


def test_criterion_reason_declining_uses_strength():
    detail = {
        "task_response": {
            "strength": "Addresses all parts of the task well.",
            "weakness": "Something.",
        }
    }
    reason = _criterion_reason("task_response", detail, "declining")
    assert reason == "Fully addresses the task"


def test_criterion_reason_no_detail_fallback():
    reason = _criterion_reason("grammatical_range_accuracy", {}, "improving")
    assert reason == "Improved grammar"


# ─── Service: get_band_improvement_report ─────────────────────────────


def _make_service_with_evals(evals):
    """Create a WritingAnalyticsService with a mocked repo returning *evals*."""
    service = WritingAnalyticsService(MagicMock())
    service.repo = MagicMock()
    service.repo.list_evaluations = MagicMock(return_value=evals)
    return service


def _make_full_evaluation():
    """A realistic evaluation matching the user's example report."""
    return {
        "id": "eval-1",
        "submission_id": "sub-1",
        "user_id": "user-123",
        "task_type": "task_2",
        "overall_band": 6.5,
        "confidence": 0.85,
        "word_count": 280,
        "status": "evaluated",
        "criteria_bands": {
            "task_response": 6.0,
            "coherence_cohesion": 6.5,
            "lexical_resource": 7.0,
            "grammatical_range_accuracy": 6.0,
        },
        "criteria_detail": {
            "task_response": {
                "band": 6.0,
                "label": "Task Response",
                "strength": "Addresses the topic.",
                "weakness": "Add more developed arguments and specific examples.",
                "errors": [],
                "suggestions": [
                    "Fully address every part of the question.",
                    "Develop your ideas with specific examples.",
                ],
            },
            "coherence_cohesion": {
                "band": 6.5,
                "label": "Coherence and Cohesion",
                "strength": "Generally readable.",
                "weakness": "Improve paragraph structure and use a wider range of linking devices.",
                "errors": [],
                "suggestions": [
                    "Use cohesive devices like 'furthermore', 'in contrast'.",
                    "Ensure each paragraph covers one main idea.",
                ],
            },
            "lexical_resource": {
                "band": 7.0,
                "label": "Lexical Resource",
                "strength": "Uses a good range of vocabulary accurately.",
                "weakness": "Avoid occasional repetition.",
                "errors": [],
                "suggestions": [
                    "Use synonyms and topic-specific collocations.",
                ],
            },
            "grammatical_range_accuracy": {
                "band": 6.0,
                "label": "Grammatical Range and Accuracy",
                "strength": "Uses a mix of simple and complex structures.",
                "weakness": "Reduce grammatical errors and proofread for accuracy.",
                "errors": [],
                "suggestions": [
                    "Proofread for subject-verb agreement and article use.",
                    "Practice complex sentences (relative clauses, conditionals).",
                ],
            },
        },
        "error_analysis": [],
        "created_at": "2026-08-01T10:00:00",
    }


def test_improvement_report_matches_user_example():
    """The report should reproduce the example: 6.5 → 7.0, +0.5 band."""
    service = _make_service_with_evals([_make_full_evaluation()])
    report = service.get_band_improvement_report("user-123", target_band=7.0)

    assert report["current_band"] == 6.5
    assert report["target_band"] == 7.0
    assert report["overall_improvement"] == 0.5
    assert report["task_type"] == "task_2"
    assert report["total_evaluated_essays"] == 1

    # Four criteria present, in display order.
    assert len(report["criteria"]) == 4
    labels = [c["label"] for c in report["criteria"]]
    assert labels == ["Task Response", "Coherence & Cohesion", "Lexical Resource", "Grammar"]

    # Task Response: 6 → 7 (biggest improvement).
    tr = report["criteria"][0]
    assert tr["current_band"] == 6.0
    assert tr["target_band"] == 7.0
    assert tr["change"] == 1.0
    assert tr["direction"] == "improving"
    assert tr["reason"] == "Stronger examples"

    # Coherence: 6.5 → 7.
    cc = report["criteria"][1]
    assert cc["current_band"] == 6.5
    assert cc["target_band"] == 7.0
    assert cc["change"] == 0.5
    assert cc["direction"] == "improving"
    assert cc["reason"] == "Better paragraph linking"

    # Lexical Resource: 7 → 7 (maintained).
    lr = report["criteria"][2]
    assert lr["current_band"] == 7.0
    assert lr["target_band"] == 7.0
    assert lr["change"] == 0.0
    assert lr["direction"] == "maintained"
    assert lr["reason"] == "Maintained"

    # Grammar: 6 → 6.5.
    gra = report["criteria"][3]
    assert gra["current_band"] == 6.0
    assert gra["target_band"] == 6.5
    assert gra["change"] == 0.5
    assert gra["direction"] == "improving"
    assert gra["reason"] == "Fewer grammatical errors"

    # Biggest improvement = Task Response (+1.0).
    biggest = report["biggest_improvement"]
    assert biggest is not None
    assert biggest["criterion"] == "task_response"
    assert biggest["change"] == 1.0


def test_improvement_report_uses_latest_evaluation():
    """Should use the first (newest) evaluation from the list."""
    newer = _make_full_evaluation()
    newer["overall_band"] = 7.0
    newer["criteria_bands"] = {
        "task_response": 7.0,
        "coherence_cohesion": 7.0,
        "lexical_resource": 7.0,
        "grammatical_range_accuracy": 6.5,
    }
    older = _make_full_evaluation()
    older["overall_band"] = 6.5
    older["created_at"] = "2026-07-01T10:00:00"

    service = _make_service_with_evals([newer, older])
    report = service.get_band_improvement_report("user-123", target_band=8.0)

    assert report["current_band"] == 7.0
    assert report["target_band"] == 8.0
    assert report["overall_improvement"] == 1.0
    assert report["total_evaluated_essays"] == 2


def test_improvement_report_empty_when_no_evaluations():
    service = _make_service_with_evals([])
    report = service.get_band_improvement_report("user-123")

    assert report["current_band"] == 0.0
    assert report["target_band"] == 0.0
    assert report["overall_improvement"] == 0.0
    assert report["total_evaluated_essays"] == 0
    assert report["criteria"] == []
    assert report["biggest_improvement"] is None


def test_improvement_report_explicit_target_band():
    service = _make_service_with_evals([_make_full_evaluation()])
    report = service.get_band_improvement_report("user-123", target_band=8.0)

    assert report["target_band"] == 8.0
    assert report["current_band"] == 6.5
    assert report["overall_improvement"] == 1.5


def test_improvement_report_default_target_is_current_plus_gap():
    """When no explicit target and no profile, default to current + 1.0."""
    service = _make_service_with_evals([_make_full_evaluation()])
    report = service.get_band_improvement_report("user-123")

    assert report["target_band"] == 7.5  # 6.5 + 1.0
    assert report["overall_improvement"] == 1.0


def test_improvement_report_biggest_when_multiple_improvements():
    eval_row = _make_full_evaluation()
    eval_row["criteria_bands"] = {
        "task_response": 5.5,    # → 7.0 = +1.5
        "coherence_cohesion": 6.5,  # → 7.0 = +0.5
        "lexical_resource": 7.0,   # → 7.0 = 0.0 (maintained)
        "grammatical_range_accuracy": 6.0,  # → 6.5 = +0.5
    }
    eval_row["overall_band"] = 6.5

    service = _make_service_with_evals([eval_row])
    report = service.get_band_improvement_report("user-123", target_band=7.0)

    biggest = report["biggest_improvement"]
    assert biggest["criterion"] == "task_response"
    assert biggest["change"] == 1.5


def test_improvement_report_no_improvement_yields_none_biggest():
    """When no criterion improves, biggest_improvement is None."""
    eval_row = _make_full_evaluation()
    eval_row["overall_band"] = 7.0
    eval_row["criteria_bands"] = {
        "task_response": 7.0,
        "coherence_cohesion": 7.0,
        "lexical_resource": 7.0,
        "grammatical_range_accuracy": 6.5,
    }

    service = _make_service_with_evals([eval_row])
    report = service.get_band_improvement_report("user-123", target_band=7.0)

    assert report["overall_improvement"] == 0.0
    assert report["biggest_improvement"] is None
    for c in report["criteria"]:
        assert c["direction"] == "maintained"


def test_improvement_report_uses_latest_for_reason():
    eval_row = _make_full_evaluation()
    eval_row["criteria_detail"]["task_response"]["weakness"] = "No examples given."
    eval_row["criteria_detail"]["coherence_cohesion"]["weakness"] = "Missing linking words."
    eval_row["criteria_detail"]["grammatical_range_accuracy"]["weakness"] = "Grammar errors everywhere."

    service = _make_service_with_evals([eval_row])
    report = service.get_band_improvement_report("user-123", target_band=7.0)

    tr = report["criteria"][0]
    assert tr["reason"] == "Stronger examples"
    cc = report["criteria"][1]
    assert cc["reason"] == "Better paragraph linking"
    gra = report["criteria"][3]
    assert gra["reason"] == "Fewer grammatical errors"


def test_improvement_report_db_none_returns_empty():
    service = WritingAnalyticsService(None)
    report = service.get_band_improvement_report("user-123", target_band=7.0)
    assert report["total_evaluated_essays"] == 0
    assert report["criteria"] == []


def test_improvement_report_suggestions_list_reason():
    """Reasons can be extracted from the suggestions list, not just weakness."""
    detail = {
        "lexical_resource": {
            "weakness": "Generic weakness.",
            "suggestions": [
                "Use synonyms and topic-specific collocations.",
                "Avoid memorised phrases.",
            ],
        }
    }
    reason = _criterion_reason("lexical_resource", detail, "improving")
    assert reason == "Better word variety"
