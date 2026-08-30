"""
Repository for the Reading Diagnostic Module.

Provides data access for:
  - reading_passages            (authentic IELTS-style passages)
  - diagnostic_questions        (reading questions, filtered by passage/type)
  - reading_diagnostic_results  (stored per-attempt reading outcomes)

All operations are owner-scoped where applicable to prevent cross-user access.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class ReadingDiagnosticRepository(BaseRepository):
    """Data access for the reading diagnostic tables."""

    table_name = "reading_diagnostic_results"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Passages
    # ------------------------------------------------------------------
    def get_passages(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all active reading passages."""
        query = (
            self.db.table("reading_passages")
            .select("*")
            .eq("is_active", True)
        )
        if limit:
            query = query.limit(limit)
        result = self.db.execute(query, "fetch reading passages")
        return result.data or []

    def get_passage(self, passage_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single active passage."""
        query = (
            self.db.table("reading_passages")
            .select("*")
            .eq("id", passage_id)
            .eq("is_active", True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch reading passage")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Reading questions (from diagnostic_questions)
    # ------------------------------------------------------------------
    def get_reading_questions(
        self,
        passage_id: Optional[str] = None,
        question_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch active reading questions, optionally filtered."""
        query = (
            self.db.table("diagnostic_questions")
            .select("*")
            .eq("section", "reading")
            .eq("is_active", True)
        )
        if passage_id:
            query = query.eq("passage_id", passage_id)
        if question_type:
            query = query.eq("question_type", question_type)
        result = self.db.execute(query, "fetch reading questions")
        return result.data or []

    def get_reading_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single reading question by id."""
        query = (
            self.db.table("diagnostic_questions")
            .select("*")
            .eq("id", question_id)
            .eq("section", "reading")
            .eq("is_active", True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch reading question")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Stored results
    # ------------------------------------------------------------------
    def save_result(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert (or upsert) a reading diagnostic result for an attempt."""
        payload = {
            "attempt_id": data.get("attempt_id"),
            "user_id": user_id,
            "total_questions": int(data.get("total_questions") or 0),
            "correct_answers": int(data.get("correct_answers") or 0),
            "accuracy": float(data.get("accuracy") or 0.0),
            "total_time_seconds": int(data.get("total_time_seconds") or 0),
            "reading_band": data.get("reading_band"),
            "difficulty_level": data.get("difficulty_level") or "Easy",
            "type_accuracy": data.get("type_accuracy") or {},
            "type_time": data.get("type_time") or {},
            "weak_types": data.get("weak_types") or [],
            "strong_types": data.get("strong_types") or [],
            "detail": data.get("detail") or [],
            "completed_at": data.get("completed_at"),
        }
        query = self.db.table("reading_diagnostic_results").upsert(
            payload, on_conflict="attempt_id"
        )
        result = self.db.execute(query, "save reading diagnostic result")
        if not result.data:
            raise NotFoundError("Failed to save reading diagnostic result")
        return result.data[0]

    def get_result(self, attempt_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a stored reading result for an attempt (owner-scoped)."""
        query = (
            self.db.table("reading_diagnostic_results")
            .select("*")
            .eq("attempt_id", attempt_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch reading diagnostic result")
        if not result.data:
            return None
        return result.data[0]

    def list_results(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """List a user's stored reading results (most recent first)."""
        query = (
            self.db.table("reading_diagnostic_results")
            .select("*")
            .eq("user_id", user_id)
            .order("completed_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list reading diagnostic results")
        return result.data or []
