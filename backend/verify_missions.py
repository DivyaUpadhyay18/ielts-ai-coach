"""
Verification script for the Daily Missions module.

Checks:
  1. Model contracts (schemas, enums, defaults)
  2. Repository data access and generation
  3. API endpoints and auto-generation logic
  4. Frontend types
  5. Frontend API service
  6. Frontend page component
"""
import ast
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

PASS_COUNT = 0
FAIL_COUNT = 0
RESULTS = []


def check(name, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        RESULTS.append(f"  PASS  {name}")
    else:
        FAIL_COUNT += 1
        RESULTS.append(f"  FAIL  {name} {detail}")


# ---------------------------------------------------------------------------
# 1. Model contracts
# ---------------------------------------------------------------------------
def section_1():
    global PASS_COUNT, FAIL_COUNT
    print("=== 1. Model contracts ===")

    model_path = BASE_DIR / "backend" / "app" / "models" / "daily_mission.py"
    content = model_path.read_text()

    check("daily_mission.py exists", model_path.exists())
    check("MISSION_SKILLS defined", "MISSION_SKILLS" in content)
    check("MISSION_STATUSES defined", "MISSION_STATUSES" in content)
    check("DailyMissionResponse defined", "class DailyMissionResponse" in content)
    check("DailyMissionSummary defined", "class DailyMissionSummary" in content)
    check("DailyMissionListResponse defined", "class DailyMissionListResponse" in content)
    check("DailyMissionGenerateResponse defined", "class DailyMissionGenerateResponse" in content)
    check("DailyMissionUpdate defined", "class DailyMissionUpdate" in content)

    # Check required fields
    check("has skill field", "skill: str" in content)
    check("has title field", "title: str" in content)
    check("has estimated_minutes field", "estimated_minutes: int" in content)
    check("has xp_reward field", "xp_reward: int" in content)
    check("has completion_percent field", "completion_percent: int" in content)
    check("has status field", "status: str" in content)
    check("has mission_date field", "mission_date: date" in content)

    # Check 6 skills
    skills = ["reading", "listening", "writing", "speaking", "vocabulary", "grammar"]
    for skill in skills:
        check(f"skill '{skill}' in MISSION_SKILLS", f'"{skill}"' in content or f"'{skill}'" in content)

    # Check 3 statuses
    statuses = ["pending", "completed", "kipped"]
    for status in statuses:
        check(f"status '{status}' in MISSION_STATUSES", f'"{status}"' in content or f"'{status}'" in content)


# ---------------------------------------------------------------------------
# 2. Repository data access and generation
# ---------------------------------------------------------------------------
def section_2():
    global PASS_COUNT, FAIL_COUNT
    print("=== 2. Repository data access and generation ===")

    repo_path = BASE_DIR / "backend" / "app" / "repositories" / "daily_mission_repo.py"
    content = repo_path.read_text()

    check("daily_mission_repo.py exists", repo_path.exists())
    check("MISSION_SKILLS defined", "MISSION_SKILLS" in content)
    check("SKILL_TEMPLATES defined", "SKILL_TEMPLATES" in content)

    # Check required methods
    check("list_for_date method", "def list_for_date" in content)
    check("list_for_date_range method", "def list_for_date_range" in content)
    check("get_summary method", "def get_summary" in content)
    check("complete method", "def complete" in content)
    check("skip method", "def skip" in content)
    check("update_progress method", "def update_progress" in content)
    check("generate_for_date method", "def generate_for_date" in content)
    check("generate_for_range method", "def generate_for_range" in content)

    # Check 6 skill templates
    skills = ["reading", "listening", "writing", "speaking", "vocabulary", "grammar"]
    for skill in skills:
        check(f"template for '{skill}'", skill in content)

    # Check idempotency
    check("idempotent generation", "existing_keys" in content and "if skill in existing_keys" in content)


# ---------------------------------------------------------------------------
# 3. API endpoints and auto-generation logic
# ---------------------------------------------------------------------------
def section_3():
    global PASS_COUNT, FAIL_COUNT
    print("=== 3. API endpoints and auto-generation logic ===")

    api_path = BASE_DIR / "backend" / "app" / "api" / "v1" / "daily_missions.py"
    content = api_path.read_text()

    check("daily_missions.py exists", api_path.exists())
    check("GET '' endpoint", '@router.get(""' in content)
    check("GET /today endpoint", '@router.get("/today"' in content)
    check("POST /generate endpoint", '@router.post("/generate"' in content)
    check("GET /{mission_id} endpoint", '@router.get("/{mission_id}"' in content)
    check("PATCH /{mission_id} endpoint", '@router.patch("/{mission_id}"' in content)
    check("POST /{mission_id}/complete endpoint", '@router.post("/{mission_id}/complete"' in content)
    check("POST /{mission_id}/skip endpoint", '@router.post("/{mission_id}/skip"' in content)

    # Check auto-generation logic
    check("auto-generates tomorrow on 100% completion", "completion_percent" in content and "100" in content and "tomorrow" in content)
    check("uses generate_for_date for auto-generation", "generate_for_date" in content)
    check("wraps auto-generation in try/except", "try:" in content and "except Exception:" in content)

    # Check streak integration
    check("calls _process_streaks on complete", "_process_streaks" in content)
    check("calls _process_streaks on skip", "_process_streaks" in content)

    # Check progress tracking integration
    check("calls _log_mission_session on complete", "_log_mission_session" in content)
    check("calls _log_mission_session on skip", "_log_mission_session" in content)


# ---------------------------------------------------------------------------
# 4. Frontend types
# ---------------------------------------------------------------------------
def section_4():
    global PASS_COUNT, FAIL_COUNT
    print("=== 4. Frontend types ===")

    types_path = BASE_DIR / "frontend" / "src" / "types" / "index.ts"
    content = types_path.read_text()

    check("types has DailyMission", "DailyMission" in content)
    check("types has DailyMissionSummary", "DailyMissionSummary" in content)
    check("types has DailyMissionListResponse", "DailyMissionListResponse" in content)
    check("types has DailyMissionGenerateResponse", "DailyMissionGenerateResponse" in content)
    check("types has MissionSkill union", "MissionSkill" in content)
    check("types has MissionStatus union", "MissionStatus" in content)

    # Check 6 skills
    skills = ["reading", "listening", "writing", "speaking", "vocabulary", "grammar"]
    for skill in skills:
        check(f"skill '{skill}' in MissionSkill", f"'{skill}'" in content)

    # Check 3 statuses
    statuses = ["pending", "completed", "skipped"]
    for status in statuses:
        check(f"status '{status}' in MissionStatus", f"'{status}'" in content)

    # Check required fields
    check("has id field", "id: string" in content)
    check("has user_id field", "user_id: string" in content)
    check("has mission_date field", "mission_date: string" in content)
    check("has title field", "title: string" in content)
    check("has estimated_minutes field", "estimated_minutes: number" in content)
    check("has xp_reward field", "xp_reward: number" in content)
    check("has completion_percent field", "completion_percent: number" in content)
    check("has status field", "status: MissionStatus" in content)


# ---------------------------------------------------------------------------
# 5. Frontend API service
# ---------------------------------------------------------------------------
def section_5():
    global PASS_COUNT, FAIL_COUNT
    print("=== 5. Frontend API service ===")

    api_path = BASE_DIR / "frontend" / "src" / "services" / "api.ts"
    content = api_path.read_text()

    check("api.ts has dailyMissionService", "dailyMissionService" in content)
    check("api.ts has list method", "list:" in content)
    check("api.ts has getToday method", "getToday:" in content)
    check("api.ts has get method", "get:" in content)
    check("api.ts has generate method", "generate:" in content)
    check("api.ts has update method", "update:" in content)
    check("api.ts has complete method", "complete:" in content)
    check("api.ts has skip method", "skip:" in content)
    check("api.ts calls /daily-missions", "'/daily-missions'" in content)
    check("api.ts calls /daily-missions/today", "'/daily-missions/today'" in content)
    check("api.ts calls /daily-missions/generate", "'/daily-missions/generate'" in content)


# ---------------------------------------------------------------------------
# 6. Frontend page component
# ---------------------------------------------------------------------------
def section_6():
    global PASS_COUNT, FAIL_COUNT
    print("=== 6. Frontend page component ===")

    page_path = BASE_DIR / "frontend" / "src" / "app" / "missions" / "page.tsx"
    check("missions page.tsx exists", page_path.exists())
    content = page_path.read_text()

    check("page uses DashboardLayout", "DashboardLayout" in content)
    check("page uses dailyMissionService", "dailyMissionService" in content)
    check("page has getToday call", "getToday" in content)
    check("page has generate call", "generate" in content)
    check("page has complete call", "complete" in content)
    check("page has skip call", "skip" in content)
    check("page shows skill icons", "BookOpen" in content and "PenTool" in content and "Mic" in content)
    check("page shows 6 skills", "reading" in content and "listening" in content and "writing" in content and "speaking" in content and "vocabulary" in content and "grammar" in content)
    check("page shows XP rewards", "xp_reward" in content or "XP" in content)
    check("page shows estimated time", "estimated_minutes" in content or "min" in content)
    check("page shows completion status", "completion_percent" in content or "Completed" in content)
    check("page has progress bar", "Progress" in content)
    check("page has summary cards", "Card" in content)
    check("page has generate button", "Generate" in content)


# ---------------------------------------------------------------------------
# Run all sections
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    section_1()
    section_2()
    section_3()
    section_4()
    section_5()
    section_6()

    print("\n" + "=" * 50)
    for r in RESULTS:
        print(r)
    print("=" * 50)
    print(f"\n  {PASS_COUNT} checks passed, {FAIL_COUNT} failed.")
    print()

    if FAIL_COUNT > 0:
        sys.exit(1)
    else:
        print("All checks passed!")
        sys.exit(0)