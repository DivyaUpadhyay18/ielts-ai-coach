"""
Pydantic schemas for the Resource Management domain.

Tracks resources for the IELTS AI Coach with full CRUD support:
- Video, PDF, Website, Quiz, Flashcard types
- Reading, Listening, Writing, Speaking, Vocabulary, Grammar skills
- Sub-skill specialization, band range, difficulty, ratings
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


RESOURCE_TYPES = ("Video", "PDF", "Website", "Quiz", "Flashcard")
RESOURCE_SKILLS = ("Reading", "Listening", "Writing", "Speaking", "Vocabulary", "Grammar")

READING_SUB_SKILLS = (
    "True False Not Given",
    "Matching Headings",
    "Sentence Completion",
    "Summary Completion",
    "Multiple Choice",
)
WRITING_SUB_SKILLS = (
    "Task 1",
    "Task 2",
    "Coherence",
    "Lexical Resource",
    "Grammar",
    "Ideas",
)
SPEAKING_SUB_SKILLS = (
    "Fluency",
    "Pronunciation",
    "Part 1",
    "Part 2",
    "Part 3",
)
LISTENING_SUB_SKILLS = (
    "Map",
    "Multiple Choice",
    "Form Completion",
)
VOCABULARY_SUB_SKILLS = (
    "Academic",
    "Daily",
    "Idioms",
)
GRAMMAR_SUB_SKILLS = (
    "Tenses",
    "Articles",
    "Prepositions",
)

DIFFICULTY_LEVELS = ("beginner", "intermediate", "advanced", "all_levels")


class ResourceCreate(BaseModel):
    """Schema for creating a new resource."""
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    type: str = Field(..., min_length=1)
    source: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    thumbnail: Optional[str] = None
    skill: str = Field(..., min_length=1)
    sub_skill: Optional[str] = None
    minimum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    maximum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    difficulty: Optional[str] = None
    estimated_time: Optional[int] = Field(None, ge=0)
    tags: List[str] = Field(default_factory=list)
    language: str = Field(default="en")
    verified: bool = Field(default=False)
    official: bool = Field(default=False)
    is_free: bool = Field(default=True)
    rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    popularity_score: int = Field(default=0, ge=0)

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

    @field_validator("sub_skill")
    @classmethod
    def validate_sub_skill(cls, v: Optional[str], info) -> Optional[str]:
        if v is None:
            return v
        skill = info.data.get("skill")
        if skill == "Reading" and v not in READING_SUB_SKILLS:
            raise ValueError(f"sub_skill for Reading must be one of: {', '.join(READING_SUB_SKILLS)}")
        if skill == "Writing" and v not in WRITING_SUB_SKILLS:
            raise ValueError(f"sub_skill for Writing must be one of: {', '.join(WRITING_SUB_SKILLS)}")
        if skill == "Speaking" and v not in SPEAKING_SUB_SKILLS:
            raise ValueError(f"sub_skill for Speaking must be one of: {', '.join(SPEAKING_SUB_SKILLS)}")
        if skill == "Listening" and v not in LISTENING_SUB_SKILLS:
            raise ValueError(f"sub_skill for Listening must be one of: {', '.join(LISTENING_SUB_SKILLS)}")
        if skill == "Vocabulary" and v not in VOCABULARY_SUB_SKILLS:
            raise ValueError(f"sub_skill for Vocabulary must be one of: {', '.join(VOCABULARY_SUB_SKILLS)}")
        if skill == "Grammar" and v not in GRAMMAR_SUB_SKILLS:
            raise ValueError(f"sub_skill for Grammar must be one of: {', '.join(GRAMMAR_SUB_SKILLS)}")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith(("https://", "http://")):
            raise ValueError("URL must start with https:// or http://")
        return v.strip()

    @field_validator("thumbnail")
    @classmethod
    def validate_thumbnail(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith(("https://", "http://")):
            raise ValueError("Thumbnail URL must start with https:// or http://")
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

    @field_validator("minimum_band", "maximum_band")
    @classmethod
    def validate_band_range(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None and (v < 0.0 or v > 9.0):
            raise ValueError("Band score must be between 0.0 and 9.0")
        return v


class ResourceUpdate(BaseModel):
    """Schema for partial update of a resource."""
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    type: Optional[str] = None
    source: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    thumbnail: Optional[str] = None
    skill: Optional[str] = None
    sub_skill: Optional[str] = None
    minimum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    maximum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    difficulty: Optional[str] = None
    estimated_time: Optional[int] = Field(None, ge=0)
    tags: Optional[List[str]] = None
    language: Optional[str] = None
    verified: Optional[bool] = None
    official: Optional[bool] = None
    is_free: Optional[bool] = None
    rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    popularity_score: Optional[int] = Field(None, ge=0)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in RESOURCE_TYPES:
            raise ValueError(f"type must be one of: {', '.join(RESOURCE_TYPES)}")
        return v

    @field_validator("skill")
    @classmethod
    def validate_skill(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in RESOURCE_SKILLS:
            raise ValueError(f"skill must be one of: {', '.join(RESOURCE_SKILLS)}")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith(("https://", "http://")):
            raise ValueError("URL must start with https:// or http://")
        return v.strip()

    @field_validator("thumbnail")
    @classmethod
    def validate_thumbnail(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith(("https://", "http://")):
            raise ValueError("Thumbnail URL must start with https:// or http://")
        return v.strip()

    @field_validator("minimum_band", "maximum_band")
    @classmethod
    def validate_band_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0.0 or v > 9.0):
            raise ValueError("Band score must be between 0.0 and 9.0")
        return v


class ResourceResponse(BaseModel):
    """Schema for a resource response."""
    id: str
    title: str
    description: Optional[str] = None
    type: str
    source: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    thumbnail: Optional[str] = None
    skill: str
    sub_skill: Optional[str] = None
    minimum_band: Optional[float] = None
    maximum_band: Optional[float] = None
    difficulty: Optional[str] = None
    estimated_time: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    language: str = "en"
    verified: bool = False
    official: bool = False
    is_free: bool = True
    rating: Optional[float] = None
    popularity_score: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResourceListResponse(BaseModel):
    """Paginated list of resources."""
    items: List[ResourceResponse]
    total: int
    limit: int
    offset: int


class ResourceSearchFilters(BaseModel):
    """Filters for searching resources."""
    skill: Optional[str] = None
    type: Optional[str] = None
    difficulty: Optional[str] = None
    minimum_band: Optional[float] = None
    maximum_band: Optional[float] = None
    is_free: Optional[bool] = None
    verified: Optional[bool] = None
    official: Optional[bool] = None
    search: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class ResourceStats(BaseModel):
    """Resource catalog statistics."""
    total_resources: int
    by_type: dict
    by_skill: dict
    by_difficulty: dict
    avg_rating: Optional[float]
    free_count: int
    verified_count: int
    official_count: int