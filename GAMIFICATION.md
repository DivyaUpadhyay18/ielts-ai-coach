# IELTS AI Coach — Duolingo-Inspired Gamification System

**Role:** Chief Product Architect
**Document:** Software Design Specification — Gamification Engine
**Status:** Draft for review & approval

---

## 0. Executive Summary

This document is a **software design specification** for a complete, Duolingo-inspired gamification system for IELTS AI Coach. It specifies the XP engine, level system, three-tier streak system (daily / weekly / monthly), adaptive missed-day logic, 50+ achievements, an 8-tier badge system, daily/weekly/monthly challenges, a multi-currency reward system, a promotion/demotion league system, a Redis-ready leaderboard with anti-cheat, notifications, database tables, API design, and future premium features.

The system's goal is **habit formation through game mechanics** while remaining pedagogically honest: gamification rewards *effort and consistency*, never inflating band scores. The AI Brain (AI_BRAIN.md) treats gamification events as *consistency signals*; the Scheduler (SCHEDULER.md) remains the authority on task placement. Gamification observes and reinforces — it never overrides pedagogy.

```
Action → Reward → Status (level/league/badge) → Motivation → More Action
   ▲                                                              │
   └────────────────────── retention loop ────────────────────────┘
```

---

## 1. XP Engine

### 1.1 XP Values for Every Activity

| Activity | Base XP | Notes |
|---|---|---|
| Writing Task 2 essay submitted | 40 | Deliberate practice |
| Writing Task 1 essay submitted | 30 | |
| Speaking Part 1 response | 15 | |
| Speaking Part 2 long turn | 25 | |
| Speaking Part 3 discussion | 20 | |
| Reading passage completed | 20 | |
| Listening section completed | 20 | |
| Vocabulary set studied | 10 | +1 XP per correct review |
| Grammar drill completed | 10 | +2 XP if 100% |
| Resource consumed (video/article) | 10 | Duration-based: +1/min up to +15 |
| Mock test section completed | 50 | Per section |
| **Full mock test completed** | **200** | Largest single award |
| Diagnostic section completed | 25 | Per section |
| Daily challenge completed | 30–60 | Tier-based |
| Weekly challenge completed | 100–200 | Tier-based |
| Monthly challenge completed | 300–500 | Tier-based |
| First task of the day | +10 | Streak-aligned bonus |
| Lesson on streak-protected day | 15 | Minimum-viable day reward |

### 1.2 XP Calculation Formulas

**Total XP for an activity:**

```
activity_xp = base_xp × difficulty_multiplier × skill_multiplier
              + combo_bonus + perfect_bonus + consistency_bonus
```

Where:
- `difficulty_multiplier`: beginner 1.0 · intermediate 1.1 · advanced 1.25 · exam-level 1.5
- `skill_multiplier`: skills flagged as user's weakest (from AI Brain M6) get 1.2 — **encourages working on gaps**
- `combo_bonus`: see §1.4
- `perfect_bonus`: see §1.5
- `consistency_bonus`: see §1.7

**XP rounding rule:** all XP values are integers (floor after multiplication); no fractional XP ever stored.

### 1.3 Daily XP Cap

| Plan | Daily XP Cap |
|---|---|
| Free | 300 |
| Pro | 500 |

Purpose: prevents grinding low-effort tasks, rewards **variety and depth**, and keeps leaderboards fair. Cap is per calendar day (user-local). Reaching the cap shows a "cap reached" state; bonus XP (challenges, perfect day) may exceed the cap but is marked separately.

### 1.4 Combo Bonuses

Combo = completing tasks **without leaving the study session** (max 2-min gap between activities).

```
combo_count = consecutive activities in one active session
combo_bonus = min(combo_count, 10) × 2     // +2 XP per combo step, capped at +20
combo resets when session ends or after a 2-min idle gap
```

### 1.5 Perfect Day Bonus

| Condition | Bonus |
|---|---|
| Complete **all** of today's scheduled tasks | +50 XP "Perfect Day" |
| Complete all tasks **AND** meet daily study-minute budget | +100 XP "Perfect Day +" |
| Perfect Day on 7 consecutive days | +250 XP "Perfect Week" |

Perfect-day state is computed at rollover from `daily_plans.completed_tasks == total_tasks`.

### 1.6 Mock Test Rewards

| Achievement | XP |
|---|---|
| Complete a full mock | 200 |
| Beat your previous mock band | +50 |
| Mock band ≥ predicted band | +50 |
| Mock band ≥ target band | +100 |
| First mock ever | +100 bonus |

Mocks are the highest-value rewards — they are the strongest learning signal (AI Brain S4).

### 1.7 Consistency Bonus

```
consistency_bonus = min(current_daily_streak, 30) × 1     // +1 XP per active day, capped +30
```
A user on a 30-day streak earns +30 XP on every activity. Rewards the streak without dominating scoring.

### 1.8 XP Ledger

Every XP event appends to an **append-only ledger**:

```
xp_ledger: { id, user_id, amount, type, source_id, metadata, created_at }
```

The ledger is the single source of truth; derived counters (`daily_xp`, `weekly_xp`, `total_xp`) are cached projections. This enables auditing, anti-cheat forensics, and recalculation after a rule change.

---

## 2. Level System

### 2.1 Level Curve

Levels are based on **cumulative lifetime XP**. Each level requires progressively more XP (Duolingo-style gentle curve):

```
level_n_required_xp = 100 × n^1.35        // round to nearest 10

Level 1:    100      Level 6:  1,350     Level 11:  3,690     Level 16:  7,180
Level 2:    320      Level 7:  1,860     Level 12:  4,410     Level 17:  8,140
Level 3:    580      Level 8:  2,430     Level 13:  5,170     Level 18:  9,140
Level 4:    880      Level 9:  3,050     Level 14:  5,970     Level 19: 10,170
Level 5:  1,200      Level 10: 3,710     Level 15:  6,810     Level 20: 11,230
```

### 2.2 Unlockable Rewards

