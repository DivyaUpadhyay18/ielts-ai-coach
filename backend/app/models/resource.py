"""
Pydantic schemas for the Resource domain entity.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

RESOURCE_TYPES = ("video", "article", "pdf", "practice_test", "guide", "flashcard_set")
RESOURCE_SKILLS = ("writing", "speaking", "reading", "listening", "vocabulary", "grammar", "general")
RESOURCE_MODULES = ("academic", "general", "both")
RESOURCE_DIFFICULTIES = ("beginner", "intermediate", "advanced", "all_levels")


class ResourceCreate(BaseModel):
    """Schema for creating a resource (admin content catalog)."""
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    type: str
    skill: str
    module: str = Field("academic", pattern="^(academic|general|both)$")
    difficulty: str = Field("intermediate", pattern="^(beginner|intermediate|advanced|all_levels)$")
    provider: Optional[str] = None
    url: str
    duration_minutes: Optional[int] = Field(None, ge=1, le=600)
    tags: List[str] = Field(default_factory=list)
    is_published: bool = True

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in RESOURCE_TYPES:
            raise ValueError(f"type must be one of: {', '.join(RESOURCE_TYPES)}")
        return v

    @field_validator("skill")
    @classmethod
    def validate_skill(cls, v: str) -> str:
        if v not in RESOURCE_SKILLS:
            raise ValueError(f"skill must be one of: {', '.join(RESOURCE_SKILLS)}")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("URL must be an HTTPS URL")
        return v.strip()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: List[str]) -> List[str]:
        seen = set()
        result = []
        for tag in v:
            normalized = tag.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result


class ResourceUpdate(BaseModel):
    """Schema for partial update of a resource."""
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    type: Optional[str] = None
    skill: Optional[str] = None
    module: Optional[str] = Field(None, pattern="^(academic|general|both)$")
    difficulty: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced|all_levels)$")
    provider: Optional[str] = None
    url: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=600)
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith("https://"):
            raise ValueError("URL must be an HTTPS URL")
        return v.strip()


class ResourceResponse(BaseModel):
    """Schema for a resource response."""
    id: str
    title: str
    description: Optional[str] = None
    type: str
    skill: str
    module: str = "academic"
    difficulty: str = "intermediate"
    provider: Optional[str] = None
    url: str
    duration_minutes: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    is_published: bool = True
    view_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResourceBookmarkCreate(BaseModel):
    """Schema for bookmarking a resource."""
    resource_id: str