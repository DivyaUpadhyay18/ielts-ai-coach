"""
Repository for the Learning Session Mode.

Provides data access for:
- Session state tracking (create, update, get)
- Session notes (create, update, delete, list)
- Session bookmarks (create, delete, list)
- Previous mistakes from task history
- Related resources from task_resources and resource_catalog
- Session history
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class LearningSessionRepository(BaseRepository):
    """Repository for learning session data access."""

    table_name = "learning_session_state"
    id_column = "id"
    _ownable = False

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ─── Session State ────────────────────────────────────────────

    def create_or_update_session_state(
        self,
        user_id: str,
        mission_id: str,
        session_id: Optional[str] = None,
        status: str = "active",
        progress_percent: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create or update the session state for a mission."""
        existing = self.get_session_state(user_id, mission_id)

        now = datetime.utcnow().isoformat()
        payload = {
            "user_id": user_id,
            "mission_id": mission_id,
            "session_id": session_id,
            "status": status,
            "progress_percent": progress_percent,
            "started_at": now,
            "updated_at": now,
            "metadata": metadata or {},
        }

        if existing:
            update_payload = dict(payload)
            if status == "completed":
                update_payload["completed_at"] = now
            query = (
                self._table()
                .update(update_payload)
                .eq(self.id_column, existing["id"])
            )
            result = self._execute(query, "update session state")
            if result.data:
                return result.data[0]
            return existing

        query = self._table().insert(payload)
        result = self._execute(query, "create session state")
        if result.data:
            return result.data[0]
        raise NotFoundError("Failed to create session state")

    def get_session_state(self, user_id: str, mission_id: str) -> Optional[Dict[str, Any]]:
        """Get the current session state for a mission."""
        query = (
            self._table()
            .select("*")
            .eq("user_id", user_id)
            .eq("mission_id", mission_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        result = self._execute(query, "fetch session state")
        if not result.data:
            return None
        return result.data[0]

    def update_session_state(
        self,
        user_id: str,
        mission_id: str,
        progress_percent: Optional[int] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update session state fields."""
        existing = self.get_session_state(user_id, mission_id)
        if not existing:
            # Create a new state if none exists
            return self.create_or_update_session_state(
                user_id, mission_id, status=status or "active",
                progress_percent=progress_percent or 0, metadata=metadata
            )

        payload: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}
        if progress_percent is not None:
            payload["progress_percent"] = progress_percent
        if status is not None:
            payload["status"] = status
            if status == "completed":
                payload["completed_at"] = datetime.utcnow().isoformat()
        if metadata is not None:
            existing_meta = existing.get("metadata") or {}
            existing_meta.update(metadata)
            payload["metadata"] = existing_meta

        query = self._table().update(payload).eq(self.id_column, existing["id"])
        result = self._execute(query, "update session state")
        if result.data:
            return result.data[0]
        return existing

    # ─── Session Notes ──────────────────────────────────────────────

    def add_note(
        self,
        user_id: str,
        content: str,
        mission_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a note to a learning session."""
        payload = {
            "user_id": user_id,
            "content": content,
            "mission_id": mission_id,
            "resource_id": resource_id,
            "session_id": session_id,
        }
        query = self.db.table("learning_session_notes").insert(payload)
        result = self._execute(query, "add session note")
        if result.data:
            return result.data[0]
        raise NotFoundError("Failed to add session note")

    def update_note(self, note_id: str, user_id: str, content: str) -> Dict[str, Any]:
        """Update a session note."""
        query = (
            self.db.table("learning_session_notes")
            .update({"content": content, "updated_at": datetime.utcnow().isoformat()})
            .eq("id", note_id)
            .eq("user_id", user_id)
        )
        result = self._execute(query, "update session note")
        if not result.data:
            raise NotFoundError("Session note not found")
        return result.data[0]

    def delete_note(self, note_id: str, user_id: str) -> None:
        """Delete a session note."""
        query = (
            self.db.table("learning_session_notes")
            .delete()
            .eq("id", note_id)
            .eq("user_id", user_id)
        )
        result = self._execute(query, "delete session note")
        if not result.data:
            raise NotFoundError("Session note not found")

    def list_notes(
        self, user_id: str, mission_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List notes for a user, optionally filtered by mission."""
        query = (
            self.db.table("learning_session_notes")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if mission_id:
            query = query.eq("mission_id", mission_id)
        result = self._execute(query, "list session notes")
        return result.data or []

    # ─── Session Bookmarks ─────────────────────────────────────────

    def add_bookmark(
        self,
        user_id: str,
        resource_id: str,
        mission_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Bookmark a resource within a learning session."""
        payload = {
            "user_id": user_id,
            "resource_id": resource_id,
            "mission_id": mission_id,
            "session_id": session_id,
        }
        query = self.db.table("learning_session_bookmarks").insert(payload)
        result = self._execute(query, "add session bookmark")
        if result.data:
            return result.data[0]
        raise NotFoundError("Failed to add session bookmark")

    def delete_bookmark(self, user_id: str, resource_id: str) -> None:
        """Delete a session bookmark."""
        query = (
            self.db.table("learning_session_bookmarks")
            .delete()
            .eq("user_id", user_id)
            .eq("resource_id", resource_id)
        )
        result = self._execute(query, "delete session bookmark")
        if not result.data:
            raise NotFoundError("Session bookmark not found")

    def list_bookmarks(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List bookmarks for a user."""
        query = (
            self.db.table("learning_session_bookmarks")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self._execute(query, "list session bookmarks")
        return result.data or []

    def is_bookmarked(self, user_id: str, resource_id: str) -> bool:
        """Check if a resource is bookmarked by the user."""
        query = (
            self.db.table("learning_session_bookmarks")
            .select("id")
            .eq("user_id", user_id)
            .eq("resource_id", resource_id)
            .limit(1)
        )
        result = self._execute(query, "check session bookmark")
        return bool(result.data)

    # ─── Previous Mistakes ─────────────────────────────────────────

    def get_previous_mistakes(
        self, user_id: str, skill: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get previous mistakes from task resource output stored in study_sessions
        or task content_payload meta.
        """
        query = (
            self.db.table("study_sessions")
            .select("source_id, skill, content_payload, meta, created_at")
            .eq("user_id", user_id)
            .in_("session_type", ["task", "mission"])
        )
        if skill:
            query = query.eq("skill", skill)
        query = query.order("created_at", desc=True).limit(limit * 5)

        result = self._execute(query, "fetch previous mistakes")
        mistakes: List[Dict[str, Any]] = []
        for row in result.data or []:
            meta = row.get("meta") or {}
            if not isinstance(meta, dict):
                continue
            mistakes_data = meta.get("mistakes") or meta.get("errors") or []
            if not mistakes_data:
                continue
            for mistake in mistakes_data:
                if isinstance(mistake, dict):
                    mistakes.append({
                        "task_id": row.get("source_id") or row.get("id"),
                        "task_title": meta.get("title", "Previous Task"),
                        "skill": row.get("skill", "general"),
                        "mistake_type": mistake.get("type", mistake.get("error_type", "general")),
                        "description": mistake.get("description", mistake.get("error", "No description")),
                        "created_at": row.get("created_at"),
                    })
            if len(mistakes) >= limit:
                break
        return mistakes[:limit]

    # ─── Related Resources ─────────────────────────────────────────

    def get_related_resources(
        self, resource_id: Optional[str] = None, skill: Optional[str] = None,
        task_type: Optional[str] = None, limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get resources related to a given resource, skill, or task type."""
        query = self._table().select("*")

        if resource_id:
            # Find resources with similar tags or same skill
            resource = self._table().select("skill, tags").eq("id", resource_id).limit(1).execute()
            if resource.data:
                res = resource.data[0]
                skill = res.get("skill")
                tags = res.get("tags") or []
                if tags:
                    query = query.eq("skill", skill)
                else:
                    query = query.eq("skill", skill)

        if skill:
            query = query.eq("skill", skill)

        if task_type:
            # Map task_type to resource type where possible
            type_map = {
                "writing_task1": "PDF",
                "writing_task2": "PDF",
                "speaking_part1": "Video",
                "speaking_part2": "Video",
                "speaking_part3": "Video",
                "vocab_set": "Flashcard",
                "grammar_lesson": "PDF",
                "video": "Video",
                "article": "Website",
            }
            mapped_type = type_map.get(task_type)
            if mapped_type:
                query = query.eq("type", mapped_type)

        query = query.order("popularity_score", desc=True).limit(limit)
        result = self._execute(query, "fetch related resources")
        return result.data or []

    # ─── Session History ───────────────────────────────────────────

    def get_session_history(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get session history for a user."""
        query = (
            self._table()
            .select("*")
            .eq("user_id", user_id)
            .order("started_at", desc=True)
            .limit(limit)
        )
        if offset:
            query = query.offset(offset)
        result = self._execute(query, "fetch session history")
        return result.data or []

    # ─── Today's Missions ──────────────────────────────────────────

    def get_todays_missions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get today's missions for a user."""
        today = date.today().isoformat()
        query = (
            self.db.table("daily_missions")
            .select("*")
            .eq("user_id", user_id)
            .eq("mission_date", today)
            .order("skill")
        )
        result = self._execute(query, "fetch today's missions")
        return result.data or []

    def get_mission_by_id(self, user_id: str, mission_id: str) -> Dict[str, Any]:
        """Get a specific mission by ID, scoped to the user."""
        query = (
            self.db.table("daily_missions")
            .select("*")
            .eq("id", mission_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self._execute(query, "fetch mission by ID")
        if not result.data:
            raise NotFoundError("Mission not found")
        return result.data[0]

    # ─── User Profile ──────────────────────────────────────────────

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile for session context."""
        query = self.db.table("users").select("*").eq("id", user_id).limit(1)
        result = self._execute(query, "fetch user profile for session")
        if not result.data:
            raise NotFoundError("User not found")
        return result.data[0]