| Level | Reward |
|---|---|
| 1 | Base avatar, default theme |
| 2 | **Streak Freeze** (1 free) |
| 3 | New avatar frame |
| 5 | League access (Bronze) |
| 6 | Gem payout (50) |
| 8 | New theme (Midnight) |
| 10 | Custom username flair |
| 12 | Gem payout (100) |
| 15 | **Streak Repair** token |
| 18 | Special avatar |
| 20 | Legend title unlock eligibility |

### 2.3 Progress Bar Logic

```
level_progress = (current_xp − xp_for_level) / (xp_for_next_level − xp_for_level)
level_up_threshold passed → XP animates into next level, unspent XP carries over (no reset)
```

Client renders the bar from `gamification_state.level_progress` (server-computed, never client-derived).

---

## 3. Streak System

Three independent-but-nested streaks: **Daily**, **Weekly**, **Monthly**.

| Property | Daily Streak | Weekly Streak | Monthly Streak |
|---|---|---|---|
| Unit | calendar day | calendar week (Mon–Sun, user-local) | calendar month |
| Start | first day with ≥1 qualifying activity | first week with ≥3 active days | first month with ≥12 active days |
| Increase | each consecutive active day | each consecutive week meeting threshold | each consecutive month meeting threshold |
| Break | a day with no activity and no freeze/repair | a week with <3 active days | a month with <12 active days |
| Preservation | freeze / repair / vacation / rest-day | rest-week / vacation | vacation month |

### 3.1 Qualifying Activity

```
qualifies_for_streak(activity):
    return activity.minutes >= 10  OR  activity.is_mock  OR  activity.is_resource_completed
```
A 10-minute minimum prevents "1-second check-in" fake streaks (see §13 Anti-Cheat).

### 3.2 Grace Period

- Daily streak: a **24-hour grace** (server timezone-aware) — activity within `day_end + 24h` counts for the previous day if no activity occurred that day. Implementation: streak check runs at rollover + 24h.
- Weekly streak: grace until **Tuesday 00:00** user-local (Monday is the "official" end; a missed Monday can be recovered Tuesday before rollover).
- Monthly streak: grace until the **2nd of next month 00:00** user-local.

### 3.3 Streak Freeze

- **Effect:** one missed day does NOT break the streak; the freeze is consumed.
- **Stacking:** max 5 freezes held.
- **How earned:** level reward (L2), gem purchase (500 gems), daily-challenge reward, milestone reward, premium.
- **Consumption order:** oldest first (FIFO).
- **UI states:** `available` (n), `active` (freeze used today — streak preserved but shows "protected"), `empty`.

### 3.4 Streak Repair

- **Effect:** restores a **recently broken** streak (broken within the last 7 days) to its pre-break value.
- **Cost:** 1 repair token **or** 1,000 gems **or** completion of a "Streak Repair Quest" (§5.4 recovery).
- **Restriction:** max 1 repair per 30 days (prevents permanent safety net).
- **Result:** streak resumes as if unbroken; `streak_repair_used_at` recorded for anti-cheat.

### 3.5 Vacation Mode

- User can schedule a **planned break** (SCHEDULER.md §9.6) of up to 14 days, twice per year.
- During vacation: no tasks scheduled, **all three streaks frozen** (`streak_state.frozen = true`), freeze inventory NOT consumed.
- Streak counter shows "frozen — on vacation 🏖" rather than incrementing.
- Daily activity during vacation does not count toward streak increases (avoids gaming), but does not break it either.

### 3.6 Rest Day Interaction

Planned rest days (SCHEDULER.md §7) are auto-preserved: streak holds, no consumption of freeze. `is_rest_day` is a protected attribute set by the scheduler.

---

## 4. Adaptive Missed-Day Logic

When a user misses a day, the **Scheduler** (authority) + **AI Brain** (recomputation) cooperate. Gamification only *observes* the resulting plan. Algorithms below match SCHEDULER.md §4/§6/§7.

### 4.1 Algorithm — Missed-Day Handling

```
PROCEDURE HandleMissedDay(user_id, missed_date):
    // Step 1: Streak evaluation (gamification observes)
    IF qualifies_for_streak_break(user_id, missed_date):
        IF has_freeze(user):        consume_freeze(user);  state = "protected"
        ELIF in_grace_period():     state = "grace";        // evaluated again at grace end
        ELIF has_repair(user):      state = "repairable"    // not auto-applied
        ELSE:                       break_streak(user)
        update streak tiers (daily/weekly/monthly)

    // Step 2: Unfinished tasks move forward (Scheduler authority)
    FOR task IN GetPendingTasks(missed_date):
        IF task.is_mock_test:
            RescheduleMockTest(user, task)        // mocks never carried forward
        ELSE:
            CarryForwardTask(user, task)          // SCHEDULER.md §4.2

    // Step 3: AI recalculates workload (AI Brain M5 + Scheduler §5)
    RecalculateRemainingHours(user)
    AdjustDailyWorkload(user)                     // ideal_daily, clamp budget
    RecomputeDecisionBundle(user)                 // risk, readiness, hours

    // Step 4: Protect high-value days
    FOR candidate_date IN CarryForwardSlots:
        IF IsProtectedDay(user, candidate_date):   // revision, mock, rest
            SKIP → FindNextAvailableSlot(user, candidate_date)
        ELSE:
            assign task

    // Step 5: Avoid impossible schedules
    overload = GetOverloadFactor(user)            // SCHEDULER.md §8
    IF overload > 1.5:
        MoveLowestPriorityTasks(user, spread_to_next_available)
    IF overload > 1.3 (weekly):
        DropBottom20PercentNonRequired(user)
    IF consecutive_overload_days > 3:
        InsertRecoveryDay(user)
```

### 4.2 Fairness Guarantees

1. **Revision days are never overwritten** by carry-forward (No-Overwrite Rule, SCHEDULER.md §7.3).
2. **Mock tests are never carried forward**; they are rescheduled to a protected slot.
3. **Foundation phase is never compressed below 50%** (SCHEDULER.md §9.2).
4. **Overload prevention runs before any task generation** — sustainability beats intensity.
5. **Streak-saver mode** (after 3 missed days) forces a single 10-minute quick-win task so the user can rebuild the habit without drowning in backlog (SCHEDULER.md §7/§9.4).

