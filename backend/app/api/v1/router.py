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
