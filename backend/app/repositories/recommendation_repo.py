"""
Repository for the Recommendation Engine domain.

Provides data-access for:
- Recommendation logs
- User completed resources
- User skill performance
- User mock scores
- Today's missions
- User profiles
"""
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class RecommendationRepository(BaseRepository):
    """Data access for recommendation engine."""

    table_name = "recommendation_logs"
    _ownable = True  # user-owned

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Recommendation logs
    # ------------------------------------------------------------------
    def log_recommendation(
        self,
        user_id: str,
        current_band: Optional[float],
        target_band: Optional[float],
        weakest_skill: Optional[str],
        today_mission_skill: Optional[str],
        sub_skill: Optional[str],
        estimated_time: Optional[int],
        remaining_days: Optional[int],
        resource_count: int,
        top_resource_id: Optional[str],
        top_score: Optional[float],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Log a recommendation run."""
        payload = {
            "user_id": user_id,
            "current_band": current_band,
            "target_band": target_band,
            "weakest_skill": weakest_skill,
            "today_mission_skill": today_mission_skill,
            "sub_skill": sub_skill,
            "estimated_time": estimated_time,
            "remaining_days": remaining_days,
            "resource_count": resource_count,
            "top_resource_id": top_resource_id,
            "top_score": top_score,
            "metadata": metadata,
        }
        query = self._table().insert(payload)
        result = self._execute(query, "log recommendation")
        if not result.data:
            raise NotFoundError("Failed to log recommendation")
        return result.data[0]

    def get_recommendation_logs(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get recommendation history for a user."""
        query = (
            self._table()
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        result = self._execute(query, "get recommendation logs")
        return result.data or []

    # ------------------------------------------------------------------
    # User context
    # ------------------------------------------------------------------
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile for recommendation context."""
        query = (
            self.db.table("users")
            .select("current_band, target_band, exam_date, daily_minutes_budget, weakest_skill, strongest_skill")
            .eq("id", user_id)
            .single()
        )
        result = self._execute(query, "get user profile")
        if not result.data:
            return None
        return dict(result.data)

    def get_today_missions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get today's missions for a user."""
        from datetime import date
        today = date.today().isoformat()
        query = (
            self.db.table("daily_missions")
            .select("*")
            .eq("user_id", user_id)
            .eq("mission_date", today)
            .eq("status", "active")
            .order("created_at", desc=False)
        )
        result = self._execute(query, "get today's missions")
        return result.data or []

    def get_skill_performance(self, user_id: str) -> Dict[str, Dict[str, float]]:
        """Get skill performance history."""
        query = (
            self.db.table("progress_tracking")
            .select("skill, criterion, band_score")
            .eq("user_id", user_id)
            .order("recorded_at", desc=True)
        )
        result = self._execute(query, "get skill performance")
        
        skill_perf: Dict[str, Dict[str, float]] = {}
        for row in (result.data or []):
            skill = row.get("skill", "general")
            criterion = row.get("criterion", "overall")
            band_score = float(row.get("band_score") or 0.0)
            
            if skill not in skill_perf:
                skill_perf[skill] = {}
            skill_perf[skill][criterion] = band_score
        
        return skill_perf

    def get_mock_scores(self, user_id: str) -> List[float]:
        """Get mock test scores."""
        query = (
            self.db.table("mock_tests")
            .select("overall_band")
            .eq("user_id", user_id)
            .order("test_date", desc=True)
            .limit(10)
        )
        result = self._execute(query, "get mock scores")
        return [float(row.get("overall_band") or 0.0) for row in (result.data or [])]

    def get_completed_resource_ids(self, user_id: str) -> set:
        """Get set of completed resource IDs for a user."""
        query = (
            self.db.table("user_resource_completions")
            .select("resource_id")
            .eq("user_id", user_id)
        )
        result = self._execute(query, "get completed resources")
        return {row.get("resource_id") for row in (result.data or []) if row.get("resource_id")}

    # ------------------------------------------------------------------
    # Catalog queries
    # ------------------------------------------------------------------
    def get_catalog_resources(
        self,
        skill: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 50,
        verified: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get resources from catalog for recommendations."""
        query = self.db.table("resources").select("*")
        
        if skill:
            query = query.eq("skill", skill)
        if resource_type:
            query = query.eq("type", resource_type)
        if verified is not None:
            query = query.eq("verified", verified)
        
        query = query.eq("is_published", True).order("popularity_score", desc=True).limit(limit)
        result = self._execute(query, "get catalog resources")
        return result.data or []

    # ------------------------------------------------------------------
    # Interaction tracking
    # ------------------------------------------------------------------
    def track_resource_view(
        self,
        user_id: str,
        resource_id: str,
        recommendation_log_id: Optional[str],
        action: str,
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """Track user interaction with a recommended resource."""
        payload = {
            "user_id": user_id,
            "resource_id": resource_id,
            "recommendation_log_id": recommendation_log_id,
            "action": action,
            "session_id": session_id,
        }
        query = self.db.table("recommendation_interactions").insert(payload)
        result = self._execute(query, "track resource view")
        if not result.data:
            return {"status": "tracked"}
        return result.data[0]