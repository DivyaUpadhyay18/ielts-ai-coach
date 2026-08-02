# IELTS AI Coach — Production-Ready Architecture

**Version:** 1.0  
**Author:** Chief Product Architect  
**Status:** Draft for review & approval

---

## 0. Executive Summary

IELTS AI Coach is currently a **UI-driven prototype** with a **thin FastAPI backend**. The frontend (Next.js 15 + Tailwind + Zustand) renders a rich, polished experience across landing, auth, dashboard, writing, speaking, diagnostic, roadmap, analytics, resources, notifications, and settings pages. The backend exposes only three endpoints (`/health`, `POST /assess`, `GET /results/{user_id}`) with a single writing-assessment AI call.

The product vision — an **adaptive AI-powered IELTS preparation platform** with personalized roadmaps, daily streaks, auto-reshuffling tasks, band prediction, exam countdown, and a recommendation engine — is **not yet implemented in the backend**. All roadmap/analytics/streak/band-prediction logic currently lives as **hard-coded mock data** inside React components.

This document defines the **target production architecture** that realizes the full vision while incrementally extending the existing codebase.

---

## 1. Overall Architecture

### 1.1 High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            CLIENT (Browser)                              │
│                                                                           │
│   Next.js 15 App Router — Vercel                                         │
│   ├── Public Pages (Landing, Login, Signup, Forgot, Resources)           │
│   ├── Protected Pages (Dashboard, Writing, Speaking, Roadmap,            │
│   │                     Diagnostic, Analytics, Notifications, Profile)    │
│   ├── Zustand Stores (Auth, UI)  +  TanStack Query (Server State)        │
│   └── API Client (axios → FastAPI)                                       │
└──────────────┬───────────────────────────────────────────┬───────────────┘
               │ HTTPS (JWT Bearer)                         │ HTTPS (Supabase Auth / Realtime / Storage)
               ▼                                            ▼
┌────────────────────────────────────────┐      ┌──────────────────────────────────┐
│         BACKEND — FastAPI              │      │        SUPABASE (BaaS)            │
│  (Railway / Render / Fly.io)           │      │  ┌────────────────────────────┐   │
│  ├── API Routers (v1)                  │      │  │ Auth (JWT, OAuth, MFA)     │   │
│  ├── Services (Domain Logic)           │      │  ├────────────────────────────┤   │
│  ├── AI Module (LLM orchestration)     │      │  │ PostgreSQL (relational)    │   │
│  ├── Scheduler Adapter                 │      │  │ + RLS Policies             │   │
│  ├── Resource Engine                   │      │  ├────────────────────────────┤   │
│  ├── Analytics / Band Prediction       │      │  │ Storage (audio, avatars,   │   │
│  └── Worker Jobs (Celery)              │      │  │  PDF reports)              │   │
│                                        │      │  ├────────────────────────────┤   │
└──────────────┬─────────────────────────┘      │  │ Realtime (streaks,         │   │
               │ internal                        │  │  notifications)            │   │
               ▼                                 │  └────────────────────────────┘   │
┌─────────────────────────────┐                 └──────────────────────────────────┘
│   Message Queue / Cache     │
│   Redis (Celery broker +    │
│   rate-limit + vector cache)│
└──────────────┬──────────────┘
               ▼
