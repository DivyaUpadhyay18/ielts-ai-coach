"""
Speaking Test Workspace service.

Provides the business logic for the full IELTS Speaking test workspace:
  - Fetch prompts from the shared speaking_prompts question bank
  - Start / resume a test session (Part 1 → Part 2 → Part 3)
  - Start / save / delete / complete per-question responses
  - Advance through parts
  - Complete the test and log progress (study session tracking)
  - Upload audio to Supabase Storage

All operations are owner-scoped (user_id from JWT). No AI evaluation.
"""
import logging
import uuid
from datetime import datetime
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.speaking_test_repo import (
    SpeakingTestRepository,
    SpeakingTestStorageRepository,
)

logger = logging.getLogger(__name__)

PART_ORDER = ("part_1", "part_2", "part_3")

# Default prep / speak times (fallback if a prompt is missing the value).
DEFAULT_PREP_TIME = 60  # seconds — Part 2
DEFAULT_SPEAK_TIME = 60  # seconds


class SpeakingTestService:
    """Business logic for the IELTS Speaking Test Workspace."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = SpeakingTestRepository(db)
        self.storage = SpeakingTestStorageRepository(db)

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------
    def get_prompts(self, part: str | None = None) -> dict[str, Any]:
        """Return active speaking prompts, optionally filtered by part."""
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
                "prep_time_seconds": int(p.get("prep_time_seconds") or 0),
                "speak_time_seconds": int(p.get("speak_time_seconds") or DEFAULT_SPEAK_TIME),
                "difficulty": int(p.get("difficulty") or 3),
                "topics": p.get("topics") or [],
                "follow_up": p.get("follow_up"),
            })
        section = part or "all"
        return {"part": section, "prompts": bank, "total": len(bank)}

    def get_prompt(self, prompt_id: str) -> dict[str, Any]:
        """Fetch a single active prompt by id."""
        p = self.repo.get_prompt(prompt_id)
        if not p:
            raise NotFoundError("Speaking prompt not found")
        return {
            "id": p["id"],
            "part": p.get("part") or "part_1",
            "title": p["title"],
            "prompt_text": p["prompt_text"],
            "prep_time_seconds": int(p.get("prep_time_seconds") or 0),
            "speak_time_seconds": int(p.get("speak_time_seconds") or DEFAULT_SPEAK_TIME),
            "difficulty": int(p.get("difficulty") or 3),
            "topics": p.get("topics") or [],
            "follow_up": p.get("follow_up"),
        }

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def start_test(self, user_id: str) -> dict[str, Any]:
        """Start a new speaking test session. Returns the session + prompts."""
        # If an in-progress session exists, resume it.
        existing = self.repo.get_active_session(user_id)
        if existing:
            logger.info("speaking test resumed user=%s session=%s", user_id, existing["id"])
            return self._session_payload(existing, user_id)

        session = self.repo.create_session(user_id)
        logger.info("speaking test started user=%s session=%s", user_id, session["id"])
        return self._session_payload(session, user_id)

    def get_session(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Fetch a session with all its responses."""
        session = self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Speaking test session not found")
        return self._session_payload(session, user_id, include_responses=True)

    def list_sessions(self, user_id: str, limit: int = 20) -> dict[str, Any]:
        """List all test sessions for a user."""
        rows = self.repo.list_sessions(user_id, limit)
        results = [self._session_payload(r, user_id, include_responses=False) for r in rows]
        return {"results": results, "total": len(results)}

    def get_current_session(self, user_id: str) -> dict[str, Any] | None:
        """Get the user's current in-progress session with responses (resume)."""
        session = self.repo.get_active_session(user_id)
        if not session:
            return None
        return self._session_payload(session, user_id, include_responses=True)

    def advance_part(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Advance the session to the next part."""
        session = self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Speaking test session not found")

        current = session.get("current_part") or "part_1"
        current_idx = PART_ORDER.index(current)
        if current_idx >= len(PART_ORDER) - 1:
            raise ValidationError("Cannot advance beyond Part 3")

        next_part = PART_ORDER[current_idx + 1]
        updated = self.repo.update_session(session_id, user_id, {
            "current_part": next_part,
        })
        logger.info("speaking test advanced user=%s session=%s part=%s→%s", user_id, session_id, current, next_part)
        return self._session_payload(updated, user_id, include_responses=True)

    def complete_test(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Mark the test session as completed and log progress."""
        session = self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Speaking test session not found")

        updated = self.repo.update_session(session_id, user_id, {
            "current_part": "part_3",
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
        })

        # Log progress — best effort.
        try:
            self._log_progress(user_id, session_id)
        except Exception as e:
            logger.warning("progress log skipped user=%s session=%s err=%s", user_id, session_id, e)

        logger.info("speaking test completed user=%s session=%s", user_id, session_id)
        return self._session_payload(updated, user_id, include_responses=True)

    def abandon_test(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Mark the test session as abandoned."""
        session = self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Speaking test session not found")
        updated = self.repo.update_session(session_id, user_id, {"status": "abandoned"})
        return self._session_payload(updated, user_id, include_responses=True)

    # ------------------------------------------------------------------
    # Response lifecycle
    # ------------------------------------------------------------------
    def start_response(
        self, user_id: str, session_id: str, prompt_id: str, part: str
    ) -> dict[str, Any]:
        """Create or resume a response for a specific prompt within a session."""
        if part not in PART_ORDER:
            raise ValidationError(f"Unknown speaking part: {part}")

        session = self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Speaking test session not found")

        prompt = self.repo.get_prompt(prompt_id)
        if not prompt:
            raise NotFoundError("Speaking prompt not found")

        # Reuse existing response for this prompt if present (resume / re-record after delete).
        existing = self.repo.get_response_by_prompt(session_id, prompt_id, user_id)
        if existing:
            logger.info("speaking test response resumed user=%s response=%s", user_id, existing["id"])
            return self._response_payload(existing, prompt)

        response = self.repo.create_response(user_id, {
            "session_id": session_id,
            "prompt_id": prompt["id"],
            "part": prompt.get("part") or part,
            "title": prompt.get("title") or "",
            "prompt_text": prompt.get("prompt_text") or "",
            "prep_time_seconds": int(prompt.get("prep_time_seconds") or 0),
            "speak_time_seconds": int(prompt.get("speak_time_seconds") or DEFAULT_SPEAK_TIME),
        })
        logger.info("speaking test response started user=%s response=%s", user_id, response["id"])
        return self._response_payload(response, prompt)

    def save_response(
        self,
        user_id: str,
        session_id: str,
        response_id: str,
        audio_url: str,
        duration_seconds: int,
        transcript: str,
        is_saved: bool = False,
    ) -> dict[str, Any]:
        """Save the recording metadata for a response."""
        response = self.repo.get_response(response_id, user_id)
        if not response:
            raise NotFoundError("Speaking test response not found")

        # Verify the response belongs to the session.
        if str(response.get("session_id")) != str(session_id):
            raise NotFoundError("Speaking test response not found in this session")

        prompt = None
        if response.get("prompt_id"):
            prompt = self.repo.get_prompt(response["prompt_id"])

        updated = self.repo.update_response(response_id, user_id, {
            "audio_url": audio_url,
            "duration_seconds": max(0, int(duration_seconds or 0)),
            "transcript": transcript,
            "is_saved": bool(is_saved),
        })
        return self._response_payload(updated, prompt)

    def delete_response(self, user_id: str, session_id: str, response_id: str) -> None:
        """Delete a response so the user can re-record."""
        response = self.repo.get_response(response_id, user_id)
        if not response:
            raise NotFoundError("Speaking test response not found")
        if str(response.get("session_id")) != str(session_id):
            raise NotFoundError("Speaking test response not found in this session")
        self.repo.delete_response(response_id, user_id)
        logger.info("speaking test response deleted user=%s response=%s", user_id, response_id)

    def get_response(self, user_id: str, session_id: str, response_id: str) -> dict[str, Any]:
        """Fetch a single response within a session."""
        response = self.repo.get_response(response_id, user_id)
        if not response:
            raise NotFoundError("Speaking test response not found")
        if str(response.get("session_id")) != str(session_id):
            raise NotFoundError("Speaking test response not found in this session")

        prompt = None
        if response.get("prompt_id"):
            prompt = self.repo.get_prompt(response["prompt_id"])
        return self._response_payload(response, prompt)

    def list_responses(self, user_id: str, session_id: str) -> dict[str, Any]:
        """List all responses for a session."""
        session = self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Speaking test session not found")
        rows = self.repo.list_responses(session_id, user_id)
        results = []
        for r in rows:
            prompt = None
            if r.get("prompt_id"):
                prompt = self.repo.get_prompt(r["prompt_id"])
            results.append(self._response_payload(r, prompt))
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Audio upload
    # ------------------------------------------------------------------
    def upload_audio(self, user_id: str, filename: str, data: bytes) -> dict[str, Any]:
        """Upload an audio blob to Supabase Storage; return the public URL."""
        public_url = self.storage.upload_audio(user_id, filename, data)
        return {
            "audio_url": public_url,
            "filename": filename,
            "size": len(data),
        }

    # ------------------------------------------------------------------
    # Progress / payload helpers
    # ------------------------------------------------------------------
    def get_progress(self, user_id: str) -> dict[str, Any]:
        """Get the current test progress for the user."""
        session = self.repo.get_active_session(user_id)
        if not session:
            return {
                "session": None,
                "parts": {},
                "total_responses": 0,
                "completed_parts": [],
            }

        responses = self.repo.list_responses(session["id"], user_id)
        parts_detail: dict[str, dict[str, Any]] = {}
        completed_parts: list[str] = []
        for p in PART_ORDER:
            part_responses = [r for r in responses if (r.get("part") or "part_1") == p]
            parts_detail[p] = {
                "total_prompts": 0,  # filled by caller from prompt bank
                "completed": len(part_responses),
                "responses": [self._response_payload(r, None) for r in part_responses],
            }
            if len(part_responses) > 0:
                completed_parts.append(p)

        # Fill total_prompts from the prompt bank.
        for p in PART_ORDER:
            prompts = self.repo.get_prompts(p)
            parts_detail[p]["total_prompts"] = len(prompts)

        return {
            "session": self._session_payload(session, user_id, include_responses=False),
            "parts": parts_detail,
            "total_responses": len(responses),
            "completed_parts": completed_parts,
        }

    def _log_progress(self, user_id: str, session_id: str) -> None:
        """Log a study session for progress tracking (best-effort)."""
        responses = self.repo.list_responses(session_id, user_id)
        minutes = max(1, sum(r.get("duration_seconds", 0) for r in responses) // 60)

        payload = {
            "session_id": str(uuid.uuid4()),
            "skill": "speaking",
            "minutes": minutes,
            "xp_earned": minutes * 5,
            "session_type": "speaking_test",
            "source_type": "speaking_test",
            "source_id": str(session_id),
            "meta": {
                "title": "IELTS Speaking Test",
                "responses": len(responses),
            },
        }
        self.db.execute(
            self.db.table("study_sessions").insert(payload),
            "log speaking test progress",
        )

    def _session_payload(
        self,
        session: dict[str, Any],
        user_id: str,
        include_responses: bool = False,
    ) -> dict[str, Any]:
        """Project a session DB row into the API response shape."""
        result: dict[str, Any] = {
            "id": session.get("id"),
            "user_id": session.get("user_id"),
            "current_part": session.get("current_part") or "part_1",
            "status": session.get("status") or "in_progress",
            "started_at": session.get("started_at"),
            "updated_at": session.get("updated_at"),
            "completed_at": session.get("completed_at"),
        }
        if include_responses:
            rows = self.repo.list_responses(session.get("id"), user_id)
            result["responses"] = []
            for r in rows:
                prompt = None
                if r.get("prompt_id"):
                    prompt = self.repo.get_prompt(r["prompt_id"])
                result["responses"].append(self._response_payload(r, prompt))
        else:
            result["responses"] = []
        return result

    def _response_payload(
        self,
        response: dict[str, Any],
        prompt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Project a response DB row into the API response shape."""
        p = prompt or {}
        return {
            "id": response.get("id"),
            "session_id": response.get("session_id"),
            "user_id": response.get("user_id"),
            "prompt_id": response.get("prompt_id"),
            "part": response.get("part") or "part_1",
            "title": response.get("title") or p.get("title") or "",
            "prompt_text": response.get("prompt_text") or p.get("prompt_text"),
            "prep_time_seconds": int(response.get("prep_time_seconds") or 0),
            "speak_time_seconds": int(response.get("speak_time_seconds") or 60),
            "audio_url": response.get("audio_url") or "",
            "duration_seconds": int(response.get("duration_seconds") or 0),
            "transcript": response.get("transcript") or "",
            "is_saved": bool(response.get("is_saved") or False),
            "created_at": response.get("created_at"),
            "updated_at": response.get("updated_at"),
        }


# Singleton bound to the shared DB session.
from app.db.session import db_session

speaking_test_service = SpeakingTestService(db_session)
