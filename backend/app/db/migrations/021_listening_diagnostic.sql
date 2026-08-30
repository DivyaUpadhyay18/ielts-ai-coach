-- IELTS AI Coach — Listening Diagnostic Module (v21)
-- Run this in your Supabase SQL editor after 020_reading_diagnostic.sql
--
-- Adds a dedicated Listening diagnostic subsystem:
--   - listening_tracks            : authentic IELTS-style listening sections
--   - listening_diagnostic_results: per-attempt granular results (accuracy by
--                                   question type, time, difficulty) — the
--                                   "store results" requirement.
--
-- The module reuses the existing `diagnostic_attempts` lifecycle for resume
-- support, but stores listening-specific outcomes (per question-type
-- accuracy, weak question types, difficulty level) in
-- `listening_diagnostic_results`.
--
-- Question types supported (IELTS Listening):
--   multiple_choice, map, form_completion, sentence_completion, matching

-- ============================================================
-- 1. listening_tracks
-- ============================================================
CREATE TABLE IF NOT EXISTS public.listening_tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    audio_url TEXT NOT NULL,
    section_number SMALLINT NOT NULL DEFAULT 1,
    difficulty SMALLINT NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
    topics TEXT[] DEFAULT '{}',
    transcript TEXT DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listening_tracks_active ON public.listening_tracks(is_active);

-- ============================================================
-- 2. listening_diagnostic_results
-- ============================================================
CREATE TABLE IF NOT EXISTS public.listening_diagnostic_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL REFERENCES public.diagnostic_attempts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    -- overall listening metrics
    total_questions INTEGER NOT NULL DEFAULT 0,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    accuracy DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_time_seconds INTEGER NOT NULL DEFAULT 0,
    listening_band NUMERIC(3,1),
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

CREATE INDEX IF NOT EXISTS idx_listening_results_user ON public.listening_diagnostic_results(user_id);
CREATE INDEX IF NOT EXISTS idx_listening_results_attempt ON public.listening_diagnostic_results(attempt_id);

-- ============================================================
-- 3. Extend diagnostic_questions with listening track linkage
-- ============================================================
ALTER TABLE public.diagnostic_questions
    ADD COLUMN IF NOT EXISTS track_id UUID REFERENCES public.listening_tracks(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_diag_questions_track ON public.diagnostic_questions(track_id);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.listening_tracks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.listening_diagnostic_results ENABLE ROW LEVEL SECURITY;

-- Tracks readable by authenticated users (shared bank).
DROP POLICY IF EXISTS "Users can view listening tracks" ON public.listening_tracks;
CREATE POLICY "Users can view listening tracks" ON public.listening_tracks FOR SELECT
    USING (auth.uid() IS NOT NULL);

-- Results owner-scoped.
DROP POLICY IF EXISTS "Users can view own listening results" ON public.listening_diagnostic_results;
CREATE POLICY "Users can view own listening results" ON public.listening_diagnostic_results FOR SELECT
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own listening results" ON public.listening_diagnostic_results;
CREATE POLICY "Users can insert own listening results" ON public.listening_diagnostic_results FOR INSERT
    WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own listening results" ON public.listening_diagnostic_results;
CREATE POLICY "Users can update own listening results" ON public.listening_diagnostic_results FOR UPDATE
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own listening results" ON public.listening_diagnostic_results;
CREATE POLICY "Users can delete own listening results" ON public.listening_diagnostic_results FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- 4. Seed tracks
-- ============================================================
INSERT INTO public.listening_tracks (
    title, description, audio_url, section_number, difficulty, topics, transcript, is_active
) VALUES
('A Campus Library Tour',
 'A university librarian explains the layout and services of the main library.',
 'https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3',
 1, 2, ARRAY['education', 'library'], 
 $$Right, welcome to the university library. Let me show you around. As you enter, the main reception desk is on your left, where you can borrow and return books. Directly ahead is the reading room, which is open to all students. The computer area is on the ground floor, to the right of the entrance, and the printing station is next to it. On the first floor you will find the science section, and the history section is at the far end of the same floor. The reserve collection is on the second floor, and there is a quiet study zone beside it. Finally, the cafe is located in the basement, near the main staircase.$$,
 true),
('A Tourist Information Session',
 'A travel advisor describes a weekend itinerary for a small coastal town.',
 'https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3',
 2, 3, ARRAY['travel', 'leisure'], 
 $$Good morning everyone. Today I am going to tell you about our weekend package to Seabright. You will be staying at the Harbour Hotel, which is a short walk from the beach. On Saturday morning, there is a guided walking tour starting at the old pier, and at midday you can visit the local market in the town square. In the afternoon, the boat trip departs from the marina at half past two. For dinner, I recommend the seafront restaurant, which is famous for its grilled fish. On Sunday, the museum opens at ten o'clock, and there is a scenic train ride along the coast at noon. Please remember to bring comfortable shoes and a raincoat, as the weather can change quickly.$$,
 true),
('A Health and Fitness Talk',
 'A health coach discusses the benefits of regular exercise and a balanced diet.',
 'https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3',
 3, 4, ARRAY['health', 'fitness'], 
 $$Hello and welcome to the health and fitness workshop. Regular exercise is one of the most effective ways to improve both physical and mental well-being. Studies show that just thirty minutes of moderate activity, five times a week, can significantly reduce the risk of heart disease. It is important to combine aerobic exercise, such as running or swimming, with strength training twice a week. A balanced diet is equally important, and you should aim to eat at least five portions of fruit and vegetables each day. Staying hydrated is also crucial, and experts recommend drinking around two litres of water daily. Finally, getting enough sleep of seven to eight hours supports recovery and helps maintain a healthy weight.$$,
 true)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 5. Seed listening questions grouped by track + type
-- ============================================================
-- Multiple Choice
INSERT INTO public.diagnostic_questions
    (section, track_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Campus Library Tour'),
     'multiple_choice',
     'According to the librarian, where is the main reception desk?',
     '["On the right of the entrance","On your left as you enter","On the first floor","In the basement"]',
     '"On your left as you enter"',
     'The librarian says "the main reception desk is on your left".',
     3, 1.0, 90, 'listening-for-detail'),
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Tourist Information Session'),
     'multiple_choice',
     'What does the advisor recommend for dinner on Saturday?',
     '["The local market","The museum cafe","The seafront restaurant","The harbour hotel kitchen"]',
     '"The seafront restaurant"',
     'The advisor says "for dinner, I recommend the seafront restaurant".',
     3, 1.0, 90, 'listening-for-detail');

