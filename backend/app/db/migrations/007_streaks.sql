-- IELTS AI Coach - Streak System (v7)
-- Run this in your Supabase SQL editor after 006_progress_tracking.sql
--
-- Extends the Progress Tracking system with a full Streak System:
--   - daily, weekly, monthly streaks (stored on progress_state)
--   - XP milestone bonuses (daily: 7/14/21/30/60/100, weekly: every 4th,
--     monthly: every month, perfect-day: +25)
--   - perfect-day bonus (all 6 missions completed, none skipped)
--   - carry-forward minutes (surplus banked to cover a missed day)
--   - streak freezes (placeholder table + events ledger for idempotent awards)
--
-- No AI. All calculations are deterministic and derived from the
-- study_sessions / daily_stats / daily_missions ledger tables.

-- ============================================================
-- 1. Extend progress_state with streak system columns
-- ============================================================
ALTER TABLE public.progress_state
    ADD COLUMN IF NOT EXISTS weekly_streak SMALLINT NOT NULL DEFAULT 0 CHECK (weekly_streak >= 0),
    ADD COLUMN IF NOT EXISTS longest_weekly_streak SMALLINT NOT NULL DEFAULT 0 CHECK (longest_weekly_streak >= 0),
    ADD COLUMN IF NOT EXISTS monthly_streak SMALLINT NOT NULL DEFAULT 0 CHECK (monthly_streak >= 0),
    ADD COLUMN IF NOT EXISTS longest_monthly_streak SMALLINT NOT NULL DEFAULT 0 CHECK (longest_monthly_streak >= 0),
    ADD COLUMN IF NOT EXISTS perfect_day_count INTEGER NOT NULL DEFAULT 0 CHECK (perfect_day_count >= 0),
    ADD COLUMN IF NOT EXISTS bonus_xp INTEGER NOT NULL DEFAULT 0 CHECK (bonus_xp >= 0),
    ADD COLUMN IF NOT EXISTS carry_forward_minutes SMALLINT NOT NULL DEFAULT 0 CHECK (carry_forward_minutes >= 0),
    ADD COLUMN IF NOT EXISTS last_streak_update DATE;

-- ============================================================
-- 2. streak_freezes (placeholder streak protection)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.streak_freezes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    period_type TEXT NOT NULL DEFAULT 'day' CHECK (period_type IN ('day','week','month')),
    status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available','used','expired')),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    source TEXT NOT NULL DEFAULT 'placeholder' CHECK (source IN ('placeholder','purchase','reward','system')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_streak_freezes_user_status ON public.streak_freezes(user_id, status);

-- ============================================================
-- 3. streak_events (idempotent bonus-award ledger)
--    UNIQUE (user_id, event_type, period_key) prevents double awards.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.streak_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('perfect_day','daily_milestone','weekly_milestone','monthly_milestone')
    ),
    period_key TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    xp_awarded SMALLINT NOT NULL DEFAULT 0 CHECK (xp_awarded >= 0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, event_type, period_key)
);

CREATE INDEX IF NOT EXISTS idx_streak_events_user_created ON public.streak_events(user_id, created_at DESC);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.streak_freezes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.streak_events ENABLE ROW LEVEL SECURITY;

-- streak_freezes
DROP POLICY IF EXISTS "Users can view own streak freezes" ON public.streak_freezes;
CREATE POLICY "Users can view own streak freezes" ON public.streak_freezes FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own streak freezes" ON public.streak_freezes;
CREATE POLICY "Users can insert own streak freezes" ON public.streak_freezes FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own streak freezes" ON public.streak_freezes;
CREATE POLICY "Users can update own streak freezes" ON public.streak_freezes FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own streak freezes" ON public.streak_freezes;
CREATE POLICY "Users can delete own streak freezes" ON public.streak_freezes FOR DELETE USING (auth.uid() = user_id);

-- streak_events
DROP POLICY IF EXISTS "Users can view own streak events" ON public.streak_events;
CREATE POLICY "Users can view own streak events" ON public.streak_events FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own streak events" ON public.streak_events;
CREATE POLICY "Users can insert own streak events" ON public.streak_events FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own streak events" ON public.streak_events;
CREATE POLICY "Users can update own streak events" ON public.streak_events FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own streak events" ON public.streak_events;
CREATE POLICY "Users can delete own streak events" ON public.streak_events FOR DELETE USING (auth.uid() = user_id);

