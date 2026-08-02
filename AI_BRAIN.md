# IELTS AI Coach — The AI Brain (Decision Engine)

**Role:** Chief AI Architect
**Document:** Continuous Evaluation & Adaptive Decision Engine
**Status:** Draft for review & approval

---

## 0. Executive Summary

The **AI Brain** is the centralized, continuously-running decision engine that unifies every signal in the platform into a single **Live User State** and produces the decisions that drive the scheduler, the roadmap, the dashboard, and the resource engine.

Today the platform has *isolated* AI modules (writing assessor, band predictor, resource recommender) that never share state. The AI Brain replaces this with a **closed adaptive loop**:

```
      ┌────────────────────────────────────────────────────────────┐
      │                    EVENTS (signal sources)                  │
      │  study_consistency │ task_completion │ diagnostic │ mocks  │
      │  reading │ writing │ listening │ speaking │ vocab │ grammar│
      └──────────────────────────────┬─────────────────────────────┘
                                     ▼
      ┌────────────────────────────────────────────────────────────┐
      │                 FEATURE ENGINEERING PIPELINE                │
      │      raw events → normalized, windowed, per-skill features │
      └──────────────────────────────┬─────────────────────────────┘
                                     ▼
      ┌────────────────────────────────────────────────────────────┐
      │                     LIVE USER STATE (brain)                │
      │   per-skill band │ per-topic score │ consistency │ effort  │
      └──────────────────────────────┬─────────────────────────────┘
                                     ▼
      ┌────────────────────────────────────────────────────────────┐
      │                        INFERENCE MODULES                    │
      │  predicted_band │ readiness │ risk │ probability │ hours    │
      │  weakest_topics │ next_best_tasks                           │
      └───────┬──────────────────────┬─────────────────────┬────────┘
              ▼                      ▼                     ▼
      ┌───────────────┐   ┌────────────────────┐  ┌──────────────────┐
      │   Scheduler   │   │   Roadmap / Plan   │  │ Resource Engine  │
      │  (next tasks) │   │  (phase, targets)  │  │ (recommendations)│
      └───────────────┘   └────────────────────┘  └──────────────────┘
              │                                                       │
              └─────────────── OUTCOMES feed back to EVENTS ─────────┘
```

**Core principles:**

1. **Every action is a signal.** No user activity is too small to feed the Brain.
2. **One live state, many consumers.** Prediction, risk, readiness, and recommendations all read from the same state model.
3. **Explainable by design.** Every output ships with contributing factors, confidence, and `model_version`.
4. **Self-calibrating.** Decisions are logged; real outcomes (mock scores, exam results) recalibrate the models.
5. **Server is the source of truth.** All inference runs server-side; the client only renders.

---

## 1. System Overview

### 1.1 The Continuous Evaluation Loop

The Brain operates on an **event-driven, incrementally-computed** loop rather than a nightly batch:

| Phase | Responsibility | Cadence |
|---|---|---|
| **Ingest** | Consume domain events (assessment done, task completed, session ended, mock submitted, diagnostic finished) | Event (realtime) |
| **Feature** | Recompute the feature groups that changed | Incremental (per event) |
| **State** | Update the Live User State (per-skill/per-topic) | Incremental |
| **Infer** | Re-run affected inference modules | Per event + nightly rollover |
| **Decide** | Produce a **Decision Bundle** (predicted band, readiness, risk, probability, hours, weakest topics, next tasks) | Per event + nightly |
| **Act** | Push decisions to Scheduler / Roadmap / Resources / Dashboard; emit notifications | After inference |
| **Learn** | Record decision→outcome pairs; recalibrate models | Daily + on mock/exam |

### 1.2 Why "Continuous" Matters

| Concern | Batch-only | Continuous (Brain) |
|---|---|---|
| Streak at risk | Discovered next morning | Detected at session end, immediate nudge |
| Band gap widening | Recalibrated weekly | Recalibrated per assessment |
| Wrong task mix | Fixed weekly plan | Re-selected per day from next-best-task rank |
| User burn-out | Not detected | Overload risk flagged before it happens |

