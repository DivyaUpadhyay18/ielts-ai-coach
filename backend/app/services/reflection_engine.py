"""
Mission Reflection engine.

After a daily mission is completed, this engine synthesises a structured
reflection from the learner's *existing* data and persists one row per
completed mission:

    Today's strengths  ·  Today's mistakes  ·  Areas to revise
    ·  Tomorrow's focus  ·  Confidence level  ·  Estimated improvement

Everything is **deterministic** (rules + thresholds, NO AI). The engine reuses
the learner snapshot already built by the AI Mentor service
(``ai_mentor_service.get_context``), so reflections are always grounded in the
same context the mentor reasons about.

Like the rest of the codebase, every DB read is defensive: the engine works
with ``db=None`` (tests) and **never** fails a mission completion because a
table is missing or Supabase is unreachable — persistence is best-effort.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, Optional

from app.core.exceptions import ConflictError
from app.models.mission_reflection import ReflectionData
from app.repositories.daily_mission_repo import DailyMissionRepository
from app.repositories.mission_reflection_repo import MissionReflectionRepository
from app.services.diagnostic_roadmap_service import SKILL_LABELS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants (deterministic — no AI)
# ---------------------------------------------------------------------------
STREAK_CAP = 30                 # streak days that yield a full streak score
# band_gap -> raw-confidence penalty (applied at the configured threshold)
CONF_BAND_PENALTY = {1.5: 8, 1.0: 4, 0.5: 2}
IMPROVEMENT_MAX = 1.0          # cap projected band gain per mission
COMPLETION_HEALTHY = 70.0       # completion % that earns a "healthy" strength
CONSISTENCY_HEALTHY = 70.0      # consistency % that earns a "solid" strength
LOW_RATE = 50.0                 # completion/consistency below this -> a mistake
READINESS_STRONG = 60.0         # readiness score that earns improvement momentum

ContextProvider = Callable[[str], Dict[str, Any]]


# ---------------------------------------------------------------------------
# Pure helpers (testable without a DB)
# ---------------------------------------------------------------------------
def _lab(skill: Any) -> str:
    """Human-readable skill label with a graceful fallback."""
    if not skill:
        return "this skill"
    key = str(skill).lower()
    label = SKILL_LABELS.get(key)
    if label:
        return label
    return key.replace("_", " ").title()


def _to_date(value: Any) -> Optional[date]:
    """Parse a date/datetime/ISO-string into a date (or None)."""
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


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _minimal_context(user_id: str) -> Dict[str, Any]:
    """Context used when the DB / mentor service is unavailable (``db=None``).

    Still produces a valid reflection (grounded only in the completed mission)
    so a mission completion never fails because of missing data.
    """
    return {
        "user_id": user_id,
        "profile": {
            "target_band": None, "current_band": None,
            "weakest_skills": [], "skill_bands": {},
            "daily_minutes_budget": 60,
        },
        "exam": {},
        "roadmap": {
            "has_active_plan": False, "today_tasks": [],
            "pending_tasks": 0, "missed_tasks": 0,
        },
        "study_history": {
            "current_streak": 0, "consistency_percent": 0.0,
            "today_minutes": 0, "today_tasks_completed": 0,
            "active_today": False, "consecutive_missed_days": 0,
            "week_percent": 0,
        },
        "missed_tasks": {
            "total_missed": 0, "recent_missed_7d": 0,
            "overdue_pending": 0, "by_skill": {}, "examples": [],
        },
        "prediction": {
            "has_prediction": False, "estimated_band": None,
            "readiness_score": None, "risk_level": None,
            "completion_rate": None, "study_consistency": None,
        },
        "band_gap": None,
        "skill_labels": {},
    }


def _dedupe_keep_order(items) -> list:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _strengths(ctx: Dict[str, Any], mission: Dict[str, Any]) -> list:
    """Ground Today's strengths in completion + readiness signals."""
    hist = ctx.get("study_history") or {}
    pred = ctx.get("prediction") or {}
    items = []

    skill = mission.get("skill")
    minutes = _int(mission.get("estimated_minutes"))
    items.append(
        f"Completed the {_lab(skill)} mission — {mission.get('title') or 'Daily Mission'} ({minutes} min)."
    )

    streak = _int(hist.get("current_streak"))
    if streak >= 3:
        items.append(f"On a {streak}-day streak — momentum is building.")

    comp = pred.get("completion_rate")
    if comp is not None and comp >= COMPLETION_HEALTHY:
        items.append(f"Study completion rate is healthy at {comp}%.")

    cons = pred.get("study_consistency") if pred.get("has_prediction") else None
    if cons is None:
        cons = hist.get("consistency_percent")
    if cons is not None and cons >= CONSISTENCY_HEALTHY:
        items.append(f"Study consistency is solid at {cons}%.")

    readiness = pred.get("readiness_score")
    if readiness is not None and readiness >= READINESS_STRONG:
        items.append(f"Predicted readiness holds at {readiness}/100.")

    week_pct = _int(hist.get("week_percent"))
    if week_pct >= COMPLETION_HEALTHY:
        items.append(f"Hit {week_pct}% of this week's study budget.")

    return _dedupe_keep_order(items)[:3]


