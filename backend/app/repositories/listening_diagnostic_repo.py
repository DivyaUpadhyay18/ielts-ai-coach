"""
Repository for the Listening Diagnostic Module.

Provides data access for:
  - listening_tracks              (authentic IELTS-style audio sections)
  - diagnostic_questions          (listening questions, filtered by track/type)
  - listening_diagnostic_results  (stored per-attempt listening outcomes)

All operations are owner-scoped where applicable to prevent cross-user access.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class ListeningDiagnosticRepository(BaseRepository):
    """Data access for the listening diagnostic tables."""

    table_name = "listening_diagnostic_results"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Tracks
    # ------------------------------------------------------------------
    def get_tracks(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all active listening tracks."""
        query = (
            self.db.table("listening_tracks")
            .select("*")
            .eq("is_active", True)
        )
        if limit:
            query = query.limit(limit)
        result = self.db.execute(query, "fetch listening tracks")
        return result.data or []

    def get_track(self, track_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single active track."""
        query = (
            self.db.table("listening_tracks")
            .select("*")
            .eq("id", track_id)
            .eq("is_active", True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch listening track")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Listening questions (from diagnostic_questions)
    # ------------------------------------------------------------------
    def get_listening_questions(
        self,
        track_id: Optional[str] = None,
        question_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch active listening questions, optionally filtered."""
        query = (
            self.db.table("diagnostic_questions")
            .select("*")
            .eq("section", "listening")
            .eq("is_active", True)
        )
        if track_id:
            query = query.eq("track_id", track_id)
        if question_type:
            query = query.eq("question_type", question_type)
        result = self.db.execute(query, "fetch listening questions")
        return result.data or []

    def get_listening_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single listening question by id."""
        query = (
            self.db.table("diagnostic_questions")
            .select("*")
            .eq("id", question_id)
            .eq("section", "listening")
            .eq("is_active", True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch listening question")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Stored results
    # ------------------------------------------------------------------
    def save_result(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert (or upsert) a listening diagnostic result for an attempt."""
        payload = {
            "attempt_id": data.get("attempt_id"),
            "user_id": user_id,
            "total_questions": int(data.get("total_questions") or 0),
            "correct_answers": int(data.get("correct_answers") or 0),
            "accuracy": float(data.get("accuracy") or 0.0),
            "total_time_seconds": int(data.get("total_time_seconds") or 0),
            "listening_band": data.get("listening_band"),
            "difficulty_level": data.get("difficulty_level") or "Easy",
            "type_accuracy": data.get("type_accuracy") or {},
            "type_time": data.get("type_time") or {},
            "weak_types": data.get("weak_types") or [],
            "strong_types": data.get("strong_types") or [],
            "detail": data.get("detail") or [],
            "completed_at": data.get("completed_at"),
        }
        query = self.db.table("listening_diagnostic_results").upsert(
            payload, on_conflict="attempt_id"
        )
        result = self.db.execute(query, "save listening diagnostic result")
        if not result.data:
            raise NotFoundError("Failed to save listening diagnostic result")
        return result.data[0]

    def get_result(self, attempt_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a stored listening result for an attempt (owner-scoped)."""
        query = (
            self.db.table("listening_diagnostic_results")
            .select("*")
            .eq("attempt_id", attempt_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch listening diagnostic result")
        if not result.data:
            return None
        return result.data[0]

    def list_results(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """List a user's stored listening results (most recent first)."""
        query = (
            self.db.table("listening_diagnostic_results")
            .select("*")
            .eq("user_id", user_id)
            .order("completed_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list listening diagnostic results")
        return result.data or []
