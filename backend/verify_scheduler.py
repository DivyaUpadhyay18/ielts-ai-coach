"""
Standalone verification for the Adaptive Scheduler feature.

Stubs the Supabase-backed DB modules so the scheduler's pure logic and
wiring can be exercised without live credentials. Run from backend/:

    python verify_scheduler.py
"""
import sys
import types
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Stub app.db.supabase and app.db.session before importing anything else.
# ---------------------------------------------------------------------------
import app  # noqa: E402
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
# Import the scheduler service, models, and repos (repos import DatabaseSession only).
# ---------------------------------------------------------------------------
from app.services.adaptive_scheduler import (  # noqa: E402
    AdaptiveSchedulerService,
    OVERLOAD_RATIO_THRESHOLD,
    DEPRIORITIZE_PROPORTION,
    CRUNCH_DAYS,
    DAILY_OVERLOAD_RATIO_THRESHOLD,
    STREAK_SAVER_THRESHOLD,
    FINAL_REVISION_DAYS,
    MOCK_BEFORE_EXAM_GUARD_DAYS,
    MAX_SHIFT_DAYS,
)
from app.models.scheduler import (  # noqa: E402
    SchedulerMetrics,
    TRIGGER_TYPES,
    ADJUSTMENT_ACTIONS,
    SchedulerRunResponse,
    SchedulerExplainResponse,
)
from app.repositories.scheduler_repo import SchedulerRepository  # noqa: E402
from app.repositories.task_repo import TaskRepository  # noqa: E402

passed = 0
failed = 0


def check(name: str, condition: bool):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")


# ---------------------------------------------------------------------------
# 1. Model constraints validated at Pydantic level
# ---------------------------------------------------------------------------
print("\n=== 1. Model constraints ===")
m = SchedulerMetrics(
    total_pending=5,
    completed_yesterday=3,
    missed_yesterday=2,
    carried_forward=2,
    rescheduled=1,
    deprioritized=1,
    days_remaining=30,
    completion_rate=0.6,
    previous_workload_minutes=420,
    new_workload_minutes=400,
    workload_percent=95.2,
    overload_factor=1.1,
    adjustment_count=4,
    streak_saver_mode=True,
    consecutive_missed_days=4,
)
check("SchedulerMetrics defaults zeroed", SchedulerMetrics().total_pending == 0)
check("SchedulerMetrics accepts valid values", m.completion_rate == 0.6)
check("SchedulerMetrics streak_saver_mode field", m.streak_saver_mode is True)
check("SchedulerMetrics consecutive_missed_days field", m.consecutive_missed_days == 4)
check("SchedulerMetrics defaults streak_saver_mode False", SchedulerMetrics().streak_saver_mode is False)
check("SchedulerMetrics defaults consecutive_missed_days 0", SchedulerMetrics().consecutive_missed_days == 0)
check("TRIGGER_TYPES include midnight/app_open/manual", set(TRIGGER_TYPES) == {"midnight", "app_open", "manual"})
check("ADJUSTMENT_ACTIONS include all 6 actions", set(ADJUSTMENT_ACTIONS) == {"rescheduled", "carried_forward", "deprioritized", "spread", "merged", "kept"})

# ---------------------------------------------------------------------------
# 2. Scheduler service static/pure helpers
# ---------------------------------------------------------------------------
print("\n=== 2. Pure helpers ===")
svc = AdaptiveSchedulerService(None)  # no DB needed for pure helpers

