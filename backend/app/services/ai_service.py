import json
import logging
import os
from typing import Any, Dict

from httpx import AsyncClient

from app.ai.prompts import IELTS_WRITING_ASSESSOR_PROMPT, IELTS_SPEAKING_ASSESSOR_PROMPT

logger = logging.getLogger(__name__)

# Deterministic band-rounding: IELTS bands are in 0.5 increments.
BAND_STEP = 0.5
MAX_BAND = 9.0
MIN_BAND = 0.0


def _round_band(value: float) -> float:
    """Round to the nearest 0.5 and clamp to [0, 9]."""
    v = max(MIN_BAND, min(MAX_BAND, float(value)))
    return round(v * 2) / 2


def _compute_overall_band(criteria_bands: Dict[str, float], task_type: str) -> float:
    """
    Compute the overall Writing band.

    IELTS Academic Writing: the overall band is the mean of the four
    criterion bands, rounded to the nearest 0.5.

    Formula:
        overall = round_to_half(mean(bands))

    Where ``bands`` is the four criterion scores:
        - Task 1: Task Achievement, Coherence & Cohesion, Lexical Resource,
          Grammatical Range & Accuracy
        - Task 2: Task Response, Coherence & Cohesion, Lexical Resource,
          Grammatical Range & Accuracy
    """
    values = list(criteria_bands.values())
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    return _round_band(avg)


def _compute_confidence(criteria_bands: Dict[str, float], essay_length: int) -> float:
    """
    Compute a confidence score for the AI evaluation.

    Formula:
        base = 0.7  (the model is generally competent)
        + length_bonus  (longer essays give more signal)
        + consistency_bonus  (similar band values increase confidence)
        - spread_penalty  (wide band spread lowers confidence)

    Clamped to [0.0, 1.0] in 0.1 steps.
    """
    base = 0.7

    # Length bonus: more words = more signal.
    length_bonus = min(0.15, essay_length / 1000)

    # Spread penalty: wide spread between criterion bands lowers confidence.
    values = list(criteria_bands.values())
    if len(values) >= 2:
        spread = max(values) - min(values)
        spread_penalty = min(0.1, spread * 0.05)
    else:
        spread_penalty = 0.0

    # Consistency bonus: narrow spread increases confidence.
    consistency_bonus = max(0.0, 0.05 - spread_penalty)

    raw = base + length_bonus + consistency_bonus - spread_penalty
    return max(0.0, min(1.0, round(raw, 1)))