---

## 2. Input Signal Layer

All ten evaluated dimensions are normalized into a single **Signal Catalog**. Each signal maps to a source table, trigger event, and freshness.

### 2.1 Signal Catalog

| # | Signal | Source Table(s) | Trigger Event | Freshness |
|---|---|---|---|---|
| S1 | Study Consistency | `daily_activity`, `study_sessions`, `streaks` | Session end, rollover | Realtime |
| S2 | Task Completion | `tasks`, `task_completions`, `daily_plans` | Task complete, rollover | Realtime |
| S3 | Diagnostic Performance | `mock_tests` (test_type=diagnostic), `progress` | Diagnostic submitted | On-event |
| S4 | Mock Tests | `mock_tests`, `progress` | Mock submitted | On-event |
| S5 | Reading | `assessments` (reading), `progress` (criterion=reading) | Reading task assessed | On-event |
| S6 | Writing | `assessments` (writing), `progress` (TR/CC/LR/GR) | Essay assessed | On-event |
| S7 | Listening | `assessments` (listening), `progress` (criterion=listening) | Listening task assessed | On-event |
| S8 | Speaking | `assessments` (speaking), `progress` (fluency/pronunciation) | Speaking assessed | On-event |
| S9 | Vocabulary | `vocabulary` (proficiency, reviews), `assessments` (LR) | Vocab review, quiz | Realtime |
| S10 | Grammar | `assessments` (GR), grammar task results, `progress` | Grammar exercise graded | On-event |

### 2.2 Event Bus

```
Domain events published to Redis Stream / Supabase Realtime channel:
  assessment.completed        {user_id, task_type, band_score, criteria_scores, topic}
  diagnostic.completed        {user_id, overall_band, skill_scores, strengths, weaknesses}
  mock.completed              {user_id, mock_id, overall_band, section_scores}
  task.completed              {user_id, task_id, skill, duration_minutes, topic}
  session.ended               {user_id, duration_minutes, skill, task_id?}
  vocab.reviewed              {user_id, word_id, correct, proficiency_delta}
  grammar.graded              {user_id, exercise_id, score, skill}
  resource.completed          {user_id, resource_id, skill, duration}
  daily.rollover              {user_id, date}   ← triggers full recompute
```

The event bus is the **single ingestion point**; the Brain subscribes to all of them. New signal types are added by publishing a new event, not by changing inference code.

---

## 3. Feature Engineering Pipeline

### 3.1 Feature Groups

| Group | Features | Window(s) |
|---|---|---|
| **Performance** | avg/max/min/latest band per skill & criterion; volatility (std); trend slope | 7d / 30d / 90d / all |
| **Consistency** | active days / total days; streak; gaps between sessions; rest-day compliance | 7d / 30d |
| **Effort** | minutes studied; tasks completed; resources consumed; XP earned | 1d / 7d / 30d |
| **Temporal** | days to exam; phase elapsed ratio; crunch mode flag; hours remaining vs available | — |
| **Context** | module (academic/general); target band; daily budget; plan version; timezone | — |

### 3.2 Per-Skill Schema

Each of the 6 skills (Reading, Writing, Listening, Speaking, Vocabulary, Grammar) is represented identically so the Brain can treat them uniformly:

```
SkillProfile = {
  skill:            "writing",
  current_band:     6.5,            // best-estimate band for this skill
  trend_30d:        +0.5,           // band movement over 30 days
  confidence:       0.7,            // 0..1 — how much evidence exists
  sample_count:     12,             // number of contributing assessments
  latest_score:     7.0,
  volatility:       0.4,            // std of recent scores
  weakest_criterion: "grammar_range",
  criterion_scores: { task_response: 7.0, coherence_cohesion: 6.5,
                      lexical_resource: 6.5, grammar_range: 6.0 },
  topics:           { opinion_essay: { band: 6.0, n: 4 },
                      bar_chart:      { band: 7.0, n: 2 } },   // topic-level profile
  last_updated:     "2025-04-29T22:10:00Z"
}
```

