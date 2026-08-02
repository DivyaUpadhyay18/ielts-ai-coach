"""
FastAPI dependencies for authentication and database access.
"""
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.db.supabase import supabase
from app.db.session import db_session
from app.core.security import decode_token
from app.models.auth import UserResponse

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None),
) -> str:
    """
    Dependency to verify the JWT token and return the user_id.
    Raises 401 if token is invalid or missing.
    """
    token = None
    
    # Try to extract token from Authorization header
    if credentials:
        token = credentials.credentials
    elif authorization:
        token = authorization.replace("Bearer ", "")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode and verify the JWT token
    payload = decode_token(token, expected_type="access")
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Dependency to optionally get the current user.
    Returns None if not authenticated (no error raised).
    """
    token = None

    if credentials:
        token = credentials.credentials
    elif authorization:
        token = authorization.replace("Bearer ", "")

    if not token:
        return None

    try:
        payload = decode_token(token, expected_type="access")
        return payload.get("sub")
    except Exception:
        return None


async def get_current_user_profile(
    user_id: str = Depends(get_current_user),
) -> UserResponse:
    """
    Dependency to get the full user profile.
    """
    try:
        result = supabase.table("users").select("*").eq("id", user_id).single().execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return UserResponse(**result.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user profile: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Repository dependencies
# ---------------------------------------------------------------------------
from app.repositories.user_repo import UserRepository
from app.repositories.study_plan_repo import StudyPlanRepository
from app.repositories.daily_plan_repo import DailyPlanRepository
from app.repositories.daily_mission_repo import DailyMissionRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.resource_repo import ResourceRepository
from app.repositories.progress_repo import ProgressRepository
from app.repositories.achievement_repo import AchievementRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository
from app.repositories.scheduler_repo import SchedulerRepository
from app.repositories.schedule_history_repo import ScheduleHistoryRepository
from app.services.schedule_history_service import ScheduleHistoryService, schedule_history_service
from app.services.study_plan_generator import StudyPlanGenerator, study_plan_generator
from app.services.adaptive_scheduler import AdaptiveSchedulerService, adaptive_scheduler
from app.services.exam_countdown import ExamCountdownService, exam_countdown_service
from app.services.prediction_engine import PredictionEngineService, prediction_engine_service


def get_user_repo() -> UserRepository:
    return UserRepository(db_session)


def get_study_plan_repo() -> StudyPlanRepository:
    return StudyPlanRepository(db_session)


def get_daily_plan_repo() -> DailyPlanRepository:
    return DailyPlanRepository(db_session)


def get_daily_mission_repo() -> DailyMissionRepository:
    return DailyMissionRepository(db_session)


def get_task_repo() -> TaskRepository:
    return TaskRepository(db_session)


def get_resource_repo() -> ResourceRepository:
    return ResourceRepository(db_session)


def get_progress_repo() -> ProgressRepository:
    return ProgressRepository(db_session)


def get_achievement_repo() -> AchievementRepository:
    return AchievementRepository(db_session)


def get_notification_repo() -> NotificationRepository:
    return NotificationRepository(db_session)


def get_progress_tracking_repo() -> ProgressTrackingRepository:
    return ProgressTrackingRepository(db_session)


def get_streak_repo() -> StreakRepository:
    return StreakRepository(db_session)


def get_study_plan_generator() -> StudyPlanGenerator:
    return study_plan_generator


def get_scheduler_repo() -> SchedulerRepository:
    return SchedulerRepository(db_session)


def get_scheduler_service() -> AdaptiveSchedulerService:
    return adaptive_scheduler


def get_schedule_history_repo() -> ScheduleHistoryRepository:
    return ScheduleHistoryRepository(db_session)


def get_schedule_history_service() -> ScheduleHistoryService:
    return schedule_history_service


def get_exam_countdown_service() -> ExamCountdownService:
    return exam_countdown_service


def get_prediction_engine_service() -> PredictionEngineService:
    return prediction_engine_service
