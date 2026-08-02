# Adaptive Scheduler — Design Document

**Role:** Senior Database Architect  
**Document:** Algorithm Design  
**Status:** Draft for review & approval  

---

## 0. Executive Summary

The Adaptive Scheduler is the **core intelligence engine** of IELTS AI Coach. It transforms a user's diagnostic score, target band, exam date, and daily study budget into a **dynamic, self-correcting daily mission plan**. Unlike a static calendar, the scheduler continuously monitors completion, automatically shifts missed work forward, recalculates workload, and protects high-priority revision windows. It is the engine behind the "Duolingo-like streaks", "auto-shift unfinished work", and "continuously updated study roadmap" features.

---

## 1. Inputs Overview

### 1.1 Per-User Configuration (User Goals)

| Input | Type | Example | Source |
|---|---|---|---|
| `exam_date` | DATE | `2025-06-15` | User profile |
| `target_band` | NUMERIC(2,1) | `7.5` | User profile |
| `diagnostic_band` | NUMERIC(2,1) | `5.5` | Diagnostic result |
| `daily_minutes` | INT | `60` | User preference |
| `module` | ENUM | `academic` / `general` | User preference |
| `skill_gaps` | JSONB | `{"grammar": 6.0, "lexical": 5.5, ...}` | Diagnostic result |
| `timezone` | TEXT | `Asia/Kolkata` | User profile |

### 1.2 Derived Constants

| Constant | Formula | Example |
|---|---|---|
| `total_days_remaining` | `exam_date - TODAY()` | 120 days |
| `total_study_hours` | `total_days_remaining * (daily_minutes / 60)` | 120 h |
| `band_gap` | `target_band - diagnostic_band` | 2.0 |
| `estimated_weeks_per_0.5_band` | Industry norm: ~4–6 weeks per 0.5 band | 5 weeks |
| `max_daily_minutes` | Cap at `daily_minutes * 1.5` (safety ceiling) | 90 min |
| `min_daily_minutes` | Floor at `daily_minutes * 0.5` (minimum viable) | 30 min |

---

## 2. Core Algorithm — Phase Generation

### 2.1 Phase Structure

The scheduler divides the user's timeline into **phases**, each with a specific pedagogical goal:

```
Phase 0:  Diagnostic & Setup          (Day 1)            — 1 day
Phase 1:  Foundation & Gap Closure    (Day 2–Week 4)     — ~4 weeks
Phase 2:  Skill Building              (Week 5–Week 10)   — ~6 weeks
Phase 3:  Advanced Techniques         (Week 11–Week 14)  — ~4 weeks
Phase 4:  Mock Test Marathon          (Week 15–Week 18)  — ~4 weeks
Phase 5:  Final Revision & Strategy   (Week 19–Exam Day) — ~2 weeks
```

**Duration allocation** is proportional to the band gap:

```
phase_weeks(i) = total_weeks * weight(i)

Weight distribution:
  Foundation:    0.30  (30% of total time)
  Skill Building: 0.30  (30%)
  Advanced:       0.20  (20%)
  Mock Tests:     0.15  (15%)
  Revision:       0.05  (5% — fixed, protected)
```

### 2.2 Skill-to-Phase Mapping

Each phase targets specific IELTS criteria. The mapping is dynamic based on the user's diagnostic skill gaps:

| Phase | Primary Focus | Secondary Focus |
|---|---|---|
| Foundation | Weakest skill(s) from diagnostic | Grammar fundamentals |
| Skill Building | All 4 criteria evenly | Fluency, vocabulary |
| Advanced | Coherence & Cohesion, Lexical Resource | Complex structures |
| Mock Tests | Full exam simulation, time management | Identifying remaining gaps |
| Revision | Biggest remaining gap, exam strategy | Confidence building |

**Algorithm — Skill Deficiency Weighting:**

```
For each skill S in {TR, CC, LR, GR}:
    gap(S) = target_band - diagnostic_skill_score(S)
    weight(S) = gap(S) / SUM(gap(all skills))
    
Phase allocation for Foundation:
    task_skill_distribution = [weight(S) for each S]
```

---

## 3. Daily Mission Generation Algorithm

### 3.1 Mission Composition

Each day's mission is a set of tasks with a total duration ≤ `adjusted_daily_budget`.

