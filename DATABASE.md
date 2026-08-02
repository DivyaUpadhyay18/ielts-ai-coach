# IELTS AI Coach — Complete Database Design

**Author:** Senior Database Architect  
**Target Platform:** Supabase (PostgreSQL 15+)  
**Scope:** All entities, fields, types, relationships, indexes, validation, rationale  
**Status:** Draft for review & approval

---

## 0. Design Principles

1. **One source of truth** — every fact stored once; derived values (streaks, predicted bands, completion rates) are computed or cached, never hand-entered.
2. **RLS-first** — every user-owned table has Row-Level Security enabled; the client anon key can only read/write its own rows (`auth.uid() = user_id`).
3. **Scalable to millions of users** — UUID PKs (distributed-safe, no contention), selective indexes on hot query paths, JSONB for flexible domain payloads, monthly partitioning for high-volume event tables, and read replicas / materialized views for analytics.
4. **Temporal integrity** — all mutable tables carry `created_at`/`updated_at`; scheduled-date logic is timezone-aware (UTC storage + user TZ offset).
5. **Referential integrity** — foreign keys everywhere; `ON DELETE CASCADE` for child aggregates; `SET NULL` where optional.
6. **Consistent enums** — domain values stored as PostgreSQL enums to prevent invalid states at the DB layer.

---

## 1. Entity-Relationship Overview

```
                        ┌───────────────────────────────────────────┐
                        │              users (1:1)                  │
                        │  (extends auth.users via user_id FK)      │
                        └──────┬──────────────┬──────────────┬──────┘
                               │              │              │
                    1:N        │              │              │       1:N
               ┌───────────────▼───┐   ┌──────▼──────┐   ┌───▼────────────┐
               │     study_plans   │   │   mock_tests │   │  achievements  │
               └───────┬───────────┘   └──────────────┘   └────────────────┘
                       │ 1:N
               ┌───────▼───────────┐
               │   daily_plans     │
               └───────┬───────────┘
                       │ 1:N
               ┌───────▼───────────┐       1:N                 ┌─────────────────┐
               │       tasks       │─────────────►             │ task_completions │
               └───────┬───────────┘                           └─────────────────┘
                       │ N:M (via task_resources)
               ┌───────▼───────────┐   N:M ┌──────────────┐
               │     resources     │◄──────┤ task_resources│
               └───────────────────┘       └──────────────┘
                       1:N
               ┌───────▼───────────┐
               │  resource_recommendations │
               └───────────────────┘

users ──1:N──► progress (skill band history)
users ──1:N──► vocabulary (user word list)
users ──1:N──► notifications
users ──1:N──► streak_history
users ──1:N──► study_sessions
users ──1:1──► streak_current (derived, cached)
users ──1:N──► band_predictions
```

---

## 2. Entity Catalog

| # | Entity | Purpose |
|---|--------|---------|
| 1 | `users` | Core profile + plan/goal attributes for every account |
| 2 | `study_plans` | Versioned, personalized roadmap (target band, phases) |
| 3 | `daily_plans` | The day's scheduled task set (the "Today's Tasks" view) |
| 4 | `tasks` | Individual study activities (writing, speaking, vocab, mock, review) |
| 5 | `resources` | Curated content catalog (videos, PDFs, practice tests, guides) |
| 6 | `task_resources` | Link table: which resources are attached to a task |
| 7 | `resource_recommendations` | Per-user AI-suggested resources with reasons & feedback loop |
| 8 | `progress` | Skill-level band history (per IELTS criterion) |
| 9 | `mock_tests` | Full-length timed mock exams and their section results |
| 10 | `vocabulary` | User word list with spaced-repetition metadata |
| 11 | `achievements` | Badges/achievements catalog (game mechanics) |
| 12 | `user_achievements` | Which achievements a user has earned |
| 13 | `notifications` | In-app notification feed (AI-ready, reminders, system) |
| 14 | `streak_history` | Daily activity log used to compute streaks |
| 15 | `study_sessions` | Every focused study session (start/end/duration/task) |
| 16 | `band_predictions` | Model output of expected IELTS band + confidence |

---

