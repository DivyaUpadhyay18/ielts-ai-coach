"""
Deterministic Study Plan Generation Engine.

Reads the user's profile (exam date, current/target band, daily budget,
weakest/strongest skills, module) and generates a day-by-day plan until the
exam, storing it in the canonical study_plans / daily_plans / tasks tables.

Design decisions (per SCHEDULER.md):
  - No AI. All selection is deterministic (hash-based rotation).
  - Phase weighting: Foundation 30% / Skill Building 30% / Advanced 20% /
    Mock Tests 15% / Final Revision 5% (protected, last days).
  - Weak-skill focus: weakest skills get more tasks and higher priority.
  - Gradual difficulty ramp: difficulty rises by week.
  - Weekly revision every 7th day; mock days every ~2 weeks from Phase 2
    onward; final week is reserved for revision + mock sections.
  - Each day has 6 skill tasks (reading, listening, writing, speaking,
    vocabulary, grammar) respecting the daily minute budget.
"""
import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import ValidationError
from app.db.session import DatabaseSession
from app.models.study_plan import StudyPlanCreate
from app.models.study_plan_engine import (
    DiagnosticStudyPlanRequest,
    GeneratedDay,
    GeneratedTask,
    PhaseBreakdown,
    PHASE_KEYS,
    PHASE_WEIGHTS,
    StudyPlanGenerateRequest,
    StudyPlanGenerateResponse,
)
from app.repositories.daily_plan_repo import DailyPlanRepository
from app.repositories.study_plan_repo import StudyPlanRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.services.schedule_history_service import schedule_history_service
from app.services.diagnostic_roadmap_service import diagnostic_roadmap_service

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PHASE_LABELS = {
    "foundation": "Foundation & Gap Closure",
    "skill_building": "Skill Building",
    "advanced": "Advanced Techniques",
    "mock_tests": "Mock Test Marathon",
    "final_revision": "Final Revision & Strategy",
}

ALL_SKILLS = ("reading", "listening", "writing", "speaking", "vocabulary", "grammar")

SKILL_TASK_TYPES = {
    "reading": ("practice_test", "article"),
    "listening": ("practice_test", "video"),
    "writing": ("writing_task1", "writing_task2"),
    "speaking": ("speaking_part1", "speaking_part2", "speaking_part3"),
    "vocabulary": ("vocab_set",),
    "grammar": ("grammar_lesson",),
}

# Base durations in minutes per skill (min, max)
SKILL_DURATIONS = {
    "reading": (20, 30),
    "listening": (20, 30),
    "writing": (30, 40),
    "speaking": (10, 15),
    "vocabulary": (12, 18),
    "grammar": (12, 18),
}

WEEKLY_REVISION_DAY = 7          # every 7th absolute day of the plan
MOCK_INTERVAL_DAYS = 14          # every 14 days from Phase 2 onward
FINAL_REVISION_DAYS = 7          # last 7 days are protected revision+mocks

# XP reward = base + duration-based bonus, scaled by difficulty.
XP_PER_MINUTE = 1
XP_DIFFICULTY_BONUS = {1: 0, 2: 2, 3: 5, 4: 8, 5: 12}

PRIORITY_WEAK = 5
PRIORITY_NORMAL = 3
PRIORITY_STRONG = 2


def _deterministic_index(key: str, pool_size: int) -> int:
    """Stable hash-based index into a pool (no randomness)."""
    if pool_size <= 0:
        return 0
    return sum(ord(c) for c in key) % pool_size


def _skill_priority(skill: str, weak: List[str], strong: List[str]) -> int:
    """Map a skill to a priority based on weak/strong profile."""
    if skill in weak:
        return PRIORITY_WEAK
    if skill in strong:
        return PRIORITY_STRONG
    return PRIORITY_NORMAL


def _xp_for_task(duration_minutes: int, difficulty: int) -> int:
    """Compute deterministic XP reward for a task."""
    return int(duration_minutes * XP_PER_MINUTE) + XP_DIFFICULTY_BONUS.get(difficulty, 0)


