-- IELTS AI Coach — Diagnostic Test Framework (v19)
-- Run this in your Supabase SQL editor after 018_community_resources.sql
--
-- Creates the tables that back the Diagnostic Test Framework:
--   - diagnostic_attempts  : one row per assessment taken by a user (resumable)
--   - diagnostic_responses : one row per answered question (resume + scoring
--                            source of truth)
--   - diagnostic_questions : static, seeded question bank covering the six
--                            IELTS skill domains.
--
-- The framework is fully deterministic (NO AI):
--   - Current IELTS level is estimated from per-section accuracy.
--   - Questions are randomized per attempt (handled by the service layer).
--   - Progress is saved per-answer so the user can resume at any time.
--   - Per-section and overall time is tracked.

-- ============================================================
-- 1. diagnostic_questions (question bank)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.diagnostic_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section TEXT NOT NULL CHECK (
        section IN ('reading','listening','writing','speaking','vocabulary','grammar')
    ),
    prompt TEXT NOT NULL,
    options JSONB,               -- array of choices for MCQ sections
    answer JSONB,                -- correct answer (string for MCQ, rubric for writing/speaking)
    explanation TEXT,
    difficulty SMALLINT NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
    weight NUMERIC(4,2) NOT NULL DEFAULT 1.00 CHECK (weight > 0),
    time_limit_seconds INTEGER NOT NULL DEFAULT 60 CHECK (time_limit_seconds > 0),
    skill_tag TEXT,              -- sub-skill (e.g. 'skimming', 'transitions')
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diag_questions_section ON public.diagnostic_questions(section, is_active);
CREATE INDEX IF NOT EXISTS idx_diag_questions_skill ON public.diagnostic_questions(skill_tag);

-- ============================================================
-- 2. diagnostic_attempts (resumable assessment sessions)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.diagnostic_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (
        status IN ('in_progress','completed','abandoned')
    ),
    current_section TEXT NOT NULL DEFAULT 'reading' CHECK (
        current_section IN ('reading','listening','writing','speaking','vocabulary','grammar')
    ),
    -- per-section state
    sections_completed JSONB NOT NULL DEFAULT '[]',
    -- time tracking (seconds)
    total_seconds_spent INTEGER NOT NULL DEFAULT 0 CHECK (total_seconds_spent >= 0),
    section_seconds JSONB NOT NULL DEFAULT '{}',
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    -- results (filled on completion)
    overall_band NUMERIC(3,1),
    skill_scores JSONB,          -- {reading: 6.5, listening: 7.0, ...}
    strengths JSONB,             -- array of strings
    weaknesses JSONB,            -- array of strings
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diag_attempts_user ON public.diagnostic_attempts(user_id, status);
CREATE INDEX IF NOT EXISTS idx_diag_attempts_user_created ON public.diagnostic_attempts(user_id, created_at DESC);

