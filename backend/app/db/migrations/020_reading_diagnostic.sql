-- IELTS AI Coach — Reading Diagnostic Module (v20)
-- Run this in your Supabase SQL editor after 019_diagnostic_test.sql
--
-- Adds a dedicated Reading diagnostic subsystem:
--   - reading_passages          : authentic IELTS-style reading passages
--   - reading_diagnostic_results: per-attempt granular results (accuracy by
--                                 question type, time, difficulty) — the
--                                 "store results" requirement.
--
-- The module reuses the existing `diagnostic_attempts` lifecycle for resume
-- support, but stores reading-specific outcomes (per question-type accuracy,
-- weak question types, difficulty level) in `reading_diagnostic_results`.
--
-- Question types supported (IELTS Reading):
--   true_false_not_given, matching_headings, multiple_choice,
--   sentence_completion, summary_completion, short_answer

-- ============================================================
-- 1. reading_passages
-- ============================================================
CREATE TABLE IF NOT EXISTS public.reading_passages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    difficulty SMALLINT NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
    topics TEXT[] DEFAULT '{}',
    word_count INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reading_passages_active ON public.reading_passages(is_active);

-- ============================================================
-- 2. reading_diagnostic_results
-- ============================================================
CREATE TABLE IF NOT EXISTS public.reading_diagnostic_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL REFERENCES public.diagnostic_attempts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    -- overall reading metrics
    total_questions INTEGER NOT NULL DEFAULT 0,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    accuracy DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_time_seconds INTEGER NOT NULL DEFAULT 0,
    reading_band NUMERIC(3,1),
    difficulty_level TEXT NOT NULL DEFAULT 'Easy' CHECK (
        difficulty_level IN ('Easy','Moderate','Hard')
    ),
    -- per-question-type breakdown: {question_type: accuracy}
    type_accuracy JSONB NOT NULL DEFAULT '{}',
    -- per-question-type time: {question_type: avg_seconds}
    type_time JSONB NOT NULL DEFAULT '{}',
    -- weak question types (accuracy below threshold)
    weak_types JSONB NOT NULL DEFAULT '[]',
    -- strong question types
    strong_types JSONB NOT NULL DEFAULT '[]',
    -- per-question detail snapshot (for future review)
    detail JSONB NOT NULL DEFAULT '[]',
    completed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (attempt_id)
);

CREATE INDEX IF NOT EXISTS idx_reading_results_user ON public.reading_diagnostic_results(user_id);
CREATE INDEX IF NOT EXISTS idx_reading_results_attempt ON public.reading_diagnostic_results(attempt_id);

-- ============================================================
-- 3. Extend diagnostic_questions with reading passage linkage
-- ============================================================
ALTER TABLE public.diagnostic_questions
    ADD COLUMN IF NOT EXISTS passage_id UUID REFERENCES public.reading_passages(id) ON DELETE SET NULL;
ALTER TABLE public.diagnostic_questions
    ADD COLUMN IF NOT EXISTS question_type TEXT;

CREATE INDEX IF NOT EXISTS idx_diag_questions_passage ON public.diagnostic_questions(passage_id);
CREATE INDEX IF NOT EXISTS idx_diag_questions_type ON public.diagnostic_questions(question_type);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.reading_passages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reading_diagnostic_results ENABLE ROW LEVEL SECURITY;

-- Passages readable by authenticated users (shared bank).
DROP POLICY IF EXISTS "Users can view reading passages" ON public.reading_passages;
CREATE POLICY "Users can view reading passages" ON public.reading_passages FOR SELECT
    USING (auth.uid() IS NOT NULL);

-- Results owner-scoped.
DROP POLICY IF EXISTS "Users can view own reading results" ON public.reading_diagnostic_results;
CREATE POLICY "Users can view own reading results" ON public.reading_diagnostic_results FOR SELECT
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own reading results" ON public.reading_diagnostic_results;
CREATE POLICY "Users can insert own reading results" ON public.reading_diagnostic_results FOR INSERT
    WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own reading results" ON public.reading_diagnostic_results;
