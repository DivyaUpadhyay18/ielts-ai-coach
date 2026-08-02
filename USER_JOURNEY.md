# Complete User Journey — IELTS AI Coach

**Role:** Chief Product Architect  
**Document:** Full User Journey Design  
**Status:** Draft for review & approval  

---

## 0. Journey Map Overview

```
LANDING PAGE
    │
    ▼
REGISTRATION ───────────────────────────────────────────────┐
    │                                                        │
    ▼                                                        │
LOGIN ─── (Forgot Password → Reset Email → Login)           │
    │                                                        │
    ▼                                                        │
ONBOARDING (Profile Setup)                                    │
    │                                                        │
    ▼                                                        │
DIAGNOSTIC TEST ─────────────────────────────────────────────┤
    │                                                        │
    ├── Writing Section                                       │
    ├── Speaking Section                                      │
    └── Vocabulary Section                                    │
    │                                                        │
    ▼                                                        │
DIAGNOSTIC RESULTS ──────────────────────────────────────────┤
    │                                                        │
    ▼                                                        │
ROADMAP GENERATION ──────────────────────────────────────────┤
    │                                                        │
    ▼                                                        │
DASHBOARD (Home) ────────────────────────────────────────────┤
    │                                                        │
    ├── Today's Missions                                      │
    ├── Quick Actions (Writing, Speaking)                     │
    ├── Streak & Progress Widgets                             │
    └── Recommended Resources                                 │
    │                                                        │
    ▼                                                        │
DAILY MISSION ───────────────────────────────────────────────┤
    │                                                        │
    ├── Task 1: Writing Practice  ──► Writing Assessment     │
    ├── Task 2: Speaking Drill   ──► Speaking Assessment     │
    ├── Task 3: Vocabulary Study ──► Resource Completion     │
    └── Task 4: Grammar Drill    ──► Resource Completion     │
    │                                                        │
    ▼                                                        │
PROGRESS & ANALYTICS ────────────────────────────────────────┤
    │                                                        │
    ├── Band Score Trend (Line Chart)                         │
    ├── Skill Gap Analysis (Radar / Bar)                      │
    ├── Study Time Distribution (Pie)                         │
    ├── Streak Calendar                                       │
    └── Predicted Band vs Target                              │
    │                                                        │
    ▼                                                        │
MOCK TESTS (Scheduled by Adaptive Scheduler) ────────────────┤
    │                                                        │
    ├── Pre-Mock Preparation (Light Review Day)                │
    ├── Full Mock Test (Writing + Speaking + Reading + Listening)
    ├── Post-Mock Review (Mistake Analysis)                    │
    └── Re-calibration of Roadmap                             │
    │                                                        │
    ▼                                                        │
FINAL EXAM PREPARATION ──────────────────────────────────────┤
    │                                                        │
    ├── Revision Phase (Protected, Last 14 Days)              │
    ├── Final Strategy Review                                  │
    │                                                        │
    ▼                                                        │
POST-EXAM ───────────────────────────────────────────────────┘
    ├── Result Entry
    ├── Score Reflection
    └── Next Steps (Retake? New Goal?)
```

---

## 1. Landing Page

### Purpose
The entry point for all users. Converts visitors into registered users by communicating the value proposition of AI-powered IELTS coaching.

### User State
- **Pre-authentication**: Anonymous visitor
- **Entry sources**: Direct URL, Google search, social media, referral

### Screen Sections

| Section | Content | Purpose |
|---|---|---|
| **Hero** | Headline: "Master the IELTS with your Personal AI Coach"; Subheadline with value prop; CTA buttons ("Start Free Practice", "View Sample Feedback") | Capture attention, drive signup |
| **Social Proof** | Star rating (5/5), "Trusted by 10,000+ students worldwide" | Build credibility |
| **Features Grid** | 6 feature cards: Writing Evaluation, Speaking Simulator, Progress Analytics, Natural Conversations, Instant Feedback, Band 9.0 Strategy | Explain product capabilities |
| **How It Works** | 3-step process: Choose a Task → Complete Practice → Get AI Analysis | Simplify the concept |
| **Testimonials** | 3 student success stories with name, band score, quote | Social proof, aspirational |
| **FAQ** | 3–5 common questions (accuracy, cost, General vs Academic) | Address objections |
| **Final CTA** | "Ready to hit your target score?" with "Get Started for Free" button | Final conversion push |
| **Footer** | Links to Privacy, Terms, Cookies, Contact | Legal compliance |

### Inputs
- None (static page)

### Outputs
- User clicks "Get Started" → navigates to `/signup`
- User clicks "Login" → navigates to `/login`
- User clicks "View Sample Feedback" → navigates to `/resources`

### User Actions
| Action | Trigger | Next Screen |
|---|---|---|
| Click "Start Free Practice" | Signup CTA | `/signup` |
| Click "Login" | Login link | `/login` |
| Click "View Sample Feedback" | Secondary CTA | `/resources` |
| Click feature card | Feature interest | Scrolls to How It Works or `/signup` |
| Click testimonial | Social proof | Scrolls to CTA or `/signup` |
| Click FAQ | Question interest | Expand/collapse answer |

### Edge Cases
| Case | Handling |
|---|---|
| User returns after logout | Show "Welcome back" personalization (optional); restore last CTA |
| User is already logged in | Redirect to `/dashboard` |
| Slow connection | Show skeleton loader; prioritize above-fold hero content |
| SEO crawler | Server-render all sections; structured data for rich snippets |
| Ad-blocker | Graceful degradation; no critical functionality affected |

---

## 2. Registration

### Purpose
Create a new user account with email/password or Google OAuth. Collect minimal information to get started.

### User State
- **Pre-authentication**: Anonymous visitor who clicked "Get Started"
- **Entry sources**: Landing page CTA, direct `/signup` URL

### Screen Sections

| Section | Content | Purpose |
|---|---|---|
| **Auth Layout** | Brand logo (IELTSAI Coach), "Back to home" link | Brand consistency, navigation |
| **Header** | "Create an Account", "Start your 7-day free trial today" | Value proposition |
| **Error Display** | Conditional error message (e.g., "Email already exists") | Error handling |
| **Form** | Full Name, Email Address, Password, Confirm Password | User data collection |
| **Terms** | "By clicking Create Account, you agree to Terms of Service and Privacy Policy" | Legal consent |
| **Footer Link** | "Already have an account? Log in" | Conversion recovery |

### Inputs
| Field | Type | Validation |
|---|---|---|
| Full Name | Text, required | Min 2 chars, max 100 chars |
| Email Address | Email, required | Valid email format, unique in system |
| Password | Password, required | Min 6 chars, max 128 chars |
| Confirm Password | Password, required | Must match Password |

### Outputs
- **Success**: Auth session created, user redirected to `/onboarding`
- **Error**: Error message displayed (duplicate email, weak password, network error)

### Navigation
| Action | Trigger | Next Screen |
|---|---|---|
| Submit form | "Create Account" button | `/onboarding` (on success) |
| Click "Log in" | Footer link | `/login` |
| Click "Back to home" | Top link | `/` |

### Edge Cases
| Case | Handling |
|---|---|
| Email already registered | Show "An account with this email already exists. Please log in." with link to `/login` |
| Password too short | Client-side validation: "Password must be at least 6 characters" |
| Passwords don't match | Client-side validation: "Passwords do not match" |
| Network error | Show "Network error. Please check your connection and try again." |
| OAuth signup (Google) | Same flow; auto-fill email and name from Google profile |
| Email verification required | Show "Check your email to verify your account" with resend option |
| Already logged in | Redirect to `/dashboard` |

---

## 3. Login

### Purpose
Authenticate existing users via email/password or Google OAuth.

### User State
- **Pre-authentication**: Returning user
- **Entry sources**: Landing page "Login" link, direct `/login` URL, logout redirect

### Screen Sections

