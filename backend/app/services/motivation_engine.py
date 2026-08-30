"""
Motivation Engine service.

Generates personalized, non-repetitive, professional motivational messages for
key student moments. Every decision is DETERMINISTIC (no randomness, no LLM):

  - **Message bank**: each moment has several professionally written variant
    templates sprinkled with `{token}` placeholders. Only variants whose
    required tokens are present in the learner context are eligible, so a
    message never references data we don't actually know.
  - **Anti-repetition rotation**: the variant chosen for (user, moment) is
    `(delivery_count + user_offset) % len(eligible)`. Identical messages are
    never delivered back-to-back, and the full set of variants is cycled
    before any repetition.
  - **Idempotent delivery**: `UNIQUE (user_id, moment, period_key)` in the
    motivation_messages table guarantees a moment+period yields one message.
  - **Today selection** (priority): final_day > exam_week > missed_day >
    streak milestone > mission_complete > general.

Event hooks let services trigger messages at the right moment:
  - `on_mission_complete`  → mission_complete + streak_7/streak_30 milestones
  - `on_mock_completed`    → mock_test
  - `on_band_assessment`   → band_improvement (when the band rose >= 0.5)

All DB reads are defensive ``_safe_*`` wrappers (empty defaults), mirroring the
AI Mentor / prediction services, so the engine is fully testable with
``db=None`` and never crashes a request because of a missing table.
"""
import hashlib
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import ConflictError
from app.db.session import DatabaseSession
from app.repositories.daily_mission_repo import DailyMissionRepository
from app.repositories.motivation_repo import MotivationRepository
from app.repositories.streak_repo import StreakRepository
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------
EXAM_FINAL_DAY = 1                      # exactly N days left → final_day
EXAM_WEEK_DAYS = 7                      # <= N days left → exam_week
STREAK_MILESTONES = (7, 30)             # streak lengths that get their own message
MISSED_GAP_DAYS = 1                     # last activity at least N+1 days ago → "missed day"
BAND_IMPROVEMENT_DELTA = 0.5            # min rise to celebrate band_improvement

MESSAGE_MOMENT_LABELS: Dict[str, str] = {
    "mission_complete": "Mission Complete",
    "missed_day": "Welcome Back",
    "streak_7": "7-Day Streak",
    "streak_30": "30-Day Streak",
    "band_improvement": "Band Improvement",
    "mock_test": "Mock Test Complete",
    "exam_week": "Exam Week",
    "final_day": "Final Day",
    "general": "Daily Focus",
}

# ---------------------------------------------------------------------------
# Message bank
# ---------------------------------------------------------------------------
# Each variant: {"title": str, "body": str, "tone": str, "requires": (tokens,)}
# "requires" lists context keys that MUST be present for the variant to be used,
# so messages never reference missing learner data.
def _variant(title: str, body: str, tone: str = "encouraging",
             requires: Tuple[str, ...] = ()) -> Dict[str, Any]:
    return {"title": title, "body": body, "tone": tone, "requires": tuple(requires)}
