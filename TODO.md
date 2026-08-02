# Adaptive Scheduler — Task Tracker

## ✅ Approved Plan

> Core feature. Runs at midnight or on app open. Checks yesterday's
> completions, missed tasks, days-remaining, completion rate. If misses:
> moves unfinished tasks forward, recalcs workload, protects revision weeks,
> keeps mocks before exam day, never exceeds daily budget by >20% (unless
> necessary), shows exactly what changed & why. Every update stored in DB
> history. Clean architecture. No AI. Production-ready.

## 🔲 Steps

### Phase 1 — Database & Models
- [x] Create `backend/app/db/migrations/009_adaptive_scheduler.sql` (schedule_runs, schedule_adjustments, tasks+source_task_id/missed_at, indexes, RLS, triggers)
- [x] Create `backend/app/models/scheduler.py` (run request/response schemas, metrics, adjustments, explain response)

### Phase 2 — Repository & Service
- [x] Create `backend/app/repositories/scheduler_repo.py` (create_run, list_runs, get_latest_run, add_adjustments, get_run_adjustments)
- [x] Extend `backend/app/repositories/task_repo.py` (list_pending_before, mark_missed, reschedule/clone-with-lineage, list_mock_tasks)
- [x] Create `backend/app/services/adaptive_scheduler.py` (deterministic rollover service)
- [x] Update `backend/app/services/__init__.py` (lazy export)

### Phase 3 — API & Wiring
- [x] Create `backend/app/api/v1/scheduler.py` (POST /run, GET /latest, GET /runs, GET /explain)
- [x] Update `backend/app/api/deps.py` (+get_scheduler_service, +get_scheduler_repo)
- [x] Update `backend/app/api/v1/router.py` (register /scheduler)
- [x] Update `backend/app/main.py` (root endpoint map)

### Phase 4 — Frontend
- [ ] Update `frontend/src/types/index.ts` (scheduler types)
- [ ] Update `frontend/src/services/api.ts` (schedulerService)
- [ ] Update `frontend/src/app/dashboard/page.tsx` ("What changed today" panel)

### Phase 5 — Verification
- [ ] `python -m py_compile` on changed/new files
- [ ] `backend/verify_scheduler.py` — standalone checks (stub DB)


### Schedule History Feature (NEW)
- [x] Create backend/app/models/schedule_history.py (Pydantic schemas)
- [x] Create backend/app/repositories/schedule_history_repo.py (data access)
- [x] Create backend/app/services/schedule_history_service.py (business logic)
- [x] Create backend/app/api/v1/schedule_history.py (REST endpoints)
- [x] Create backend/app/db/migrations/011_schedule_history.sql (DB schema)
- [x] Create frontend/src/app/schedule-history/page.tsx (history page)
- [x] Create frontend/src/components/scheduler/scheduler-changes.tsx (changes component)
- [x] Update frontend/src/types/index.ts (ScheduleHistory types)
- [x] Update frontend/src/services/api.ts (scheduleHistoryService)
- [x] Update frontend/src/components/shared/sidebar.tsx (Schedule History link)
- [x] Update backend/app/api/deps.py (+get_schedule_history_repo, +get_schedule_history_service)
- [x] Update backend/app/api/v1/router.py (register /schedule-history)
- [x] Update backend/app/main.py (root endpoint map)
- [x] Fix previous/new schedule snapshot capture in adaptive_scheduler.py (capture before changes)
- [x] Add schedule history logging to exam_countdown.py (exam date updates)
- [x] Add schedule history logging to study_plan_generator.py (plan regeneration)
- [x] Implement POST /internal/create endpoint in schedule_history.py
- [x] Create backend/verify_schedule_history.py (verification script)
- [x] Update SCHEDULE_HISTORY.md (reflect actual implementation)

### Resource Management System (NEW)
- [x] Create backend/app/db/migrations/012_resources.sql (resources table with full schema)
- [x] Create backend/app/models/resource_management.py (Pydantic schemas for CRUD)
- [x] Create backend/app/repositories/resource_management_repo.py (data access layer)
- [x] Create backend/app/services/resource_management_service.py (business logic)
- [x] Create backend/app/api/v1/resource_management.py (REST CRUD endpoints)
- [x] Update backend/app/api/deps.py (+get_resource_management_repo)
- [x] Update backend/app/api/v1/router.py (register /resource-management)
- [x] Update backend/app/main.py (root endpoint map)
- [x] Update frontend/src/types/index.ts (ResourceItem, ResourceType, etc.)
- [x] Update frontend/src/services/api.ts (resourcesService)
- [x] Update frontend/src/app/resources/page.tsx (resource management page)
- [x] Update frontend/src/components/shared/sidebar.tsx (Resource Library link)


### Intelligent Recommendation Engine (NEW)
- [x] Create backend/app/db/migrations/013_recommendation_engine.sql (recommendation_logs, recommendation_cache, recommendation_resource_view)
- [x] Create backend/app/models/recommendation.py (Pydantic schemas for recommendations)
- [x] Create backend/app/repositories/recommendation_repo.py (data access for user context, completed resources, performance)
- [x] Create backend/app/services/recommendation_engine_service.py (rule-based ranking algorithm, NO AI)
- [x] Create backend/app/api/v1/recommendation_engine.py (REST API endpoints)
- [x] Update backend/app/api/v1/router.py (register /recommendations)
- [x] Update backend/app/main.py (root endpoint map)
- [x] Create frontend/src/app/recommendations/page.tsx (recommendations dashboard)
- [x] Update frontend/src/components/shared/sidebar.tsx (Recommendations link)
- [x] Create RECOMMENDATION_ENGINE.md (ranking algorithm documentation)
- [x] Create backend/verify_recommendation_engine.py (verification script - 133 checks)
- [x] Run verification: all 133 checks passed
- [x] Run frontend build: all 28 routes compiled successfully
- [x] Run backend py_compile: all files pass

### Learning Session Mode (NEW)
- [x] Create backend/app/db/migrations/014_learning_session.sql (learning_session_notes, learning_session_bookmarks, learning_session_state tables with RLS, indexes, triggers)
- [x] Create backend/app/models/learning_session.py (Pydantic schemas: SessionStartResponse, SessionNote, SessionBookmark, SessionCompleteRequest/Response, SessionHistoryResponse)
- [x] Create backend/app/repositories/learning_session_repo.py (session state CRUD, notes, bookmarks, previous mistakes, related resources, session history)
- [x] Create backend/app/services/learning_session_service.py (start_session, update progress, add note/bookmark, complete_session with XP/streaks/dashboard updates)
- [x] Create backend/app/api/v1/learning_session.py (REST endpoints: POST /start, POST /{mission_id}/progress, POST /{mission_id}/notes, POST /{mission_id}/bookmarks, POST /{mission_id}/complete, GET /today, GET /history)
- [x] Update backend/app/api/v1/router.py (register /learning-sessions routes)
- [x] Update backend/app/main.py (root endpoint map)
- [x] Update frontend/src/types/index.ts (SessionStartResponse, SessionNote, SessionBookmark, SessionCompleteResponse, etc.)
- [x] Update frontend/src/services/api.ts (learningSessionsService: startSession, updateProgress, addNote, addBookmark, completeSession, getTodayOverview, getHistory)
- [x] Create frontend/src/app/learn/page.tsx (interactive learning session page with all UI elements)
- [x] Update frontend/src/components/shared/sidebar.tsx (Learning Session link)
- [x] Create LEARNING_SESSION.md (architecture and API documentation)
- [x] Run verification: py_compile and tsc --noEmit pass