---

## 5. Achievements (50+)

Achievement catalog structure: `{ code, category, name, description, tier, unlock_condition (predicate), hidden? }`. Unlock is **event-driven**: an achievement evaluator subscribes to domain events (assessment.completed, task.completed, daily.rollover, etc.) and evaluates predicates.

### 5.1 Learning (8)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A1 | learn_first | First Steps | Complete first task |
| A2 | learn_plan | Roadmap Ready | Generate your first roadmap |
| A3 | learn_diag | Baseline Set | Complete diagnostic |
| A4 | learn_resource | Curious Learner | Consume 10 resources |
| A5 | learn_review | Reflection Pro | Review 10 past assessments |
| A6 | learn_adaptive | Plan Adaptor | Complete tasks across 3 different phases |
| A7 | learn_dive | Deep Diver | Complete a task with 100% focus (session ≥ 45 min) |
| A8 | learn_allround | All-Rounder | Complete a task in every skill in one day |

### 5.2 Consistency (8)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A9 | con_3 | Getting Started | 3-day daily streak |
| A10 | con_7 | Weekly Warrior | 7-day daily streak |
| A11 | con_14 | Fortnight Fire | 14-day daily streak |
| A12 | con_30 | Monthly Master | 30-day daily streak |
| A13 | con_60 | Two-Month Titan | 60-day daily streak |
| A14 | con_100 | Century Club | 100-day daily streak |
| A15 | con_week4 | Weekly Streak 4 | 4 consecutive qualifying weeks |
| A16 | con_month3 | Monthly Streak 3 | 3 consecutive qualifying months |

### 5.3 Reading (5)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A17 | rd_1 | First Read | Complete 1 reading passage |
| A18 | rd_10 | Bookworm | Complete 10 reading passages |
| A19 | rd_50 | Speed Reader | Complete 50 reading passages |
| A20 | rd_70 | Band 7 Reader | Score ≥ 7.0 on a reading assessment |
| A21 | rd_perfect | Perfect Scan | Score 9.0 on a reading assessment |

### 5.4 Listening (5)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A22 | ls_1 | First Listen | Complete 1 listening section |
| A23 | ls_10 | Attentive Ear | Complete 10 listening sections |
| A24 | ls_50 | Audio Ace | Complete 50 listening sections |
| A25 | ls_70 | Band 7 Listener | Score ≥ 7.0 on a listening assessment |
| A26 | ls_perfect | Perfect Ear | Score 9.0 on a listening assessment |

### 5.5 Writing (6)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A27 | wr_1 | First Draft | Submit 1 essay |
| A28 | wr_10 | Ten Essays | Submit 10 essays |
| A29 | wr_50 | Fifty Essays | Submit 50 essays |
| A30 | wr_70 | Band 7 Writer | Score ≥ 7.0 on a writing assessment |
| A31 | wr_85 | Band 8.5 Writer | Score ≥ 8.5 on a writing assessment |
| A32 | wr_t1t2 | Both Tasks | Complete a Task 1 and Task 2 in the same day |

### 5.6 Speaking (6)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A33 | sp_1 | First Response | Submit 1 speaking response |
| A34 | sp_10 | Ten Responses | Submit 10 speaking responses |
| A35 | sp_50 | Fifty Responses | Submit 50 speaking responses |
| A36 | sp_70 | Band 7 Speaker | Score ≥ 7.0 on a speaking assessment |
| A37 | sp_85 | Band 8.5 Speaker | Score ≥ 8.5 on a speaking assessment |
| A38 | sp_allparts | Full Interview | Complete all 3 speaking parts in one session |

### 5.7 Vocabulary (5)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A39 | vocab_10 | Word Collector | Add 10 vocabulary words to personal bank |
| A40 | vocab_50 | Lexicon Builder | Add 50 vocabulary words to personal bank |
| A41 | vocab_200 | Walking Dictionary | Add 200 vocabulary words to personal bank |
| A42 | vocab_review50 | Consistent Reviewer | Review 50 vocabulary cards |
| A43 | vocab_master | Mastered 20 | Master 20 words (proficiency = "mastered") |

### 5.8 Mock Tests (5)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A44 | mock_1 | First Mock | Complete 1 full mock test |
| A45 | mock_3 | Mock Marathoner | Complete 3 full mock tests |
| A46 | mock_10 | Mock Veteran | Complete 10 full mock tests |
| A47 | mock_improve | Rising Score | Improve mock score by ≥ 0.5 band from first mock |
| A48 | mock_target | Target Breaker | Achieve target band or higher on a mock test |

### 5.9 Band Prediction (4)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A49 | pred_first | First Prediction | Receive first AI band prediction |
| A50 | pred_confidence | High Confidence | Achieve prediction confidence ≥ 0.8 |
| A51 | pred_accuracy | Prediction Aligned | Actual mock band equals predicted band (within ±0.5) |
| A52 | pred_beat | Beat the Prediction | Score 0.5+ band higher than predicted on a mock |

### 5.10 Milestones (8)

| # | Code | Name | Unlock Condition |
|---|---|---|---|
| A53 | mile_50k | 50K XP | Accumulate 50,000 lifetime XP |
| A54 | mile_100k | 100K XP | Accumulate 100,000 lifetime XP |
| A55 | mile_100h | 100 Hours | Log 100 total study hours |
| A56 | mile_500h | 500 Hours | Log 500 total study hours |
| A57 | mile_500t | 500 Tasks | Complete 500 tasks |
| A58 | mile_1000t | 1000 Tasks | Complete 1,000 tasks |
| A59 | mile_lv10 | Level 10 | Reach level 10 |
| A60 | mile_lv20 | Level 20 | Reach level 20 |

---

## 6. Badges

### 6.1 Badge Tiers

Badges are **meta-achievements** — cosmetic tiers applied to skill categories. A user earns a badge tier for a skill by completing a set of related achievements.