MESSAGE_BANK: Dict[str, List[Dict[str, Any]]] = {
    "mission_complete": [
        _variant(
            "All missions complete",
            "{first_name}, every mission for today is done. That is the repeatable "
            "habit that moves a band score. Rest well - tomorrow's plan is already "
            "built on today.",
            "celebratory", requires=("first_name",),
        ),
        _variant(
            "Mission Complete",
            "All {completed} of today's missions are complete. The skills you "
            "practiced today are now part of your exam-day recall. Close the day "
            "with a clear mind.",
            "celebratory", requires=("completed",),
        ),
        _variant(
            "Day complete",
            "Today's full mission set is finished. Consistency like this is what "
            "turns a target band into a scheduled outcome. Take the win.",
            "celebratory",
        ),
        _variant(
            "Mission Complete",
            "You finished every planned session today and gave your roadmap a real "
            "day of progress. That compounds - one more day banked.",
            "encouraging",
        ),
        _variant(
            "All missions done",
            "Every session on today's list is complete. Steady, scheduled progress "
            "beats intense bursts - you proved that again today.",
            "encouraging",
        ),
    ],
    "missed_day": [
        _variant(
            "Welcome back",
            "{first_name}, welcome back. You missed a day - that is a fact, not a "
            "judgment. Your roadmap still holds and today's plan is ready. Start "
            "with a single session.",
            "calm", requires=("first_name",),
        ),
        _variant(
            "Good to see you again",
            "A missed day does not erase the days before it. Everything you have "
            "completed is preserved. Pick today's first task and rebuild momentum.",
            "calm",
        ),
        _variant(
            "Back on track",
            "It is good to see you again. The schedule carried forward while you "
            "were away, so nothing piled up unfairly. Complete one achievable "
            "mission today.",
            "calm",
        ),
        _variant(
            "Welcome back",
            "Every long preparation has these pauses - what counts is the return. "
            "Today's sessions are ready; start with the lightest one and build "
            "from there.",
            "encouraging",
        ),
    ],
    "streak_7": [
        _variant(
            "7-Day Streak",
            "Seven consecutive days of study. A week is exactly where real skill "
            "consolidation begins - your consistency is now measurable, and it is "
            "working.",
            "celebratory",
        ),
        _variant(
            "One full week",
            "One full week, {first_name}. You have built the single strongest "
            "predictor of IELTS success: daily practice. Day 8 looks good on you.",
            "celebratory", requires=("first_name",),
        ),
        _variant(
            "7 days in a row",
            "Seven days in a row - not intensity, method. That is the foundation "
            "most candidates never build. Keep the run going.",
            "encouraging",
        ),
        _variant(
            "Habit locked in",
            "Your 7-day streak is live. This is the moment a habit becomes "
            "self-sustaining. Protect the run: one focused session each day is "
            "enough.",
            "encouraging",
        ),
    ],
    "streak_30": [
        _variant(
            "30-Day Streak",
            "Thirty consecutive days of study. That is a month of discipline most "
            "test-takers never reach - and it shows in your readiness.",
            "celebratory",
        ),
        _variant(
            "A month of discipline",
            "A 30-day streak, {first_name}. You have turned preparation into "
            "routine, and routine is what performs on exam day. Remarkable.",
            "celebratory", requires=("first_name",),
        ),
        _variant(
            "Four weeks, no breaks",
            "Four weeks without a break. This streak is your arrowhead: the longer "
            "it runs, the more your target band becomes a probability.",
            "encouraging",
        ),
        _variant(
            "30 days of practice",
            "Thirty days of deliberate practice. Your consistency profile now "
            "ranks in the top tier of candidates - keep the edge.",
            "encouraging",
        ),
    ],
"band_improvement": [
        _variant(
            "Band improvement",
            "Your latest assessment moved up to Band {band} - up from "
            "{previous_band}. That is real, measured progress in a skill where "
            "plateaus are normal.",
            "celebratory", requires=("band", "previous_band"),
        ),
        _variant(
            "Measured progress",
            "Band {band} on your most recent assessment, up from {previous_band}. "
            "The specific work you chose is working. Note what it was and keep "
            "doing that.",
            "celebratory", requires=("band", "previous_band"),
        ),
        _variant(
            "Improvement confirmed",
            "{previous_band} to {band} - that improvement came from targeted "
            "practice, not chance. Let us lock in the next half-band.",
            "celebratory", requires=("band", "previous_band"),
        ),
        _variant(
            "Rising score",
            "Your score rose to Band {band}. Improvements at this level come from "
            "the adjustments you made - reproduce them and this becomes a trend.",
            "encouraging", requires=("band",),
        ),
    ],
    "mock_test": [
        _variant(
            "Mock complete",
            "You completed a full mock test. Whether the score met your target or "
            "not, the test itself is now data - it gives your roadmap real "
            "calibration.",
            "encouraging",
        ),
        _variant(
            "Mock test done",
            "A full mock is one of the toughest sessions there is - and you finished "
            "it. Reviewing the mistakes is where the band lives; the score is a "
            "reading, not a verdict.",
            "neutral",
        ),
        _variant(
            "Mock logged",
            "Your mock is complete and your section scores are now feeding your "
            "prediction and roadmap, so the next plan is sharper for it.",
            "encouraging",
        ),
        _variant(
            "Mock complete",
            "You finished a full-length mock - excellent stamina. Your results "
            "will recalibrate the next phase of practice, section by section.",
            "encouraging",
        ),
        _variant(
            "Mock results in",
            "Mock complete at Band {mock_band}. Use the section scores to target "
            "the next phase; this is exactly the feedback your plan needs.",
            "calm", requires=("mock_band",),
        ),
    ],
    "exam_week": [
        _variant(
            "Exam week",
            "One week to go, {first_name}. Confidence at this stage comes from "
            "review, not new material: light practice, full sleep, steady routine.",
            "calm", requires=("first_name",),
        ),
        _variant(
            "Final stretch",
            "Your exam is inside a week. Protect the plan: finish scheduled "
            "revision, keep mock timing consistent, and avoid introducing anything "
            "unfamiliar now.",
            "firm",
        ),
        _variant(
            "The final stretch",
            "You have done the training. This week is about rhythm and rest - "
            "trust the work you have already completed.",
            "calm",
        ),
        _variant(
            "Exam week is here",
            "Keep sessions short and targeted this week: summarize, review "
            "past mistakes, and guard your energy. The preparation is done.",
            "calm",
        ),
    ],
    "final_day": [
        _variant(
            "The day before",
            "Tomorrow is your exam. You are as ready as your preparation has made "
            "you, and that is more than enough. Tonight: review light, sleep well, "
            "plan the journey.",
            "calm",
        ),
        _variant(
            "One sleep to go",
            "The day before the exam: no new material. A quick scan of your "
            "weakest notes, then rest. You have earned the calm.",
            "calm",
        ),
        _variant(
            "Final day",
            "Tomorrow you sit the exam. Everything you need is already stored from "
            "months of practice - sleep is your final study session.",
            "calm",
        ),
        _variant(
            "Final preparation night",
            "One sleep to go. Lay out your test-day logistics, do a gentle review, "
            "and shut the books early. You will perform from what you have already "
            "built.",
            "calm",
        ),
    ],
    "general": [
        _variant(
            "Daily focus",
            "{first_name}, today's plan is waiting. Two focused sessions build more "
            "genuine readiness than one long, unfocused evening.",
            "encouraging", requires=("first_name",),
        ),
        _variant(
            "Daily focus",
            "Steady work today: complete one mission from your weakest skill and "
            "keep the streak alive.",
            "encouraging",
        ),
        _variant(
            "Daily focus",
            "Your roadmap for today is set. The best next move is the first task "
            "on the list - done is always better than perfect.",
            "encouraging",
        ),
        _variant(
            "Daily focus",
            "Make today a quiet win: one full mission, one review of a past "
            "mistake, and protect your streak.",
            "neutral",
        ),
    ],
}

