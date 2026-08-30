"""
AI Mentor service.

The AI Mentor behaves like an experienced IELTS tutor. It **coaches the
student inside their existing study roadmap** — it never generates a study
plan from scratch. The service:

  1. **Understands** the learner: profile, diagnostic results, current
     progress, study history, missed tasks, weakest/strongest skills, target
     band, exam date, and the current roadmap (+ scheduler history).
  2. **Analyses** the existing roadmap deterministically (rules + thresholds,
     no randomness) to produce structured insights and actionable directives
     that always reference existing roadmap items.
  3. **Coaches** by rendering a natural-language message. The LLM is used only
     to *polish the wording* of the deterministic coaching (per AI_BRAIN P3:
     "the LLM explains, never decides"); a full deterministic template engine
     guarantees a quality message even without an API key.

All DB reads are defensive (safe wrappers return empty values), mirroring the
prediction_engine / exam_countdown services, so the service is testable with
``db=None`` and never crashes a request because of a missing table.
"""
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.ai.prompts import IELTS_MENTOR_PROMPT
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.models.study_plan_engine import PHASE_KEYS, PHASE_WEIGHTS
from app.repositories.daily_plan_repo import DailyPlanRepository
from app.repositories.diagnostic_repo import DiagnosticRepository
from app.repositories.mentor_repo import MentorRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.scheduler_repo import SchedulerRepository
from app.repositories.study_plan_repo import StudyPlanRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.services.diagnostic_roadmap_service import (
    SKILL_LABELS,
    diagnostic_roadmap_service,
)
from app.services.prediction_engine import prediction_engine_service
from app.services.writing_analytics_service import writing_analytics_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants (deterministic thresholds — the "tutor instincts")
# ---------------------------------------------------------------------------
CRUNCH_WINDOW_DAYS = 14            # final-stretch protection window
INTENSITY_FINAL_DAYS = 14          # exam countdown intensity thresholds
INTENSITY_INTENSIVE_DAYS = 30
INTENSITY_FOCUSED_DAYS = 60
MISSED_HIGH_THRESHOLD = 5          # >=5 recent missed tasks -> high severity
MISSED_MEDIUM_THRESHOLD = 2        # >=2 missed tasks -> medium severity
OVERDUE_HIGH_THRESHOLD = 5         # >=5 overdue pending tasks -> high
CONSISTENCY_LOW_THRESHOLD = 40.0   # active-day ratio below this -> low consistency
CONSISTENCY_MEDIUM_THRESHOLD = 70.0
WEEK_BUDGET_LOW_THRESHOLD = 60.0   # week minutes < 60% of budget -> flag
WEAK_COVERAGE_PRIORITY_DAYS = 7    # window for weak-skill coverage check
MOCK_LOOKAHEAD_DAYS = 14           # window for mock-readiness check
MOCK_NEAR_EXAM_DAYS = 30           # mocks become "expected" inside 30 days
READINESS_LOW_THRESHOLD = 50.0     # readiness score below this -> high risk
DAILY_OVERLOAD_RATIO = 1.5         # a roadmap day above 1.5x budget -> overload
ADJUSTMENT_OVERLOAD_THRESHOLD = 8  # >=8 recent scheduler adjustments -> overload
MIN_DAYS_FOR_CONSISTENCY = 3       # avoid 0/0 early-on

# Mock task types (used for mock-readiness analysis).
MOCK_TASK_TYPES = ("full_mock", "mock_section")

