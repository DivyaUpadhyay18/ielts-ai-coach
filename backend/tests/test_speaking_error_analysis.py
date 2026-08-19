"""
Tests for the Speaking Error Analysis engine and AI service.

Validates:
  - Prompt builder produces correct context
  - Normaliser shapes AI output correctly
  - Deterministic fallback detects fillers, repeated vocabulary,
    weak vocabulary, incomplete sentences, pronunciation markers
  - AI path with mocked OpenAI call
  - Engine business logic (response lookup, transcript validation,
    storage, response projection, severity counting)
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services import ai_service
from app.services.ai_service import (
    AIService,
    _build_speaking_errors_prompt,
    _normalize_speaking_error_analysis,
    _fallback_speaking_error_analysis,
)
from app.services.speaking_error_analysis_engine import SpeakingErrorAnalysisEngine


# ─── Prompt builder tests ─────────────────────────────────────────────

def test_build_speaking_errors_prompt_basic():
    context = {
        "part": "part_2",
        "topic": "Describe a memorable journey",
        "word_count": 45,
        "transcript": "I went to the mountains last summer. It was very beautiful.",
    }
    prompt = _build_speaking_errors_prompt(context)
    assert "Part: part_2" in prompt
    assert "Topic: Describe a memorable journey" in prompt
    assert "45" in prompt
    assert "I went to the mountains" in prompt


def test_build_speaking_errors_prompt_defaults():
    context = {}
    prompt = _build_speaking_errors_prompt(context)
    assert "Part: part_1" in prompt
    assert "Estimated word count: 0" in prompt


# ─── Normalisation tests ──────────────────────────────────────────────

def test_normalize_speaking_error_analysis_valid():
    result = {
        "issues": [
            {
                "original_phrase": "um",
                "issue_type": "Filler Words",
                "explanation": "You used 'um' several times.",
                "why_problem": "Fillers interrupt flow.",
                "suggested_improvement": "Pause instead.",
                "criterion_affected": "fluency_coherence",
                "severity": "minor",
                "context": "throughout",
            },
            {
                "original_phrase": "very big",
                "issue_type": "Weak Vocabulary",
                "explanation": "'very' is weak.",
                "why_problem": "limits lexical range.",
                "suggested_improvement": "Use 'enormous'.",
                "criterion_affected": "lexical_resource",
                "severity": "major",
                "context": "middle of response",
            },
        ],
        "overall_band": 6.5,
        "fluency_coherence_band": 6.0,
        "lexical_resource_band": 6.0,
        "grammatical_range_band": 7.0,
        "pronunciation_band": 7.0,
        "feedback": "Good job.",
        "is_estimate": True,
    }
    normalised = _normalize_speaking_error_analysis(result)
    assert len(normalised["issues"]) == 2
    assert normalised["issues"][0]["issue_type"] == "Filler Words"
    assert normalised["overall_band"] == 6.5
    assert "feedback" in normalised


def test_normalize_speaking_error_analysis_empty():
    normalised = _normalize_speaking_error_analysis({})
    assert normalised["issues"] == []
    assert normalised["is_estimate"] is True


def test_normalize_speaking_error_analysis_censors_bad_issue_type():
    result = {
        "issues": [
            {"issue_type": "Made Up Type", "original_phrase": "x",
             "explanation": "y", "why_problem": "z",
             "suggested_improvement": "w", "criterion_affected": "fluency_coherence",
             "severity": "minor"},
            {"issue_type": "Filler Words", "original_phrase": "um",
             "explanation": "y", "why_problem": "z",
             "suggested_improvement": "w", "criterion_affected": "fluency_coherence",
             "severity": "critical"},
        ],
    }
    normalised = _normalize_speaking_error_analysis(result)
    assert len(normalised["issues"]) == 1
    assert normalised["issues"][0]["issue_type"] == "Filler Words"


def test_normalize_speaking_error_analysis_invalid_severity_defaults_minor():
    result = {
        "issues": [
            {"issue_type": "Filler Words", "original_phrase": "um",
             "explanation": "y", "why_problem": "z",
             "suggested_improvement": "w", "criterion_affected": "fluency_coherence",
             "severity": "unknown"},
        ],
    }
    normalised = _normalize_speaking_error_analysis(result)
    assert normalised["issues"][0]["severity"] == "minor"


def test_normalize_speaking_error_analysis_invalid_criterion_defaults_fluency():
    result = {
        "issues": [
            {"issue_type": "Grammar", "original_phrase": "bad grammar",
             "explanation": "y", "why_problem": "z",
             "suggested_improvement": "w", "criterion_affected": "bad",
             "severity": "major"},
        ],
    }
    normalised = _normalize_speaking_error_analysis(result)
    assert normalised["issues"][0]["criterion_affected"] == "fluency_coherence"


def test_normalize_speaking_error_analysis_truncates():
    long = "x" * 2000
    result = {
        "issues": [
            {"original_phrase": long, "issue_type": "Grammar",
             "explanation": long, "why_problem": long,
             "suggested_improvement": long, "criterion_affected": "grammatical_range",
             "severity": "critical"},
        ],
        "feedback": long,
    }
    normalised = _normalize_speaking_error_analysis(result)
    assert len(normalised["issues"][0]["original_phrase"]) <= 300
    assert len(normalised["issues"][0]["suggested_improvement"]) <= 500
    assert len(normalised["feedback"]) <= 800


def test_normalize_speaking_error_analysis_caps_issues():
    issues = [
        {"issue_type": "Grammar", "original_phrase": f"err{i}",
         "explanation": "e", "why_problem": "w",
         "suggested_improvement": "s", "criterion_affected": "grammatical_range",
         "severity": "minor"}
        for i in range(20)
    ]
    normalised = _normalize_speaking_error_analysis({"issues": issues})
    assert len(normalised["issues"]) == 15


# ─── Fallback tests ───────────────────────────────────────────────────

def test_fallback_detects_filler_words():
    transcript = "Um, I think that I very like the mountains. Um."
    context = {"part": "part_2", "topic": "test", "word_count": 10, "transcript": transcript}
    result = _fallback_speaking_error_analysis(context, transcript)
    assert any(i["issue_type"] == "Filler Words" for i in result["issues"])
    assert result["is_estimate"] is True


def test_fallback_detects_repeated_vocabulary():
    transcript = "I like dogs. Dogs are nice. Dogs are good. I think dogs are the best."
    context = {"part": "part_1", "topic": "pets", "word_count": 15, "transcript": transcript}
    result = _fallback_speaking_error_analysis(context, transcript)
    assert any(i["issue_type"] == "Repeated Vocabulary" for i in result["issues"])


def test_fallback_detects_weak_vocabulary_very():
    transcript = "I am very happy with my life and very lucky."
    context = {"part": "part_1", "topic": "happy", "word_count": 10, "transcript": transcript}
    result = _fallback_speaking_error_analysis(context, transcript)
    assert any(i["issue_type"] == "Weak Vocabulary" for i in result["issues"])


def test_fallback_detects_incomplete_sentence():
    transcript = "I really like this topic and I want to talk about"
    context = {"part": "part_3", "topic": "topic", "word_count": 12, "transcript": transcript}
    result = _fallback_speaking_error_analysis(context, transcript)
    assert any(i["issue_type"] == "Incomplete Sentence" for i in result["issues"])


def test_fallback_detects_pronunciation_markers():
    transcript = "I went to dis place called libary."
    context = {"part": "part_1", "topic": "place", "word_count": 10, "transcript": transcript}
    result = _fallback_speaking_error_analysis(context, transcript)
    assert any(i["issue_type"] == "Pronunciation" for i in result["issues"])


def test_fallback_no_issues_for_clean_transcript():
    transcript = "I enjoy reading books in my free time. Reading helps me relax and learn new things."
    context = {"part": "part_1", "topic": "hobbies", "word_count": 20, "transcript": transcript}
    result = _fallback_speaking_error_analysis(context, transcript)
    assert result["issues"] == [] or len(result["issues"]) <= 1
    assert result["overall_band"] >= 6.0


def test_fallback_empty_transcript():
    context = {"part": "part_1", "topic": "", "word_count": 0, "transcript": ""}
    result = _fallback_speaking_error_analysis(context, "")
    assert result["issues"] == []
    assert isinstance(result["feedback"], str)


def test_fallback_coherence_problem_for_short_linkers():
    transcript = ("I like dogs. Dogs are nice. I like cats too. Dogs are better. "
                  "I think animals are great companions in our daily lives. "
                  "They make us happy and give us purposes.")
    context = {"part": "part_1", "topic": "pets", "word_count": 30, "transcript": transcript}
    result = _fallback_speaking_error_analysis(context, transcript)
    assert any(i["issue_type"] == "Coherence Problem" for i in result["issues"])


def test_fallback_severity_counting():
    transcript = "Um um uh uh um. I very very like this and this and this and this and this and this and this and this and this and this."
    context = {"part": "part_2", "topic": "test", "word_count": 25, "transcript": transcript}
    result = _fallback_speaking_error_analysis(context, transcript)
    assert result["issue_count"] == len(result["issues"])
    assert result["high_severity_count"] >= 0
    assert result["low_severity_count"] >= 0


def test_fallback_does_not_shame():
    transcript = "Um I think I very like um this thing."
    context = {"part": "part_1", "topic": "things", "word_count": 8, "transcript": transcript}
    result = _fallback_speaking_error_analysis(context, transcript)
    feedback_lower = result["feedback"].lower()
    assert "shame" not in feedback_lower
    assert "bad" not in feedback_lower or "great" in feedback_lower


# ─── AIService.analyze_speaking_errors tests ──────────────────────────

def test_ai_service_speaking_errors_no_key():
    """When no API key, use deterministic fallback."""
    service = AIService()
    service.api_key = None
    result = asyncio.run(service.analyze_speaking_errors(
        "Um, I think this is nice.", part="part_1", topic="test"
    ))
    assert result["source"] == "deterministic_fallback"
    assert "issues" in result
    assert "explanation" in str(result["issues"][0]) if result["issues"] else True


def test_ai_service_speaking_errors_with_key():
    """When API key is set and call succeeds, use AI."""
    service = AIService()
    service.api_key = "fake-key"

    fake_response = {
        "choices": [{
            "message": {
                "content": '{"issues": [{"original_phrase": "um", "issue_type": "Filler Words", "explanation": "test", "why_problem": "test", "suggested_improvement": "test", "criterion_affected": "fluency_coherence", "severity": "minor"}], "overall_band": 6.5, "feedback": "Good!", "is_estimate": true}'
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
        result = asyncio.run(service.analyze_speaking_errors(
            "Um I think this.", part="part_2", topic="test"
        ))

    assert result["source"] == "ai"
    assert len(result["issues"]) == 1
    assert result["issues"][0]["issue_type"] == "Filler Words"


def test_ai_service_speaking_errors_api_error():
    """When AI call raises, fall back to deterministic."""
    service = AIService()
    service.api_key = "fake-key"

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("API down")
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client

    with patch.object(ai_service, "AsyncClient", mock_client_cls):
        result = asyncio.run(service.analyze_speaking_errors(
            "Some transcript.", part="part_1", topic="test"
        ))

    assert result["source"] == "deterministic_fallback"


# ─── Engine integration tests ────────────────────────────────────────

class TestSpeakingErrorAnalysisEngine:
    @pytest.fixture
    def engine(self):
        eng = SpeakingErrorAnalysisEngine(db=MagicMock())
        eng.db = MagicMock()
        eng.ai_service = MagicMock()
        return eng

    def test_get_analysis_not_found(self, engine):
        engine.db.execute.return_value = MagicMock(data=[])
        with pytest.raises(Exception):
            engine.get_analysis("user1", "resp1")

    def test_list_analyses_empty(self, engine):
        engine.db.execute.return_value = MagicMock(data=[])
        result = engine.list_analyses("user1", 10)
        assert result["total"] == 0
        assert result["results"] == []

    def test_to_response_projects_from_row(self):
        row = {
            "id": "abc",
            "response_id": "resp1",
            "part": "part_2",
            "topic": "journey",
            "issues": '[{"original_phrase": "um", "issue_type": "Filler Words", "explanation": "x", "why_problem": "y", "suggested_improvement": "z", "criterion_affected": "fluency_coherence", "severity": "minor"}]',
            "overall_band": 6.5,
            "fluency_coherence_band": 6.0,
            "lexical_resource_band": 6.5,
            "grammatical_range_band": 7.0,
            "pronunciation_band": 6.5,
            "feedback": "Nice work!",
            "issue_count": 1,
            "high_severity_count": 0,
            "medium_severity_count": 0,
            "low_severity_count": 1,
            "is_estimate": True,
            "source": "ai",
            "created_at": "2025-01-01T00:00:00Z",
        }
        result = SpeakingErrorAnalysisEngine._to_response(row)
        assert result["id"] == "abc"
        assert result["response_id"] == "resp1"
        assert len(result["issues"]) == 1
        assert result["issues"][0]["issue_type"] == "Filler Words"
        assert result["overall_band"] == 6.5

    def test_to_response_handles_json_string_issues(self):
        row = {
            "id": "x",
            "response_id": "y",
            "issues": "[]",  # JSON string
            "overall_band": 6.0,
        }
        result = SpeakingErrorAnalysisEngine._to_response(row)
        assert result["issues"] == []

    def test_to_response_handles_list_issues(self):
        row = {
            "id": "x",
            "response_id": "y",
            "issues": [{"original_phrase": "test", "issue_type": "Grammar"}],  # already a list
            "overall_band": 6.0,
        }
        result = SpeakingErrorAnalysisEngine._to_response(row)
        assert len(result["issues"]) == 1