```
DailyMission = {
    date: DATE,
    tasks: [
        { title, skill, duration_minutes, type, resource_id?, is_required },
        ...
    ],
    total_minutes: INT,
    is_revision_day: BOOLEAN,
    is_mock_test_day: BOOLEAN,
    phase: STRING
}
```

### 3.2 Task Types

| Task Type | Duration (min) | Frequency | Priority |
|---|---|---|---|
| **Writing — Task 1** | 30 | 2× per week | High |
| **Writing — Task 2** | 40 | 3× per week | High |
| **Speaking — Part 1** | 10 | 2× per week | Medium |
| **Speaking — Part 2** | 12 | 2× per week | Medium |
| **Speaking — Part 3** | 12 | 1× per week | Medium |
| **Vocabulary Study** | 15 | Daily | Medium |
| **Grammar Drill** | 15 | Daily (Foundation) | High (early) |
| **Reading Practice** | 20 | 2× per week | Low |
| **Listening Practice** | 20 | 2× per week | Low |
| **Mock Test (Full)** | 180 | Per schedule | Critical |
| **Mock Test (Section)** | 45 | Per schedule | High |
| **Review Mistakes** | 15 | After each mock/test | High |
| **Revision** | 30 | Protected days | Critical |

### 3.3 Task Selection Algorithm

```
INPUT:  user_profile, today_date, phase, previous_completions, remaining_gaps
OUTPUT: DailyMission

PROCEDURE GenerateMission:
    1.  budget = GetAdjustedDailyBudget(user_profile, today_date)
    
    2.  // STEP 1: Check for protected days
        IF today_date is in PROTECTED_REVISION_WINDOW:
            RETURN RevisionMission(budget)
        IF today_date is MOCK_TEST_SCHEDULE:
            RETURN MockTestMission(budget, mock_test_number)
    
    3.  // STEP 2: Collect all overdue tasks (carried forward)
        overdue = GetOverdueTasks(user_id, today_date)
    
    4.  // STEP 3: Prioritize overdue tasks
        // Sort by: priority → original_date → duration
        overdue.sort(key=lambda t: (t.priority, t.original_date, -t.duration))
    
    5.  // STEP 4: Fill mission with overdue tasks first
        mission_tasks = []
        remaining_budget = budget
        FOR task IN overdue:
            IF task.duration_minutes <= remaining_budget:
                mission_tasks.append(task)
                remaining_budget -= task.duration_minutes
            ELSE:
                // Partial carry-forward — split task
                IF task.duration_minutes > 30:  // only splittable tasks
                    partial = SplitTask(task, remaining_budget)
                    mission_tasks.append(partial)
                    remaining_budget = 0
                BREAK  // budget exhausted
    
    6.  // STEP 5: Fill remaining budget with new tasks from current phase
        IF remaining_budget > 0:
            new_tasks = SelectNewTasks(
                phase = current_phase,
                skill_weights = skill_gap_weights,
                budget = remaining_budget,
                exclude_types = recently_done_types  // variety
            )
            mission_tasks.extend(new_tasks)
    
    7.  // STEP 6: Add a "streak-friendly" quick task if budget allows
        IF remaining_budget >= 10:
            mission_tasks.append(QuickWinTask())  // 10-min vocab or review
    
    8.  RETURN DailyMission(date=today_date, tasks=mission_tasks, 
                           total_minutes=budget - remaining_budget)
```

### 3.4 Task Variety Enforcement

The scheduler ensures no skill is neglected:

```
// Rolling 3-day window check
last_3_days = GetTasksLastNDays(user_id, today_date, 3)
skills_covered = set(last_3_days.skill)

// If a skill is missing from the last 3 days, force at least one task
missing_skills = ALL_SKILLS - skills_covered
IF missing_skills:
    forced_task = SelectTaskForSkill(missing_skills[0], budget)
    mission_tasks.append(forced_task)
```

---

## 4. Missed Task Carry-Forward Algorithm

### 4.1 Detection

The Daily Rollover Job runs at `00:00` (user-local time) every day:

```
FOR EACH user:
    yesterday = TODAY() - 1
    pending_tasks = SELECT * FROM tasks
                   WHERE user_id = user.id
                   AND scheduled_date = yesterday
                   AND status = 'pending'
    
    FOR EACH task IN pending_tasks:
        IF task.is_mock_test:
            // Mock tests are never carried forward; they are rescheduled
            RescheduleMockTest(user, task)
        ELSE:
            CarryForwardTask(user, task)
```

