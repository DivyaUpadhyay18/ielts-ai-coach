# IELTS AI Coach — In-App Feedback System

**Role:** Chief Product Officer & Product Architect
**Document:** Feedback System Design Specification
**Status:** Draft for review & approval

---

## 0. Executive Summary

The Feedback System is the **product's R&D pipeline**. It captures every signal a user emits — explicit ratings, bug reports, feature requests, and implicit reactions — and routes them into a single, structured, actionable stream that drives the weekly iteration loop (LAUNCH_STRATEGY.md §4).

This document specifies a complete, unified feedback system supporting **five feedback types**:

| Icon | Type | What it captures |
|---|---|---|
| ⭐ | **Feature Rating** | How much a user values a specific feature/screen |
| 🐞 | **Bug Report** | Something is broken or behaving incorrectly |
| 💡 | **Feature Suggestion** | A new capability or improvement the user wants |
| 😊 | **AI Recommendation Rating** | Feedback on AI-produced outputs (assessment, resource rec, roadmap) |
| 📈 | **Study Plan Rating** | Feedback on the roadmap / daily mission quality |

**Design principles:**

1. **Zero-friction capture** — feedback must take ≤ 10 seconds for a rating, ≤ 60 seconds for a bug/suggestion.
2. **Context is king** — every feedback item auto-attaches product context (page, feature, AI output ID, device, session) so the team can reproduce and understand without asking "what happened?"
3. **One unified pipeline** — all five types feed a single moderation/triage queue with type-specific workflows.
4. **Loop closure** — every actionable item reaches a status; users are notified when their feedback ships, is fixed, or is answered.
5. **RLS-first & server-authoritative** — consistent with ARCHITECTURE.md / DATABASE.md: users own their rows; all aggregation happens server-side.

---

## 1. Feedback Types & Data Model Overview

### 1.1 Type Comparison

| Property | Feature Rating | Bug Report | Feature Suggestion | AI Recommendation Rating | Study Plan Rating |
|---|---|---|---|---|---|
| **Granularity** | Per feature/screen | Per issue | Per idea | Per AI output instance | Per plan/day/phase |
| **Scale** | 1–5 stars (or emoji) | Severity + category | Priority vote + category | 1–5 stars + optional comment | 1–5 stars + optional comment |
| **Required fields** | Feature ref | Description, severity, steps | Title, description | Output ref | Plan/day ref |
| **Auto-context** | Route, feature key | Telemetry dump | Route, plan version | Output snapshot | Plan snapshot |
| **Lifecycle** | None (aggregate) | Reported → Fixed → Verified | New → Planned → Shipped / Won't Do | None (aggregate) | None (aggregate) |
| **Moderation** | Optional (abuse) | Required | Required | Optional | Optional |
| **Reward** | XP (consistent with GAMIFICATION.md) | Bug Hunter badge + XP | Upvotes + XP | XP | XP |

### 1.2 Entity-Relationship Overview

```
                           ┌──────────┐
                           │  users   │
                           └────┬─────┘
                                │ 1:N
        ┌──────────┬────────────┼────────────┬─────────────┬──────────────┐
        ▼          ▼            ▼            ▼             ▼              ▼
  ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌───────────┐
  │ features │ │  bugs   │ │ requests │ │ai_feedback │ │plan_feedback│ │feedback_  │
  │(rating)  │ │         │ │ (votes)  │ │ (ratings)  │ │ (ratings)  │ │telemetry  │
  └──────────┘ └─────────┘ └──────────┘ └────────────┘ └───────────┘ └───────────┘
       │            │            │              │              │            │
       └────────────┴────────────┴──────────────┴──────────────┴────────────┘
                                    │
                              ┌─────▼─────┐
                              │ feedback_ │  ← unified moderation/triage queue
                              │  items    │    (view over all types)
                              └───────────┘
```

---

## 2. Database Design

### 2.1 `feature_ratings` — ⭐ Rate Features

Per-user rating of a specific feature/screen. One active rating per (user, feature); re-rating updates.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → users(id) ON DELETE CASCADE; RLS owner |
| `feature_key` | TEXT | NO | — | Stable feature identifier, e.g., `writing_feedback`, `speaking_recorder`, `roadmap_view`, `streak_calendar` |
| `feature_name` | TEXT | NO | — | Human-readable snapshot at time of rating (denormalized) |
| `screen_path` | TEXT | YES | NULL | Route where the rating was given (e.g., `/writing`) |
| `rating` | SMALLINT | NO | — | `CHECK (rating BETWEEN 1 AND 5)` |
| `comment` | TEXT | YES | NULL | Optional; `CHECK (char_length(comment) <= 1000)` |
| `created_at` | TIMESTAMPTZ | NO | `now()` | — |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | — |

