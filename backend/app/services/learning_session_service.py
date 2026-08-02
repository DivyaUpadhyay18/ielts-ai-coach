"""
Learning Session Mode Service.

Orchestrates the learning session lifecycle:
1. Start a session: fetch today's mission + recommended resources + previous mistakes
2. Track session state: progress bar, notes, bookmarks
3. Complete session: mark mission complete, log to study_sessions, update progress,
   update streaks, update dashboard/scheduler, earn XP

No AI — all recommendations are rule-based (delegates to RecommendationEngineService).
"""
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.daily_mission_repo import DailyMissionRepository
from app.repositories.learning_session_repo import LearningSessionRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.resource_management_repo import ResourceRepository
from app.repositories.streak_repo import StreakRepository
from app.repositories.user_repo import UserRepository
from app.repositories.task_repo import TaskRepository
from app.services.recommendation_engine_service import RecommendationEngineService

logger = logging.getLogger(__name__)


class LearningSessionService:
    """Service for managing learning sessions."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.session_repo = LearningSessionRepository(db)
        self.mission_repo = DailyMissionRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)
        self.resource_repo = ResourceRepository(db)
        self.streak_repo = StreakRepository(db)
        self.user_repo = UserRepository(db)
        self.task_repo = TaskRepository(db)
        self.recommendation_service = RecommendationEngineService(db)

    # ─── Public API ────────────────────────────────────────────────

    def start_session(
        self,
        user_id: str,
        mission_id: Optional[str] = None,
        skill: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a learning session for a mission.

        Fetches:
        - Mission details (title, description, estimated time, XP reward)
        - Recommended resource (using the recommendation engine)
        - Related resources
        - Previous mistakes for the user's weakest skill
        - Existing notes and bookmarks
        - Session state (progress %)
        - User context (current/target band, remaining days)
        """
        today = date.today()

        # Fetch user profile
        user = self._safe_get_user_profile(user_id)
        if not user:
            raise NotFoundError("User not found")

        current_band = float(user.get("current_band") or 5.0)
        target_band = float(user.get("target_band") or 6.5)
        exam_date_str = user.get("exam_date")
        daily_budget = int(user.get("daily_minutes_budget") or 60)
        weakest_skills = user.get("weakest_skill") or []

        remaining_days = None
        if exam_date_str:
            try:
                exam_date = datetime.fromisoformat(str(exam_date_str)[:10]).date()
                remaining_days = max((exam_date - today).days, 0)
            except (ValueError, TypeError):
                remaining_days = None

        # Determine which mission to start
        if mission_id:
            mission = self._safe_get_mission(user_id, mission_id)
        else:
            # Get today's missions, optionally filtered by skill
            todays_missions = self._safe_get_todays_missions(user_id)
            if not todays_missions:
                # Generate today's missions if none exist
                self.mission_repo.generate_for_date(user_id, today)
                todays_missions = self._safe_get_todays_missions(user_id)

            if skill:
                target_skill_lower = skill.lower()
                todays_missions = [m for m in todays_missions if m.get("skill", "").lower() == target_skill_lower]

            if not todays_missions:
                raise NotFoundError("No missions found for today")

            # Pick the mission that matches the weakest skill, or the first pending one
            mission = None
            for m in todays_missions:
                if m.get("skill") and weakest_skills and m.get("skill").lower() in [s.lower() for s in weakest_skills]:
                    mission = m
                    break

            if mission is None:
                mission = todays_missions[0]

        if not mission:
            raise NotFoundError("No mission found")

        mission_id = mission.get("id")
        mission_skill = mission.get("skill", "").capitalize()

        # Generate session ID
        session_id = str(uuid.uuid4())

        # Create or get session state
        session_state = self.session_repo.create_or_update_session_state(
            user_id=user_id,
            mission_id=mission_id,
            session_id=session_id,
            status="active",
            progress_percent=0,
            metadata={
                "started_via": "learning_session",
                "mission_skill": mission_skill,
            },
        )

        # Get recommended resource
        recommended_resource = self._get_recommended_resource(
            user_id, mission_skill, daily_budget
        )

        # Get related resources
        related_resources = self._get_related_resources(mission_skill, recommended_resource)

        # Get previous mistakes for this skill
        previous_mistakes = self._get_previous_mistakes(user_id, mission_skill)

        # Get existing notes and bookmarks for this mission
        notes = self._safe_list_notes(user_id, mission_id)
        bookmarks = self._safe_list_bookmarks(user_id)

        # Calculate session timing
        estimated_time = int(mission.get("estimated_minutes") or 30)
        xp_reward = int(mission.get("xp_reward") or 10)

        return {
            "user_id": user_id,
            "session_id": session_id,
            "mission": self._to_mission_response(mission),
            "recommended_resource": recommended_resource,
            "related_resources": related_resources,
            "previous_mistakes": previous_mistakes,
            "notes": notes,
            "bookmarks": bookmarks,
            "progress_percent": session_state.get("progress_percent", 0),
            "estimated_time": estimated_time,
            "xp_reward": xp_reward,
            "current_band": current_band,
            "target_band": target_band,
            "remaining_days": remaining_days,
            "created_at": session_state.get("created_at") or datetime.utcnow().isoformat(),
        }

    def update_session_progress(
        self,
        user_id: str,
        mission_id: str,
        progress_percent: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update the session progress bar and status."""
        return self.session_repo.update_session_state(
            user_id=user_id,
            mission_id=mission_id,
            progress_percent=progress_percent,
            status=status,
        )

    def add_note(
        self,
        user_id: str,
        content: str,
        mission_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a note to the current session."""
        note = self.session_repo.add_note(
            user_id=user_id,
            content=content,
            mission_id=mission_id,
            resource_id=resource_id,
            session_id=session_id,
        )

        # Update notes count in session state
        if mission_id:
            session_state = self.session_repo.get_session_state(user_id, mission_id)
            if session_state:
                notes_count = int(session_state.get("notes_count") or 0) + 1
                self.session_repo.update_session_state(
                    user_id=user_id,
                    mission_id=mission_id,
                    metadata={"notes_count": notes_count},
                )

        return note

    def add_bookmark(
        self,
        user_id: str,
        resource_id: str,
        mission_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Bookmark a resource within the current session."""
        bookmark = self.session_repo.add_bookmark(
            user_id=user_id,
            resource_id=resource_id,
            mission_id=mission_id,
        )

        # Update bookmarks count in session state
        if mission_id:
            session_state = self.session_repo.get_session_state(user_id, mission_id)
            if session_state:
                bookmarks_count = int(session_state.get("bookmarked_resources") or 0) + 1
                self.session_repo.update_session_state(
                    user_id=user_id,
                    mission_id=mission_id,
                    metadata={"bookmarked_resources": bookmarks_count},
                )

        # Also add to the resource_bookmarks table for persistence
        self._add_resource_bookmark(user_id, resource_id)

        return bookmark

    def complete_session(
        self,
        user_id: str,
        mission_id: str,
        actual_duration_minutes: Optional[int] = None,
        notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Complete a learning session.

        This triggers:
        1. Mark mission as completed (in daily_missions table)
        2. Log session to study_sessions (progress tracking)
        3. Update session state to completed
        4. Update streaks (daily/weekly/monthly, perfect day, milestones)
        5. Check for new achievements
        6. Return XP earned and current stats
        """
        today = date.today()

        # Verify the mission exists
        mission = self._safe_get_mission(user_id, mission_id)
        if not mission:
            raise NotFoundError("Mission not found")

        # Get session state before completing
        session_state = self.session_repo.get_session_state(user_id, mission_id)

        # Add any provided notes
        if notes:
            for note in notes:
                self.session_repo.add_note(
                    user_id=user_id,
                    content=note,
                    mission_id=mission_id,
                    session_id=session_state.get("session_id") if session_state else None,
                )

        # Mark mission as completed
        updated_mission = self._safe_complete_mission(user_id, mission_id)

        # Log to study_sessions (progress tracking)
        minutes = actual_duration_minutes or int(mission.get("estimated_minutes") or 30)
        xp = int(mission.get("xp_reward") or 10)

        self._safe_log_session(user_id, mission, minutes, xp)

        # Update streaks
        self._safe_process_streaks(user_id, today)

        # Update session state to completed
        if session_state:
            self.session_repo.update_session_state(
                user_id=user_id,
                mission_id=mission_id,
                status="completed",
                progress_percent=100,
                metadata={
                    "completed_at": datetime.utcnow().isoformat(),
                    "xp_earned": xp,
                },
            )
        else:
            self.session_repo.create_or_update_session_state(
                user_id=user_id,
                mission_id=mission_id,
                status="completed",
                progress_percent=100,
                metadata={"xp_earned": xp, "completed_at": datetime.utcnow().isoformat()},
            )

        # Get updated stats
        progress_state = self._safe_get_progress_state(user_id)
        streak_overview = self._safe_get_streak_overview(user_id)
        achievements = self._check_achievements(user_id, updated_mission)

        return {
            "session_id": session_state.get("session_id") if session_state else None,
            "mission_completed": True,
            "xp_earned": xp,
            "total_xp": int(progress_state.get("total_xp") or 0),
            "level": int(progress_state.get("level") or 1),
            "level_progress": float(progress_state.get("level_progress") or 0.0),
            "streak_current": int(progress_state.get("current_streak") or 0),
            "streak_longest": int(progress_state.get("longest_streak") or 0),
            "achievements_unlocked": achievements,
            "message": f"Mission completed! +{xp} XP earned.",
        }

    def get_session_history(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """Get session history for a user."""
        sessions = self.session_repo.get_session_history(user_id, limit=limit, offset=offset)

        # Get total count
        total = len(sessions)  # Approximate; could be more precise with a count query

        return {
            "sessions": [self._to_session_history(s) for s in sessions],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_todays_session_overview(
        self, user_id: str
    ) -> Dict[str, Any]:
        """Get an overview of today's session state."""
        today = date.today()
        todays_missions = self._safe_get_todays_missions(user_id)

        sessions = []
        for mission in todays_missions:
            mission_id = mission.get("id")
            session_state = self.session_repo.get_session_state(user_id, mission_id)
            sessions.append({
                "mission": self._to_mission_response(mission),
                "session": session_state,
                "started": session_state is not None and session_state.get("status") == "active",
                "completed": session_state is not None and session_state.get("status") == "completed",
            })

        return {
            "user_id": user_id,
            "date": today.isoformat(),
            "missions": [s["mission"] for s in sessions],
            "sessions": sessions,
            "total_missions": len(todays_missions),
            "completed": sum(1 for s in sessions if s["completed"]),
            "in_progress": sum(1 for s in sessions if s["started"] and not s["completed"]),
        }

    # ─── Private helpers ───────────────────────────────────────────

    def _get_recommended_resource(
        self, user_id: str, skill: str, daily_budget: int
    ) -> Optional[Dict[str, Any]]:
        """Get a single recommended resource using the recommendation engine."""
        try:
            result = self.recommendation_service.get_recommendations(
                user_id=user_id,
                skill=skill,
                limit=1,
            )
            recs = result.get("recommendations", [])
            if recs:
                return recs[0].get("resource")
        except Exception as exc:
            logger.warning("Recommendation engine failed: %s", exc)
        return None

    def _get_related_resources(
        self, skill: str, primary_resource: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get resources related to the skill or primary resource."""
        resource_id = primary_resource.get("id") if primary_resource else None
        try:
            return self.session_repo.get_related_resources(
                resource_id=resource_id,
                skill=skill,  # Skill is capitalized (e.g., "Writing")
                limit=5,
            )
        except Exception as exc:
            logger.warning("Failed to fetch related resources: %s", exc)
            return []

    def _get_previous_mistakes(
        self, user_id: str, skill: str
    ) -> List[Dict[str, Any]]:
        """Get previous mistakes for a skill."""
        try:
            return self.session_repo.get_previous_mistakes(
                user_id=user_id,
                skill=skill.capitalize(),
                limit=5,
            )
        except Exception as exc:
            logger.warning("Failed to fetch previous mistakes: %s", exc)
            return []

    def _safe_get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Safely fetch user profile."""
        if self.db is None:
            return None
        try:
            return self.user_repo.get_profile(user_id)
        except NotFoundError:
            return None
        except Exception as exc:
            logger.warning("Failed to fetch user profile: %s", exc)
            return None

    def _safe_get_todays_missions(self, user_id: str) -> List[Dict[str, Any]]:
        """Safely fetch today's missions."""
        if self.db is None:
            return []
        try:
            return self.session_repo.get_todays_missions(user_id)
        except Exception as exc:
            logger.warning("Failed to fetch today's missions: %s", exc)
            return []

    def _safe_get_mission(self, user_id: str, mission_id: str) -> Optional[Dict[str, Any]]:
        """Safely fetch a mission by ID."""
        if self.db is None:
            return None
        try:
            return self.session_repo.get_mission_by_id(user_id, mission_id)
        except NotFoundError:
            return None
        except Exception as exc:
            logger.warning("Failed to fetch mission: %s", exc)
            return None

    def _safe_complete_mission(self, user_id: str, mission_id: str) -> Dict[str, Any]:
        """Safely mark a mission as completed."""
        if self.db is None:
            return {}
        try:
            return self.mission_repo.complete(mission_id, user_id)
        except Exception as exc:
            logger.warning("Failed to complete mission: %s", exc)
            return {}

    def _safe_log_session(self, user_id: str, mission: Dict[str, Any], minutes: int, xp: int) -> None:
        """Safely log a session to the progress tracking ledger."""
        if self.db is None:
            return
        try:
            self.progress_repo.log_session(
                user_id,
                {
                    "activity_date": mission.get("mission_date"),
                    "skill": mission.get("skill"),
                    "session_type": "mission",
                    "minutes": minutes,
                    "xp_earned": xp,
                    "source_type": "mission",
                    "source_id": mission.get("id"),
                    "meta": {
                        "title": mission.get("title", "Daily Mission"),
                        "session_type": "learning_session",
                    },
                },
            )
        except Exception as exc:
            logger.warning("Failed to log session: %s", exc)

    def _safe_process_streaks(self, user_id: str, day: date) -> None:
        """Safely process streaks after session completion."""
        if self.db is None:
            return
        try:
            self.streak_repo.process_activity(user_id, day=day)
        except Exception as exc:
            logger.warning("Failed to process streaks: %s", exc)

    def _safe_get_progress_state(self, user_id: str) -> Dict[str, Any]:
        """Safely get progress state."""
        if self.db is None:
            return {}
        try:
            return self.progress_repo.get_state(user_id)
        except Exception as exc:
            logger.warning("Failed to get progress state: %s", exc)
            return {}

    def _safe_get_streak_overview(self, user_id: str) -> Dict[str, Any]:
        """Safely get streak overview."""
        if self.db is None:
            return {}
        try:
            return self.streak_repo.get_overview(user_id)
        except Exception as exc:
            logger.warning("Failed to get streak overview: %s", exc)
            return {}

    def _safe_list_notes(self, user_id: str, mission_id: str) -> List[Dict[str, Any]]:
        """Safely list notes for a mission."""
        if self.db is None:
            return []
        try:
            return self.session_repo.list_notes(user_id, mission_id)
        except Exception as exc:
            logger.warning("Failed to list notes: %s", exc)
            return []

    def _safe_list_bookmarks(self, user_id: str) -> List[Dict[str, Any]]:
        """Safely list bookmarks for a user."""
        if self.db is None:
            return []
        try:
            return self.session_repo.list_bookmarks(user_id)
        except Exception as exc:
            logger.warning("Failed to list bookmarks: %s", exc)
            return []

    def _add_resource_bookmark(self, user_id: str, resource_id: str) -> None:
        """Also add to the resource_bookmarks table for persistence."""
        if self.db is None:
            return
        try:
            self.resource_repo.add_bookmark(user_id, resource_id)
        except Exception:
            # Bookmark might already exist; that's fine
            pass

    def _check_achievements(self, user_id: str, mission: Dict[str, Any]) -> List[str]:
        """Check for newly unlocked achievements after mission completion."""
        try:
            from app.repositories.achievement_repo import AchievementRepository
            ach_repo = AchievementRepository(self.db)
            # Get existing achievements
            existing = ach_repo.list_user_achievements(user_id)
            existing_codes = [a.get("code") for a in existing if a.get("code")]

            unlocked: List[str] = []
            # Simple achievement checks
            completed_count = len(existing)
            if completed_count >= 1 and "first_mission" not in existing_codes:
                first_mission = ach_repo.get_by_code("first_mission")
                ach_repo.award(user_id, first_mission["id"], {"mission_id": mission.get("id")})
                unlocked.append("first_mission")

            # Check milestone achievements
            total_completed = self._count_completed_missions(user_id)
            milestone_map = {5: "five_missions", 10: "ten_missions", 20: "twenty_missions"}
            for count, code in milestone_map.items():
                if total_completed >= count and code not in existing_codes:
                    try:
                        ach = ach_repo.get_by_code(code)
                        ach_repo.award(user_id, ach["id"], {"count": total_completed})
                        unlocked.append(code)
                    except NotFoundError:
                        pass

            return unlocked
        except Exception as exc:
            logger.warning("Failed to check achievements: %s", exc)
            return []

    def _count_completed_missions(self, user_id: str) -> int:
        """Count completed missions for a user."""
        if self.db is None:
            return 0
        try:
            query = (
                self.db.table("daily_missions")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("status", "completed")
            )
            result = query.execute()
            return result.count or 0
        except Exception as exc:
            logger.warning("Failed to count completed missions: %s", exc)
            return 0

    @staticmethod
    def _level_from_xp(xp: int) -> Optional[Dict[str, Any]]:
        """Calculate level from XP."""
        try:
            from app.repositories.progress_tracking_repo import level_from_xp
            return level_from_xp(xp)
        except Exception:
            return None

    def _to_mission_response(self, mission: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a mission dict to a response-compatible dict."""
        return {
            "id": mission.get("id"),
            "user_id": mission.get("user_id"),
            "mission_date": mission.get("mission_date"),
            "skill": mission.get("skill"),
            "title": mission.get("title"),
            "estimated_minutes": int(mission.get("estimated_minutes") or 0),
            "xp_reward": int(mission.get("xp_reward") or 0),
            "completion_percent": int(mission.get("completion_percent") or 0),
            "status": mission.get("status") or "pending",
            "created_at": mission.get("created_at"),
            "updated_at": mission.get("updated_at"),
        }

    def _to_session_history(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a session state dict to a history response."""
        return {
            "id": session.get("id"),
            "user_id": session.get("user_id"),
            "mission_id": session.get("mission_id"),
            "session_id": session.get("session_id"),
            "status": session.get("status"),
            "progress_percent": int(session.get("progress_percent") or 0),
            "started_at": session.get("started_at"),
            "completed_at": session.get("completed_at"),
            "notes_count": int(session.get("notes_count") or 0),
            "bookmarked_resources": int(session.get("bookmarked_resources") or 0),
            "xp_earned": int(session.get("xp_earned") or 0),
            "metadata": session.get("metadata") or {},
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
        }


# Singleton bound to the shared DB session
from app.db.session import db_session

learning_session_service = LearningSessionService(db_session)