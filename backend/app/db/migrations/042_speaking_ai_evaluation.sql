-- IELTS AI Coach — Speaking AI Evaluation (v042)
-- Run this in your Supabase SQL editor after 041_speaking_audio_pipeline.sql
--
-- When the audio processing pipeline completes (transcript stored), the backend
-- runs the AI Speaking evaluation (Phase 10):
--   1. Sends the transcript to the speech-aware AI assessment (OpenAI, or a
--      deterministic fallback when no key is configured)
--   2. Scores the 4 official IELTS Speaking criteria:
--        Fluency & Coherence, Lexical Resource, Grammatical Range, Pronunciation
--   3. Computes the overall band (0-9, 0.5 steps) + a confidence score
--   4. Stores strengths / weaknesses / corrections / suggestions + the AI
--      feedback as structured JSONB
--
-- The original recording and transcript are never modified — the AI evaluation
-- is additive. ``is_estimate`` is always TRUE (AI estimate, not an official
-- IELTS Speaking band).
-- ============================================================
-- 1. AI evaluation columns on speaking_evaluations
-- ============================================================
ALTER TABLE public.speaking_evaluations
    ADD COLUMN IF NOT EXISTS overall_band NUMERIC(3, 1)
        CHECK (overall_band >= 0 AND overall_band <= 9),
    ADD COLUMN IF NOT EXISTS confidence NUMERIC(3, 2)
        CHECK (confidence >= 0 AND confidence <= 1),
    ADD COLUMN IF NOT EXISTS criteria JSONB
        NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS strengths JSONB
        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS weaknesses JSONB
        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS corrections JSONB
        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS suggestions JSONB
        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS is_estimate BOOLEAN
        NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS source TEXT
        NOT NULL DEFAULT 'pending'
        CHECK (source IN ('ai', 'deterministic_fallback', 'pending')),
    ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS evaluation_version INTEGER
        NOT NULL DEFAULT 0
        CHECK (evaluation_version >= 0);

-- ============================================================
-- 2. Index: quickly find completed-but-unevaluated transcriptions
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_speaking_evaluations_ai_pending
    ON public.speaking_evaluations (status, overall_band)
    WHERE status = 'completed' AND overall_band IS NULL;

-- ============================================================
-- 3. Updated updated_at trigger already covers these columns.
-- ============================================================
