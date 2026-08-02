"""
Standalone verification for the Exam Countdown module.

Stubs the Supabase-backed DB modules so the countdown service's pure logic
and wiring can be exercised without live credentials. Run from backend/:

    python verify_countdown.py
"""
import sys
import types
import os
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Set required env vars before any app imports (config.py needs them).
# ---------------------------------------------------------------------------
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

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
# Import the countdown service, models, and API.
# ---------------------------------------------------------------------------
from app.services.exam_countdown import ExamCountdownService  # noqa: E402
from app.models.countdown import (  # noqa: E402
    ExamCountdownResponse,
    ExamDateUpdateRequest,
    ExamDateUpdateResponse,
    StudyHoursData,
    INTENSITY_LEVELS,
)
from app.core.exceptions import NotFoundError, ValidationError  # noqa: E402

# ---------------------------------------------------------------------------
# Minimal test framework
# ---------------------------------------------------------------------------
_passed = 0
_failed = 0
_failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        msg = f"  FAIL  {name}" + (f" — {detail}" if detail else "")
        print(msg)
        _failures.append(msg)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# ── 1. Model contracts ─────────────────────────────────────────────────
section("1. Model contracts")

check("INTENSITY_LEVELS has 4 values", len(INTENSITY_LEVELS) == 4)
check("INTENSITY_LEVELS includes final", "final" in INTENSITY_LEVELS)

sh = StudyHoursData()
check("StudyHoursData defaults to 0", sh.planned == 0 and sh.completed == 0 and sh.remaining == 0)

ec = ExamCountdownResponse(exam_date="2025-08-15", today="2025-06-02")
check("ExamCountdownResponse has days_remaining", hasattr(ec, "days_remaining"))
check("ExamCountdownResponse has weeks_remaining", hasattr(ec, "weeks_remaining"))
check("ExamCountdownResponse has study_hours", hasattr(ec, "study_hours"))
check("ExamCountdownResponse has completion_percentage", hasattr(ec, "completion_percentage"))
check("ExamCountdownResponse has intensity", hasattr(ec, "intensity"))
check("ExamCountdownResponse has has_active_plan", hasattr(ec, "has_active_plan"))
check("ExamCountdownResponse has study_plan_id", hasattr(ec, "study_plan_id"))
check("ExamCountdownResponse has study_plan_version", hasattr(ec, "study_plan_version"))

req = ExamDateUpdateRequest(exam_date=date(2025, 9, 20))
check("ExamDateUpdateRequest defaults auto_regenerate True", req.auto_regenerate is True)

resp = ExamDateUpdateResponse(exam_date="2025-09-20", message="Updated")
check("ExamDateUpdateResponse defaults regenerated False", resp.regenerated is False)
check("ExamDateUpdateResponse defaults new_study_plan_id None", resp.new_study_plan_id is None)

# ── 2. Service pure helpers ─────────────────────────────────────────────
section("2. Service pure helpers")

check("intensity normal (>60 days)", ExamCountdownService._intensity(61) == "normal")
check("intensity focused (30-60 days)", ExamCountdownService._intensity(45) == "focused")
check("intensity intensive (14-30 days)", ExamCountdownService._intensity(20) == "intensive")
check("intensity final (<14 days)", ExamCountdownService._intensity(10) == "final")
check("intensity final (0 days)", ExamCountdownService._intensity(0) == "final")

check("parse_date accepts date object", ExamCountdownService._parse_date(date(2025, 8, 15)) == date(2025, 8, 15))
check("parse_date accepts iso string", ExamCountdownService._parse_date("2025-08-15") == date(2025, 8, 15))
check("parse_date accepts datetime", ExamCountdownService._parse_date(datetime(2025, 8, 15, 10, 30)) == date(2025, 8, 15))

# ── 3. Service with no DB (safe wrappers) ───────────────────────────────
section("3. Service with no DB (safe wrappers)")

svc = ExamCountdownService(db=None)

check("_safe_get_profile returns None (no db)", svc._safe_get_profile("test-user") is None)
check("_safe_get_active_plan returns None (no db)", svc._safe_get_active_plan("test-user") is None)

try:
    svc.get_countdown("test-user")
    check("get_countdown raises NotFoundError (no db)", False)
except NotFoundError:
    check("get_countdown raises NotFoundError (no db)", True)
