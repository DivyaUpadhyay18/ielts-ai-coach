"""
Repository for the DailyMission domain entity.

Data access for the daily_missions table including placeholder mission
generation (deterministic — NO AI scheduling), completion/skip updates,
and per-day summary aggregation.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository

# The six IELTS skill domains that make up a day's mission set.
MISSION_SKILLS = ("reading", "listening", "writing", "speaking", "vocabulary", "grammar")

# Placeholder mission template per skill: (title, est_minutes, xp_reward)
SKILL_TEMPLATES: Dict[str, tuple] = {
    "reading": ("Reading Practice Passages", 25, 20),
    "listening": ("Listening Section Drills", 20, 20),
    "writing": ("Writing Task Practice", 30, 30),
    "speaking": ("Speaking Fluency Practice", 15, 20),
    "vocabulary": ("Vocabulary Builder Set", 10, 10),
    "grammar": ("Grammar Fundamentals Drill", 10, 10),
}


class DailyMissionRepository(BaseRepository):
    """Data access for the daily_missions table."""

    table_name = "daily_missions"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def list_for_date(self, user_id: str, mission_date: date) -> List[Dict[str, Any]]:
        """Fetch all missions for a user on a specific date, ordered by skill."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .eq("mission_date", mission_date.isoformat())
            .order("skill")
        )
        result = self._execute(query, "list daily missions for date")
        return result.data or []

    def list_for_date_range(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Fetch all missions for a user within a date range, ordered by date+skill."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .gte("mission_date", start_date.isoformat())
            .lte("mission_date", end_date.isoformat())
            .order("mission_date")
            .order("skill")
        )
        result = self._execute(query, "list daily missions for date range")
        return result.data or []

    def get_by_date_and_skill(
        self,
        user_id: str,
        mission_date: date,
        skill: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single mission for a user/date/skill combination, if it exists."""
        query = (
            self._table()
            .select("*")
            .eq(self.user_id_column, user_id)
            .eq("mission_date", mission_date.isoformat())
            .eq("skill", skill)
            .limit(1)
        )
        result = self._execute(query, "get daily mission by date+skill")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def get_summary(
        self,
        user_id: str,
        mission_date: date,
    ) -> Dict[str, Any]:
        """
        Aggregate a day's missions into a summary payload.

        Counts total/completed/skipped/pending, sums estimated minutes and
        XP rewards, and derives earned XP + completion percent.
        """
        missions = self.list_for_date(user_id, mission_date)

        total = len(missions)
        completed = sum(1 for m in missions if m.get("status") == "completed")
        skipped = sum(1 for m in missions if m.get("status") == "skipped")
        pending = total - completed - skipped

        total_minutes = sum(int(m.get("estimated_minutes") or 0) for m in missions)
        total_xp = sum(int(m.get("xp_reward") or 0) for m in missions)

        # Earned XP counts only fully completed missions (completion_percent >= 100).
        earned_xp = sum(
            int(m.get("xp_reward") or 0)
            for m in missions
            if m.get("status") == "completed" and int(m.get("completion_percent") or 0) >= 100
        )

        # Completion percent = completed+skipped resolved missions / total.
        resolved = completed + skipped
        completion_percent = round((resolved / total) * 100) if total > 0 else 0

        return {
            "mission_date": mission_date.isoformat(),
            "total_missions": total,
            "completed_missions": completed,
            "skipped_missions": skipped,
            "pending_missions": pending,
            "total_estimated_minutes": total_minutes,
            "total_xp_reward": total_xp,
            "earned_xp": earned_xp,
            "completion_percent": completion_percent,
        }

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------
    def complete(self, mission_id: str, user_id: str) -> Dict[str, Any]:
        """
        Mark a mission as completed with completion_percent = 100.
        """
        query = (
            self._table()
            .update({
                "status": "completed",
                "completion_percent": 100,
            })
            .eq(self.id_column, mission_id)
            .eq(self.user_id_column, user_id)
        )
        result = self._execute(query, "complete daily mission")
        if not result.data:
            raise NotFoundError("Daily mission not found")
        return result.data[0]

    def skip(self, mission_id: str, user_id: str) -> Dict[str, Any]:
        """
        Mark a mission as skipped (completion_percent preserved / reset to 0).
        """
        query = (
            self._table()
            .update({
                "status": "skipped",
                "completion_percent": 0,
            })
            .eq(self.id_column, mission_id)
            .eq(self.user_id_column, user_id)
        )
        result = self._execute(query, "skip daily mission")
        if not result.data:
            raise NotFoundError("Daily mission not found")
        return result.data[0]

    def update_progress(
        self,
        mission_id: str,
        user_id: str,
        completion_percent: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a mission's completion_percent and/or status (validated by caller)."""
        payload: Dict[str, Any] = {}
        if completion_percent is not None:
            payload["completion_percent"] = completion_percent
        if status is not None:
            payload["status"] = status

        if not payload:
            return self.get_by_id(mission_id, user_id=user_id)

        query = (
            self._table()
            .update(payload)
            .eq(self.id_column, mission_id)
            .eq(self.user_id_column, user_id)
        )
        result = self._execute(query, "update daily mission")
        if not result.data:
            raise NotFoundError("Daily mission not found")
        return result.data[0]

    # ------------------------------------------------------------------
    # Placeholder generation (NO AI scheduling)
    # ------------------------------------------------------------------
    def _mission_title(self, skill: str, mission_date: date) -> str:
        """Deterministic placeholder title from the skill template."""
        template = SKILL_TEMPLATES.get(skill)
        if template:
            return template[0]
        return f"{skill.title()} Practice"

    def _mission_meta(self, skill: str, mission_date: date) -> Dict[str, Any]:
        """Deterministic placeholder metadata (minutes + XP) for a skill."""
        minutes, xp = SKILL_TEMPLATES.get(skill, (15, 10))
        return {"estimated_minutes": minutes, "xp_reward": xp}

    def generate_for_date(self, user_id: str, mission_date: date) -> List[Dict[str, Any]]:
        """
        Generate (idempotently) the six skill missions for a user on a date.

        Placeholder-only: missions are derived from a static skill template —
        no AI scheduling or personalization is performed. Existing missions
        for the same user/date/skill are left untouched.
        """
        existing = self.list_for_date(user_id, mission_date)
        existing_keys = {(m["skill"]) for m in existing}

        created: List[Dict[str, Any]] = []
        for skill in MISSION_SKILLS:
            if skill in existing_keys:
                continue
            meta = self._mission_meta(skill, mission_date)
            payload = {
                "user_id": user_id,
                "mission_date": mission_date.isoformat(),
                "skill": skill,
                "title": self._mission_title(skill, mission_date),
                "estimated_minutes": meta["estimated_minutes"],
                "xp_reward": meta["xp_reward"],
                "completion_percent": 0,
                "status": "pending",
            }
            try:
                row = self.create(payload)
                created.append(row)
            except Exception:
                # Race-safe: another request may have created it concurrently.
                row = self.get_by_date_and_skill(user_id, mission_date, skill)
                if row:
                    created.append(row)
        return created

    def generate_for_range(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Generate placeholder missions for every day in [start, end]."""
        created: List[Dict[str, Any]] = []
        current = start_date
        while current <= end_date:
            created.extend(self.generate_for_date(user_id, current))
            current += timedelta(days=1)
        return created

