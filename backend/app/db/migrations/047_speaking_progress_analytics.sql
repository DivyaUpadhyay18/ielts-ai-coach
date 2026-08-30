-- IELTS AI Coach — Speaking Progress Analytics (v047)
--
-- Speaking Progress Analytics computes metrics from:
--   - speaking_evaluations        (AI evaluation results with criteria JSONB)
--   - speaking_practice_sessions  (practice mode sessions with bands + errors)
--   - speaking_test_responses     (test responses with audio duration + transcript)
--   - speaking_error_analysis     (per-response error issues)
--
-- Metrics:
--   - Speaking Band History
--   - Fluency History (per criterion over time)
--   - Lexical Resource History
--   - Grammar History
--   - Pronunciation History
--   - Average Speaking Duration
--   - Average Filler Words
--   - Common Grammar Errors
--   - Common Vocabulary Errors
--   - Strongest Criterion
--   - Weakest Criterion
--   - Improvement Rate
--   - Attempt History
--
-- This migration doesn't create new tables — it relies on the existing
-- speaking_evaluations, speaking_practice_sessions, speaking_test_responses,
-- and speaking_error_analysis tables.  Analytics are computed in the service layer.
--
-- The only addition is an index to speed up analytics queries:
CREATE INDEX IF NOT EXISTS idx_speaking_evaluations_completed_bands
    ON public.speaking_evaluations(user_id, created_at DESC)
    WHERE status = 'completed' AND overall_band IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_speaking_practice_evaluated
    ON public.speaking_practice_sessions(user_id, created_at DESC)
    WHERE status = 'evaluated';