## 3. Entity Definitions

### 3.1 `users`

The application profile for an authenticated user. `auth.users` (Supabase) holds credentials; this table holds domain attributes. Created automatically via a `on_auth_user_created` trigger.

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK; references `auth.users(id)` ON DELETE CASCADE |
| `email` | `TEXT` | NO | — | `UNIQUE`; validated format at app layer (`^[^@\s]+@[^@\s]+\.[^@\s]+$`) |
| `full_name` | `TEXT` | YES | NULL | Length 1–120 |
| `avatar_url` | `TEXT` | YES | NULL | Must be HTTPS URL; Supabase Storage path |
| `country` | `TEXT` | YES | NULL | ISO 3166-1 alpha-2 (2 chars) |
| `timezone` | `TEXT` | NO | `'UTC'` | IANA tz name (e.g., `Asia/Kolkata`) — drives scheduling |
| `module` | `TEXT` | NO | `'academic'` | `IN ('academic','general')` enum |
| `plan` | `TEXT` | NO | `'free'` | `IN ('free','pro')` enum |
| `daily_minutes_budget` | `SMALLINT` | NO | `60` | `BETWEEN 15 AND 480` |
| `target_band` | `NUMERIC(2,1)` | YES | NULL | `IN (0,0.5,...,9.0)` — step 0.5 validated |
| `exam_date` | `DATE` | YES | NULL | Must be `> CURRENT_DATE` (countdown source) |
| `onboarded_at` | `TIMESTAMPTZ` | YES | NULL | Set after diagnostic complete |
| `is_onboarding_complete` | `BOOLEAN` | NO | `false` | — |
| `preferences` | `JSONB` | YES | `'{}'` | e.g., `{"notifications": {...}, "theme": "dark"}` |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Auto-updated by trigger |

**Indexes**
- PK: `PRIMARY KEY (id)`
- `UNIQUE INDEX users_email_idx ON users(email)`
- `INDEX users_plan_idx ON users(plan)` — filtering free vs pro
- `INDEX users_exam_date_idx ON users(exam_date)` — countdown/reminder scans (partial `WHERE exam_date IS NOT NULL`)

**Relationships**
- `1:1` with `auth.users` (id = auth.uid())
- `1:N` → `study_plans`, `daily_plans`, `tasks` (indirect), `resources` (creator), `progress`, `mock_tests`, `vocabulary`, `notifications`, `streak_history`, `study_sessions`, `band_predictions`, `user_achievements`

**Why this table exists:** The application needs profile + goal attributes beyond auth credentials. Centralizing `target_band`, `exam_date`, `timezone`, and `daily_minutes_budget` here powers the roadmap generator, scheduler, countdown, and streak engines.

---

### 3.2 `study_plans`

A versioned, personalized roadmap generated from the diagnostic + user goals. Each regeneration creates a new version (auditable).

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `user_id` | `UUID` | NO | — | FK → `users(id)` ON DELETE CASCADE; RLS owner |
| `version` | `INTEGER` | NO | `1` | `>= 1`; `UNIQUE (user_id, version)` |
| `title` | `TEXT` | NO | — | Length 1–200 |
| `source_diagnostic_id` | `UUID` | YES | NULL | FK → `mock_tests(id)` (diagnostic) SET NULL |
| `target_band` | `NUMERIC(2,1)` | NO | — | Step 0.5; `0.0–9.0` |
| `start_band` | `NUMERIC(2,1)` | NO | — | Step 0.5; `<= target_band` |
| `status` | `TEXT` | NO | `'active'` | `IN ('active','archived','completed')` |
| `total_weeks` | `SMALLINT` | NO | — | `BETWEEN 2 AND 52` |
| `meta` | `JSONB` | YES | `'{}'` | generator model version, prompt version, phase count |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Indexes**
- PK: `PRIMARY KEY (id)`
- `UNIQUE INDEX study_plans_user_version_idx ON study_plans(user_id, version)`
- `INDEX study_plans_user_status_idx ON study_plans(user_id, status)` — active plan lookup

**Relationships**
- `1:N` → `daily_plans`
- `1:N` → `tasks` (via daily_plans or direct plan_id)
- `N:1` → `users`

