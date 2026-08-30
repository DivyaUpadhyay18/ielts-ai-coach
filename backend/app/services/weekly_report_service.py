"""
Weekly AI Reports service.

Generates a deterministic (NO AI) weekly summary report for a user,
aggregating data from all downstream engines that the Diagnostic Test feeds:

  - Summary: high-level narrative of the week
  - Achievements: milestones unlocked (streak milestones, perfect days, etc.)
  - Weakest Skill: lowest band from band estimation / diagnostic
  - Strongest Skill: highest band
  - Hours Studied: total study minutes in the week / 60
  - Tasks Completed: number of completed tasks in the week
  - Streak: current daily streak
  - Consistency: active days / total days in week * 100
  - Estimated Band: blended current band + completion progress
  - Suggestions: actionable deterministic advice
  - Next Week's Focus: weakest skills prioritized

Data sources (all defensive — never raises if a table is missing):
  - User profile (current_band, target_band, daily_minutes_budget)
  - Band estimation (latest snapshot for skill bands)
  - Diagnostic roadmap service (resolve_profile for weakest/strongest)
  - Progress tracking (study sessions, daily stats, progress state)
  - Streak system (daily/weekly streaks, perfect days, milestones)
  - Task repository (completed tasks in date range)
  - Prediction engine (estimated band + readiness)
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.db.session import DatabaseSession
from app.models.diagnostic import DIAGNOSTIC_SECTIONS 
from app.repositories.band_estimation_repo import BandEstimationRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.repositories.weekly_report_repo import WeeklyReportRepository
from app.services.diagnostic_roadmap_service import DiagnosticRoadmapService, diagnostic_roadmap_service

logger = logging.getLogger(__name__)

# ISO weekday offset: Monday=0, Sunday=6
WEEK_LENGTH_DAYS = 7

# Skill labels for human-readable text.
SKILL_LABELS = {
    "reading": "Reading",
    "listening": "Listening",
    "writing": "Writing",
    "speaking": "Speaking",
    "vocabulary": "Lexical Resource",
    "grammar": "Grammatical Range",
}

# Minimum consistency threshold to avoid division by zero on short weeks.
MIN_DAYS_FOR_CONSISTENCY = 1


class WeeklyReportService:
    """Deterministic weekly AI report generator — no AI, all formulas documented."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.band_estimation_repo = BandEstimationRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)
        self.streak_repo = StreakRepository(db)
        self.task_repo = TaskRepository(db)
        self.repo = WeeklyReportRepository(db)

    # ─── Public API ────────────────────────────────────────────────────

    def generate_report(
        self,
        user_id: str,
        run_date: Optional[date] = None,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a weekly AI report for the week containing `run_date`.

        Returns the full report dict. The report is persisted to
        weekly_reports (upsert by week_start) and weekly_report_cache.
        """
        today = run_date or date.today()
        week_start, week_end = self._week_bounds(today)

        # Check for an existing report this week (idempotent by default).
        if not force_regenerate:
            existing = self.repo.get_by_week(user_id, week_start.isoformat())
            if existing:
                logger.info("reusing existing weekly report user=%s week=%s", user_id, week_start)
                return existing

        report = self._compute_report(user_id, week_start, week_end, today)

        # Persist.
        try:
            saved = self.repo.save_report(user_id, report)
            report["id"] = saved.get("id")
            report["version"] = saved.get("version", 1)
            self.repo.update_cache(user_id, report)
        except Exception as exc:
            logger.warning("weekly report save failed user=%s: %s", user_id, exc)

        logger.info(
            "weekly report generated user=%s week=%s band=%.1f tasks=%d hours=%.1f",
            user_id, week_start.isoformat(),
            report["estimated_band"], report["tasks_completed"],
            report["hours_studied"],
        )
        return report

    def get_latest_report(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the user's most recent weekly report (from cache)."""
        return self._safe_latest(user_id)

    def get_history(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """Return paginated history of weekly reports."""
        items = self._safe_list_history(user_id, limit, offset)
        total = self._safe_count_history(user_id)
        return {
            "items": [
                {
                    "id": row.get("id"),
                    "user_id": row.get("user_id"),
                    "week_start": row.get("week_start"),
                    "week_end": row.get("week_end"),
                    "generated_at": row.get("generated_at"),
                    "summary": (row.get("report_json") or {}).get("summary", ""),
                    "estimated_band": float((row.get("report_json") or {}).get("estimated_band") or 0),
                    "tasks_completed": int((row.get("report_json") or {}).get("tasks_completed") or 0),
                    "hours_studied": float((row.get("report_json") or {}).get("hours_studied") or 0),
                    "consistency": float((row.get("report_json") or {}).get("consistency") or 0),
                    "streak": int((row.get("report_json") or {}).get("streak") or 0),
                }
                for row in items
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # ─── Report Computation ────────────────────────────────────────────

    def _compute_report(
        self, user_id: str, week_start: date, week_end: date, today: date
    ) -> Dict[str, Any]:
        """Assemble the full report dict from all data sources."""
        user = self._safe_get_profile(user_id) or {}
        current_band = float(user.get("current_band") or 5.0)
        target_band = float(user.get("target_band") or (current_band + 1.0))
        exam_date_raw = user.get("exam_date")
        exam_date = self._parse_date(exam_date_raw) if exam_date_raw else None
        days_remaining = max((exam_date - today).days, 0) if exam_date else None
        daily_budget = int(user.get("daily_minutes_budget") or 60)

        # ── Diagnostic-first profile signals ──
        diag_profile = self._safe_resolve_profile(user_id)
        diag_bands = diag_profile.get("skill_bands", {})
        if diag_profile.get("has_diagnostic"):
            current_band = diag_profile.get("current_band", current_band)
            target_band = diag_profile.get("target_band", target_band)

        # ── Band estimation (latest snapshot) ──
        latest_estimation = self._safe_get_latest_band_estimation(user_id)
        skill_bands = {}
        weakest_skill = None
        strongest_skill = None
        if latest_estimation:
            skill_bands = latest_estimation.get("skill_bands", {})
            weakest_list = latest_estimation.get("weakest_skills", [])
            strongest_list = latest_estimation.get("strongest_skills", [])
            weakest_skill = weakest_list[0] if weakest_list else None
            strongest_skill = strongest_list[0] if strongest_list else None

        # Fallback: derive from diagnostic if no band estimation exists.
        if not skill_bands:
            skill_bands = diag_bands
            if diag_bands:
                ordered = sorted(skill_bands.items(), key=lambda kv: kv[1])
                weakest_skill = ordered[0][0] if ordered else None
                strongest_skill = ordered[-1][0] if ordered else None

        # ── Study hours & tasks completed (from progress tracking) ──
        week_stats = self.progress_repo.get_range_stats(user_id, week_start, week_end)
        hours_studied = round(sum(int(s.get("minutes") or 0) for s in week_stats) / 60.0, 1)
        tasks_completed = sum(int(s.get("tasks_completed") or 0) for s in week_stats)

        # ── Streak & consistency ──
        streak_overview = self._safe_get_streak_overview(user_id)
        daily_streak = streak_overview.get("daily", {}).get("current", 0)
        active_dates = self._safe_get_active_dates(user_id)
        week_active_days = sum(
            1 for d in range(WEEK_LENGTH_DAYS)
            if (week_start + timedelta(days=d)) in active_dates
        )
        consistency = self._compute_consistency(week_active_days)

        # ── Estimated band ──
        estimated_band = self._compute_estimated_band(
            current_band, target_band, tasks_completed, daily_budget,
            week_start, today, diag_profile
        )

        # ── Achievements ──
        achievements = self._compute_achievements(
            user_id, streak_overview, tasks_completed, week_stats
        )

        # ── Previous week band ──
        prev_report = self._safe_get_by_week(
            user_id, (week_start - timedelta(weeks=1)).isoformat()
        )
        prev_week_band = None
        if prev_report:
            prev_week_band = float((prev_report.get("report_json") or {}).get("estimated_band") or 0)

        # ── Suggestions + next week focus ──
        suggestions = self._compute_suggestions(
            current_band, target_band, tasks_completed, daily_budget,
            hours_studied, consistency, days_remaining, estimated_band,
            skill_bands, weakest_skill
        )

        next_week_focus = self._compute_next_week_focus(skill_bands, weakest_skill)

        # ── Summary ──
        summary = self._build_summary(
            week_start, week_end, current_band, estimated_band,
            hours_studied, tasks_completed, consistency, daily_streak
        )

        # ── Formulas documentation ──
        formulas = self._build_formulas()

        # ── Metrics ──
        metrics = {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "current_band": current_band,
            "target_band": target_band,
            "days_remaining": days_remaining,
            "daily_budget_minutes": daily_budget,
            "task_target": daily_budget * WEEK_LENGTH_DAYS // 45,
            "active_days_in_week": week_active_days,
            "total_days_in_week": WEEK_LENGTH_DAYS,
            "daily_streak": daily_streak,
            "longest_streak": streak_overview.get("daily", {}).get("longest", 0),
            "weekly_streak": streak_overview.get("weekly", {}).get("current", 0),
            "monthly_streak": streak_overview.get("monthly", {}).get("current", 0),
            "perfect_day_count": streak_overview.get("bonuses", {}).get("perfect_day_count", 0),
            "total_xp": streak_overview.get("bonuses", {}).get("total_bonus_xp", 0),
            "has_diagnostic": diag_profile.get("has_diagnostic", False),
            "diagnostic_source": diag_profile.get("source", "default"),
            "skill_bands": skill_bands,
            "weakest_skills": diag_profile.get("weakest_skills", []) or [],
            "strongest_skills": diag_profile.get("strongest_skills", []) or [],
        }

        return {
            "user_id": user_id,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
            "summary": summary,
            "achievements": achievements,
            "weakest_skill": SKILL_LABELS.get(weakest_skill, weakest_skill or "N/A") if weakest_skill else None,
            "weakest_skill_key": weakest_skill,
            "strongest_skill": SKILL_LABELS.get(strongest_skill, strongest_skill or "N/A") if strongest_skill else None,
            "strongest_skill_key": strongest_skill,
            "hours_studied": hours_studied,
            "tasks_completed": tasks_completed,
            "streak": daily_streak,
            "consistency": consistency,
            "estimated_band": estimated_band,
            "suggestions": suggestions,
            "next_week_focus": next_week_focus,
            "metrics": metrics,
            "formulas": formulas,
            "previous_week_band": prev_week_band,
            "previous_report": {
                "week_start": prev_report.get("week_start") if prev_report else None,
                "estimated_band": prev_week_band,
                "tasks_completed": (prev_report.get("report_json") or {}).get("tasks_completed") if prev_report else None,
            } if prev_report else None,
        }

    # ─── Metric computations (pure, deterministic) ─────────────────────

    @staticmethod
    def _week_bounds(today: date) -> tuple:
        """Return (monday, sunday) for the ISO week of `today`."""
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=WEEK_LENGTH_DAYS - 1)
        return monday, sunday

    @staticmethod
    def _compute_consistency(week_active_days: int) -> float:
        """
        Consistency = (active_days / 7) * 100, rounded to 1 decimal.
        Clamped to [0, 100].
        """
        return round((week_active_days / WEEK_LENGTH_DAYS) * 100, 1)

    @staticmethod
    def _compute_estimated_band(
        current_band: float,
        target_band: float,
        tasks_completed: int,
        daily_budget: int,
        week_start: date,
        today: date,
        diag_profile: Dict[str, Any],
    ) -> float:
        """
        Estimate the user's band at the current point in time.

        Formula:
          days_since_start = max(0, (today - week_start).days)
          total_planned_tasks = daily_budget * days_since_start / 45
          completion_ratio = tasks_completed / total_planned_tasks (if > 0)
          progress = min(completion_ratio, 1.0)
          estimated = current_band + (target_band - current_band) * progress
          rounded to nearest 0.5, clamped to [0, 9]
        """
        days_since_start = max(0, (today - week_start).days)
        if days_since_start == 0:
            days_since_start = WEEK_LENGTH_DAYS

        total_planned = (daily_budget * days_since_start) / 45.0
        if total_planned > 0:
            progress = min(tasks_completed / total_planned, 1.0)
        else:
            progress = 0.0

        band_gap = max(target_band - current_band, 0.0)
        estimated = current_band + band_gap * progress
        estimated = round(estimated * 2) / 2
        return max(0.0, min(9.0, estimated))

    @staticmethod
    def _compute_achievements(
        user_id: str,
        streak_overview: Dict[str, Any],
        tasks_completed: int,
        week_stats: List[Dict[str, Any]],
    ) -> List[str]:
        """Derive deterministic achievements unlocked during the week."""
        achievements: List[str] = []

        daily_streak = streak_overview.get("daily", {}).get("current", 0)
        weekly_streak = streak_overview.get("weekly", {}).get("current", 0)
        monthly_streak = streak_overview.get("monthly", {}).get("current", 0)
        perfect_day_count = streak_overview.get("bonuses", {}).get("perfect_day_count", 0)
        bonus_xp = streak_overview.get("bonuses", {}).get("total_bonus_xp", 0)

        if daily_streak >= 7:
            achievements.append(f"Daily streak milestone: {daily_streak} days")
        if weekly_streak >= 4:
            achievements.append(f"Weekly streak milestone: {weekly_streak} weeks")
        if monthly_streak >= 1:
            achievements.append(f"Monthly streak: {monthly_streak} month(s) strong")
        if perfect_day_count > 0:
            achievements.append(f"Perfect day x{perfect_day_count} — all missions completed")
        if bonus_xp > 0:
            achievements.append(f"Bonus XP earned: {bonus_xp}")
        if tasks_completed >= 35:
            achievements.append(f"High productivity: {tasks_completed} tasks this week")
        elif tasks_completed >= 14:
            achievements.append(f"Consistent learner: {tasks_completed} tasks completed")
        if tasks_completed > 0:
            total_minutes = sum(int(s.get("minutes") or 0) for s in week_stats)
            if total_minutes >= 500:
                achievements.append(f"Deep focus: {total_minutes} minutes studied")

        if not achievements:
            achievements.append("Keep going — your next milestone is around the corner!")

        return achievements

    @staticmethod
    def _compute_suggestions(
        current_band: float,
        target_band: float,
        tasks_completed: int,
        daily_budget: int,
        hours_studied: float,
        consistency: float,
        days_remaining: Optional[int],
        estimated_band: float,
        skill_bands: Dict[str, float],
        weakest_skill: Optional[str],
    ) -> List[str]:
        """Generate deterministic, actionable suggestions."""
        recs: List[str] = []

        # Band gap guidance
        gap = target_band - current_band
        if gap >= 2.0:
            recs.append(
                f"Your target band ({target_band}) is {gap:.1f} above your current ({current_band}). "
                "Focus intensively on weak skills for the next 4 weeks."
            )
        elif gap >= 1.0:
            recs.append(
                f"Gap of {gap:.1f} band to target. Continue targeting weak skills consistently."
            )
        else:
            recs.append(
                f"You are close to your target ({target_band}). Focus on exam technique and mock tests."
            )

        # Task volume
        target_tasks = daily_budget * WEEK_LENGTH_DAYS // 45
        if tasks_completed < target_tasks * 0.5:
            recs.append(
                f"You completed {tasks_completed} tasks vs. {target_tasks} target. "
                "Aim for at least 5 tasks per study day to stay on track."
            )
        elif tasks_completed >= target_tasks:
            recs.append(
                f"Excellent task completion ({tasks_completed}/{target_tasks}). "
                "Maintain this pace and add full mock tests."
            )

        # Consistency
        if consistency < 50:
            recs.append(
                f"Consistency is {consistency:.0f}%. Try studying at the same time daily "
                "to build a stronger habit."
            )
        elif consistency < 80:
            recs.append(
                f"Good consistency ({consistency:.0f}%). Push for daily activity to reach 90%+."
            )

        # Hours
        if hours_studied < daily_budget * WEEK_LENGTH_DAYS / 60 * 0.5:
            recs.append(
                f"You studied {hours_studied}h this week. Aim for at least "
                f"{(daily_budget * WEEK_LENGTH_DAYS / 60 * 0.5):.1f}h per week."
            )

        # Exam date proximity
        if days_remaining is not None:
            if days_remaining < 14:
                recs.append("Less than 2 weeks left — shift to final revision and timed mocks.")
            elif days_remaining < 30:
                recs.append("Less than a month — intensify daily practice and mock tests.")

        # Weak skill focus
        if weakest_skill and weakest_skill in skill_bands:
            weak_band = skill_bands[weakest_skill]
            label = SKILL_LABELS.get(weakest_skill, weakest_skill)
            recs.append(
                f"Your weakest skill is {label} (band {weak_band}). "
                "Allocate 30% of study time to this area next week."
            )

        return recs

    @staticmethod
    def _compute_next_week_focus(skill_bands: Dict[str, float]) -> List[str]:
        """Derive next week's focus skills from the lowest bands."""
        if not skill_bands:
            return ["Maintain balanced practice across all skills."]

        ordered = sorted(skill_bands.items(), key=lambda kv: kv[1])
        focus = []
        for skill, band in ordered[:3]:
            label = SKILL_LABELS.get(skill, skill)
            if band < 6.0:
                focus.append(f"Build fundamentals — {label} (band {band})")
            elif band < 7.0:
                focus.append(f"Target improvement — {label} (band {band})")
            else:
                focus.append(f"Maintain polish — {label} (band {band})")

        return focus if focus else ["Maintain balanced practice across all skills."]

    @staticmethod
    def _build_summary(
        week_start: date,
        week_end: date,
        current_band: float,
        estimated_band: float,
        hours_studied: float,
        tasks_completed: int,
        consistency: float,
        daily_streak: int,
    ) -> str:
        """Generate a deterministic narrative summary of the week."""
        month_day = week_start.strftime("%b %d")
        end_month_day = week_end.strftime("%b %d")

        if tasks_completed == 0:
            return (
                f"Week of {month_day}–{end_month_day}: No tasks completed this week. "
                "Restart your study routine to build momentum."
            )

        progress = "ahead of" if estimated_band > current_band else "on track with"
        band_delta = round(estimated_band - current_band, 1)

        return (
            f"Week of {month_day}–{end_month_day}: You studied {hours_studied:.1f} hours, "
            f"completed {tasks_completed} tasks, and maintained a {daily_streak}-day streak. "
            f"Your estimated band is {estimated_band:.1f} ({progress} your current {current_band:.1f} "
            f"by {band_delta:+.1f}). Consistency: {consistency:.0f}%."
        )

    @staticmethod
    def _build_formulas() -> Dict[str, str]:
        """Document all formulas used in this report."""
        return {
            "consistency": (
                "consistency = (active_days_in_week / 7) * 100. "
                "active_days = days with >=1 minute of study activity."
            ),
            "estimated_band": (
                "estimated = current_band + (target_band - current_band) * progress, "
                "where progress = tasks_completed / (daily_budget * days_since_start / 45), "
                "clamped to [0, 1]. Rounded to nearest 0.5, clamped to [0, 9]."
            ),
            "weakest_skill": (
                "The skill with the lowest band score from the Band Estimation Engine "
                "or diagnostic results. Falls back to diagnostic profile weakest skills."
            ),
            "strongest_skill": (
                "The skill with the highest band score from the Band Estimation Engine "
                "or diagnostic results."
            ),
            "hours_studied": (
                "Sum of daily study minutes in the week (from daily_stats), divided by 60."
            ),
            "tasks_completed": (
                "Sum of tasks_completed across all daily_stats rows in the week."
            ),
            "streak": (
                "Current daily streak from the progress_state / streak system. "
                "Includes 1-day grace and carry-forward minute bank."
            ),
            "next_week_focus": (
                "Top 3 skills sorted by lowest band. Skills < 6.0 are 'fundamentals', "
                "6.0–7.0 are 'improvement', >= 7.0 are 'maintenance'."
            ),
        }

    # ─── Safe DB wrappers ──────────────────────────────────────────────

    def _safe_resolve_profile(self, user_id: str) -> Dict[str, Any]:
        if self.db is None:
            return {}
        try:
            return diagnostic_roadmap_service.resolve_profile(user_id)
        except Exception:
            return {}

    def _safe_get_latest_band_estimation(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.band_estimation_repo.get_latest(user_id)
        except Exception:
            return None

    def _safe_get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.user_repo.get_profile(user_id)
        except Exception:
            return None

    def _safe_get_streak_overview(self, user_id: str) -> Dict[str, Any]:
        if self.db is None:
            return {}
        try:
            return self.streak_repo.get_overview(user_id)
        except Exception:
            return {
                "daily": {"current": 0, "longest": 0},
                "weekly": {"current": 0, "longest": 0},
                "monthly": {"current": 0, "longest": 0},
                "bonuses": {"total_bonus_xp": 0, "perfect_day_count": 0},
            }

    def _safe_get_active_dates(self, user_id: str) -> set:
        """Fetch the set of active dates from daily_stats."""
        if self.db is None:
            return set()
        query = (
            self.db.table("daily_stats")
            .select("stats_date")
            .eq("user_id", user_id)
            .eq("is_active", True)
        )
        result = self.db.execute(query, "fetch active dates for weekly report")
        active = set()
        for r in result.data or []:
            try:
                active.add(date.fromisoformat(r["stats_date"]))
            except (ValueError, TypeError):
                continue
        return active

    def _safe_get_by_week(self, user_id: str, week_start: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.repo.get_by_week(user_id, week_start)
        except Exception:
            return None

    def _safe_latest(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.repo.get_latest(user_id)
        except Exception:
            return None

    def _safe_list_history(self, user_id: str, limit: int, offset: int) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.repo.list_history(user_id, limit=limit, offset=offset)
        except Exception:
            return []

    def _safe_count_history(self, user_id: str) -> int:
        if self.db is None:
            return 0
        try:
            return self.repo.count_history(user_id)
        except Exception:
            return 0

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return datetime.fromisoformat(str(value)[:10]).date()
        except (ValueError, TypeError):
            return None


# Singleton bound to the shared DB session.
from app.db.session import db_session

weekly_report_service = WeeklyReportService(db_session)
