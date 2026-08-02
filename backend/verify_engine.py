"""
Standalone verification for the Study Plan Generation Engine.

Stubs the Supabase-backed DB modules so the generator's pure logic can be
exercised without live credentials. Run from the backend/ directory:

    python verify_engine.py
"""
import sys
import types
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Stub app.db.supabase and app.db.session before importing anything else.
# We register ONLY the two DB modules; the real app/services, app/models,
# app/core, app/repositories packages are imported normally from disk.
# ---------------------------------------------------------------------------
import app  # noqa: E402  (real package, keeps __path__ intact)
import app.db as db_pkg  # noqa: E402

supabase_mod = types.ModuleType("app.db.supabase")
supabase_mod.supabase = None
supabase_mod.get_supabase = lambda: None

class DatabaseSession:  # noqa: F811
    def __init__(self, *args, **kwargs):
        pass

session_mod = types.ModuleType("app.db.session")
session_mod.DatabaseSession = DatabaseSession
session_mod.db_session = None
session_mod.get_db = lambda: None

sys.modules["app.db.supabase"] = supabase_mod
sys.modules["app.db.session"] = session_mod

# ---------------------------------------------------------------------------
# Now import the generator and schemas (repos import DatabaseSession only)
# ---------------------------------------------------------------------------
from app.services.study_plan_generator import (  # noqa: E402
    StudyPlanGenerator,
    _daily_budget_for_date,
    _xp_for_task,
    _skill_priority,
)
from app.models.study_plan_engine import (  # noqa: E402
    StudyPlanGenerateRequest,
    StudyPlanDaysResponse,
)

_allocate_phases = StudyPlanGenerator._allocate_phases

passed = 0


def check(name: str, condition: bool):
    global passed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}")


# ---------------------------------------------------------------------------
# 1. Phase allocation (weights honored + sums exact)
# ---------------------------------------------------------------------------
for total in (30, 45, 60, 90, 120):
    alloc = _allocate_phases(total)
    check(f"_allocate_phases({total}) sums to {total}", sum(alloc.values()) == total)
    check(
        f"_allocate_phases({total}) includes all 5 phases",
        set(alloc.keys()) == {"foundation", "skill_building", "advanced", "mock_tests", "final_revision"},
    )
    if total >= 30:
        # Foundation & skill building should each be the biggest buckets (~30%).
        check(
            f"_allocate_phases({total}) weights roughly honored",
            alloc["foundation"] >= alloc["advanced"] and alloc["skill_building"] >= alloc["advanced"],
        )

# Final revision protected to last 7 days.
alloc90 = _allocate_phases(90)
check("final_revision <= 7 days for 90-day plan", alloc90["final_revision"] <= 7)

# ---------------------------------------------------------------------------
# 2. XP and priority rules
# ---------------------------------------------------------------------------
check("XP(30,3) == 35 (30 min + 5 difficulty bonus)", _xp_for_task(30, 3) == 35)
check("XP(15,1) == 15 (15 min + 0 bonus)", _xp_for_task(15, 1) == 15)
check("weak skill priority == 5", _skill_priority("reading", ["reading", "grammar"], ["speaking"]) == 5)
check("normal skill priority == 3", _skill_priority("writing", ["reading"], ["speaking"]) == 3)
check("strong skill priority == 2", _skill_priority("speaking", ["reading"], ["speaking"]) == 2)

# ---------------------------------------------------------------------------
# 3. Daily budget adjustments
# ---------------------------------------------------------------------------
check("revision day budget halved", _daily_budget_for_date(60, 20, True, False, 20) == 30)
check("crunch-mode budget boosted", _daily_budget_for_date(60, 10, False, False, 10) == 78)
check("mock day keeps full budget", _daily_budget_for_date(60, 5, False, True, 5) == 60)

# ---------------------------------------------------------------------------
# 4. Day-task builder guarantees 6 skill tasks per standard day
# ---------------------------------------------------------------------------
gen = StudyPlanGenerator(None)  # no DB needed for pure builder helpers

request = StudyPlanGenerateRequest(
    exam_date=date.today() + timedelta(days=30),
    current_band=6.5,
    target_band=7.5,
    daily_minutes_budget=60,
    module="academic",
    weakest_skills=["reading", "grammar"],
    strongest_skills=["speaking"],
)

# Build a standard (non-mock, non-revision) day.
task_dict = gen._build_day_tasks(
    plan_date=date.today() + timedelta(days=1),
    day_index=2,
    phase_key="foundation",
    budget=60,
    weak=list(request.weakest_skills),
    strong=list(request.strongest_skills),
    module=request.module,
    is_revision_day=False,
    is_mock_day=False,
)
tasks, used, xp = task_dict
skills = [t["skill"] for t in tasks]
check("standard day produces 6 tasks", len(tasks) == 6)
check("standard day covers all 6 skills", set(skills) == {"reading", "listening", "writing", "speaking", "vocabulary", "grammar"})
check("standard day stays within budget", used <= 60)
check("standard day XP > 0", xp > 0)
check("every task has difficulty in 1..5", all(1 <= t["difficulty"] <= 5 for t in tasks))
check("every task has xp_reward >= 0", all(t["xp_reward"] >= 0 for t in tasks))
check("every task has priority in 1..5", all(1 <= t["priority"] <= 5 for t in tasks))

# ---------------------------------------------------------------------------
# 5. Mock day + revision day builders
# ---------------------------------------------------------------------------
mock_tasks, mock_used, mock_xp = gen._build_day_tasks(
    plan_date=date.today() + timedelta(days=1),
    day_index=16,
    phase_key="mock_tests",
    budget=60,
    weak=[],
    strong=[],
    module="academic",
    is_revision_day=False,
    is_mock_day=True,
)
check("mock day has a mock task", any(t["skill"] == "mock" for t in mock_tasks))

rev_tasks, rev_used, rev_xp = gen._build_day_tasks(
    plan_date=date.today() + timedelta(days=1),
    day_index=30,
    phase_key="final_revision",
    budget=30,
    weak=[],
    strong=[],
    module="academic",
    is_revision_day=True,
    is_mock_day=False,
)
check("revision day produces at least 1 task", len(rev_tasks) >= 1)

# ---------------------------------------------------------------------------
# 6. __init__ wiring — study_plan_generator available in deps module
# ---------------------------------------------------------------------------
from app.services.study_plan_generator import study_plan_generator  # noqa: E402
check("singleton study_plan_generator exists", study_plan_generator is not None)

print(f"\n{passed} checks passed.")
sys.exit(0 if passed == 34 else 1)

