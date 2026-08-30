"""
Repository for the Speaking Test Workspace module.

Provides data access for:
  - speaking_test_sessions   (full 3-part test attempts)
  - speaking_test_responses  (per-question recorded responses)

Prompts are sourced from the existing speaking_prompts table (v023).

All operations are owner-scoped to prevent cross-user access (IDOR).
"""
from datetime import datetime
from typing import Any

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class SpeakingTestRepository(BaseRepository):
    """Data access for speaking_test_sessions (inherits BaseRepository CRUD)."""

    table_name = "speaking_test_sessions"
    user_id_column = "user_id"
    _ownable = True

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Prompts (reuse speaking_prompts table)
    # ------------------------------------------------------------------
    def get_prompts(self, part: str | None = None) -> list[dict[str, Any]]:
        """Fetch active speaking prompts, optionally filtered by part."""
        query = (
            self.db.table("speaking_prompts")
            .select("*")
            .eq("is_active", True)
        )
        if part:
            query = query.eq("part", part)
        result = self.db.execute(query, "fetch speaking test prompts")
        return result.data or []

    def get_prompt(self, prompt_id: str) -> dict[str, Any] | None:
        """Fetch a single active speaking prompt by id."""
        query = (
            self.db.table("speaking_prompts")
            .select("*")
            .eq("id", prompt_id)
            .eq("is_active", True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking test prompt")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------
    def get_session(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        """Fetch a single session scoped to the owner."""
        query = (
            self.db.table("speaking_test_sessions")
            .select("*")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking test session")
        if not result.data:
            return None
        return result.data[0]

    def get_active_session(self, user_id: str) -> dict[str, Any] | None:
        """Fetch the user's latest in-progress session (for resume)."""
        query = (
            self.db.table("speaking_test_sessions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "in_progress")
            .order("started_at", desc=True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch active speaking test session")
        if not result.data:
            return None
        return result.data[0]

    def list_sessions(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """List all sessions for a user (most recent first)."""
        query = (
            self.db.table("speaking_test_sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("started_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list speaking test sessions")
        return result.data or []

    def create_session(self, user_id: str) -> dict[str, Any]:
        """Create a new speaking test session."""
        payload = {
            "user_id": user_id,
            "current_part": "part_1",
            "status": "in_progress",
        }
        query = self.db.table("speaking_test_sessions").insert(payload)
        result = self.db.execute(query, "create speaking test session")
        if not result.data:
            raise NotFoundError("Failed to create speaking test session")
        return result.data[0]

    def update_session(self, session_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a session scoped to the owner."""
        data["updated_at"] = datetime.utcnow().isoformat()
        query = (
            self.db.table("speaking_test_sessions")
            .update(data)
            .eq("id", session_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "update speaking test session")
        if not result.data:
            raise NotFoundError("Speaking test session not found")
        return result.data[0]

    # ------------------------------------------------------------------
    # Response CRUD
    # ------------------------------------------------------------------
    def create_response(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a new speaking test response."""
        payload = {
            "session_id": data["session_id"],
            "user_id": user_id,
            "prompt_id": data.get("prompt_id"),
            "part": data.get("part") or "part_1",
            "title": data.get("title") or "",
            "prompt_text": data.get("prompt_text") or "",
            "prep_time_seconds": int(data.get("prep_time_seconds") or 0),
            "speak_time_seconds": int(data.get("speak_time_seconds") or 60),
            "audio_url": data.get("audio_url") or "",
            "duration_seconds": int(data.get("duration_seconds") or 0),
            "transcript": data.get("transcript") or "",
            "is_saved": bool(data.get("is_saved") or False),
        }
        query = self.db.table("speaking_test_responses").insert(payload)
        result = self.db.execute(query, "create speaking test response")
        if not result.data:
            raise NotFoundError("Failed to create speaking test response")
        return result.data[0]

    def get_response(self, response_id: str, user_id: str) -> dict[str, Any] | None:
        """Fetch a single response scoped to the owner."""
        query = (
            self.db.table("speaking_test_responses")
            .select("*")
            .eq("id", response_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking test response")
        if not result.data:
            return None
        return result.data[0]

    def update_response(self, response_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a response scoped to the owner."""
        data["updated_at"] = datetime.utcnow().isoformat()
        query = (
            self.db.table("speaking_test_responses")
            .update(data)
            .eq("id", response_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "update speaking test response")
        if not result.data:
            raise NotFoundError("Speaking test response not found")
        return result.data[0]

    def delete_response(self, response_id: str, user_id: str) -> None:
        """Delete a response scoped to the owner."""
        query = (
            self.db.table("speaking_test_responses")
            .delete()
            .eq("id", response_id)
            .eq("user_id", user_id)
        )
        self.db.execute(query, "delete speaking test response")

    def list_responses(self, session_id: str, user_id: str) -> list[dict[str, Any]]:
        """List all responses for a session (owner-scoped)."""
        query = (
            self.db.table("speaking_test_responses")
            .select("*")
            .eq("session_id", session_id)
            .eq("user_id", user_id)
            .order("created_at", desc=False)
        )
        result = self.db.execute(query, "list speaking test responses")
        return result.data or []

    def get_response_by_prompt(
        self, session_id: str, prompt_id: str, user_id: str
    ) -> dict[str, Any] | None:
        """Fetch the response for a specific (session, prompt) pair."""
        query = (
            self.db.table("speaking_test_responses")
            .select("*")
            .eq("session_id", session_id)
            .eq("prompt_id", prompt_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking test response by prompt")
        if not result.data:
            return None
        return result.data[0]


class SpeakingTestStorageRepository:
    """Handles audio file uploads via the Supabase storage API."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    def upload_audio(
        self, user_id: str, filename: str, data: bytes
    ) -> str:
        """Upload an audio blob to Supabase Storage and return the public URL."""
        bucket = "speaking-tests"
        path = f"{user_id}/{filename}"

        client = self.db.client
        try:
            result = client.storage.from_(bucket).upload(
                path=path,
                file=data,
                file_options={"cacheControl": "3600", "upsert": False},
            )
            if result.error:
                raise NotFoundError(f"Storage upload failed: {result.error}")
        except Exception:
            # If storage is not configured, fall back to data URI
            raise NotFoundError("Audio storage not available")

        # Get the public URL
        public_url = client.storage.from_(bucket).get_public_url(path)
        return public_url
