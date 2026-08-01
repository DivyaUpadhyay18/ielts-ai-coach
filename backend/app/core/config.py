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

    # Load .env file
    model_config = SettingsConfigDict(env_file=".env")

# Initialize settings
settings = Settings()