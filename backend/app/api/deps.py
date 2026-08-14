"""
FastAPI dependencies for authentication and database access.
"""
from __future__ import annotations

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


async def get_current_admin(
    user_id: str = Depends(get_current_user),
) -> str:
    """
    Dependency to verify the current user has admin or super_admin role.
    Raises 403 if the user is not an admin.
    """
    try:
        result = supabase.table("users").select("role").eq("id", user_id).single().execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        role = result.data.get("role", "user")
        if role not in ("admin", "super_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking admin role: {str(e)}",
        )


async def get_current_super_admin(
    user_id: str = Depends(get_current_user),
) -> str:
    """
    Dependency to verify the current user has super_admin role.
    Raises 403 if the user is not a super admin.
    """
    try:
        result = supabase.table("users").select("role").eq("id", user_id).single().execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        role = result.data.get("role", "user")
        if role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super admin access required",
            )
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking super admin role: {str(e)}",
        )


async def get_current_moderator(
    user_id: str = Depends(get_current_user),
) -> str:
    """
    Dependency to verify the current user has moderator, admin, or super_admin role.
    Raises 403 if the user does not have moderator access.
    """
    try:
        result = supabase.table("users").select("role").eq("id", user_id).single().execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        role = result.data.get("role", "user")
        if role not in ("moderator", "admin", "super_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Moderator access required",
            )
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking moderator role: {str(e)}",
        )


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
from app.repositories.resource_management_repo import ResourceRepository
from app.repositories.progress_repo import ProgressRepository
from app.repositories.achievement_repo import AchievementRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository
from app.repositories.scheduler_repo import SchedulerRepository
from app.repositories.schedule_history_repo import ScheduleHistoryRepository
from app.repositories.analytics_repo import AnalyticsRepository
from app.repositories.resource_quality_repo import ResourceQualityRepository
from app.services.schedule_history_service import ScheduleHistoryService, schedule_history_service
from app.services.study_plan_generator import StudyPlanGenerator, study_plan_generator
from app.services.adaptive_scheduler import AdaptiveSchedulerService, adaptive_scheduler
from app.services.exam_countdown import ExamCountdownService, exam_countdown_service
from app.services.prediction_engine import PredictionEngineService, prediction_engine_service
from app.services.diagnostic_service import DiagnosticService, diagnostic_service
from app.services.reading_diagnostic_service import ReadingDiagnosticService, reading_diagnostic_service
from app.services.listening_diagnostic_service import ListeningDiagnosticService, listening_diagnostic_service
from app.services.writing_diagnostic_service import WritingDiagnosticService, writing_diagnostic_service
from app.services.speaking_diagnostic_service import SpeakingDiagnosticService, speaking_diagnostic_service
from app.services.vocab_grammar_diagnostic_service import VocabGrammarDiagnosticService, vocab_grammar_diagnostic_service
from app.repositories.band_estimation_repo import BandEstimationRepository
from app.services.band_estimation_service import BandEstimationService, band_estimation_service
from app.services.weekly_report_service import WeeklyReportService, weekly_report_service
from app.services.ai_recommendations_service import AiRecommendationsService, ai_recommendations_service
from app.services.mentor_memory_service import MentorMemoryService, mentor_memory_service
from app.services.ai_mentor_service import AIMentorService, ai_mentor_service
from app.services.writing_workspace_service import WritingWorkspaceService
from app.services.writing_evaluation_engine import WritingEvaluationEngine
from app.services.writing_improvement_plan_engine import WritingImprovementPlanEngine


# Writing Workspace service factory
def get_writing_workspace_service() -> WritingWorkspaceService:
    from app.db.session import db_session
    return WritingWorkspaceService(db_session)


# Writing Evaluation Engine factory
def get_writing_evaluation_engine() -> WritingEvaluationEngine:
    from app.db.session import db_session
    return WritingEvaluationEngine(db_session)


# Writing Improvement Plan Engine factory
def get_writing_improvement_plan_engine() -> WritingImprovementPlanEngine:
    from app.db.session import db_session
    return WritingImprovementPlanEngine(db_session)


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


def get_resource_management_repo() -> ResourceRepository:
    return ResourceRepository(db_session)


def get_exam_countdown_service() -> ExamCountdownService:
    return exam_countdown_service


def get_prediction_engine_service() -> PredictionEngineService:
    return prediction_engine_service


def get_analytics_repo() -> AnalyticsRepository:
    return AnalyticsRepository(db_session)


def get_resource_quality_repo() -> ResourceQualityRepository:
    return ResourceQualityRepository(db_session)


def get_diagnostic_service() -> DiagnosticService:
    return diagnostic_service


def get_reading_diagnostic_service() -> ReadingDiagnosticService:
    return reading_diagnostic_service


def get_listening_diagnostic_service() -> ListeningDiagnosticService:
    return listening_diagnostic_service


def get_writing_diagnostic_service() -> WritingDiagnosticService:
    return writing_diagnostic_service


def get_speaking_diagnostic_service() -> SpeakingDiagnosticService:
    return speaking_diagnostic_service


def get_vocab_grammar_diagnostic_service() -> VocabGrammarDiagnosticService:
    return vocab_grammar_diagnostic_service


def get_band_estimation_repo() -> BandEstimationRepository:
    return BandEstimationRepository(db_session)


def get_band_estimation_service() -> BandEstimationService:
    return band_estimation_service


def get_weekly_report_service() -> WeeklyReportService:
    return weekly_report_service


def get_ai_recommendations_service() -> AiRecommendationsService:
    return ai_recommendations_service


def get_mentor_memory_service() -> MentorMemoryService:
    return mentor_memory_service


def get_mentor_service() -> AIMentorService:
    return ai_mentor_service


def get_mission_reflection_repo() -> MissionReflectionRepository:
    """Repository for stored mission reflections (owner-scoped)."""
    from app.repositories.mission_reflection_repo import MissionReflectionRepository
    return MissionReflectionRepository(db_session)


def get_reflection_engine() -> ReflectionEngine:
    """ReflectionEngine singleton bound to the shared DB session."""
    from app.services.reflection_engine import ReflectionEngine
    return ReflectionEngine(db=db_session)