**Why this table exists:** The adaptive roadmap is the product's core artifact. Versioning gives an audit trail of "why did my plan change" and supports A/B testing of the roadmap generator. `start_band` vs `target_band` drives progress reporting.

---

### 3.3 `daily_plans`

One row per (user, plan, date). Represents "Today's Tasks" — the daily aggregate shown on the dashboard. The scheduler creates these daily; missed tasks auto-roll forward (scheduler updates this table).

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `user_id` | `UUID` | NO | — | FK → `users(id)` ON DELETE CASCADE |
| `study_plan_id` | `UUID` | NO | — | FK → `study_plans(id)` ON DELETE CASCADE |
| `plan_date` | `DATE` | NO | — | `UNIQUE (user_id, plan_date)` |
| `total_tasks` | `SMALLINT` | NO | `0` | `>= 0` |
| `completed_tasks` | `SMALLINT` | NO | `0` | `>= 0` and `<= total_tasks` |
| `total_minutes` | `SMALLINT` | NO | `0` | `BETWEEN 0 AND 1440` |
| `completed_minutes` | `SMALLINT` | NO | `0` | `>= 0` and `<= total_minutes` |
| `status` | `TEXT` | NO | `'scheduled'` | `IN ('scheduled','in_progress','completed','missed','rolled_forward')` |
| `is_rest_day` | `BOOLEAN` | NO | `false` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Indexes**
- PK: `PRIMARY KEY (id)`
- `UNIQUE INDEX daily_plans_user_date_idx ON daily_plans(user_id, plan_date)` — primary daily query
- `INDEX daily_plans_status_idx ON daily_plans(status)` — scheduler scans for missed/rolled_forward
- `INDEX daily_plans_plan_date_idx ON daily_plans(plan_date)` — date-range scans

**Relationships**
- `1:N` → `tasks` (via `daily_plan_id` on tasks)
- `N:1` → `study_plans`, `users`

**Why this table exists:** Provides a fixed, queryable snapshot of each day's workload, decoupled from the more complex task graph. Enables fast dashboard rendering (`WHERE user_id=? AND plan_date=CURRENT_DATE`), simple scheduler rollover, and historical "what did I do each day" analytics without scanning individual tasks.

---

### 3.4 `tasks`

The atomic unit of study. A task belongs to a plan and optionally a daily_plan. Can be a writing prompt, speaking drill, vocabulary set, mock section, video/PDF review, or diagnostic item.

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `user_id` | `UUID` | NO | — | FK → `users(id)` ON DELETE CASCADE |
| `study_plan_id` | `UUID` | YES | NULL | FK → `study_plans(id)` ON DELETE CASCADE |
| `daily_plan_id` | `UUID` | YES | NULL | FK → `daily_plans(id)` ON DELETE SET NULL |
| `phase_index` | `SMALLINT` | YES | NULL | 0-based phase ordering; `>= 0` |
| `title` | `TEXT` | NO | — | Length 1–300 |
| `skill` | `TEXT` | NO | — | `IN ('writing','speaking','reading','listening','vocabulary','grammar','mock','general')` |
| `task_type` | `TEXT` | NO | — | `IN ('writing_task1','writing_task2','speaking_part1','speaking_part2','speaking_part3','vocab_set','grammar_lesson','mock_section','full_mock','video','article','practice_test','review')` |
| `content_payload` | `JSONB` | YES | NULL | Prompt/question data; `{"prompt": "...", "word_limit": 250}` |
| `resource_id` | `UUID` | YES | NULL | FK → `resources(id)` SET NULL (primary linked resource) |
| `duration_minutes` | `SMALLINT` | NO | — | `BETWEEN 1 AND 240` |
| `scheduled_date` | `DATE` | YES | NULL | Set by scheduler; NULL = unscheduled backlog |
| `priority` | `SMALLINT` | NO | `1` | `1 (low) – 5 (critical)` |
| `status` | `TEXT` | NO | `'pending'` | `IN ('pending','in_progress','completed','missed','rescheduled','skipped')` |
| `is_mandatory` | `BOOLEAN` | NO | `false` | Core tasks vs optional enrichment |
| `due_at` | `TIMESTAMPTZ` | YES | NULL | Optional hard deadline |
| `completed_at` | `TIMESTAMPTZ` | YES | NULL | Set on completion |
| `order_index` | `SMALLINT` | YES | NULL | Sort order within daily_plan |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Indexes**
- PK: `PRIMARY KEY (id)`
- `INDEX tasks_user_date_idx ON tasks(user_id, scheduled_date)` — daily planner query (high traffic)
- `INDEX tasks_daily_plan_idx ON tasks(daily_plan_id)` — load day's task list
- `INDEX tasks_status_idx ON tasks(status)` — scheduler scans missed/pending
- `INDEX tasks_plan_phase_idx ON tasks(study_plan_id, phase_index)` — roadmap rendering
- Partial: `INDEX tasks_user_pending_idx ON tasks(user_id) WHERE status IN ('pending','rescheduled')` — overdue computation

