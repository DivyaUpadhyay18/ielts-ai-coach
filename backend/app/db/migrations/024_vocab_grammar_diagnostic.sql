-- IELTS AI Coach — Vocabulary & Grammar Diagnostic Module (v24)
-- Run this in your Supabase SQL editor after 023_speaking_diagnostic.sql
--
-- Adds a dedicated Vocabulary & Grammar diagnostic subsystem:
--   - vocab_grammar_diagnostic_results: per-attempt granular results (accuracy,
--     grammar vs vocabulary breakdown, weak grammar topics, weak vocabulary
--     categories, time, difficulty, estimated band) — the "store results"
--     requirement.
--
-- The module reuses the existing `diagnostic_attempts` lifecycle (resume
-- support) and stores its questions in `diagnostic_questions` filtered by
-- section = 'vocabulary' or 'grammar' and a `question_type` column (already
-- added by the reading migration).
--
-- Question types supported:
--   Vocabulary: fill_in_the_blanks, synonyms, antonyms
--   Grammar:    sentence_correction, grammar_correction, tenses, articles,
--               prepositions

-- ============================================================
-- 1. vocab_grammar_diagnostic_results
-- ============================================================
CREATE TABLE IF NOT EXISTS public.vocab_grammar_diagnostic_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL REFERENCES public.diagnostic_attempts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    -- overall metrics
    total_questions INTEGER NOT NULL DEFAULT 0,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    accuracy DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_time_seconds INTEGER NOT NULL DEFAULT 0,
    band NUMERIC(3,1),
    difficulty_level TEXT NOT NULL DEFAULT 'Easy' CHECK (
        difficulty_level IN ('Easy','Moderate','Hard')
    ),
    -- grammar vs vocabulary accuracy
    grammar_accuracy DOUBLE PRECISION NOT NULL DEFAULT 0,
    vocabulary_accuracy DOUBLE PRECISION NOT NULL DEFAULT 0,
    -- per-question-type breakdown: {question_type: accuracy}
    type_accuracy JSONB NOT NULL DEFAULT '{}',
    -- per-question-type time: {question_type: avg_seconds}
    type_time JSONB NOT NULL DEFAULT '{}',
    -- weak grammar topics (grammar question types below threshold)
    weak_grammar_topics JSONB NOT NULL DEFAULT '[]',
    -- weak vocabulary categories (vocabulary question types below threshold)
    weak_vocab_categories JSONB NOT NULL DEFAULT '[]',
    -- strong question types
    strong_types JSONB NOT NULL DEFAULT '[]',
    -- per-question detail snapshot (for future review)
    detail JSONB NOT NULL DEFAULT '[]',
    completed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (attempt_id)
);

CREATE INDEX IF NOT EXISTS idx_vg_results_user ON public.vocab_grammar_diagnostic_results(user_id);
CREATE INDEX IF NOT EXISTS idx_vg_results_attempt ON public.vocab_grammar_diagnostic_results(attempt_id);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.vocab_grammar_diagnostic_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own vg results" ON public.vocab_grammar_diagnostic_results;
CREATE POLICY "Users can view own vg results" ON public.vocab_grammar_diagnostic_results FOR SELECT
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own vg results" ON public.vocab_grammar_diagnostic_results;
CREATE POLICY "Users can insert own vg results" ON public.vocab_grammar_diagnostic_results FOR INSERT
    WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own vg results" ON public.vocab_grammar_diagnostic_results;
