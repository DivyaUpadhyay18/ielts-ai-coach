# IELTS AI Coach — User Behavior Analytics

**Role:** Chief Product Officer & Data Architect
**Document:** Analytics & Event Tracking Design
**Status:** Draft for review & approval

---

## 0. Executive Summary

The Analytics System is the **product's measurement backbone**. It captures every meaningful user action as a structured event, pipes it into a unified analytics pipeline, and powers the KPIs, dashboards, and growth models that drive product decisions.

This document specifies the complete event taxonomy covering **11 core KPI families**:

| # | KPI | What it measures |
|---|---|---|
| 1 | **Registration** | Signup conversion, signup method, signup velocity |
| 2 | **Daily Active Users (DAU)** | Engagement volume, daily/weekly/monthly active users |
| 3 | **Session Duration** | Depth of engagement per visit |
| 4 | **Tasks Completed** | Learning output, daily mission completion rate |
| 5 | **Videos Watched** | Resource consumption, content engagement |
| 6 | **Study Minutes** | Total invested time, consistency |
| 7 | **Resource Clicks** | Content discovery, recommendation effectiveness |
| 8 | **Roadmap Completion** | Study plan progress, phase advancement |
| 9 | **Streak Length** | Habit formation, retention proxy |
| 10 | **Retention** | Day N retention, weekly/monthly resurrection |
| 11 | **Exam Success** | Outcome achievement, band score improvement |

**Design principles:**

1. **Event-first, not metric-first** — define all events at the grain of a single user action; KPIs are aggregations of events, never the reverse.
2. **Server-authoritative for business events** — write events on the server (after validation, deduplication) to ensure accuracy; client-side events are supplementary (UX telemetry, scroll depth).
3. **Consistent identity** — all events carry `user_id`, `session_id`, `anonymous_id` (pre-auth), `timestamp`, and `environment` (production/staging/beta).
4. **Privacy-by-default** — no PII in event names/values; user IDs are pseudonymous; IPs are anonymized; opt-out mechanism required.
5. **Backward-compatible evolution** — events are append-only; properties are additive; never rename or delete a property — only deprecate.

---

## 1. Event Taxonomy

### 1.1 Event Naming Convention

```
[domain]_[action]            — e.g., auth_signup, task_completed, video_watched
```

| Convention | Rule | Example |
|---|---|---|
| Domain | Lowercase, singular noun | `auth`, `task`, `resource`, `session`, `roadmap`, `streak`, `diagnostic`, `writing`, `speaking`, `assessment`, `mock_test` |
| Action | Past-tense verb | `signup`, `completed`, `watched`, `clicked`, `started`, `rated` |
| Separator | Underscore | `video_watched`, `task_completed` |

### 1.2 Global Properties (Every Event)

| Property | Type | Description | Example |
|---|---|---|---|
| `event` | `string` | Event name | `auth_signup` |
| `user_id` | `uuid` | Authenticated user ID (null pre-auth) | `9f8c2b1e-...` |
| `anonymous_id` | `uuid` | Device-level anonymous ID (set before auth) | `a1b2c3d4-...` |
| `session_id` | `uuid` | Session ID (generated on app load) | `e5f6g7h8-...` |
| `timestamp` | `datetime` | Event time (ISO 8601 UTC) | `2025-05-01T14:23:11Z` |
| `environment` | `string` | `production` \| `staging` \| `beta` | `production` |
| `app_version` | `string` | Semantic version of the frontend | `0.4.3` |
| `platform` | `string` | `web` \| `mobile` | `web` |
| `user_agent` | `string` | Browser user-agent string (anonymized) | `Mozilla/5.0...` |
| `referrer` | `string` | Document referrer (UTM params parsed) | `https://google.com/...` |
| `country` | `string` | Geo-IP derived country code | `IN` |
| `device` | `string` | `desktop` \| `tablet` \| `mobile` | `desktop` |

### 1.3 User Properties (Identity Traits)

Stored in a separate `user_properties` store and joined at query time (not sent with every event):

| Property | Type | Description | Set at |
|---|---|---|---|
| `$user_id` | `uuid` | User ID | Signup |
| `$email` | `string` | Email (hashed for analytics) | Signup |
| `$name` | `string` | Full name | Signup / onboarding |
| `$signup_date` | `date` | Account creation date | Signup |
| `$signup_method` | `string` | `email` \| `google` \| `magic_link` | Signup |
| `$plan` | `string` | `free` \| `pro` \| `ultimate` | Account creation |
| `$country` | `string` | ISO country code | Onboarding |
| `$timezone` | `string` | IANA timezone | Onboarding |
| `$target_band` | `numeric` | Target IELTS band | Onboarding |
| `$module` | `string` | `academic` \| `general` | Onboarding |
| `$daily_minutes` | `int` | Daily study commitment | Onboarding |
| `$exam_date` | `date` | Target exam date | Onboarding / settings |
| `$diagnostic_band` | `numeric` | Baseline band from diagnostic | Diagnostic complete |
| `$current_band` | `numeric` | Latest predicted band | Updated on assessment |
| `$streak` | `int` | Current streak length | Updated daily |
| `$longest_streak` | `int` | Longest streak ever | Updated daily |
| `$total_study_minutes` | `int` | Lifetime study minutes | Updated on session end |
| `$tasks_completed` | `int` | Lifetime tasks completed | Updated on task completion |
| `$phase` | `string` | Current roadmap phase | Phase transition |
| `$cohort_date` | `date` | Week of signup (for cohort analysis) | Signup |