**Relationships**
- `N:1` → `users`, `study_plans`, `daily_plans`, `resources`
- `1:N` → `task_completions` (optional), `study_sessions`
- `N:M` → `resources` via `task_resources`

**Validation rules**
- If `status = 'completed'`, then `completed_at` is NOT NULL.
- `scheduled_date` may be NULL only if `status = 'pending'` (unscheduled backlog).
- `completed_tasks` on parent `daily_plans` must equal count of completed tasks — enforced by service layer/trigger.

**Why this table exists:** Tasks are the core unit the scheduler manipulates (auto-shift), the streak engine counts, and the roadmap renders. JSONB `content_payload` allows heterogeneous task types without schema sprawl.

---

### 3.5 `resources`

The curated content catalog — videos, articles, PDFs, practice tests, guides. Shared across all users (public library), so **no RLS** (readable by anon).

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `title` | `TEXT` | NO | — | Length 1–300 |
| `description` | `TEXT` | YES | NULL | — |
| `type` | `TEXT` | NO | — | `IN ('video','article','pdf','practice_test','guide','flashcard_set')` |
| `skill` | `TEXT` | NO | — | `IN ('writing','speaking','reading','listening','vocabulary','grammar','general')` |
| `module` | `TEXT` | NO | `'academic'` | `IN ('academic','general','both')` |
| `difficulty` | `TEXT` | NO | `'intermediate'` | `IN ('beginner','intermediate','advanced','all_levels')` |
| `provider` | `TEXT` | YES | NULL | e.g., British Council, IDP, AI Coach Team |
| `url` | `TEXT` | NO | — | HTTPS URL |
| `duration_minutes` | `SMALLINT` | YES | NULL | `BETWEEN 1 AND 600` |
| `tags` | `TEXT[]` | NO | `'{}'` | Lowercased, deduped tags |
| `embedding` | `VECTOR(1536)` | YES | NULL | OpenAI text-embedding-3-large; for pgvector search |
| `is_published` | `BOOLEAN` | NO | `true` | Admin publish flag |
| `view_count` | `BIGINT` | NO | `0` | Popularity signal |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Indexes**
- PK: `PRIMARY KEY (id)`
- `GIN INDEX resources_tags_idx ON resources USING gin(tags)`
- `INDEX resources_type_skill_idx ON resources(type, skill)` — filter queries
- `INDEX resources_published_idx ON resources(is_published)` — partial `WHERE is_published = true`
- `HNSW INDEX resources_embedding_idx ON resources USING hnsw (embedding vector_cosine_ops)` — vector search (requires pgvector 0.5+)
- `INDEX resources_provider_idx ON resources(provider)`

**Relationships**
- `1:N` → `resource_recommendations`
- `N:M` → `tasks` via `task_resources`
- `1:N` → `vocabulary` (if resource is a flashcard set, optional)

**Validation rules**
- `url` must be HTTPS (check constraint with regex).
- If `type = 'practice_test'`, `duration_minutes` is required.
- Embedding vector dimension must match the embedding model (1536 for OpenAI text-embedding-3-large).

**Why this table exists:** The Resource Engine needs a structured catalog to support filtering, search, and pgvector semantic recommendations. Shared/public nature means no per-user RLS.

