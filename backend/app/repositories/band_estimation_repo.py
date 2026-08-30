"""
Repository for the Band Estimation Engine.

Provides data access for the `band_estimations` table which stores the
stored results requirement — one snapshot per user per day.

All operations are owner-scoped to prevent cross-user access (IDOR).
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class BandEstimationRepository(BaseRepository):
    """Data access for the band_estimations table."""

    table_name = "band_estimations"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def save_result(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upsert a band estimation snapshot for a user on a given date.

        Uses UNIQUE(user_id, run_date) so re-runs on the same day overwrite.
        """
        payload = {
            "user_id": user_id,
            "run_date": data.get("run_date"),
            "overall_band": float(data.get("overall_band") or 0.0),
            "confidence_score": float(data.get("confidence_score") or 0.0),
            "confidence_label": data.get("confidence_label") or "medium",
            "skill_bands": data.get("skill_bands") or {},
            "weakest_skills": data.get("weakest_skills") or [],
            "strongest_skills": data.get("strongest_skills") or [],
            "explanations": data.get("explanations") or {},
            "formulas_json": data.get("formulas") or {},
            "raw_input": data.get("raw_input") or {},
        }
        query = self.db.table("band_estimations").upsert(
            payload, on_conflict="user_id,run_date"
        )
        result = self.db.execute(query, "save band estimation")
        if not result.data:
            raise NotFoundError("Failed to save band estimation")
        return result.data[0]

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_latest(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the user's most recent band estimation snapshot."""
        query = (
            self.db.table("band_estimations")
            .select("*")
            .eq("user_id", user_id)
            .order("run_date", desc=True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch latest band estimation")
        if not result.data:
            return None
        return result.data[0]

    def list_results(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List a user's stored band estimations (most recent first)."""
        query = (
            self.db.table("band_estimations")
            .select("*")
            .eq("user_id", user_id)
            .order("run_date", desc=True)
            .limit(limit)
            .offset(offset)
        )
        result = self.db.execute(query, "list band estimations")
        return result.data or []

    def count_results(self, user_id: str) -> int:
        """Count a user's stored band estimations."""
        query = (
            self.db.table("band_estimations")
            .select("id", count="exact")
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "count band estimations")
        return result.count or 0
