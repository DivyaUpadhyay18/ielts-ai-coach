"""
Repository for the AI Mentor domain.

Persists coaching conversations (`mentor_conversations`) and the user/mentor
messages inside them (`mentor_messages`). Every access is owner-scoped to
prevent cross-user reads/writes (IDOR). The repository is intentionally thin:
all coaching analysis lives in the AI Mentor service.
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class MentorRepository(BaseRepository):
    """Data access for mentor_conversations + mentor_messages."""

    table_name = "mentor_conversations"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------
    def create_conversation(
        self,
        user_id: str,
        mode: str,
        title: str,
        context_snapshot: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Open a new coaching conversation with a context snapshot."""
        payload = {
            "user_id": user_id,
            "mode": mode,
            "title": title[:120],
            "status": "active",
            "context_snapshot": context_snapshot or {},
            "meta": meta or {},
        }
        query = self._table().insert(payload)
        result = self._execute(query, "create mentor conversation")
        if not result.data:
            raise ConflictError("Failed to create mentor conversation")
        return result.data[0]

    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a conversation owner-scoped (None if not found)."""
        query = (
            self._table()
            .select("*")
            .eq(self.id_column, conversation_id)
            .eq(self.user_id_column, user_id)
            .limit(1)
        )
        result = self._execute(query, "get mentor conversation")
        if not result.data:
            return None
        return result.data[0]

    def count_conversations(self, user_id: str, mode: Optional[str] = None) -> int:
        """Count the user's conversations (optionally per mode)."""
        query = self._table().select("*", count="exact").eq(self.user_id_column, user_id)
        if mode:
            query = query.eq("mode", mode)
        result = self._execute(query, "count mentor conversations")
        return result.count or 0

    def archive_conversation(self, conversation_id: str, user_id: str) -> None:
        """Archive a conversation owner-scoped (soft delete)."""
        query = (
            self._table()
            .update({"status": "archived"})
            .eq(self.id_column, conversation_id)
            .eq(self.user_id_column, user_id)
        )
        result = self._execute(query, "archive mentor conversation")
        if not result.data:
            raise NotFoundError("Mentor conversation not found")

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------
    def add_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        structured: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append a message to a conversation (owner-scoped insert)."""
        payload = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "structured": structured or {},
        }
        query = self.db.table("mentor_messages").insert(payload)
        result = self._execute(query, "add mentor message")
        if not result.data:
            raise ConflictError("Failed to add mentor message")
        return result.data[0]

    def list_messages(self, conversation_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Fetch all messages in a conversation (owner-scoped), oldest first."""
        query = (
            self.db.table("mentor_messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .eq(self.user_id_column, user_id)
            .order("created_at")
        )
        result = self._execute(query, "list mentor messages")
        return result.data or []

    def count_messages(self, conversation_id: str) -> int:
        """Count messages inside a conversation."""
        query = (
            self.db.table("mentor_messages")
            .select("*", count="exact")
            .eq("conversation_id", conversation_id)
        )
        result = self._execute(query, "count mentor messages")
        return result.count or 0

    def get_last_message_at(self, conversation_id: str) -> Optional[str]:
        """Return the newest message's created_at for a conversation."""
        query = (
            self.db.table("mentor_messages")
            .select("created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        result = self._execute(query, "get last mentor message time")
        if not result.data:
            return None
        return result.data[0].get("created_at")

    def list_conversations(
        self,
        user_id: str,
        mode: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List the user's conversations, newest first (optionally by mode)."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
        )
        if mode:
            query = query.eq("mode", mode)
        query = query.order("created_at", desc=True).limit(limit).offset(offset)
        result = self._execute(query, "list mentor conversations")
        return result.data or []