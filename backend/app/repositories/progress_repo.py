"""
Repository for the Progress domain entity.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class ProgressRepository(BaseRepository):
    """Data access for the progress table."""

    table_name = "progress"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    def create(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new progress record for a user."""
        payload = dict(data)
        payload["user_id"] = user_id
        query = self._table().insert(payload)
        result = self._execute(query, "create progress record")
        if not result.data:
            raise NotFoundError("Failed to create progress record")
        return result.data[0]

    def list_for_criterion(
        self,
        user_id: str,
        criterion: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List progress records for a user, optionally filtered by criterion."""
        query = self._table().select("*").eq(self.user_id_column, user_id)

        if criterion:
            query = query.eq("criterion", criterion)
        if source_type:
            query = query.eq("source_type", source_type)

        query = query.order("recorded_at", desc=True)

        result = self._execute(query)
        return result.data or []

    def get_timeline(self, user_id: str, criterion: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch progress records ordered chronologically for a band-score timeline.
        """
        query = self._table().select("*").eq(self.user_id_column, user_id)

        if criterion:
            query = query.eq("criterion", criterion)

        query = query.order("recorded_at")

        result = self._execute(query)
        return result.data or []

    def get_latest_per_criterion(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch the most recent progress record for each criterion.

        Returns a dict keyed by criterion name with the latest band score.
        """
        records = self.list_for_criterion(user_id)
        latest: Dict[str, Any] = {}
        for record in records:
            criterion = record.get("criterion")
            if criterion and criterion not in latest:
                latest[criterion] = record
        return latest

    def get_skill_gaps(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Compute current vs target band for each criterion.

        Uses the user's current_band / target_band from the users table
        and the latest progress record per criterion.
        """
        # Fetch user goals.
        user_query = (
            self.db.table("users")
            .select("current_band, target_band")
            .eq("id", user_id)
            .limit(1)
        )
        user_result = self.db.execute(user_query)
        user_row = user_result.data[0] if user_result.data else {}

        target = float(user_row.get("target_band")) if user_row.get("target_band") else None
        current_overall = float(user_row.get("current_band")) if user_row.get("current_band") else None

        latest = self.get_latest_per_criterion(user_id)

        # Criterion display labels.
        labels = {
            "task_response": "Task Response",
            "coherence_cohesion": "Coherence & Cohesion",
            "lexical_resource": "Lexical Resource",
            "grammar": "Grammatical Range & Accuracy",
            "fluency_coherence": "Fluency & Coherence",
            "pronunciation": "Pronunciation",
            "listening": "Listening",
            "reading": "Reading",
            "overall": "Overall",
        }

        gaps: List[Dict[str, Any]] = []
        for criterion, label in labels.items():
            record = latest.get(criterion)
            current = None
            last_date = None
            if record:
                current = float(record.get("band_score"))
                last_date = record.get("recorded_at")

            # For overall, prefer the user profile current_band if no record.
            if criterion == "overall" and current is None:
                current = current_overall

            gap = None
            if current is not None and target is not None:
                gap = round(target - current, 1)

            gaps.append({
                "criterion": criterion,
                "label": label,
                "current": current,
                "target": target,
                "gap": gap,
                "last_assessment_date": last_date,
            })

        return gaps