### 3.3 Topic-Level Profiling (for Weakest Topics)

Assessments carry a `topic` tag (e.g., `opinion_essay`, `discussion_essay`, `bar_chart`, `process`, `speaking_part3_abstract`). The Brain aggregates a mini-profile **per topic**:

```
TopicProfile = { topic, skill, avg_band, n, recency_weight, trend }
```

Topics with `n >= MIN_SAMPLES (2)` are eligible for "weakest topic" ranking; topics with `n < 2` are flagged `insufficient_data`.

---

## 4. Live User State (The Brain's Working Memory)

The Live User State is a JSON document persisted per user (table `live_user_state`) and cached in Redis. It is the **single source of truth** for all inference modules.

```json
{
  "user_id": "…",
  "profile": {
    "target_band": 7.5,
    "start_band": 6.0,
    "module": "academic",
    "daily_minutes_budget": 60,
    "exam_date": "2025-06-15",
    "days_to_exam": 47,
    "phase": "skill_building",
    "phase_elapsed_ratio": 0.4
  },
  "skills": {
    "writing":  { …SkillProfile… },
    "speaking": { …SkillProfile… },
    "reading":  { …SkillProfile… },
    "listening": { …SkillProfile… },
    "vocabulary": { …SkillProfile… },
    "grammar":  { …SkillProfile… }
  },
  "consistency": {
    "current_streak": 6,
    "longest_streak": 14,
    "active_days_30d": 24,
    "avg_sessions_per_week": 5.2,
    "avg_session_minutes": 28,
    "rest_day_compliance": 0.8
  },
  "effort": {
    "minutes_30d": 1800,
    "tasks_completed_30d": 42,
    "resources_completed_30d": 8,
    "xp_30d": 620
  },
  "mocks": {
    "count": 2,
    "avg_band": 6.5,
    "latest_band": 6.5,
    "first_mock_band": 6.0
  },
  "computed": {
    "predicted_band": 6.8,
    "readiness": 62,
    "risk_score": 41,
    "probability_target": 0.43,
    "recommended_hours": { "total_per_week": 9, "writing": 2.5, "speaking": 2, "…": "…" },
    "weakest_topics": ["opinion_essay", "speaking_part3_abstract"],
    "next_best_tasks": [ {task_id, reason, score} ]
  },
  "model_meta": {
    "prediction_version": "brain-v3",
    "last_full_recompute": "2025-04-29T23:00:00Z",
    "calibration_date": "2025-04-25"
  }
}
```

---

## 5. Inference Modules

Each module specifies: **Purpose · Inputs · Algorithm · Outputs · Edge Cases**.

### M1. Predicted IELTS Band

| Aspect | Specification |
|---|---|
| **Purpose** | The best-estimate current band, per skill and overall. The backbone for readiness, risk, probability, and hours. |
| **Inputs** | `SkillProfile` per skill, `mocks`, `diagnostic`, `consistency`, `effort`, `temporal`. |
| **Algorithm** | **Hybrid weighted ensemble.** For each skill: |
| | `skill_band = 0.45 × weighted_avg_recent_skill_band + 0.25 × weighted_avg_mock_section_band + 0.20 × trend_adjusted_skill_band + 0.10 × diagnostic_skill_band` |
| | where `weighted_avg_recent` uses exponential decay (`w = 0.6^(days_ago/7)`); `trend_adjusted` adds `min(trend_30d, 0.5)` to the baseline. |
| | Overall: `overall = round_to_0.5( mean(reading, writing, listening, speaking) )` per IELTS official rounding rule (DATABASE.md validation). Vocabulary & grammar are **enablers** — they influence skill bands (e.g., `lexical_resource` feeds writing; `grammar_range` feeds writing & speaking) rather than being averaged in directly. |
| **Outputs** | `{ overall_band, per_skill: {skill: {band, confidence}} , trend_30d, model_version }`. |
| **Edge Cases** | No mocks → mock weight redistributed to recent assessments. Only diagnostic → return diagnostic with `confidence=0.3`, label "provisional". Zero data → null + onboarding CTA. Skill with < 2 samples → lower weight, `insufficient_data` flag. |

