# IELTS AI Coach — Complete Software Design Document

**Document Version:** 1.0  
**Status:** Final — Master Blueprint  
**Audience:** Software Engineering Team  
**Last Updated:** 2025-05-15  

---

## Table of Contents

1. Executive Summary
2. Functional Requirements
3. Non-Functional Requirements
4. System Architecture
5. Database Design
6. API Design
7. Folder Structure
8. Security
9. Performance
10. Scalability
11. Accessibility
12. Future Features
13. Deployment Strategy
14. Testing Strategy
15. Risk Analysis
16. Assumptions
17. Edge Cases

---

## 1. Executive Summary

### 1.1 Product Vision

IELTS AI Coach is an **adaptive, AI-powered IELTS preparation platform** that provides personalized study roadmaps, real-time writing and speaking assessment, progress analytics, and gamified motivation — all at a fraction of the cost of human tutoring. The platform transforms a user's diagnostic score, target band, exam date, and daily study budget into a **dynamic, self-correcting daily mission plan** that continuously adapts to their performance.

### 1.2 Current State

The product exists as a **UI-driven prototype** with a thin FastAPI backend. The frontend (Next.js 15 + Tailwind + Zustand) renders a rich, polished experience across landing, auth, dashboard, writing, speaking, diagnostic, roadmap, analytics, resources, notifications, and settings pages. The backend exposes three endpoints (`/health`, `POST /assess`, `GET /results/{user_id}`) with a single writing-assessment AI call. All roadmap, analytics, streak, and band-prediction logic currently lives as **hard-coded mock data** inside React components.

### 1.3 Target Architecture

The target architecture is a **modular monolith** (FastAPI backend) with a **Next.js 15 SPA frontend**, **Supabase** as the BaaS (Auth, PostgreSQL, Storage, Realtime), **Celery + Redis** for async AI processing, and a **continuous AI Brain** that unifies all signals into a single Live User State. The platform is designed to scale from 1 to 1,000,000+ users without architectural changes.

### 1.4 Key Design Principles

| Principle | Description |
|---|---|
| **Server is the source of truth** | All business rules (band rounding, streak calc, task rescheduling) live in the backend, never in React components |
| **Async-first AI** | Heavy AI work runs in Celery workers; clients poll or get pushed results via Supabase Realtime |
| **Adaptive by design** | Every user action feeds an event stream that triggers roadmap re-computation |
| **Row-Level Security (RLS)** | Users can only access their own data; the backend uses service-role key only for trusted server-side operations |
| **Explainable AI** | Every inference output ships with contributing factors, confidence, and model version |
| **Pedagogically honest gamification** | Gamification rewards effort and consistency, never inflating band scores |

---

## 2. Functional Requirements

### 2.1 User Journey Modules

#### FR1: Landing & Marketing
- Display hero section with value proposition, features grid, how-it-works, testimonials, FAQ, and final CTA
- Server-render for SEO with structured data for rich snippets
- Redirect authenticated users to `/dashboard`
- Serve static content with skeleton loaders on slow connections

#### FR2: Authentication
- **Registration:** Email/password signup with Full Name, Email, Password, Confirm Password; Google OAuth
- **Login:** Email/password login with "Forgot Password" flow; Google OAuth; session management
- **Password Reset:** Email-based reset flow with secure token; redirect to login on completion
- **Session Management:** JWT-based auth with refresh token rotation; Supabase Auth cookies
- **Email Verification:** Optional email verification with resend capability

#### FR3: Onboarding (Profile Setup)
- One-time profile setup after registration
- Collect: Full Name, Country, Timezone, Target Band (5.0–9.0), Exam Date, Module (Academic/General), Daily Study Commitment
- Auto-detect timezone with manual override
- Validate exam date (future, max 2 years)
- Provide "Skip for now" with defaults (Band 6.5, Academic, 60 min/day, 3 months out)
- Warn on exam date < 30 days (intensive plan) or > 1 year (relaxed plan)

#### FR4: Diagnostic Test
- 3-section assessment: Writing (10-min essay), Speaking (5-min recording), Vocabulary (5-min quiz)
- **Writing:** Timer, prompt, text editor with word count, auto-submit on expiry, min 50 words
- **Speaking:** Microphone permission, recording with waveform visualization, 2-min limit, Whisper transcription
- **Vocabulary:** 10 multiple-choice questions, 5-min timer, auto-submit
- **Results Calculation:** Average of 3 sections → overall band (0.5 step), per-criterion scores, CEFR level, strengths/weaknesses, AI tip
- Save progress mid-way; allow resume within 7 days
- Allow retake after 30 days (or on-demand for Pro users)

#### FR5: Diagnostic Results Report
- Display overall band score with circular gauge, CEFR level, target comparison
- Show skill breakdown (4 criteria: Grammatical Range, Lexical Resource, Coherence & Cohesion, Fluency & Pronunciation)
- List strengths (top 2) and weaknesses (bottom 2)
- Provide AI-generated actionable tip
- "Generate My Study Roadmap" CTA → triggers roadmap generation
- "Download PDF Report" option

#### FR6: Roadmap Generation
- Generate personalized phased study plan based on diagnostic results, target band, exam date, and daily commitment
- **5 Phases:** Foundation (30%), Skill Building (30%), Advanced (20%), Mock Tests (15%), Revision (5%)
- Each phase has tasks with skill tags, durations, and scheduled dates
- Generate first 7 days of daily missions
- Schedule mock tests at appropriate intervals
- Protect revision windows (last 14 days) from carry-forward
- Handle timeline compression/extension on exam date changes
- Show loading progress during generation (Phase 2 of 5 complete)

#### FR7: Dashboard (Home)
- **17 widgets across 4 zones:**
  - **Zone 1 (Goal Cluster):** Exam Countdown, Predicted Band, Target Band, Readiness Score, Current Streak
  - **Zone 2 (Action Surface):** Today's Mission, Quick Continue, Daily Progress
  - **Zone 3 (Progress Rail):** Daily XP, Upcoming Mock, Weakest/Strongest Skill, Weekly/Monthly Progress
  - **Zone 4 (Discovery Shelf):** Recommended Resources, Achievements, Notifications
- BFF aggregation endpoint for above-fold rendering
- Per-widget lazy loading with skeletons
- Realtime updates via Supabase Realtime channels
- Responsive zone model with mobile degradation

#### FR8: Daily Mission
- Primary work screen showing today's scheduled tasks
- Task types: Writing, Speaking, Vocabulary, Grammar, Reading, Listening, Review, Mock Test
- Each task has: checkbox, title, skill badge, duration, resource link, status (overdue/carry-forward/new/in-progress/completed)
- Inline workspace for each task type (editor, recorder, quiz, etc.)
- Carry-forward overdue tasks with priority increase
- Track study time via auto-tracking (page focus)
- Mission complete celebration state
- Rest day state with streak preservation

#### FR9: Writing Assessment
- Task selection (Task 1 or Task 2) with prompt display
- Text editor with word count (150+ for T1, 250+ for T2)
- Timer (20 min for T1, 40 min for T2)
- Auto-submit on timer expiry
- AI analysis: band score, 4-criteria scores, feedback, corrections
- Async AI processing with polling/realtime notification
- Draft persistence (local storage + server save)

#### FR10: Speaking Assessment
- 3-part structure: Part 1 (intro, 4 min), Part 2 (cue card, 3 min), Part 3 (discussion, 8 min)
- Microphone recording with waveform visualization
- Audio upload to Supabase Storage
- Async transcription via Whisper/Deepgram
- AI analysis: band score, fluency/pronunciation/lexis/grammar scores, feedback
- Fallback to text input if microphone unavailable

#### FR11: Progress & Analytics
- Band Score Trend (line chart over time)
- Skill Gap Analysis (bar chart with target markers)
- Study Time Distribution (pie chart by skill)
- Streak Calendar (month grid with activity coloring)
- Test History Table (date, type, topic, band, status)
- Export to PDF/CSV
- Time range filter (7d, 30d, 90d, all)

#### FR12: Mock Tests
- Full IELTS simulation: Listening (30 min), Reading (60 min), Writing (60 min), Speaking (15 min)
- 4-section progress bar
- Timed sections with auto-submit
- Post-mock review: overall band, section scores, mistake analysis, comparison vs predicted/target
- Scheduled by Adaptive Scheduler with increasing frequency
- Pre-mock light review day, post-mock mistake review day

#### FR13: Resource Engine
- Curated catalog of 1,000+ free resources from 7 official providers
- 10 resource types: YouTube, PDF, Website, Vocab Sheet, Grammar Guide, Listening, Writing Sample, Speaking, Practice Test, Strategy
- 12 skill tags for filtering
- Personalized recommendations via composite scoring (skill gap, band match, popularity, diversity, recency, provider, scheduler alignment)
- Bookmark system with collections, notes, priority
- Completion tracking with progress detection (scroll depth, watch percentage)
- Search and filter by skill, type, provider, difficulty, band range, duration, rating

#### FR14: Adaptive Scheduler
- Daily mission generation adjusting to user's budget and phase
- Carry-forward algorithm for missed tasks (shift to next available day, increase priority)
- Overload prevention (daily/weekly overload detection, priority merge, recovery days)
- Phase transition logic (80% completion OR time elapsed)
- Protected day system (revision, mock, rest, streak saver)
- Recalculation engine (remaining hours, daily workload, predicted band, mock schedule, revision schedule)
- Planned vacation mode (streak freeze, no task scheduling)