### 4.2 Carry-Forward Algorithm

```
PROCEDURE CarryForwardTask(user, task):
    
    // 1. Mark original task as 'missed'
    task.status = 'missed'
    task.missed_at = NOW()
    task.save()
    
    // 2. Determine how many days forward to shift
    overload_factor = GetCurrentOverloadFactor(user)
    
    // Base: shift by 1 day
    // If overloaded, shift by more days to spread the load
    shift_days = 1
    IF overload_factor > 1.2:
        shift_days = CEIL(overload_factor * task.duration_minutes / user.daily_minutes)
    
    // 3. Find the first available day with enough budget
    target_date = TODAY()
    attempts = 0
    WHILE attempts < MAX_SHIFT_DAYS (14):
        daily_budget = GetRemainingBudgetForDate(user, target_date)
        IF daily_budget >= task.duration_minutes:
            // Create a new task instance on the target date
            new_task = task.clone()
            new_task.scheduled_date = target_date
            new_task.original_task_id = task.id  // lineage tracking
            new_task.status = 'pending'
            new_task.priority = task.priority + 1  // increase priority
            new_task.save()
            BREAK
        target_date += 1 day
        attempts += 1
    
    // 4. If no slot found in 14 days, flag for priority merge
    IF attempts >= MAX_SHIFT_DAYS:
        FlagForPriorityMerge(user, task)
```

### 4.3 Overload Factor Calculation

```
PROCEDURE GetCurrentOverloadFactor(user):
    today = TODAY()
    next_7_days = SELECT SUM(duration_minutes) FROM tasks
                  WHERE user_id = user.id
                  AND scheduled_date BETWEEN today AND today + 7
                  AND status = 'pending'
    
    available_capacity = 7 * user.daily_minutes  // e.g., 7 × 60 = 420 min
    
    IF available_capacity == 0:
        RETURN 1.0
    
    overload_factor = next_7_days / available_capacity
    
    // Clamp between 0.5 and 3.0
    RETURN MIN(MAX(overload_factor, 0.5), 3.0)
```

---

## 5. Recalculation Engine

Every time a task is completed or the daily rollover runs, the scheduler recalculates:

### 5.1 Remaining Study Hours

```
PROCEDURE RecalculateRemainingHours(user):
    total_required = EstimateTotalHoursRequired(user)
    
    // Hours already completed
    completed = SELECT SUM(duration_minutes) / 60.0 FROM study_sessions
                WHERE user_id = user.id
                AND completed_at >= user.study_plan.created_at
    
    // Hours already scheduled (future)
    scheduled = SELECT SUM(duration_minutes) / 60.0 FROM tasks
                WHERE user_id = user.id
                AND scheduled_date >= TODAY()
                AND status = 'pending'
    
    remaining = total_required - completed - scheduled
    RETURN MAX(remaining, 0)
```

### 5.2 Remaining Days

```
remaining_days = exam_date - TODAY()
```

### 5.3 Daily Workload Adjustment

```
PROCEDURE AdjustDailyWorkload(user):
    remaining_days = user.exam_date - TODAY()
    remaining_hours = RecalculateRemainingHours(user)
    
    // Ideal daily minutes
    IF remaining_days > 0:
        ideal_daily = CEIL((remaining_hours * 60) / remaining_days)
    ELSE:
        ideal_daily = user.daily_minutes * 1.5  // crunch mode
    
    // Clamp: respect user's preference but allow slight increase
    new_budget = CLAMP(
        ideal_daily,
        user.daily_minutes * 0.5,      // min: half of preference
        user.daily_minutes * 1.5       // max: 1.5x of preference
    )
    
    // If remaining days < 30, allow up to 2x (crunch mode)
    IF remaining_days < 30:
        new_budget = MIN(new_budget, user.daily_minutes * 2.0)
    
    user.adjusted_daily_minutes = new_budget
    user.save()
```

### 5.4 Predicted Band

