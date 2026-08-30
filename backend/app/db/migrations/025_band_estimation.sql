-- IELTS AI Coach — Band Estimation Engine (v25)
-- Run this in your Supabase SQL editor after 024_vocab_grammar_diagnostic.sql
--
-- Adds a deterministic (NO AI) Band Estimation Engine that maps a user's
-- skill-wise band scores (reading, listening, writing, speaking, vocabulary,
-- grammar) to an estimated overall IELTS band, per-skill bands, a confidence
-- score, weakest/strongest skills, and per-skill explanations.
--
-- Requirements covered:
--   - Estimated Overall Band
--   - Skill-wise Band
--   - Confidence Score
--   - Weakest Skills
--   - Strongest Skills
--   - Explain why each score was assigned
--   - Store results (band_estimations history)

-- ============================================================
-- 1. band_estimations
-- ============================================================
CREATE TABLE IF NOT EXISTS public.band_estimations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- The date this estimation was computed for (defaults to today).
    run_date DATE NOT NULL DEFAULT CURRENT_DATE,

    -- Core outputs
    overall_band NUMERIC(3,1) NOT NULL,            -- 0.0–9.0 in 0.5 steps
    confidence_score NUMERIC(5,2) NOT NULL,        -- 0–100
    confidence_label TEXT NOT NULL DEFAULT 'medium' CHECK (
        confidence_label IN ('low','medium','high','very_high')
    ),

    -- Per-skill bands: {skill: band}
    skill_bands JSONB NOT NULL DEFAULT '{}',

    -- Weakest skills (ascending band order, then name)
    weakest_skills JSONB NOT NULL DEFAULT '[]',

    -- Strongest skills (descending band order, then name)
    strongest_skills JSONB NOT NULL DEFAULT '[]',

    -- Per-skill explanations: {skill: explanation_text}
    explanations JSONB NOT NULL DEFAULT '{}',

    -- Human-readable formula documentation
    formulas_json JSONB NOT NULL DEFAULT '{}',

    -- Raw input snapshot for audit
    raw_input JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One estimation per user per day (re-runs overwrite).
    UNIQUE (user_id, run_date)
);

CREATE INDEX IF NOT EXISTS idx_band_estimations_user ON public.band_estimations(user_id);
CREATE INDEX IF NOT EXISTS idx_band_estimations_user_date ON public.band_estimations(user_id, run_date DESC);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.band_estimations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own band estimations" ON public.band_estimations;
CREATE POLICY "Users can view own band estimations" ON public.band_estimations FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own band estimations" ON public.band_estimations;
CREATE POLICY "Users can insert own band estimations" ON public.band_estimations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own band estimations" ON public.band_estimations;
CREATE POLICY "Users can update own band estimations" ON public.band_estimations FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own band estimations" ON public.band_estimations;
CREATE POLICY "Users can delete own band estimations" ON public.band_estimations FOR DELETE
    USING (auth.uid() = user_id);