┌──────────────────────────────────────────────────────────┐
│                  EXTERNAL AI PROVIDERS                    │
│  ├── OpenAI (GPT-4o-mini / gpt-4o)  — assessment, plans   │
│  ├── Whisper / Deepgram  — speech-to-text for Speaking    │
│  └── TTS provider  — examiner voice for Speaking practice │
└──────────────────────────────────────────────────────────┘
```

### 1.2 Architectural Style

| Decision | Choice | Rationale |
|---|---|---|
| Backend style | **Modular Monolith** (FastAPI) | Fast to ship, single deployable, easy split into microservices later |
| Frontend | **Next.js 15 (App Router) SPA + SSR** | SEO for landing, code-splitting, middleware for route guards |
| Backend-as-a-Service | **Supabase** | Auth, Postgres, Storage, Realtime out of the box |
| Async processing | **Celery + Redis** | Long-running AI tasks (essay analysis, speaking transcription, roadmap regeneration) |
| AI orchestration | **Backend service layer** | Keeps prompt/LLM logic server-side; swappable providers |
| Real-time | **Supabase Realtime** | Streaks, notification badges, live countdown |
| State management | **Zustand (client) + TanStack Query (server)** | Separation of ephemeral vs remote state |

### 1.3 Key Design Principles

1. **Server is the source of truth** — all business rules (band rounding, streak calc, task rescheduling) live in the backend, never in React components.
2. **Async-first AI** — heavy AI work runs in Celery workers; clients poll or get pushed results via Supabase Realtime / WebSocket.
3. **Adaptive by design** — every user action (task completion, assessment, diagnostic) feeds an event stream that triggers roadmap re-computation.
4. **Row-Level Security (RLS)** — users can only access their own data; the backend uses the service-role key only for trusted server-side operations.
5. **Feature-based folder structure** — scales with the team.

---

## 2. Frontend Architecture

### 2.1 Current State (as built)

- Next.js **15.0.3** / React **18.3.1** / TypeScript 5 / Tailwind 3.4
- Pages under `src/app/**` using the App Router; three layouts (`landing`, `auth`, `dashboard`)
- **Zustand** store for auth (`useAuthStore`), initialized by `AuthInitializer` in root layout
- **axios** client (`src/services/api.ts`) with `ieltsService` (health / submitAssessment / getUserResults)
- Reusable **UI kit** (`src/components/ui/*`) — button, card, input, tabs, modal, dropdown, badge, progress, etc.
- **Recharts** is a dependency (analytics charts currently mocked with divs)
- All roadmap/analytics/diagnostic data are **hard-coded mock objects** in page components

### 2.2 Target Structure & Data Flow

```
Rendering strategy
├── Server Components (RSC): landing, legal pages, SEO metadata
├── Client Components ("use client"): all interactive dashboard pages
└── API layer: all data-fetching goes through typed service functions

State strategy
├── Zustand (ephemeral): auth session, UI toggles, active recording state
├── TanStack Query (server state): assessments, roadmap, analytics, resources
└── Local component state: form fields, timers, filters

Route protection
└── middleware.ts — checks Supabase session cookie; redirects /dashboard, /writing,
    /speaking, /roadmap, /analytics, /diagnostic, /notifications, /profile → /login
```

### 2.3 Recommended Frontend Modules

| Module | Responsibility | Tech |
|---|---|---|
| `app/` pages | Route definitions, page composition | Next.js App Router |
| `components/ui` | Atomic design system (existing) | Tailwind + shadcn-style |
| `components/shared` | Navbar, Sidebar, Footer (existing) | — |
| `components/features` | Feature-specific widgets (StreakCard, BandTrendChart, TaskItem, RecommendationCard) | Recharts for charts |
| `services/` | Typed API clients per domain | axios + TanStack Query hooks |
| `stores/` | Auth + future UI stores | Zustand |
| `hooks/` | `useAssessment`, `useRoadmap`, `useStreak`, `useCountdown`, `useNotifications` | TanStack Query |
| `types/` | Shared domain types (extend existing) | TypeScript |

### 2.4 Frontend Improvements (required)

1. **Replace mock data with live API calls** — the highest-impact change. Every dashboard widget must consume backend endpoints via TanStack Query.
2. **Introduce TanStack Query** for caching, optimistic updates, and background refetch (e.g., streak refresh after task completion).
3. **Add `middleware.ts`** for route protection using the Supabase session cookie.
4. **Speaking module**: wire `MediaRecorder` output (Blob) to an upload endpoint → backend transcription → AI assessment.
5. **Writing module**: replace `simulateSubmit()` with a real `POST /assess` call + async polling for results.
6. **Realtime subscription** to `notifications` and streak counters via Supabase Realtime.
7. **Error boundaries + loading skeletons** for every page (skeleton components already exist).
8. **Form validation** (react-hook-form + zod) for signup/profile/settings.

---

## 3. Backend Architecture

### 3.1 Current State (as built)

- FastAPI app (`app/main.py`) with CORS and a single router included under `/api`
- `app/api/endpoints.py` — 3 routes, plus a `get_current_user` dependency that verifies the Supabase JWT
- `app/services/ielts_service.py` — save/get assessments, `calculate_overall_band` (IELTS 0.5 rounding rule)
- `app/services/ai_service.py` — `analyze_writing` calling OpenAI `gpt-4o-mini` with mock fallback
- `app/ai/prompts.py` — writing & speaking examiner prompt templates
- `app/models/schemas.py` — Pydantic models (assessment + user profile update)
- `app/db/supabase.py` — Supabase client (service-role key)
- `app/core/config.py` — pydantic-settings

### 3.2 Target Layered Architecture

```
app/
├── main.py                 # App factory, middleware, router mounting, lifespan hooks
├── core/                   # config, security, logging, exceptions
├── api/
│   ├── deps.py             # get_current_user, get_db, get_redis, require_role
│   └── v1/
│       ├── auth.py         # profile endpoints (uses Supabase Auth)
│       ├── assessments.py  # writing/speaking submit + results
│       ├── diagnostic.py   # start, submit section, get report
│       ├── roadmap.py      # get, regenerate, complete task
│       ├── analytics.py    # trends, skill gaps, band prediction
│       ├── resources.py    # catalog search/filter, recommendations
│       ├── scheduler.py    # manual trigger of daily rollover (admin)
│       ├── notifications.py
│       └── users.py        # profile, goals, settings
├── services/               # Business logic (no HTTP/DB awareness)
│   ├── assessment_service.py
│   ├── diagnostic_service.py
│   ├── roadmap_service.py
│   ├── streak_service.py
│   ├── prediction_service.py
│   ├── resource_service.py
│   ├── notification_service.py
│   └── user_service.py
├── repositories/           # Data access (Supabase/Postgres) per entity
│   ├── assessment_repo.py
│   ├── roadmap_repo.py
│   ├── streak_repo.py
│   ├── resource_repo.py
│   └── ...
├── ai/
│   ├── client.py           # LLM provider abstraction (OpenAI, fallbacks)
│   ├── prompts.py          # centralized prompt library (extend existing)
│   ├── writing_assessor.py
│   ├── speaking_assessor.py
│   ├── diagnostic_analyzer.py
│   ├── roadmap_generator.py
│   ├── band_predictor.py
│   └── resource_recommender.py
├── workers/                # Celery tasks
│   ├── tasks_assessment.py
│   ├── tasks_speaking.py
│   ├── tasks_roadmap.py
│   └── tasks_scheduler.py
├── scheduler/
│   └── daily_jobs.py       # beat schedule + rollover logic
├── models/                 # Pydantic schemas (request/response)
│   ├── schemas.py          # existing
│   ├── roadmap.py
│   ├── analytics.py
│   └── resources.py
├── db/
│   ├── supabase.py         # existing client + typed table helpers
│   └── migrations/         # SQL migrations (roadmap, streaks, etc.)
└── utils/                  # band rounding, date math, text helpers
```

### 3.3 API Versioning & Contract

- Prefix all routes with `/api/v1` (e.g., `GET /api/v1/roadmap`).
- Every response uses Pydantic `response_model`; errors use a consistent `{"detail": {...}}` envelope.
- Idempotency keys on assessment submissions to prevent duplicate AI charges.
- Pagination via `limit`/`offset` or cursor for history endpoints.

### 3.4 Security

- `get_current_user` (existing) is hardened: verify JWT with Supabase, cache verification, reject expired tokens.
- CORS restricted to the deployed frontend origin (env-driven).
- Rate limiting on `/assess` (per-user and per-IP) via Redis.
- Input size caps (essay length, audio duration) in Pydantic validators.
- Service-role key only used in trusted server context; never exposed client-side.

---

## 4. Database Architecture

### 4.1 Platform & Strategy

- **Supabase Postgres** is the single relational store.
- Migrations managed with **Alembic** or Supabase SQL migrations (versioned SQL files).
- **RLS enabled on all user-owned tables**; policies `USING (auth.uid() = user_id)`.
- **pgvector** extension for resource embeddings (semantic search / recommendations).
- **Enum types** for task_type, phase status, resource type, notification type.

### 4.2 Proposed Schema

```
users (extends auth.users)
  id UUID PK
  full_name TEXT
  avatar_url TEXT
  country TEXT
  plan TEXT DEFAULT 'free'          -- free | pro
  onboarded_at TIMESTAMPTZ
  created_at TIMESTAMPTZ

user_goals
  user_id UUID PK FK → users.id
  target_band NUMERIC(2,1)          -- 0.0–9.0
  exam_date DATE                    -- drives countdown
  daily_minutes INT DEFAULT 60
  module TEXT DEFAULT 'academic'    -- academic | general
  updated_at TIMESTAMPTZ

diagnostic_results
  id UUID PK
  user_id UUID FK → users.id
  overall_band NUMERIC(2,1)
  skill_scores JSONB                -- {grammar, lexical, coherence, fluency, ...}
  strengths JSONB
  weaknesses JSONB
  created_at TIMESTAMPTZ

assessments
  id UUID PK
  user_id UUID FK → users.id
  task_type TEXT                    -- Writing Task 1 | Writing Task 2 | Speaking
  user_input TEXT
  audio_url TEXT NULL
  transcript TEXT NULL
  band_score NUMERIC(2,1)
  criteria_scores JSONB             -- per-criterion band
  feedback TEXT
  corrections JSONB
  created_at TIMESTAMPTZ

roadmaps
  id UUID PK
  user_id UUID FK → users.id
  source_diagnostic_id UUID NULL
  target_band NUMERIC(2,1)
  version INT DEFAULT 1
  status TEXT DEFAULT 'active'      -- active | archived
  created_at TIMESTAMPTZ

roadmap_phases
  id UUID PK
  roadmap_id UUID FK → roadmaps.id
  order_index INT
  title TEXT
  description TEXT
  status TEXT DEFAULT 'locked'      -- locked | active | completed

study_tasks
  id UUID PK
  phase_id UUID FK → roadmap_phases.id
  title TEXT
  skill TEXT                         -- writing | speaking | vocabulary | grammar | listening | reading
  duration_minutes INT
  scheduled_date DATE                -- adaptive; rolled forward if missed
  status TEXT DEFAULT 'pending'      -- pending | in_progress | completed | missed
  resource_id UUID NULL
  is_diagnostic BOOLEAN DEFAULT false
  created_at TIMESTAMPTZ

task_completions
  id UUID PK
  task_id UUID FK → study_tasks.id
  user_id UUID FK → users.id
  completed_at TIMESTAMPTZ
  duration_minutes INT
  notes JSONB

daily_activity  (streak engine input)
  id UUID PK
  user_id UUID FK → users.id
  activity_date DATE
  minutes INT DEFAULT 0
  tasks_completed INT DEFAULT 0
  UNIQUE (user_id, activity_date)

streaks
  user_id UUID PK FK → users.id
  current_streak INT DEFAULT 0
  longest_streak INT DEFAULT 0
  last_activity_date DATE
  updated_at TIMESTAMPTZ

resources
  id UUID PK
  title TEXT
  description TEXT
  type TEXT                          -- video | article | pdf | practice_test | guide
  skill TEXT
  difficulty TEXT
  provider TEXT
  duration_minutes INT
  url TEXT
  tags TEXT[]
  embedding VECTOR(1536) NULL        -- for semantic search
  created_at TIMESTAMPTZ

resource_recommendations
  id UUID PK
  user_id UUID FK → users.id
  resource_id UUID FK → resources.id
  reason TEXT
  score NUMERIC(5,2)
  status TEXT DEFAULT 'suggested'    -- suggested | viewed | saved | dismissed
  created_at TIMESTAMPTZ

band_predictions
  id UUID PK
  user_id UUID FK → users.id
  predicted_band NUMERIC(2,1)
  confidence NUMERIC(5,2)
  model_version TEXT
  features JSONB
  created_at TIMESTAMPTZ

notifications
  id UUID PK
  user_id UUID FK → users.id
  type TEXT                          -- ai_feedback | reminder | system
  title TEXT
  body TEXT
  is_read BOOLEAN DEFAULT false
  created_at TIMESTAMPTZ
```

### 4.3 Indexing & Performance

- Composite index on `study_tasks(user_id, scheduled_date)` for daily planner queries.
- Index on `assessments(user_id, created_at desc)` for history (already ordered).
- GIN index on `resources.tags`.
- Partition `task_completions`/`daily_activity` by month once volume grows.

---

## 5. AI Modules

### 5.1 Module Map

| Module | Input | Output | Provider |
|---|---|---|---|
| **Writing Assessor** (exists) | essay text + task type | band score, 4-criteria scores, feedback, corrections | GPT-4o-mini |
| **Speaking Assessor** | transcript (from Whisper) | band score, fluency/lexis/grammar/pronunciation scores, feedback | GPT-4o-mini + Whisper |
| **Diagnostic Analyzer** | essay + speaking clip + vocab quiz | baseline band, strengths/weaknesses, skill profile | GPT-4o-mini |
| **Roadmap Generator** | diagnostic profile, target band, exam date, daily budget | phased roadmap with tasks & dates | GPT-4o-mini + rules engine |
| **Band Predictor** | historical assessment scores + study volume | expected band + confidence | Statistical (weighted regression) + LLM ensemble |
| **Resource Recommender** | skill gaps + preferences | ranked resources with reasons | pgvector + LLM scoring |
| **Adaptive Re-planner** | task completions / missed tasks | updated schedule, reshuffled tasks | Rule-based + LLM |

### 5.2 AI Orchestration Pattern

```
Request → Validate → Enqueue (Celery) → Worker:
  1. Load latest prompt from prompts.py
  2. Call LLM provider (structured JSON output via function calling)
  3. Validate/normalize output (band within 0–9, step 0.5)
  4. Persist result
  5. Emit event (Realtime / notification) → client updates
```

- **Structured output:** prompts request strict JSON; response is parsed with Pydantic and re-validated (e.g., `BandScore` step check). Falls back to deterministic mock only in dev.
- **Prompt versioning:** each module uses a `PROMPT_VERSION` constant so outputs are reproducible & auditable.
- **Cost control:** model tier selection (mini vs full) based on task complexity and plan tier; caching for repeated/similar inputs (embedding hash).

### 5.3 Speaking Pipeline (new)

```
MediaRecorder (webm) → upload to Supabase Storage (audio/…)
  → Celery task: transcribe (Whisper/Deepgram)
  → Speaking Assessor (LLM) → transcript + scores + feedback
  → Persist assessment + emit Realtime notification
```

---

## 6. Scheduler Module

### 6.1 Responsibilities

1. **Daily rollover** (daily at 00:00 user-local): any `study_tasks` with `scheduled_date < today` and status `pending` are either:
   - marked `missed`, **or**
   - automatically rescheduled to the next available day(s) based on user's daily minutes budget (the "auto-shift unfinished work" requirement).
2. **Streak engine:** aggregate `daily_activity`; update `streaks`; detect break → reset current streak (grace window configurable).
3. **Exam countdown:** compute days-remaining; insert reminder notifications at configurable thresholds (e.g., T-30, T-14, T-7, T-1).
4. **Roadmap regeneration:** when a diagnostic/assessment changes the skill profile, or when the rescheduler shifts > N tasks, enqueue adaptive re-planning.
5. **Notification dispatcher:** daily reminder, streak-at-risk, AI feedback ready, resource-of-the-day.

### 6.2 Implementation

| Concern | Tool |
|---|---|
| Schedule definition | **Celery Beat** (cron, timezone-aware per user via UTC + offset) |
| Execution | **Celery worker** |
| Idempotency | job runs keyed by `(user_id, scheduled_date)` to avoid double-processing |
| Manual trigger | `/api/v1/scheduler/daily-rollover` (admin) + dry-run mode |
| Alternative (no infra) | **Supabase pg_cron** + Postgres function — good MVP fallback |

### 6.3 Algorithm — Auto-Shift Unfinished Tasks

```
FOR each user with tasks WHERE scheduled_date < today AND status = 'pending':
    daily_budget = user_goals.daily_minutes
    next_date = today
    FOR each overdue task ordered by (scheduled_date, priority):
        while task.duration_minutes > remaining_budget(next_date):
            next_date += 1 day
        assign task to next_date
        if next_date - today > MAX_SHIFT_DAYS (e.g., 14):
            merge/prioritize task (flag to planner)
    status(task) = 'rescheduled'
    emit Realtime update
```

---

## 7. Resource Engine

### 7.1 Responsibilities

- Maintain the **content catalog** (`resources` table): videos, articles, PDFs, practice tests, guides.
- **Search & filter** by skill, difficulty, type, provider, keyword.
- **Recommendation scoring**:
  - Base score: matches current skill gaps (from diagnostics/analytics).
  - Semantic similarity: pgvector cosine similarity between resource embedding and user profile embedding.
  - Recency & feedback loop: track `resource_recommendations.status` (viewed/saved/dismissed) to refine.
- **Surfacing:** dashboard "Recommended for you", resources page, task-attached resources (`study_tasks.resource_id`).

### 7.2 Pipeline

```
Curation (admin/manual or crawler) → normalize metadata → chunk & embed (OpenAI embeddings)
  → store in resources.embedding → index via pgvector
Query time: candidate filter (skill/tags) → vector search → LLM re-rank (optional)
  → persist recommendation with reason → return ranked list
```

---

## 8. Analytics Module

### 8.1 KPIs Computed

| KPI | Source | Method |
|---|---|---|
| Estimated band | `assessments` + `band_predictions` | Weighted moving average per criterion; prediction service |
| Skill gap | `assessments.criteria_scores` vs target | Delta per criterion; biggest-gap insight |
| Trend | historical band over time | SQL window functions + Recharts line |
| Streak | `daily_activity` | streak engine |
| Study time | `daily_activity.minutes` | daily/weekly/monthly aggregation |
| Countdown | `user_goals.exam_date` | days diff |
| Confidence score | `band_predictions.confidence` | prediction model |
| Task completion rate | `task_completions` / `study_tasks` | rolling 7/30-day |

### 8.2 Band Prediction Model

1. Feature vector: last N band scores per criterion (TR, CC, LR, GR), variance, study minutes, streak length, days-to-exam.
2. Method (MVP): **weighted regression** → predicted band rounded to nearest 0.5; confidence from residual variance and sample size.
3. Method (later): gradient-boosted model (LightGBM) trained on labeled dataset; keep deterministic fallback.
4. **Explainable output:** "Predicted Band 7.0 (±0.5) based on your last 12 assessments; Lexical Resource is your highest-leverage skill."

### 8.3 API Surface

```
GET /api/v1/analytics/overview            → band, countdown, streak, study time
GET /api/v1/analytics/trends?range=30d    → band score trend series
GET /api/v1/analytics/skill-gaps          → per-criterion current vs target
GET /api/v1/analytics/prediction          → predicted band + confidence + factors
GET /api/v1/analytics/export?format=pdf   → PDF report (WeasyPrint) or CSV
```

---

## 9. Authentication Flow

### 9.1 Current Implementation

- **Supabase Auth** on the frontend via `@supabase/supabase-js` (anon key).
- `useAuthStore` (Zustand) holds the session; `AuthInitializer` calls `initialize()` on mount.
- Methods: `login` (email/password), `signup`, `resetPassword`, `loginWithGoogle` (OAuth), `logout`.
- Backend `get_current_user` verifies the Bearer token via `supabase.auth.get_user(token)` and returns `user_id` (or `None`).

### 9.2 Target Flow (production)

```
1. Signup/Login (email+password | Google OAuth | magic link)
2. Supabase issues JWT (access + refresh) and sets auth cookies
3. Next.js middleware.ts validates session cookie → guards protected routes
4. Frontend attaches Bearer token to FastAPI requests via axios interceptor
5. FastAPI `get_current_user` dependency:
     - extracts token → verifies via Supabase (with Redis cache of verified tokens)
     - returns user_id + user profile
     - rejects with 401 if invalid/expired
6. Refresh-token rotation handled by @supabase/ssr on the client
7. All Postgres reads/writes governed by RLS (auth.uid())
8. On logout: signOut → clear cookies → redirect to landing
```

### 9.3 Roles

- `authenticated` user — own data only (RLS).
- `admin` (service-role / `app_metadata.role='admin'`) — manage resources, trigger scheduler, view system metrics.
- `anonymous` — public pages, resources browsing (optional), no personal data.

---

## 10. Folder Structure Recommendations

### 10.1 Backend (target)

```
backend/
├── app/
│   ├── main.py
│   ├── core/               # config, security, logging, exceptions
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── router.py       # aggregates all v1 routers
│   │       ├── auth.py
│   │       ├── assessments.py
│   │       ├── diagnostic.py
│   │       ├── roadmap.py
│   │       ├── analytics.py
│   │       ├── resources.py
│   │       ├── scheduler.py
│   │       ├── notifications.py
│   │       └── users.py
│   ├── services/
│   ├── repositories/
│   ├── ai/
│   │   ├── client.py
│   │   ├── prompts.py
│   │   └── modules/
│   ├── workers/            # Celery tasks
│   ├── scheduler/          # beat schedule + daily jobs
│   ├── models/             # Pydantic schemas
│   ├── db/
│   │   ├── supabase.py
│   │   └── migrations/
│   └── utils/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── requirements.txt
├── Dockerfile
├── alembic.ini (or SQL migrations dir)
├── .env.example
└── pyproject.toml (lint/format: ruff, mypy)
```

### 10.2 Frontend (target)

```
frontend/
├── src/
│   ├── app/                      # App Router routes
│   │   ├── (marketing)/          # landing, privacy, terms, cookies
│   │   ├── (auth)/login|signup|forgot-password
│   │   └── (app)/dashboard|writing|speaking|roadmap|analytics|
│   │            diagnostic/|resources|notifications|profile|settings
│   ├── components/
│   │   ├── ui/                   # existing design system
│   │   ├── shared/               # navbar, sidebar, footer
│   │   └── features/             # widget components per domain
│   ├── services/                 # typed API clients + TanStack Query hooks
│   ├── stores/                   # zustand (auth, ui)
│   ├── hooks/                    # useRoadmap, useStreak, useCountdown...
│   ├── types/
│   ├── lib/                      # utils, supabase client, constants
│   └── middleware.ts             # route guard
├── tests/                        # Vitest + React Testing Library
├── package.json
├── tailwind.config.ts
└── .env.example
```

### 10.3 Repository Root (target)

```
ielts-ai-coach/
├── ARCHITECTURE.md
├── TODO.md
├── backend/        (as above)
├── frontend/       (as above)
├── docs/           # API contract, product spec, design notes
├── docker-compose.yml   # local redis, postgres (optional), backend, worker
├── .github/workflows/   # CI: lint, test, build; CD: deploy
└── .env.example
```

---

## 11. Architectural Improvements (Priority-Ordered)

### P0 — Critical (unblocks the product vision)

1. **Backend is the source of truth.** Move roadmap, streak, prediction, and analytics logic from frontend mock data into FastAPI services. Frontend consumes real endpoints.
2. **Database schema & migrations.** Create all tables in §4.2 with RLS policies, enums, indexes. Add Alembic/SQL migrations.
3. **Async AI pipeline.** Introduce Celery + Redis; move essay/speaking/diagnostic analysis to workers; return job status; emit Realtime notifications when ready.
4. **Speaking transcription.** Add audio upload → Whisper/Deepgram → speaking assessor. Currently speaking feedback is non-existent server-side.
5. **Real auth guard.** Add `middleware.ts`; enforce 401/403; stop allowing `user_id: None` fallback on protected endpoints (the current `get_current_user` silently allows unauthenticated access).

### P1 — High Impact

6. **Roadmap Generator + adaptive re-planner.** Implement the phased roadmap generation and the auto-shift scheduler from §6.
7. **Band prediction service.** Implement weighted regression predictor + `band_predictions` table.
8. **Resource engine.** Populate `resources`; add search + recommendation endpoints with pgvector embeddings.
9. **Streak engine.** Daily activity aggregation + streak computation + Realtime streak badge.
10. **TanStack Query adoption** on the frontend; remove mock arrays; add optimistic task completion.

### P2 — Hardening & Scale

11. **API versioning** (`/api/v1`), rate limiting, idempotency keys, request size caps.
12. **Observability:** structured logging, Sentry (frontend+backend), OpenTelemetry traces on workers, health/readiness endpoints.
13. **Test suite:** unit tests for band rounding/streak/rollover; integration tests for endpoints; Playwright for critical flows.
14. **CI/CD:** GitHub Actions (lint → test → build → deploy backend + frontend); preview deployments.
15. **Cost controls:** prompt/model tiering, per-user AI quotas on free tier, caching.
16. **Multi-language/exam variants** (Academic vs General Training) reflected in roadmap content.

---

## 12. Technology Stack Summary

| Layer | Production Choice | Current |
|---|---|---|
| Frontend | Next.js 15 + Tailwind + TanStack Query + Zustand + Recharts | ✅ present (minus Query, live data) |
| Backend | FastAPI (modular monolith) | ✅ present (thin) |
| DB | Supabase Postgres + RLS + pgvector | ✅ present (unused schema) |
| Auth | Supabase Auth (JWT, OAuth, magic link) + cookies | ✅ present (JWT only) |
| Async | Celery + Redis (+ optional pg_cron MVP) | ❌ absent |
| AI | OpenAI GPT-4o-mini (orchestrated, structured output) | ⚠️ partial (single module, mock fallback) |
| Speech | Whisper / Deepgram STT + TTS | ❌ absent |
| Files | Supabase Storage | ⚠️ configured in next.config only |
| Realtime | Supabase Realtime | ❌ absent |
| Observability | Sentry + Logfire + OpenTelemetry | ❌ absent |
| CI/CD | GitHub Actions + Vercel + Railway/Render | ❌ absent |

---

## 13. Suggested Implementation Phases

- **Phase A — Foundation (2–3 weeks):** DB schema + RLS + migrations; auth hardening + middleware; replace mock data with real endpoints for dashboard/analytics; assessment pipeline async.
- **Phase B — Core Loops (3–4 weeks):** diagnostic flow end-to-end; roadmap generator; daily scheduler/auto-shift; streak engine; notifications.
- **Phase C — Differentiators (3–4 weeks):** band prediction; resource engine + recommendations; speaking transcription pipeline; PDF report export.
- **Phase D — Scale (ongoing):** observability, tests, CI/CD, cost controls, A/B on adaptive algorithms.

---

*This document is a living artifact. Once approved, it will be broken down into a tracked implementation plan (TODO.md) and executed incrementally.*

