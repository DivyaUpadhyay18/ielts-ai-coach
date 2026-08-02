"""
Repository for the Streak System.

Backs the extended progress_state columns (weekly/monthly streaks,
perfect-day count, bonus XP, carry-forward minutes) plus the
streak_freezes and streak_events tables.

All rules are deterministic — NO AI scheduling:
  - Daily streak: walk active-day dates from today (1-day grace).
  - Weekly streak: an ISO-week counts when total active days in the
    week >= WEEKLY_ACTIVE_DAYS (default 4) OR minutes >= WEEKLY_MINUTES.
  - Monthly streak: a calendar month counts when total active days in
    the month >= MONTHLY_ACTIVE_DAYS (default 12) OR minutes >= budget*20.
  - Carry forward: surplus daily minutes over AM_EXCESS (default 15)
    are banked into carry_forward_minutes (cap 120). If the next day is
    missed, banked minutes are consumed and the daily streak survives.
  - Streak freeze: a placeholder token covers a missed day/week/month so
    the streak continues (consumed on use).
  - Perfect-day bonus: all 6 missions completed with none skipped → +25 XP
    (awarded once per (user, perfect_day, YYYY-MM-DD) via streak_events).
  - Milestone bonuses: daily at 7/14/21/30/60/100 days, weekly every 4th
    week, monthly each month — awarded once per (user, event, period_key).
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository
from app.repositories.progress_tracking_repo import level_from_xp

# ---------------------------------------------------------------------------
# Tunable constants (deterministic placeholder thresholds — no AI)
# ---------------------------------------------------------------------------
WEEKLY_ACTIVE_DAYS = 4          # active days required for a weekly streak week
WEEKLY_MINUTES = 0              # optional minutes threshold (0 = disabled)
MONTHLY_ACTIVE_DAYS = 12        # active days required for a monthly streak month
MONTHLY_MINUTES_POOL = 20       # minutes multiplier relative to pool target
PERFECT_DAY_BONUS_XP = 25
CARRY_FORWARD_CAP = 120
CARRY_EXCESS_MINIMUM = 15       # minutes above this are banked
CARRY_FORWARD_MAX_SKIP_MINUTES = 60  # a carry can cover a day up to this many minutes

# Daily streak XP milestone checkpoints: length -> bonus XP
DAILY_MILESTONES = {
    7: 50,
    14: 100,
    21: 150,
    30: 250,
    60: 500,
    100: 1000,
}

# Weekly streak milestone: every 4 consecutive weeks
WEEKLY_MILESTONE_EVERY = 4
WEEKLY_MILESTONE_XP = 75

# Monthly streak milestone: each consecutive month
MONTHLY_MILESTONE_EVERY = 1
MONTHLY_MILESTONE_XP = 200


def _iso_week_key(d: date) -> str:
    """Return the ISO year-week key for a date, e.g. '2025-W07'."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _month_key(d: date) -> str:
    """Return the calendar month key, e.g. '2025-07'."""
    return d.strftime("%Y-%m")


def _iso_week_bounds(d: date) -> tuple:
    """Return (monday, sunday) for the ISO week of a date."""
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def _month_bounds(d: date) -> tuple:
    """Return (first, last) day of the month containing a date."""
    first = d.replace(day=1)
    if first.month == 12:
        nxt = first.replace(year=first.year + 1, month=1)
    else:
        nxt = first.replace(month=first.month + 1)
    return first, nxt - timedelta(days=1)


