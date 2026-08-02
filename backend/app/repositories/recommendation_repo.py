"""
Repository for the Intelligent Recommendation Engine.

Provides data access methods for:
- Fetching user context (profile, onboarding data, preferences)
- Fetching resources from the catalog
- Fetching completed resources (from study_sessions where source_type='resource')
- Fetching past performance by skill
- Fetching today's mission
- Logging recommendation requests
- Tracking user interactions with recommendations
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository
from app.models.resource_management import RESOURCE_TYPES, RESOURCE_SKILLS


class RecommendationRepository(BaseRepository):
    """Repository for recommendation engine data access."""

    table_name = "resources"
    id_column = "id"
    _ownable = False

    # Valid resource types and skills for validation
    RESOURCE_TYPES = RESOURCE_TYPES
    RESOURCE_SKILLS = RESOURCE_SKILLS

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # User context fetches
    # ------------------------------------------------------------------
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetch the user's full profile including band scores and exam date."""
        query = (
            self._table()
            .select("*")
            .eq("id", user_id)
            .limit(1)
        )
        # Use users table directly
        query = self.db.table("users").select("*").eq("id", user_id).limit(1)
        result = self._execute(query, "fetch user profile for recommendations")
        if not result.data:
            raise NotFoundError("User not found")
        return result.data[0]

    def get_user_onboarding(self, user_id: str) -> Dict[str, Any]:
        """Fetch onboarding data for a user (weakest_skill, strongest_skill, etc.)."""
        query = (
            self.db.table("users")
            .select("weakest_skill, strongest_skill, previous_ielts_attempt")
            .eq("id", user_id)
            .limit(1)
        )
        result = self._execute(query, "fetch user onboarding for recommendations")
        if not result.data:
            return {}
        return result.data[0]

    def get_today_missions(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch today's daily missions for a user."""
        today = date.today().isoformat()
        query = (
            self.db.table("daily_missions")
            .select("*")
            .eq("user_id", user_id)
            .eq("mission_date", today)
        )
        result = self._execute(query, "fetch today's missions for recommendations")
        return result.data or []

    # ------------------------------------------------------------------
    # Resource fetches
    # ------------------------------------------------------------------
    def get_catalog_resources(
        self,
        skill: Optional[str] = None,
        resource_type: Optional[str] = None,
        difficulty: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        minimum_band: Optional[float] = None,
        maximum_band: Optional[float] = None,
        is_free: Optional[bool] = None,
        verified: Optional[bool] = True,
        official: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch resources from the catalog with optional filters."""
        query = self._table().select("*")

        if skill:
            query = query.eq("skill", skill)
        if resource_type:
            query = query.eq("type", resource_type)
        if difficulty:
            query = query.eq("difficulty", difficulty)
        if minimum_band is not None:
            query = query.gte("minimum_band", minimum_band)
        if maximum_band is not None:
            query = query.lte("maximum_band", maximum_band)
        if is_free is not None:
            query = query.eq("is_free", is_free)
        if verified is not None:
            query = query.eq("verified", verified)
        if official is not None:
            query = query.eq("official", official)

        query = query.order("popularity_score", desc=True)
        query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        result = self._execute(query, "fetch catalog resources for recommendations")
        return result.data or []

    def get_resource_by_id(self, resource_id: str) -> Dict[str, Any]:
        """Fetch a single resource by ID."""
        query = self._table().select("*").eq("id", resource_id).limit(1)
        result = self._execute(query, "fetch resource for recommendations")
        if not result.data:
            raise NotFoundError("Resource not found")
        return result.data[0]

    # ------------------------------------------------------------------
    # Completed / interacted resources
    # ------------------------------------------------------------------
    def get_completed_resource_ids(self, user_id: str) -> Set[str]:
        """
        Get the set of resource IDs that the user has previously interacted with
        via study_sessions (where source_type = 'resource' or 'recommendation').
        """
        query = (
            self.db.table("study_sessions")
            .select("source_id")
            .eq("user_id", user_id)
            .in_("source_type", ["resource", "recommendation"])
        )
        result = self._execute(query, "fetch completed resource IDs")
        completed = set()
        for row in result.data or []:
            sid = row.get("source_id")
            if sid:
                completed.add(str(sid))
        return completed

    def get_completed_resources_detail(
        self, user_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get detailed info about completed resources with performance data."""
        since = (date.today() - timedelta(days=90)).isoformat()
        query = (
            self.db.table("study_sessions")
            .select("source_id, skill, session_type, minutes, xp_earned, created_at, meta")
            .eq("user_id", user_id)
            .in_("source_type", ["resource", "recommendation"])
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self._execute(query, "fetch completed resource details")
        return result.data or []

    # ------------------------------------------------------------------
    # Performance history
    # ------------------------------------------------------------------
    def get_skill_performance(self, user_id: str) -> Dict[str, Dict[str, float]]:
        """
        Get the user's performance by skill from study_sessions.
        Returns {skill: {"tasks": count, "minutes": total, "xp": total, "completion_rate": %}}
        """
        query = (
            self.db.table("study_sessions")
            .select("skill, minutes, xp_earned, source_type")
            .eq("user_id", user_id)
        )
        result = self._execute(query, "fetch skill performance for recommendations")
        rows = result.data or []

        skill_data: Dict[str, Dict[str, float]] = {}
        for row in rows:
            skill = row.get("skill") or "general"
            if skill not in skill_data:
                skill_data[skill] = {"tasks": 0, "minutes": 0, "xp": 0}
            if row.get("source_type") in ("mission", "task"):
                skill_data[skill]["tasks"] += 1
            skill_data[skill]["minutes"] += int(row.get("minutes") or 0)
            skill_data[skill]["xp"] += int(row.get("xp_earned") or 0)

        return skill_data

    def get_task_completions(self, user_id: str) -> Dict[str, Dict[str, int]]:
        """
        Get task completion stats per skill.
        Returns {skill: {"completed": int, "total": int}}
        """
        today = date.today()
        thirty_days_ago = (today - timedelta(days=30)).isoformat()

        # Get completed tasks
        completed_query = (
            self.db.table("tasks")
            .select("skill", count="exact")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .gte("created_at", thirty_days_ago)
        )
        completed_result = self._execute(completed_query, "count completed tasks")
        completed_count = completed_result.count or 0

        # Get total tasks
        total_query = (
            self.db.table("tasks")
            .select("skill", count="exact")
            .eq("user_id", user_id)
            .gte("created_at", thirty_days_ago)
        )
        total_result = self._execute(total_query, "count total tasks")
        total_count = total_result.count or 0

        # Get skill breakdown
        skill_query = (
            self.db.table("tasks")
            .select("skill, status")
            .eq("user_id", user_id)
            .gte("created_at", thirty_days_ago)
        )
        skill_result = self._execute(skill_query, "fetch task skill stats")

        skill_stats: Dict[str, Dict[str, int]] = {}
        for row in skill_result.data or []:
            skill = row.get("skill") or "general"
            if skill not in skill_stats:
                skill_stats[skill] = {"completed": 0, "total": 0}
            skill_stats[skill]["total"] += 1
            if row.get("status") == "completed":
                skill_stats[skill]["completed"] += 1

        return skill_stats

    def get_mock_scores(self, user_id: str) -> List[float]:
        """Get mock test band scores from study sessions."""
        query = (
            self.db.table("study_sessions")
            .select("meta")
            .eq("user_id", user_id)
            .eq("session_type", "mock_test")
            .order("created_at", desc=True)
            .limit(10)
        )
        result = self._execute(query, "fetch mock scores for recommendations")
        scores: List[float] = []
        for row in result.data or []:
            meta = row.get("meta") or {}
            if isinstance(meta, dict):
                band = meta.get("band_score") or meta.get("score")
                if band is not None:
                    try:
                        scores.append(float(band))
                    except (ValueError, TypeError):
                        continue
        return scores

    # ------------------------------------------------------------------
    # Recommendation logging
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
        """Log a recommendation request for audit purposes."""
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
        query = self.db.table("recommendation_logs").insert(payload)
        result = self._execute(query, "log recommendation")
        return result.data[0] if result.data else {}

    def get_recommendation_logs(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get recommendation logs for a user."""
        query = (
            self.db.table("recommendation_logs")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if offset:
            query = query.offset(offset)
        result = self._execute(query, "fetch recommendation logs")
        return result.data or []

    def track_resource_view(
        self,
        user_id: str,
        resource_id: str,
        recommendation_log_id: Optional[str],
        action: str,
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """Track a user interaction with a recommended resource."""
        update_data: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}

        if action == "viewed":
            update_data["viewed"] = True
        elif action == "clicked":
            update_data["viewed"] = True
            update_data["clicked"] = True
        elif action == "completed":
            update_data["viewed"] = True
            update_data["clicked"] = True
            update_data["completed"] = True

        # Try to find existing record
        select_query = (
            self.db.table("recommendation_resource_view")
            .select("*")
            .eq("user_id", user_id)
            .eq("resource_id", resource_id)
            .limit(1)
        )
        select_result = self._execute(select_query, "fetch recommendation resource view")

        if select_result.data:
            # Update existing record
            rid = select_result.data[0].get("id")
            query = (
                self.db.table("recommendation_resource_view")
                .update(update_data)
                .eq("id", rid)
            )
            result = self._execute(query, "update recommendation resource view")
            return result.data[0] if result.data else {}
        else:
            # Create new record
            payload = {
                "user_id": user_id,
                "resource_id": resource_id,
                "recommendation_log_id": recommendation_log_id,
                "viewed": action in ("viewed", "clicked", "completed"),
                "clicked": action in ("clicked", "completed"),
                "completed": action == "completed",
                "session_id": session_id,
            }
            query = self.db.table("recommendation_resource_view").insert(payload)
            result = self._execute(query, "insert recommendation resource view")
            return result.data[0] if result.data else {}

    def cache_recommendations(
        self, user_id: str, run_date: str, resources_json: List[Dict[str, Any]], metadata: Dict[str, Any]
    ) -> None:
        """Cache recommendations for a user to avoid recomputation."""
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        payload = {
            "user_id": user_id,
            "run_date": run_date,
            "resources_json": resources_json,
            "metadata": metadata,
            "expires_at": expires_at,
        }
        query = self.db.table("recommendation_cache").upsert(
            payload, on_conflict="user_id,run_date"
        )
        self._execute(query, "cache recommendations")