except Exception as e:
    check("get_countdown raises NotFoundError (no db)", False, f"got {type(e).__name__}")

# ── 4. Service with mock user (no DB) ───────────────────────────────────
section("4. Service with mock user (no DB)")


class MockExamCountdownService(ExamCountdownService):
    def __init__(self):
        super().__init__(db=None)

    def _safe_get_profile(self, user_id):
        return {
            "id": user_id,
            "exam_date": "2025-08-15",
            "daily_minutes_budget": 120,
            "current_band": 6.0,
            "target_band": 7.5,
            "module": "academic",
            "preferences": {
                "weakest_skills": ["writing"],
                "strongest_skills": ["reading"],
            },
        }

    def _safe_get_active_plan(self, user_id):
        return {"id": "plan-1", "version": 1, "status": "active"}

    def _compute_study_hours(self, user_id, study_plan_id):
        return (600, 240)  # 10 hrs planned, 4 hrs completed


mock_svc = MockExamCountdownService()
run_date = date(2025, 6, 2)
result = mock_svc.get_countdown("test-user", run_date=run_date)

check("countdown has exam_date", result["exam_date"] == "2025-08-15")
check("countdown has today", result["today"] == "2025-06-02")
check("countdown days_remaining correct", result["days_remaining"] == 74)
check("countdown weeks_remaining correct", result["weeks_remaining"] == 11)
check("countdown study_hours.planned", result["study_hours"]["planned"] == 10.0)
check("countdown study_hours.completed", result["study_hours"]["completed"] == 4.0)
check("countdown study_hours.remaining", result["study_hours"]["remaining"] == 6.0)
check("countdown completion_percentage", result["completion_percentage"] == 40.0)
check("countdown intensity normal (74 days > 60)", result["intensity"] == "normal")
check("countdown has_active_plan True", result["has_active_plan"] is True)
check("countdown study_plan_id", result["study_plan_id"] == "plan-1")
check("countdown study_plan_version", result["study_plan_version"] == 1)


class MockNoPlanService(MockExamCountdownService):
    def _safe_get_active_plan(self, user_id):
        return None


no_plan_svc = MockNoPlanService()
result2 = no_plan_svc.get_countdown("test-user", run_date=run_date)
check("no-plan has_active_plan False", result2["has_active_plan"] is False)
check("no-plan study_hours all zero", result2["study_hours"]["planned"] == 0.0)
check("no-plan completion 0", result2["completion_percentage"] == 0.0)


class MockNoExamService(ExamCountdownService):
    def __init__(self):
        super().__init__(db=None)

    def _safe_get_profile(self, user_id):
        return {"id": user_id, "exam_date": None}


no_exam_svc = MockNoExamService()
try:
    no_exam_svc.get_countdown("test-user", run_date=run_date)
    check("no-exam raises ValidationError", False)
except ValidationError:
    check("no-exam raises ValidationError", True)
except Exception as e:
    check("no-exam raises ValidationError", False, f"got {type(e).__name__}")


class MockPastExamService(ExamCountdownService):
    def __init__(self):
        super().__init__(db=None)

    def _safe_get_profile(self, user_id):
        return {"id": user_id, "exam_date": "2025-01-01"}


past_svc = MockPastExamService()
result3 = past_svc.get_countdown("test-user", run_date=run_date)
check("past-exam days_remaining 0", result3["days_remaining"] == 0)
check("past-exam intensity final", result3["intensity"] == "final")

# ── 5. update_exam_date (no DB, no regeneration) ────────────────────────
section("5. update_exam_date (no DB, no regeneration)")


class FakeUserRepo:
    def update_goals(self, user_id, data):
        return {"id": user_id, **data}


class MockUpdateService(ExamCountdownService):
    def __init__(self):
        super().__init__(db=None)
        self.user_repo = FakeUserRepo()

    def _safe_get_profile(self, user_id):
        return {
            "id": user_id,
            "exam_date": "2025-08-15",
            "daily_minutes_budget": 120,
            "current_band": 6.0,
            "target_band": 7.5,
            "module": "academic",
            "preferences": {},
        }

    def _safe_get_active_plan(self, user_id):
        return None

    def _regenerate_plan_for_new_exam(self, user_id, user, new_exam_date):
        return None


