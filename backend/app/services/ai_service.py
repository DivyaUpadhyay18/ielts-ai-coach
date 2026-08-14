import json
import logging
import os
import re
from typing import Any, Dict, List

from httpx import AsyncClient

from app.ai.prompts import (
    IELTS_WRITING_ASSESSOR_PROMPT,
    IELTS_SPEAKING_ASSESSOR_PROMPT,
    IELTS_WRITING_ERROR_ANALYSIS_PROMPT,
    IELTS_IMPROVEMENT_PLAN_PROMPT,
)

logger = logging.getLogger(__name__)

# Deterministic band-rounding: IELTS bands are in 0.5 increments.
BAND_STEP = 0.5
MAX_BAND = 9.0
MIN_BAND = 0.0

# ─────────────────────────────────────────────────────────────────────────
# Writing Error Analysis — vocabulary / contracts
# ─────────────────────────────────────────────────────────────────────────
# The nine official error categories surfaced in the UI.
ERROR_TYPE_LABELS = (
    "Grammar",
    "Vocabulary",
    "Spelling",
    "Punctuation",
    "Sentence Structure",
    "Cohesion",
    "Repetition",
    "Word Choice",
    "Task Response",
)

# Valid severity levels.
SEVERITY_LEVELS = ("critical", "major", "minor")

# Writing criterion keys affected by each error category.
CRITERION_FOR_ERROR_TYPE = {
    "Grammar": "grammatical_range_accuracy",
    "Spelling": "grammatical_range_accuracy",
    "Punctuation": "grammatical_range_accuracy",
    "Sentence Structure": "grammatical_range_accuracy",
    "Vocabulary": "lexical_resource",
    "Repetition": "lexical_resource",
    "Word Choice": "lexical_resource",
    "Cohesion": "coherence_cohesion",
    "Task Response": "task_response",
}

CRITERIA_KEYS = (
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammatical_range_accuracy",
)

# Common connecting/cohesive devices used by the deterministic fallback.
_COHESIVE_DEVICES = (
    "however", "moreover", "furthermore", "therefore", "thus", "consequently",
    "in addition", "additionally", "for instance", "for example", "as a result",
    "in conclusion", "nevertheless", "although", "while", "because", "hence",
    "similarly", "on the other hand", "whereas", "in contrast",
)

# Common informal / weak word choice detected offline.
_INFORMAL_WORDS = {
    "kids": "children",
    "stuff": "things",
    "gonna": "going to",
    "wanna": "want to",
    "alot": "a lot",
    "a lot of": "many / numerous",
    "very big": "major / significant",
    "nice": "beneficial / positive",
    "bad": "detrimental / harmful",
    "good": "beneficial / advantageous",
    "things": "factors / aspects",
    "get": "obtain / acquire",
}

# Lightweight offline spelling + grammar spot-checks.
_COMMON_MISSPELLINGS = {
    "enviornment": "environment",
    "goverment": "government",
    "definately": "definitely",
    "seperate": "separate",
    "occured": "occurred",
    "recieve": "receive",
    "wich": "which",
    "untill": "until",
    "wil": "will",
    "bussiness": "business",
    "emergancy": "emergency",
    "teached": "taught",
    "childs": "children",
    "peoples": "people",
    "informations": "information",
    "studys": "studies",
    "was were": "was / were",
}

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "at", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "it", "its", "this", "that", "these", "those", "they", "them",
    "he", "she", "we", "you", "i", "their", "there", "his", "her", "not",
    "will", "would", "can", "could", "should", "have", "has", "had", "do",
    "does", "did", "so", "than", "then", "which", "who", "whom", "all",
    "more", "most", "some", "no", "yes", "if", "because",
}

# Maximum number of issues reported (bounds cost + highlight rendering).
MAX_ERRORS = 15


def _find_offsets(text: str, needle: str) -> tuple:
    """Return (start, end) char offsets of the first occurrence of needle.

    Falls back to (0, 0) when the needle can't be found so the caller still
    gets a usable pair (UI can list the issue without highlighting).
    """
    if not needle:
        return 0, 0
    idx = text.find(needle)
    if idx == -1:
        return 0, 0
    return idx, idx + len(needle)


