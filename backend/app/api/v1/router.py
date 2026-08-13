# API v1 router aggregation
from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.users import router as users_router
from app.api.v1.study_plans import router as study_plans_router
from app.api.v1.daily_plans import router as daily_plans_router
from app.api.v1.daily_missions import router as daily_missions_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.resources import router as resources_router
from app.api.v1.progress import router as progress_router
from app.api.v1.achievements import router as achievements_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.progress_tracking import router as progress_tracking_router
from app.api.v1.streaks import router as streaks_router
from app.api.v1.scheduler import router as scheduler_router
from app.api.v1.schedule_history import router as schedule_history_router
from app.api.v1.countdown import router as countdown_router
from app.api.v1.prediction import router as prediction_router
from app.api.v1.resource_management import router as resource_management_router
from app.api.v1.recommendation_engine import router as recommendation_router
from app.api.v1.learning_session import router as learning_session_router
from app.api.v1.resource_notes import router as resource_notes_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.resource_quality import router as resource_quality_router
from app.api.v1.diagnostic import router as diagnostic_router
from app.api.v1.reading_diagnostic import router as reading_diagnostic_router
from app.api.v1.listening_diagnostic import router as listening_diagnostic_router
from app.api.v1.writing_diagnostic import router as writing_diagnostic_router
from app.api.v1.speaking_diagnostic import router as speaking_diagnostic_router
from app.api.v1.vocab_grammar_diagnostic import router as vocab_grammar_diagnostic_router
from app.api.v1.admin import router as admin_router
from app.api.v1.band_estimation import router as band_estimation_router
from app.api.v1.mentor import router as mentor_router
from app.api.v1.weekly_reports import router as weekly_reports_router
from app.api.v1.ai_recommendations import router as ai_recommendations_router
from app.api.v1.mentor_memory import router as mentor_memory_router
from app.api.v1.reflections import router as reflections_router
from app.api.v1.writing_workspace import router as writing_workspace_router
from app.api.v1.writing_evaluation import router as writing_evaluation_router

router = APIRouter()

# Include all v1 routers
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(onboarding_router, prefix="/onboarding", tags=["Onboarding"])
router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(study_plans_router, prefix="/study-plans", tags=["Study Plans"])
router.include_router(daily_plans_router, prefix="/daily-plans", tags=["Daily Plans"])
router.include_router(daily_missions_router, prefix="/daily-missions", tags=["Daily Missions"])
router.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
router.include_router(resources_router, prefix="/resources", tags=["Resources"])
router.include_router(progress_router, prefix="/progress", tags=["Progress"])
router.include_router(progress_tracking_router, prefix="/progress-tracking", tags=["Progress Tracking"])
router.include_router(streaks_router, prefix="/streaks", tags=["Streaks"])
router.include_router(achievements_router, prefix="/achievements", tags=["Achievements"])
router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
router.include_router(scheduler_router, prefix="/scheduler", tags=["Adaptive Scheduler"])
router.include_router(schedule_history_router, prefix="/schedule-history", tags=["Schedule History"])
router.include_router(countdown_router, prefix="/countdown", tags=["Exam Countdown"])
router.include_router(prediction_router, prefix="/prediction", tags=["Prediction Engine"])
router.include_router(resource_management_router, prefix="/resource-management", tags=["Resource Management"])
router.include_router(recommendation_router, prefix="/recommendations", tags=["Intelligent Recommendations"])
router.include_router(learning_session_router, prefix="/learning-sessions", tags=["Learning Sessions"])
router.include_router(resource_notes_router, prefix="/resource-notes", tags=["Resource Notes"])
router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
router.include_router(resource_quality_router, prefix="/resource-quality", tags=["Resource Quality"])
router.include_router(diagnostic_router, prefix="/diagnostic", tags=["Diagnostic Test"])
router.include_router(reading_diagnostic_router, prefix="/reading", tags=["Reading Diagnostic"])
router.include_router(listening_diagnostic_router, prefix="/listening", tags=["Listening Diagnostic"])
router.include_router(writing_diagnostic_router, prefix="/writing", tags=["Writing Diagnostic"])
router.include_router(speaking_diagnostic_router, prefix="/speaking", tags=["Speaking Diagnostic"])
router.include_router(vocab_grammar_diagnostic_router, prefix="/vocab-grammar", tags=["Vocabulary & Grammar Diagnostic"])
router.include_router(admin_router, prefix="/admin", tags=["Admin"])
router.include_router(band_estimation_router, prefix="/band-estimation", tags=["Band Estimation"])
router.include_router(mentor_router, prefix="/mentor", tags=["AI Mentor"])
router.include_router(reflections_router, prefix="/reflections", tags=["Mission Reflections"])
router.include_router(weekly_reports_router, prefix="/weekly-reports", tags=["Weekly AI Reports"])
router.include_router(ai_recommendations_router, prefix="/ai-recommendations", tags=["AI Recommendations"])
router.include_router(mentor_memory_router, prefix="/mentor-memory", tags=["AI Mentor Memory"])
router.include_router(writing_workspace_router, prefix="/writing-workspace", tags=["Writing Workspace"])
router.include_router(writing_evaluation_router, prefix="/writing-evaluations", tags=["Writing Evaluations"])