| Tier | Color | Unlock Condition | XP Reward |
|---|---|---|---|
| **Bronze** | 🥉 | Complete 2 achievements in the category | 50 |
| **Silver** | 🥈 | Complete 4 achievements OR any 1 with score ≥ 7.0 | 100 |
| **Gold** | 🥇 | Complete 6 achievements OR any 1 with score ≥ 8.0 | 200 |
| **Platinum** | 💎 | Complete all achievements in category + score ≥ 8.5 | 350 |
| **Diamond** | 💠 | Complete all achievements + 100+ tasks in category + average ≥ 7.5 | 500 |
| **Master** | 👑 | Category achievements + 500+ tasks + average ≥ 8.0 + maintain 30-day streak | 750 |
| **Legend** | ⭐ | Master tier + top 1% of users in category + 90-day streak | 1,000 |

### 6.2 Badge Categories

| Category | Badge Name | Assessed By |
|---|---|---|
| Writing | The Author | A30–A32 + score thresholds |
| Speaking | The Orator | A36–A38 + score thresholds |
| Reading | The Scholar | A20–A21 + score thresholds |
| Listening | The Listener | A25–A26 + score thresholds |
| Vocabulary | The Lexicographer | A42–A43 + proficiency thresholds |
| Consistency | The Iron Will | A9–A16 + streak thresholds |
| Mock Tests | The Strategist | A44–A48 + improvement thresholds |
| Milestones | The Champion | A53–A60 + cumulative thresholds |

### 6.3 Badge Display

- Badges appear on the **profile page** as a showcase grid (max 8 visible).
- User can select a **"featured badge"** displayed on the dashboard.
- Each badge shows tier icon, category name, and progress to next tier.
- **Secret badges** exist (e.g., "Complete a mock at 3 AM" → "Night Owl"). Hidden until unlocked.

---

## 7. Daily Challenges

Three challenges served per day (user-local), refreshed at midnight. Each has a tier (Easy / Medium / Hard) with scaling XP rewards.

### 7.1 Challenge Pool (Examples)

| # | Challenge | Objective | Tier | XP |
|---|---|---|---|---|
| DC1 | Quick Study | Complete 1 task | Easy | 30 |
| DC2 | Half Hour | Study for 30+ minutes | Easy | 40 |
| DC3 | Task Master | Complete 3 tasks | Medium | 50 |
| DC4 | Full Hour | Study for 60+ minutes | Medium | 60 |
| DC5 | Skill Focus | Complete tasks in one skill only | Medium | 60 |
| DC6 | Variety Hour | Complete tasks in 3 different skills | Hard | 80 |
| DC7 | Perfect Score | Score ≥ 7.0 on any assessment | Hard | 80 |
| DC8 | Mock Section | Complete 1 mock test section | Hard | 90 |
| DC9 | Essay Day | Submit 2 essays | Hard | 90 |
| DC10 | Streak Saver | Complete any task (streak-protection day) | Easy | 30 |
| DC11 | No Distractions | Complete a 45+ minute focused session | Medium | 70 |
| DC12 | Flashcard Frenzy | Review 20 vocabulary cards | Easy | 35 |
| DC13 | Grammar Guru | Complete 3 grammar exercises | Medium | 55 |
| DC14 | Listen Up | Complete 2 listening sections | Hard | 85 |
| DC15 | Perfect Day | Complete all today's scheduled tasks | Hard | 100 |

### 7.2 Challenge Selection Algorithm

```
PROCEDURE SelectDailyChallenges(user):
    // 1. Always include 1 Easy challenge (guaranteed achievable)
    // 2. Include 1 challenge targeting user's weakest skill (AI Brain M6)
    // 3. Include 1 challenge from the "stretch" pool (Medium/Hard)
    // 4. Never repeat the same challenge within 7 days
    // 5. Adapt difficulty: if user completed all 3 for 5+ consecutive days, increase pool difficulty
```

### 7.3 Challenge Completion

- Progress is tracked in `challenge_progress` table with `target_value`, `current_value`, `completed` flag.
- XP is awarded on completion (not on assignment).
- All 3 completed → bonus "Triple Crown" +50 XP.

---

## 8. Weekly Challenges

One weekly challenge assigned every Monday, expires Sunday night. Harder, longer-term goals.

### 8.1 Weekly Challenge Pool (Examples)

| # | Challenge | Objective | XP |
|---|---|---|---|
| WC1 | 5-Day Streak | Maintain activity for 5 of 7 days | 100 |
| WC2 | Essay Marathon | Submit 5 essays | 150 |
| WC3 | Speaking Week | Complete 10 speaking responses | 150 |
| WC4 | Mock Prep | Complete 2 full mock tests | 200 |
| WC5 | Resource Explorer | Consume 5 resources | 100 |
| WC6 | Vocabulary Builder | Add 20 new words + review 50 | 150 |
| WC7 | Skill Focus Week | Complete 80% of tasks in weakest skill | 175 |
| WC8 | Band Target | Score ≥ 7.0 on 3 assessments | 200 |
| WC9 | Perfect Week | Complete all daily tasks for 7 consecutive days | 250 |
| WC10 | Mock Improvement | Improve mock score by ≥ 0.5 vs previous week | 200 |
| WC11 | Social (future) | Complete a challenge with a study buddy | 150 |
| WC12 | No Overdue Tasks | Clear all overdue tasks by week end | 100 |

### 8.2 Weekly Challenge Selection

- AI Brain selects challenge based on: current skill gaps, phase, recent completion rate, and streak status.
- Streak-at-risk users get "5-Day Streak" (WC1).
- Users in Mock Phase get "Mock Prep" (WC4) or "Mock Improvement" (WC10).

---

## 9. Monthly Challenges

One monthly challenge, assigned on the 1st, expires at month end. Major goals that drive significant progress.

### 9.1 Monthly Challenge Pool (Examples)

| # | Challenge | Objective | XP |
|---|---|---|---|
| MC1 | 20-Day Streak | Maintain activity for 20+ days this month | 300 |
| MC2 | Band Climb | Improve predicted band by ≥ 0.5 this month | 400 |
| MC3 | Mock Month | Complete 4 full mock tests | 500 |
| MC4 | 100 Tasks | Complete 100 tasks this month | 350 |
| MC5 | 30 Hours | Study 30+ hours this month | 350 |
| MC6 | Skill Transformation | Improve weakest skill by ≥ 1.0 band | 500 |
| MC7 | All-Rounder | Complete tasks in all 6 skills every week | 450 |
| MC8 | Perfect Month | Complete all daily tasks every day this month | 600 |
| MC9 | Vocabulary Surge | Add 100 new words + master 50 | 400 |
| MC10 | Exam Simulation | Complete 4 full mocks + 8 section mocks | 500 |

