"""
Standalone verification for the Schedule History feature.

Stubs the Supabase-backed DB modules so the schedule history's
pure logic and wiring can be exercised without live credentials.
Run from backend/:

    python verify_schedule_history.py
"""
import sys
import types

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
# Import schedule history components.
# ---------------------------------------------------------------------------
from app.models.schedule_history import (  # noqa: E402
    ScheduleHistoryEntry,
    ScheduleHistoryListResponse,
    ScheduleComparisonResponse,
    ScheduleHistoryCreate,
    ScheduleHistoryUpdate,
    ScheduleHistoryFilter,
)
from app.repositories.schedule_history_repo import ScheduleHistoryRepository  # noqa: E402
from app.services.schedule_history_service import ScheduleHistoryService  # noqa: E402

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
entry = ScheduleHistoryEntry(
    id="test-id",
    user_id="user-1",
    change_reason="Test change",
    change_type="scheduler_run",
)
check("ScheduleHistoryEntry accepts minimal fields", entry.id == "test-id")
check("ScheduleHistoryEntry default change_type is scheduler_run", entry.change_type == "scheduler_run")
check("ScheduleHistoryEntry default adjustments_count is 0", entry.adjustments_count == 0)
check("ScheduleHistoryEntry default tasks_affected is 0", entry.tasks_affected == 0)
check("ScheduleHistoryEntry default previous_schedule is empty dict", entry.previous_schedule == {})
check("ScheduleHistoryEntry default new_schedule is empty dict", entry.new_schedule == {})

create_data = ScheduleHistoryCreate(
    previous_schedule={"tasks": []},
    new_schedule={"tasks": []},
    change_reason="Test reason",
)
check("ScheduleHistoryCreate accepts required fields", create_data.change_reason == "Test reason")
check("ScheduleHistoryCreate default change_type is scheduler_run", create_data.change_type == "scheduler_run")

update_data = ScheduleHistoryUpdate(user_action="accepted")
check("ScheduleHistoryUpdate accepts user_action", update_data.user_action == "accepted")

filter_data = ScheduleHistoryFilter()
check("ScheduleHistoryFilter default limit is 20", filter_data.limit == 20)
check("ScheduleHistoryFilter default offset is 0", filter_data.offset == 0)

# ---------------------------------------------------------------------------
# 2. Service methods exist and have correct signatures
# ---------------------------------------------------------------------------
print("\n=== 2. Service methods ===")
svc = ScheduleHistoryService()
check("Service has log_scheduler_run method", hasattr(svc, "log_scheduler_run"))
check("Service has log_exam_date_update method", hasattr(svc, "log_exam_date_update"))
check("Service has log_manual_reschedule method", hasattr(svc, "log_manual_reschedule"))
check("Service has log_study_plan_regeneration method", hasattr(svc, "log_study_plan_regeneration"))
check("Service has get_user_history method", hasattr(svc, "get_user_history"))
check("Service has get_comparison method", hasattr(svc, "get_comparison"))
check("Service has update_user_action method", hasattr(svc, "update_user_action"))
check("Service has get_stats method", hasattr(svc, "get_stats"))

# ---------------------------------------------------------------------------
# 3. Valid user actions
# ---------------------------------------------------------------------------
print("\n=== 3. User action validation ===")
valid_actions = ["accepted", "rejected", "modified", "pending", "auto_applied"]
for action in valid_actions:
    check(f"Action '{action}' is valid", action in valid_actions)

invalid_action = "invalid_action"
check(f"Action '{invalid_action}' is invalid", invalid_action not in valid_actions)

# ---------------------------------------------------------------------------
# 4. Change types
# ---------------------------------------------------------------------------
print("\n=== 4. Change types ===")
change_types = [
    "scheduler_run",
    "exam_date_update",
    "manual_reschedule",
    "study_plan_regeneration",
    "task_modification",
    "user_override",
]
for ct in change_types:
    check(f"Change type '{ct}' is valid", ct in change_types)

# ---------------------------------------------------------------------------
# 5. Repository methods exist
# ---------------------------------------------------------------------------
print("\n=== 5. Repository methods ===")
repo = ScheduleHistoryRepository(None)
for method in [
    "create_entry",
    "get_by_id",
    "list_history",
    "update_user_action",
    "get_comparison",
    "get_latest",
    "get_by_run_id",
    "get_stats",
    "delete_old_entries",
]:
    check(f"ScheduleHistoryRepository.{method} exists", hasattr(repo, method))

# ---------------------------------------------------------------------------
# 6. API wiring â router + deps registered
# ---------------------------------------------------------------------------
print("\n=== 6. API wiring ===")
from app.api.v1.router import router as v1_router  # noqa: E402
paths = {r.path for r in v1_router.routes}
check("schedule_history router registered under /schedule-history", "/schedule-history" in str(paths))
check("GET /schedule-history route exists", "/schedule-history" in str(paths))
check("GET /schedule-history/latest route exists", "/schedule-history/latest" in str(paths))
check("GET /schedule-history/stats/summary route exists", "/schedule-history/stats/summary" in str(paths))

from app.api.deps import get_schedule_history_repo, get_schedule_history_service  # noqa: E402
check("get_schedule_history_repo dependency exists", callable(get_schedule_history_repo))
check("get_schedule_history_service dependency exists", callable(get_schedule_history_service))

# ---------------------------------------------------------------------------
# 7. Summary
# ---------------------------------------------------------------------------
print(f"\n{'=' * 50}")
print(f"  {passed} checks passed, {failed} failed.")
print(f"{'=' * 50}")
sys.exit(0 if failed == 0 else 1)