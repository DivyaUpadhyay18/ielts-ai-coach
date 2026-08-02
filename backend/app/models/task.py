"""
Pydantic schemas for the Task domain entity.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

TASK_SKILLS = ("writing", "speaking", "reading", "listening", "vocabulary", "grammar", "mock", "general")
TASK_TYPES = (
    "writing_task1",
    "writing_task2",
    "speaking_part1",
    "speaking_part2",
    "speaking_part3",
    "vocab_set",
    "grammar_lesson",
    "mock_section",
    "full_mock",
    "video",
    "article",
    "practice_test",
    "review",
)
TASK_STATUSES = ("pending", "in_progress", "completed", "missed", "rescheduled", "skipped")


class TaskCreate(BaseModel):
    """Schema for creating a task."""
    study_plan_id: Optional[str] = None
    daily_plan_id: Optional[str] = None
    phase_index: Optional[int] = Field(None, ge=0)
    title: str = Field(..., min_length=1, max_length=300)
    skill: str
    task_type: str
    content_payload: Optional[Dict[str, Any]] = None
    resource_id: Optional[str] = None
    duration_minutes: int = Field(..., ge=1, le=240)
    scheduled_date: Optional[date] = None
    priority: int = Field(1, ge=1, le=5)
    status: str = Field("pending", pattern="^(pending|in_progress|completed|missed|rescheduled|skipped)$")
    is_mandatory: bool = False
    due_at: Optional[datetime] = None
    order_index: Optional[int] = None
    xp_reward: int = Field(10, ge=0)
    difficulty: int = Field(1, ge=1, le=5)
    week_index: Optional[int] = Field(None, ge=0)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped

    @field_validator("skill")
    @classmethod
    def validate_skill(cls, v: str) -> str:
        if v not in TASK_SKILLS:
            raise ValueError(f"Skill must be one of: {', '.join(TASK_SKILLS)}")
        return v

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v: str) -> str:
        if v not in TASK_TYPES:
            raise ValueError(f"task_type must be one of: {', '.join(TASK_TYPES)}")
        return v


class TaskUpdate(BaseModel):
    """Schema for partial update of a task."""
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    skill: Optional[str] = None
    task_type: Optional[str] = None
    content_payload: Optional[Dict[str, Any]] = None
    resource_id: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=240)
    scheduled_date: Optional[date] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[str] = None
    is_mandatory: Optional[bool] = None
    due_at: Optional[datetime] = None
    order_index: Optional[int] = None
    phase_index: Optional[int] = Field(None, ge=0)
    xp_reward: Optional[int] = Field(None, ge=0)
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    week_index: Optional[int] = Field(None, ge=0)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped

    @field_validator("skill")
    @classmethod
    def validate_skill(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in TASK_SKILLS:
            raise ValueError(f"Skill must be one of: {', '.join(TASK_SKILLS)}")
        return v

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in TASK_TYPES:
            raise ValueError(f"task_type must be one of: {', '.join(TASK_TYPES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in TASK_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(TASK_STATUSES)}")
        return v


class TaskComplete(BaseModel):
    """Schema for completing a task."""
    duration_minutes: Optional[int] = Field(None, ge=1, le=240)
    output: Optional[Dict[str, Any]] = None
    notes: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    """Schema for a task response."""
    id: str
    user_id: str
    study_plan_id: Optional[str] = None
    daily_plan_id: Optional[str] = None
    phase_index: Optional[int] = None
    title: str
    skill: str
    task_type: str
    content_payload: Optional[Dict[str, Any]] = None
    resource_id: Optional[str] = None
    duration_minutes: int
    scheduled_date: Optional[date] = None
    priority: int = 1
    status: str = "pending"
    is_mandatory: bool = False
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    order_index: Optional[int] = None
    xp_reward: int = 10
    difficulty: int = 1
    week_index: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TaskResourceLink(BaseModel):
    """Schema for attaching a resource to a task."""
    resource_id: str
    relation: str = Field("supplementary", pattern="^(primary|required|supplementary)$")


class TaskWithResourcesResponse(TaskResponse):
    """Task response that includes attached resources."""
    resources: List[Dict[str, Any]] = Field(default_factory=list)