---

## 2. Event Catalog

### 2.1 Auth & Registration Events

#### `auth_signup`

**Trigger:** User successfully creates an account.

| Property | Type | Example |
|---|---|---|
| `method` | `string` | `email` \| `google` \| `magic_link` |
| `has_full_name` | `boolean` | `true` |
| `referrer_source` | `string` | `direct` \| `google` \| `product_hunt` \| `referral` \| `youtube` |
| `utm_source` | `string` | `product_hunt` |
| `utm_medium` | `string` | `social` |
| `utm_campaign` | `string` | `launch_week` |

**Used for:** Registration count, signup velocity, channel attribution, signup conversion rate.

#### `auth_login`

**Trigger:** User successfully authenticates (email/password, OAuth, session restore).

| Property | Type | Example |
|---|---|---|
| `method` | `string` | `email` \| `google` \| `session_restore` |
| `is_returning` | `boolean` | `true` |
| `days_since_last_visit` | `int` | `3` |

**Used for:** DAU, login frequency, churn prediction.

#### `auth_logout`

**Trigger:** User explicitly logs out.

| Property | Type | Example |
|---|---|---|
| `session_duration_seconds` | `int` | `1842` |
| `tasks_completed_this_session` | `int` | `2` |

**Used for:** Session duration calculation, engagement depth.

#### `onboarding_completed`

**Trigger:** User completes the onboarding profile setup (skips also counted).

| Property | Type | Example |
|---|---|---|
| `target_band` | `numeric` | `7.5` |
| `module` | `string` | `academic` |
| `daily_minutes` | `int` | `60` |
| `exam_date` | `date` | `2025-12-15` |
| `country` | `string` | `IN` |
| `timezone` | `string` | `Asia/Kolkata` |
| `skipped` | `boolean` | `false` |

**Used for:** Onboarding completion rate, goal distribution, activation funnel.

### 2.2 Session Events

#### `session_started`

**Trigger:** User opens the app (page load / app open) — sent once per session.

| Property | Type | Example |
|---|---|---|
| `entry_page` | `string` | `/dashboard` \| `/login` \| `/writing` |
| `is_new_session` | `boolean` | `true` |
| `previous_session_end` | `datetime` | `2025-05-01T10:00:00Z` |

**Used for:** DAU, session count, session interval.

#### `session_ended`

**Trigger:** User becomes inactive for 30 minutes, closes tab, or logs out.

| Property | Type | Example |
|---|---|---|
| `duration_seconds` | `int` | `1842` |
| `pages_visited` | `int` | `5` |
| `tasks_completed` | `int` | `2` |
| `resources_viewed` | `int` | `1` |
| `exit_page` | `string` | `/dashboard` |
| `last_event` | `string` | `task_completed` |

**Used for:** Session duration, pages per session, session depth.

#### `page_viewed`

**Trigger:** User navigates to a page (throttled: max 1 per 5 seconds per page).

| Property | Type | Example |
|---|---|---|
| `page` | `string` | `/dashboard` |
| `page_category` | `string` | `dashboard` \| `writing` \| `speaking` \| `roadmap` \| `analytics` \| `resources` \| `diagnostic` \| `settings` \| `profile` \| `auth` |
| `referrer_page` | `string` | `/login` |
| `load_time_ms` | `int` | `1200` |
| `is_authenticated` | `boolean` | `true` |

**Used for:** Page popularity, navigation flow analysis, load time monitoring.

### 2.3 Diagnostic Events

#### `diagnostic_started`

**Trigger:** User begins the diagnostic assessment.

| Property | Type | Example |
|---|---|---|
| `section` | `string` | `writing` \| `speaking` \| `vocabulary` |
| `section_order` | `int` | `1` |

**Used for:** Diagnostic start rate, section dropout analysis.

#### `diagnostic_section_completed`

**Trigger:** User completes one section of the diagnostic.

| Property | Type | Example |
|---|---|---|
| `section` | `string` | `writing` |
| `time_spent_seconds` | `int` | `540` |
| `word_count` | `int` | `320` | (writing only) |
| `recording_duration_seconds` | `int` | `90` | (speaking only) |
| `vocabulary_score` | `int` | `7` | (vocabulary only) |

**Used for:** Section completion rate, time per section, diagnostic funnel.

#### `diagnostic_completed`

**Trigger:** User completes all 3 sections of the diagnostic.

| Property | Type | Example |
|---|---|---|
| `overall_band` | `numeric` | `6.5` |
| `writing_band` | `numeric` | `6.0` |
| `speaking_band` | `numeric` | `7.0` |
| `vocabulary_score` | `int` | `7` |
| `total_duration_seconds` | `int` | `1200` |
| `cefr_level` | `string` | `B2` |
| `top_strength` | `string` | `Task Response` |
| `top_weakness` | `string` | `Grammatical Range` |

**Used for:** Diagnostic completion rate, baseline score distribution, activation milestone.

### 2.4 Task Events

#### `task_started`

**Trigger:** User opens a task from the daily mission or roadmap.

| Property | Type | Example |
|---|---|---|
| `task_id` | `uuid` | `...` |
| `task_type` | `string` | `writing_task2` \| `speaking_part1` \| `vocab_set` \| `grammar_lesson` \| `reading` \| `listening` \| `mock_section` \| `review` |
| `skill` | `string` | `writing` \| `speaking` \| `vocabulary` \| `grammar` \| `reading` \| `listening` |
| `phase_index` | `int` | `1` |
| `daily_plan_id` | `uuid` | `...` |
| `is_carry_forward` | `boolean` | `false` |
| `estimated_duration_minutes` | `int` | `40` |

