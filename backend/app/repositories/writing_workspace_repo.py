"""
Repository for the Writing Workspace module.

Provides data access for the `writing_workspace_submissions` table —
the practice-essay storage that sits alongside the diagnostic
`writing_essays` table but is simpler (draft → submitted / locked).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class WritingWorkspaceRepository(BaseRepository):
    """Data access for the Writing Workspace submissions table."""

    table_name = "writing_workspace_submissions"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Submission CRUD
    # ------------------------------------------------------------------
    def create_submission(
        self, user_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Insert a new workspace submission (draft by default)."""
        payload = {
            "user_id": user_id,
            "prompt_id": data["prompt_id"],
            "task_type": data.get("task_type", "task_2"),
            "title": data.get("title", ""),
            "prompt_text": data.get("prompt_text", ""),
            "word_limit": int(data.get("word_limit", 250)),
            "time_limit_seconds": int(data.get("time_limit_seconds", 2400)),
            "essay_text": data.get("essay_text", ""),
            "word_count": int(data.get("word_count", 0)),
            "time_seconds_spent": int(data.get("time_seconds_spent", 0)),
            "status": data.get("status", "draft"),
            "submission_summary": data.get("submission_summary", {}),
        }
        query = self.db.table("writing_workspace_submissions").insert(payload)
        result = self.db.execute(query, "create writing workspace submission")
        if not result.data:
            raise NotFoundError("Failed to create writing submission")
        return result.data[0]

    def get_submission(self, submission_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single submission scoped to the owner."""
        query = (
            self.db.table("writing_workspace_submissions")
            .select("*")
            .eq("id", submission_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch writing workspace submission")
        if not result.data:
            return None
        return result.data[0]

    def update_submission(
        self, submission_id: str, user_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a draft submission. Raises if locked."""
        query = (
            self.db.table("writing_workspace_submissions")
            .update(data)
            .eq("id", submission_id)
            .eq("user_id", user_id)
            .eq("is_locked", False)
        )
        result = self.db.execute(query, "update writing workspace submission")
        if not result.data:
            raise NotFoundError("Submission not found or locked")
        return result.data[0]

    def delete_submission(self, submission_id: str, user_id: str) -> None:
        """Delete a draft submission."""
        query = (
            self.db.table("writing_workspace_submissions")
            .delete()
            .eq("id", submission_id)
            .eq("user_id", user_id)
            .eq("status", "draft")
        )
        self.db.execute(query, "delete writing workspace submission")

    def list_submissions(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List a user's submissions (most recent first)."""
        query = (
            self.db.table("writing_workspace_submissions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list writing workspace submissions")
        return result.data or []

    def list_drafts(self, user_id: str) -> List[Dict[str, Any]]:
        """List the user's in-progress drafts (for resume)."""
        query = (
            self.db.table("writing_workspace_submissions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "draft")
            .order("updated_at", desc=True)
        )
        result = self.db.execute(query, "list writing drafts")
        return result.data or []