**Constraints / Indexes**
- `UNIQUE (user_id, feature_key)` — one rating per user per feature
- `INDEX feature_ratings_feature_idx ON feature_ratings(feature_key)`
- `INDEX feature_ratings_user_idx ON feature_ratings(user_id)`

### 2.2 `bug_reports` — 🐞 Report Bugs

Structured bug report with severity, category, status, and rich telemetry.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → users(id) ON DELETE CASCADE |
| `title` | TEXT | NO | — | Auto-generated from template or user-entered; ≤ 200 chars |
| `description` | TEXT | NO | — | What happened; what you expected; ≤ 4000 chars |
| `steps_to_reproduce` | TEXT | YES | NULL | ≤ 4000 chars |
| `category` | TEXT | NO | `'other'` | `IN ('auth','onboarding','diagnostic','writing','speaking','roadmap','dashboard','analytics','resources','gamification','notifications','performance','ui','other')` |
| `severity` | TEXT | NO | `'minor'` | `IN ('blocker','critical','major','minor','trivial')` — maps to P0–P4 (LAUNCH_STRATEGY.md §6.2) |
| `status` | TEXT | NO | `'new'` | `IN ('new','triaged','in_progress','fixed','verified','closed','duplicate','won_fix')` |
| `status_history` | JSONB | NO | `'[]'` | `[{status, changed_at, changed_by, note}]` |
| `assigned_to` | UUID | YES | NULL | FK → users(id) (admin/developer) |
| `occurred_at` | TIMESTAMPTZ | YES | NULL | When the user hit the bug |
| `device` | JSONB | YES | NULL | `{os, browser, version, screen_size, device_type, user_agent}` |
| `environment` | TEXT | NO | `'production'` | `IN ('production','staging','beta')` |
| `is_duplicate_of` | UUID | YES | NULL | Self-referential FK → bug_reports(id) |
| `resolution_note` | TEXT | YES | NULL | Visible to user once resolved |
| `created_at` | TIMESTAMPTZ | NO | `now()` | — |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | — |

**Constraints / Indexes**
- `INDEX bug_reports_status_idx ON bug_reports(status)`
- `INDEX bug_reports_severity_idx ON bug_reports(severity)`
- `INDEX bug_reports_user_idx ON bug_reports(user_id, created_at DESC)`
- `INDEX bug_reports_category_idx ON bug_reports(category)`

### 2.3 `feature_requests` — 💡 Suggest Features

Feature suggestions with community voting and public status.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → users(id) ON DELETE CASCADE |
| `title` | TEXT | NO | — | ≤ 200 chars |
| `description` | TEXT | NO | — | ≤ 4000 chars |
| `category` | TEXT | NO | `'general'` | `IN ('learning','ai_quality','ux','community','performance','content','accessibility','other')` |
| `status` | TEXT | NO | `'new'` | `IN ('new','investigating','planned','in_progress','shipped','wont_do')` (LAUNCH_STRATEGY.md §7.2) |
| `status_note` | TEXT | YES | NULL | Public note explaining status (esp. for `wont_do`) |
| `status_history` | JSONB | NO | `'[]'` | `[{status, changed_at, changed_by}]` |
| `vote_count` | INTEGER | NO | `0` | Denormalized from `request_votes`; maintained by trigger/service |
| `shipped_in_version` | TEXT | YES | NULL | e.g., `v0.4.2` |
| `created_at` | TIMESTAMPTZ | NO | `now()` | — |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | — |

**Indexes**
- `INDEX feature_requests_status_idx ON feature_requests(status)`
- `INDEX feature_requests_votes_idx ON feature_requests(vote_count DESC)`
- `INDEX feature_requests_user_idx ON feature_requests(user_id)`

### 2.4 `request_votes` — Voting on Suggestions

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `request_id` | UUID | NO | — | FK → feature_requests(id) ON DELETE CASCADE |
| `user_id` | UUID | NO | — | FK → users(id) ON DELETE CASCADE |
| `created_at` | TIMESTAMPTZ | NO | `now()` | — |