def _split_sentences(text: str) -> List[str]:
    """Split an essay into sentences, keeping whitespace/newlines stripped."""
    text = text.replace("\r\n", " ").replace("\n", " ")
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _normalize_error_type(value: Any, default: str = "Grammar") -> str:
    """Normalise an error type to one of the nine allowed labels."""
    if not isinstance(value, str):
        return default
    v = value.strip()
    lower = v.lower()
    for label in ERROR_TYPE_LABELS:
        if label.lower() == lower:
            return label
    # Accept snake/camel variants (e.g. "sentence_structure").
    alias_map = {
        "sentence_structure": "Sentence Structure",
        "sentence-structure": "Sentence Structure",
        "word_choice": "Word Choice",
        "word-choice": "Word Choice",
        "task_response": "Task Response",
        "task-response": "Task Response",
        "cohesion": "Cohesion",
        "repetition": "Repetition",
        "grammar": "Grammar",
        "vocabulary": "Vocabulary",
        "spelling": "Spelling",
        "punctuation": "Punctuation",
    }
    return alias_map.get(lower, default)


def _normalize_severity(value: Any, default: str = "minor") -> str:
    """Normalise a severity to critical | major | minor."""
    if not isinstance(value, str):
        return default
    v = value.strip().lower()
    if v in SEVERITY_LEVELS:
        return v
    if v in ("severe", "high", "ckritická", "error"):
        return "critical"
    if v in ("medium", "moderate", "warning"):
        return "major"
    if v in ("low", "info", "suggestion", "polish"):
        return "minor"
    return default


def _normalize_criterion(value: Any, error_type: str) -> str:
    """Resolve the affected IELTS criterion key.

    Prefer the model's explicit value; fall back to the canonical mapping for
    the error type so the field is always populated.
    """
    if not isinstance(value, str):
        return CRITERION_FOR_ERROR_TYPE.get(error_type, "grammatical_range_accuracy")
    v = value.strip()
    lower = v.lower()
    for key in CRITERIA_KEYS:
        if key == lower:
            return key
    # Accept human labels (e.g. "Lexical Resource").
    label_map = {
        "task achievement": "task_response",
        "task response": "task_response",
        "coherence and cohesion": "coherence_cohesion",
        "coherence & cohesion": "coherence_cohesion",
        "lexical resource": "lexical_resource",
        "grammatical range and accuracy": "grammatical_range_accuracy",
        "grammatical range & accuracy": "grammatical_range_accuracy",
    }
    if lower in label_map:
        return label_map[lower]
    return CRITERION_FOR_ERROR_TYPE.get(error_type, "grammatical_range_accuracy")


def _error_payload(
    *,
    original: str,
    error_type: str,
    explanation: str,
    correction: str,
    severity: str,
    criterion: str,
    start: int,
    end: int,
    sentence: str = "",
) -> Dict[str, Any]:
    """Build a single, validated error object for storage."""
    return {
        "original": (original or "").strip()[:400],
        "error_type": error_type,
        "explanation": (explanation or "").strip()[:600],
        "correction": (correction or "").strip()[:400],
        "severity": severity,
        "criterion": criterion,
        "start": max(0, int(start)),
        "end": max(0, int(end)),
        "sentence": (sentence or "").strip()[:300],
    }


def _normalize_error_analysis(raw_errors: Any, essay_text: str) -> List[Dict[str, Any]]:
    """Validate and shape a set of raw errors into stable Error objects.

    Assigns an incremental ``id``, normalises type/severity/criterion, and
    computes highlight offsets by searching the verbatim ``original`` text.
    """
    if not isinstance(raw_errors, list):
        return []
    cleaned = []
    for i, raw in enumerate(raw_errors):
        if not isinstance(raw, dict):
            continue
        original = (raw.get("original") or "").strip()
        if not original or len(original) < 2:
            continue
        error_type = _normalize_error_type(raw.get("error_type"))
        severity = _normalize_severity(raw.get("severity"))
        criterion = _normalize_criterion(raw.get("criterion"), error_type)
        start, end = _find_offsets(essay_text, original)
        cleaned.append(
            {
                "id": f"err-{i + 1}",
                "original": original[:400],
                "error_type": error_type,
                "explanation": (raw.get("explanation") or "").strip()[:600],
                "correction": (raw.get("correction") or "").strip()[:400],
                "severity": severity,
                "criterion": criterion,
                "start": start,
                "end": end,
                "sentence": (raw.get("sentence") or "").strip()[:300] if raw.get("sentence") else "",
            }
        )
        if len(cleaned) >= MAX_ERRORS:
            break
    return cleaned