| Section | Content | Purpose |
|---|---|---|
| **Auth Layout** | Brand logo, "Back to home" link | Brand consistency |
| **Header** | "Welcome Back", "Log in to continue your IELTS journey" | Re-engagement |
| **Error Display** | Conditional error (e.g., "Invalid email or password") | Error handling |
| **Social Login** | "Continue with Google" button | One-click login |
| **Divider** | "Or continue with email" | Visual separation |
| **Form** | Email Address, Password, "Forgot password?" link | Credential collection |
| **Footer Link** | "Don't have an account? Create an account" | Conversion recovery |

### Inputs
| Field | Type | Validation |
|---|---|---|
| Email Address | Email, required | Valid email format |
| Password | Password, required | Non-empty |

### Outputs
- **Success**: Auth session restored, user redirected to `/dashboard`
- **Error**: Error message displayed (invalid credentials, account not found)

### Navigation
| Action | Trigger | Next Screen |
|---|---|---|
| Submit form | "Sign In" button | `/dashboard` (on success) |
| Click "Forgot password?" | Link | `/forgot-password` |
| Click "Create an account" | Footer link | `/signup` |
| Click "Continue with Google" | OAuth button | Google OAuth flow → redirect to `/dashboard` |
| Click "Back to home" | Top link | `/` |

### Edge Cases
| Case | Handling |
|---|---|
| Invalid email/password | "Invalid email or password. Please try again." |
| Account not verified | "Please verify your email before logging in." with resend verification link |
| Too many failed attempts | Rate limit: "Too many attempts. Please try again in 15 minutes." |
| Session expired | Silent re-authentication; redirect to dashboard after login |
| OAuth cancellation | Return to login page with no error |

---

## 4. Onboarding (Profile Setup)

### Purpose
Collect essential user information to personalize the study plan. This screen appears **only once** after registration.

### User State
- **Post-authentication**: New user, first login
- **Entry sources**: Redirect from `/signup` or first login

### Screen Sections

| Section | Content | Purpose |
|---|---|---|
| **Header** | "Let's set up your profile", "We need a few details to personalize your IELTS journey" | Context setting |
| **Progress Indicator** | Step 1 of 2: Profile | Show progress through onboarding |
| **Profile Form** | Full Name (pre-filled from signup), Country, Timezone | User identity |
| **Goals Form** | Target Band (dropdown: 5.0–9.0, step 0.5), Exam Date (date picker), Module (Academic / General Training), Daily Study Commitment (30 min / 1 hr / 2 hr / 3+ hr) | Personalization inputs |
| **CTA** | "Create My Study Plan" button | Proceed to next step |

### Inputs
| Field | Type | Validation |
|---|---|---|
| Full Name | Text, pre-filled | Editable, min 2 chars |
| Country | Select dropdown | Required |
| Timezone | Auto-detect + manual override | Required |
| Target Band | Select: 5.0–9.0 (step 0.5) | Required, between 5.0–9.0 |
| Exam Date | Date picker | Must be in the future (max 2 years) |
| Module | Radio: Academic / General Training | Required |
| Daily Commitment | Select: 0.5 / 1 / 2 / 3+ hours | Required |

### Outputs
- **User Profile**: Saved to `users` and `user_goals` tables
- **Redirect**: User sent to `/diagnostic` (not dashboard — diagnostic is mandatory)

### Navigation
| Action | Trigger | Next Screen |
|---|---|---|
| Submit form | "Create My Study Plan" | `/diagnostic` |
| Skip (optional) | "Skip for now" link | `/diagnostic` (defaults to Band 6.5, Academic) |

### Edge Cases
| Case | Handling |
|---|---|
| User picks exam date < 30 days away | Show warning: "Your exam is very soon. We'll create an intensive plan." |
| User picks exam date > 1 year away | Show recommendation: "You have plenty of time. We'll create a relaxed pace plan." |
| User skips onboarding | Default values: Band 6.5, Academic, 60 min/day, exam date = 3 months from now |
| User returns to onboarding (session interrupted) | Resume from where they left off; data persisted in local storage |
| Timezone changes after onboarding | Update in Settings; scheduler adjusts task times on next daily rollover |

---

## 5. Diagnostic Test

### Purpose
Assess the user's baseline IELTS level across Writing, Speaking, and Vocabulary. This is the **foundation of all personalization** — without it, the roadmap cannot be generated.

### User State
- **Post-onboarding**: New user with profile, no diagnostic data
- **Entry sources**: Onboarding completion, `/diagnostic` URL

### Screen Sections

| Section | Content | Purpose |
|---|---|---|
| **Header** | "Find your starting point", "Complete this 20-minute diagnostic test" | Context setting |
| **Badge** | "Step 1: Baseline Assessment" | Progress indicator |
| **What's Included** | 4 cards: Short Essay (10 min), Speaking Clip (5 min), Vocabulary Check (5 min), Band Estimate (instant) | Set expectations |
| **Stats** | Total Duration: 20 mins, Result Speed: Instant | Reassurance |
| **Action Card** | "Ready to start?" with checklist (no credit card, 100% AI, save progress) and "Begin Diagnostic" button | Conversion |
| **Back Navigation** | Link to `/diagnostic` overview | Navigation |

### 5.1 Diagnostic — Section 1: Writing

#### Purpose
Evaluate the user's writing ability on Task 2 (Opinion Essay).

#### Screen Components
| Component | Description |
|---|---|
| **Timer** | 10-minute countdown (visible, starts when user begins typing) |
| **Prompt** | Standard IELTS Writing Task 2 prompt (e.g., "Some people believe... Discuss both views") |
| **Editor** | Text area with word count (target: 150+ words) |
| **Submit** | "Submit Essay" button (disabled until 50+ words typed) |

#### Inputs
| Field | Type | Validation |
|---|---|---|
| Essay text | Textarea | Min 50 words, max 500 words |

#### Outputs
- Essay text stored in `diagnostic_results` (section data)
- AI analysis triggered (async): band score, criteria scores, feedback

#### User Actions
| Action | Description |
|---|---|
| Read prompt | User reads the writing task |
| Type essay | User writes their response |
| Track word count | Real-time counter turns green at 150+ words |
| Submit | Essay sent for AI analysis |

#### Edge Cases
| Case | Handling |
|---|---|
| User doesn't write 50 words | Button remains disabled; "Please write at least 50 words" hint |
| Timer expires | Auto-submit whatever is written; mark as "incomplete" |
| User pastes content | Accept paste; count words; warn if suspiciously fast (cheating detection) |
| Network error on submit | Save to local storage; retry on reconnect |

### 5.2 Diagnostic — Section 2: Speaking

#### Purpose
Evaluate the user's speaking fluency and pronunciation.

#### Screen Components
| Component | Description |
|---|---|
| **Prompt** | Speaking Part 1 question (e.g., "Tell me about your hometown") |
| **Record Button** | Mic icon; tap to start, tap to stop |
| **Timer** | 2-minute recording limit |
| **Waveform** | Visual audio feedback during recording |
| **Transcript** | Live or post-recording transcript display |

#### Inputs
| Field | Type | Validation |
|---|---|---|
| Audio recording | Blob (webm) | Min 30 seconds, max 2 minutes |

#### Outputs
- Audio file uploaded to Supabase Storage
- Async transcription via Whisper/Deepgram
- Transcript stored in `diagnostic_results`

#### User Actions
| Action | Description |
|---|---|
| Grant microphone permission | Browser permission prompt |
| Tap record | Recording starts; timer begins |
| Speak | User responds to the prompt |
| Tap stop | Recording ends; audio uploaded |
| Review transcript | Read AI-generated transcript |

#### Edge Cases
| Case | Handling |
|---|---|
| Microphone permission denied | Show "Microphone access is required. Please enable it in your browser settings." with retry |
| User speaks < 30 seconds | Show "Please speak for at least 30 seconds for accurate analysis." Allow retry once |
| Recording too quiet | "Your recording seems very quiet. Please speak louder and try again." |
| Background noise detected | "We detected background noise. For best results, find a quiet room." |
| Browser doesn't support recording | Fallback: type response instead of recording |

### 5.3 Diagnostic — Section 3: Vocabulary

#### Purpose
Assess the user's academic vocabulary range.

