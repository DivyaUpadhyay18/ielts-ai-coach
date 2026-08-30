-- IELTS AI Coach — Speaking Test Workspace (v040)
-- Run this in your Supabase SQL editor after 039_writing_coaching_conversations.sql
--
-- The Speaking Test Workspace is a full-mock exam environment that lets users
-- practice the complete IELTS Speaking test (Part 1, Part 2, Part 3) with:
--   • Per-question recording with MediaRecorder
--   • Preparation timers (Part 2 gets a 60-second prep phase)
--   • Speaking timers per question
--   • Playback, delete/re-record, save, and continue
--   • Automatic progress saving and resume across browser sessions
--
-- Two tables:
--   speaking_test_sessions  — one row per full 3-part test attempt
--   speaking_test_responses — one row per recorded question response
--
-- Prompts are sourced from the existing speaking_prompts table (v023), which
-- already seeds Part 1 / Part 2 / Part 3 questions with prep & speak times.

-- ============================================================
-- 1. speaking_test_sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.speaking_test_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    current_part TEXT NOT NULL DEFAULT 'part_1'
        CHECK (current_part IN ('part_1','part_2','part_3')),
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress','completed','abandoned')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_speaking_test_sessions_user
    ON public.speaking_test_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_speaking_test_sessions_user_status
    ON public.speaking_test_sessions(user_id, status, started_at DESC);

-- ============================================================
-- 2. speaking_test_responses
-- ============================================================
CREATE TABLE IF NOT EXISTS public.speaking_test_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.speaking_test_sessions(id)
        ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    prompt_id UUID REFERENCES public.speaking_prompts(id) ON DELETE SET NULL,
    part TEXT NOT NULL DEFAULT 'part_1'
        CHECK (part IN ('part_1','part_2','part_3')),
    title TEXT NOT NULL DEFAULT '',
    prompt_text TEXT NOT NULL DEFAULT '',
    prep_time_seconds INTEGER NOT NULL DEFAULT 0,
    speak_time_seconds INTEGER NOT NULL DEFAULT 60,
    -- audio asset stored in Supabase Storage (public URL)
    audio_url TEXT NOT NULL DEFAULT '',
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    transcript TEXT NOT NULL DEFAULT '',
    is_saved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_speaking_test_responses_session
    ON public.speaking_test_responses(session_id);
CREATE INDEX IF NOT EXISTS idx_speaking_test_responses_user
    ON public.speaking_test_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_speaking_test_responses_part
    ON public.speaking_test_responses(part);

-- ============================================================
-- 3. updated_at triggers
-- ============================================================
DROP TRIGGER IF EXISTS update_speaking_test_sessions_updated_at
    ON public.speaking_test_sessions;
CREATE TRIGGER update_speaking_test_sessions_updated_at
    BEFORE UPDATE ON public.speaking_test_sessions
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_speaking_test_responses_updated_at
    ON public.speaking_test_responses;
CREATE TRIGGER update_speaking_test_responses_updated_at
    BEFORE UPDATE ON public.speaking_test_responses
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 4. Row Level Security
-- ============================================================
ALTER TABLE public.speaking_test_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.speaking_test_responses ENABLE ROW LEVEL SECURITY;

-- Sessions owner-scoped.
DROP POLICY IF EXISTS "Users can view own speaking test sessions" ON public.speaking_test_sessions;
CREATE POLICY "Users can view own speaking test sessions" ON public.speaking_test_sessions FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own speaking test sessions" ON public.speaking_test_sessions;
CREATE POLICY "Users can insert own speaking test sessions" ON public.speaking_test_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own speaking test sessions" ON public.speaking_test_sessions;
CREATE POLICY "Users can update own speaking test sessions" ON public.speaking_test_sessions FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own speaking test sessions" ON public.speaking_test_sessions;
CREATE POLICY "Users can delete own speaking test sessions" ON public.speaking_test_sessions FOR DELETE
    USING (auth.uid() = user_id);

-- Responses owner-scoped.
DROP POLICY IF EXISTS "Users can view own speaking test responses" ON public.speaking_test_responses;
CREATE POLICY "Users can view own speaking test responses" ON public.speaking_test_responses FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own speaking test responses" ON public.speaking_test_responses;
CREATE POLICY "Users can insert own speaking test responses" ON public.speaking_test_responses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own speaking test responses" ON public.speaking_test_responses;
CREATE POLICY "Users can update own speaking test responses" ON public.speaking_test_responses FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own speaking test responses" ON public.speaking_test_responses;
CREATE POLICY "Users can delete own speaking test responses" ON public.speaking_test_responses FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- 5. Grants
-- ============================================================
GRANT ALL ON public.speaking_test_sessions TO authenticated;
GRANT ALL ON public.speaking_test_responses TO authenticated;