### 9.2 Monthly Challenge Selection

- Automatic based on AI Brain's predicted trajectory: if risk > 50, offer "Band Climb" (MC2) or "Skill Transformation" (MC6).
- If predicted band is on track, offer "Mock Month" (MC3) or "Perfect Month" (MC8) for stretch goals.

---

## 10. Reward System

### 10.1 Reward Currencies

| Currency | Symbol | Earned Via | Spent On |
|---|---|---|---|
| **XP** | XP | All activities, challenges, bonuses | Level progression, leaderboard ranking |
| **Gems** | 💎 | Level ups, achievements, daily challenges, streaks | Streak freeze, streak repair, cosmetics, themes |
| **Coins** | 🪙 | Milestones, mock completion, weekly challenges | Avatar items, title unlocks, boosters |

### 10.2 Reward Catalog

| Item | Currency | Cost | Notes |
|---|---|---|---|
| Streak Freeze x1 | Gems | 500 | Max 5 held |
| Streak Repair | Gems | 1,000 | Max 1 per 30 days |
| XP Boost (24h, 2x) | Gems | 300 | Doubles all XP earned for 24 hours |
| Avatar Frame — Bronze | Coins | 200 | Cosmetic only |
| Avatar Frame — Silver | Coins | 500 | |
| Avatar Frame — Gold | Coins | 1,000 | |
| Theme — Midnight | Gems | 800 | Dark dashboard theme |
| Theme — Forest | Gems | 1,200 | |
| Title — "Scholar" | Coins | 2,000 | Displays next to username |
| Title — "Band Champion" | Coins | 5,000 | |
| Title — "Legend" | Coins | 10,000 | Only if level 20+ |
| Username Flair | Coins | 500 | Colored name highlight |
| Pro Trial (7 days) | Gems | 5,000 | Future premium feature |
| Exclusive Badge — "Lunar" | Gems | 3,000 | Seasonal limited edition |

### 10.3 Redemption Flow

```
1. User browses reward catalog → GET /api/v1/gamification/rewards
2. User selects item → POST /api/v1/gamification/redeem { item_code }
3. Server validates: sufficient currency × item not already owned × eligibility
4. Server deducts currency, grants item, logs transaction
5. Response: updated balance + item state
```

---

## 11. League System

### 11.1 League Tiers

| Tier | Users per Group | Promotion | Demotion | Reward |
|---|---|---|---|---|
| **Bronze** | 15 | Top 5 → Silver | N/A (bottom of ladder) | 50 XP |
| **Silver** | 15 | Top 5 → Gold | Bottom 5 → Bronze | 100 XP |
| **Gold** | 15 | Top 5 → Platinum | Bottom 5 → Silver | 150 XP |
| **Platinum** | 15 | Top 5 → Diamond | Bottom 5 → Gold | 200 XP |
| **Diamond** | 15 | Top 5 → Master | Bottom 5 → Platinum | 300 XP |
| **Master** | 10 | Top 3 → Legend | Bottom 4 → Diamond | 500 XP |
| **Legend** | 10 | Top 1 stays; bottom 3 → Master | Bottom 3 → Master | 1,000 XP + exclusive badge |

### 11.2 Promotion & Demotion Rules

| Rule | Detail |
|---|---|
| **Season** | Weekly (Mon–Sun, user-local) |
| **Scoring** | XP earned **during the week only** (capped at daily cap × 7) |
| **Promotion** | Top N users at season end move up one tier |
| **Demotion** | Bottom N users at season end move down one tier |
| **New user** | Enters Bronze; if returning after > 30 days, placed in Bronze (resets league history) |
| **Inactivity** | 0 XP for the week → auto-demotion (one tier) regardless of group rank |
| **Ties** | Total XP → then streak → then total tasks → then earlier join time |
| **League freeze** | Premium feature: skip one week without demotion |

### 11.3 Grouping Strategy

```
PROCEDURE AssignLeagueGroups():
    // 1. Collect all users in the same tier
    // 2. Sort by league score (XP this season) descending
    // 3. Bucket: group size = N (per tier), snake-draft to balance
    //    e.g., 1→Group A, 2→Group B, 3→Group C, 4→Group C, 5→Group B, 6→Group A
    // 4. Assign each user to a group
    // 5. Groups are static for the week
```

### 11.4 League UI States

| State | Display |
|---|---|
| **Active** | Leaderboard of group members, your rank highlighted |
| **Promotion zone** | Green highlight on top N positions |
| **Demotion zone** | Red highlight on bottom N positions |
| **Safe zone** | Middle positions, neutral |
| **Season end** | Countdown timer, final results, reward animation |
| **New season** | Fresh board, "New season — climb the ranks!" |

---

## 12. Leaderboard (Redis-Ready Architecture)

### 12.1 Data Model

The leaderboard uses **Redis Sorted Sets** for real-time ranking and weekly resets.

```
Redis Keys:
  leaderboard:global:daily                    → Sorted Set (user_id, XP_today)
  leaderboard:global:weekly                   → Sorted Set (user_id, XP_this_week)
  leaderboard:global:monthly                  → Sorted Set (user_id, XP_this_month)
  leaderboard:global:alltime                  → Sorted Set (user_id, total_XP)
  leaderboard:league:{tier}:{group_id}:weekly → Sorted Set (user_id, XP_this_week)
  leaderboard:league:{tier}:{group_id}:daily  → Sorted Set (user_id, XP_today)
```

### 12.2 Ranking Operations

