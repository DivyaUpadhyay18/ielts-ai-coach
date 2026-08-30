"""
Tests for the Writing Band Examples engine and API.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import ai_service
from app.services.ai_service import (
    AIService,
    _build_band_examples_prompt,
    _fallback_band_examples,
    _normalize_band_examples,
)

# ─── Prompt builder tests ─────────────────────────────────────────────

def test_build_band_examples_prompt_basic():
    context = {
        "task_type": "task_2",
        "target_band": 7.5,
        "current_band": 6.0,
        "error_types": "Grammar, Vocabulary",
        "weaknesses": "Grammar, Vocabulary Repetition",
        "criteria_bands": {"task_response": 6.0, "coherence": 6.0, "lexis": 5.0, "grammar": 6.0},
        "generate_sample": "false",
        "essay_text": "This is my essay.",
    }
    prompt = _build_band_examples_prompt(context)
    assert "Task 2 (Essay)" in prompt
    assert "Target band: 7.5" in prompt
    assert "Current band: 6.0" in prompt
    assert "This is my essay." in prompt
    assert "false" in prompt


def test_build_band_examples_prompt_task_1():
    context = {
        "task_type": "task_1",
        "target_band": 8.0,
        "current_band": 6.5,
        "error_types": "none",
        "weaknesses": "none",
        "criteria_bands": {},
        "generate_sample": "true",
        "essay_text": "",
    }
    prompt = _build_band_examples_prompt(context)
    assert "Task 1 (Academic report / letter)" in prompt
    assert "true" in prompt


# ─── Normalization tests ──────────────────────────────────────────────

def test_normalize_band_examples_valid():
    plan = {
        "key_weaknesses": "Repetition and grammar",
        "improved_sentences": [
            {"original": "old", "improved": "new", "explanation": "because"}
        ],
        "vocabulary_alternatives": [
            {"from": "very", "to": "extremely", "why": "more academic"}
        ],
        "paragraph_structure": "Start with topic sentence",
        "example_introduction": "Intro here",
        "example_body_paragraph": "Body here",
        "example_conclusion": "Conclusion here",
        "sample_answer": "Full essay",
    }
    result = _normalize_band_examples(plan)
    assert result["key_weaknesses"] == "Repetition and grammar"
    assert len(result["improved_sentences"]) == 1
    assert result["improved_sentences"][0]["original"] == "old"
    assert len(result["vocabulary_alternatives"]) == 1
    assert result["vocabulary_alternatives"][0]["from"] == "very"
    assert result["is_sample_answer"] is True
    assert result["sample_answer"] == "Full essay"


def test_normalize_band_examples_empty():
    plan = {}
    result = _normalize_band_examples(plan)
    assert result["key_weaknesses"] == ""
    assert result["improved_sentences"] == []
    assert result["vocabulary_alternatives"] == []
    assert result["is_sample_answer"] is False
    assert result["sample_answer"] is None


def test_normalize_band_examples_truncates():
    long = "x" * 2000
    plan = {"key_weaknesses": long, "sample_answer": long}
    result = _normalize_band_examples(plan)
    assert len(result["key_weaknesses"]) <= 500
    assert len(result["sample_answer"]) <= 5000


def test_normalize_band_examples_filters_non_dict_list_items():
    plan = {
        "improved_sentences": [{"original": "a", "improved": "b", "explanation": "c"}, "junk", 42],
        "vocabulary_alternatives": [{"from": "x", "to": "y", "why": "z"}, None],
    }
    result = _normalize_band_examples(plan)
    assert len(result["improved_sentences"]) == 1
    assert len(result["vocabulary_alternatives"]) == 1


# ─── Fallback tests ───────────────────────────────────────────────────

def test_fallback_band_examples_basic():
    context = {
        "task_type": "task_2",
        "target_band": 7.0,
        "current_band": 6.0,
        "error_types": "Grammar",
        "weaknesses": "Grammar",
        "criteria_bands": {"task_response": 6.0},
        "generate_sample": "false",
        "essay_text": "This is a sentence. Another one.",
    }
    result = _fallback_band_examples(context)
    assert result["is_sample_answer"] is False
    assert result["sample_answer"] is None
    assert "Grammar" in result["key_weaknesses"]
    assert len(result["improved_sentences"]) >= 1
    assert result["improved_sentences"][0]["original"] == "This is a sentence."
    assert "Band 7" in result["paragraph_structure"]
    assert "example_introduction" in result
    assert "example_body_paragraph" in result
    assert "example_conclusion" in result


def test_fallback_band_examples_vocabulary_weakness():
    context = {
        "task_type": "task_2",
        "target_band": 6.5,
        "current_band": 5.5,
        "error_types": "Vocabulary Repetition",
        "weaknesses": "Vocabulary Repetition",
        "criteria_bands": {},
        "generate_sample": "false",
        "essay_text": "I very like this.",
    }
    result = _fallback_band_examples(context)
    assert len(result["vocabulary_alternatives"]) >= 1
    assert result["vocabulary_alternatives"][0]["from"] == "very"


def test_fallback_band_examples_empty_essay():
    context = {
        "task_type": "task_2",
        "target_band": 7.5,
        "current_band": 6.0,
        "error_types": "none",
        "weaknesses": "none",
        "criteria_bands": {},
        "generate_sample": "false",
        "essay_text": "",
    }
    result = _fallback_band_examples(context)
    assert result["improved_sentences"] == []
    assert "none" in result["key_weaknesses"]


# ─── AIService.generate_band_examples tests ──────────────────────────

def test_ai_service_generate_band_examples_with_key():
    """When API key is set and call succeeds, use AI."""
    service = AIService()
    service.api_key = "fake-key"

    evaluation = {
        "id": "eval-123",
        "task_type": "task_2",
        "overall_band": 6.0,
        "criteria_bands": {"task_response": 6.0, "coherence": 6.0, "lexis": 5.5, "grammar": 6.0},
        "error_analysis": [{"error_type": "Grammar", "message": "verb tense"}],
        "source": "ai",
    }
    fake_response = {
        "choices": [{
            "message": {
                "content": '{"key_weaknesses": "Grammar issues", "improved_sentences": [], "sample_answer": null}'
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
        result = asyncio.run(service.generate_band_examples(
            "My essay text here.", evaluation, 7.5, generate_sample=True
        ))

    assert result["source"] == "ai"
    assert result["key_weaknesses"] == "Grammar issues"


def test_ai_service_generate_band_examples_no_key():
    """When no API key, use deterministic fallback."""
    service = AIService()
    service.api_key = None

    evaluation = {
        "id": "eval-456",
        "task_type": "task_2",
        "overall_band": 5.0,
        "criteria_bands": {"task_response": 5.0},
        "error_analysis": [],
        "source": "ai",
    }
    result = asyncio.run(service.generate_band_examples(
        "Essay text.", evaluation, 7.0, generate_sample=False
    ))

    assert result["source"] == "deterministic_fallback"
    assert result["is_sample_answer"] is False
    assert "key_weaknesses" in result


def test_ai_service_generate_band_examples_api_error():
    """When AI call raises, fall back to deterministic."""
    service = AIService()
    service.api_key = "fake-key"

    evaluation = {
        "id": "eval-789",
        "task_type": "task_1",
        "overall_band": 6.5,
        "criteria_bands": {"coherence": 6.5},
        "error_analysis": [{"error_type": "Vocabulary"}],
        "source": "ai",
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("API down")
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.object(ai_service, "AsyncClient", return_value=mock_client):
        result = asyncio.run(service.generate_band_examples(
            "Some essay.", evaluation, 8.0, generate_sample=False
        ))

    assert result["source"] == "deterministic_fallback"


def test_ai_service_generate_band_examples_sample_answer():
    """When AI returns sample_answer, is_sample_answer is True."""
    service = AIService()
    service.api_key = "fake-key"

    evaluation = {
        "id": "eval-s1",
        "task_type": "task_2",
        "overall_band": 6.0,
        "criteria_bands": {},
        "error_analysis": [],
        "source": "ai",
    }
    fake_response = {
        "choices": [{
            "message": {
                "content": '{"key_weaknesses": "x", "improved_sentences": [], "sample_answer": "Full Band 8 essay..."}'
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
        result = asyncio.run(service.generate_band_examples(
            "Essay", evaluation, 8.0, generate_sample=True
        ))

    assert result["is_sample_answer"] is True
    assert result["sample_answer"] == "Full Band 8 essay..."
