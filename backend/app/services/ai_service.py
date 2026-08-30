import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from httpx import AsyncClient

from app.ai.prompts import (
    IELTS_WRITING_ASSESSOR_PROMPT,
    IELTS_SPEAKING_ASSESSOR_PROMPT,
    IELTS_WRITING_ERROR_ANALYSIS_PROMPT,
    IELTS_IMPROVEMENT_PLAN_PROMPT,
    IELTS_BAND_EXAMPLES_PROMPT,
    IELTS_WRITING_COACH_PROMPT,
    IELTS_SPEAKING_ERROR_ANALYSIS_PROMPT,
    IELTS_SPEAKING_IMPROVEMENT_PLAN_PROMPT,
    IELTS_SPEAKING_REATTEMPT_COMPARISON_PROMPT,
    IELTS_SPEAKING_COACH_PROMPT,
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


def _build_band_examples_prompt(context: Dict[str, Any]) -> str:
    """Build the user message for the band-examples call.

    Uses string replacement (not str.format) because the system prompt
    contains literal JSON braces that would conflict with formatting.
    """
    task_type = context.get("task_type", "task_2")
    task_label = "Task 1 (Academic report / letter)" if task_type == "task_1" else "Task 2 (Essay)"
    return (
        f"The student answered {task_label}.\n"
        f"Target band: {context.get('target_band', 0.0)}\n"
        f"Current band: {context.get('current_band', 0.0)}\n"
        f"Error types detected: {context.get('error_types', 'none')}\n"
        f"Key weaknesses: {context.get('weaknesses', 'none')}\n"
        f"Criteria bands: {context.get('criteria_bands', {})}\n"
        f"Generate sample answer: {context.get('generate_sample', 'false')}\n\n"
        f"Original essay:\n{context.get('essay_text', '')}\n\n"
        f"Now produce the JSON object following your instructions."
    )


def _normalize_band_examples(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and shape the AI band-examples response into stable shape."""
    def _coerce_list(value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    return {
        "key_weaknesses": str(plan.get("key_weaknesses", "") or "")[:500],
        "improved_sentences": _coerce_list(plan.get("improved_sentences"))[:6],
        "vocabulary_alternatives": _coerce_list(plan.get("vocabulary_alternatives"))[:6],
        "paragraph_structure": str(plan.get("paragraph_structure", "") or "")[:1000],
        "example_introduction": str(plan.get("example_introduction", "") or "")[:500],
        "example_body_paragraph": str(plan.get("example_body_paragraph", "") or "")[:1000],
        "example_conclusion": str(plan.get("example_conclusion", "") or "")[:500],
        "sample_answer": str(plan.get("sample_answer", "") or "")[:5000] if plan.get("sample_answer") else None,
        "is_sample_answer": bool(plan.get("sample_answer")),
    }


def _fallback_band_examples(context: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic band-examples fallback when no AI provider is available."""
    essay = context.get("essay_text", "") or ""
    weaknesses = context.get("weaknesses", "none")
    target = context.get("target_band", 7.0)

    improved_sentences = []
    sentences = _split_sentences(essay) if essay else []
    if sentences:
        first = sentences[0]
        improved = f"[Improved version of: '{first[:80]}'...] Develop this idea more fully with a clear topic sentence, supporting detail, and a concluding link."
        improved_sentences.append({
            "original": first[:400],
            "improved": improved,
            "explanation": "A Band 7+ response needs clearer topic sentences and extended ideas.",
        })

    vocab_alternatives = []
    if "Vocabulary" in str(weaknesses) or "Repetition" in str(weaknesses):
        vocab_alternatives.append({
            "from": "very",
            "to": "exceedingly / significantly / considerably",
            "why": "More precise academic alternatives to the vague intensifier 'very'.",
        })

    paragraph_structure = (
        "Your paragraphs should each cover one main idea. Start with a clear topic "
        f"sentence, provide specific examples or evidence, and link back to the thesis. "
        f"At Band {target:.0f}, vary your paragraph length and ensure each has a clear "
        "function (introducing, developing, or concluding)."
    )

    intro = (
        f"Band {target:.0f} introduction: paraphrase the question and outline your "
        "position clearly, then preview your main arguments in 2-3 sentences."
    )
    body = (
        f"Band {target:.0f} body paragraph: open with a strong topic sentence, "
        "develop ONE idea with specific examples and explanation, then link to the "
        "next point. Each paragraph should be 4-6 sentences."
    )
    conclusion = (
        f"Band {target:.0f} conclusion: briefly restate your position using different "
        "vocabulary, and summarise your main points without introducing new ideas."
    )

    return {
        "key_weaknesses": f"Your main weaknesses are: {weaknesses}. At Band {target:.1f} you need to address these specifically.",
        "improved_sentences": improved_sentences,
        "vocabulary_alternatives": vocab_alternatives,
        "paragraph_structure": paragraph_structure,
        "example_introduction": intro,
        "example_body_paragraph": body,
        "example_conclusion": conclusion,
        "sample_answer": None,
        "is_sample_answer": False,
    }


# ─── Speaking Error Analysis helpers (module-level) ────────────────────

# Filler word / hesitation patterns to detect in transcripts.
_FILLER_PATTERNS = [
    (r"\bum\b", "um"),
    (r"\buh\b", "uh"),
    (r"\ber\b", "er"),
    (r"\byou know\b", "you know"),
    (r"\blike\b", "like —"),  # contextual — only if used as filler
    (r"\bi mean\b", "i mean"),
    (r"\bi think\b", "i think"),
]

# Common misspellings that hint at pronunciation issues.
_PRONUNCIATION_MARKERS = {
    "dis": "this",
    "des": "these",
    "dem": "them",
    "libary": "library",
    "teh": "the",
}

# Allowed issue types for Speaking error analysis.
_SPEAKING_ISSUE_TYPES = {
    "Grammar", "Repeated Vocabulary", "Weak Vocabulary",
    "Unnatural Expression", "Filler Words", "Repetition",
    "Incomplete Sentence", "Hesitation Indicator",
    "Coherence Problem", "Pronunciation",
}


def _build_speaking_errors_prompt(context: Dict[str, Any]) -> str:
    """Build the user message for the speaking-error-analysis call."""
    part = context.get("part", "part_1")
    topic = context.get("topic", "")
    word_count = context.get("word_count", 0)
    transcript = context.get("transcript", "")
    return (
        f"Analyze the following IELTS Speaking transcript.\n\n"
        f"Part: {part}\n"
        f"Topic: {topic}\n"
        f"Estimated word count: {word_count}\n\n"
        f"Transcript:\n{transcript}\n\n"
        f"Follow the instructions in your system prompt exactly."
    )


def _normalize_speaking_error_analysis(
    result: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate and shape the AI speaking-error-analysis response."""
    def _coerce_issues(raw: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        valid = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            issue_type = item.get("issue_type", "")
            if issue_type not in _SPEAKING_ISSUE_TYPES:
                continue
            severity = item.get("severity", "minor")
            if severity not in ("critical", "major", "minor"):
                severity = "minor"
            criterion = item.get("criterion_affected", "fluency_coherence")
            if criterion not in (
                "fluency_coherence", "lexical_resource",
                "grammatical_range", "pronunciation",
            ):
                criterion = "fluency_coherence"
            valid.append({
                "original_phrase": str(item.get("original_phrase", "") or "")[:300],
                "issue_type": issue_type,
                "explanation": str(item.get("explanation", "") or "")[:400],
                "why_problem": str(item.get("why_problem", "") or "")[:400],
                "suggested_improvement": str(
                    item.get("suggested_improvement", "") or ""
                )[:500],
                "criterion_affected": criterion,
                "severity": severity,
                "context": str(item.get("context", "") or "")[:100],
            })
        return valid[:15]

    return {
        "issues": _coerce_issues(result.get("issues", [])),
        "overall_band": float(result.get("overall_band", 6.0)),
        "fluency_coherence_band": float(result.get("fluency_coherence_band", 6.0)),
        "lexical_resource_band": float(result.get("lexical_resource_band", 6.0)),
        "grammatical_range_band": float(result.get("grammatical_range_band", 6.0)),
        "pronunciation_band": float(result.get("pronunciation_band", 6.0)),
        "feedback": str(result.get("feedback", "") or "")[:800],
        "is_estimate": bool(result.get("is_estimate", True)),
    }


def _fallback_speaking_error_analysis(
    context: Dict[str, Any], transcript: str
) -> Dict[str, Any]:
    """Deterministic fallback for speaking error analysis."""
    issues: List[Dict[str, Any]] = []
    text = transcript or ""
    lowered = text.lower()

    # 1. Filler words (from patterns)
    for pattern, label in _FILLER_PATTERNS:
        matches = re.findall(pattern, lowered)
        if matches:
            count = len(matches)
            issues.append({
                "original_phrase": label,
                "issue_type": "Filler Words",
                "explanation": f"You used the filler '{label}' {count} time(s) in your response.",
                "why_problem": "Filler words can interrupt the natural flow of your speech and affect how smoothly ideas connect.",
                "suggested_improvement": f"Try pausing briefly instead of saying '{label}'. Practice answering sample questions without fillers, aiming to link your points with cohesive words like 'additionally', 'however', or 'on the other hand'.",
                "criterion_affected": "fluency_coherence",
                "severity": "minor" if count <= 2 else "major",
                "context": "throughout transcript",
            })

    # 2. Repeated vocabulary — find words used 3+ times
    word_freq: Dict[str, int] = {}
    for w in re.findall(r"[A-Za-z']+", lowered):
        wl = w.lower()
        if len(wl) > 3 and wl not in ("that", "this", "with", "have", "they"):
            word_freq[wl] = word_freq.get(wl, 0) + 1

    for word, count in sorted(word_freq.items(), key=lambda x: -x[1]):
        if count >= 3:
            issues.append({
                "original_phrase": word,
                "issue_type": "Repeated Vocabulary",
                "explanation": f"You used '{word}' {count} times. Repeating the same word can make your vocabulary seem limited.",
                "why_problem": "Using the same word repeatedly suggests a narrower vocabulary range, which may affect your Lexical Resource band.",
                "suggested_improvement": f"Try paraphrasing: think of synonyms before you speak. For '{word}', consider alternatives like '{word} in addition', or rephrase the sentence entirely.",
                "criterion_affected": "lexical_resource",
                "severity": "major" if count >= 5 else "minor",
                "context": "throughout transcript",
            })
        if len(issues) >= 4:
            break

    # 3. Incomplete sentences — look for trailing conjunctions / fragments
    stripped = text.strip().lower()
    trailing_incomplete = (
        stripped.endswith((" and", " but", " or", " so", " because",
                          " to", " of", " with", " for", " in", " on",
                          " about", " because", " although", " while", " if",
                          " however", " therefore", " nevertheless",
                          " that", " which", " who", " what", " how", " why"))
        or stripped.endswith(",")
        or stripped.endswith(" —")
    )
    if stripped and trailing_incomplete:
        issues.append({
            "original_phrase": "sentence trails off / ends incomplete",
            "issue_type": "Incomplete Sentence",
            "explanation": "Your response ends without completing the sentence structure.",
            "why_problem": "Incomplete sentences can make your speech difficult to follow and affect your Grammatical Range score.",
            "suggested_improvement": "Always finish your thought before stopping. If you start a sentence, complete it. Practice counting to 2 silently to collect your full thought before speaking.",
            "criterion_affected": "grammatical_range",
            "severity": "major",
            "context": "end of transcript",
        })

    # 4. Self-correction / hesitation indicators
    if re.search(r"\b(i (mean|think|guess|say|believe) (that|uh|um)?)", lowered):
        issues.append({
            "original_phrase": "i think / i mean / i guess",
            "issue_type": "Hesitation Indicator",
            "explanation": "You used a self-correction phrase like 'I think' or 'I mean', which signals hesitation.",
            "why_problem": "Multiple hesitation markers can make your speech sound uncertain and reduce your Fluency score.",
            "suggested_improvement": "Instead of 'I think...', commit to your answer directly. If you're unsure, you can say 'One perspective is...' or 'I would say that...'.",
            "criterion_affected": "fluency_coherence",
            "severity": "minor",
            "context": "throughout transcript",
        })

    # 5. Weak vocabulary — "very" + adjective
    if re.search(r"\bvery\s+\w+", lowered):
        issues.append({
            "original_phrase": "very + adjective",
            "issue_type": "Weak Vocabulary",
            "explanation": "You relied on 'very' to intensify adjectives.",
            "why_problem": "'Very' is a basic intensifier that doesn't showcase sophisticated vocabulary, which is needed for a high Lexical Resource band.",
            "suggested_improvement": "Replace 'very' with precise alternatives: 'extremely', 'particularly', 'significantly', 'remarkably', or phrase it differently (e.g. 'to a great extent').",
            "criterion_affected": "lexical_resource",
            "severity": "minor",
            "context": "throughout transcript",
        })

    # 6. Pronunciation indicators (only from transcript misspellings)
    for marker, correct in _PRONUNCIATION_MARKERS.items():
        if marker in lowered:
            issues.append({
                "original_phrase": marker,
                "issue_type": "Pronunciation",
                "explanation": f"You wrote/spelled '{marker}' where '{correct}' is expected, which may indicate a pronunciation challenge.",
                "why_problem": "Consistent misspellings of /θ/ vs /t/ or /s/ vs /θ/ sounds can affect your Pronunciation band.",
                "suggested_improvement": f"Practice the /θ/ sound (theta) — place your tongue between your teeth. Use minimal pairs: 'think/thank', 'thin/then'.",
                "criterion_affected": "pronunciation",
                "severity": "minor",
                "context": "transcript shows possible pronunciation marker",
            })

    # 7. Coherence — check for linking word variety (only for longer responses)
    linkers = ["and", "but", "so", "because", "however", "therefore",
               "additionally", "furthermore", "meanwhile", "in addition",
               "on the other hand", "as a result", "consequently"]
    used_linkers = [w for w in linkers if re.search(rf"\b{w}\b", lowered)]
    if len(used_linkers) <= 1 and len(text) > 150:
        issues.append({
            "original_phrase": "limited linking words",
            "issue_type": "Coherence Problem",
            "explanation": "Your response uses mostly simple linking words without variety.",
            "why_problem": "Limited use of cohesive devices can make your speech sound disconnected, affecting your Fluency and Coherence score.",
            "suggested_improvement": "Expand your range of linkers: 'furthermore', 'in addition', 'on the other hand', 'as a result', 'consequently'. Use them naturally between ideas.",
            "criterion_affected": "fluency_coherence",
            "severity": "major",
            "context": "throughout transcript",
        })

    # Aggregate stats
    severity_counts = {"critical": 0, "major": 0, "minor": 0}
    for issue in issues:
        sev = issue.get("severity", "minor")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    high = severity_counts["critical"] + severity_counts["major"]
    overall = max(5.0, min(9.0, round(6.5 - high * 0.25 * 2) / 2)) if issues else 6.5

    bands = {
        "fluency_coherence": overall,
        "lexical_resource": max(5.0, min(9.0, overall - 0.5)) if len(issues) > 2 else overall,
        "grammatical_range": max(5.0, min(9.0, overall - 0.5)) if issues else overall,
        "pronunciation": overall,
    }

    feedback = (
        "You communicated your ideas clearly — that's a great foundation. "
    )
    if issues:
        feedback += (
            f"I noticed {len(issues)} area(s) where you could refine your speaking. "
            "Each suggestion below is designed to help you sound more natural and confident. "
            "Keep practicing — these improvements will come with regular speaking practice!"
        )
    else:
        feedback += "Your response was strong across all criteria. Keep up the great work!"

    return {
        "issues": issues,
        "overall_band": overall,
        "fluency_coherence_band": bands["fluency_coherence"],
        "lexical_resource_band": bands["lexical_resource"],
        "grammatical_range_band": bands["grammatical_range"],
        "pronunciation_band": bands["pronunciation"],
        "feedback": feedback,
        "issue_count": len(issues),
        "high_severity_count": severity_counts["critical"] + severity_counts["major"],
        "medium_severity_count": 0,
        "low_severity_count": severity_counts["minor"],
        "is_estimate": True,
    }


# ─── Speaking Improvement Plan helpers (module-level) ─────────────────

_SPEAKING_CRITERIA = [
    "fluency_coherence", "lexical_resource", "grammatical_range", "pronunciation",
]
_CRITERION_LABEL = {
    "fluency_coherence": "Fluency & Coherence",
    "lexical_resource": "Lexical Resource",
    "grammatical_range": "Grammatical Range",
    "pronunciation": "Pronunciation",
}

# Resource + topic pools keyed by criterion.
_SPEAKING_RESOURCES = {
    "fluency_coherence": [
        ("IELTS Liz — Linking Words", "https://ieltsliz.com/linking-words/",
         "Helps you expand your range of cohesive devices."),
        ("TED Talks — Fluent Speaking", "https://ted.com/talks",
         "Listen and shadow fluent speakers to improve your rhythm."),
        ("BBC Learning English — 6 Minute English", "https://www.bbc.co.uk/learningenglish",
         "Regular listening + repeat practice for natural flow."),
    ],
    "lexical_resource": [
        ("IELTS Simon — Topic Vocabulary", "https://ieltssimon.com",
         "Daily vocabulary lists organised by topic."),
        ("Vocabulary for IELTS — Collocations", "https://vocabulary.ielts.com",
         "Learn natural word pairings to sound more fluent."),
        ("Oxford Learner's Dictionary", "https://www.oxfordlearnersdictionaries.com",
         "Find precise, natural-sounding alternatives to basic words."),
    ],
    "grammatical_range": [
        ("IELTS Liz — Grammar Tips", "https://ieltsliz.com/grammar-tips/",
         "Targeted grammar practice for complex sentence structures."),
        ("Perfect English Grammar", "https://www.perfect-english-grammar.com",
         "Practice advanced tenses and conditional forms."),
        ("English Page — Grammar", "https://www.englishpage.com",
         "Exercises on relative clauses, passive voice, and inversion."),
    ],
    "pronunciation": [
        ("IELTS Speaking — Pronunciation Tips", "https://ielts.org",
         "Official guidance on sound production and word stress."),
        ("Rachel's English", "https://rachelsenglish.com",
         "American English pronunciation with minimal pairs."),
        ("BBC Learning — Pronunciation", "https://www.bbc.co.uk/learningenglish",
         "Listen and repeat to improve clarity and stress patterns."),
    ],
}
_SPEAKING_TOPICS = [
    "Your hometown and what makes it special",
    "A person who has influenced your career",
    "Describe a memorable journey you took",
    "An article about education that caught your attention",
    "A traditional meal that is important to you",
    "A book that changed your perspective",
    "Describe a skill you would like to learn",
    "An important decision you made recently",
    "A place you would recommend to visitors",
    "A challenge you overcame in your studies",
    "Describe a film you would recommend",
    "An invention that has impacted society",
    "A hobby that helps you relax",
    "A teacher who inspired you",
    "Describe an event you organised",
]


def _rank_speaking_weaknesses(
    criteria_bands: Dict[str, Any],
) -> tuple[Optional[str], Optional[str]]:
    """Return (strongest_criterion, weakest_criterion) from band values."""
    valid = {}
    for key in _SPEAKING_CRITERIA:
        val = criteria_bands.get(key)
        try:
            valid[key] = float(val)
        except (TypeError, ValueError):
            continue
    if not valid:
        return None, None
    strongest = max(valid, key=valid.get)
    weakest = min(valid, key=valid.get)
    return strongest, weakest


def _build_speaking_plan_prompt(context: Dict[str, Any]) -> str:
    """Build the user message for the speaking-improvement-plan call."""
    return (
        f"Generate a personalized IELTS Speaking improvement plan.\n\n"
        f"Current band: {context['current_band']}\n"
        f"Target band: {context['target_band']}\n"
        f"Band gap: {context['band_gap']}\n"
        f"Strengths and weaknesses per criterion:\n"
        f"  Fluency & Coherence: {context['fluency_coherence_band']}\n"
        f"  Lexical Resource: {context['lexical_resource_band']}\n"
        f"  Grammatical Range: {context['grammatical_range_band']}\n"
        f"  Pronunciation: {context['pronunciation_band']}\n"
        f"Strongest criterion: {context['strongest_criterion']}\n"
        f"Weakest criterion: {context['weakest_criterion']}\n"
        f"Error issues: {context.get('issues_summary', 'N/A')}\n"
        f"Part: {context['part']}\n"
        f"Topic: {context['topic']}\n\n"
        f"Transcript:\n{context['transcript']}\n\n"
        f"Follow the instructions in your system prompt exactly."
    )


def _normalize_speaking_improvement_plan(
    result: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate and shape the AI speaking improvement-plan response."""
    def _coerce_list(key, max_items=10):
        raw = result.get(key, [])
        if not isinstance(raw, list):
            return []
        return [r for r in raw if isinstance(r, (dict, str))][:max_items]

    priorities = result.get("criterion_priorities", {})
    if not isinstance(priorities, dict):
        priorities = {}

    return {
        "current_band": float(result.get("current_band", 0.0)),
        "target_band": float(result.get("target_band", 0.0)),
        "band_gap": float(result.get("band_gap", 0.0)),
        "strongest_criterion": str(result.get("strongest_criterion", "") or ""),
        "weakest_criterion": str(result.get("weakest_criterion", "") or ""),
        "criterion_priorities": priorities,
        "current_level_description": str(result.get("current_level_description", "") or "")[:500],
        "target_level_description": str(result.get("target_level_description", "") or "")[:500],
        "specific_changes": _coerce_list("specific_changes", 10),
        "practice_exercises": _coerce_list("practice_exercises", 10),
        "practice_topics": _coerce_list("practice_topics", 15),
        "recommended_resources": _coerce_list("recommended_resources", 12),
        "suggested_daily_minutes": int(result.get("suggested_daily_minutes", 15)),
        "next_speaking_task": str(result.get("next_speaking_task", "") or "")[:300],
        "suggested_mission": result.get("suggested_mission", {}) if isinstance(result.get("suggested_mission"), dict) else {},
        "is_estimate": bool(result.get("is_estimate", True)),
    }


def _fallback_speaking_improvement_plan(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Deterministic fallback: produce a plan from bands + issues alone."""
    current_band = context.get("current_band", 6.0)
    target_band = context.get("target_band", round(current_band + 1.0, 1))
    target_band = min(max(target_band, 1.0), 9.0)
    band_gap = round(target_band - current_band, 1)

    strongest = context.get("strongest_criterion") or "fluency_coherence"
    weakest = context.get("weakest_criterion") or "lexical_resource"

    bands = {
        "fluency_coherence": context.get("fluency_coherence_band", current_band),
        "lexical_resource": context.get("lexical_resource_band", current_band),
        "grammatical_range": context.get("grammatical_range_band", current_band),
        "pronunciation": context.get("pronunciation_band", current_band),
    }

    def _priority(criterion: str) -> str:
        if criterion == weakest:
            return "high"
        if criterion == strongest:
            return "low"
        band_val = float(bands.get(criterion, current_band))
        return "high" if band_val < (current_band + 0.5) else "medium"

    criterion_priorities = {k: _priority(k) for k in _SPEAKING_CRITERIA}

    # Build changes — always include one per criterion, with weakest first
    priority_order = sorted(_SPEAKING_CRITERIA, key=lambda c: (criterion_priorities[c] != "high", c))
    specific_changes = []
    for c in priority_order:
        specific_changes.append({
            "area": _CRITERION_LABEL.get(c, c),
            "change": _FALLBACK_CHANGE.get(c, "Work on this area through targeted practice."),
            "priority": criterion_priorities[c],
        })

    # Scale resources/exercises by gap
    if band_gap <= 1.0:
        n_exercises = 2
        n_resources = 3
        n_topics = 5
        daily_minutes = 15
    elif band_gap <= 2.5:
        n_exercises = 4
        n_resources = 5
        n_topics = 8
        daily_minutes = 20
    else:
        n_exercises = 5
        n_resources = 7
        n_topics = 10
        daily_minutes = 30

    # Collect resources from weakest criteria
    recs = []
    for c in priority_order[:3]:
        for rec in _SPEAKING_RESOURCES.get(c, []):
            recs.append({"title": rec[0], "url": rec[1], "why": rec[2]})
    recommended_resources = recs[:6]

    # Exercises
    practice_exercises = [
        {"title": "Timed Part 1 Practice",
         "description": f"Record yourself answering 5 Part 1 questions in {n_exercises * 2} minutes, then listen back and count fillers.",
         "skill_focus": "fluency", "estimated_minutes": n_exercises * 2},
        {"title": "Vocabulary Expansion",
         "description": "Write 10 synonyms for common IELTS topics, then use each in a sentence.",
         "skill_focus": "vocabulary", "estimated_minutes": n_exercises * 3},
    ]

    # Topics
    import random
    rng = random.Random(hash(str(context)))
    shuffled_topics = _SPEAKING_TOPICS[:]
    rng.shuffle(shuffled_topics)
    practice_topics = shuffled_topics[:n_topics]

    # Daily minutes
    if band_gap <= 1.0:
        daily_minutes = 15
    elif band_gap <= 2.5:
        daily_minutes = 20
    else:
        daily_minutes = 30

    feedback = (_FALLBACK_CURRENT_DESC.format(
        current_band=current_band, weakest=weakest, strongest=strongest
    ))
    target_desc = (_FALLBACK_TARGET_DESC.format(target_band=target_band))

    return {
        "current_band": float(current_band),
        "target_band": float(target_band),
        "band_gap": float(band_gap),
        "strongest_criterion": strongest,
        "weakest_criterion": weakest,
        "criterion_priorities": criterion_priorities,
        "current_level_description": feedback,
        "target_level_description": target_desc,
        "specific_changes": specific_changes,
        "practice_exercises": practice_exercises,
        "practice_topics": practice_topics,
        "recommended_resources": recommended_resources,
        "suggested_daily_minutes": daily_minutes,
        "next_speaking_task": _FALLBACK_NEXT_TASK.format(weakest=_CRITERION_LABEL.get(weakest, weakest)),
        "suggested_mission": {
            "title": f"Speaking { _CRITERION_LABEL.get(weakest, weakest)} Improvement",
            "skill": "speaking",
            "sub_skill": weakest,
            "duration_minutes": daily_minutes,
            "description": f"Focus on improving { _CRITERION_LABEL.get(weakest, weakest)} through targeted exercises.",
        },
        "is_estimate": True,
    }


_FALLBACK_CURRENT_DESC = (
    "You are currently at Band {current_band}. "
    "Your strongest area is {strongest}, but your weakest area is {weakest}. "
    "Focus on targeted improvement in your weakest criterion."
)
_FALLBACK_TARGET_DESC = (
    "A Band {target_band} Speaking response demonstrates consistent fluency, "
    "a wide range of vocabulary, sophisticated grammar, and clear pronunciation. "
    "You need to reduce errors and use more natural language."
)
_FALLBACK_NEXT_TASK = (
    "Record a 1-2 minute response to a Part 2 cue card, then listen back and "
    "note every instance of {weakest} issues. Practice replacing them with "
    "stronger alternatives."
)

_FALLBACK_CHANGE = {
    "fluency_coherence": "Slow down your speech and practice pausing at natural breaks instead of using fillers. Use linking words like 'furthermore', 'however', and 'as a result' between ideas.",
    "lexical_resource": "Build topic-specific word lists and practice using synonyms. Replace 'very' + adjective with precise alternatives like 'extremely', 'particularly', or 'significantly'.",
    "grammatical_range": "Practice complex sentence structures: conditionals, relative clauses, and passive voice. Record yourself using 3-4 different structures per response.",
    "pronunciation": "Practice minimal pairs (think/sink, ship/sheep) and word stress. Record yourself and compare with native speaker models.",
}


# ─── Speaking Reattempt Comparison helpers (module-level) ───────────────

_SPEAKING_CRITERIA_KEYS = (
    "fluency_coherence",
    "lexical_resource",
    "grammatical_range",
    "pronunciation",
)
_SPEAKING_CRITERION_LABELS = {
    "fluency_coherence": "Fluency and Coherence",
    "lexical_resource": "Lexical Resource",
    "grammatical_range": "Grammatical Range",
    "pronunciation": "Pronunciation",
}


def _build_reattempt_comparison_context(
    attempt_1: Dict[str, Any], attempt_2: Dict[str, Any]
) -> Dict[str, Any]:
    """Build the context dict for the reattempt comparison prompt."""
    return {
        "attempt_1_overall": attempt_1.get("overall_band", 0.0),
        "attempt_2_overall": attempt_2.get("overall_band", 0.0),
        "attempt_1_fluency": attempt_1.get("fluency_coherence_band", 0.0),
        "attempt_2_fluency": attempt_2.get("fluency_coherence_band", 0.0),
        "attempt_1_lexical": attempt_1.get("lexical_resource_band", 0.0),
        "attempt_2_lexical": attempt_2.get("lexical_resource_band", 0.0),
        "attempt_1_grammar": attempt_1.get("grammatical_range_band", 0.0),
        "attempt_2_grammar": attempt_2.get("grammatical_range_band", 0.0),
        "attempt_1_pronunciation": attempt_1.get("pronunciation_band", 0.0),
        "attempt_2_pronunciation": attempt_2.get("pronunciation_band", 0.0),
        "attempt_1_duration": attempt_1.get("duration_seconds", 0),
        "attempt_2_duration": attempt_2.get("duration_seconds", 0),
        "attempt_1_fillers": attempt_1.get("filler_words_count", 0),
        "attempt_2_fillers": attempt_2.get("filler_words_count", 0),
        "attempt_1_errors": attempt_1.get("error_count", 0),
        "attempt_2_errors": attempt_2.get("error_count", 0),
    }


def _normalize_reattempt_comparison(
    result: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate and shape the AI reattempt-comparison response."""
    def _coerce_list(key: str, max_items: int = 8) -> List[str]:
        raw = result.get(key, [])
        if not isinstance(raw, list):
            return []
        return [str(item) for item in raw][:max_items]

    return {
        "what_improved": _coerce_list("what_improved", 8),
        "what_stayed_the_same": _coerce_list("what_stayed_the_same", 8),
        "what_became_worse": _coerce_list("what_became_worse", 8),
        "focus_next": _coerce_list("focus_next", 5),
        "feedback": str(result.get("feedback", "") or "")[:800],
    }


def _fallback_reattempt_comparison(context: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic fallback for reattempt comparison."""
    a1 = {
        "overall": context["attempt_1_overall"],
        "fluency": context["attempt_1_fluency"],
        "lexical": context["attempt_1_lexical"],
        "grammar": context["attempt_1_grammar"],
        "pronunciation": context["attempt_1_pronunciation"],
        "duration": context["attempt_1_duration"],
        "fillers": context["attempt_1_fillers"],
        "errors": context["attempt_1_errors"],
    }
    a2 = {
        "overall": context["attempt_2_overall"],
        "fluency": context["attempt_2_fluency"],
        "lexical": context["attempt_2_lexical"],
        "grammar": context["attempt_2_grammar"],
        "pronunciation": context["attempt_2_pronunciation"],
        "duration": context["attempt_2_duration"],
        "fillers": context["attempt_2_fillers"],
        "errors": context["attempt_2_errors"],
    }

    improved = []
    unchanged = []
    worsened = []
    focus = []

    for key, label in zip(
        ("fluency", "lexical", "grammar", "pronunciation"),
        (_SPEAKING_CRITERION_LABELS["fluency_coherence"],
         _SPEAKING_CRITERION_LABELS["lexical_resource"],
         _SPEAKING_CRITERION_LABELS["grammatical_range"],
         _SPEAKING_CRITERION_LABELS["pronunciation"]),
    ):
        d = round(a2[key] - a1[key], 1)
        if d > 0:
            improved.append(f"{label} improved by {d:.1f} band(s) ({a1[key]:.1f} → {a2[key]:.1f}).")
        elif d < 0:
            worsened.append(f"{label} decreased by {abs(d):.1f} band(s) ({a1[key]:.1f} → {a2[key]:.1f}).")
            focus.append(label)
        else:
            unchanged.append(f"{label} stayed the same ({a1[key]:.1f}).")

    overall_d = round(a2["overall"] - a1["overall"], 1)
    if overall_d > 0:
        improved.append(f"Overall band improved by {overall_d:.1f} ({a1['overall']:.1f} → {a2['overall']:.1f}).")
    elif overall_d < 0:
        worsened.append(f"Overall band decreased by {abs(overall_d):.1f} ({a1['overall']:.1f} → {a2['overall']:.1f}).")
        focus.append("Overall band")
    else:
        unchanged.append(f"Overall band stayed at {a1['overall']:.1f}.")

    # Duration
    dur_d = a2["duration"] - a1["duration"]
    if dur_d != 0:
        direction = "increased" if dur_d > 0 else "decreased"
        improved.append(f"Duration {direction} by {abs(dur_d)} seconds.")
    else:
        unchanged.append(f"Duration stayed at {a1['duration']} seconds.")

    # Fillers
    filler_d = a2["fillers"] - a1["fillers"]
    if filler_d < 0:
        improved.append(f"Filler words decreased by {abs(filler_d)} ({a1['fillers']} → {a2['fillers']}).")
    elif filler_d > 0:
        worsened.append(f"Filler words increased by {filler_d} ({a1['fillers']} → {a2['fillers']}).")
        focus.append("Reducing filler words")
    else:
        unchanged.append(f"Filler words stayed at {a1['fillers']}.")

    # Errors
    err_d = a2["errors"] - a1["errors"]
    if err_d < 0:
        improved.append(f"Error count decreased by {abs(err_d)} ({a1['errors']} → {a2['errors']}).")
    elif err_d > 0:
        worsened.append(f"Error count increased by {err_d} ({a1['errors']} → {a2['errors']}).")
        focus.append("Error reduction")

    if not focus:
        focus = ["Maintain your strengths and continue practicing"]

    feedback = (
        f"You completed another Speaking attempt — that's excellent progress! "
    )
    if improved:
        feedback += f"I can see {len(improved)} area(s) of improvement. "
    if worsened:
        feedback += "A few areas need attention, but every reattempt builds your skills. "
    feedback += "Keep recording and reflecting — you're on the right track!"

    return {
        "what_improved": improved,
        "what_stayed_the_same": unchanged,
        "what_became_worse": worsened,
        "focus_next": focus[:3],
        "feedback": feedback,
    }


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

    async def generate_band_examples(
        self,
        essay_text: str,
        evaluation: Dict[str, Any],
        target_band: float,
        generate_sample: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate band-level improvement examples tailored to the student's
        actual evaluation.  Falls back to a deterministic example set when
        no API key is set or the call fails.
        """
        criteria_bands = evaluation.get("criteria_bands", {}) or {}
        error_analysis = evaluation.get("error_analysis") or []
        error_types = sorted({e.get("error_type", "Grammar") for e in error_analysis})
        weaknesses = _rank_weaknesses(criteria_bands)

        context = {
            "task_type": evaluation.get("task_type", "task_2"),
            "current_band": evaluation.get("overall_band") or 0.0,
            "target_band": target_band,
            "error_types": ", ".join(error_types) if error_types else "none",
            "weaknesses": ", ".join(weaknesses) if weaknesses else "none identified",
            "criteria_bands": criteria_bands,
            "generate_sample": "true" if generate_sample else "false",
            "essay_text": essay_text[:2000],
        }

        if self.api_key:
            try:
                prompt = _build_band_examples_prompt(context)
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
                                {"role": "system", "content": IELTS_BAND_EXAMPLES_PROMPT},
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
                        result = _normalize_band_examples(parsed)
                        result["source"] = "ai"
                        return result
            except Exception as e:
                logger.warning("AI band examples fallback: %s", e)

        result = _fallback_band_examples(context)
        result["source"] = "deterministic_fallback"
        return result

 
    async def analyze_speaking_errors(
        self,
        transcript: str,
        part: str = "part_1",
        topic: str = "",
    ) -> Dict[str, Any]:
        """
        Analyse a Speaking transcript for specific issues:

        - Grammar errors
        - Repeated / weak vocabulary
        - Unnatural expressions
        - Filler words
        - Repetition
        - Incomplete sentences
        - Hesitation indicators
        - Coherence problems
        - Pronunciation issues (only when supported by audio analysis)

        For every issue returns: original phrase, issue type, explanation,
        suggested improvement, criterion affected, and severity.

        Falls back to a deterministic analysis when no AI provider is available.
        """
        context = {
            "part": part,
            "topic": topic,
            "word_count": len(transcript.split()) if transcript else 0,
            "transcript": transcript[:3000] if transcript else "",
        }

        if self.api_key:
            try:
                prompt = _build_speaking_errors_prompt(context)
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
                                {"role": "system", "content": IELTS_SPEAKING_ERROR_ANALYSIS_PROMPT},
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
                        result = _normalize_speaking_error_analysis(parsed)
                        result["source"] = "ai"
                        return result
            except Exception as e:
                logger.warning("AI speaking error analysis fallback: %s", e)

        result = _fallback_speaking_error_analysis(context, transcript)
        result["source"] = "deterministic_fallback"
        return result

    async def generate_speaking_improvement_plan(
        self,
        evaluation: Dict[str, Any],
        target_band: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate a personalized "Improve My Speaking Band" plan.

        Uses the AI service (backend-only) with a deterministic fallback.
        The plan is based on the student's actual evaluation data.
        """
        criteria_bands = evaluation.get("criteria_bands", evaluation) or {}
        current_band = float(evaluation.get("overall_band", 0.0) or 0.0)

        if target_band is None:
            target_band = current_band + 1.0
        target_band = min(max(target_band, 1.0), 9.0)
        band_gap = round(target_band - current_band, 1)

        strongest, weakest = _rank_speaking_weaknesses(criteria_bands)

        context = {
            "current_band": current_band,
            "target_band": target_band,
            "band_gap": band_gap,
            "fluency_coherence_band": criteria_bands.get("fluency_coherence", current_band),
            "lexical_resource_band": criteria_bands.get("lexical_resource", current_band),
            "grammatical_range_band": criteria_bands.get("grammatical_range", current_band),
            "pronunciation_band": criteria_bands.get("pronunciation", current_band),
            "strongest_criterion": strongest,
            "weakest_criterion": weakest,
            "issues_summary": evaluation.get("issues_summary", ""),
            "part": evaluation.get("part", "part_1"),
            "topic": evaluation.get("topic", evaluation.get("title", "")),
            "transcript": (evaluation.get("transcript", "") or "")[:2000],
        }

        if self.api_key:
            try:
                prompt = _build_speaking_plan_prompt(context)
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
                                {"role": "system", "content": IELTS_SPEAKING_IMPROVEMENT_PLAN_PROMPT},
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
                        result = _normalize_speaking_improvement_plan(parsed)
                        result["source"] = "ai"
                        return result
            except Exception as e:
                logger.warning("AI speaking improvement plan fallback: %s", e)

        result = _fallback_speaking_improvement_plan(context)
        result["source"] = "deterministic_fallback"
        return result

    async def generate_speaking_reattempt_comparison(
        self,
        attempt_1: Dict[str, Any],
        attempt_2: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a natural-language comparison between two speaking attempts.

        Uses the AI service (backend-only) with a deterministic fallback.
        """
        context = _build_reattempt_comparison_context(attempt_1, attempt_2)

        if self.api_key:
            try:
                prompt = _build_reattempt_comparison_prompt(context)
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
                                {"role": "system", "content": IELTS_SPEAKING_REATTEMPT_COMPARISON_PROMPT},
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
                        result = _normalize_reattempt_comparison(parsed)
                        result["source"] = "ai"
                        return result
            except Exception as e:
                logger.warning("AI speaking reattempt comparison fallback: %s", e)

        result = _fallback_reattempt_comparison(context)
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

    async def speaking_coach_chat(
        self,
        question: str,
        transcript: str,
        evaluation: Dict[str, Any],
        error_analysis: Optional[Dict[str, Any]] = None,
        previous_attempts: Optional[List[Dict[str, Any]]] = None,
        target_band: Optional[float] = None,
        weaknesses: Optional[List[str]] = None,
        student_question: str = "",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Chat with the AI Speaking Coach using the student's actual response data.

        Uses the real transcript, evaluation, error analysis, previous attempts,
        target band, and weaknesses to produce a personalized answer. Falls back
        to a deterministic response when no API key is configured.
        """
        error_analysis_str = ""
        if error_analysis and error_analysis.get("issues"):
            error_analysis_str = "; ".join(
                f"{i.get('issue_type', 'Unknown')}: {i.get('explanation', '')}"
                for i in error_analysis["issues"][:10]
            )

        attempts_str = ""
        if previous_attempts:
            attempts_str = json.dumps([
                {
                    "band": a.get("overall_band", ""),
                    "errors": a.get("error_count", 0),
                    "duration": a.get("duration_seconds", 0),
                }
                for a in previous_attempts[:5]
            ])

        weaknesses_str = ", ".join(weaknesses or [])
        target_str = str(target_band) if target_band else "none set"

        prompt = (
            IELTS_SPEAKING_COACH_PROMPT
            .replace("{question}", question)
            .replace("{transcript}", transcript)
            .replace("{overall_band}", str(evaluation.get("overall_band", evaluation.get("band_score", ""))))
            .replace("{fluency_band}", str(evaluation.get("fluency_coherence_band", evaluation.get("fluency_coherence", ""))))
            .replace("{lexical_band}", str(evaluation.get("lexical_resource_band", evaluation.get("lexical_resource", ""))))
            .replace("{grammar_band}", str(evaluation.get("grammatical_range_band", evaluation.get("grammatical_range", ""))))
            .replace("{pronunciation_band}", str(evaluation.get("pronunciation_band", evaluation.get("pronunciation", ""))))
            .replace("{error_analysis}", error_analysis_str)
            .replace("{previous_attempts}", attempts_str)
            .replace("{target_band}", target_str)
            .replace("{weaknesses}", weaknesses_str)
            .replace("{student_question}", student_question)
        )

        if self.api_key:
            messages = [{"role": "system", "content": IELTS_SPEAKING_COACH_PROMPT}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": prompt})
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
                                {"role": "system", "content": IELTS_SPEAKING_COACH_PROMPT},
                                {"role": "user", "content": prompt},
                            ] + (conversation_history or []),
                            "temperature": 0.3,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"] or ""
                    try:
                        parsed = json.loads(content)
                        parsed["source"] = "ai"
                        return parsed
                    except (json.JSONDecodeError, ValueError):
                        return {
                            "answer": content[:500] if content else "I'd be happy to help you with your speaking!",
                            "key_points": [],
                            "example": "",
                            "action_step": "Practice the skill we discussed today.",
                            "tone": "encouraging",
                            "source": "ai_raw",
                        }
            except Exception as e:
                logger.warning("AI speaking coach chat fallback: %s", e)

        return self._fallback_speaking_coach(
            prompt, transcript, evaluation, student_question, weaknesses_str
        )

    def _fallback_speaking_coach(
        self,
        prompt: str,
        transcript: str,
        evaluation: Dict[str, Any],
        student_question: str,
        weaknesses: str,
    ) -> Dict[str, Any]:
        """Deterministic fallback for the speaking coach."""
        band = evaluation.get("overall_band", evaluation.get("band_score", 6.0))
        transcript_preview = transcript[:100] if transcript else "(no transcript)"
        word_count = len(transcript.split()) if transcript else 0

        answer = (
            f"Looking at your response, your overall band is {band}. "
            f"Your transcript is: \"{transcript_preview}\"."
        )
        if student_question:
            answer += f" Regarding your question '{student_question}': "

        if "why did i get" in student_question.lower() or "6.5" in student_question:
            bands = {
                "Fluency & Coherence": evaluation.get("fluency_coherence_band", evaluation.get("fluency_coherence", "")),
                "Lexical Resource": evaluation.get("lexical_resource_band", evaluation.get("lexical_resource", "")),
                "Grammatical Range": evaluation.get("grammatical_range_band", evaluation.get("grammatical_range", "")),
                "Pronunciation": evaluation.get("pronunciation_band", evaluation.get("pronunciation", "")),
            }
            lowest = min(bands, key=lambda k: float(bands[k]) if bands[k] else 9.0)
            answer += (
                f"Your lowest criterion is {lowest} at "
                f"{bands[lowest]}. Improving this will raise your overall band."
            )
            action_step = f"Focus your next practice on {lowest} — use the weak-area practice mode."
        elif "fluency" in student_question.lower():
            answer += (
                f"Your response contains {word_count} words. "
                f"For a stronger fluency score, aim for more detailed, connected responses "
                f"rather than short phrases. Practice timing yourself: 1 minute for Part 1."
            )
            action_step = "Practice extending your Part 1 answers to 40-50 words with 2-3 ideas."
        elif "too short" in student_question.lower():
            if word_count < 40:
                answer += f"Your response seems short at {word_count} words. Try adding examples and explaining your reasons."
            else:
                answer += f"Your response is {word_count} words, which is reasonable for this part."
            action_step = "Count your words after each practice to track length."
        elif "vocabulary" in student_question.lower():
            answer += f"Build topic-specific vocabulary. For your response about '{transcript_preview[:50]}', try using more precise words."
            action_step = "Learn 5 topic-specific synonyms before your next practice."
        elif "grammar" in student_question.lower():
            answer += f"Work on using a mix of simple and complex sentence structures — compound, relative clauses, and conditionals."
            action_step = "Practice writing one complex sentence and one simple sentence per idea."
        else:
            answer += (
                "Your practice shows room for improvement. Keep going — each attempt "
                "builds your confidence and skills!"
            )
            action_step = "Use the weak-area practice mode to focus on your lowest band criterion."

        if weaknesses:
            answer += f" Current weaknesses: {weaknesses}."

        return {
            "answer": answer,
            "key_points": ["Keep practicing", "Focus on your weakest area"],
            "example": "",
            "action_step": action_step,
            "tone": "encouraging",
            "source": "deterministic_fallback",
        }


# Create a single instance
ai_service = AIService()
