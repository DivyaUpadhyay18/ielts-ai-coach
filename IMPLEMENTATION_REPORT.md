# Diagnostic Engine Integration — Implementation Report

## Project
**ielts-ai-coach** — IELTS AI Coach diagnostic test engine & downstream integrations.

## Status
**COMPLETE** — All 39 tests pass. TypeScript compiles cleanly. Python syntax verified.

---

## What the Diagnostic Engine Does

The Diagnostic Test Framework is a **deterministic (NO AI)** system that assesses a user's current IELTS level across **six skill domains**:

| Section | Type | Marking | Band Formula |
|---------|------|---------|-------------|
| **Reading** | Objective | Right/wrong | `accuracy → band: 3.0 + (accuracy/100) × 6.0, rounded to 0.5` |
| **Listening** | Objective | Right/wrong | Same as Reading |
| **Vocabulary** | Objective | Right/wrong | Same as Reading |
| **Grammar** | Objective | Right/wrong | Same as Reading |
| **Writing** | Subjective | Rubric (0–9) | Average of rubric self-scores, rounded to 0.5 (default 5.5 if no input) |
| **Speaking** | Subjective | Rubric (0–9) | Same as Writing |

**Overall Band** = mean of all 6 section bands, rounded to nearest 0.5 (IELTS convention), clamped to [0, 9].

---

## Downstream Integrations

All integrations use `DiagnosticRoadmapService.resolve_profile()` to pull **diagnostic-first signals** — the user's latest completed diagnostic results override profile defaults.

### 1. Study Plan Generator
- **File**: `backend/app/services/study_plan_generator.py`
- **Method**: `generate_from_diagnostic(user_id, data)`
- **API**: `POST /api/v1/study-plans/generate-from-diagnostic`
- **Flow**: Diagnostic `overall_band` becomes `start_band`, `weakest_skills` become focus areas. Phase weights: Foundation 30% / Skill Building 30% / Advanced 20% / Mock Tests 15% / Final Revision 5%. Archives existing plan, creates new version.

### 2. Adaptive Scheduler
- **File**: `backend/app/services/adaptive_scheduler.py`
- **Flow**: Reads study plan days → generates daily tasks → rebalances based on streak, XP, and completion history. After diagnostic plan generation, the frontend calls `schedulerService.run("app_open")` to trigger rebalancing.

### 3. Mission Engine (Daily Missions)
- **File**: `backend/app/api/v1/daily_missions.py`
- **Flow**: Daily missions are generated for 6 skills (reading, listening, writing, speaking, vocabulary, grammar). Completed missions log XP + minutes into progress tracking. Missions auto-generate for tomorrow when today is 100% complete.

### 4. Resource Recommendation Engine
- **File**: `backend/app/services/recommendation_engine_service.py`
- **API**: `GET /api/v1/recommendations`
- **Flow**: Uses diagnostic `weakest_skills`, `current_band`, `target_band`, and `remaining_days` to rank resources. Ranking algorithm: skill_match (30%) + band_fit (25%) + difficulty_match (20%) + official (10%) + free (5%) + rating (5%) + popularity (5%).

### 5. Dashboard
- **File**: `backend/app/api/v1/dashboard.py`
- **API**: `GET /api/v1/dashboard`
- **Flow**: Dashboard overview calls `resolve_profile()` to display diagnostic-derived current_band, target_band, weakest/strongest skills, and focus areas.

### 6. Progress Tracking
- **File**: `backend/app/api/v1/progress_tracking.py`
- **Flow**: Mission completions feed into the progress-tracking ledger (`source_type=mission`). Dashboard reads daily progress percentage, XP, and streak data.

### 7. Band Prediction
- **File**: `backend/app/services/prediction_engine.py`
- **API**: `GET /api/v1/prediction`
- **Flow**: Uses diagnostic `current_band` and `target_band` to compute `estimated_band`, `ready_for_exam` probability, and risk level. Confidence intervals based on skill dispersion.

---

## Frontend Integration Changes

### `frontend/src/services/api.ts`
Added two new services:

**`studyPlanService`**:
- `generate(data)` — POST `/study-plans/generate`
- `generateFromDiagnostic(data)` — POST `/study-plans/generate-from-diagnostic`
- `getPlanDays(planId, params)` — GET `/study-plans/{id}/days`
- `getActivePlan()` — GET `/study-plans/active`
- `listPlans()` — GET `/study-plans`

**`recommendationService`**:
- `getRecommendations(params)` — GET `/recommendations`
- `getHistory(params)` — GET `/recommendations/history`
- `track(data)` — POST `/recommendations/track`
- `getStats()` — GET `/recommendations/stats`

### `frontend/src/types/index.ts`
Added types:
- `StudyPlanGenerateRequest`, `DiagnosticStudyPlanRequest`
- `GeneratedTask`, `GeneratedDay`, `PhaseBreakdown`
- `StudyPlanGenerateResponse`
- `RecommendedResource`, `RecommendationItem`, `RecommendationResponse`

### `frontend/src/app/diagnostic/result/page.tsx`
- **Auto-band estimation**: On report load, automatically calls `bandEstimationService.estimate()` with the diagnostic skill scores → displays an "Band Estimation Engine" card with overall band, confidence meter, skill bands, weakest/strongest skills, and formula documentation.
- **"Generate My Personalized Study Plan" button**: Replaces the static `<Link href="/roadmap">` → calls `studyPlanService.generateFromDiagnostic()` → then triggers `schedulerService.run("app_open")` to rebalance daily missions.
- After generation, the button becomes a link to `/roadmap` showing the generated plan.

### `frontend/src/app/recommendations/page.tsx`
- **Fixed**: Replaced `resourcesService` (which never called any recommendation API) with `recommendationService.getRecommendations()`.
- Displays the user's profile context (current_band, target_band, weakest_skill, remaining_days) from the recommendation response.

---

## Test Suite

**File**: `backend/tests/test_diagnostic_roadmap_engine.py` (39 tests)
**File**: `backend/tests/conftest.py` (Supabase mock for test isolation)

### Test Categories

| Category | Tests | Coverage |
|----------|-------|----------|
| Band Estimation Engine | 9 | Overall band formula, confidence calculation, weakest/strongest sorting, 0.5 rounding, explanations, formula docs |
| Diagnostic Scoring | 14 | Accuracy→band conversion, band clamping, rounding, answer checking, insights derivation, focus areas, weekly hours, exam timeline |
| Diagnostic Roadmap Service | 11 | Skill band normalization (list/dict), weakest/strongest derivation, target band resolution, profile priority (diagnostic > profile > default), focus areas, key completeness |
| Diagnostic Sections | 3 | All 6 sections present, section ordering, objective vs subjective classification |

---

## Verification Results

```
TypeScript (npx tsc --noEmit):      ✓ 0 errors
Python (py_compile):                ✓ All files pass
Frontend Build (npx next build):   ✓ Compiled successfully
  (Note: Pre-existing ESLint errors in estimation/learn/resources/suggest pages — not modified)
Test Suite (pytest):                ✓ 39 passed in 0.62s
```

---

## Files Modified

### Created:
- `backend/tests/test_diagnostic_roadmap_engine.py` — 39-test comprehensive suite
- `backend/tests/conftest.py` — Test configuration with Supabase mock

### Modified (frontend):
- `frontend/src/types/index.ts` — Added study plan + recommendation types
- `frontend/src/services/api.ts` — Added studyPlanService + recommendationService
- `frontend/src/app/diagnostic/result/page.tsx` — Wired Band Estimation + Study Plan + Scheduler
- `frontend/src/app/recommendations/page.tsx` — Fixed to call recommendation API

### Pre-existing (no changes needed — backend already fully integrated):
- `backend/app/services/diagnostic_service.py`
- `backend/app/services/band_estimation_service.py`
- `backend/app/services/diagnostic_roadmap_service.py`
- `backend/app/services/study_plan_generator.py`
- `backend/app/services/adaptive_scheduler.py`
- `backend/app/services/prediction_engine.py`
- `backend/app/services/recommendation_engine_service.py`
- `backend/app/api/v1/band_estimation.py`
- `backend/app/api/v1/study_plans.py`
- `backend/app/api/v1/recommendation_engine.py`
- `backend/app/api/v1/dashboard.py`
- `backend/app/api/deps.py`
