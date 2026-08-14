-- IELTS AI Coach — Writing Error Analysis (v35)
-- Run this in your Supabase SQL editor after 034_writing_evaluations.sql
--
-- Adds a dedicated, structured error-analysis payload to each writing evaluation.
--
-- Every detected issue is stored as an object with:
--   original      – the exact problematic text
--   error_type    – one of: Grammar, Vocabulary, Spelling, Punctuation,
--                   Sentence Structure, Cohesion, Repetition, Word Choice,
--                   Task Response
--   explanation   – why it is wrong
--   correction    – suggested correction (per issue; the essay is never
--                   auto-rewritten as a whole)
--   severity      – critical | major | minor
--   criterion     – affected IELTS Writing criterion key
--   start / end   – character offsets into the essay (for UI highlighting)
--   sentence      – surrounding sentence for context (optional)
--
-- The column lives on writing_evaluations so the full analysis is stored
-- with the immutable evaluation record and covered by the existing RLS.

ALTER TABLE public.writing_evaluations
    ADD COLUMN IF NOT EXISTS error_analysis JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Helpful for analytics on error-type distribution (optional).
CREATE INDEX IF NOT EXISTS idx_writing_evaluations_error_type
    ON public.writing_evaluations USING GIN (error_analysis);