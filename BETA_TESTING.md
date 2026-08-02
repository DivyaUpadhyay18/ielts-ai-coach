# IELTS AI Coach — Beta Testing Program

**Role:** Chief Product Officer & Head of Quality
**Document:** Beta Program Design
**Status:** Draft for review & approval

---

## 0. Executive Summary

The beta program is the **bridge between "it works" and "people love it."** It is a structured, time-boxed period during which a controlled group of real IELTS candidates exercises the full product, reports what breaks, tells us what they think, and shapes what we build next — all before the public launch described in LAUNCH_STRATEGY.md.

This program is deliberately **small, high-signal, and feedback-hungry**. We are not measuring *scale* in beta; we are measuring *truth* — honest reviews, real bugs, genuine engagement patterns, and unmet needs. Every tester is treated as a co-founder who gets a direct line to the team, and every piece of feedback is treated as a product requirement in waiting (consistent with FEEDBACK_SYSTEM.md §0 and LAUNCH_STRATEGY.md §4).

```
┌────────────────────────────────────────────────────────────────────┐
│                          BETA PROGRAM                              │
│                                                                    │
│  GOALS           ┌──────────┬──────────┬──────────┬──────────┐    │
│  ─────────       │ Honest   │ Find     │ Measure  │ Feature  │    │
│  Define the      │ Reviews  │ Bugs     │Engagement│ Requests │    │
│  "why"           │ + UX     │          │          │          │    │
│  ─────────       └──────────┴──────────┴──────────┴──────────┘    │
│  Instrument                                                    │
│  ─────────                                                     │
│  TESTING CHECKLIST ──► FEEDBACK QUESTIONNAIRE ──► SUCCESS      │
│  (what we exercise)    (what we ask)          METRICS           │
│                                                  (what we        │
│  ─────────                                      measure)         │
│  Decide when done                                               │
│  ─────────                                                     │
│  EXIT CRITERIA ──► OPEN BETA (LAUNCH_STRATEGY.md)               │
└────────────────────────────────────────────────────────────────────┘
```

**Key design principles:**

1. **Free-first, honest-only.** Beta testers get the full product free (no paywall, per LAUNCH_STRATEGY.md §1.2). In exchange, we ask for candor — including negative reviews.
2. **Small cohorts, rich signals.** 100–300 hand-picked users (per LAUNCH_STRATEGY.md §2.3) produce deeper qualitative data than 10,000 silent users.
3. **Instrumented from day one.** Every funnel step, every AI output, and every feedback action is measured (ANALYTICS.md + FEEDBACK_SYSTEM.md).
4. **Weekly iteration loop.** Feedback is triaged every week and shipped every week ("Ship-It Friday," LAUNCH_STRATEGY.md §9.5). Testers see their feedback become product.
5. **Exit criteria gate the launch.** The program does not end on a calendar date; it ends when reliability, quality, engagement, and AI-quality gates are all met (LAUNCH_STRATEGY.md §2.4).

---

## 1. Program Goals

### 1.1 Goal Map

| # | Goal | What success looks like | Primary source of truth |
|---|---|---|---|
| G1 | **Collect honest reviews** | Testers give candid ratings and written feedback (positive *and* negative); sentiment is actionable, not empty praise | Feedback questionnaire, NPS, AI/plan rating widgets, exit survey |
| G2 | **Find bugs** | Bugs are reported with repro steps and telemetry; P0/P1 are found *before* public launch | Bug reports, telemetry, crash logs, daily standup triage |
| G3 | **Measure engagement** | We know exactly where users drop off, what they repeat, and what they ignore | Activation funnel, cohort retention, DAU/WAU, mission completion |
| G4 | **Collect feature requests** | Requests are deduplicated, voted, and triaged into the roadmap; top requests are shipped during beta | Feature request board, votes, weekly triage |
| G5 | **Improve UX** | Friction points are identified and removed; aha-moments are strengthened; activation improves week over week | Session recordings, funnel analysis, qualitative interviews |

### 1.2 Goal → Deliverable Mapping

Each goal maps to a concrete deliverable produced *by* the beta program:

| Goal | Deliverable produced |
|---|---|
| G1 | A prioritized **sentiment report** (what users love, what they tolerate, what they hate) |
| G2 | A **bug backlog** with severity, repro, and fix status; zero open P0/P1 at exit |
| G3 | A **funnel + retention report** with per-step conversion and cohort curves |
| G4 | A **prioritized feature roadmap** derived from real user votes and requests |
| G5 | A **UX change log** — every friction fix shipped and its measured impact |

### 1.3 Non-Goals

The beta program is explicitly **not** for:

- Monetization testing (deferred until post-launch gates are met — LAUNCH_STRATEGY.md §9.4).
- Marketing-scale acquisition (that is Open Beta / Phase 2).
- Perfection — we ship small, learn, and iterate (LAUNCH_STRATEGY.md §1.2 rule 3).
- Testing features we are not willing to keep free forever.

---

## 2. Cohorts & Roles

### 2.1 Cohort Design (per LAUNCH_STRATEGY.md §2.3)

The beta cohort is a **stratified sample** of the target market, not a random one:

| Dimension | Mix | Why |
|---|---|---|
| **Starting band** | ~40% Beginner (4.0–5.0) · ~35% Intermediate (5.5–6.5) · ~25% Advanced (7.0+) | Exercise the diagnostic, roadmap, and AI assessment across ability levels |
| **Module** | ~75% Academic · ~25% General Training | Verify module-specific content and prompts |
| **Device** | ~70% mobile · ~25% desktop · ~5% tablet | Match target device mix (LAUNCH_STRATEGY.md §1.3); surface mobile-only bugs |
| **Geography** | Primary markets: India, Vietnam, China, Middle East, Latin America, Nigeria | Timezone/browser/network variance; localization signal |
| **Commitment** | Mix of "daily" (30+ min/day) and "casual" (3×/week) users | Exercise scheduler under different load patterns |
| **Familiarity** | Mix of first-time IELTS and retakers | Onboarding friction vs. feature depth feedback |

**Target size:** 100–300 active testers (LAUNCH_STRATEGY.md §2.3). We over-recruit ~30% to account for attrition.

### 2.2 Tester Personas

| Persona | Profile | What we learn from them |
|---|---|---|
| **The Beginner** | Band 4–5, first attempt, anxious | Onboarding clarity, diagnostic understandability, motivation design |
| **The Busy Professional** | Band 6, 45 min/day, time-poor | Scheduler realism, daily mission fit, notification usefulness |
| **The Power User** | Band 7+, preparing for a high target | AI feedback depth, advanced features, analytics usefulness |
| **The Retaker** | Already took the exam, needs a specific band | Roadmap differentiation, mock test fidelity, band prediction trust |
| **The Skeptic** | Tried other IELTS apps, easily disappointed | Product credibility, AI accuracy perception, NPS anchor |

### 2.3 Program Roles

| Role | Responsibility |
|---|---|
| **Beta Lead (CPO)** | Owns the program; weekly triage; final exit-criteria sign-off |
| **QA Engineer** | Runs the testing checklist; reproduces bugs; verifies fixes; maintains bug backlog |
| **Community Manager** | Recruits testers; runs Discord; moderates; channels feedback into the queue |
| **Data Analyst** | Instruments metrics; builds funnel/retention reports; surfaces anomalies |
| **Product Manager** | Converts feedback into requirements; manages the public roadmap |
| **AI/ML Engineer** | Monitors AI feedback ratings; tunes prompts on low-rated clusters |
| **Testers (the users)** | Use the product as they naturally would; report honestly |

---

## 3. Testing Checklist

The testing checklist is the **structured exercise plan** — it ensures the entire user journey and every critical feature is exercised, in the right order, and with clear pass criteria. It is used by QA for regression sweeps and by testers as a guided task list.

### 3.1 Journey Coverage Matrix

Every screen from the user journey (USER_JOURNEY.md) is covered:

| # | Area / Screen | Key test actions | Pass criteria |
|---|---|---|---|
| 1 | **Landing Page** | Load, scroll all sections, click all CTAs, test on mobile/desktop | All CTAs route correctly; no layout breakage; fast load |
| 2 | **Registration** | Email signup, Google OAuth, validation errors, duplicate email, weak password | Account created; errors shown inline; session established |
| 3 | **Email Verification** | Verify link, resend, unverified login attempt | Verified users can log in; unverified users see a clear message |
| 4 | **Login** | Email login, Google login, forgot password, wrong password, rate-limit | Login succeeds/fails gracefully; reset email sent |
| 5 | **Onboarding** | Profile fields, target band, exam date, module, daily commitment, skip path | Profile saved; defaults applied on skip; warnings for <30d and >1yr exam dates |
| 6 | **Diagnostic — Writing** | Timer, word count, min-word validation, submit, auto-submit on expiry | Essay submits; word count enforced; timer behaves |
| 7 | **Diagnostic — Speaking** | Mic permission, record/stop, min-duration, retry, fallback | Recording uploads; transcript appears; permission-denied handled |
| 8 | **Diagnostic — Vocabulary** | Answer 10 questions, navigate, early submit, timer expiry | Score computed; unanswered counted wrong; progress shown |
| 9 | **Diagnostic Results** | Score display, skill bars, strengths/weaknesses, AI tip, PDF download, roadmap CTA | All data renders; PDF downloads; CTA triggers generation |
| 10 | **Roadmap Generation** | Loading state, phases, task cards, locked phases, goal flag | Roadmap generates; phases reflect diagnostic; tasks link to correct pages |
| 11 | **Dashboard** | Greeting, stats grid, today's tasks, quick actions, recent assessments, resources | All widgets load from live data; task checkbox updates; streak shows |
| 12 | **Daily Mission** | Task list, task completion, study timer, carry-forward badge, rest day, celebration | Tasks complete and persist; overdue tasks flagged; timer tracks |
| 13 | **Writing Practice** | Prompt, editor, word count, submit, AI feedback overlay, annotations, edit-again | Essay submits; feedback shows band + criteria; annotate view works |
| 14 | **Speaking Practice** | Prompt, record, waveform, transcript, replay, part navigation | Recording works; transcript streams; parts advance |
| 15 | **Progress & Analytics** | Stats grid, band trend chart, skill gaps, study-time distribution, history table, export | Charts render; data matches history; export downloads |
| 16 | **Mock Tests** | Full mock: listening/reading/writing/speaking, timers, submit, post-mock review | All sections run; timers enforced; results saved; review shows mistakes |
| 17 | **Resources** | Browse, filter, search, view, bookmark, completion, dismiss | Filters work; bookmarks save; completion tracked |
| 18 | **Notifications** | List, mark read, click-through, preferences | Notifications render; actions navigate; prefs persist |
| 19 | **Profile & Settings** | Edit profile, change goals, timezone, notifications, plan | Changes persist; scheduler respects new timezone |
| 20 | **Feedback System** | Rate a feature, report a bug, suggest an idea, rate AI output, rate plan | Each flow submits; XP rewarded; status visible in "My Feedback" |

### 3.2 Cross-Cutting Checklist (Every Build)

These checks run on **every release candidate** before it reaches testers:

| # | Check | Detail |
|---|---|---|
| C1 | **Build health** | `next lint` clean; TypeScript compiles; backend tests pass |
| C2 | **Smoke test** | Signup → diagnostic → roadmap → mission completes without a blocker |
| C3 | **Regression sweep** | Re-run the 20-item journey matrix on the 3 most-used devices |
| C4 | **AI quality spot-check** | 10 random assessments reviewed by a tutor; avg rating ≥ 4/5 |
| C5 | **Performance** | Page load ≤ 2.5s on 4G; assessment results ≤ 60s median (LAUNCH_STRATEGY.md §2.4) |
| C6 | **Data integrity** | No RLS leaks; streaks/XP ledger consistent; no PII in telemetry |
| C7 | **Accessibility pass** | Keyboard navigation, screen-reader labels, contrast on key screens |
| C8 | **Changelog** | "What's new" note written and in-app changelog updated |

### 3.3 Test Task Allocation

| Tester type | Exercises |
|---|---|
| **All testers** | 1–5 (core journey), 11–15 (daily usage), 20 (feedback) |
| **QA + assigned testers** | 6–10 (diagnostic + roadmap), 16 (mock tests), 17–18 (resources/notifications) |
| **Spot assignment** | Each new release assigns 5–10 testers to re-test a specific changed area |
| **Free exploration** | Every tester is encouraged to wander outside the checklist — novel paths find novel bugs |

### 3.4 Bug Report Template (used in-app, per FEEDBACK_SYSTEM.md §2.2)

```
What were you trying to do?
[one line]

What happened instead?
[description]

Steps to reproduce:
1. ...
2. ...

Expected behavior:
[what should have happened]

Severity:
[ ] P0 Blocker — can't use the app at all
[ ] P1 Critical — core action broken for me
[ ] P2 Major — feature degraded but usable
[ ] P3 Minor — cosmetic / edge case
[ ] P4 Trivial — polish

Device / Browser / OS:
[auto-captured with telemetry]

Screenshot / recording:
[optional attach]
```

---

## 4. Feedback Questionnaire

The questionnaire is the **structured voice of the beta** (G1 + G4 + G5). It is deliberately short (3–5 questions per survey, per LAUNCH_STRATEGY.md §4.2), timed to moments of truth, and always includes an open-text field.

### 4.1 Survey Cadence & Placement

| Survey | When | Length | Primary goals |
|---|---|---|---|
| **Welcome Survey** | Immediately after signup | 3 questions | Segmentation (band, target, device), expectation setting |
| **Post-Diagnostic** | Right after diagnostic results | 4 questions | First-impression sentiment, diagnostic clarity, aha-moment check |
| **Week-1 Check-in** | Day 7 | 5 questions | Onboarding friction, first-week experience, roadmap feel |
| **AI Feedback Rating** | After every AI output (embedded) | 1–2 taps | AI quality (G1), per FEEDBACK_SYSTEM.md §4.6 |
| **Plan Rating** | After roadmap / daily mission | 1–2 taps + flags | Scheduler fit (G3, G5), per FEEDBACK_SYSTEM.md §4.7 |
| **Weekly Pulse** | Every Friday | 4 questions | Trending sentiment, top friction, feature request prompt |
| **Mid-Beta Review** | Week 4 | 6 questions | Deep UX review, NPS, feature priorities |
| **Exit Survey** | At program close / churn | 5 questions | Why stay / why leave; what would make it a must-have |

### 4.2 Core Question Bank

**Segmentation (Welcome)**
1. What band are you currently at? [4.0–5.0] [5.5–6.5] [7.0+] [Not sure]
2. What band do you need? [___]
3. When is your exam? [___]
4. How many minutes/day can you study? [<30] [30–60] [60–120] [120+]
5. Which module? [Academic] [General Training]

**Onboarding & First Impressions (Post-Diagnostic)**
1. How would you rate the signup/onboarding process? ★★★★★ (1 = frustrating, 5 = effortless)
2. Did the diagnostic feel accurate for your level? [Too hard] [About right] [Too easy] [Not sure]
3. How clear was your diagnostic report? ★★★★★
4. "What was the single most useful thing you've seen so far?" [open text]
5. "What almost made you quit?" [open text]

**Week-1 & Roadmap (Week-1 Check-in)**
1. Does your study plan feel realistic for your schedule? [Too much] [Just right] [Too little] [Wrong focus]
2. Are the daily missions the right mix of skills? ★★★★★
3. Did you complete any task you *hadn't planned* to try? [Yes — which?] [No]
4. "What's the biggest thing we could improve this week?" [open text]
5. NPS: "How likely are you to recommend IELTS AI Coach?" (0–10)