# Generic fallback — used only if every variant is ineligible.
FALLBACK_TEMPLATE = _variant(
    "Daily focus",
    "Keep moving forward today. A small, consistent step is still a step - and "
    "steps are what close the gap to your target band.",
    "encouraging",
)
class MotivationEngine:
    """Deterministic, personalized, non-repetitive motivation message engine."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = MotivationRepository(db)
        self.user_repo = UserRepository(db)
        self.streak_repo = StreakRepository(db)
        self.mission_repo = DailyMissionRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_today(self, user_id: str, run_date: Optional[date] = None) -> Dict[str, Any]:
        """Return (and persist once per day) the message for today.

        Selection priority: final_day > exam_week > missed_day >
        streak milestone > mission_complete > general.
        """
        run_date = run_date or date.today()
        ctx = self._gather_context(user_id, run_date)
        moment = self._select_today_moment(ctx)
        message = self._deliver(user_id, moment, ctx,
                                period_key=run_date.isoformat())
        return {
            "server_date": run_date.isoformat(),
            "applied_moment": moment,
            "message": message,
        }

    def generate(
        self,
        user_id: str,
        moment: str,
        context: Optional[Dict[str, Any]] = None,
        run_date: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate (and persist idempotently) a message for a specific moment.

        ``context`` may inject event facts (assessment_id, mock_id, band, mock_band,
        streak, previous_band, ...) that override what the engine reads from the
        database. Returns None if the moment is unknown.
        """
        if moment not in MESSAGE_BANK:
            return None
        run_date = run_date or date.today()
        ctx = self._gather_context(user_id, run_date)
        if context:
            ctx.update({k: v for k, v in context.items() if v is not None})
        period_key = self._default_period_key(moment, ctx, run_date)
        return self._deliver(user_id, moment, ctx, period_key=period_key)

    def on_mission_complete(
        self,
        user_id: str,
        mission: Dict[str, Any],
        run_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Event hook fired when a daily mission is completed.

        Returns every message generated:
          - mission_complete once all of today's missions are done
          - streak_7 / streak_30 when the daily streak just hit a milestone
        """
        run_date = run_date or date.today()
        messages: List[Dict[str, Any]] = []

        summary = self._safe_mission_summary(user_id, run_date)
        completed = int(summary.get("completed_tasks") or 0)
        total = int(summary.get("total_tasks") or 0)
        if total > 0 and completed >= total:
            ctx = self._gather_context(user_id, run_date,
                                       extra={"completed": completed, "total": total})
            msg = self._deliver(user_id, "mission_complete", ctx,
                                period_key=run_date.isoformat())
            if msg:
                messages.append(msg)

        streak = self._safe_daily_streak(user_id)
        if streak in STREAK_MILESTONES:
            moment = f"streak_{streak}"
            ctx = self._gather_context(user_id, run_date, extra={"streak": streak})
            msg = self._deliver(user_id, moment, ctx, period_key=str(streak))
            if msg:
                messages.append(msg)

        return messages

    def on_mock_completed(
        self,
        user_id: str,
        mock: Optional[Dict[str, Any]] = None,
        mock_id: Optional[str] = None,
        band: Optional[float] = None,
        run_date: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        """Event hook fired when a mock test is submitted."""
        mock = mock or {}
        run_date = run_date or date.today()
        ctx = {
            "mock_band": band if band is not None else mock.get("overall_band"),
            "mock_id": mock_id or mock.get("id") or mock.get("mock_id"),
        }
        return self.generate(user_id, "mock_test", context=ctx, run_date=run_date)

    def on_band_assessment(
        self,
        user_id: str,
        band: float,
        assessment_id: Optional[str] = None,
        skill: Optional[str] = None,
        run_date: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        """Event hook for a new assessment; celebrates a >= 0.5 band improvement.

        The previous band is read from the assessments ledger, so the message is
        grounded in real, measured progress.
        """
        run_date = run_date or date.today()
        previous = self._safe_previous_assessment_band(user_id, band, skill)
        if previous is None or band - previous + 1e-9 < BAND_IMPROVEMENT_DELTA:
            return None
        ctx = {
            "band": band,
            "previous_band": previous,
            "assessment_id": assessment_id or "",
            "skill": skill or "",
        }
        period_key = assessment_id or f"{run_date.isoformat()}-{band}"
        return self.generate(user_id, "band_improvement",
                             context=ctx, run_date=run_date)

    def list_messages(
        self,
        user_id: str,
        moment: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Return the persisted motivation feed (newest first)."""
        if self.db is None:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}
        try:
            moment_f = moment if moment in MESSAGE_BANK else None
            items = self.repo.list_for_user(user_id, moment=moment_f,
                                            limit=limit, offset=offset)
            total = self.repo.count_for_moment(user_id, moment_f) if moment_f \
                else self.repo.total_for_user(user_id)
            return {"items": items, "total": total, "limit": limit, "offset": offset}
        except Exception:
            logger.warning("motivation.list failed user=%s", user_id, exc_info=True)
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

    def overview(self, user_id: str) -> Dict[str, Any]:
        """Aggregate: total messages, per-moment counts, and the latest message."""
        if self.db is None:
            return {
                "total_messages": 0,
                "by_moment": [{"moment": m, "count": 0} for m in MESSAGE_BANK],
                "latest": None,
            }
        try:
            counts = self.repo.counts_by_moment(user_id)
            return {
                "total_messages": sum(counts.values()),
                "by_moment": [{"moment": m, "count": counts.get(m, 0)}
                              for m in MESSAGE_BANK],
                "latest": self.repo.latest_for_user(user_id),
            }
        except Exception:
            logger.warning("motivation.overview failed user=%s", user_id, exc_info=True)
            return {
                "total_messages": 0,
                "by_moment": [{"moment": m, "count": 0} for m in MESSAGE_BANK],
                "latest": None,
            }

    # ------------------------------------------------------------------
    # Context gathering (defensive reads)
    # ------------------------------------------------------------------
    def _gather_context(self, user_id: str, run_date: date,
                        extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Assemble the learner context used to select + personalize messages."""
        profile = self._safe_profile(user_id) or {}
        first_name = (profile.get("full_name") or "").strip().split(" ")[0] or None

        days_left = self._safe_days_left(profile, run_date)
        target_band = self._safe_band(profile.get("target_band"))
        current_band = self._safe_band(profile.get("current_band"))

        summary = self._safe_mission_summary(user_id, run_date)
        streak = self._safe_daily_streak(user_id)
        last_active = self._safe_last_active(user_id, run_date)

        ctx: Dict[str, Any] = {
            "first_name": first_name,
            "target_band": target_band,
            "current_band": current_band,
            "days_left": days_left,
            "intensity": self._intensity(days_left),
            "streak": streak,
            "last_active": last_active,
            "completed": int(summary.get("completed_tasks") or 0),
            "total": int(summary.get("total_tasks") or 0),
            "mock_band": self._safe_latest_mock_band(user_id),
        }
        if extra:
            ctx.update({k: v for k, v in extra.items() if v is not None})
        return ctx

    def _select_today_moment(self, ctx: Dict[str, Any]) -> str:
        """Conservative moment priority for the 'today' message."""
        days_left = ctx.get("days_left")
        if days_left == EXAM_FINAL_DAY:
            return "final_day"
        if days_left is not None and days_left <= EXAM_WEEK_DAYS:
            return "exam_week"
        if ctx.get("last_active") is not None and \
                ctx["last_active"] <= self._today_minus_gap():
            return "missed_day"
        streak = ctx.get("streak") or 0
        if streak in STREAK_MILESTONES:
            return f"streak_{streak}"
        if ctx.get("total") and ctx.get("completed") >= ctx["total"]:
            return "mission_complete"
        return "general"

    # ------------------------------------------------------------------
    # Message selection + persistence
    # ------------------------------------------------------------------
    def _deliver(
        self,
        user_id: str,
        moment: str,
        ctx: Dict[str, Any],
        period_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Select a variant, personalize it, and persist idempotently.

        If a message already exists for (moment, period_key), the stored version
        is returned — delivery stays idempotent.
        """
        if moment not in MESSAGE_BANK:
            return None

        existing = self._safe_get_for_period(user_id, moment, period_key)
        if existing:
            return existing

        variant = self._choose_variant(user_id, moment, ctx)
        title = self._personalize(variant["title"], ctx)
        body = self._personalize(variant["body"], ctx)
        snapshot = self._context_snapshot(ctx)

        if self.db is None:
            # Test mode: return an unsaved representation.
            return {
                "id": "-",
                "user_id": user_id,
                "moment": moment,
                "title": title,
                "body": body,
                "tone": variant["tone"],
                "variant": variant.get("_id", ""),
                "period_key": period_key,
                "context": snapshot,
                "created_at": datetime.utcnow().isoformat(),
            }

        try:
            row = self.repo.create_message(
                user_id, moment, period_key, title, body,
                variant["tone"], variant=variant.get("_id", ""),
                context=snapshot,
            )
            return row
        except ConflictError:
            # Race-safe: another request delivered the same (moment, period_key).
            return self._safe_get_for_period(user_id, moment, period_key)
        except Exception as exc:
            logger.warning("motivation._deliver failed user=%s moment=%s: %s",
                           user_id, moment, exc)
            return None

    def _choose_variant(self, user_id: str, moment: str,
                        ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Pick a variant deterministically with anti-repetition rotation.

        Only variants whose required tokens are present in ``ctx`` are eligible.
        Rotation index = (delivery_count + user_offset) % len(eligible), so the
        engine cycles the whole pool before repeating a message.
        """
        bank = MESSAGE_BANK.get(moment, [])
        eligible = [
            v for v in bank
            if all(ctx.get(key) is not None for key in v["requires"])
        ]
        if not eligible:
            return FALLBACK_TEMPLATE

        count = self._safe_count_for_moment(user_id, moment)
        offset = self._user_offset(user_id, moment, len(eligible))
        variant = eligible[(count + offset) % len(eligible)]
        # Tag the chosen template variant for storage/analytics.
        return {**variant, "_id": f"{moment}-v{(count + offset) % len(eligible)}"}

    @staticmethod
    def _user_offset(user_id: str, moment: str, n: int) -> int:
        """Deterministic per-user starting point so users diverge from day one."""
        if n <= 1:
            return 0
        digest = hashlib.md5(f"{user_id}:{moment}".encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % n