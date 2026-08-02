# Schedule History Feature

## Overview

The Schedule History feature provides a comprehensive audit trail of all changes made to a user's study schedule. It tracks previous and new schedules, reasons for changes, timestamps, and user actions, enabling users to review and compare schedule modifications over time.

## Architecture

### Database Schema

**Table: `schedule_history`**
- `id` - UUID primary key
- `user_id` - References the user
- `study_plan_id` - References the study plan (optional)
- `run_id` - References the scheduler run (optional)
- `previous_schedule` - JSONB snapshot of schedule before changes
- `new_schedule` - JSONB snapshot of schedule after changes
- `change_reason` - Human-readable explanation of why changes were made
- `change_type` - Type of change (scheduler_run, exam_date_update, manual_reschedule, etc.)
- `trigger_type` - What triggered the change (midnight, app_open, manual, system, user)
- `user_action` - User's response (accepted, rejected, modified, pending, auto_applied)
- `user_action_at` - Timestamp of user action
- `user_action_notes` - Optional notes from user
- `metrics_before` - JSONB snapshot of metrics before changes
- `metrics_after` - JSONB snapshot of metrics after changes
- `summary` - Auto-generated summary of changes
- `adjustments_count` - Number of adjustments made
- `tasks_affected` - Number of tasks affected
- `created_at` - Timestamp of history entry
- `updated_at` - Timestamp of last update

**Helper Function: `get_schedule_comparison`**
- Compares two schedule history entries
- Returns tasks added/removed/rescheduled
- Calculates workload and completion rate changes

### Backend Components

#### 1. Models (`backend/app/models/schedule_history.py`)
- `ScheduleHistoryEntry` - Main history entry model
- `ScheduleHistoryListResponse` - Paginated list response
- `ScheduleComparisonResponse` - Comparison between two entries
- `ScheduleHistoryCreate` - Creation request model
- `ScheduleHistoryUpdate` - Update request model
- `ScheduleHistoryFilter` - Filter parameters
- `ScheduleHistoryStats` - Statistics response

#### 2. Repository (`backend/app/repositories/schedule_history_repo.py`)
- `create_entry()` - Create new history entry
- `get_by_id()` - Get entry by ID
- `list_history()` - List entries with filters and pagination
- `update_user_action()` - Update user action on entry
- `get_comparison()` - Get comparison between two entries
- `get_latest()` - Get latest entries
- `get_by_run_id()` - Get entry by scheduler run ID
- `get_stats()` - Get statistics
- `delete_old_entries()` - Cleanup old entries

#### 3. Service (`backend/app/services/schedule_history_service.py`)
- `log_scheduler_run()` - Log scheduler run changes
- `log_exam_date_update()` - Log exam date changes
- `log_manual_reschedule()` - Log manual task rescheduling
- `log_study_plan_regeneration()` - Log plan regeneration
- `get_user_history()` - Get user's history
- `get_comparison()` - Get comparison between entries
- `update_user_action()` - Update user action
- `get_stats()` - Get statistics

#### 4. API Endpoints (`backend/app/api/v1/schedule_history.py`)
- `GET /api/v1/schedule-history` - List history with filters
- `GET /api/v1/schedule-history/{history_id}` - Get specific entry
- `GET /api/v1/schedule-history/compare/{id1}/{id2}` - Compare two entries
- `PATCH /api/v1/schedule-history/{history_id}/action` - Update user action
- `GET /api/v1/schedule-history/stats/summary` - Get statistics
- `GET /api/v1/schedule-history/latest` - Get latest entry
- `POST /api/v1/schedule-history/internal/create` - Internal endpoint for creating entries

### Frontend Components

#### 1. Types (`frontend/src/types/index.ts`)
```typescript
export type ScheduleChangeType =
  | 'scheduler_run'
  | 'exam_date_update'
  | 'manual_reschedule'
  | 'study_plan_regeneration'
  | 'task_modification'
  | 'user_override';

export type UserAction =
  | 'accepted'
  | 'rejected'
  | 'modified'
  | 'pending'
  | 'auto_applied';

export interface ScheduleHistoryEntry {
  id: string;
  user_id: string;
  study_plan_id?: string | null;
  run_id?: string | null;
  previous_schedule: Record<string, any>;
  new_schedule: Record<string, any>;
  change_reason: string;
  change_type: ScheduleChangeType;
  trigger_type?: ScheduleTriggerType | null;
  user_action?: UserAction | null;
  user_action_at?: string | null;
  user_action_notes?: string | null;
  metrics_before: Record<string, any>;
  metrics_after: Record<string, any>;
  summary?: string | null;
  adjustments_count: number;
  tasks_affected: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ScheduleComparisonResponse {
  history_1_id: string;
  history_2_id: string;
  history_1_date: string;
  history_2_date: string;
  history_1_change_type: ScheduleChangeType;
  history_2_change_type: ScheduleChangeType;
  tasks_added: number;
  tasks_removed: number;
  tasks_rescheduled: number;
  workload_change_minutes: number;
  completion_rate_change: number;
}
```

