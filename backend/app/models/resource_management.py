"""
Pydantic schemas for the Resource Management domain.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResourceCreate(BaseModel):
    """Schema for creating a new resource."""
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    type: str = Field(..., description="Resource type: video, article, pdf, practice_test, guide, flashcard_set")
    skill: str = Field(..., description="Skill: writing, speaking, reading, listening, vocabulary, grammar, general")
    module: str = Field("academic", description="Module: academic, general, both")
    difficulty: str = Field("intermediate", description="Difficulty: beginner, intermediate, advanced, all_levels")
    provider: Optional[str] = None
    url: str = Field(..., description="URL starting with https://")
    duration_minutes: Optional[int] = Field(None, ge=1, le=600)
    tags: List[str] = Field(default_factory=list)
    is_published: bool = True
    source: Optional[str] = None
    author: Optional[str] = None
    thumbnail: Optional[str] = None
    sub_skill: Optional[str] = None
    minimum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    maximum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    estimated_time: Optional[int] = Field(None, ge=0)
    language: str = "en"
    verified: bool = False
    official: bool = False
    is_free: bool = True
    rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    popularity_score: int = 0


class ResourceUpdate(BaseModel):
    """Schema for updating a resource."""
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    type: Optional[str] = None
    skill: Optional[str] = None
    module: Optional[str] = None
    difficulty: Optional[str] = None
    provider: Optional[str] = None
    url: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=600)
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = None
    source: Optional[str] = None
    author: Optional[str] = None
    thumbnail: Optional[str] = None
    sub_skill: Optional[str] = None
    minimum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    maximum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    estimated_time: Optional[int] = Field(None, ge=0)
    language: Optional[str] = None
    verified: Optional[bool] = None
    official: Optional[bool] = None
    is_free: Optional[bool] = None
    rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    popularity_score: Optional[int] = None


class ResourceResponse(BaseModel):
    """Schema for resource response."""
    id: str
    title: str
    description: Optional[str]
    type: str
    skill: str
    module: str
    difficulty: str
    provider: Optional[str]
    url: str
    duration_minutes: Optional[int]
    tags: List[str]
    is_published: bool
    view_count: int
    created_at: Optional[str]
    updated_at: Optional[str]
    source: Optional[str]
    author: Optional[str]
    thumbnail: Optional[str]
    sub_skill: Optional[str]
    minimum_band: Optional[float]
    maximum_band: Optional[float]
    estimated_time: Optional[int]
    language: str
    verified: bool
    official: bool
    is_free: bool
    rating: Optional[float]
    popularity_score: int


class ResourceSuggestionCreate(BaseModel):
    """Schema for creating a resource suggestion (community submission)."""
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    category: str = Field(
        "Website",
        description="Category: YouTube Video, PDF, Website, Practice Test, Vocabulary List",
    )
    reason: Optional[str] = Field(None, description="Why this resource is valuable")
    type: str = Field(..., description="Video, PDF, Website, Quiz, Flashcard")
    source: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    thumbnail: Optional[str] = None
    skill: str = Field(..., description="Reading, Listening, Writing, Speaking, Vocabulary, Grammar")
    sub_skill: Optional[str] = None
    minimum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    maximum_band: Optional[float] = Field(None, ge=0.0, le=9.0)
    difficulty: Optional[str] = Field(None, description="beginner, intermediate, advanced, all_levels")
    estimated_time: Optional[int] = Field(None, ge=0)
    tags: List[str] = Field(default_factory=list)
    language: str = "en"
    is_free: bool = True


class ResourceSuggestionUpdate(BaseModel):
    """Schema for admin editing a suggestion."""
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    category: Optional[str] = None
    reason: Optional[str] = None
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
    is_free: Optional[bool] = None
    admin_notes: Optional[str] = None


class ResourceSuggestionVoteResponse(BaseModel):
    """Schema for vote response."""
    suggestion_id: str
    votes: int
    voted: bool


class ResourceSuggestionResponse(BaseModel):
    """Schema for resource suggestion response."""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    category: str
    reason: Optional[str]
    votes: int = 0
    type: str
    source: Optional[str]
    author: Optional[str]
    url: Optional[str]
    thumbnail: Optional[str]
    skill: str
    sub_skill: Optional[str]
    minimum_band: Optional[float]
    maximum_band: Optional[float]
    difficulty: Optional[str]
    estimated_time: Optional[int]
    tags: List[str]
    language: str
    is_free: bool
    status: str
    admin_notes: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[str]
    rejected_by: Optional[str]
    rejected_at: Optional[str]
    resource_id: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    voted: Optional[bool] = False


class BulkOperationRequest(BaseModel):
    """Schema for bulk operations."""
    operation: str = Field(..., description="create, update, or delete")
    items: List[Dict[str, Any]]


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation response."""
    success: int
    failed: int
    errors: List[Dict[str, Any]]