**Constraints / Indexes**
- `UNIQUE (request_id, user_id)` — one vote per user per request
- `INDEX request_votes_user_idx ON request_votes(user_id)`

### 2.5 `ai_feedback` — 😊 Rate AI Recommendations

Ratings on any AI-produced output: writing/speaking assessments, resource recommendations, AI tips, band predictions.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → users(id) ON DELETE CASCADE |
| `source_type` | TEXT | NO | — | `IN ('writing_assessment','speaking_assessment','resource_recommendation','ai_tip','band_prediction','roadmap_generation','mock_feedback','diagnostic_result')` |
| `source_id` | UUID | NO | — | Polymorphic FK → assessments.id / resource_recommendations.id / band_predictions.id / mock_tests.id etc. |
| `rating` | SMALLINT | NO | — | `CHECK (rating BETWEEN 1 AND 5)` |
| `comment` | TEXT | YES | NULL | ≤ 2000 chars |
| `snapshot` | JSONB | YES | NULL | Lightweight snapshot of the AI output for offline analysis |
| `created_at` | TIMESTAMPTZ | NO | `now()` | — |

**Constraints / Indexes**
- `UNIQUE (user_id, source_type, source_id)` — one rating per output instance
- `INDEX ai_feedback_source_idx ON ai_feedback(source_type, source_id)`
- `INDEX ai_feedback_user_idx ON ai_feedback(user_id)`

### 2.6 `plan_feedback` — 📈 Rate Study Plans

Ratings on the roadmap, a phase, a daily mission, or an individual task suggestion.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → users(id) ON DELETE CASCADE |
| `plan_level` | TEXT | NO | — | `IN ('roadmap','phase','daily_mission','task')` |
| `plan_ref_id` | UUID | NO | — | Polymorphic FK → study_plans.id / roadmap_phases.id / daily_plans.id / tasks.id |
| `rating` | SMALLINT | NO | — | `CHECK (rating BETWEEN 1 AND 5)` |
| `comment` | TEXT | YES | NULL | ≤ 2000 chars |
| `usefulness_flags` | TEXT[] | YES | NULL | e.g., `['too_easy','too_hard','wrong_focus','too_much_work','good_pace']` |
| `snapshot` | JSONB | YES | NULL | Snapshot of the plan/day/task at rating time |
| `created_at` | TIMESTAMPTZ | NO | `now()` | — |

**Constraints / Indexes**
- `UNIQUE (user_id, plan_level, plan_ref_id)` — one rating per plan object
- `INDEX plan_feedback_ref_idx ON plan_feedback(plan_level, plan_ref_id)`
- `INDEX plan_feedback_user_idx ON plan_feedback(user_id)`

### 2.7 `feedback_telemetry` — Auto-Captured Context

Attached to bug reports (and optionally others) to help reproduce issues.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `bug_report_id` | UUID | YES | NULL | FK → bug_reports(id) ON DELETE CASCADE |
| `feedback_item_id` | UUID | YES | NULL | Generic link (optional) |
| `page_url` | TEXT | NO | — | Full route/URL |
| `session_id` | UUID | YES | NULL | Current session |
| `console_logs` | JSONB | YES | NULL | Last N console entries (errors/warnings) |
| `network_log` | JSONB | YES | NULL | Failed/slow requests (method, url, status, latency) |
| `ui_state_snapshot` | JSONB | YES | NULL | Sanitized UI state (no secrets) |
| `steps_log` | JSONB | YES | NULL | Last N user actions/events before bug |
| `created_at` | TIMESTAMPTZ | NO | `now()` | — |

**Indexes**
- `INDEX feedback_telemetry_bug_idx ON feedback_telemetry(bug_report_id)`

### 2.8 `feedback_items` — Unified Moderation View

A read-only **SQL view** (not a physical table) that unions all five types into one triage stream for the admin dashboard:

```sql
CREATE VIEW feedback_items AS
SELECT
  'feature_rating' AS type, id, user_id, created_at,
  rating AS primary_value, comment,
  feature_key AS ref_key, NULL::text AS status, NULL::text AS severity
FROM feature_ratings
UNION ALL
SELECT 'bug_report', id, user_id, created_at, NULL, description,
       category, status, severity
FROM bug_reports
UNION ALL
SELECT 'feature_request', id, user_id, created_at, vote_count, description,
       category, status, NULL
FROM feature_requests
UNION ALL
SELECT 'ai_feedback', id, user_id, created_at, rating, comment,
       source_type, NULL, NULL
FROM ai_feedback
UNION ALL
SELECT 'plan_feedback', id, user_id, created_at, rating, comment,
       plan_level, NULL, NULL
FROM plan_feedback;
```