#### 2. API Service (`frontend/src/services/api.ts`)
```typescript
export const scheduleHistoryService = {
  list: async (params?) => Promise<ScheduleHistoryListResponse>,
  get: async (historyId: string) => Promise<ScheduleHistoryEntry>,
  getLatest: async () => Promise<ScheduleHistoryEntry | null>,
  compare: async (historyId1, historyId2) => Promise<ScheduleComparisonResponse>,
  updateAction: async (historyId, action, notes?) => Promise<ScheduleHistoryEntry>,
  getStats: async (days: number) => Promise<ScheduleHistoryStats>,
};
```

#### 3. Page Component (`frontend/src/app/schedule-history/page.tsx`)
- Displays complete history of schedule changes
- Shows statistics overview (total changes, accepted/rejected, tasks affected)
- Filterable by change type and user action
- Interactive comparison feature (select two entries to compare)
- Expandable cards showing detailed metrics
- Visual indicators for workload changes

#### 4. Navigation (`frontend/src/components/shared/sidebar.tsx`)
- Added "Schedule History" link to sidebar navigation
- Uses History icon from lucide-react

## Integration with Adaptive Scheduler

The schedule history feature is automatically integrated with the adaptive scheduler. After each scheduler run:

1. **Schedule Snapshots**: Captures before/after snapshots of the next 7 days of tasks
2. **Metrics Tracking**: Records workload minutes and completion rates
3. **Automatic Logging**: Creates a history entry with:
   - All adjustments made
   - Reasons for each change
   - Trigger type (midnight, app_open, manual)
   - Summary of changes

### Integration with Exam Countdown

When a user updates their exam date and the study plan is auto-regenerated, the schedule history logs an `exam_date_update` entry with:
- Previous and new exam dates
- Before/after schedule snapshots
- Auto-regeneration flag

### Integration with Study Plan Generator

When a study plan is regenerated (new version), the schedule history logs a `study_plan_regeneration` entry with:
- Previous and new plan IDs
- Before/after schedule snapshots
- Regeneration reason

## Usage

### Viewing Schedule History

1. Navigate to `/schedule-history` from the sidebar
2. View complete history of all schedule changes
3. See statistics for the last 30 days
4. Filter by change type or user action
5. Click on any entry to expand details
6. Select two entries to compare changes

### Comparing Schedules

1. Click on two history entries to select them (they'll be highlighted)
2. The comparison view automatically appears
3. View:
   - Tasks added/removed/rescheduled
   - Workload changes (minutes)
   - Completion rate changes
   - Timestamps and change types

### User Actions

Users can:
- **Accept** changes they agree with
- **Reject** changes they don't want
- **Modify** changes and add notes
- View auto-applied changes

## Production Readiness

### Error Handling
- All database operations wrapped in try-catch blocks
- Graceful degradation if history logging fails (scheduler continues)
- Proper HTTP status codes and error messages
- Input validation on all endpoints
- Previous schedule snapshot captured BEFORE changes are persisted (fixes data accuracy bug)

### Performance
- Database indexes on frequently queried columns
- Pagination support (limit/offset)
- Efficient JSONB queries for schedule snapshots
- Connection pooling via repository pattern

### Security
- Row Level Security (RLS) enabled on schedule_history table
- Users can only access their own history
- JWT authentication required for all endpoints
- SQL injection prevention via parameterized queries

### Scalability
- JSONB for flexible schedule storage
- Efficient comparison via database function
- Support for large history volumes
- Cleanup method for old entries

### Security
- Row Level Security (RLS) enabled on schedule_history table
- Users can only access their own history
- JWT authentication required for all endpoints
- SQL injection prevention via parameterized queries

### Scalability
- JSONB for flexible schedule storage
- Efficient comparison via database function
- Support for large history volumes
- Cleanup method for old entries

## Database Migration

Run the migration file in Supabase SQL editor:

```sql
-- File: backend/app/db/migrations/011_schedule_history.sql
-- Run after: 009_adaptive_scheduler.sql
```

This creates:
- `schedule_history` table
- Indexes for performance
- RLS policies for security
- `get_schedule_comparison()` function

## Testing

The implementation includes:
- Type safety with TypeScript
- Pydantic validation on backend
- Error handling in all service methods
- Async/await patterns for database operations
- Comprehensive logging for debugging

## Future Enhancements

Potential improvements:
1. Visual timeline of schedule changes
2. Export history to PDF/CSV
3. Advanced filtering and search
4. Notifications for significant changes
5. Analytics dashboard for study patterns
6. Rollback functionality to restore previous schedules