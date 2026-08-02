-- IELTS AI Coach - Progress Tracking (v6)
-- Run this in your Supabase SQL editor after 005_daily_missions.sql
--
-- Creates the tables that back the Progress Tracking system:
--   - study_sessions   : append-only log of every study activity (minutes + XP)
--   - daily_stats      : per-user/day cached aggregates (minutes, tasks, XP, streak)
--   - progress_state   : per-user lifetime aggregate (total XP/minutes/tasks, level)
-- Everything is stored in the database and derived through this schema
-- (no AI scheduling, no client-side fabrication). XP follows the
-- gamification curve: level_n_required_xp = 100 * n^1.35.

-- ============================================================
-- 1. study_sessions (append-only activity ledger)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.study_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    activity_date DATE NOT NULL,
    skill TEXT,
    session_type TEXT NOT NULL DEFAULT 'mission' CHECK (
        session_type IN ('mission','task','writing','speaking','reading','listening','vocabulary','grammar','assessment','mock_test','resource')
    ),
    minutes SMALLINT NOT NULL DEFAULT 10 CHECK (minutes BETWEEN 1 AND 600),
    xp_earned SMALLINT NOT NULL DEFAULT 0 CHECK (xp_earned >= 0),
    source_type TEXT NOT NULL DEFAULT 'mission' CHECK (source_type IN ('mission','task','assessment','manual','resource')),
    source_id TEXT,
    meta JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_study_sessions_user_date ON public.study_sessions(user_id, activity_date);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user_created ON public.study_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user_type ON public.study_sessions(user_id, session_type);

-- ============================================================
-- 2. daily_stats (per-user/day cached aggregates)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.daily_stats (
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    stats_date DATE NOT NULL,
    minutes SMALLINT NOT NULL DEFAULT 0 CHECK (minutes >= 0),
    tasks_completed SMALLINT NOT NULL DEFAULT 0 CHECK (tasks_completed >= 0),
    xp_earned SMALLINT NOT NULL DEFAULT 0 CHECK (xp_earned >= 0),
    is_active BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, stats_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_user_date ON public.daily_stats(user_id, stats_date DESC);

-- ============================================================
-- 3. progress_state (lifetime aggregate per user)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.progress_state (
    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    total_minutes INTEGER NOT NULL DEFAULT 0 CHECK (total_minutes >= 0),
    total_tasks INTEGER NOT NULL DEFAULT 0 CHECK (total_tasks >= 0),
    total_xp INTEGER NOT NULL DEFAULT 0 CHECK (total_xp >= 0),
    level SMALLINT NOT NULL DEFAULT 1 CHECK (level >= 1),
    level_progress NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (level_progress >= 0 AND level_progress <= 1),
    current_streak SMALLINT NOT NULL DEFAULT 0 CHECK (current_streak >= 0),
    longest_streak SMALLINT NOT NULL DEFAULT 0 CHECK (longest_streak >= 0),
    last_active_date DATE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- updated_at trigger (shared function from v3)
-- ============================================================
DROP TRIGGER IF EXISTS update_daily_stats_updated_at ON public.daily_stats;
CREATE TRIGGER update_daily_stats_updated_at BEFORE UPDATE ON public.daily_stats
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_progress_state_updated_at ON public.progress_state;
CREATE TRIGGER update_progress_state_updated_at BEFORE UPDATE ON public.progress_state
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.study_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.progress_state ENABLE ROW LEVEL SECURITY;

-- study_sessions
DROP POLICY IF EXISTS "Users can view own study sessions" ON public.study_sessions;
CREATE POLICY "Users can view own study sessions" ON public.study_sessions FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own study sessions" ON public.study_sessions;
CREATE POLICY "Users can insert own study sessions" ON public.study_sessions FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own study sessions" ON public.study_sessions;
CREATE POLICY "Users can update own study sessions" ON public.study_sessions FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own study sessions" ON public.study_sessions;
CREATE POLICY "Users can delete own study sessions" ON public.study_sessions FOR DELETE USING (auth.uid() = user_id);

-- daily_stats
DROP POLICY IF EXISTS "Users can view own daily stats" ON public.daily_stats;
CREATE POLICY "Users can view own daily stats" ON public.daily_stats FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own daily stats" ON public.daily_stats;
CREATE POLICY "Users can insert own daily stats" ON public.daily_stats FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own daily stats" ON public.daily_stats;
CREATE POLICY "Users can update own daily stats" ON public.daily_stats FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own daily stats" ON public.daily_stats;
CREATE POLICY "Users can delete own daily stats" ON public.daily_stats FOR DELETE USING (auth.uid() = user_id);

-- progress_state
DROP POLICY IF EXISTS "Users can view own progress state" ON public.progress_state;
CREATE POLICY "Users can view own progress state" ON public.progress_state FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own progress state" ON public.progress_state;
CREATE POLICY "Users can insert own progress state" ON public.progress_state FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own progress state" ON public.progress_state;
CREATE POLICY "Users can update own progress state" ON public.progress_state FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own progress state" ON public.progress_state;
CREATE POLICY "Users can delete own progress state" ON public.progress_state FOR DELETE USING (auth.uid() = user_id);