---

### M2. Readiness Score

| Aspect | Specification |
|---|---|
| **Purpose** | 0–100 composite of "how ready am I **today**?" — the dashboard north-star (refines DASHBOARD.md W7, now fed by the unified Brain state). |
| **Inputs** | `computed.predicted_band`, `mocks`, `schedule_adherence`, `effort`, `streak`. |
| **Algorithm** | |
| | `Readiness = clamp(0,100): 0.40×BandProximity + 0.20×MockConsistency + 0.15×ScheduleAdherence + 0.15×StudyVolume + 0.10×StreakHealth` |
| | `BandProximity = clamp((predicted − start)/(target − start), 0, 1) × 100` |
| | `MockConsistency = avg(mock_band)/target × 100` (0 if no mocks) |
| | `ScheduleAdherence = completed_tasks_30d / scheduled_tasks_30d × 100` |
| | `StudyVolume = clamp(minutes_30d / (30×budget) × 100, 0, 100)` |
| | `StreakHealth = clamp(current_streak/30, 0, 1) × 100` |
| | Labels: 0–39 Building Foundation · 40–69 On Track · 70–84 Nearly Ready · 85–100 Exam Ready. |
| **Outputs** | `{ score, label, components {…}, explanation }`. |
| **Edge Cases** | No mocks → renormalize weights (0.50/0.20/0.20/0.10). No predicted band → use diagnostic for BandProximity, "provisional". Score drop > 15/wk → alert notification. |

---

### M3. Risk Score

| Aspect | Specification |
|---|---|
| **Purpose** | 0–100 measure of **the likelihood that the user's preparation will fail to reach target on time**. Complements Readiness (which measures current state) by weighting **time pressure** and **schedule risk**. *(New — defined here.)* |
| **Inputs** | `days_to_exam`, `band_gap`, `predicted_band confidence`, `schedule_adherence`, `overdue_tasks`, `overload_factor`, `mock_trend`, `consistency`. |
| **Algorithm** | Composite of five risk factors, each 0–100: |
| | `Risk = clamp(0,100): 0.25×GapRisk + 0.25×TimeRisk + 0.20×ScheduleRisk + 0.15×ConsistencyRisk + 0.15×PredictionRisk` |
| | |
| | **GapRisk** = `min(band_gap / 2.0, 1) × 100` — bigger gap → more risk |
| | **TimeRisk** = `clamp((30 − days_to_exam)/30, 0, 1) × 100` if gap > 0.5; else `0` — little time + big gap = high risk |
| | **ScheduleRisk** = `(1 − schedule_adherence) × 50 + min(overdue_tasks / 10, 1) × 50` |
| | **ConsistencyRisk** = `(1 − active_days_30d/30) × 100` + `(1 − rest_day_compliance) × 20`, clamped |
| | **PredictionRisk** = `(1 − prediction_confidence) × 100` — uncertainty itself is risk |
| | Labels: 0–24 Low · 25–49 Moderate · 50–74 High · 75–100 Critical. |
| **Outputs** | `{ score, label, factors {…}, top_risk_reason, mitigations }`. |
| **Edge Cases** | Exam very close (<14d) + large gap → Critical risk, "consider postponing" recommendation. Postponed exam → TimeRisk auto-drops, GapRisk stays. No diagnostic → PredictionRisk maxed, "unknown baseline" flag. |

---

### M4. Probability of Achieving Target Band