```python
# Award XP (called by XP engine on every activity)
ZINCRBY leaderboard:global:daily user_id XP_amount
ZINCRBY leaderboard:global:weekly user_id XP_amount
ZINCRBY leaderboard:global:monthly user_id XP_amount
ZINCRBY leaderboard:global:alltime user_id XP_amount
ZINCRBY leaderboard:league:{tier}:{group}:weekly user_id XP_amount

# Get user rank
ZREVRANK leaderboard:global:daily user_id              # 0-based rank
ZREVRANK leaderboard:global:weekly user_id
ZREVRANK leaderboard:league:{tier}:{group}:weekly user_id

# Get leaderboard slice
ZREVRANGE leaderboard:global:daily 0 9 WITHSCORES      # Top 10 today
ZREVRANGE leaderboard:league:{tier}:{group}:weekly 0 14 WITHSCORES  # Full group

# Get user's score
ZSCORE leaderboard:global:weekly user_id
```

### 12.3 Reset Strategy

| Key | Reset Cadence | Method |
|---|---|---|
| `daily` | Every 24h (user-local midnight) | `DEL key` at rollover; recompute from `xp_ledger` for timezone-aware users |
| `weekly` | Every Monday 00:00 UTC | `DEL key`; weekly league promotion/demotion computed before delete |
| `monthly` | 1st of month 00:00 UTC | `DEL key`; monthly challenge completion finalized before delete |
| `alltime` | Never | Append-only; `ZINCRBY` only |
| `league:weekly` | Every Monday 00:00 UTC | `DEL key` after promotions/demotions applied; new groups assigned |

### 12.4 Leaderboard Caching Layer

| Query | Cache | TTL |
|---|---|---|
| Top 10 daily | Redis `leaderboard:global:daily` | Realtime (sorted set) |
| Top 10 weekly | Redis `leaderboard:global:weekly` | Realtime |
| User rank (all) | Redis `leaderboard:global:alltime` | Realtime |
| League group table | Redis `leaderboard:league:{tier}:{group}:weekly` | Realtime |
| Historical leaderboard | Postgres `leaderboard_snapshots` table | Persistent |

### 12.5 Anti-Cheat on Leaderboard

| Measure | Implementation |
|---|---|
| **XP cap enforced** | Daily cap prevents grinders from dominating |
| **Rate limiting** | Max 10 XP events per minute per user |
| **Pattern detection** | Sudden XP spike (> 3× daily average) triggers review flag |
| **Session validation** | XP only awarded during active study sessions (tracked by `study_sessions`) |
| **Manual flagging** | Admin can freeze a user's leaderboard position pending review |

---

## 13. Anti-Cheat

### 13.1 Prevent Fake Streaks

| Threat | Mitigation |
|---|---|
| 1-second activity to "check in" | Minimum 10 minutes of activity per day to qualify for streak |
| Auto-refresh scripts | Session validation: streak only counts if activity is tied to a server-verified `study_sessions` record |
| Timezone hopping | Streak is computed per user-local timezone (set at onboarding); changing TZ requires cooldown |
| Multiple devices | Streak is account-level, not device-level; server-authoritative counter |

### 13.2 Prevent Fake XP

| Threat | Mitigation |
|---|---|
| Submit empty essays | Minimum word count (50 words) for writing XP |
| Submit blank recordings | Minimum duration (30 seconds) for speaking XP |
| Rapid task completion | Time-spent validation: XP only awarded if task was open for ≥ 60% of estimated duration |
| Duplicate resource completion | XP per resource is one-time; subsequent completions yield 0 XP |
| Bot submissions | Rate limiting, CAPTCHA on signup, device fingerprinting on suspicious patterns |

### 13.3 Prevent Task Spam

| Threat | Mitigation |
|---|---|
| Submit same essay 10 times | Deduplication by text hash (SHA-256 of content) — second identical submission within 24h yields 0 XP |
| Rapid skill switching | Cooldown: same skill can't generate XP more than once per 2 minutes |
| Create fake study sessions | Session must be tied to a real task or resource; orphan sessions are ignored |

### 13.4 Prevent Duplicate Completion

| Threat | Mitigation |
|---|---|
| Complete same task twice | `task_completions` has `UNIQUE(task_id, user_id)` constraint |
| Re-submit after completion | Task status prevents re-submission; client enforces + server validates |
| Multiple browser tabs | Server-side idempotency key per task-submission event |

### 13.5 Audit Trail

All XP and streak events are logged in the `xp_ledger` and `streak_history` tables. Anomaly detection runs nightly:

```sql
-- Detect users with XP > 3σ above their 30-day average
SELECT user_id, SUM(amount) as daily_xp
FROM xp_ledger
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY user_id
HAVING SUM(amount) > (
    SELECT AVG(daily_xp) + 3 * STDDEV(daily_xp)
    FROM user_daily_xp
    WHERE user_id = xp_ledger.user_id
    AND date >= NOW() - INTERVAL '30 days'
);
```

---

## 14. Notifications

### 14.1 Notification Types & Triggers

| Type | Trigger | Timing | Channel |
|---|---|---|---|
| **Morning Reminder** | Daily at user's preferred time (default 08:00) | Scheduled | Push, email (opt-in) |
| **Streak Reminder** | No activity by 18:00 user-local | Conditional | Push, in-app |
| **Streak at Risk** | 2 consecutive missed days | Evening day 2 | Push, in-app, email |
| **Streak Broken** | 3rd consecutive missed day (no freeze) | After rollover | Push, in-app |
| **Streak Restored** | Streak repair applied | On repair | In-app |
| **Challenge Reminder** | 1 hour before daily reset with incomplete challenges | Conditional | Push, in-app |
| **League Promotion** | Promoted to higher tier | Monday after season end | Push, in-app |
| **League Demotion** | Demoted to lower tier | Monday after season end | In-app (soft notification) |
| **Achievement Unlocked** | Achievement predicate evaluated true | On event | In-app, push (optional) |
| **Badge Earned** | Badge tier threshold crossed | On event | In-app (celebration modal) |
| **Level Up** | Cumulative XP crosses next level threshold | On event | In-app (animation) |
| **Perfect Day** | All tasks completed | After last task | In-app |
| **XP Milestone** | 10K, 25K, 50K, 100K XP | On event | In-app |

### 14.2 Notification Content