#### Screen Components
| Component | Description |
|---|---|
| **Quiz Interface** | 10 multiple-choice questions testing academic word knowledge |
| **Timer** | 5-minute countdown |
| **Progress** | Question X of 10 indicator |
| **Submit** | Auto-submit on completion or timer expiry |

#### Inputs
| Field | Type | Validation |
|---|---|---|
| 10 answers | Multiple choice (A/B/C/D) | One selection per question |

#### Outputs
- Vocabulary score (0–10) stored in `diagnostic_results`
- Weak word categories identified

#### User Actions
| Action | Description |
|---|---|
| Read question | Academic word in context |
| Select answer | Click one of 4 options |
| Navigate | Next/Previous buttons |
| Submit | Auto-submit when all answered or timer expires |

#### Edge Cases
| Case | Handling |
|---|---|
| User doesn't finish all 10 | Score based on answered questions; mark unanswered as wrong |
| User finishes early | Allow early submission |

### 5.4 Diagnostic — Section 4: Results Calculation

#### Process
After all 3 sections are complete, the backend runs the Diagnostic Analyzer:

```
INPUT: 
  - Essay text + band score (from Writing Assessor)
  - Speaking transcript + band score (from Speaking Assessor)
  - Vocabulary quiz score (0–10)

OUTPUT:
  - Overall band score (average of 3 sections, rounded to 0.5)
  - Per-criterion scores (Grammatical Range, Lexical Resource, Coherence & Cohesion, Fluency & Pronunciation)
  - Strengths (top 2 skills)
  - Weaknesses (bottom 2 skills)
  - CEFR level (A2, B1, B2, C1, C2)
  - Band gap to target
  - Recommended focus area
```

### Edge Cases (Full Diagnostic)

| Case | Handling |
|---|---|
| User exits diagnostic mid-way | Save progress; allow resume from `/diagnostic/start` |
| User doesn't return for 7 days | Expire diagnostic; force restart |
| AI analysis fails for one section | Use other sections only; mark as "partial diagnostic" |
| All 3 sections fail | Prompt user to retry; or skip to default roadmap |
| User wants to retake diagnostic | Allow after 30 days (or on demand for Pro users) |

---

## 6. Diagnostic Results Report

### Purpose
Display the user's baseline assessment results and provide actionable insights. This is the **first major milestone** and a key engagement moment.

### User State
- **Post-diagnostic**: Has completed all 3 sections, results are ready
- **Entry sources**: Redirect from diagnostic completion, `/diagnostic/result` URL

### Screen Sections

| Section | Content | Purpose |
|---|---|---|
| **Badge** | "Assessment Complete" | Milestone confirmation |
| **Header** | "Your Diagnostic Report", "Generated by AI Coach" | Context |
| **Overall Band Score** | Large circular display with overall band (e.g., 6.5), CEFR level (B2), and target comparison | Core metric |
| **Current vs Target** | Side-by-side visualization: Current Band → Target Band with arrow | Gap visualization |
| **Skill Breakdown** | 4 horizontal bars showing per-criterion scores (Grammatical Range, Lexical Resource, Coherence & Cohesion, Fluency & Pronunciation) | Granular view |
| **Strengths** | List of top 2 skills with checkmark icons | Positive reinforcement |
| **Weaknesses** | List of bottom 2 skills with alert icons | Growth areas |
| **AI Tip** | One actionable recommendation (e.g., "Focus on Grammatical Range this week") | Immediate next step |
| **CTA** | "Generate My Study Roadmap" button | Primary action |

### Inputs
- `diagnostic_results` from backend
- `user_goals` (target band)

### Outputs
- Display of all diagnostic data
- User clicks "Generate My Study Roadmap" → triggers Roadmap generation

### Navigation
| Action | Trigger | Next Screen |
|---|---|---|
| Click "Generate My Study Roadmap" | Primary CTA | `/roadmap` (generation in progress) |
| Click "Download PDF Report" | Secondary CTA | Download PDF of results |
| Click "Learn how" | AI Tip link | Scroll to skill breakdown or open resource |

### Edge Cases
| Case | Handling |
|---|---|
| Results still processing | Show spinner: "AI is analyzing your responses... This usually takes a few seconds." |
| Results are lower than expected | Show encouraging message: "This is your starting point. Every great journey begins with a single step." |
| Results are higher than expected | Show "Great foundation! You're closer to your target than you think." |
| User closes page before seeing results | Save results; allow access from `/diagnostic/result` anytime |

---

## 7. Roadmap Generation

### Purpose
Generate a personalized, phased study plan based on the diagnostic results, target band, exam date, and daily study commitment.

### User State
- **Post-diagnostic**: Has results ready
- **Entry sources**: Diagnostic Results page, `/roadmap` URL

### Screen Sections

| Section | Content | Purpose |
|---|---|---|
| **Loading State** | "Creating your personalized roadmap..." with progress bar (0–100%) | Manage expectations during AI generation |
| **Phase 1: Foundation** | Completed phase with tasks (Diagnostic, Grammar Basics) | Show progress |
| **Phase 2: Skill Building** | Active phase with current tasks (Writing, Speaking, Vocabulary) | Current focus |
| **Phase 3: Advanced** | Locked phase (future) | Upcoming work |
| **Phase 4: Mock Tests** | Locked phase | Future milestone |
| **Phase 5: Revision** | Locked phase, flagged as "Protected" | Final preparation |
| **Goal Flag** | "Goal: IELTS Band X.X" with estimated achievement date and confidence score | End goal visualization |

### 7.1 Generation Algorithm

```
PROCEDURE GenerateRoadmap(user):
    // 1. Calculate phase durations (from SCHEDULER.md)
    total_weeks = (exam_date - TODAY()) / 7
    phases = [
        { name: 'foundation', weight: 0.30, tasks: [...] },
        { name: 'skill_building', weight: 0.30, tasks: [...] },
        { name: 'advanced', weight: 0.20, tasks: [...] },
        { name: 'mock_tests', weight: 0.15, tasks: [...] },
        { name: 'revision', weight: 0.05, tasks: [...] },
    ]
    
    // 2. Assign tasks per phase based on skill gaps
    FOR phase IN phases:
        phase.tasks = GenerateTasksForPhase(phase, user.skill_gaps, user.daily_minutes)
        phase.start_date = CalculatePhaseStart(phase)
        phase.end_date = CalculatePhaseEnd(phase)
    
    // 3. Save to roadmaps table
    roadmap = SaveRoadmap(user, phases)
    
    // 4. Generate first week of daily missions
    GenerateDailyMissions(user, roadmap, week_count=1)
    
    // 5. Schedule mock tests
    ScheduleMockTests(user, roadmap)
    
    // 6. Set revision windows as protected
    ProtectRevisionDays(user, roadmap)
    
    RETURN roadmap
```

### Inputs
- `diagnostic_results` (skill gaps, overall band)
- `user_goals` (target band, exam date, daily minutes, module)
- `phases` (pre-defined structure)

### Outputs
- `roadmap` record with phases and tasks
- First 7 days of `daily_plans` generated
- `mock_tests` scheduled
- Protected revision windows set

### Navigation
| Action | Trigger | Next Screen |
|---|---|---|
| Generation complete | Auto-redirect | `/dashboard` |
| Click "Start Now" on active task | Task card button | `/writing` or `/speaking` or resource page |
| Click "Review" on completed task | Task card button | Assessment result page |
| Click "View Full Roadmap" | Dashboard CTA | `/roadmap` |

### Edge Cases
| Case | Handling |
|---|---|
| Generation takes > 30 seconds | Show progress updates (e.g., "Phase 2 of 5 complete") |
| Generation fails | Show "Something went wrong. Please try again." with retry button |
| User has very little time (< 30 days) | Generate "Intensive Plan" with compressed phases, emphasis on mock tests |
| User has a lot of time (> 6 months) | Generate "Extended Plan" with more tasks per phase, slower pace |
| User changes exam date after generation | Regenerate roadmap (see SCHEDULER.md edge case 9.2) |

---

