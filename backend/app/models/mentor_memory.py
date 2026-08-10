"""
Pydantic schemas for the AI Mentor Memory system.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """A single mentor memory entry."""
    id: str
    memory_type: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    content: str
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5
    weight: int = 1
    context: Dict[str, Any] = Field(default_factory=dict)
    last_accessed_at: Optional[str] = None
    accessed_count: int = 0
    expires_at: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryTypeSchema(BaseModel):
    """Schema for an available memory type."""
    type: str
    label: str
    description: str
    category_required: bool = False
    subcategory_required: bool = False


class MemoryProfileResponse(BaseModel):
    """Consolidated memory profile consumed by the AI mentor."""
    total_memories: int
    recurring_mistakes: List[MemoryEntry] = Field(default_factory=list)
    faqs: List[MemoryEntry] = Field(default_factory=list)
    weak_grammar: List[MemoryEntry] = Field(default_factory=list)
    weak_vocabulary: List[MemoryEntry] = Field(default_factory=list)
    learning_preferences: List[MemoryEntry] = Field(default_factory=list)
    motivation_styles: List[MemoryEntry] = Field(default_factory=list)
    conversation_insights: List[MemoryEntry] = Field(default_factory=list)
    weak_skills: List[str] = Field(default_factory=list)
    preference_texts: List[str] = Field(default_factory=list)
    motivation_texts: List[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Result of a memory extraction run."""
    status: str
    memories_added: int
    memories_updated: int
    details: Dict[str, int] = Field(default_factory=dict)


class MemoryCreateRequest(BaseModel):
    """Request to manually add a memory."""
    memory_type: str
    content: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    confidence: float = 0.7


class MemoryUpdateRequest(BaseModel):
    """Request to update a memory."""
    content: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    is_active: Optional[bool] = None
    expires_at: Optional[str] = None