| Aspect | Specification |
|---|---|
| **Purpose** | The single most motivating (and honest) number: "what are my odds?" Calibrated from observed outcomes, not arbitrary. |
| **Inputs** | `predicted_band`, `prediction_confidence`, `days_to_exam`, `band_gap`, `mock_trend`, `readiness`, `historical_user_outcomes` (aggregate calibration set). |
| **Algorithm** | **Calibrated logistic model.** |
| | `logit = β0 + β1×(predicted_band − target_band) + β2×(readiness/100) + β3×(mock_trend_slope) + β4×(days_to_exam/90) + β5×prediction_confidence` |
| | `p = sigmoid(logit)` — coefficients fitted on the platform-wide outcome dataset (users who took the real exam: predicted features at T-30 vs. actual result). |
| | **Calibration:** probability is binned (0–10%, 10–20%, …) and adjusted by the ratio of observed successes per bin (Platt-style recalibration), so "60%" genuinely means ~6 of 10 similar users hit target. |
| | Early (few samples): fall back to heuristic `p = clamp(0.5 + 0.4×(predicted − target), 0.05, 0.95)`. |
| **Outputs** | `{ probability, confidence_band: "60–70%", calibrated: true/false, contributing_factors }`. |
| **Edge Cases** | No prediction yet → hide, show "take the diagnostic to estimate your odds". User already above target → p → 0.95 cap + "maintenance mode". Probability < 0.2 → supportive framing + risk mitigations, never discouraging. |

---

### M5. Recommended Study Hours

| Aspect | Specification |
|---|---|
| **Purpose** | Converts the gap into **actionable time**. Answers "how much do I actually need to study per week, and where?" — then feeds the scheduler's daily budget. |
| **Inputs** | `band_gap`, `days_to_exam`, `skill_profiles`, `per-skill gaps`, `available hours (budget)`. |
| **Algorithm** | Two-layer computation: |
| | **Layer 1 — Total required hours:** `required_hours = band_gap × HOURS_PER_0_5_BAND` where `HOURS_PER_0_5_BAND` is an empirically-calibrated constant (initial estimate ~40–60h per 0.5 band, refined from outcome data). |
| | **Layer 2 — Feasible weekly hours:** `weekly_required = required_hours / (weeks_to_exam)`; capped at `budget × 1.5` (crunch ceiling, SCHEDULER.md §8), floored at `budget × 0.5`. |
| | **Per-skill allocation:** `hours_skill = weekly_required × skill_gap_weight(skill)` where `skill_gap_weight = gap(skill)/Σgaps`, biased by the skill's trainability and exam weighting (e.g., speaking & writing often need more deliberate practice). |
| **Outputs** | `{ total_required_hours, weekly_recommended, weekly_feasible, per_skill: {skill: hours}, pacing: "relaxed|steady|intensive|crunch" }`. |
| **Edge Cases** | Required > feasible → pacing = "crunch", notify "consider postponing or raising daily budget". Huge time (>6mo) → pacing "relaxed", spread thinly, add enrichment. Gap = 0 (target reached) → maintenance hours (e.g., 3h/wk). |

---

### M6. Weakest Topics

| Aspect | Specification |
|---|---|
| **Purpose** | Granular gap detection **below the skill level**. "Writing is weak" is less actionable than "opinion essays and bar charts are your weakest topics." Drives targeted task/resource selection. |
| **Inputs** | `TopicProfile` per topic (from S5–S10 assessments), `skill_profiles`, target band. |
| **Algorithm** | |
| `topic_gap = target_band − topic_avg_band` (topics with `n>=2`). |
| `topic_priority = topic_gap × recency_weight × (1 − n/50)` — penalizes low-sample noise, rewards fresh evidence. |
| Rank all topics; return top `K=3` as weakest. |
| **Outputs** | `[ { topic, skill, avg_band, gap, n, reason } ]`. |
| **Edge Cases** | Fewer than 2 topics with data → fall back to weakest **criteria** (e.g., "grammar_range") with a note. Topic with n=1 → excluded from ranking, listed as "needs more data". New topic just introduced → lower priority until enough samples. |

---

### M7. Next Best Tasks