-- ============================================================
-- 3. diagnostic_responses (per-question answers + timing)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.diagnostic_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL REFERENCES public.diagnostic_attempts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    section TEXT NOT NULL CHECK (
        section IN ('reading','listening','writing','speaking','vocabulary','grammar')
    ),
    question_id UUID,
    answer_json JSONB NOT NULL DEFAULT '{}',
    is_correct BOOLEAN,
    score NUMERIC(4,2),
    time_taken_seconds INTEGER NOT NULL DEFAULT 0 CHECK (time_taken_seconds >= 0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (attempt_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_diag_responses_attempt ON public.diagnostic_responses(attempt_id);
CREATE INDEX IF NOT EXISTS idx_diag_responses_user ON public.diagnostic_responses(user_id);

-- ============================================================
-- updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_diagnostic_attempts_updated_at ON public.diagnostic_attempts;
CREATE TRIGGER update_diagnostic_attempts_updated_at BEFORE UPDATE ON public.diagnostic_attempts
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.diagnostic_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.diagnostic_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.diagnostic_responses ENABLE ROW LEVEL SECURITY;

-- Questions are readable by any authenticated user (it's a shared bank).
DROP POLICY IF EXISTS "Users can view questions" ON public.diagnostic_questions;
CREATE POLICY "Users can view questions" ON public.diagnostic_questions FOR SELECT
    USING (auth.uid() IS NOT NULL);

-- attempts
DROP POLICY IF EXISTS "Users can view own attempts" ON public.diagnostic_attempts;
CREATE POLICY "Users can view own attempts" ON public.diagnostic_attempts FOR SELECT
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own attempts" ON public.diagnostic_attempts;
CREATE POLICY "Users can insert own attempts" ON public.diagnostic_attempts FOR INSERT
    WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own attempts" ON public.diagnostic_attempts;
CREATE POLICY "Users can update own attempts" ON public.diagnostic_attempts FOR UPDATE
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own attempts" ON public.diagnostic_attempts;
CREATE POLICY "Users can delete own attempts" ON public.diagnostic_attempts FOR DELETE
    USING (auth.uid() = user_id);

-- responses
DROP POLICY IF EXISTS "Users can view own responses" ON public.diagnostic_responses;
CREATE POLICY "Users can view own responses" ON public.diagnostic_responses FOR SELECT
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own responses" ON public.diagnostic_responses;
CREATE POLICY "Users can insert own responses" ON public.diagnostic_responses FOR INSERT
    WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own responses" ON public.diagnostic_responses;
CREATE POLICY "Users can update own responses" ON public.diagnostic_responses FOR UPDATE
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own responses" ON public.diagnostic_responses;
CREATE POLICY "Users can delete own responses" ON public.diagnostic_responses FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- Seed question bank (deterministic, no AI)
-- ============================================================
INSERT INTO public.diagnostic_questions
    (section, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    -- ------------------------------------------------ READING
    ('reading',
     'The main purpose of skimming a passage is to ____.',
     '["read every word carefully", "get the general idea quickly", "memorise the text", "translate unknown words"]',
     '"get the general idea quickly"',
     'Skimming is a fast-reading technique used to grasp the overall meaning (gist) without reading every word.',
     2, 1.0, 90, 'skimming'),
    ('reading',
     'In "The findings suggest that climate change accelerates coastal erosion", the word "accelerates" most likely means ____.',
     '["slows down", "speeds up", "reverses", "measures"]',
     '"speeds up"',
     '"Accelerates" means to increase the speed or rate of something.',
     3, 1.0, 60, 'vocabulary-in-context'),
    ('reading',
     'A question that asks you to decide whether a statement is True, False, or Not Given tests your ability to ____.',
     '["predict the author opinion", "locate and compare explicit and implicit information", "paraphrase the whole passage", "memorise statistics"]',
     '"locate and compare explicit and implicit information"',
     'True/False/Not Given requires locating the relevant part and deciding if the information matches, contradicts, or is absent.',
     4, 1.0, 90, 'true-false-not-given'),
    ('reading',
     'Which of the following is the best heading for a paragraph that introduces a problem and then outlines two rival solutions?',
     '["Background and Methods", "A Tale of Two Solutions", "Conclusion and Recommendations", "Literature Review"]',
     '"A Tale of Two Solutions"',
     'A heading should capture the core content: two competing solutions to one problem.',
     4, 1.0, 90, 'matching-headings'),
    ('reading',
     'The word "nevertheless" in a text most strongly signals ____.',
     '["a restatement", "a cause and effect", "a contrast", "a list of examples"]',
     '"a contrast"',
     '"Nevertheless" is a concession/contrast marker that introduces information opposing the previous idea.',
     3, 1.0, 60, 'cohesive-devices'),

    -- ------------------------------------------------ LISTENING
    ('listening',
     'In IELTS Listening, you hear each recording ____.',
     '["only once", "twice", "three times", "as many times as you need"]',
     '"only once"',
     'IELTS Listening audio is played ONCE. Note-taking and prediction are essential.',
     1, 1.0, 45, 'test-format'),
    ('listening',
     'When you hear "The seminar begins at a quarter past nine", the time is ____.',
     '["9:15", "9:45", "9:05", "8:45"]',
     '"9:15"',
     '"A quarter past nine" = 9:15.',
     2, 1.0, 45, 'numbers-time'),
    ('listening',
     'A speaker says: "I would have attended the workshop, but I was abroad." This expresses ____.',
     '["a definite plan", "a hypothetical past situation", "a future arrangement", "a repeated habit"]',
     '"a hypothetical past situation"',
     '"Would have + past participle" describes an unreal/imagined past scenario.',
     4, 1.0, 60, 'inference'),
    ('listening',
     'The main purpose of a map-labelling question is to test your ability to ____.',
     '["follow spatial descriptions", "recall exact quotations", "count words", "spell technical terms"]',
     '"follow spatial descriptions"',
     'Map-labelling tests whether you can match spoken directions/locations to a visual.',
     3, 1.0, 60, 'map-labelling'),
    ('listening',
     'If you miss an answer in Listening, the best strategy is to ____.',
     '["panic and stop listening", "keep listening and move on", "guess randomly and dwell on it", "rewind the audio"]',
     '"keep listening and move on"',
     'The audio plays once, so the best strategy is to stay focused and not lose subsequent answers.',
     2, 1.0, 45, 'test-strategy'),

    -- ------------------------------------------------ VOCABULARY
    ('vocabulary',
     'Choose the closest synonym for "ubiquitous".',
     '["rare", "everywhere present", "outdated", "harmful"]',
     '"everywhere present"',
     '"Ubiquitous" means present, appearing, or found everywhere.',
     4, 1.0, 45, 'synonyms'),
    ('vocabulary',
     'The word "mitigate" means to ____.',
     '["intensify", "make less severe", "ignore", "celebrate"]',
     '"make less severe"',
     '"Mitigate" means to make something less harmful, serious, or painful.',
     4, 1.0, 45, 'word-meaning'),
    ('vocabulary',
     'Which word best completes: "The new policy had a ____ effect on the company, causing widespread job losses."',
     '["benign", "detrimental", "negligible", "redundant"]',
     '"detrimental"',
     '"Detrimental" means causing harm or damage, matching the negative outcome described.',
     4, 1.0, 60, 'collocation-context'),
    ('vocabulary',
     'The opposite of "transparent" in the context of a process is ____.',
     '["clear", "opaque", "efficient", "spontaneous"]',
     '"opaque"',
     '"Opaque" is the antonym of "transparent"; it means not able to be seen through or understood.',
     3, 1.0, 45, 'antonyms'),
    ('vocabulary',
     'A formal academic word meaning "to examine in detail" is ____.',
     '["scrutinise", "glance", "skim", "glimpse"]',
     '"scrutinise"',
     '"Scrutinise" means to examine or inspect closely and thoroughly.',
     3, 1.0, 45, 'academic-register'),

    -- ------------------------------------------------ GRAMMAR
    ('grammar',
     'Choose the correct sentence.',
     '["She have finished her report.", "She has finished her report.", "She is finished her report.", "She finishing her report."]',
     '"She has finished her report."',
     'Present perfect for a recently completed action uses "has/have + past participle"; third-person singular uses "has".',
     2, 1.0, 45, 'verb-tenses'),
    ('grammar',
     'Which sentence uses the conditional correctly?',
     '["If I was you, I would apologise.", "If I were you, I would apologise.", "If I am you, I would apologise.", "If I will be you, I would apologise."]',
     '"If I were you, I would apologise."',
     'Second conditional / subjunctive uses "If I were you" for hypothetical advice.',
     3, 1.0, 45, 'conditionals'),
    ('grammar',
     'Choose the sentence with correct parallel structure.',
     '["She enjoys reading, to swim, and cooking.", "She enjoys reading, swimming, and cooking.", "She enjoys to read, swimming, and to cook.", "She enjoys reading, swim, and cooked."]',
     '"She enjoys reading, swimming, and cooking."',
     'Items in a list should be in the same grammatical form (all gerunds here).',
     4, 1.0, 60, 'parallelism'),
    ('grammar',
     'The passive voice of "The committee approved the plan" is ____.',
     '["The plan was approved by the committee.", "The committee was approved by the plan.", "The plan approved the committee.", "Approved the committee the plan."]',
     '"The plan was approved by the committee."',
     'Passive voice: object becomes subject, "was + past participle", original subject becomes the agent.',
     3, 1.0, 60, 'passive-voice'),
    ('grammar',
     'Which sentence correctly uses a relative clause?',
     '["The report which it was late caused delays.", "The report, that was late, caused delays.", "The report that was submitted late caused delays.", "The report who was late caused delays."]',
     '"The report that was submitted late caused delays."',
     '"That/who/which" introduce relative clauses; "that" is appropriate for a thing (the report).',
     3, 1.0, 60, 'relative-clauses'),

    -- ------------------------------------------------ WRITING
    ('writing',
     'In IELTS Academic Writing Task 1, you should ____.',
     '["give your opinion on the topic", "summarise and compare the main features of the data/chart", "write a story", "copy the data exactly"]',
     '"summarise and compare the main features of the data/chart"',
     'Task 1 requires an objective summary and comparison of key features, not opinion or storytelling.',
     2, 1.0, 90, 'task-achievement'),
    ('writing',
     'A strong thesis statement in an IELTS essay should ____.',
     '["be vague and general", "clearly state your position on the question", "list every example", "be a question"]',
     '"clearly state your position on the question"',
     'A thesis directly answers the question and states the writer''s position.',
     3, 1.0, 60, 'task-response'),
    ('writing',
     'Which linking phrase best introduces an opposing viewpoint?',
     '["Moreover", "On the other hand", "In addition", "For instance"]',
     '"On the other hand"',
     '"On the other hand" introduces a contrasting/opposing viewpoint.',
     3, 1.0, 45, 'cohesion'),
    ('writing',
     'A paragraph that lacks a topic sentence is most likely to be penalised for ____.',
     '["grammatical range", "coherence and cohesion", "lexical resource", "spelling"]',
     '"coherence and cohesion"',
     'A clear topic sentence helps organise the paragraph and supports coherence & cohesion.',
     3, 1.0, 60, 'paragraphing'),
    ('writing',
     'For a Band 7+ essay, lexical resource requires ____.',
     '["repeating the same basic words", "precise, varied vocabulary with some less common items", "very long sentences", "only formal idioms"]',
     '"precise, varied vocabulary with some less common items"',
     'Band 7+ rewards precise and flexible use of vocabulary, including less common items.',
     4, 1.0, 60, 'lexical-resource'),

    -- ------------------------------------------------ SPEAKING
    ('speaking',
     'In IELTS Speaking Part 2, you are asked to ____.',
     '["answer short personal questions", "speak for 1-2 minutes on a topic card", "read a passage aloud", "have a debate"]',
     '"speak for 1-2 minutes on a topic card"',
     'Part 2 is a long turn: you speak for 1-2 minutes on a given cue card.',
     2, 1.0, 45, 'part-2'),
    ('speaking',
     'To improve fluency, the speaker should ____.',
     '["pause for several seconds on every word", "use fillers like "um" excessively", "speak at a natural, steady pace and use linking devices", "memorise a script and recite it"]',
     '"speak at a natural, steady pace and use linking devices"',
     'Fluency is about natural pace and connecting ideas, not memorisation or excessive fillers.',
     3, 1.0, 60, 'fluency'),
    ('speaking',
     'Which response shows good lexical resource for describing a "busy" place?',
     '["It is very crowded and full of people.", "It''s bustling with activity and teeming with commuters.", "It is a place. People are there. It is busy.", "It is like, um, very, like, busy."]',
     '"It''s bustling with activity and teeming with commuters."',
     'Rich, precise vocabulary ("bustling", "teeming", "commuters") demonstrates lexical resource.',
     4, 1.0, 60, 'lexical-resource'),
    ('speaking',
     'When you do not understand an examiner''s question, the best strategy is to ____.',
     '["stay silent", "politely ask for clarification", "answer a different question", "guess wildly"]',
     '"politely ask for clarification"',
     'Asking for clarification is natural and acceptable; it shows communication skills.',
     2, 1.0, 45, 'communication'),
    ('speaking',
     'Pronunciation is assessed in terms of ____.',
     '["accent and nationality", "intelligibility, stress, intonation, and sounds", "speaking speed only", "memorising difficult words"]',
     '"intelligibility, stress, intonation, and sounds"',
     'IELTS pronunciation band descriptors focus on intelligibility, stress, rhythm, intonation, and individual sounds.',
     3, 1.0, 60, 'pronunciation')
ON CONFLICT (id) DO NOTHING;
