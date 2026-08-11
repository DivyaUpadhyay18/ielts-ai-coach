"""
Pydantic schemas for the Writing Workspace API.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SubmissionStart(BaseModel):
    """Request to start/resume a writing submission."""
    prompt_id: str


class SubmissionSave(BaseModel):
    """Request to auto-save a draft."""
    essay_text: str
    time_seconds_spent: Optional[int] = None


class SubmissionSubmit(BaseModel):
    """Request to submit a draft for evaluation."""
    time_seconds_spent: Optional[int] = None


class PromptResponse(BaseModel):
    """A single writing prompt."""
    id: str
    task_type: str
    title: str
    prompt_text: str
    word_limit: int
    time_limit_seconds: int
    difficulty: int
    topics: List[str] = []


class PromptsResponse(BaseModel):
    """List of writing prompts."""
    task_type: str
    prompts: List[PromptResponse]
    total: int


class WritingSubmissionSummary(BaseModel):
    """Pre-submission summary captured at submit time."""
    word_count: int
    word_limit: int
    time_seconds_spent: int
    time_limit_seconds: int
    meets_word_requirement: bool
    within_time_limit: bool
    warnings: List[str] = []
    submitted_at: Optional[str] = None


class SubmissionResponse(BaseModel):
    """A writing workspace submission."""
    id: str
    user_id: str
    prompt_id: Optional[str] = None
    task_type: str
    title: str
    prompt_text: Optional[str] = None
    word_limit: int
    time_limit_seconds: int
    essay_text: str
    word_count: int
    time_seconds_spent: int
    status: str
    is_locked: bool
    submission_summary: Dict[str, Any] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None


class SubmissionListResponse(BaseModel):
    """List of submissions."""
    results: List[SubmissionResponse]
    total: int
