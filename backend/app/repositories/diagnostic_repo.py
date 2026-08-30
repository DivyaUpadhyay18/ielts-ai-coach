"""
Repository for the Diagnostic Test Framework.

Provides data access for:
  - diagnostic_questions (the shared question bank)
  - diagnostic_attempts (resumable assessment sessions)
  - diagnostic_responses (per-question answers + timing)

All operations are owner-scoped to prevent cross-user access (IDOR).
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class DiagnosticRepository(BaseRepository):
    """Data access for the diagnostic tables."""

    table_name = "diagnostic_attempts"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Question bank
    # ------------------------------------------------------------------
    def get_questions(self, section: str) -> List[Dict[str, Any]]:
        """Fetch all active questions for a section (unordered)."""
        query = (
            self.db.table("diagnostic_questions")
            .select("*")
            .eq("section", section)
            .eq("is_active", True)
        )
        result = self.db.execute(query, "fetch diagnostic questions")
        return result.data or []

    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single question by id (or None if missing/inactive)."""
        query = (
            self.db.table("diagnostic_questions")
            .select("*")
            .eq("id", question_id)
            .eq("is_active", True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch diagnostic question")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Attempts
    # ------------------------------------------------------------------
    def create_attempt(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new diagnostic attempt for a user."""
        payload = {
            "user_id": user_id,
            "status": "in_progress",
            "current_section": "reading",
            "sections_completed": [],
            "section_seconds": {},
            "total_seconds_spent": 0,
        }
        payload.update(data or {})
        query = self.db.table("diagnostic_attempts").insert(payload)
        result = self.db.execute(query, "create diagnostic attempt")
        if not result.data:
            raise NotFoundError("Failed to create diagnostic attempt")
        return result.data[0]

    def get_attempt(self, attempt_id: str, user_id: str) -> Dict[str, Any]:
        """Fetch an attempt scoped to the owner."""
        return self.get_by_id(attempt_id, user_id)

    def get_active_attempt(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return the most recent in-progress attempt for a user."""
        query = (
            self.db.table("diagnostic_attempts")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "in_progress")
            .order("created_at", desc=True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch active diagnostic attempt")
        if not result.data:
            return None
        return result.data[0]

    def get_latest_completed(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return the most recent completed diagnostic attempt for a user.

        This is the source of truth for the diagnostic-derived learning
        profile (overall band, per-skill bands, strengths/weaknesses).
        """
        query = (
            self.db.table("diagnostic_attempts")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch latest completed diagnostic attempt")
        if not result.data:
            return None
        return result.data[0]

    def update_attempt(
        self, attempt_id: str, user_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update attempt scoped to the owner."""
        return self.update(attempt_id, data, user_id)

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------
    def save_response(
        self, user_id: str, attempt_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Insert (or upsert) a response for a question within an attempt.

        Because the table has UNIQUE (attempt_id, question_id), we upsert
        on that conflict so re-answering a question updates the row.
        """
        payload = {
            "attempt_id": attempt_id,
            "user_id": user_id,
            "section": data.get("section"),
            "question_id": data.get("question_id"),
            "answer_json": data.get("answer_json") or {},
            "is_correct": data.get("is_correct"),
            "score": data.get("score"),
            "time_taken_seconds": int(data.get("time_taken_seconds") or 0),
        }
        query = self.db.table("diagnostic_responses").upsert(
            payload, on_conflict="attempt_id,question_id"
        )
        result = self.db.execute(query, "save diagnostic response")
        if not result.data:
            raise NotFoundError("Failed to save diagnostic response")
        return result.data[0]

    def list_responses(
        self, attempt_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch all responses for an attempt (owner-scoped)."""
        query = (
            self.db.table("diagnostic_responses")
            .select("*")
            .eq("attempt_id", attempt_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "list diagnostic responses")
        return result.data or []

    def get_answered_question_ids(
        self, attempt_id: str, user_id: str
    ) -> List[str]:
        """Return the question_ids already answered for an attempt."""
        responses = self.list_responses(attempt_id, user_id)
        return [r.get("question_id") for r in responses if r.get("question_id")]

    def get_responses_by_section(
        self, attempt_id: str, user_id: str, section: str
    ) -> List[Dict[str, Any]]:
        """Fetch responses belonging to a specific section."""
        responses = self.list_responses(attempt_id, user_id)
        return [r for r in responses if r.get("section") == section]
