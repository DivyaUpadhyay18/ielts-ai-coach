"""
AI Recommendations service.

Generates deterministic (NO AI) personalized recommendations covering six
categories, all derived from real user data:

  1. Study Order       — which skills to tackle first, based on band gap
                          and remaining time.
  2. Revision Priorities — which topics within weak skills need review.
  3. Extra Practice    — targeted practice recommendations per weak skill.
  4. Additional Resources — resource recommendations pulled from the
                             Resource Recommendation Engine.
  5. Break Suggestions  — when to take breaks based on study load.
  6. Time Management    — daily budget allocation and scheduling tips.

Data sources (all defensive — never raises if a table is missing):
  - User profile (current_band, target_band, exam_date, daily_minutes_budget)
  - Diagnostic / Band Estimation (weakest/strongest skills, skill bands)
  - Progress Tracking (study minutes, tasks, streak, daily stats)
  - Streak System (daily/weekly streaks, perfect days)
  - Prediction Engine (estimated band, readiness score, risk level, days remaining)
  - Resource Recommendation Engine (for additional resources)
  - Study Plan (active plan, daily plan tasks)

All formulas are documented inline and in the report's `formulas` field.
Reports are stored in the `ai_recommendations` table (one per user per day,
upserted).
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.band_estimation_repo import BandEstimationRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository
from app.repositories.user_repo import UserRepository
from app.services.diagnostic_roadmap_service import DiagnosticRoadmapService, diagnostic_roadmap_service
from app.services.prediction_engine import PredictionEngineService, prediction_engine_service
from app.services.recommendation_engine_service import RecommendationEngineService, recommendation_engine_service

logger = logging.getLogger(__name__)

# Skill labels for human-readable output.
SKILL_LABELS = {
    "reading": "Reading",
    "listening": "Listening",
    "writing": "Writing",
    "speaking": "Speaking",
    "vocabulary": "Lexical Resource",
    "grammar": "Grammatical Range",
}

# Skill categories for study ordering.
SKILL_ORDER_HIGH_PRIORITY = ["writing", "speaking"]  # production skills — harder to improve
SKILL_ORDER_MID_PRIORITY = ["reading", "listening"]
SKILL_ORDER_LOW_PRIORITY = ["vocabulary", "grammar"]  # supporting skills

# IELTS band step.
BAND_STEP = 0.5

# ISO weekday offset: Monday=0, Sunday=6
WEEK_LENGTH_DAYS = 7


class AiRecommendationsService:
    """
    Deterministic AI Recommendations service.

    Generates personalized recommendations based on real user data — no hallucinations.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.band_estimation_repo = BandEstimationRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)
        self.streak_repo = StreakRepository(db)

    # ─── Week utilities ─────────────────────────────────────────────────

    @staticmethod
    def _week_bounds(today: date) -> tuple:
        """Return (monday, sunday) for the ISO week of `today`."""
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=WEEK_LENGTH_DAYS - 1)
        return monday, sunday

    @staticmethod
    def _compute_consistency(week_active_days: int) -> float:
        """Consistency = (active_days / 7) * 100, rounded to 1 decimal."""
        return round((week_active_days / WEEK_LENGTH_DAYS) * 100, 1)

    # ─── Public API ────────────────────────────────────────────────────

    def get_recommendations(
        self,
        user_id: str,
        run_date: Optional[date] = None,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate the full AI recommendations payload for a user.

        Returns a dict matching AIRecommendationsResponse. Persists to
        the ai_recommendations table (upsert by user_id + run_date).
        """
        today = run_date or date.today()

        # Check for existing report today (idempotent by default).
        if not force_regenerate:
            existing = self._safe_get_cached(user_id, today)
            if existing:
                return existing

        # ─── 1. Gather all user context ────────────────────────────────
        profile = self._safe_get_profile(user_id) or {}

        current_band = float(profile.get("current_band") or 5.0)
        target_band = float(profile.get("target_band") or 6.5)
        if target_band < current_band:
            target_band = min(9.0, current_band + 1.0)

        exam_date_raw = profile.get("exam_date")
        exam_date = self._parse_date(exam_date_raw) if exam_date_raw else None
        days_remaining = max((exam_date - today).days, 0) if exam_date else None
        daily_budget = int(profile.get("daily_minutes_budget") or 60)

        # Diagnostic-first signals.
        diag = self._safe_resolve_profile(user_id)
        if diag.get("has_diagnostic"):
            current_band = float(diag.get("current_band") or current_band)
            target_band = float(diag.get("target_band") or target_band)

        skill_bands = self._unsafe_get_skill_bands(user_id, diag)
        weakest_skills, strongest_skills = self._derive_weak_strong(skill_bands, diag)

        # Progress data.
        state = self._safe_get_progress_state(user_id)
        total_minutes = int(state.get("total_minutes") or 0)
        total_tasks = int(state.get("total_tasks") or 0)
        current_streak = int(state.get("current_streak") or 0)
        level = int(state.get("level") or 1)

        # Study history for the past 7 days.
        week_start, week_end = self._week_bounds(today)
        week_stats = self.progress_repo.get_range_stats(user_id, week_start, today)
        week_minutes = sum(int(s.get("minutes") or 0) for s in week_stats)
        week_tasks = sum(int(s.get("tasks_completed") or 0) for s in week_stats)
        active_days = sum(1 for s in week_stats if int(s.get("minutes") or 0) > 0)

        # Streak overview.
        streak_overview = self._safe_get_streak_overview(user_id)
        weekly_streak = streak_overview.get("weekly", {}).get("current", 0)
        perfect_days = streak_overview.get("bonuses", {}).get("perfect_day_count", 0)

        # Derived metrics.
        hours_studied = round(week_minutes / 60.0, 1)
        consistency = self._compute_consistency(active_days)
        estimated_band = self._compute_estimated_band(
            current_band, target_band, week_tasks, daily_budget, week_start, today
        )

        # ─── 2. Compute each recommendation category ────────────────────
        study_order = self._compute_study_order(
            skill_bands, weakest_skills, strongest_skills,
            current_band, target_band, days_remaining,
        )

        revision_priorities = self._compute_revision_priorities(
            weakest_skills, skill_bands, days_remaining,
        )

        extra_practice = self._compute_extra_practice(
            weakest_skills, strongest_skills, skill_bands,
            daily_budget, days_remaining,
        )

        additional_resources = self._compute_additional_resources(
            user_id, weakest_skills, current_band, target_band,
            days_remaining, daily_budget,
        )

        break_suggestions = self._compute_break_suggestions(
            week_minutes, active_days, daily_budget, current_streak,
        )

        time_management = self._compute_time_management(
            daily_budget, days_remaining, week_tasks, active_days,
            current_band, target_band, level,
        )

        suggestions = self._compute_suggestions(
            current_band, target_band, week_tasks, hours_studied,
            consistency, days_remaining, estimated_band,
            skill_bands, weakest_skills,
        )

        next_week_focus = self._compute_next_week_focus(skill_bands, weakest_skills)

        # ─── 3. Build summary ───────────────────────────────────────────
        summary = self._build_summary(
            current_band, target_band, days_remaining,
            week_minutes, week_tasks, active_days, current_streak,
        )

        # ─── 4. Formulas ────────────────────────────────────────────────
        formulas = self._build_formulas()

        result = {
            "user_id": user_id,
            "run_date": today.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "current_band": current_band,
            "target_band": target_band,
            "days_remaining": days_remaining,
            "daily_budget_minutes": daily_budget,
            "skill_bands": skill_bands,
            "weakest_skills": weakest_skills,
            "strongest_skills": strongest_skills,
            "weakest_skill": SKILL_LABELS.get(weakest_skills[0], weakest_skills[0].title()) if weakest_skills else None,
            "weakest_skill_key": weakest_skills[0] if weakest_skills else None,
            "strongest_skill": SKILL_LABELS.get(strongest_skills[0], strongest_skills[0].title()) if strongest_skills else None,
            "strongest_skill_key": strongest_skills[0] if strongest_skills else None,
            "hours_studied": hours_studied,
            "tasks_completed": week_tasks,
            "streak": current_streak,
            "consistency": consistency,
            "estimated_band": estimated_band,
            "summary": summary,
            "study_order": study_order,
            "revision_priorities": revision_priorities,
            "extra_practice": extra_practice,
            "additional_resources": additional_resources,
            "break_suggestions": break_suggestions,
            "time_management": time_management,
            "suggestions": suggestions,
            "next_week_focus": next_week_focus,
            "metrics": {
                "week_start": week_start.isoformat(),
                "week_end": today.isoformat(),
                "week_minutes": week_minutes,
                "week_tasks": week_tasks,
                "active_days": active_days,
                "current_streak": current_streak,
                "weekly_streak": weekly_streak,
                "perfect_days": perfect_days,
                "level": level,
                "total_minutes": total_minutes,
                "total_tasks": total_tasks,
            },
            "formulas": formulas,
            "version": 1,
        }

        # ─── 5. Persist ─────────────────────────────────────────────────
        self._safe_store(user_id, today, result)

        return result

    # ─── Recommendation computations (pure, deterministic) ──────────────

    @staticmethod
    def _compute_study_order(
        skill_bands: Dict[str, float],
        weakest_skills: List[str],
        strongest_skills: List[str],
        current_band: float,
        target_band: float,
        days_remaining: Optional[int],
    ) -> List[Dict[str, Any]]:
        """
        Determine the order in which to study skills this week.

        Formula:
          - Skills with the largest band gap (target_band - skill_band) get priority.
          - Production skills (writing, speaking) are weighted first because
            they are harder to improve and require more practice.
          - If time is short (<=14 days), focus only on weakest skills.
          - If time is ample (>30 days), include all skills in a balanced rotation.

        Returns a list of {order, skill, label, band, band_gap, priority} dicts.
        """
        if not skill_bands:
            return []

        band_gap = target_band - current_band

        entries = []
        for skill, band in skill_bands.items():
            gap = target_band - band
            # Production skill bonus: add +0.5 to gap for writing/speaking
            is_production = skill in SKILL_ORDER_HIGH_PRIORITY
            adjusted_gap = gap + (1.0 if is_production else 0.0)

            # Time pressure: if < 14 days, double the gap for weak skills
            time_factor = 2.0 if (days_remaining is not None and days_remaining <= 14 and gap >= band_gap * 0.5) else 1.0
            score = adjusted_gap * time_factor

            entries.append({
                "skill": skill,
                "label": SKILL_LABELS.get(skill, skill.title()),
                "band": band,
                "band_gap": round(gap, 1),
                "priority_score": round(score, 2),
                "is_production": is_production,
            })

        # Sort by priority score descending.
        entries.sort(key=lambda x: x["priority_score"], reverse=True)

        for i, entry in enumerate(entries):
            entry["order"] = i + 1

        return entries

    @staticmethod
    def _compute_revision_priorities(
        weakest_skills: List[str],
        skill_bands: Dict[str, float],
        days_remaining: Optional[int],
    ) -> List[Dict[str, Any]]:
        """
        Prioritize revision topics within weak skills.

        Formula:
          - For each weak skill, identify the specific area to revise based on
            the band deficit relative to target.
          - Lower band → higher revision priority.
          - If days_remaining < 14, only list the single most critical skill.
        """
        priorities = []

        for skill in weakest_skills:
            band = skill_bands.get(skill, 5.0)
            label = SKILL_LABELS.get(skill, skill.title())

            # Determine revision focus area.
            if skill == "writing":
                focus = "Task 2 essay structure and coherence"
            elif skill == "speaking":
                focus = "Fluency and vocabulary variety"
            elif skill == "reading":
                focus = "Skimming, scanning, and time management"
            elif skill == "listening":
                focus = "Note-taking and distractor recognition"
            elif skill == "vocabulary":
                focus = "Collocations and topic-specific lexis"
            elif skill == "grammar":
                focus = "Complex sentence structures"
            else:
                focus = "Core concepts"

            # Band deficit determines intensity.
            band_deficit = 9.0 - band
            if band < 5.0:
                intensity = "critical"
                topics = [focus, "Foundational concepts", "Band 5.0+ strategies"]
            elif band < 6.5:
                intensity = "high"
                topics = [focus, "Common error patterns"]
            elif band < 7.5:
                intensity = "medium"
                topics = [focus]
            else:
                intensity = "low"
                topics = [focus, "Advanced techniques"]

            priorities.append({
                "skill": skill,
                "label": label,
                "band": band,
                "intensity": intensity,
                "focus_area": focus,
                "topics": topics,
            })

            if days_remaining is not None and days_remaining <= 14:
                break  # Only most critical skill when time is short.

        return priorities

    @staticmethod
    def _compute_extra_practice(
        weakest_skills: List[str],
        strongest_skills: List[str],
        skill_bands: Dict[str, float],
        daily_budget: int,
        days_remaining: Optional[int],
    ) -> List[Dict[str, Any]]:
        """
        Recommend specific extra practice sessions.

        Formula:
          - Weakest skill gets the most practice time (40% of daily budget).
          - Second weakest gets 25%.
          - Strongest skills get maintenance practice (15% each, max 2).
          - If days_remaining < 30, shift 15% of strong-skill time to weak skills.
        """
        items = []

        if not weakest_skills:
            return []

        # Time allocation.
        if days_remaining is not None and days_remaining < 30:
            weak_alloc = [0.55, 0.25]  # more to weakest
            strong_alloc = 0.20
        else:
            weak_alloc = [0.40, 0.25]
            strong_alloc = 0.15

        for i, skill in enumerate(weakest_skills[:2]):
            alloc_pct = weak_alloc[i] if i < len(weak_alloc) else weak_alloc[-1]
            minutes = int(daily_budget * alloc_pct)
            band = skill_bands.get(skill, 5.0)

            # Suggest practice type based on band.
            if band < 5.5:
                practice_type = "Foundational exercises"
            elif band < 6.5:
                practice_type = "Targeted skill drills"
            elif band < 7.5:
                practice_type = "Advanced timed practice"
            else:
                practice_type = "Exam technique refinement"

            items.append({
                "skill": skill,
                "label": SKILL_LABELS.get(skill, skill.title()),
                "band": band,
                "recommended_minutes": minutes,
                "practice_type": practice_type,
                "priority": "high" if i == 0 else "medium",
            })

        # Strong skills — maintenance.
        for skill in strongest_skills[:2]:
            minutes = int(daily_budget * strong_alloc)
            if minutes < 5:
                continue
            band = skill_bands.get(skill, 6.0)
            items.append({
                "skill": skill,
                "label": SKILL_LABELS.get(skill, skill.title()),
                "band": band,
                "recommended_minutes": minutes,
                "practice_type": "Maintenance practice",
                "priority": "low",
            })

        return items

    def _compute_additional_resources(
        self,
        user_id: str,
        weakest_skills: List[str],
        current_band: float,
        target_band: float,
        days_remaining: Optional[int],
        daily_budget: int,
    ) -> List[Dict[str, Any]]:
        """
        Delegate to the existing RecommendationEngineService for resource
        recommendations, but frame them as 'additional resources' here.

        Returns up to 5 resources focused on the weakest skill.
        """
        try:
            skill = weakest_skills[0] if weakest_skills else None
            result = recommendation_engine_service.get_recommendations(
                user_id=user_id,
                skill=skill,
                limit=5,
            )
            return result.get("recommendations", [])
        except Exception as exc:
            logger.warning("additional_resources failed user=%s: %s", user_id, exc)
            return []

    @staticmethod
    def _compute_break_suggestions(
        week_minutes: int,
        active_days: int,
        daily_budget: int,
        current_streak: int,
    ) -> List[Dict[str, Any]]:
        """
        Compute break suggestions based on study load.

        Formula:
          - Daily budget > 90 min AND active 5+ days this week → long break (20 min) on weekend.
          - Daily budget > 60 min AND streak >= 7 → micro-breaks (5 min every 25 min) recommended.
          - Active < 3 days this week → gentle restart with 5-min warm-up.
          - If no active days → recovery suggestion.
        """
        suggestions = []

        avg_daily_minutes = week_minutes / 7 if active_days > 0 else 0

        if active_days == 0:
            suggestions.append({
                "type": "recovery",
                "title": "Gentle Restart Recommended",
                "description": "You haven't studied this week. Start with a 5-minute warm-up session today.",
                "frequency": "once",
                "duration_minutes": 5,
            })
            return suggestions

        if avg_daily_minutes > 90 and active_days >= 5:
            suggestions.append({
                "type": "long_break",
                "title": "Long Break on Weekend",
                "description": "After 5+ days of intensive study, take a 15-20 minute break on weekends to recharge.",
                "frequency": "weekly",
                "duration_minutes": 20,
            })

        if avg_daily_minutes > 60 and current_streak >= 7:
            suggestions.append({
                "type": "micro_break",
                "title": "Micro-Break Schedule",
                "description": "Take a 5-minute break every 25 minutes of focused study to maintain concentration.",
                "frequency": "daily",
                "duration_minutes": 5,
            })

        if avg_daily_minutes > 120:
            suggestions.append({
                "type": "extended_rest",
                "title": "Extended Rest Day",
                "description": "You've been studying intensively. Take a full rest day to prevent burnout.",
                "frequency": "every_3_days",
                "duration_minutes": 0,
            })

        if active_days < 3:
            suggestions.append({
                "type": "gentle_restart",
                "title": "Gentle Restart",
                "description": "You've been inconsistent this week. Start with shorter 30-minute sessions to rebuild momentum.",
                "frequency": "daily_this_week",
                "duration_minutes": 30,
            })

        if not suggestions:
            suggestions.append({
                "type": "standard_break",
                "title": "Standard Break",
                "description": "Take a 5-minute break between study sessions to maintain focus.",
                "frequency": "between_sessions",
                "duration_minutes": 5,
            })

        return suggestions

    @staticmethod
    def _compute_time_management(
        daily_budget: int,
        days_remaining: Optional[int],
        week_tasks: int,
        active_days: int,
        current_band: float,
        target_band: float,
        level: int,
    ) -> Dict[str, Any]:
        """
        Compute time management recommendations.

        Formula:
          - Daily budget split: weak skills take 50%, strong skills 30%, review 20%.
          - If days_remaining < 30, increase weak skill time to 65%.
          - If days_remaining < 14, all focus on weak skills (80%).
          - Tasks per day = daily_budget / 45 (average 45 min per task).
          - Weekly goal = daily_budget * active_days (target).
        """
        band_gap = target_band - current_band

        # Time split.
        if days_remaining is not None and days_remaining < 14:
            weak_pct = 0.80
            strong_pct = 0.10
            review_pct = 0.10
            focus = "exam-cram"
        elif days_remaining is not None and days_remaining < 30:
            weak_pct = 0.65
            strong_pct = 0.20
            review_pct = 0.15
            focus = "intensive"
        else:
            weak_pct = 0.50
            strong_pct = 0.30
            review_pct = 0.20
            focus = "balanced"

        weak_minutes = int(daily_budget * weak_pct)
        strong_minutes = int(daily_budget * strong_pct)
        review_minutes = daily_budget - weak_minutes - strong_minutes

        tasks_per_day = max(1, round(daily_budget / 45))
        target_weekly_minutes = daily_budget * 7

        # If behind on active days, suggest catch-up.
        if active_days < 5 and week_tasks < tasks_per_day * 7 * 0.7:
            suggestion = (
                f"You're behind this week ({active_days}/7 active days). "
                f"Aim for {tasks_per_day + 1} short tasks today to catch up."
            )
        else:
            suggestion = (
                f"Stick to {tasks_per_day} focused tasks per day ({daily_budget} min budget). "
                f"Weekly goal: {target_weekly_minutes} minutes."
            )

        return {
            "daily_budget_minutes": daily_budget,
            "time_split": {
                "weak_skills": f"{int(weak_pct * 100)}%",
                "weak_minutes": weak_minutes,
                "strong_skills": f"{int(strong_pct * 100)}%",
                "strong_minutes": strong_minutes,
                "review": f"{int(review_pct * 100)}%",
                "review_minutes": review_minutes,
            },
            "tasks_per_day": tasks_per_day,
            "weekly_target_minutes": target_weekly_minutes,
            "weekly_actual_minutes": active_days * daily_budget,  # estimate
            "focus_mode": focus,
            "band_gap": round(band_gap, 1),
            "level": level,
            "tip": suggestion,
        }

    @staticmethod
    # ─── Missing computation methods ───────────────────────────────────

    @staticmethod
    def _compute_estimated_band(
        current_band: float,
        target_band: float,
        tasks_completed: int,
        daily_budget: int,
        week_start: date,
        today: date,
    ) -> float:
        """
        Estimate the user's band at the current point in time.

        Formula:
          days_since_start = max(0, (today - week_start).days)
          if days_since_start == 0: days_since_start = 7
          total_planned_tasks = (daily_budget * days_since_start) / 45
          progress = min(tasks_completed / total_planned_tasks, 1.0)
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
    def _compute_suggestions(
        current_band: float,
        target_band: float,
        tasks_completed: int,
        hours_studied: float,
        consistency: float,
        days_remaining: Optional[int],
        estimated_band: float,
        skill_bands: Dict[str, float],
        weakest_skills: List[str],
    ) -> List[str]:
        """Generate deterministic, actionable suggestions."""
        recs: List[str] = []

        band_gap = target_band - current_band
        if band_gap >= 2.0:
            recs.append(
                f"Gap of {band_gap:.1f} band to target. Focus intensively on weak skills for the next 4 weeks."
            )
        elif band_gap >= 1.0:
            recs.append(
                f"Gap of {band_gap:.1f} band. Continue targeting weak skills consistently."
            )
        else:
            recs.append(
                f"You are close to your target ({target_band:.1f}). Focus on exam technique and mock tests."
            )

        if tasks_completed < 14:
            recs.append(
                f"You completed {tasks_completed} tasks this week. Aim for at least 2 tasks per study day."
            )
        elif tasks_completed >= 35:
            recs.append(
                f"Excellent productivity ({tasks_completed} tasks). Add full mock tests to your routine."
            )

        if consistency < 50:
            recs.append(
                f"Consistency is {consistency:.0f}%. Try studying at the same time every day to build a habit."
            )
        elif consistency < 80:
            recs.append(
                f"Good consistency ({consistency:.0f}%). Push for daily activity to reach 90%+."
            )

        if hours_studied < 5.0:
            recs.append(
                f"You studied only {hours_studied:.1f}h this week. Aim for at least 7h per week."
            )

        if days_remaining is not None:
            if days_remaining < 14:
                recs.append("Less than 2 weeks left — shift to final revision and timed mocks.")
            elif days_remaining < 30:
                recs.append("Less than a month left — intensify daily practice.")

        if weakest_skills and weakest_skills[0] in skill_bands:
            weak_band = skill_bands[weakest_skills[0]]
            label = SKILL_LABELS.get(weakest_skills[0], weakest_skills[0])
            recs.append(
                f"Your weakest skill is {label} (band {weak_band:.1f}). "
                "Allocate 50% of study time to this area."
            )

        return recs

    @staticmethod
    def _compute_next_week_focus(
        skill_bands: Dict[str, float], weakest_skills: List[str]
    ) -> List[str]:
        """Derive next week's focus skills from the lowest bands."""
        if not skill_bands:
            return ["Maintain balanced practice across all skills."]

        ordered = sorted(skill_bands.items(), key=lambda kv: kv[1])
        focus = []
        for skill, band in ordered[:3]:
            label = SKILL_LABELS.get(skill, skill.title())
            if band < 6.0:
                focus.append(f"Build fundamentals — {label} (band {band:.1f})")
            elif band < 7.0:
                focus.append(f"Target improvement — {label} (band {band:.1f})")
            else:
                focus.append(f"Maintain polish — {label} (band {band:.1f})")

        return focus if focus else ["Maintain balanced practice across all skills."]

    # ─── Summary ────────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(
        current_band: float,
        target_band: float,
        days_remaining: Optional[int],
        week_minutes: int,
        week_tasks: int,
        active_days: int,
        current_streak: int,
    ) -> str:
        """Generate a deterministic narrative summary."""
        band_gap = target_band - current_band
        hours = round(week_minutes / 60.0, 1)

        parts = []

        if days_remaining is not None:
            parts.append(
                f"With {days_remaining} days remaining until your exam"
            )
        parts.append(f"your band goal is {current_band:.1f} → {target_band:.1f}")
        parts.append(f"(gap: {band_gap:+.1f})")

        if week_tasks == 0:
            parts.append(
                f"This week you studied {hours:.1f}h across {active_days}/7 days, "
                f"but completed no tasks. Restart your study routine to build momentum."
            )
            return " ".join(parts) + "."

        parts.append(
            f"This week you studied {hours:.1f}h across {active_days}/7 days, "
            f"completing {week_tasks} tasks with a {current_streak}-day streak."
        )

        if week_tasks >= 35:
            parts.append("Excellent productivity — maintain this pace and add mock tests.")
        elif week_tasks >= 14:
            parts.append("Good consistency — keep building on your routine.")
        else:
            parts.append("Consistency needs work — try shorter daily sessions to rebuild momentum.")

        return " ".join(parts) + "."

    @staticmethod
    def _build_formulas() -> Dict[str, str]:
        """Document all formulas used."""
        return {
            "study_order": (
                "Skills ranked by (target_band - skill_band + production_bonus) * time_pressure_factor. "
                "Production skills (writing/speaking) get +1.0 bonus. "
                "If days_remaining <= 14 and band_gap >= 50%, time_pressure doubles the score."
            ),
            "revision_priorities": (
                "For each weak skill, intensity is: critical if band < 5.0, "
                "high if < 6.5, medium if < 7.5, low otherwise. "
                "If days_remaining <= 14, only the most critical skill is listed."
            ),
            "extra_practice": (
                "Weakest skill: 40% of daily budget (55% if < 30 days left). "
                "Second weakest: 25%. Strongest skills: 15% each (maintenance). "
                "Practice type: foundational (< 5.5), targeted drills (5.5-6.5), "
                "timed practice (6.5-7.5), exam technique (>= 7.5)."
            ),
            "break_suggestions": (
                "Long break (20 min) if avg_daily > 90 min AND active >= 5 days. "
                "Micro-break (5 min, every 25 min) if avg_daily > 60 AND streak >= 7. "
                "Extended rest if avg_daily > 120. "
                "Gentle restart (30 min) if active < 3 days."
            ),
            "time_management": (
                "Weak skills: 50% daily budget (65% if < 30 days, 80% if < 14 days). "
                "Strong skills: 30% (20% if < 30 days, 10% if < 14 days). "
                "Review: 20% (15% if < 30 days, 10% if < 14 days). "
                "Tasks/day = daily_budget / 45. "
                "Focus modes: balanced (> 30 days), intensive (14-30 days), exam-cram (< 14 days)."
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

    def _safe_get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.user_repo.get_profile(user_id)
        except Exception:
            return None

    def _safe_get_skill_bands(
        self, user_id: str, diag_profile: Dict[str, Any]
    ) -> Dict[str, float]:
        """Get skill bands from latest band estimation, falling back to diagnostic."""
        if self.db is not None:
            try:
                latest = self.band_estimation_repo.get_latest(user_id)
                if latest and latest.get("skill_bands"):
                    return {k: float(v) for k, v in latest["skill_bands"].items()}
            except Exception:
                pass

        # Fallback to diagnostic profile.
        return {k: float(v) for k, v in diag_profile.get("skill_bands", {}).items()}

    def _unsafe_get_skill_bands(
        self, user_id: str, diag_profile: Dict[str, Any]
    ) -> Dict[str, float]:
        """Alias for _safe_get_skill_bands (kept for naming consistency)."""
        return self._safe_get_skill_bands(user_id, diag_profile)

    @staticmethod
    def _derive_weak_strong(
        skill_bands: Dict[str, float], diag_profile: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """Derive weakest and strongest skills from skill bands or diagnostic profile."""
        if skill_bands:
            ordered = sorted(skill_bands.items(), key=lambda kv: kv[1])
            weakest = [ks[0] for ks in ordered[:2]]
            strongest = [ks[0] for ks in reversed(ordered[:2])]
        else:
            weakest = list(diag_profile.get("weakest_skills", []))[:2]
            strongest = list(diag_profile.get("strongest_skills", []))[:2]
        return weakest, strongest

    def _safe_get_progress_state(self, user_id: str) -> Dict[str, Any]:
        if self.db is None:
            return {}
        return self.progress_repo.get_state(user_id)

    def _safe_get_streak_overview(self, user_id: str) -> Dict[str, Any]:
        if self.db is None:
            return {}
        try:
            return self.streak_repo.get_overview(user_id)
        except Exception:
            return {}

    def _safe_get_cached(self, user_id: str, day: date) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("ai_recommendations")
                .select("report_json")
                .eq("user_id", user_id)
                .eq("run_date", day.isoformat())
                .limit(1)
            )
            result = self.db.execute(query, "fetch cached AI recommendation")
            if result.data:
                report = result.data[0].get("report_json") or {}
                report["id"] = result.data[0].get("id")
                return report
        except Exception:
            pass
        return None

    def _safe_store(self, user_id: str, run_date: date, result: Dict[str, Any]) -> None:
        if self.db is None:
            return
        try:
            payload = {
                "user_id": user_id,
                "run_date": run_date.isoformat(),
                "report_json": result,
                "generated_at": result.get("generated_at"),
                "version": result.get("version", 1),
            }
            query = self.db.table("ai_recommendations").upsert(
                payload, on_conflict="user_id,run_date"
            )
            self.db.execute(query, "store AI recommendation")

            # Update cache.
            cache_payload = {
                "user_id": user_id,
                "run_date": run_date.isoformat(),
                "report_json": result,
                "generated_at": result.get("generated_at"),
                "latest_report_id": result.get("id"),
            }
            cache_query = self.db.table("ai_recommendations_cache").upsert(
                cache_payload, on_conflict="user_id"
            )
            self.db.execute(cache_query, "update AI recommendation cache")
        except Exception as exc:
            logger.warning("AI recommendation store failed user=%s: %s", user_id, exc)

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


# ─── Migration helper: create tables if they don't exist ────────────────
# The tables are created via migration 029. This method is a fallback.
def _ensure_tables_exist(db: DatabaseSession) -> None:
    if db is None:
        return
    try:
        db.table("ai_recommendations").select("id").limit(1).execute()
    except Exception:
        pass


from app.db.session import db_session

ai_recommendations_service = AiRecommendationsService(db_session)
