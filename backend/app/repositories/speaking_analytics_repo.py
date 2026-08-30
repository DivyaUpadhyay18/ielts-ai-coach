"""
Repository for the Speaking Progress Analytics module.

Reads from:
  - speaking_evaluations        (AI evaluation results with criteria JSONB)
  - speaking_practice_sessions  (practice sessions with evaluated bands)
  - speaking_test_responses     (test responses with transcript + duration)
  - speaking_error_analysis     (per-response error issues)

All reads are owner-scoped (no cross-user leakage) and return plain dicts
so the service layer can compute analytics metrics deterministically.
"""
from typing import Any, Dict, List, Optional

from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class SpeakingAnalyticsRepository(BaseRepository):
    """Data access for speaking analytics (read-only)."""

    table_name = "speaking_evaluations"
    user_id_column = "user_id"
    _ownable = False

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Speaking Evaluations (AI-evaluated transcripts)
    # ------------------------------------------------------------------
    def list_evaluations(
        self,
        user_id: str,
        part: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
        days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return AI-evaluated speaking transcripts for a user, newest first.

        Includes overall_band, criteria JSONB, confidence, part, strengths,
        weaknesses, and the associated transcript + prompt title.
        """
        query = (
            self.db.table("speaking_evaluations")
            .select("*, speaking_test_responses(title, prompt_text, duration_seconds)")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .not_.is_("overall_band", None)
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if part:
            query = query.eq("part", part)
        if days:
            from datetime import datetime, timedelta, timezone
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query = query.gte("created_at", cutoff)

        result = self.db.execute(query, "list speaking evaluations")
        return result.data or []

    # ------------------------------------------------------------------
    # Practice Sessions (evalulated practice responses)
    # ------------------------------------------------------------------
    def list_practice_sessions(
        self,
        user_id: str,
        practice_mode: Optional[str] = None,
        limit: int = 500,
        days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return evaluated speaking practice sessions for a user."""
        query = (
            self.db.table("speaking_practice_sessions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "evaluated")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if practice_mode:
            query = query.eq("practice_mode", practice_mode)
        if days:
            from datetime import datetime, timedelta, timezone
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query = query.gte("created_at", cutoff)

        result = self.db.execute(query, "list speaking practice sessions")
        return result.data or []

    # ------------------------------------------------------------------
    # Error Analysis (aggregated error issues)
    # ------------------------------------------------------------------
    def list_error_analysis(
        self,
        user_id: str,
        limit: int = 500,
        days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return speaking error analysis records for a user."""
        query = (
            self.db.table("speaking_error_analysis")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if days:
            from datetime import datetime, timedelta, timezone
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query = query.gte("created_at", cutoff)

        result = self.db.execute(query, "list speaking error analysis")
        return result.data or []

    # ------------------------------------------------------------------
    # Test Responses (for duration + filler data)
    # ------------------------------------------------------------------
    def list_test_responses(
        self,
        user_id: str,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Return speaking test responses with transcripts for filler counting."""
        query = (
            self.db.table("speaking_test_responses")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_saved", True)
            .not_.is_("transcript", None)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list speaking test responses")
        return result.data or []