```
PROCEDURE PredictBand(user):
    // Feature vector
    features = {
        'diagnostic_band': user.diagnostic_band,
        'current_avg_band': GetWeightedAverageBand(user),  // last 5 assessments
        'skill_scores': GetLatestSkillScores(user),
        'hours_completed': GetTotalHoursCompleted(user),
        'streak_length': GetCurrentStreak(user),
        'days_remaining': user.exam_date - TODAY(),
        'tasks_completed_30d': CountTasksCompletedLast30Days(user),
        'mock_test_scores_avg': GetAverageMockTestBand(user)
    }
    
    // Weighted regression model
    predicted_band = 
        0.25 * features.diagnostic_band +
        0.35 * features.current_avg_band +
        0.10 * NORMALIZE(features.hours_completed, 0, 120) * 9.0 +
        0.10 * NORMALIZE(features.streak_length, 0, 100) * 9.0 +
        0.10 * features.mock_test_scores_avg +
        0.10 * NORMALIZE(features.tasks_completed_30d, 0, 60) * 9.0
    
    // Apply IELTS rounding rule
    predicted_band = ROUND(predicted_band * 2) / 2
    
    // Clamp
    predicted_band = CLAMP(predicted_band, 0.0, 9.0)
    
    // Confidence score
    assessment_count = CountAssessments(user)
    IF assessment_count >= 10:
        confidence = 0.9
    ELIF assessment_count >= 5:
        confidence = 0.7
    ELIF assessment_count >= 2:
        confidence = 0.5
    ELSE:
        confidence = 0.3
    
    RETURN { 'predicted_band': predicted_band, 'confidence': confidence }
```

### 5.5 Mock Test Schedule

```
PROCEDURE ScheduleMockTests(user):
    remaining_days = user.exam_date - TODAY()
    target_band = user.target_band
    current_band = GetCurrentAverageBand(user)
    
    // Number of mock tests based on time remaining
    IF remaining_days >= 90:
        mock_count = 6
    ELIF remaining_days >= 60:
        mock_count = 4
    ELIF remaining_days >= 30:
        mock_count = 3
    ELIF remaining_days >= 14:
        mock_count = 2
    ELSE:
        mock_count = 1
    
    // Spacing: start after Phase 2, with increasing frequency
    mock_intervals = []
    phase2_end = user.study_plan.created_at + Phase2Duration(user)
    
    FOR i IN range(1, mock_count + 1):
        // Exponential spacing: each mock is closer to the exam
        spacing_factor = 1.0 - (i / (mock_count + 1)) * 0.6  // 0.4 to 1.0
        interval_days = CEIL((remaining_days * spacing_factor) / (mock_count - i + 1))
        
        mock_date = (i == 1) ? phase2_end : mock_intervals[-1].date + interval_days
        
        mock_intervals.append({
            'mock_number': i,
            'date': mock_date,
            'type': 'full' if i >= mock_count - 1 else 'section',
            'focus_area': GetFocusAreaForMock(i, user.skill_gaps)
        })
    
    // Protect days before/after each mock test
    FOR mock IN mock_intervals:
        // Day before mock: light review only (50% budget)
        AddLightReviewDay(mock.date - 1, 0.5 * user.daily_minutes)
        // Day after mock: mistake review + rest (60% budget)
        AddMistakeReviewDay(mock.date + 1, 0.6 * user.daily_minutes)
    
    RETURN mock_intervals
```

### 5.6 Revision Schedule

```
PROCEDURE ScheduleRevision(user):
    exam_date = user.exam_date
    
    // Protected revision windows (these are NEVER overwritten by carry-forward)
    revision_windows = [
        { start: exam_date - 14, end: exam_date, type: 'final_revision' },
        { start: exam_date - 30, end: exam_date - 15, type: 'intensive_revision' },
    ]
    
    // Within revision windows, tasks are:
    FOR window IN revision_windows:
        FOR date IN RANGE(window.start, window.end):
            IF window.type == 'final_revision':
                // 80% review, 20% new practice
                task_mix = [
                    { type: 'review_mistakes', weight: 0.40 },
                    { type: 'vocabulary_review', weight: 0.20 },
                    { type: 'grammar_drill', weight: 0.20 },
                    { type: 'light_practice', weight: 0.20 },
                ]
            ELSE:
                // 50% new practice, 30% review, 20% mock
                task_mix = [
                    { type: 'practice', weight: 0.50 },
                    { type: 'review_mistakes', weight: 0.30 },
                    { type: 'mock_section', weight: 0.20 },
                ]
            
            // Mark these days as protected
            MarkProtectedDays(date, window.type)
```

---

## 6. Phase Transition Logic

### 6.1 When to Advance

The scheduler advances a phase when the user has **completed 80% of the phase's tasks** OR the **phase's time allocation has elapsed**, whichever comes first.