check(
    "overload_factor clamps to min 0.5",
    svc._overload_factor(0, 60) == 0.5,
)
check(
    "overload_factor computes 7-day ratio",
    abs(svc._overload_factor(7 * 60, 60) - 1.0) < 1e-6,
)
check(
    "overload_factor clamps to max 3.0",
    svc._overload_factor(5000, 60) == 3.0,
)
check(
    "overload_factor returns 1.0 for zero budget",
    svc._overload_factor(100, 0) == 1.0,
)
check(
    "_parse_date accepts date object",
    svc._parse_date(date(2025, 1, 1)) == date(2025, 1, 1),
)
check(
    "_parse_date accepts iso string",
    svc._parse_date("2025-06-15T00:00:00") == date(2025, 6, 15),
)
check(
    "_parse_date accepts short iso string",
    svc._parse_date("2025-06-15") == date(2025, 6, 15),
)
check(
    "_sort_by_priority orders highest priority first",
    [t["id"] for t in svc._sort_by_priority([
        {"id": "b", "priority": 1, "scheduled_date": "2025-01-02"},
        {"id": "a", "priority": 5, "scheduled_date": "2025-01-01"},
        {"id": "c", "priority": 3, "scheduled_date": "2025-01-03"},
    ])] == ["a", "c", "b"],
)
check(
    "_sort_by_priority breaks ties by earliest date",
    [t["id"] for t in svc._sort_by_priority([
        {"id": "b", "priority": 3, "scheduled_date": "2025-01-02"},
        {"id": "a", "priority": 3, "scheduled_date": "2025-01-01"},
    ])] == ["a", "b"],
)

# ---------------------------------------------------------------------------
# 3. _build_neutral returns safe no-op payloads (no DB crash)
# ---------------------------------------------------------------------------
print("\n=== 3. Neutral / no-op payloads ===")
neutral = svc._build_neutral("u1", date.today(), "manual", "no_active_plan", note="Generate a study plan first.")
check("neutral run reports would_change False", neutral["would_change"] is False)
check("neutral run has empty adjustments", neutral["adjustments"] == [])
check("neutral run has days_remaining", "days_remaining" in neutral["metrics"])
check("neutral run has summary", "summary" in neutral)
check("neutral run has note", "note" in neutral)

neutral_exam = svc._build_neutral("u1", date.today(), "manual", "exam_date_passed")
check("neutral exam_date_passed has would_change False", neutral_exam["would_change"] is False)

neutral_with_exam = svc._build_neutral(
    "u1", date(2025, 6, 1), "manual", "no_active_plan",
    exam_date=date(2025, 7, 1),
)
check("neutral with exam_date computes days_remaining", neutral_with_exam["metrics"]["days_remaining"] == 30)

# ---------------------------------------------------------------------------
# 4. Summarize strings
# ---------------------------------------------------------------------------
print("\n=== 4. Summary strings ===")
s_all_done = svc._summarize({"carried_forward": 0, "rescheduled": 0, "deprioritized": 0, "missed_yesterday": 0, "streak_saver_mode": False}, [])
check("summary: all-done message", "on track" in s_all_done)

s_carried = svc._summarize({"carried_forward": 3, "rescheduled": 2, "deprioritized": 0, "missed_yesterday": 5, "streak_saver_mode": False}, [{"action": "carried_forward"}])
check("summary: counts carried + rescheduled", "3 unfinished" in s_carried and "2 task(s)" in s_carried)

s_kept = svc._summarize({"carried_forward": 0, "rescheduled": 0, "deprioritized": 0, "missed_yesterday": 2, "streak_saver_mode": False}, [])
check("summary: kept-in-place message", "kept in place" in s_kept)

s_deprioritized = svc._summarize({"carried_forward": 0, "rescheduled": 0, "deprioritized": 1, "missed_yesterday": 1, "streak_saver_mode": False}, [])
check("summary: deprioritized message", "deferred" in s_deprioritized)

s_streak = svc._summarize({"carried_forward": 1, "rescheduled": 0, "deprioritized": 0, "missed_yesterday": 3, "streak_saver_mode": True, "consecutive_missed_days": 4}, [])
check("summary: streak-saver message", "Streak-saver" in s_streak and "4 days" in s_streak)

