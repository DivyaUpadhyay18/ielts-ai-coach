"""
Tests for Writing Coach service.

Deterministic — mocks all DB and LLM dependencies.
Validates context gathering, Q&A flow, conversation persistence, and fallback.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.writing_coach_service import WritingCoachService
from app.core.exceptions import NotFoundError


EVAL = {
    "id": "eval-1",
    "submission_id": "sub-1",
    "task_type": "task_2",
    "overall_band": 6.5,
    "criteria_bands": {
        "task_response": 6.0,
        "coherence_cohesion": 6.5,
        "lexical_resource": 7.0,
        "grammatical_range_accuracy": 6.5,
    },
    "strengths": ["Good vocabulary range"],
    "weaknesses": ["Task Response needs development"],
    "errors": [{"type": "repetition", "criterion": "task_response"}],
    "suggestions": ["Develop your argument further"],
    "word_count": 250,
    "confidence": 0.85,
    "is_estimate": True,
    "status": "evaluated",
}

SUBMISSION = {
    "id": "sub-1",
    "user_id": "u1",
    "prompt_id": "p1",
    "task_type": "task_2",
    "title": "Essay Title",
    "prompt_text": "Discuss the causes and effects of...",
    "word_limit": 250,
    "time_limit_seconds": 2400,
    "essay_text": "This is my essay about something important.",
    "word_count": 250,
    "time_seconds_spent": 1200,
    "status": "submitted",
}


class TestWritingCoachService_Ask:
    """Validate the ask() flow."""

    @pytest.fixture
    def service(self):
        svc = WritingCoachService(db=MagicMock())
        svc.db = MagicMock()
        svc.ai_service = MagicMock()
        svc.repo = MagicMock()
        return svc

    def test_ask_raises_if_submission_not_found(self, service):
        service.repo.get_submission.return_value = None
        with pytest.raises(NotFoundError):
            asyncio.run(service.ask("u1", "sub-999", "Why is my grammar bad?"))

    def test_ask_raises_if_submission_not_submitted(self, service):
        service.repo.get_submission.return_value = {
            "id": "sub-1", "status": "draft", "essay_text": "",
        }
        with pytest.raises(NotFoundError):
            asyncio.run(service.ask("u1", "sub-1", "Why is my grammar bad?"))

    def test_ask_raises_if_no_evaluation(self, service):
        service.repo.get_submission.return_value = SUBMISSION
        service.repo.get_evaluation.return_value = None
        with pytest.raises(NotFoundError):
            asyncio.run(service.ask("u1", "sub-1", "Why is my grammar bad?"))

    def test_ask_returns_coached_answer(self, service):
        service.repo.get_submission.return_value = SUBMISSION
        service.repo.get_evaluation.return_value = EVAL
        service._get_or_create_conversation = MagicMock(return_value={"id": "conv-1"})
        service._list_messages = MagicMock(return_value=[])
        service._call_coach_llm = AsyncMock(return_value={
            "answer": "Your essay has issues with...",
            "focus": "grammar",
            "referenced_text": ["This is my essay"],
            "referenced_feedback": ["Task Response needs development"],
        })
        service._save_message = MagicMock()
        service._touch_conversation = MagicMock()

        result = asyncio.run(service.ask("u1", "sub-1", "Why is my grammar bad?"))

        assert result["conversation_id"] == "conv-1"
        assert result["answer"] == "Your essay has issues with..."
        assert result["focus"] == "grammar"
        assert result["referenced_text"] == ["This is my essay"]
        assert "Task Response needs development" in result["referenced_feedback"]
        # Verify messages were saved (user + coach).
        assert service._save_message.call_count == 2

    def test_ask_fallback_when_no_api_key(self, service):
        service.repo.get_submission.return_value = SUBMISSION
        service.repo.get_evaluation.return_value = EVAL
        service._get_or_create_conversation = MagicMock(return_value={"id": "conv-1"})
        service._list_messages = MagicMock(return_value=[])
        service._save_message = MagicMock()
        service._touch_conversation = MagicMock()

        # Patch the LLM call to return fallback (simulates no API key).
        service._call_coach_llm = AsyncMock(return_value={
            "answer": "I don't have enough information...",
            "focus": "other",
            "referenced_text": [],
            "referenced_feedback": [],
        })

        result = asyncio.run(service.ask("u1", "sub-1", "Generic question"))

        assert "I don't have enough information" in result["answer"]
        assert result["focus"] == "other"


class TestWritingCoachService_Comparison:
    """Validate _evaluation_to_context and _build_llm_messages."""

    @pytest.fixture
    def service(self):
        svc = WritingCoachService(db=None)
        return svc

    def test_evaluation_to_context(self, service):
        ctx = service._evaluation_to_context(EVAL)
        assert ctx["overall_band"] == 6.5
        assert ctx["criteria_bands"]["task_response"] == 6.0
        assert ctx["weaknesses"] == ["Task Response needs development"]
        assert ctx["is_estimate"] is True

    def test_build_llm_messages_includes_question_and_essay(self, service):
        messages = service._build_llm_messages(
            "Why is my Task Response low?",
            "My essay text",
            {"overall_band": 6.5},
            [],
        )
        # First message is system prompt.
        assert messages[0]["role"] == "system"
        # Second message is the user question.
        assert messages[1]["role"] == "user"
        user_content = messages[1]["content"]
        assert "Why is my Task Response low?" in user_content
        assert "My essay text" in user_content
        assert "6.5" in user_content

    def test_build_llm_messages_includes_history(self, service):
        history = [
            {"role": "user", "content": "What is IELTS?"},
            {"role": "coach", "content": "IELTS is..."},
        ]
        messages = service._build_llm_messages(
            "Follow up question",
            "Essay",
            {},
            history,
        )
        # System + history (user, assistant) + current user question = 4 messages.
        assert len(messages) == 4
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"


class TestWritingCoachService_ConversationOps:
    """Validate conversation listing and fetching."""

    @pytest.fixture
    def service(self):
        svc = WritingCoachService(db=MagicMock())
        svc.db = MagicMock()
        svc.ai_service = MagicMock()
        svc.repo = MagicMock()
        return svc

    def test_get_conversation_not_found(self, service):
        service._get_conversation = MagicMock(return_value=None)
        with pytest.raises(NotFoundError):
            service.get_conversation("u1", "conv-999")

    def test_list_conversations_empty_when_no_db(self):
        svc = WritingCoachService(db=None)
        svc.db = None
        result = svc.list_conversations("u1")
        assert result["items"] == []
        assert result["total"] == 0