class AIService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def analyze_writing(
        self,
        essay_text: str,
        task_type: str = "task_2",
        prompt_text: str = "",
    ) -> Dict[str, Any]:
        """
        Evaluate an IELTS Writing essay using the OpenAI API (if configured).

        Returns a structured evaluation with:
          - 4 criterion bands (Task Response/Achievement, Coherence & Cohesion,
            Lexical Resource, Grammatical Range & Accuracy)
          - Overall band (weighted mean, rounded to 0.5)
          - Confidence score
          - Strengths, weaknesses, errors, suggestions per criterion
          - is_estimate flag (always True)

        When no API key is set or the call fails, returns a deterministic
        placeholder so the pipeline is functional without AI.
        """
        if self.api_key:
            try:
                async with AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": IELTS_WRITING_ASSESSOR_PROMPT,
                                },
                                {
                                    "role": "user",
                                    "content": (
                                        f"Task type: {task_type}\n"
                                        f"Prompt: {prompt_text}\n\n"
                                        f"Please evaluate this essay:\n\n{essay_text}"
                                    ),
                                },
                            ],
                            "temperature": 0.3,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]

                    # Parse structured JSON from the AI response.
                    result = json.loads(content)
                    return self._normalize_ai_result(result, essay_text, task_type)

            except Exception as e:
                logger.warning("AI evaluation fallback: %s", e)

        # Deterministic fallback when no API key or API call fails.
        return self._fallback_analysis(essay_text, task_type)

    def _normalize_ai_result(
        self, result: Dict[str, Any], essay_text: str, task_type: str
    ) -> Dict[str, Any]:
        """Validate and normalise the AI JSON response into our schema."""
        criteria: Dict[str, Any] = {}
        bands: Dict[str, float] = {}

        for key, label in [
            ("task_response", "Task Response" if task_type == "task_2" else "Task Achievement"),
            ("coherence_cohesion", "Coherence and Cohesion"),
            ("lexical_resource", "Lexical Resource"),
            ("grammatical_range_accuracy", "Grammatical Range and Accuracy"),
        ]:
            c = result.get("criteria", {}).get(key, {})
            band = _round_band(float(c.get("band", 5.0)))
            criteria[key] = {
                "band": band,
                "label": label,
                "strength": c.get("strength", "No specific strength identified."),
                "weakness": c.get("weakness", "No specific weakness identified."),
                "errors": c.get("errors", []) or [],
                "suggestions": c.get("suggestions", []) or [],
            }
            bands[key] = band

        overall = _round_band(
            result.get("overall_band", _compute_overall_band(bands, task_type))
        )
        essay_length = len(essay_text.strip().split()) if essay_text.strip() else 0
        confidence = float(result.get("confidence", _compute_confidence(bands, essay_length)))

        return {
            "task_type": task_type,
            "criteria": criteria,
            "overall_band": overall,
            "confidence": round(confidence, 2),
            "is_estimate": True,
            "word_count": essay_length,
            "source": "ai",
        }

    def _fallback_analysis(
        self, essay_text: str, task_type: str
    ) -> Dict[str, Any]:
        """
        Deterministic placeholder evaluation used when the OpenAI API key is
        not configured. Provides a basic structural assessment so the
        evaluation pipeline is always functional.
        """
        words = essay_text.strip().split()
        word_count = len(words)

        # Structural heuristics (deterministic, no AI).
        has_intro = len(essay_text) > 50
        has_paragraphs = essay_text.count("\n\n") >= 1 or essay_text.count("\n") >= 2
        has_conclusion = word_count > 100

        # Derive bands from structural heuristics.
        task_label = "Task Response" if task_type == "task_2" else "Task Achievement"
        tr_band = _round_band(5.0 + (0.5 if word_count >= 150 else 0.0))
        cc_band = _round_band(5.0 + (0.5 if has_paragraphs else 0.0))
        lr_band = _round_band(5.0 + (0.5 if word_count >= 150 else 0.0))
        gr_band = _round_band(5.0 + (0.5 if word_count >= 200 else 0.0))

        bands = {
            "task_response": tr_band,
            "coherence_cohesion": cc_band,
            "lexical_resource": lr_band,
            "grammatical_range_accuracy": gr_band,
        }
        overall = _compute_overall_band(bands, task_type)
        confidence = _compute_confidence(bands, word_count)

        return {
            "task_type": task_type,
            "criteria": {
                "task_response": {
                    "band": tr_band,
                    "label": task_label,
                    "strength": "Your response addresses the topic.",
                    "weakness": "Add more developed arguments and examples.",
                    "errors": [],
                    "suggestions": [
                        "Fully address every part of the question.",
                        "Develop your ideas with specific examples.",
                    ],
                },
                "coherence_cohesion": {
                    "band": cc_band,
                    "label": "Coherence and Cohesion",
                    "strength": "Your writing is generally readable.",
                    "weakness": "Improve paragraph structure and use a wider range of linking devices.",
                    "errors": [],
                    "suggestions": [
                        "Use cohesive devices like 'furthermore', 'in contrast', 'as a result'.",
                        "Ensure each paragraph covers one main idea.",
                    ],
                },
                "lexical_resource": {
                    "band": lr_band,
                    "label": "Lexical Resource",
                    "strength": "You use a reasonable range of vocabulary.",
                    "weakness": "Expand your lexical range and avoid repetition.",
                    "errors": [],
                    "suggestions": [
                        "Use synonyms and topic-specific collocations.",
                        "Avoid memorised phrases and aim for natural word choice.",
                    ],
                },
                "grammatical_range_accuracy": {
                    "band": gr_band,
                    "label": "Grammatical Range and Accuracy",
                    "strength": "You use a mix of simple and complex structures.",
                    "weakness": "Work on complex sentence forms and accuracy.",
                    "errors": [],
                    "suggestions": [
                        "Practice complex sentences (relative clauses, conditionals).",
                        "Proofread for subject-verb agreement and article use.",
                    ],
                },
            },
            "overall_band": overall,
            "confidence": round(confidence, 2),
            "is_estimate": True,
            "word_count": word_count,
            "source": "deterministic_fallback",
        }

    async def analyze_speaking(self, user_transcript: str) -> Dict[str, Any]:
        """
        Analyse a Speaking transcript using OpenAI (if API key is set) or
        return mock data.
        """
        if self.api_key:
            try:
                async with AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": IELTS_SPEAKING_ASSESSOR_PROMPT},
                                {"role": "user", "content": f"Please assess this IELTS speaking transcript:\n\n{user_transcript}"},
                            ],
                            "temperature": 0.3,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    try:
                        result = json.loads(content)
                        return {
                            "band_score": float(result.get("band_score", 6.0)),
                            "feedback": result.get("feedback", "No detailed feedback provided."),
                            "corrections": result.get("corrections", []),
                        }
                    except (json.JSONDecodeError, ValueError, TypeError):
                        return {
                            "band_score": 6.5,
                            "feedback": content[:500] if content else "Analysis complete.",
                            "corrections": [],
                        }
            except Exception as e:
                logger.warning("AI speaking evaluation fallback: %s", e)

        return {
            "band_score": 6.0,
            "feedback": "Your fluency is good, but try to elaborate more and use a wider range of linking devices.",
            "corrections": ["Use 'moreover' to extend ideas", "Reduce filler words like 'um'"],
        }


# Create a single instance
ai_service = AIService()