# ---------------------------------------------------------------------------
# 5. Tunables sanity
# ---------------------------------------------------------------------------
print("\n=== 5. Tunables ===")
check("OVERLOAD_RATIO_THRESHOLD == 1.3", OVERLOAD_RATIO_THRESHOLD == 1.3)
check("DEPRIORITIZE_PROPORTION == 0.2", abs(DEPRIORITIZE_PROPORTION - 0.2) < 1e-9)
check("CRUNCH_DAYS == 14", CRUNCH_DAYS == 14)
check("DAILY_OVERLOAD_RATIO_THRESHOLD == 1.5", DAILY_OVERLOAD_RATIO_THRESHOLD == 1.5)
check("STREAK_SAVER_THRESHOLD == 3", STREAK_SAVER_THRESHOLD == 3)
check("FINAL_REVISION_DAYS == 14", FINAL_REVISION_DAYS == 14)
check("MOCK_BEFORE_EXAM_GUARD_DAYS == 1", MOCK_BEFORE_EXAM_GUARD_DAYS == 1)
check("MAX_SHIFT_DAYS == 14", MAX_SHIFT_DAYS == 14)

# ---------------------------------------------------------------------------
# 6. __init__ / wiring — router + deps registered
# ---------------------------------------------------------------------------
print("\n=== 6. API wiring ===")
from app.api.v1.router import router as v1_router  # noqa: E402
paths = {r.path for r in v1_router.routes}
check("scheduler router registered under /scheduler", "/scheduler/run" in paths)
check("scheduler /latest route exists", "/scheduler/latest" in paths)
check("scheduler /runs route exists", "/scheduler/runs" in paths)
check("scheduler /explain route exists", "/scheduler/explain" in paths)
check("scheduler /runs/{run_id} route exists", "/scheduler/runs/{run_id}" in paths)

from app.api.deps import get_scheduler_service, get_scheduler_repo  # noqa: E402
check("get_scheduler_service dependency exists", callable(get_scheduler_service))
check("get_scheduler_repo dependency exists", callable(get_scheduler_repo))

# ---------------------------------------------------------------------------
# 7. TaskRepository scheduler methods present
# ---------------------------------------------------------------------------
print("\n=== 7. Repository methods ===")
for method in (
    "list_pending_before",
    "list_for_date",
    "list_mock_tasks",
    "mark_missed",
    "carry_forward",
    "reschedule_for_date",
    "count_consecutive_missed_days",
):
    check(f"TaskRepository.{method} exists", hasattr(TaskRepository, method))

for method in (
    "create_run",
    "list_runs",
    "get_latest_run",
    "get_run_for_date",
    "get_run",
    "add_adjustments",
    "get_run_adjustments",
    "list_adjustments",
):
    check(f"SchedulerRepository.{method} exists", hasattr(SchedulerRepository, method))

# ---------------------------------------------------------------------------
# 8. Safe DB wrappers return empty/None when db is None
# ---------------------------------------------------------------------------
print("\n=== 8. Safe DB wrappers (no DB) ===")
check("_safe_get_profile returns None", svc._safe_get_profile("u1") is None)
check("_safe_get_active_plan returns None", svc._safe_get_active_plan("u1") is None)
check("_safe_list_pending_before returns []", svc._safe_list_pending_before("u1", date.today()) == [])
check("_safe_list_for_user returns []", svc._safe_list_for_user(user_id="u1", status="pending") == [])
check("_safe_count_consecutive_missed returns 0", svc._safe_count_consecutive_missed("u1", date.today()) == 0)
check("_safe_get_run_for_date returns None", svc._safe_get_run_for_date("u1", date.today(), "midnight") is None)
check("_safe_list_for_date returns []", svc._safe_list_for_date("u1", date.today()) == [])
check("_safe_get_latest_run returns None", svc._safe_get_latest_run("u1") is None)
check("_safe_get_run_adjustments returns []", svc._safe_get_run_adjustments("run1") == [])
check("_safe_list_runs returns []", svc._safe_list_runs("u1") == [])

# ---------------------------------------------------------------------------
# 9. Day type classification (no DB → all normal except final revision)
# ---------------------------------------------------------------------------
print("\n=== 9. Day type classification ===")
exam = date(2025, 8, 15)
# A day well before the exam with no DB → normal
# Use June 3 (Tuesday) to avoid the default Sunday rest day
check("_day_type returns normal for far day", svc._day_type("u1", date(2025, 6, 3), exam) == "normal")
# A day in the final revision window → final_revision
check("_day_type returns final_revision in last 14 days", svc._day_type("u1", exam - timedelta(days=7), exam) == "final_revision")
# The exam day itself → final_revision (it's >= exam - 14)
check("_day_type returns final_revision on exam day", svc._day_type("u1", exam, exam) == "final_revision")

