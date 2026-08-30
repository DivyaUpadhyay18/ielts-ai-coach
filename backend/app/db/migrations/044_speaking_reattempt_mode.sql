-- IELTS AI Coach — Speaking Reattempt Mode (v44)
--
-- Reattempt Mode allows a student to retry the same Speaking question
-- after receiving an evaluation.  Each attempt is stored as a separate
-- speaking_test_responses row (immutable — responses are locked at save time).
-- A lightweight speaking_attempts table links attempts together for
-- comparison and bonus-XP computation.

-- ============================================================
-- 1. speaking_attempts
-- ============================================================
CREATE TABLE IF NOT EXISTS public.speaking_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- The original (first) response that started this attempt chain.
    attempt_group UUID NOT NULL REFERENCES public.speaking_test_responses(id)
        ON DELETE CASCADE,

    -- This specific attempt's response.
    response_id UUID NOT NULL REFERENCES public.speaking_test_responses(id)
        ON DELETE CASCADE,

    -- Sequential attempt number (1 = first, 2 = reattempt, etc.)
    attempt_number INTEGER NOT NULL DEFAULT 1,

    -- When this attempt was evaluated.
    evaluated_at TIMESTAMPTZ DEFAULT NOW(),

    -- The overall band the student scored on this attempt.
    overall_band NUMERIC(3,1),

    -- Per-criterion bands for this attempt.
    fluency_coherence_band NUMERIC(3,1),
    lexical_resource_band NUMERIC(3,1),
    grammatical_range_band NUMERIC(3,1),
    pronunciation_band NUMERIC(3,1),

    -- Duration of this attempt in seconds.
    duration_seconds INTEGER,

    -- Filler word count (detected by the AI service).
    filler_words_count INTEGER NOT NULL DEFAULT 0,

    -- Error count from the error analysis.
    error_count INTEGER NOT NULL DEFAULT 0,

    -- Track whether a streak bonus / XP bonus was awarded for this attempt.
    bonus_xp INTEGER NOT NULL DEFAULT 0,
    bonus_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_speaking_attempts_user
    ON public.speaking_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_speaking_attempts_group
    ON public.speaking_attempts(attempt_group, attempt_number);
CREATE INDEX IF NOT EXISTS idx_speaking_attempts_user_group
    ON public.speaking_attempts(user_id, attempt_group);

-- ============================================================
-- 3. RLS
-- ============================================================
ALTER TABLE public.speaking_attempts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own speaking attempts" ON public.speaking_attempts;
CREATE POLICY "Users can view own speaking attempts"
    ON public.speaking_attempts FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own speaking attempts" ON public.speaking_attempts;
CREATE POLICY "Users can insert own speaking attempts"
    ON public.speaking_attempts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own speaking attempts" ON public.speaking_attempts;
CREATE POLICY "Users can update own speaking attempts"
    ON public.speaking_attempts FOR UPDATE
    USING (auth.uid() = user_id);

-- ============================================================
-- 4. Grants
-- ============================================================
GRANT ALL ON public.speaking_attempts TO authenticated;
