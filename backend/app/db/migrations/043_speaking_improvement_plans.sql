-- IELTS AI Coach — Speaking Improvement Plans (v43)
-- Run after 037_speaking_error_analysis.sql
--
-- Stores personalized "Improve My Speaking Band" plans generated after a
-- Speaking evaluation.  Each plan is tied to a single speaking response
-- (speaking_test_responses.id) and owned by the user.
--
-- Table: speaking_improvement_plans
--   → current_band, target_band, band_gap
--   → strongest_criterion, weakest_criterion
--   → criterion_priorities — per-criterion priority level (high/medium/low)
--   → current_level_description, target_level_description
--   → specific_changes, practice_exercises, recommended_resources
--   → practice_topics, suggested_daily_minutes, next_task
--   → suggested_mission (integration with Mission Engine)
--   → plan_json (full raw plan for audit / re-projection)

CREATE TABLE IF NOT EXISTS public.speaking_improvement_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    response_id     UUID NOT NULL REFERENCES public.speaking_test_responses(id)
        ON DELETE CASCADE,

    -- Core band numbers
    current_band    NUMERIC(3,1) NOT NULL,
    target_band     NUMERIC(3,1) NOT NULL,
    band_gap        NUMERIC(3,1) NOT NULL,

    -- Strongest / weakest criteria
    strongest_criterion  TEXT,
    weakest_criterion    TEXT,

    -- Per-criterion priority (fluency_coherence / lexical_resource /
    -- grammatical_range / pronunciation)
    criterion_priorities JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Human-readable structured content
    current_level_description  TEXT,
    target_level_description   TEXT,
    specific_changes      JSONB NOT NULL DEFAULT '[]'::jsonb,
    practice_exercises   JSONB NOT NULL DEFAULT '[]'::jsonb,
    practice_topics      JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommended_resources JSONB NOT NULL DEFAULT '[]'::jsonb,
    suggested_daily_minutes  INTEGER,
    next_speaking_task  TEXT,

    -- Integration hooks
    suggested_mission   JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Full raw plan snapshot
    plan_json        JSONB NOT NULL DEFAULT '{}'::jsonb,

    is_estimate      BOOLEAN NOT NULL DEFAULT TRUE,
    source           TEXT NOT NULL DEFAULT 'ai',

    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sip_response
    ON public.speaking_improvement_plans(response_id);
CREATE INDEX IF NOT EXISTS idx_sip_user_created
    ON public.speaking_improvement_plans(user_id, created_at DESC);

-- updated_at trigger
DROP TRIGGER IF EXISTS update_speaking_improvement_plans_updated_at ON public.speaking_improvement_plans;
CREATE TRIGGER update_speaking_improvement_plans_updated_at BEFORE UPDATE ON public.speaking_improvement_plans
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Row Level Security
ALTER TABLE public.speaking_improvement_plans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own speaking improvement plans" ON public.speaking_improvement_plans;
CREATE POLICY "Users can view own speaking improvement plans"
    ON public.speaking_improvement_plans FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own speaking improvement plans" ON public.speaking_improvement_plans;
CREATE POLICY "Users can insert own speaking improvement plans"
    ON public.speaking_improvement_plans FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own speaking improvement plans" ON public.speaking_improvement_plans;
CREATE POLICY "Users can update own speaking improvement plans"
    ON public.speaking_improvement_plans FOR UPDATE
    USING (auth.uid() = user_id);

GRANT ALL ON public.speaking_improvement_plans TO authenticated;