| Aspect | Specification |
|---|---|
| **Purpose** | The **action output** of the Brain — the ranked candidate task list the scheduler draws from to build the daily mission. Unifies prediction, risk, topic gaps, and scheduling constraints into one selector. |
| **Inputs** | `weakest_topics`, `skill_gaps`, `overdue_tasks`, `today's protected-day status`, `overload_factor`, `recent task history (variety)`, `phase`, `daily budget`. |
| **Algorithm** | Candidate pool = overdue tasks ∪ current-phase tasks ∪ targeted tasks (built from weakest topics) ∪ quick-win tasks. Each candidate scored: |
| | `task_score = 0.30×GapScore + 0.20×Priority(overdue/mandatory) + 0.15×TopicScore + 0.15×VarietyScore + 0.10×EffortScore + 0.10×TimeFitScore` |
| | where |
| | `GapScore` = matches top skill gap (M1 skill gaps) |
| | `TopicScore` = targets a weakest topic (M6) |
| | `VarietyScore` = skill not done in last 3 days (SCHEDULER.md §3.4) |
| | `EffortScore` = task duration within remaining budget |
| | `TimeFitScore` = fits phase & days-to-exam pacing (M5) |
| | Protected-day override: if revision window → revision-mix only (SCHEDULER.md §7); if mock day → mock task only. |
| **Outputs** | `[ { task_id (or task_spec), title, skill, topic, duration_minutes, score, reason } ]` sorted desc. |
| **Edge Cases** | No candidates → generate a quick-win (10-min vocab). Overload > 1.5 → drop low-priority candidates, spread to next day (SCHEDULER.md §8). Rest day → empty list + "rest" state. All tasks done + target reached → maintenance-mode tasks. |

---

## 6. Decision Engine Orchestration

### 6.1 Recompute Graph

Inference modules have a **dependency order**; running out of order wastes compute:

```
1. Feature pipeline (refresh changed features)
2. M1 Predicted Band            ← needs features
3. M6 Weakest Topics            ← needs features + topic profiles
4. M7 Next Best Tasks           ← needs M1 gaps + M6 topics + scheduler state
5. M2 Readiness                 ← needs M1 + effort
6. M3 Risk                      ← needs M1 + M2 + schedule/consistency
7. M4 Probability               ← needs M1 + M2 + M3 + calibration set
8. M5 Recommended Hours         ← needs M1 gaps + temporal
   (M7 consumes M5 pacing for TimeFitScore → M5 may run before M7)
```

**Optimization:** full recompute runs on `daily.rollover`. On fast events (task completed, session ended) only the **affected modules** recompute:
- task completed → M7, M5 (effort), M2 (schedule adherence)
- assessment completed → M1, M6, M7, M2, M3, M4
- mock completed → M1, M2, M3, M4, M5 (mock trend), M7
- diagnostic completed → M1 (baseline), M6, M7

### 6.2 Rule Layer (Hard Constraints)

Applied **before** statistical scoring, mirroring SCHEDULER.md §7 protection system:

| Rule | Effect |
|---|---|
| Protected revision days | Only revision-mix tasks (no new heavy tasks) |
| Mock test day & ±1 day | Mock task / light review / mistake review only |
| Rest day | No tasks; streak frozen |
| Carry-forward never on protected days | SCHEDULER.md §7.3 |
| Overload ceiling (budget × 1.5) | Task pool trimmed before scoring |
| Streak-saver after 3 missed days | Force one 10-min quick-win task |

### 6.3 The Decision Bundle

Every inference cycle produces one **Decision Bundle**, persisted and pushed to consumers:

```json
{
  "user_id": "…",
  "computed_at": "2025-04-29T23:00:00Z",
  "predicted_band": { "overall": 6.8, "per_skill": {…}, "confidence": 0.7 },
  "readiness": { "score": 62, "label": "On Track", "components": {…} },
  "risk": { "score": 41, "label": "Moderate", "factors": {…} },
  "probability_target": { "p": 0.43, "band": "40–50%", "calibrated": true },
  "recommended_hours": { "weekly": 9, "per_skill": {…}, "pacing": "steady" },
  "weakest_topics": [ … ],
  "next_best_tasks": [ … ]
}
```

**Consumers:**
- **Scheduler** — consumes `next_best_tasks` to build the daily mission (replaces SCHEDULER.md §3 task selection inputs).
- **Roadmap** — consumes `predicted_band`, `risk`, `probability` to re-pace phases and show goal-feasibility.
- **Resource Engine** — consumes `weakest_topics` + skill gaps for `skill_gap` reasons (RESOURCE_ENGINE.md §6.3).
- **Dashboard** — renders the bundle via `/api/v1/brain/*` (W5/W7 + new W-risk/probability widgets).
- **Notifications** — risk-triggered alerts, probability milestones, next-best-task nudges.