## 8. Dashboard (Home)

### Purpose
The user's primary home base. Displays today's missions, key stats, and quick actions. This is the **highest-frequency screen** — users see it every time they log in.

### User State
- **Post-roadmap**: Has an active study plan
- **Entry sources**: Login redirect, navigation sidebar, browser bookmark

### Screen Sections

**A. Welcome Header**

| Component | Content | Data Source |
|---|---|---|
| Greeting | "Good Morning/Afternoon/Evening, {Name}!" | Time-based + user.name |
| Streak message | "You've studied for {N} days in a row!" | `streaks.current_streak` |
| CTA | "Continue Last Lesson" button | Last incomplete task |

**B. Stats Grid (4 cards)**

| Card | Content | Data Source |
|---|---|---|
| **Estimated Band** | Current band score, trend (+0.5 from last week), progress bar | `band_predictions.predicted_band` |
| **Exam Countdown** | Days remaining, exam date, intensity indicator | `user_goals.exam_date` |
| **Study Streak** | Current streak number, longest streak, streak calendar (mini) | `streaks` |
| **Tasks Completed** | Today's completed count / total, weekly trend | `daily_plans` + `task_completions` |

**C. Today's Missions (Right Sidebar)**

| Component | Content | Data Source |
|---|---|---|
| **Task List** | 3–5 tasks with checkbox, title, estimated time, skill badge | `daily_plans` for today |
| **Progress** | "45 / 60 minutes studied today" with progress bar | `study_sessions` today |
| **CTA** | "View Full Roadmap" button | Link to `/roadmap` |

**D. Quick Actions (Cards)**

| Card | Content | Action |
|---|---|---|
| **Writing Practice** | Icon + "Grade your Task 1 & 2 essays" | Navigate to `/writing` |
| **Speaking Coach** | Icon + "Practice with AI Examiner" | Navigate to `/speaking` |

**E. Recent Assessments (List)**

| Component | Content | Data Source |
|---|---|---|
| **Assessment items** | 2–3 recent items: type icon, task name, date, band score badge, "View" arrow | `assessments` (last 5) |

**F. Recommended Resources (Widget)**

| Component | Content | Data Source |
|---|---|---|
| **Resource cards** | 2–3 cards: title, provider badge, type icon, reason, "View" button | `resource_recommendations` (top 3) |

### Inputs
- `user.id` for all data queries
- `TODAY()` for date-specific data

### Outputs
- Real-time dashboard display
- "Continue Last Lesson" redirects to the last incomplete task's page
- Task checkbox toggles `task_completions` and updates streak

### Navigation
| Action | Trigger | Next Screen |
|---|---|---|
| Click "Continue Last Lesson" | Welcome CTA | `/writing` or `/speaking` or resource |
| Click task checkbox | Task item | Mark task complete (inline) |
| Click task title | Task item | `/writing` or `/speaking` or resource |
| Click "Writing Practice" | Quick action card | `/writing` |
| Click "Speaking Coach" | Quick action card | `/speaking` |
| Click "View Full Roadmap" | CTA button | `/roadmap` |
| Click assessment item | Recent assessments list | Assessment result |
| Click resource card | Recommended resources | Resource detail page |
| Click "View Resource" | Resource card | External link (new tab) |

### Edge Cases
| Case | Handling |
|---|---|
| No tasks for today | Show "No tasks scheduled today. Enjoy your rest day!" with streak preserved |
| All tasks completed | Show "All tasks complete! 🎉" with celebration animation |
| Streak at risk (no activity past 2 days) | Show warning banner: "Complete a task today to keep your streak alive!" |
| No diagnostic taken | Show banner: "Take your diagnostic test to get a personalized study plan." with link |
| Exam is tomorrow | Show "Your exam is tomorrow! Here's your final checklist." with revision tasks |
| New week starts | Show weekly summary: "You completed 12/15 tasks last week. Great effort!" |

---

## 9. Daily Mission

### Purpose
The user's **primary work screen**. Each day, the user sees their assigned tasks, completes them, tracks time, and receives feedback. This is where the bulk of learning happens.

### User State
- **Active plan**: User has a roadmap and daily missions
- **Entry sources**: Dashboard task click, notification, `/daily-mission` URL

### Screen Sections

**A. Mission Header**

| Component | Content | Data Source |
|---|---|---|
| **Date** | "Today's Mission — {Date}" | Calculated |
| **Phase** | "Phase {N}: {Phase Name}" | `roadmap_phases` |
| **Progress** | "X of Y tasks completed" | Today's `task_completions` |
| **Timer** | "Studied: {N} min / {M} min" | Today's `study_sessions` |

**B. Task List (Ordered by Priority)**

| Task Card Component | Content | Data Source |
|---|---|---|
| **Checkbox** | Circular completion toggle | `tasks.status` |
| **Title** | Task description (e.g., "Writing Task 2: Opinion Essay") | `tasks.title` |
| **Skill Badge** | Color-coded skill tag (Writing, Speaking, Vocabulary, Grammar) | `tasks.skill` |
| **Duration** | Estimated time (e.g., "40 min") | `tasks.duration_minutes` |
| **Resource Link** | Optional attached resource (e.g., "📄 View Sample Answer") | `tasks.resource_id` |
| **Status** | overdue, carry-forward, new, in_progress, completed | `tasks.status` |

**C. Task Detail / Workspace (Expanded)**

When user clicks a task, it expands to show the workspace:

| Task Type | Workspace | Action |
|---|---|---|
| **Writing** | Prompt + text editor + timer + submit | Submit for AI assessment |
| **Speaking** | Prompt + record button + timer + transcript | Record and submit |
| **Vocabulary** | Word list + flashcards + quiz | Mark as studied |
| **Grammar** | Rules + exercises + answer check | Complete exercises |
| **Reading** | Passage + questions + timer | Submit answers |
| **Listening** | Audio + questions + timer | Submit answers |
| **Review** | Previous assessment feedback + error list | Mark as reviewed |
| **Mock Test** | Full exam interface (multi-part) | Complete all sections |

### Inputs
| Action | Input | Validation |
|---|---|---|
| Complete writing task | Essay text (250+ words) | Min word count |
| Complete speaking task | Audio recording (1–2 min) | Min duration |
| Complete vocabulary task | "Mark as studied" click | None |
| Complete grammar task | Exercise answers | All questions answered |
| Track study time | Auto-tracked via page focus | None |

### Outputs
| Output | Destination |
|---|---|
| Task completion | `task_completions` table |
| Study time | `study_sessions` table |
| Assessment (if writing/speaking) | `assessments` table |
| Daily activity update | `daily_activity` table |
| Streak update | `streaks` table |
| Next recommendation | `resource_recommendations` (if resource attached) |

### Navigation
| Action | Trigger | Next Screen |
|---|---|---|
| Click task card | Expand task | Inline workspace |
| Complete task | Mark as done | Stay on mission (next task auto-highlights) |
| Click "View All Tasks" | Header | `/roadmap` |
| All tasks complete | Auto | Celebration state → `/dashboard` |
| Click notification | Bell icon | Notifications panel |

### Edge Cases
| Case | Handling |
|---|---|
| Carry-forward task (overdue) | Show orange "Carried Forward" badge; highlight in task list |
| Task takes longer than estimated | Allow "Add Time" button; recalculate future estimates |
| User closes task mid-way | Save progress (draft essay, partial recording); resume later |
| User completes task very quickly | Flag as "potentially incomplete"; ask "Did you fully complete this task?" |
| All tasks completed before noon | Show "Mission Complete! 🎉" with option to do bonus tasks or review |
| No tasks today (rest day) | Show "Rest Day — You've earned it!" with streak preserved |
| User has 10+ overdue tasks | Show "You have {N} overdue tasks. Let's start with the most important one." |

---

## 10. Progress & Analytics

### Purpose
Provide detailed insights into the user's performance, skill gaps, trends, and predicted band. This is the **reflection and motivation screen**.

### User State
- **Active user**: Has completed at least 2–3 assessments
- **Entry sources**: Sidebar navigation, `/analytics` URL

