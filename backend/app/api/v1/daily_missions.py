"""
Daily Mission endpoints.

Every day has a set of six skill missions (reading, listening, writing,
speaking, vocabulary, grammar) with estimated time, XP reward, completion %,
and status (pending / completed / skipped).

Generation uses deterministic placeholder data — NO AI scheduling.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.api.deps import (
    get_current_user,
    get_daily_mission_repo,
    get_progress_tracking_repo,
    get_streak_repo,
)
from app.repositories.daily_mission_repo import MISSION_SKILLS
from app.core.exceptions import ValidationError
from app.models.daily_mission import (
    DailyMissionUpdate,
    DailyMissionResponse,
    DailyMissionListResponse,
    DailyMissionSummary,
    DailyMissionGenerateResponse,
    MISSION_SKILLS,
)
from app.repositories.daily_mission_repo import DailyMissionRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository


def _log_mission_session(
    mission: dict,
    user_id: str,
    progress_repo: ProgressTrackingRepository,
) -> None:
    """
    Feed a completed/skipped mission into the progress-tracking ledger.

    Completed missions log minutes + XP (source_type=mission, source_id=mission id)
    so the progress/dashboard reads update automatically. Skipped missions are
    deliberately NOT logged (no study time or XP is credited).
    """
    status = mission.get("status")
    if status != "completed":
        return

    minutes = int(mission.get("estimated_minutes") or 0)
    xp = int(mission.get("xp_reward") or 0)
    if minutes <= 0 and xp <= 0:
        return

    progress_repo.log_session(
        user_id,
        {
            "activity_date": mission.get("mission_date"),
            "skill": mission.get("skill"),
            "session_type": "mission",
            "minutes": minutes,
            "xp_earned": xp,
            "source_type": "mission",
            "source_id": mission.get("id"),
            "meta": {"title": mission.get("title", "Daily Mission")},
        },
    )


def _process_streaks(
    user_id: str,
    mission_date,
    streak_repo: StreakRepository,
) -> None:
    """
    Recompute the streak engine after a mission is completed or skipped.

    Runs the deterministic daily/weekly/monthly streak calculus with
    carry-forward, perfect-day detection and idempotent XP bonuses.
    Safe to call repeatedly.
    """
    try:
        streak_repo.process_activity(user_id, day=mission_date)
    except Exception:
        # Streak processing is best-effort — a failure here should not
        # block the mission completion response.
        pass


router = APIRouter()


def _list_response(
    repo: DailyMissionRepository,
    user_id: str,
    mission_date: date,
) -> DailyMissionListResponse:
    """Build a DailyMissionListResponse for a single day."""
    missions = repo.list_for_date(user_id, mission_date)
    summary = repo.get_summary(user_id, mission_date)
    return DailyMissionListResponse(
        missions=[DailyMissionResponse(**m) for m in missions],
        summary=DailyMissionSummary(**summary),
    )


@router.get(
    "",
    response_model=List[DailyMissionResponse],
    summary="List daily missions",
)
async def list_daily_missions(
    mission_date: Optional[date] = Query(None),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    user_id: str = Depends(get_current_user),
    repo: DailyMissionRepository = Depends(get_daily_mission_repo),
):
    """
    List the current user's daily missions.

    - `?mission_date=YYYY-MM-DD` → missions for a single day
    - `?from=YYYY-MM-DD&to=YYYY-MM-DD` → missions across a date range
    - No params → today's missions
    """
    if mission_date:
        return repo.list_for_date(user_id, mission_date)

    if from_date or to_date:
        start = from_date or date.today()
        end = to_date or start
        if start > end:
            raise ValidationError("from must be before or equal to to")
        return repo.list_for_date_range(user_id, start, end)

    return repo.list_for_date(user_id, date.today())


@router.get(
    "/today",
    response_model=DailyMissionListResponse,
    summary="Get today's missions with summary",
)
async def get_today_missions(
    user_id: str = Depends(get_current_user),
    repo: DailyMissionRepository = Depends(get_daily_mission_repo),
):
    """Fetch today's missions plus the aggregated daily summary."""
    return _list_response(repo, user_id, date.today())


