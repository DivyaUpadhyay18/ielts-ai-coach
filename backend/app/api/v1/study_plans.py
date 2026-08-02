"""
Study Plan CRUD + Generation endpoints.
"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.api.deps import (
    get_current_user,
    get_study_plan_generator,
    get_study_plan_repo,
)
from app.core.exceptions import NotFoundError
from app.models.study_plan import StudyPlanCreate, StudyPlanUpdate, StudyPlanResponse
from app.models.study_plan_engine import (
    StudyPlanDaysResponse,
    StudyPlanGenerateRequest,
    StudyPlanGenerateResponse,
)
from app.repositories.study_plan_repo import StudyPlanRepository
from app.services.study_plan_generator import StudyPlanGenerator

router = APIRouter()


@router.get(
    "",
    response_model=List[StudyPlanResponse],
    summary="List study plans",
)
async def list_study_plans(
    user_id: str = Depends(get_current_user),
    repo: StudyPlanRepository = Depends(get_study_plan_repo),
):
    """List all study plans for the current user, newest version first."""
    return repo.list_versions(user_id)


@router.post(
    "",
    response_model=StudyPlanResponse,
    status_code=201,
    summary="Create a study plan",
)
async def create_study_plan(
    data: StudyPlanCreate,
    user_id: str = Depends(get_current_user),
    repo: StudyPlanRepository = Depends(get_study_plan_repo),
):
    """Create a new study plan. The version is auto-incremented for this user."""
    payload = data.model_dump()
    return repo.create(user_id, payload)


@router.get(
    "/active",
    response_model=StudyPlanResponse,
    summary="Get active study plan",
)
async def get_active_study_plan(
    user_id: str = Depends(get_current_user),
    repo: StudyPlanRepository = Depends(get_study_plan_repo),
):
    """Fetch the user's currently active study plan."""
    plan = repo.get_active(user_id)
    if not plan:
        raise NotFoundError("No active study plan found")
    return plan


@router.get(
    "/{plan_id}",
    response_model=StudyPlanResponse,
    summary="Get a study plan by ID",
)
async def get_study_plan(
    plan_id: str,
    user_id: str = Depends(get_current_user),
    repo: StudyPlanRepository = Depends(get_study_plan_repo),
):
    """Fetch a specific study plan by ID (scoped to the current user)."""
    return repo.get_by_id(plan_id, user_id=user_id)


@router.patch(
    "/{plan_id}",
    response_model=StudyPlanResponse,
    summary="Update a study plan",
)
async def update_study_plan(
    plan_id: str,
    data: StudyPlanUpdate,
    user_id: str = Depends(get_current_user),
    repo: StudyPlanRepository = Depends(get_study_plan_repo),
):
    """Partially update a study plan (title, status, total_weeks, meta)."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_by_id(plan_id, user_id=user_id)
    return repo.update(plan_id, payload, user_id=user_id)


@router.delete(
    "/{plan_id}",
    status_code=204,
    summary="Delete a study plan",
)
async def delete_study_plan(
    plan_id: str,
    user_id: str = Depends(get_current_user),
    repo: StudyPlanRepository = Depends(get_study_plan_repo),
):
    """Delete a study plan (scoped to the current user)."""
    repo.delete(plan_id, user_id=user_id)
    return None


@router.post(
    "/generate",
    response_model=StudyPlanGenerateResponse,
    status_code=201,
    summary="Generate a deterministic study plan",
)
async def generate_study_plan(
    data: StudyPlanGenerateRequest,
    user_id: str = Depends(get_current_user),
    generator: StudyPlanGenerator = Depends(get_study_plan_generator),
):
    """
    Generate a full day-by-day study plan until the exam date.

    Deterministic, no AI: phase weighting (Foundation 30% / Skill Building
    30% / Advanced 20% / Mock Tests 15% / Final Revision 5%), weak-skill
    focus, gradual difficulty ramp, weekly revision, biweekly mocks, and a
    protected final revision window. Archives any existing active plan and
    creates a new version.
    """
    return generator.generate(user_id, data)


@router.get(
    "/{plan_id}/days",
    response_model=StudyPlanDaysResponse,
    summary="Get day-by-day view of a study plan",
)
async def get_study_plan_days(
    plan_id: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    user_id: str = Depends(get_current_user),
    generator: StudyPlanGenerator = Depends(get_study_plan_generator),
):
    """
    Fetch a study plan's daily plan + task breakdown.

    Supports optional date-range filtering via from/to query params.
    """
    return generator.get_plan_days(user_id, plan_id, from_date, to_date)