**AI Quality (Embedded Rating — per FEEDBACK_SYSTEM.md §4.6)**
1. Was this feedback helpful? ★★★★★
   - If ≤ 2★: [Too harsh] [Too generous] [Didn't understand] [Wrong topic] [Other]
2. Optional: "What did it get right or wrong?" [open text]

**Plan Quality (Embedded Rating — per FEEDBACK_SYSTEM.md §4.7)**
1. Was today's plan the right amount of work? ★★★★★
2. Quick flags: [Good pace] [Too much work] [Too easy] [Too hard] [Wrong focus]
3. Optional: [open text]

**Weekly Pulse (Friday)**
1. Compared to last week, the product feels… [Better] [Same] [Worse]
2. What's your favorite thing this week? [open text]
3. What's your biggest frustration this week? [open text]
4. "If you could change one thing about the app, what would it be?" [open text] → auto-suggests creating a feature request

**Mid-Beta Review (Week 4)**
1. Rate each: Diagnostic / Roadmap / Daily Missions / Writing feedback / Speaking practice / Analytics ★★★★★ each
2. "Which feature would you be sad to lose?" [open text]
3. "Which feature do you ignore?" [open text]
4. "What's missing that would make this a complete IELTS solution?" [open text]
5. NPS: (0–10)
6. "Are you on track to hit your target band?" [Yes] [No — why?]

**Exit Survey (Close or Churn)**
1. Why are you leaving / wrapping up? [Reached goal] [Too busy] [Found something better] [Product doesn't meet needs] [Other]
2. "What would bring you back / make you stay?" [open text]
3. NPS: (0–10)
4. "What did we do best?" [open text]
5. "What did we do worst?" [open text]

### 4.3 Survey Design Rules (enforced)

| Rule | Detail |
|---|---|
| **≤ 5 questions** | Longer surveys kill response rates (LAUNCH_STRATEGY.md §4.2) |
| **Always one open field** | The richest signal is free text |
| **In-the-moment timing** | Post-diagnostic survey beats "survey next week" |
| **Dismissible** | "Not now" is always available; never nag |
| **Rewarded** | Feedback grants XP (5 XP per rating, 15 XP per bug — FEEDBACK_SYSTEM.md §2.9) |
| **Loop-closed** | Testers who give detailed feedback are invited to a 15-min interview (free roadmap review as thanks) |

### 4.4 Qualitative Interviews (Weekly, per LAUNCH_STRATEGY.md §4.3)

| Who | How many | Focus |
|---|---|---|
| New testers (day 1–7) | 2–3 / week | Onboarding friction, aha-moments, confusion |
| Churned testers | 1–2 / week | Why they left; what would bring them back |
| Power users (≥ 20 missions) | 1–2 / week | What to deepen; superfan behaviors |
| IELTS tutors (paid advisors) | 1 / month | AI feedback quality, pedagogical gaps |

Every interview → 3–5 "insight bullets" → posted to the feedback board → triaged with the weekly queue.

---

## 5. Success Metrics

Metrics map 1:1 to the five goals. All are instrumented via ANALYTICS.md event taxonomy and the FEEDBACK_SYSTEM.md tables.

### 5.1 Goal-to-Metric Matrix

| Goal | Primary metrics | Targets (during beta) |
|---|---|---|
| **G1 Honest reviews** | NPS; avg AI-feedback rating; avg plan rating; feedback volume; review depth (comments submitted) | NPS ≥ 50 by exit; AI rating ≥ 4.2/5; plan rating ≥ 4.0/5; ≥ 8 feedback items / 100 active users / week |
| **G2 Find bugs** | Bug count by severity; P0/P1 open at any time; time-to-fix; report→verified rate | ≥ 95% of testers exercise the journey; zero open P0/P1 at exit; median report→fix ≤ 7 days |
| **G3 Measure engagement** | Activation funnel conversion; D1/D7/D30 retention; DAU/WAU; missions/week; median study minutes; streak rate | Activation ≥ 40% (signup→1st mission); D30 retention ≥ 25% (guardrail); DAU/WAU ≥ 0.25; missions ≥ 3/week/active user |
| **G4 Feature requests** | Request count; unique request count (post-dedupe); votes/request; shipped-request rate; % of roadmap from beta feedback | ≥ 50 unique requests; ≥ 10 shipped during beta; ≥ 60% of shipped items traceable to feedback |
| **G5 Improve UX** | Funnel-step conversion week-over-week; friction-point count; interview insight count; UX-fix impact (conversion delta) | Every weak funnel step improved week-over-week; ≥ 15 UX fixes shipped and measured |

### 5.2 Activation Funnel (from LAUNCH_STRATEGY.md §3.2)

```
Visit landing → Sign up (goal ≥ 40%)
Sign up → Complete onboarding (goal ≥ 70%)
Onboarding → Start diagnostic (goal ≥ 85%)
Diagnostic → Finish diagnostic (goal ≥ 60%)
Diagnostic → Generate roadmap (goal ≥ 90%)
Roadmap → Complete first daily mission (goal ≥ 70%)
Complete 3 missions in week 1 (goal ≥ 50%)
```

Every step is instrumented. Any step below target becomes the next iteration sprint's focus.

### 5.3 Reliability & Quality Gates (from LAUNCH_STRATEGY.md §2.4)

| Gate | Beta target | Measured by |
|---|---|---|
| Uptime | ≥ 99.5% for 14 consecutive days | Monitoring |
| Performance | Page load ≤ 2.5s on 4G; assessment ≤ 60s median | RUM / backend logs |
| AI quality | Writing/speaking feedback ≥ 4/5 | `ai_feedback` |
| Core bugs | Zero P0/P1 open | Bug tracker |
| Support | Mods trained; bug flow tested | Community ops |
| Activation | ≥ 50% first-run activation | Funnel |

### 5.4 Funnel Health & Weekly Review (per LAUNCH_STRATEGY.md §5.3)

Every Monday, the team reviews:
1. **Activation funnel** — where are we losing testers?
2. **Cohort retention curves** — is retention improving with each ship?
3. **Feedback board** — what was asked, what shipped, what's the sentiment?
4. **AI quality spot-checks** — 10 random assessments reviewed by a tutor.
5. **Infrastructure health** — uptime, error rate, latency.
6. **Bug backlog** — new, triaged, fixed, verified counts by severity.

---

## 6. Launch Timeline

### 6.1 Beta Timeline (aligned to LAUNCH_STRATEGY.md §2.1)

```
Week -6 to -4   PHASE 0: PRIVATE ALPHA (Internal)
                • ~25 internal testers (team + 3–5 paid IELTS tutors)
                • Prove the core loop end-to-end; no embarrassing bugs
                • Exit: journey completion ≥ 95% w/o blocker; AI ≥ 4/5 by tutors

Week -4 to -2   PHASE 0.5: ALPHA→BETA PREP
                • Recruit beta cohort (waitlist + community outreach)
                • Instrument all funnel/metrics; stand up feedback tools
                • Write weekly triage process; train mods

Week -2 to 0    PHASE 1: CLOSED BETA — WAVE 1 (First 100–150)
                • Onboard wave 1 (stratified cohort)
                • Full testing checklist sweep (QA + testers)
                • Baseline metrics captured (Week 0 = baseline)

Week 1–2        ITERATION SLOOP 1
                • Weekly triage + Ship-It Friday #1, #2
                • First qualitative interviews; first UX fixes ship

Week 3–4        PHASE 1b: CLOSED BETA — WAVE 2 (Next 150)
                • Expand to full 300; re-run checklist on new builds
                • Mid-Beta Review survey (Week 4); NPS baseline

Week 5–8        ITERATION SLOOPS 3–6
                • Continue weekly ship cycles
                • Target: all funnel steps ≥ threshold; P0/P1 = 0
                • AI quality sustained ≥ 4.2/5

Week 9–10       STABILIZATION & GATE REVIEW
                • Full regression sweep; performance test on 4G
                • Exit criteria assessment (see §7)

Week 10+        OPEN BETA (Public Launch) — per LAUNCH_STRATEGY.md §2.4
                • Gates met → open to everyone
                • Beta testers become founding community members
```

### 6.2 Milestones & Gates

| Milestone | When | Gate to proceed |
|---|---|---|
| **M1 Alpha complete** | Week -4 | Core journey ≥ 95% without blocker; AI ≥ 4/5 (tutor-rated) |
| **M2 Wave-1 baseline** | Week 0 | 100+ active testers; all metrics instrumented; baseline captured |
| **M3 First ship** | Week 1 | ≥ 1 feedback-driven release shipped |
| **M4 Wave-2 on board** | Week 4 | 300 total testers; mid-beta survey complete |
| **M5 Funnel green** | Week 8 | All activation steps ≥ target; D30 retention ≥ 25% |
| **M6 Zero-P1** | Week 9 | No open P0/P1; AI ≥ 4.2/5 sustained 2 weeks |
| **M7 Open beta** | Week 10+ | All exit criteria met (below) |

### 6.3 Release Cadence During Beta

```
Every Week:
  Mon — Review KPIs + cohort curves; triage feedback; select sprint items
  Tue–Thu — Build & ship small, focused batches
  Fri — Ship-It Friday: changelog + "what we shipped because of you"
Every Month:
  Deep-dive retention; tutor audit of AI quality; strategy reset
```
(Consistent with LAUNCH_STRATEGY.md §9.5.)

---

## 7. Exit Criteria

The beta program **ends when it has proven the product is ready for public launch** — not when the calendar says so. The exit criteria below are the **release gates** from LAUNCH_STRATEGY.md §2.4, expanded with beta-specific evidence requirements.

### 7.1 Gate Table

| # | Gate | Requirement | Evidence |
|---|---|---|---|
| E1 | **Reliability** | Uptime ≥ 99.5% for 14 consecutive days | Monitoring dashboard |
| E2 | **Performance** | Page load ≤ 2.5s on 4G; assessment results ≤ 60s median | RUM + backend latency |
| E3 | **AI quality** | Writing/speaking feedback rated ≥ 4.2/5 (avg, last 14 days) | `ai_feedback` table |
| E4 | **Core bugs** | Zero open P0/P1; P2 resolved or scheduled | Bug tracker |
| E5 | **Activation** | First-run activation ≥ 50%; funnel steps ≥ LAUNCH_STRATEGY targets | Funnel analytics |
| E6 | **Engagement** | D30 retention ≥ 25%; missions ≥ 3/week/active user; DAU/WAU ≥ 0.25 | Cohort + usage analytics |
| E7 | **Feedback loop** | ≥ 8 feedback items / 100 active users / week; median report→fix ≤ 7 days | Feedback + bug tables |
| E8 | **Feature signal** | ≥ 50 unique requests triaged; top 10 requests planned or shipped | Request board |
| E9 | **UX validated** | No unidentified friction blocking any funnel step; interview insights resolved | Funnel + interview log |
| E10 | **Honest reviews** | NPS ≥ 50; exit-survey completion ≥ 60% of leavers | NPS + exit surveys |

### 7.2 Decision Framework

```
FOR each gate E1–E10:
    IF met → record as PASS
    IF not met → record as FAIL with owner + fix action

AFTER review of all gates:
    ALL PASS → OPEN BETA (public launch)
    ≥ 1 FAIL but no P0/P1 and E3–E6 within 10% → CONDITIONAL PASS
              (open with a documented risk list + review in 2 weeks)
    Otherwise → EXTEND BETA (re-run iteration loop; re-assess in 2 weeks)
```

### 7.3 Beta Completion Checklist (Sign-off)

- [ ] All 10 gates documented with evidence
- [ ] Bug backlog: zero open P0/P1; P2 scheduled with owners
- [ ] Funnel report: every step ≥ target, or a documented fix in the sprint
- [ ] AI quality: tutor-audit log maintained; rating ≥ 4.2/5
- [ ] Feature roadmap: beta requests triaged; top items planned/shipped
- [ ] UX log: all identified friction points closed or scheduled
- [ ] Tester communication: every tester notified of program outcome + thanked
- [ ] Beta rewards granted (badges, founder shout-outs, early-access perks)

### 7.4 Handoff to Open Beta

At exit, the program hands over to LAUNCH_STRATEGY.md §2.4 (Open Beta):

1. **Testers → community**: Beta badge, early-adopter roles in Discord, "founding member" status.
2. **Bug backlog → triage queue**: P0/P1 must be zero; P2+ carry into normal triage.
3. **Metrics → KPI dashboard**: Funnel, retention, and quality dashboards continue into launch.
4. **Roadmap → public roadmap**: Beta feature requests migrate to the public board with statuses.
5. **Feedback channels → production**: In-app feedback, NPS, and exit surveys remain live.

---

## 8. Governance & Reporting

### 8.1 Weekly Triage Ritual (per LAUNCH_STRATEGY.md §4.4)

| Signal | Action |
|---|---|
| 1 passionate complaint | Investigate; respond within 24h; fix if valid |
| 3+ similar complaints | Escalate to a sprint item this week |
| Repeated praise of a hack/workaround | Turn the hack into a feature |
| Confusion on a screen | Watch session recordings (with consent); redesign |
| Feature request + 10 upvotes | Add to public roadmap for voting |

### 8.2 Bug Severity & SLA (per LAUNCH_STRATEGY.md §6.2)

| Severity | Definition | Response SLA | Fix SLA |
|---|---|---|---|
| **P0 — Blocker** | Prevents all users from a core action | 1 hour | 24 hours (hotfix) |
| **P1 — Critical** | Prevents a subset from a core action; data loss | 4 hours | 3 days |
| **P2 — Major** | Core feature degraded but usable | 24 hours | 1 week |
| **P3 — Minor** | Cosmetic, edge case | 3 days | Next sprint or backlog |
| **P4 — Trivial** | Polish, typo | 1 week | Backlog |

### 8.3 Weekly Report Template

```
BETA REPORT — Week N
──────────────────────────────────────────────────────
Testers: active / total · churned this week
Funnel: signup→activation %, each step vs target
Retention: D1/D7/D30 for latest cohort
Engagement: DAU/WAU · missions/user/week · median minutes
AI quality: avg rating · low-rated clusters · tutor spot-check
Bugs: new / open P0 / P1 / P2 · fixed · verified
Feedback: items/100 users · top 3 asks · shipped this week
UX: friction found · interviews done · fixes shipped
Risk: top 3 risks + owner + action
Exit gates: E1–E10 status (PASS/FAIL)
──────────────────────────────────────────────────────
```

### 8.4 Communication with Testers

| Channel | Content | Cadence |
|---|---|---|
| **Discord #announcements** | Release notes, "you asked, we shipped," known issues | Per ship |
| **Weekly email** | Summary of what changed, what's next, thanks | Weekly |
| **In-app changelog** | "What's new this week" banner | Per ship |
| **Direct DMs** | For P0 reporters, interview invites, personal thanks | As needed |
| **Public roadmap** | Feature request statuses, votes, ship dates | Live |

---

## 9. Edge Cases & Risk

### 9.1 Edge Cases

| Case | Handling |
|---|---|
| Tester never completes diagnostic | Targeted nudge (notification) at day 3/7; if inactive 14 days, mark churned and run exit survey |
| Tester reports the same bug as others | Dedupe by text hash (24h window) → prompt "already reported" + link (FEEDBACK_SYSTEM.md §7) |
| Tester rates AI feedback 1★ without comment | Prompt once "mind telling us why?" (dismissible); flag for tutor spot-check |
| Tester breaks a core flow | Treat as P0; hotfix within 24h; notify all testers of the fix |
| Tester only uses one feature | Segment their feedback as "power-user of X"; interview to understand why they ignore the rest |
| Tester asks for a paid feature | Log as feature request; explain free-first stance; no premature monetization |
| Tester's exam date passes during beta | Post-exam flow (result entry / reflection) becomes a test case; capture outcome signal |
| Telemetry contains PII | Sanitize by default; user opts in to include content (FEEDBACK_SYSTEM.md §7) |
| Feedback volume overwhelms the team | Triage by severity/votes first; cluster before reading; batch interview insights |
| Tester churns during a broken release | Exit survey; fix the bug; invite them back with a personal apology + perk |
| New build introduces regression | Instant rollback to previous build; QA re-runs cross-cutting checklist C1–C8 |

### 9.2 Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Low tester activity → weak signal | Medium | High | Over-recruit 30%; weekly nudges; engagement-based perks; interviews |
| AI feedback quality inconsistent | Medium | High | Tutor audit loop; confidence labels; prompt tuning on low-rated clusters |
| Beta drags on without exit | Medium | Medium | Fixed 10-week target; gate review at week 9; extension requires explicit sign-off |
| Testers become "professional feedback-givers" (not real users) | Low | Medium | Use the product naturally; engagement metrics tracked; interviews probe authenticity |
| Too many P2/P3 bugs overwhelm sprint | High | Medium | Severity discipline; P2 scheduled, P3/P4 backlogged; fix-by-severity triage |
| Scaling AI costs during free beta | Medium | High | Model tiering; caching; per-user caps; monitor cost/user weekly (LAUNCH_STRATEGY.md §11) |
| Tester expectations exceed scope | Medium | Medium | Onboarding sets expectations ("early co-founder, rough edges"); public roadmap shows progress |

---

## 10. Conclusion

The beta program is **the product's first real test with real people**. It converts the theoretical design documents into observed truth: does the diagnostic wow? Does the roadmap feel right? Does the AI feedback earn trust? Does the scheduler keep people coming back?

When the program exits, we will know:

- **What users love** (and what we double down on),
- **What breaks** (and that the public launch is clean),
- **How users engage** (and where the funnel leaks),
- **What users want** (and what ships next),
- **How the UX feels** (and where we removed the friction).

The exit criteria in §7 are the contract: **we do not open the doors until the product deserves it.** When we do, the beta testers become our founding community — the first advocates, the first ambassadors, and the proof that IELTS AI Coach is built by listening.

---

*This document is the complete design for the IELTS AI Coach Beta Testing Program. It is consistent with LAUNCH_STRATEGY.md (beta phases §2, activation funnel §3.2, success metrics §5, bug severity §6, iteration cadence §9.5), FEEDBACK_SYSTEM.md (feedback types, questionnaire placement, XP rewards, triage), ANALYTICS.md (event taxonomy, funnel instrumentation), and GAMIFICATION.md (tester rewards). It defines what we test, what we ask, what we measure, when we ship, and when we are done.*

