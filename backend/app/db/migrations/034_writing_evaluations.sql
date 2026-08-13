-- IELTS AI Coach — Writing Evaluations (v34)
-- Run this in your Supabase SQL editor after 033_writing_workspace.sql
--
-- Stores the complete AI evaluation for submitted Writing Workspace essays.
-- All evaluations are immutable (created at evaluation time, never updated).
-- The evaluation JSON is also stored on writing_workspace_submissions.ai_evaluation
-- for read-side convenience.
--
-- Table:
--   writing_evaluations
--     → per-user evaluation records tied to a submission
--     → stores all 4 criteria bands, overall band, confidence
--     → strengths, weaknesses, errors, suggestions (flattened)
--     → is_estimate flag (always true — AI estimate, not official IELTS)

-- ============================================================
-- 1. writing_evaluations
-- ============================================================
CREATE TABLE IF NOT EXISTS public.writing_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    submission_id UUID NOT NULL REFERENCES public.writing_workspace_submissions(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL CHECK (task_type IN ('task_1', 'task_2')),

    -- Core scores
    overall_band NUMERIC(3,1),         -- 0-9 in 0.5 steps
    confidence NUMERIC(3,2),            -- 0.00-1.00
    criteria_bands JSONB NOT NULL DEFAULT '{}'::jsonb,    -- {criterion: band}
    criteria_detail JSONB NOT NULL DEFAULT '{}'::jsonb,   -- full per-criterion detail

    -- Aggregated insights (flattened from criteria)
    strengths JSONB NOT NULL DEFAULT '[]'::jsonb,
    weaknesses JSONB NOT NULL DEFAULT '[]'::jsonb,
    errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,

    word_count INTEGER NOT NULL DEFAULT 0,
    is_estimate BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT NOT NULL DEFAULT 'ai',   -- 'ai' or 'deterministic_fallback'
    evaluated_at TIMESTAMPTZ DEFAULT NOW(),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_writing_evaluations_user
    ON public.writing_evaluations(user_id);

CREATE INDEX IF NOT EXISTS idx_writing_evaluations_submission
    ON public.writing_evaluations(submission_id);

CREATE INDEX IF NOT EXISTS idx_writing_evaluations_user_created
    ON public.writing_evaluations(user_id, created_at DESC);

-- ============================================================
-- 2b. Evaluation lifecycle status
-- ============================================================
-- AI scoring is NOT implemented in this phase.  Every submitted essay gets
-- a record created in the 'pending' state; a future phase fills it in and
-- flips it to 'evaluated'.
ALTER TABLE public.writing_evaluations
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'evaluated'));

CREATE INDEX IF NOT EXISTS idx_writing_evaluations_status
    ON public.writing_evaluations(status);

-- ============================================================
-- 3. RLS
-- ============================================================
ALTER TABLE public.writing_evaluations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own writing evaluations" ON public.writing_evaluations;
CREATE POLICY "Users can view own writing evaluations"
    ON public.writing_evaluations FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own writing evaluations" ON public.writing_evaluations;
CREATE POLICY "Users can insert own writing evaluations"
    ON public.writing_evaluations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Evaluations are immutable — no UPDATE or DELETE policies.

-- ============================================================
-- 4. Grants
-- ============================================================
GRANT ALL ON public.writing_evaluations TO authenticated;