def _daily_budget_for_date(
    base_budget: int,
    day_index: int,
    is_revision_day: bool,
    is_mock_day: bool,
    days_remaining: int,
) -> int:
    """
    Compute the adjusted daily budget.

    - Revision days: 50% of base budget (light review).
    - Mock days: full budget (the mock itself is the focus).
    - Crunch mode (<=14 days): up to 1.3x base.
    """
    budget = base_budget
    if is_revision_day:
        budget = int(base_budget * 0.5)
    elif days_remaining <= 14 and not is_mock_day:
        budget = int(base_budget * 1.3)
    return max(budget, 15)


class StudyPlanGenerator:
    """Core engine for generating deterministic day-by-day study plans."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.study_plan_repo = StudyPlanRepository(db)
        self.daily_plan_repo = DailyPlanRepository(db)
        self.task_repo = TaskRepository(db)
        self.user_repo = UserRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self, user_id: str, request: StudyPlanGenerateRequest) -> Dict[str, Any]:
        """Generate a full study plan for a user and persist it."""
        start_date = request.start_date or date.today()
        if start_date < date.today():
            raise ValidationError("start_date cannot be in the past")

        exam_date = request.exam_date
        total_days = max((exam_date - start_date).days, 1)
        if total_days < 7:
            raise ValidationError("At least 7 days are required between start date and exam date")

        total_weeks = max(2, round(total_days / 7))

        weak = list(request.weakest_skills)
        strong = list(request.strongest_skills)

        # ----------------------------------------------------------
        # 1. Archive any existing active plan (versioned re-generation)
        # ----------------------------------------------------------
        previous_plan = self._safe_get_active_plan(user_id)
        previous_plan_id = previous_plan.get("id") if previous_plan else None
        previous_schedule = self._capture_schedule_snapshot(user_id)
        self.study_plan_repo.archive_active(user_id)

        # ----------------------------------------------------------
        # 2. Create study plan row
        # ----------------------------------------------------------
        plan_payload = StudyPlanCreate(
            title=f"IELTS {request.module.title()} Study Plan",
            target_band=request.target_band,
            start_band=request.current_band,
            total_weeks=total_weeks,
            meta={
                "engine": "study_plan_generator_v1",
                "module": request.module,
                "daily_minutes_budget": request.daily_minutes_budget,
                "weakest_skills": weak,
                "strongest_skills": strong,
                "start_date": start_date.isoformat(),
                "exam_date": exam_date.isoformat(),
            },
        ).model_dump()

        study_plan = self.study_plan_repo.create(user_id, plan_payload)
        study_plan_id = study_plan["id"]
        version = int(study_plan["version"])

        # ----------------------------------------------------------
        # 3. Phase allocation
        # ----------------------------------------------------------
        phase_days = self._allocate_phases(total_days)
        phase_breakdown = self._build_phase_breakdown(start_date, phase_days)

        # ----------------------------------------------------------
        # 4. Generate days + tasks
        # ----------------------------------------------------------
        days, total_tasks, total_xp = self._generate_days(
            user_id=user_id,
            study_plan_id=study_plan_id,
            start_date=start_date,
            exam_date=exam_date,
            total_days=total_days,
            phase_days=phase_days,
            base_budget=request.daily_minutes_budget,
            weak=weak,
            strong=strong,
            module=request.module,
        )

        # ----------------------------------------------------------
        # 5. Build response
        # ----------------------------------------------------------
        response = StudyPlanGenerateResponse(
            study_plan_id=study_plan_id,
            version=version,
            title=study_plan["title"],
            target_band=request.target_band,
            start_band=request.current_band,
            total_weeks=total_weeks,
            start_date=start_date,
            exam_date=exam_date,
            total_days=total_days,
            phase_breakdown=phase_breakdown,
            days=days,
            total_tasks=total_tasks,
            total_xp=total_xp,
            generated_at=datetime.utcnow(),
        )

        # Capture new schedule snapshot after generation
        new_schedule = self._capture_schedule_snapshot(user_id)

        # Log to schedule history
        try:
            asyncio.run(
                schedule_history_service.log_study_plan_regeneration(
                    user_id=user_id,
                    previous_plan_id=previous_plan_id if previous_plan_id else "",
                    new_plan_id=study_plan_id,
                    previous_schedule=previous_schedule,
                    new_schedule=new_schedule,
                    reason=f"Study plan regenerated (version {version})",
                    metrics_before={},
                    metrics_after={},
                )
            )
        except Exception as exc:
            logger.warning("schedule_history.log_study_plan_regeneration failed user=%s: %s", user_id, exc)

        return response.model_dump()

    def get_plan_days(
        self,
        user_id: str,
        study_plan_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Return a day-by-day view of an existing study plan."""
        study_plan = self.study_plan_repo.get_by_id(study_plan_id, user_id=user_id)

        daily_plans = self.daily_plan_repo.list_for_study_plan(user_id, study_plan_id)
        daily_plans.sort(key=lambda d: d.get("plan_date", ""))

        days: List[Dict[str, Any]] = []
        total_tasks = 0
        total_xp = 0

        for dp in daily_plans:
            plan_date = dp.get("plan_date")
            if not plan_date:
                continue
            pd = plan_date if isinstance(plan_date, date) else self._parse_date(plan_date)
            if from_date and pd < from_date:
                continue
            if to_date and pd > to_date:
                continue

            task_rows = self.task_repo.list_for_user(
                user_id=user_id,
                daily_plan_id=dp["id"],
            )
            total_tasks += len(task_rows)
            total_xp += int(dp.get("xp_reward") or 0)

            tasks: List[Dict[str, Any]] = []
            for t in task_rows:
                tasks.append(
                    GeneratedTask(
                        title=t["title"],
                        skill=t["skill"],
                        task_type=t["task_type"],
                        duration_minutes=int(t["duration_minutes"]),
                        priority=int(t.get("priority") or 1),
                        xp_reward=int(t.get("xp_reward") or 0),
                        difficulty=int(t.get("difficulty") or 1),
                        is_mandatory=bool(t.get("is_mandatory") or False),
                    ).model_dump()
                )

            days.append(
                GeneratedDay(
                    plan_date=pd,
                    phase_index=int(dp.get("phase_index") or 0),
                    is_revision_day=bool(dp.get("is_revision_day") or False),
                    is_mock_day=bool(dp.get("is_mock_day") or False),
                    is_rest_day=bool(dp.get("is_rest_day") or False),
                    xp_reward=int(dp.get("xp_reward") or 0),
                    total_minutes=int(dp.get("total_minutes") or 0),
                    tasks=tasks,
                ).model_dump()
            )

        return {
            "study_plan_id": study_plan_id,
            "version": int(study_plan["version"]),
            "title": study_plan["title"],
            "start_date": (study_plan.get("meta") or {}).get("start_date")
            or (days[0]["plan_date"].isoformat() if days else None),
            "exam_date": (study_plan.get("meta") or {}).get("exam_date"),
            "days": days,
            "total_days": len(days),
            "total_tasks": total_tasks,
            "total_xp": total_xp,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)).date()

    @staticmethod
    def _allocate_phases(total_days: int) -> Dict[str, int]:
        """
        Split total_days into per-phase day counts using the fixed weights.

        The final revision phase is protected to the last 7 days (or all
        remaining if fewer than 7 days exist, which we guard against).
        """
        result: Dict[str, int] = {}
        remaining = total_days

        # Mock tests and final revision get their own minimum allocation.
        # We allocate in order: final_revision (protected), mock_tests, then
        # the three academic phases by weight.
        protected_revision = min(7, remaining) if total_days >= 7 else remaining
        result["final_revision"] = protected_revision
        remaining -= protected_revision

        if remaining > 0:
            # Reserve ~15% of remaining for mocks (biweekly cadence).
            mock_days = max(1, int(round(remaining * PHASE_WEIGHTS["mock_tests"])))
            mock_days = min(mock_days, remaining)
            result["mock_tests"] = mock_days
            remaining -= mock_days

        if remaining > 0:
            # Allocate the three academic phases proportionally to their weights.
            academic_total = PHASE_WEIGHTS["foundation"] + PHASE_WEIGHTS["skill_building"] + PHASE_WEIGHTS["advanced"]
            alloc: Dict[str, int] = {}
            for key in ("foundation", "skill_building", "advanced"):
                alloc[key] = int(round(remaining * PHASE_WEIGHTS[key] / academic_total))
            alloc_sum = sum(alloc.values())
            diff = remaining - alloc_sum
            if diff != 0:
                # Adjust the largest bucket first to absorb rounding.
                biggest = max(alloc, key=lambda k: alloc[k])
                alloc[biggest] = max(0, alloc[biggest] + diff)
            # Enforce minimum 1 day per phase.
            for key in ("foundation", "skill_building", "advanced"):
                if remaining == 0:
                    alloc[key] = 0
                elif alloc[key] <= 0:
                    # Steal a day from the biggest phase if possible.
                    if alloc_sum > len([k for k in alloc if alloc[k] > 0]):
                        biggest = max(alloc, key=lambda k: alloc[k])
                        if alloc[biggest] > 1:
                            alloc[biggest] -= 1
                            alloc[key] = 1
            result.update(alloc)

        # Correct any drift so the total equals total_days.
        total_alloc = sum(result.values())
        if total_alloc != total_days:
            diff = total_days - total_alloc
            biggest = max(result, key=lambda k: result[k]) if result else "foundation"
            result[biggest] = max(0, result[biggest] + diff)

        # Normalize phase order (non-decreasing day indices).
        return result

    @staticmethod
    def _build_phase_breakdown(start_date: date, phase_days: Dict[str, int]) -> List[PhaseBreakdown]:
        """Build the phase breakdown list with real start/end dates."""
        breakdown: List[PhaseBreakdown] = []
        cursor = start_date
        for key in PHASE_KEYS:
            days = phase_days.get(key, 0)
            if days <= 0:
                continue
            end = cursor + timedelta(days=days - 1)
            breakdown.append(
                PhaseBreakdown(
                    key=key,
                    label=PHASE_LABELS[key],
                    weight=PHASE_WEIGHTS[key],
                    start_date=cursor,
                    end_date=end,
                    days=days,
                )
            )
            cursor = end + timedelta(days=1)
        return breakdown

    def _phase_index_for_date(self, phase_days: Dict[str, int], day_index: int) -> int:
        """Map an absolute day index (0-based) to a phase index."""
        cursor = 0
        for phase_idx, key in enumerate(PHASE_KEYS):
            cursor += phase_days.get(key, 0)
            if day_index < cursor:
                return phase_idx
        return len(PHASE_KEYS) - 1

    def _phase_key_for_date(self, phase_days: Dict[str, int], day_index: int) -> str:
        cursor = 0
        for key in PHASE_KEYS:
            cursor += phase_days.get(key, 0)
            if day_index < cursor:
                return key
        return PHASE_KEYS[-1]

    def _generate_days(
        self,
        user_id: str,
        study_plan_id: str,
        start_date: date,
        exam_date: date,
        total_days: int,
        phase_days: Dict[str, int],
        base_budget: int,
        weak: List[str],
        strong: List[str],
        module: str,
    ) -> Tuple[List[GeneratedDay], int, int]:
        """Generate + persist daily plans and tasks for the whole timeline."""
        days: List[GeneratedDay] = []
        total_tasks = 0
        total_xp = 0

        for day_index in range(total_days):
            plan_date = start_date + timedelta(days=day_index)
            days_remaining = max((exam_date - plan_date).days, 0)

            phase_key = self._phase_key_for_date(phase_days, day_index)
            phase_index = self._phase_index_for_date(phase_days, day_index)

            is_revision_day = phase_key == "final_revision"
            is_mock_day = self._is_mock_day(day_index, phase_days)
            is_rest_day = phase_key == "final_revision" and (day_index % 2 == 1)

            budget = _daily_budget_for_date(
                base_budget=base_budget,
                day_index=day_index,
                is_revision_day=is_revision_day,
                is_mock_day=is_mock_day,
                days_remaining=days_remaining,
            )

            day_tasks, used_minutes, day_xp = self._build_day_tasks(
                plan_date=plan_date,
                day_index=day_index,
                phase_key=phase_key,
                budget=budget,
                weak=weak,
                strong=strong,
                module=module,
                is_revision_day=is_revision_day,
                is_mock_day=is_mock_day,
            )

            # ----------------------------------------------------------
            # Persist daily plan
            # ----------------------------------------------------------
            daily_plan = self.daily_plan_repo.create(
                user_id,
                {
                    "study_plan_id": study_plan_id,
                    "plan_date": plan_date.isoformat(),
                    "status": "scheduled",
                    "total_tasks": len(day_tasks),
                    "total_minutes": used_minutes,
                    "phase_index": phase_index,
                    "is_revision_day": is_revision_day,
                    "is_mock_day": is_mock_day,
                    "is_rest_day": is_rest_day,
                    "xp_reward": day_xp,
                },
            )
            daily_plan_id = daily_plan["id"]

            # ----------------------------------------------------------
            # Persist each task
            # ----------------------------------------------------------
            week_index = day_index // 7
            for order_idx, task_data in enumerate(day_tasks):
                self.task_repo.create(
                    user_id,
                    {
                        "study_plan_id": study_plan_id,
                        "daily_plan_id": daily_plan_id,
                        "phase_index": phase_index,
                        "title": task_data["title"],
                        "skill": task_data["skill"],
                        "task_type": task_data["task_type"],
                        "duration_minutes": task_data["duration_minutes"],
                        "scheduled_date": plan_date.isoformat(),
                        "priority": task_data["priority"],
                        "status": "pending",
                        "is_mandatory": task_data["is_mandatory"],
                        "order_index": order_idx,
                        "xp_reward": task_data["xp_reward"],
                        "difficulty": task_data["difficulty"],
                        "week_index": week_index,
                    },
                )

            total_tasks += len(day_tasks)
            total_xp += day_xp

            days.append(
                GeneratedDay(
                    plan_date=plan_date,
                    phase_index=phase_index,
                    is_revision_day=is_revision_day,
                    is_mock_day=is_mock_day,
                    is_rest_day=is_rest_day,
                    xp_reward=day_xp,
                    total_minutes=used_minutes,
                    tasks=day_tasks,
                )
            )

        return days, total_tasks, total_xp

    @staticmethod
    def _is_mock_day(day_index: int, phase_days: Dict[str, int]) -> bool:
        """Mock days every ~14 days starting after Phase 1 (foundation)."""
        foundation_days = phase_days.get("foundation", 0)
        mock_tests_days = phase_days.get("mock_tests", 0)
        # Never mock during foundation.
        if day_index < foundation_days:
            return False
        # Inside mock_tests phase, mock on alternating days (review days between).
        end_foundation = foundation_days
        start_mocks = end_foundation + phase_days.get("skill_building", 0) + phase_days.get("advanced", 0)
        if start_mocks <= day_index < start_mocks + mock_tests_days:
            offset = day_index - start_mocks
            return offset % 2 == 0
        # Outside explicit phases, use a 14-day cadence.
        if day_index >= start_mocks + mock_tests_days:
            return (day_index - start_mocks) % MOCK_INTERVAL_DAYS == 0
        return False

    def _build_day_tasks(
        self,
        plan_date: date,
        day_index: int,
        phase_key: str,
        budget: int,
        weak: List[str],
        strong: List[str],
        module: str,
        is_revision_day: bool,
        is_mock_day: bool,
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """Build the task list for a single day within budget."""
        tasks: List[Dict[str, Any]] = []
        used = 0

        # On mock days, the mock dominates the budget.
        if is_mock_day:
            mock_duration = min(budget, 45)  # section mock
            difficulty = min(5, 2 + day_index // 14)
            mock = self._make_task(
                skill="mock",
                task_type="mock_section" if mock_duration <= 60 else "full_mock",
                title=f"Mock Test — {self._mock_focus(day_index)}",
                duration=mock_duration,
                difficulty=difficulty,
                weak=weak,
                strong=strong,
                plan_date=plan_date,
            )
            tasks.append(mock)
            used += mock_duration
            # Add a short mistake-review task if budget allows.
            if used + 15 <= budget:
                review = self._make_task(
                    skill="grammar",
                    task_type="review",
                    title="Review Mock Mistakes",
                    duration=15,
                    difficulty=difficulty,
                    weak=weak,
                    strong=strong,
                    plan_date=plan_date,
                )
                tasks.append(review)
                used += 15
            return tasks, used, sum(t["xp_reward"] for t in tasks)

        # Revision days: light review tasks (mix of vocab/grammar/reading).
        if is_revision_day:
            revision_mix = [
                ("vocabulary", "vocab_set", "Vocabulary Review"),
                ("grammar", "grammar_lesson", "Grammar Drill"),
                ("reading", "practice_test", "Reading Warm-up"),
            ]
            idx = day_index % len(revision_mix)
            skill, task_type, base_title = revision_mix[idx]
            if used + 15 <= budget:
                task = self._make_task(
                    skill=skill,
                    task_type=task_type,
                    title=self._variant_title(base_title, day_index),
                    duration=min(15, budget - used),
                    difficulty=max(1, min(5, day_index // 21 + 1)),
                    weak=weak,
                    strong=strong,
                    plan_date=plan_date,
                )
                tasks.append(task)
                used += task["duration_minutes"]
            return tasks, used, sum(t["xp_reward"] for t in tasks)

        # --------------------------------------------------------------
        # Standard day: all 6 skills across every phase.
        # Foundation prioritizes weak skills earlier in the rotation.
        # Durations are scaled to fit the daily budget so every skill is
        # always represented (guarantees 6+ tasks per day).
        # --------------------------------------------------------------
        skill_pool = list(ALL_SKILLS)

        # Foundation prioritizes weak skills heavily.
        if phase_key == "foundation" and weak:
            skill_pool = list(weak) + [s for s in ALL_SKILLS if s not in weak]

        skill_cycle_index = day_index % len(skill_pool)
        rotated = skill_pool[skill_cycle_index:] + skill_pool[:skill_cycle_index]

        MIN_TASK_MINUTES = 5
        for idx, skill in enumerate(rotated):
            remaining_skills = len(rotated) - idx - 1
            remaining_budget = budget - used
            # Reserve minimum minutes for every remaining skill so all 6 fit.
            max_allowed = remaining_budget - remaining_skills * MIN_TASK_MINUTES

            task_type = self._select_task_type(skill, day_index)
            natural = self._select_duration(skill, day_index, remaining_budget)
            if max_allowed >= MIN_TASK_MINUTES:
                duration = max(MIN_TASK_MINUTES, min(natural, max_allowed))
            else:
                # Budget is very tight: a minimal viable slice still counts.
                duration = MIN_TASK_MINUTES

            difficulty = min(5, max(1, 1 + day_index // 21))  # ramp over ~3 weeks
            week_index_local = day_index // 7

            task = self._make_task(
                skill=skill,
                task_type=task_type,
                title=self._task_title(skill, task_type, day_index, week_index_local),
                duration=duration,
                difficulty=difficulty,
                weak=weak,
                strong=strong,
                plan_date=plan_date,
            )
            tasks.append(task)
            used += task["duration_minutes"]

        return tasks, used, sum(t["xp_reward"] for t in tasks)

    # ------------------------------------------------------------------
    # Task construction helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _mock_focus(day_index: int) -> str:
        focuses = ("Listening", "Reading", "Writing", "Speaking")
        return focuses[day_index % len(focuses)]

    @staticmethod
    def _select_task_type(skill: str, day_index: int) -> str:
        types = SKILL_TASK_TYPES.get(skill, ("practice_test",))
        return types[day_index % len(types)]

    @staticmethod
    def _select_duration(skill: str, day_index: int, remaining_budget: int) -> int:
        lo, hi = SKILL_DURATIONS.get(skill, (15, 25))
        duration = lo + (day_index % (hi - lo + 1))
        return min(duration, max(remaining_budget, lo))

    def _task_title(self, skill: str, task_type: str, day_index: int, week_index: int) -> str:
        base = task_type.replace("_", " ").title()
        return f"{base} — {skill.title()} (W{week_index + 1})"

    @staticmethod
    def _variant_title(base_title: str, day_index: int) -> str:
        themes = ("Essentials", "Spotlight", "Deep Dive", "Quick Wins", "Core Review")
        return f"{base_title} — {themes[day_index % len(themes)]}"

    def _make_task(
        self,
        skill: str,
        task_type: str,
        title: str,
        duration: int,
        difficulty: int,
        weak: List[str],
        strong: List[str],
        plan_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Construct a task dict with computed XP and priority."""
        xp = _xp_for_task(duration, difficulty)
        priority = _skill_priority(skill, weak, strong)
        return {
            "title": title,
            "skill": skill,
            "task_type": task_type,
            "duration_minutes": duration,
            "priority": priority,
            "xp_reward": xp,
            "difficulty": difficulty,
            "is_mandatory": priority >= PRIORITY_WEAK if plan_date else False,
        }

    def _capture_schedule_snapshot(self, user_id: str) -> Dict[str, Any]:
        """Capture a snapshot of the current schedule for history tracking."""
        if self.db is None:
            return {}

        try:
            study_plan = self._safe_get_active_plan(user_id)
            study_plan_id = study_plan.get("id") if study_plan else None
            if not study_plan_id:
                return {"study_plan_id": None, "tasks": []}

            daily_plans = self.daily_plan_repo.list_for_study_plan(user_id, study_plan_id)
            tasks = []
            for dp in daily_plans:
                day_tasks = self.task_repo.list_for_user(
                    user_id=user_id, daily_plan_id=dp["id"]
                )
                for t in day_tasks:
                    tasks.append({
                        "id": t.get("id"),
                        "title": t.get("title"),
                        "scheduled_date": t.get("scheduled_date"),
                        "status": t.get("status"),
                        "duration_minutes": t.get("duration_minutes"),
                        "priority": t.get("priority"),
                        "skill": t.get("skill"),
                        "task_type": t.get("task_type"),
                    })

            return {
                "study_plan_id": study_plan_id,
                "captured_at": date.today().isoformat(),
                "tasks": tasks,
            }
        except Exception as exc:
            logger.warning("schedule_history._capture_schedule_snapshot failed user=%s: %s", user_id, exc)
            return {}

    def _safe_get_active_plan(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        return self.study_plan_repo.get_active(user_id)

    # ------------------------------------------------------------------
    # Diagnostic-first generation (personalized roadmap)
    # ------------------------------------------------------------------
    def generate_from_diagnostic(
        self, user_id: str, request: DiagnosticStudyPlanRequest
    ) -> Dict[str, Any]:
        """
        Generate a personalized study plan (roadmap) seeded from the **latest
        diagnostic results** instead of manual assumptions.

        The Diagnostic Roadmap Service resolves the user's measured current band
        and weakest/strongest skills from their latest completed diagnostic;
        those signals drive every decision in :meth:`generate` (skill priority,
        task emphasis, phase focus). Client values (exam date, minutes budget,
        module, optional target band) are honored as overrides.

        Raises ValidationError if the user has neither diagnostic results nor a
        usable profile fallback.
        """
        profile = diagnostic_roadmap_service.resolve_profile(
            user_id, explicit_target=request.target_band
        )

        exam_date = request.exam_date
        if exam_date is None:
            raw = profile.get("profile_exam_date")
            if raw:
                try:
                    exam_date = raw if isinstance(raw, date) else date.fromisoformat(str(raw)[:10])
                except (ValueError, TypeError):
                    exam_date = None
        if exam_date is None or exam_date <= date.today():
            raise ValidationError(
                "exam_date is required to generate a roadmap (set it on your profile or in the request)."
            )

        current_band = float(profile.get("current_band") or 5.0)
        target_band = float(profile.get("target_band") or min(9.0, current_band + 1.0))
        target_band = max(target_band, current_band)  # target >= current

        weak = profile.get("weakest_skills") or []
        strong = profile.get("strongest_skills") or []

        if not profile.get("has_diagnostic") and not weak and not strong:
            raise ValidationError(
                "Complete the Diagnostic Test first, or set weakest/strongest skills in your profile."
            )

        plan_request = StudyPlanGenerateRequest(
            exam_date=exam_date,
            current_band=current_band,
            target_band=target_band,
            daily_minutes_budget=request.daily_minutes_budget,
            module=request.module,
            weakest_skills=weak,
            strongest_skills=strong,
            start_date=request.start_date,
        )

        result = self.generate(user_id, plan_request)
        self._tag_plan_source(user_id, result, profile)
        return result

    def _tag_plan_source(
        self, user_id: str, generated: Dict[str, Any], profile: Dict[str, Any]
    ) -> None:
        """Stamp the generated plan with its diagnostic source (best-effort)."""
        if self.db is None:
            return
        plan_id = generated.get("study_plan_id")
        if not plan_id:
            return
        try:
            plan = self.study_plan_repo.get_by_id(plan_id, user_id=user_id)
            meta = dict(plan.get("meta") or {})
            meta["source"] = profile.get("source", "unknown")
            meta["diagnostic_attempt_id"] = profile.get("attempt_id")
            meta["skill_bands"] = profile.get("skill_bands")
            self.study_plan_repo.update(plan_id, {"meta": meta}, user_id)
        except Exception:
            return


# Singleton instance bound to the shared DB session.
from app.db.session import db_session

study_plan_generator = StudyPlanGenerator(db_session)

