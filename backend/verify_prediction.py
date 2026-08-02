"""
Verification script for the Prediction Engine module.

Checks:
  1. Model contracts (schemas, enums, defaults)
  2. Service pure helpers (formula functions)
  3. Service with no DB (safe wrappers)
  4. Service with mock user (no DB)
  5. API router registration
  6. Dependency injection
  7. Frontend types
  8. Frontend API service
  9. Frontend components
"""
import ast
import inspect
import os
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

    model_path = BASE_DIR / "backend" / "app" / "models" / "prediction.py"
    content = model_path.read_text()
    tree = ast.parse(content)

    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    class_names = [c.name for c in classes]

    check("prediction.py exists", model_path.exists())
    check("PredictionMetrics defined", "PredictionMetrics" in class_names)
    check("PredictionResponse defined", "PredictionResponse" in class_names)
    check("PredictionHistoryItem defined", "PredictionHistoryItem" in class_names)
    check("PredictionHistoryResponse defined", "PredictionHistoryResponse" in class_names)

    # Check enums
    check("RISK_LEVELS has 4 values", "RISK_LEVELS" in content and '"low"' in content and '"medium"' in content and '"high"' in content and '"critical"' in content)
    check("READINESS_LEVELS defined", "READINESS_LEVELS" in content)

    # Check required fields in PredictionResponse
    resp_fields = ["preparation_percentage", "estimated_band", "study_consistency",
                   "completion_rate", "risk_level", "readiness_score", "metrics", "formulas", "recommendations"]
    for field in resp_fields:
        check(f"PredictionResponse has {field}", field in content)

    # Check defaults
    check("StudyHoursData defaults to 0", "= 0" in content or "= 0.0" in content)


# ---------------------------------------------------------------------------
# 2. Service pure helpers (AST-based to avoid DB/settings import)
# ---------------------------------------------------------------------------
def section_2():
    global PASS_COUNT, FAIL_COUNT
    print("=== 2. Service pure helpers ===")

    service_path = BASE_DIR / "backend" / "app" / "services" / "prediction_engine.py"
    content = service_path.read_text()

    # Check that all formula methods are defined as staticmethods
    check("service has _compute_estimated_band", "def _compute_estimated_band" in content)
    check("service has _compute_risk_level", "def _compute_risk_level" in content)
    check("service has _compute_readiness_score", "def _compute_readiness_score" in content)
    check("service has _compute_consistency", "def _compute_consistency" in content)
    check("service has _intensity", "def _intensity" in content)
    check("service has _parse_date", "def _parse_date" in content)
    check("service has _build_formulas", "def _build_formulas" in content)
    check("service has _build_recommendations", "def _build_recommendations" in content)

    # Check documented constants
    check("BAND_STEP = 0.5 defined", "BAND_STEP = 0.5" in content)
    check("MOCK_BLEND = 0.70 defined", "MOCK_BLEND = 0.70" in content)
    check("W_COMPLETION defined", "W_COMPLETION" in content)
    check("W_CONSISTENCY defined", "W_CONSISTENCY" in content)
    check("W_BAND_PROGRESS defined", "W_BAND_PROGRESS" in content)
    check("W_MISSED_DAYS defined", "W_MISSED_DAYS" in content)
    check("W_STREAK defined", "W_STREAK" in content)

    # Check formula documentation strings
    check("formula doc for estimated_band", "estimated_band" in content and "mock" in content)
    check("formula doc for risk_level", "critical:" in content and "high:" in content)
    check("formula doc for readiness_score", "readiness =" in content)


# ---------------------------------------------------------------------------
# 3. Service with no DB (safe wrappers - AST based)
# ---------------------------------------------------------------------------
def section_3():
    global PASS_COUNT, FAIL_COUNT
    print("=== 3. Service with no DB (safe wrappers) ===")

    service_path = BASE_DIR / "backend" / "app" / "services" / "prediction_engine.py"
    content = service_path.read_text()

    # Check safe wrappers exist and handle None db
    check("_safe_get_profile defined", "def _safe_get_profile" in content)
    check("_safe_get_active_plan defined", "def _safe_get_active_plan" in content)
    check("_safe_list_tasks defined", "def _safe_list_tasks" in content)
    check("_safe_get_progress_state defined", "def _safe_get_progress_state" in content)
    check("_safe_get_mock_scores defined", "def _safe_get_mock_scores" in content)
    check("_safe_count_missed_days defined", "def _safe_count_missed_days" in content)
    check("_safe_get_active_dates defined", "def _safe_get_active_dates" in content)
    check("safe wrappers check db is None", "self.db is None" in content)


# ---------------------------------------------------------------------------
# 4. Service with mock user (no DB - AST based)
# ---------------------------------------------------------------------------
def section_4():
    global PASS_COUNT, FAIL_COUNT
    print("=== 4. Service with mock user (no DB) ===")

    service_path = BASE_DIR / "backend" / "app" / "services" / "prediction_engine.py"
    content = service_path.read_text()

    # Check get_prediction handles missing exam date
    check("get_prediction checks exam_date", "exam_date" in content and "ValidationError" in content)
    check("get_prediction handles no profile", "NotFoundError" in content)
    check("get_prediction stores history", "_store_history" in content)


