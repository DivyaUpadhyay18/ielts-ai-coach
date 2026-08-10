"""
Repository for the Weekly AI Reports.

Stores generated weekly reports in the `weekly_reports` table and maintains
a fast-lookup cache in `weekly_report_cache`. All operations are owner-scoped
(IDOR-safe).
"""
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class WeeklyReportRepository(BaseRepository):
    """Data access for the weekly_reports + weekly_report_cache tables."""

    table_name = "weekly_reports"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def save_report(self, user_id: str, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upsert a weekly report for a user + week_start.
        Uses UNIQUE(user_id, week_start) so re-generations overwrite.
        """
        payload = {
            "user_id": user_id,
            "week_start": report.get("week_start"),
            "week_end": report.get("week_end"),
            "report_json": report,
            "generated_at": report.get("generated_at"),
            "version": int(report.get("version", 1)),
        }
        query = self.db.table("weekly_reports").upsert(
            payload, on_conflict="user_id,week_start"
        )
        result = self.db.execute(query, "save weekly report")
        if not result.data:
            raise NotFoundError("Failed to save weekly report")
        return result.data[0]

    def update_cache(self, user_id: str, report: Dict[str, Any]) -> None:
        """Upsert the latest report into the weekly_report_cache table."""
        if self.db is None:
            return
        try:
            payload = {
                "user_id": user_id,
                "week_start": report.get("week_start"),
                "week_end": report.get("week_end"),
                "report_json": report,
                "generated_at": report.get("generated_at"),
                "latest_report_id": report.get("id"),
            }
            query = self.db.table("weekly_report_cache").upsert(
                payload, on_conflict="user_id"
            )
            self.db.execute(query, "update weekly report cache")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_latest(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the user's most recent weekly report via the cache table."""
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("weekly_report_cache")
                .select("report_json, generated_at, week_start")
                .eq("user_id", user_id)
                .limit(1)
            )
            result = self.db.execute(query, "fetch latest weekly report cache")
            if not result.data:
                return None
            row = result.data[0]
            report = row.get("report_json") or {}
            report["generated_at"] = report.get("generated_at") or row.get("generated_at")
            report["week_start"] = report.get("week_start") or row.get("week_start")
            report["id"] = row.get("latest_report_id")
            return report
        except Exception:
            return None

    def get_by_week(
        self, user_id: str, week_start: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch a specific weekly report by week_start date string."""
        if self.db is None:
            return None
        query = (
            self.db.table("weekly_reports")
            .select("*")
            .eq("user_id", user_id)
            .eq("week_start", week_start)
            .limit(1)
        )
        result = self.db.execute(query, "fetch weekly report by week")
        if not result.data:
            return None
        row = result.data[0]
        report = row.get("report_json") or {}
        report["id"] = row.get("id")
        report["generated_at"] = row.get("generated_at")
        report["version"] = row.get("version")
        return report

    def list_history(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List a user's historical weekly reports (newest first)."""
        if self.db is None:
            return []
        query = (
            self.db.table("weekly_reports")
            .select("id, user_id, week_start, week_end, generated_at, report_json")
            .eq("user_id", user_id)
            .order("week_start", desc=True)
            .limit(limit)
            .offset(offset)
        )
        result = self.db.execute(query, "list weekly report history")
        return result.data or []

    def count_history(self, user_id: str) -> int:
        """Count total weekly reports for a user."""
        if self.db is None:
            return 0
        query = (
            self.db.table("weekly_reports")
            .select("id", count="exact")
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "count weekly reports")
        return result.count or 0
