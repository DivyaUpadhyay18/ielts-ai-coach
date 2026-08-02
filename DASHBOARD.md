# Ultimate IELTS Dashboard — Architecture Design

**Role:** Chief Product Architect
**Document:** Dashboard Widget Architecture & Data Contracts
**Status:** Draft for review & approval

---

## 0. Executive Summary

The Dashboard is the **highest-frequency screen** in IELTS AI Coach — the user's home base on every login. It must answer, at a glance, three questions:

1. **Where am I going?** — Exam countdown, target band, predicted band, readiness score.
2. **What do I do today?** — Today's mission, daily XP, quick continue, progress bars.
3. **How am I doing?** — Streak, skills (weakest/strongest), weekly/monthly progress, achievements.

This document specifies **17 widgets**, their purpose, data sources, computation rules, display intent, refresh triggers, and edge cases. It also defines the **readiness score** (a new composite metric), the **layout/prioritization architecture** (zone model), the **API surface** the frontend consumes, and the **implementation gaps** versus the current mock-data dashboard.

The architecture follows the project principles in ARCHITECTURE.md: **server is the source of truth**, async AI in workers, adaptive by design, and RLS-protected per-user data.

---

## 1. Dashboard Architecture Overview

### 1.1 Composition Model

The dashboard is a **widget grid** composed of server-fetched data. It is **not** a single monolithic page; each widget is independently:

- **Data-fetched** via a dedicated hook (`useWidgetName`) backed by TanStack Query.
- **Rendered** as a self-contained client component with its own skeleton, error state, and empty state.
- **Refreshed** on its own cadence (on-mount, realtime, on-event, or scheduled poll).

### 1.2 Data-Fetching Strategy

```
BFF aggregation endpoint (GET /api/v1/dashboard/overview)
  └─ returns the "goal cluster" (countdown, target, predicted, readiness, streak, mock)
     in ONE round trip for above-the-fold rendering (fastest paint).

Per-widget endpoints (GET /api/v1/dashboard/{widget})
  └─ lazy-load below-the-fold widgets on scroll / after interaction
     (today's mission list, resources, achievements, notifications).

Supabase Realtime channels
  └─ push updates for streak, notifications, task completion, band prediction
     (no polling for high-frequency counters).

Event-driven refetch (TanStack Query invalidation)
  └─ completing a task, receiving an assessment, or a scheduler rollover
     invalidates the affected widget keys.
```

### 1.3 Refresh Cadence by Widget Class

| Class | Widgets | Refresh Policy |
|---|---|---|
| **Realtime** | Notifications, Streak, Daily XP, Task checkboxes | Supabase Realtime push + optimistic update |
| **On-event** | Predicted Band, Weakest/Strongest Skill, Readiness, Recent Resources | Invalidate on assessment completion / diagnostic / mock submission |
| **On-mount + daily** | Countdown, Today's Mission, Daily/Weekly/Monthly Progress | Refetch on mount; scheduler rollover emits `daily_rollover` event |
| **On-mount only** | Target Band, Upcoming Mock Test | Refetch on mount and on goal/profile change |

### 1.4 Resilience & Performance

| Concern | Strategy |
|---|---|
| **Slow network** | Skeleton loaders per widget; goal cluster loads first; below-fold lazy-loads |
| **Widget API fails** | Per-widget error boundary; rest of dashboard remains usable; retry button |
| **Stale data** | `staleTime` on TanStack Query; background refetch on window focus |
| **No diagnostic yet** | Goal cluster + mission widgets render **onboarding state** (see edge cases) |
| **Mobile** | Zone model collapses; priority widgets (mission, countdown) stay above fold |
| **Offline** | Last-known data cached in localStorage; write actions queued and synced |

---

## 2. Widget Catalog

Each widget is specified with: **Purpose · Data Source · Computation · Display · Refresh Trigger · Edge Cases**.

### W1. Exam Countdown