```
PROCEDURE CheckPhaseTransition(user):
    phase = GetCurrentPhase(user)
    
    completion_rate = phase.completed_tasks / phase.total_tasks
    time_elapsed_rate = (TODAY() - phase.start_date) / (phase.end_date - phase.start_date)
    
    IF completion_rate >= 0.80 OR time_elapsed_rate >= 1.0:
        IF phase.order_index < MAX_PHASE_INDEX:
            next_phase = GetNextPhase(user)
            next_phase.status = 'active'
            phase.status = 'completed'
            GenerateTasksForPhase(user, next_phase)
            
            // Notification
            SendNotification(user, 'phase_complete', {
                'completed_phase': phase.title,
                'next_phase': next_phase.title
            })
```

### 6.2 What Happens to Incomplete Phase Tasks

```
PROCEDURE HandleIncompletePhaseTasks(user, old_phase, new_phase):
    // 1. Carry forward all incomplete tasks to the new phase
    pending_tasks = GetPendingTasksForPhase(user, old_phase.id)
    
    FOR task IN pending_tasks:
        // Reprioritize: highest-value tasks come first
        task.phase_id = new_phase.id
        task.priority = CalculatePrioritizationScore(task)
        task.status = 'pending'
        task.scheduled_date = FindNextAvailableSlot(user, new_phase)
        task.save()
    
    // 2. If too many tasks were carried forward, merge some
    //    (e.g., combine two grammar drills into one)
    total_carried = SUM(task.duration_minutes FOR task IN pending_tasks)
    IF total_carried > new_phase.total_budget * 0.3:
        MergeLowPriorityTasks(user, pending_tasks, new_phase)
```

---

## 7. Special Day Protection System

### 7.1 Protected Day Types

| Type | Days | What Happens |
|---|---|---|
| **Revision** | Last 14 days | Light review only; no new heavy tasks |
| **Mock Test** | As scheduled | Full mock; day before = light prep; day after = mistake review |
| **Rest** | 1 day per week (user-configurable) | No tasks assigned; streak is preserved |
| **Streak Saver** | After 3 consecutive missed days | Force a "minimum viable" day (a single 10-min task) |

### 7.2 Protection Algorithm

```
PROCEDURE IsProtectedDay(user, date):
    // 1. Check if in revision window
    exam = user.exam_date
    IF date >= exam - 14 AND date <= exam:
        RETURN 'final_revision'
    
    // 2. Check if mock test day or adjacent
    mock = GetMockTestOnDate(user, date)
    IF mock:
        RETURN 'mock_test'
    IF date == mock.date - 1:
        RETURN 'mock_prep'
    IF date == mock.date + 1:
        RETURN 'mock_review'
    
    // 3. Check if rest day
    day_of_week = DAYOFWEEK(date)
    IF day_of_week == user.rest_day:
        RETURN 'rest'
    
    // 4. Check if streak saver required
    IF GetConsecutiveMissedDays(user) >= 3:
        RETURN 'streak_saver'
    
    RETURN 'normal'
```

### 7.3 No-Overwrite Rule

```
// Protected days are NOT available for carry-forward placement
PROCEDURE FindNextAvailableSlot(user, date):
    max_attempts = 14
    attempts = 0
    WHILE attempts < max_attempts:
        IF IsProtectedDay(user, date) == 'normal':
            available_budget = GetRemainingBudgetForDate(user, date)
            IF available_budget >= MIN_TASK_DURATION:
                RETURN date
        date += 1 day
        attempts += 1
    
    // Fallback: use the first non-revision day
    RETURN FirstNonRevisionDay(user, date)
```

---

## 8. Overload Prevention System

### 8.1 Overload Detection

The scheduler monitors four metrics:

| Metric | Threshold | Action |
|---|---|---|
| `daily_overload_ratio` | > 1.5 (150% of budget) | Spread tasks to next 2 days |
| `weekly_overload_ratio` | > 1.3 (130% of weekly budget) | Drop lowest-priority tasks |
| `consecutive_overload_days` | > 3 | Insert a recovery day (50% budget) |
| `carryforward_accumulation` | > 5 tasks pending | Trigger priority merge |

### 8.2 Overload Mitigation