### Screen Sections

**A. Header**

| Component | Content | Data Source |
|---|---|---|
| **Title** | "Performance Analytics" | Static |
| **Subtitle** | "Detailed insights into your IELTS preparation journey" | Static |
| **Actions** | "Export Data" (PDF/CSV), "Last 30 Days" filter | Analytics API |

**B. Stats Grid (4 cards)**

| Card | Content | Trend Indicator |
|---|---|---|
| **Overall Band** | Current predicted band | +0.3 this month |
| **Writing Avg** | Average of last 5 writing assessments | +0.5 this month |
| **Speaking Avg** | Average of last 5 speaking assessments | -0.2 this month |
| **Tests Taken** | Total assessments completed | +2 this week |

**C. Band Score Trend Chart (Line Chart — Recharts)**

| Axis | Content | Data Source |
|---|---|---|
| **X-axis** | Time (weeks) | `assessments.created_at` |
| **Y-axis** | Band score (0–9) | `assessments.band_score` |
| **Lines** | Overall band, Writing avg, Speaking avg | Aggregated |
| **Target** | Horizontal dashed line at target band | `user_goals.target_band` |

**D. Skill Gap Analysis (Bar Chart)**

| Component | Content | Data Source |
|---|---|---|
| **Bars** | 4 criteria: TR, CC, LR, GR | `assessments.criteria_scores` |
| **Target markers** | Vertical line on each bar at target band | `user_goals.target_band` |
| **Gap text** | "-1.5", "-0.5", etc. | Calculated |
| **Insight** | "Your Coherence & Cohesion is your biggest bottleneck" | Highest gap |

**E. Study Time Distribution (Pie Chart)**

| Slice | Content | Data Source |
|---|---|---|
| **Writing** | % of total study time | `study_sessions` grouped by skill |
| **Speaking** | % of total study time | `study_sessions` grouped by skill |
| **Vocabulary** | % of total study time | `study_sessions` grouped by skill |
| **Grammar** | % of total study time | `study_sessions` grouped by skill |
| **Mock Tests** | % of total study time | `mock_tests` |

**F. Streak Calendar**

| Component | Content | Data Source |
|---|---|---|
| **Calendar grid** | Current month, day cells colored by activity (green = active, gray = inactive, orange = streak saved) | `daily_activity` |
| **Stats** | Current streak, longest streak, streak freeze count | `streaks` |

**G. Test History Table**

| Column | Content | Data Source |
|---|---|---|
| Date | Assessment date | `assessments.created_at` |
| Task Type | Writing T1, Writing T2, Speaking | `assessments.task_type` |
| Topic | Essay/speaking topic | `assessments.user_input` (truncated) |
| Band | Band score | `assessments.band_score` |
| Status | Improved / Stable / Needs Work | Trend calculation |

### Inputs
- `user.id`
- `range` filter (7d, 30d, 90d, all)

### Outputs
- Charts, tables, and stats displayed
- PDF export (via WeasyPrint or similar)
- CSV export for data portability

### Navigation
| Action | Trigger | Next Screen |
|---|---|---|
| Click chart data point | Assessment on specific date | Assessment result page |
| Click "Export Data" | Button | Download PDF/CSV |
| Change filter range | Dropdown | Refresh all data |
| Click row in history table | Row click | Assessment result page |

### Edge Cases
| Case | Handling |
|---|---|
| No assessments yet (new user) | Show "Complete your first assessment to see your progress." with link to `/writing` |
| Only 1 assessment | Show trend line as a single point; "More data needed for trend analysis" |
| Sharp drop in band | Show "Don't worry! Scores fluctuate naturally. Focus on consistency." |
| Data export fails | Show "Export failed. Please try again." with retry |
| Recharts rendering on mobile | Responsive chart sizing; horizontal scroll for wide charts |

---

## 11. Mock Tests

### Purpose
Simulate the full IELTS exam experience under timed conditions. Mock tests are **scheduled by the Adaptive Scheduler** and are a critical milestone for band prediction and roadmap re-calibration.

### User State
- **Post-Foundation**: User has completed Phase 1 and part of Phase 2
- **Entry sources**: Scheduler notification, dashboard task, `/mock-test` URL

### Screen Sections

**A. Mock Test Overview (Pre-Mock)**

| Component | Content | Data Source |
|---|---|---|
| **Header** | "Mock Test #{N} — Full IELTS Simulation" | `mock_tests` |
| **Sections** | 4 sections: Listening (30 min), Reading (60 min), Writing (60 min), Speaking (15 min) | Mock test structure |
| **Instructions** | "Find a quiet room. Ensure stable internet. Duration: ~2 hours 45 minutes." | Static |
| **CTA** | "Start Mock Test" button | Begin test |

**B. Mock Test Progress Bar**

| Component | Content |
|---|---|
| **Section indicators** | 4 segments: Listening, Reading, Writing, Speaking |
| **Current section** | Highlighted, active |
| **Completed sections** | Green checkmark |
| **Upcoming sections** | Grayed out |

**C. Listening Section (30 min)**

| Component | Content |
|---|---|
| **Audio player** | Play/pause, volume, progress bar |
| **Questions** | 40 questions across 4 sections |
| **Answer sheet** | Radio buttons, text inputs, checkboxes as appropriate |
| **Timer** | 30-minute countdown |

**D. Reading Section (60 min)**

| Component | Content |
|---|---|
| **Passage** | 3 passages (academic texts) |
| **Questions** | 40 questions: multiple choice, T/F/NG, matching headings, sentence completion |
| **Split view** | Passage on left, questions on right |
| **Timer** | 60-minute countdown |

**E. Writing Section (60 min)**

| Component | Content |
|---|---|
| **Task 1** | Prompt + editor (20 min recommended) |
| **Task 2** | Prompt + editor (40 min recommended) |
| **Word count** | 150+ for Task 1, 250+ for Task 2 |
| **Timer** | 60-minute countdown (shared) |

**F. Speaking Section (15 min)**

| Component | Content |
|---|---|
| **Part 1** | 3 questions (intro + familiar topics) — 4 min |
| **Part 2** | Cue card + 1 min preparation + 2 min speaking — 3 min |
| **Part 3** | 3 discussion questions — 8 min |
| **Recording** | Audio recorded for each part |

**G. Post-Mock Review**

| Component | Content | Data Source |
|---|---|---|
| **Overall Band** | Mock test band score | `mock_tests.band_score` |
| **Section Scores** | Listening, Reading, Writing, Speaking | `mock_tests.section_scores` |
| **Comparison** | Mock score vs predicted band vs target band | Calculated |
| **Mistake Analysis** | List of incorrect answers with correct answers and explanations | `mock_tests.mistake_analysis` |
| **Skill Re-calibration** | Updated skill gap analysis based on mock performance | Calculated from mock breakdown |
| **CTA** | "Review Mistakes" | Navigate to mistake detail page |

### Inputs

| Input | Source | Description |
|---|---|---|
| Mock test answers | User input during test | Writing essays, reading/listening selections, speaking recordings |
| Test timer data | Client-side timer | Start/stop timestamps per section |
| Mistake self-assessment | Optional user input | "I ran out of time" / "I didn't understand the question" |

### Outputs

| Output | Destination | Trigger |
|---|---|---|
| Section scores | `mock_tests.section_scores` | After AI evaluation of all sections |
| Overall band score | `mock_tests.overall_band` | Aggregated and rounded from section scores |
| Mistake analysis | `mock_tests.mistake_analysis` | Answer key comparison + AI explanation |
| Roadmap re-calibration | `roadmap_phases` + `tasks` | Significant score delta triggers regeneration |
| Predicted band update | `band_predictions` | New mock data fed into prediction model |
| Notification | `notifications` | "Your Mock Test #{N} results are ready!" |

### Navigation