| Notification | Title | Body |
|---|---|---|
| Morning Reminder | "Good morning, {name}! ☀️" | "You have {N} tasks today. Let's start with {first_task_title}." |
| Streak Reminder | "Don't lose your streak! 🔥" | "You haven't studied yet today. {N} minutes is all it takes." |
| Streak at Risk | "Your {N}-day streak is at risk ⚠️" | "Complete one task today to keep it alive!" |
| Streak Broken | "Streak broken 💔" | "Your {N}-day streak was broken. But every day is a new start!" |
| Challenge Reminder | "Challenges closing soon ⏰" | "You have {N} incomplete daily challenges. Just {X} more to finish them." |
| League Promotion | "You're moving up! 🏆" | "Congratulations! You've been promoted to {tier}. Your new league starts Monday." |
| Achievement Unlocked | "Achievement unlocked! 🎉" | "You earned: {achievement_name}. {achievement_description}" |
| Level Up | "Level {N} reached! ⬆️" | "You're now level {N}. Check out your new rewards!" |

### 14.3 Notification Delivery Rules

- **Quiet hours:** 22:00–08:00 user-local: no push notifications, only in-app.
- **Frequency cap:** max 5 push notifications per day per user.
- **Opt-in/out:** each notification type is individually toggleable in Settings.
- **Cooldown:** same notification type not repeated within 24 hours.

---

## 15. Database Design

### 15.1 New Tables

#### `gamification_state`
Per-user aggregate gamification state (cached projection, rebuilt from ledger).

| Column | Type | Notes |
|---|---|---|
| user_id | UUID PK | FK → users.id |
| total_xp | INTEGER | Lifetime XP |
| level | SMALLINT | Current level |
| level_progress | NUMERIC(5,2) | 0.00–1.00 progress to next level |
| gems | INTEGER | Current gem balance |
| coins | INTEGER | Current coin balance |
| league_tier | TEXT | bronze | silver | gold | platinum | diamond | master | legend |
| league_group_id | UUID | Current league group |
| featured_badge | TEXT | Badge code for profile showcase |
| preferred_theme | TEXT | Theme code |
| preferred_title | TEXT | Title code |
| updated_at | TIMESTAMPTZ | Auto-updated |

#### `xp_ledger`
Append-only log of all XP events.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK | |
| amount | INTEGER | Positive for earned, negative for refunds (admin) |
| balance_after | INTEGER | Running total after this event |
| type | TEXT | task_completion | assessment | challenge | mock | diagnostic | resource | bonus | streak | daily_cap | refund |
| source_id | UUID | Polymorphic: task_id, assessment_id, challenge_id, etc. |
| metadata | JSONB | `{skill, difficulty, combo_count, multipliers}` |
| created_at | TIMESTAMPTZ | Event timestamp |

Indexes: `(user_id, created_at DESC)`, `(user_id, type)`, `(created_at)` for daily aggregation.

#### `streak_state`
Three-tier streak tracking.

| Column | Type | Notes |
|---|---|---|
| user_id | UUID PK | |
| daily_current | SMALLINT | Current daily streak count |
| daily_longest | SMALLINT | Longest daily streak |
| daily_last_active | DATE | Last qualifying activity date |
| daily_frozen | BOOLEAN | True if on vacation/rest |
| weekly_current | SMALLINT | Current weekly streak |
| weekly_longest | SMALLINT | |
| weekly_last_qualifying_week | DATE | Start of last qualifying week |
| monthly_current | SMALLINT | |
| monthly_longest | SMALLINT | |
| monthly_last_qualifying_month | DATE | |
| freeze_count | SMALLINT | Current freeze inventory |
| last_freeze_used_at | DATE | |
| repair_available | BOOLEAN | |
| last_repair_used_at | TIMESTAMPTZ | |
| vacation_start | DATE | |
| vacation_end | DATE | |
| updated_at | TIMESTAMPTZ | |

#### `user_achievements`
Achievement unlock tracking.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK | |
| achievement_code | TEXT | FK → achievements.code |
| unlocked_at | TIMESTAMPTZ | |
| progress_current | INTEGER | For progress-based achievements |
| progress_target | INTEGER | |
| notified | BOOLEAN | Whether user was notified of unlock |

Index: `UNIQUE(user_id, achievement_code)`.

#### `challenge_progress`
Daily, weekly, and monthly challenge tracking.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK | |
| challenge_code | TEXT | |
| period | TEXT | daily | weekly | monthly |
| period_start | DATE | |
| period_end | DATE | |
| target_value | INTEGER | |
| current_value | INTEGER | |
| completed | BOOLEAN | |
| completed_at | TIMESTAMPTZ | |
| xp_awarded | INTEGER | |
| notified | BOOLEAN | |

Index: `UNIQUE(user_id, challenge_code, period_start)`.

#### `league_groups`
League group assignments per season.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| tier | TEXT | |
| season_week_start | DATE | Monday of the week |
| group_size | SMALLINT | |
| created_at | TIMESTAMPTZ | |

#### `league_group_members`
User membership in league groups.

| Column | Type | Notes |
|---|---|---|
| group_id | UUID FK | |
| user_id | UUID FK | |
| rank | SMALLINT | Final rank at season end (NULL during active) |
| xp_earned | INTEGER | XP during this season |
| promoted_to | TEXT | Next tier on promotion |
| demoted_to | TEXT | Previous tier on demotion |

Index: `(group_id, user_id)`.

#### `leaderboard_snapshots`
Historical leaderboard data for analytics and display.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| snapshot_type | TEXT | daily | weekly | monthly | alltime |
| snapshot_date | DATE | |
| rank | INTEGER | |
| user_id | UUID | |
| score | INTEGER | |
| metadata | JSONB | tier, level, streak |

Index: `(snapshot_type, snapshot_date, rank)`.

#### `reward_catalog`
Available rewards and their costs.

| Column | Type | Notes |
|---|---|---|
| code | TEXT PK | |
| name | TEXT | |
| description | TEXT | |
| currency | TEXT | gems | coins |
| cost | INTEGER | |
| category | TEXT | cosmetic | utility | badge |
| is_limited | BOOLEAN | Seasonal or limited edition |
| active_from | DATE | |
| active_until | DATE | |