# ---------------------------------------------------------------------------
# 10. Rest day detection
# ---------------------------------------------------------------------------
print("\n=== 10. Rest day detection ===")
# With no DB, _get_user_rest_day defaults to Sunday (6)
check("_get_user_rest_day defaults to Sunday (6)", svc._get_user_rest_day("u1") == 6)
# 2025-06-01 is a Sunday (weekday 6)
check("_day_type returns rest on Sunday", svc._day_type("u1", date(2025, 6, 1), date(2025, 8, 15)) == "rest")
# 2025-06-02 is a Monday (weekday 0) — not rest
check("_day_type returns normal on Monday", svc._day_type("u1", date(2025, 6, 2), date(2025, 8, 15)) == "normal")

# ---------------------------------------------------------------------------
# 11. Slot finding (no DB → all days have full budget available)
# ---------------------------------------------------------------------------
print("\n=== 11. Slot finding ===")
# With no DB, every day has full base_budget available and is "normal"
# (except rest days and final revision).
slot = svc._find_next_available_slot("u1", date(2025, 6, 2), date(2025, 8, 15), 30, 60)
check("_find_next_available_slot returns a date", slot is not None)
check("_find_next_available_slot returns the start date", slot == date(2025, 6, 2))

# Slot finding past exam returns None
slot_past = svc._find_next_available_slot("u1", date(2025, 8, 20), date(2025, 8, 15), 30, 60)
check("_find_next_available_slot returns None past exam", slot_past is None)

# Mock slot before exam
mock_slot = svc._find_slot_before_exam("u1", date(2025, 6, 2), date(2025, 8, 15), 45, 60)
check("_find_slot_before_exam returns a date", mock_slot is not None)
check("_find_slot_before_exam returns before exam", mock_slot < date(2025, 8, 15))

# ---------------------------------------------------------------------------
# 12. Remaining budget calculation (no DB → full budget)
# ---------------------------------------------------------------------------
print("\n=== 12. Budget calculation ===")
check("_remaining_budget_for_date returns full budget (no tasks)", svc._remaining_budget_for_date("u1", date(2025, 6, 2), 60) == 60)
check("_remaining_budget_for_date with 0 budget returns 0", svc._remaining_budget_for_date("u1", date(2025, 6, 2), 0) == 0)

# ---------------------------------------------------------------------------
# 13. Serialization
# ---------------------------------------------------------------------------
print("\n=== 13. Serialization ===")
serialized = svc._serialize_adjustments([
    {
        "task_id": "t1",
        "task_title": "Reading Practice",
        "from_date": date(2025, 6, 1),
        "to_date": date(2025, 6, 2),
        "action": "carried_forward",
        "reason": "Missed task moved forward.",
        "priority_delta": 1,
    }
])
check("_serialize_adjustments converts dates to iso strings", serialized[0]["from_date"] == "2025-06-01")
check("_serialize_adjustments preserves task_title", serialized[0]["task_title"] == "Reading Practice")
check("_serialize_adjustments preserves action", serialized[0]["action"] == "carried_forward")

# ---------------------------------------------------------------------------
# 14. Handle overdue — mock task (no DB, so no write but action recorded)
# ---------------------------------------------------------------------------
print("\n=== 14. Overdue task handling ===")
# Use a section mock (45min) that fits within the 60min budget.
mock_task = {
    "id": "m1",
    "title": "Mock Section — Listening",
    "task_type": "mock_section",
    "duration_minutes": 45,
    "priority": 5,
    "scheduled_date": "2025-06-01",
    "is_mandatory": True,
}
mock_action = svc._handle_overdue("u1", mock_task, date(2025, 6, 2), date(2025, 8, 15), 60)
check("_handle_overdue mock returns rescheduled action", mock_action["action"] == "rescheduled")
check("_handle_overdue mock keeps task_title", mock_action["task_title"] == "Mock Section — Listening")
check("_handle_overdue mock target before exam", mock_action["to_date"] < date(2025, 8, 15))