def _surrounding_sentence(text: str, pos: int) -> str:
    """Return the sentence containing ``pos`` for context, or an empty string."""
    if pos < 0:
        return ""
    start = max(text.rfind(".", 0, pos), text.rfind("!", 0, pos), text.rfind("?", 0, pos)) + 1
    end = len(text)
    for char in ".!?":
        idx = text.find(char, pos)
        if idx != -1:
            end = min(end, idx + 1)
    return text[start:end].strip()[:300]


def _rank_weaknesses(criteria_bands: Dict[str, Any]) -> List[str]:
    """Return criterion keys sorted ascending by band (weakest first)."""
    valid = {k: v for k, v in criteria_bands.items() if isinstance(v, (int, float))}
    return [k for k, _ in sorted(valid.items(), key=lambda kv: kv[1])]


def _normalize_improvement_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and shape the AI improvement-plan response into stable shape."""
    return {
        "current_level_description": str(plan.get("current_level_description", "") or "")[:500],
        "target_level_description": str(plan.get("target_level_description", "") or "")[:500],
        "specific_changes": _coerce_list(plan.get("specific_changes"))[:10],
        "practice_exercises": _coerce_list(plan.get("practice_exercises"))[:8],
        "recommended_resources": _coerce_list(plan.get("recommended_resources"))[:10],
        "suggested_mission": _coerce_dict(plan.get("suggested_mission")),
    }


def _coerce_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _coerce_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value


def _fallback_improvement_plan(context: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic improvement plan when no AI provider is available."""
    criteria_bands = context.get("criteria_bands", {}) or {}
    weaknesses = _rank_weaknesses(criteria_bands)
    band_gap = context.get("band_gap", 0.0)
    target = context.get("target_band", 7.0)
    current = context.get("current_band", 0.0)
    task_type = context.get("task_type", "task_2")
    error_types = context.get("error_types", "none")

    # Scale depth by gap size.
    if band_gap >= 3.0:
        n_changes, n_exercises, n_resources = 6, 5, 6
    elif band_gap >= 1.5:
        n_changes, n_exercises, n_resources = 5, 3, 5
    else:
        n_changes, n_exercises, n_resources = 3, 2, 3

    criterion_labels = {
        "task_response": "Task Response" if task_type == "task_2" else "Task Achievement",
        "coherence_cohesion": "Coherence & Cohesion",
        "lexical_resource": "Lexical Resource",
        "grammatical_range_accuracy": "Grammatical Range & Accuracy",
    }

    changes: List[Dict[str, Any]] = []
    for wk in weaknesses[:n_changes]:
        label = criterion_labels.get(wk, wk)
        changes.append({
            "area": label,
            "change": f"Focus on {label}: your current band here is the lowest in your assessment. Work through targeted exercises for this criterion.",
            "priority": "high",
        })
    while len(changes) < n_changes:
        changes.append({
            "area": "Task Response",
            "change": "Fully address every part of the question and extend your ideas with specific examples.",
            "priority": "medium",
        })

    exercises = [
        {
            "title": f"Timed {task_type.replace('_', ' ').title()} Practice",
            "description": f"Write one {task_type.replace('_', ' ')} under strict timed conditions (40 min for Task 2), then review your error analysis.",
            "skill_focus": task_type,
            "estimated_minutes": 50,
        },
        {
            "title": "Error Analysis Review",
            "description": "Re-read the specific errors flagged in your evaluation and write corrected versions of each problematic sentence.",
            "skill_focus": "grammar",
            "estimated_minutes": 30,
        },
    ][:n_exercises]

    resources = []
    resource_pool = [
        ("IELTS Liz — Task 2 Band 8+ Samples", "https://ieltsliz.com/ielts-writing-task-2/", "Model answers at Band 8+ level for your target."),
        ("IELTS Simon — Vocabulary Builder", "https://ieltssimon.com/category/writing/", "Daily vocabulary and topic-specific word lists."),
        ("British Council — Essay Planning Guide", "https://takeielts.britishcouncil.org/writing-task-2", "Official planning and structuring advice."),
    ]
    for title, url, why in resource_pool[:n_resources]:
        resources.append({"title": title, "url": url, "why": why})

    mission = {
        "title": f"Band {target:.0f} {task_type.replace('_', ' ').title()} Practice",
        "skill": "writing",
        "sub_skill": task_type,
        "duration_minutes": 60,
        "description": f"One timed {task_type.replace('_', ' ')} essay plus detailed self-review against your error analysis.",
    }

    return {
        "current_level_description": f"You are currently estimated at Band {current:.1f} on {task_type.replace('_', ' ')}. Your weakest areas are {', '.join(weaknesses[:3]) if weaknesses else 'being identified'}.",
        "target_level_description": f"A Band {target:.1f} response requires fully addressing every part of the question, clear paragraphing, a wide range of vocabulary used accurately, and a mix of simple and complex sentence structures with minimal errors.",
        "specific_changes": changes,
        "practice_exercises": exercises,
        "recommended_resources": resources,
        "suggested_mission": mission,
    }


