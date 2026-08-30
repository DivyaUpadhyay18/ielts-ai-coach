"""
Speaking Diagnostic Module service.

Assesses IELTS Speaking across the three official parts:
  - Part 1 (Introduction & Interview)
  - Part 2 (Individual Long Turn with prep + speaking time)
  - Part 3 (Two-way Discussion)

Speaking is free-form: the user records a spoken response (audio captured
client-side via MediaRecorder), the audio asset URL is persisted, and the
response is scored manually across the four official IELTS Speaking criteria.

Responsibilities:
  - fetch speaking prompts (rotating question bank) by part
  - start a recording tied to a diagnostic attempt (resume support)
  - save the recorded audio metadata + transcript (store recordings)
  - complete a recording (submit for scoring)
  - apply manual IELTS scoring (Fluency & Coherence, Lexical Resource,
    Grammatical Range, Pronunciation) and derive the overall band
  - persist recordings with a reserved JSONB column for future AI evaluation
  - build and return a speaking report

The AI-evaluation scaffold is provided via `ai_evaluate()` which calls the
existing `app.services.ai_service` when an API key is present, otherwise
returns a placeholder — ready to be wired into a future AI speaking module.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.diagnostic_repo import DiagnosticRepository
from app.repositories.speaking_diagnostic_repo import SpeakingDiagnosticRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable constants (deterministic — no AI)
# ---------------------------------------------------------------------------
# IELTS bands are in 0.5 steps.
BAND_STEP = 0.5

# Default prep / speak times per part (used as fallback if a prompt is missing).
DEFAULT_PREP_TIMES = {
    "part_1": 0,
    "part_2": 60,   # 1 minute preparation
    "part_3": 0,
}
DEFAULT_SPEAK_TIMES = {
    "part_1": 60,
    "part_2": 120,  # 2 minutes long turn
    "part_3": 90,
}

# Human-readable labels for the speaking parts.
PART_LABELS = {
    "part_1": "Part 1 — Introduction & Interview",
    "part_2": "Part 2 — Individual Long Turn",
    "part_3": "Part 3 — Two-way Discussion",
}

# The four official IELTS Speaking marking criteria.
CRITERIA_KEYS = (
    "fluency_coherence",
    "lexical_resource",
    "grammatical_range",
    "pronunciation",
)


class SpeakingDiagnosticService:
    """Business logic for the Speaking Diagnostic Module."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = SpeakingDiagnosticRepository(db)
        # Reuse the generic diagnostic repo for attempt lifecycle.
        self.diag_repo = DiagnosticRepository(db)

    # ------------------------------------------------------------------
    # Question bank
    # ------------------------------------------------------------------
    def get_prompts(self, part: Optional[str] = None) -> Dict[str, Any]:
        """Return all active speaking prompts, optionally filtered by part."""
        if part and part not in ("part_1", "part_2", "part_3"):
            raise ValidationError(f"Unknown speaking part: {part}")

        prompts = self.repo.get_prompts(part)
        bank = []
        for p in sorted(prompts, key=lambda x: int(x.get("difficulty") or 3)):
            bank.append({
                "id": p["id"],
                "part": p.get("part") or "part_1",
                "title": p["title"],
                "prompt_text": p["prompt_text"],
                "prep_time_seconds": int(p.get("prep_time_seconds") or (
                    DEFAULT_PREP_TIMES.get(p.get("part"), 0)
                )),
                "speak_time_seconds": int(p.get("speak_time_seconds") or (
                    DEFAULT_SPEAK_TIMES.get(p.get("part"), 60)
                )),
                "difficulty": int(p.get("difficulty") or 3),
                "topics": p.get("topics") or [],
                "follow_up": p.get("follow_up"),
            })
        section = part or "all"
        return {"part": section, "prompts": bank, "total": len(bank)}

    # ------------------------------------------------------------------
    # Recording lifecycle
    # ------------------------------------------------------------------
    def start_recording(self, user_id: str, prompt_id: str) -> Dict[str, Any]:
        """Start a speaking recording for a prompt (reusing/resuming an attempt)."""
        prompt = self.repo.get_prompt(prompt_id)
        if not prompt:
            raise NotFoundError("Speaking prompt not found")

        # Reuse an active diagnostic attempt if present (resume support).
        attempt = self.diag_repo.get_active_attempt(user_id)
        if not attempt:
            attempt = self.diag_repo.create_attempt(user_id, {
                "current_section": "speaking",
            })
        attempt_id = attempt["id"]

        # If a recording already exists for this attempt, return it (resume).
        existing = self.repo.get_recording_by_attempt(attempt_id, user_id)
        if existing:
            return self._recording_payload(existing, prompt)

        recording = self.repo.create_recording(user_id, {
            "attempt_id": attempt_id,
            "prompt_id": prompt["id"],
            "part": prompt.get("part") or "part_1",
            "title": prompt.get("title") or "",
            "status": "in_progress",
        })

        logger.info("speaking recording started user=%s recording=%s attempt=%s", user_id, recording["id"], attempt_id)
        return self._recording_payload(recording, prompt)

    def save_recording(
        self,
        user_id: str,
        recording_id: str,
        audio_url: str,
        duration_seconds: int,
        transcript: str,
    ) -> Dict[str, Any]:
        """Save the recorded audio metadata + transcript (store recordings)."""
        recording = self.repo.get_recording(recording_id, user_id)
        if not recording:
            raise NotFoundError("Speaking recording not found")
        if recording.get("status") == "completed":
            raise ValidationError("Recording already completed")

        data = {
            "audio_url": audio_url,
            "duration_seconds": max(0, int(duration_seconds or 0)),
            "transcript": transcript,
            "saved_at": datetime.utcnow().isoformat(),
        }
        updated = self.repo.update_recording(recording_id, user_id, data)

        prompt = self.repo.get_prompt(recording.get("prompt_id")) if recording.get("prompt_id") else None
        return self._recording_payload(updated, prompt)

    def complete_recording(
        self, user_id: str, recording_id: str, duration_seconds: int
    ) -> Dict[str, Any]:
        """Finalize a recording and mark it as completed (ready for scoring)."""
        recording = self.repo.get_recording(recording_id, user_id)
        if not recording:
            raise NotFoundError("Speaking recording not found")

        data = {
            "status": "completed",
            "duration_seconds": max(0, int(duration_seconds or recording.get("duration_seconds") or 0)),
            "completed_at": datetime.utcnow().isoformat(),
        }
        updated = self.repo.update_recording(recording_id, user_id, data)

        # Mark speaking as completed on the shared attempt.
        attempt = self.diag_repo.get_attempt(recording.get("attempt_id"), user_id)
        completed = list(attempt.get("sections_completed") or [])
        if "speaking" not in completed:
            completed.append("speaking")
        self.diag_repo.update_attempt(recording.get("attempt_id"), user_id, {
            "sections_completed": completed,
            "last_activity_at": datetime.utcnow().isoformat(),
        })

        prompt = self.repo.get_prompt(recording.get("prompt_id")) if recording.get("prompt_id") else None
        logger.info("speaking recording completed user=%s recording=%s", user_id, recording_id)
        return self._recording_payload(updated, prompt)

    # ------------------------------------------------------------------
    # Manual scoring
    # ------------------------------------------------------------------
    def submit_manual_score(
        self,
        user_id: str,
        recording_id: str,
        scores: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply manual IELTS scoring across the four criteria."""
        recording = self.repo.get_recording(recording_id, user_id)
        if not recording:
            raise NotFoundError("Speaking recording not found")

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
            "completed_at": recording.get("completed_at") or datetime.utcnow().isoformat(),
        }
        updated = self.repo.update_recording(recording_id, user_id, data)

        prompt = self.repo.get_prompt(recording.get("prompt_id")) if recording.get("prompt_id") else None
        logger.info("speaking recording scored user=%s recording=%s overall=%.1f", user_id, recording_id, overall)
        return self._recording_payload(updated, prompt)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    def get_report(self, user_id: str, recording_id: str) -> Dict[str, Any]:
        """Build and return the speaking diagnostic report for a recording."""
        recording = self.repo.get_recording(recording_id, user_id)
        if not recording:
            raise NotFoundError("Speaking recording not found")

        prompt = self.repo.get_prompt(recording.get("prompt_id")) if recording.get("prompt_id") else None
        payload = self._recording_payload(recording, prompt)
        scored = recording.get("overall_band") is not None
        return {
            "recording": payload,
            "is_scored": scored,
            "completed": recording.get("status") == "completed",
        }

    def list_recordings(self, user_id: str, limit: int = 20) -> Dict[str, Any]:
        """Return a user's stored speaking recordings/results."""
        rows = self.repo.list_recordings(user_id, limit)
        results = []
        for r in rows:
            prompt = self.repo.get_prompt(r.get("prompt_id")) if r.get("prompt_id") else None
            results.append(self._recording_payload(r, prompt))
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Future AI evaluation scaffold
    # ------------------------------------------------------------------
    def ai_evaluate(
        self, user_id: str, recording_id: str
    ) -> Dict[str, Any]:
        """
        Architecture scaffold for future AI evaluation.

        When an OpenAI API key is configured, this calls the existing
        `ai_service.analyze_speaking()` to produce a full AI band assessment
        for the stored transcript. Otherwise it returns a deterministic
        placeholder so the pipeline is already wired.

        The result is persisted into the reserved `ai_evaluation` JSONB column.
        """
        recording = self.repo.get_recording(recording_id, user_id)
        if not recording:
            raise NotFoundError("Speaking recording not found")

        transcript = recording.get("transcript") or ""

        # Attempt to call the real AI service; fall back to placeholder.
        try:
            from app.services.ai_service import ai_service
            result = ai_service.analyze_speaking(transcript)
            band = float(result.get("band_score") or 0.0)
            ai_eval = {
                "band": band,
                "criteria": {
                    "fluency_coherence": None,
                    "lexical_resource": None,
                    "grammatical_range": None,
                    "pronunciation": None,
                },
                "feedback": result.get("feedback") or "",
                "source": "ai",
            }
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("AI evaluation fallback: %s", e)
            band = 0.0
            ai_eval = {
                "band": None,
                "criteria": {k: None for k in CRITERIA_KEYS},
                "feedback": "AI evaluation placeholder. Connect an AI provider to enable.",
                "source": "placeholder",
            }

        data = {"ai_evaluation": ai_eval}
        updated = self.repo.update_recording(recording_id, user_id, data)
        prompt = self.repo.get_prompt(recording.get("prompt_id")) if recording.get("prompt_id") else None
        return self._recording_payload(updated, prompt)

    # ------------------------------------------------------------------
    # Payload + helpers
    # ------------------------------------------------------------------
    def _recording_payload(
        self, recording: Dict[str, Any], prompt: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Project a DB row (plus optional prompt snapshot) into the API shape."""
        return {
            "id": recording.get("id"),
            "attempt_id": recording.get("attempt_id"),
            "user_id": recording.get("user_id"),
            "prompt_id": recording.get("prompt_id"),
            "part": recording.get("part") or "part_1",
            "title": recording.get("title") or "",
            "audio_url": recording.get("audio_url") or "",
            "duration_seconds": int(recording.get("duration_seconds") or 0),
            "transcript": recording.get("transcript") or "",
            "status": recording.get("status") or "in_progress",
            # prompt snapshot
            "prompt_text": (prompt or {}).get("prompt_text"),
            "prep_time_seconds": int((prompt or {}).get("prep_time_seconds") or 0) or None,
            "speak_time_seconds": int((prompt or {}).get("speak_time_seconds") or 0) or None,
            "follow_up": (prompt or {}).get("follow_up"),
            # manual scores
            "fluency_coherence": _to_float(recording.get("fluency_coherence")),
            "lexical_resource": _to_float(recording.get("lexical_resource")),
            "grammatical_range": _to_float(recording.get("grammatical_range")),
            "pronunciation": _to_float(recording.get("pronunciation")),
            "overall_band": _to_float(recording.get("overall_band")),
            # AI placeholder (future)
            "ai_evaluation": recording.get("ai_evaluation") or {},
            "saved_at": recording.get("saved_at"),
            "completed_at": recording.get("completed_at"),
            "created_at": recording.get("created_at"),
        }

    @staticmethod
    def _round_band(value: float) -> float:
        """Round to nearest 0.5 and clamp to [0, 9]."""
        value = max(0.0, min(9.0, float(value)))
        return round(value * 2) / 2


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

speaking_diagnostic_service = SpeakingDiagnosticService(db_session)