def _mistakes(ctx: Dict[str, Any], mission: Dict[str, Any]) -> list:
    """Ground Today's mistakes in missed/overdue/gap/band-gap signals."""
    prof = ctx.get("profile") or {}
    pred = ctx.get("prediction") or {}
    hist = ctx.get("study_history") or {}
    missed = ctx.get("missed_tasks") or {}
    roadmap = ctx.get("roadmap") or {}
    gap = ctx.get("band_gap")
    items = []

    recent = _int(missed.get("recent_missed_7d"))
    if recent > 0:
        examples = missed.get("examples") or []
        ex_title = examples[0].get("title", "task") if examples else "task"
        items.append(f"{recent} task(s) missed this week — e.g. '{ex_title}'.")

    overdue = _int(missed.get("overdue_pending"))
    if overdue > 0:
        items.append(f"{overdue} overdue task(s) still pending — reschedule today.")

    consec = _int(hist.get("consecutive_missed_days"))
    if consec > 0:
        items.append(
            f"Activity gap of {consec} day(s) since last study — streak at risk."
        )

    comp = pred.get("completion_rate")
    if comp is not None and comp < LOW_RATE:
        items.append(f"Completion rate has slipped to {comp}%.")

    cons = pred.get("study_consistency") if pred.get("has_prediction") else None
    if cons is None:
        cons = hist.get("consistency_percent")
    if cons is not None and cons < LOW_RATE:
        items.append(f"Study consistency is low at {cons}%.")

    if gap is not None and prof.get("current_band") is not None:
        items.append(
            f"{gap:.1f} band(s) still between current ({prof.get('current_band')}) "
            f"and target ({prof.get('target_band')})."
        )

    if not pred.get("has_prediction"):
        items.append(
            "Readiness not yet predicted — complete a diagnostic/mock for a band estimate."
        )
    if not roadmap.get("has_active_plan"):
        items.append(
            "No active study roadmap — coaching is limited until one exists."
        )

    if not items:
        items.append("All on track — no notable mistakes today.")
    return _dedupe_keep_order(items)[:3]