---

### 3.6 `task_resources`

Join table (N:M) between `tasks` and `resources`. A task can reference multiple resources (e.g., a writing task with 1 model-answer PDF + 1 video).

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `task_id` | `UUID` | NO | — | FK → `tasks(id)` ON DELETE CASCADE |
| `resource_id` | `UUID` | NO | — | FK → `resources(id)` ON DELETE CASCADE |
| `relation` | `TEXT` | NO | `'supplementary'` | `IN ('primary','required','supplementary')` |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Constraints**
- Composite PK: `PRIMARY KEY (task_id, resource_id)`

**Indexes**
- `INDEX task_resources_resource_idx ON task_resources(resource_id)` — reverse lookup (which tasks use this resource)

**Why this table exists:** Avoids embedding arrays of resource IDs into tasks (violates normalization), and allows a many-to-many relationship that scales.

---

### 3.7 `resource_recommendations`

Per-user AI recommendation log with a feedback loop (suggested → viewed/saved/dismissed). Feeds the recommender's learning.

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `user_id` | `UUID` | NO | — | FK → `users(id)` ON DELETE CASCADE |
| `resource_id` | `UUID` | NO | — | FK → `resources(id)` ON DELETE CASCADE |
| `reason` | `TEXT` | NO | — | AI-generated explanation (e.g., "targets your Lexical Resource gap") |
| `score` | `NUMERIC(5,2)` | NO | — | `BETWEEN 0.00 AND 1.00` — recommender score |
| `status` | `TEXT` | NO | `'suggested'` | `IN ('suggested','viewed','saved','dismissed','completed')` |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Indexes**
- PK: `PRIMARY KEY (id)`
- `UNIQUE INDEX recs_user_resource_idx ON resource_recommendations(user_id, resource_id)` — prevent duplicate suggestions
- `INDEX recs_user_status_idx ON resource_recommendations(user_id, status)` — user feed queries

**Relationships**
- `N:1` → `users`, `resources`

**Why this table exists:** Recommendation quality improves when we track impressions and outcomes. This table provides the signal store for the recommender and the data source for the "Recommended for you" widget.

---

### 3.8 `progress`