```
PROCEDURE MitigateOverload(user):
    IF user.daily_overload_ratio > 1.5:
        // Find the 2 lowest-priority tasks and move them to tomorrow
        lowest_tasks = GetLowestPriorityTasks(user, TODAY(), 2)
        FOR task IN lowest_tasks:
            next_date = FindNextAvailableSlot(user, TODAY() + 1)
            task.scheduled_date = next_date
            task.save()
    
    IF user.weekly_overload_ratio > 1.3:
        // Drop the lowest-priority non-required tasks
        candidates = GetNonRequiredTasksInRange(user, TODAY(), TODAY() + 7)
        candidates.sort(by='priority', ascending=True)
        drop_count = CEIL(len(candidates) * 0.2)  // drop bottom 20%
        FOR task IN candidates[:drop_count]:
            task.status = 'deprioritized'
            task.save()
            SendNotification(user, 'task_deprioritized', {
                'title': task.title
            })
    
    IF user.consecutive_overload_days > 3:
        // Insert a recovery day tomorrow
        recovery_date = TODAY() + 1
        existing_tasks = GetTasksForDate(user, recovery_date)
        // Move all but the highest-priority task to the next day
        existing_tasks.sort(by='priority', reverse=True)
        FOR task IN existing_tasks[1:]:
            next_date = FindNextAvailableSlot(user, recovery_date + 1)
            task.scheduled_date = next_date
            task.save()
```

### 8.3 Priority Merge Algorithm

When too many low-priority tasks accumulate:

```
PROCEDURE MergeLowPriorityTasks(user, tasks, target_phase):
    // Group tasks by type
    grouped = {}
    FOR task IN tasks:
        key = task.type
        grouped.setdefault(key, []).append(task)
    
    FOR type, group IN grouped.items():
        IF len(group) >= 2:
            // Merge: create one consolidated task with combined duration
            // But cap at 30 minutes max for any single task
            merged_duration = MIN(
                SUM(task.duration FOR task IN group),
                30
            )
            merged_task = CreateTask(
                title = f"Consolidated {type} Practice",
                type = type,
                duration_minutes = merged_duration,
                priority = MAX(task.priority FOR task IN group),
                phase_id = target_phase.id,
                scheduled_date = FindNextAvailableSlot(user, TODAY())
            )
            merged_task.save()
            
            // Mark original tasks as merged
            FOR task IN group:
                task.status = 'merged'
                task.merged_into_id = merged_task.id
                task.save()
```

---

## 9. Edge Cases

### 9.1 Exam Date Has Passed

```
IF TODAY() > user.exam_date:
    // Scheduler enters "post-exam" mode
    // 1. Generate a post-exam reflection task
    // 2. If user took the exam: ask for results, store them
    // 3. If user postponed: prompt for new exam date
    // 4. If no action: archive the study plan
    user.study_plan.status = 'expired'
    SendNotification(user, 'exam_date_passed', {
        'message': 'Your exam date has passed. Please update your exam date to continue.'
    })
    RETURN
```

### 9.2 User Changes Exam Date

```
IF new_exam_date > old_exam_date:
    // Postponed — recalculate phases with extra time
    extra_days = new_exam_date - old_exam_date
    // Distribute extra days proportionally across phases
    FOR phase IN user.study_plan.phases:
        phase.end_date += extra_days * phase.weight
        phase.save()
    // Re-generate tasks for the extended period
    RegenerateTasksForExtendedPeriod(user, extra_days)

IF new_exam_date < old_exam_date:
    // Brought forward — compress phases
    lost_days = old_exam_date - new_exam_date
    // First, shorten revision window (protected)
    // Then shorten mock test phase
    // Then shorten advanced phase
    // Never compress Foundation below 50% of original
    compression_order = ['revision', 'mock_tests', 'advanced', 'skill_building']
    FOR phase_type IN compression_order:
        phase = GetPhaseByType(user, phase_type)
        reduction = MIN(lost_days, phase.duration_days * 0.5)
        phase.end_date -= reduction
        lost_days -= reduction
        IF lost_days <= 0:
            BREAK
    // Flag for user: "Your plan has been compressed"
    SendNotification(user, 'plan_compressed', {
        'message': f'Your study plan has been adjusted for the new exam date.'
    })
```

### 9.3 User Changes Target Band

