"""
Daily Plan CRUD endpoints.
"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.api.deps import get_current_user, get_daily_plan_repo, get_task_repo
from app.core.exceptions import NotFoundError, ValidationError
from app.models.daily_plan import DailyPlanCreate, DailyPlanUpdate, DailyPlanResponse
from app.repositories.daily_plan_repo import DailyPlanRepository
from app.repositories.task_repo import TaskRepository

router = APIRouter()


@router.get(
    "",
    response_model=List[DailyPlanResponse],
    summary="List daily plans",
)
async def list_daily_plans(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    study_plan_id: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
    repo: DailyPlanRepository = Depends(get_daily_plan_repo),
):
    """
    List daily plans for the current user.

    Supports optional date-range filtering via from/to query params.
    """
    if from_date and to_date:
        if from_date > to_date:
            raise ValidationError("from must be before or equal to to")
        return repo.list_by_date_range(user_id, from_date, to_date)

    if study_plan_id:
        return repo.list_for_study_plan(user_id, study_plan_id)

    return repo.list(user_id=user_id, order_by="plan_date")


@router.post(
    "",
    response_model=DailyPlanResponse,
    status_code=201,
    summary="Create a daily plan",
)
async def create_daily_plan(
    data: DailyPlanCreate,
    user_id: str = Depends(get_current_user),
    repo: DailyPlanRepository = Depends(get_daily_plan_repo),
):
    """Create a new daily plan for the current user."""
    payload = data.model_dump()
    payload["plan_date"] = payload["plan_date"].isoformat()

    # Reject if a daily plan already exists for this user + date.
    existing = repo.get_by_date(user_id, data.plan_date)
    if existing:
        raise ValidationError(
            "A daily plan already exists for this date",
            fields={"plan_date": str(data.plan_date)},
        )

    return repo.create(
        {
            "user_id": user_id,
            **payload,
        }
    )


@router.get(
    "/today",
    response_model=DailyPlanResponse,
    summary="Get today's daily plan",
)
async def get_today_plan(
    user_id: str = Depends(get_current_user),
    repo: DailyPlanRepository = Depends(get_daily_plan_repo),
):
    """Fetch the current user's daily plan for today, if one exists."""
    plan = repo.get_by_date(user_id, date.today())
    if not plan:
        raise NotFoundError("No daily plan exists for today")
    return plan


@router.get(
    "/{plan_id}",
    response_model=DailyPlanResponse,
    summary="Get a daily plan by ID",
)
async def get_daily_plan(
    plan_id: str,
    user_id: str = Depends(get_current_user),
    repo: DailyPlanRepository = Depends(get_daily_plan_repo),
):
    """Fetch a specific daily plan by ID (scoped to the current user)."""
    return repo.get_by_id(plan_id, user_id=user_id)


@router.patch(
    "/{plan_id}",
    response_model=DailyPlanResponse,
    summary="Update a daily plan",
)
async def update_daily_plan(
    plan_id: str,
    data: DailyPlanUpdate,
    user_id: str = Depends(get_current_user),
    repo: DailyPlanRepository = Depends(get_daily_plan_repo),
):
    """Update a daily plan's status or rest-day flag."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_by_id(plan_id, user_id=user_id)
    return repo.update(plan_id, payload, user_id=user_id)


@router.delete(
    "/{plan_id}",
    status_code=204,
    summary="Delete a daily plan",
)
async def delete_daily_plan(
    plan_id: str,
    user_id: str = Depends(get_current_user),
    repo: DailyPlanRepository = Depends(get_daily_plan_repo),
):
    """Delete a daily plan (scoped to the current user)."""
    repo.delete(plan_id, user_id=user_id)
    return None


@router.get(
    "/{plan_id}/tasks",
    response_model=list,
    summary="List tasks in a daily plan",
)
async def list_daily_plan_tasks(
    plan_id: str,
    user_id: str = Depends(get_current_user),
    repo: DailyPlanRepository = Depends(get_daily_plan_repo),
    task_repo: TaskRepository = Depends(get_task_repo),
):
    """Fetch all tasks belonging to a daily plan (scoped to owner)."""
    # Verify the daily plan belongs to the user first.
    repo.get_by_id(plan_id, user_id=user_id)
    return task_repo.list_for_user(user_id=user_id, daily_plan_id=plan_id)