Historical record of skill-level bands per IELTS criterion. Inserted on every assessment/diagnostic/mock completion. Drives analytics trends and the band predictor.

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `user_id` | `UUID` | NO | — | FK → `users(id)` ON DELETE CASCADE |
| `source_type` | `TEXT` | NO | — | `IN ('diagnostic','assessment','mock_test')` |
| `source_id` | `UUID` | YES | NULL | Polymorphic ref to assessment/mock/diagnostic row |
| `criterion` | `TEXT` | NO | — | `IN ('task_response','coherence_cohesion','lexical_resource','grammar','fluency_coherence','pronunciation','listening','reading','overall')` |
| `band_score` | `NUMERIC(2,1)` | NO | — | Step 0.5; `0.0–9.0` |
| `recorded_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Indexes**
- PK: `PRIMARY KEY (id)`
- `INDEX progress_user_criterion_date_idx ON progress(user_id, criterion, recorded_at DESC)` — trend queries (critical hot path)
- `INDEX progress_source_idx ON progress(source_id)` — reverse lookup
- Consider **monthly range partitioning** on `recorded_at` at scale (millions of rows)

**Relationships**
- `N:1` → `users`

**Validation rules**
- `band_score` step-0.5 enforced via check constraint (`(band_score * 2)::int = (band_score * 2)`).
- A single assessment may insert up to 9 rows (one per criterion + overall).

**Why this table exists:** Analytics trends, skill-gap analysis, and band prediction all require a normalized, queryable history of criterion-level scores over time. This is the analytics backbone.

---

### 3.9 `mock_tests`

Full-length timed mock exams (or the diagnostic baseline). Contains an overall band + per-section results.

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `user_id` | `UUID` | NO | — | FK → `users(id)` ON DELETE CASCADE |
| `test_type` | `TEXT` | NO | — | `IN ('diagnostic','full_mock','section_mock')` |
| `module` | `TEXT` | NO | `'academic'` | `IN ('academic','general')` |
| `overall_band` | `NUMERIC(2,1)` | NO | — | Step 0.5; `0.0–9.0` |
| `section_scores` | `JSONB` | NO | — | `{"writing": 6.5, "speaking": 7.0, "reading": 6.0, "listening": 7.5}` |
| `criteria_scores` | `JSONB` | YES | NULL | Detailed per-criterion bands |
| `started_at` | `TIMESTAMPTZ` | NO | — | — |
| `submitted_at` | `TIMESTAMPTZ` | NO | — | `>= started_at` |
| `duration_seconds` | `INTEGER` | YES | NULL | `BETWEEN 1 AND 21600` (6h) |
| `status` | `TEXT` | NO | `'submitted'` | `IN ('in_progress','submitted','expired')` |
| `answers` | `JSONB` | YES | NULL | Section answers (writing essays, reading/listening answers) |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Indexes**
- PK: `PRIMARY KEY (id)`
- `INDEX mock_tests_user_date_idx ON mock_tests(user_id, submitted_at DESC)` — history
- `INDEX mock_tests_type_idx ON mock_tests(test_type)` — filter diagnostics vs mocks

**Relationships**
- `N:1` → `users`
- `1:N` → `progress` (source rows)
- `N:1` ← `study_plans.source_diagnostic_id`

**Validation rules**
- `overall_band` must equal the average of `section_scores` rounded to nearest 0.5 — enforced by service layer.
- If `test_type = 'diagnostic'`, only one active per user allowed at a time (app-level).

**Why this table exists:** Mocks and the diagnostic baseline produce composite, multi-skill results that need to be stored as a cohesive unit for the roadmap generator, band predictor, and history views. Storing section scores in JSONB while keeping `overall_band` and `submitted_at` as queryable columns balances flexibility with query performance.

---

### 3.10 `vocabulary`

The user's personal word bank with spaced-repetition metadata for daily review drills.

| Field | Type | Nullable | Default | Constraints / Validation |
|---|---|---|---|---|
| `id` | `UUID` | NO | `gen_random_uuid()` | PK |
| `user_id` | `UUID` | NO | — | FK → `users(id)` ON DELETE CASCADE |
| `word` | `TEXT` | NO | — | Length 1–100; lowercase |
| `definition` | `TEXT` | NO | — | — |
| `example_sentence` | `TEXT` | YES | NULL | — |
| `synonyms` | `TEXT[]` | YES | NULL | — |
| `part_of_speech` | `TEXT` | YES | NULL | `IN ('noun','verb','adjective','adverb','phrase')` |
| `topic` | `TEXT` | YES | NULL | e.g., education, environment, technology |
| `proficiency` | `TEXT` | NO | `'new'` | `IN ('new','learning','familiar','mastered')` |
| `review_count` | `SMALLINT` | NO | `0` | `>= 0` |
| `last_reviewed_at` | `TIMESTAMPTZ` | YES | NULL | — |
| `next_review_at` | `TIMESTAMPTZ` | YES | NULL | Spaced-repetition due date (SM-2/FSRS) |
| `streak_in_word` | `SMALLINT` | NO | `0` | consecutive correct reviews |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | — |

**Indexes**
- PK: `PRIMARY KEY (id)`
- `UNIQUE INDEX vocab_user_word_idx ON vocabulary(user_id, word)` — prevent duplicates
- `INDEX vocab_user_due_idx ON vocabulary(user_id, next_review_at)` — daily review query (hot path)
- `INDEX vocab_user_proficiency_idx ON vocabulary(user_id, proficiency)` — stats

**Relationships**
- `N:1` → `users`

**Validation rules**
- `word` unique per user (case-insensitive: store lowercase).
- `next_review_at` recomputed after each review by the SRS algorithm in the service layer.

**Why this table exists:** Vocabulary is a first-class IELTS skill. Storing per-user words with SRS metadata powers the daily vocab drill tasks and directly addresses the "free study resources / vocabulary" product requirement.

---

### 3.11 `achievements`

Catalog of all possible achievements/badges (e.g., "7-Day Stre
