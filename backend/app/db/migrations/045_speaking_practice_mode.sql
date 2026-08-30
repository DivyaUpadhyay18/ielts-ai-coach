-- IELTS AI Coach — Speaking Practice Mode (v045)
--
-- Speaking Practice Mode lets users practice individual Speaking skills
-- with focused, targeted exercises rather than a full 3-part test.
--
-- Practice modes:
--   - quick_practice      → random question, any part
--   - part_1_practice     → Part 1 questions (Introduction & Interview)
--   - part_2_practice     → Part 2 cue cards (Individual Long Turn)
--   - part_3_practice     → Part 3 discussion questions
--   - vocabulary_practice → vocabulary-focused prompts
--   - fluency_practice    → fluency-focused prompts
--   - random_question     → random across all modes
--   - weak_area_practice  → targets the user's weakest criterion
--
-- Two tables:
--   speaking_practice_sessions  — one row per practice session
--   speaking_practice_results   — one row per response evaluated in a session

CREATE TABLE IF NOT EXISTS public.speaking_practice_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- The practice mode used for this session.
    practice_mode TEXT NOT NULL CHECK (
        practice_mode IN (
            'quick_practice', 'part_1_practice', 'part_2_practice',
            'part_3_practice', 'vocabulary_practice', 'fluency_practice',
            'random_question', 'weak_area_practice'
        )
    ),

    -- The prompt selected for this session (from speaking_prompts).
    prompt_id UUID REFERENCES public.speaking_prompts(id) ON DELETE SET NULL,
    part TEXT NOT NULL DEFAULT 'part_1'
        CHECK (part IN ('part_1', 'part_2', 'part_3')),
    title TEXT NOT NULL DEFAULT '',
    prompt_text TEXT NOT NULL DEFAULT '',
    prep_time_seconds INTEGER NOT NULL DEFAULT 0,
    speak_time_seconds INTEGER NOT NULL DEFAULT 60,

    -- The user's recorded response.
    audio_url TEXT NOT NULL DEFAULT '',
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    transcript TEXT NOT NULL DEFAULT '',

    -- Evaluation results (populated after evaluation).
    overall_band NUMERIC(3,1),
    fluency_coherence_band NUMERIC(3,1),
    lexical_resource_band NUMERIC(3,1),
    grammatical_range_band NUMERIC(3,1),
    pronunciation_band NUMERIC(3,1),
    error_count INTEGER NOT NULL DEFAULT 0,
    filler_words_count INTEGER NOT NULL DEFAULT 0,

    -- AI feedback.
    feedback TEXT,

    -- Next recommended exercise.
    next_recommendation TEXT,

    -- Session status.
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'evaluated', 'abandoned')),

    -- Mission integration: optionally link to a mission that generated/scheduled this session.
    mission_id UUID,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_spp_sessions_user
    ON public.speaking_practice_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_spp_sessions_mode
    ON public.speaking_practice_sessions(practice_mode, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_spp_sessions_status
    ON public.speaking_practice_sessions(status, created_at DESC);

-- updated_at trigger
DROP TRIGGER IF EXISTS update_speaking_practice_sessions_updated_at
    ON public.speaking_practice_sessions;
CREATE TRIGGER update_speaking_practice_sessions_updated_at
    BEFORE UPDATE ON public.speaking_practice_sessions
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Row Level Security
ALTER TABLE public.speaking_practice_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own speaking practice sessions"
    ON public.speaking_practice_sessions;
CREATE POLICY "Users can view own speaking practice sessions"
    ON public.speaking_practice_sessions FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own speaking practice sessions"
    ON public.speaking_practice_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own speaking practice sessions"
    ON public.speaking_practice_sessions FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own speaking practice sessions"
    ON public.speaking_practice_sessions FOR DELETE
    USING (auth.uid() = user_id);

GRANT ALL ON public.speaking_practice_sessions TO authenticated;

-- ============================================================
-- 2. speaking_practice_history — immutable log of all sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.speaking_practice_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES public.speaking_practice_sessions(id)
        ON DELETE CASCADE,
    practice_mode TEXT NOT NULL,
    part TEXT NOT NULL,
    overall_band NUMERIC(3,1),
    total_errors INTEGER NOT NULL DEFAULT 0,
    total_fillers INTEGER NOT NULL DEFAULT 0,
    xp_earned INTEGER NOT NULL DEFAULT 0,
    xp_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spp_history_user
    ON public.speaking_practice_history(user_id, created_at DESC);

ALTER TABLE public.speaking_practice_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own speaking practice history"
    ON public.speaking_practice_history;
CREATE POLICY "Users can view own speaking practice history"
    ON public.speaking_practice_history FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own speaking practice history"
    ON public.speaking_practice_history FOR INSERT
    WITH CHECK (auth.uid() = user_id);

GRANT ALL ON public.speaking_practice_history TO authenticated;