future_date = date.today() + timedelta(days=30)
upd_svc = MockUpdateService()
result4 = upd_svc.update_exam_date("test-user", future_date, auto_regenerate=True)
check("update returns new exam_date", result4["exam_date"] == future_date.isoformat())
check("update returns previous_exam_date", result4["previous_exam_date"] == "2025-08-15")
check("update regenerated False (no plan)", result4["regenerated"] is False)
check("update message", "Exam date updated." in result4["message"])

try:
    upd_svc.update_exam_date("test-user", date(2020, 1, 1))
    check("update past date raises ValidationError", False)
except ValidationError:
    check("update past date raises ValidationError", True)
except Exception as e:
    check("update past date raises ValidationError", False, f"got {type(e).__name__}")

# ── 6. API router registration ───────────────────────────────────────────
section("6. API router registration")

from app.api.v1.router import router as v1_router  # noqa: E402

routes = [r.path for r in v1_router.routes]
check("countdown GET route registered", any("/countdown" in r for r in routes))
check("countdown POST exam-date route registered", any("/countdown/exam-date" in r for r in routes))

from app.api.v1.countdown import router as countdown_router  # noqa: E402
countdown_routes = [r.path for r in countdown_router.routes]
check("countdown router has GET ''", "" in countdown_routes)
check("countdown router has POST '/exam-date'", "/exam-date" in countdown_routes)

# ── 7. Dependency injection ─────────────────────────────────────────────
section("7. Dependency injection")

from app.api.deps import get_exam_countdown_service  # noqa: E402
check("get_exam_countdown_service exists", callable(get_exam_countdown_service))

# ── 8. Frontend types ───────────────────────────────────────────────────
section("8. Frontend types")

frontend_types_path = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "src", "types", "index.ts"
)
with open(frontend_types_path, "r") as f:
    types_content = f.read()

check("types has ExamCountdown", "ExamCountdown" in types_content)
check("types has StudyHoursData", "StudyHoursData" in types_content)
check("types has ExamDateUpdateRequest", "ExamDateUpdateRequest" in types_content)
check("types has ExamDateUpdateResponse", "ExamDateUpdateResponse" in types_content)
check("types has IntensityLevel", "IntensityLevel" in types_content)

# ── 9. Frontend API service ─────────────────────────────────────────────
section("9. Frontend API service")

frontend_api_path = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "src", "services", "api.ts"
)
with open(frontend_api_path, "r") as f:
    api_content = f.read()

check("api.ts has countdownService", "countdownService" in api_content)
check("api.ts has getCountdown", "getCountdown" in api_content)
check("api.ts has updateExamDate", "updateExamDate" in api_content)
check("api.ts calls /countdown", "/countdown" in api_content)
check("api.ts calls /countdown/exam-date", "/countdown/exam-date" in api_content)

# ── 10. Frontend components ─────────────────────────────────────────────
section("10. Frontend components")

widget_path = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "src", "components", "countdown",
    "countdown-widget.tsx",
)
page_path = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "src", "app", "countdown", "page.tsx"
)

check("countdown-widget.tsx exists", os.path.exists(widget_path))
check("countdown page.tsx exists", os.path.exists(page_path))

with open(widget_path, "r") as f:
    widget_content = f.read()
check("widget has ProgressRing", "ProgressRing" in widget_content)
check("widget has progress ring SVG", "<svg" in widget_content)
check("widget has strokeDasharray", "strokeDasharray" in widget_content)
check("widget has days_remaining", "days_remaining" in widget_content)
check("widget has weeks_remaining", "weeks_remaining" in widget_content)
check("widget has completion_percentage", "completion_percentage" in widget_content)
check("widget has study_hours", "study_hours" in widget_content)
check("widget has intensity", "intensity" in widget_content)

with open(page_path, "r") as f:
    page_content = f.read()
check("page uses DashboardLayout", "DashboardLayout" in page_content)
check("page uses CountdownWidget", "CountdownWidget" in page_content)
check("page has updateExamDate call", "updateExamDate" in page_content)
check("page has Modal for exam date change", "Modal" in page_content)

# ── Summary ─────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
print(f"  { _passed} checks passed, { _failed} failed.")
print("=" * 50)

if _failed > 0:
    print("\nFailures:")
    for f in _failures:
        print(f)
    sys.exit(1)
else:
    print("\nAll checks passed!")
    sys.exit(0)
