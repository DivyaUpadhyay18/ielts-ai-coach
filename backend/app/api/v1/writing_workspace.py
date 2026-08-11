"""
Writing Workspace API endpoints.

The Writing Workspace is a practice environment where users can:
  - Select Task 1 or Task 2
  - View the IELTS question/prompt
  - Use a full-screen editor with live timer + word counter
  - Auto-save drafts (resume later)
  - Submit for (future) evaluation — once submitted, locked

Endpoints:
  GET  /api/v1/writing-workspace/prompts      → list prompts
  GET  /api/v1/writing-workspace/prompts/{id} → single prompt
  POST /api/v1/writing-workspace/start        → start/resume a submission
  POST /api/v1/writing-workspace/{id}/save    → auto-save
  POST /api/v1/writing-workspace/{id}/submit  → submit (locks)
  GET  /api/v1/writing-workspace/{id}         → fetch submission
  GET  /api/v1/writing-workspace              → list submissions

All operations are owner-scoped (user_id from JWT).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.models.writing_workspace import (
    SubmissionResponse,
    SubmissionSave,
    SubmissionSubmit,
    SubmissionStart,
    SubmissionListResponse,
    PromptResponse,
    PromptsResponse,
)
from app.services.writing_workspace_service import WritingWorkspaceService


router = APIRouter()


def get_writing_workspace_service() -> WritingWorkspaceService:
    from app.db.session import db_session
    return WritingWorkspaceService(db_session)


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------
@router.get(
    "/prompts",
    response_model=PromptsResponse,
    summary="List writing prompts (Task 1 / Task 2)",
)
async def get_prompts(
    task_type: Optional[str] = Query(None, regex="^(task_1|task_2)$"),
    user_id: str = Depends(get_current_user),
    service: WritingWorkspaceService = Depends(get_writing_workspace_service),
):
    """Return all active writing prompts, optionally filtered by task type."""
    return service.get_prompts(task_type)


@router.get(
    "/prompts/{prompt_id}",
    response_model=PromptResponse,
    summary="Get a single writing prompt",
)
async def get_prompt(
    prompt_id: str,
    user_id: str = Depends(get_current_user),
    service: WritingWorkspaceService = Depends(get_writing_workspace_service),
):
    """Fetch a single writing prompt by ID."""
    try:
        return service.get_prompt(prompt_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing prompt not found",
        )


# ---------------------------------------------------------------------------
# Submission lifecycle
# ---------------------------------------------------------------------------
@router.post(
    "/start",
    response_model=SubmissionResponse,
    summary="Start or resume a writing submission",
)
async def start_submission(
    data: SubmissionStart,
    user_id: str = Depends(get_current_user),
    service: WritingWorkspaceService = Depends(get_writing_workspace_service),
):
    """Start a new writing submission or resume an existing draft for a prompt."""
    try:
        return service.start_submission(user_id, data.prompt_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing prompt not found",
        )


@router.post(
    "/{submission_id}/save",
    response_model=SubmissionResponse,
    summary="Auto-save a writing submission draft",
)
async def auto_save(
    submission_id: str,
    data: SubmissionSave,
    user_id: str = Depends(get_current_user),
    service: WritingWorkspaceService = Depends(get_writing_workspace_service),
):
    """Auto-save the essay body + time spent (live word count computed server-side)."""
    try:
        return service.auto_save(
            user_id, submission_id, data.essay_text, data.time_seconds_spent or 0
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{submission_id}/submit",
    response_model=SubmissionResponse,
    summary="Submit a writing submission for evaluation (locks the essay)",
)
async def submit_submission(
    submission_id: str,
    data: SubmissionSubmit,
    user_id: str = Depends(get_current_user),
    service: WritingWorkspaceService = Depends(get_writing_workspace_service),
):
    """Submit the essay. Once submitted, it is locked and immutable."""
    try:
        return service.submit(
            user_id, submission_id, data.time_seconds_spent or 0
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{submission_id}",
    response_model=SubmissionResponse,
    summary="Get a writing submission",
)
async def get_submission(
    submission_id: str,
    user_id: str = Depends(get_current_user),
    service: WritingWorkspaceService = Depends(get_writing_workspace_service),
):
    """Fetch a full submission (owner-scoped)."""
    try:
        return service.get_submission(user_id, submission_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )


@router.get(
    "",
    response_model=SubmissionListResponse,
    summary="List all writing submissions",
)
async def list_submissions(
    limit: int = Query(50, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    service: WritingWorkspaceService = Depends(get_writing_workspace_service),
):
    """List the current user's writing submissions (most recent first)."""
    return service.list_submissions(user_id, limit)
