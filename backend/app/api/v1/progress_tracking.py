"""
Progress Tracking endpoints.

Provides:
  - POST /overview          → daily/weekly/monthly progress + XP + streak
  - POST /log               → log a study session (idempotent per source)
  - GET  /charts            → 7-day + 30-day chart series + skill totals
  - GET  /history           → recent study-session history
All numbers are read from real stored data (study_sessions / daily_stats /
progress_state) — never client-side fabricated.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.api.deps import get_current_user, get_progress_tracking_repo, get_analytics_repo
from app.models.progress_tracking import (
    StudySessionCreate,
    StudySessionResponse,
    ProgressOverviewResponse,
    ChartsResponse,
    HistoryResponse,
    XPInfo,
    StreakInfo,
    DailyProgress,
    WeeklyProgress,
    MonthlyProgress,
)
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.analytics_repo import AnalyticsRepository

router = APIRouter()


@router.get(
    "/overview",
    response_model=ProgressOverviewResponse,
    summary="Get aggregated progress overview",
)
async def get_progress_overview(
    user_id: str = Depends(get_current_user),
    repo: ProgressTrackingRepository = Depends(get_progress_tracking_repo),
):
    """
    Aggregate the current user's progress:

    - XP today / lifetime + level from the XP curve
    - current & longest streak
    - study time today / week, budget, and goals
    - daily / weekly / monthly progress (% against user's budget)
    - lifetime totals
    """
    today = date.today()
    # Week: Monday-start.
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    # Month.
    month_start = today.replace(day=1)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    month_end = next_month - timedelta(days=1)

    state = repo.get_state(user_id)
    today_stats = repo.get_day_stats(user_id, today)
    week = repo.get_period_progress(user_id, week_start, week_end)
    month = repo.get_period_progress(user_id, month_start, month_end)
    today_xp = repo.get_today_xp(user_id)

    # Budget from user profile.
    user_query = (
        repo.db.table("users")
        .select("daily_minutes_budget")
        .eq("id", user_id)
        .limit(1)
    )
    user_result = repo.db.execute(user_query, "fetch user budget")
    budget = int(user_result.data[0].get("daily_minutes_budget") or 60) if user_result.data else 60
    weekly_target = budget * 7
    monthly_target = budget * 30

    daily = {
        "period_start": today.isoformat(),
        "period_end": today.isoformat(),
        "minutes": int(today_stats.get("minutes") or 0),
        "tasks_completed": int(today_stats.get("tasks_completed") or 0),
        "xp_earned": int(today_stats.get("xp_earned") or 0),
        "target_minutes": budget,
        "target_tasks": 6,  # six skill missions per day
        "percent": min(round((int(today_stats.get("minutes") or 0) / budget) * 100), 100) if budget > 0 else 0,
    }

    state_level = int(state.get("level") or 1)
    state_progress = float(state.get("level_progress") or 0.0)
    total_xp = int(state.get("total_xp") or 0)

    xp = XPInfo(
        today=today_xp,
        daily_target=100,
        level=state_level,
        level_progress=state_progress,
        total=total_xp,
        note="XP is earned by completing daily missions.",
    )

    streak = StreakInfo(
        current=int(state.get("current_streak") or 0),
        longest=int(state.get("longest_streak") or 0),
        at_risk=bool(state.get("at_risk")),
        last_active_date=state.get("last_active_date"),
        note=("Complete one mission today to protect your streak." if state.get("at_risk") else "Tracked from daily activity."),
    )

    return ProgressOverviewResponse(
        xp=xp,
        streak=streak,
        study_time={
            "today_minutes": int(today_stats.get("minutes") or 0),
            "week_minutes": week["minutes"],
            "budget_minutes": budget,
            "tracking_note": "Study minutes are tracked from completed missions.",
        },
        daily=DailyProgress(**daily),
        weekly=WeeklyProgress(**week, target_minutes=weekly_target, target_tasks=0),
        monthly=MonthlyProgress(**month, target_minutes=monthly_target, target_tasks=0),
        total_minutes=int(state.get("total_minutes") or 0),
        total_tasks=int(state.get("total_tasks") or 0),
        total_xp=total_xp,
    )


@router.post(
    "/log",
    response_model=StudySessionResponse,
    status_code=201,
    summary="Log a study session",
)
async def log_study_session(
    data: StudySessionCreate,
    user_id: str = Depends(get_current_user),
    repo: ProgressTrackingRepository = Depends(get_progress_tracking_repo),
    analytics_repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    """
    Append a study session to the ledger.

    Idempotent when `source_type` + `source_id` are provided: logging the
    same mission/source twice does not double-count minutes or XP.

    Also forwards the session to the analytics event ledger so study time
    and task completions feed the analytics dashboard.
    """
    payload = data.model_dump(exclude_none=True)
    result = repo.log_session(user_id, payload)

    # Track analytics (best-effort; do not fail the primary operation)
    try:
        analytics_repo.record_study_session(
            user_id=user_id,
            minutes=int(payload.get("minutes") or 0),
            skill=payload.get("skill"),
            source_type=payload.get("source_type", "task"),
            source_id=payload.get("source_id"),
        )
    except Exception:
        pass

    return result


@router.get(
    "/charts",
    response_model=ChartsResponse,
    summary="Get chart series for progress",
)
async def get_progress_charts(
    days: int = Query(30, ge=7, le=90),
    user_id: str = Depends(get_current_user),
    repo: ProgressTrackingRepository = Depends(get_progress_tracking_repo),
):
    """Return 7-day and 30-day series plus lifetime skill totals."""
    return ChartsResponse(**repo.get_charts(user_id))


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Get recent study history",
)
async def get_progress_history(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    repo: ProgressTrackingRepository = Depends(get_progress_tracking_repo),
):
    """Return the most recent study-session entries (newest first)."""
    rows = repo.get_history(user_id, limit)
    items = [
        {
            "id": r.get("id", ""),
            "date": r.get("activity_date") or r.get("created_at", "")[:10],
            "title": (r.get("meta") or {}).get("title") or r.get("session_type", "mission"),
            "skill": r.get("skill"),
            "session_type": r.get("session_type", "mission"),
            "minutes": int(r.get("minutes") or 0),
            "xp": int(r.get("xp_earned") or 0),
        }
        for r in rows
    ]
    return HistoryResponse(items=items)