| Action | Trigger | Next Screen |
|---|---|---|
| Click "Start Mock Test" | Pre-mock CTA | Listening section (first section) |
| Complete section | Auto-advance | Next section (Reading → Writing → Speaking) |
| Complete all sections | Auto-redirect | Post-mock review page |
| Click "Review Mistakes" | Post-mock review CTA | Mistake detail / answer key page |
| Click "View Updated Roadmap" | Post-mock review CTA | `/roadmap` |
| Click "Dismiss" | Notification | Dismiss; return to current page |

### User Actions

| Action | Description |
|---|---|
| Read instructions | User reviews mock test format and rules |
| Start test | User clicks "Begin" — timer starts, first section loads |
| Answer questions (Listening) | User plays audio and selects answers for 40 questions |
| Answer questions (Reading) | User reads passages and answers 40 questions in split-view |
| Write essays (Writing) | User completes Task 1 and Task 2 with word count tracking |
| Record speaking (Speaking) | User records responses for Parts 1, 2, and 3 |
| Submit section | User submits current section (or auto-submit on timer expiry) |
| Take break between sections | Optional 2-minute break between sections |
| Review results | User reads post-mock review with band scores and mistake analysis |
| Mark mistakes as "reviewed" | User acknowledges they understand the mistake |

### Edge Cases

| Case | Handling |
|---|---|
| User exits mid-mock | Save all completed sections; allow resume within 24 hours; mark as "incomplete" after 24h |
| Internet drops during test | Cache answers locally; sync on reconnect; warn if > 5 minutes offline |
| Timer expires on a section | Auto-submit whatever answers exist; mark section as "timed out" |
| Speaking recording fails | Allow text-based fallback response; flag for manual review |
| User submits all answers in 10 minutes | Flag as "potentially rushed"; prompt "Did you review your answers?" |
| Mock score is significantly lower than predicted | Trigger roadmap re-calibration; add "foundation review" tasks |
| Mock score is significantly higher than predicted | Accelerate roadmap; add advanced tasks; increase confidence score |
| User hasn't completed all 4 sections | Partial mock — score only completed sections; mark as "partial" |
| User takes multiple mocks in one day | Warn: "You've already taken a mock test today. Rest is important for retention." |

### Section-Level Edge Cases (Full Mock Test)

| Case | Handling |
|---|---|
| No mock test scheduled | Show "No mock test scheduled. Complete your current phase tasks to unlock." |
| Mock test is overdue | Show "Your Mock Test #{N} was scheduled for {date}. Take it now to keep your roadmap on track." |
| User has already completed this mock number | Prevent duplicate; show "You've already completed Mock Test #{N}. View results or wait for next scheduled mock." |
| Listening audio fails to load | Show retry button; fallback to text transcript of audio |
| Reading passage is too long for split view | Enable scroll sync between passage and questions; mobile: stack vertically |
| Writing submitted with < 150 words (Task 1) | Flag as "under word count"; AI still evaluates but notes the deficiency |
| Speaking recorded in noisy environment | AI detects background noise; append note "Recording quality may affect pronunciation assessment" |

---

## 12. Final Exam Preparation

### Purpose
Guide the user through the **final 14-day revision window** leading up to their IELTS exam. This phase is **protected** — no new heavy tasks are introduced, and the focus shifts entirely to revision, strategy reinforcement, and confidence building. The system enters a "maintenance + review" mode.

### User State
- **Post-mock tests**: User has completed at least 2–3 mock tests and is within 14 days of exam date
- **Entry sources**: Automatic scheduler transition, dashboard banner, `/roadmap` (Phase 5)

### Screen Sections

**A. Revision Phase Banner (Dashboard)**

| Component | Content | Data Source |
|---|---|---|
| **Header** | "🏁 Final Countdown — {N} Days to Go!" | `user_goals.exam_date` |
| **Sub-header** | "You're in the Revision Phase. Focus on reviewing your mistakes and staying sharp." | Static |
| **Progress Bar** | "Day {N} of 14" | Calculated from revision window start |
| **CTA** | "View Final Checklist" | Opens checklist modal or `/roadmap` |

**B. Final Strategy Review (Dedicated Page — `/final-review`)**

| Section | Content | Purpose |
|---|---|---|
| **Exam Day Checklist** | Documents required, timings, what to expect | Practical preparation |
| **Band-Specific Tips** | 3–5 tips tailored to the user's current band (e.g., "At Band 6.5, focus on Coherence & Cohesion") | Targeted last-minute advice |
| **Time Management Strategy** | Per-section time allocation table (e.g., Reading: 20 min per passage) | Exam technique |
| **Common Mistakes to Avoid** | Top 5 mistakes from the user's own assessment history, with corrections | Personalized review |
| **Mental Preparation** | Breathing exercises, positive affirmations, sleep schedule | Confidence building |

**C. Revision Task List (Last 14 Days)**

| Day | Task Type | Duration | Focus |
|---|---|---|---|
| Day -14 | Review all Writing Task 2 feedback | 30 min | Weakest essay type |
| Day -13 | Speaking Part 2 mock (self-record) | 15 min | Fluency practice |
| Day -12 | Review Reading mistake log | 20 min | Skimming/scanning technique |
| Day -11 | Listening section practice | 30 min | Note-taking strategy |
| Day -10 | Review all Speaking feedback | 20 min | Pronunciation & fluency |
| Day -9 | Vocabulary: weakest topic area | 15 min | Last-minute vocab boost |
| Day -8 | Full Reading section (timed) | 20 min | Time management check |
| Day -7 | Writing Task 1 (data) review | 30 min | Structure review |
| Day -6 | Grammar: most common error | 15 min | Fix recurring mistakes |
| Day -5 | Light Review: exam format | 15 min | Familiarity check |
| Day -4 | Rest day / light vocab | 10 min | Mental rest |
| Day -3 | Final Writing Task 2 practice | 40 min | One last essay |
| Day -2 | Final Speaking mock | 15 min | Confidence builder |
| Day -1 | **Rest & Preparation** | 0 min | No tasks — relax, prepare documents |
| **Exam Day** | **Go get your target score!** | — | — |

**D. Protected Revision Window (System Behavior)**

| Component | Behavior | Implementation |
|---|---|---|
| **No new tasks** | Scheduler stops generating new writing/speaking tasks | `scheduler.active = False` for new task generation |
| **No carry-forward** | Missed tasks from earlier phases are NOT shifted into this window | `IsProtectedDay()` returns `final_revision` |
| **Streak preservation** | Streak continues even with minimal (10 min) activity | Minimum viable day = 10 min review |
| **Mock tests blocked** | No new mock tests are scheduled in the last 7 days | `ScheduleMockTests()` skips dates in revision window |
| **Notification cadence** | 1 daily reminder vs. normal 2–3 | `notification_service` reduces frequency |

### Inputs

| Input | Source | Description |
|---|---|---|
| Exam date | `user_goals.exam_date` | Triggers revision window calculation |
| Assessment history | `assessments` table | Personalized mistake list and band-specific tips |
| User's weakest skills | `diagnostic_results` + `progress` | Targeted revision content |
| User's module | `user_goals.module` | Academic vs General Training specific tips |

### Outputs

| Output | Destination | Trigger |
|---|---|---|
| Revision task list | `tasks` with `phase_index = 5` | Scheduler daily rollover during revision window |
| Final checklist | Frontend UI | User clicks "View Final Checklist" |
| Exam day reminder | `notifications` | Day before exam (T-1) |
| Band prediction final | `band_predictions` | Last prediction before exam |
| Study plan archival | `study_plans.status = 'completed'` | On exam date |

### Navigation

| Action | Trigger | Next Screen |
|---|---|---|
| Click "View Final Checklist" | Dashboard banner or sidebar | `/final-review` |
| Click revision task | Task card | Relevant workspace (writing, speaking, vocab) |
| Click "Mark as Reviewed" | Mistake review task | Mark complete; next task highlights |
| All tasks complete | Auto | Celebration → dashboard |
| Exam day arrives | Scheduler | Post-exam screen (see Section 13) |

### User Actions

| Action | Description |
|---|---|
| Complete daily revision task | User performs the assigned light review task |
| Read final checklist | User reviews exam day preparation guide |
| Review past mistakes | User reads through their historical assessment feedback |
| Practice one last essay | Optional: user writes a final essay for confidence |
| Mark exam as "taken" | After exam day, user indicates they've taken the test |

