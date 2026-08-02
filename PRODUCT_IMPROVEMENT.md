# IELTS AI Coach — Continuous Product Improvement System

**Role:** Chief Product Officer & Head of Data Science
**Document:** Self-Improving Platform Design
**Status:** Draft for review & approval

---

## 0. Executive Summary

IELTS AI Coach is designed to **get better with every user interaction**. The Continuous Improvement System (CIS) is the closed feedback loop that converts raw user behavior, outcomes, and feedback into measurable improvements across every intelligent layer of the platform — the AI assessors, the roadmap generator, the resource recommender, the adaptive scheduler, and the band predictor.

```
┌────────────────────────────────────────────────────────────────────┐
│                    EVERY USER INTERACTION                           │
│  (assessment submitted · task completed · resource viewed ·        │
│   roadmap generated · mock finished · plan rated · exam entered)   │
└──────────────────────────────┬─────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                 1. DATA COLLECTION LAYER                           │
│  Behavioral events (ANALYTICS.md) · Explicit feedback               │
│  (FEEDBACK_SYSTEM.md) · Outcomes (mock/exam) ·                       │
│  Content interactions · Performance telemetry                       │
└──────────────────────────────┬─────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                 2. FEATURE & SIGNAL PIPELINE                       │
│  Normalization · deduplication · validation · feature engineering   │
│  → structured signals per user, per skill, per content item         │
└──────────────────────────────┬─────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                 3. IMPROVEMENT ENGINE (7 loops)                    │
│  L1 AI Recommendation ↑   L2 Roadmap Quality ↑                     │
│  L3 Resource Ranking ↑    L4 Task Difficulty ↑                     │
│  L5 Band Prediction ↑     L6 Content Curation ↑                    │
│  L7 User Satisfaction ↑                                            │
└──────────────────────────────┬─────────────────────────────────────┘
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                 4. DEPLOYMENT & MEASUREMENT                        │
│  A/B test → canary deploy → monitor → rollback                     │
│  Every change must improve a tracked KPI or it is reverted          │
└────────────────────────────────────────────────────────────────────┘
```

**Core principles:**

1. **Every interaction is a signal.** Nothing the user does — or fails to do — is wasted. Completion, abandonment, skip, rating, retry, dwell time, and outcome all carry information.
2. **Explicit feedback is truth; implicit behavior is evidence.** Ratings tell us what users *say*; behavior tells us what users *do*. When they conflict, behavior wins for prioritization, feedback wins for diagnosis.
3. **Outcomes are the ultimate calibrator.** The only ground truth is what actually happens: mock bands, real exam results, target attainment. All model weights are recalibrated against outcomes.
4. **Improve, don't just measure.** Every KPI has an owner, a feedback loop, and an action. A metric without a decision attached is decoration.
5. **Pedagogy is never compromised for engagement.** Optimizing for short-term interaction at the expense of learning quality is forbidden (consistent with AI_BRAIN.md and GAMIFICATION.md §0).

---

## 1. What Data Should Be Collected

### 1.1 The Five Data Classes

| Class | What it captures | Primary Source | Storage |
|---|---|---|---|
| **A. Behavioral Events** | What users do (click, type, submit, view, abandon) | ANALYTICS.md event taxonomy | `analytics_events` |
| **B. Explicit Feedback** | What users say (ratings, bugs, ideas, flags) | FEEDBACK_SYSTEM.md | `feature_ratings`, `ai_feedback`, `plan_feedback`, `bug_reports`, `feature_requests` |
| **C. Outcomes** | What actually happened (mock bands, exam results, target met) | Mock submission, exam entry | `mock_tests`, `progress`, `exam_results` |
| **D. Content Interactions** | How content performs (watch %, scroll depth, bookmark, completion) | RESOURCE_ENGINE.md | `resource_views`, `resource_completions`, `resource_bookmarks` |
| **E. Performance & Quality** | How well the AI and platform perform (latency, error rate, feedback ratings) | Server logs, `ai_feedback` | `assessments`, `decision_log`, `model_registry` |

### 1.2 Behavioral Events (Class A)

Collected per the full ANALYTICS.md taxonomy. The minimum viable set for the improvement engine:

| Domain | Events | Improvement value |
|---|---|---|
| Auth | `auth_signup`, `auth_login`, `auth_logout`, `onboarding_completed` | Activation funnel; churn prediction |
| Session | `session_started`, `session_ended`, `page_viewed` | Engagement depth; flow analysis |
| Diagnostic | `diagnostic_started`, `diagnostic_section_completed`, `diagnostic_completed` | Baseline distribution; section difficulty |
| Task | `task_started`, `task_completed`, `task_skipped` | Completion rate; task difficulty signal |
| Writing/Speaking | `writing_essay_started`, `writing_essay_submitted`, `speaking_recording_started`, `speaking_recording_completed` | Engagement; submission quality |
| Assessment | `assessment_feedback_viewed`, `ai_feedback` (rating) | AI quality; feedback comprehension |
| Resource | `resource_clicked`, `video_watched`, `video_watch_progress`, `pdf_opened`, `resource_bookmarked`, `resource_completed` | Content performance; ranking signal |
| Roadmap | `roadmap_generated`, `roadmap_phase_unlocked`, `roadmap_task_rescheduled`, `roadmap_completed` | Plan quality; scheduler health |
| Streak | `streak_updated`, `streak_milestone_reached`, `streak_broken` | Habit formation; retention |
| Mock | `mock_test_started`, `mock_section_completed`, `mock_test_completed` | Readiness; prediction calibration |
| Exam | `exam_result_entered`, `exam_result_shared` | Ground truth outcomes |
| Feedback | `feedback_submitted`, `notification_clicked` | Loop closure; engagement |

### 1.3 Explicit Feedback (Class B)

Collected per FEEDBACK_SYSTEM.md, with special attention to these signals:

| Signal | Where captured | Used by |
|---|---|---|
| AI feedback rating (1–5★) | Post-assessment widget (`ai_feedback`) | L1 AI quality, L5 prediction |
| Plan feedback rating + flags (`too_hard`, `too_easy`, `too_much_work`, `wrong_focus`) | Post-mission/roadmap prompts (`plan_feedback`) | L2 Roadmap, L4 Task difficulty |
| Feature rating (1–5★) | FAB → Rate a Feature (`feature_ratings`) | Product prioritization |
| Bug reports + severity | FAB → Report a Bug (`bug_reports`) | Reliability |
| Feature requests + votes | FAB → Suggest an Idea (`feature_requests`) | Roadmap prioritization |
| Resource rating/feedback | Resource page, completion flow | L3 Resource ranking |

### 1.4 Outcomes (Class C)

| Outcome | When captured | What it calibrates |
|---|---|---|
| Mock test band per section | Each mock submission | Band predictor (M1), readiness (M2), risk (M3), hours (M5) |
| Diagnostic retake | On demand (30-day cooldown) | Baseline drift; skill profile convergence |
| **Real exam result** | Post-exam flow | Probability model (M4), hours constant (M5), roadmap realism, assessor calibration |
| Target attainment (met/not met) | Exam result entry | Product outcome validation |
| Postponement / abandonment | Exam date change, 14-day inactivity | Scheduler edge cases; churn model |

### 1.5 Content Interactions (Class D)

| Signal | Captured via | Improvement value |
|---|---|---|
| Watch % / video completion | `video_watch_progress` (25/50/75/90%) | Content quality; drop-off diagnosis |
| Scroll depth (PDF/article) | `pdf_opened` + scroll telemetry | Content engagement |
| Bookmark rate & collections | `resource_bookmarked` | Content value signal |
| Completion rate per resource | `resource_completed` | Resource ranking weight |
| Re-open / re-view rate | `resource_views` (count, session) | Retained value signal |
| Click-through rate by position | `resource_clicked` (rank) | Recommendation position bias |

### 1.6 Performance & Quality (Class E)

| Signal | Source | Used by |
|---|---|---|
| AI response latency | Server logs on `/assess`, `/brain/*` | Model tier selection; infra |
| AI output failure rate | Error tracking | Model reliability |
| Assessment band spread vs human | Tutor spot-check queue (FEEDBACK_SYSTEM.md §5.3) | Assessor calibration |
| Prediction error | `decision_log` vs outcome | L5 band prediction |
| Feedback comprehension proxy | `assessment_feedback_viewed` time + re-open rate | L1 AI quality |

### 1.7 What is NOT Collected

| Data | Reason |
|---|---|
| Essay text / audio content in event streams | PII; stored only in `assessments` with RLS (ANALYTICS.md §8) |
| Raw keystroke-level data | No pedagogical value at scale; privacy risk |
| Email contents / payment details | Out of scope for product improvement |
| Cross-device browsing data | Not relevant to the study platform |

---

## 2. How AI Recommendations Improve

### 2.1 The Improvement Loop (Loop L1)

AI recommendations cover: writing/speaking assessments, resource recommendations, AI tips, band predictions, and roadmap generation. Each follows the same four-stage loop:

```
STAGE 1 — OUTPUT       AI produces a recommendation (band, resource, tip, prediction)
STAGE 2 — REACTION     User interacts: views feedback, rates it, ignores it, disputes it
STAGE 3 — SIGNAL       Rating (1–5★), dispute, time-on-feedback, re-open, follow-through
STAGE 4 — RETUNE       Prompt/model weights updated per signal; A/B tested; deployed
```

### 2.2 Signal Weighting

Each recommendation carries an implicit quality score computed from both explicit and implicit signals:

```
RECOMMENDATION_QUALITY = 
    0.35 × explicit_rating_norm          // ai_feedback rating (1–5 → 0–100)
  + 0.25 × follow_through               // did the user act on it? (e.g., opened the resource, did the suggested task)
  + 0.20 × engagement_depth             // time viewing feedback, number of re-opens, annotation clicks
  + 0.10 × dispute_or_negative_flag     // "This seems wrong" / rating ≤ 2
  + 0.10 × outcome_correlation          // did acting on the recommendation improve the next assessment?
```

### 2.3 Retuning Mechanisms

| Mechanism | What changes | Trigger | Cadence |
|---|---|---|---|
| **Prompt tuning** | Prompt wording, rubric emphasis, few-shot examples | Low-rated cluster (avg ≤ 2.5★ on a task type) | On threshold |
| **Model tier escalation** | `gpt-4o-mini` → `gpt-4o` for contested outputs | Repeated disputes on a task type | On threshold |
| **Scoring weight adjustment** | Ensemble weights in assessor (AI_BRAIN.md M1) | Tutor spot-check disagreement rate | Weekly |
| **Recommendation re-ranking** | Resource recommender weights (RESOURCE_ENGINE.md §5.1) | Click/rating/outcome deltas | Weekly |
| **Tip template improvement** | AI tip phrasing, length, specificity | Low engagement with tips | Monthly |

### 2.4 Dispute Handling

When a user rates an AI recommendation ≤ 2★, it enters the **dispute pipeline**:

