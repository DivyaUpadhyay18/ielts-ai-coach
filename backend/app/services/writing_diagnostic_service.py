"""
Writing Diagnostic Module service.

Assesses IELTS Writing through authentic Task 1 (report/letter) and Task 2
(essay) prompts. Writing is free-form: the user writes an essay body that is
auto-saved as they type, tracked against a word count and a countdown timer,
and finally scored manually across the four official IELTS criteria.

Responsibilities:
  - fetch writing prompts (question bank) by task type
  - start an essay tied to a diagnostic attempt (resume support)
  - auto-save the essay body + compute live word count and time (auto-save)
  - complete an essay (submit for scoring)
  - apply manual IELTS scoring (Task Response, Coherence & Cohesion,
    Lexical Resource, Grammatical Range) and derive the overall band
  - persist essays (store essays) with reserved JSONB columns for future
    AI evaluation (grammar, vocabulary, full AI band)
  - build and return a writing report

The AI-evaluation scaffold is provided via `ai_evaluate()` which calls the
existing `app.services.ai_service` when an API key is present, otherwise
returns a placeholder — ready to be wired into a future AI module.
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.diagnostic_repo import DiagnosticRepository
from app.repositories.writing_diagnostic_repo import WritingDiagnosticRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable constants (deterministic — no AI)
# ---------------------------------------------------------------------------
# IELTS bands are in 0.5 steps.
BAND_STEP = 0.5

# Default word counts and time limits (used as fallback if a prompt is missing).
DEFAULT_TASK_1_WORDS = 150
DEFAULT_TASK_2_WORDS = 250
DEFAULT_TASK_1_TIME = 1200  # 20 minutes
DEFAULT_TASK_2_TIME = 2400  # 40 minutes

# Human-readable labels for the writing task types.
TASK_LABELS = {
    "task_1": "Academic Task 1",
    "task_2": "Task 2 Essay",
}

# The four official IELTS Writing marking criteria.
CRITERIA_KEYS = (
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammatical_range",
)


class WritingDiagnosticService:
    """Business logic for the Writing Diagnostic Module."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = WritingDiagnosticRepository(db)
        # Reuse the generic diagnostic repo for attempt lifecycle.
        self.diag_repo = DiagnosticRepository(db)

    # ------------------------------------------------------------------
    # Question bank
    # ------------------------------------------------------------------
    def get_prompts(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Return all active writing prompts, optionally filtered by task type."""
        if task_type and task_type not in ("task_1", "task_2"):
            raise ValidationError(f"Unknown task type: {task_type}")

        prompts = self.repo.get_prompts(task_type)
        bank = []
        for p in sorted(prompts, key=lambda x: int(x.get("difficulty") or 3)):
            bank.append({
                "id": p["id"],
                "task_type": p.get("task_type") or "task_2",
                "title": p["title"],
                "prompt_text": p["prompt_text"],
                "word_limit": int(p.get("word_limit") or (
                    DEFAULT_TASK_1_WORDS if p.get("task_type") == "task_1" else DEFAULT_TASK_2_WORDS
                )),
                "time_limit_seconds": int(p.get("time_limit_seconds") or (
                    DEFAULT_TASK_1_TIME if p.get("task_type") == "task_1" else DEFAULT_TASK_2_TIME
                )),
                "difficulty": int(p.get("difficulty") or 3),
                "topics": p.get("topics") or [],
            })
        task = task_type or "all"
        return {"task_type": task, "prompts": bank, "total": len(bank)}

    # ------------------------------------------------------------------
    # Essay lifecycle
    # ------------------------------------------------------------------
    def start_essay(self, user_id: str, prompt_id: str) -> Dict[str, Any]:
        """Start a writing essay for a prompt (reusing/resuming an attempt)."""
        prompt = self.repo.get_prompt(prompt_id)
        if not prompt:
            raise NotFoundError("Writing prompt not found")

        # Reuse an active diagnostic attempt if present (resume support).
        attempt = self.diag_repo.get_active_attempt(user_id)
        if not attempt:
            attempt = self.diag_repo.create_attempt(user_id, {
                "current_section": "writing",
            })
        attempt_id = attempt["id"]

        # If an essay already exists for this attempt, return it (resume).
        existing = self.repo.get_essay_by_attempt(attempt_id, user_id)
        if existing:
            return self._essay_payload(existing, prompt)

        task_type = prompt.get("task_type") or "task_2"
        essay = self.repo.create_essay(user_id, {
            "attempt_id": attempt_id,
            "prompt_id": prompt["id"],
            "task_type": task_type,
            "title": prompt.get("title") or "",
            "status": "in_progress",
        })

        logger.info("writing essay started user=%s essay=%s attempt=%s", user_id, essay["id"], attempt_id)
        return self._essay_payload(essay, prompt)

    def auto_save(
        self,
        user_id: str,
        essay_id: str,
        essay_text: str,
        time_seconds_spent: int,
    ) -> Dict[str, Any]:
        """Auto-save the essay body and update word count + time."""
        essay = self.repo.get_essay(essay_id, user_id)
        if not essay:
            raise NotFoundError("Writing essay not found")
        if essay.get("status") == "completed":
            raise ValidationError("Essay already completed")

        word_count = self._count_words(essay_text)
        data = {
            "essay_text": essay_text,
            "word_count": word_count,
            "time_seconds_spent": max(0, int(time_seconds_spent or 0)),
            "saved_at": datetime.utcnow().isoformat(),
        }
        updated = self.repo.update_essay(essay_id, user_id, data)

        # Update shared attempt time tracking.
        self._touch_attempt(essay.get("attempt_id"), user_id, data["time_seconds_spent"])

        prompt = self.repo.get_prompt(essay.get("prompt_id")) if essay.get("prompt_id") else None
        return self._essay_payload(updated, prompt)

    def complete_essay(
        self, user_id: str, essay_id: str, time_seconds_spent: int
    ) -> Dict[str, Any]:
        """Finalize an essay and mark it as completed (ready for scoring)."""
        essay = self.repo.get_essay(essay_id, user_id)
        if not essay:
            raise NotFoundError("Writing essay not found")

        data = {
            "status": "completed",
            "time_seconds_spent": max(0, int(time_seconds_spent or essay.get("time_seconds_spent") or 0)),
            "completed_at": datetime.utcnow().isoformat(),
        }
        updated = self.repo.update_essay(essay_id, user_id, data)

        # Mark writing as completed on the shared attempt.
        attempt = self.diag_repo.get_attempt(essay.get("attempt_id"), user_id)
        completed = list(attempt.get("sections_completed") or [])
        if "writing" not in completed:
            completed.append("writing")
        self.diag_repo.update_attempt(essay.get("attempt_id"), user_id, {
            "sections_completed": completed,
            "last_activity_at": datetime.utcnow().isoformat(),
        })

        prompt = self.repo.get_prompt(essay.get("prompt_id")) if essay.get("prompt_id") else None
        logger.info("writing essay completed user=%s essay=%s", user_id, essay_id)
        return self._essay_payload(updated, prompt)

    # ------------------------------------------------------------------
    # Manual scoring
    # ------------------------------------------------------------------
    def submit_manual_score(
        self,
        user_id: str,
        essay_id: str,
        scores: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply manual IELTS scoring across the four criteria."""
        essay = self.repo.get_essay(essay_id, user_id)
        if not essay:
            raise NotFoundError("Writing essay not found")

        # Normalize and round each score to nearest 0.5 within [0, 9].
        normalized = {}
        for key in CRITERIA_KEYS:
            val = scores.get(key)
            if val is None:
                raise ValidationError(f"Missing score for criterion: {key}")
            normalized[key] = self._round_band(float(val))

        overall = self._round_band(
            sum(normalized.values()) / len(normalized)
        )

        data = {
            **normalized,
            "overall_band": overall,
            "status": "completed",
            "completed_at": essay.get("completed_at") or datetime.utcnow().isoformat(),
        }
        updated = self.repo.update_essay(essay_id, user_id, data)

        prompt = self.repo.get_prompt(essay.get("prompt_id")) if essay.get("prompt_id") else None
        logger.info("writing essay scored user=%s essay=%s overall=%.1f", user_id, essay_id, overall)
        return self._essay_payload(updated, prompt)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    def get_report(self, user_id: str, essay_id: str) -> Dict[str, Any]:
        """Build and return the writing diagnostic report for an essay."""
        essay = self.repo.get_essay(essay_id, user_id)
        if not essay:
            raise NotFoundError("Writing essay not found")

        prompt = self.repo.get_prompt(essay.get("prompt_id")) if essay.get("prompt_id") else None
        payload = self._essay_payload(essay, prompt)
        scored = essay.get("overall_band") is not None
        return {
            "essay": payload,
            "is_scored": scored,
            "completed": essay.get("status") == "completed",
        }

    def list_essays(self, user_id: str, limit: int = 20) -> Dict[str, Any]:
        """Return a user's stored writing essays/results."""
        rows = self.repo.list_essays(user_id, limit)
        results = []
        for r in rows:
            prompt = self.repo.get_prompt(r.get("prompt_id")) if r.get("prompt_id") else None
            results.append(self._essay_payload(r, prompt))
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Future AI evaluation scaffold
    # ------------------------------------------------------------------
    def ai_evaluate(
        self, user_id: str, essay_id: str
    ) -> Dict[str, Any]:
        """
        Architecture scaffold for future AI evaluation.

        When an OpenAI API key is configured, this calls the existing
        `ai_service.analyze_writing()` to produce a full AI band assessment
        and accompanying grammar/vocabulary feedback. Otherwise it returns a
        deterministic placeholder so the pipeline is already wired.

        The result is persisted into the reserved `ai_evaluation`,
        `grammar_feedback`, and `vocabulary_feedback` JSONB columns.
        """
        essay = self.repo.get_essay(essay_id, user_id)
        if not essay:
            raise NotFoundError("Writing essay not found")

        essay_text = essay.get("essay_text") or ""

        # Attempt to call the real AI service; fall back to placeholder.
        try:
            from app.services.ai_service import ai_service
            result = ai_service.analyze_writing(essay_text)
            band = float(result.get("band_score") or 0.0)
            grammar = {
                "summary": result.get("feedback") or "",
                "corrections": result.get("corrections") or [],
                "source": "ai",
            }
            vocabulary = {
                "summary": "AI vocabulary feedback will appear here.",
                "source": "placeholder",
            }
            ai_eval = {
                "band": band,
                "criteria": {
                    "task_response": None,
                    "coherence_cohesion": None,
                    "lexical_resource": None,
                    "grammatical_range": None,
                },
                "feedback": result.get("feedback") or "",
                "source": "ai",
            }
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("AI evaluation fallback: %s", e)
            band = 0.0
            grammar = {"summary": "Grammar feedback placeholder.", "source": "placeholder"}
            vocabulary = {"summary": "Vocabulary feedback placeholder.", "source": "placeholder"}
            ai_eval = {
                "band": None,
                "criteria": {k: None for k in CRITERIA_KEYS},
                "feedback": "AI evaluation placeholder. Connect an AI provider to enable.",
                "source": "placeholder",
            }

        data = {
            "grammar_feedback": grammar,
            "vocabulary_feedback": vocabulary,
            "ai_evaluation": ai_eval,
        }
        updated = self.repo.update_essay(essay_id, user_id, data)
        prompt = self.repo.get_prompt(essay.get("prompt_id")) if essay.get("prompt_id") else None
        return self._essay_payload(updated, prompt)

    # ------------------------------------------------------------------
    # Payload + helpers
    # ------------------------------------------------------------------
    def _essay_payload(
        self, essay: Dict[str, Any], prompt: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Project a DB row (plus optional prompt snapshot) into the API shape."""
        return {
            "id": essay.get("id"),
            "attempt_id": essay.get("attempt_id"),
            "user_id": essay.get("user_id"),
            "prompt_id": essay.get("prompt_id"),
            "task_type": essay.get("task_type") or "task_2",
            "title": essay.get("title") or "",
            "essay_text": essay.get("essay_text") or "",
            "word_count": int(essay.get("word_count") or 0),
            "time_seconds_spent": int(essay.get("time_seconds_spent") or 0),
            "status": essay.get("status") or "in_progress",
            # prompt snapshot
            "prompt_text": (prompt or {}).get("prompt_text"),
            "word_limit": int((prompt or {}).get("word_limit") or 0) or None,
            "time_limit_seconds": int((prompt or {}).get("time_limit_seconds") or 0) or None,
            # manual scores
            "task_response": _to_float(essay.get("task_response")),
            "coherence_cohesion": _to_float(essay.get("coherence_cohesion")),
            "lexical_resource": _to_float(essay.get("lexical_resource")),
            "grammatical_range": _to_float(essay.get("grammatical_range")),
            "overall_band": _to_float(essay.get("overall_band")),
            # AI placeholders (future)
            "grammar_feedback": essay.get("grammar_feedback") or {},
            "vocabulary_feedback": essay.get("vocabulary_feedback") or {},
            "ai_evaluation": essay.get("ai_evaluation") or {},
            "saved_at": essay.get("saved_at"),
            "completed_at": essay.get("completed_at"),
            "created_at": essay.get("created_at"),
        }

    @staticmethod
    def _count_words(text: str) -> int:
        """Count words in an essay (whitespace-separated tokens)."""
        if not text:
            return 0
        return len(re.findall(r"\S+", text.strip()))

    @staticmethod
    def _round_band(value: float) -> float:
        """Round to nearest 0.5 and clamp to [0, 9]."""
        value = max(0.0, min(9.0, float(value)))
        return round(value * 2) / 2

    def _touch_attempt(self, attempt_id: str, user_id: str, seconds: int) -> None:
        """Update time tracking on the shared attempt."""
        if not attempt_id:
            return
        attempt = self.diag_repo.get_attempt(attempt_id, user_id)
        total = int(attempt.get("total_seconds_spent") or 0) + seconds
        section_seconds = dict(attempt.get("section_seconds") or {})
        section_seconds["writing"] = int(section_seconds.get("writing", 0)) + seconds
        self.diag_repo.update_attempt(attempt_id, user_id, {
            "total_seconds_spent": total,
            "section_seconds": section_seconds,
            "last_activity_at": datetime.utcnow().isoformat(),
        })


def _to_float(value: Any) -> Optional[float]:
    """Convert a value to float, or None if empty."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Singleton bound to the shared DB session.
from app.db.session import db_session

writing_diagnostic_service = WritingDiagnosticService(db_session)
