-- IELTS AI Coach - Motivation Engine (v30)
-- Run this in your Supabase SQL editor after 029_ai_recommendations.sql
--
-- The Motivation Engine generates personalized, non-repetitive, professional
-- motivational messages for key student moments:
--   mission_complete / missed_day / streak_7 / streak_30 /
--   band_improvement / mock_test / exam_week / final_day
--
-- Design:
--   - Deterministic message bank + anti-repetition rotation (no randomness).
--   - UNIQUE (user_id, moment, period_key) guarantees each moment+period
--     yields exactly ONE stored message (idempotent delivery).
--   - `context` JSONB captures the learner snapshot at message time.
--
-- No AI. All messages are derived from a professional template bank and the
-- student's stored data (profile, streak, missions, assessments, mocks, exam).

-- ============================================================
-- 1. motivation_messages (delivery ledger)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.motivation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    moment TEXT NOT NULL CHECK (
        moment IN ('mission_complete','missed_day','streak_7','streak_30',
                   'band_improvement','mock_test','exam_week','final_day',
                   'general')
    ),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tone TEXT NOT NULL DEFAULT 'encouraging' CHECK (tone IN ('encouraging','firm','celebratory','calm','neutral')),
    variant TEXT NOT NULL DEFAULT '',
    period_key TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- One message per (moment, period_key) per user — idempotent delivery.
    UNIQUE (user_id, moment, period_key)
);

CREATE INDEX IF NOT EXISTS idx_motivation_messages_user_created
    ON public.motivation_messages(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_motivation_messages_user_moment
    ON public.motivation_messages(user_id, moment);

-- ============================================================
-- 2. Row Level Security
-- ============================================================
ALTER TABLE public.motivation_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own motivation messages" ON public.motivation_messages;
CREATE POLICY "Users can view own motivation messages" ON public.motivation_messages
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own motivation messages" ON public.motivation_messages;
CREATE POLICY "Users can insert own motivation messages" ON public.motivation_messages
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own motivation messages" ON public.motivation_messages;
CREATE POLICY "Users can update own motivation messages" ON public.motivation_messages
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own motivation messages" ON public.motivation_messages;
CREATE POLICY "Users can delete own motivation messages" ON public.motivation_messages
    FOR DELETE USING (auth.uid() = user_id);

GRANT ALL ON public.motivation_messages TO authenticated;