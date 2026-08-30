-- IELTS AI Coach — Speaking Audio Processing Pipeline (v041)
-- Run this in your Supabase SQL editor after 040_speaking_test_workspace.sql
--
-- When a user submits a recorded speaking response, the backend:
--   1. Stores the recording securely (Supabase Storage, user-scoped path)
--   2. Creates one row here (speaking_evaluations) — the pipeline record
--   3. Prepares the audio (fetches + validates bytes from storage)
--   4. Sends it to the configured speech-to-text provider
--   5. Stores the transcript
--   6. Preserves the original recording (audio_url is never overwritten)
--
-- The table tracks everything the pipeline needs:
--   audio_duration_seconds  — audio duration
--   file_size_bytes         — uploaded file size
--   transcript              — speech-to-text output
--   status                  — processing status (queued/preparing/transcribing/completed/failed)
--   created_at / updated_at — lifecycle timestamps
--
-- One evaluation row per submitted speaking response (idempotent re-submits
-- reuse the existing row). Failed rows are retryable without re-uploading.

-- ============================================================
-- 1. speaking_evaluations
-- ============================================================
CREATE TABLE IF NOT EXISTS public.speaking_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    response_id UUID NOT NULL REFERENCES public.speaking_test_responses(id)
        ON DELETE CASCADE,
    session_id UUID REFERENCES public.speaking_test_sessions(id)
        ON DELETE SET NULL,
    part TEXT NOT NULL DEFAULT 'part_1'
        CHECK (part IN ('part_1','part_2','part_3')),

    -- Original recording — preserved unchanged for the whole lifecycle.
    audio_url TEXT NOT NULL DEFAULT '',
    audio_duration_seconds INTEGER NOT NULL DEFAULT 0
        CHECK (audio_duration_seconds >= 0),
    file_size_bytes BIGINT NOT NULL DEFAULT 0
        CHECK (file_size_bytes >= 0),

    -- Speech-to-text output.
    transcript TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT 'openai_whisper',
    model TEXT NOT NULL DEFAULT 'whisper-1',

    -- Processing lifecycle.
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','preparing','transcribing','completed','failed')),
    error_message TEXT NOT NULL DEFAULT '',
    retry_count INTEGER NOT NULL DEFAULT 0
        CHECK (retry_count >= 0),
    last_processed_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_speaking_evaluations_user
    ON public.speaking_evaluations(user_id);
CREATE INDEX IF NOT EXISTS idx_speaking_evaluations_response
    ON public.speaking_evaluations(response_id);
CREATE INDEX IF NOT EXISTS idx_speaking_evaluations_user_created
    ON public.speaking_evaluations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_speaking_evaluations_status
    ON public.speaking_evaluations(status);

-- ============================================================
-- 2. updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_speaking_evaluations_updated_at
    ON public.speaking_evaluations;
CREATE TRIGGER update_speaking_evaluations_updated_at
    BEFORE UPDATE ON public.speaking_evaluations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 3. Row Level Security
-- ============================================================
ALTER TABLE public.speaking_evaluations ENABLE ROW LEVEL SECURITY;

-- Owner-scoped read / insert / update. No delete policy — the pipeline
-- preserves the original recording and its processing history.
DROP POLICY IF EXISTS "Users can view own speaking evaluations"
    ON public.speaking_evaluations;
CREATE POLICY "Users can view own speaking evaluations"
    ON public.speaking_evaluations FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own speaking evaluations"
    ON public.speaking_evaluations;
CREATE POLICY "Users can insert own speaking evaluations"
    ON public.speaking_evaluations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own speaking evaluations"
    ON public.speaking_evaluations;
CREATE POLICY "Users can update own speaking evaluations"
    ON public.speaking_evaluations FOR UPDATE
    USING (auth.uid() = user_id);

-- ============================================================
-- 4. Grants
-- ============================================================
GRANT ALL ON public.speaking_evaluations TO authenticated;
