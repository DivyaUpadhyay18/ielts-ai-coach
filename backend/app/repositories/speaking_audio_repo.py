"""
Repository for the Speaking Audio Processing Pipeline.

Provides data access for ``speaking_evaluations`` (one record per submitted
speaking response) plus storage helpers to download the original recording
for transcription.

The original recording is never modified or deleted by the pipeline — it is
downloaded for STT and re-stored only if the provider ever needs a prepared
copy. All operations are owner-scoped to prevent cross-user access (IDOR).
"""
import logging
import re
from datetime import datetime
from typing import Any

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class SpeakingAudioRepository(BaseRepository):
    """Data access for speaking_evaluations (owner-scoped)."""

    table_name = "speaking_evaluations"
    user_id_column = "user_id"
    _ownable = True

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Evaluation CRUD
    # ------------------------------------------------------------------
    def create_evaluation(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a pipeline evaluation record."""
        row = {
            "user_id": data.get("user_id"),
            "response_id": data.get("response_id"),
            "session_id": data.get("session_id"),
            "part": data.get("part") or "part_1",
            "audio_url": data.get("audio_url") or "",
            "audio_duration_seconds": int(data.get("audio_duration_seconds") or 0),
            "file_size_bytes": int(data.get("file_size_bytes") or 0),
            "transcript": data.get("transcript") or "",
            "provider": data.get("provider") or "openai_whisper",
            "model": data.get("model") or "whisper-1",
            "status": data.get("status") or "queued",
            "error_message": data.get("error_message") or "",
            "retry_count": int(data.get("retry_count") or 0),
        }
        result = self.db.execute(
            self.db.table("speaking_evaluations").insert(row),
            "create speaking evaluation",
        )
        return result.data[0]

    def get_evaluation(self, evaluation_id: str, user_id: str) -> dict[str, Any] | None:
        """Fetch a single evaluation scoped to the owner."""
        query = (
            self.db.table("speaking_evaluations")
            .select("*")
            .eq("id", evaluation_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking evaluation")
        if not result.data:
            return None
        return result.data[0]

    def get_evaluation_by_response(
        self, response_id: str, user_id: str
    ) -> dict[str, Any] | None:
        """Fetch the evaluation for a specific response (owner-scoped)."""
        query = (
            self.db.table("speaking_evaluations")
            .select("*")
            .eq("response_id", response_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking evaluation by response")
        if not result.data:
            return None
        return result.data[0]

    def list_evaluations(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """List a user's evaluations (most recent first)."""
        query = (
            self.db.table("speaking_evaluations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list speaking evaluations")
        return result.data or []

    def update_evaluation(
        self, evaluation_id: str, user_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an evaluation scoped to the owner."""
        row = dict(data)
        row["updated_at"] = datetime.utcnow().isoformat()
        query = (
            self.db.table("speaking_evaluations")
            .update(row)
            .eq("id", evaluation_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "update speaking evaluation")
        if not result.data:
            raise NotFoundError("Speaking evaluation not found")
        return result.data[0]

    def get_evaluation_unscoped(self, evaluation_id: str) -> dict[str, Any] | None:
        """
        Fetch an evaluation by id without a user filter — used by the
        background transcription worker which already knows the evaluation id.
        """
        query = (
            self.db.table("speaking_evaluations")
            .select("*")
            .eq("id", evaluation_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking evaluation for processing")
        if not result.data:
            return None
        return result.data[0]

    def update_evaluation_unscoped(
        self, evaluation_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update an evaluation by id without a user filter — used by the
        background transcription worker (server-side processing).
        """
        row = dict(data)
        row["updated_at"] = datetime.utcnow().isoformat()
        query = (
            self.db.table("speaking_evaluations")
            .update(row)
            .eq("id", evaluation_id)
        )
        result = self.db.execute(query, "update speaking evaluation (worker)")
        if not result.data:
            raise NotFoundError("Speaking evaluation not found")
        return result.data[0]


class SpeakingAudioStorageRepository:
    """Storage helpers for the audio pipeline (download original for STT)."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    @staticmethod
    def parse_public_url(public_url: str) -> tuple[str, str] | None:
        """
        Parse a Supabase public storage URL into (bucket, path).

        Handles ``https://<ref>.supabase.co/storage/v1/object/public/<bucket>/<path>``.
        Returns None when the URL is not a Supabase object URL.
        """
        pattern = r"/storage/v1/object/public/([^/]+)/(.+)$"
        match = re.search(pattern, public_url)
        if not match:
            return None
        return match.group(1), match.group(2)

    def download_audio(self, public_url: str) -> bytes:
        """
        Download the original recording bytes from Supabase Storage.

        Raises :class:`NotFoundError` when the URL is invalid or the object
        is missing (the pipeline converts this into a failed evaluation).
        """
        parsed = self.parse_public_url(public_url)
        if not parsed:
            raise NotFoundError("Audio URL is not a valid stored object")
        bucket, path = parsed

        client = self.db.client
        try:
            result = client.storage.from_(bucket).download(path)
        except Exception as exc:
            logger.warning("audio download failed bucket=%s path=%s err=%s", bucket, path, exc)
            raise NotFoundError(f"Audio object not available in storage: {exc}")

        if result is None:
            raise NotFoundError("Audio object not available in storage")
        return result if isinstance(result, bytes) else bytes(result)

        if not result.data:
            return None
        return result.data[0]
