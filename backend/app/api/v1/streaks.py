"""
Streak System endpoints.

Exposes the deterministic streak engine (daily/weekly/monthly streaks,
XP bonuses, perfect-day bonus, carry-forward, streak-freeze placeholder).
No AI — all values are derived from the stored progress/mission ledger.
"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from typing import List

from app.api.deps import get_current_user, get_streak_repo
from app.models.streak import (
    StreakOverviewResponse,
    StreakEventItem,
    StreakFreezeResponse,
    FreezeUseRequest,
)
from app.repositories.streak_repo import StreakRepository, DAILY_MILESTONES

router = APIRouter()


@router.get(
    "/overview",
    response_model=StreakOverviewResponse,
    summary="Get the full streak-system overview",
)
async def get_streak_overview(
    user_id: str = Depends(get_current_user),
    repo: StreakRepository = Depends(get_streak_repo),
):
    """Daily/weekly/monthly streaks, perfect-day, carry-forward, freezes,
    bonuses, next milestones and 14-day history."""
    return repo.get_overview(user_id)


@router.get(
    "/events",
    response_model=List[StreakEventItem],
    summary="List bonus-award events",
)
async def list_streak_events(
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user),
    repo: StreakRepository = Depends(get_streak_repo),
):
    """Recent XP bonus events (perfect days, milestones)."""
    return repo.get_events(user_id, limit=limit)


@router.get(
    "/freezes",
    response_model=List[StreakFreezeResponse],
    summary="List streak freezes",
)
async def list_freezes(
    user_id: str = Depends(get_current_user),
    repo: StreakRepository = Depends(get_streak_repo),
):
    """List all streak-freeze tokens for the current user."""
    return repo.list_freezes(user_id)


@router.post(
    "/freezes/grant",
    response_model=StreakFreezeResponse,
    status_code=201,
    summary="Grant a placeholder streak freeze",
)
async def grant_freeze(
    period_type: str = Query("day", pattern="^(day|week|month)$"),
    source: str = Query("placeholder", pattern="^(placeholder|purchase|reward|system)$"),
    user_id: str = Depends(get_current_user),
    repo: StreakRepository = Depends(get_streak_repo),
):
    """Grant a placeholder streak-freeze token (used for testing/placeholder)."""
    return repo.grant_freeze(user_id, period_type=period_type, source=source)


@router.post(
    "/freezes/use",
    response_model=StreakFreezeResponse,
    summary="Use a streak freeze",
)
async def use_freeze(
    data: FreezeUseRequest,
    user_id: str = Depends(get_current_user),
    repo: StreakRepository = Depends(get_streak_repo),
):
    """Consume a streak-freeze token to protect a streak (placeholder)."""
    return repo.use_freeze(user_id, data.freeze_id)


@router.post(
    "/recompute",
    response_model=dict,
    summary="Recompute streak state from stored activity",
)
async def recompute_streaks(
    day: date = Query(date.today(), description="Activity date to process (default today)"),
    user_id: str = Depends(get_current_user),
    repo: StreakRepository = Depends(get_streak_repo),
):
    """
    Deterministically recompute all streak state (daily/weekly/monthly,
    carry-forward, perfect-day + milestone bonuses) for the current user.

    Safe to call repeatedly — bonus awards are idempotent.
    """
    return repo.process_activity(user_id, day=day)


@router.get(
    "/milestones",
    response_model=dict,
    summary="List daily streak XP milestone checkpoints",
)
async def get_milestones(
    user_id: str = Depends(get_current_user),
    repo: StreakRepository = Depends(get_streak_repo),
):
    """Return the deterministic daily/weekly/monthly milestone table."""
    return {
        "daily": DAILY_MILESTONES,
        "weekly": {"every_n_weeks": 4, "xp": 75},
        "monthly": {"every_n_months": 1, "xp": 200},
        "perfect_day_bonus_xp": 25,
        "note": "Deterministic XP milestone table (no AI).",
    }

