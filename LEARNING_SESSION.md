# Learning Session Mode

## Overview

The Learning Session Mode provides an interactive, guided practice session that activates when a user starts today's mission. It combines the mission system, the intelligent recommendation engine, and the progress/streak tracking into a single cohesive learning experience.

## Architecture

```
Learning Session Mode
├── Database (014_learning_session.sql)
│   ├── learning_session_state   — tracks session progress, status, XP
│   ├── learning_session_notes    — notes taken during sessions
│   └── learning_session_bookmarks — bookmarked resources within sessions
├── Backend
│   ├── models/learning_session.py          — Pydantic schemas
│   ├── repositories/learning_session_repo.py — data access layer
│   ├── services/learning_session_service.py  — business logic orchestrator
│   └── api/v1/learning_session.py           — REST API endpoints
├── Frontend
│   ├── src/app/learn/page.tsx               — interactive session UI
│   ├── src/services/api.ts (learningSessionsService) — API client
│   └── src/types/index.ts (session types)   — TypeScript types
└── Documentation
    └── LEARNING_SESSION.md (this file)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/learning-sessions/start` | Start a learning session — fetches mission, recommended resources, previous mistakes |
| POST | `/api/v1/learning-sessions/{mission_id}/progress` | Update session progress (progress bar) |
| POST | `/api/v1/learning-sessions/{mission_id}/notes` | Add a note during the session |
| POST | `/api/v1/learning-sessions/{mission_id}/bookmarks` | Bookmark a resource during the session |
| POST | `/api/v1/learning-sessions/{mission_id}/complete` | Complete the session — earns XP, updates dashboard/mission/progress/scheduler |
| GET | `/api/v1/learning-sessions/today` | Get today's session overview (missions + states) |
| GET | `/api/v1/learning-sessions/history` | Get session history |

## Database Schema

### learning_session_state
Tracks the state of each learning session:
- `user_id` — FK to users
- `mission_id` — FK to daily_missions
- `session_id` — UUID for the session instance
- `status` — active, completed, or abandoned
- `progress_percent` — 0-100 progress bar value
- `started_at` / `completed_at` — timestamps
- `notes_count` — number of notes taken in this session
- `bookmarked_resources` — count of bookmarks in this session
- `xp_earned` — XP earned in this session
- `metadata` — flexible JSON for additional session context

### learning_session_notes
Notes taken during learning sessions:
- `user_id`, `mission_id`, `resource_id`, `session_id` — context
- `content` — the note text
- `created_at` / `updated_at` — timestamps

### learning_session_bookmarks
Resources bookmarked within learning sessions:
- `user_id`, `resource_id`, `mission_id`, `session_id`
- `created_at` — timestamps
- Unique constraint on (user_id, resource_id, mission_id)

All tables have Row Level Security enabled with policies scoped to `auth.uid() = user_id`.

## Session Lifecycle

1. **Start Session**: When the user navigates to `/learn` or clicks "Start Mission" on the dashboard:
   - Fetches today's missions (generates them if none exist — deterministic, no AI)
   - Selects the mission matching the user's weakest skill, or the first pending mission
   - Sets mission status to active (tracked in `learning_session_state`)
   - Uses the **Recommendation Engine** to fetch a recommended resource for the mission's skill
   - Fetches related resources with the same skill
   - Fetches previous mistakes from the user's study history for this skill
   - Fetches existing notes and bookmarks for this mission
   - Returns the user's current band, target band, and remaining days to exam

2. **Track Progress**: As the user interacts:
   - Progress bar updates via `POST /progress`
   - Notes are added via `POST /notes` (also saved to `learning_session_notes`)
   - Resources are bookmarked via `POST /bookmarks` (also saved to `resource_bookmarks`)

3. **Complete Session**: When the user clicks "Mark Complete":
   - Mission is marked as `completed` with 100% completion (in `daily_missions`)
   - Session time + XP is logged to `study_sessions` (progress tracking ledger)
   - Streaks are recomputed (daily/weekly/monthly, perfect day, milestones)
   - Session state is updated to `completed` with `progress_percent = 100`
   - Achievements are checked and awarded
   - All of these trigger cascading updates to:
     - **Dashboard**: total XP, level, streak, completion rate
     - **Mission**: mission status changes to completed, completion % updates
     - **Progress**: study time + XP logged to progress_state
     - **Scheduler**: streak recompute may affect next day's workload

4. **Post-Completion**: If all of today's missions are completed:
   - Tomorrow's missions are auto-generated (deterministic)

## UI Components (Frontend `/learn` page)

The page displays all requested elements:

| UI Element | Implementation |
|---|---|
| **Mission Title** | `mission.title` in the header |
| **Task Description** | Description text in the Mission Details card |
| **Recommended Resource** | Resource card with title, description, type badges, bookmark button |
| **Estimated Time** | `mission.estimated_minutes` in the stats grid |
| **Progress Bar** | `<Progress>` component bound to `progress_percent` |
| **Notes Section** | Textarea input + list of existing notes |
| **Bookmark Button** | Toggle button on resource cards and related resources |
| **Previous Mistakes** | Orange-highlighted list with mistake type and description |
| **Related Resources** | Grid of resource cards with type and metadata |
| **Mark Complete** | Green button that triggers the completion flow |
| **Earn XP** | XP reward displayed + full XP/level/streak summary on completion |

## Integration Points

- **Recommendation Engine**: Uses `RecommendationEngineService.get_recommendations()` to fetch personalized resource recommendations (rule-based, no AI)
- **Daily Missions**: Reuses existing mission completion flow (status update, XP logging, streak triggers)
- **Progress Tracking**: Logs sessions to `study_sessions` via `ProgressTrackingRepository.log_session()`
- **Streak System**: Triggers `StreakRepository.process_activity()` on completion
- **Resource Management**: Bookmarks are also saved to the `resource_bookmarks` table
- **Achievements**: Checks for unlocked achievements on mission completion

## Error Handling

- All database calls use safe wrapper methods that return empty defaults when DB is unavailable
- Frontend displays inline error messages for all failures (same pattern as other pages)
- Completion is blocked until progress is set to at least 50%
- All session operations are scoped to the authenticated user via `user_id`

## Production Notes

- All SQL tables have RLS policies enforcing per-user isolation
- Indexes on frequently queried columns (user_id, mission_id, status)
- `updated_at` triggers auto-update timestamps
- No AI/scheduling logic — all data is deterministic
- Frontend uses native HTML + existing UI components (no new dependencies)