### Edge Cases

| Case | Handling |
|---|---|
| Exam date is < 14 days from diagnostic | Go directly to revision phase; skip Skill Building and Advanced phases |
| Exam date is > 14 days away | Normal scheduler; revision phase not yet active |
| User has no assessment history (new) | Show generic tips: "Here are the most common IELTS mistakes to avoid." |
| User wants to continue heavy practice | Allow "opt-out" of revision mode via Settings; warn "This may lead to burnout." |
| User hasn't taken any mock tests | Show "We recommend taking at least one mock test. Even a partial mock helps." |
| Exam is postponed | Regenerate roadmap; revision phase shifts accordingly; new tasks generated |
| User feels anxious / requests mental break | Show "Mental Health Day" option — skip 1 day without streak penalty |

---

## 13. Post-Exam

### Purpose
Provide a structured experience after the user has taken their IELTS exam. This phase handles result entry, score reflection, and next-step planning (retake, new goal, or platform departure). This is the **final milestone** and the closure of the user's journey.

### User State
- **Post-exam**: User has indicated they took the IELTS exam
- **Entry sources**: Automatic redirect on exam date, dashboard banner, direct URL

### Screen Sections

**A. Post-Exam Entry Screen (Dashboard Replacement)**

| Component | Content | Data Source |
|---|---|---|
| **Header** | "How did it go?" | Static |
| **Sub-header** | "Congratulations on completing your IELTS journey! Let us know how you did." | Static |
| **Options** | 3 cards: "I got my results 🎉", "I'm still waiting ⏳", "I haven't taken the exam yet ↩️" | User selection |

**B. Result Entry Screen (if user has results)**

| Section | Content | Purpose |
|---|---|---|
| **Header** | "Enter Your Score" | Data collection |
| **Form** | Overall Band Score (dropdown: 0.0–9.0, step 0.5), Section Scores (Listening, Reading, Writing, Speaking), Exam Date (pre-filled), Test Centre (optional text) | Result recording |
| **Comparison** | Side-by-side: Predicted Band vs Actual Band | Outcome visualization |
| **Reflection** | Optional textarea: "What helped you most? Any tips for future students?" | Community feedback |
| **CTA** | "Save My Results" | Persist result |

**C. Score Reflection Screen**

| Component | Content | Data Source |
|---|---|---|
| **Score Card** | Large display of achieved band; color-coded (green = met target, yellow = close, red = below) | User input |
| **Target Comparison** | "Your target was Band {X}. You achieved Band {Y}." | `user_goals.target_band` vs entered score |
| **Journey Summary** | "You completed {N} tasks, {M} mock tests, and studied for {H} hours over {D} days." | Aggregated from all tables |
| **Streak Finale** | "Your longest streak was {N} days!" | `streaks.longest_streak` |
| **Skill Correlation** | "Your strongest skill was {skill} (avg {band}). Your weakest was {skill} (avg {band})." | Aggregated from `progress` |

**D. Next Steps Screen**

| Option | Condition | Action |
|---|---|---|
| **🎉 Celebrate & Leave** | User met or exceeded target | Show congratulations; offer to share on social media; ask for testimonial; soft account deactivation |
| **🔄 Retake Plan** | User didn't meet target | Generate a new "Retake Roadmap" based on actual score vs new target; schedule new exam date |
| **🎯 New Goal** | User met target but wants another score | Create new goal with higher target band; generate new roadmap |
| **📚 Continue Learning** | Any condition | Offer free resource access; suggest General Training version if Academic was taken; keep account active |
| **🗑️ Delete Account** | User wants to leave | Soft delete; export data option; confirmation flow |

### Inputs

| Field | Type | Validation |
|---|---|---|
| Overall Band Score | Select dropdown: 0.0–9.0 (step 0.5) | Required, valid IELTS band |
| Listening Score | Select dropdown: 0.0–9.0 (step 0.5) | Optional |
| Reading Score | Select dropdown: 0.0–9.0 (step 0.5) | Optional |
| Writing Score | Select dropdown: 0.0–9.0 (step 0.5) | Optional |
| Speaking Score | Select dropdown: 0.0–9.0 (step 0.5) | Optional |
| Test Centre | Text | Optional, max 200 chars |
| Reflection | Textarea | Optional, max 1000 chars |
| Next Step | Selection: Retake / New Goal / Continue / Leave | Required |

### Outputs

| Output | Destination | Trigger |
|---|---|---|
| Exam result | `mock_tests` (marked as `test_type = 'real_exam'`) | User submits result form |
| Journey summary | Frontend display | Calculated on result submission |
| Retake roadmap | `study_plans` (new version) | User selects "Retake" |
| Account archival | `users` (status = 'archived') | User selects "Celebrate & Leave" |
| Testimonial prompt | `notifications` | User met target |
| Data export | Download link | User requests account deletion |

### Navigation

| Action | Trigger | Next Screen |
|---|---|---|
| Select "I got my results" | Post-exam entry | Result entry form |
| Select "I'm still waiting" | Post-exam entry | "Check back later" screen; reminder set for 13 days |
| Select "I haven't taken the exam" | Post-exam entry | Redirect to dashboard; normal mode continues |
| Submit results | Result form submit | Score reflection screen |
| Select "Retake" | Next steps | `/onboarding` (new goal) → `/diagnostic` (optional) → new roadmap |
| Select "Celebrate & Leave" | Next steps | Account closure flow |
| Select "New Goal" | Next steps | `/onboarding` (new target) → new roadmap |
| Click "Share" | Score reflection | Social media share dialog |

### User Actions

| Action | Description |
|---|---|
| Indicate exam status | User selects whether they have results, are waiting, or haven't taken the exam |
| Enter scores | User fills in their actual IELTS band scores |
| Write reflection | User optionally shares their experience and tips |
| Choose next step | User decides what to do next (retake, new goal, leave) |
| Share on social media | User posts their achievement (optional) |
| Delete account | User initiates account deletion (with confirmation) |

### Edge Cases

| Case | Handling |
|---|---|
| User enters invalid band (e.g., 7.3) | Reject with "Band scores must be in 0.5 increments (e.g., 6.0, 6.5, 7.0)" |
| User doesn't return after exam | Send reminder at T+13 days (results typically released in 13 days); archive plan after 30 days |
| User achieved higher than target | Show "🎉 Outstanding! You exceeded your target by {N} bands!" |
| User achieved much lower than target | Show encouraging message: "This is a data point, not a definition. Many successful students take IELTS multiple times." |
| User wants to retake but with same target | Regenerate roadmap with same target but adjusted timeline; suggest focus on weakest areas |
| User wants to retake with higher target | Validate new target is achievable given previous score; show "We recommend Band {X} based on your progress" |
| User doesn't want to enter scores | Allow skip: "You can always enter your scores later from your profile." |
| User enters scores significantly different from prediction | Show "Your scores differ from our prediction. This helps us improve our AI models." |
| User wants to delete account | Soft delete with 30-day grace period; export data option; confirm by email |
| User is on free plan and wants to retake | Offer premium plan for retake roadmap; free plan allows 1 retake roadmap |

---

## 14. Post-Exam Account Lifecycle

### Purpose
Define how the platform handles accounts after the exam journey is complete, including data retention, re-activation, and alumni engagement.

### User States

| State | Condition | Platform Behavior |
|---|---|---|
| **Active** | User is pre-exam or has chosen "Continue Learning" | Normal scheduler, daily missions, full access |
| **Results Pending** | User indicated "I'm still waiting" | Reduced notifications; no new tasks; check back prompt |
| **Completed — Met Target** | User entered score ≥ target | Celebration mode; archive plan; offer alumni resources |
| **Completed — Below Target** | User entered score < target | Retake roadmap generation; encouragement messaging |
| **Retake** | User chose to retake | New study plan generated; new exam date set |
| **Archived** | User chose "Celebrate & Leave" or inactive > 90 days | Account soft-deleted; data preserved for 12 months |
| **Deleted** | User requested deletion | Data purged after 30-day grace period |