CREATE POLICY "Users can update own reading results" ON public.reading_diagnostic_results FOR UPDATE
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own reading results" ON public.reading_diagnostic_results;
CREATE POLICY "Users can delete own reading results" ON public.reading_diagnostic_results FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- 4. Seed passages
-- ============================================================
INSERT INTO public.reading_passages (title, content, difficulty, topics, word_count, is_active) VALUES
('The Urban Bee Revival',
 $$For decades, honeybee populations across the industrialized world have been in decline, a phenomenon attributed to habitat loss, pesticide use, and climate change. In response, a surprising movement has taken root: urban beekeeping.

City roofs, balconies, and even window boxes now host hives that produce honey and support local pollination. Researchers at several universities have found that urban bees can actually thrive, sometimes healthier than their rural counterparts, because cities offer a wider variety of flowering plants over a longer season than monoculture farmland.

However, urban beekeeping is not without controversy. Critics argue that a flood of hobbyist hives can deplete nectar resources and spread disease to wild pollinators. Some cities have therefore introduced regulations requiring registration or limiting hive numbers. Proponents counter that responsible beekeeping, combined with planting more native flowers, can create a healthier urban ecosystem for all pollinators.$$,
 2, ARRAY['urban', 'environment', 'beekeeping'], 214, true),
('The Psychology of Decision Fatigue',
 $$Every day, people make hundreds of decisions, from trivial choices about what to eat to high-stakes judgments at work. Psychologists use the term 'decision fatigue' to describe the mental exhaustion that sets in after making many choices, which can lead to poorer judgement or impulsive behaviour.

Studies show that the order of decisions matters. When judges reviewed parole cases, they granted parole significantly more often early in the day and immediately after meal breaks. The researchers interpreted this as evidence that glucose depletion and mental effort reduce the capacity to weigh complex information.

One practical countermeasure is to reduce the number of decisions by establishing routines. Executives, for instance, often wear the same clothes each day to conserve mental energy for more important tasks. The evidence suggests that designing one's environment to minimise trivial choices can protect the quality of important ones.$$,
 3, ARRAY['psychology', 'decision', 'behaviour'], 178, true),
('The Last Ice Age and Human Migration',
 $$Around twenty thousand years ago, much of northern Europe and North America lay beneath vast ice sheets up to two kilometres thick. Sea levels were dramatically lower, exposing land bridges that connected continents and enabled the earliest human migrations.

Archaeological evidence indicates that the first settlers of the Americas crossed a land bridge between Siberia and Alaska, following herds of large game. As the climate warmed and the ice retreated, these populations spread rapidly southward, adapting to forests, coasts, and grasslands.

The end of the Ice Age also coincided with the extinction of many megafauna species. While some researchers emphasise climate as the driver, others point to human hunting pressure. The debate continues, but the period illustrates how environmental change and human expansion are deeply intertwined.$$,
 4, ARRAY['history', 'climate', 'migration'], 172, true)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 5. Seed reading questions grouped by passage + type
-- ============================================================
-- True / False / Not Given
INSERT INTO public.diagnostic_questions
    (section, passage_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Urban Bee Revival'),
     'true_false_not_given',
     'Urban honeybees are always healthier than bees kept in rural areas.',
     '["True","False","Not Given"]',
     '"False"',
     'The passage says urban bees "can actually thrive, sometimes healthier than their rural counterparts" — "sometimes", not always.',
     3, 1.0, 90, 'true-false-not-given'),
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Urban Bee Revival'),
     'true_false_not_given',
     'All cities require urban beekeepers to register their hives.',
     '["True","False","Not Given"]',
     '"Not Given"',
     'The passage says "some cities have therefore introduced regulations" — some, not all.',
     3, 1.0, 90, 'true-false-not-given'),
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Psychology of Decision Fatigue'),
     'true_false_not_given',
     'Judges granted parole more often directly after a meal break.',
     '["True","False","Not Given"]',
     '"True"',
     'The passage states judges granted parole "significantly more often early in the day and immediately after meal breaks".',
     3, 1.0, 90, 'true-false-not-given');