CREATE POLICY "Users can update own vg results" ON public.vocab_grammar_diagnostic_results FOR UPDATE
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own vg results" ON public.vocab_grammar_diagnostic_results;
CREATE POLICY "Users can delete own vg results" ON public.vocab_grammar_diagnostic_results FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- Seed question bank
-- Mock type: any question_type is stored in `question_type` column.
-- section is 'vocabulary' or 'grammar'.
-- ============================================================
-- ------------------------------------------------ VOCABULARY
-- Fill in the blanks
INSERT INTO public.diagnostic_questions
    (section, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('vocabulary', 'fill_in_the_blanks',
     'The discovery was a major ____ in the field of medicine.',
     '["breakthrough", "breakdown", "setback", "outbreak"]',
     '"breakthrough"',
     '"Breakthrough" means a sudden, important discovery or development, fitting the positive context.',
     3, 1.0, 45, 'collocation-context'),
    ('vocabulary', 'fill_in_the_blanks',
     'Her argument was so ____ that no one could easily refute it.',
     '["compelling", "ambiguous", "fragile", "trivial"]',
     '"compelling"',
     '"Compelling" means convincing and persuasive, which matches the idea that it was hard to refute.',
     4, 1.0, 45, 'word-meaning'),
    ('vocabulary', 'fill_in_the_blanks',
     'The report was criticised for being overly ____ and hard to follow.',
     '["convoluted", "straightforward", "concise", "lucid"]',
     '"convoluted"',
     '"Convoluted" means extremely complex and difficult to follow.',
     4, 1.0, 45, 'collocation-context');

-- Synonyms
INSERT INTO public.diagnostic_questions
    (section, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('vocabulary', 'synonyms',
     'Choose the closest synonym for "meticulous".',
     '["careless", "thorough", "hasty", "sloppy"]',
     '"thorough"',
     '"Meticulous" means showing great attention to detail; very careful and precise — a synonym of "thorough".',
     4, 1.0, 45, 'synonyms'),
    ('vocabulary', 'synonyms',
     'Choose the closest synonym for "deteriorate".',
     '["improve", "worsen", "stabilise", "accelerate"]',
     '"worsen"',
     '"Deteriorate" means to become progressively worse — a synonym of "worsen".',
     3, 1.0, 45, 'synonyms'),
    ('vocabulary', 'synonyms',
     'Choose the closest synonym for "ambiguous".',
     '["clear", "unclear", "rigid", "obvious"]',
     '"unclear"',
     '"Ambiguous" means open to more than one interpretation; not clear — a synonym of "unclear".',
     3, 1.0, 45, 'synonyms');

-- Antonyms
INSERT INTO public.diagnostic_questions
    (section, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('vocabulary', 'antonyms',
     'Choose the opposite (antonym) of "transparent".',
     '["clear", "opaque", "obvious", "visible"]',
     '"opaque"',
     '"Opaque" is the antonym of "transparent"; it means not able to be seen through.',
     3, 1.0, 45, 'antonyms'),
    ('vocabulary', 'antonyms',
     'Choose the opposite (antonym) of "scarce".',
     '["rare", "plentiful", "limited", "sparse"]',
     '"plentiful"',
     '"Scarce" means insufficient in supply; "plentiful" is its antonym.',
     3, 1.0, 45, 'antonyms'),
    ('vocabulary', 'antonyms',
     'Choose the opposite (antonym) of "fragile".',
     '["delicate", "robust", "frail", "breakable"]',
     '"robust"',
     '"Fragile" means easily broken; "robust" meaning strong and sturdy is its antonym.',
     3, 1.0, 45, 'antonyms');

-- ------------------------------------------------ GRAMMAR
-- Sentence correction
INSERT INTO public.diagnostic_questions
    (section, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('grammar', 'sentence_correction',
     'Choose the grammatically correct sentence.',
     '["The team are divided on the issue.", "The team is divided on the issue.", "The team are being divided on the issue.", "The team were divided on the issue."]',
     '"The team is divided on the issue."',
     'A collective noun (team) treated as a single unit takes a singular verb "is".',
     3, 1.0, 45, 'subject-verb-agreement'),
    ('grammar', 'sentence_correction',
     'Choose the grammatically correct sentence.',
     '["Neither of the answers were correct.", "Neither of the answers was correct.", "Neither of the answers are correct.", "Neither of the answers be correct."]',
     '"Neither of the answers was correct."',
     '"Neither" is singular, so it takes a singular verb "was".',
     4, 1.0, 45, 'subject-verb-agreement'),
    ('grammar', 'sentence_correction',
     'Choose the grammatically correct sentence.',
     '["She don''t like coffee.", "She doesn''t likes coffee.", "She doesn''t like coffee.", "She not like coffee."]',
     '"She doesn''t like coffee."',
     'Third-person singular negative in present simple uses "doesn''t + base verb".',
     2, 1.0, 45, 'verb-tenses');

-- Grammar correction
INSERT INTO public.diagnostic_questions
    (section, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('grammar', 'grammar_correction',
     'Which option correctly fixes the error in: "He is looking forward to meet you."?',
     '["He is looking forward to meeting you.", "He is looking forward to met you.", "He is looking forward to meets you.", "He is looked forward to meet you."]',
     '"He is looking forward to meeting you."',
     '"Looking forward to" is followed by a gerund (-ing form), not the base verb.',
     3, 1.0, 45, 'gerund-infinitive'),
    ('grammar', 'grammar_correction',
     'Which option correctly fixes the error in: "I am used to work late."?',
     '["I am used to working late.", "I am used to works late.", "I used to working late.", "I am use to work late."]',
     '"I am used to working late."',
     '"Be used to" is followed by a gerund (-ing form).',
     3, 1.0, 45, 'gerund-infinitive'),
    ('grammar', 'grammar_correction',
     'Which option correctly fixes the error in: "She has went to the market."?',
     '["She has gone to the market.", "She has went to the market.", "She have gone to the market.", "She goes gone to the market."]',
     '"She has gone to the market."',
     'Present perfect uses the past participle "gone", not "went".',
     3, 1.0, 45, 'verb-tenses');

-- Tenses
INSERT INTO public.diagnostic_questions
    (section, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('grammar', 'tenses',
     'Choose the correct tense: "By this time next week, I ____ my project."',
     '["will be finishing", "will have finished", "finish", "have finished"]',
     '"will have finished"',
     'Future perfect ("will have + past participle") describes an action completed before a future time.',
     4, 1.0, 45, 'future-perfect'),
    ('grammar', 'tenses',
     'Choose the correct tense: "She ____ in London for five years before she moved to Paris."',
     '["has lived", "had lived", "lives", "is living"]',
     '"had lived"',
     'Past perfect describes an action completed before another past action.',
     4, 1.0, 45, 'past-perfect'),
    ('grammar', 'tenses',
     'Choose the correct tense: "Look! The children ____ in the garden."',
     '["play", "are playing", "played", "have played"]',
     '"are playing"',
     'Present continuous is used for actions happening at the moment of speaking.',
     2, 1.0, 45, 'present-continuous');

-- Articles
INSERT INTO public.diagnostic_questions
    (section, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('grammar', 'articles',
     'Choose the correct article: "She is ____ honest person."',
     '["a", "an", "the", "no article"]',
     '"an"',
     '"Honest" begins with a vowel sound (/ɒ/), so the indefinite article "an" is used.',
     2, 1.0, 45, 'articles'),
    ('grammar', 'articles',
     'Choose the correct article: "____ Amazon is the largest river by volume."',
     '["A", "An", "The", "No article"]',
     '"The"',
     'Unique or well-known geographical names (rivers) take the definite article "the".',
     3, 1.0, 45, 'articles'),
    ('grammar', 'articles',
     'Choose the correct article: "He plays ____ piano every evening."',
     '["a", "an", "the", "no article"]',
     '"the"',
     'Musical instruments generally take the definite article "the".',
     2, 1.0, 45, 'articles');

-- Prepositions
INSERT INTO public.diagnostic_questions
    (section, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('grammar', 'prepositions',
     'Choose the correct preposition: "She is good ____ solving problems."',
     '["in", "at", "on", "for"]',
     '"at"',
     'The adjective "good at" is the correct collocation for a skill.',
     2, 1.0, 45, 'prepositions'),
    ('grammar', 'prepositions',
     'Choose the correct preposition: "We arrived ____ the station on time."',
     '["to", "at", "in", "on"]',
     '"at"',
     '"Arrive at" is used for a specific point or small place like a station.',
     3, 1.0, 45, 'prepositions'),
    ('grammar', 'prepositions',
     'Choose the correct preposition: "The report depends ____ the data collected."',
     '["from", "on", "of", "with"]',
     '"on"',
     'The verb "depend on" is the correct collocation.',
     3, 1.0, 45, 'prepositions')
ON CONFLICT (id) DO NOTHING;
