from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router
from app.core.config import settings

app = FastAPI(
    title="IELTS AI Coach API",
    description="Backend API for IELTS AI grading and feedback",
    version="1.0.0"
)

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
)

# Include the routes we defined in endpoints.py
# All routes in endpoints.py will now start with /api
app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    return {
        "message": "IELTS AI Coach API is online",
        "docs": "/docs" # This is a built-in FastAPI feature
    }