```
IF new_target > old_target:
    band_increase = new_target - old_target
    extra_weeks = band_increase * 5  // 5 weeks per 0.5 band
    extra_days = extra_weeks * 7
    
    IF extra_days <= remaining_days_before_exam:
        // Redistribute existing time + add more tasks
        RedistributeForHigherTarget(user, new_target)
    ELSE:
        // Not enough time — warn user
        SendNotification(user, 'target_too_high', {
            'message': f'To reach Band {new_target}, you may need to postpone your exam.'
        })
        // Still try, but with lower confidence
        RedistributeForHigherTarget(user, new_target)
        user.prediction_confidence *= 0.8

IF new_target < old_target:
    // Lower target — relax schedule
    // Remove some advanced tasks, reduce mock test frequency
    RelaxSchedule(user, new_target)
```

### 9.4 User Misses Multiple Days (Streak Break)

```
missed_days = GetConsecutiveMissedDays(user)

IF missed_days == 1:
    // Normal — carry forward as usual
    CarryForwardMissedTasks(user, 1)

IF missed_days == 2:
    // Carry forward but mark as "catch-up mode"
    CarryForwardMissedTasks(user, 2)
    user.is_catch_up_mode = True
    // Reduce new task generation by 30%
    user.new_task_multiplier = 0.7

IF missed_days >= 3:
    // Enter "streak saver" mode
    // 1. Only generate minimum viable tasks (1 quick task per day)
    // 2. Do NOT carry forward all tasks at once
    // 3. Prioritize: revision > mock > writing > speaking > vocabulary
    IF missed_days >= 5:
        // After 5 days, reset the plan
        // 1. Archive current plan
        // 2. Generate a "recovery plan" (compressed version of foundation)
        // 3. After recovery plan is complete, re-enter main plan
        ArchiveAndRegeneratePlan(user, 'recovery')
```

### 9.5 User Completes a Mock Test

```
// Mock test completion triggers significant recalculation
PROCEDURE OnMockTestCompleted(user, mock_result):
    // 1. Store the result
    SaveMockTestResult(user, mock_result)
    
    // 2. Compare actual vs predicted band
    delta = mock_result.band_score - GetPredictedBand(user)
    
    // 3. If mock score is significantly lower (> 0.5 band) than predicted:
    IF delta < -0.5:
        // Re-analyze skill gaps based on mock test breakdown
        new_gaps = AnalyzeMockTestGaps(mock_result)
        user.skill_gaps = new_gaps
        
        // Adjust future phases: add more foundation tasks
        AdjustPhaseContent(user, current_phase, 'more_foundation')
        
        // Warn user
        SendNotification(user, 'mock_below_target', {
            'message': f'Your mock score ({mock_result.band_score}) is below your target. We\'ve adjusted your plan.'
        })
    
    // 4. If mock score is significantly higher (> 0.5 band) than predicted:
    IF delta > 0.5:
        // Accelerate: reduce some practice tasks, add more advanced tasks
        AcceleratePhase(user, current_phase)
        
        // Congratulate user
        SendNotification(user, 'mock_above_target', {
            'message': f'Great progress! Your mock score ({mock_result.band_score}) exceeds expectations.'
        })
    
    // 5. Recalculate predicted band (with new mock data)
    RecalculatePredictedBand(user)
```

### 9.6 User takes a Vacation / Planned Break

```
IF user.planned_break_start and user.planned_break_end:
    // 1. During the break: do NOT schedule any tasks
    // 2. Do NOT mark tasks as missed during the break
    // 3. Pause the streak counter (freeze, don't break)
    // 4. After break: redistribute missed tasks evenly across remaining days
    break_duration = user.planned_break_end - user.planned_break_start
    
    // Redistribute
    FOR day IN RANGE(break_start, break_end):
        tasks = GetTasksForDate(user, day)
        FOR task IN tasks:
            new_date = FindNextAvailableSlot(user, break_end + 1)
            task.scheduled_date = new_date
            task.save()
    
    user.streak.frozen = True
    user.streak.freeze_until = break_end
    user.save()
```

### 9.7 User Has No Diagnostic Score (New User)

```
IF user.diagnostic_band IS NULL:
    // 1. Do NOT generate a full study plan
    // 2. Generate a "Get Started" mini-plan (3 days):
    //    Day 1: Writing Task 2 (to assess writing)
    //    Day 2: Speaking Part 1 (to assess speaking)
    //    Day 3: Vocabulary quiz (to assess vocabulary)
    // 3. After all 3 tasks are completed, run diagnostic analysis
    // 4. Generate full study plan based on diagnostic
    GenerateOnboardingPlan(user)
```

### 9.8 Zero Daily Minutes Available

