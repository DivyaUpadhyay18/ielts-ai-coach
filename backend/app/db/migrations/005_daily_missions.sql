-- IELTS AI Coach - Daily Missions (v5)
-- Run this in your Supabase SQL editor after 004_resource_bookmarks.sql
--
-- Creates the daily_missions table for the Daily Mission system.
-- Each day has 6 skill missions (reading, listening, writing, speaking,
-- vocabulary, grammar) with estimated time, XP reward, completion %,
-- and status (pending, completed, skipped).

-- ============================================================
-- 1. daily_missions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.daily_missions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    mission_date DATE NOT NULL,
    skill TEXT NOT NULL CHECK (skill IN ('reading','listening','writing','speaking','vocabulary','grammar')),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
    estimated_minutes SMALLINT NOT NULL CHECK (estimated_minutes BETWEEN 1 AND 240),
    xp_reward SMALLINT NOT NULL DEFAULT 10 CHECK (xp_reward >= 0),
    completion_percent SMALLINT NOT NULL DEFAULT 0 CHECK (completion_percent BETWEEN 0 AND 100),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','completed','skipped')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, mission_date, skill)
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_daily_missions_user_date ON public.daily_missions(user_id, mission_date);
CREATE INDEX IF NOT EXISTS idx_daily_missions_status ON public.daily_missions(status);
CREATE INDEX IF NOT EXISTS idx_daily_missions_user_pending ON public.daily_missions(user_id) WHERE status = 'pending';

-- ============================================================
-- updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_daily_missions_updated_at ON public.daily_missions;
CREATE TRIGGER update_daily_missions_updated_at BEFORE UPDATE ON public.daily_missions
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.daily_missions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own daily missions" ON public.daily_missions;
CREATE POLICY "Users can view own daily missions" ON public.daily_missions FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own daily missions" ON public.daily_missions;
CREATE POLICY "Users can insert own daily missions" ON public.daily_missions FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own daily missions" ON public.daily_missions;
CREATE POLICY "Users can update own daily missions" ON public.daily_missions FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own daily missions" ON public.daily_missions;
CREATE POLICY "Users can delete own daily missions" ON public.daily_missions FOR DELETE USING (auth.uid() = user_id);