#### `user_rewards`
Items the user has purchased.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK | |
| reward_code | TEXT FK | |
| purchased_at | TIMESTAMPTZ | |
| is_equipped | BOOLEAN | Whether currently in use (cosmetics) |

#### `achievement_catalog`
Master list of all achievements.

| Column | Type | Notes |
|---|---|---|
| code | TEXT PK | |
| category | TEXT | |
| name | TEXT | |
| description | TEXT | |
| tier | TEXT | bronze | silver | gold | platinum | diamond | master | legend |
| xp_reward | INTEGER | |
| hidden | BOOLEAN | Secret achievements |
| is_badge | BOOLEAN | True if this is a badge-tier achievement |

---

## 16. API Design

### 16.1 Gamification Endpoints

| Method | Endpoint | Purpose | Response |
|---|---|---|---|
| GET | `/api/v1/gamification/state` | Full gamification state for current user | `gamification_state` + `streak_state` + `level` |
| GET | `/api/v1/gamification/xp/ledger?page=&limit=` | XP ledger history (paginated) | `{ entries, total, page }` |
| GET | `/api/v1/gamification/streaks` | Current streak state | `{ daily, weekly, monthly, freeze_count, repair_available }` |
| POST | `/api/v1/gamification/streaks/freeze` | Consume a freeze (manually triggered) | `{ new_streak, freeze_count }` |
| POST | `/api/v1/gamification/streaks/repair` | Apply streak repair | `{ restored_streak, repair_used }` |
| GET | `/api/v1/gamification/achievements` | All achievements + user progress | `{ catalog: [...], unlocked: [...], progress: [...] }` |
| GET | `/api/v1/gamification/badges` | Badge progress per category | `{ category, tier, progress, next_tier }` |
| GET | `/api/v1/gamification/challenges/daily` | Today's daily challenges + progress | `[ { code, objective, tier, progress, completed } ]` |
| GET | `/api/v1/gamification/challenges/weekly` | Current weekly challenge | `{ code, objective, progress, completed }` |
| GET | `/api/v1/gamification/challenges/monthly` | Current monthly challenge | `{ code, objective, progress, completed }` |
| GET | `/api/v1/gamification/leagues/current` | Current league group + standings | `{ tier, group_id, rank, members[], promotion_zone, demotion_zone }` |
| GET | `/api/v1/gamification/leagues/history` | Past league seasons | `[ { season, tier, rank, promoted } ]` |
| GET | `/api/v1/gamification/leaderboard?type=daily|weekly|monthly|alltime` | Global leaderboard | `{ type, entries: [{rank, user, score, level}], my_rank, my_score }` |
| GET | `/api/v1/gamification/rewards` | Reward catalog | `[ { code, name, cost, currency, owned, equipped } ]` |
| POST | `/api/v1/gamification/rewards/redeem` | Purchase a reward | `{ success, new_balance, item }` |
| POST | `/api/v1/gamification/rewards/equip` | Equip/unequip cosmetic | `{ equipped }` |
| GET | `/api/v1/gamification/notifications` | Pending gamification notifications | `[ { type, title, body, metadata } ]` |
| POST | `/api/v1/gamification/notifications/dismiss` | Dismiss notification | `{ dismissed }` |

### 16.2 Realtime Channels

| Channel | Events | Data |
|---|---|---|
| `user:{id}:gamification` | xp_change, level_up, streak_update, achievement_unlock, badge_earned, challenge_complete | `{ type, data }` |
| `user:{id}:league` | season_start, season_end, promotion, demotion, rank_change | `{ tier, group_id, rank }` |
| `user:{id}:notifications` | new_notification, notification_count | `{ type, title, body, count }` |

---

## 17. Future Premium Features

### 17.1 Premium Gamification Features

| Feature | Description | Monetization Model |
|---|---|---|
| **XP Boost** | 2× XP for 24 hours (from reward catalog) | Gem purchase |
| **League Freeze** | Skip one week without demotion | Subscription perk |
| **Streak Repair** | Additional repair tokens (beyond the 1/30d limit) | Gem purchase |
| **Exclusive Themes** | Premium-only dashboard themes (Aurora, Ocean, Sunset) | Subscription |
| **Exclusive Badges** | Seasonal badges (Lunar, Anniversary, Holiday) | Limited-time gem purchase |
| **Custom Avatar** | Full avatar customization (hairstyle, outfit, accessories) | Gem + coin hybrid |
| **Study Buddy** | Compete against a friend in a private league | Subscription |
| **Double Gems** | All gem rewards doubled | Subscription |
| **Premium Challenges** | Extra daily challenge slot (4 instead of 3) | Subscription |
| **Legendary Badge** | Exclusive "Legendary" badge variant for each category | Subscription + achievement |
| **XP Insurance** | One missed day per week doesn't break streak (auto-freeze) | Subscription |
| **Advanced Analytics** | Gamification-insights dashboard: XP per hour, most efficient study times, streak prediction | Subscription |
| **Seasonal Leagues** | 4-week seasons instead of 1-week, with end-of-season rewards | Free (engagement driver) |
| **Tournaments** | 24-hour global XP tournaments with leaderboard and prizes | Free + premium entry |
| **NFT Badges (future)** | Earn verifiable achievement badges on blockchain | Blockchain integration |

### 17.2 Premium Subscription Tiers

| Tier | Price | Gamification Benefits |
|---|---|---|
| **Free** | $0 | Base XP, levels, leagues, basic achievements, daily/weekly/monthly challenges |
| **Pro** | $15/mo | 2× XP, league freeze, 2 streak repairs/mo, exclusive themes, premium badge eligibility |
| **Ultimate** | $25/mo | All Pro features + double gems, 4 daily challenges, XP insurance, advanced analytics, seasonal tournaments |

---

*This document is a complete software design specification for the Duolingo-inspired gamification system. It is the source of truth for the `backend/app/gamification` module and all client-side gamification rendering. All design decisions are consistent with ARCHITECTURE.md, SCHEDULER.md, AI_BRAIN.md, and DASHBOARD.md.*
