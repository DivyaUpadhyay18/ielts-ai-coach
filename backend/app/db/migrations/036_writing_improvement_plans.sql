-- IELTS AI Coach — Writing Improvement Plans (v36)
-- Run after 035_writing_error_analysis.sql
--
-- Stores personalized "Improve My Band" plans generated after a Writing
-- evaluation.  Each plan is tied to a single evaluation and owned by the
-- user who wrote the essay.
--
-- Table: writing_improvement_plans
--   → current_band, target_band, gap
--   → weaknesses (array of criterion keys)
--   → current_level_description — plain-text summary of what the student is doing well / poorly
--   → target_level_description — what a Band 8+ response requires
--   → specific_changes     — structured list of concrete changes to make
--   → practice_exercises   — list of exercise descriptors
--   → recommended_resources — array of {resource_id, title, url, why}
--   → suggested_mission    — {task_id, title, skill, duration_minutes, ...}
--   → plan_json            — the full raw plan (for re-projection / future diffing)
--   → is_estimate          — always true (AI generated)

CREATE TABLE IF NOT EXISTS public.writing_improvement_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    evaluation_id   UUID NOT NULL REFERENCES public.writing_evaluations(id) ON DELETE CASCADE,
    submission_id   UUID NOT NULL REFERENCES public.writing_workspace_submissions(id) ON DELETE CASCADE,
    task_type       TEXT NOT NULL CHECK (task_type IN ('task_1', 'task_2')),

    -- Core band numbers
    current_band    NUMERIC(3,1) NOT NULL,
    target_band     NUMERIC(3,1) NOT NULL,
    band_gap        NUMERIC(3,1) NOT NULL,

    -- The student's weakest criteria, ranked (e.g. ["task_response", "grammatical_range_accuracy"])
    weaknesses      TEXT[] NOT NULL DEFAULT '{}',

    -- Human-readable structured content
    current_level_description  TEXT,
    target_level_description   TEXT,
    specific_changes  JSONB NOT NULL DEFAULT '[]'::jsonb,
    practice_exercises JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommended_resources JSONB NOT NULL DEFAULT '[]'::jsonb,
    suggested_mission  JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Full raw plan snapshot (for audit / re-projection)
    plan_json        JSONB NOT NULL DEFAULT '{}'::jsonb,

    is_estimate      BOOLEAN NOT NULL DEFAULT TRUE,
    source           TEXT NOT NULL DEFAULT 'ai',

    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_wip_evaluation
    ON public.writing_improvement_plans(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_wip_user_created
    ON public.writing_improvement_plans(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wip_submission
    ON public.writing_improvement_plans(submission_id);

-- updated_at trigger
DROP TRIGGER IF EXISTS update_writing_improvement_plans_updated_at ON public.writing_improvement_plans;
CREATE TRIGGER update_writing_improvement_plans_updated_at BEFORE UPDATE ON public.writing_improvement_plans
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Row Level Security
ALTER TABLE public.writing_improvement_plans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own improvement plans" ON public.writing_improvement_plans;
CREATE POLICY "Users can view own improvement plans"
    ON public.writing_improvement_plans FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own improvement plans" ON public.writing_improvement_plans;
CREATE POLICY "Users can insert own improvement plans"
    ON public.writing_improvement_plans FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own improvement plans" ON public.writing_improvement_plans;
CREATE POLICY "Users can update own improvement plans"
    ON public.writing_improvement_plans FOR UPDATE
    USING (auth.uid() = user_id);

-- Evaluations are immutable — no DELETE policy.

GRANT ALL ON public.writing_improvement_plans TO authenticated;