# Human-readable phase labels (mirrors study_plan_generator).
PHASE_LABELS = {
    "foundation": "Foundation & Gap Closure",
    "skill_building": "Skill Building",
    "advanced": "Advanced Techniques",
    "mock_tests": "Mock Test Marathon",
    "final_revision": "Final Revision & Strategy",
}
class AIMentorService:
    """Coaches the student within their existing roadmap (never from scratch)."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.mentor_repo = MentorRepository(db)
        self.user_repo = UserRepository(db)
        self.study_plan_repo = StudyPlanRepository(db)
        self.daily_plan_repo = DailyPlanRepository(db)
        self.task_repo = TaskRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)
        self.scheduler_repo = SchedulerRepository(db)
        self.diagnostic_repo = DiagnosticRepository(db)

    # ==================================================================
    # Public API
    # ==================================================================
    def get_context(self, user_id: str) -> Dict[str, Any]:
        """Return the full learner-context snapshot the mentor understands."""
        ctx = self._gather_context(user_id)
        return self._build_context_response(ctx)

    def coach(
        self,
        user_id: str,
        mode: str = "daily_coaching",
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run a coaching session for the given mode.

        Always analyses the EXISTING roadmap — never generates a plan.
        Persists the conversation + mentor message when the DB is available.
        """
        ctx = self._gather_context(user_id)
        insights, directives = self._analyze(ctx)
        rendered = self._render(mode, ctx, insights, directives)
        return self._finalize(user_id, mode, ctx, insights, directives, rendered)

    def ask(self, user_id: str, question: str) -> Dict[str, Any]:
        """
        Answer a student's question strictly within the existing roadmap.

        If the question implies "build me a new plan", the mentor responds
        with the roadmap-missing/guardrail guidance instead of planning.
        """
        ctx = self._gather_context(user_id)
        insights, directives = self._analyze(ctx)
        rendered = self._render("ask_mentor", ctx, insights, directives, question=question)
        return self._finalize(
            user_id, "ask_mentor", ctx, insights, directives, rendered,
            user_message=question,
        )

    def list_conversations(
        self, user_id: str, mode: Optional[str] = None, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """Return paginated conversation history."""
        rows = self._safe_list_conversations(user_id, mode, limit, offset)
        total = self._safe_count_conversations(user_id, mode)
        items = []
        for row in rows:
            conv_id = row.get("id")
            items.append({
                "id": conv_id,
                "mode": row.get("mode"),
                "title": row.get("title", "Coaching session"),
                "status": row.get("status", "active"),
                "message_count": self._safe_count_messages(conv_id) if conv_id else 0,
                "last_message_at": self._safe_get_last_message_at(conv_id) if conv_id else None,
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            })
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def get_conversation(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """Return a single conversation with all its messages (owner-scoped)."""
        conv = self._safe_get_conversation(conversation_id, user_id)
        if not conv:
            raise NotFoundError("Mentor conversation not found")
        messages = self._safe_list_messages(conversation_id, user_id)
        return {
            "id": conv.get("id"),
            "user_id": conv.get("user_id"),
            "mode": conv.get("mode"),
            "title": conv.get("title", "Coaching session"),
            "status": conv.get("status", "active"),
            "context_snapshot": conv.get("context_snapshot") or {},
            "meta": conv.get("meta") or {},
            "messages": messages,
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at"),
        }

    # ==================================================================
    # Context gathering — everything the mentor "understands"
    # ==================================================================
    def _gather_context(self, user_id: str) -> Dict[str, Any]:
        """Collect every learner signal into one context dict (never raises)."""
        profile_row = self._safe_get_profile(user_id)
        if not profile_row:
            # A valid token for a user that does not exist is a broken state.
            raise NotFoundError("User not found")

        diag = self._safe_resolve_profile(user_id)
        exam = self._gather_exam(profile_row, diag)
        roadmap = self._gather_roadmap(user_id)
        study_history = self._gather_study_history(user_id)
        missed = self._gather_missed_tasks(user_id)
        prediction = self._gather_prediction(user_id)
        writing_analytics = self._gather_writing_analytics(user_id)

        current_band = diag.get("current_band") or profile_row.get("current_band")
        target_band = diag.get("target_band") or profile_row.get("target_band")
        band_gap = None
        if current_band is not None and target_band is not None and target_band >= current_band:
            band_gap = round(float(target_band) - float(current_band), 1)

        profile = {
            "user_id": user_id,
            "full_name": profile_row.get("full_name"),
            "module": profile_row.get("module") or "academic",
            "plan": profile_row.get("plan") or "free",
            "daily_minutes_budget": int(profile_row.get("daily_minutes_budget") or 60),
            "current_band": float(current_band) if current_band is not None else None,
            "target_band": float(target_band) if target_band is not None else None,
            "exam_date": _as_iso_date(diag.get("profile_exam_date") or profile_row.get("exam_date")),
            "profile_source": diag.get("source") or "unknown",
            "has_diagnostic": bool(diag.get("has_diagnostic") or False),
            "diagnostic_attempt_id": diag.get("attempt_id"),
            "weakest_skills": diag.get("weakest_skills") or [],
            "strongest_skills": diag.get("strongest_skills") or [],
            "skill_bands": {k: float(v) for k, v in (diag.get("skill_bands") or {}).items()},
        }

        return {
            "user_id": user_id,
            "generated_at": _now_iso(),
            "profile": profile,
            "exam": exam,
            "roadmap": roadmap,
            "study_history": study_history,
            "missed_tasks": missed,
            "prediction": prediction,
            "writing_analytics": writing_analytics,
            "band_gap": band_gap,
            "skill_labels": dict(SKILL_LABELS),
        }

    def _gather_exam(self, profile_row: Dict[str, Any], diag: Dict[str, Any]) -> Dict[str, Any]:
        """Exam date, days remaining and intensity (deterministic)."""
        raw = diag.get("profile_exam_date") or profile_row.get("exam_date")
        exam_date = _parse_date(raw)
        today = date.today()
        days_remaining = None
        weeks_remaining = None
        if exam_date:
            days_remaining = max((exam_date - today).days, 0)
            weeks_remaining = round(days_remaining / 7) if days_remaining else 0
        return {
            "exam_date": exam_date.isoformat() if exam_date else None,
            "days_remaining": days_remaining,
            "weeks_remaining": weeks_remaining,
            "intensity": _intensity(days_remaining),
            "in_crunch_window": (
                days_remaining is not None and days_remaining <= CRUNCH_WINDOW_DAYS
            ),
        }

    def _gather_roadmap(self, user_id: str) -> Dict[str, Any]:
        """Analyse the student's EXISTING roadmap (never creates one)."""
        plan = self._safe_get_active_plan(user_id)
        plan = plan or {}
        ctx = {
            "has_active_plan": bool(plan),
            "study_plan_id": plan.get("id"),
            "title": plan.get("title"),
            "version": plan.get("version"),
            "start_date": _as_iso_date(plan.get("start_date")),
            "exam_date": _as_iso_date(plan.get("exam_date") or plan.get("end_date")),
            "total_tasks": 0,
            "completed_tasks": 0,
            "progress_percent": 0.0,
            "missed_tasks": 0,
            "pending_tasks": 0,
            "current_phase_index": None,
            "total_phases": len(PHASE_KEYS),
            "upcoming_task_count_7d": 0,
            "upcoming_by_skill_7d": {},
            "today_tasks": [],
            "days_since_start": 0,
            "roadmap_generated_from": (plan.get("meta") or {}).get("source"),
        }
        if not plan:
            return ctx

        plan_id = plan["id"]
        tasks = self._safe_list_tasks(user_id, plan_id)
        start_date = _parse_date(plan.get("start_date")) if plan.get("start_date") else None

        today = date.today()
        completed = [t for t in tasks if t.get("status") == "completed"]
        missed = [t for t in tasks if t.get("status") == "missed"]
        pending = [t for t in tasks if t.get("status") in ("pending", "in_progress")]

        total = len(tasks)
        ctx["total_tasks"] = total
        ctx["completed_tasks"] = len(completed)
        ctx["missed_tasks"] = len(missed)
        ctx["pending_tasks"] = len(pending)
        ctx["progress_percent"] = round(len(completed) / total * 100, 1) if total else 0.0

        if start_date:
            ctx["days_since_start"] = max((today - start_date).days + 1, 0)

        window_end = today + timedelta(days=WEAK_COVERAGE_PRIORITY_DAYS)
        upcoming = [
            t for t in pending
            if t.get("scheduled_date")
            and today <= _parse_date(t["scheduled_date"]) <= window_end
        ]
        ctx["upcoming_task_count_7d"] = len(upcoming)
        by_skill: Dict[str, int] = {}
        for t in upcoming:
            skill = t.get("skill") or "general"
            by_skill[skill] = by_skill.get(skill, 0) + 1
        ctx["upcoming_by_skill_7d"] = by_skill

        # Tasks scheduled for *today* (the mission for this coaching session).
        ctx["today_tasks"] = [
            t for t in pending
            if t.get("scheduled_date") and _parse_date(t["scheduled_date"]) == today
        ]

        # Estimate current phase from elapsed time through the plan.
        ctx["current_phase_index"] = self._estimate_phase_index(start_date, plan)
        return ctx

    def _gather_study_history(self, user_id: str) -> Dict[str, Any]:
        """Minutes / XP / streak / consistency from the progress ledger."""
        state = self._safe_get_progress_state(user_id)
        profile_row = self._safe_get_profile(user_id)
        budget = int((profile_row or {}).get("daily_minutes_budget") or 60)

        today = date.today()
        today_stats = self._safe_get_day_stats(user_id, today)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week = self._safe_get_period_progress(user_id, week_start, week_end)

        active_days = self._safe_count_active_days(user_id)

        # days_since: prefer roadmap start, otherwise earliest recorded activity.
        plan = self._safe_get_active_plan(user_id)
        plan_start = _parse_date(plan.get("start_date")) if plan and plan.get("start_date") else None
        if plan_start:
            days_since = max((today - plan_start).days + 1, 1)
        else:
            days_since = self._days_since_first_active(user_id) or 1

        consistency = round(min(active_days / days_since * 100, 100.0), 1) if days_since > 0 else 0.0

        active_today = int(today_stats.get("minutes") or 0) > 0 or int(
            today_stats.get("tasks_completed") or 0
        ) > 0

        return {
            "total_minutes": int(state.get("total_minutes") or 0),
            "total_tasks_completed": int(state.get("total_tasks") or 0),
            "total_xp": int(state.get("total_xp") or 0),
            "current_streak": int(state.get("current_streak") or 0),
            "longest_streak": int(state.get("longest_streak") or 0),
            "last_active_date": _as_iso_date(state.get("last_active_date")),
            "active_days": active_days,
            "minutes_this_week": int(week.get("minutes") or 0),
            "week_budget_minutes": budget * 7,
            "week_percent": int(week.get("percent") or 0),
            "consistency_percent": consistency,
            "active_today": active_today,
            "today_minutes": int(today_stats.get("minutes") or 0),
            "today_tasks_completed": int(today_stats.get("tasks_completed") or 0),
            "consecutive_missed_days": _consecutive_missed_days(state, today),
            "last_active_iso": _as_iso_date(state.get("last_active_date")),
            "recent_sessions": self._safe_get_history(user_id, limit=5),
        }

    def _gather_missed_tasks(self, user_id: str) -> Dict[str, Any]:
        """Missed / overdue / carried-forward work, plus scheduler audit trail."""
        plan = self._safe_get_active_plan(user_id)
        tasks = self._safe_list_tasks(user_id, (plan or {}).get("id")) if plan else []
        today = date.today()

        missed = [t for t in tasks if t.get("status") == "missed"]
        overdue = [
            t for t in tasks
            if t.get("status") in ("pending", "in_progress")
            and t.get("scheduled_date")
            and _parse_date(t["scheduled_date"]) < today
        ]

        recent_week = today - timedelta(days=7)
        recent_missed = [
            t for t in missed
            if t.get("scheduled_date") and _parse_date(t["scheduled_date"]) >= recent_week
        ]

        by_skill: Dict[str, int] = {}
        for t in missed:
            skill = t.get("skill") or "general"
            by_skill[skill] = by_skill.get(skill, 0) + 1

        def _example(t: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "task_id": t.get("id"),
                "title": t.get("title"),
                "skill": t.get("skill"),
                "task_type": t.get("task_type"),
                "scheduled_date": _as_iso_date(t.get("scheduled_date")),
                "status": t.get("status"),
                "priority": int(t.get("priority") or 1),
            }

        examples = sorted(missed, key=lambda x: -int(x.get("priority") or 1))[:5]
        return {
            "total_missed": len(missed),
            "recent_missed_7d": len(recent_missed),
            "overdue_pending": len(overdue),
            "by_skill": by_skill,
            "examples": [_example(t) for t in examples],
            "last_scheduler_adjustments": self._safe_list_adjustments(user_id, limit=6),
        }

    def _gather_writing_analytics(self, user_id: str) -> Dict[str, Any]:
        """Writing progress analytics snapshot for the mentor context."""
        return writing_analytics_service.context_brief(user_id, days=90)

    def _gather_prediction(self, user_id: str) -> Dict[str, Any]:
        """Readiness / risk from the deterministic prediction engine (if any)."""
        try:
            result = prediction_engine_service.get_prediction(user_id)
            return {
                "has_prediction": True,
                "estimated_band": result.get("estimated_band"),
                "readiness_score": result.get("readiness_score"),
                "risk_level": result.get("risk_level"),
                "preparation_percentage": result.get("preparation_percentage"),
                "completion_rate": result.get("completion_rate"),
                "study_consistency": result.get("study_consistency"),
            }
        except Exception as exc:  # never fail coaching because of the predictor
            logger.info("mentor prediction gather failed user=%s: %s", user_id, exc)
            return {"has_prediction": False}

    def _build_context_response(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Translate the internal context into the public context payload."""
        return {
            "generated_at": _now_iso(),
            "profile": ctx["profile"],
            "exam": ctx["exam"],
            "roadmap": ctx["roadmap"],
            "study_history": ctx["study_history"],
            "missed_tasks": ctx["missed_tasks"],
            "prediction": ctx["prediction"],
            "writing_analytics": ctx.get("writing_analytics", {}),
            "band_gap": ctx.get("band_gap"),
            "skill_labels": ctx.get("skill_labels") or dict(SKILL_LABELS),
        }

    # ==================================================================
    # Deterministic roadmap analysis (rules + thresholds, no AI)
    # ==================================================================
    def _analyze(self, ctx: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Produce insights + directives from the learner context (never plans)."""
        insights: List[Dict[str, Any]] = []
        directives: List[Dict[str, Any]] = []

        profile = ctx["profile"]
        exam = ctx["exam"]
        roadmap = ctx["roadmap"]
        hist = ctx["study_history"]
        missed = ctx["missed_tasks"]
        prediction = ctx["prediction"]

        # ── 1. Roadmap presence (the hard guardrail) ──────────────────
        if not roadmap["has_active_plan"]:
            insights.append(_insight(
                "roadmap_missing", "high",
                "No active roadmap yet",
                "Coaching can only begin once a personalized roadmap exists. "
                "Generate it from your diagnostic results or profile, then come back.",
            ))
            directives.append(_directive(
                5, "generate_roadmap",
                "First step: build your personalized roadmap from your diagnostic "
                "results and exam date. The mentor will coach you through it day by "
                "day — but never invents a plan for you.",
            ))
            return insights, directives

        # ── 2. Roadmap progress ───────────────────────────────────────
        phase_label = _phase_label(roadmap["current_phase_index"])
        insights.append(_insight(
            "roadmap_progress",
            "positive" if roadmap["progress_percent"] >= 30 else "low",
            f"Roadmap progress: {roadmap['progress_percent']:.1f}%",
            f"You have completed {roadmap['completed_tasks']} of {roadmap['total_tasks']} "
            f"roadmap tasks. Current phase: {phase_label}.",
            metric={"progress_percent": roadmap["progress_percent"],
                    "phase": phase_label,
                    "total_tasks": roadmap["total_tasks"],
                    "completed_tasks": roadmap["completed_tasks"]},
        ))

        # ── 3. Missed tasks ───────────────────────────────────────────
        if missed["recent_missed_7d"] > 0 or missed["total_missed"] > 0:
            n = missed["recent_missed_7d"] or missed["total_missed"]
            severity = (
                "high" if missed["recent_missed_7d"] >= MISSED_HIGH_THRESHOLD
                else "medium" if n >= MISSED_MEDIUM_THRESHOLD else "low"
            )
            skills = ", ".join(
                SKILL_LABELS.get(s, s.title()) for s in list(missed["by_skill"].keys())[:3]
            ) or "general"
            insights.append(_insight(
                "missed_tasks", severity,
                f"{n} missed task(s) to close out",
                f"The scheduler carried {n} task(s) forward ({skills}). "
                "These still belong to your roadmap — finish the highest priority ones first.",
                metric={"missed": missed["total_missed"],
                        "recent_missed_7d": missed["recent_missed_7d"],
                        "by_skill": missed["by_skill"]},
            ))
            for ex in missed["examples"][:2]:
                directives.append(_directive(
                    5, "prioritize_task",
                    f"Complete the carried-forward task '{ex['title']}' "
                    f"({SKILL_LABELS.get(ex['skill'], ex['skill'].title())}) — "
                    f"it was scheduled for {ex['scheduled_date']}.",
                    skill=ex["skill"],
                    ref={"task_id": ex["task_id"], "task_title": ex["title"],
                         "scheduled_date": ex["scheduled_date"]},
                ))

        # ── 5. Study consistency + streak ─────────────────────────────
        consistency = hist["consistency_percent"]
        if consistency < CONSISTENCY_LOW_THRESHOLD:
            insights.append(_insight(
                "study_consistency", "medium",
                f"Study consistency is {consistency:.1f}%",
                "Consistency drives IELTS results more than intensity. Small daily wins "
                "beat occasional marathon sessions.",
                metric={"consistency_percent": consistency},
            ))
            directives.append(_directive(
                4, "keep_streak",
                "Aim for a short daily session instead of skipping days — protect your routine.",
            ))

        last_active = _parse_date(hist.get("last_active_date"))
        if (
            hist["current_streak"] > 0
            and last_active is not None
            and last_active < date.today()
            and not hist["active_today"]
            and (date.today() - last_active).days <= 2
        ):
            insights.append(_insight(
                "streak_at_risk", "medium",
                "Your streak is at risk",
                f"You have a {hist['current_streak']}-day streak. Complete at least one task "
                "today to keep it alive.",
                metric={"current_streak": hist["current_streak"]},
            ))
            directives.append(_directive(
                5, "keep_streak",
                "Complete at least one roadmap task today to protect your streak.",
            ))

        # --- 6. Missed-day recovery (student returned after missing days) ---
        missed_days = hist.get("consecutive_missed_days") or 0
        if missed_days >= 1 and not hist.get("active_today"):
            md_severity = (
                "high" if missed_days >= 4
                else "medium" if missed_days >= 2
                else "low"
            )
            insights.append(_insight(
                "missed_day", md_severity,
                f"You missed {missed_days} day(s) of study",
                "You're back - that's what matters. The Adaptive Scheduler has moved "
                "your carried-forward tasks ahead and lightened today's load so you can "
                "rebuild momentum without pressure.",
                metric={"consecutive_missed_days": missed_days},
            ))
            directives.append(_directive(
                5, "recover_gently",
                "Start today's lighter schedule: complete one task and log it so the "
                "Adaptive Scheduler rebalances your roadmap for tomorrow.",
            ))

        # --- 7. Band gap ---------------------------------------------------
        band_gap = ctx.get("band_gap")
        if band_gap is not None and band_gap >= 1.0:
            insights.append(_insight(
                "band_gap", "low",
                f"{band_gap:.1f} band(s) between current and target",
                f"Your target is {profile['target_band']} and your current level is around "
                f"{profile['current_band']}. The roadmap's phases exist to close exactly this gap.",
                metric={"band_gap": band_gap,
                        "current_band": profile["current_band"],
                        "target_band": profile["target_band"]},
            ))
# --- 7b. Writing progress analytics ---------------------------------
        wa = ctx.get("writing_analytics") or {}
        if wa.get("has_writing_data"):
            w_dir = (wa.get("improvement") or {}).get("direction")
            w_band = (wa.get("improvement") or {}).get("band_change")
            weakest = wa.get("weakest_criterion")
            strongest = wa.get("strongest_criterion")
            if w_dir == "improving" and w_band is not None and w_band > 0:
                insights.append(_insight(
                    "writing_progress", "positive",
                    f"Writing band improving (+{w_band:.1f})",
                    f"Your evaluated essays are trending stronger. Keep submitting essays "
                    f"— the {weakest or 'weaker'} criterion is your best lever right now.",
                    metric={"band_change": w_band, "direction": w_dir,
                            "strongest_criterion": strongest,
                            "weakest_criterion": weakest},
                ))
            elif weakest:
                insights.append(_insight(
                    "writing_progress", "low",
                    f"Focus your writing on {weakest}",
                    f"Across your evaluated essays, {weakest} is your lowest-scoring "
                    f"criterion. Target it in your next essay to move the most.",
                    metric={"weakest_criterion": weakest,
                            "strongest_criterion": strongest,
                            "evaluated_essays": wa.get("evaluated_essays", 0)},
                ))

        # ── 8. Crunch window ──────────────────────────────────────────
        if exam["in_crunch_window"]:
            insights.append(_insight(
                "crunch_window", "high",
                "You are in the final stretch",
                f"{exam['days_remaining']} days remain. This is mock and revision season — "
                "protect the scheduled mocks and revision days on your roadmap.",
                metric={"days_remaining": exam["days_remaining"]},
            ))
            directives.append(_directive(
                5, "protect_revision",
                f"With {exam['days_remaining']} days to go, follow the roadmap's final "
                "revision and mock schedule strictly. Do not add new material.",
            ))

        # ── 10. Weekly budget ─────────────────────────────────────────
        if hist["week_budget_minutes"] > 0:
            week_pct = round(hist["minutes_this_week"] / hist["week_budget_minutes"] * 100)
            if week_pct < WEEK_BUDGET_LOW_THRESHOLD and not hist["active_today"]:
                insights.append(_insight(
                    "weekly_budget", "medium",
                    f"{week_pct}% of the weekly study budget reached",
                    f"You have studied {hist['minutes_this_week']} of "
                    f"{hist['week_budget_minutes']} planned minutes this week.",
                    metric={"minutes_this_week": hist["minutes_this_week"],
                            "week_budget_minutes": hist["week_budget_minutes"]},
                ))
                directives.append(_directive(
                    4, "reach_budget",
                    "Reach today's budget from your roadmap tasks — every block counts.",
                ))

        # ── 12. Mock readiness ────────────────────────────────────────
        days_left = exam["days_remaining"]
        if days_left is not None:
            lookahead = days_left if days_left < MOCK_LOOKAHEAD_DAYS else MOCK_LOOKAHEAD_DAYS
            horizon = date.today() + timedelta(days=lookahead)
            upcoming_tasks = self._safe_upcoming_tasks_for_analysis(
                ctx["user_id"], roadmap.get("study_plan_id"), horizon
            )
            mocks = [t for t in upcoming_tasks if t.get("task_type") in MOCK_TASK_TYPES]
            if days_left <= MOCK_NEAR_EXAM_DAYS and not mocks:
                insights.append(_insight(
                    "mock_readiness",
                    "high" if days_left <= CRUNCH_WINDOW_DAYS else "medium",
                    "No mock test scheduled in the coming days",
                    f"With {days_left} days remaining, a timed mock is the single most "
                    "valuable thing the roadmap should be delivering right now.",
                    metric={"days_remaining": days_left, "mocks_upcoming": 0},
                ))
                directives.append(_directive(
                    5, "review_assessment",
                    "Prioritize the mock/assessment tasks already scheduled on your roadmap — "
                    "full timed conditions, then review errors.",
                ))

        # ── 13. Readiness / risk from prediction engine ───────────────
        if prediction.get("has_prediction"):
            risk = (prediction.get("risk_level") or "low").lower()
            readiness = prediction.get("readiness_score")
            p_severity = "high"
            if risk in ("low", "stable"):
                p_severity = "positive"
            elif risk in ("medium", "moderate"):
                p_severity = "medium"
            if readiness is not None and readiness < READINESS_LOW_THRESHOLD and p_severity != "high":
                p_severity = "high"
            insights.append(_insight(
                "readiness_risk", p_severity,
                f"Readiness score {readiness if readiness is not None else 'n/a'} · risk {risk}",
                "Computed by the prediction engine from your completion, consistency, "
                "mock scores and streak.",
                metric={"readiness_score": readiness, "risk_level": risk},
            ))

        # Sort directives by priority (highest first) and cap at 6.
        directives = sorted(directives, key=lambda d: -d["priority"])[:6]
        return insights, directives

    def _safe_upcoming_tasks_for_analysis(
        self, user_id: str, plan_id: Optional[str], horizon: date
    ) -> List[Dict[str, Any]]:
        """Return pending roadmap tasks scheduled on/before `horizon` (defensive)."""
        if not plan_id:
            return []
        today = date.today()
        tasks = self._safe_list_tasks(user_id, plan_id)
        return [
            t for t in tasks
            if t.get("status") in ("pending", "in_progress")
            and t.get("scheduled_date")
            and today <= _parse_date(t["scheduled_date"]) <= horizon
        ]

    def _estimate_phase_index(self, start_date: Optional[date], plan: Dict[str, Any]) -> Optional[int]:
        """Estimate which roadmap phase the student is in (elapsed-time based)."""
        if not start_date:
            return None
        exam_raw = plan.get("exam_date") or plan.get("end_date")
        if not exam_raw:
            return None
        exam_date = _parse_date(exam_raw)
        if not exam_date or exam_date <= start_date:
            return None
        total_days = max((exam_date - start_date).days, 1)
        elapsed = max((date.today() - start_date).days + 1, 0)
        ratio = elapsed / total_days
        cumulative = 0.0
        for idx, key in enumerate(PHASE_KEYS):
            cumulative += PHASE_WEIGHTS.get(key, 0.0)
            if ratio <= cumulative:
                return idx
        return len(PHASE_KEYS) - 1

    # ==================================================================
    # Coaching message rendering (LLM polish + deterministic templates)
    # ==================================================================
    def _render(
        self,
        mode: str,
        ctx: Dict[str, Any],
        insights: List[Dict[str, Any]],
        directives: List[Dict[str, Any]],
        question: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Render the coach's natural-language message.

        Tries the LLM first (gpt-4o-mini grounded on the deterministic
        insights); falls back to a deterministic template so the mentor
        always coaches successfully.
        """
        brief = self._build_llm_brief(mode, ctx, insights, directives, question)
        polished = self._llm_polish(brief)
        if polished:
            content, tone = polished
            if content:
                return {"content": content, "tone": tone, "generated_by": "llm"}
        content, tone = self._template_message(mode, ctx, insights, directives, question)
        return {"content": content, "tone": tone, "generated_by": "template"}

    def _build_llm_brief(
        self,
        mode: str,
        ctx: Dict[str, Any],
        insights: List[Dict[str, Any]],
        directives: List[Dict[str, Any]],
        question: Optional[str] = None,
    ) -> str:
        """Serialize the deterministic coaching facts for the LLM."""
        payload = {
            "mode": mode,
            "learner_context": {
                "band_gap": ctx.get("band_gap"),
                "profile": ctx["profile"],
                "exam": ctx["exam"],
                "roadmap": ctx["roadmap"],
                "study_history": {k: v for k, v in ctx["study_history"].items()
                                  if k != "recent_sessions"},
                "missed_tasks": {k: v for k, v in ctx["missed_tasks"].items()
                                 if k != "last_scheduler_adjustments"},
                "prediction": ctx["prediction"],
            },
            "insights": insights,
            "directives": directives,
        }
        if question:
            payload["question"] = question
        return json.dumps(payload, default=str)

    def _template_message(
        self,
        mode: str,
        ctx: Dict[str, Any],
        insights: List[Dict[str, Any]],
        directives: List[Dict[str, Any]],
        question: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Deterministic template engine — always produces a coaching message."""
        roadmap = ctx["roadmap"]
        if not roadmap["has_active_plan"]:
            return self._template_roadmap_missing(ctx), "neutral"

        if mode == "roadmap_analysis":
            return self._template_roadmap(ctx, insights), "neutral"
        if mode == "risk_check":
            return self._template_risk(ctx, insights), self._pick_tone(ctx, "firm")
        if mode == "ask_mentor":
            return self._template_ask(ctx, question or "", insights), "neutral"
        if mode == "missed_day":
            return self._template_missed_day(ctx, insights), self._pick_tone(ctx, "encouraging")

        # daily_coaching (default)
        has_missed = any(i["type"] in ("missed_tasks", "overdue_pending") for i in insights)
        missed_days = ctx["study_history"].get("consecutive_missed_days") or 0
        if missed_days >= 1 and not ctx["study_history"].get("active_today"):
            return self._template_missed_day(ctx, insights), self._pick_tone(ctx, "encouraging")
        if has_missed:
            return self._template_daily_with_missed(ctx, insights), self._pick_tone(ctx, "firm")
        return self._template_daily_good(ctx), self._pick_tone(ctx, "encouraging")

    # ── Individual templates ──────────────────────────────────────────
    def _template_roadmap_missing(self, ctx: Dict[str, Any]) -> str:
        """Guidance when no roadmap exists — the mentor never invents one."""
        name = _first_name(ctx["profile"].get("full_name"))
        target = ctx["profile"].get("target_band")
        target_txt = f" toward band {target}" if target else ""
        greeting = f"{name}, " if name else ""
        return (
            f"{greeting}I can't coach you into exam shape until your personalized roadmap "
            f"exists — that's step one{target_txt}.\n\n"
            "Here's exactly what to do: complete your diagnostic test (or set your target band "
            "and exam date in your profile), then generate your roadmap from the Roadmap page. "
            "Your plan has to be built from your real band, your real exam date, and your real "
            "weakest skills — I'll never invent one for you.\n\n"
            "The moment your roadmap is live, I'll coach you through it every single day: "
            "which tasks to prioritize, when to revise, and when to run mocks."
        )

    def _template_daily_good(self, ctx: Dict[str, Any]) -> str:
        """Personalised morning briefing when the student is on track today."""
        return "\n\n".join(self._daily_sections(ctx))

    def _template_daily_with_missed(self, ctx: Dict[str, Any],
                                    insights: List[Dict[str, Any]]) -> str:
        """Morning briefing that leads with carried-forward work recovery."""
        name = _first_name(ctx["profile"].get("full_name"))
        missed = ctx["missed_tasks"]
        n = missed.get("recent_missed_7d") or missed.get("total_missed") or 0
        first = (missed.get("examples") or [{}])[0]
        title = first.get("title") or "your carried-forward task"
        skill = SKILL_LABELS.get(
            first.get("skill"), (first.get("skill") or "").title() or "general"
        )

        opener: List[str] = []
        if name:
            opener.append(f"{name}, let's get your roadmap back on track together.")
        else:
            opener.append("Let's get your roadmap back on track together.")
        if n:
            opener.append(
                f"The scheduler moved {n} task(s) forward for you. Before today's "
                f"missions, close out the top one: '{title}' ({skill}). It's still on "
                "your roadmap - it just got a new spot, and finishing it keeps "
                "everything from snowballing."
            )

        return "\n\n".join(opener + self._daily_sections(ctx))

    def _template_missed_day(self, ctx: Dict[str, Any],
                             insights: List[Dict[str, Any]]) -> str:
        """Personalised recovery briefing for when a student returns after missing days."""
        name = _first_name(ctx["profile"].get("full_name"))
        roadmap = ctx["roadmap"]
        hist = ctx["study_history"]
        profile = ctx["profile"]
        missed = ctx["missed_tasks"]
        pred = ctx["prediction"]
        exam = ctx["exam"]

        days = hist.get("consecutive_missed_days") or 0
        last_active = hist.get("last_active_iso") or "recently"
        carried = missed.get("recent_missed_7d") or missed.get("total_missed") or 0
        adjustments = len(missed.get("last_scheduler_adjustments") or [])
        budget = int(profile.get("daily_minutes_budget") or 60)
        target = profile.get("target_band")
        today_tasks = roadmap.get("today_tasks") or []

        sections: List[str] = []

        # Good morning / what changed
        greeting = f"Good morning, {name}." if name else "Good morning."
        if days >= 1:
            sections.append(
                f"{greeting} I noticed you've been away for {days} day(s) - "
                f"last session {last_active}."
            )
            sections.append(
                f"What changed: the Adaptive Scheduler automatically carried {carried} "
                f"of your roadmap task(s) forward across {adjustments} adjustment(s) and "
                "rebalanced your upcoming workload so nothing piled up unfairly. Your "
                f"roadmap '{roadmap.get('title') or 'plan'}' is intact - it just shifted "
                "to make room for a clean comeback."
            )
        else:
            sections.append(greeting)
            sections.append(
                "What changed: your roadmap is unchanged and waiting. Today's schedule "
                "has been set to your target daily block to keep momentum steady."
            )

        # Encouragement (never shame)
        sections.append(
            "Taking time off isn't falling behind - it's how sustainable prep works. "
            "The plan is still here, and today is a fresh chance to step back in without "
            "pressure."
        )

        # Today's updated workload
        if today_tasks:
            lines = [
                f"Today's updated workload (~{budget} minutes) - the scheduler set this "
                "lighter load for you:"
            ]
            for t in today_tasks[:4]:
                skill = SKILL_LABELS.get(
                    t.get("skill"), (t.get("skill") or "general").title()
                )
                lines.append(f"  - {t.get('title')} ({skill})")
            sections.append("\n".join(lines))
        else:
            sections.append(
                f"Today's updated workload: the scheduler set today to ~{budget} minutes "
                "(lighter than usual) to help you rebuild momentum. Complete one task and "
                "log it - that's enough."
            )

        # Estimated impact on target band
        ready = pred.get("readiness_score")
        risk = (pred.get("risk_level") or "unknown")
        est = pred.get("estimated_band")
        readiness_txt = f"{ready:.0f}" if isinstance(ready, (int, float)) else "n/a"
        est_txt = f"about {est}" if est is not None else "in progress"
        days_remaining = exam.get("days_remaining")
        countdown = (
            f" {days_remaining} days remain until your exam."
            if days_remaining is not None
            else ""
        )
        sections.append(
            f"Impact on your target: your readiness is {readiness_txt} ({risk}), which "
            f"currently projects to {est_txt} against your band {target} goal. The gap is "
            "recoverable - each logged task lifts readiness and pushes the projection back "
            "toward target. One focused block today opens more distance than you might "
            "expect." + countdown
        )

        # Motivation + next step
        streak = hist.get("current_streak") or 0
        if streak:
            sections.append(
                f"You've already built a {streak}-day streak before - muscle memory is "
                "real. Restarting is always easier the second time. Show up for the first "
                "25-minute block and the rest follows."
            )
        else:
            sections.append(
                "Momentum loves a gentle restart. Finish one small task, log it, and let "
                "the Adaptive Scheduler rebuild from there."
            )
        sections.append(
            "Next step: start a task, mark it Complete, then log the session. The "
            "Adaptive Scheduler will read that signal and rebalance tomorrow's plan for "
            "you. No need to catch up everything - just show up for today."
        )
        return "\n\n".join(sections)

    # -- Morning-briefing section builders --------------------------------
    def _daily_sections(self, ctx: Dict[str, Any]) -> List[str]:
        """Assemble the personalised morning briefing (always deterministic)."""
        return [
            self._daily_greeting(ctx),
            self._daily_mission(ctx),
            self._daily_why_it_matters(ctx),
            self._daily_estimated_time(ctx),
            self._daily_motivation(ctx),
            self._daily_exam_countdown(ctx),
            self._daily_yesterday_tip(ctx),
        ]
    def _daily_greeting(self, ctx: Dict[str, Any]) -> str:
        """Warm, tutor-style morning opener; always deterministic, never shame."""
        name = _first_name(ctx["profile"].get("full_name"))
        hist = ctx["study_history"]
        streak = int(hist.get("current_streak") or 0)
        active_today = bool(hist.get("active_today"))
        day_of = date.today().strftime("%A")
        greeting = f"Good morning, {name}." if name else "Good morning."
        if streak and active_today:
            greeting += f" You're on a {streak}-day streak - keep riding that momentum into today."
        elif streak:
            greeting += f" You've already built a {streak}-day streak before; showing up today brings it right back."
        else:
            greeting += " A fresh day is a fresh chance to add distance between where you are and where you want to be."
        return greeting + f" Here's your personalised IELTS coaching briefing for {day_of}."
    def _daily_mission(self, ctx: Dict[str, Any]) -> str:
        roadmap = ctx["roadmap"]
        today_tasks = roadmap.get("today_tasks") or []
        phase = _phase_label(roadmap["current_phase_index"])
        title = roadmap.get("title") or "your roadmap"
        if today_tasks:
            lines = [f"Today's mission on your roadmap - {title} ({phase} phase):"]
            for t in today_tasks[:5]:
                skill = SKILL_LABELS.get(
                    t.get("skill"), (t.get("skill") or "general").title()
                )
                lines.append(f"  - {t.get('title')} ({skill})")
            if len(today_tasks) > 5:
                lines.append(f"  - ...plus {len(today_tasks) - 5} more.")
            return "\n".join(lines)
        by_skill = roadmap.get("upcoming_by_skill_7d") or {}
        if by_skill:
            coverage = ", ".join(
                f"{SKILL_LABELS.get(s, s.title())} ({n})" for s, n in by_skill.items()
            )
            return (f"Today's mission on your roadmap - {title} ({phase} phase): no task "
                    f"pinned to today, so cover the week ahead: {coverage}.")
        return ("Today's mission on your roadmap - "
                f"{title} ({phase} phase): follow the roadmap's daily order - finish the "
                "next scheduled task and log it.")

    def _daily_why_it_matters(self, ctx: Dict[str, Any]) -> str:
        profile = ctx["profile"]
        roadmap = ctx["roadmap"]
        weakest = profile.get("weakest_skills") or []
        target = profile.get("target_band")
        phase = _phase_label(roadmap["current_phase_index"])
        skills_txt = (", ".join(SKILL_LABELS.get(s, s.title()) for s in weakest[:2])
                      or "your target skills")
        target_txt = f" toward band {target}" if target else ""
        return (
            f"Why this matters: every task in the {phase} phase is weighted around your exam "
            f"date and weakest areas ({skills_txt}){target_txt}. Completing them in order is "
            "what converts study time into real band gains - the roadmap already knows the "
            "sequence that works for you."
        )

    def _daily_estimated_time(self, ctx: Dict[str, Any]) -> str:
        profile = ctx["profile"]
        hist = ctx["study_history"]
        budget = int(profile.get("daily_minutes_budget") or 60)
        done = int(hist.get("today_minutes") or 0)
        done_tasks = int(hist.get("today_tasks_completed") or 0)
        remaining = max(budget - done, 0)
        return (
            f"Estimated study time: {done}/{budget} minutes logged today ({done_tasks} "
            f"task(s) done). Aim for the remaining ~{remaining} minutes - that's the daily "
            "block the roadmap designed for you."
        )
    def _daily_motivation(self, ctx: Dict[str, Any]) -> str:
        roadmap = ctx["roadmap"]
        hist = ctx["study_history"]
        band_gap = ctx.get("band_gap")
        progress = roadmap.get("progress_percent") or 0.0
        streak = hist.get("current_streak") or 0
        target = ctx["profile"].get("target_band")
        parts = [f"You're {progress:.0f}% of the way through your roadmap."]
        if band_gap is not None:
            parts.append(f"With {band_gap:.1f} band(s) left to {target}, consistency is the "
                         "fastest lever you have.")
        if streak:
            parts.append(f"That {streak}-day streak proves you can show up on the days that "
                         "count - keep stacking small wins.")
        else:
            parts.append("A short session today beats a skipped day - start the timer and "
                         "win the first block.")
        return " ".join(parts)

    def _daily_exam_countdown(self, ctx: Dict[str, Any]) -> str:
        exam = ctx["exam"]
        days = exam.get("days_remaining")
        intensity = (exam.get("intensity") or "normal").replace("_", " ")
        if days is None:
            return ("Exam countdown: no exam date set yet - lock one in so your roadmap "
                    "can weight your work.")
        return (f"Exam countdown: {days} day(s) to your IELTS exam. Current intensity: "
                f"{intensity}. The roadmap's schedule is already counting this down - trust it.")

    def _daily_yesterday_tip(self, ctx: Dict[str, Any]) -> str:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        sessions = ctx["study_history"].get("recent_sessions") or []
        for s in sessions:
            sdate = s.get("activity_date") or s.get("date")
            if sdate == yesterday:
                minutes = int(s.get("minutes") or 0)
                skill = SKILL_LABELS.get(
                    s.get("skill"), (s.get("skill") or "general").title()
                )
                tasks = int(s.get("tasks") or s.get("tasks_completed") or 0)
                if minutes > 0:
                    return ("Tip from yesterday: you studied "
                            f"{minutes} min ({skill}, {tasks} task(s)). Carry that same "
                            "rhythm into today - build on it, don't fight it.")
        return ("Tip from yesterday: nothing logged yesterday, so start today with a "
                "single focused skill block - a 25-minute win resets the momentum.")

    def _template_roadmap(self, ctx: Dict[str, Any], insights: List[Dict[str, Any]]) -> str:
        """Deep analysis of the existing roadmap."""
        roadmap = ctx["roadmap"]
        exam = ctx["exam"]
        missed = ctx["missed_tasks"]
        coverage = next(
            (i for i in insights if i["type"] == "weak_skill_coverage"), None
        )
        text = [
            "Here's how your roadmap looks right now.",
            (
                f"You're in the {_phase_label(roadmap['current_phase_index'])} phase, "
                f"{roadmap['progress_percent']:.1f}% complete ({roadmap['completed_tasks']} of "
                f"{roadmap['total_tasks']} tasks done)."
            ),
        ]
        if missed.get("total_missed"):
            text.append(
                f"{missed['total_missed']} task(s) were marked missed and carried forward — "
                "they're still part of this roadmap, scheduled into your coming days."
            )
        if coverage:
            text.append(coverage["detail"])
        if exam.get("days_remaining") is not None:
            text.append(
                f"{exam['days_remaining']} day(s) remain — the roadmap is weighted accordingly "
                f"({_phase_label(roadmap['current_phase_index'])} work now, revision and mocks later)."
            )
        text.append(
            "Stick to the order the roadmap sets. If a day feels heavy, the scheduler has "
            "already balanced it; complete the priority-5 tasks first."
        )
        return "\n\n".join(text)

    def _template_risk(self, ctx: Dict[str, Any], insights: List[Dict[str, Any]]) -> str:
        """Direct, honest risk assessment grounded in roadmap data."""
        exam = ctx["exam"]
        missed = ctx["missed_tasks"]
        pred = ctx["prediction"]
        risk_txt = "unknown"
        if pred.get("risk_level"):
            risk_txt = pred["risk_level"]
        text = [
            f"Straight talk: your current risk level is '{risk_txt}'.",
        ]
        days = exam.get("days_remaining")
        if days is not None:
            if days <= CRUNCH_WINDOW_DAYS:
                text.append(
                    f"You're {days} day(s) from the exam. This is the final stretch — protection "
                    "mode: mocks and revision only, exactly as your roadmap schedules them."
                )
            else:
                text.append(f"With {days} day(s) left, there is real time to change the outcome.")
        if missed.get("total_missed"):
            text.append(
                f"The biggest leak right now is the {missed['total_missed']} missed task(s) "
                "piling up. Clear the highest-priority carried-forward tasks first."
            )
        text.append(
            "Do not add new material. Do not restart your roadmap. Execute what's scheduled, "
            "log your sessions, and the numbers will move."
        )
        return "\n\n".join(text)

    def _template_ask(self, ctx: Dict[str, Any], question: str,
                      insights: List[Dict[str, Any]]) -> str:
        """Answer a student question strictly within the existing roadmap.

        Routing (priority order):
          1. Plan-building requests -> refused, anchored to the existing roadmap.
          2. Predicted-band / readiness questions -> grounded diagnosis.
          3. IELTS question-type knowledge -> a short factual explanation.
          4. Skill-practice questions -> grounded, weakest-skill-focused answer.

        Everything is anchored in the learner's real context (ctx); the mentor
        never invents a plan and never answers with generic tips only.
        """
        q = (question or "").lower()
        roadmap = ctx["roadmap"]

        # 1) Plan-building refusal (never invent a plan).
        if any(k in q for k in self._PLAN_KEYWORDS):
            if not roadmap["has_active_plan"]:
                return self._template_roadmap_missing(ctx)
            title = roadmap.get("title") or "your roadmap"
            return (
                "I coach inside your existing roadmap - I won't invent a new one. Your current "
                f"roadmap, '{title}', is already weighted around your exam date and weak skills. "
                "If it needs reshaping (for example, a new exam date), regenerate it from the "
                "Roadmap page with your updated dates - then I'll coach the new version. "
                "Tell me what's worrying you about the current week and I'll give you concrete "
                "next steps."
            )

        # 2) Predicted-band / readiness diagnosis.
        if self._is_band_diagnosis_question(q):
            return self._answer_band_diagnosis(ctx, insights)

        # 3) IELTS question-type knowledge explanations.
        explanation = self._explain_question_type(q)
        if explanation:
            return explanation

        # 4) Default: grounded, weakest-skill-focused coaching.
        return self._answer_skill_question(ctx, insights)

    # Phrasing that signals a plan-building request the mentor must refuse.
    _PLAN_KEYWORDS = (
        "plan", "schedule", "roadmap", "study plan", "new tasks", "add task",
        "build me", "make me", "build a new", "make a new",
    )

    @classmethod
    def _is_band_diagnosis_question(cls, q: str) -> bool:
        """True for 'why is my predicted band / readiness' style questions."""
        return (
            ("predicted" in q and ("band" in q or "score" in q))
            or ("estimated band" in q)
            or ("why is my" in q and ("band" in q or "predicted" in q or "score" in q))
            or ("why am i" in q and ("band" in q or "predicted" in q))
            or ("lower than" in q and ("target" in q or "band" in q))
            or ("higher than" in q and ("target" in q or "band" in q))
            or ("readiness" in q)
            or ("risk level" in q)
        )

    @classmethod
    def _explain_question_type(cls, q: str) -> Optional[str]:
        """Short factual answers for IELTS question-type knowledge.

        Only fires for ``explain / what-is / how-does`` style questions so that
        improvement-style questions still fall through to the grounded handler.
        Returns None when the question isn't a known question type.
        """
        is_knowledge_q = any(
            w in q for w in (
                "explain", "what is", "what are", "what does", "what's",
                "meaning of", "how does", "tell me", "i don't understand",
                "i'm confused", "struggle with",
            )
        )
        if not is_knowledge_q:
            return None

        answers = {
            "true_false_ng": (
                "True / False / Not Given is an IELTS Academic Reading question type. For each "
                "statement you decide: TRUE if it AGREES with the information, FALSE if it "
                "CONTRADICTS it, and NOT GIVEN if the text does not say enough to decide. Anchor "
                "every answer ONLY in specific words from the passage - ignore your own knowledge "
                "- and watch the trap where 'Not Given' feels like 'wrong': it is only correct "
                "when the text genuinely leaves the point open."
            ),
            "yes_no_ng": (
                "Yes / No / Not Given is the General Training Reading equivalent. YES means the "
                "statement agrees with the text, NO means it contradicts it, and NOT GIVEN means "
                "the text does not state it. Same rule: answer from the passage alone, never from "
                "general knowledge, and treat 'Not Given' as 'not stated', not 'wrong'."
            ),
            "matching": (
                "Matching asks you to pick ONE correct option per item from a pool. Read the word "
                "limit first, then use keywords to locate each match in the paragraph. You do NOT "
                "have to answer in order - grab the easiest items first and write only the letter "
                "in the correct box."
            ),
            "map": (
                "Maps / Diagrams describe how something CHANGES. Open with an overview (before vs "
                "after, the general trend), then group the body into 2-3 logical paragraphs (for "
                "example 'the north', 'the south'). Paraphrase the question in your first sentence "
                "and stay factual - you are describing, not giving opinions."
            ),
            "overview": (
                "Bar charts / line graphs start with an OVERVIEW: the overall trend plus the "
                "highest and lowest figures. Then compare just 2-3 logical categories and report "
                "the key numbers using a range ('about 20%'), never listing every single figure. "
                "Paraphrase the topic in your opening sentence."
            ),
            "task_response": (
                "Task Response means fully answering ALL parts of the task with a clear position "
                "you maintain throughout. For Task 2: state your view in the introduction, back "
                "up every paragraph with it, and answer the writer's 'why / how' - not just 'how'."
            ),
            "coherence": (
                "Coherence = clear paragraphing. One idea plus one example plus a topic sentence "
                "per paragraph, linked with signposts (First...; Next...; In contrast...; "
                "Overall...). Use 1-2 cohesive devices per paragraph and avoid over-linking."
            ),
            "band_descriptors": (
                "IELTS is scored in 0.5 bands against the public Band Descriptors. Higher bands "
                "reward fewer errors across Task Response, Coherence, Lexical Resource and "
                "Grammar. To raise a band: pin down the error type that caps you right now, widen "
                "your topic vocabulary, and practise shifting from a complex idea to simple "
                "grammar. Each 0.5 band typically needs one focused skill area done hard."
            ),
            "general": (
                "Improvement comes from targeted weakness work, not generic effort. Attack the "
                "skill where your band is lowest, sit a full past paper under timed conditions, "
                "and trace every error back to a PATTERN before the next attempt - two error "
                "reviews move one band more than three careless repeats."
            ),
        }

        if "not given" in q or "true/false" in q or "true, false" in q:
            if "yes" in q or "yes/no" in q or ("no," in q and "not" not in q):
                return answers["yes_no_ng"]
            return answers["true_false_ng"]
        if "matching" in q:
            return answers["matching"]
        if "map" in q or "diagram" in q or "flow" in q:
            return answers["map"]
        if "overview" in q or "bar chart" in q or "line graph" in q or "chart" in q or "graph" in q:
            return answers["overview"]
        if "task response" in q or "task 2" in q:
            return answers["task_response"]
        if "coherence" in q or "paragraph" in q or "linking" in q:
            return answers["coherence"]
        if "band descriptor" in q or "how is" in q or "scoring" in q:
            return answers["band_descriptors"]
        if "improve" in q or "get a higher" in q or "raise" in q or "higher band" in q or "better score" in q:
            return answers["general"]
        return None

    def _answer_band_diagnosis(self, ctx: Dict[str, Any],
                               insights: List[Dict[str, Any]]) -> str:
        """Explain the predicted band using the learner's real prediction data."""
        pred = ctx.get("prediction") or {}
        profile = ctx["profile"]
        roadmap = ctx["roadmap"]
        target = profile.get("target_band")
        estimated = pred.get("estimated_band")
        band_gap = ctx.get("band_gap")
        readiness = pred.get("readiness_score")
        completion = pred.get("completion_rate")
        consistency = pred.get("study_consistency")
        risk = (pred.get("risk_level") or "").lower()

        weakest = profile.get("weakest_skills") or []
        skill_bands = profile.get("skill_bands") or {}
        weakest_skill = weakest[0] if weakest else None
        wband = skill_bands.get(weakest_skill) if weakest_skill else None

        missed = ctx.get("missed_tasks") or {}
        recent_missed = missed.get("recent_missed_7d") or missed.get("total_missed") or 0
        completed = roadmap.get("completed_tasks", 0)
        total = roadmap.get("total_tasks", 0)

        parts = ["Great question - let's anchor it in your real data."]
        if estimated is not None and target is not None:
            gap_txt = f"{band_gap:.1f} band(s)" if band_gap is not None else "a gap"
            parts.append(
                f"Right now your estimated band is {estimated}, about {gap_txt} below "
                f"your target of {target}."
            )
        elif band_gap is not None and target is not None:
            parts.append(
                f"Right now you're {band_gap:.1f} band(s) from your target of {target}."
            )
        else:
            parts.append("Right now the model is still building a band estimate from your activity.")

        levers = []
        if readiness is not None:
            levers.append(f"readiness score ({readiness}/100)")
        if completion is not None:
            levers.append(f"completion rate ({completion}% of your roadmap done)")
        if consistency is not None:
            levers.append(f"study consistency ({consistency}% active-day ratio)")
        if levers:
            parts.append("The prediction blends: " + ", ".join(levers) + ".")
        if risk:
            parts.append(f"My read on the risk: {risk}.")

        if weakest_skill and wband is not None and target is not None:
            try:
                drag = round(float(target) - float(wband), 1)
                gap_word = f"~{drag:.1f} band(s)"
            except (TypeError, ValueError):
                gap_word = "a gap"
            parts.append(
                f"Your weakest skill is {weakest_skill.title()} at band {wband}; closing that "
                f"{gap_word} is usually the fastest lever."
            )

        if total > 0:
            parts.append(
                f"Your roadmap shows {completed}/{total} tasks done, with {recent_missed} "
                "carried-forward (missed) task(s) this week - finish those first, and schedule the "
                "next mock: mocks are weighted the heaviest in the band blend."
            )
        parts.append(
            "Do the next scheduled task, note exactly what's hard, and bring it back to me - "
            "that's how we turn practice into bands."
        )
        return "\n\n".join(parts)

    def _answer_skill_question(self, ctx: Dict[str, Any],
                               insights: List[Dict[str, Any]]) -> str:
        """Grounded, weakest-skill-focused coaching for practice questions."""
        profile = ctx["profile"]
        roadmap = ctx["roadmap"]
        band_gap = ctx.get("band_gap")
        weakest = profile.get("weakest_skills") or []
        weakest_skill = weakest[0] if weakest else None

        summary_parts = []
        if band_gap is not None:
            summary_parts.append(f"you're {band_gap:.1f} band(s) from target")
        if roadmap.get("has_active_plan"):
            summary_parts.append(
                f"your roadmap is {roadmap.get('progress_percent', 0):.0f}% complete"
            )
        context_line = ", and ".join(summary_parts) or "here's your situation"

        focus = ""
        if weakest_skill:
            focus = (f" The single highest-leverage move is to practice "
                     f"{weakest_skill.title()} - it's where a half-band is most available for "
                     "you right now.")

        return (
            "Great question - let's anchor it in your real data. Right now " + context_line
            + ".\n\nRather than a generic tip, look at what your own roadmap schedules next: "
            "those tasks ARE the answer to your question. Do them in order, note what's hard, "
            "and bring that specific difficulty back to me - that's how we turn practice into "
            "bands." + focus
        )

    def _pick_tone(self, ctx: Dict[str, Any], fallback: str) -> str:
        """Choose a message tone from the risk context (deterministic)."""
        pred = ctx.get("prediction") or {}
        risk = (pred.get("risk_level") or "").lower()
        if risk in ("critical", "high"):
            return "urgent"
        if risk in ("medium", "moderate"):
            return "firm"
        return fallback

    # ==================================================================
    # LLM polish (optional) + persistence
    # ==================================================================
    def _llm_polish(self, brief: str) -> Optional[Tuple[str, str]]:
        """
        Ask gpt-4o-mini to polish the coaching wording from the deterministic
        brief. Returns (content, tone) or None so the template always wins.
        """
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            return None
        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": IELTS_MENTOR_PROMPT},
                            {"role": "user", "content": brief},
                        ],
                        "temperature": 0.4,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                text = str(parsed.get("content") or "").strip()
                tone = str(parsed.get("tone") or "neutral").strip()
                if not text:
                    return None
                return text, tone
        except Exception as exc:  # LLM is polish-only; never break coaching
            logger.info("mentor LLM polish failed: %s", exc)
            return None

    def _finalize(
        self,
        user_id: str,
        mode: str,
        ctx: Dict[str, Any],
        insights: List[Dict[str, Any]],
        directives: List[Dict[str, Any]],
        rendered: Dict[str, Any],
        user_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist the conversation/messages (when possible) and build the response."""
        guardrails = {
            "never_generates_plan": True,
            "plan_generation_triggered": False,
            "analysis_source": "existing_roadmap",
            "note": "The AI Mentor coaches within the student's existing roadmap and never "
                    "generates a study plan from scratch.",
        }
        structured = {
            "insights": insights,
            "directives": directives,
            "guardrails": guardrails,
            "context_summary": self._context_summary(ctx),
        }
        title = self._conversation_title(mode, ctx)
        snapshot = self._compact_context(ctx)

        conv = self._safe_create_conversation(user_id, mode, title, snapshot)
        self._safe_add_message(
            conv, user_id, "mentor", rendered["content"],
            {**structured, "message_meta": {"tone": rendered["tone"],
                                            "generated_by": rendered["generated_by"]}},
        )
        if user_message:
            self._safe_add_message(conv, user_id, "user", user_message)

        return {
            "conversation_id": (conv or {}).get("id"),
            "mode": mode,
            "created_at": _now_iso(),
            "title": title,
            "message": {
                "role": "mentor",
                "content": rendered["content"],
                "generated_by": rendered["generated_by"],
                "tone": rendered["tone"],
            },
            "context_summary": structured["context_summary"],
            "insights": insights,
            "directives": directives,
            "guardrails": guardrails,
        }

    def _conversation_title(self, mode: str, ctx: Dict[str, Any]) -> str:
        """Short, human-readable conversation title by mode."""
        titles = {
            "daily_coaching": "Daily coaching",
            "roadmap_analysis": "Roadmap analysis",
            "risk_check": "Risk check",
            "ask_mentor": "Ask the mentor",
            "missed_day": "Missed day coaching",
        }
        return titles.get(mode, "Coaching session")

    def _context_summary(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Curated summary the frontend can render without parsing full context."""
        roadmap = ctx["roadmap"]
        hist = ctx["study_history"]
        missed = ctx["missed_tasks"]
        pred = ctx["prediction"]
        exam = ctx["exam"]
        return {
            "exam_date": exam.get("exam_date"),
            "days_remaining": exam.get("days_remaining"),
            "intensity": exam.get("intensity"),
            "current_band": ctx["profile"].get("current_band"),
            "target_band": ctx["profile"].get("target_band"),
            "band_gap": ctx.get("band_gap"),
            "weakest_skills": ctx["profile"].get("weakest_skills") or [],
            "strongest_skills": ctx["profile"].get("strongest_skills") or [],
            "has_diagnostic": ctx["profile"].get("has_diagnostic"),
            "has_active_roadmap": roadmap.get("has_active_plan"),
            "roadmap_title": roadmap.get("title"),
            "roadmap_phase": _phase_label(roadmap.get("current_phase_index")),
            "roadmap_progress_percent": roadmap.get("progress_percent"),
            "missed_tasks": missed.get("total_missed"),
            "readiness_score": pred.get("readiness_score"),
            "risk_level": pred.get("risk_level"),
            "streak": hist.get("current_streak"),
            "consistency_percent": hist.get("consistency_percent"),
        }

    def _compact_context(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Small, JSON-safe snapshot stored on the conversation row."""
        return {
            "profile": dict(ctx["profile"]),
            "exam": ctx["exam"],
            "roadmap": dict(ctx["roadmap"]),
            "study_history": {k: v for k, v in ctx["study_history"].items()
                              if k != "recent_sessions"},
            "missed_tasks": {k: v for k, v in ctx["missed_tasks"].items()
                             if k != "last_scheduler_adjustments"},
            "prediction": ctx["prediction"],
            "band_gap": ctx.get("band_gap"),
        }

    # ==================================================================
    # Safe DB wrappers (never raise — mirror prediction_engine)
    # ==================================================================
    def _safe_get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.user_repo.get_profile(user_id)
        except NotFoundError:
            return None
        except Exception as exc:
            logger.warning("mentor get_profile failed user=%s: %s", user_id, exc)
            return None

    def _safe_resolve_profile(self, user_id: str) -> Dict[str, Any]:
        try:
            return diagnostic_roadmap_service.resolve_profile(user_id)
        except Exception as exc:
            logger.warning("mentor resolve_profile failed user=%s: %s", user_id, exc)
            return {}

    def _safe_get_active_plan(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.study_plan_repo.get_active(user_id)
        except Exception as exc:
            logger.warning("mentor get_active plan failed user=%s: %s", user_id, exc)
            return None

    def _safe_list_tasks(self, user_id: str, plan_id: Optional[str]) -> List[Dict[str, Any]]:
        if self.db is None or not plan_id:
            return []
        try:
            return self.task_repo.list_for_user(user_id=user_id, study_plan_id=plan_id)
        except Exception as exc:
            logger.warning("mentor list tasks failed user=%s: %s", user_id, exc)
            return []

    def _safe_get_progress_state(self, user_id: str) -> Dict[str, Any]:
        if self.db is None:
            return {}
        try:
            return self.progress_repo.get_state(user_id)
        except Exception as exc:
            logger.warning("mentor get_state failed user=%s: %s", user_id, exc)
            return {}

    def _safe_get_day_stats(self, user_id: str, day: date) -> Dict[str, Any]:
        if self.db is None:
            return {}
        try:
            return self.progress_repo.get_day_stats(user_id, day)
        except Exception as exc:
            logger.warning("mentor get_day_stats failed user=%s: %s", user_id, exc)
            return {}

    def _safe_get_period_progress(
        self, user_id: str, start: date, end: date
    ) -> Dict[str, Any]:
        if self.db is None:
            return {}
        try:
            return self.progress_repo.get_period_progress(user_id, start, end)
        except Exception as exc:
            logger.warning("mentor period progress failed user=%s: %s", user_id, exc)
            return {}

    def _safe_count_active_days(self, user_id: str) -> int:
        if self.db is None:
            return 0
        try:
            query = (
                self.db.table("daily_stats")
                .select("*", count="exact")
                .eq("user_id", user_id)
                .eq("is_active", True)
            )
            result = self.db.execute(query, "count mentor active days")
            return result.count or 0
        except Exception as exc:
            logger.warning("mentor count active days failed user=%s: %s", user_id, exc)
            return 0

    def _days_since_first_active(self, user_id: str) -> Optional[int]:
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("daily_stats")
                .select("stats_date")
                .eq("user_id", user_id)
                .eq("is_active", True)
                .order("stats_date")
                .limit(1)
            )
            result = self.db.execute(query, "mentor first active date")
            if not result.data or not result.data[0].get("stats_date"):
                return None
            first = _parse_date(result.data[0]["stats_date"])
            return max((date.today() - first).days + 1, 1)
        except Exception as exc:
            logger.warning("mentor first active failed user=%s: %s", user_id, exc)
            return None

    def _safe_get_history(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.progress_repo.get_history(user_id, limit=limit)
        except Exception as exc:
            logger.warning("mentor history failed user=%s: %s", user_id, exc)
            return []

    def _safe_list_adjustments(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.scheduler_repo.list_adjustments(user_id, limit=limit)
        except Exception as exc:
            logger.warning("mentor adjustments failed user=%s: %s", user_id, exc)
            return []

    def _safe_create_conversation(
        self, user_id: str, mode: str, title: str, snapshot: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.mentor_repo.create_conversation(user_id, mode, title, snapshot)
        except Exception as exc:
            logger.warning("mentor create conversation failed user=%s: %s", user_id, exc)
            return None

    def _safe_add_message(
        self, conv: Optional[Dict[str, Any]], user_id: str, role: str,
        content: str, structured: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if self.db is None or not conv or not conv.get("id"):
            return None
        try:
            return self.mentor_repo.add_message(conv["id"], user_id, role, content, structured)
        except Exception as exc:
            logger.warning("mentor add message failed user=%s: %s", user_id, exc)
            return None

    def _safe_get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.mentor_repo.get_conversation(conversation_id, user_id)
        except Exception as exc:
            logger.warning("mentor get conversation failed user=%s: %s", user_id, exc)
            return None

    def _safe_list_conversations(
        self, user_id: str, mode: Optional[str], limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.mentor_repo.list_conversations(
                user_id, mode=mode, limit=limit, offset=offset
            )
        except Exception as exc:
            logger.warning("mentor list conversations failed user=%s: %s", user_id, exc)
            return []

    def _safe_count_conversations(self, user_id: str, mode: Optional[str]) -> int:
        if self.db is None:
            return 0
        try:
            return self.mentor_repo.count_conversations(user_id, mode=mode)
        except Exception as exc:
            logger.warning("mentor count conversations failed user=%s: %s", user_id, exc)
            return 0

    def _safe_list_messages(self, conversation_id: str, user_id: str) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.mentor_repo.list_messages(conversation_id, user_id)
        except Exception as exc:
            logger.warning("mentor list messages failed user=%s: %s", user_id, exc)
            return []

    def _safe_count_messages(self, conversation_id: Optional[str]) -> int:
        if self.db is None or not conversation_id:
            return 0
        try:
            return self.mentor_repo.count_messages(conversation_id)
        except Exception as exc:
            logger.warning("mentor count messages failed conv=%s: %s", conversation_id, exc)
            return 0

    def _safe_get_last_message_at(self, conversation_id: Optional[str]) -> Optional[str]:
        if self.db is None or not conversation_id:
            return None
        try:
            return self.mentor_repo.get_last_message_at(conversation_id)
        except Exception as exc:
            logger.warning("mentor last message failed conv=%s: %s", conversation_id, exc)
            return None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _insight(
    insight_type: str,
    severity: str,
    title: str,
    detail: str,
    skill: Optional[str] = None,
    metric: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an insight dict (used by the deterministic analysis)."""
    return {
        "type": insight_type,
        "severity": severity,
        "title": title,
        "detail": detail,
        "skill": skill,
        "metric": metric or {},
    }


def _directive(
    priority: int,
    action: str,
    detail: str,
    skill: Optional[str] = None,
    ref: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a coaching directive dict (always references roadmap items)."""
    return {
        "priority": priority,
        "action": action,
        "detail": detail,
        "skill": skill,
        "ref": ref,
    }


def _parse_date(value: Any) -> Optional[date]:
    """Robustly parse a date/datetime/ISO string into a date."""
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


def _as_iso_date(value: Any) -> Optional[str]:
    """Parse a value into a date and return its ISO string (or None)."""
    d = _parse_date(value)
    return d.isoformat() if d else None


def _intensity(days_remaining: Optional[int]) -> Optional[str]:
    """Map remaining days to an exam-intensity label (matches exam_countdown)."""
    if days_remaining is None:
        return None
    if days_remaining < INTENSITY_FINAL_DAYS:
        return "final"
    if days_remaining < INTENSITY_INTENSIVE_DAYS:
        return "intensive"
    if days_remaining < INTENSITY_FOCUSED_DAYS:
        return "focused"
    return "normal"


def _phase_label(phase_index: Optional[int]) -> str:
    """Map a phase index back to its human-readable label."""
    if phase_index is None or not (0 <= phase_index < len(PHASE_KEYS)):
        return "Structured preparation"
    return PHASE_LABELS.get(PHASE_KEYS[phase_index], "Structured preparation")


def _first_name(full_name: Any) -> str:
    """Extract the student's first name for the coaching greeting."""
    if not full_name:
        return ""
    parts = str(full_name).strip().split()
    return parts[0] if parts else ""


def _consecutive_missed_days(state: Dict[str, Any], today: date) -> int:
    """Whole days since the student's last logged activity (>= 0)."""
    last = _parse_date(state.get("last_active_date"))
    if last is None:
        return 0
    return max((today - last).days, 0)


def _now_iso() -> str:
    """ISO-8601 UTC timestamp used in responses/snapshots."""
    return datetime.now(timezone.utc).isoformat()


# Singleton bound to the shared DB session.
from app.db.session import db_session

ai_mentor_service = AIMentorService(db_session)