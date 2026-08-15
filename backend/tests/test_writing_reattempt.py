"""
Tests for Writing Reattempt Mode.

Deterministic — mocks all DB and engine dependencies.
Validates attempt lifecycle, comparison logic, and bonus XP awarding.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.services.writing_attempt_service import (
    CRITERIA_KEYS,
    IMPROVEMENT_BONUS_XP,
    WritingAttemptService,
)


def _make_eval(bands, word_count=0, time_spent=0, **overrides):
    return {
        "submission_id": overrides.get("submission_id", "sub-1"),
        "task_type": "task_2",
        "attempt_number": overrides.get("attempt_number", 1),
        "overall_band": sum(bands.values()) / len(bands) if bands else 0.0,
        "criteria_bands": bands,
        "strengths": [],
        "weaknesses": [],
        "errors": [],
        "suggestions": [],
        "word_count": word_count,
        "time_seconds_spent": time_spent,
        "is_estimate": True,
        **overrides,
    }


class TestWritingAttemptService_StartReattempt:
    """Validate start_reattempt logic."""

    @pytest.fixture
    def service(self):
        svc = WritingAttemptService(db=MagicMock())
        svc.writing_repo = MagicMock()
        svc.progress_repo = MagicMock()
        svc.streak_repo = MagicMock()
        svc.evaluation_engine = MagicMock()
        svc.mission_service = MagicMock()
        return svc

    def test_start_reattempt_creates_new_draft(self, service):
        original = {
            "id": "sub-1", "user_id": "u1", "prompt_id": "p1",
            "task_type": "task_2", "title": "My Essay",
            "prompt_text": "Write about...", "word_limit": 250,
            "time_limit_seconds": 2400, "status": "submitted",
        }
        service.writing_repo.get_submission.return_value = original
        service.writing_repo.get_evaluation.return_value = _make_eval(
            {"task_response": 6.0, "coherence_cohesion": 6.5,
             "lexical_resource": 6.0, "grammatical_range_accuracy": 6.5},
            submission_id="sub-1", status="evaluated",
        )
        service.writing_repo.create_submission.return_value = {
            "id": "sub-2", "status": "draft", "essay_text": "",
        }
        service._count_attempts = MagicMock(return_value=0)
        service._create_attempt_record = MagicMock(return_value={"id": "att-1"})

        result = service.start_reattempt("u1", "sub-1")

        assert result["original_submission_id"] == "sub-1"
        assert result["attempt_number"] == 1
        assert result["submission"]["id"] == "sub-2"
        service.writing_repo.create_submission.assert_called_once()

    def test_start_reattempt_fails_if_not_submitted(self, service):
        service.writing_repo.get_submission.return_value = {
            "id": "sub-1", "status": "draft",
        }
        with pytest.raises(ValidationError):
            service.start_reattempt("u1", "sub-1")

    def test_start_reattempt_fails_if_not_evaluated(self, service):
        service.writing_repo.get_submission.return_value = {
            "id": "sub-1", "status": "submitted",
        }
        service.writing_repo.get_evaluation.return_value = None
        with pytest.raises(ValidationError):
            service.start_reattempt("u1", "sub-1")


class TestWritingAttemptService_Compare:
    """Validate _compare_attempts logic."""

    @pytest.fixture
    def service(self):
        svc = WritingAttemptService(db=MagicMock())
        svc.writing_repo = MagicMock()
        return svc

    def test_compare_detects_improvement(self, service):
        service.writing_repo.get_evaluation.side_effect = [
            _make_eval(
                {"task_response": 6.0, "coherence_cohesion": 6.5,
                 "lexical_resource": 6.0, "grammatical_range_accuracy": 6.5},
                submission_id="sub-1",
            ),
            _make_eval(
                {"task_response": 7.0, "coherence_cohesion": 7.0,
                 "lexical_resource": 7.0, "grammatical_range_accuracy": 7.0},
                submission_id="sub-2", attempt_number=2,
            ),
        ]
        service.writing_repo.get_submission.side_effect = [
            {"word_count": 250, "time_seconds_spent": 1200},
            {"word_count": 280, "time_seconds_spent": 1100},
        ]
        result = service._compare_attempts("u1", "sub-1", "sub-2")
        assert result["compared"] is True
        assert result["overall_band"]["delta"] == 0.8
        assert result["overall_band"]["improved"] is True
        assert result["improvement"] is True
        assert len(result["criteria"]) == 4
        assert result["word_count"]["delta"] == 30

    def test_compare_no_improvement(self, service):
        service.writing_repo.get_evaluation.side_effect = [
            _make_eval(
                {"task_response": 7.0, "coherence_cohesion": 7.0,
                 "lexical_resource": 7.0, "grammatical_range_accuracy": 7.0},
                submission_id="sub-1",
            ),
            _make_eval(
                {"task_response": 7.0, "coherence_cohesion": 7.0,
                 "lexical_resource": 7.0, "grammatical_range_accuracy": 7.0},
                submission_id="sub-2", attempt_number=2,
            ),
        ]
        service.writing_repo.get_submission.side_effect = [
            {"word_count": 250, "time_seconds_spent": 1200},
            {"word_count": 240, "time_seconds_spent": 1300},
        ]
        result = service._compare_attempts("u1", "sub-1", "sub-2")
        assert result["improvement"] is False

    def test_compare_missing_eval(self, service):
        service.writing_repo.get_evaluation.side_effect = [None, None]
        result = service._compare_attempts("u1", "sub-1", "sub-2")
        assert result["compared"] is False

    def test_criteria_keys(self):
        assert CRITERIA_KEYS == (
            "task_response",
            "coherence_cohesion",
            "lexical_resource",
            "grammatical_range_accuracy",
        )


class TestWritingAttemptService_Evaluate:
    """Validate evaluate_reattempt logic."""

    @pytest.fixture
    def service(self):
        svc = WritingAttemptService(db=MagicMock())
        svc.writing_repo = MagicMock()
        svc.progress_repo = MagicMock()
        svc.streak_repo = MagicMock()
        svc.evaluation_engine = MagicMock()
        svc.mission_service = MagicMock()
        return svc

    def test_evaluate_awards_bonus_on_improvement(self, service):
        import asyncio

        service.writing_repo.get_submission.return_value = {
            "id": "sub-2", "status": "submitted", "task_type": "task_2",
            "word_count": 280,
        }
        service._get_attempt_record = MagicMock(return_value={
            "id": "att-1", "attempt_group": "sub-1", "attempt_number": 2,
        })
        eval_result = _make_eval(
            {"task_response": 7.0, "coherence_cohesion": 7.0,
             "lexical_resource": 7.0, "grammatical_range_accuracy": 7.0},
            submission_id="sub-2", attempt_number=2, overall_band=7.0,
            status="evaluated",
        )
        service.evaluation_engine.evaluate_submission = AsyncMock(
            return_value=eval_result
        )
        service._award_bonus_xp = MagicMock()
        service._update_attempt_record = MagicMock()
        service._compare_attempts = MagicMock(return_value={
            "compared": True, "improvement": True,
        })

        result = asyncio.run(service.evaluate_reattempt("u1", "sub-2"))

        assert result["bonus_xp"] == IMPROVEMENT_BONUS_XP
        assert result["bonus_reason"] == "Meaningful improvement detected"
        assert result["attempt_number"] == 2
        service._award_bonus_xp.assert_called_once()


    def test_evaluate_no_bonus_without_improvement(self, service):
        import asyncio

        service.writing_repo.get_submission.return_value = {
            "id": "sub-2", "status": "submitted", "task_type": "task_2",
            "word_count": 280,
        }
        service._get_attempt_record = MagicMock(return_value={
            "id": "att-1", "attempt_group": "sub-1", "attempt_number": 2,
        })
        eval_result = _make_eval(
            {"task_response": 6.0, "coherence_cohesion": 6.0,
             "lexical_resource": 6.0, "grammatical_range_accuracy": 6.0},
            submission_id="sub-2", attempt_number=2, overall_band=6.0,
            status="evaluated",
        )
        service.evaluation_engine.evaluate_submission = AsyncMock(
            return_value=eval_result
        )
        service._compare_attempts = MagicMock(return_value={
            "compared": True, "improvement": False,
        })
        service._award_bonus_xp = MagicMock()

        result = asyncio.run(service.evaluate_reattempt("u1", "sub-2"))

        assert result["bonus_xp"] == 0
        service._award_bonus_xp.assert_not_called()

    def test_evaluate_fails_if_not_submitted(self, service):
        import asyncio

        service.writing_repo.get_submission.return_value = {
            "id": "sub-2", "status": "draft",
        }
        with pytest.raises(ValidationError):
            asyncio.run(service.evaluate_reattempt("u1", "sub-2"))