-- Matching Headings
INSERT INTO public.diagnostic_questions
    (section, passage_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Urban Bee Revival'),
     'matching_headings',
     'Choose the best heading for the final paragraph of "The Urban Bee Revival".',
     '["The Rise of Wild Pollinators","Opposing Views on Urban Beekeeping","A History of Honey","The Decline of Rural Farms"]',
     '"Opposing Views on Urban Beekeeping"',
     'The final paragraph presents the arguments of critics and proponents — opposing views.',
     4, 1.0, 90, 'matching-headings'),
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Psychology of Decision Fatigue'),
     'matching_headings',
     'Choose the best heading for the second paragraph of "Decision Fatigue".',
     '["Evidence From the Courtroom","How to Make Better Decisions","The Cost of Breakfast","Why People Procrastinate"]',
     '"Evidence From the Courtroom"',
     'The second paragraph presents the parole study as evidence from the courtroom.',
     4, 1.0, 90, 'matching-headings');

-- Multiple Choice
INSERT INTO public.diagnostic_questions
    (section, passage_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Urban Bee Revival'),
     'multiple_choice',
     'According to the passage, why can urban bees sometimes be healthier than rural bees?',
     '["Pesticide use is banned in cities","Cities offer a wider variety of flowering plants over a longer season","Urban bees are bred to be stronger","City hives are always larger"]',
     '"Cities offer a wider variety of flowering plants over a longer season"',
     'The passage cites "a wider variety of flowering plants over a longer season than monoculture farmland".',
     3, 1.0, 90, 'reading-for-detail'),
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Last Ice Age and Human Migration'),
     'multiple_choice',
     'According to the passage, how did the first settlers of the Americas arrive?',
     '["By boat across the Atlantic","Across a land bridge between Siberia and Alaska","By following the coastline from Europe","By air across the Pacific"]',
     '"Across a land bridge between Siberia and Alaska"',
     'The passage states settlers "crossed a land bridge between Siberia and Alaska, following herds of large game".',
     3, 1.0, 90, 'reading-for-detail');

-- Sentence Completion
INSERT INTO public.diagnostic_questions
    (section, passage_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Psychology of Decision Fatigue'),
     'sentence_completion',
     'Complete the sentence: Studies indicate that mental exhaustion can lead to poorer judgement or ____.',
     NULL,
     '"impulsive behaviour"',
     'The passage: "which can lead to poorer judgement or impulsive behaviour."',
     3, 1.0, 90, 'sentence-completion'),
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Last Ice Age and Human Migration'),
     'sentence_completion',
     'Complete the sentence: Sea levels were dramatically lower, exposing ____ that connected continents.',
     NULL,
     '"land bridges"',
     'The passage: "exposing land bridges that connected continents".',
     3, 1.0, 90, 'sentence-completion');

-- Summary Completion
INSERT INTO public.diagnostic_questions
    (section, passage_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Urban Bee Revival'),
     'summary_completion',
     'Complete the summary with ONE word from the passage: Urban beekeeping has grown in cities, where bees can thrive because cities offer more ____ plants.',
     NULL,
     '"flowering"',
     'The passage uses "flowering plants" — the required word is "flowering".',
     4, 1.0, 90, 'summary-completion'),
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Last Ice Age and Human Migration'),
     'summary_completion',
     'Complete the summary with ONE word from the passage: The end of the Ice Age saw the retreat of the ice and the extinction of many ____ species.',
     NULL,
     '"megafauna"',
     'The passage: "the extinction of many megafauna species."',
     4, 1.0, 90, 'summary-completion');

-- Short Answer
INSERT INTO public.diagnostic_questions
    (section, passage_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Psychology of Decision Fatigue'),
     'short_answer',
     'What term do psychologists use for the mental exhaustion that follows making many choices?',
     NULL,
     '"decision fatigue"',
     'The passage defines "decision fatigue" as the mental exhaustion that sets in after making many choices.',
     3, 1.0, 90, 'short-answer'),
    ('reading', (SELECT id FROM public.reading_passages WHERE title='The Urban Bee Revival'),
     'short_answer',
     'What countermeasure do some executives use to conserve mental energy, according to the passage?',
     NULL,
     '"wearing the same clothes each day"',
     'The passage: "Executives, for instance, often wear the same clothes each day to conserve mental energy".',
     4, 1.0, 90, 'reading-for-detail')
ON CONFLICT (id) DO NOTHING;
