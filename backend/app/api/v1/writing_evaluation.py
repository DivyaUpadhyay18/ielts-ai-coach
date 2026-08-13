"""
Writing Evaluation API endpoints.

Provides endpoints to evaluate submitted Writing Workspace essays:
  - POST /api/v1/writing-evaluations/{submission_id}  → run AI evaluation
  - GET  /api/v1/writing-evaluations/{submission_id}  → fetch evaluation
  - GET  /api/v1/writing-evaluations                   → list user evaluations

All AI calls are on the backend. API keys and prompts are never exposed.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_writing_evaluation_engine
from app.core.exceptions import NotFoundError, ValidationError
from app.models.writing_workspace import (
    WritingEvaluationResponse,
    WritingEvaluationListResponse,
)
from app.services.writing_evaluation_engine import WritingEvaluationEngine


router = APIRouter()


@router.post(
    "/{submission_id}",
    response_model=WritingEvaluationResponse,
    summary="Evaluate a submitted writing essay (AI-powered)",
)
async def evaluate_submission(
    submission_id: str,
    task_type: str = "task_2",
    user_id: str = Depends(get_current_user),
    engine: WritingEvaluationEngine = Depends(get_writing_evaluation_engine),
):
    """
    Run the AI Writing Evaluation on a submitted essay.

    Assesses all four official IELTS Writing criteria (Task Achievement/Response,
    Coherence and Cohesion, Lexical Resource, Grammatical Range and Accuracy),
    computes an overall band, and stores the complete evaluation.

    The result is **always an estimate** — ``is_estimate`` is set to ``true``.
    This is not an official IELTS score.
    """
    try:
        result = await engine.evaluate_submission(
            user_id, submission_id, task_type
        )
        return WritingEvaluationResponse(**result)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found — only submitted essays can be evaluated",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{submission_id}",
    response_model=WritingEvaluationResponse,
    summary="Get the evaluation for a submission",
)
async def get_evaluation(
    submission_id: str,
    user_id: str = Depends(get_current_user),
    engine: WritingEvaluationEngine = Depends(get_writing_evaluation_engine),
):
    """Fetch the stored evaluation for a submitted essay."""
    try:
        result = engine.get_evaluation(user_id, submission_id)
        return WritingEvaluationResponse(**result)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No evaluation found for this submission",
        )


@router.get(
    "",
    response_model=WritingEvaluationListResponse,
    summary="List all writing evaluations for the current user",
)
async def list_evaluations(
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    engine: WritingEvaluationEngine = Depends(get_writing_evaluation_engine),
):
    """List the current user's writing evaluations (most recent first)."""
    result = engine.get_user_evaluations(user_id, limit)
    return WritingEvaluationListResponse(**result)