def _build_improvement_prompt(context: Dict[str, Any]) -> str:
    """Build the user message for the improvement-plan call.

    Uses string replacement (not str.format) because the system prompt
    contains literal JSON braces that would conflict with formatting.
    """
    system_prompt = IELTS_IMPROVEMENT_PLAN_PROMPT
    # The system prompt already has the schema; build the user message with
    # the context substituted.
    return (
        f"The student answered {context.get('task_type', 'task_2')}.\n"
        f"Current band: {context.get('current_band', 0.0)}\n"
        f"Target band: {context.get('target_band', 0.0)}\n"
        f"Band gap: {context.get('band_gap', 0.0)}\n"
        f"Word count: {context.get('word_count', 0)}\n"
        f"Criteria bands: {context.get('criteria_bands', {})}\n"
        f"Main weaknesses (ranked): {context.get('weaknesses', 'none')}\n"
        f"Error types detected: {context.get('error_types', 'none')}\n\n"
        f"Essay text:\n{context.get('essay_text', '')}\n\n"
        f"Now produce the JSON plan object following your instructions."
    )


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

    # ------------------------------------------------------------------
    # Writing Error Analysis
    # ------------------------------------------------------------------
    @staticmethod
    def _build_error_user_prompt(essay_text: str, task_type: str, prompt_text: str) -> str:
        """Build the user message for the error-analysis call."""
        task = "Task 1 (Academic report / letter)" if task_type == "task_1" else "Task 2 (Essay)"
        req = 150 if task_type == "task_1" else 250
        return (
            f"The student answered {task}. Minimum word count: {req}.\n"
            f"Task prompt: {prompt_text[:800]}\n\n"
            f"Student essay:\n{essay_text}"
        )

    async def analyze_writing_errors(
        self,
        essay_text: str,
        task_type: str = "task_2",
        prompt_text: str = "",
    ) -> Dict[str, Any]:
        """
        Produce a detailed, per-issue error analysis of an essay.

        Each issue carries original text, error type, explanation, suggested
        correction, severity, affected IELTS criterion, and highlight offsets.

        Uses OpenAI when ``OPENAI_API_KEY`` is set (all on the backend);
        otherwise returns a deterministic structural analysis so the feature
        is always functional.
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
                                {"role": "system", "content": IELTS_WRITING_ERROR_ANALYSIS_PROMPT},
                                {"role": "user", "content": self._build_error_user_prompt(essay_text, task_type, prompt_text)},
                            ],
                            "temperature": 0.3,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"] or ""
                    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        raw_errors = parsed.get("errors") or parsed.get("error_analysis") or []
                    elif isinstance(parsed, list):
                        raw_errors = parsed
                    else:
                        raw_errors = []
                    errors = _normalize_error_analysis(raw_errors, essay_text)
                    return {"error_analysis": errors, "source": "ai"}
            except Exception as e:  # noqa: BLE001 - graceful fallback
                logger.warning("AI error analysis fallback: %s", e)

        errors = self._fallback_error_analysis(essay_text, task_type)
        return {"error_analysis": errors, "source": "deterministic_fallback"}

    def _fallback_error_analysis(self, essay_text: str, task_type: str) -> List[Dict[str, Any]]:
        """Deterministic, rule-based error analysis (no AI provider required).

        Detects common, easily automated issues across the nine categories:
        sentence length, fragments, missing punctuation, repetition, common
        misspellings, informal word choice, weak cohesion, and under-length
        Task Response. Bounded to ``MAX_ERRORS`` issues.
        """
        text = essay_text or ""
        errors: List[Dict[str, Any]] = []
        lowered = text.lower()

        def add(
            original: str,
            error_type: str,
            explanation: str,
            correction: str,
            severity: str,
            criterion: str,
            start: int,
            end: int,
            sentence: str = "",
        ) -> None:
            if len(errors) >= MAX_ERRORS:
                return
            errors.append(
                _error_payload(
                    original=original,
                    error_type=error_type,
                    explanation=explanation,
                    correction=correction,
                    severity=severity,
                    criterion=criterion,
                    start=start,
                    end=end,
                    sentence=sentence,
                )
            )

        # 1. Task Response — under the minimum word count.
        words = re.findall(r"\S+", text)
        required = 150 if task_type == "task_1" else 250
        if words and len(words) < required:
            tail = (text or "").strip()[:80]
            add(
                original=tail or "(essay too short)",
                error_type="Task Response",
                explanation=f"Your essay is about {len(words)} words, below the required minimum of {required}. This limits how fully you can address the task.",
                correction=f"Extend your answer to at least {required} words by developing your ideas with reasons and examples.",
                severity="critical",
                criterion="task_response",
                start=0,
                end=len(tail),
                sentence=text[:300],
            )

        if not text.strip():
            return errors

        # 2. Repetition — content words used many times.
        freq: Dict[str, int] = {}
        for w in re.findall(r"[A-Za-z']+", lowered):
            wl = w.lower()
            if wl in _STOPWORDS or len(wl) < 4:
                continue
            freq[wl] = freq.get(wl, 0) + 1
        for word, count in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])):
            if count >= 5:
                idx = lowered.find(word)
                if idx != -1:
                    phrase = text[idx:idx + len(word)]
                    add(
                        original=phrase,
                        error_type="Repetition",
                        explanation=f"The word \"{phrase}\" appears {count} times. Over-using one word weakens your Lexical Resource score.",
                        correction=f"Replace some occurrences of \"{phrase}\" with synonyms or restructuring.",
                        severity="major",
                        criterion="lexical_resource",
                        start=idx,
                        end=idx + len(word),
                        sentence=_surrounding_sentence(text, idx),
                    )
                if len(errors) >= MAX_ERRORS:
                    break

        # 3. Sentence structure — very long sentences and fragments.
        sentences = _split_sentences(text)
        for sent in sentences:
            s_words = re.findall(r"\S+", sent)
            s_idx = text.find(sent)
            if s_idx == -1:
                continue
            if len(s_words) > 45:
                add(
                    original=sent[:180],
                    error_type="Sentence Structure",
                    explanation="This sentence is very long and hard to follow, which can obscure your meaning and hurt Grammatical Range & Accuracy.",
                    correction="Split it into two or three shorter, clearer sentences.",
                    severity="major",
                    criterion="grammatical_range_accuracy",
                    start=s_idx,
                    end=s_idx + len(sent),
                    sentence=sent[:300],
                )
            elif 0 < len(s_words) < 4:
                add(
                    original=sent,
                    error_type="Sentence Structure",
                    explanation="This reads like a sentence fragment rather than a complete sentence.",
                    correction="Connect it to the surrounding sentence or add a subject and a main verb.",
                    severity="minor",
                    criterion="grammatical_range_accuracy",
                    start=s_idx,
                    end=s_idx + len(sent),
                    sentence=sent[:300],
                )

        # 4. Punctuation — sentence lacks terminal punctuation.
        for sent in sentences:
            s_idx = text.find(sent)
            if s_idx != -1 and sent and sent[-1] not in ".!?":
                add(
                    original=sent[:120],
                    error_type="Punctuation",
                    explanation="This sentence is missing terminal punctuation (a full stop, question mark, or exclamation mark).",
                    correction=f"Add a full stop at the end: \"{sent.rstrip()}.\"",
                    severity="minor",
                    criterion="grammatical_range_accuracy",
                    start=s_idx,
                    end=s_idx + len(sent),
                    sentence=sent[:300],
                )

        # 5. Spelling + 6. Grammar — common misspellings / word-form slips.
        for w in re.findall(r"[A-Za-z']+", text):
            wl = w.lower()
            if wl in _COMMON_MISSPELLINGS:
                idx = text.find(w)
                if idx != -1:
                    correction = _COMMON_MISSPELLINGS[wl]
                    if wl.startswith("childs") or wl.startswith("peoples") or wl.startswith("informations"):
                        err_type = "Grammar"
                    else:
                        err_type = "Spelling"
                    add(
                        original=w,
                        error_type=err_type,
                        explanation=f"\"{w}\" is incorrect; \"{correction}\" is the standard form.",
                        correction=f"Correct it to \"{correction}\".",
                        severity="major",
                        criterion="grammatical_range_accuracy",
                        start=idx,
                        end=idx + len(w),
                        sentence=_surrounding_sentence(text, idx),
                    )

        # 7. Word choice — informal / weak vocabulary.
        for informal, formal in _INFORMAL_WORDS.items():
            idx = lowered.find(informal)
            if idx != -1 and formal not in _COMMON_MISSPELLINGS.values():
                phrase = text[idx:idx + len(informal)]
                add(
                    original=phrase,
                    error_type="Word Choice",
                    explanation=f"\"{phrase}\" is informal or vague for academic writing.",
                    correction=f"Use a more precise academic alternative such as \"{formal}\".",
                    severity="minor",
                    criterion="lexical_resource",
                    start=idx,
                    end=idx + len(phrase),
                    sentence=_surrounding_sentence(text, idx),
                )

        # 8. Cohesion — a longer essay with none of the common linking devices.
        if len(sentences) >= 4 and not any(d in lowered for d in _COHESIVE_DEVICES):
            add(
                original=text[:80],
                error_type="Cohesion",
                explanation="Your ideas are not linked with connecting words, so the argument is hard to follow (Coherence & Cohesion).",
                correction="Add linking words such as 'however', 'moreover', or 'as a result' to connect your ideas.",
                severity="major",
                criterion="coherence_cohesion",
                start=0,
                end=min(80, len(text)),
                sentence=_surrounding_sentence(text, 0),
            )

        # Sort by offsets for a tidy reading order, keep the bound.
        errors = sorted(errors, key=lambda e: (e["start"], e["end"]))[:MAX_ERRORS]
        # Re-assign stable ids after sorting.
        for i, err in enumerate(errors):
            err["id"] = f"err-{i + 1}"
        return errors

    async def generate_improvement_plan(
        self,
        essay_text: str,
        evaluation: Dict[str, Any],
        target_band: float,
    ) -> Dict[str, Any]:
        """
        Generate a personalized improvement plan using the student's actual
        evaluation data.  Falls back to a deterministic plan when no API key
        is set or the call fails.
        """
        criteria_bands = evaluation.get("criteria_bands", {}) or {}
        error_analysis = evaluation.get("error_analysis") or []
        error_types = sorted({e.get("error_type", "Grammar") for e in error_analysis})
        weaknesses = _rank_weaknesses(criteria_bands)

        context = {
            "task_type": evaluation.get("task_type", "task_2"),
            "current_band": evaluation.get("overall_band") or 0.0,
            "target_band": target_band,
            "band_gap": round(target_band - (evaluation.get("overall_band") or 0.0), 1),
            "word_count": evaluation.get("word_count", 0),
            "criteria_bands": criteria_bands,
            "weaknesses": ", ".join(weaknesses) or "none identified",
            "error_types": ", ".join(error_types) if error_types else "none",
            "essay_text": essay_text[:2000],
        }

        if self.api_key:
            try:
                prompt = _build_improvement_prompt(context)
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
                                {"role": "system", "content": IELTS_IMPROVEMENT_PLAN_PROMPT},
                                {"role": "user", "content": prompt},
                            ],
                            "temperature": 0.3,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"] or ""
                    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        result = _normalize_improvement_plan(parsed)
                        result["source"] = "ai"
                        return result
            except Exception as e:
                logger.warning("AI improvement plan fallback: %s", e)

        result = _fallback_improvement_plan(context)
        result["source"] = "deterministic_fallback"
        return result

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