### 2.9 Rewards Ledger Integration (Gamification)

Feedback actions award XP / badges consistent with GAMIFICATION.md:

| Action | Reward |
|---|---|
| Submit a rating (any type) | 5 XP |
| Submit a bug report | 15 XP |
| Bug verified & fixed | **Bug Hunter** badge + 25 XP |
| Submit a feature request | 10 XP |
| Feature request shipped | +50 XP |
| Upvote a feature request | 2 XP (once per request) |

All rewards write to `xp_ledger` with `type = 'feedback'` and `source_id` = feedback item id.

---

## 3. API Design

### 3.1 Conventions

- Base path: `/api/v1/feedback`
- Auth: Bearer JWT (Supabase), `get_current_user` dependency (ARCHITECTURE.md §9)
- All responses: Pydantic `response_model`; errors: `{"detail": {...}}`
- Pagination: `limit` (default 20, max 100) + `offset` or cursor
- Idempotency: `UNIQUE` constraints make re-submission safe (upsert semantics)
- Rate limiting: max 60 feedback writes / hour / user (anti-spam, LAUNCH_STRATEGY.md §6)

### 3.2 Endpoint Catalog

#### ⭐ Feature Ratings

| Method | Endpoint | Purpose | Request | Response |
|---|---|---|---|---|
| `PUT` | `/api/v1/feedback/feature-ratings` | Create or update a feature rating (upsert) | `{feature_key, feature_name?, rating, comment?}` | `{id, feature_key, rating, updated_at}` |
| `GET` | `/api/v1/feedback/feature-ratings` | List the user's feature ratings | `?feature_key=` | `{items: [...], total}` |
| `GET` | `/api/v1/feedback/features/{key}/rating` | Get current user's rating for one feature | — | `{feature_key, rating, comment} \| null` |
| `DELETE` | `/api/v1/feedback/feature-ratings/{id}` | Remove a rating | — | `{deleted: true}` |

#### 🐞 Bug Reports

| Method | Endpoint | Purpose | Request | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/feedback/bugs` | Submit a bug report (auto-attaches telemetry) | `{title?, description, steps_to_reproduce?, category, severity, occurred_at?, device?}` | `{id, status: 'new', created_at}` |
| `GET` | `/api/v1/feedback/bugs` | List user's bug reports + status | `?status=&limit=&offset=` | `{items: [...], total}` |
| `GET` | `/api/v1/feedback/bugs/{id}` | Get one bug + full status history + resolution note | — | Full bug object |
| `PUT` | `/api/v1/feedback/bugs/{id}` | User edits a *new* bug (before triage) | Partial fields | Updated bug |
| `POST` | `/api/v1/feedback/bugs/{id}/follow-up` | User adds a follow-up comment | `{comment}` | `{status_history: [...]}` |

#### 💡 Feature Suggestions

| Method | Endpoint | Purpose | Request | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/feedback/requests` | Submit a feature suggestion | `{title, description, category}` | `{id, status: 'new', vote_count: 0}` |
| `GET` | `/api/v1/feedback/requests` | List requests (filterable, sortable) | `?status=&category=&sort=votes\|recent&q=` | `{items: [...], total}` |
| `GET` | `/api/v1/feedback/requests/{id}` | Get one request + status history + status note | — | Full request object |
| `POST` | `/api/v1/feedback/requests/{id}/vote` | Upvote / un-vote (toggle) | — | `{vote_count, voted: true\|false}` |
| `GET` | `/api/v1/feedback/requests/mine` | List requests the user submitted/voted on | — | `{submitted: [...], voted: [...]}` |

#### 😊 AI Recommendation Ratings

| Method | Endpoint | Purpose | Request | Response |
|---|---|---|---|---|
| `PUT` | `/api/v1/feedback/ai` | Rate an AI output (upsert per source) | `{source_type, source_id, rating, comment?}` | `{id, rating, created_at}` |
| `GET` | `/api/v1/feedback/ai` | List user's AI feedback | `?source_type=&limit=&offset=` | `{items: [...], total}` |

#### 📈 Study Plan Ratings

