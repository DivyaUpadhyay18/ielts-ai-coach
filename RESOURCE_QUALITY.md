# Resource Quality Scoring System

## Overview

The Resource Quality Scoring system provides a comprehensive framework for tracking, scoring, and moderating the quality of learning resources in the IELTS AI Coach platform. It enables users to submit feedback on resources, allows administrators to moderate that feedback, and computes quality scores that power the recommendation engine and resource discovery.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                    │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │ Quality Page     │  │ ResourceQuality Component│   │
│  │ (/quality)       │  │ (inline on resource view)│   │
│  │ - Leaderboard    │  │ - Score display          │   │
│  │ - Statistics     │  │ - Feedback form          │   │
│  │ - Moderation     │  │ - Feedback list          │   │
│  └──────────────────┘  └──────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │         resourceQualityService (api.ts)          │   │
│  │  - submitFeedback, listFeedback, getFeedback     │   │
│  │  - getScores, getBreakdown, recomputeScores      │   │
│  │  - getLeaderboard, recomputeAll                  │   │
│  │  - getModerationQueue, moderateFeedback          │   │
│  │  - getStats                                      │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                     │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  /api/v1/resource-quality/*                      │   │
│  │  (resource_quality.py)                           │   │
│  │  - POST /feedback                                │   │
│  │  - GET /feedback                                 │   │
│  │  - GET /feedback/{id}                            │   │
│  │  - DELETE /feedback/{id}                         │   │
│  │  - GET /resources/{id}/scores                    │   │
│  │  - GET /resources/{id}/breakdown                 │   │
│  │  - POST /resources/{id}/recompute                │   │
│  │  - GET /leaderboard                              │   │
│  │  - POST /recompute-all                           │   │
│  │  - GET /admin/queue                              │   │
│  │  - GET /admin/feedback/{id}/log                  │   │
│  │  - POST /admin/feedback/{id}/moderate            │   │
│  │  - GET /stats                                    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  ResourceQualityRepository                       │   │
│  │  (resource_quality_repo.py)                      │   │
│  │  - submit_feedback()                             │   │
│  │  - get_feedback()                                │   │
│  │  - list_user_feedback()                          │   │
│  │  - list_resource_feedback()                      │   │
│  │  - moderate_feedback()                           │   │
│  │  - get_moderation_log()                          │   │
│  │  - get_moderation_queue()                        │   │
│  │  - compute_quality_scores()                    │   │
│  │  - get_leaderboard()                             │   │
│  │  - get_quality_stats()                           │   │
│  │  - delete_feedback()                             │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Database (Supabase / PostgreSQL)                │   │
│  │  - resource_feedback                             │   │
│  │  - resource_quality_scores                       │   │
│  │  - resource_moderation_log                       │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Database Schema

### `resource_feedback` Table

| Column              | Type         | Description                                      |
|---------------------|--------------|--------------------------------------------------|
| `id`                | UUID (PK)    | Primary key                                      |
| `user_id`           | UUID         | User who submitted the feedback                  |
| `resource_id`       | UUID         | Resource being reported                          |
| `feedback_type`     | TEXT         | `broken_link`, `better_resource`, `correction`, `rating` |
| `title`             | TEXT         | Title for broken_link feedback                   |
| `description`       | TEXT         | Description of the issue                         |
| `suggested_url`     | TEXT         | Suggested replacement URL                        |
| `suggested_title`   | TEXT         | Suggested replacement title                      |
| `field_name`        | TEXT         | Field to correct (for correction feedback)       |
| `suggested_value`   | TEXT         | Corrected value (for correction feedback)        |
| `reason`            | TEXT         | Reason for the suggestion                        |
| `rating`            | INTEGER      | Rating value (1-5, for rating feedback)          |
| `status`            | TEXT         | `pending`, `approved`, `rejected`, `resolved`, `dismissed` |
| `priority`          | TEXT         | `low`, `normal`, `high`, `urgent`                |
| `admin_notes`       | TEXT         | Notes from admin moderation                      |
| `moderated_by`      | UUID         | Admin who moderated the feedback                 |
| `moderated_at`      | TIMESTAMP    | When the feedback was moderated                  |
| `resolved_at`       | TIMESTAMP    | When the feedback was resolved                   |
| `created_at`        | TIMESTAMP    | Creation timestamp                               |
| `updated_at`        | TIMESTAMP    | Last update timestamp                            |

### `resource_quality_scores` Table

| Column                    | Type    | Description                                      |
|---------------------------|---------|--------------------------------------------------|
| `resource_id`             | UUID (PK) | Resource identifier                            |
| `quality_score`           | REAL    | Overall quality score (0-100)                    |
| `popularity_score`        | REAL    | Popularity score (0-100)                         |
| `completion_score`        | REAL    | Completion score (0-100)                       |
| `recommendation_score`    | REAL    | Recommendation score (0-100)                   |
| `avg_rating`              | REAL    | Average user rating (1-5)                        |
| `rating_count`            | INTEGER | Number of ratings                                |
| `view_count`              | INTEGER | Number of views                                  |
| `bookmark_count`          | INTEGER | Number of bookmarks                              |
| `like_count`              | INTEGER | Number of likes                                  |
| `completion_count`        | INTEGER | Number of completions                            |
| `broken_link_count`       | INTEGER | Number of broken link reports                    |
| `correction_count`        | INTEGER | Number of correction suggestions                 |
| `suggestion_count`        | INTEGER | Number of better resource suggestions            |
| `computed_at`             | TIMESTAMP | When scores were last computed                 |
| `updated_at`              | TIMESTAMP | Last update timestamp                          |

### `resource_moderation_log` Table

| Column         | Type    | Description                                      |
|----------------|---------|--------------------------------------------------|
| `id`           | UUID (PK) | Log entry ID                                   |
| `feedback_id`  | UUID    | Reference to feedback                            |
| `admin_id`     | UUID    | Admin who performed the action                   |
| `action`       | TEXT    | `approved`, `rejected`, `resolved`, `dismissed`, `escalated`, `commented` |
| `old_status`   | TEXT    | Previous status                                  |
| `new_status`   | TEXT    | New status                                       |
| `notes`        | TEXT    | Admin notes                                      |
| `created_at`   | TIMESTAMP | When the action was performed                  |

## Quality Score Computation

The quality score is computed using a weighted formula that combines multiple signals:

### Weights

| Component             | Weight | Description                                      |
|-----------------------|--------|--------------------------------------------------|
| `avg_rating`          | 30%    | Average user rating (normalized to 0-100)        |
| `view_count`          | 15%    | Number of views (normalized)                     |
| `bookmark_count`      | 15%    | Number of bookmarks (normalized)                 |
| `like_count`          | 10%    | Number of likes (normalized)                     |
| `completion_count`    | 15%    | Number of completions (normalized)               |
| `feedback_penalty`    | -15%   | Penalty for negative feedback (broken links, etc.) |

### Score Types

1. **Quality Score**: Overall quality based on ratings and feedback
2. **Popularity Score**: Based on views, bookmarks, and likes
3. **Completion Score**: Based on completion rate
4. **Recommendation Score**: Composite score used for resource recommendations

### Normalization

All raw counts are normalized using a logarithmic scale to prevent gaming:
```
normalized = min(raw_count / 100, 1.0) * 100
```

## Feedback Types

| Type             | Priority  | Description                                      |
|------------------|-----------|--------------------------------------------------|
| `broken_link`    | High      | Report a broken or inaccessible link             |
| `better_resource`| Normal    | Suggest a better alternative resource            |
| `correction`     | Normal    | Suggest a correction to resource details         |
| `rating`         | Low       | Rate the resource on a 1-5 scale                 |

## Moderation Workflow

1. User submits feedback → status = `pending`
2. Admin reviews feedback in the moderation queue
3. Admin takes action:
   - `approved` — Feedback is valid and acknowledged
   - `rejected` — Feedback is invalid/spam
   - `resolved` — Issue has been fixed
   - `dismissed` — Feedback is not actionable
   - `escalated` — Feedback requires further review
   - `commented` — Admin adds a note (status unchanged)
4. Each moderation action is logged in `resource_moderation_log`

## API Endpoints

### User Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/resource-quality/feedback` | Submit feedback |
| GET | `/api/v1/resource-quality/feedback` | List feedback (with filters) |
| GET | `/api/v1/resource-quality/feedback/{id}` | Get specific feedback |
| DELETE | `/api/v1/resource-quality/feedback/{id}` | Delete own pending feedback |
| GET | `/api/v1/resource-quality/resources/{id}/scores` | Get quality scores |
| GET | `/api/v1/resource-quality/resources/{id}/breakdown` | Get score breakdown |
| POST | `/api/v1/resource-quality/resources/{id}/recompute` | Recompute scores |
| GET | `/api/v1/resource-quality/leaderboard` | Get leaderboard |
| GET | `/api/v1/resource-quality/stats` | Get quality stats |

### Admin Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/resource-quality/admin/queue` | Get moderation queue |
| GET | `/api/v1/resource-quality/admin/feedback/{id}/log` | Get moderation log |
| POST | `/api/v1/resource-quality/admin/feedback/{id}/moderate` | Moderate feedback |
| POST | `/api/v1/resource-quality/recompute-all` | Recompute all scores |

## Frontend Components

### `ResourceQuality` Component

Used inline on resource detail pages to display:
- Quality score rings (Quality, Popularity, Completion, Recommendation)
- Feedback submission form (4 feedback types)
- User's submitted feedback list

### `QualityPage` (`/quality`)

Full dashboard page with three tabs:
- **Leaderboard**: Ranked list of resources by quality score
- **Statistics**: Aggregate stats and average scores
- **Moderation**: Admin moderation queue with action buttons

### `ModerationPanel` Component

Admin-only component showing:
- Stats cards (pending, broken links, corrections, resolved)
- Moderation queue with approve/reject/resolve/dismiss actions
- Moderation log history

## Verification

Run the verification script:
```bash
cd backend
python verify_resource_quality.py
```

This tests:
1. Feedback submission (all 4 types)
2. Feedback retrieval and listing
3. Moderation workflow (approve, resolve)
4. Quality score computation
5. Leaderboard retrieval
6. Stats retrieval
7. Feedback deletion

## Production Considerations

- **Rate limiting**: All endpoints are protected by the global rate limiter
- **Authentication**: All endpoints require a valid JWT token
- **Authorization**: Admin endpoints check for admin role
- **Input validation**: All inputs are validated with Pydantic schemas
- **Error handling**: Consistent error envelope via `register_exception_handlers`
- **Security headers**: HSTS, X-Frame-Options, X-Content-Type-Options
- **Caching**: Scores are cached and only recomputed on demand or via cron
- **Audit trail**: All moderation actions are logged
</arg_value><arg_key>path</arg_key><arg_value>RESOURCE_QUALITY.md</arg_value></tool_call>