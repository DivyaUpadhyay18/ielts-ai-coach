-- IELTS AI Coach — Speaking Error Analysis (v37)
--
-- Stores AI-generated error analysis for a recorded Speaking response.
-- One analysis per recording (speaking_test_responses.id).
--
-- Each issue is stored as a JSONB array element so the full analysis is
-- always retrievable and can be re-projected.  The table is immutable
-- (insert-only): re-analysis creates a new row, preserving history.

CREATE TABLE IF NOT EXISTS public.speaking_error_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    response_id UUID NOT NULL REFERENCES public.speaking_test_responses(id)
        ON DELETE CASCADE,
    part TEXT NOT NULL DEFAULT 'part_1'
        CHECK (part IN ('part_1', 'part_2', 'part_3')),

    -- The transcript that was analysed
    transcript TEXT NOT NULL DEFAULT '',

    -- Aggregated AI assessment
    overall_band NUMERIC(3,1),
    fluency_coherence_band NUMERIC(3,1),
    lexical_resource_band NUMERIC(3,1),
    grammatical_range_band NUMERIC(3,1),
    pronunciation_band NUMERIC(3,1),

    -- Severity counts (denormalised for quick display)
    issue_count INTEGER NOT NULL DEFAULT 0,
    high_severity_count INTEGER NOT NULL DEFAULT 0,
    medium_severity_count INTEGER NOT NULL DEFAULT 0,
    low_severity_count INTEGER NOT NULL DEFAULT 0,

    -- Full structured issue list (can be re-projected at any time)
    issues JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- AI summary feedback
    feedback TEXT,

    is_estimate BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT NOT NULL DEFAULT 'ai',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sea_response 
    ON public.speaking_error_analysis(response_id);
CREATE INDEX IF NOT EXISTS idx_sea_user_created 
    ON public.speaking_error_analysis(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sea_part 
    ON public.speaking_error_analysis(part);
CREATE INDEX IF NOT EXISTS idx_sea_severity 
    ON public.speaking_error_analysis USING GIN (issues jsonb_path_ops);

-- Row Level Security
ALTER TABLE public.speaking_error_analysis ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own speaking error analyses" ON public.speaking_error_analysis;
CREATE POLICY "Users can view own speaking error analyses" ON public.speaking_error_analysis FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own speaking error analyses" ON public.speaking_error_analysis;
CREATE POLICY "Users can insert own speaking error analyses" ON public.speaking_error_analysis FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Immutable — no UPDATE or DELETE policies.

GRANT ALL ON public.speaking_error_analysis TO authenticated;
