"""
Repository for the Progress Tracking domain.

Backs the study_sessions (append-only ledger), daily_stats (per-day cached
aggregates) and progress_state (lifetime aggregate) tables. Derives XP level
from the gamification curve, computes current/longest streaks from daily
activity, and produces daily/weekly/monthly aggregates, chart series and a
recent-history feed — all stored in the database.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository

# ---------------------------------------------------------------------------
# Level curve (GAMIFICATION.md): level_n_required_xp = 100 * n^1.35
# ---------------------------------------------------------------------------
def _xp_for_level(level: int) -> int:
    return int(round(100 * (level ** 1.35) / 10.0) * 10)


def level_from_xp(xp: int) -> Dict[str, Any]:
    """Map a lifetime XP total to (current_level, progress-to-next)."""
    if xp <= 0:
        return {"level": 1, "level_progress": 0.0}

    level = 1
    while level < 100:
        threshold = _xp_for_level(level)
        if xp < threshold:
            break
        level += 1

    current_level = max(level - 1, 1)
    lower = _xp_for_level(current_level)
    upper = _xp_for_level(current_level + 1)
    progress = (xp - lower) / (upper - lower) if upper > lower else 1.0
    return {
        "level": current_level,
        "level_progress": round(max(0.0, min(progress, 1.0)), 2),
    }


def _today_has_activity(active_dates: set) -> bool:
    """Whether the supplied active dates set includes today."""
    return date.today() in active_dates


class ProgressTrackingRepository(BaseRepository):
    """Data access for the progress tracking tables."""

    table_name = "study_sessions"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Session logging (append-only, idempotent per source)
    # ------------------------------------------------------------------
    def log_session(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append a study session to the ledger.

        Idempotent when source_type+source_id are provided: if a session
        already exists for that (user, source_type, source_id), it returns
        the existing row instead of double-counting.
        """
        activity_date = data.get("activity_date") or date.today()
        if isinstance(activity_date, str):
            activity_date = date.fromisoformat(activity_date[:10])

        payload = {
            "user_id": user_id,
            "activity_date": activity_date.isoformat(),
            "skill": data.get("skill"),
            "session_type": data.get("session_type", "mission"),
            "minutes": int(data.get("minutes") or 0),
            "xp_earned": int(data.get("xp_earned") or 0),
            "source_type": data.get("source_type", "mission"),
            "source_id": data.get("source_id"),
            "meta": data.get("meta") or {},
        }

        # Idempotency key: (user_id, source_type, source_id).
        source_id = payload["source_id"]
        if source_id:
            existing = self._get_by_source(user_id, payload["source_type"], source_id)
            if existing:
                return existing

        query = self.db.table("study_sessions").insert(payload)
        result = self.db.execute(query, "log study session")
        if not result.data:
            raise NotFoundError("Failed to log study session")
        row = result.data[0]

        self._refresh_daily_stats(user_id, activity_date)
        self._refresh_progress_state(user_id)
        return row

    def _get_by_source(
        self, user_id: str, source_type: str, source_id: str
    ) -> Optional[Dict[str, Any]]:
        query = (
            self.db.table("study_sessions")
            .select("*")
            .eq("user_id", user_id)
            .eq("source_type", source_type)
            .eq("source_id", source_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch study session by source")
        if not result.data:
            return None
        return result.data[0]

    # ------------------------------------------------------------------
    # Derived aggregates (recomputed from the ledger)
    # ------------------------------------------------------------------
    def _refresh_daily_stats(self, user_id: str, day: date) -> None:
        """Recompute a user's daily_stats row from the study_sessions ledger."""
        query = (
            self.db.table("study_sessions")
            .select("minutes, xp_earned, source_type")
            .eq("user_id", user_id)
            .eq("activity_date", day.isoformat())
        )
        result = self.db.execute(query, "fetch sessions for day")
        rows = result.data or []

        minutes = sum(int(r.get("minutes") or 0) for r in rows)
        xp = sum(int(r.get("xp_earned") or 0) for r in rows)
        tasks = sum(
            1 for r in rows if r.get("source_type") in ("mission", "task")
        )
        is_active = minutes > 0 or xp > 0 or tasks > 0

        upsert = (
            self.db.table("daily_stats")
            .upsert(
                {
                    "user_id": user_id,
                    "stats_date": day.isoformat(),
                    "minutes": minutes,
                    "tasks_completed": tasks,
                    "xp_earned": xp,
                    "is_active": is_active,
                },
                on_conflict="user_id,stats_date",
            )
        )
        self.db.execute(upsert, "refresh daily stats")

    def _refresh_progress_state(self, user_id: str) -> None:
        """
        Recompute lifetime aggregates (total minutes/xp/tasks, level) and
        streak counters from the study_sessions + daily_stats tables.
        """
        ledger_query = (
            self.db.table("study_sessions")
            .select("minutes, xp_earned, source_type")
            .eq("user_id", user_id)
        )
        ledger_result = self.db.execute(ledger_query, "fetch lifetime ledger")
        rows = ledger_result.data or []
        total_minutes = sum(int(r.get("minutes") or 0) for r in rows)
        total_xp = sum(int(r.get("xp_earned") or 0) for r in rows)
        total_tasks = sum(
            1 for r in rows if r.get("source_type") in ("mission", "task")
        )

        level_info = level_from_xp(total_xp)

        # Streak: walk daily_stats backwards from today (with 1-day grace).
        stats_query = (
            self.db.table("daily_stats")
            .select("stats_date, is_active, minutes")
            .eq("user_id", user_id)
            .order("stats_date", desc=True)
            .limit(370)
        )
        stats_result = self.db.execute(stats_query, "fetch daily stats for streak")
        stats_rows = stats_result.data or []

        active_dates = {
            date.fromisoformat(r["stats_date"])
            for r in stats_rows
            if r.get("is_active") and int(r.get("minutes") or 0) > 0
        }

        current_streak = 0
        last_active_date = None
        cursor = date.today()

        # Grace: if today has no activity yet but yesterday did, the streak is
        # still alive (user may log a session later today).
        if not _today_has_activity(active_dates):
            if cursor - timedelta(days=1) in active_dates:
                cursor = cursor - timedelta(days=1)

        while cursor in active_dates:
            current_streak += 1
            last_active_date = cursor
            cursor -= timedelta(days=1)

        if last_active_date is None and active_dates:
            last_active_date = max(active_dates)

        # Longest streak over the available window.
        longest_streak = 0
        run = 0
        prev = None
        for d in sorted(active_dates):
            if prev is not None and (d - prev).days == 1:
                run += 1
            else:
                run = 1
            longest_streak = max(longest_streak, run)
            prev = d

        at_risk = False
        if last_active_date is not None:
            days_since = (date.today() - last_active_date).days
            at_risk = 0 < days_since <= 2

        upsert = (
            self.db.table("progress_state")
            .upsert(
                {
                    "user_id": user_id,
                    "total_minutes": total_minutes,
                    "total_tasks": total_tasks,
                    "total_xp": total_xp,
                    "level": level_info["level"],
                    "level_progress": level_info["level_progress"],
                    "current_streak": current_streak,
                    "longest_streak": max(longest_streak, current_streak),
                    "last_active_date": last_active_date.isoformat()
                    if last_active_date
                    else None,
                },
                on_conflict="user_id",
            )
        )
        self.db.execute(upsert, "refresh progress state")

    # ------------------------------------------------------------------
    # Reads (used by API + dashboard)
    # ------------------------------------------------------------------
    def get_state(self, user_id: str) -> Dict[str, Any]:
        """Fetch the cached progress_state row (or a zero default)."""
        query = (
            self.db.table("progress_state")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch progress state")
        if not result.data:
            return {
                "total_minutes": 0,
                "total_tasks": 0,
                "total_xp": 0,
                "level": 1,
                "level_progress": 0.0,
                "current_streak": 0,
                "longest_streak": 0,
                "last_active_date": None,
                "at_risk": False,
            }
        state = dict(result.data[0])
        # Compute at_risk on the fly.
        last = state.get("last_active_date")
        at_risk = False
        if last:
            try:
                last_d = date.fromisoformat(str(last)[:10])
                days_since = (date.today() - last_d).days
                at_risk = 0 < days_since <= 2
            except (ValueError, TypeError):
                at_risk = False
        state["at_risk"] = at_risk
        return state

    def get_day_stats(self, user_id: str, day: date) -> Dict[str, Any]:
        """Fetch a single day's stats (or zero default)."""
        query = (
            self.db.table("daily_stats")
            .select("*")
            .eq("user_id", user_id)
            .eq("stats_date", day.isoformat())
            .limit(1)
        )
        result = self.db.execute(query, "fetch day stats")
        if not result.data:
            return {
                "stats_date": day.isoformat(),
                "minutes": 0,
                "tasks_completed": 0,
                "xp_earned": 0,
                "is_active": False,
            }
        return result.data[0]

    def get_range_stats(
        self, user_id: str, start: date, end: date
    ) -> List[Dict[str, Any]]:
        """Fetch all daily stats within [start, end] (inclusive)."""
        query = (
            self.db.table("daily_stats")
            .select("*")
            .eq("user_id", user_id)
            .gte("stats_date", start.isoformat())
            .lte("stats_date", end.isoformat())
            .order("stats_date")
        )
        result = self.db.execute(query, "fetch range stats")
        return result.data or []

    def get_today_xp(self, user_id: str) -> int:
        """XP earned today (from the ledger)."""
        query = (
            self.db.table("study_sessions")
            .select("xp_earned")
            .eq("user_id", user_id)
            .eq("activity_date", date.today().isoformat())
        )
        result = self.db.execute(query, "fetch today xp")
        return sum(int(r.get("xp_earned") or 0) for r in (result.data or []))

    def get_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Most recent study-session entries (newest first)."""
        query = (
            self.db.table("study_sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "fetch study history")
        return result.data or []

    def get_charts(self, user_id: str) -> Dict[str, Any]:
        """Build chart series for the last 7 and 30 days, plus skill totals."""
        today = date.today()

        # 7-day series
        start7 = today - timedelta(days=6)
        stats7 = {r["stats_date"]: r for r in self.get_range_stats(user_id, start7, today)}
        daily_series = []
        for i in range(7):
            d = start7 + timedelta(days=i)
            row = stats7.get(d.isoformat(), {})
            daily_series.append({
                "date": d.isoformat(),
                "label": d.strftime("%a"),
                "minutes": int(row.get("minutes") or 0),
                "tasks": int(row.get("tasks_completed") or 0),
                "xp": int(row.get("xp_earned") or 0),
            })

        # 30-day series
        start30 = today - timedelta(days=29)
        stats30 = {r["stats_date"]: r for r in self.get_range_stats(user_id, start30, today)}
        monthly_series = []
        for i in range(30):
            d = start30 + timedelta(days=i)
            row = stats30.get(d.isoformat(), {})
            monthly_series.append({
                "date": d.isoformat(),
                "label": d.strftime("%d %b"),
                "minutes": int(row.get("minutes") or 0),
                "tasks": int(row.get("tasks_completed") or 0),
                "xp": int(row.get("xp_earned") or 0),
            })

        # Skill totals (lifetime minutes + tasks per skill)
        ledger_query = (
            self.db.table("study_sessions")
            .select("skill, minutes, source_type")
            .eq("user_id", user_id)
        )
        ledger_result = self.db.execute(ledger_query, "fetch ledger for skill totals")
        skill_totals: Dict[str, Dict[str, int]] = {}
        for r in ledger_result.data or []:
            skill = r.get("skill") or "general"
            entry = skill_totals.setdefault(skill, {"minutes": 0, "tasks": 0})
            entry["minutes"] += int(r.get("minutes") or 0)
            if r.get("source_type") in ("mission", "task"):
                entry["tasks"] += 1

        return {
            "daily_series": daily_series,
            "monthly_series": monthly_series,
            "skill_totals": skill_totals,
        }

    def get_period_progress(
        self,
        user_id: str,
        start: date,
        end: date,
        target_minutes: int = 0,
        target_tasks: int = 0,
    ) -> Dict[str, Any]:
        """Aggregate a period (day/week/month) from daily_stats rows."""
        rows = self.get_range_stats(user_id, start, end)
        minutes = sum(int(r.get("minutes") or 0) for r in rows)
        tasks = sum(int(r.get("tasks_completed") or 0) for r in rows)
        xp = sum(int(r.get("xp_earned") or 0) for r in rows)

        percent = 0
        if target_minutes > 0:
            percent = round((minutes / target_minutes) * 100)
        elif target_tasks > 0:
            percent = round((tasks / target_tasks) * 100)
        percent = max(0, min(percent, 100))

        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "minutes": minutes,
            "tasks_completed": tasks,
            "xp_earned": xp,
            "target_minutes": target_minutes,
            "target_tasks": target_tasks,
            "percent": percent,
        }

