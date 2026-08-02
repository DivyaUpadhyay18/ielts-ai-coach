from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.endpoints import router as api_router
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.security import limiter
from app.core.exceptions import register_exception_handlers
import time

app = FastAPI(
    title="IELTS AI Coach API",
    description="Backend API for IELTS AI grading and feedback",
    version="1.0.0"
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Consistent error envelope handlers
register_exception_handlers(app)

# Configure CORS — reads from env var or defaults to localhost:3000
origins = ["http://localhost:3000"]
if hasattr(settings, "CORS_ORIGINS") and settings.CORS_ORIGINS:
    origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    
    # Add request timing
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Global rate limiter
@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    if settings.RATE_LIMIT_ENABLED and request.url.path.startswith("/api/"):
        try:
            response = await call_next(request)
            return response
        except Exception:
            return await call_next(request)
    return await call_next(request)


# Include the routes
# Legacy v0 routes (existing)
app.include_router(api_router, prefix="/api")

# New v1 routes (auth, etc.)
app.include_router(v1_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "IELTS AI Coach API is online",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/health",
            "auth": {
                "register": "POST /api/v1/auth/register",
                "login": "POST /api/v1/auth/login",
                "refresh": "POST /api/v1/auth/refresh",
                "logout": "POST /api/v1/auth/logout",
                "me": "GET /api/v1/auth/me",
                "forgot_password": "POST /api/v1/auth/forgot-password",
                "reset_password": "POST /api/v1/auth/reset-password",
                "change_password": "POST /api/v1/auth/change-password",
            },
            "study_plans": {
                "generate": "POST /api/v1/study-plans/generate",
                "days": "GET /api/v1/study-plans/{plan_id}/days",
            },
            "daily_missions": {
                "today": "GET /api/v1/daily-missions/today",
                "generate": "POST /api/v1/daily-missions/generate",
            },
            "scheduler": {
                "run": "POST /api/v1/scheduler/run",
                "latest": "GET /api/v1/scheduler/latest",
                "runs": "GET /api/v1/scheduler/runs",
                "explain": "GET /api/v1/scheduler/explain",
            },
            "schedule_history": {
                "list": "GET /api/v1/schedule-history",
                "get": "GET /api/v1/schedule-history/{history_id}",
                "compare": "GET /api/v1/schedule-history/compare/{id1}/{id2}",
                "update_action": "PATCH /api/v1/schedule-history/{history_id}/action",
                "stats": "GET /api/v1/schedule-history/stats/summary",
                "latest": "GET /api/v1/schedule-history/latest",
            },
            "resource_management": {
                "list": "GET /api/v1/resource-management",
                "search": "GET /api/v1/resource-management/search",
                "get": "GET /api/v1/resource-management/{resource_id}",
                "create": "POST /api/v1/resource-management",
                "update": "PATCH /api/v1/resource-management/{resource_id}",
                "delete": "DELETE /api/v1/resource-management/{resource_id}",
                "stats": "GET /api/v1/resource-management/stats",
                "by_skill": "GET /api/v1/resource-management/by-skill/{skill}",
                "by_type": "GET /api/v1/resource-management/by-type/{type}",
                "verified": "GET /api/v1/resource-management/verified",
                "official": "GET /api/v1/resource-management/official",
                "free": "GET /api/v1/resource-management/free",
            },
            "recommendation_engine": {
                "get": "GET /api/v1/recommendations",
                "history": "GET /api/v1/recommendations/history",
                "track": "POST /api/v1/recommendations/track",
                "stats": "GET /api/v1/recommendations/stats",
            },
            "learning_sessions": {
                "start": "POST /api/v1/learning-sessions/start",
                "progress": "POST /api/v1/learning-sessions/{mission_id}/progress",
                "add_note": "POST /api/v1/learning-sessions/{mission_id}/notes",
                "bookmark": "POST /api/v1/learning-sessions/{mission_id}/bookmarks",
                "complete": "POST /api/v1/learning-sessions/{mission_id}/complete",
                "today": "GET /api/v1/learning-sessions/today",
                "history": "GET /api/v1/learning-sessions/history",
            }
        }
    }
