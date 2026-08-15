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

    # ------------------------------------------------------------------
    # Evaluation records
    #
    # A pending evaluation record is created at submit time so every
    # submitted essay owns an evaluation slot.  AI scoring is intentionally
    # NOT implemented yet — the record stays 'pending' until a future phase
    # fills it in.
    # ------------------------------------------------------------------
    def create_evaluation(
        self,
        user_id: str,
        submission_id: str,
        task_type: str,
        word_count: int = 0,
        attempt_number: int = 1,
    ) -> Dict[str, Any]:
        """Create a pending evaluation record for a submitted essay."""
        payload = {
            "user_id": user_id,
            "submission_id": submission_id,
            "task_type": task_type or "task_2",
            "attempt_number": attempt_number,
            "status": "pending",
            "overall_band": None,
            "confidence": None,
            "criteria_bands": {},
            "criteria_detail": {},
            "strengths": [],
            "weaknesses": [],
            "errors": [],
            "suggestions": [],
            "error_analysis": [],
            "word_count": int(word_count or 0),
            "is_estimate": True,
            "source": "pending",
        }
        query = self.db.table("writing_evaluations").insert(payload)
        result = self.db.execute(query, "create writing evaluation record")
        if not result.data:
            raise NotFoundError("Failed to create writing evaluation record")
        return result.data[0]

    def get_evaluation(
        self, submission_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch the evaluation record for a submission (owner-scoped)."""
        query = (
            self.db.table("writing_evaluations")
            .select("*")
            .eq("submission_id", submission_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch writing evaluation record")
        if not result.data:
            return None
        return result.data[0]

    def list_evaluations(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List a user's evaluation records (most recent first)."""
        query = (
            self.db.table("writing_evaluations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list writing evaluation records")
        return result.data or []

    def update_evaluation(
        self,
        evaluation_id: str,
        user_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an evaluation record (owner-scoped)."""
        query = (
            self.db.table("writing_evaluations")
            .update(data)
            .eq("id", evaluation_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "update writing evaluation record")
        if not result.data:
            raise NotFoundError("Writing evaluation record not found")
        return result.data[0]

    # ------------------------------------------------------------------
    # Improvement plans
    # ------------------------------------------------------------------
    def create_improvement_plan(
        self, user_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Insert a new improvement plan (owner-scoped)."""
        payload = {
            "user_id": user_id,
            "evaluation_id": data["evaluation_id"],
            "submission_id": data["submission_id"],
            "task_type": data.get("task_type", "task_2"),
            "current_band": float(data.get("current_band", 0.0)),
            "target_band": float(data.get("target_band", 0.0)),
            "band_gap": float(data.get("band_gap", 0.0)),
            "weaknesses": data.get("weaknesses", []),
            "current_level_description": data.get("current_level_description", ""),
            "target_level_description": data.get("target_level_description", ""),
            "specific_changes": data.get("specific_changes", []),
            "practice_exercises": data.get("practice_exercises", []),
            "recommended_resources": data.get("recommended_resources", []),
            "suggested_mission": data.get("suggested_mission", {}),
            "plan_json": data.get("plan_json", {}),
            "is_estimate": data.get("is_estimate", True),
            "source": data.get("source", "ai"),
        }
        query = self.db.table("writing_improvement_plans").insert(payload)
        result = self.db.execute(query, "create writing improvement plan")
        if not result.data:
            raise NotFoundError("Failed to create writing improvement plan")
        return result.data[0]

    def get_improvement_plan(
        self, evaluation_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch the improvement plan for an evaluation (owner-scoped)."""
        query = (
            self.db.table("writing_improvement_plans")
            .select("*")
            .eq("evaluation_id", evaluation_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch writing improvement plan")
        if not result.data:
            return None
        return result.data[0]

    def list_improvement_plans(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List a user's improvement plans (most recent first)."""
        query = (
            self.db.table("writing_improvement_plans")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list writing improvement plans")
        return result.data or []