| Aspect | Specification |
|---|---|
| **Purpose** | Creates urgency and anchors the entire plan. Transforms an abstract goal into a concrete date; drives the scheduler's intensity (crunch mode when < 30 days). |
| **Data Source** | `users.exam_date`; `users.timezone` for day-boundary correctness. |
| **Computation** | `days_left = exam_date - TODAY(user_tz)`. Intensity level: `normal` (> 60d), `focused` (30–60d), `intensive` (14–30d), `final` (< 14d). |
| **Display** | Days remaining (large number), exam date, intensity badge, mini progress bar of time elapsed vs. total plan window. |
| **Refresh Trigger** | On-mount; refetch on profile update; scheduler inserts countdown reminder notifications at T-30/T-14/T-7/T-1. |
| **Edge Cases** | No exam date set → prompt to set one (onboarding gate). Exam date passed → "post-exam" state (see SCHEDULER.md §9.1) with CTA to enter results or set a new date. User in a different timezone → compute against `users.timezone`, never server-local. |

---

### W2. Today's Mission

| Aspect | Specification |
|---|---|
| **Purpose** | The **primary action surface**. Reduces decision friction by telling the user exactly what to do next. Drives habit formation and the streak loop. |
| **Data Source** | `daily_plans` (today's row), `tasks` (via `daily_plan_id`), `task_completions`, `study_sessions`. |
| **Computation** | Scheduler generates the mission at daily rollover (SCHEDULER.md §3). Widget reads today's plan: `total_tasks`, `completed_tasks`, `total_minutes`, `completed_minutes`. Tasks ordered by `priority`, then `order_index`; overdue/carry-forward tasks flagged. |
| **Display** | Checkboxed task list (title, skill badge, duration, status), progress "X of Y tasks", "studied N / M minutes" bar. |
| **Refresh Trigger** | On-mount; realtime update on each task completion; `daily_rollover` event at midnight (user-local). |
| **Edge Cases** | Rest day → motivational "Rest Day" card, streak preserved. No tasks (plan not generated) → "Take your diagnostic to build your plan" CTA. 10+ overdue tasks → prioritize + warning banner. All complete → celebration state + offer bonus/review tasks. Task mid-way → resume state (draft essay/partial recording persisted). |

---

### W3. Daily XP

| Aspect | Specification |
|---|---|
| **Purpose** | Gamified feedback on **effort**, independent of score. Rewards consistency (a 10-min vocab review counts), drives daily habit completion, and feeds achievement thresholds. |
| **Data Source** | `study_sessions` (duration), `task_completions`, `resource_completions` (bonus XP). |
| **Computation** | XP ledger per day. Proposed award table: task completion = `10 XP`; resource completion = `5 XP`; study minute = `1 XP/min` (capped at daily budget + 50%); streak-bonus multiplier = `min(1 + 0.1 * streak, 2.0)`. Store computed `daily_xp` in `daily_activity` (denormalized for fast reads). |
| **Display** | Today's XP total, animated bar toward a **daily target** (e.g., 100 XP = full mission), "level" progress ring (optional). |
| **Refresh Trigger** | Realtime on study-session end / task completion (optimistic increment). |
| **Edge Cases** | No activity yet → 0 XP with "Complete your first task to earn XP". XP cap exceeded → show "cap reached" state. Rest day → XP target reduced or disabled. Rollover at midnight → reset daily XP, archive yesterday's. |

---

### W4. Current Streak

| Aspect | Specification |
|---|---|
| **Purpose** | The core retention mechanic (Duolingo-style). Motivates daily return and visualizes consistency, the single strongest predictor of band improvement. |
| **Data Source** | `streaks` (current_streak, longest_streak, last_activity_date), `daily_activity` for the mini calendar. |
| **Computation** | Streak engine (SCHEDULER.md §6): `current_streak = consecutive days with activity (minutes >= min_threshold)`, with rest-day preservation and streak-saver mode after 3 misses. |
| **Display** | Flame icon + current streak number, "longest" secondary stat, 7-day mini calendar (green = active, gray = inactive, orange = streak-saver/rest), "streak at risk" warning when today is a must-do day. |
| **Refresh Trigger** | Realtime on any activity event; daily rollover updates. |
| **Edge Cases** | Streak at risk (no activity 2 days) → warning banner + push reminder. Streak broken → empathetic state, restart CTA ("Start a new streak today"). Rest day → streak frozen (not broken). Planned vacation → freeze via `streaks.frozen` (SCHEDULER.md §9.6). |

---

### W5. Predicted Band

| Aspect | Specification |
|---|---|
| **Purpose** | Shows the **trajectory** — what the user would likely score today based on all evidence. Creates a gap-to-target conversation and motivates continued effort. |
| **Data Source** | `band_predictions` (predicted_band, confidence, model_version, features); inputs from `progress`, `assessments`, `mock_tests`, `study_sessions`. |
| **Computation** | Weighted regression model (SCHEDULER.md §5.4): combines diagnostic band, weighted avg of last 5 assessments, hours completed, streak length, mock average, tasks completed in 30 days; rounded to nearest 0.5; confidence 0.3–0.9 by assessment count. |
| **Display** | Large band number, trend arrow vs last prediction, confidence % ("±0.5 based on 12 assessments"), "last updated" timestamp. |
| **Refresh Trigger** | On-event: assessment submitted, mock completed, diagnostic retaken; nightly rollover. |
| **Edge Cases** | No assessments → hide or show diagnostic band with "Complete 2+ assessments for a prediction". Confidence < 0.5 → show "early estimate" label. Sharp drop → contextual reassurance ("scores fluctuate; focus on consistency"). Model version change → note "prediction model updated". |

---

### W6. Target Band

| Aspect | Specification |
|---|---|
| **Purpose** | The **fixed goal anchor** set during onboarding. Every other widget (predicted band, readiness, skill gaps) is measured against this number. |
| **Data Source** | `users.target_band` (via `user_goals` / onboarding). |
| **Computation** | Static value; band gap = `target_band − current predicted band`; days-to-target feasibility check vs. exam date (SCHEDULER.md §9.3). |
| **Display** | Target band number, "gap" badge (e.g., "1.0 to go"), progress bar of `(current − start) / (target − start)`. |
| **Refresh Trigger** | On-mount; refetch on goal change (Settings). |
| **Edge Cases** | No target set → onboarding CTA. Target changed → scheduler re-plans (extra/lost weeks logic, SCHEDULER.md §9.3) and widget reflects new gap. Target unreachable in remaining time → warning + suggestion to adjust exam date or target. |

---

### W7. Readiness Score

| Aspect | Specification |
|---|---|
| **Purpose** | A single **0–100 composite** answering "how ready am I for the exam?" — the dashboard's north-star metric. Simplifies the many signals into one actionable number. *(New composite metric — defined here.)* |
| **Data Source** | `band_predictions`, `user_goals`, `mock_tests`, `daily_activity`, `daily_plans`. |
| **Computation** | Weighted composite: |
| | |
| | `Readiness = 0.40 × BandProximity + 0.20 × MockConsistency + 0.15 × ScheduleAdherence + 0.15 × StudyVolume + 0.10 × StreakHealth` |
| | where |
| | `BandProximity = clamp( (predicted_band − start_band) / (target_band − start_band), 0, 1) × 100` |
| | `MockConsistency = avg over mocks of (mock_band / target_band) × 100` (0 if no mocks) |
| | `ScheduleAdherence = (completed_tasks_30d / scheduled_tasks_30d) × 100` |
| | `StudyVolume = clamp( (total_study_minutes_30d / (30 × daily_minutes_budget)) × 100, 0, 100 )` |
| | `StreakHealth = clamp( current_streak / 30, 0, 1) × 100` |
| | Category labels: 0–39 "Building Foundation", 40–69 "On Track", 70–84 "Nearly Ready", 85–100 "Exam Ready". |
| **Display** | Circular gauge with score, category label, and 1-sentence explanation ("Your mock average is your biggest gap"). |
| **Refresh Trigger** | On-event (assessment/mock/task) and nightly rollover. |
| **Edge Cases** | No mock tests → MockConsistency omitted (renormalize weights). No predicted band yet → substitute diagnostic band for BandProximity, label "provisional". Score drops > 15 pts in a week → notification + coaching message. Target reached → score shows 100 state + "maintenance mode" note. |

---

### W8. Upcoming Mock Test

| Aspect | Specification |
|---|---|
| **Purpose** | Makes the next **milestone** visible and reduces anxiety by showing what's coming. Mock tests are the strongest band signal and trigger roadmap re-calibration. |
| **Data Source** | `mock_tests` (scheduled rows: test_type, date), scheduler mock schedule (SCHEDULER.md §5.5). |
| **Computation** | `next_mock = min over scheduled mocks of date >= today`; countdown to it; type (section vs full); focus area. |
| **Display** | Card: "Mock Test #N" countdown, section type, focus-area chip, "Start" (if today) or "View prep plan" (day-before light-review reminder). |
| **Refresh Trigger** | On-mount; on scheduler re-schedule event. |
| **Edge Cases** | No mock scheduled (early plan) → "Mocks begin after Phase 2" informational state. Mock is today → prominent CTA + "find a quiet room" checklist. Mock rescheduled (carry-forward never applies to mocks) → updated card + notification. Post-mock → show "Review your mistakes" next step. |

---

### W9. Weakest Skill

| Aspect | Specification |
|---|---|
| **Purpose** | Tells the user **where to focus**. Directs effort to the highest-leverage improvement area, which the scheduler also weights (skill-deficiency weighting in SCHEDULER.md §2.2). |
| **Data Source** | `diagnostic_results.skill_scores`, `progress` (latest per criterion), `assessments.criteria_scores`. |
| **Computation** | `gap(criterion) = target_band − latest_score(criterion)`; pick criterion with the **largest gap** (not lowest absolute score — a 6.0 in a 6.5-target skill is a smaller gap than a 6.5 in a 7.5-target skill). Tie-break by recency, then by assessment count (more evidence wins). |
| **Display** | Skill name, current score vs target, gap badge, short AI reason, and 1 primary action ("Practice Task 2 essays"). |
| **Refresh Trigger** | On-event: any assessment/mock/diagnostic. |
| **Edge Cases** | No diagnostic/assessments → "Complete your diagnostic to identify weak areas". Skill with insufficient data (< 2 samples) → label "insufficient data", fall back to diagnostic. Gap ties → show both with "focus on either". |

---

### W10. Strongest Skill

| Aspect | Specification |
|---|---|
| **Purpose** | **Positive reinforcement** and strategy signal — shows what's already working so the user can lean into it (and use it to buy time in the real exam). |
| **Data Source** | Same as W9: `diagnostic_results`, `progress`, `assessments.criteria_scores`. |
| **Computation** | Smallest gap (or highest absolute score when gaps equal); tie-break by recency and sample count. |
| **Display** | Skill name, current score, "strength" badge, encouragement line, optional "push to next band" resource link. |
| **Refresh Trigger** | On-event (same as W9). |
| **Edge Cases** | No data → hidden until first assessment. Target already reached on this skill → "Maintain this skill" state. All skills equal → show "Balanced profile" message. |

---

### W11. Daily Progress

| Aspect | Specification |
|---|---|
| **Purpose** | Immediate, short-horizon feedback — "am I on track **today**?" Closes the loop between Today's Mission (W2) and Daily XP (W3). |
| **Data Source** | `daily_plans` (completed/total tasks, completed/total minutes for today), `daily_activity.minutes`. |
| **Computation** | `task_pct = completed_tasks / total_tasks`; `minute_pct = completed_minutes / total_minutes`; combine as `daily_progress = round(0.5 × task_pct + 0.5 × minute_pct) × 100`. |
| **Display** | Two micro-progress bars (tasks & minutes) or one composite bar with split markers; "X/Y tasks · N/M min". |
| **Refresh Trigger** | Realtime on task completion / session end. |
| **Edge Cases** | Rest day → "Rest day" state, no bar. Plan not generated → diagnostic CTA. Over 100% (bonus tasks) → bar caps at 100% with "+N bonus" tag. |

---

### W12. Weekly Progress

| Aspect | Specification |
|---|---|
| **Purpose** | Medium-horizon reflection — "was this a good week?" Catches streaks of low output before they compound; feeds the weekly-summary notification. |
| **Data Source** | `daily_activity` (last 7 days), `daily_plans` (last 7 days), `study_sessions`. |
| **Computation** | `week_completion = completed_tasks_7d / scheduled_tasks_7d`; `week_minutes = SUM(daily_activity.minutes)` over 7 days; `vs_budget = week_minutes / (7 × daily_minutes_budget)`. Status: "Ahead" (> 100%), "On Track" (80–100%), "Behind" (< 80%). |
| **Display** | 7-day bar strip (each day colored by activity), % completion, "N min / M min" vs budget, trend vs prior week. |
| **Refresh Trigger** | On-mount; realtime on activity; weekly rollover (Mon). |
| **Edge Cases** | Week just started → "early in the week" state. Zero scheduled tasks → rest-heavy week note. Streak-saver days → counted as activity (habit preserved) but labeled. |

---

### W13. Monthly Progress

| Aspect | Specification |
|---|---|
| **Purpose** | Long-horizon trend — "am I actually improving month over month?" Connects effort (hours) to outcome (band movement) and surfaces plateaus. |
| **Data Source** | `daily_activity` (30d), `progress` (band points in 30d), `band_predictions` (current vs 30d ago). |
| **Computation** | `hours_studied_30d`; `band_delta = predicted_band_now − predicted_band_30d_ago` (or diagnostic band as baseline); `assessments_taken_30d`; `completion_rate_30d`. |
| **Display** | Small trend chart (band over last 4–6 weeks), headline stats (hours, band delta, tests taken), "monthly summary" line (e.g., "You added +0.5 band in 22 hours"). |
| **Refresh Trigger** | On-mount; nightly rollover; on prediction recompute. |
| **Edge Cases** | First month → baseline = diagnostic, "first month" label. Band plateau → "plateau detected" coaching note + suggest a mock or new strategy. Fewer than 10 hours → "low volume month" gentle nudge, no judgment. |

---

### W14. Recent Resources

| Aspect | Specification |
|---|---|
| **Purpose** | Content discovery driven by current gaps — keeps the user in learning mode and surfaces free high-quality materials at the moment of need. |
| **Data Source** | `resource_recommendations` (top N by score, not dismissed/expired), joined with `resources` metadata. |
| **Computation** | Recommendation scoring per RESOURCE_ENGINE.md §5 (skill-gap 30%, band-match 20%, popularity 15%, diversity 10%, recency 10%, provider 10%, scheduler alignment 5%). Regenerated on signup, assessment, phase transition, daily, resource consumed. |
| **Display** | 2–3 compact cards: title, provider badge, type icon, reason line ("Targets your weakest skill: Grammar"), duration, "View" + "Dismiss". |
| **Refresh Trigger** | On-mount; on assessment completion; on dismiss/completion (replace with next best). |
| **Edge Cases** | No diagnostic yet → popular/featured resources (no personalization) + prompt to take diagnostic. User completed all → "New resources added weekly" state. Dismissed items → hidden 30 days (RESOURCE_ENGINE.md §12). Broken link → hidden (link-checker daily). |

---

### W15. Achievements

| Aspect | Specification |
|---|---|
| **Purpose** | Long-term **motivation milestones** beyond streaks — badges for consistency, volume, accuracy, and milestones (e.g., "7-Day Streak", "10 Essays", "First Mock"). |
| **Data Source** | `achievements` (catalog), `user_achievements` (earned), derived from `streaks`, `task_completions`, `mock_tests`, `vocabulary`. |
| **Computation** | Achievement service evaluates unlock conditions on each relevant event (streak update, assessment count, mock completed, XP thresholds). |
| **Display** | Recent 3 earned badges + "next badge" progress (e.g., "2/7 days to 7-Day Streak"), all-badges link. |
| **Refresh Trigger** | On-event (task completion, streak, assessment); realtime badge-unlock notification. |
| **Edge Cases** | No badges yet → show first achievable badge + progress ("Complete 3 tasks to earn 'First Steps'"). Badge just unlocked → toast/celebration + push to list. Disabled for users who opt out of gamification (preference flag). |

---

### W16. Notifications

| Aspect | Specification |
|---|---|
| **Purpose** | The **attention channel** — surfaces AI-feedback-ready, reminders, system updates, and streak-at-risk alerts without the user navigating away. |
| **Data Source** | `notifications` (type: ai_feedback | reminder | system; is_read), Supabase Realtime channel per user. |
| **Computation** | None (CRUD). Badge count = `COUNT WHERE is_read = false`. |
| **Display** | Bell icon + unread-count badge in the dashboard header; widget shows latest 3 with type icon, time, read/unread state; "View all" → `/notifications`. |
| **Refresh Trigger** | Realtime push; on-mount initial fetch; mark-as-read optimistically clears badge. |
| **Edge Cases** | Zero unread → badge hidden; empty-state "All caught up". Push channel drops → refetch on reconnect (Supabase rejoin). Notification links to deleted assessment → graceful fallback to notifications list. |

---

### W17. Quick Continue

| Aspect | Specification |
|---|---|
| **Purpose** | **Zero-friction resume.** Removes the "where was I?" barrier so the user re-enters flow in one click. The single most important habit-retention affordance. |
| **Data Source** | `study_sessions` (most recent in_progress), `tasks` (last in_progress/started), `resource_completions` (in_progress). |
| **Computation** | `resume_target = latest of (task with status='in_progress', session without ended_at, resource with status='in_progress')`; fallback to the **next incomplete task** in today's mission. |
| **Display** | Hero CTA card: task type icon, title, progress ("draft saved · 132 words"), estimated remaining time, big "Continue" button. |
| **Refresh Trigger** | On-mount; realtime on state change (draft save, session pause). |
| **Edge Cases** | Nothing in progress → show "Start Today's First Task" (links to W2 mission top item). Draft is stale (> 7 days) → prompt "Resume or discard draft?". Target page deleted → fallback to next mission task. User completed everything → "All caught up — bonus practice?" state. |

---

## 3. Layout & Prioritization Architecture

### 3.1 Zone Model (Desktop)

The dashboard is divided into **four zones**, ordered by attention priority. Each widget has an assigned zone; zones degrade gracefully on smaller viewports.

| Zone | Position | Widgets | Rationale |
|---|---|---|---|
| **Zone 1 — Goal Cluster** | Top, full-width | W1 Countdown, W5 Predicted Band, W6 Target Band, W7 Readiness Score, W4 Streak | Answers "where am I going?" in the first paint; highest emotional stakes |
| **Zone 2 — Action Surface** | Top-left, primary column | W2 Today's Mission, W17 Quick Continue, W11 Daily Progress | Answers "what do I do now?"; the habit loop lives here |
| **Zone 3 — Progress Rail** | Middle-right column | W3 Daily XP, W8 Upcoming Mock, W9 Weakest Skill, W10 Strongest Skill, W12 Weekly Progress, W13 Monthly Progress | Answers "how am I doing?"; secondary-but-encouraging |
| **Zone 4 — Discovery & Attention Shelf** | Bottom, full-width | W14 Recent Resources, W15 Achievements, W16 Notifications | Answers "what else is there?"; non-blocking, scroll/lazy-loaded |

### 3.2 Mobile Degradation

| Zone | Mobile Behavior |
|---|---|
| Zone 1 | Condensed into a 2×2 grid (countdown + streak + predicted + readiness); target band shown as a chip on predicted band card |
| Zone 2 | Mission becomes the single above-fold card; Quick Continue merges into mission header |
| Zone 3 | Collapses to 2-column tiles; weekly/monthly progress accessible via horizontal swipe or "Analytics" link |
| Zone 4 | Below-fold; notifications badge stays in header; resources/achievements via "More" section |

### 3.3 Loading Priority

```
Paint 1 (immediate):  W16 notifications badge (header), W1 countdown, W6 target
Paint 2 (above fold): W4 streak, W5 predicted, W7 readiness, W2 mission, W17 continue
Paint 3 (scroll):     W3, W8, W9, W10, W11, W12, W13
Paint 4 (lazy):       W14, W15
```

---

## 4. API Surface & Data Contracts

### 4.1 Endpoints

| Endpoint | Method | Purpose | Widgets |
|---|---|---|---|
| `/api/v1/dashboard/overview` | GET | Goal cluster in one round trip | W1, W4, W5, W6, W7 |
| `/api/v1/dashboard/mission?date=today` | GET | Today's plan + tasks + progress | W2, W11 |
| `/api/v1/dashboard/skills` | GET | Weakest/strongest + gaps | W9, W10 |
| `/api/v1/dashboard/progress?range=daily\|weekly\|monthly` | GET | Aggregated progress data | W12, W13 |
| `/api/v1/dashboard/xp` | GET | Daily XP + target + level | W3 |
| `/api/v1/dashboard/mocks/next` | GET | Upcoming mock + prep state | W8 |
| `/api/v1/dashboard/continue` | GET | Resume target resolution | W17 |
| `/api/v1/recommendations?limit=3` | GET | Top recommendations | W14 |
| `/api/v1/achievements/recent` | GET | Recent + next badges | W15 |
| `/api/v1/notifications?limit=3&unread_only=true` | GET | Notification preview | W16 |
| `POST /api/v1/tasks/{id}/complete` | POST | Complete task → invalidate mission/xp/progress | W2, W3, W11 |

### 4.2 Example — `GET /api/v1/dashboard/overview` Response Contract

```json
{
  "countdown": {
    "exam_date": "2025-06-15",
    "days_left": 47,
    "intensity": "focused"
  },
  "target_band": 7.5,
  "predicted_band": {
    "band": 6.5,
    "trend": 0.0,
    "confidence": 0.7,
    "last_updated": "2025-04-29T22:10:00Z"
  },
  "readiness": {
    "score": 62,
    "label": "On Track",
    "explanation": "Your mock average is your biggest lever."
  },
  "streak": {
    "current": 6,
    "longest": 14,
    "at_risk": false,
    "frozen": false
  }
}
```

### 4.3 Realtime Channels

| Channel | Event | Widgets updated |
|---|---|---|
| `user:{id}:notifications` | INSERT (new), UPDATE (read) | W16 |
| `user:{id}:activity` | INSERT/UPDATE daily_activity | W3, W4, W12 |
| `user:{id}:tasks` | UPDATE status | W2, W11, W17 |
| `user:{id}:assessments` | INSERT (feedback ready) | W5, W7, W9, W10 |
| `scheduler:{id}:rollover` | daily mission generated | W1, W2, W8 |

---

## 5. Readiness Score — Deep Definition

The **Readiness Score (W7)** is a new dashboard metric defined in this document. It is computed server-side by a `readiness_service.py` and stored (cached) in `band_predictions.meta` or a dedicated `readiness_scores` table with `(user_id, score, components JSONB, computed_at)`.

```
Readiness = clamp(0,100):
  0.40 × BandProximity     = predicted vs start vs target  → 0–100
  0.20 × MockConsistency   = avg(mock_band)/target         → 0–100 (0 if no mocks)
  0.15 × ScheduleAdherence = completed/scheduled (30d)     → 0–100
  0.15 × StudyVolume       = minutes/(30×budget)           → 0–100
  0.10 × StreakHealth      = current_streak/30             → 0–100

Renormalization: if MockConsistency missing (no mocks), weights become
  0.50 / 0.20 / 0.20 / 0.10 (BandProximity, Schedule, Volume, Streak).
```

**Why this composition:** Band proximity is the outcome metric (highest weight); mock performance is the most trustworthy signal of true readiness; schedule adherence and study volume capture effort consistency; streak health captures habit sustainability. The score is deliberately **explainable** — every drop in score maps to a named component, enabling the coaching message.

---

## 6. Implementation Gaps & Backlog

| Widget | Backend Needed | Status Today |
|---|---|---|
| W1 Countdown | `users.exam_date` (exists) | Frontend mock → wire live |
| W2 Mission | Scheduler daily generation + `daily_plans`/`tasks` tables | **Not built** — P0 (SCHEDULER.md) |
| W3 Daily XP | XP ledger service + `daily_activity.xp` | **Not built** — new |
| W4 Streak | Streak engine (SCHEDULER.md §6) | **Not built** — P1 |
| W5 Predicted Band | Prediction service + `band_predictions` | **Not built** — P1 |
| W6 Target Band | `users.target_band` (exists) | Frontend mock → wire live |
| W7 Readiness | `readiness_service.py` (**new**) | **Not built** — new |
| W8 Upcoming Mock | Mock scheduler (SCHEDULER.md §5.5) + `mock_tests` | **Not built** — P1 |
| W9/W10 Skills | Diagnostic + progress + assessments | Partially exists → aggregate endpoint |
| W11/12/13 Progress | Daily/weekly/monthly aggregation service | **Not built** — aggregation |
| W14 Resources | Resource engine (RESOURCE_ENGINE.md) | **Not built** — P1 |
| W15 Achievements | Achievement service + tables | **Not built** — new |
| W16 Notifications | Notification service + Realtime | Partially exists (mock page) |
| W17 Quick Continue | Session/task resume resolver | **Not built** — new |

### Recommended Build Order

1. **P0 (unlocks core loop):** W1, W2, W6, W11 — mission + countdown + progress live data.
2. **P1 (motivation):** W3, W4, W5, W16 — XP, streak, prediction, notifications.
3. **P1 (differentiators):** W7 (readiness), W8 (mock), W9/W10 (skills), W14 (resources).
4. **P2 (polish):** W12, W13, W15, W17.

---

*This document is a living artifact. The dashboard widget catalog, readiness-score formula, and API contracts are the source of truth for the frontend Dashboard and the backend `/api/v1/dashboard/*` router.*

