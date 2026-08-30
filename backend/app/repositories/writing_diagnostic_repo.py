"""
Repository for the Writing Diagnostic Module.

Provides data access for:
  - writing_prompts  (Task 1 & Task 2 prompts — the question bank)
  - writing_essays   (stored per-attempt essays, with auto-save, word count,
                      time, manual IELTS scores, and reserved AI columns)

All operations are owner-scoped where applicable to prevent cross-user access.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class WritingDiagnosticRepository(BaseRepository):
    """Data access for the writing diagnostic tables."""

    table_name = "writing_essays"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------
    def get_prompts(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all active writing prompts, optionally filtered by task type."""
        query = (
            self.db.table("writing_prompts")
            .select("*")
            .eq("is_active", True)
        )
        if task_type:
            query = query.eq("task_type", task_type)
        result = self.db.execute(query, "fetch writing prompts")
        return result.data or []

    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single active writing prompt by id."""
        query = (
            self.db.table("writing_prompts")
            .select("*")
            .eq("id", prompt_id)
            .eq("is_active", True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch writing prompt")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Essays
    # ------------------------------------------------------------------
    def create_essay(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new writing essay for a user."""
        payload = {
            "attempt_id": data.get("attempt_id"),
            "user_id": user_id,
            "prompt_id": data.get("prompt_id"),
            "task_type": data.get("task_type") or "task_2",
            "title": data.get("title") or "",
            "essay_text": data.get("essay_text") or "",
            "word_count": int(data.get("word_count") or 0),
            "time_seconds_spent": int(data.get("time_seconds_spent") or 0),
            "status": data.get("status") or "in_progress",
        }
        query = self.db.table("writing_essays").insert(payload)
        result = self.db.execute(query, "create writing essay")
        if not result.data:
            raise NotFoundError("Failed to create writing essay")
        return result.data[0]

    def get_essay(self, essay_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single essay scoped to the owner."""
        query = (
            self.db.table("writing_essays")
            .select("*")
            .eq("id", essay_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch writing essay")
        if not result.data:
            return None
        return result.data[0]

    def get_essay_by_attempt(
        self, attempt_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch the essay for an attempt (owner-scoped)."""
        query = (
            self.db.table("writing_essays")
            .select("*")
            .eq("attempt_id", attempt_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch writing essay by attempt")
        if not result.data:
            return None
        return result.data[0]

    def update_essay(
        self, essay_id: str, user_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an essay scoped to the owner."""
        return self.update(essay_id, data, user_id)

    def list_essays(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """List a user's stored essays (most recent first)."""
        query = (
            self.db.table("writing_essays")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list writing essays")
        return result.data or []
