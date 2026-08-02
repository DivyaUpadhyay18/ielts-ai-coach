# IELTS AI Coach — Complete Backend API Design

**Role:** Chief Product Architect  
**Document:** Full API Specification  
**Version:** 1.0  
**Status:** Draft for review & approval  
**Base URL:** `/api/v1`

---

## 0. API Conventions

### 0.1 General Rules

| Rule | Standard |
|---|---|
| **Base path** | `/api/v1` — all endpoints prefixed |
| **Method semantics** | GET = read, POST = create, PUT = update/replace, PATCH = partial update, DELETE = remove |
| **Request body** | JSON (`application/json`) |
| **Response body** | JSON (`application/json`) |
| **Pagination** | `?page=1&limit=20` → `{ data: [...], total: int, page: int, limit: int, has_more: bool }` |
| **Date format** | ISO 8601 (`2025-06-15T10:30:00Z`) |
| **Date-only format** | `2025-06-15` |
| **IDs** | UUID v4 |
| **Errors** | Consistent `{ "detail": { "code": "string", "message": "string", "fields": {} } }` envelope |
| **Idempotency** | POST requests accept `Idempotency-Key` header (UUID); duplicate requests within 24h return cached response |

### 0.2 Authentication

| Scheme | Type | Header |
|---|---|---|
| **JWT Bearer** | `Authorization: Bearer <token>` | Supabase JWT (access token) |
| **Cookie** | `sb-*-auth-token` | Supabase SSR cookie for Next.js middleware |

- All endpoints except `/health`, `/auth/login`, `/auth/signup`, `/auth/forgot-password` require authentication.
- Unauthenticated requests return `401 Unauthorized`.
- Expired tokens return `401` with `code: "token_expired"`.
- Insufficient permissions return `403 Forbidden`.

### 0.3 Rate Limiting

| Tier | Default | Burst | Headers Returned |
|---|---|---|---|
| **Free** | 60 req/min | 100 | `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` |
| **Pro** | 300 req/min | 500 | same |
| **AI endpoints** | 20 req/min (shared across all AI) | 30 | same |
| **Login** | 5 req/min per IP | — | same |

Rate limit exceeded → `429 Too Many Requests` with `Retry-After` header.

### 0.4 Error Response Envelope

```json
{
  "detail": {
    "code": "validation_error",
    "message": "Human-readable description",
    "fields": {
      "email": "Invalid email format"
    }
  }
}
```

| Code | HTTP Status | Meaning |
|---|---|---|
| `validation_error` | 400 | Request body validation failed |
| `unauthorized` | 401 | Missing or invalid auth token |
| `token_expired` | 401 | JWT expired; refresh required |
| `forbidden` | 403 | Authenticated but not authorized |
| `not_found` | 404 | Resource doesn't exist |
| `conflict` | 409 | Duplicate resource (e.g., email exists) |
| `rate_limited` | 429 | Too many requests |
| `internal_error` | 500 | Unexpected server error |
| `ai_service_unavailable` | 503 | AI provider is down |
| `diagnostic_incomplete` | 400 | Diagnostic not yet complete |

---

## 1. Authentication Module

Base path: `/api/v1/auth`

### 1.1 Sign Up

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/auth/signup` |
| **Purpose** | Create a new user account. Delegates to Supabase Auth. On success, creates a row in `users` table via trigger. |

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePass123!",
  "full_name": "John Doe"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `email` | Required, valid email format, unique in system, max 255 chars |
| `password` | Required, min 6 chars, max 128 chars |
| `full_name` | Required, min 2 chars, max 100 chars |

**Response (201 Created):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2025-06-15T10:30:00Z",
  "session": {
    "access_token": "jwt...",
    "refresh_token": "jwt...",
    "expires_at": 1723456789
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `conflict` | 409 | Email already registered |
| `validation_error` | 400 | Password too short, invalid email |
| `internal_error` | 500 | Supabase Auth unavailable |

**Rate Limiting:** 5 requests per minute per IP.

---

### 1.2 Login

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/auth/login` |
| **Purpose** | Authenticate user with email/password. Returns JWT session. |

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePass123!"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `email` | Required, valid email format |
| `password` | Required, non-empty |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "session": {
    "access_token": "jwt...",
    "refresh_token": "jwt...",
    "expires_at": 1723456789
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `unauthorized` | 401 | Invalid email or password |
| `unauthorized` | 401 | Account not verified |
| `rate_limited` | 429 | Too many failed attempts |
| `internal_error` | 500 | Supabase Auth unavailable |

**Rate Limiting:** 5 req/min per IP. After 10 consecutive failed attempts, lock for 15 minutes.

---

### 1.3 Logout

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/auth/logout` |
| **Purpose** | Invalidate current session. Revokes refresh token in Supabase. |

**Request Body:** None

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "Logged out successfully"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `unauthorized` | 401 | Invalid or expired token |

---

### 1.4 Forgot Password

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/auth/forgot-password` |
| **Purpose** | Send password reset email via Supabase Auth. |

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `email` | Required, valid email format |

**Response (200 OK):**
```json
{
  "message": "If the email exists, a reset link has been sent."
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `rate_limited` | 429 | Too many reset requests (3 per hour per email) |

**Note:** Always returns 200 even if email doesn't exist (prevents email enumeration).

---

### 1.5 Reset Password

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/auth/reset-password` |
| **Purpose** | Set new password using reset token from email link. |

**Request Body:**
```json
{
  "token": "reset-token-from-email",
  "new_password": "newSecurePass123!"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `token` | Required, valid reset token |
| `new_password` | Required, min 6 chars, max 128 chars |

**Response (200 OK):**
```json
{
  "message": "Password reset successfully"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `unauthorized` | 401 | Invalid or expired reset token |
| `validation_error` | 400 | Password too weak |

---

### 1.6 Get Current User

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/auth/me` |
| **Purpose** | Fetch the authenticated user's profile. |

**Authentication:** Required

**Request Body:** None

**Response (200 OK):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "avatar_url": "https://...",
  "country": "US",
  "timezone": "America/New_York",
  "module": "academic",
  "plan": "free",
  "target_band": 7.5,
  "exam_date": "2025-12-15",
  "daily_minutes_budget": 60,
  "is_onboarding_complete": false,
  "onboarded_at": null,
  "preferences": {
    "notifications": { "push": true, "email": false },
    "theme": "light"
  },
  "created_at": "2025-06-15T10:30:00Z"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `unauthorized` | 401 | Missing or invalid token |

---

### 1.7 Update Profile

| Property | Value |
|---|---|
| **Method** | `PUT` |
| **Endpoint** | `/api/v1/auth/me` |
| **Purpose** | Update the authenticated user's profile fields. |

**Authentication:** Required

**Request Body:**
```json
{
  "full_name": "John Updated",
  "country": "GB",
  "timezone": "Europe/London",
  "avatar_url": "https://...",
  "preferences": {
    "theme": "dark"
  }
}
```

**Validation:**
| Field | Rule |
|---|---|
| `full_name` | Optional, min 2 chars, max 100 |
| `country` | Optional, ISO 3166-1 alpha-2 (2 chars) |
| `timezone` | Optional, IANA tz name |
| `avatar_url` | Optional, HTTPS URL |
| `preferences` | Optional, JSON object |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "full_name": "John Updated",
  "country": "GB",
  "timezone": "Europe/London",
  "preferences": { "theme": "dark" },
  "updated_at": "2025-06-16T08:00:00Z"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | Invalid field values |
| `unauthorized` | 401 | Missing auth |

---

### 1.8 Update Goals

| Property | Value |
|---|---|
| **Method** | `PUT` |
| **Endpoint** | `/api/v1/auth/goals` |
| **Purpose** | Update user's IELTS goals (target band, exam date, etc.). Triggers roadmap re-evaluation if changed. |

**Authentication:** Required

**Request Body:**
```json
{
  "target_band": 8.0,
  "exam_date": "2025-12-15",
  "module": "academic",
  "daily_minutes_budget": 90
}
```

**Validation:**
| Field | Rule |
|---|---|
| `target_band` | Required, 0.0–9.0, step 0.5 |
| `exam_date` | Required, must be in the future, max 2 years from now |
| `module` | Required, `academic` or `general` |
| `daily_minutes_budget` | Required, 15–480 |

**Response (200 OK):**
```json
{
  "target_band": 8.0,
  "exam_date": "2025-12-15",
  "module": "academic",
  "daily_minutes_budget": 90,
  "roadmap_needs_regeneration": true
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | Exam date in past, band out of range |
| `conflict` | 409 | Exam date too close for target band (warning) |

**Rate Limiting:** 10 req/min (goal changes are expensive due to roadmap regeneration).

---

### 1.9 Refresh Token

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/auth/refresh` |
| **Purpose** | Exchange a refresh token for a new access token. |

**Request Body:**
```json
{
  "refresh_token": "jwt..."
}
```

**Validation:**
| Field | Rule |
|---|---|
| `refresh_token` | Required, valid JWT |

**Response (200 OK):**
```json
{
  "access_token": "new-jwt...",
  "refresh_token": "new-refresh-jwt...",
  "expires_at": 1723456789
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `unauthorized` | 401 | Invalid or expired refresh token |

---

### 1.10 Google OAuth

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/auth/oauth/google` |
| **Purpose** | Authenticate or sign up with Google OAuth token. |

**Request Body:**
```json
{
  "id_token": "google-id-token..."
}
```

**Validation:**
| Field | Rule |
|---|---|
| `id_token` | Required, valid Google ID token |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "email": "user@gmail.com",
  "full_name": "John Google",
  "avatar_url": "https://...",
  "is_new_user": true,
  "session": {
    "access_token": "jwt...",
    "refresh_token": "jwt...",
    "expires_at": 1723456789
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `unauthorized` | 401 | Invalid Google token |
| `internal_error` | 500 | OAuth provider error |

---

## 2. Dashboard Module

Base path: `/api/v1/dashboard`

The Dashboard module is a **BFF (Backend-for-Frontend)** layer. It aggregates data from multiple domain services into optimized payloads for the 17-widget dashboard (see DASHBOARD.md).

### 2.1 Dashboard Overview

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/dashboard/overview` |
| **Purpose** | Fetch all dashboard widget data in a single round trip. Aggregates band, streak, countdown, tasks, XP, skills, and recommendations. |

**Authentication:** Required

**Query Parameters:** None

**Response (200 OK):**
```json
{
  "user": {
    "full_name": "John Doe",
    "greeting": "Good Morning",
    "avatar_url": "https://..."
  },
  "band": {
    "current": 6.5,
    "target": 7.5,
    "trend": "+0.3",
    "progress_pct": 65
  },
  "countdown": {
    "days_remaining": 24,
    "exam_date": "2025-12-15",
    "intensity": "moderate"
  },
  "streak": {
    "current": 5,
    "longest": 14,
    "is_at_risk": false
  },
  "today_mission": {
    "date": "2025-11-21",
    "total_tasks": 3,
    "completed_tasks": 1,
    "total_minutes": 60,
    "completed_minutes": 20,
    "tasks": [
      {
        "id": "uuid",
        "title": "Writing Task 2: Opinion Essay",
        "skill": "writing",
        "duration_minutes": 40,
        "status": "in_progress"
      }
    ]
  },
  "xp": {
    "daily_xp": 120,
    "daily_target": 300,
    "level": 4,
    "level_progress": 0.45
  },
  "quick_actions": {
    "continue_last_lesson": { "task_id": "uuid", "url": "/writing" },
    "writing_practice": { "url": "/writing" },
    "speaking_coach": { "url": "/speaking" }
  },
  "recent_assessments": [
    {
      "id": "uuid",
      "task_type": "Writing Task 2",
      "topic": "Education",
      "band_score": 7.0,
      "created_at": "2025-11-20T10:30:00Z"
    }
  ],
  "recommendations": [
    {
      "id": "uuid",
      "title": "IELTS Writing Task 2 Guide",
      "provider": "ielts_liz",
      "reason": "Targets your Coherence & Cohesion gap"
    }
  ],
  "next_mock": {
    "mock_number": 2,
    "scheduled_date": "2025-12-01",
    "prep_state": "needs_preparation"
  },
  "readiness": {
    "score": 72,
    "level": "on_track",
    "components": {
      "consistency": 80,
      "skill_coverage": 65,
      "band_proximity": 70
    }
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `unauthorized` | 401 | Missing auth |
| `internal_error` | 500 | Aggregation failure |

**Caching:** 60-second server-side cache. Invalidated on task completion, assessment submission, or XP event.

---

### 2.2 Today's Mission (Widget)

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/dashboard/mission` |
| **Purpose** | Fetch today's scheduled tasks and progress. Supports date parameter for look-ahead. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `date` | DATE | `today` | Plan date to fetch |

**Response (200 OK):**
```json
{
  "date": "2025-11-21",
  "phase": { "index": 2, "name": "Skill Building" },
  "total_tasks": 3,
  "completed_tasks": 1,
  "total_minutes": 60,
  "completed_minutes": 20,
  "is_rest_day": false,
  "tasks": [
    {
      "id": "uuid",
      "title": "Writing Task 2: Opinion Essay",
      "skill": "writing",
      "task_type": "writing_task2",
      "duration_minutes": 40,
      "status": "in_progress",
      "priority": 3,
      "is_mandatory": true,
      "resource": { "id": "uuid", "title": "Sample Essay", "url": "https://..." }
    }
  ]
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | No plan for this date |
| `unauthorized` | 401 | Missing auth |

---

### 2.3 Skill Overview (Widget)

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/dashboard/skills` |
| **Purpose** | Return weakest and strongest skills with gap analysis. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "strongest": [
    { "skill": "task_response", "score": 7.5, "label": "Task Response" }
  ],
  "weakest": [
    { "skill": "coherence_cohesion", "score": 6.0, "label": "Coherence & Cohesion", "gap": -1.5 }
  ],
  "all_skills": [
    { "skill": "task_response", "score": 7.5, "target": 8.0, "gap": -0.5 },
    { "skill": "coherence_cohesion", "score": 6.0, "target": 7.5, "gap": -1.5 },
    { "skill": "lexical_resource", "score": 7.0, "target": 7.5, "gap": -0.5 },
    { "skill": "grammar", "score": 6.5, "target": 7.5, "gap": -1.0 }
  ]
}
```

---

### 2.4 Progress Snapshot (Widget)

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/dashboard/progress` |
| **Purpose** | Aggregated progress data for the stats cards. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `range` | string | `weekly` | `daily`, `weekly`, `monthly`, `all` |

**Response (200 OK):**
```json
{
  "tasks_completed": { "current": 12, "previous": 9, "trend": "+33%" },
  "study_minutes": { "current": 450, "previous": 380, "trend": "+18%" },
  "assessments_taken": { "current": 4, "previous": 2, "trend": "+100%" },
  "band_improvement": { "current": 6.5, "previous": 6.0, "trend": "+0.5" }
}
```

---

### 2.5 XP & Gamification State (Widget)

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/dashboard/xp` |
| **Purpose** | Return daily XP, level, and progress toward next level. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "daily_xp": 120,
  "daily_cap": 300,
  "daily_xp_pct": 40,
  "level": 4,
  "level_title": "Scholar",
  "current_level_xp": 580,
  "next_level_xp": 880,
  "level_progress_pct": 45,
  "xp_to_next_level": 300,
  "lifetime_xp": 2450
}
```

---

### 2.6 Continue Last Lesson (Widget)

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/dashboard/continue` |
| **Purpose** | Resolve the best task for the user to continue — the last incomplete task. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "has_pending": true,
  "task": {
    "id": "uuid",
    "title": "Writing Task 2: Opinion Essay",
    "skill": "writing",
    "url": "/writing",
    "duration_minutes": 40,
    "scheduled_date": "2025-11-21"
  }
}
```

**Response (200 OK, no pending):**
```json
{
  "has_pending": false,
  "message": "All tasks complete! 🎉"
}
```

---

## 3. Study Plans (Roadmap) Module

Base path: `/api/v1/roadmap`

### 3.1 Generate Roadmap

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/roadmap/generate` |
| **Purpose** | Generate a personalized phased study plan from diagnostic results + user goals. Runs the Roadmap Generator algorithm (see SCHEDULER.md §2). |

**Authentication:** Required

**Request Body:** None (uses user's existing diagnostic results and goals)

**Validation:** User must have completed diagnostic. Returns `diagnostic_incomplete` if not.

**Response (202 Accepted):**
```json
{
  "job_id": "uuid",
  "status": "processing",
  "estimated_seconds": 15
}
```

**Polling:** Client polls `GET /api/v1/roadmap` until `status != 'generating'`.

**Webhook:** Optionally, a `roadmap.ready` Realtime event fires when complete.

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `diagnostic_incomplete` | 400 | User hasn't completed diagnostic |
| `conflict` | 409 | Active roadmap already exists; use `regenerate` |
| `ai_service_unavailable` | 503 | AI provider unavailable |

**Rate Limiting:** 3 req/hour (generation is expensive).

---

### 3.2 Get Current Roadmap

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/roadmap` |
| **Purpose** | Fetch the user's active roadmap with all phases and tasks. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "id": "uuid",
  "version": 1,
  "status": "active",
  "start_band": 6.5,
  "target_band": 7.5,
  "total_weeks": 12,
  "overall_progress_pct": 35,
  "phases": [
    {
      "id": "uuid",
      "order_index": 0,
      "title": "Foundation",
      "description": "Mastering the basics",
      "status": "completed",
      "start_date": "2025-10-01",
      "end_date": "2025-10-28",
      "tasks": [
        {
          "id": "uuid",
          "title": "Diagnostic Assessment",
          "skill": "general",
          "duration_minutes": 20,
          "status": "completed",
          "completed_at": "2025-10-01T10:00:00Z"
        }
      ]
    },
    {
      "id": "uuid",
      "order_index": 1,
      "title": "Skill Building",
      "description": "Deep dive into complex structures",
      "status": "active",
      "start_date": "2025-10-29",
      "end_date": "2025-12-09",
      "tasks": [
        {
          "id": "uuid",
          "title": "Writing Task 2: Opinion Essays",
          "skill": "writing",
          "duration_minutes": 40,
          "status": "completed",
          "completed_at": "2025-11-18T14:00:00Z"
        },
        {
          "id": "uuid",
          "title": "Speaking Part 2: Long Turn Drills",
          "skill": "speaking",
          "duration_minutes": 15,
          "status": "in_progress"
        }
      ]
    }
  ],
  "goal_flag": {
    "target_band": 7.5,
    "estimated_achievement_date": "2025-12-10",
    "confidence_score": 0.88
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | No roadmap generated yet |
| `unauthorized` | 401 | Missing auth |

---

### 3.3 Regenerate Roadmap

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/roadmap/regenerate` |
| **Purpose** | Archive current roadmap and generate a new one. Creates a new version. |

**Authentication:** Required

**Request Body:**
```json
{
  "reason": "exam_date_changed"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `reason` | Required, one of: `exam_date_changed`, `target_changed`, `diagnostic_updated`, `mock_result`, `manual` |

**Response (202 Accepted):**
```json
{
  "job_id": "uuid",
  "status": "processing",
  "new_version": 2,
  "estimated_seconds": 15
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | No existing roadmap to regenerate from |
| `ai_service_unavailable` | 503 | AI provider unavailable |

**Rate Limiting:** 3 req/hour.

---

### 3.4 Get Roadmap History

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/roadmap/history` |
| **Purpose** | List all past roadmap versions. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `limit` | int | 10 | Items per page |

**Response (200 OK):**
```json
{
  "data": [
    {
      "version": 2,
      "status": "active",
      "target_band": 7.5,
      "total_weeks": 12,
      "created_at": "2025-11-01T10:00:00Z",
      "reason": "exam_date_changed"
    },
    {
      "version": 1,
      "status": "archived",
      "target_band": 7.5,
      "total_weeks": 16,
      "created_at": "2025-10-01T10:00:00Z",
      "reason": "initial"
    }
  ],
  "total": 2,
  "page": 1,
  "limit": 10,
  "has_more": false
}
```

---

### 3.5 Get Roadmap Phase Detail

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/roadmap/phases/{phase_id}` |
| **Purpose** | Fetch a single phase with all its tasks. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `phase_id` | UUID | Phase ID |

**Response (200 OK):** Same phase object as in 3.2.

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | Phase not found |

---

## 4. Daily Tasks Module

Base path: `/api/v1/tasks`

### 4.1 List Today's Tasks

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/tasks/today` |
| **Purpose** | Fetch all tasks scheduled for today, ordered by priority. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `include_completed` | bool | `true` | Include already completed tasks |

**Response (200 OK):**
```json
{
  "date": "2025-11-21",
  "total_tasks": 4,
  "completed_tasks": 1,
  "total_minutes": 75,
  "completed_minutes": 15,
  "tasks": [
    {
      "id": "uuid",
      "title": "Writing Task 2: Opinion Essay",
      "skill": "writing",
      "task_type": "writing_task2",
      "duration_minutes": 40,
      "status": "in_progress",
      "priority": 5,
      "is_mandatory": true,
      "phase_index": 1,
      "order_index": 1,
      "content_payload": {
        "prompt": "Some people believe that...",
        "word_limit": 250
      },
      "resource": {
        "id": "uuid",
        "title": "Sample Band 9 Essay",
        "type": "writing_sample",
        "url": "https://..."
      },
      "is_overdue": false,
      "original_date": null
    }
  ]
}
```

---

### 4.2 List Tasks (Filtered)

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/tasks` |
| **Purpose** | Fetch tasks with filters (date range, skill, status). |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `from_date` | DATE | — | Start date |
| `to_date` | DATE | — | End date |
| `skill` | string | — | Filter by skill: `writing`, `speaking`, `reading`, `listening`, `vocabulary`, `grammar`, `mock`, `general` |
| `status` | string | — | Filter by status: `pending`, `in_progress`, `completed`, `missed`, `rescheduled` |
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "Writing Task 2: Opinion Essay",
      "skill": "writing",
      "duration_minutes": 40,
      "scheduled_date": "2025-11-21",
      "status": "in_progress",
      "phase_index": 1
    }
  ],
  "total": 45,
  "page": 1,
  "limit": 20,
  "has_more": true
}
```

---

### 4.3 Get Task Detail

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/tasks/{task_id}` |
| **Purpose** | Fetch full task detail including content payload and attached resources. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `task_id` | UUID | Task ID |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "title": "Writing Task 2: Opinion Essay",
  "skill": "writing",
  "task_type": "writing_task2",
  "duration_minutes": 40,
  "status": "in_progress",
  "priority": 5,
  "is_mandatory": true,
  "phase_index": 1,
  "order_index": 1,
  "scheduled_date": "2025-11-21",
  "due_at": "2025-11-21T23:59:00Z",
  "content_payload": {
    "prompt": "Some people believe that it is best to accept a bad situation...",
    "word_limit": 250,
    "task_type": "opinion_essay"
  },
  "resources": [
    {
      "id": "uuid",
      "title": "Sample Band 9 Essay",
      "type": "writing_sample",
      "url": "https://...",
      "relation": "supplementary"
    }
  ],
  "completion": null,
  "created_at": "2025-10-29T10:00:00Z"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | Task not found or not owned by user |

---

### 4.4 Start Task

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/tasks/{task_id}/start` |
| **Purpose** | Mark a task as in_progress. Records the start time for study session tracking. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `task_id` | UUID | Task ID |

**Request Body:** None

**Response (200 OK):**
```json
{
  "id": "uuid",
  "status": "in_progress",
  "started_at": "2025-11-21T10:00:00Z",
  "session_id": "uuid"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `conflict` | 409 | Task already completed or in progress |
| `not_found` | 404 | Task not found |

---

### 4.5 Complete Task

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/tasks/{task_id}/complete` |
| **Purpose** | Mark a task as completed. Records duration, triggers assessment if applicable, updates streak, awards XP. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `task_id` | UUID | Task ID |

**Request Body:**
```json
{
  "duration_minutes": 35,
  "output": {
    "essay_text": "In today's world, the debate about...",
    "word_count": 287
  },
  "notes": {}
}
```

**Validation:**
| Field | Rule |
|---|---|
| `duration_minutes` | Required, 1–240 |
| `output` | Conditional: required for writing/speaking tasks |
| `output.essay_text` | Required for writing, min 50 words |
| `output.audio_url` | Required for speaking, min 30 seconds |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "status": "completed",
  "completed_at": "2025-11-21T10:35:00Z",
  "duration_minutes": 35,
  "assessment": {
    "id": "uuid",
    "status": "processing",
    "estimated_seconds": 10
  },
  "xp_awarded": 40,
  "streak_updated": true,
  "daily_plan_progress": {
    "completed_tasks": 2,
    "total_tasks": 4,
    "completed_minutes": 50,
    "total_minutes": 75
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `conflict` | 409 | Task already completed |
| `validation_error` | 400 | Output validation failed |
| `not_found` | 404 | Task not found |

**Rate Limiting:** 30 req/min (each completion triggers AI + gamification updates).

---

### 4.6 Skip Task

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/tasks/{task_id}/skip` |
| **Purpose** | Skip a non-mandatory task. Marks it as `skipped` and adjusts the scheduler. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `task_id` | UUID | Task ID |

**Request Body:**
```json
{
  "reason": "too_difficult"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `reason` | Optional, one of: `too_difficult`, `not_relevant`, `already_know`, `no_time`, `other` |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "status": "skipped",
  "skipped_at": "2025-11-21T10:40:00Z",
  "replacement_task": {
    "id": "uuid",
    "title": "Alternative: Vocabulary Review",
    "duration_minutes": 15
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `conflict` | 409 | Task is mandatory; cannot be skipped |
| `not_found` | 404 | Task not found |

---

### 4.7 Get Overdue Tasks

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/tasks/overdue` |
| **Purpose** | Fetch all overdue (missed) tasks that need to be completed. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "count": 3,
  "total_overdue_minutes": 75,
  "tasks": [
    {
      "id": "uuid",
      "title": "Grammar Drill: Conditionals",
      "skill": "grammar",
      "duration_minutes": 15,
      "original_date": "2025-11-19",
      "days_overdue": 2,
      "priority": 4
    }
  ]
}
```

---

## 5. Resources Module

Base path: `/api/v1/resources`

### 5.1 Browse Resources

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/resources` |
| **Purpose** | Browse the resource catalog with filters and pagination. |

**Authentication:** Optional (recommendations personalized if authenticated)

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `skill` | string | — | Filter by primary skill |
| `resource_type` | string | — | youtube, pdf, website, vocab_sheet, grammar_guide, listening, writing_sample, speaking, practice_test, strategy |
| `provider` | string | — | british_council, idp, ielts_liz, ielts_advantage, e2_ielts, cambridge, ielts_online |
| `difficulty` | string | — | beginner, intermediate, advanced, all_levels |
| `min_rating` | number | — | Minimum student rating (1.0–5.0) |
| `max_duration` | int | — | Max duration in minutes |
| `search` | string | — | Full-text search query |
| `official_only` | bool | `false` | Only official resources |
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page |
| `sort` | string | `curator_rating` | `curator_rating`, `student_rating_avg`, `newest`, `popularity` |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "IELTS Writing Task 2 — Full Guide",
      "description": "Complete walkthrough of Task 2 essay structure",
      "provider": "e2_ielts",
      "resource_type": "youtube",
      "primary_skill": "writing_task2",
      "difficulty_level": "intermediate",
      "min_band": 5.0,
      "max_band": 7.5,
      "url": "https://youtube.com/watch?v=...",
      "duration_minutes": 25,
      "curator_rating": 4.8,
      "student_rating_avg": 4.6,
      "is_official": false,
      "tags": ["task2", "opinion_essay", "structure"],
      "is_bookmarked": true
    }
  ],
  "total": 142,
  "page": 1,
  "limit": 20,
  "has_more": true,
  "filters_applied": {
    "skill": "writing_task2",
    "difficulty": "intermediate"
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | Invalid filter value |

**Caching:** 5-minute cache for anonymous users; 1-minute cache for authenticated.

---

### 5.2 Search Resources

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/resources/search` |
| **Purpose** | Full-text search across resource titles, descriptions, and tags. |

**Authentication:** Optional

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `q` | string | — | **Required.** Search query |
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page |

**Response (200 OK):** Same structure as 5.1.

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | `q` parameter is required |

---

### 5.3 Get Resource Detail

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/resources/{resource_id}` |
| **Purpose** | Fetch full resource details including description, tags, and user-specific state. |

**Authentication:** Optional

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `resource_id` | UUID | Resource ID |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "title": "IELTS Writing Task 2 — Full Guide",
  "description": "Complete walkthrough of Task 2 essay structure by E2 IELTS.",
  "provider": "e2_ielts",
  "resource_type": "youtube",
  "primary_skill": "writing_task2",
  "secondary_skills": ["vocabulary", "grammar"],
  "difficulty_level": "intermediate",
  "min_band": 5.0,
  "max_band": 7.5,
  "target_band": null,
  "url": "https://youtube.com/watch?v=...",
  "duration_minutes": 25,
  "curator_rating": 4.8,
  "student_rating_avg": 4.6,
  "student_rating_count": 342,
  "is_official": false,
  "is_featured": true,
  "tags": ["task2", "opinion_essay", "structure", "academic"],
  "is_bookmarked": false,
  "completion_status": null,
  "created_at": "2025-01-15T10:00:00Z"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | Resource not found |

---

### 5.4 Log Resource View

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/resources/{resource_id}/view` |
| **Purpose** | Log a resource view for analytics. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `resource_id` | UUID | Resource ID |

**Request Body:**
```json
{
  "source": "recommendation",
  "session_id": "uuid"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `source` | Required, one of: `recommendation`, `search`, `bookmark`, `task_link`, `browse` |
| `session_id` | Optional, UUID |

**Response (200 OK):**
```json
{
  "message": "View logged"
}
```

---

### 5.5 Bookmark Resource

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/resources/{resource_id}/bookmark` |
| **Purpose** | Add a resource to the user's bookmarks. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `resource_id` | UUID | Resource ID |

**Request Body:**
```json
{
  "collection_name": "favorites",
  "notes": "Watch this after finishing Task 2 lesson"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `collection_name` | Optional, default `"default"`, max 50 chars |
| `notes` | Optional, max 500 chars |

**Response (201 Created):**
```json
{
  "id": "uuid",
  "resource_id": "uuid",
  "collection_name": "favorites",
  "notes": "Watch this after finishing Task 2 lesson",
  "created_at": "2025-11-21T10:00:00Z"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `conflict` | 409 | Already bookmarked |

---

### 5.6 Remove Bookmark

| Property | Value |
|---|---|
| **Method** | `DELETE` |
| **Endpoint** | `/api/v1/resources/{resource_id}/bookmark` |
| **Purpose** | Remove a bookmark. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `resource_id` | UUID | Resource ID |

**Response (200 OK):**
```json
{
  "message": "Bookmark removed"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | Bookmark not found |

---

### 5.7 List Bookmarks

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/bookmarks` |
| **Purpose** | List all bookmarks for the authenticated user. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `collection` | string | — | Filter by collection name |
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "resource": {
        "id": "uuid",
        "title": "IELTS Writing Task 2 Guide",
        "provider": "e2_ielts",
        "resource_type": "youtube",
        "url": "https://...",
        "duration_minutes": 25
      },
      "collection_name": "favorites",
      "notes": "Watch this after finishing Task 2 lesson",
      "created_at": "2025-11-21T10:00:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "limit": 20,
  "has_more": false,
  "collections": ["default", "favorites", "writing", "vocabulary"]
}
```

---

### 5.8 Mark Resource Completion

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/completions` |
| **Purpose** | Mark a resource as in_progress, completed, or abandoned. |

**Authentication:** Required

**Request Body:**
```json
{
  "resource_id": "uuid",
  "status": "completed",
  "time_spent_minutes": 22,
  "rating": 4,
  "review_notes": "Very helpful for understanding essay structure",
  "task_id": "uuid"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `resource_id` | Required, valid UUID |
| `status` | Required, `in_progress`, `completed`, or `abandoned` |
| `time_spent_minutes` | Optional, 1–600 |
| `rating` | Optional, 1–5 |
| `review_notes` | Optional, max 1000 chars |
| `task_id` | Optional, links to scheduler task |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "status": "completed",
  "completed_at": "2025-11-21T11:00:00Z",
  "xp_awarded": 10,
  "study_minutes": 22
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `conflict` | 409 | Already completed |
| `not_found` | 404 | Resource not found |

---

### 5.9 Get Recommendations

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/recommendations` |
| **Purpose** | Get personalized resource recommendations for the user. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 4 | Number of recommendations |
| `include_reason` | bool | `true` | Include AI-generated reason |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "resource": {
        "id": "uuid",
        "title": "Coherence & Cohesion: Linking Words",
        "provider": "ielts_liz",
        "resource_type": "pdf",
        "url": "https://...",
        "duration_minutes": 15
      },
      "reason": "Targets your weakest skill (Coherence & Cohesion) — improving this could boost your overall band",
      "reason_code": "skill_gap",
      "score": 92.5,
      "rank": 1
    }
  ],
  "total": 10,
  "generated_at": "2025-11-21T06:00:00Z"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | No recommendations available (no diagnostic?) |

---

### 5.10 Dismiss Recommendation

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/recommendations/{recommendation_id}/dismiss` |
| **Purpose** | Dismiss a recommendation. Excluded from future recommendations for 30 days. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `recommendation_id` | UUID | Recommendation ID |

**Request Body:** None

**Response (200 OK):**
```json
{
  "message": "Recommendation dismissed",
  "replacement": {
    "id": "uuid",
    "resource": { "title": "Alternative Resource", "url": "https://..." }
  }
}
```

---

## 6. Mock Tests Module

Base path: `/api/v1/mock-tests`

### 6.1 List Mock Tests

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/mock-tests` |
| **Purpose** | List all mock tests for the user (scheduled, in-progress, completed). |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `status` | string | — | `scheduled`, `in_progress`, `submitted`, `expired` |
| `page` | int | 1 | Page number |
| `limit` | int | 10 | Items per page |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "mock_number": 2,
      "test_type": "full_mock",
      "module": "academic",
      "status": "scheduled",
      "scheduled_date": "2025-12-01",
      "overall_band": null,
      "section_scores": null,
      "duration_seconds": 9900
    },
    {
      "id": "uuid",
      "mock_number": 1,
      "test_type": "full_mock",
      "module": "academic",
      "status": "submitted",
      "scheduled_date": "2025-11-15",
      "overall_band": 6.5,
      "section_scores": {
        "listening": 7.0,
        "reading": 6.5,
        "writing": 6.0,
        "speaking": 6.5
      },
      "submitted_at": "2025-11-15T12:45:00Z"
    }
  ],
  "total": 4,
  "page": 1,
  "limit": 10,
  "has_more": false,
  "next_mock": {
    "id": "uuid",
    "mock_number": 2,
    "scheduled_date": "2025-12-01"
  }
}
```

---

### 6.2 Get Mock Test Detail

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/mock-tests/{mock_id}` |
| **Purpose** | Fetch full mock test details including sections and instructions. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `mock_id` | UUID | Mock test ID |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "mock_number": 2,
  "test_type": "full_mock",
  "module": "academic",
  "status": "scheduled",
  "sections": [
    {
      "order": 1,
      "name": "Listening",
      "duration_minutes": 30,
      "total_questions": 40,
      "status": "pending"
    },
    {
      "order": 2,
      "name": "Reading",
      "duration_minutes": 60,
      "total_questions": 40,
      "status": "pending"
    },
    {
      "order": 3,
      "name": "Writing",
      "duration_minutes": 60,
      "tasks": [
        { "order": 1, "name": "Task 1", "prompt": "The chart below shows..." },
        { "order": 2, "name": "Task 2", "prompt": "Some people believe that..." }
      ],
      "status": "pending"
    },
    {
      "order": 4,
      "name": "Speaking",
      "duration_minutes": 15,
      "parts": [
        { "order": 1, "name": "Part 1: Introduction", "estimated_minutes": 4 },
        { "order": 2, "name": "Part 2: Long Turn", "estimated_minutes": 3 },
        { "order": 3, "name": "Part 3: Discussion", "estimated_minutes": 8 }
      ],
      "status": "pending"
    }
  ],
  "instructions": {
    "duration": "~2 hours 45 minutes",
    "requirements": ["Find a quiet room", "Stable internet", "Headphones recommended"]
  },
  "prep_day": {
    "date": "2025-11-30",
    "is_light_review": true,
    "tasks": [
      { "title": "Review past mistakes", "duration_minutes": 15 }
    ]
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | Mock test not found |

---

### 6.3 Start Mock Test

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/mock-tests/{mock_id}/start` |
| **Purpose** | Start a scheduled mock test. Changes status to `in_progress` and records start time. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `mock_id` | UUID | Mock test ID |

**Request Body:** None

**Response (200 OK):**
```json
{
  "id": "uuid",
  "status": "in_progress",
  "started_at": "2025-12-01T09:00:00Z",
  "current_section": "listening",
  "time_remaining_seconds": 9900
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `conflict` | 409 | Mock test already started or completed |
| `not_found` | 404 | Mock test not found |

---

### 6.4 Submit Section

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/mock-tests/{mock_id}/sections/{section_order}/submit` |
| **Purpose** | Submit answers for a single mock test section. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `mock_id` | UUID | Mock test ID |
| `section_order` | int | 1–4 (Listening=1, Reading=2, Writing=3, Speaking=4) |

**Request Body:**
```json
{
  "answers": {
    "essay_text": "In today's world...",
    "word_count": 312
  },
  "time_spent_seconds": 3540
}
```

**Validation:**
| Section | Validation |
|---|---|
| Listening | 40 answers (A/B/C/D mapping) |
| Reading | 40 answers (multiple types) |
| Writing | Min 150 words (Task 1), min 250 words (Task 2) |
| Speaking | Audio URL, min 30 seconds per part |

**Response (200 OK):**
```json
{
  "section_order": 3,
  "status": "submitted",
  "next_section": {
    "order": 4,
    "name": "Speaking",
    "duration_minutes": 15
  },
  "is_last_section": false
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | Missing or invalid answers |
| `conflict` | 409 | Section already submitted |
| `not_found` | 404 | Mock test or section not found |

---

### 6.5 Submit Full Mock Test

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/mock-tests/{mock_id}/submit` |
| **Purpose** | Submit the entire mock test (all sections). Automatically submits any unsaved sections. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `mock_id` | UUID | Mock test ID |

**Request Body:** None

**Response (200 OK):**
```json
{
  "id": "uuid",
  "status": "submitted",
  "submitted_at": "2025-12-01T11:45:00Z",
  "overall_band": null,
  "results_pending": true,
  "estimated_analysis_seconds": 30
}
```

---

### 6.6 Get Mock Test Results

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/mock-tests/{mock_id}/results` |
| **Purpose** | Fetch the band scores and analysis for a completed mock test. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `mock_id` | UUID | Mock test ID |

**Response (200 OK):**
```json
{
  "id": "uuid",
  "mock_number": 1,
  "test_type": "full_mock",
  "overall_band": 6.5,
  "section_scores": {
    "listening": 7.0,
    "reading": 6.5,
    "writing": 6.0,
    "speaking": 6.5
  },
  "criteria_scores": {
    "task_response": 6.5,
    "coherence_cohesion": 6.0,
    "lexical_resource": 6.5,
    "grammar": 6.0,
    "fluency_coherence": 6.5,
    "pronunciation": 7.0,
    "listening": 7.0,
    "reading": 6.5
  },
  "comparison": {
    "vs_predicted": -0.3,
    "vs_target": -1.0,
    "vs_previous_mock": "+0.5"
  },
  "mistake_analysis": {
    "listening": [
      { "question_number": 12, "user_answer": "B", "correct_answer": "C", "topic": "Map labeling", "explanation": "The speaker mentioned the library on the east side, not the north." }
    ],
    "reading": [],
    "writing": {
      "strengths": ["Clear position throughout", "Good vocabulary range"],
      "weaknesses": ["Cohesion between paragraphs", "Limited use of complex structures"]
    }
  },
  "roadmap_adjustment": {
    "needs_recalibration": true,
    "new_focus_areas": ["Coherence & Cohesion", "Complex grammar"],
    "adjusted_confidence": 0.75
  }
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | Results not ready or mock not found |
| `conflict` | 409 | Results still processing |

---

### 6.7 Get Mistake Review

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/mock-tests/{mock_id}/review` |
| **Purpose** | Detailed mistake analysis for review. Includes full answer key and explanations. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `mock_id` | UUID | Mock test ID |

**Response (200 OK):**
```json
{
  "sections": [
    {
      "name": "Listening",
      "total_questions": 40,
      "correct": 32,
      "incorrect": 8,
      "score_pct": 80,
      "band_equivalent": 7.0,
      "mistakes": [
        {
          "question_number": 12,
          "question_type": "map_labeling",
          "user_answer": "B",
          "correct_answer": "C",
          "explanation": "The speaker said 'the library is on the east side, opposite the park'.",
          "topic": "Section 2: Map labeling"
        }
      ],
      "weak_areas": ["Map labeling", "Multiple choice (Section 3)"]
    }
  ],
  "recommended_resources": [
    {
      "title": "Listening Map Labeling Practice",
      "url": "https://...",
      "reason": "Focus on your weakest listening area"
    }
  ]
}
```

---

## 7. Progress Module

Base path: `/api/v1/progress`

### 7.1 Band Score Timeline

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/progress/timeline` |
| **Purpose** | Fetch the user's band score history over time for charting. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `range` | string | `30d` | `7d`, `30d`, `90d`, `all` |
| `criterion` | string | `overall` | `overall`, `task_response`, `coherence_cohesion`, `lexical_resource`, `grammar`, `fluency_coherence`, `pronunciation` |

**Response (200 OK):**
```json
{
  "data": [
    {
      "date": "2025-10-01",
      "overall": 6.0,
      "task_response": 6.5,
      "coherence_cohesion": 5.5,
      "lexical_resource": 6.0,
      "grammar": 6.0
    },
    {
      "date": "2025-10-15",
      "overall": 6.5,
      "task_response": 7.0,
      "coherence_cohesion": 6.0,
      "lexical_resource": 6.5,
      "grammar": 6.5
    }
  ],
  "target_band": 7.5,
  "trend": "+0.5 over 30 days",
  "points_used": 6
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | No assessment data available |

---

### 7.2 Per-Skill Progress

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/progress/skills` |
| **Purpose** | Fetch the latest scores per skill criterion with gap to target. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "skills": [
    {
      "criterion": "task_response",
      "label": "Task Response",
      "current_score": 7.0,
      "target_score": 7.5,
      "gap": -0.5,
      "trend": "+0.5",
      "last_assessment_date": "2025-11-18"
    },
    {
      "criterion": "coherence_cohesion",
      "label": "Coherence & Cohesion",
      "current_score": 6.0,
      "target_score": 7.5,
      "gap": -1.5,
      "trend": "+0.0",
      "last_assessment_date": "2025-11-15"
    }
  ],
  "biggest_gap": {
    "criterion": "coherence_cohesion",
    "gap": -1.5,
    "insight": "Your Coherence & Cohesion is your biggest bottleneck. Improving this will have the highest impact."
  }
}
```

---

### 7.3 Streak Data

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/progress/streaks` |
| **Purpose** | Fetch the user's streak data. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "daily": {
    "current": 5,
    "longest": 14,
    "last_activity_date": "2025-11-21",
    "is_at_risk": false,
    "grace_remaining_hours": 18
  },
  "weekly": {
    "current": 3,
    "longest": 8,
    "qualifying_weeks": 12
  },
  "monthly": {
    "current": 1,
    "longest": 3,
    "qualifying_months": 4
  },
  "freeze_count": 2,
  "repair_available": true,
  "last_repair_date": null
}
```

---

### 7.4 Study Time Distribution

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/progress/study-time` |
| **Purpose** | Fetch study time breakdown by skill. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `range` | string | `30d` | `7d`, `30d`, `90d`, `all` |

**Response (200 OK):**
```json
{
  "total_minutes": 2450,
  "by_skill": [
    { "skill": "writing", "minutes": 850, "percentage": 34.7 },
    { "skill": "speaking", "minutes": 450, "percentage": 18.4 },
    { "skill": "vocabulary", "minutes": 380, "percentage": 15.5 },
    { "skill": "grammar", "minutes": 320, "percentage": 13.1 },
    { "skill": "mock_tests", "minutes": 300, "percentage": 12.2 },
    { "skill": "reading", "minutes": 100, "percentage": 4.1 },
    { "skill": "listening", "minutes": 50, "percentage": 2.0 }
  ],
  "daily_average": 45,
  "range": "30d"
}
```

---

### 7.5 Assessment History

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/progress/history` |
| **Purpose** | Fetch paginated assessment history. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page |
| `task_type` | string | — | Filter: `Writing Task 1`, `Writing Task 2`, `Speaking`, `Mock Test` |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "task_type": "Writing Task 2",
      "topic": "Education",
      "band_score": 7.0,
      "criteria_scores": {
        "task_response": 7.0,
        "coherence_cohesion": 6.5,
        "lexical_resource": 7.0,
        "grammar": 6.5
      },
      "created_at": "2025-11-18T10:30:00Z",
      "status": "improved"
    }
  ],
  "total": 24,
  "page": 1,
  "limit": 20,
  "has_more": true
}
```

---

## 8. Analytics Module

Base path: `/api/v1/analytics`

### 8.1 Analytics Overview

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/analytics/overview` |
| **Purpose** | Fetch high-level KPIs for the analytics dashboard header. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "overall_band": {
    "current": 6.8,
    "trend": "+0.3",
    "trend_direction": "up"
  },
  "writing_avg": {
    "current": 6.5,
    "trend": "+0.5",
    "trend_direction": "up"
  },
  "speaking_avg": {
    "current": 7.0,
    "trend": "-0.2",
    "trend_direction": "down"
  },
  "tests_taken": {
    "total": 12,
    "this_week": 2
  },
  "study_hours": {
    "total": 45,
    "this_week": 5.5
  },
  "days_until_exam": 24,
  "predicted_band": 7.0,
  "confidence": 0.72
}
```

---

### 8.2 Band Score Trends

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/analytics/trends` |
| **Purpose** | Fetch band score trend data series for line chart. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `range` | string | `30d` | `7d`, `30d`, `90d`, `all` |

**Response (200 OK):**
```json
{
  "series": [
    {
      "criterion": "overall",
      "label": "Overall Band",
      "data": [
        { "date": "2025-10-01", "value": 6.0 },
        { "date": "2025-10-15", "value": 6.5 },
        { "date": "2025-11-01", "value": 6.5 },
        { "date": "2025-11-15", "value": 6.8 }
      ]
    },
    {
      "criterion": "writing",
      "label": "Writing Average",
      "data": [
        { "date": "2025-10-01", "value": 5.5 },
        { "date": "2025-10-15", "value": 6.0 },
        { "date": "2025-11-01", "value": 6.5 },
        { "date": "2025-11-15", "value": 6.5 }
      ]
    },
    {
      "criterion": "speaking",
      "label": "Speaking Average",
      "data": [
        { "date": "2025-10-01", "value": 6.5 },
        { "date": "2025-10-15", "value": 7.0 },
        { "date": "2025-11-01", "value": 7.0 },
        { "date": "2025-11-15", "value": 7.0 }
      ]
    }
  ],
  "target_band": 7.5,
  "target_line": [
    { "date": "2025-10-01", "value": 7.5 },
    { "date": "2025-11-21", "value": 7.5 }
  ]
}
```

---

### 8.3 Skill Gap Analysis

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/analytics/skill-gaps` |
| **Purpose** | Fetch per-criterion current vs target for bar chart. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "target_band": 7.5,
  "gaps": [
    { "criterion": "task_response", "label": "Task Response", "current": 7.0, "target": 7.5, "gap": -0.5, "gap_pct": 6.7 },
    { "criterion": "coherence_cohesion", "label": "Coherence & Cohesion", "current": 6.0, "target": 7.5, "gap": -1.5, "gap_pct": 20.0 },
    { "criterion": "lexical_resource", "label": "Lexical Resource", "current": 7.0, "target": 7.5, "gap": -0.5, "gap_pct": 6.7 },
    { "criterion": "grammar", "label": "Grammatical Range", "current": 6.5, "target": 7.5, "gap": -1.0, "gap_pct": 13.3 }
  ],
  "biggest_bottleneck": {
    "criterion": "coherence_cohesion",
    "gap": -1.5,
    "insight": "Your Coherence & Cohesion is your biggest bottleneck. Improving this will have the highest impact on your overall band."
  }
}
```

---

### 8.4 Band Prediction

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/analytics/prediction` |
| **Purpose** | Fetch the predicted band score with confidence and factors. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "predicted_band": 7.0,
  "target_band": 7.5,
  "confidence": 0.72,
  "confidence_label": "moderate",
  "assessment_count": 12,
  "factors": [
    { "factor": "diagnostic_band", "weight": 0.25, "value": 6.5 },
    { "factor": "current_avg_band", "weight": 0.35, "value": 6.8 },
    { "factor": "hours_completed", "weight": 0.10, "value": 45 },
    { "factor": "streak_length", "weight": 0.10, "value": 5 },
    { "factor": "mock_test_avg", "weight": 0.10, "value": 6.5 },
    { "factor": "tasks_completed_30d", "weight": 0.10, "value": 28 }
  ],
  "explanation": "Predicted Band 7.0 (±0.5) based on your last 12 assessments. Lexical Resource is your highest-leverage skill."
}
```

---

### 8.5 Export Data

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/analytics/export` |
| **Purpose** | Export user data as PDF or CSV. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `format` | string | `pdf` | `pdf` or `csv` |

**Response (200 OK):**
- **PDF:** Binary file download (`application/pdf`)
- **CSV:** Text file download (`text/csv`)

**Headers:** `Content-Disposition: attachment; filename="ielts-progress-report-2025-11-21.pdf"`

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | Invalid format parameter |
| `internal_error` | 500 | Report generation failed |

**Rate Limiting:** 5 req/hour (report generation is expensive).

---

## 9. Notifications Module

Base path: `/api/v1/notifications`

### 9.1 List Notifications

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/notifications` |
| **Purpose** | Fetch the user's notification feed. |

**Authentication:** Required

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page |
| `unread_only` | bool | `false` | Only unread notifications |
| `type` | string | — | Filter: `ai_feedback`, `reminder`, `system`, `gamification`, `streak` |

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "uuid",
      "type": "ai_feedback",
      "title": "Writing Assessment Ready",
      "body": "Your Writing Task 2 essay has been graded. You scored Band 7.0.",
      "is_read": false,
      "metadata": {
        "assessment_id": "uuid",
        "band_score": 7.0,
        "url": "/writing/result/uuid"
      },
      "created_at": "2025-11-21T10:35:00Z"
    },
    {
      "id": "uuid",
      "type": "streak",
      "title": "Streak at Risk!",
      "body": "You haven't studied today. Complete a task to keep your 5-day streak alive!",
      "is_read": true,
      "metadata": {
        "streak": 5,
        "url": "/dashboard"
      },
      "created_at": "2025-11-21T18:00:00Z"
    }
  ],
  "total": 15,
  "unread_count": 3,
  "page": 1,
  "limit": 20,
  "has_more": false
}
```

---

### 9.2 Mark as Read

| Property | Value |
|---|---|
| **Method** | `PUT` |
| **Endpoint** | `/api/v1/notifications/{notification_id}/read` |
| **Purpose** | Mark a single notification as read. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `notification_id` | UUID | Notification ID |

**Request Body:** None

**Response (200 OK):**
```json
{
  "id": "uuid",
  "is_read": true,
  "read_at": "2025-11-21T19:00:00Z"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | Notification not found |

---

### 9.3 Mark All as Read

| Property | Value |
|---|---|
| **Method** | `PUT` |
| **Endpoint** | `/api/v1/notifications/read-all` |
| **Purpose** | Mark all unread notifications as read. |

**Authentication:** Required

**Request Body:** None

**Response (200 OK):**
```json
{
  "message": "All notifications marked as read",
  "updated_count": 3
}
```

---

### 9.4 Delete Notification

| Property | Value |
|---|---|
| **Method** | `DELETE` |
| **Endpoint** | `/api/v1/notifications/{notification_id}` |
| **Purpose** | Delete a single notification. |

**Authentication:** Required

**Path Parameters:**
| Param | Type | Description |
|---|---|---|
| `notification_id` | UUID | Notification ID |

**Response (200 OK):**
```json
{
  "message": "Notification deleted"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | Notification not found |

---

### 9.5 Update Notification Preferences

| Property | Value |
|---|---|
| **Method** | `PUT` |
| **Endpoint** | `/api/v1/notifications/settings` |
| **Purpose** | Update the user's notification preferences. |

**Authentication:** Required

**Request Body:**
```json
{
  "push_enabled": true,
  "email_enabled": false,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "08:00",
  "subscribed_types": ["ai_feedback", "streak", "reminder", "system", "gamification"]
}
```

**Validation:**
| Field | Rule |
|---|---|
| `push_enabled` | Boolean |
| `email_enabled` | Boolean |
| `quiet_hours_start` | HH:MM format |
| `quiet_hours_end` | HH:MM format |
| `subscribed_types` | Array of valid notification types |

**Response (200 OK):**
```json
{
  "message": "Preferences updated",
  "preferences": {
    "push_enabled": true,
    "email_enabled": false,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "subscribed_types": ["ai_feedback", "streak", "reminder", "system", "gamification"]
  }
}
```

---

## 10. AI Module

Base path: `/api/v1/ai`

### 10.1 Assess Writing

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/ai/assess/writing` |
| **Purpose** | Submit a writing task for AI assessment. Returns band score, criteria scores, feedback, and corrections. |

**Authentication:** Required

**Request Body:**
```json
{
  "task_type": "Writing Task 2",
  "essay_text": "In today's world, the debate about education has become increasingly prominent...",
  "prompt": "Some people believe that it is best to accept a bad situation...",
  "word_count": 287
}
```

**Validation:**
| Field | Rule |
|---|---|
| `task_type` | Required, `Writing Task 1` or `Writing Task 2` |
| `essay_text` | Required, min 50 words, max 500 words |
| `prompt` | Optional |
| `word_count` | Optional, auto-calculated if omitted |

**Response (200 OK):**
```json
{
  "assessment_id": "uuid",
  "band_score": 7.0,
  "criteria_scores": {
    "task_response": 7.0,
    "coherence_cohesion": 6.5,
    "lexical_resource": 7.0,
    "grammar": 6.5
  },
  "feedback": "Your essay has a clear position and good vocabulary. Work on using more cohesive devices to link paragraphs.",
  "corrections": [
    {
      "original": "moreover",
      "suggestion": "Furthermore",
      "type": "vocabulary",
      "explanation": "'Furthermore' is more formal in academic writing"
    }
  ],
  "strengths": ["Clear thesis statement", "Good use of examples"],
  "weaknesses": ["Limited range of cohesive devices", "Some subject-verb agreement errors"],
  "model_version": "gpt-4o-mini-v2",
  "processing_time_ms": 3420
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | Essay too short or too long |
| `ai_service_unavailable` | 503 | AI provider unavailable |
| `rate_limited` | 429 | Too many AI requests |

**Rate Limiting:** 20 req/min (shared across all AI endpoints).

---

### 10.2 Assess Speaking

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/ai/assess/speaking` |
| **Purpose** | Submit a speaking recording for AI assessment. Requires audio URL (pre-uploaded) or base64 audio. |

**Authentication:** Required

**Request Body:**
```json
{
  "task_type": "Speaking Part 1",
  "audio_url": "https://storage.supabase.co/audio/uuid.webm",
  "duration_seconds": 85,
  "prompt": "Tell me about your hometown"
}
```

**Validation:**
| Field | Rule |
|---|---|
| `task_type` | Required, `Speaking Part 1`, `Speaking Part 2`, or `Speaking Part 3` |
| `audio_url` | Required, HTTPS URL to Supabase Storage |
| `duration_seconds` | Required, min 30, max 120 |
| `prompt` | Optional |

**Response (200 OK):**
```json
{
  "assessment_id": "uuid",
  "transcript": "Well, I live in a coastal city in the south of the country...",
  "band_score": 6.5,
  "criteria_scores": {
    "fluency_coherence": 6.5,
    "lexical_resource": 7.0,
    "grammar": 6.5,
    "pronunciation": 7.0
  },
  "feedback": "Good fluency with some hesitation. Try to reduce filler words and expand your answers with more specific examples.",
  "strengths": ["Natural intonation", "Good pronunciation"],
  "weaknesses": ["Filler words ('well', 'you know')", "Limited complex sentence structures"],
  "model_version": "whisper-v2+gpt-4o-mini-v2",
  "processing_time_ms": 5200
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | Audio too short or missing |
| `ai_service_unavailable` | 503 | Speech-to-text or AI unavailable |

**Rate Limiting:** 10 req/min (speech processing is expensive).

---

### 10.3 Analyze Diagnostic

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/ai/diagnostic/analyze` |
| **Purpose** | Analyze all 3 diagnostic sections and produce baseline band, strengths, weaknesses, and CEFR level. |

**Authentication:** Required

**Request Body:**
```json
{
  "essay": {
    "text": "In today's world...",
    "band_score": 6.5,
    "criteria_scores": { "task_response": 6.5, "coherence_cohesion": 6.0, "lexical_resource": 6.5, "grammar": 6.0 }
  },
  "speaking": {
    "transcript": "Well, I live in...",
    "band_score": 7.0,
    "criteria_scores": { "fluency_coherence": 7.0, "lexical_resource": 7.0, "grammar": 6.5, "pronunciation": 7.5 }
  },
  "vocabulary": {
    "score": 7,
    "total": 10,
    "weak_categories": ["academic verbs", "collocations"]
  }
}
```

**Response (200 OK):**
```json
{
  "diagnostic_id": "uuid",
  "overall_band": 6.5,
  "cefr_level": "B2",
  "cefr_label": "Upper Intermediate",
  "per_criterion_scores": {
    "task_response": 6.5,
    "coherence_cohesion": 6.0,
    "lexical_resource": 6.5,
    "grammar": 6.0,
    "fluency_coherence": 7.0,
    "pronunciation": 7.5
  },
  "strengths": ["Task Response", "Pronunciation", "Vocabulary Variety"],
  "weaknesses": ["Complex Sentence Structures", "Coherence & Cohesion", "Filler Words in Speaking"],
  "target_gap": -1.0,
  "recommended_focus": "Coherence & Cohesion",
  "ai_tip": "Focus your first week on improving your use of cohesive devices. This could boost your writing score by 0.5 points alone.",
  "model_version": "diagnostic-analyzer-v2"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | Missing required section data |
| `ai_service_unavailable` | 503 | AI provider unavailable |

---

### 10.4 Generate Roadmap (AI)

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/ai/roadmap/generate` |
| **Purpose** | AI-powered roadmap generation from diagnostic results. This is the internal endpoint called by the Roadmap Generator service. |

**Authentication:** Required (admin/service)

**Request Body:**
```json
{
  "diagnostic_band": 6.5,
  "target_band": 7.5,
  "exam_date": "2025-12-15",
  "daily_minutes": 60,
  "module": "academic",
  "skill_gaps": {
    "task_response": 6.5,
    "coherence_cohesion": 6.0,
    "lexical_resource": 6.5,
    "grammar": 6.0,
    "fluency_coherence": 7.0,
    "pronunciation": 7.5
  },
"strengths": ["Task Response", "Pronunciation"],
  "weaknesses": ["Coherence & Cohesion", "Grammar"]
}
```

**Response (200 OK):**
```json
{
  "phases": [
    {
      "name": "Foundation",
      "weight": 0.30,
      "duration_weeks": 4,
      "description": "Mastering the basics and grammar fundamentals",
      "focus_skills": ["grammar", "vocabulary"],
      "task_distribution": {
        "grammar": 0.40,
        "vocabulary": 0.30,
        "writing": 0.15,
        "speaking": 0.15
      },
      "tasks_per_week": 5,
      "estimated_hours": 20
    },
    {
      "name": "Skill Building",
      "weight": 0.30,
      "duration_weeks": 4,
      "description": "Deep dive into complex structures and fluency techniques",
      "focus_skills": ["writing", "speaking", "vocabulary"],
      "task_distribution": {
        "writing": 0.30,
        "speaking": 0.25,
        "vocabulary": 0.25,
        "grammar": 0.20
      },
      "tasks_per_week": 7,
      "estimated_hours": 28
    },
    {
      "name": "Advanced Techniques",
      "weight": 0.20,
      "duration_weeks": 3,
      "description": "Mastering complex arguments and sophisticated language",
      "focus_skills": ["writing", "speaking", "reading"],
      "task_distribution": {
        "writing": 0.35,
        "speaking": 0.25,
        "reading": 0.20,
        "listening": 0.20
      },
      "tasks_per_week": 6,
      "estimated_hours": 18
    },
    {
      "name": "Mock Test Marathon",
      "weight": 0.15,
      "duration_weeks": 2,
      "description": "Full-length timed practices and performance analysis",
      "focus_skills": ["mock", "review"],
      "task_distribution": {
        "mock": 0.60,
        "review": 0.40
      },
      "tasks_per_week": 4,
      "estimated_hours": 12
    },
    {
      "name": "Final Revision",
      "weight": 0.05,
      "duration_weeks": 1,
      "description": "Protected revision window — light review and exam strategy",
      "focus_skills": ["review", "strategy"],
      "task_distribution": {
        "review": 0.70,
        "strategy": 0.30
      },
      "tasks_per_week": 3,
      "estimated_hours": 5
    }
  ],
  "estimated_total_hours": 83,
  "confidence_score": 0.82,
  "model_version": "roadmap-generator-v2"
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `validation_error` | 400 | Missing diagnostic data |
| `ai_service_unavailable` | 503 | AI provider unavailable |

**Rate Limiting:** 5 req/min.

---

### 10.5 Predict Band

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/ai/predict/band` |
| **Purpose** | Predict the user's expected band score based on historical data, study volume, and streak information. |

**Authentication:** Required

**Request Body:** None (uses server-side data)

**Response (200 OK):**
```json
{
  "predicted_band": 7.0,
  "confidence": 0.72,
  "confidence_label": "moderate",
  "model_version": "band-predictor-v2",
  "features_used": {
    "diagnostic_band": 6.5,
    "current_avg_band": 6.8,
    "hours_completed": 45,
    "streak_length": 5,
    "mock_test_avg": 6.5,
    "tasks_completed_30d": 28
  },
  "explanation": "Predicted Band 7.0 (±0.5) based on your last 12 assessments. Lexical Resource is your highest-leverage skill."
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | Insufficient assessment data for prediction |
| `ai_service_unavailable` | 503 | AI provider unavailable |

**Rate Limiting:** 10 req/min.

---

### 10.6 Get Brain State

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/ai/brain/state` |
| **Purpose** | Fetch the full AI Brain live state for the user. |

**Authentication:** Required

**Response (200 OK):**
```json
{
  "prediction": {
    "predicted_band": 7.0,
    "confidence": 0.72
  },
  "readiness": {
    "score": 72,
    "level": "on_track",
    "components": {
      "consistency": 80,
      "skill_coverage": 65,
      "band_proximity": 70
    }
  },
  "risk": {
    "score": 28,
    "level": "low",
    "factors": ["Speaking fluency plateau", "Low mock test frequency"],
    "mitigations": ["Increase speaking practice to 3x/week", "Schedule Mock Test #2"]
  },
  "probability": {
    "target_band": 7.5,
    "probability": 0.65,
    "optimistic": 0.78,
    "pessimistic": 0.52
  },
  "recommended_hours": {
    "total_remaining": 38,
    "daily_target": 45,
    "current_daily_avg": 35
  },
  "weakest_topics": [
    { "skill": "coherence_cohesion", "score": 6.0, "gap": -1.5, "impact": "high" },
    { "skill": "grammar", "score": 6.5, "gap": -1.0, "impact": "medium" }
  ],
  "next_best_tasks": [
    {
      "task_id": "uuid",
      "title": "Coherence & Cohesion: Linking Words Exercise",
      "skill": "writing",
      "duration_minutes": 15,
      "reason": "Targets your biggest bottleneck",
      "expected_impact": "+0.3 band on Coherence & Cohesion"
    }
  ]
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `not_found` | 404 | No assessment data available for AI Brain state |
| `internal_error` | 500 | Brain computation failed |

**Caching:** 60-second server-side cache; invalidated on assessment completion.

---

### 10.7 Force Recompute (Admin)

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/ai/brain/recompute` |
| **Purpose** | Force a full recompute of the AI Brain state. |

**Authentication:** Required (admin)

**Request Body:** None

**Response (200 OK):**
```json
{
  "message": "Brain state recomputed",
  "computation_time_ms": 245
}
```

**Error Responses:**
| Code | Status | Condition |
|---|---|---|
| `forbidden` | 403 | User is not an admin |
| `internal_error` | 500 | Computation failed |

**Rate Limiting:** 10 req/hour.

---

## 11. Health & System Module

Base path: `/api/v1`

### 11.1 Health Check

| Property | Value |
|---|---|
| **Method** | `GET` |
| **Endpoint** | `/api/v1/health` |
| **Purpose** | Verify the API is running and all critical dependencies are reachable. |

**Authentication:** None

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "IELTS AI Coach",
  "version": "1.0.0",
  "checks": {
    "database": { "status": "healthy", "latency_ms": 12 },
    "ai_provider": { "status": "healthy", "provider": "openai" },
    "cache": { "status": "healthy", "provider": "redis" }
  },
  "uptime_seconds": 123456
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "degraded",
  "service": "IELTS AI Coach",
  "version": "1.0.0",
  "checks": {
    "database": { "status": "healthy", "latency_ms": 15 },
    "ai_provider": { "status": "unhealthy", "error": "OpenAI API returned 503" },
    "cache": { "status": "healthy", "provider": "redis" }
  }
}
```

---

## 12. Webhook & Realtime Events

### 12.1 Realtime Channels (Supabase Realtime)

| Channel | Event | Payload | Trigger |
|---|---|---|---|
| `notifications:{user_id}` | INSERT | notification data | New notification created |
| `gamification:{user_id}` | UPDATE | xp, level, streak, achievement | XP award, level up, streak change |
| `roadmap:{user_id}` | UPDATE | status, version | Roadmap generation complete |
| `assessment:{user_id}` | INSERT | id, band_score, task_type | New assessment result ready |
| `mission:{user_id}` | UPDATE | date, completed_tasks, total_tasks | Task completion updates daily plan |

### 12.2 Webhook Endpoints (External Integrations)

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Endpoint** | `/api/v1/webhooks/supabase/auth` |
| **Purpose** | Receive auth events from Supabase (user created, deleted). |

**Authentication:** Webhook secret (Bearer token)

**Response (200 OK):**
```json
{
  "received": true
}
```

---

## Appendix A: Endpoint Summary Table

| Module | Method | Endpoint | Auth | Rate Limit |
|---|---|---|---|---|
| Auth | POST | `/api/v1/auth/signup` | No | 5/min |
| Auth | POST | `/api/v1/auth/login` | No | 5/min |
| Auth | POST | `/api/v1/auth/logout` | Yes | -- |
| Auth | POST | `/api/v1/auth/forgot-password` | No | 3/hr |
| Auth | POST | `/api/v1/auth/reset-password` | No | -- |
| Auth | GET | `/api/v1/auth/me` | Yes | -- |
| Auth | PUT | `/api/v1/auth/me` | Yes | -- |
| Auth | PUT | `/api/v1/auth/goals` | Yes | 10/min |
| Auth | POST | `/api/v1/auth/refresh` | No | -- |
| Auth | POST | `/api/v1/auth/oauth/google` | No | 5/min |
| Dashboard | GET | `/api/v1/dashboard/overview` | Yes | 60/min |
| Dashboard | GET | `/api/v1/dashboard/mission` | Yes | 60/min |
| Dashboard | GET | `/api/v1/dashboard/skills` | Yes | 60/min |
| Dashboard | GET | `/api/v1/dashboard/progress` | Yes | 60/min |
| Dashboard | GET | `/api/v1/dashboard/xp` | Yes | 60/min |
| Dashboard | GET | `/api/v1/dashboard/continue` | Yes | 60/min |
| Roadmap | POST | `/api/v1/roadmap/generate` | Yes | 3/hr |
| Roadmap | GET | `/api/v1/roadmap` | Yes | 30/min |
| Roadmap | POST | `/api/v1/roadmap/regenerate` | Yes | 3/hr |
| Roadmap | GET | `/api/v1/roadmap/history` | Yes | 30/min |
| Roadmap | GET | `/api/v1/roadmap/phases/{id}` | Yes | 30/min |
| Tasks | GET | `/api/v1/tasks/today` | Yes | 60/min |
| Tasks | GET | `/api/v1/tasks` | Yes | 60/min |
| Tasks | GET | `/api/v1/tasks/{id}` | Yes | 60/min |
| Tasks | POST | `/api/v1/tasks/{id}/start` | Yes | 30/min |
| Tasks | POST | `/api/v1/tasks/{id}/complete` | Yes | 30/min |
| Tasks | POST | `/api/v1/tasks/{id}/skip` | Yes | 10/min |
| Tasks | GET | `/api/v1/tasks/overdue` | Yes | 30/min |
| Resources | GET | `/api/v1/resources` | Optional | 60/min |
| Resources | GET | `/api/v1/resources/search` | Optional | 60/min |
| Resources | GET | `/api/v1/resources/{id}` | Optional | 60/min |
| Resources | POST | `/api/v1/resources/{id}/view` | Yes | 60/min |
| Resources | POST | `/api/v1/resources/{id}/bookmark` | Yes | 30/min |
| Resources | DELETE | `/api/v1/resources/{id}/bookmark` | Yes | 30/min |
| Resources | GET | `/api/v1/bookmarks` | Yes | 60/min |
| Resources | POST | `/api/v1/completions` | Yes | 30/min |
| Resources | GET | `/api/v1/recommendations` | Yes | 30/min |
| Resources | POST | `/api/v1/recommendations/{id}/dismiss` | Yes | 30/min |
| Mock Tests | GET | `/api/v1/mock-tests` | Yes | 30/min |
| Mock Tests | GET | `/api/v1/mock-tests/{id}` | Yes | 30/min |
| Mock Tests | POST | `/api/v1/mock-tests/{id}/start` | Yes | 10/min |
| Mock Tests | POST | `/api/v1/mock-tests/{id}/sections/{order}/submit` | Yes | 10/min |
| Mock Tests | POST | `/api/v1/mock-tests/{id}/submit` | Yes | 10/min |
| Mock Tests | GET | `/api/v1/mock-tests/{id}/results` | Yes | 30/min |
| Mock Tests | GET | `/api/v1/mock-tests/{id}/review` | Yes | 30/min |
| Progress | GET | `/api/v1/progress/timeline` | Yes | 60/min |
| Progress | GET | `/api/v1/progress/skills` | Yes | 60/min |
| Progress | GET | `/api/v1/progress/streaks` | Yes | 60/min |
| Progress | GET | `/api/v1/progress/study-time` | Yes | 60/min |
| Progress | GET | `/api/v1/progress/history` | Yes | 60/min |
| Analytics | GET | `/api/v1/analytics/overview` | Yes | 60/min |
| Analytics | GET | `/api/v1/analytics/trends` | Yes | 60/min |
| Analytics | GET | `/api/v1/analytics/skill-gaps` | Yes | 60/min |
| Analytics | GET | `/api/v1/analytics/prediction` | Yes | 30/min |
| Analytics | GET | `/api/v1/analytics/export` | Yes | 5/hr |
| Notifications | GET | `/api/v1/notifications` | Yes | 60/min |
| Notifications | PUT | `/api/v1/notifications/{id}/read` | Yes | 60/min |
| Notifications | PUT | `/api/v1/notifications/read-all` | Yes | 30/min |
| Notifications | DELETE | `/api/v1/notifications/{id}` | Yes | 30/min |
| Notifications | PUT | `/api/v1/notifications/settings` | Yes | 30/min |
| AI | POST | `/api/v1/ai/assess/writing` | Yes | 20/min |
| AI | POST | `/api/v1/ai/assess/speaking` | Yes | 10/min |
| AI | POST | `/api/v1/ai/diagnostic/analyze` | Yes | 10/min |
| AI | POST | `/api/v1/ai/roadmap/generate` | Yes | 5/min |
| AI | POST | `/api/v1/ai/predict/band` | Yes | 10/min |
| AI | GET | `/api/v1/ai/brain/state` | Yes | 30/min |
| AI | POST | `/api/v1/ai/brain/recompute` | Yes | 10/hr |
| System | GET | `/api/v1/health` | No | -- |
| System | POST | `/api/v1/webhooks/supabase/auth` | Yes | -- |

---

## Appendix B: Request/Response Model Catalog

| Model | Module | Fields |
|---|---|---|
| `SignupRequest` | Auth | `email: str`, `password: str`, `full_name: str` |
| `LoginRequest` | Auth | `email: str`, `password: str` |
| `ForgotPasswordRequest` | Auth | `email: str` |
| `ResetPasswordRequest` | Auth | `token: str`, `new_password: str` |
| `RefreshTokenRequest` | Auth | `refresh_token: str` |
| `GoogleOAuthRequest` | Auth | `id_token: str` |
| `UpdateProfileRequest` | Auth | `full_name, country, timezone, avatar_url, preferences` |
| `UpdateGoalsRequest` | Auth | `target_band, exam_date, module, daily_minutes_budget` |
| `UserResponse` | Auth | `id, email, full_name, avatar_url, country, timezone, module, plan, target_band, exam_date, daily_minutes_budget, is_onboarding_complete, onboarded_at, preferences, created_at` |
| `TaskCompleteRequest` | Tasks | `duration_minutes, output, notes` |
| `TaskSkipRequest` | Tasks | `reason` |
| `TaskResponse` | Tasks | `id, title, skill, task_type, duration_minutes, status, priority, is_mandatory, phase_index, scheduled_date, due_at, content_payload, resources, completion, created_at` |
| `MockSubmitSectionRequest` | Mock Tests | `answers, time_spent_seconds` |
| `MockTestResponse` | Mock Tests | `id, mock_number, test_type, module, status, scheduled_date, overall_band, section_scores, sections, prep_day` |
| `MockResultsResponse` | Mock Tests | `id, mock_number, overall_band, section_scores, criteria_scores, comparison, mistake_analysis, roadmap_adjustment` |
| `WritingAssessmentRequest` | AI | `task_type, essay_text, prompt, word_count` |
| `SpeakingAssessmentRequest` | AI | `task_type, audio_url, duration_seconds, prompt` |
| `DiagnosticAnalysisRequest` | AI | `essay, speaking, vocabulary` |
| `RoadmapGenerateRequest` | AI | `diagnostic_band, target_band, exam_date, daily_minutes, module, skill_gaps, strengths, weaknesses` |
| `BrainStateResponse` | AI | `prediction, readiness, risk, probability, recommended_hours, weakest_topics, next_best_tasks` |
| `NotificationResponse` | Notifications | `id, type, title, body, is_read, metadata, created_at` |
| `NotificationPreferencesRequest` | Notifications | `push_enabled, email_enabled, quiet_hours_start, quiet_hours_end, subscribed_types` |
| `ResourceBookmarkRequest` | Resources | `collection_name, notes` |
| `ResourceCompletionRequest` | Resources | `resource_id, status, time_spent_minutes, rating, review_notes, task_id` |
| `PaginatedResponse<T>` | Common | `data: T[], total, page, limit, has_more` |
| `ErrorResponse` | Common | `detail: { code, message, fields }` |

---

*This document defines the complete backend API surface for IELTS AI Coach. Every endpoint is designed to be implemented as a FastAPI route under `/api/v1`, following the conventions in Section 0. All endpoints are consistent with the data models in DATABASE.md, the scheduler algorithms in SCHEDULER.md, the dashboard widget design in DASHBOARD.md, the AI decision engine in AI_BRAIN.md, and the gamification system in GAMIFICATION.md.*