**Used for:** Task engagement, task-type popularity, daily mission interaction.

#### `task_completed`

**Trigger:** User marks a task as complete (or auto-completes via assessment).

| Property | Type | Example |
|---|---|---|
| `task_id` | `uuid` | `...` |
| `task_type` | `string` | `writing_task2` |
| `skill` | `string` | `writing` |
| `duration_minutes` | `int` | `38` |
| `estimated_duration_minutes` | `int` | `40` |
| `over_under_minutes` | `int` | `-2` |
| `is_carry_forward` | `boolean` | `false` |
| `phase_index` | `int` | `1` |
| `source` | `string` | `daily_mission` \| `roadmap` \| `quick_action` \| `notification` |
| `assessment_id` | `uuid` | `...` | (if writing/speaking) |
| `band_score` | `numeric` | `7.0` | (if writing/speaking) |

**Used for:** Tasks completed (KPI), task completion rate, over/under estimation accuracy, daily mission progress.

#### `task_skipped`

**Trigger:** User explicitly skips or dismisses a task.

| Property | Type | Example |
|---|---|---|
| `task_id` | `uuid` | `...` |
| `task_type` | `string` | `speaking_part1` |
| `reason` | `string` | `too_hard` \| `too_easy` \| `no_time` \| `no_mic` \| `other` |

**Used for:** Task difficulty calibration, scheduler feedback (SCHEDULER.md §8).

### 2.5 Writing & Speaking Events

#### `writing_essay_started`

**Trigger:** User begins typing in the writing editor.

| Property | Type | Example |
|---|---|---|
| `task_id` | `uuid` | `...` |
| `task_type` | `string` | `writing_task1` \| `writing_task2` |
| `prompt` | `string` | Truncated prompt (first 100 chars) |

**Used for:** Writing engagement, prompt popularity.

#### `writing_essay_submitted`

**Trigger:** User submits an essay for AI assessment.

| Property | Type | Example |
|---|---|---|
| `task_id` | `uuid` | `...` |
| `word_count` | `int` | `320` |
| `time_spent_seconds` | `int` | `1200` |
| `is_auto_submit` | `boolean` | `false` | (true if timer expired) |
| `benefited_from_timer` | `boolean` | `true` |

**Used for:** Writing submission rate, word count distribution, time management.

#### `speaking_recording_started`

**Trigger:** User begins recording a speaking response.

| Property | Type | Example |
|---|---|---|
| `task_id` | `uuid` | `...` |
| `part` | `int` | `1` \| `2` \| `3` |
| `mic_permission_granted` | `boolean` | `true` |

**Used for:** Speaking engagement, microphone permission success rate.

#### `speaking_recording_completed`

**Trigger:** User stops recording or timer expires.

| Property | Type | Example |
|---|---|---|
| `task_id` | `uuid` | `...` |
| `duration_seconds` | `int` | `90` |
| `is_auto_submit` | `boolean` | `false` |
| `file_size_bytes` | `int` | `512000` |

**Used for:** Speaking recording duration, audio quality proxy.

#### `assessment_feedback_viewed`

**Trigger:** User views the AI feedback overlay after a writing or speaking assessment.

| Property | Type | Example |
|---|---|---|
| `assessment_id` | `uuid` | `...` |
| `task_type` | `string` | `writing_task2` |
| `band_score` | `numeric` | `7.0` |
| `time_spent_viewing_seconds` | `int` | `45` |
| `feedback_rating` | `int` | `4` | (if rated — see FEEDBACK_SYSTEM.md) |

**Used for:** Feedback engagement, AI quality proxy, assessment-to-feedback funnel.

### 2.6 Resource Events

#### `resource_clicked`

**Trigger:** User clicks on a resource (recommendation card, search result, bookmark).

| Property | Type | Example |
|---|---|---|
| `resource_id` | `uuid` | `...` |
| `resource_type` | `string` | `youtube` \| `pdf` \| `website` \| `vocab_sheet` \| `grammar_guide` \| `listening` \| `writing_sample` \| `speaking` \| `practice_test` \| `strategy` |
| `provider` | `string` | `british_council` \| `ielts_liz` \| `e2_ielts` \| ... |
| `skill` | `string` | `writing` \| `speaking` \| `vocabulary` \| `grammar` \| `reading` \| `listening` |
| `source` | `string` | `recommendation` \| `search` \| `bookmark` \| `task_link` \| `browse` |
| `recommendation_id` | `uuid` | `...` | (if from recommendation) |
| `rank` | `int` | `2` | (position in recommendation list) |

**Used for:** Resource clicks (KPI), recommendation CTR, content discovery.

#### `video_watched`

**Trigger:** User watches a video resource (≥ 10 seconds continuous play).

| Property | Type | Example |
|---|---|---|
| `resource_id` | `uuid` | `...` |
| `provider` | `string` | `e2_ielts` \| `ielts_liz` \| ... |
| `video_title` | `string` | Truncated title |
| `video_duration_seconds` | `int` | `1200` |
| `watch_duration_seconds` | `int` | `840` |
| `watch_percentage` | `float` | `70.0` |
| `completed` | `boolean` | `false` | (≥ 90% watched) |
| `source` | `string` | `recommendation` \| `search` \| `task_link` | |

**Used for:** Videos watched (KPI), video completion rate, content engagement.

#### `video_watch_progress`