| Method | Endpoint | Purpose | Request | Response |
|---|---|---|---|---|
| `PUT` | `/api/v1/feedback/plans` | Rate a roadmap/phase/mission/task (upsert per ref) | `{plan_level, plan_ref_id, rating, comment?, usefulness_flags?}` | `{id, rating, created_at}` |
| `GET` | `/api/v1/feedback/plans` | List user's plan feedback | `?plan_level=` | `{items: [...], total}` |

#### 🔔 Status & Notifications

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/feedback/subscription` | Get user's feedback-notification preferences (email/push on status change) |
| `PUT` | `/api/v1/feedback/subscription` | Update preferences |

### 3.3 Realtime Events (Supabase Realtime)

| Channel | Event | Payload |
|---|---|---|
| `user:{id}:feedback` | `bug_status_changed`, `request_status_changed`, `feedback_rewarded` | `{type, item_id, status, reward_xp?}` |
| `user:{id}:notifications` | `new_notification` | `{type: 'feedback', title, body, metadata}` |

### 3.4 Example Request/Response — Submit a Bug

**Request:**
```http
POST /api/v1/feedback/bugs
Authorization: Bearer <JWT>

{
  "description": "After submitting my essay, the feedback overlay never appeared.",
  "steps_to_reproduce": "1. Open /writing 2. Type 260 words 3. Click submit 4. Spinner spins forever",
  "category": "writing",
  "severity": "major",
  "occurred_at": "2025-05-01T14:23:00Z"
}
```

**Response (201 Created):**
```json
{
  "id": "9f8c2b1e-...",
  "status": "new",
  "severity": "major",
  "category": "writing",
  "created_at": "2025-05-01T14:23:11Z",
  "rewards": { "xp": 15, "badge_eligible": false },
  "telemetry": { "attached": true, "size_bytes": 18432 }
}
```

---

## 4. UI Flow

### 4.1 Global Entry Points

| Entry Point | Location | Opens |
|---|---|---|
| **Feedback FAB** (Floating Action Button) | Bottom-right corner on all authenticated pages | Central feedback hub (bottom sheet) |
| **Post-action prompt** | After diagnostic, assessment, roadmap generation, resource view | Contextual micro-rating for that specific action |
| **Help menu** | Sidebar/navbar "Help & Feedback" | Central feedback hub |
| **Exit/churn prompt** | After 7+ days inactive (survey) | Lightweight 3-question exit survey |
| **Footer** | "Report a problem" on all pages | Bug report flow (pre-filled with route) |

### 4.2 Central Feedback Hub (Bottom Sheet)

```
┌──────────────────────────────────────────────┐
│  How can we improve IELTS AI Coach?          │
│                                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│  │ ⭐ Rate│ │ 🐞 Bug │ │ 💡 Idea│ │ 📈 Plan│ │
│  │ a      │ │ Report │ │ Suggest│ │ Feedback│ │
│  │ Feature│ │        │ │        │ │        │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ │
│  ──────────────────────────────────────────  │
│  Your recent feedback:  View status →        │
│  (link to "My feedback" page)                │
└──────────────────────────────────────────────┘
```

### 4.3 Flow A — ⭐ Rate a Feature

**Trigger:** FAB → "Rate a Feature" **OR** post-action prompt (e.g., after viewing writing feedback).

```
Step 1 — Pick context (pre-filled if from a prompt):
   "Which feature are you rating?"
   [Current screen pre-selected] | [Search/select from list]

Step 2 — Star rating (1–5) with quick-labels:
   1 = Frustrating · 3 = Okay · 5 = Love it
   Optional: "What made it good/bad?" (textarea, ≤ 1000 chars)

Step 3 — Submit (≤ 10 seconds total)
   → Success toast: "Thanks! +5 XP"
   → Button: "Review your feedback" (optional)
```

**Design rules:**
- The star control is large (touch-friendly), with animated fill.
- Quick-labels reduce cognitive load (users rarely type).
- Rating is **always** stored with `screen_path` + `feature_key` (auto).

### 4.4 Flow B — 🐞 Report a Bug

**Trigger:** FAB → "Report a Bug" **OR** footer "Report a problem".

```
Step 1 — Category (optional, pre-selected from route):
   [Writing] [Speaking] [Diagnostic] [Roadmap] [Dashboard] [Other]