#### FR15: AI Brain (Decision Engine)
- Continuous evaluation loop: Ingest → Feature → State → Infer → Decide → Act → Learn
- 7 inference modules: Predicted Band, Readiness Score, Risk Score, Probability of Target, Recommended Hours, Weakest Topics, Next Best Tasks
- Live User State (JSON document, cached in Redis)
- Event-driven recompute (assessment, task, session, mock, diagnostic)
- Nightly full recompute
- Explainability contract (contributing factors, confidence, model version, human-readable reason)
- Self-calibration via outcome capture (mock scores, exam results)

#### FR16: Gamification
- XP Engine: activity-based XP with multipliers (difficulty, skill, combo, perfect, consistency)
- Level System: 20 levels with progressive XP curve, unlockable rewards
- 3-Tier Streak System: Daily, Weekly, Monthly with freeze, repair, vacation mode
- 50+ Achievements across 10 categories
- 8-Tier Badge System (Bronze → Legend)
- Daily/Weekly/Monthly Challenges with adaptive selection
- Multi-Currency Rewards: XP, Gems, Coins
- League System: 7 tiers (Bronze → Legend), weekly seasons, promotion/demotion
- Redis-backed Leaderboard with anti-cheat

#### FR17: Notifications
- Types: Morning Reminder, Streak Reminder, Streak at Risk, Streak Broken, Challenge Reminder, League Promotion/Demotion, Achievement Unlocked, Badge Earned, Level Up, XP Milestone, AI Feedback Ready
- Channels: In-app, Push (opt-in), Email (opt-in)
- Delivery rules: Quiet hours (22:00–08:00), frequency cap (5/day), per-type toggle, cooldown

### 2.2 User Roles & Permissions

| Role | Permissions |
|---|---|
| **Anonymous** | View landing page, public resources (browsing only) |
| **Authenticated (Free)** | Own data only (RLS), all features with daily XP cap (300), basic gamification |
| **Authenticated (Pro)** | Own data + 500 XP cap, premium features, extended diagnostics |
| **Admin** | Manage resources, trigger scheduler, view system metrics, user management |

---

## 3. Non-Functional Requirements

### 3.1 Performance

| Requirement | Target | Measurement |
|---|---|---|
| Dashboard time-to-interactive | < 2 seconds | Lighthouse, Web Vitals |
| API response time (p95) | < 500ms for read endpoints, < 5s for AI assessment | APM monitoring |
| AI assessment completion | < 30 seconds (async) | Task tracking |
| Page load (above-fold) | < 1.5 seconds | Core Web Vitals (LCP) |
| Realtime notification delivery | < 500ms | Supabase Realtime latency |
| Database query time (p99) | < 200ms | pg_stat_statements |
| Leaderboard rendering | < 1 second | Redis sorted set performance |

### 3.2 Availability

| Metric | Target |
|---|---|
| Uptime | 99.9% (8.76 hours/year max downtime) |
| Maintenance windows | Weekly, 1-hour, announced 48h in advance |
| Degraded mode | Dashboard serves cached data if backend unreachable |
| Disaster recovery | RPO < 15 minutes, RTO < 1 hour |

### 3.3 Reliability

| Concern | Strategy |
|---|---|
| AI assessment failure | Retry (3x), fallback to deterministic mock, partial diagnostic |
| Database connection loss | Connection pooling, retry logic, circuit breaker |
| Celery worker crash | Auto-restart, task retry with backoff, dead letter queue |
| Supabase outage | Backend caching, read-replica fallback, graceful degradation |
| Redis failure | Fallback to Postgres for leaderboard, disable realtime features |

### 3.4 Security

| Requirement | Implementation |
|---|---|
| Authentication | Supabase Auth (JWT, OAuth, magic link) + refresh token rotation |
| Authorization | RLS on all user-owned tables, service-role key server-only |
| API security | JWT verification, rate limiting, CORS, input validation, size caps |
| Data encryption | TLS 1.3 in transit, AES-256 at rest (Supabase managed) |
| AI safety | Prompt injection prevention, output validation, content filtering |
| Audit logging | All auth events, admin actions, sensitive data access logged |

### 3.5 Scalability

| Requirement | Target |
|---|---|
| Concurrent users | 10,000+ (initial), 1,000,000+ (target) |
| Database scaling | Read replicas, partitioning (monthly for event tables), connection pooling |
| AI processing | Celery worker auto-scaling, queue prioritization |
| Static assets | CDN (Vercel Edge Network) |
| Session storage | Supabase (managed), Redis for cache |

### 3.6 Maintainability

| Requirement | Practice |
|---|---|
| Code quality | ESLint, Prettier, mypy, ruff, pre-commit hooks |
| Documentation | Inline docstrings, API docs (OpenAPI), ADRs |
| Monitoring | Sentry (errors), Logfire/OpenTelemetry (traces), health endpoints |
| CI/CD | GitHub Actions: lint → test → build → deploy |
| Feature flags | LaunchDarkly or custom toggle system for gradual rollouts |

### 3.7 Accessibility

| Requirement | Standard |
|---|---|
| WCAG compliance | WCAG 2.1 AA minimum |
| Keyboard navigation | All interactive elements reachable and operable via keyboard |
| Screen reader support | ARIA labels, semantic HTML, focus management |
| Color contrast | 4.5:1 minimum for normal text, 3:1 for large text |
| Motion sensitivity | Respect `prefers-reduced-motion` |
| Language | English (primary), i18n architecture for future expansion |

---

## 4. System Architecture

### 4.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT (Browser)                                   │
│                                                                               │
│   Next.js 15 App Router — Vercel Edge Network                                │
│   ├── Server Components (RSC): Landing, Legal, SEO pages                     │
│   ├── Client Components ("use client"): All interactive dashboard pages       │
│   ├── Zustand Stores: Auth session, UI toggles, active recording state       │
│   ├── TanStack Query: Server state (assessments, roadmap, analytics, etc.)   │
│   └── API Client (axios): Typed service functions per domain                  │
└──────────────────┬──────────────────────────────────────────┬────────────────┘
                   │ HTTPS (JWT Bearer)                        │ HTTPS (Supabase SDK)
                   ▼                                           ▼
