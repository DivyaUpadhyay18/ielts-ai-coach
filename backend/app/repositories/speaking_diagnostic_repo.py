"""
Repository for the Speaking Diagnostic Module.

Provides data access for:
  - speaking_prompts   (Part 1, 2 & 3 prompts — the rotating question bank)
  - speaking_recordings (stored per-attempt audio recordings, with duration,
                         transcript, manual IELTS scores, and reserved AI column)

All operations are owner-scoped where applicable to prevent cross-user access.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class SpeakingDiagnosticRepository(BaseRepository):
    """Data access for the speaking diagnostic tables."""

    table_name = "speaking_recordings"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------
    def get_prompts(self, part: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all active speaking prompts, optionally filtered by part."""
        query = (
            self.db.table("speaking_prompts")
            .select("*")
            .eq("is_active", True)
        )
        if part:
            query = query.eq("part", part)
        result = self.db.execute(query, "fetch speaking prompts")
        return result.data or []

    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single active speaking prompt by id."""
        query = (
            self.db.table("speaking_prompts")
            .select("*")
            .eq("id", prompt_id)
            .eq("is_active", True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking prompt")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Recordings
    # ------------------------------------------------------------------
    def create_recording(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new speaking recording for a user."""
        payload = {
            "attempt_id": data.get("attempt_id"),
            "user_id": user_id,
            "prompt_id": data.get("prompt_id"),
            "part": data.get("part") or "part_1",
            "title": data.get("title") or "",
            "audio_url": data.get("audio_url") or "",
            "duration_seconds": int(data.get("duration_seconds") or 0),
            "transcript": data.get("transcript") or "",
            "status": data.get("status") or "in_progress",
        }
        query = self.db.table("speaking_recordings").insert(payload)
        result = self.db.execute(query, "create speaking recording")
        if not result.data:
            raise NotFoundError("Failed to create speaking recording")
        return result.data[0]

    def get_recording(
        self, recording_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single recording scoped to the owner."""
        query = (
            self.db.table("speaking_recordings")
            .select("*")
            .eq("id", recording_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking recording")
        if not result.data:
            return None
        return result.data[0]

    def get_recording_by_attempt(
        self, attempt_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch the recording for an attempt (owner-scoped)."""
        query = (
            self.db.table("speaking_recordings")
            .select("*")
            .eq("attempt_id", attempt_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking recording by attempt")
        if not result.data:
            return None
        return result.data[0]

    def update_recording(
        self, recording_id: str, user_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a recording scoped to the owner."""
        return self.update(recording_id, data, user_id)

    def list_recordings(
        self, user_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List a user's stored recordings (most recent first)."""
        query = (
            self.db.table("speaking_recordings")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list speaking recordings")
        return result.data or []
