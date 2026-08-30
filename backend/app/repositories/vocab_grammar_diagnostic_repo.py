"""
Repository for the Vocabulary & Grammar Diagnostic Module.

Provides data access for:
  - diagnostic_questions (vocabulary/grammar questions, filtered by section/type)
  - vocab_grammar_diagnostic_results (stored per-attempt vocabulary & grammar
    outcomes)

All operations are owner-scoped where applicable to prevent cross-user access.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class VocabGrammarDiagnosticRepository(BaseRepository):
    """Data access for the vocabulary & grammar diagnostic tables."""

    table_name = "vocab_grammar_diagnostic_results"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Questions (from diagnostic_questions)
    # ------------------------------------------------------------------
    def get_questions(
        self,
        section: Optional[str] = None,
        question_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch active vocabulary/grammar questions, optionally filtered by
        section and/or question_type.
        """
        query = (
            self.db.table("diagnostic_questions")
            .select("*")
            .in_("section", ["vocabulary", "grammar"])
            .eq("is_active", True)
        )
        if section in ("vocabulary", "grammar"):
            query = query.eq("section", section)
        if question_type:
            query = query.eq("question_type", question_type)
        result = self.db.execute(query, "fetch vocabulary/grammar questions")
        return result.data or []

    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single vocabulary/grammar question by id."""
        query = (
            self.db.table("diagnostic_questions")
            .select("*")
            .eq("id", question_id)
            .in_("section", ["vocabulary", "grammar"])
            .eq("is_active", True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch vocabulary/grammar question")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Stored results
    # ------------------------------------------------------------------
    def save_result(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert (or upsert) a vocabulary & grammar result for an attempt."""
        payload = {
            "attempt_id": data.get("attempt_id"),
            "user_id": user_id,
            "total_questions": int(data.get("total_questions") or 0),
            "correct_answers": int(data.get("correct_answers") or 0),
            "accuracy": float(data.get("accuracy") or 0.0),
            "total_time_seconds": int(data.get("total_time_seconds") or 0),
            "band": data.get("band"),
            "difficulty_level": data.get("difficulty_level") or "Easy",
            "grammar_accuracy": float(data.get("grammar_accuracy") or 0.0),
            "vocabulary_accuracy": float(data.get("vocabulary_accuracy") or 0.0),
            "type_accuracy": data.get("type_accuracy") or {},
            "type_time": data.get("type_time") or {},
            "weak_grammar_topics": data.get("weak_grammar_topics") or [],
            "weak_vocab_categories": data.get("weak_vocab_categories") or [],
            "strong_types": data.get("strong_types") or [],
            "detail": data.get("detail") or [],
            "completed_at": data.get("completed_at"),
        }
        query = self.db.table("vocab_grammar_diagnostic_results").upsert(
            payload, on_conflict="attempt_id"
        )
        result = self.db.execute(query, "save vocabulary/grammar diagnostic result")
        if not result.data:
            raise NotFoundError("Failed to save vocabulary/grammar diagnostic result")
        return result.data[0]

    def get_result(self, attempt_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a stored result for an attempt (owner-scoped)."""
        query = (
            self.db.table("vocab_grammar_diagnostic_results")
            .select("*")
            .eq("attempt_id", attempt_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch vocabulary/grammar diagnostic result")
        if not result.data:
            return None
        return result.data[0]

    def list_results(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """List a user's stored results (most recent first)."""
        query = (
            self.db.table("vocab_grammar_diagnostic_results")
            .select("*")
            .eq("user_id", user_id)
            .order("completed_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list vocabulary/grammar diagnostic results")
        return result.data or []
