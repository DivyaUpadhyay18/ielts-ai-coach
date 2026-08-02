# Dashboard Build Plan

## Information Gathered

### Current State
- **Frontend**: Next.js 15, Tailwind CSS, Zustand (auth), axios (API client)
- **Backend**: FastAPI with auth (register/login/refresh/logout/me) and onboarding endpoints under `/api/v1`
- **Database**: `users` table with `target_band`, `exam_date`, `current_band`, `daily_minutes_budget`, `timezone`, `plan`, `onboarded_at`, etc.
- **Dashboard Spec**: 17 widgets defined in DASHBOARD.md with data contracts, refresh strategies, and zone model
- **Current Dashboard**: Uses mock data with basic layout (welcome header, 3 stat cards, quick actions, recent assessments, today's tasks, daily goal)
- **UI Components Available**: Card, Button, Badge, Progress, Skeleton, Avatar, Tabs, Textarea, Modal, Dropdown, Spinner
- **API client**: `frontend/src/services/api.ts` with `ieltsService`
- **Auth Store**: `useAuthStore` (Zustand) with user profile

### Required Sections
1. Exam Countdown
2. Today's Mission
3. Current Band
4. Target Band
5. Predicted Band (placeholder)
6. Today's Progress
7. Study Time
8. XP
9. Current Streak
10. Daily Goal
11. Weekly Goal
12. Continue Learning
13. Upcoming Mock Test
14. Recent Activity
15. Motivational Card
16. Notifications
17. Responsive & Modern UI

## Plan

### Step 1: Create Backend Dashboard API Endpoint
- Create `backend/app/api/v1/dashboard.py` with a `GET /dashboard/overview` endpoint
- Return placeholder data structure matching the required sections
- Register the router in `backend/app/api/v1/router.py`
- Use `get_current_user` dependency for auth

### Step 2: Create Frontend Dashboard Types
- Define TypeScript interfaces for dashboard data in `frontend/src/types/index.ts`
- Create a `useDashboardStore` (Zustand) or direct API service for fetching dashboard data

### Step 3: Create Frontend Dashboard API Service
- Add dashboard API methods to `frontend/src/services/api.ts`
- Implement `getDashboardOverview()` and `getTodayMission()` functions

### Step 4: Build Dashboard Page Components
- Rewrite `frontend/src/app/dashboard/page.tsx` with all 16+ sections
- Create reusable widget components grouped by zone:
  - **Zone 1 (Goal Cluster)**: Exam Countdown, Current Band, Target Band, Predicted Band, Current Streak
  - **Zone 2 (Action Surface)**: Today's Mission, Continue Learning, Today's Progress, Study Time, Daily Goal, Weekly Goal
  - **Zone 3 (Progress Rail)**: XP, Upcoming Mock Test, Recent Activity, Motivational Card
  - **Zone 4 (Header/Footer)**: Notifications (badge in header), Weekly Goal

### Step 5: Make it Responsive
- Use Tailwind responsive grid classes
- Mobile-first layout with proper stacking
- Zone model degrades gracefully on mobile

### Step 6: Modern UI Polish
- Gradient backgrounds, hover effects, shadows
- Smooth animations (fade-in, slide-up)
- Skeleton loading states
- Dark mode compatible

## Files to Edit
1. `backend/app/api/v1/dashboard.py` — NEW file
2. `backend/app/api/v1/router.py` — Add dashboard router
3. `frontend/src/types/index.ts` — Add dashboard types
4. `frontend/src/services/api.ts` — Add dashboard API methods
5. `frontend/src/app/dashboard/page.tsx` — Rewrite with all sections

## Follow-up Steps
- Test the backend endpoint
- Verify the frontend renders correctly
- Ensure responsive behavior on mobile/tablet/desktop

## Questions for Approval
- Should I proceed with building this plan?
- Any changes to the section layout or priority?