Step 2 — What happened? (required, ≤ 4000 chars)
   Auto-suggested template: "I was trying to ___ but ___"
   + Steps to reproduce (optional, ≤ 4000 chars)
   + Severity: [Blocker] [Critical] [Major] [Minor] [Trivial]
     (with plain-language labels: "I can't use the app at all" ...)

Step 3 — Attach (optional):
   Screenshot (auto-suggested after error) · Screen recording

Step 4 — Review & submit
   → Auto-captures telemetry (device, console, network, last steps)
   → Success: "Bug reported! Our team will look into it. +15 XP"
   → Shows tracking ID: "You can follow progress in My Feedback"
```

**Telemetry capture (automatic, with consent notice):**
- Device/OS/browser/version, screen size, user-agent
- Page URL + session id
- Last 50 console entries (errors/warnings)
- Failed/slow network requests (method, URL, status, latency)
- Last 20 user actions before the report
- Sanitized UI state snapshot (strip tokens, passwords, essay text by default — user opts-in to include content)

### 4.5 Flow C — 💡 Suggest a Feature

**Trigger:** FAB → "Suggest an Idea".

```
Step 1 — Title (required, ≤ 200 chars)
   Auto-suggest: "I want to be able to ___"

Step 2 — Description (required, ≤ 4000 chars)
   Template prompts: "What problem does this solve?" · "How would you use it?"

Step 3 — Category: [Learning] [AI quality] [UX] [Community] [Content] [Other]

Step 4 — Duplicate check (live, debounced):
   "Similar ideas exist: 'Grammar checker for essays' (12 votes) — [View] [Submit anyway]"

Step 5 — Submit
   → Success: "Idea added! +10 XP. It's now public for voting."
   → Shows the request on the public board with status 'New'.
```

### 4.6 Flow D — 😊 Rate AI Recommendations

**Trigger:** Always available after any AI output (embedded widget, not the FAB).

**Placement examples:**

| AI Output | Widget placement |
|---|---|
| Writing assessment result | Bottom of feedback overlay: "Was this feedback helpful?" |
| Speaking assessment | After transcript/score review |
| Resource recommendation | On the recommendation card (thumb/stars) |
| Band prediction | Beside the predicted-band widget (Dashboard W5) |
| Roadmap generation | On the roadmap page header |
| Mock test feedback | End of post-mock review |

```
Widget:  [★★★★☆]  "Was this AI feedback helpful?"  [+ optional comment]