# Standard overdue task
std_task = {
    "id": "t2",
    "title": "Vocabulary Set",
    "task_type": "vocab_set",
    "duration_minutes": 15,
    "priority": 3,
    "scheduled_date": "2025-06-01",
    "is_mandatory": False,
}
std_action = svc._handle_overdue("u1", std_task, date(2025, 6, 2), date(2025, 8, 15), 60)
check("_handle_overdue standard returns carried_forward", std_action["action"] == "carried_forward")
check("_handle_overdue standard bumps priority", std_action["priority_delta"] == 1)

# Streak-saver mode: low-priority task is deprioritized
low_task = {
    "id": "t3",
    "title": "Light Reading",
    "task_type": "article",
    "duration_minutes": 15,
    "priority": 2,
    "scheduled_date": "2025-06-01",
    "is_mandatory": False,
}
saver_action = svc._handle_overdue("u1", low_task, date(2025, 6, 2), date(2025, 8, 15), 60, streak_saver_mode=True)
check("_handle_overdue streak-saver deprioritizes low-priority", saver_action["action"] == "deprioritized")
check("_handle_overdue streak-saver reason mentions streak-saver", "Streak-saver" in saver_action["reason"])

# Streak-saver mode: high-priority task is still carried forward
high_task = {
    "id": "t4",
    "title": "Critical Writing Task",
    "task_type": "writing_task2",
    "duration_minutes": 40,
    "priority": 5,
    "scheduled_date": "2025-06-01",
    "is_mandatory": True,
}
high_action = svc._handle_overdue("u1", high_task, date(2025, 6, 2), date(2025, 8, 15), 60, streak_saver_mode=True)
check("_handle_overdue streak-saver carries high-priority", high_action["action"] == "carried_forward")

# ---------------------------------------------------------------------------
# 15. Overload mitigation (no DB → no tasks → no actions)
# ---------------------------------------------------------------------------
print("\n=== 15. Overload mitigation ===")
new_wl, actions = svc._mitigate_overload("u1", date(2025, 6, 2), 72, 60, 1.0, date(2025, 8, 15))
check("_mitigate_overload returns 0 workload with no tasks", new_wl == 0)
check("_mitigate_overload returns no actions with no tasks", actions == [])

# ---------------------------------------------------------------------------
# 16. Dry-run (explain) with no DB — should not crash, returns neutral
# ---------------------------------------------------------------------------
print("\n=== 16. Dry-run / explain ===")
try:
    result = svc.explain("u1", run_date=date(2025, 6, 2))
    # With no DB, user is None → exam_date is None → raises ValidationError
    check("explain raises ValidationError when no exam date", False)
except Exception as exc:
    from app.core.exceptions import ValidationError
    check("explain raises ValidationError when no exam date", isinstance(exc, ValidationError))

# ---------------------------------------------------------------------------
# 17. Idempotency — _build_existing_run_response
# ---------------------------------------------------------------------------
print("\n=== 17. Idempotency ===")
fake_run = {
    "id": "run-1",
    "user_id": "u1",
    "trigger_type": "midnight",
    "run_date": "2025-06-02",
    "metrics": {"total_pending": 5},
    "summary": "Test run",
}
existing_resp = svc._build_existing_run_response(fake_run, "u1")
check("_build_existing_run_response sets idempotent flag", existing_resp["idempotent"] is True)
check("_build_existing_run_response preserves run id", existing_resp["run"]["id"] == "run-1")
check("_build_existing_run_response has empty adjustments (no DB)", existing_resp["adjustments"] == [])

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'=' * 50}")
print(f"  {passed} checks passed, {failed} failed.")
print(f"{'=' * 50}")
sys.exit(0 if failed == 0 else 1)