**Trigger:** Fired at 25%, 50%, 75%, 90% watch milestones (throttled).

| Property | Type | Example |
|---|---|---|
| `resource_id` | `uuid` | `...` |
| `milestone` | `float` | `0.50` |
| `watch_duration_seconds` | `int` | `420` |

**Used for:** Video drop-off analysis, content quality proxy.

#### `pdf_opened`

**Trigger:** User opens a PDF resource.

| Property | Type | Example |
|---|---|---|
| `resource_id` | `uuid` | `...` |
| `provider` | `string` | `british_council` |
| `scroll_depth_percent` | `int` | `65` | (throttled, max 1 per 10s) |

**Used for:** PDF engagement, content consumption.

#### `resource_bookmarked`

**Trigger:** User bookmarks a resource.

| Property | Type | Example |
|---|---|---|
| `resource_id` | `uuid` | `...` |
| `collection_name` | `string` | `favorites` \| `to_study` \| `writing` |

**Used for:** Bookmark rate, content value signal.

#### `resource_completed`

**Trigger:** User marks a resource as complete (or auto-completes via watch threshold).

| Property | Type | Example |
|---|---|---|
| `resource_id` | `uuid` | `...` |
| `resource_type` | `string` | `youtube` |
| `time_spent_minutes` | `int` | `15` |
| `completion_source` | `string` | `auto_complete` \| `manual_mark` |

**Used for:** Resource completion rate, content consumption KPI.

### 2.7 Roadmap Events

#### `roadmap_generated`

**Trigger:** AI generates a personalized study roadmap after diagnostic.

| Property | Type | Example |
|---|---|---|
| `roadmap_id` | `uuid` | `...` |
| `start_band` | `numeric` | `6.5` |
| `target_band` | `numeric` | `7.5` |
| `total_weeks` | `int` | `12` |
| `phase_count` | `int` | `5` |
| `generation_time_ms` | `int` | `3400` |

**Used for:** Roadmap generation success rate, band gap distribution.

#### `roadmap_phase_unlocked`

**Trigger:** User advances to the next phase (completion ≥ 80% or time elapsed).

| Property | Type | Example |
|---|---|---|
| `roadmap_id` | `uuid` | `...` |
| `phase_index` | `int` | `2` |
| `phase_title` | `string` | `Skill Building` |
| `completion_rate` | `float` | `85.0` |
| `days_in_phase` | `int` | `28` |
| `tasks_completed_in_phase` | `int` | `24` |
| `predicted_band` | `numeric` | `7.0` | (at phase transition) |

**Used for:** Roadmap completion (KPI), phase advancement rate, time per phase.

#### `roadmap_task_rescheduled`

**Trigger:** Scheduler automatically reschedules a missed task.

| Property | Type | Example |
|---|---|---|
| `task_id` | `uuid` | `...` |
| `original_date` | `date` | `2025-05-01` |
| `new_date` | `date` | `2025-05-03` |
| `shift_days` | `int` | `2` |
| `reason` | `string` | `missed` \| `overload` \| `protection` |

**Used for:** Scheduler overload detection, carry-forward frequency.

#### `roadmap_completed`

**Trigger:** User completes all phases in the roadmap (or exam date passes).

| Property | Type | Example |
|---|---|---|
| `roadmap_id` | `uuid` | `...` |
| `total_days_elapsed` | `int` | `84` |
| `planned_days` | `int` | `90` |
| `completion_rate` | `float` | `93.0` |
| `final_predicted_band` | `numeric` | `7.5` |
| `target_band` | `numeric` | `7.5` |
| `band_gap_closed` | `numeric` | `1.0` | (= target_band - start_band) |

**Used for:** Roadmap completion rate, time-to-completion, band improvement.

### 2.8 Streak Events

#### `streak_updated`

**Trigger:** Daily streak engine updates the user's streak (fired once per day per user).

| Property | Type | Example |
|---|---|---|
| `current_streak` | `int` | `7` |
| `longest_streak` | `int` | `14` |
| `streak_action` | `string` | `incremented` \| `maintained` \| `reset` \| `frozen` |
| `streak_freeze_used` | `boolean` | `false` |
| `consecutive_missed_days` | `int` | `0` |

**Used for:** Streak length (KPI), streak distribution, freeze usage.

#### `streak_milestone_reached`

**Trigger:** User reaches a streak milestone (3, 7, 14, 21, 30, 60, 90, 365 days).

| Property | Type | Example |
|---|---|---|
| `streak_length` | `int` | `7` |
| `milestone` | `string` | `7_day` |
| `badge_awarded` | `string` | `weekly_warrior` |

**Used for:** Streak milestone rate, retention proxy, gamification engagement.

#### `streak_broken`

**Trigger:** User misses a day and loses their streak (no freeze available).

| Property | Type | Example |
|---|---|---|
| `previous_streak` | `int` | `14` |
| `missed_days_count` | `int` | `1` |
| `days_since_last_activity` | `int` | `2` |

**Used for:** Streak break rate, churn leading indicator.

### 2.9 Gamification Events

#### `xp_earned`

**Trigger:** User earns XP from any action (task, streak, feedback, achievement).

