"""
Dashboard endpoints — aggregate overview data for the main dashboard.

Design principle: NO fake data. Values are read from real user rows and
existing tables where available. Features not yet implemented (XP engine,
streak engine, band prediction, mock scheduler, notifications service)
return neutral empty/null values instead of fabricated numbers, so the UI
can render honest empty states.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from app.db.supabase import supabase
from app.api.deps import get_current_user
from app.repositories.daily_mission_repo import DailyMissionRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository
from app.db.session import db_session
from app.services.diagnostic_roadmap_service import diagnostic_roadmap_service

router = APIRouter()


def _intensity(days_left: int) -> str:
    """Map remaining days to a preparation-intensity label."""
    if days_left < 14:
        return "final"
    if days_left < 30:
        return "intensive"
    if days_left < 60:
        return "focused"
    return "normal"


def _streak_detail_section(user_id: str) -> dict:
    """
    Build the detailed streak payload (daily/weekly/monthly, perfect-day,
    carry-forward, freezes, bonuses) for the dashboard overview.

    Delegates to the StreakRepository which owns the deterministic rules.
    Falls back to an honest empty state if the streak tables are missing.
    """
    try:
        repo = StreakRepository(db_session)
        return repo.get_overview(user_id)
    except Exception:
        return {
            "daily": {"current": 0, "longest": 0, "at_risk": False},
            "weekly": {"current": 0, "longest": 0, "at_risk": False},
            "monthly": {"current": 0, "longest": 0, "at_risk": False},
            "perfect_day": {"achieved": False, "perfect_day_count": 0},
            "carry_forward": {"bank_minutes": 0, "cap_minutes": 120},
            "freezes": {"available": 0, "used": 0, "can_use": False},
            "bonuses": {"total_bonus_xp": 0, "perfect_day_xp": 0, "milestone_xp": 0},
            "next_milestones": [],
            "history": [],
        }


def _daily_missions_section(user_id: str) -> dict:
    """
    Build the daily missions payload for the dashboard overview.

    Reads real rows from the daily_missions table (placeholder-generated)
    and aggregates them into a summary. Returns an honest empty state when
    no missions have been generated yet.
    """
    repo = DailyMissionRepository(db_session)
    today = date.today()
    missions = repo.list_for_date(user_id, today)
    summary = repo.get_summary(user_id, today)

    return {
        "mission_date": today.isoformat(),
        "missions": missions,
        "summary": summary,
        "generated": len(missions) > 0,
        "note": "Generate placeholder missions from the Daily Missions page."
        if len(missions) == 0
        else "Missions are placeholder-generated (no AI scheduling).",
    }


def _progress_tracking_section(user_id: str, daily_budget: int) -> dict:
    """
    Build the real progress-tracking payload (XP, streak, study time,
    daily/weekly/monthly goals, chart series, recent history) for the
    dashboard overview.

    All values are read from the study_sessions / daily_stats /
    progress_state tables via the ProgressTrackingRepository.
    """
    repo = ProgressTrackingRepository(db_session)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
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
    charts = repo.get_charts(user_id)
    history = repo.get_history(user_id, limit=10)

    weekly_target_minutes = daily_budget * 7
    monthly_target_minutes = daily_budget * 30

    return {
        "xp": {
            "today": today_xp,
            "daily_target": 100,
            "level": int(state.get("level") or 1),
            "level_progress": round(float(state.get("level_progress") or 0.0) * 100),
            "total": int(state.get("total_xp") or 0),
            "note": "XP is earned by completing daily missions.",
        },
        "streak": {
            "current": int(state.get("current_streak") or 0),
            "longest": int(state.get("longest_streak") or 0),
            "at_risk": bool(state.get("at_risk")),
            "last_active_date": state.get("last_active_date"),
            "note": "Streaks are built from daily study activity.",
        },
        "study_time": {
            "today_minutes": int(today_stats.get("minutes") or 0),
            "week_minutes": week["minutes"],
            "budget_minutes": daily_budget,
            "tracking_note": "Study minutes are tracked from completed missions.",
        },
        "daily": {
            "period_start": today.isoformat(),
            "period_end": today.isoformat(),
            "minutes": int(today_stats.get("minutes") or 0),
            "tasks_completed": int(today_stats.get("tasks_completed") or 0),
            "xp_earned": int(today_stats.get("xp_earned") or 0),
            "target_minutes": daily_budget,
            "target_tasks": 6,
            "percent": min(round((int(today_stats.get("minutes") or 0) / daily_budget) * 100), 100) if daily_budget > 0 else 0,
        },
        "weekly": {
            "period_start": week_start.isoformat(),
            "period_end": week_end.isoformat(),
            "minutes": week["minutes"],
            "tasks_completed": week["tasks_completed"],
            "xp_earned": week["xp_earned"],
            "target_minutes": weekly_target_minutes,
            "target_tasks": 0,
            "percent": week["percent"],
        },
        "monthly": {
            "period_start": month_start.isoformat(),
            "period_end": month_end.isoformat(),
            "minutes": month["minutes"],
            "tasks_completed": month["tasks_completed"],
            "xp_earned": month["xp_earned"],
            "target_minutes": monthly_target_minutes,
            "target_tasks": 0,
            "percent": month["percent"],
        },
        "charts": charts,
        "history": [
            {
                "id": r.get("id", ""),
                "date": r.get("activity_date") or (r.get("created_at") or "")[:10],
                "title": (r.get("meta") or {}).get("title") or r.get("session_type", "mission"),
                "skill": r.get("skill"),
                "session_type": r.get("session_type", "mission"),
                "minutes": int(r.get("minutes") or 0),
                "xp": int(r.get("xp_earned") or 0),
            }
            for r in history
        ],
        "total_minutes": int(state.get("total_minutes") or 0),
        "total_tasks": int(state.get("total_tasks") or 0),
        "total_xp": int(state.get("total_xp") or 0),
    }



def _safe_select(table: str, query) -> list:
    """Run a select and fall back to [] on any table/query error."""
    try:
        res = query.execute()
        return res.data or []
    except Exception:
        return []


def _safe_scalar(table: str, query):
    """Run a select expecting a single row and fall back to None on error."""
    try:
        res = query.execute()
        if res.data:
            return res.data[0]
        return None
    except Exception:
        return None


@router.get(
    "/overview",
    summary="Get aggregated dashboard overview",
    responses={
        200: {"description": "Dashboard overview returned"},
        401: {"description": "Not authenticated"},
    },
)
async def get_dashboard_overview(
    user_id: str = Depends(get_current_user),
):
    """Build the full dashboard payload from live user/roadmap/assessment data."""
    # ---------------------------------------------------------------
    # 1. User profile (exists)
    # ---------------------------------------------------------------
    user_row = _safe_scalar(
        "users",
        supabase.table("users").select("*").eq("id", user_id).limit(1),
    )
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    today = date.today()
    exam_date_raw = user_row.get("exam_date")
    exam_date = None
    days_left = None
    if exam_date_raw:
        try:
            exam_date = datetime.strptime(exam_date_raw[:10], "%Y-%m-%d").date()
            days_left = max((exam_date - today).days, 0)
        except (ValueError, TypeError):
            exam_date = None

    daily_budget = int(user_row.get("daily_minutes_budget") or 60)
    # Diagnostic-first band/profile signals (measured performance > manual).
    diag = diagnostic_roadmap_service.resolve_profile(user_id)
    current_band = diag.get("current_band") if diag.get("has_diagnostic") else user_row.get("current_band")
    target_band = diag.get("target_band") if diag.get("has_diagnostic") else user_row.get("target_band")
    full_name = user_row.get("full_name") or "Student"
    first_name = full_name.split(" ")[0] if full_name else "Student"

    # ---------------------------------------------------------------
    # 2. Active roadmap + today's tasks (real data if roadmap exists)
    # ---------------------------------------------------------------
    roadmap_rows = _safe_select(
        "roadmaps",
        supabase.table("roadmaps")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1),
    )

    mission_tasks = []
    has_plan = bool(roadmap_rows)
    roadmap_meta = (roadmap_rows[0].get("meta") or {}) if roadmap_rows else {}

    if roadmap_rows:
        roadmap_id = roadmap_rows[0]["id"]
        phase_rows = _safe_select(
            "roadmap_phases",
            supabase.table("roadmap_phases")
            .select("*")
            .eq("roadmap_id", roadmap_id)
            .order("order_index"),
        )
        # Pick the active phase (or first) to surface its pending tasks as
        # "today's recommended focus". Honors completion status honestly.
        active = next((p for p in phase_rows if p.get("status") == "active"), None)
        phase = active or (phase_rows[0] if phase_rows else None)
        if phase:
            task_rows = _safe_select(
                "roadmap_tasks",
                supabase.table("roadmap_tasks")
                .select("*")
                .eq("phase_id", phase["id"])
                .order("id"),
            )
            completed = 0
            for t in task_rows:
                done = t.get("status") == "completed"
                if done:
                    completed += 1
                mission_tasks.append({
                    "id": t.get("id", ""),
                    "title": t.get("title", "Untitled task"),
                    "skill": t.get("skill", "general"),
                    "duration_minutes": t.get("duration_minutes", 15),
                    "status": t.get("status", "pending"),
                    "completed": done,
                })
            # Snap summary counters
            mission_summary = {
                "has_plan": True,
                "phase_title": phase.get("title", ""),
                "phase_status": phase.get("status", "locked"),
                "total_tasks": len(mission_tasks),
                "completed_tasks": completed,
                "total_minutes": sum(t["duration_minutes"] for t in mission_tasks),
            }
        else:
            mission_summary = {"has_plan": True, "phase_title": "",
                               "phase_status": "locked", "total_tasks": 0,
                               "completed_tasks": 0, "total_minutes": 0}
    else:
        mission_summary = {"has_plan": False, "phase_title": "",
                           "phase_status": "", "total_tasks": 0,
                           "completed_tasks": 0, "total_minutes": 0}

    # ---------------------------------------------------------------
    # 3. Recent activity / assessments (real data if present)
    # ---------------------------------------------------------------
    recent_activity = []
    assessment_rows = _safe_select(
        "assessments",
        supabase.table("assessments")
        .select("id, task_type, band_score, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(5),
    )
    for a in assessment_rows:
        recent_activity.append({
            "type": "assessment",
            "title": a.get("task_type", "Assessment"),
            "meta": f"Band {a.get('band_score')}" if a.get("band_score") is not None else "Completed",
            "created_at": a.get("created_at"),
        })

    # ---------------------------------------------------------------
    # 4. Notifications (real data if table exists)
    # ---------------------------------------------------------------
    notification_rows = _safe_select(
        "notifications",
        supabase.table("notifications")
        .select("id, type, title, body, is_read, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(5),
    )
    unread_count = sum(1 for n in notification_rows if not n.get("is_read", False))
    notifications = [
        {
            "id": n.get("id", ""),
            "type": n.get("type", "system"),
            "title": n.get("title", ""),
            "body": n.get("body", ""),
            "is_read": n.get("is_read", False),
            "created_at": n.get("created_at"),
        }
        for n in notification_rows
    ]

    # ---------------------------------------------------------------
    # 5. Progress tracking (real stored data when available)
    # ---------------------------------------------------------------
    progress_tracking = _progress_tracking_section(user_id, daily_budget)

    # Daily / weekly goal targets come from the user's real budget.
    weekly_target_minutes = daily_budget * 7
    weekly_target_tasks = max(mission_summary["total_tasks"] * 7, 0) if has_plan else 0

    # Continue learning — derived from the first incomplete mission task.
    continue_learning = None
    for t in mission_tasks:
        if not t["completed"] and t["status"] != "completed":
            continue_learning = {
                "has_item": True,
                "title": t["title"],
                "type": t["skill"],
                "duration_minutes": t["duration_minutes"],
                "progress": None,  # draft/resume progress not tracked yet
            }
            break
    if continue_learning is None:
        continue_learning = {"has_item": False}

    # Motivational message — neutral greeting, not a fabricated stat.
    hour = datetime.now(timezone.utc).hour
    if hour < 12:
        greeting = f"Good morning, {first_name}!"
    elif hour < 18:
        greeting = f"Good afternoon, {first_name}!"
    else:
        greeting = f"Good evening, {first_name}!"

    if not has_plan:
        message_text = "Complete on onboarding to unlock your personalized study roadmap."
        message_type = "info"
    elif mission_summary["completed_tasks"] == mission_summary["total_tasks"] and mission_summary["total_tasks"] > 0:
        message_text = "All scheduled tasks complete. Consistency wins exams — you earned this!"
        message_type = "success"
    else:
        message_text = "Small consistent steps compound into big band gains. Stay the course."
        message_type = "motivation"

    payload = {
        "user": {
            "id": user_id,
            "full_name": full_name,
            "first_name": first_name,
        },
        "countdown": {
            "exam_date": exam_date.isoformat() if exam_date else None,
            "days_left": days_left,
            "intensity": _intensity(days_left) if days_left is not None else None,
            "exam_set": exam_date is not None,
        },
        "current_band": current_band,
        "target_band": target_band,
        "diagnostic_profile": {
            "has_diagnostic": diag.get("has_diagnostic", False),
            "source": diag.get("source", "default"),
            "attempt_id": diag.get("attempt_id"),
            "current_band": diag.get("current_band"),
            "target_band": diag.get("target_band"),
            "weakest_skills": diag.get("weakest_skills", []),
            "strongest_skills": diag.get("strongest_skills", []),
            "skill_bands": diag.get("skill_bands", {}),
            "focus_areas": diag.get("focus_areas", []),
        },
        "predicted_band": {
            "band": None,
            "trend": None,
            "confidence": None,
            "note": "Complete 2+ assessments to unlock your AI band prediction.",
        },
        "mission": {
            **mission_summary,
            "tasks": mission_tasks,
        },
        "progress": {
            "daily": {
                "tasks_completed": mission_summary["completed_tasks"],
                "tasks_target": mission_summary["total_tasks"],
                "percent": round((mission_summary["completed_tasks"] / mission_summary["total_tasks"]) * 100) if mission_summary["total_tasks"] > 0 else 0,
            },
            "weekly": {
                "target_minutes": weekly_target_minutes,
                "completed_minutes": 0,
                "percent": 0,
            },
        },
        "study_time": progress_tracking["study_time"],
        "xp": progress_tracking["xp"],
        "streak": progress_tracking["streak"],
        "streak_detail": _streak_detail_section(user_id),
        "daily_goal": {
            "target_minutes": daily_budget,
            "completed_minutes": progress_tracking["daily"]["minutes"],
            "percent": progress_tracking["daily"]["percent"],
        },
        "weekly_goal": {
            "target_minutes": weekly_target_minutes,
            "completed_minutes": progress_tracking["weekly"]["minutes"],
            "target_tasks": weekly_target_tasks,
            "completed_tasks": progress_tracking["weekly"]["tasks_completed"],
            "percent": progress_tracking["weekly"]["percent"],
        },
        "progress_monthly": progress_tracking["monthly"],
        "progress_charts": progress_tracking["charts"],
        "progress_history": progress_tracking["history"],
        "progress_totals": {
            "total_minutes": progress_tracking["total_minutes"],
            "total_tasks": progress_tracking["total_tasks"],
            "total_xp": progress_tracking["total_xp"],
        },
        "continue_learning": continue_learning,
        "upcoming_mock": {
            "has_mock": False,
            "note": "Mock tests are scheduled after Phase 2 of your roadmap.",
        },
        "recent_activity": recent_activity,
        "notifications": {
            "unread_count": unread_count,
            "items": notifications,
        },
        "daily_missions": _daily_missions_section(user_id),
        "message": {
            "greeting": greeting,
            "text": message_text,
            "type": message_type,
        },
    }

    return payload