---

## 7. Feedback & Calibration Loop

### 7.1 Decision Logging

Every Decision Bundle is appended to a `decision_log` (append-only, one row per recompute). Fields: user_id, bundle snapshot, trigger event, model_version, computed_at.

### 7.2 Outcome Capture

| Outcome | Source | Used to calibrate |
|---|---|---|
| Mock band (each) | `mock_tests.submitted_at` | M1 weights, M3 mock-trend, M4 |
| Diagnostic retake | `mock_tests` (diagnostic) | M1 baseline drift |
| **Real exam result** | User entry (post-exam flow) | M4 calibration set, M5 hours constant, M3 |
| Dropout / inactivity | 14+ days no activity | ConsistencyRisk thresholds |

### 7.3 Recalibration Jobs

| Job | Cadence | Action |
|---|---|---|
| **Prediction recalibration** | Weekly | Re-fit M1 ensemble weights on last N mock-vs-predicted deltas |
| **Probability calibration** | Monthly (or on 100 new exam outcomes) | Re-fit logistic coefficients + Platt bins |
| **Hours constant update** | Monthly | Re-estimate `HOURS_PER_0_5_BAND` from exam outcomes vs hours logged |
| **Threshold tuning** | Monthly | Risk/readiness label boundaries tuned to minimize false "Exam Ready" |

### 7.4 Cold-Start Strategy

New user with no history uses **population priors** (platform averages) blended with the diagnostic:

```
cold_start_band = 0.7 × diagnostic + 0.3 × population_prior(module)
cold_start_confidence = 0.3
```
The blend converges to user-specific data as samples accumulate (`confidence` rises toward 0.9).

---

## 8. Persistence & Data Contracts

### 8.1 New Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `live_user_state` | The Brain's working memory (JSON doc) | user_id PK, state JSONB, updated_at |
| `skill_profiles` | Normalized per-skill bands & trends | user_id, skill, current_band, trend_30d, confidence, criterion_scores JSONB, topics JSONB |
| `topic_profiles` | Per-topic aggregates | user_id, topic, skill, avg_band, n, recency_weight, updated_at |
| `decision_bundles` | Latest computed bundle | user_id PK, bundle JSONB, trigger, model_version, computed_at |
| `decision_log` | Append-only audit trail | id, user_id, bundle JSONB, trigger, model_version, computed_at |
| `risk_scores` | Risk history | user_id, score, factors JSONB, computed_at |
| `readiness_scores` | Readiness history | user_id, score, components JSONB, computed_at |
| `probability_target` | Probability history | user_id, p, calibrated, factors JSONB, computed_at |
| `model_registry` | Model versions & calibration meta | model_id, version, trained_at, metrics JSONB, is_active |

