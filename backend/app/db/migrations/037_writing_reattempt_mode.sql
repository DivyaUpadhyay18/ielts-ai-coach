-- IELTS AI Coach — Writing Reattempt Mode (v37)
-- Run this in your Supabase SQL editor after 036_writing_improvement_plans.sql
--
-- Reattempt Mode allows a student to retry the same writing task after
-- receiving an evaluation.  Each attempt is stored as a separate
-- writing_workspace_submissions row (immutable — submissions are locked
-- at submit time).  A lightweight writing_attempts table links attempts
-- together for comparison and bonus-XP computation.

-- ============================================================
-- 1. writing_attempts
-- ============================================================
CREATE TABLE IF NOT EXISTS public.writing_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- The original (first) submission that started this attempt chain.
    attempt_group UUID NOT NULL REFERENCES public.writing_workspace_submissions(id) ON DELETE CASCADE,

    -- This specific attempt's submission.
    submission_id UUID NOT NULL REFERENCES public.writing_workspace_submissions(id) ON DELETE CASCADE,

    -- Sequential attempt number (1 = first, 2 = reattempt, etc.)
    attempt_number INTEGER NOT NULL DEFAULT 1,

    -- When this attempt was evaluated.
    evaluated_at TIMESTAMPTZ DEFAULT NOW(),

    -- The overall band the student scored on this attempt.
    overall_band NUMERIC(3,1),

    -- Track whether a streak bonus / XP bonus was awarded for this attempt.
    bonus_xp INTEGER NOT NULL DEFAULT 0,
    bonus_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_writing_attempts_user
    ON public.writing_attempts(user_id);

CREATE INDEX IF NOT EXISTS idx_writing_attempts_group
    ON public.writing_attempts(attempt_group, attempt_number);

CREATE INDEX IF NOT EXISTS idx_writing_attempts_user_group
    ON public.writing_attempts(user_id, attempt_group);

-- ============================================================
-- 3. RLS
-- ============================================================
ALTER TABLE public.writing_attempts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own writing attempts" ON public.writing_attempts;
CREATE POLICY "Users can view own writing attempts"
    ON public.writing_attempts FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own writing attempts" ON public.writing_attempts;
CREATE POLICY "Users can insert own writing attempts"
    ON public.writing_attempts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ============================================================
-- 4. Grants
-- ============================================================
GRANT ALL ON public.writing_attempts TO authenticated;