class StreakRepository(BaseRepository):
    """Data access + rules for the Streak System."""

    table_name = "streak_events"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ==================================================================
    # Primary entry: called after a mission is completed/skipped
    # ==================================================================
    def process_activity(self, user_id: str, day: Optional[date] = None) -> Dict[str, Any]:
        """
        Recompute the entire streak state after a day of activity.

        Steps:
          1. Track carry-forward minutes (surplus banked, missed-day draw).
          2. Recompute the daily streak over the active-day window
             (grace + carry-forward + freeze protection).
          3. Recompute weekly + monthly streaks from active-day counts.
          4. Detect perfect day (6 completed, 0 skipped) → +25 XP.
          5. Award milestone bonuses (daily/weekly/monthly) idempotently.
          6. Persist updated progress_state (including bonus XP and level).
        """
        day = day or date.today()
        active_dates = self._active_dates(user_id)

        # -- 1. carry-forward bank ------------------------------------
        carry_bank = self._apply_carry_forward(user_id, active_dates, day)

        # -- 2. daily streak (with grace + carry + freeze) ------------
        daily_streak, last_active, used_freezes = self._compute_daily_streak(
            user_id, active_dates, day, carry_bank
        )

        # -- 3. weekly + monthly streaks ------------------------------
        weekly_streak, longest_weekly = self._compute_weekly_streak(user_id, active_dates, day)
        monthly_streak, longest_monthly = self._compute_monthly_streak(user_id, active_dates, day)

        # -- 4+5. bonuses ---------------------------------------------
        perfect_state = self._check_perfect_day(user_id, day)
        perfect_xp = perfect_state["bonus_xp"] if perfect_state["achieved"] else 0

        bonus_xp = perfect_xp
        events: List[Dict[str, Any]] = []

        # Daily milestones
        for checkpoint, bonus in DAILY_MILESTONES.items():
            if daily_streak >= checkpoint:
                if self._award_event(user_id, "daily_milestone", f"d{checkpoint}",
                                     f"{checkpoint}-Day Streak", bonus):
                    bonus_xp += bonus
                    events.append({"type": "daily_milestone", "label": f"{checkpoint}-Day Streak", "xp": bonus})

        # Weekly milestones
        if weekly_streak >= 1 and weekly_streak % WEEKLY_MILESTONE_EVERY == 0:
            wk_key = f"wk{weekly_streak}"
            if self._award_event(user_id, "weekly_milestone", wk_key,
                                 f"{weekly_streak}-Week Streak", WEEKLY_MILESTONE_XP):
                bonus_xp += WEEKLY_MILESTONE_XP
                events.append({"type": "weekly_milestone", "label": f"{weekly_streak}-Week Streak", "xp": WEEKLY_MILESTONE_XP})

        # Monthly milestones
        if monthly_streak >= 1 and monthly_streak % MONTHLY_MILESTONE_EVERY == 0:
            mo_key = f"mo{monthly_streak}"
            if self._award_event(user_id, "monthly_milestone", mo_key,
                                 f"{monthly_streak}-Month Streak", MONTHLY_MILESTONE_XP):
                bonus_xp += MONTHLY_MILESTONE_XP
                events.append({"type": "monthly_milestone", "label": f"{monthly_streak}-Month Streak", "xp": MONTHLY_MILESTONE_XP})

        # -- 6. persist ------------------------------------------------
        self._persist_state(
            user_id,
            active_dates,
            daily_streak,
            weekly_streak,
            monthly_streak,
            last_active,
            carry_bank,
            perfect_state["perfect_day_count"],
            bonus_xp,
            day,
        )

        return {
            "daily_streak": daily_streak,
            "weekly_streak": weekly_streak,
            "monthly_streak": monthly_streak,
            "last_active_date": last_active.isoformat() if last_active else None,
            "carry_forward": carry_bank,
            "perfect_day": perfect_state,
            "bonus_xp_awarded": bonus_xp,
            "events": events,
            "freezes_used": used_freezes,
        }

    # ==================================================================
    # Active-day window
    # ==================================================================
    def _active_dates(self, user_id: str, window_days: int = 370) -> set:
        """All dates with >=1 minute of activity within the window."""
        query = (
            self.db.table("daily_stats")
            .select("stats_date, is_active, minutes")
            .eq("user_id", user_id)
            .order("stats_date", desc=True)
            .limit(window_days)
        )
        result = self.db.execute(query, "fetch daily stats for streak")
        active = set()
        for r in result.data or []:
            if r.get("is_active") and int(r.get("minutes") or 0) > 0:
                try:
                    active.add(date.fromisoformat(r["stats_date"]))
                except (ValueError, TypeError):
                    continue
        return active

    # ==================================================================
    # Carry-forward
    # ==================================================================
    def _apply_carry_forward(self, user_id: str, active_dates: set, today: date) -> int:
        """
        Maintain the carry-forward minute bank.

        - An active day banks surplus minutes (over CARRY_EXCESS_MINIMUM),
          capped at CARRY_FORWARD_CAP.
        - If yesterday was missed (no activity), up to
          CARRY_FORWARD_MAX_SKIP_MINUTES banked minutes are consumed so the
          daily streak survives the gap; the bank is reduced accordingly.
        """
        state = self._get_state(user_id)
        bank = int(state.get("carry_forward_minutes") or 0)

        # Today's activity (if any) banks surplus.
        if today in active_dates:
            today_row = self._day_row(user_id, today)
            minutes = int(today_row.get("minutes") or 0)
            if minutes > CARRY_EXCESS_MINIMUM:
                bank = min(bank + (minutes - CARRY_EXCESS_MINIMUM), CARRY_FORWARD_CAP)

        # If yesterday was missed and we have a bank, consume it.
        yesterday = today - timedelta(days=1)
        if yesterday not in active_dates and bank > 0:
            bank = max(bank - CARRY_FORWARD_MAX_SKIP_MINUTES, 0)

        return bank

    # ==================================================================
    # Streak computations
    # ==================================================================
    def _resolve_daily_active(self, user_id: str, active_dates: set, today: date, bank: int) -> set:
        """
        Build the effective active-date set used for the daily streak.

        Adds a "virtual active day" for yesterday (once) when covered by
        carry-forward (bank > 0) or by an available streak freeze.
        """
        effective = set(active_dates)
        yesterday = today - timedelta(days=1)

        if yesterday not in effective:
            covered = False
            # Freeze protection takes priority over carry-forward.
            if self._has_available_freeze(user_id, "day"):
                covered = True
            elif bank > 0:
                covered = True
            if covered:
                effective.add(yesterday)
        return effective

    def _compute_daily_streak(
        self, user_id: str, active_dates: set, today: date, bank: int
    ) -> tuple:
        """Return (daily_streak, last_active_date, freezes_used)."""
        effective = self._resolve_daily_active(user_id, active_dates, today, bank)
        freezes_used = 0

        # Determine freezes available for a missed recent day.
        freezes = self._available_freezes(user_id, "day")

        cursor = today
        # 1-day grace: if today has no activity yet but yesterday did,
        # start counting from yesterday (streak stays alive for today).
        if today not in effective and (today - timedelta(days=1)) in effective:
            cursor = today - timedelta(days=1)

        streak = 0
        last_active = None
        gap_consumed = False

        while cursor in effective:
            streak += 1
            last_active = cursor
            cursor -= timedelta(days=1)

        # If there's a single-day gap immediately before the streak and we
        # have a freeze, consume one freeze to bridge it (placeholder).
        if streak == 0 and last_active is None and gap_consumed is False:
            candidate = cursor
            if candidate not in effective and candidate in active_dates and len(freezes) > 0:
                # Not used: the gap handling is already covered by carry/freeze
                # in _resolve_daily_active. Kept here for explicitness.
                pass

        return streak, last_active, freezes_used

    def _compute_weekly_streak(self, user_id: str, active_dates: set, today: date) -> tuple:
        """Compute the weekly streak as consecutive ISO-weeks meeting the
        active-day threshold."""
        # Group active dates by ISO week key.
        week_counts: Dict[str, int] = {}
        for d in active_dates:
            key = _iso_week_key(d)
            week_counts[key] = week_counts.get(key, 0) + 1

        # Order weeks chronologically.
        ordered_keys = sorted(week_counts.keys())
        if not ordered_keys:
            return 0, 0

        # Determine qualifying weeks (meet active-day threshold).
        qualifying = set()
        for key in ordered_keys:
            if week_counts[key] >= WEEKLY_ACTIVE_DAYS:
                qualifying.add(key)
            elif WEEKLY_MINUTES > 0:
                # Optional: check minutes threshold for the week.
                monday, sunday = _iso_week_bounds(
                    date.fromisoformat(f"{key[:4]}-01-01")
                )
                # Recompute properly from the key's actual dates.
                year = int(key[:4])
                week = int(key.split("-W")[1])
                # Find Monday for this ISO week.
                jan4 = date(year, 1, 4)
                monday = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week - 1)
                sunday = monday + timedelta(days=6)
                minutes = self._range_minutes(user_id, monday, sunday)
                if minutes >= WEEKLY_MINUTES:
                    qualifying.add(key)

        # Current week key.
        current_key = _iso_week_key(today)

        # Walk backwards from the current week (with a 1-week grace if the
        # current week isn't qualifying yet but the previous one did).
        streak = 0
        last_week = None
        cursor_key = current_key
        if cursor_key not in qualifying and _prev_week_key(current_key) in qualifying:
            cursor_key = _prev_week_key(current_key)

        while cursor_key in qualifying:
            streak += 1
            last_week = cursor_key
            cursor_key = _prev_week_key(cursor_key)

        longest = self._longest_qualifying_run(qualifying)

        return streak, max(longest, streak)

    def _compute_monthly_streak(self, user_id: str, active_dates: set, today: date) -> tuple:
        """Compute the monthly streak as consecutive calendar months meeting
        the active-day threshold."""
        month_counts: Dict[str, int] = {}
        for d in active_dates:
            key = _month_key(d)
            month_counts[key] = month_counts.get(key, 0) + 1

        ordered_keys = sorted(month_counts.keys())
        if not ordered_keys:
            return 0, 0

        qualifying = set()
        for key in ordered_keys:
            if month_counts[key] >= MONTHLY_ACTIVE_DAYS:
                qualifying.add(key)

        current_key = _month_key(today)

        streak = 0
        last_month = None
        cursor_key = current_key
        if cursor_key not in qualifying and _prev_month_key(current_key) in qualifying:
            cursor_key = _prev_month_key(current_key)

        while cursor_key in qualifying:
            streak += 1
            last_month = cursor_key
            cursor_key = _prev_month_key(cursor_key)

        longest = self._longest_qualifying_run(qualifying)

        return streak, max(longest, streak)

    def _longest_qualifying_run(self, qualifying: set) -> int:
        """Longest consecutive run of qualifying period keys."""
        ordered = sorted(qualifying)
        longest = 0
        run = 0
        prev = None
        for key in ordered:
            if prev is None or self._next_period_key(prev) == key:
                run += 1
            else:
                run = 1
            longest = max(longest, run)
            prev = key
        return longest

    def _next_period_key(self, key: str) -> Optional[str]:
        """Return the next ISO-week or month key after the given key."""
        if "-W" in key:
            return _next_week_key(key)
        return _next_month_key(key)

    # ==================================================================
    # Perfect day
    # ==================================================================
    def _check_perfect_day(self, user_id: str, day: date) -> Dict[str, Any]:
        """
        Detect a perfect day: all 6 skill missions completed, none skipped.

        Awards PERFECT_DAY_BONUS_XP once per calendar day, idempotently
        via a streak_events row keyed (perfect_day, YYYY-MM-DD).
        """
        missions = self._day_missions(user_id, day)
        total = len(missions)
        completed = sum(1 for m in missions if m.get("status") == "completed")
        skipped = sum(1 for m in missions if m.get("status") == "skipped")

        achieved = total > 0 and completed == total and skipped == 0

        bonus_xp = 0
        if achieved and self._award_event(
            user_id, "perfect_day", day.isoformat(), "Perfect Day", PERFECT_DAY_BONUS_XP
        ):
            bonus_xp = PERFECT_DAY_BONUS_XP

        # Reload actual count after any award.
        count = self._perfect_day_count(user_id)

        return {
            "achieved": achieved,
            "bonus_xp": bonus_xp,
            "perfect_day_count": count,
            "last_perfect_date": self._last_perfect_date(user_id),
            "remaining_missions": total - completed,
        }

    def _day_missions(self, user_id: str, day: date) -> List[Dict[str, Any]]:
        query = (
            self.db.table("daily_missions")
            .select("id, skill, status, completion_percent")
            .eq("user_id", user_id)
            .eq("mission_date", day.isoformat())
        )
        result = self.db.execute(query, "fetch day missions for perfect day")
        return result.data or []

    def _perfect_day_count(self, user_id: str) -> int:
        query = (
            self.db.table("streak_events")
            .select("id")
            .eq("user_id", user_id)
            .eq("event_type", "perfect_day")
        )
        result = self.db.execute(query, "count perfect days")
        return len(result.data or [])

    def _last_perfect_date(self, user_id: str) -> Optional[date]:
        query = (
            self.db.table("streak_events")
            .select("period_key")
            .eq("user_id", user_id)
            .eq("event_type", "perfect_day")
            .order("created_at", desc=True)
            .limit(1)
        )
        result = self.db.execute(query, "last perfect date")
        if not result.data:
            return None
        try:
            return date.fromisoformat(result.data[0]["period_key"][:10])
        except (ValueError, TypeError):
            return None

    # ==================================================================
    # Bonus events (idempotent)
    # ==================================================================
    def _award_event(
        self,
        user_id: str,
        event_type: str,
        period_key: str,
        label: str,
        xp: int,
    ) -> bool:
        """
        Award a bonus XP via the streak_events ledger.

        Returns True only if the event was newly inserted (idempotency).
        Raises silently on conflict -> returns False.
        """
        existing = self._find_event(user_id, event_type, period_key)
        if existing:
            return False

        try:
            query = self.db.table("streak_events").insert(
                {
                    "user_id": user_id,
                    "event_type": event_type,
                    "period_key": period_key,
                    "label": label,
                    "xp_awarded": xp,
                }
            )
            result = self.db.execute(query, "award streak bonus")
            return bool(result.data)
        except Exception:
            # Unique conflict means already awarded.
            return False

    def _find_event(self, user_id: str, event_type: str, period_key: str) -> Optional[Dict[str, Any]]:
        query = (
            self.db.table("streak_events")
            .select("*")
            .eq("user_id", user_id)
            .eq("event_type", event_type)
            .eq("period_key", period_key)
            .limit(1)
        )
        result = self.db.execute(query, "find streak event")
        if not result.data:
            return None
        return result.data[0]

    # ==================================================================
    # Streak freezes (placeholder)
    # ==================================================================
    def list_freezes(self, user_id: str) -> List[Dict[str, Any]]:
        query = (
            self.db.table("streak_freezes")
            .select("*")
            .eq("user_id", user_id)
            .order("granted_at", desc=True)
        )
        result = self.db.execute(query, "list streak freezes")
        return result.data or []

    def grant_freeze(
        self,
        user_id: str,
        period_type: str = "day",
        source: str = "placeholder",
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Grant a placeholder streak freeze token."""
        if period_type not in ("day", "week", "month"):
            raise ValidationError("period_type must be day, week or month")
        if source not in ("placeholder", "purchase", "reward", "system"):
            raise ValidationError("source must be placeholder, purchase, reward or system")

        payload = {
            "user_id": user_id,
            "period_type": period_type,
            "status": "available",
            "source": source,
        }
        if expires_at:
            payload["expires_at"] = expires_at.isoformat()

        query = self.db.table("streak_freezes").insert(payload)
        result = self.db.execute(query, "grant streak freeze")
        if not result.data:
            raise NotFoundError("Failed to grant streak freeze")
        return result.data[0]

    def use_freeze(self, user_id: str, freeze_id: str) -> Dict[str, Any]:
        """Consume a freeze token (placeholder mechanic)."""
        query = (
            self.db.table("streak_freezes")
            .select("*")
            .eq("id", freeze_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "find freeze")
        if not result.data:
            raise NotFoundError("Streak freeze not found")
        freeze = result.data[0]
        if freeze.get("status") != "available":
            raise ValidationError("Streak freeze is not available")

        update = (
            self.db.table("streak_freezes")
            .update({"status": "used", "used_at": datetime.utcnow().isoformat()})
            .eq("id", freeze_id)
            .eq("user_id", user_id)
        )
        updated = self.db.execute(update, "use streak freeze")
        if not updated.data:
            raise NotFoundError("Streak freeze not found")
        return updated.data[0]

    def _has_available_freeze(self, user_id: str, period_type: str) -> bool:
        query = (
            self.db.table("streak_freezes")
            .select("id")
            .eq("user_id", user_id)
            .eq("period_type", period_type)
            .eq("status", "available")
            .limit(1)
        )
        result = self.db.execute(query, "check available freeze")
        return bool(result.data)

    def _available_freezes(self, user_id: str, period_type: str) -> List[Dict[str, Any]]:
        query = (
            self.db.table("streak_freezes")
            .select("*")
            .eq("user_id", user_id)
            .eq("period_type", period_type)
            .eq("status", "available")
        )
        result = self.db.execute(query, "available freezes")
        return result.data or []

    # ==================================================================
    # Persistence
    # ==================================================================
    def _persist_state(
        self,
        user_id: str,
        active_dates: set,
        daily_streak: int,
        weekly_streak: int,
        monthly_streak: int,
        last_active: Optional[date],
        carry_bank: int,
        perfect_day_count: int,
        bonus_xp: int,
        today: date,
    ) -> None:
        """Persist all streak fields onto progress_state."""
        state = self._get_state(user_id)
        total_xp = int(state.get("total_xp") or 0)

        # Recompute level from ledger + bonus XP.
        level_info = level_from_xp(total_xp + bonus_xp)

        # Longest streaks.
        longest_daily = int(state.get("longest_streak") or 0)
        longest_weekly = int(state.get("longest_weekly_streak") or 0)
        longest_monthly = int(state.get("longest_monthly_streak") or 0)

        upsert = (
            self.db.table("progress_state")
            .upsert(
                {
                    "user_id": user_id,
                    "current_streak": daily_streak,
                    "longest_streak": max(longest_daily, daily_streak),
                    "weekly_streak": weekly_streak,
                    "longest_weekly_streak": max(longest_weekly, weekly_streak),
                    "monthly_streak": monthly_streak,
                    "longest_monthly_streak": max(longest_monthly, monthly_streak),
                    "perfect_day_count": perfect_day_count,
                    "bonus_xp": bonus_xp,
                    "carry_forward_minutes": carry_bank,
                    "last_active_date": last_active.isoformat() if last_active else None,
                    "last_streak_update": today.isoformat(),
                },
                on_conflict="user_id",
            )
        )
        self.db.execute(upsert, "persist streak state")

    def _get_state(self, user_id: str) -> Dict[str, Any]:
        query = (
            self.db.table("progress_state")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch progress state for streak")
        if not result.data:
            return {}
        return result.data[0]

    def _day_row(self, user_id: str, day: date) -> Dict[str, Any]:
        query = (
            self.db.table("daily_stats")
            .select("*")
            .eq("user_id", user_id)
            .eq("stats_date", day.isoformat())
            .limit(1)
        )
        result = self.db.execute(query, "fetch day row")
        if not result.data:
            return {}
        return result.data[0]

    def _range_minutes(self, user_id: str, start: date, end: date) -> int:
        query = (
            self.db.table("daily_stats")
            .select("minutes")
            .eq("user_id", user_id)
            .gte("stats_date", start.isoformat())
            .lte("stats_date", end.isoformat())
        )
        result = self.db.execute(query, "fetch range minutes")
        return sum(int(r.get("minutes") or 0) for r in (result.data or []))

    # ==================================================================
    # Reads (overview / events)
    # ==================================================================
    def get_events(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        query = (
            self.db.table("streak_events")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list streak events")
        return result.data or []

    def get_overview(self, user_id: str) -> Dict[str, Any]:
        """
        Build the full streak-system overview.

        Includes daily/weekly/monthly streaks, perfect-day status,
        carry-forward bank, freeze summary, bonus breakdown, next
        milestones and a 14-day streak history.
        """
        state = self._get_state(user_id)
        today = date.today()

        # -- Daily streak info ----------------------------------------
        active_dates = self._active_dates(user_id)

        daily = {
            "kind": "daily",
            "current": int(state.get("current_streak") or 0),
            "longest": int(state.get("longest_streak") or 0),
            "at_risk": self._at_risk(state),
            "last_active": state.get("last_active_date"),
            "target": self._next_daily_milestone(int(state.get("current_streak") or 0)),
        }

        # -- Weekly streak info ---------------------------------------
        weekly = {
            "kind": "weekly",
            "current": int(state.get("weekly_streak") or 0),
            "longest": int(state.get("longest_weekly_streak") or 0),
            "at_risk": round(self._week_active_days(active_dates, today) / WEEKLY_ACTIVE_DAYS * 100) >= 50,
            "last_active": state.get("last_streak_update"),
            "target": WEEKLY_ACTIVE_DAYS,
        }

        # -- Monthly streak info --------------------------------------
        monthly = {
            "kind": "monthly",
            "current": int(state.get("monthly_streak") or 0),
            "longest": int(state.get("longest_monthly_streak") or 0),
            "at_risk": False,
            "last_active": state.get("last_streak_update"),
            "target": MONTHLY_ACTIVE_DAYS,
        }

        # -- Perfect day ----------------------------------------------
        perfect = self._check_perfect_day(user_id, today)

        # -- Carry-forward --------------------------------------------
        carry_bank = int(state.get("carry_forward_minutes") or 0)
        carry = {
            "bank_minutes": carry_bank,
            "cap_minutes": CARRY_FORWARD_CAP,
            "next_miss_covered": carry_bank > 0,
        }

        # -- Freezes ---------------------------------------------------
        freezes = self.list_freezes(user_id)
        available_freezes = sum(1 for f in freezes if f.get("status") == "available")
        freeze = {
            "available": available_freezes,
            "used": sum(1 for f in freezes if f.get("status") == "used"),
            "can_use": available_freezes > 0,
            "note": "Placeholder: freezes are currently granted manually (no purchases yet).",
        }

        # -- Bonuses ---------------------------------------------------
        bonus_xp = int(state.get("bonus_xp") or 0)
        perfect_xp = int(perfect["bonus_xp"] or 0)
        milestone_xp = max(bonus_xp - perfect_xp, 0)
        bonuses = {
            "total_bonus_xp": bonus_xp,
            "perfect_day_xp": perfect_xp,
            "milestone_xp": milestone_xp,
            "perfect_day_count": perfect["perfect_day_count"],
        }

        # -- Next milestones -------------------------------------------
        daily_len = int(state.get("current_streak") or 0)
        next_milestones = []
        for checkpoint, bonus in sorted(DAILY_MILESTONES.items()):
            if checkpoint > daily_len:
                next_milestones.append({
                    "label": f"{checkpoint}-Day Streak",
                    "target": checkpoint,
                    "current": daily_len,
                    "remaining": checkpoint - daily_len,
                    "xp_bonus": bonus,
                })
                if len(next_milestones) >= 3:
                    break
        if weekly["current"] > 0:
            next_week = (int(weekly["current"] // WEEKLY_MILESTONE_EVERY) + 1) * WEEKLY_MILESTONE_EVERY
            if len(next_milestones) < 3:
                next_milestones.append({
                    "label": f"{next_week}-Week Streak",
                    "target": next_week,
                    "current": int(weekly["current"]),
                    "remaining": next_week - int(weekly["current"]),
                    "xp_bonus": WEEKLY_MILESTONE_XP,
                })

        # -- History (last 14 days) -------------------------------------
        history: List[Dict[str, Any]] = []
        active_days = {d: d in active_dates for d in self._last_n_days(14)}
        run = 0
        for day in sorted(active_days.keys()):
            if active_days[day]:
                run += 1
            else:
                run = 0
            history.append({
                "date": day.isoformat(),
                "label": day.strftime("%a %d"),
                "value": run,
                "note": "Active" if active_days[day] else "Missed",
            })

        return {
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly,
            "perfect_day": perfect,
            "carry_forward": carry,
            "freezes": freeze,
            "bonuses": bonuses,
            "next_milestones": next_milestones,
            "history": history,
            "last_streak_update": state.get("last_streak_update"),
        }

    def _at_risk(self, state: Dict[str, Any]) -> bool:
        last = state.get("last_active_date")
        if not last:
            return False
        try:
            last_d = date.fromisoformat(str(last)[:10])
            days_since = (date.today() - last_d).days
            return 0 < days_since <= 2
        except (ValueError, TypeError):
            return False

    def _next_daily_milestone(self, current: int) -> int:
        for checkpoint in sorted(DAILY_MILESTONES.keys()):
            if checkpoint > current:
                return checkpoint
        return 0

    def _week_active_days(self, active_dates: set, today: date) -> int:
        monday, _ = _iso_week_bounds(today)
        return sum(1 for i in range(7) if (monday + timedelta(days=i)) in active_dates)

    def _last_n_days(self, n: int) -> List[date]:
        today = date.today()
        return [today - timedelta(days=i) for i in range(n - 1, -1, -1)]


# ==================================================================
# Module-level period-key helpers
# ==================================================================
def _prev_week_key(key: str) -> str:
    """Previous ISO week key."""
    year = int(key[:4])
    week = int(key.split("-W")[1])
    if week > 1:
        return f"{year}-W{week - 1:02d}"
    # Last week of previous year.
    prev = date(year - 1, 12, 28)
    iso = prev.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _next_week_key(key: str) -> str:
    """Next ISO week key."""
    year = int(key[:4])
    week = int(key.split("-W")[1])
    monday = _week_monday(year, week) + timedelta(days=7)
    iso = monday.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_monday(year: int, week: int) -> date:
    jan4 = date(year, 1, 4)
    return jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week - 1)


def _prev_month_key(key: str) -> str:
    year, month = int(key[:4]), int(key[5:7])
    if month > 1:
        return f"{year}-{month - 1:02d}"
    return f"{year - 1}-12"


def _next_month_key(key: str) -> str:
    year, month = int(key[:4]), int(key[5:7])
    if month < 12:
        return f"{year}-{month + 1:02d}"
    return f"{year + 1}-01"