| Property | Type | Example |
|---|---|---|
| `amount` | `int` | `15` |
| `source` | `string` | `task_completed` \| `streak_milestone` \| `feedback_submitted` \| `achievement_unlocked` |
| `source_id` | `uuid` | `...` |
| `total_xp` | `int` | `1240` | (running total) |
| `level` | `int` | `4` |
| `daily_xp_earned` | `int` | `120` | (today's XP so far) |
| `daily_xp_cap` | `int` | `300` | (free plan cap) |

**Used for:** XP velocity, level progression, daily engagement cap utilization.

#### `achievement_unlocked`

**Trigger:** User earns a new achievement/badge.

| Property | Type | Example |
|---|---|---|
| `achievement_id` | `uuid` | `...` |
| `achievement_key` | `string` | `first_essay` \| `weekly_warrior` \| `vocab_master` |
| `category` | `string` | `streak` \| `task` \| `feedback` \| `milestone` \| `social` |
| `xp_bonus` | `int` | `50` |

**Used for:** Achievement unlock rate, gamification engagement.

#### `league_promoted`

**Trigger:** User moves up to a higher league at weekly reset.

| Property | Type | Example |
|---|---|---|
| `previous_league` | `string` | `bronze` |
| `new_league` | `string` | `silver` |
| `rank_in_league` | `int` | `3` |
| `total_members` | `int` | `50` |
| `xp_earned_this_week` | `int` | `850` |

**Used for:** League progression, competitive engagement.

### 2.10 Mock Test Events

#### `mock_test_started`

**Trigger:** User begins a scheduled mock test.

| Property | Type | Example |
|---|---|---|
| `mock_test_id` | `uuid` | `...` |
| `mock_number` | `int` | `2` | (1st, 2nd, 3rd mock) |
| `test_type` | `string` | `full_mock` \| `section_mock` |
| `sections` | `string[]` | `[listening, reading, writing, speaking]` |

**Used for:** Mock test start rate, schedule adherence.

#### `mock_section_completed`

**Trigger:** User completes one section of a mock test.

| Property | Type | Example |
|---|---|---|
| `mock_test_id` | `uuid` | `...` |
| `section` | `string` | `listening` \| `reading` \| `writing` \| `speaking` |
| `time_spent_seconds` | `int` | `1800` |
| `answers_count` | `int` | `40` | (listening/reading) |

**Used for:** Section completion rate, time per section.

#### `mock_test_completed`

**Trigger:** User submits all sections of the mock test.

| Property | Type | Example |
|---|---|---|
| `mock_test_id` | `uuid` | `...` |
| `mock_number` | `int` | `2` |
| `overall_band` | `numeric` | `7.0` |
| `section_scores` | `json` | `{writing: 6.5, speaking: 7.0, reading: 6.5, listening: 7.5}` |
| `total_duration_seconds` | `int` | `9900` |
| `was_auto_submitted` | `boolean` | `false` |
| `band_change_from_previous` | `numeric` | `+0.5` | (vs previous mock) |

**Used for:** Mock test completion rate, band improvement, exam readiness.

### 2.11 Exam Success Events

#### `exam_result_entered`

**Trigger:** User enters their official IELTS exam result.

| Property | Type | Example |
|---|---|---|
| `overall_band` | `numeric` | `7.5` |
| `listening_band` | `numeric` | `8.0` |
| `reading_band` | `numeric` | `7.5` |
| `writing_band` | `numeric` | `7.0` |
| `speaking_band` | `numeric` | `7.5` |
| `exam_date` | `date` | `2025-06-15` |
| `module` | `string` | `academic` |
| `target_band` | `numeric` | `7.5` |
| `target_met` | `boolean` | `true` |
| `band_gap_closed` | `numeric` | `1.0` | (= overall - diagnostic_band) |
| `predicted_band_before_exam` | `numeric` | `7.5` | (last prediction before exam) |
| `prediction_accuracy` | `string` | `exact_match` \| `within_0.5` \| `off_by_1` \| `off_by_more` |

**Used for:** Exam success (KPI), target attainment rate, band prediction accuracy, product outcome validation.

#### `exam_result_shared`

**Trigger:** User shares their exam result on social media or community.

| Property | Type | Example |
|---|---|---|
| `overall_band` | `numeric` | `7.5` |
| `target_met` | `boolean` | `true` |
| `platform` | `string` | `discord` \| `twitter` \| `whatsapp` |

**Used for:** Social proof, referral velocity, viral coefficient.

### 2.12 Feedback & Engagement Events

#### `feedback_submitted`

**Trigger:** User submits any feedback (rating, bug, idea, AI rating, plan rating).

| Property | Type | Example |
|---|---|---|
| `feedback_type` | `string` | `feature_rating` \| `bug_report` \| `feature_request` \| `ai_feedback` \| `plan_feedback` |
| `feedback_id` | `uuid` | `...` |
| `rating` | `int` | `4` | (if applicable) |
| `xp_awarded` | `int` | `5` |

**Used for:** Feedback submission rate, engagement quality.

#### `notification_clicked`

**Trigger:** User clicks on a notification (in-app or push).

| Property | Type | Example |
|---|---|---|
| `notification_id` | `uuid` | `...` |
| `notification_type` | `string` | `reminder` \| `ai_feedback` \| `streak_at_risk` \| `achievement` \| `feedback_status` |
| `source` | `string` | `in_app` \| `push` \| `email` |
| `target_page` | `string` | `/writing` |

**Used for:** Notification CTR, engagement effectiveness.

---

## 3. Session & Identity Tracking

### 3.1 Session Definition

| Property | Value |
|---|---|
| Session start | `session_started` event (page load) |
| Session end | 30 minutes of inactivity, tab close, or logout |
| Session timeout | 30 minutes (configurable) |
| Session ID | UUID generated on app load, stored in memory/localStorage |
| Cross-tab | Same session ID across tabs within 5 minutes (browser storage) |

### 3.2 Identity Resolution

| Stage | ID | Events |
|---|---|---|
| Pre-auth | `anonymous_id` (UUID, stored in localStorage) | `page_viewed`, `session_started` |
| Auth | `user_id` (from Supabase session) | All events |
| Post-auth merge | Backend links `anonymous_id` → `user_id` | Backend identity stitch job |

### 3.3 Identity Linkage (Backend Job)

```
PROCEDURE LinkAnonymousToUser(anonymous_id, user_id):
    UPDATE analytics_events
    SET user_id = user_id, anonymous_id = NULL
    WHERE anonymous_id = anonymous_id AND user_id IS NULL
```

---

## 4. Retention & Cohort Analysis

### 4.1 Retention Definitions

| Metric | Definition | Formula |
|---|---|---|
| **Day 1 Retention** | Users who return within 1 day of signup | `users_active_on_day_1 / users_in_cohort` |
| **Day 7 Retention** | Users who return within 7 days of signup | `users_active_on_day_7 / users_in_cohort` |
| **Day 30 Retention** | Users who return within 30 days of signup | `users_active_on_day_30 / users_in_cohort` |
| **Weekly Resurrection** | Users who were inactive for ≥ 7 days and returned | `users_who_returned_after_7d_break / users_at_risk` |
| **Monthly Churn** | Users inactive for 30+ days | `users_inactive_30d / total_users_at_start_of_month` |

### 4.2 Activation Funnel

The activation funnel tracks the key milestones from signup to "aha moment":

| Step | Event | Target Conversion |
|---|---|---|
| 1. Signup | `auth_signup` | 100% |
| 2. Onboarding Start | `page_viewed` → `/onboarding` | ≥ 80% |
| 3. Onboarding Complete | `onboarding_completed` | ≥ 90% of step 2 |
| 4. Diagnostic Start | `diagnostic_started` (first section) | ≥ 70% of step 3 |
| 5. Diagnostic Complete | `diagnostic_completed` | ≥ 80% of step 4 |
| 6. Roadmap Generated | `roadmap_generated` | ≥ 95% of step 5 |
| 7. First Task Started | `task_started` (first task) | ≥ 70% of step 6 |
| 8. First Task Completed | `task_completed` (first task) | ≥ 80% of step 7 |
| 9. Day 7 Active | See retention | ≥ 30% of step 1 |

### 4.3 Cohort Analysis Dimensions

| Dimension | Values | Use Case |
|---|---|---|
| Signup week | `2025-W18`, `2025-W19`, ... | Track retention improvements over time |
| Signup method | `email`, `google`, `magic_link` | Channel quality comparison |
| Country | `IN`, `PK`, `BD`, `US`, `GB`, ... | Regional engagement differences |
| Module | `academic`, `general` | Module-specific activation |
| Target band | `5.0–5.5`, `6.0–6.5`, `7.0–7.5`, `8.0+` | Goal-based retention |
| Plan | `free`, `pro`, `ultimate` | Plan retention comparison |
| Diagnostic band | `0.0–4.5`, `5.0–5.5`, `6.0–6.5`, `7.0+` | Skill-level retention |

---

## 5. KPI Dashboard Definitions

### 5.1 Executive Dashboard (Daily)

| KPI | Definition | Segment | Refresh |
|---|---|---|---|
| **New Registrations** | Count of `auth_signup` events (last 24h) | Total, by channel | Real-time |
| **DAU** | Unique `user_id` with ≥ 1 `session_started` (last 24h) | Total, by plan, by country | Real-time |
| **WAU** | Unique users with ≥ 1 session in last 7 days | Total | Daily |
| **MAU** | Unique users with ≥ 1 session in last 30 days | Total, by plan | Daily |
| **DAU/MAU** | DAU / MAU (stickiness) | Total | Daily |
| **Avg Session Duration** | AVG(`session_ended.duration_seconds`) / 60 | Total, by plan | Daily |
| **Tasks Completed** | Count of `task_completed` events (last 24h) | Total, by skill | Real-time |
| **Study Minutes** | SUM(`task_completed.duration_minutes`) (last 24h) | Total, per user avg | Real-time |
| **Videos Watched** | Count of `video_watched` with `completed = true` (last 24h) | Total, by provider | Daily |
| **Resource Clicks** | Count of `resource_clicked` events (last 24h) | Total, by source | Real-time |
| **Streak Distribution** | % of active users with streak = 0, 1–3, 4–7, 8–14, 15–30, 30+ | Active users | Daily |
| **Avg Streak Length** | AVG(`streak_updated.current_streak`) among active users | Active users | Daily |
| **Roadmap Completion Rate** | % of users with roadmap who reached phase ≥ 3 | Users with roadmap | Weekly |
| **Day 1/7/30 Retention** | Cohort retention (rolling 7d window) | By signup week | Weekly |
| **NPS** | From feedback system (FEEDBACK_SYSTEM.md) | Total | Weekly |

### 5.2 Growth Dashboard (Weekly)

| Metric | Definition |
|---|---|
| Signup-to-activation rate | % of signups who complete diagnostic + first task |
| Viral coefficient (K) | Avg invites sent × invite conversion rate |
| Channel attribution | Registrations by `referrer_source` / `utm_source` |
| Referral conversion rate | % of referral invites that result in signup |
| Churn rate (weekly) | % of users active last week, inactive this week |
| Resurrection rate | % of churned users who return this week |

### 5.3 Learning Outcomes Dashboard (Monthly)

| Metric | Definition |
|---|---|
| Avg band improvement | AVG(current_band - diagnostic_band) among active users |
| Target attainment rate | % of users who entered exam result with `target_met = true` |
| Band prediction accuracy | % of exam results where `prediction_accuracy = exact_match` or `within_0.5` |
| Assessment completion rate | % of started writing/speaking tasks that result in a completed assessment |
| Mock-to-exam correlation | Correlation between last mock band and actual exam band |
| Time-to-target | Avg days from signup to target band attainment |

### 5.4 AI Quality Dashboard (Weekly)

| Metric | Definition | Source |
|---|---|---|
| Avg AI feedback rating | AVG(`ai_feedback.rating`) | FEEDBACK_SYSTEM.md |
| Low-rating rate | % of AI feedback with rating ≤ 2 | FEEDBACK_SYSTEM.md |
| Feedback viewing rate | % of assessments where `assessment_feedback_viewed` fired | Analytics |
| Avg feedback viewing time | AVG(`assessment_feedback_viewed.time_spent_viewing_seconds`) | Analytics |
| Tutor spot-check pass rate | % of low-rated assessments that pass manual tutor review | LAUNCH_STRATEGY.md |

---

## 6. Data Architecture

### 6.1 Event Pipeline

```
USER ACTION (client-side)
        │
        ▼
Client SDK (custom analytics module)
  ├─ Enriches: global properties (user_id, session_id, timestamp, device)
  ├─ Buffers: batches events every 5 seconds (max 50 events per batch)
  └─ Sends: POST /api/v1/analytics/events (async, fire-and-forget)
        │
        ▼
Backend (FastAPI)
  ├─ Validates: required fields, property types, rate limits
  ├─ Enriches: server-side properties (country, user_agent parsing)
  ├─ Deduplicates: idempotency key (event_id = hash of event + timestamp + user_id)
  ├─ Writes to: analytics_events table (append-only) OR Kafka topic
  └─ Returns: 202 Accepted (no blocking)
        │
        ▼
Event Pipeline (async)
  ├─ Option A: Supabase + partitioned `analytics_events` table (MVP)
  │   └─ SQL aggregations (materialized views for KPIs)
  ├─ Option B: Kafka → ClickHouse (scale, 1M+ events/day)
  │   └─ Real-time aggregations + dashboards
  └─ Option C: Third-party (PostHog / Amplitude / Mixpanel)
        │
        ▼
Analytics Dashboards (Metabase / Grafana / PostHog)
  ├─ Executive dashboard (daily refresh)
  ├─ Growth dashboard (weekly refresh)
  ├─ Learning outcomes dashboard (monthly refresh)
  └─ AI quality dashboard (weekly refresh)
```

### 6.2 Database Table (MVP)

```sql
CREATE TABLE analytics_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event           TEXT NOT NULL,
    user_id         UUID,                    -- nullable (pre-auth)
    anonymous_id    UUID,
    session_id      UUID NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    environment     TEXT NOT NULL DEFAULT 'production',
    app_version     TEXT,
    platform        TEXT NOT NULL DEFAULT 'web',
    
    -- Structured properties (JSONB — flexible, indexed where needed)
    properties      JSONB NOT NULL DEFAULT '{}',
    
    -- Server-enriched
    country         TEXT,
    device_type     TEXT,
    ip_address_hash TEXT,                    -- anonymized
    
    -- Deduplication
    event_id_hash   TEXT UNIQUE,             -- SHA256(event + user_id + timestamp)
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_analytics_event ON analytics_events(event, timestamp DESC);
CREATE INDEX idx_analytics_user ON analytics_events(user_id, timestamp DESC);
CREATE INDEX idx_analytics_session ON analytics_events(session_id);
CREATE INDEX idx_analytics_date ON analytics_events(timestamp::date);
CREATE INDEX idx_analytics_properties ON analytics_events USING gin(properties jsonb_path_ops);

-- Partition by month (for scale)
-- CREATE TABLE analytics_events_2025_05 PARTITION OF analytics_events
--     FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
```

### 6.3 Materialized Views (MVP)

```sql
-- DAU (daily refresh)
CREATE MATERIALIZED VIEW mv_dau AS
SELECT
    timestamp::date AS date,
    COUNT(DISTINCT user_id) AS dau
FROM analytics_events
WHERE event = 'session_started' AND user_id IS NOT NULL
GROUP BY 1;

-- Tasks completed (daily refresh)
CREATE MATERIALIZED VIEW mv_tasks_completed AS
SELECT
    timestamp::date AS date,
    properties->>'skill' AS skill,
    COUNT(*) AS count
FROM analytics_events
WHERE event = 'task_completed'
GROUP BY 1, 2;

-- Study minutes (daily refresh)
CREATE MATERIALIZED VIEW mv_study_minutes AS
SELECT
    timestamp::date AS date,
    SUM((properties->>'duration_minutes')::int) AS total_minutes,
    AVG((properties->>'duration_minutes')::int) AS avg_minutes
FROM analytics_events
WHERE event = 'task_completed'
GROUP BY 1;
```

---

## 7. Event Summary Table

| # | Event | KPI | Trigger | Client/Server |
|---|---|---|---|---|
| 1 | `auth_signup` | Registration | Account created | Server |
| 2 | `auth_login` | DAU | User logs in | Server |
| 3 | `auth_logout` | Session duration | User logs out | Client |
| 4 | `onboarding_completed` | Activation | Onboarding done | Server |
| 5 | `session_started` | DAU | Page load | Client |
| 6 | `session_ended` | Session duration | 30min idle / tab close | Client |
| 7 | `page_viewed` | Page popularity | Navigation | Client |
| 8 | `diagnostic_started` | Activation | Begin diagnostic | Server |
| 9 | `diagnostic_section_completed` | Diagnostic funnel | Section done | Server |
| 10 | `diagnostic_completed` | Activation | All sections done | Server |
| 11 | `task_started` | Engagement | Open task | Client |
| 12 | `task_completed` | Tasks completed | Complete task | Server |
| 13 | `task_skipped` | Task difficulty | Skip task | Server |
| 14 | `writing_essay_started` | Writing engagement | Start typing | Client |
| 15 | `writing_essay_submitted` | Writing submissions | Submit essay | Server |
| 16 | `speaking_recording_started` | Speaking engagement | Start recording | Client |
| 17 | `speaking_recording_completed` | Speaking submissions | Stop recording | Server |
| 18 | `assessment_feedback_viewed` | AI quality | View feedback | Client |
| 19 | `resource_clicked` | Resource clicks | Click resource | Client |
| 20 | `video_watched` | Videos watched | Watch ≥ 10s | Client |
| 21 | `video_watch_progress` | Video engagement | Milestone hit | Client |
| 22 | `pdf_opened` | PDF engagement | Open PDF | Client |
| 23 | `resource_bookmarked` | Content value | Bookmark | Server |
| 24 | `resource_completed` | Resource consumption | Mark complete | Server |
| 25 | `roadmap_generated` | Roadmap activation | Generate plan | Server |
| 26 | `roadmap_phase_unlocked` | Roadmap completion | Phase advance | Server |
| 27 | `roadmap_task_rescheduled` | Scheduler health | Auto-reschedule | Server |
| 28 | `roadmap_completed` | Roadmap completion | All phases done | Server |
| 29 | `streak_updated` | Streak length | Daily rollover | Server |
| 30 | `streak_milestone_reached` | Streak milestones | Milestone hit | Server |
| 31 | `streak_broken` | Streak break | Missed day | Server |
| 32 | `xp_earned` | XP velocity | Any XP event | Server |
| 33 | `achievement_unlocked` | Gamification | Earn badge | Server |
| 34 | `league_promoted` | League progression | Weekly reset | Server |
| 35 | `mock_test_started` | Mock engagement | Start mock | Server |
| 36 | `mock_section_completed` | Mock progress | Section done | Server |
| 37 | `mock_test_completed` | Mock completion | Submit mock | Server |
| 38 | `exam_result_entered` | Exam success | Enter result | Server |
| 39 | `exam_result_shared` | Social proof | Share result | Client |
| 40 | `feedback_submitted` | Feedback engagement | Submit feedback | Server |
| 41 | `notification_clicked` | Notification CTR | Click notification | Client |

---

## 8. Edge Cases

| Case | Handling |
|---|---|
| **Duplicate events** | Idempotency key (`event_id_hash` UNIQUE) prevents double-counting |
| **Offline events** | Queue in localStorage; flush on reconnect with `is_offline = true` flag |
| **Pre-auth events** | Use `anonymous_id`; backend identity stitch job links to `user_id` after signup |
| **Event rate limit** | Max 200 events / minute / user (client-side throttling) |
| **Missing properties** | NULL values allowed; analytics queries handle NULLs gracefully |
| **PII in event properties** | Server-side strip: `user_input`, `essay_text`, `audio_url`, `transcript` are never sent as event properties |
| **User deletes account** | Anonymize `user_id` → hash; remove all properties; keep event count for aggregate |
| **Bot / automated traffic** | Rate limits + bot detection (user-agent, session patterns); flag and exclude |
| **Time zone mismatch** | Events stored in UTC; dashboards convert to user's timezone or platform default |
| **Event schema evolution** | New properties added; old properties never removed; deprecated fields marked `_deprecated` |
| **High-volume spike** | Client-side batch (5s window); server-side queue (Kafka backpressure); circuit breaker |
| **Cross-device identity** | Not supported in MVP; use `user_id` only (single device at a time) |

---

## 9. Implementation Notes

1. **Client SDK** — lightweight analytics module (`src/services/analytics.ts`) that wraps all event captures, handles batching, offline queue, and deduplication.
2. **Server endpoint** — `POST /api/v1/analytics/events` (batch: accepts array of events, max 50 per request).
3. **Database** — `analytics_events` table with monthly partitioning once volume exceeds 1M rows/month.
4. **Materialized views** — refresh via pg_cron (Supabase) or Celery beat (daily for DAU, hourly for real-time).
5. **Dashboards** — Metabase (self-hosted) or PostHog (SaaS) connected to the analytics database.
6. **Privacy** — IP anonymization (hash + truncate), no PII in event properties, opt-out mechanism, data retention policy (raw events: 12 months, aggregated: indefinite).
7. **Identity stitch** — Celery job runs every 5 minutes: `UPDATE analytics_events SET user_id = ... WHERE anonymous_id = ... AND user_id IS NULL`.

---

*This document is the complete specification for the User Behavior Analytics system. It is consistent with ARCHITECTURE.md (event pipeline), DATABASE.md (analytics_events table), FEEDBACK_SYSTEM.md (feedback_submitted event), SCHEDULER.md (roadmap_task_rescheduled), GAMIFICATION.md (xp_earned, achievement_unlocked), LAUNCH_STRATEGY.md (activation funnel, retention targets), and USER_JOURNEY.md (all tracked screens and actions).*