def _areas_to_revise(ctx: Dict[str, Any], mission: Dict[str, Any]) -> list:
    """Ground areas-to-revise in the diagnosed weakest / below-target skills."""
    prof = ctx.get("profile") or {}
    skill_bands = prof.get("skill_bands") or {}
    target = prof.get("target_band")
    weakest = prof.get("weakest_skills") or []
    missed_by_skill = (ctx.get("missed_tasks") or {}).get("by_skill") or {}
    areas: list = []
    seen: set = set()

    def _add(skill_key: Optional[str], text: str) -> None:
        if skill_key and skill_key in seen:
            return
        if skill_key:
            seen.add(skill_key)
        areas.append(text)

    # 1) diagnosed weakest skills first.
    for s in weakest:
        if len(areas) >= 3:
            break
        wb = skill_bands.get(s)
        base = f"{_lab(s)} - band {wb}" if wb is not None else f"{_lab(s)} - needs attention"
        line = f"{base} is your lowest-scoring area"
        if target is not None:
            line += f" (target {target})"
        line += "; revise fundamentals and review 1-2 IELTS-style questions before the next mock."
        _add(s, line)

    # 2) other skills whose band is >= 0.5 below target.
    if target is not None:
        below = [(s, b) for s, b in skill_bands.items()
                 if s not in seen and _num(b) <= _num(target) - 0.5]
        below.sort(key=lambda x: x[1])
        for s, b in below:
            if len(areas) >= 3:
                break
            _add(s, f"{_lab(s)} (band {b}, {_num(target) - _num(b):.1f} below target): "
                     f"add targeted {_lab(s)} practice to your upcoming tasks.")

    # 3) skills with recent missed work.
    if len(areas) < 3 and missed_by_skill:
        top = max(missed_by_skill, key=lambda k: missed_by_skill[k])
        if top not in seen:
            _add(top, f"Overdue work in {_lab(top)} ({missed_by_skill[top]} missed): "
                      "reschedule it ahead of new tasks.")

    if not areas:
        areas.append(
            "No weak areas flagged — keep practising across all skills at your target level."
        )
    return areas[:3]


def _confidence(ctx: Dict[str, Any]) -> int:
    """1-10 confidence in the predicted trajectory (deterministic blend)."""
    pred = ctx.get("prediction") or {}
    hist = ctx.get("study_history") or {}
    readiness = pred.get("readiness_score")
    completion = pred.get("completion_rate")
    cons = pred.get("study_consistency") if pred.get("has_prediction") else None
    if cons is None:
        cons = hist.get("consistency_percent")
    streak = _int(hist.get("current_streak"))
    week_pct = _int(hist.get("week_percent"))
    streak_score = min(streak / float(STREAK_CAP), 1.0) * 100.0

    if readiness is not None and completion is not None:
        raw = 0.45 * _num(readiness) + 0.30 * _num(completion) \
              + 0.15 * _num(cons) + 0.10 * streak_score
    else:
        raw = 0.35 * _num(cons) + 0.30 * streak_score + 0.35 * week_pct

    gap = ctx.get("band_gap")
    if gap is not None:
        penalty = 0.0
        for threshold, pen in sorted(CONF_BAND_PENALTY.items(), reverse=True):
            if _num(gap) >= threshold:
                penalty = pen
                break
        raw -= penalty

    raw = max(0.0, min(raw, 100.0))
    return int(round(1 + 9 * raw / 100.0))