@router.post(
    "/generate",
    response_model=DailyMissionGenerateResponse,
    summary="Generate placeholder missions for a date or range",
)
async def generate_daily_missions(
    mission_date: Optional[date] = Query(None),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    days: Optional[int] = Query(None, ge=1, le=90, description="Generate for the next N days"),
    user_id: str = Depends(get_current_user),
    repo: DailyMissionRepository = Depends(get_daily_mission_repo),
):
    """
    Idempotently generate the six placeholder skill missions per day.

    Deterministic placeholder data — no AI scheduling. Existing missions
    for the same user/date/skill are never duplicated.
    """
    start = mission_date or from_date or date.today()
    end = mission_date or to_date

    if days is not None:
        start = date.today()
        end = start + timedelta(days=days - 1)

    if end is None:
        end = start

    if start > end:
        raise ValidationError("from must be before or equal to to")

    created = repo.generate_for_range(user_id, start, end)
    expected = (end - start).days + 1

    return DailyMissionGenerateResponse(
        generated=len(created),
        skipped=max(expected * len(MISSION_SKILLS) - len(created), 0),
        date_range=f"{start.isoformat()}..{end.isoformat()}",
    )


@router.get(
    "/{mission_id}",
    response_model=DailyMissionResponse,
    summary="Get a daily mission by ID",
)
async def get_daily_mission(
    mission_id: str,
    user_id: str = Depends(get_current_user),
    repo: DailyMissionRepository = Depends(get_daily_mission_repo),
):
    """Fetch a single mission (scoped to the current user)."""
    return repo.get_by_id(mission_id, user_id=user_id)


@router.patch(
    "/{mission_id}",
    response_model=DailyMissionResponse,
    summary="Update a daily mission's status or completion",
)
async def update_daily_mission(
    mission_id: str,
    data: DailyMissionUpdate,
    user_id: str = Depends(get_current_user),
    repo: DailyMissionRepository = Depends(get_daily_mission_repo),
):
    """Update a mission's completion_percent and/or status."""
    # Verify ownership first (raises NotFoundError if not found/scoped).
    repo.get_by_id(mission_id, user_id=user_id)
    return repo.update_progress(
        mission_id,
        user_id,
        completion_percent=data.completion_percent,
        status=data.status,
    )


@router.post(
    "/{mission_id}/complete",
    response_model=DailyMissionResponse,
    summary="Mark a daily mission as completed",
)
async def complete_daily_mission(
    mission_id: str,
    user_id: str = Depends(get_current_user),
    repo: DailyMissionRepository = Depends(get_daily_mission_repo),
    progress_repo: ProgressTrackingRepository = Depends(get_progress_tracking_repo),
    streak_repo: StreakRepository = Depends(get_streak_repo),
):
    """
    Mark a mission as completed with 100% completion.

    When all missions for the day are completed, automatically generates
    tomorrow's missions (deterministic placeholder data — no AI).
    """
    updated = repo.complete(mission_id, user_id)
    mission_date = updated.get("mission_date")
    if isinstance(mission_date, str):
        mission_date = date.fromisoformat(mission_date)

    # Feed minutes + XP into the progress-tracking ledger.
    _log_mission_session(updated, user_id, progress_repo)
    # Recompute streaks (carry-forward, perfect-day, milestone bonuses).
    _process_streaks(user_id, mission_date, streak_repo)

    # Check if all missions for today are completed → auto-generate tomorrow's missions.
    try:
        summary = repo.get_summary(user_id, mission_date)
        if summary.get("completion_percent") == 100:
            tomorrow = mission_date + timedelta(days=1)
            repo.generate_for_date(user_id, tomorrow)
    except Exception:
        # Auto-generation is best-effort — failure should not block the response.
        pass

    return updated


@router.post(
    "/{mission_id}/skip",
    response_model=DailyMissionResponse,
    summary="Mark a daily mission as skipped",
)
async def skip_daily_mission(
    mission_id: str,
    user_id: str = Depends(get_current_user),
    repo: DailyMissionRepository = Depends(get_daily_mission_repo),
    progress_repo: ProgressTrackingRepository = Depends(get_progress_tracking_repo),
    streak_repo: StreakRepository = Depends(get_streak_repo),
):
    """Mark a mission as skipped (no minutes/XP are credited)."""
    updated = repo.skip(mission_id, user_id)
    # Skipped missions are deliberately not logged into the ledger.
    _log_mission_session(updated, user_id, progress_repo)
    # Skipping still affects the perfect-day calculation, so re-run streaks.
    _process_streaks(user_id, updated.get("mission_date"), streak_repo)
    return updated