```
// If adjusted_daily_minutes < minimum_threshold (10 min):
IF user.adjusted_daily_minutes < 10:
    // Option 1: Show a "rest day" message
    // Option 2: Force a 5-minute vocabulary review (minimum viable)
    IF remaining_days_before_exam < 30:
        // Exam is close — force a 10-min session
        user.adjusted_daily_minutes = 10
    ELSE:
        // No pressure — mark as rest day
        MarkAsRestDay(user, TODAY())
```

### 9.9 All Tasks Completed Early

```
IF CountPendingTasks(user) == 0 AND remaining_days_before_exam > 0:
    // 1. Check if user has reached their target band
    current_band = GetCurrentAverageBand(user)
    IF current_band >= user.target_band:
        // User has surpassed target! Enter maintenance mode
        // 1 task per day, focus on keeping skills sharp
        GenerateMaintenanceTasks(user)
        SendNotification(user, 'ahead_of_schedule', {
            'message': 'You\'ve completed all tasks ahead of schedule! We\'re entering maintenance mode.'
        })
    ELSE:
        // User completed tasks but hasn't reached target
        // Generate additional advanced tasks
        GenerateAdvancedTasks(user)
```

### 9.10 Concurrent User Count (Millions Scale)

- **Partitioning:** `tasks` and `study_sessions` partitioned by `user_id % 100` (hash-based) or by month
- **Batch processing:** Daily rollover runs in batches of 10,000 users; each batch is a separate Celery task
- **Caching:** `daily_plans` for the current week are cached in Redis; invalidated on task completion
- **Read replicas:** Dashboard queries (read-heavy) routed to Supabase read replicas
- **Write throttling:** Task completion events batched and flushed every 5 seconds per user

---

## 10. Algorithm Pseudocode — Daily Rollover (Complete)

```
FUNCTION DailyRollover(user_id):
    user = LoadUser(user_id)
    
    // Step 1: Check exam date
    IF TODAY() > user.exam_date:
        HandleExpiredExam(user)
        RETURN
    
    // Step 2: Detect and carry forward missed tasks
    missed_tasks = GetMissedTasks(user, TODAY() - 1)
    FOR task IN missed_tasks:
        IF IsProtectedDay(user, task.scheduled_date + 1):
            // Skip protected days; find next available
            next_date = FindNextAvailableSlot(user, task.scheduled_date + 1)
            RescheduleTask(task, next_date)
        ELSE:
            CarryForwardTask(user, task)
    
    // Step 3: Recalculate remaining hours and workload
    RecalculateRemainingHours(user)
    AdjustDailyWorkload(user)
    
    // Step 4: Generate today's mission
    mission = GenerateMission(user, TODAY())
    
    // Step 5: Check phase transition
    CheckPhaseTransition(user)
    
    // Step 6: Update streak
    UpdateStreak(user)
    
    // Step 7: Recalculate predicted band
    RecalculatePredictedBand(user)
    
    // Step 8: Check for mock test scheduling
    IF ShouldScheduleMockTest(user):
        ScheduleMockTests(user)
    
    // Step 9: Check for overload
    MitigateOverload(user)
    
    // Step 10: Send daily notification
    SendDailyNotification(user, mission)
    
    RETURN mission
```

---

## 11. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Carry-forward, not drop** | Every task is valuable. Dropping tasks would create knowledge gaps. Carry-forward ensures coverage. |
| **Protected days are sacred** | Revision and mock test days are the highest-leverage activities. Never overwrite them with carry-forward. |
| **Overload prevention before everything** | A user who burns out stops using the app. The scheduler always prioritizes sustainability over intensity. |
| **Phase-based, not time-based** | Users progress at different speeds. Phase transitions based on completion rate (80%) ensure mastery before advancement. |
| **Mock tests trigger re-planning** | Mock tests are the most accurate signal of true progress. They should cause the scheduler to re-calibrate. |
| **Streak is preserved on rest days** | Rest is essential for learning. The scheduler never penalizes a planned rest day. |
| **Minimum viable day after 3 misses** | A 10-minute task preserves the habit and prevents the "all or nothing" spiral. |
| **Plan compression preserves foundation** | When exam is brought forward, revision is cut first, then mocks, then advanced. Foundation is never cut below 50%. |

---

*This document describes the complete Adaptive Scheduler design. It is the core intelligence of the IELTS AI Coach platform. All algorithms are designed to be implemented as Celery tasks (daily rollover) and FastAPI service methods (on-demand operations).*