def _estimated_improvement(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Project the band gain from sustaining today's momentum."""
    pred = ctx.get("prediction") or {}
    prof = ctx.get("profile") or {}
    hist = ctx.get("study_history") or {}
    missed = ctx.get("missed_tasks") or {}
    gap = ctx.get("band_gap")
    has_pred = bool(pred.get("has_prediction"))
    readiness = pred.get("readiness_score")
    completion = pred.get("completion_rate")
    recent_missed = _int(missed.get("recent_missed_7d"))
    consec = _int(hist.get("consecutive_missed_days"))

    delta = 0.0
    if has_pred:
        if readiness is not None and readiness >= READINESS_STRONG \
                and gap is not None and _num(gap) >= 0.5:
            delta += 0.5
        elif readiness is not None and readiness >= READINESS_STRONG:
            delta += 0.25
        # clean-execution bonus: no recent gaps.
        if consec == 0 and recent_missed == 0 \
                and completion is not None and completion >= COMPLETION_HEALTHY:
            delta += 0.25
        # never project beyond the remaining band gap.
        if gap is not None:
            delta = min(delta, _num(gap))
        delta = min(delta, IMPROVEMENT_MAX)
    delta = round(delta * 4) / 4.0  # 0.25-band granularity

    target = prof.get("target_band")
    base = pred.get("estimated_band") if has_pred else prof.get("current_band")

    if delta > 0:
        projected = round((_num(base) + delta) * 2) / 2 if base is not None else None
        text = f"+{delta:.2f} band expected by sustaining today's progress"
        if projected is not None and target is not None:
            text += f" (est. {base} -> {projected} toward target {target})"
        elif projected is not None:
            text += f" (est. {base} -> {projected})"
    elif gap == 0:
        text = "On track to meet target — keep studying consistently."
    else:
        text = ("Hold current pace — close missed tasks and keep the streak "
                "to unlock the next half-band.")

    return {"delta": delta, "text": text}


def _tomorrow_focus(
    ctx: Dict[str, Any], mission: Dict[str, Any], mission_repo: Optional[Any]
) -> str:
    """One concrete, roadmap/grounded action for tomorrow."""
    prof = ctx.get("profile") or {}
    roadmap = ctx.get("roadmap") or {}
    weakest = prof.get("weakest_skills") or []
    budget = _int(prof.get("daily_minutes_budget"), 60)
    skill = mission.get("skill")

    # 1) Grounded in the mission system: tomorrow's pending mission for the
    #    weakest skill (this fires right after a mission completes).
    if mission_repo is not None and getattr(mission_repo, "db", None) is not None:
        mdate = _to_date(mission.get("mission_date"))
        if mdate:
            try:
                tomorrow = mdate + timedelta(days=1)
                pending = mission_repo.list_for_date(ctx.get("user_id"), tomorrow) or []
                ws = weakest[0] if weakest else None
                match = next(
                    (
                        m for m in pending
                        if str(m.get("status")).lower() == "pending"
                        and (not ws or m.get("skill") == ws)
                    ),
                    None,
                )
                if match:
                    return (
                        f"Complete tomorrow's {_lab(ws or match.get('skill'))} "
                        f"mission: '{match.get('title')}'."
                    )
            except Exception as exc:
                logger.warning("tomorrow mission lookup failed: %s", exc)

    # 2) Grounded in the roadmap: a pending task due today/overdue.
    today_tasks = [
        t for t in (roadmap.get("today_tasks") or [])
        if str(t.get("status")).lower() in ("pending", "in_progress")
    ]
    if today_tasks:
        t = today_tasks[0]
        return (
            f"Finish pending task '{t.get('title')}' "
            f"({_lab(t.get('skill'))}) scheduled today."
        )

    # 3) Fallback: weakest-skill practice budget.
    ws = (weakest and weakest[0]) or skill
    wb = (prof.get("skill_bands") or {}).get(ws)
    target = prof.get("target_band")
    focus = f"Spend {budget} min on {_lab(ws)} practice"
    if wb is not None:
        focus += f" (lowest band {wb})"
    if target is not None:
        focus += f"; close the gap toward target {target}"
    return focus + "."


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class ReflectionEngine:
    """Synthesises and stores a structured reflection after a mission completes.

    Dependencies:
      - ``context_provider``: optional callable(user_id) -> learner context dict.
        Defaults to the AI Mentor service's ``get_context`` snapshot (lazy import
        to avoid a circular/early import). Tests inject a fake.
      - ``reflection_repo``: persistence layer (injected for tests).
      - ``mission_repo``: grounds "tomorrow's focus" in tomorrow's pending
        daily missions (built lazily, only when a DB is available).
    """

    def __init__(
        self,
        db: Any = None,
        context_provider: Optional[ContextProvider] = None,
        reflection_repo: Optional[MissionReflectionRepository] = None,
        mission_repo: Optional[DailyMissionRepository] = None,
    ) -> None:
        from app.services.ai_mentor_service import ai_mentor_service as _mentor

        self.db = db
        self._context_provider: Optional[ContextProvider] = context_provider
        self._mentor = _mentor
        self.reflection_repo = reflection_repo or MissionReflectionRepository(db)
        # Only build a mission repo when we actually have a DB to query.
        self.mission_repo = mission_repo or (
            DailyMissionRepository(db) if db is not None else None
        )

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
    def _get_context(self, user_id: str) -> Dict[str, Any]:
        """Return the learner context, degrading gracefully when DB is absent."""
        if self._context_provider is not None:
            try:
                return self._context_provider(user_id)
            except Exception as exc:
                logger.warning("context_provider failed user=%s: %s", user_id, exc)
                return _minimal_context(user_id)
        try:
            return self._mentor.get_context(user_id)
        except Exception as exc:
            logger.info("reflection context unavailable user=%s: %s", user_id, exc)
            return _minimal_context(user_id)

    # ------------------------------------------------------------------
    # Core computation (pure: ctx + mission -> reflection fields)
    # ------------------------------------------------------------------
    def _compute(
        self, ctx: Dict[str, Any], mission: Dict[str, Any],
        mission_repo: Optional[Any] = None,
    ) -> Dict[str, Any]:
        strengths = _strengths(ctx, mission)
        mistakes = _mistakes(ctx, mission)
        areas = _areas_to_revise(ctx, mission)
        tomorrow = _tomorrow_focus(ctx, mission, mission_repo)
        confidence = _confidence(ctx)
        improvement = _estimated_improvement(ctx)
        return {
            "strengths": strengths,
            "mistakes": mistakes,
            "areas_to_revise": areas,
            "tomorrow_focus": tomorrow,
            "confidence_level": confidence,
            "estimated_improvement": improvement["delta"],
            "estimated_improvement_text": improvement["text"],
        }

    def generate(self, user_id: str, mission: Dict[str, Any]) -> ReflectionData:
        """Compute a reflection WITHOUT persisting (pure read)."""
        ctx = self._get_context(user_id)
        return ReflectionData(**self._compute(ctx, mission, self.mission_repo))

    # ------------------------------------------------------------------
    # Persist (idempotent: one reflection per (user, mission))
    # ------------------------------------------------------------------
    def _to_payload(
        self, user_id: str, mission: Dict[str, Any],
        data: Dict[str, Any], ctx: Dict[str, Any],
        ) -> Dict[str, Any]:
        mdate = _to_date(mission.get("mission_date"))
        return {
            "user_id": user_id,
            "mission_id": mission.get("id"),
            "mission_date": mdate.isoformat() if mdate else None,
            "skill": mission.get("skill") or "general",
            "strengths": data["strengths"],
            "mistakes": data["mistakes"],
            "areas_to_revise": data["areas_to_revise"],
            "tomorrow_focus": data["tomorrow_focus"],
            "confidence_level": data["confidence_level"],
            "estimated_improvement": data["estimated_improvement"],
            "estimated_improvement_text": data["estimated_improvement_text"],
            "context_snapshot": ctx,
        }

    def _persist(
        self, user_id: str, mission: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        repo = self.reflection_repo
        if repo is None or getattr(repo, "db", None) is None:
            # No DB available (tests / db=None): return the computed payload
            # without persisting. The reflection is still produced.
            return dict(payload)
        try:
            existing = repo.get_for_mission(user_id, mission.get("id"))
            if existing:
                return repo.update(existing["id"], payload, user_id=user_id)
            return repo.create(payload)
        except ConflictError:
            # Race: another reflection for this mission was inserted.
            try:
                row = repo.get_for_mission(user_id, mission.get("id"))
                return row or dict(payload)
            except Exception:
                return dict(payload)
        except Exception as exc:
            # Persistence is best-effort — never block mission completion.
            logger.warning(
                "reflection persist failed user=%s mission=%s: %s",
                user_id, mission.get("id"), exc,
            )
            return dict(payload)

    def generate_and_store(
        self, user_id: str, mission: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute a reflection and persist it (create-or-update per mission).

        Safe even when the DB is unavailable: returns the computed payload
        (without an ``id``) so callers always get a reflection.
        """
        ctx = self._get_context(user_id)
        data = self._compute(ctx, mission, self.mission_repo)
        payload = self._to_payload(user_id, mission, data, ctx)
        return self._persist(user_id, mission, payload)