### Alumni Features

| Feature | Description | Access |
|---|---|---|
| **Resource Library** | Continue accessing free resources without active plan | Unlimited |
| **Community Forum** | Share tips, answer questions, mentor new students | Optional opt-in |
| **Score Verification** | Employers/universities can verify scores (with user consent) | Premium feature |
| **Alumni Badge** | "IELTS AI Coach Graduate" digital badge for LinkedIn | Automatic |
| **Referral Program** | Refer friends; get 1 month free premium per referral | Permanent |

### Data Retention Policy

| Data Type | Retention Period | Rationale |
|---|---|---|
| Assessment history | 24 months post-exam | User may want to review progress |
| Study activity | 12 months post-exam | Analytics improvement |
| Personal information | Until account deletion | GDPR compliance |
| AI training data (anonymized) | Indefinite | Product improvement (aggregated, de-identified) |
| Payment information | 36 months (tax compliance) | Legal requirement |

---

## Appendix A: Complete Journey Map — State Machine

```
STATES:
  ANONYMOUS → REGISTERED → ONBOARDED → DIAGNOSTIC_IN_PROGRESS → DIAGNOSTIC_COMPLETE
  → ROADMAP_ACTIVE → MOCK_TEST_SCHEDULED → REVISION_ACTIVE → EXAM_TAKEN
  → RESULTS_PENDING → RESULTS_KNOWN → (RETAKE | NEW_GOAL | ARCHIVED)

TRANSITIONS:
  ANONYMOUS → REGISTERED:         Signup form submitted
  REGISTERED → ONBOARDED:         Onboarding form submitted
  ONBOARDED → DIAGNOSTIC_IN_PROGRESS: Redirect to /diagnostic/start
  DIAGNOSTIC_IN_PROGRESS → DIAGNOSTIC_COMPLETE: All 3 sections submitted
  DIAGNOSTIC_COMPLETE → ROADMAP_ACTIVE: Roadmap generated
  ROADMAP_ACTIVE → MOCK_TEST_SCHEDULED: Scheduler triggers mock test
  MOCK_TEST_SCHEDULED → ROADMAP_ACTIVE: Post-mock re-calibration
  ROADMAP_ACTIVE → REVISION_ACTIVE: T-14 days from exam date
  REVISION_ACTIVE → EXAM_TAKEN: User marks exam as taken
  EXAM_TAKEN → RESULTS_PENDING: User indicates "I'm still waiting"
  EXAM_TAKEN → RESULTS_KNOWN: User enters scores
  RESULTS_PENDING → RESULTS_KNOWN: User enters scores (later)
  RESULTS_KNOWN → RETAKE: User chooses to retake
  RESULTS_KNOWN → NEW_GOAL: User sets new target
  RESULTS_KNOWN → ARCHIVED: User celebrates & leaves
  RETAKE → ROADMAP_ACTIVE: New roadmap generated
  NEW_GOAL → ONBOARDED: New goal set, new roadmap generated
```

## Appendix B: Data Flow Summary

| Screen | Reads From | Writes To | Triggers |
|---|---|---|---|
| Landing | — | — | — |
| Registration | — | `auth.users`, `users` | Auth session |
| Login | `auth.users` | — | Auth session |
| Onboarding | — | `users`, `user_goals` | Redirect to diagnostic |
| Diagnostic | `user_goals` | `diagnostic_results`, `progress` | Roadmap generation |
| Diagnostic Results | `diagnostic_results` | — | Roadmap generation |
| Roadmap | `diagnostic_results`, `user_goals` | `study_plans`, `daily_plans`, `tasks` | Daily mission generation |
| Dashboard | `daily_plans`, `tasks`, `streaks`, `band_predictions`, `assessments` | — | Streak check, daily rollover |
| Daily Mission | `daily_plans`, `tasks` | `task_completions`, `study_sessions`, `daily_activity`, `streaks` | Assessment creation, streak update |
| Writing Assessment | `tasks` | `assessments`, `progress` | Band prediction update |
| Speaking Assessment | `tasks` | `assessments`, `progress` | Band prediction update |
| Progress & Analytics | `assessments`, `progress`, `study_sessions`, `daily_activity`, `streaks`, `band_predictions` | — | — |
| Mock Tests | `mock_tests`, `tasks` | `mock_tests` (answers), `assessments`, `progress`, `band_predictions` | Roadmap re-calibration |
| Final Exam Prep | `user_goals`, `assessments`, `progress` | `tasks` (revision) | Protected revision window |
| Post-Exam | — | `mock_tests` (real exam), `users` (status) | Account lifecycle transition |

## Appendix C: Route Map

| Screen | Route | Auth Required | Layout |
|---|---|---|---|
| Landing | `/` | No | LandingLayout |
| Registration | `/signup` | No | AuthLayout |
| Login | `/login` | No | AuthLayout |
| Forgot Password | `/forgot-password` | No | AuthLayout |
| Onboarding | `/onboarding` | Yes | DashboardLayout |
| Diagnostic Overview | `/diagnostic` | Yes | DashboardLayout |
| Diagnostic Start | `/diagnostic/start` | Yes | DashboardLayout |
| Diagnostic Writing | `/diagnostic/writing` | Yes | DashboardLayout |
| Diagnostic Speaking | `/diagnostic/speaking` | Yes | DashboardLayout |
| Diagnostic Vocabulary | `/diagnostic/vocabulary` | Yes | DashboardLayout |
| Diagnostic Results | `/diagnostic/result` | Yes | DashboardLayout |
| Roadmap | `/roadmap` | Yes | DashboardLayout |
| Dashboard | `/dashboard` | Yes | DashboardLayout |
| Daily Mission | `/daily-mission` | Yes | DashboardLayout |
| Writing Practice | `/writing` | Yes | DashboardLayout |
| Speaking Practice | `/speaking` | Yes | DashboardLayout |
| Analytics | `/analytics` | Yes | DashboardLayout |
| Mock Test Overview | `/mock-test` | Yes | DashboardLayout |
| Mock Test In Progress | `/mock-test/{id}` | Yes | DashboardLayout |
| Mock Test Results | `/mock-test/{id}/results` | Yes | DashboardLayout |
| Final Review | `/final-review` | Yes | DashboardLayout |
| Post-Exam | `/post-exam` | Yes | DashboardLayout |
| Resources | `/resources` | No | LandingLayout |
| Profile | `/profile` | Yes | DashboardLayout |
| Settings | `/settings` | Yes | DashboardLayout |
| Notifications | `/notifications` | Yes | DashboardLayout |
| Privacy | `/privacy` | No | LandingLayout |
| Terms | `/terms` | No | LandingLayout |
| Cookies | `/cookies` | No | LandingLayout |

## Appendix D: Key Performance Indicators

| KPI | Target | Screen | Purpose |
|---|---|---|---|
| Landing → Signup conversion | ≥ 5% | Landing | Top-of-funnel health |
| Signup → Diagnostic completion | ≥ 80% | Registration → Diagnostic | Onboarding effectiveness |
| Diagnostic → Roadmap generation | ≥ 95% | Diagnostic Results | AI reliability |
| Dashboard return rate (DAU/MAU) | ≥ 40% | Dashboard | Engagement |
| Daily mission completion rate | ≥ 70% | Daily Mission | Stickiness |
| Streak retention (7+ day streak) | ≥ 50% | Dashboard | Habit formation |
| Mock test completion rate | ≥ 85% | Mock Tests | Commitment |
| Post-exam result entry rate | ≥ 60% | Post-Exam | Data collection |
| Retake rate (if below target) | ≥ 40% | Post-Exam | User retention |
| NPS (Net Promoter Score) | ≥ 50 | Post-Exam | Overall satisfaction |

---

*This document is a living artifact. It defines the complete user journey for the IELTS AI Coach platform, from first visit through post-exam reflection. All screen designs, inputs, outputs, navigation, and edge cases are documented to guide implementation across frontend, backend, and infrastructure teams.*
