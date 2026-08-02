"""
Pydantic models for authentication requests and responses.
"""
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re


class UserCreate(BaseModel):
    """Schema for user registration."""
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=100, example="John Doe")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """Validate full name."""
        if not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip()


class UserLogin(BaseModel):
    """Schema for user login."""
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower().strip()


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""
    refresh_token: str


class UserResponse(BaseModel):
    """Schema for user data response."""
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Onboarding / profile fields
    country: Optional[str] = None
    timezone: Optional[str] = None
    module: Optional[str] = None
    current_band: Optional[float] = None
    target_band: Optional[float] = None
    exam_date: Optional[str] = None
    daily_minutes_budget: Optional[int] = None
    preferred_study_time: Optional[str] = None
    weakest_skill: Optional[list] = None
    strongest_skill: Optional[list] = None
    previous_ielts_attempt: Optional[bool] = None
    is_onboarding_complete: Optional[bool] = False
    onboarded_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class PasswordResetRequest(BaseModel):
    """Schema for requesting password reset."""
    email: str = Field(..., example="user@example.com")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower().strip()


class PasswordReset(BaseModel):
    """Schema for resetting password with token."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ChangePassword(BaseModel):
    """Schema for changing password (authenticated)."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    detail: str
    error_code: Optional[str] = None
