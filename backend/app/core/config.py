from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "IELTS AI Coach"
    ENVIRONMENT: str = "development"
    
    # Supabase Settings
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    DATABASE_URL: str
    
    # AI Settings
    OPENAI_API_KEY: Optional[str] = None

    # CORS Settings
    CORS_ORIGINS: Optional[str] = None

    # JWT Settings
    JWT_SECRET_KEY: str = "ielts-ai-coach-jwt-secret-key-change-in-production"
    JWT_REFRESH_SECRET_KEY: str = "ielts-ai-coach-refresh-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_GLOBAL: str = "100/minute"
    RATE_LIMIT_AUTH: str = "5/minute"

    # Redis (optional, for rate limiting cache)
    REDIS_URL: Optional[str] = None

    # Load .env file
    model_config = SettingsConfigDict(env_file=".env")

# Initialize settings
settings = Settings()