Interaction:
  ★≥4  → toast "+5 XP", optionally "What did you like?" (free text)
  ★≤2  → expands: "What went wrong?" quick-chips:
         [Too harsh] [Too generous] [Didn't understand] [Wrong topic] [Other]
         + optional comment → submit → +5 XP, tagged for review
```

**Special rules:**
- Ratings < 3 with `source_type = writing_assessment` **auto-flag** the assessment for tutor spot-check (LAUNCH_STRATEGY.md §5.3 AI quality audit).
- Low ratings are the **highest-priority signal** for prompt tuning.

### 4.7 Flow E — 📈 Rate Study Plans

**Trigger:** Post-plan prompts at natural moments.

| Moment | Plan level | Prompt |
|---|---|---|
| Roadmap generated | `roadmap` | "Does this roadmap feel right for your schedule?" |
| Phase unlocked | `phase` | "Rate your experience in this phase." |
| End of daily mission | `daily_mission` | "Was today's mission the right amount of work?" |
| Task completed | `task` | "Was this task useful?" |

```
Prompt (bottom card / modal, dismissible):
  "How was your study plan today?"
  [★★★★☆]
  Quick flags (multi-select chips):
  [Good pace] [Too much work] [Too easy] [Too hard] [Wrong focus]
  Optional comment (≤ 2000 chars)
  [Not now]        [Submit (+5 XP)]
```

**Special rules:**
- `too_much_work` or `too_hard` flags **feed back to the Adaptive Scheduler** (overload signals — SCHEDULER.md §8) as a soft input.
- `too_easy` flags feed the difficulty curve (increase task difficulty).

### 4.8 "My Feedback" Page

A user-facing page listing all their submitted feedback with live status:

```
┌──────────────────────────────────────────────────┐
│  My Feedback                       (Total: 14)   │
│                                                  │
│  Tabs: [All] [Bugs (3)] [Ideas (5)] [Ratings (6)]│
│                                                  │
│  🐞 "Feedback overlay never appeared"            │
│     Writing · Major · ✅ Fixed · v0.4.3          │
│     "Fixed in v0.4.3 — thank you! +25 XP"        │
│                                                  │
│  💡 "Grammar checker for essays"                 │
│     Learning · 🛠 In Progress · 42 votes         │
│                                                  │
│  ⭐ Writing feedback · 5★ · 2 days ago           │
│  📈 Today's mission · 4★ · "Good pace" · 1d ago  │
└──────────────────────────────────────────────────┘
```

**Elements:** status badges, resolution notes, vote counts, reward history, "withdraw idea" (if still `new`).

---

## 5. Admin Dashboard Requirements

### 5.1 Overview Page

| Metric | Source |
|---|---|
| Total feedback items (7d / 30d / all) | `feedback_items` view |
| Open bugs (P0/P1/P2 counts) | `bug_reports` |
| Open feature requests (+ total votes) | `feature_requests` |
| Avg rating by type (feature / AI / plan) | Aggregations |
| Avg AI feedback rating (7d) — **key AI quality signal** | `ai_feedback` |
| Feedback-to-ship rate (closed loops) | `bug_reports` + `feature_requests` |
| Response SLA compliance (P0 < 1h, P1 < 4h) | `bug_reports.status_history` |

### 5.2 Bug Triage Queue

| Feature | Detail |
|---|---|
| **List** | Sortable/filterable by severity, status, category, date, device |
| **Detail view** | Full description, steps, telemetry panel (device/console/network/steps), screenshot, status history, reporter info |
| **Actions** | Assign → set severity → set status → mark duplicate (links to parent) → resolve with `resolution_note` (user-visible) |
| **Bulk** | Multi-select: mark duplicate, batch severity update, notify reporters |
| **SLA clock** | Visual countdown per severity; alerts when breach imminent |
| **Search** | Full-text + filter by feature_key/category/reporter |

### 5.3 Feature Request Board

| Feature | Detail |
|---|---|
| **Kanban board** | Columns: New → Investigating → Planned → In Progress → Shipped → Won't Do |
| **Ranking** | Default sort by `vote_count`; toggle to recency |
| **Vote trend** | Sparkline of vote velocity (votes/week) to spot rising demand |
| **Duplicate merge** | Merge duplicates (redirect votes to canonical request) |
| **Status note** | Required when moving to `wont_do` (shown publicly) |
| **Ship linkage** | When moving to `shipped`, record `shipped_in_version`; auto-notifies voters + submitter |
| **Triage score** | Compute LAUNCH_STRATEGY.md §7.3 score (impact × fit × feasibility × retention) inline |

### 5.4 Ratings & Sentiment Analytics

| View | Content |
|---|---|
| **Feature ratings matrix** | Feature × avg rating × count × trend (last 30d) |
| **AI feedback dashboard** | Avg rating by source_type; low-rating clusters (comment mining); prompt-tune candidates |
| **Plan feedback dashboard** | Avg rating by plan_level; flag frequency (`too_hard`, `too_easy`, etc.); scheduler-integration signals |
| **Comment mining** | Keyword extraction from comments (e.g., "confusing", "slow", "love") → topic clouds |
| **CSV/PDF export** | All analytics exportable for weekly review (LAUNCH_STRATEGY.md §5.3) |

### 5.5 Moderation & Abuse Prevention

| Control | Detail |
|---|---|
| **Profanity/toxicity filter** | Server-side scan (open-source classifier) flags items; admin reviews |
| **Spam detection** | Rate limits (60 writes/hr); identical-content dedupe; new-account cooldown (no feedback within 5 min of signup) |
| **Manual flags** | Admin can hide an item, mute a user, or revoke XP rewards for abuse |
| **Abuse appeals** | Flagged users can appeal; admin inbox for appeals |

### 5.6 Notification of Users (Loop Closure)

| Event | Notification |
|---|---|
| Bug status → `fixed` | "Your bug report is fixed! 🎉 See what changed" (in-app + email opt-in) |
| Bug → `duplicate` | "Your bug report was merged with an existing one" |
| Feature request → `planned` | "Your idea is on the roadmap!" |
| Feature request → `shipped` | "You asked, we shipped ✅ (v0.4.3)" — credits submitter + top voters |
| Reward granted | "You earned the Bug Hunter badge + 25 XP" |

### 5.7 Admin API (role-protected)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/admin/feedback/overview` | KPIs for overview page |
| `GET` | `/api/v1/admin/feedback/bugs` | Triage queue (filters, pagination) |
| `PUT` | `/api/v1/admin/feedback/bugs/{id}` | Update status/severity/assignee/resolution |
| `POST` | `/api/v1/admin/feedback/bugs/{id}/duplicate` | Mark duplicate |
| `GET` | `/api/v1/admin/feedback/requests` | Board data |
| `PUT` | `/api/v1/admin/feedback/requests/{id}` | Update status/status_note/shipped_in_version |
| `POST` | `/api/v1/admin/feedback/requests/{id}/merge` | Merge duplicates |
| `GET` | `/api/v1/admin/feedback/analytics` | Ratings + sentiment aggregations |
| `POST` | `/api/v1/admin/feedback/{type}/{id}/hide` | Hide/restore item (moderation) |
| `POST` | `/api/v1/admin/feedback/users/{id}/mute` | Mute user from feedback |

Admin access: `app_metadata.role = 'admin'` (ARCHITECTURE.md §9.3), with full audit log of admin actions.

---

## 6. Data Flow Summary

```
USER ACTION (rate / bug / idea / AI rating / plan rating)
        │
        ▼
Client validates + attaches context (route, feature_key, telemetry)
        │
        ▼
POST/PUT /api/v1/feedback/*   (Bearer JWT, rate-limited)
        │
        ▼
Backend service:
  ├─ Validate (Pydantic) + dedupe (UNIQUE constraints)
  ├─ Persist row (RLS-enforced)
  ├─ Write xp_ledger reward (feedback type)
  ├─ Emit Realtime event (user:{id}:feedback)
  └─ Enqueue async jobs:
       ├─ Toxicity/spam scan (flagged → admin queue)
       ├─ Low AI rating (< 3) → tutor spot-check queue
       └─ Plan flags → scheduler soft-input (overload/difficulty)
        │
        ▼
Admin dashboard (feedback_items view) → triage → status change
        │
        ▼
Loop closure: notification to user + status history + optional reward
```

---

## 7. Edge Cases

| Case | Handling |
|---|---|
| User submits duplicate bug | Dedupe by text hash (24h window) → prompt "already reported", link to existing |
| Offline submission | Queue locally (service worker); flush on reconnect |
| Rating an AI output that was later deleted | `source_id` orphan → soft-delete rating, keep aggregate |
| User rates a feature 1★ without comment | Stored; prompts once "mind telling us why?" (dismissible) |
| Feedback spam (new account) | Cooldown 5 min post-signup; rate limits; flag for review |
| User edits a bug already triaged | Edit locked; user adds a follow-up comment instead |
| Feature request reaches 100 votes | Auto-notify product team (webhook) + elevate to "investigating" |
| Bug reported in beta vs production | `environment` field routes to different severity baselines |
| Telemetry contains PII | Sanitize by default; user opts-in to include essay/recording content |
| Admin resolves without note | `wont_do`/`duplicate`/`fixed` without `resolution_note` → blocked by validation |
| User closes app mid-bug-report | Draft auto-saved to localStorage; restored on next open |
| AI rating low but assessment accurate | Tutor audit distinguishes "feedback clarity" vs "score wrong"; both tracked |
| Plan flagged `too_much_work` repeatedly | Scheduler receives overload signal; reduces future workload (SCHEDULER.md §8) |

---

## 8. Implementation Notes (Non-Code Checklist)

1. **Schema migrations** for the 7 tables + `feedback_items` view + RLS policies (`auth.uid() = user_id`) + trigger to maintain `vote_count`.
2. **Realtime channels** wired to `user:{id}:feedback` for status-change notifications.
3. **XP integration** via `xp_ledger` (GAMIFICATION.md §1.8) — never double-award (idempotency keys).
4. **Tutor spot-check queue** for low-rated AI outputs (LAUNCH_STRATEGY.md §5.3).
5. **Scheduler soft-input** hook for plan feedback flags (SCHEDULER.md §8 overload detection).
6. **Admin RBAC** + audit log for all admin actions.
7. **Privacy** — telemetry sanitization, consent notice, data deletion on account deletion.

---

*This document is the complete specification for the in-app Feedback System. It is consistent with ARCHITECTURE.md (layered backend), DATABASE.md (RLS + UUID + timestamps), GAMIFICATION.md (XP/badges), SCHEDULER.md (plan-feedback soft-input), LAUNCH_STRATEGY.md (triage SLAs, public roadmap, loop closure), and AI_BRAIN.md (AI quality signals).*

