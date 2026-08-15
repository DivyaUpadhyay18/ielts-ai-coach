-- IELTS AI Coach — Writing Evaluations: Attempt tracking column (v38)
-- Run this in your Supabase SQL editor after 037_writing_reattempt_mode.sql
--
-- Adds attempt_number to writing_evaluations so each evaluation knows which
-- attempt number it belongs to (for reattempt mode).

ALTER TABLE public.writing_evaluations
    ADD COLUMN IF NOT EXISTS attempt_number INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_writing_evaluations_attempt
    ON public.writing_evaluations(user_id, attempt_number);
