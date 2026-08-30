-- IELTS AI Coach — Writing Band Examples (v36)
-- Run after 036_writing_improvement_plans.sql
--
-- Stores AI-generated band-level example essays and improvements that
-- illustrate how to address specific weaknesses identified in an
-- evaluation or improvement plan.
--
-- Each example is tied to a submission (the student's original essay) and
-- can optionally reference a target band level.

CREATE TABLE IF NOT EXISTS public.writing_band_examples (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    submission_id   UUID NOT NULL REFERENCES public.writing_workspace_submissions(id) ON DELETE CASCADE,
    task_type       TEXT NOT NULL CHECK (task_type IN ('task_1', 'task_2')),
    target_band     NUMERIC(3,1),

    -- The weak areas this example addresses (e.g. ["Grammar", "Vocabulary"])
    focus_areas     TEXT[] NOT NULL DEFAULT '{}',

    -- Structured example content
    key_weaknesses  TEXT NOT NULL DEFAULT '',                  -- summary of key weaknesses
    improved_sentences JSONB NOT NULL DEFAULT '[]'::jsonb,    -- [{original, improved, explanation}]
    vocabulary_alternatives JSONB NOT NULL DEFAULT '[]'::jsonb, -- [{from, to, why}]
    paragraph_structure TEXT,                                  -- description + guide
    example_introduction TEXT,                                 -- full intro paragraph
    example_body_paragraph TEXT,                               -- full body paragraph
    example_conclusion TEXT,                                   -- full conclusion

    -- Full sample answer (if generated)
    sample_answer   TEXT,                                      -- may be null if not generated
    is_sample_answer BOOLEAN NOT NULL DEFAULT FALSE,

    -- Full raw JSON snapshot (for audit / re-projection)
    plan_json       JSONB NOT NULL DEFAULT '{}'::jsonb,

    is_estimate     BOOLEAN NOT NULL DEFAULT TRUE,
    source          TEXT NOT NULL DEFAULT 'ai',

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_wbe_submission
    ON public.writing_band_examples(submission_id);
CREATE INDEX IF NOT EXISTS idx_wbe_user_created
    ON public.writing_band_examples(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wbe_focus
    ON public.writing_band_examples USING GIN (focus_areas);

-- Row Level Security
ALTER TABLE public.writing_band_examples ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own band examples" ON public.writing_band_examples;
CREATE POLICY "Users can view own band examples"
    ON public.writing_band_examples FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own band examples" ON public.writing_band_examples;
CREATE POLICY "Users can insert own band examples"
    ON public.writing_band_examples FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Immutable — no UPDATE or DELETE policies.

GRANT ALL ON public.writing_band_examples TO authenticated;
