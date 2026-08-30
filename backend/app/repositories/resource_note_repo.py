"""
Repository for Resource Notes, Highlights, and Revision Reminders.
"""
from datetime import date
from typing import List, Optional

from app.db.session import get_supabase


class ResourceNoteRepo:
    """Repository for resource notes, highlights, and revision reminders."""

    # ─── Notes ─────────────────────────────────────────────────────────────

    @staticmethod
    def create_note(user_id: str, resource_id: str, content: str, color: str = "yellow", is_highlighted: bool = False) -> dict:
        """Create a new note for a resource."""
        supabase = get_supabase()
        data = {
            "user_id": user_id,
            "resource_id": resource_id,
            "content": content,
            "color": color,
            "is_highlighted": is_highlighted,
        }
        result = supabase.table("resource_notes").insert(data).execute()
        return result.data[0] if result.data else {}

    @staticmethod
    def list_notes(user_id: str, resource_id: Optional[str] = None, search: Optional[str] = None) -> List[dict]:
        """List notes for a user, optionally filtered by resource and search."""
        supabase = get_supabase()
        query = supabase.table("resource_notes").select("*").eq("user_id", user_id).order("created_at", desc=True)

        if resource_id:
            query = query.eq("resource_id", resource_id)

        result = query.execute()

        notes = result.data or []

        # Client-side search filter
        if search:
            search_lower = search.lower()
            notes = [n for n in notes if search_lower in (n.get("content") or "").lower()]

        return notes

    @staticmethod
    def get_note(user_id: str, note_id: str) -> Optional[dict]:
        """Get a single note by ID."""
        supabase = get_supabase()
        result = supabase.table("resource_notes").select("*").eq("id", note_id).eq("user_id", user_id).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def update_note(user_id: str, note_id: str, data: dict) -> Optional[dict]:
        """Update a note."""
        supabase = get_supabase()
        data["updated_at"] = "NOW()"
        result = supabase.table("resource_notes").update(data).eq("id", note_id).eq("user_id", user_id).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def delete_note(user_id: str, note_id: str) -> bool:
        """Delete a note."""
        supabase = get_supabase()
        result = supabase.table("resource_notes").delete().eq("id", note_id).eq("user_id", user_id).execute()
        return len(result.data or []) > 0

    @staticmethod
    def get_note_count(user_id: str) -> int:
        """Get the total count of notes for a user."""
        supabase = get_supabase()
        result = supabase.table("resource_notes").select("id").eq("user_id", user_id).execute()
        return len(result.data or [])

    # ─── Highlights ─────────────────────────────────────────────────────────

    @staticmethod
    def create_highlight(user_id: str, resource_id: str, selected_text: str, color: str = "yellow", note: Optional[str] = None) -> dict:
        """Create a new highlight for a resource."""
        supabase = get_supabase()
        data = {
            "user_id": user_id,
            "resource_id": resource_id,
            "selected_text": selected_text,
            "color": color,
        }
        if note:
            data["note"] = note

        result = supabase.table("resource_highlights").insert(data).execute()
        return result.data[0] if result.data else {}

    @staticmethod
    def list_highlights(user_id: str, resource_id: Optional[str] = None) -> List[dict]:
        """List highlights for a user, optionally filtered by resource."""
        supabase = get_supabase()
        query = supabase.table("resource_highlights").select("*").eq("user_id", user_id).order("created_at", desc=True)

        if resource_id:
            query = query.eq("resource_id", resource_id)

        result = query.execute()
        return result.data or []

    @staticmethod
    def delete_highlight(user_id: str, highlight_id: str) -> bool:
        """Delete a highlight."""
        supabase = get_supabase()
        result = supabase.table("resource_highlights").delete().eq("id", highlight_id).eq("user_id", user_id).execute()
        return len(result.data or []) > 0

    @staticmethod
    def get_highlight_count(user_id: str) -> int:
        """Get the total count of highlights for a user."""
        supabase = get_supabase()
        result = supabase.table("resource_highlights").select("id").eq("user_id", user_id).execute()
        return len(result.data or [])

    # ─── Revision Reminders ─────────────────────────────────────────────────

    @staticmethod
    def create_reminder(
        user_id: str,
        resource_id: str,
        reminder_date: date,
        title: str,
        note_id: Optional[str] = None,
        reminder_time: Optional[str] = None,
    ) -> dict:
        """Create a new revision reminder."""
        supabase = get_supabase()
        data = {
            "user_id": user_id,
            "resource_id": resource_id,
            "reminder_date": reminder_date.isoformat(),
            "title": title,
        }
        if note_id:
            data["note_id"] = note_id
        if reminder_time:
            data["reminder_time"] = reminder_time

        result = supabase.table("revision_reminders").insert(data).execute()
        return result.data[0] if result.data else {}

    @staticmethod
    def list_reminders(user_id: str, upcoming_only: bool = False) -> List[dict]:
        """List revision reminders for a user."""
        supabase = get_supabase()
        query = supabase.table("revision_reminders").select("*").eq("user_id", user_id).order("reminder_date")

        if upcoming_only:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            query = query.gte("reminder_date", today)

        result = query.execute()
        return result.data or []

    @staticmethod
    def update_reminder(user_id: str, reminder_id: str, data: dict) -> Optional[dict]:
        """Update a revision reminder."""
        supabase = get_supabase()
        result = supabase.table("revision_reminders").update(data).eq("id", reminder_id).eq("user_id", user_id).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def delete_reminder(user_id: str, reminder_id: str) -> bool:
        """Delete a revision reminder."""
        supabase = get_supabase()
        result = supabase.table("revision_reminders").delete().eq("id", reminder_id).eq("user_id", user_id).execute()
        return len(result.data or []) > 0

    @staticmethod
    def get_reminder_count(user_id: str) -> int:
        """Get the total count of reminders for a user."""
        supabase = get_supabase()
        result = supabase.table("revision_reminders").select("id").eq("user_id", user_id).execute()
        return len(result.data or [])