### 8.2 API Surface

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/brain/state` | GET | Live User State (dashboard consumes this) |
| `/api/v1/brain/prediction` | GET | Predicted band + confidence |
| `/api/v1/brain/readiness` | GET | Readiness score + components |
| `/api/v1/brain/risk` | GET | Risk score + factors + mitigations |
| `/api/v1/brain/probability` | GET | Probability of achieving target |
| `/api/v1/brain/hours` | GET | Recommended study hours |
| `/api/v1/brain/weakest-topics` | GET | Weakest topics list |
| `/api/v1/brain/next-tasks` | GET | Next-best-task ranking |
| `/api/v1/brain/recompute` | POST | Force a recompute (admin/debug) |

### 8.3 Caching & Performance

| Data | Store | TTL / Policy |
|---|---|---|
| Live User State | Redis | Invalidate on any signal event |
| Decision Bundle | Redis | Invalidate on recompute; served to dashboard |
| Skill/Topic profiles | Postgres + Redis read cache | 5-min TTL |
| Model weights & priors | Postgres (`model_registry`) + in-memory | Loaded at worker boot |
| Event stream | Redis Stream | Consumed by Brain workers |

---

## 9. Model Strategy & Explainability

### 9.1 Hybrid Approach

| Layer | Technique | Used for |
|---|---|---|
| **Rules** | Hard constraints, protection system, IELTS rounding, cold-start blending | Everywhere (invariant) |
| **Statistics** | Exponential-decay averages, weighted ensembles, logistic regression, Platt calibration | M1, M2, M3, M4, M5 |
| **Heuristics** | Priority scoring, variety enforcement, quick-wins | M7 |
| **LLM (optional)** | Natural-language explanations ("Your speaking fluency dipped after mock 2"), topic tagging of assessments | Explanation layer, topic extraction |

**Design choice:** heavy lifting is **statistical + rules** for determinism, cost control, and auditability. LLM is reserved for *explaining* decisions, never *making* them.

### 9.2 Explainability Contract

Every inference output MUST include:

1. **`contributing_factors`** — top 3–5 factors with direction (e.g., `{factor: "mock_avg", direction: "-0.5", weight: 0.20}`).
2. **`confidence`** — 0..1 based on sample count and recency.
3. **`model_version`** — auditable provenance.
4. **A human-readable `reason`** — generated from factors (template + optional LLM polish).

This guarantees the user (and the product team) always knows *why* the Brain said what it said.

---

## 10. Component Architecture & Roadmap

### 10.1 Services & Workers

```
backend/app/brain/
├── events/                 # event bus subscribers (ingest)
│   ├── assessment_event.py
│   ├── task_event.py
│   ├── session_event.py
│   └── mock_event.py
├── features/               # feature engineering pipeline
│   ├── feature_store.py
│   ├── performance_features.py
│   ├── consistency_features.py
│   ├── effort_features.py
│   └── temporal_features.py
├── state/                  # Live User State management
│   ├── live_state.py
│   ├── skill_profile.py
│   └── topic_profile.py
├── inference/              # the 7 modules (M1–M7)
│   ├── band_predictor.py
│   ├── readiness.py
│   ├── risk.py
│   ├── probability.py
│   ├── hours.py
│   ├── weakest_topics.py
│   └── next_tasks.py
├── decision/               # orchestration + decision bundle
│   ├── orchestrator.py
│   ├── rules.py            # hard constraints (protection system)
│   └── bundle.py
├── calibration/            # feedback loop
│   ├── outcome_ingest.py
│   ├── probability_calibrator.py
│   └── hours_estimator.py
├── models/                 # Pydantic contracts for all I/O
└── api/
    └── brain_router.py     # /api/v1/brain/*
```

### 10.2 Event-Driven Worker Model

- **Ingest workers** subscribe to Redis Streams (one per event type).
- **Inference workers** process recompute jobs; module-level tasks are idempotent.
- **Nightly rollover worker** triggers full recompute + calibration jobs.
- Celery queues: `brain-fast` (high-priority event recompute), `brain-slow` (calibration, full recompute).

### 10.3 Build Roadmap

| Phase | Scope | Enables |
|---|---|---|
| **P0 — Foundation** | Event bus, feature pipeline, Live User State, M1 band predictor | Live dashboard prediction; replaces mock band widget |
| **P1 — Motivation** | M2 Readiness, M3 Risk, M4 Probability, M5 Hours | Dashboard north-star metrics; risk alerts |
| **P1 — Action** | M6 Weakest Topics, M7 Next Best Tasks; wire into Scheduler | Adaptive daily mission from Brain outputs |
| **P2 — Self-learning** | Decision log, outcome capture, calibration jobs, model registry | Closed loop; improving accuracy |
| **P3 — Explainability** | LLM explanation layer, natural-language coaching messages | "Why" for every decision |

---

*This document defines the complete AI decision engine — the continuous evaluation loop that turns every user action into a signal, maintains a live state, and drives all eight outputs (predicted band, readiness, risk, probability, hours, weakest topics, next-best tasks) with explainability and self-calibration. It is the architectural source of truth for the `backend/app/brain` module.*

