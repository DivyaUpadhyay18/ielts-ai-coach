"""
Writing Improvement Plan API endpoints.

Provides "Improve My Band" functionality:
  - POST /api/v1/writing-improvement-plans/{submission_id}
      → generate a personalized improvement plan from an evaluated essay
  - GET  /api/v1/writing-improvement-plans/{evaluation_id}
      → fetch a stored plan
  - GET  /api/v1/writing-improvement-plans
      → list the user's plans

All AI calls are on the backend.  Plans are owner-scoped.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.api.deps import get_current_user, get_writing_improvement_plan_engine
from app.core.exceptions import NotFoundError, ValidationError
from app.models.writing_workspace import (
    WritingImprovementPlanResponse,
    WritingImprovementPlanListResponse,
)
from app.services.writing_improvement_plan_engine import WritingImprovementPlanEngine


router = APIRouter()


@router.post(
    "/{submission_id}",
    response_model=WritingImprovementPlanResponse,
    summary="Generate a personalized 'Improve My Band' plan",
)
async def generate_improvement_plan(
    submission_id: str,
    target_band: Optional[float] = Query(
        None, ge=0.0, le=9.0,
        description="Optional target band. If omitted, uses the user's profile target or current_band + 1.0.",
    ),
    user_id: str = Depends(get_current_user),
    engine: WritingImprovementPlanEngine = Depends(get_writing_improvement_plan_engine),
):
    """
    Generate a personalized improvement plan for a submitted and evaluated essay.

    The plan uses the student's *actual* evaluation data (criterion bands,
    error types, error analysis) to produce:
      - Current estimated band and target band
      - Gap to target
      - Ranked main weaknesses
      - What the student is doing now vs. what a Band 8+ response requires
      - Specific changes to make
      - Practice exercises
      - Recommended resources (integrated with the Resource Engine)
      - A suggested next Writing Mission (integrated with the Adaptive Scheduler)
    """
    try:
        result = await engine.generate_plan(user_id, submission_id, target_band)
        return WritingImprovementPlanResponse(**result)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{evaluation_id}",
    response_model=WritingImprovementPlanResponse,
    summary="Get the improvement plan for an evaluation",
)
async def get_improvement_plan(
    evaluation_id: str,
    user_id: str = Depends(get_current_user),
    engine: WritingImprovementPlanEngine = Depends(get_writing_improvement_plan_engine),
):
    """Fetch the stored improvement plan for an evaluation."""
    try:
        result = engine.get_plan(user_id, evaluation_id)
        return WritingImprovementPlanResponse(**result)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No improvement plan found for this evaluation",
        )


@router.get(
    "",
    response_model=WritingImprovementPlanListResponse,
    summary="List all improvement plans for the current user",
)
async def list_improvement_plans(
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    engine: WritingImprovementPlanEngine = Depends(get_writing_improvement_plan_engine),
):
    """List the current user's improvement plans (most recent first)."""
    result = engine.list_plans(user_id, limit)
    return WritingImprovementPlanListResponse(**result)