-- Map
INSERT INTO public.diagnostic_questions
    (section, track_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Campus Library Tour'),
     'map',
     'On the ground floor, where is the computer area located?',
     '["To the left of the entrance","Next to the cafe","To the right of the entrance","On the first floor"]',
     '"To the right of the entrance"',
     'The librarian says "the computer area is on the ground floor, to the right of the entrance".',
     4, 1.0, 90, 'map'),
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Campus Library Tour'),
     'map',
     'Where is the quiet study zone located?',
     '["Beside the reserve collection","Near the reception desk","Next to the cafe","By the main staircase"]',
     '"Beside the reserve collection"',
     'The librarian says "the reserve collection is on the second floor, and there is a quiet study zone beside it".',
     4, 1.0, 90, 'map');

-- Form Completion
INSERT INTO public.diagnostic_questions
    (section, track_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Tourist Information Session'),
     'form_completion',
     'Complete the form: The guided walking tour starts at the ____.',
     NULL,
     '"old pier"',
     'The advisor says "a guided walking tour starting at the old pier".',
     3, 1.0, 90, 'form-completion'),
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Tourist Information Session'),
     'form_completion',
     'Complete the form: The boat trip departs from the marina at ____.',
     NULL,
     '"half past two"',
     'The advisor says "the boat trip departs from the marina at half past two".',
     3, 1.0, 90, 'form-completion');

-- Sentence Completion
INSERT INTO public.diagnostic_questions
    (section, track_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Health and Fitness Talk'),
     'sentence_completion',
     'Complete the sentence: Regular exercise of thirty minutes, five times a week, can reduce the risk of ____.',
     NULL,
     '"heart disease"',
     'The coach says "significantly reduce the risk of heart disease".',
     3, 1.0, 90, 'sentence-completion'),
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Health and Fitness Talk'),
     'sentence_completion',
     'Complete the sentence: Experts recommend drinking around ____ litres of water each day.',
     NULL,
     '"two"',
     'The coach says "drinking around two litres of water daily".',
     3, 1.0, 90, 'sentence-completion');

-- Matching
INSERT INTO public.diagnostic_questions
    (section, track_id, question_type, prompt, options, answer, explanation, difficulty, weight, time_limit_seconds, skill_tag)
VALUES
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Health and Fitness Talk'),
     'matching',
     'Match the activity to its recommended frequency: strength training.',
     '["Five times a week","Twice a week","Once a month","Every day"]',
     '"Twice a week"',
     'The coach says "combine aerobic exercise ... with strength training twice a week".',
     4, 1.0, 90, 'matching'),
    ('listening', (SELECT id FROM public.listening_tracks WHERE title='A Campus Library Tour'),
     'matching',
     'Match the service to its location: the printing station.',
     '["Next to the computer area","On the second floor","Beside the cafe","In the basement"]',
     '"Next to the computer area"',
     'The librarian says "the printing station is next to it" (the computer area).',
     4, 1.0, 90, 'matching')
ON CONFLICT (id) DO NOTHING;