1. **Auto-escalation**: If rating ≤ 2★ and `source_type` is an assessment → flagged for tutor spot-check (FEEDBACK_SYSTEM.md §5.3).
2. **Cluster analysis**: Comment text is mined (keyword extraction) to identify the *reason* (too harsh, too generous, didn't understand, wrong topic).
3. **Root-cause attribution**: The cluster is mapped to the likely cause — prompt ambiguity, rubric misapplication, model hallucination, or content mismatch.
4. **Targeted fix**: The fix is applied to the specific prompt/module, not globally.

### 2.5 Continuous Calibration (with AI_BRAIN.md)

The AI Brain already recalibrates prediction modules against outcomes (§7.3). The CIS extends this to recommendations:

| Recalibration | Input | Output |
|---|---|---|
| Assessor calibration | Tutor-spot-checked assessments vs AI scores | Adjust per-criterion severity |
| Prediction calibration | Mock/exam results vs predictions | Re-fit M1 ensemble weights, M4 logistic coefficients |
| Hours calibration | Exam outcome vs hours logged | Re-estimate `HOURS_PER_0_5_BAND` constant |
| Difficulty calibration | Task skip/completion data | Adjust task difficulty labels |

---

## 3. How Roadmap Quality Improves

### 3.1 What "Roadmap Quality" Means

A high-quality roadmap is one that the user **follows to target attainment** without burning out. It is measured by four outcomes:

| Quality Metric | Definition | Target |
|---|---|---|
| **Phase completion rate** | % of assigned tasks completed per phase | ≥ 80% |
| **On-track rate** | % of users whose predicted band is within ±0.5 of plan trajectory | ≥ 70% |
| **Target attainment** | % of users reaching target band at exam | As high as possible |
| **Sustainability** | % of users who reach the revision phase without a streak break ≥ 5 days | ≥ 60% |

### 3.2 The Improvement Loop (Loop L2)

```
PLAN GENERATION  →  USER FOLLOWS  →  ADHERENCE DATA  →  QUALITY SCORE  →  GENERATOR RETUNE
   (roadmap,        (task start/        (completion,        (phase rate,        (phase weights,
    daily mission)   complete, skip)     skip, re-plan)       outcome gap)         task mix, pacing)
```

### 3.3 Plan Feedback Signals

From `plan_feedback` (FEEDBACK_SYSTEM.md) and behavior:

| Signal | Meaning | Generator adjustment |
|---|---|---|
| `too_hard` flag (frequent) | Task difficulty misaligned | Lower difficulty ramp; increase foundation weight |
| `too_easy` flag (frequent) | User under-challenged | Accelerate; add advanced tasks |
| `too_much_work` flag | Overload; budget too high | Reduce daily task count; spread workload |
| `wrong_focus` flag | Skill allocation off | Re-weight skill distribution toward flagged skill |
| Task skipped > 2× same type | Specific task type disliked/difficult | Replace task type; adjust difficulty |
| Task completed suspiciously fast | Too easy OR cheating | Re-assess difficulty label |
| Phase completion < 50% + high time-elapsed | Plan too ambitious for user's capacity | Auto-compress or extend plan (SCHEDULER.md §9.2) |

### 3.4 Roadmap Versioning & A/B Testing

Every roadmap is versioned (DATABASE.md §3.2 `study_plans.version`). When the generator is retuned, new users get the new version while existing users in-progress stay on their current version (no mid-stream disruption). A/B testing compares:

| Variant | Difference | Metric | Duration |
|---|---|---|---|
| **Control** | Current generator weights | Phase completion rate | 2 weeks |
| **Treatment A** | Adjusted phase weights (e.g., more foundation) | Phase completion rate | 2 weeks |
| **Treatment B** | Different task mix per phase | Skill improvement rate | 2 weeks |

The winning variant is rolled out to 100% of new users. Losers are either abandoned or re-tuned for another test.

---

## 4. How Resource Ranking Improves

### 4.1 The Improvement Loop (Loop L3)

Resource ranking uses the RESOURCE_ENGINE.md §5.1 composite score. The CIS extends it with a feedback-driven weight adjustment:

```
RANKING → USER SEES → USER CLICKS → USER ENGAGES → OUTCOME → WEIGHT UPDATE
  (score)   (top 10)   (CTR)        (time, rate,     (skill      (skill/type/
                                    bookmark,         improvement) provider
                                    completion)                     weights)
```

### 4.2 Implicit Relevance Signals

| Signal | What it measures | Weight impact |
|---|---|---|
| Click-through rate (CTR) by position | Position-normalized (RESOURCE_ENGINE.md §5.3.4) | Increase PopularityScore component |
| Average view duration / scroll depth | Content engagement | Increase BandMatchScore |
| Completion rate | Resource finished; high value | Increase ProviderScore |
| Bookmark rate | User wants to revisit | Increase SkillGapScore for that skill |
| Re-open rate | Used as reference material | Increase SchedulerAlignmentScore |
| Skill improvement after resource | Next assessment in same skill | Increase composite score |

### 4.3 Explicit Feedback Signals

| Signal | Direct impact | Correction |
|---|---|---|
| User rates resource 1–5★ | Factor into `student_rating_avg` | Recalculate PopularityScore |
| User dismisses recommendation | `is_dismissed = TRUE` (30-day exclusion) | Reduce score for that resource |
| User reports "wrong skill" flag | Skill tag correction | Update `primary_skill` or `secondary_skills` |
| User bookmarks to a specific collection | Collection relevance signal | Increase weight for similar users |

### 4.4 Cold-Start Resource Handling

New resources (no interaction data) enter the ranking with:
- **Curator rating** (expert-curated baseline) as the popularity proxy
- **Boosted recency score** (100 for first 7 days, then decays per RESOURCE_ENGINE.md §5.2.5)
- **Skill gap match** at full weight (no penalty for missing interaction data)

After 50 user interactions, the resource transitions to data-driven ranking.

### 4.5 Position Bias Correction

Resources at position 1 get ~3× the CTR of position 5, regardless of relevance. The CIS applies **inverse position weighting** to normalize CTR:

```
normalized_ctr = actual_ctr / expected_ctr_at_position
expected_ctr_at_position = 0.3 × exp(-0.3 × position)
```

This prevents popular items from dominating the top positions simply because they are at the top.

---

## 5. How Task Difficulty Improves

### 5.1 The Improvement Loop (Loop L4)

Task difficulty is a **latent variable** — no single "correct" difficulty exists for all users. The CIS estimates it per user cohort:

```
TASK ASSIGNED → USER ATTEMPTS → COMPLETION/SKIP → DIFFICULTY → DIFFICULTY
  (at assigned    (start,        (completed,        ESTIMATE      LABEL UPDATE
   difficulty)     engage)        timed out, skip)   (IRT model)   (per cohort)
```

### 5.2 Difficulty Estimation (Item Response Theory Light)

Using a simplified 2-parameter IRT model:
- **Difficulty** (β): how hard the task is (higher = harder)
- **Discrimination** (α): how well the task distinguishes between skill levels

```
P(correct) = 1 / (1 + exp(-α × (user_skill - β)))
```

Estimates are updated per task after each completion/skip event using Bayesian updating. Tasks with fewer than 20 observations retain their initial label (curator-assigned).

### 5.3 Calibration Signals

| Signal | Interpretation | Difficulty adjustment |
|---|---|---|
| High completion rate + low skill user | Task too easy for this cohort | Increase β by 0.1 |
| Low completion rate + high skill user | Task too hard or confusing | Decrease β by 0.2 AND flag for content review |
| High skip rate (any user) | Task unappealing or unclear | Decrease β by 0.3 AND review prompt clarity |
| Low time-to-complete + high accuracy | Low cognitive load; too easy | Increase β by 0.3 |
| High time-to-complete + low accuracy | Appropriate challenge OR unclear | No change; monitor |
| Rapid completion (< 30% expected time) | Potential cheating OR too easy | Flag for review |

### 5.4 Cohort-Based Difficulty

Tasks have a **base difficulty** (β₀) and **per-cohort adjustments**:

| Cohort dimension | Adjustment basis |
|---|---|
| Current band (0–4.5, 5.0–5.5, 6.0–6.5, 7.0+) | Base difficulty aligned to band range |
| Module (Academic vs General) | Academic tasks inherently harder for some cohorts |
| Skill gap profile | Same task may be harder for users with low Lexical Resource |
| Phase (Foundation vs Advanced) | Same task gets harder label in earlier phases |

### 5.5 Difficulty Label Refresh

```
PROCEDURE RefreshDifficultyLabels():
    FOR each task with >= 20 completions in last 30 days:
        estimated_β = ComputeIRT(user_skill, completion)
        delta = ABS(estimated_β - current_β)
        
        IF delta > 0.5:
            // Significant drift — update label
            current_β = weighted_avg(current_β, estimated_β)
            LogDifficultyChange(task_id, old_β, new_β, "IRT recalibration")
        
        IF skip_rate > 0.3 AND unclear_flag_set:
            FlagForContentReview(task_id, "High skip rate — review prompt")
```

---

## 6. How Band Prediction Improves

### 6.1 The Improvement Loop (Loop L5)

Band prediction is the most calibrated module (AI_BRAIN.md M1). The CIS adds an explicit error-analysis loop:

```
PREDICTION → USER PROGRESS → OUTCOME → ERROR ANALYSIS → MODEL UPDATE
  (M1 band,    (completions,    (mock,      (error by       (weight re-fit,
   M4 prob)     assessments)     exam)       skill, phase)    prompt adjust)
```

### 6.2 Prediction Error Tracking

Every prediction is logged in `decision_log` (AI_BRAIN.md §8.1). When an outcome arrives (mock or exam), the error is computed:

```
prediction_error = ABS(predicted_band - actual_band)
```

Errors are bucketed by:

| Bucket | What it diagnoses | Action |
|---|---|---|
| Consistent over-prediction (+0.5+) | Model too optimistic; rubric too generous | Tighten rubric; reduce ensemble weight on recent assessments |
| Consistent under-prediction (-0.5+) | Model too harsh; not capturing recent improvement | Increase recent-assessment weight; relax rubric |
| High variance (no systematic bias) | Insufficient signal; user has variable performance | Increase confidence threshold; flag "highly variable" |
| Skill-specific bias | One criterion consistently off | Re-tune that criterion's prompt or weight |
| Phase-specific bias | Prediction accuracy changes by phase | Adjust phase transition logic |

### 6.3 Error Analysis Runbook

```
PROCEDURE AnalyzePredictionErrors():
    // 1. Compute overall MAE (Mean Absolute Error)
    mae = AVG(ABS(predicted_band - actual_band)) OVER last 30 days
    
    // 2. If MAE > 0.5, trigger full recalibration
    IF mae > 0.5:
        TriggerFullRecalibration()
        SendAlert("Prediction MAE exceeded 0.5 — recalibration triggered")
    
    // 3. Check per-skill bias
    FOR skill in [writing, speaking, reading, listening]:
        skill_mae = AVG(ABS(predicted_skill_band - actual_skill_band))
        IF skill_mae > 0.7:
            FlagSkillForReview(skill, skill_mae)
    
    // 4. Check calibration (M4 probability)
    //   If 60% probability → ~60% of users should achieve target
    calibration_error = ABS(actual_success_rate - predicted_probability)
    IF calibration_error > 0.10:
        RecalibrateProbabilityModel()
```

### 6.4 Model Version Promotion

| Stage | Users | Duration | Success criterion |
|---|---|---|---|
| **Shadow** | 5% of users (prediction logged, not shown) | 1 week | MAE ≤ current model |
| **Canary** | 10% of users (prediction shown) | 1 week | MAE ≤ current model; no negative feedback spike |
| **Rollout** | 50% → 100% | 1 week each | MAE stable; no regression |

If a new model version fails at any stage, it is auto-reverted and the old model retained.

---

## 7. How Content Curation Improves

### 7.1 The Improvement Loop (Loop L6)

Content curation covers both the Resource Engine catalog and the AI-generated content (prompts, tips, feedback). The loop:

```
CONTENT ADDED → USERS INTERACT → PERFORMANCE DATA → QUALITY SCORE → CURATION ACTION
  (resource,     (views,           (CTR,              (0–100,          (re-rank,
   prompt,        completions,      completion,         auto-decay,      archive,
   tip)           ratings)          bookmark)           flag)            withdraw)
```

### 7.2 Content Quality Score

Each content item (resource, prompt, tip template) has a quality score:

```
CONTENT_QUALITY = 
    0.30 × completion_rate          // % of users who finished it
  + 0.25 × avg_user_rating          // 1–5★ normalized to 0–100
  + 0.20 × engagement_depth         // avg view time / expected time
  + 0.15 × bookmark_rate            // % of viewers who bookmarked
  + 0.10 × recency                  // days since last update (decay)
```

### 7.3 Quality-Driven Actions

| Score Range | Label | Action |
|---|---|---|
| 80–100 | **Featured** | High visibility; boost in recommendations; highlight as "Top Rated" |
| 60–79 | **Standard** | Normal ranking; eligible for all placements |
| 40–59 | **Underperforming** | Reduce recommendation frequency; review for improvement |
| 20–39 | **At Risk** | Flag for curator review; archival consideration |
| 0–19 | **Archived** | Remove from active catalog; hidden from search |

### 7.4 Content Decay & Freshness

Content ages; even high-quality resources lose relevance over time:

```
CONTENT_PRIORITY = CONTENT_QUALITY × FRESHNESS_MULTIPLIER

freshness_multiplier = MAX(0.5, 1.0 - (days_since_last_review / 365))
```

- Resources older than 1 year without review: 50% priority penalty
- Resources older than 2 years: auto-flagged for re-evaluation
- Broken links (detected by daily link checker): auto-downgrade to "At Risk"

### 7.5 Content Gap Detection

The CIS identifies **content gaps** — skills or topics with insufficient high-quality resources:

```
PROCEDURE DetectContentGaps():
    FOR each skill/topic combination:
        quality_resources = COUNT(resources WHERE content_quality >= 60 AND skill = skill AND topic = topic)
        
        IF quality_resources == 0:
            EmitGapAlert(skill, topic, "No high-quality resources available")
        ELIF quality_resources < 3:
            EmitGapAlert(skill, topic, "Insufficient high-quality resources")
    
    // Also detect skill gaps from user behavior
    FOR each skill that is a top-3 weakness for > 30% of users:
        IF quality_resources < 5:
            EmitGapAlert(skill, NULL, "High demand, low supply")
```

Gap alerts are routed to the content curation team (or automated content ingestion pipeline, RESOURCE_ENGINE.md §10).

---

## 8. How User Satisfaction Improves

### 8.1 The Improvement Loop (Loop L7)

User satisfaction is the **ultimate metric** — it correlates with retention, referral, and revenue. The CIS tracks it at three levels:

| Level | Metric | Source | Target |
|---|---|---|---|
| **Episode** | Post-interaction satisfaction | Post-writing/speaking prompt (1–5★) | ≥ 4.0★ |
| **Session** | Session satisfaction | End-of-session prompt (1–5★) | ≥ 4.0★ |
| **Overall** | NPS (Net Promoter Score) | Periodic survey (0–10) | ≥ 50 |

### 8.2 Satisfaction Drivers

Based on the Five Data Classes, the CIS identifies the strongest drivers of satisfaction:

| Driver | Proxy metric | Improvement lever |
|---|---|---|
| **AI quality** | AI feedback rating | L1 — prompt tuning, model escalation |
| **Plan relevance** | Plan feedback rating | L2 — roadmap generator retune |
| **Content value** | Resource completion rate | L3, L6 — ranking, curation |
| **Task difficulty** | Task completion rate | L4 — difficulty calibration |
| **Prediction accuracy** | Prediction error | L5 — model recalibration |
| **Reliability** | Bug report count | Bug fixes, error rate reduction |
| **Speed** | AI response latency | Model tier, caching, infra scaling |
| **Support** | Support ticket resolution time | Team efficiency |

### 8.3 Satisfaction Alert System

| Trigger | Action |
|---|---|
| Episode satisfaction drops below 3.5★ for 3 consecutive days | Auto-create investigation ticket with drill-down by feature |
| NPS drops by 10+ points in a month | Full product review; user interview requests |
| "AI quality" ratings drop 0.5★ in a week | Prompt freeze; rollback last change; manual review |
| Support ticket volume spikes 2× | Categorize; prioritize top bug; update status page |

### 8.4 The Feedback-to-Fix Pipeline

```
FEEDBACK RECEIVED
  (bug report, feature request, low rating)
        │
        ▼
CATEGORIZE & PRIORITIZE
  (severity, impact, frequency)
        │
        ▼
ASSIGN & FIX
  (developer, prompt engineer, content team)
        │
        ▼
DEPLOY & NOTIFY
  (version update, changelog, user notification)
        │
        ▼
MEASURE IMPACT
  (did the fix improve the metric?)
        │
        ▼
CLOSE LOOP
  (notify reporter, update status, reward feedback)
```

---

## 9. Improvement Engine Governance

### 9.1 KPI Ownership

| KPI | Owner | Review cadence |
|---|---|---|
| AI recommendation rating (L1) | AI/ML Engineer | Weekly |
| Roadmap phase completion rate (L2) | Product Manager | Weekly |
| Resource CTR & completion rate (L3) | Content Lead | Bi-weekly |
| Task difficulty error (L4) | Curriculum Designer | Bi-weekly |
| Prediction MAE (L5) | Data Scientist | Weekly |
| Content quality score (L6) | Content Lead | Monthly |
| User satisfaction / NPS (L7) | CPO | Monthly |

### 9.2 Change Review Board

Any change that affects an improvement loop must pass through a lightweight review:

| Change type | Reviewer | Threshold |
|---|---|---|
| Prompt tweak | AI/ML Engineer | Always |
| Weight adjustment | Data Scientist | ≥ 0.05 change to any weight |
| New model version | Data Scientist + CPO | Always |
| Content curation action | Content Lead | Archive/feature decisions |
| A/B test design | Product Manager | Always |

### 9.3 Rollback Protocol

If a deployed change causes a KPI to degrade beyond threshold:

```
1. DETECT: Automated monitoring flags KPI drop > 10% in 24h
2. FREEZE: Auto-revert to previous version; no new changes to that module
3. NOTIFY: Alert owner + Change Review Board
4. DIAGNOSE: Root cause analysis (48h SLA)
5. REMEDIATE: Fix and re-deploy with enhanced monitoring
6. VERIFY: KPI recovers to baseline within 7 days
```

### 9.4 Improvement Velocity Tracking

| Metric | Definition | Target |
|---|---|---|
| **Loops active** | Number of improvement loops with recent changes | 3–5 (of 7) |
| **Time to fix** | Avg time from signal to deployed fix | ≤ 7 days for P1 |
| **A/B test throughput** | Tests completed per month | ≥ 2 |
| **Win rate** | % of A/B tests that improve the KPI | ≥ 40% |
| **Regression rate** | % of deployed changes that cause regression | ≤ 10% |

---

## 10. Database Schema Additions

### 10.1 New Tables

#### `improvement_signals`

Stores aggregated signals per improvement loop for analysis and reporting.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `loop_id` | TEXT | L1–L7 identifier |
| `signal_type` | TEXT | e.g., `ai_rating`, `plan_completion`, `ctr`, `prediction_error` |
| `signal_value` | NUMERIC | Aggregated value |
| `sample_size` | INTEGER | Number of observations |
| `period_start` | DATE | Start of aggregation period |
| `period_end` | DATE | End of aggregation period |
| `metadata` | JSONB | Additional context (skill, phase, cohort) |
| `created_at` | TIMESTAMPTZ | |

Index: `(loop_id, signal_type, period_start)`.

#### `model_versions`

Tracks deployed model versions and their performance.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `module` | TEXT | assessor | predictor | recommender | scheduler |
| `version` | TEXT | Semantic version (e.g., `v2.1.3`) |
| `status` | TEXT | shadow | canary | active | deprecated | rolled_back |
| `metrics` | JSONB | Performance metrics at deployment time |
| `deployed_at` | TIMESTAMPTZ | |
| `rolled_back_at` | TIMESTAMPTZ | |
| `deployed_by` | UUID | Admin user ID |

#### `a_b_tests`

Tracks A/B test configurations and results.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | TEXT | Human-readable test name |
| `loop_id` | TEXT | L1–L7 |
| `variant_a` | JSONB | Control configuration |
| `variant_b` | JSONB | Treatment configuration |
| `metric` | TEXT | Primary success metric |
| `status` | TEXT | planning | running | analysing | completed | cancelled |
| `user_allocation` | JSONB | Cohort assignment criteria |
| `sample_size` | INTEGER | Users per variant |
| `started_at` | TIMESTAMPTZ | |
| `completed_at` | TIMESTAMPTZ | |
| `result` | JSONB | Winner, effect size, confidence |

#### `content_quality_scores`

Per-content-item quality scores and history.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `content_type` | TEXT | resource | prompt | tip_template |
| `content_id` | UUID | Polymorphic FK |
| `quality_score` | NUMERIC(5,2) | 0–100 |
| `components` | JSONB | Individual score components |
| `score_label` | TEXT | featured | standard | underperforming | at_risk | archived |
| `computed_at` | TIMESTAMPTZ | |

### 10.2 Existing Table Modifications

| Table | New column | Purpose |
|---|---|---|
| `resources` | `quality_score` NUMERIC(5,2) DEFAULT 0 | Computed content quality (L6) |
| `resources` | `quality_label` TEXT DEFAULT 'standard' | Derived from quality_score |
| `resources` | `last_quality_reviewed_at` TIMESTAMPTZ | Freshness tracking |
| `tasks` | `difficulty_beta` NUMERIC(5,2) DEFAULT 0.0 | IRT difficulty parameter (L4) |
| `tasks` | `difficulty_alpha` NUMERIC(5,2) DEFAULT 1.0 | IRT discrimination parameter (L4) |
| `tasks` | `sample_count` INTEGER DEFAULT 0 | Observations for difficulty estimation |
| `assessments` | `ai_quality_score` NUMERIC(5,2) | Computed from RECOMMENDATION_QUALITY formula (L1) |
| `decision_bundles` | `prediction_error` NUMERIC(5,2) | Set when outcome arrives (L5) |

---

## 11. Implementation Roadmap

### Phase 1 — Foundation (Weeks 1–4)

| Task | Deliverable | Dependencies |
|---|---|---|
| Create `improvement_signals` table | Schema + migration | DATABASE.md schema |
| Create `model_versions` table | Schema + migration | — |
| Implement L1 signal collection | `ai_feedback` → signal aggregation | FEEDBACK_SYSTEM.md API |
| Implement L5 error tracking | `decision_log` + outcome → error computation | AI_BRAIN.md §8.1 |
| Dashboard for signal monitoring | Read-only view of all signals | Frontend analytics page |

### Phase 2 — Core Loops (Weeks 5–8)

| Task | Deliverable | Dependencies |
|---|---|---|
| L2 Roadmap quality computation | Phase completion rate aggregation | Scheduler integration |
| L3 Resource ranking signals | CTR, completion, bookmark tracking | RESOURCE_ENGINE.md |
| L4 Task difficulty estimation | IRT model (light) | Task completion data |
| A/B testing framework | `a_b_tests` table + cohort assignment | Phase 1 |
| First A/B test: prompt variant | Compare two prompt versions | L1 signal pipeline |

### Phase 3 — Automation (Weeks 9–12)

| Task | Deliverable | Dependencies |
|---|---|---|
| Automated retuning | Prompts/weights update on threshold | Phase 2 |
| Content quality scoring | `content_quality_scores` table + computation | L6 definition |
| Content gap detection | Alert system for missing resources | L6 definition |
| Satisfaction alert system | Automated monitoring + notifications | Phase 2 |
| Rollback automation | Auto-revert on KPI degradation | Phase 2 |

### Phase 4 — Optimization (Ongoing)

| Task | Deliverable | Dependencies |
|---|---|---|
| Run first 10 A/B tests | Measured improvement across loops | Phase 3 |
| Calibrate IRT model | Improved difficulty estimation | Phase 2 data |
| Tune satisfaction alert thresholds | Reduce false positives | Phase 3 |
| Content decay automation | Auto-archive expired resources | Phase 3 |
| Velocity tracking dashboard | Improvement velocity metrics | All phases |

---

## 12. Edge Cases

| Case | Handling |
|---|---|
| **Insufficient data for signal** | Do not trigger retuning until minimum sample size (n ≥ 30) reached |
| **Conflicting signals** | Behavior (completion rate) takes priority over feedback (rating) for retuning; feedback is used for diagnosis |
| **Single user gaming the system** | Outlier detection: user's feedback weighted less if it deviates > 3σ from cohort average |
| **Model regression** | Auto-rollback within 24h of detection; rollback is the default action |
| **A/B test inconclusive** | Extend test by 1 week; if still inconclusive, abandon and document |
| **Content quality score drops suddenly** | Check for broken link, paywall change, or content removal — auto-flag for curator |
| **Prediction error spikes for new user cohort** | Cold-start priors may be wrong; re-estimate population priors |
| **Satisfaction drops but no single driver identified** | Qualitative investigation: user interviews, session replays, support ticket analysis |
| **Improvement loops conflict** | E.g., L4 makes task easier (increases completion) but L2 wants harder tasks (improves skill). The KPI with highest impact on NPS wins. |
| **New feature lacks data** | Apply conservative defaults (no auto-tuning for 30 days post-launch) |

---

*This document defines the complete Continuous Product Improvement System for IELTS AI Coach. It is consistent with all existing design documents (ARCHITECTURE.md, DATABASE.md, ANALYTICS.md, FEEDBACK_SYSTEM.md, AI_BRAIN.md, SCHEDULER.md, RESOURCE_ENGINE.md, GAMIFICATION.md) and extends them with the feedback-driven loops that make the platform self-improving. Every interaction is a signal; every signal is acted upon; every action is measured; every measurement closes a loop.*