┌──────────────────────────────────────┐       ┌──────────────────────────────────┐
│        BACKEND — FastAPI             │       │        SUPABASE (BaaS)            │
│  (Railway / Render / Fly.io)         │       │  ┌────────────────────────────┐   │
│  ├── API Routers (/api/v1/*)         │       │  │ Auth (JWT, OAuth, MFA)     │   │
│  ├── Services (Domain Logic)         │       │  ├────────────────────────────┤   │
│  ├── AI Module (LLM orchestration)   │       │  │ PostgreSQL 15 + pgvector   │   │
│  ├── Brain Engine (Decision Engine)  │       │  │ + RLS Policies             │   │
│  ├── Scheduler (Daily Rollover)      │       │  ├────────────────────────────┤   │
│  ├── Resource Engine (Recommend)     │       │  │ Storage (audio, avatars,   │   │
│  ├── Gamification Engine            │       │  │  PDF reports)              │   │
│  └── Worker Jobs (Celery)            │       │  ├────────────────────────────┤   │
│                                │              │  │ Realtime (streaks,         │   │
│                                │              │  │  notifications, brain)    │   │
│                                ▼              │  └────────────────────────────┘   │
│                      ┌──────────────────┐     └──────────────────────────────────┘
│                      │   Redis          │
│                      │  (Cache + Queue) │
│                      └──────────────────┘
│                                │
│                                ▼
│                      ┌──────────────────────────────────────┐
│                      │   EXTERNAL AI PROVIDERS              │
│                      │  ├── OpenAI (GPT-4o-mini / gpt-4o)   │
│                      │  ├── Whisper / Deepgram (STT)        │
│                      │  └── TTS Provider (Speaking practice)│
│                      └──────────────────────────────────────┘
```

### 4.2 Architectural Style

| Decision | Choice | Rationale |
|---|---|---|
| Backend pattern | **Modular Monolith** (FastAPI) | Fast to ship, single deployable, easy to split into microservices later |
| Frontend framework | **Next.js 15 (App Router) + SSR** | SEO for landing, code-splitting, middleware for route guards |
| Backend-as-a-Service | **Supabase** | Auth, Postgres, Storage, Realtime out of the box |
| Async processing | **Celery + Redis** | Long-running AI tasks (essay analysis, speaking transcription, roadmap regeneration) |
| AI orchestration | **Backend service layer** | Keeps prompt/LLM logic server-side; swappable providers |
| Real-time | **Supabase Realtime** | Streaks, notification badges, live countdown, Brain updates |
| State management | **Zustand (client) + TanStack Query (server)** | Separation of ephemeral vs remote state |

### 4.3 Component Descriptions

#### 4.3.1 Frontend (Next.js 15)

| Layer | Technology | Responsibility |
|---|---|---|
| Pages | Next.js App Router | Route definitions, page composition, layout nesting |
| UI Components | Tailwind CSS + shadcn-style | Atomic design system (buttons, cards, inputs, modals, etc.) |
| Shared Components | React components | Navbar, Sidebar, Footer, Auth guards |
| Feature Components | Per-domain widgets | StreakCard, BandTrendChart, TaskItem, RecommendationCard |
| Services | axios + typed clients | API calls per domain (assessments, roadmap, analytics, etc.) |
| Stores | Zustand | Auth session, UI toggles, recording state |
| Hooks | TanStack Query | useAssessment, useRoadmap, useStreak, useCountdown |
| Types | TypeScript | Shared domain types, API response contracts |

#### 4.3.2 Backend (FastAPI)

| Layer | Responsibility |
|---|---|
| API Routers | HTTP endpoints, request validation, response serialization |
| Services | Business logic (no HTTP/DB awareness) |
| Repositories | Data access (Supabase/Postgres), typed queries |
| AI Module | LLM orchestration, prompt management, structured output parsing |
| Brain Engine | Continuous evaluation, inference modules, decision bundle |
| Scheduler | Daily rollover, carry-forward, phase transitions, overload prevention |
| Resource Engine | Content catalog, recommendation scoring, bookmark management |
| Gamification Engine | XP, levels, streaks, achievements, challenges, leagues |
| Workers | Celery tasks for async AI, scheduler, notifications |
| Models | Pydantic schemas for request/response |

### 4.4 Data Flow Patterns

#### 4.4.1 AI Assessment Flow (Writing Example)

```
1. User submits essay → POST /api/v1/assessments/writing
2. API validates input (word count, content hash)
3. Service persists essay to `assessments` table (status: 'processing')
4. Celery task enqueued: `analyze_writing.delay(assessment_id)`
5. API returns 202 Accepted with `assessment_id`
6. Frontend polls GET /api/v1/assessments/{id} or subscribes to Realtime
7. Celery worker:
   a. Loads assessment from DB
   b. Calls OpenAI with structured prompt (function calling)
   c. Parses response → band score, criteria scores, feedback, corrections
   d. Validates output (band rounding, range checks)
   e. Persists result to `assessments` table (status: 'completed')
   f. Inserts rows into `progress` table
   g. Publishes event to Brain event bus
   h. Creates notification (ai_feedback ready)
8. Frontend receives Realtime update → renders feedback
```

#### 4.4.2 Daily Rollover Flow

```
1. Celery Beat triggers `daily_rollover` task at 00:00 user-local
2. For each user (batched in groups of 10,000):
   a. Check exam date (passed? → post-exam mode)
   b. Detect missed tasks from yesterday
   c. Carry forward missed tasks (with overload check)
   d. Recalculate remaining hours and daily workload
   e. Generate today's mission (next_best_tasks from Brain)
   f. Check phase transition (80% completion or time elapsed)
   g. Update streak (daily, weekly, monthly)
   h. Recalculate predicted band
   i. Check mock test scheduling
   j. Mitigate overload
   k. Send daily notification
3. Emit Realtime events for affected users (mission, streak, notifications)
```

#### 4.4.3 Brain Recomputation Flow (Event-Triggered)

```
1. Domain event published (e.g., assessment.completed)
2. Brain event subscriber receives event
3. Feature pipeline recomputes affected feature groups
4. Live User State updated incrementally
5. Affected inference modules recomputed (dependency order):
   M1 Predicted Band → M6 Weakest Topics → M7 Next Best Tasks
   → M2 Readiness → M3 Risk → M4 Probability → M5 Hours
6. Decision Bundle persisted and cached in Redis
7. Realtime event emitted: `user:{id}:brain` with updated bundle
8. Dashboard widgets update reactively
```

### 4.5 Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                        │
│  LandingPage ← AuthPages ← Onboarding ← Diagnostic ← Results ← Roadmap     │
│      ↓                                                                       │
│  Dashboard ─→ Today'sMission ─→ Writing/Speaking Workspace                  │
│      ↓                          ↓                                             │
│  Analytics ← Assessments ← AI Brain Feedback                                │
│      ↓                                                                       │
│  Resources ← ResourceEngine                                                  │
│      ↓                                                                       │
│  Notifications ← Gamification Events                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                          │ API calls
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                         │
│                                                                               │
│  ┌─────────────────┐    ┌──────────────────┐    ┌────────────────────────┐  │
│  │  API Routers     │    │   Services       │    │   AI Module            │  │
│  │  ├─ auth         │◄──►│  ├─ assessment   │◄──►│  ├─ writing_assessor  │  │
│  │  ├─ assessments  │    │  ├─ diagnostic   │    │  ├─ speaking_assessor  │  │
│  │  ├─ diagnostic   │    │  ├─ roadmap      │    │  ├─ diagnostic_analyzer│  │
│  │  ├─ roadmap      │    │  ├─ streak       │    │  ├─ roadmap_generator  │  │
│  │  ├─ analytics    │    │  ├─ prediction   │    │  └─ resource_recommender│  │
│  │  ├─ resources    │    │  ├─ resource     │    └────────────────────────┘  │
│  │  ├─ scheduler    │    │  ├─ notification │    ┌────────────────────────┐  │
│  │  ├─ brain        │    │  └─ user         │    │   Brain Engine         │  │
│  │  ├─ gamification │    └──────────────────┘    │  ├─ M1 Band Predictor  │  │
│  │  └─ users        │         │                  │  ├─ M2 Readiness       │  │
│  └─────────────────┘          │                  │  ├─ M3 Risk            │  │
│                               │                  │  ├─ M4 Probability     │  │
│  ┌─────────────────┐          │                  │  ├─ M5 Hours           │  │
│  │   Repositories   │◄────────┘                  │  ├─ M6 Weakest Topics  │  │
│  │  ├─ assessment   │                            │  └─ M7 Next Tasks     │  │
│  │  ├─ roadmap      │    ┌──────────────────┐    └────────────────────────┘  │
│  │  ├─ streak       │    │   Scheduler       │                               │
│  │  ├─ resource     │    │  ├─ daily_rollover │                               │
│  │  └─ user         │    │  ├─ carry_forward  │                               │
│  └─────────────────┘    │  ├─ phase_transition│                               │
│                          │  └─ overload_mitigate│                               │
│  ┌─────────────────┐    └──────────────────┘                               │
│  │   Workers        │                                                       │
│  │  ├─ assessment   │    ┌──────────────────┐                               │
│  │  ├─ speaking     │    │  Gamification     │                               │
│  │  ├─ roadmap      │    │  ├─ XP engine     │                               │
│  │  └─ scheduler    │    │  ├─ streak engine │                               │
│  └─────────────────┘    │  ├─ achievements   │                               │
│                          │  ├─ challenges    │                               │
│  ┌─────────────────┐    │  └─ leagues       │                               │
│  │   Supabase/DB    │◄───┘                   │                               │
│  │  ├─ PostgreSQL   │    └──────────────────┘                               │
│  │  ├─ Storage      │                                                       │
│  │  └─ Realtime     │                                                       │
│  └─────────────────┘                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Database Design

### 5.1 Platform

- **Supabase PostgreSQL 15+** with pgvector extension
- **RLS enabled** on all user-owned tables
- **Migrations:** Supabase SQL migrations (versioned)
- **Enums:** PostgreSQL enums for domain values

### 5.2 Entity Catalog

| # | Entity | Purpose | Owner |
|---|--------|---------|-------|
| 1 | `users` | Application profile for authenticated users | User |
| 2 | `user_goals` | User's target band, exam date, daily budget | User |
| 3 | `diagnostic_results` | Baseline assessment results | User |
| 4 | `assessments` | Writing and speaking assessment results | User |
| 5 | `study_plans` | Versioned, personalized roadmap | User |
| 6 | `roadmap_phases` | Phase within a study plan | User |
| 7 | `study_tasks` | Individual study activities | User |
| 8 | `task_completions` | Task completion records | User |
| 9 | `daily_plans` | Daily aggregated task plan | User |
| 10 | `daily_activity` | Daily activity log (streak engine input) | User |
| 11 | `streaks` | Current/pending streak state | User |
| 12 | `study_sessions` | Focused study sessions | User |
| 13 | `resources` | Content catalog (public, no RLS) | Public |
| 14 | `resource_recommendations` | Per-user AI recommendations | User |
| 15 | `resource_bookmarks` | User bookmarks with collections | User |
| 16 | `resource_completions` | Resource completion tracking | User |
| 17 | `resource_views` | Analytics events | User |
| 18 | `mock_tests` | Mock exam results and diagnostic baseline | User |
| 19 | `band_predictions` | Predicted band model output | User |
| 20 | `progress` | Skill-level band history per criterion | User |
| 21 | `vocabulary` | User's personal word bank with SRS metadata | User |
| 22 | `notifications` | In-app notification feed | User |
| 23 | `live_user_state` | AI Brain's working memory (JSON) | User |
| 24 | `skill_profiles` | Normalized per-skill bands and trends | User |
| 25 | `topic_profiles` | Per-topic aggregates | User |
| 26 | `decision_bundles` | Latest computed Brain bundle | User |
| 27 | `decision_log` | Append-only audit trail of Brain decisions | System |
| 28 | `gamification_state` | Aggregate XP, level, gems, coins, league | User |
| 29 | `xp_ledger` | Append-only XP event log | User |
| 30 | `streak_state` | Three-tier streak tracking | User |
| 31 | `user_achievements` | Achievement unlock records | User |
| 32 | `achievement_catalog` | Master list of all achievements | System |
| 33 | `challenge_progress` | Daily/weekly/monthly challenge tracking | User |
| 34 | `league_groups` | League group assignments per season | System |
| 35 | `league_group_members` | User membership in league groups | User |
| 36 | `leaderboard_snapshots` | Historical leaderboard data | System |
| 37 | `reward_catalog` | Available rewards and costs | System |
| 38 | `user_rewards` | Items the user has purchased | User |

### 5.3 Key Entity Relationships

```
auth.users
    │
    ▼
users (1:1 with auth.users)
    ├── 1:1 → user_goals
    ├── 1:1 → streaks
    ├── 1:1 → streak_state
    ├── 1:N → study_plans
    │       └── 1:N → roadmap_phases
    │               └── 1:N → study_tasks
    │                       └── 1:N → task_completions
    ├── 1:N → daily_plans
    │       └── 1:N → study_tasks
    ├── 1:N → assessments
    ├── 1:N → diagnostic_results
    ├── 1:N → mock_tests
    ├── 1:N → progress
    ├── 1:N → study_sessions
    ├── 1:N → daily_activity
    ├── 1:N → vocabulary
    ├── 1:N → notifications
    ├── 1:N → band_predictions
    ├── 1:1 → live_user_state
    ├── 1:N → skill_profiles
    ├── 1:N → topic_profiles
    ├── 1:N → resource_recommendations
    ├── 1:N → resource_bookmarks
    ├── 1:N → resource_completions
    ├── 1:1 → gamification_state
    ├── 1:N → xp_ledger
    ├── 1:N → user_achievements
    ├── 1:N → challenge_progress
    └── 1:N → user_rewards

resources (public, no RLS)
    ├── 1:N → resource_recommendations
    ├── 1:N → resource_bookmarks
    ├── 1:N → resource_completions
    └── N:M → study_tasks (via task_resources)
```

### 5.4 Indexing Strategy

| Table | Index | Type | Purpose |
|---|---|---|---|
| `users` | `email` | UNIQUE B-tree | Login lookup |
| `users` | `exam_date` | B-tree | Countdown/reminder scans |
| `study_tasks` | `(user_id, scheduled_date)` | Composite B-tree | Daily planner query |
| `study_tasks` | `(user_id, status)` | Partial B-tree | Overdue task scan |
| `daily_plans` | `(user_id, plan_date)` | UNIQUE composite | Daily dashboard query |
| `assessments` | `(user_id, created_at DESC)` | Composite B-tree | History view |
| `progress` | `(user_id, criterion, recorded_at DESC)` | Composite B-tree | Trend queries |
| `resources` | `tags` | GIN | Tag filtering |
| `resources` | `embedding` | HNSW (pgvector) | Semantic search |
| `xp_ledger` | `(user_id, created_at DESC)` | Composite B-tree | XP history |
| `notifications` | `(user_id, is_read, created_at)` | Composite B-tree | Unread badge |
| `study_sessions` | `(user_id, started_at DESC)` | Composite B-tree | Recent sessions |

### 5.5 Partitioning Strategy

| Table | Partition Key | Type | Trigger |
|---|---|---|---|
| `xp_ledger` | `created_at` | Monthly range | > 10M rows |
| `decision_log` | `computed_at` | Monthly range | > 5M rows |
| `resource_views` | `created_at` | Monthly range | > 10M rows |
| `study_sessions` | `started_at` | Monthly range | > 50M rows |
| `task_completions` | `completed_at` | Monthly range | > 50M rows |

---

## 6. API Design

### 6.1 API Versioning & Conventions

- **Base URL:** `/api/v1`
- **Authentication:** JWT Bearer token in `Authorization` header
- **Response format:** Consistent JSON envelope with `response_model` using Pydantic
- **Error format:** `{"detail": {"code": "ERROR_CODE", "message": "Human-readable message", "fields": {...}}}`
- **Pagination:** `limit` + `offset` or cursor-based for history endpoints
- **Idempotency:** `Idempotency-Key` header on assessment submissions
- **Rate limiting:** Per-user and per-IP, varying by endpoint sensitivity

### 6.2 Endpoint Summary

| Module | Endpoints | Auth | Rate Limit |
|---|---|---|---|
| **Auth** | POST /auth/signup, POST /auth/login, POST /auth/logout, POST /auth/reset-password, POST /auth/google | None | 10/min |
| **Users** | GET /users/me, PUT /users/me, PUT /users/me/goals | JWT | 30/min |
| **Assessments** | POST /assessments/writing, POST /assessments/speaking, GET /assessments/{id}, GET /assessments | JWT | 10/min |
| **Diagnostic** | POST /diagnostic/start, POST /diagnostic/writing, POST /diagnostic/speaking, POST /diagnostic/vocabulary, GET /diagnostic/result | JWT | 5/min |
| **Roadmap** | GET /roadmap, POST /roadmap/generate, GET /roadmap/phases, PUT /roadmap/phases/{id}/tasks/{id}/complete | JWT | 10/min |
| **Dashboard** | GET /dashboard/overview, GET /dashboard/mission, GET /dashboard/skills, GET /dashboard/progress, GET /dashboard/xp, GET /dashboard/mocks/next, GET /dashboard/continue | JWT | 30/min |
| **Analytics** | GET /analytics/overview, GET /analytics/trends, GET /analytics/skill-gaps, GET /analytics/prediction, GET /analytics/export | JWT | 20/min |
| **Resources** | GET /resources, GET /resources/search, GET /resources/{id}, POST /resources/{id}/view, GET /bookmarks, POST /bookmarks, PUT /bookmarks/{id}, DELETE /bookmarks/{id} | JWT | 30/min |
| **Recommendations** | GET /recommendations, POST /recommendations/{id}/dismiss, POST /recommendations/refresh | JWT | 10/min |
| **Brain** | GET /brain/state, GET /brain/prediction, GET /brain/readiness, GET /brain/risk, GET /brain/probability, GET /brain/hours, GET /brain/weakest-topics, POST /brain/recompute | JWT | 20/min |
| **Scheduler** | POST /scheduler/daily-rollover (admin), GET /scheduler/status | Admin | 1/min |
| **Gamification** | GET /gamification/state, GET /gamification/xp/ledger, GET /gamification/streaks, POST /gamification/streaks/freeze, GET /gamification/achievements, GET /gamification/badges, GET /gamification/challenges/daily, GET /gamification/leagues/current, GET /gamification/leaderboard, GET /gamification/rewards, POST /gamification/rewards/redeem | JWT | 20/min |
| **Notifications** | GET /notifications, PUT /notifications/{id}/read, PUT /notifications/read-all | JWT | 30/min |
| **Health** | GET /health, GET /health/ready | None | 60/min |

### 6.3 Key API Contracts

#### GET /api/v1/dashboard/overview

```json
{
  "countdown": { "exam_date": "2025-06-15", "days_left": 47, "intensity": "focused" },
  "target_band": 7.5,
  "predicted_band": { "band": 6.5, "trend": 0.0, "confidence": 0.7, "last_updated": "2025-04-29T22:10:00Z" },
  "readiness": { "score": 62, "label": "On Track", "explanation": "Your mock average is your biggest lever." },
  "streak": { "current": 6, "longest": 14, "at_risk": false, "frozen": false }
}
```

#### GET /api/v1/brain/state

```json
{
  "predicted_band": { "overall": 6.8, "per_skill": {"writing": 6.5, "speaking": 7.0, ...}, "confidence": 0.7 },
  "readiness": { "score": 62, "label": "On Track", "components": {...} },
  "risk": { "score": 41, "label": "Moderate", "factors": {...} },
  "probability_target": { "p": 0.43, "band": "40–50%", "calibrated": true },
  "recommended_hours": { "weekly": 9, "per_skill": {...}, "pacing": "steady" },
  "weakest_topics": [{"topic": "opinion_essay", "skill": "writing", "avg_band": 6.0, "gap": 1.5}],
  "next_best_tasks": [{"task_id": "...", "title": "...", "score": 85, "reason": "..."}]
}
```

### 6.4 Realtime Channels

| Channel | Events | Payload |
|---|---|---|
| `user:{id}:notifications` | INSERT, UPDATE | `{ type, title, body, count }` |
| `user:{id}:activity` | INSERT/UPDATE | `{ daily_xp, streak, minutes }` |
| `user:{id}:tasks` | UPDATE | `{ task_id, status, mission_progress }` |
| `user:{id}:assessments` | INSERT | `{ assessment_id, status }` |
| `user:{id}:brain` | UPDATE | `{ bundle: DecisionBundle }` |
| `user:{id}:gamification` | UPDATE | `{ xp, level, streak, achievement }` |
| `user:{id}:league` | UPDATE | `{ tier, rank, promotion }` |
| `scheduler:{id}:rollover` | EVENT | `{ date, mission_ready }` |

---

## 7. Folder Structure

### 7.1 Repository Root

```
ielts-ai-coach/
├── ARCHITECTURE.md
├── DATABASE.md
├── SCHEDULER.md
├── RESOURCE_ENGINE.md
├── DASHBOARD.md
├── AI_BRAIN.md
├── GAMIFICATION.md
├── API.md
├── USER_JOURNEY.md
├── SOFTWARE_DESIGN_DOCUMENT.md
├── TODO.md
├── .env.example
├── docker-compose.yml
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       ├── auth.py
│   │   │       ├── assessments.py
│   │   │       ├── diagnostic.py
│   │   │       ├── roadmap.py
│   │   │       ├── dashboard.py
│   │   │       ├── analytics.py
│   │   │       ├── resources.py
│   │   │       ├── brain.py
│   │   │       ├── scheduler.py
│   │   │       ├── gamification.py
│   │   │       ├── notifications.py
│   │   │       └── users.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── assessment_service.py
│   │   │   ├── diagnostic_service.py
│   │   │   ├── roadmap_service.py
│   │   │   ├── streak_service.py
│   │   │   ├── prediction_service.py
│   │   │   ├── resource_service.py
│   │   │   ├── notification_service.py
│   │   │   └── user_service.py
│   │   ├── repositories/
│   │   │   ├── assessment_repo.py
│   │   │   ├── roadmap_repo.py
│   │   │   ├── streak_repo.py
│   │   │   ├── resource_repo.py
│   │   │   └── user_repo.py
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── prompts.py
│   │   │   ├── writing_assessor.py
│   │   │   ├── speaking_assessor.py
│   │   │   ├── diagnostic_analyzer.py
│   │   │   ├── roadmap_generator.py
│   │   │   └── resource_recommender.py
│   │   ├── brain/
│   │   │   ├── __init__.py
│   │   │   ├── events/
│   │   │   │   ├── assessment_event.py
│   │   │   │   ├── task_event.py
│   │   │   │   ├── session_event.py
│   │   │   │   └── mock_event.py
│   │   │   ├── features/
│   │   │   │   ├── feature_store.py
│   │   │   │   ├── performance_features.py
│   │   │   │   ├── consistency_features.py
│   │   │   │   ├── effort_features.py
│   │   │   │   └── temporal_features.py
│   │   │   ├── state/
│   │   │   │   ├── live_state.py
│   │   │   │   ├── skill_profile.py
│   │   │   │   └── topic_profile.py
│   │   │   ├── inference/
│   │   │   │   ├── band_predictor.py
│   │   │   │   ├── readiness.py
│   │   │   │   ├── risk.py
│   │   │   │   ├── probability.py
│   │   │   │   ├── hours.py
│   │   │   │   ├── weakest_topics.py
│   │   │   │   └── next_tasks.py
│   │   │   ├── decision/
│   │   │   │   ├── orchestrator.py
│   │   │   │   ├── rules.py
│   │   │   │   └── bundle.py
│   │   │   ├── calibration/
│   │   │   │   ├── outcome_ingest.py
│   │   │   │   ├── probability_calibrator.py
│   │   │   │   └── hours_estimator.py
│   │   │   ├── models/
│   │   │   │   └── schemas.py
│   │   │   └── api/
│   │   │       └── brain_router.py
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   ├── tasks_assessment.py
│   │   │   ├── tasks_speaking.py
│   │   │   ├── tasks_roadmap.py
│   │   │   └── tasks_scheduler.py
│   │   ├── scheduler/
│   │   │   ├── __init__.py
│   │   │   ├── daily_jobs.py
│   │   │   ├── carry_forward.py
│   │   │   ├── phase_transition.py
│   │   │   └── overload_mitigate.py
│   │   ├── gamification/
│   │   │   ├── __init__.py
│   │   │   ├── xp_engine.py
│   │   │   ├── streak_engine.py
│   │   │   ├── achievements.py
│   │   │   ├── challenges.py
│   │   │   ├── leagues.py
│   │   │   └── leaderboard.py
│   │   ├── models/
│   │   │   ├── schemas.py
│   │   │   ├── roadmap.py
│   │   │   ├── analytics.py
│   │   │   └── resources.py
│   │   ├── db/
│   │   │   ├── supabase.py
│   │   │   └── migrations/
│   │   │       ├── 001_users.sql
│   │   │       ├── 002_assessments.sql
│   │   │       ├── 003_roadmap.sql
│   │   │       ├── 004_resources.sql
│   │   │       ├── 005_brain.sql
│   │   │       ├── 006_gamification.sql
│   │   │       └── 007_indexes.sql
│   │   └── utils/
│   │       ├── band_rounding.py
│   │       ├── date_math.py
│   │       └── text_helpers.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── tailwind.config.ts
    ├── tsconfig.json
    ├── next.config.ts
    ├── postcss.config.mjs
    ├── public/
    │   └── robots.txt
    ├── src/
    │   ├── app/
    │   │   ├── globals.css
    │   │   ├── layout.tsx
    │   │   ├── auth-initializer.tsx
    │   │   ├── middleware.ts
    │   │   ├── page.tsx                    # Landing
    │   │   ├── not-found.tsx
    │   │   ├── (marketing)/
    │   │   │   ├── privacy/page.tsx
    │   │   │   ├── terms/page.tsx
    │   │   │   └── cookies/page.tsx
    │   │   ├── (auth)/
    │   │   │   ├── login/page.tsx
    │   │   │   ├── signup/page.tsx
    │   │   │   ├── forgot-password/page.tsx
    │   │   │   └── onboarding/page.tsx
    │   │   └── (app)/
    │   │       ├── dashboard/page.tsx
    │   │       ├── daily-mission/page.tsx
    │   │       ├── writing/page.tsx
    │   │       ├── speaking/page.tsx
    │   │       ├── diagnostic/
    │   │       │   ├── page.tsx
    │   │       │   ├── start/page.tsx
    │   │       │   └── result/page.tsx
    │   │       ├── roadmap/page.tsx
    │   │       ├── analytics/page.tsx
    │   │       ├── resources/page.tsx
    │   │       ├── mock-test/
    │   │       │   ├── page.tsx
    │   │       │   ├── start/page.tsx
    │   │       │   └── result/page.tsx
    │   │       ├── notifications/page.tsx
    │   │       ├── profile/page.tsx
    │   │       ├── settings/page.tsx
    │   │       └── post-exam/page.tsx
    │   ├── components/
    │   │   ├── ui/                    # Atomic design system
    │   │   │   ├── button.tsx
    │   │   │   ├── card.tsx
    │   │   │   ├── input.tsx
    │   │   │   ├── textarea.tsx
    │   │   │   ├── badge.tsx
    │   │   │   ├── progress.tsx
    │   │   │   ├── tabs.tsx
    │   │   │   ├── modal.tsx
    │   │   │   ├── dropdown.tsx
    │   │   │   ├── avatar.tsx
    │   │   │   ├── skeleton.tsx
    │   │   │   └── spinner.tsx
    │   │   ├── shared/               # Layout components
    │   │   │   ├── navbar.tsx
    │   │   │   ├── sidebar.tsx
    │   │   │   └── footer.tsx
    │   │   ├── layouts/
    │   │   │   ├── landing-layout.tsx
    │   │   │   ├── auth-layout.tsx
    │   │   │   └── dashboard-layout.tsx
    │   │   └── features/             # Domain-specific widgets
    │   │       ├── StreakCard.tsx
    │   │       ├── BandTrendChart.tsx
    │   │       ├── TaskItem.tsx
    │   │       ├── RecommendationCard.tsx
    │   │       ├── ReadinessGauge.tsx
    │   │       ├── SkillGapChart.tsx
    │   │       ├── StreakCalendar.tsx
    │   │       ├── MissionList.tsx
    │   │       ├── QuickContinue.tsx
    │   │       └── AchievementsGrid.tsx
    │   ├── hooks/
    │   │   ├── useAssessment.ts
    │   │   ├── useRoadmap.ts
    │   │   ├── useStreak.ts
    │   │   ├── useCountdown.ts
    │   │   ├── useNotifications.ts
    │   │   ├── useBrain.ts
    │   │   ├── useGamification.ts
    │   │   └── useMission.ts
    │   ├── services/
    │   │   ├── api.ts
    │   │   ├── assessment-service.ts
    │   │   ├── roadmap-service.ts
    │   │   ├── dashboard-service.ts
    │   │   ├── brain-service.ts
    │   │   ├── gamification-service.ts
    │   │   └── resource-service.ts
    │   ├── stores/
    │   │   ├── useAuthStore.ts
    │   │   └── useUIStore.ts
    │   ├── types/
    │   │   └── index.ts
    │   └── lib/
    │       ├── supabase.ts
    │       ├── utils.ts
    │       └── constants.ts
    └── tests/
        ├── unit/
        ├── integration/
        └── e2e/
```

---

## 8. Security

### 8.1 Authentication & Authorization

| Layer | Mechanism |
|---|---|
| **User Authentication** | Supabase Auth (email/password, Google OAuth, magic link) |
| **Session Management** | JWT (access + refresh) with automatic rotation via `@supabase/ssr` |
| **API Authorization** | Bearer token in `Authorization` header; verified by `get_current_user` dependency |
| **Database Authorization** | Row-Level Security (RLS) policies on all user-owned tables using `auth.uid()` |
| **Admin Authorization** | Service-role key for trusted server-side operations; `app_metadata.role='admin'` for admin endpoints |
| **Route Protection** | Next.js `middleware.ts` validates session cookie; redirects to `/login` for protected routes |

### 8.2 Data Protection

| Concern | Implementation |
|---|---|
| **In-transit encryption** | TLS 1.3 (HTTPS) enforced at load balancer and CDN level |
| **At-rest encryption** | AES-256 managed by Supabase (Postgres, Storage) |
| **API input validation** | Pydantic models with strict field validation, size caps, and type coercion |
| **SQL injection** | Parameterized queries via Supabase client library; no raw SQL construction |
| **XSS prevention** | React's built-in escaping; Content-Security-Policy headers |
| **CSRF protection** | SameSite cookies; anti-forgery tokens on state-changing requests |
| **Rate limiting** | Per-user and per-IP limits on auth endpoints, assessment submissions, and AI calls |
| **Idempotency** | Idempotency-Key header prevents duplicate AI assessment charges |

### 8.3 AI Safety

| Concern | Mitigation |
|---|---|
| **Prompt injection** | Input sanitization, output validation, structured JSON output via function calling |
| **Hallucination** | Band score validation (0–9, step 0.5), criteria range checks, deterministic fallback |
| **Cost control** | Model tiering (mini vs full), per-user AI quotas on free tier, caching for repeated inputs |
| **Content filtering** | Output moderation for offensive/biased content; automated review flags |

### 8.4 Audit Trail

| Event | Logged Information | Retention |
|---|---|---|
| Auth events (login, signup, logout) | User ID, IP, timestamp, event type | 90 days |
| Admin actions | Admin ID, action, target, timestamp | 1 year |
| AI assessment calls | Assessment ID, model, tokens used, cost | 30 days |
| Data export | User ID, export type, timestamp | 90 days |
| API access (sensitive endpoints) | User ID, endpoint, method, status, timestamp | 30 days |

---

## 9. Performance

### 9.1 Frontend Performance

| Technique | Application |
|---|---|
| **Server Components** | Landing page, legal pages, SEO metadata — rendered on server, zero client JS |
| **Code Splitting** | Dynamic imports for chart libraries (Recharts), audio recording, modal components |
| **Image Optimization** | `next/image` for all images; WebP format; responsive sizes |
| **Font Loading** | `next/font` with `display=swap` and subsetting |
| **Bundle Analysis** | `@next/bundle-analyzer` in CI to track bundle size regressions |
| **Caching** | TanStack Query `staleTime` and `gcTime`; `stale-while-revalidate` for API responses |
| **Skeleton Loading** | Per-widget skeleton components for dashboard zone model |
| **Lazy Loading** | Below-fold widgets (Zone 4) loaded on scroll/intersection observer |

### 9.2 Backend Performance

| Technique | Application |
|---|---|
| **Connection Pooling** | Supabase connection pooler (PgBouncer) for Postgres connections |
| **Caching** | Redis for Live User State, decision bundles, leaderboards, session cache |
| **Async Processing** | Celery workers for all AI assessment, transcription, and roadmap generation |
| **BFF Aggregation** | `/api/v1/dashboard/overview` endpoint aggregates data in one round trip |
| **Database Indexes** | Composite indexes on all hot query paths (see §5.4) |
| **Query Optimization** | Materialized views for analytics aggregation; EXPLAIN analysis in CI |
| **Response Compression** | gzip/brotli compression at CDN and application level |
| **HTTP/2** | Multiplexed requests via Vercel Edge Network |

### 9.3 AI Performance

| Concern | Strategy |
|---|---|
| **Assessment latency** | 30-second target for writing assessment; async polling with progress updates |
| **Speaking transcription** | WebSocket streaming for real-time transcript; final result via Celery |
| **Roadmap generation** | Progress updates during generation ("Phase 2 of 5 complete") |
| **Model tiering** | GPT-4o-mini for assessments; GPT-4o for complex roadmap generation |
| **Caching** | Semantic caching for repeated/similar inputs (embedding hash) |

---

## 10. Scalability

### 10.1 Horizontal Scaling Strategy

| Component | Scaling Strategy | Auto-scaling Trigger |
|---|---|---|
| **Frontend (Next.js)** | Vercel Edge Network — auto-scales globally | Traffic-based |
| **Backend (FastAPI)** | Multiple instances behind load balancer (Railway/Render) | CPU > 70%, latency > 500ms |
| **Celery Workers** | Worker pool per queue (brain-fast, brain-slow, assessment, scheduler) | Queue depth > 100 |
| **Redis** | ElastiCache / Upstash with cluster mode | Memory > 75% |
| **PostgreSQL** | Supabase read replicas + connection pooling | CPU > 70%, connections > 80% |
| **Supabase Realtime** | Managed by Supabase — scales with plan | Connection count |

### 10.2 Database Scaling

| Technique | Implementation |
|---|---|
| **Read replicas** | Dashboard queries (read-heavy) routed to Supabase read replicas |
| **Partitioning** | Monthly range partitioning for `xp_ledger`, `decision_log`, `resource_views`, `study_sessions`, `task_completions` |
| **Connection pooling** | PgBouncer (Supabase pooler) for efficient connection management |
| **Materialized views** | Weekly refresh for analytics aggregations (band trends, study time distribution) |
| **Archival** | Data older than 6 months moved to cold storage (Parquet files in S3) |

### 10.3 Batch Processing Scaling

| Process | Batch Size | Scheduling |
|---|---|---|
| **Daily rollover** | 10,000 users per Celery task | Celery Beat at 00:00 user-local (staggered by timezone) |
| **Leaderboard reset** | All users in league | Monday 00:00 UTC |
| **Recommendation refresh** | 100 users per batch | Hourly, rolling |
| **Calibration jobs** | All users with new outcomes | Weekly (Sunday 02:00 UTC) |
| **Link checker (resources)** | All resources | Daily (03:00 UTC) |

### 10.4 Caching Strategy

| Data | Store | TTL | Invalidation |
|---|---|---|---|
| Live User State | Redis | Event-driven | On any signal event |
| Decision Bundle | Redis | Event-driven | On recompute |
| Dashboard overview | Redis | 5 minutes | On daily rollover |
| Leaderboard scores | Redis | Realtime | On XP event |
| Skill/Topic profiles | Redis | 5 minutes | On assessment |
| Resource catalog | CDN (Vercel Edge) | 1 hour | On content update |
| Static assets | CDN (Vercel Edge) | 1 year | On build |

---

## 11. Accessibility

### 11.1 WCAG Compliance Targets

| Principle | Guideline | Target Level |
|---|---|---|
| **Perceivable** | 1.1 Text Alternatives | AA |
| | 1.2 Time-based Media | AA |
| | 1.3 Adaptable | AA |
| | 1.4 Distinguishable (color contrast 4.5:1) | AA |
| **Operable** | 2.1 Keyboard Accessible | AA |
| | 2.2 Enough Time (timers adjustable) | AA |
| | 2.3 Seizures (no flashing > 3/second) | AAA |
| | 2.4 Navigable (skip links, headings) | AA |
| **Understandable** | 3.1 Readable (language attributes) | AA |
| | 3.2 Predictable (consistent navigation) | AA |
| | 3.3 Input Assistance (error suggestions) | AA |
| **Robust** | 4.1 Compatible (ARIA, semantic HTML) | AA |

### 11.2 Specific Implementations

| Feature | Implementation |
|---|---|
| **Keyboard navigation** | All interactive elements focusable and operable via keyboard; visible focus rings |
| **Screen readers** | ARIA labels on icons, `role` attributes on custom components, `aria-live` regions for dynamic updates |
| **Timer accessibility** | Timer warnings announced via screen reader; adjustable time limits |
| **Color independence** | Information not conveyed by color alone (patterns, icons, text labels supplement) |
| **Motion sensitivity** | `prefers-reduced-motion` respected; animations disabled; no auto-playing content |
| **Form validation** | Clear error messages with suggestions; error summary at top of form |
| **Skip navigation** | "Skip to main content" link at top of every page |
| **Heading hierarchy** | Proper h1-h6 hierarchy; one h1 per page |
| **Focus management** | Focus trapped in modals; focus returned on close; programmatic focus for dynamic content |

---

## 12. Future Features

### 12.1 Phase D — Scale & Differentiate (Post-MVP)

| Feature | Description | Priority |
|---|---|---|
| **Multi-language support** | i18n architecture for Spanish, Chinese, Arabic, Hindi, French | High |
| **General Training module** | Full GT-specific content (letter writing, different reading passages) | High |
| **Speaking TTS feedback** | AI examiner voice for Speaking practice (ElevenLabs / OpenAI TTS) | Medium |
| **PDF report export** | Full diagnostic and progress report as downloadable PDF | Medium |
| **Social features** | Study groups, buddy challenges, shared playlists | Medium |
| **Mobile app** | React Native or Flutter for iOS/Android | Medium |
| **Offline mode** | Service worker caching, local storage queue, sync on reconnect | Medium |
| **Advanced analytics** | Topic heatmaps, error pattern clustering, vocabulary gap analysis | Low |
| **A/B testing framework** | Built-in experiment framework for adaptive algorithm tuning | Low |

### 12.2 Premium Features

| Feature | Monetization | Description |
|---|---|---|
| **XP Boost** | Gem purchase | 2× XP for 24 hours |
| **League Freeze** | Subscription | Skip one week without demotion |
| **Streak Repair** | Gem purchase | Additional repair tokens beyond 1/30d limit |
| **Exclusive Themes** | Subscription | Premium dashboard themes (Aurora, Ocean, Sunset) |
| **Exclusive Badges** | Gem purchase | Seasonal limited-edition badges |
| **Custom Avatar** | Hybrid | Full avatar customization |
| **Study Buddy** | Subscription | Private league with friends |
| **Double Gems** | Subscription | All gem rewards doubled |
| **Premium Challenges** | Subscription | 4th daily challenge slot |
| **Advanced Analytics** | Subscription | Gamification insights dashboard |
| **Seasonal Tournaments** | Free + premium entry | 24-hour global XP competitions |

### 12.3 Long-Term Vision

| Feature | Description | Timeline |
|---|---|---|
| **Real exam result integration** | Official IDP/British Council API integration for direct score import | 12+ months |
| **AI lesson generation** | Dynamic lesson content generated by AI based on weakest topics | 12+ months |
| **Writing plagiarism detection** | Cross-user essay similarity checking | 12+ months |
| **Video-based speaking assessment** | Visual cues (facial expression, eye contact) added to speaking analysis | 18+ months |
| **Multi-exam platform** | Expand to PTE, TOEFL, Duolingo English Test | 18+ months |
| **Tutor marketplace** | Human tutor booking integrated with AI recommendations | 24+ months |

---

## 13. Deployment Strategy

### 13.1 Environment Architecture

| Environment | Purpose | Infrastructure | Data |
|---|---|---|---|
| **Development** | Local development | Docker Compose (FastAPI, Redis, Celery) + Supabase local | Seeded mock data |
| **Staging** | Integration testing, QA | Railway/Render (backend) + Vercel (frontend) + Supabase staging | Anonymized production clone |
| **Production** | Live user traffic | Railway/Render (backend) + Vercel (frontend) + Supabase production | Real user data |

### 13.2 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  lint:
    - frontend: eslint, prettier, tsc
    - backend: ruff, mypy
  test:
    - frontend: vitest, react-testing-library
    - backend: pytest (unit, integration)
  build:
    - frontend: next build
    - backend: docker build
  deploy:
    - staging: auto-deploy on main branch
    - production: manual approval on release tag
```

### 13.3 Infrastructure as Code

| Resource | Provider | Configuration |
|---|---|---|
| **Frontend hosting** | Vercel | `vercel.json` — team, project, environment variables |
| **Backend hosting** | Railway / Render | `railway.json` / `render.yaml` — service definition, health check, scaling |
| **Database** | Supabase | Managed — no IaC; migration files version-controlled |
| **Cache/Queue** | Upstash Redis | `terraform` or manual — endpoint URL in env vars |
| **DNS** | Vercel | Automatic — custom domain with SSL |

### 13.4 Deployment Runbook

| Step | Action | Verification |
|---|---|---|
| 1 | Run migrations (`supabase db push`) | Check migration status |
| 2 | Deploy backend (Railway CLI / GitHub Action) | Health check `/health` returns 200 |
| 3 | Deploy frontend (Vercel CLI / GitHub Action) | E2E smoke test on dashboard |
| 4 | Verify Celery workers | `celery inspect ping` returns pong |
| 5 | Verify Redis connectivity | Brain state endpoint returns data |
| 6 | Send test notification | Realtime channel delivers event |
| 7 | Run smoke tests | Playwright suite passes |
| 8 | Monitor (15 min) | Error rate < 0.1%, latency < p95 threshold |

### 13.5 Rollback Strategy

| Component | Rollback Method | RTO |
|---|---|---|
| Frontend | Vercel instant rollback to previous deployment | < 1 minute |
| Backend | Railway rollback to previous version | < 2 minutes |
| Database | Supabase point-in-time recovery (PITR) | < 15 minutes |
| Migrations | Down-migration script (versioned) | < 5 minutes |

---

## 14. Testing Strategy

### 14.1 Test Pyramid

```
        ╱─────╲
       ╱  E2E  ╲          ← 5% — Critical user journeys (Playwright)
      ╱─────────╲
     ╱ Integration ╲       ← 20% — API contracts, database queries, AI module I/O
    ╱───────────────╲
   ╱   Unit Tests     ╲    ← 75% — Services, utils, helpers, Pydantic models
  ╱─────────────────────╲
```

### 14.2 Unit Testing

| Module | Framework | Coverage Target | Key Tests |
|---|---|---|---|
| **Services** | pytest | 95% | Band rounding, streak calculation, XP computation, carry-forward logic |
| **Utils** | pytest | 95% | Date math, text helpers, validation |
| **Models** | pytest | 100% | Pydantic validation, field constraints, type coercion |
| **Frontend components** | vitest + RTL | 80% | Render, user interaction, state changes, edge cases |
| **Frontend hooks** | vitest + RTL | 80% | Data fetching, optimistic updates, error states |

### 14.3 Integration Testing

| Scope | Framework | Key Tests |
|---|---|---|
| **API endpoints** | pytest + httpx | Request/response contracts, auth, error handling, pagination |
| **Database queries** | pytest + testcontainers | CRUD operations, RLS enforcement, index usage |
| **AI module I/O** | pytest + mocks | Prompt formatting, output parsing, fallback handling |
| **Celery tasks** | pytest + celery_worker | Task enqueue, execution, result persistence |
| **Frontend + API** | vitest + msw | Service calls, response handling, error states |

### 14.4 End-to-End Testing

| Flow | Playwright Test | Critical Path |
|---|---|---|
| **Auth flow** | signup → login → session persistence | Yes |
| **Onboarding** | profile setup → diagnostic → roadmap | Yes |
| **Writing assessment** | submit essay → poll result → view feedback | Yes |
| **Speaking assessment** | record → transcribe → view feedback | Yes |
| **Dashboard** | load → view widgets → complete task | Yes |
| **Daily mission** | view tasks → complete → celebrate | Yes |
| **Analytics** | view charts → filter → export | No |
| **Resources** | browse → filter → bookmark → complete | No |
| **Gamification** | earn XP → level up → view leaderboard | No |

### 14.5 Performance Testing

| Test Type | Tool | Scenarios | Thresholds |
|---|---|---|---|
| **Load testing** | k6 / Locust | 1000 concurrent users, mixed read/write | p95 < 500ms, error rate < 1% |
| **Stress testing** | k6 / Locust | 2× expected peak load, 30 min duration | Graceful degradation, no crash |
| **Endurance testing** | k6 / Locust | 500 concurrent users, 4 hours | No memory leak, stable latency |
| **AI assessment** | Custom script | 100 concurrent essay submissions | All complete within 60 seconds |
| **Frontend Lighthouse** | Lighthouse CI | All pages, mobile + desktop | LCP < 2.5s, TBT < 200ms, CLS < 0.1 |

### 14.6 Testing Data Strategy

| Environment | Data Source | Data Volume | Refresh |
|---|---|---|---|
| **Unit tests** | Factories (factory_boy) | Minimal | Per test run |
| **Integration** | Testcontainers + seed SQL | 1000 users, 10K assessments | Per test suite |
| **E2E** | Supabase branch + seed | 100 users, 500 assessments | Per branch |
| **Performance** | Synthetic data generator | 1M users, 10M assessments | Weekly |

---

## 15. Risk Analysis

### 15.1 Risk Register

| Risk | Probability | Impact | Severity | Mitigation |
|---|---|---|---|---|
| **AI assessment hallucination** | Medium | High | **Critical** | Structured output validation, band rounding checks, deterministic fallback, human review flag |
| **Supabase outage** | Low | Critical | **High** | Backend caching, read-replica fallback, graceful degradation, status page monitoring |
| **Redis data loss** | Low | Medium | **Medium** | Persistent storage (AOF), Redis Cluster, automated rebuild from Postgres |
| **Database performance degradation** | Medium | High | **High** | Index monitoring, query optimization in CI, read replicas, partitioning, connection pooling |
| **Security breach (JWT compromise)** | Low | Critical | **Critical** | Short-lived tokens, refresh rotation, RLS as second layer, rate limiting, audit logging |
| **User data loss** | Low | Critical | **Critical** | Daily automated backups, point-in-time recovery, multi-region replication |
| **AI cost overrun** | Medium | Medium | **Medium** | Model tiering, caching, per-user quotas, cost monitoring dashboard, alerting |
| **Low user engagement** | Medium | High | **High** | Gamification system, streak mechanics, daily notifications, adaptive difficulty |
| **Scaling under peak load** | Medium | Medium | **Medium** | Auto-scaling, load testing, CDN caching, queue-based processing |
| **Third-party API deprecation** | Low | Medium | **Low** | Abstraction layer (OpenAI/Deepgram), swappable providers, versioned prompts |
| **Regulatory compliance (GDPR)** | Medium | Medium | **Medium** | Data anonymization, export/delete APIs, consent management, privacy-by-design |
| **Mobile responsiveness gaps** | Medium | Low | **Low** | Responsive design system, mobile-first development, device lab testing |

### 15.2 Mitigation Priority Matrix

```
                    Impact
                Low     Medium    High    Critical
        ┌───────────────────────────────────────┐
   High  │  Mobile Resp  │  AI Cost   │ Low Eng  │  ─  │
Probab  ├───────────────┼───────────┼──────────┤─────┤
  ility  │               │  DB Perf   │  Scaling  │  ─  │
   Med   │  ─────────── │  ──────── │  ─────── │  AI Halluc  │
        ├───────────────┼───────────┼──────────┤─────┤
   Low   │  3rd Party    │  Redis    │  Security │  Data Loss  │
        │  API Deprec    │  Data Loss│  Breach   │  Supabase   │
        └───────────────┴───────────┴──────────┴─────┘
```

### 15.3 Disaster Recovery

| Scenario | RPO | RTO | Recovery Procedure |
|---|---|---|---|
| **Database failure** | 15 min | 1 hour | Promote read replica → point DNS → verify data integrity |
| **Backend failure** | N/A | 5 min | Auto-scale new instance → health check → resume traffic |
| **Frontend failure** | N/A | 1 min | Vercel instant rollback → verify CDN cache |
| **Redis failure** | 5 min | 15 min | Restore from AOF → rebuild from Postgres → verify |
| **Full region failure** | 15 min | 4 hours | Deploy to secondary region → restore DB → update DNS |

---

## 16. Assumptions

### 16.1 Technical Assumptions

| # | Assumption | Rationale | Impact if False |
|---|---|---|---|
| A1 | Supabase is available and scales with our growth | BaaS reduces operational overhead | Need to migrate to self-hosted Supabase or alternative |
| A2 | OpenAI API remains available with acceptable latency | Core AI assessment depends on it | Need fallback LLM provider (Anthropic, local model) |
| A3 | Users have stable internet connections | Audio recording upload, realtime features | Enhance offline support, add retry logic |
| A4 | Modern browsers support MediaRecorder API | Speaking assessment core feature | Add text-input fallback, feature detection |
| A5 | PostgreSQL with pgvector meets our semantic search needs | Resource recommendation engine | Consider dedicated vector database (Pinecone, Weaviate) |
| A6 | Celery + Redis handles the async processing load | AI assessment, scheduler, notifications | Consider alternatives (BullMQ, AWS SQS) |
| A7 | Vercel Edge Network provides sufficient global CDN coverage | Frontend performance | Configure additional CDN providers |

### 16.2 Business Assumptions

| # | Assumption | Rationale | Impact if False |
|---|---|---|---|
| B1 | Users are motivated to practice regularly (2-5x/week) | Streak engine, mission design | Need stronger engagement mechanics, marketing automation |
| B2 | Free resources from 7 providers remain available | Resource engine catalog | Add automated link checking, content curation pipeline |
| B3 | IELTS band score improvement follows predictable patterns | Prediction model, scheduler | Calibrate models with real user data, add ML retraining |
| B4 | Users have a target band and exam date | Personalization, countdown | Provide defaults, guide users through goal setting |
| B5 | Users are willing to grant microphone permission | Speaking assessment | Provide clear value proposition, permission education |
| B6 | Free tier is sufficient for user acquisition | Conversion funnel | Adjust feature gating, trial period, pricing |
| B7 | Primary market is English-proficient (interface) | UI language | Add i18n support for non-English interfaces |

### 16.3 Regulatory Assumptions

| # | Assumption | Rationale | Impact if False |
|---|---|---|---|
| C1 | GDPR compliance required (EU users) | Data protection | Implement data export, delete, consent mechanisms |
| C2 | COPPA compliance not required (users 16+) | Age restriction | Add age verification, parental consent for minors |
| C3 | IELTS is a registered trademark, fair use applies | Content referencing | Consult legal, avoid trademark infringement |
| C4 | No medical/health data classification | Data sensitivity | Avoid collecting health data, if needed add HIPAA compliance |

---

## 17. Edge Cases

### 17.1 User Journey Edge Cases

| # | Scenario | Handling |
|---|---|---|
| E1 | User signs up but never completes onboarding | Periodic reminder emails (3, 7, 14 days); after 30 days, archive account |
| E2 | User starts diagnostic but exits mid-way | Save progress per section (local storage + server); allow resume within 7 days; after 7 days, expire and force restart |
| E3 | User completes diagnostic but never generates roadmap | Show results page with persistent CTA; after 7 days, auto-generate default roadmap |
| E4 | User has no activity for 14+ days | Enter "dormant" state; send re-engagement email sequence; after 90 days, archive plan |
| E5 | User changes exam date to sooner | Compress plan (revision cut first, then mocks, then advanced; foundation never below 50%); notify user |
| E6 | User changes exam date to later | Extend plan proportionally; add enrichment tasks |
| E7 | User changes target band | If higher: recalculate gap, warn if unachievable in remaining time; if lower: relax schedule |
| E8 | User takes a planned vacation | Freeze streaks (all 3 tiers); no tasks scheduled; no freeze items consumed; max 14 days, 2x/year |
| E9 | User completes all tasks before exam | Enter maintenance mode (1 task/day, focus on skill sharpening); if target reached, show "maintenance" state |
| E10 | Exam date has passed | Enter post-exam mode: prompt to enter results, postpone, or archive plan |

### 17.2 Technical Edge Cases

| # | Scenario | Handling |
|---|---|---|
| E11 | AI assessment fails for one diagnostic section | Use other sections only; mark as "partial diagnostic"; notify user |
| E12 | All 3 diagnostic sections fail | Prompt user to retry; if declined, generate default roadmap from population priors |
| E13 | Microphone permission denied | Show clear instructions for enabling; provide text-input fallback for speaking |
| E14 | User submits empty essay | Reject with "Please write at least 50 words"; save draft locally |
| E15 | Timer expires during assessment | Auto-submit current content; mark as "incomplete" with partial data |
| E16 | Network failure during submission | Save to local storage; retry on reconnect with exponential backoff |
| E17 | Concurrent submissions (same essay, multiple tabs) | Idempotency key prevents duplicate AI charges; return existing result |
| E18 | User pastes suspiciously fast content | Flag as potential cheating; still accept but warn; log for review |
| E19 | Database connection pool exhausted | Queue requests; return 503 with retry-after header; auto-scale connections |
| E20 | Celery worker queue backs up | Prioritize: assessment > task completion > gamification > scheduler > calibration |

### 17.3 Gamification Edge Cases

| # | Scenario | Handling |
|---|---|---|
| E21 | User reaches daily XP cap | Show "cap reached" state; bonus XP from challenges may exceed cap (marked separately) |
| E22 | User breaks a long streak | Empathetic messaging; offer streak repair (1 per 30 days); show "start a new streak" CTA |
| E23 | User uses streak freeze on multiple consecutive days | Freezes consumed FIFO; after 5 freezes exhausted, streak breaks normally |
| E24 | User is on vacation during league week | Auto-demotion prevented; league position frozen |
| E25 | League group has uneven member count | Snake-draft assignment balances groups; minimum 10 members per group |
| E26 | User achieves 0 XP in a league week | Auto-demotion (one tier) regardless of group rank |
| E27 | Achievement predicate evaluates during event storm | Debounced evaluation (1-second window); idempotent unlock |
| E28 | User dismisses a recommendation | Excluded for 30 days; then re-evaluated; log for feedback loop |

### 17.4 Scheduler Edge Cases

| # | Scenario | Handling |
|---|---|---|
| E29 | User has 10+ overdue tasks | Show warning banner; prioritize top 3 most important; merge low-priority tasks |
| E30 | User consistently misses 3+ days | Enter streak-saver mode: single 10-min quick-win task per day; after 5 missed days, generate recovery plan |
| E31 | Carry-forward creates overload (> 1.5x budget) | Spread to next 2 days; if weekly overload > 1.3x, drop bottom 20% non-required tasks |
| E32 | Mock test day conflicts with rest day | Mock takes priority; rest day rescheduled to nearest available day |
| E33 | User has < 30 days to exam | Enter crunch mode: allow up to 2x daily budget; compress non-essential tasks; emphasize mocks |
| E34 | User has > 6 months to exam | Relaxed pacing: spread tasks thinly; add enrichment and exploratory activities |
| E35 | Protected revision days are full | No carry-forward allowed; tasks spill to first non-revision day |
| E36 | User's daily budget is 0 (zero minutes) | Show rest day; if exam is within 30 days, force minimum 10-minute session |

### 17.5 Data Edge Cases

| # | Scenario | Handling |
|---|---|---|
| E37 | User deletes account | Cascade delete all user data; anonymize in analytics (retain aggregate counts) |
| E38 | User changes email | Verify new email; update auth + all related records; invalidate old sessions |
| E39 | User changes timezone | Recompute all scheduled dates; adjust daily rollover time; no streak penalty |
| E40 | Resource link becomes broken | Auto-detect via daily link checker; hide from recommendations; notify admin; set `is_active = FALSE` |
| E41 | Duplicate resource recommendation | `UNIQUE(user_id, resource_id, reason_code)` prevents duplicates; return existing |
| E42 | User completes all available resources | Show "New resources added weekly"; notify when new resources match their profile |

---

## Appendix A: Document References

| Document | Purpose | Location |
|---|---|---|
| ARCHITECTURE.md | Production-ready architecture design | `./ARCHITECTURE.md` |
| DATABASE.md | Complete database schema with validation | `./DATABASE.md` |
| SCHEDULER.md | Adaptive scheduler algorithms | `./SCHEDULER.md` |
| RESOURCE_ENGINE.md | Resource recommendation engine | `./RESOURCE_ENGINE.md` |
| DASHBOARD.md | Dashboard widget architecture | `./DASHBOARD.md` |
| AI_BRAIN.md | AI decision engine (continuous evaluation) | `./AI_BRAIN.md` |
| GAMIFICATION.md | Gamification system design | `./GAMIFICATION.md` |
| API.md | Complete API specification | `./API.md` |
| USER_JOURNEY.md | Complete user journey map | `./USER_JOURNEY.md` |
| TODO.md | Implementation tracking | `./TODO.md` |

---

## Appendix B: Glossary

| Term | Definition |
|---|---|
| **Band Score** | IELTS score from 0 to 9 in 0.5 increments |
| **BFF** | Backend For Frontend — aggregation endpoint |
| **Brain** | AI decision engine (continuous evaluation module) |
| **CEFR** | Common European Framework of Reference for Languages |
| **Daily Mission** | Set of tasks assigned to a user for a specific day |
| **Decision Bundle** | AI Brain's output: predicted band, readiness, risk, probability, hours, weakest topics, next tasks |
| **Diagnostic** | Baseline assessment (Writing + Speaking + Vocabulary) |
| **Gamification** | Game mechanics (XP, levels, streaks, achievements, leagues) |
| **GT** | General Training (IELTS module) |
| **Live User State** | AI Brain's working memory — JSON document of all user signals |
| **LLM** | Large Language Model (e.g., GPT-4o-mini) |
| **Mock Test** | Full-length simulated IELTS exam |
| **pgvector** | PostgreSQL extension for vector similarity search |
| **Readiness Score** | 0–100 composite metric of exam readiness |
| **Realtime** | Supabase WebSocket-based real-time event system |
| **RLS** | Row-Level Security (PostgreSQL) |
| **Roadmap** | Phased, personalized study plan |
| **Scheduler** | Adaptive engine that generates daily missions |
| **SRS** | Spaced Repetition System (for vocabulary) |
| **Streak** | Consecutive days of study activity |
| **TanStack Query** | Frontend data-fetching and caching library |
| **XP** | Experience Points (gamification currency) |
| **Zustand** | Frontend state management library |

---

*This Software Design Document is the master blueprint for the IELTS AI Coach platform. It synthesizes all design decisions from the companion documents listed in Appendix A and serves as the single source of truth for the engineering team. All implementation work should be traceable to requirements and design decisions documented herein.*