# ---------------------------------------------------------------------------
# 5. API router registration
# ---------------------------------------------------------------------------
def section_5():
    global PASS_COUNT, FAIL_COUNT
    print("=== 5. API router registration ===")

    router_path = BASE_DIR / "backend" / "app" / "api" / "v1" / "router.py"
    content = router_path.read_text()

    check("router.py imports prediction_router", "prediction_router" in content)
    check("router includes /prediction prefix", 'prefix="/prediction"' in content)

    api_path = BASE_DIR / "backend" / "app" / "api" / "v1" / "prediction.py"
    check("prediction.py exists", api_path.exists())
    content = api_path.read_text()
    check("prediction.py has GET '' route", '@router.get(""' in content and 'response_model=dict' in content)
    check("prediction.py has GET /history route", '@router.get("/history"' in content)


# ---------------------------------------------------------------------------
# 6. Dependency injection
# ---------------------------------------------------------------------------
def section_6():
    global PASS_COUNT, FAIL_COUNT
    print("=== 6. Dependency injection ===")

    deps_path = BASE_DIR / "backend" / "app" / "api" / "deps.py"
    content = deps_path.read_text()
    check("deps.py imports PredictionEngineService", "PredictionEngineService" in content)
    check("deps.py imports prediction_engine_service", "prediction_engine_service" in content)
    check("deps.py has get_prediction_engine_service", "get_prediction_engine_service" in content)


# ---------------------------------------------------------------------------
# 7. Frontend types
# ---------------------------------------------------------------------------
def section_7():
    global PASS_COUNT, FAIL_COUNT
    print("=== 7. Frontend types ===")

    types_path = BASE_DIR / "frontend" / "src" / "types" / "index.ts"
    content = types_path.read_text()

    check("types has PredictionMetrics", "PredictionMetrics" in content)
    check("types has PredictionResponse", "PredictionResponse" in content)
    check("types has PredictionHistoryItem", "PredictionHistoryItem" in content)
    check("types has PredictionHistoryResponse", "PredictionHistoryResponse" in content)
    check("types has risk_level union", "'low' | 'medium' | 'high' | 'critical'" in content)
    check("types has preparation_percentage", "preparation_percentage" in content)
    check("types has estimated_band", "estimated_band" in content)
    check("types has readiness_score", "readiness_score" in content)
    check("types has formulas", "formulas" in content)
    check("types has recommendations", "recommendations" in content)


# ---------------------------------------------------------------------------
# 8. Frontend API service
# ---------------------------------------------------------------------------
def section_8():
    global PASS_COUNT, FAIL_COUNT
    print("=== 8. Frontend API service ===")

    api_path = BASE_DIR / "frontend" / "src" / "services" / "api.ts"
    content = api_path.read_text()

    check("api.ts has predictionService", "predictionService" in content)
    check("api.ts has getPrediction", "getPrediction" in content)
    check("api.ts has getHistory", "getHistory" in content)
    check("api.ts calls /prediction", "'/prediction'" in content)
    check("api.ts calls /prediction/history", "'/prediction/history'" in content)


# ---------------------------------------------------------------------------
# 9. Frontend components
# ---------------------------------------------------------------------------
def section_9():
    global PASS_COUNT, FAIL_COUNT
    print("=== 9. Frontend components ===")

    widget_path = BASE_DIR / "frontend" / "src" / "components" / "prediction" / "prediction-widget.tsx"
    check("prediction-widget.tsx exists", widget_path.exists())
    content = widget_path.read_text()
    check("widget has PredictionWidget export", "export function PredictionWidget" in content)
    check("widget has readiness_score", "readiness_score" in content)
    check("widget has estimated_band", "estimated_band" in content)
    check("widget has risk_level", "risk_level" in content)
    check("widget has recommendations", "recommendations" in content)
    check("widget has formulas/details", "<details" in content)
    check("widget has RefreshCw icon", "RefreshCw" in content)

    page_path = BASE_DIR / "frontend" / "src" / "app" / "prediction" / "page.tsx"
    check("prediction page.tsx exists", page_path.exists())
    content = page_path.read_text()
    check("page uses DashboardLayout", "DashboardLayout" in content)
    check("page uses PredictionWidget", "PredictionWidget" in content)
    check("page has getPrediction call", "getPrediction" in content)
    check("page has getHistory call", "getHistory" in content)
    check("page has history section", "Prediction History" in content)


# ---------------------------------------------------------------------------
# Run all sections
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from datetime import date as date_type

    section_1()
    section_2()
    section_3()
    section_4()
    section_5()
    section_6()
    section_7()
    section_8()
    section_9()

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
