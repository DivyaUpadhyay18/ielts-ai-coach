"""
Speaking Improvement Plan API endpoints.

Provides personalized "Improve My Speaking Band" plans after a Speaking
response has been evaluated.

  - POST /api/v1/speaking-improvement-plan/{response_id}
      → generate a plan for a spoken response (with optional target_band)
  - GET  /api/v1/speaking-improvement-plan/{response_id}
      → fetch the most recent plan for a response
  - GET  /api/v1/speaking-improvement-plan
      → list all plans for the current user

The plan uses the student's ACTUAL evaluation data — not generic advice.
Recommendations integrate with the Adaptive Scheduler, Resource Engine,
Mission Engine, and AI Mentor.

The user's original transcript and evaluation are never modified.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_speaking_improvement_plan_engine
from app.core.exceptions import NotFoundError, ValidationError
from app.models.writing_workspace import (
    SpeakingImprovementPlanResponse,
    SpeakingImprovementPlanListResponse,
)
from app.services.speaking_improvement_plan_engine import SpeakingImprovementPlanEngine


router = APIRouter()


@router.post(
    "/{response_id}",
    response_model=SpeakingImprovementPlanResponse,
    summary="Generate a personalized speaking improvement plan",
)
async def generate_speaking_improvement_plan(
    response_id: str,
    target_band: float | None = None,
    user_id: str = Depends(get_current_user),
    engine: SpeakingImprovementPlanEngine = Depends(get_speaking_improvement_plan_engine),
):
    """
    Generate a personalized "Improve My Speaking Band" plan for a spoken response.

    The plan is based on the student's actual evaluation data and error analysis,
    covering:
    - Current estimated Speaking Band
    - Target Band (resolved from arg, profile, or current + 1.0)
    - Band Gap
    - Strongest / Weakest Criterion
    - Per-criterion priority levels (high / medium / low)
    - Specific exercises
    - Recommended resources
    - Practice topics
    - Suggested daily speaking time
    - Next recommended speaking task
    - A schedulable mission for the Mission Engine

    Recommendations integrate with:
    - Adaptive Scheduler (scheduling the suggested mission)
    - Resource Engine (resource titles resolved to real content)
    - Mission Engine (suggested_mission provides a mission template)
    - AI Mentor (plan feeds the mentor's coaching context)

    The user's original transcript and evaluation are never modified.
    """
    try:
        result = await engine.generate_plan(user_id, response_id, target_band)
        return SpeakingImprovementPlanResponse(**result)
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
    "/{response_id}",
    response_model=SpeakingImprovementPlanResponse,
    summary="Get speaking improvement plan for a response",
)
async def get_speaking_improvement_plan(
    response_id: str,
    user_id: str = Depends(get_current_user),
    engine: SpeakingImprovementPlanEngine = Depends(get_speaking_improvement_plan_engine),
):
    """Fetch the most recent speaking improvement plan for a response."""
    try:
        result = engine.get_plan(user_id, response_id)
        return SpeakingImprovementPlanResponse(**result)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No speaking improvement plan found for this response",
        )


@router.get(
    "",
    response_model=SpeakingImprovementPlanListResponse,
    summary="List all speaking improvement plans for the current user",
)
async def list_speaking_improvement_plans(
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    engine: SpeakingImprovementPlanEngine = Depends(get_speaking_improvement_plan_engine),
):
    """List the current user's speaking improvement plans (most recent first)."""
    result = engine.list_plans(user_id, limit)
    return SpeakingImprovementPlanListResponse(**result)
