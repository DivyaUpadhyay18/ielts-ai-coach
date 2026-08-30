-- IELTS AI Coach — Speaking Diagnostic Module (v23)
-- Run this in your Supabase SQL editor after 022_writing_diagnostic.sql
--
-- Adds a dedicated Speaking diagnostic subsystem:
--   - speaking_prompts   : the Part 1 / Part 2 / Part 3 question bank with
--                          per-part prep & speaking time limits, topics, and
--                          optional Part-2 follow-up questions.
--   - speaking_recordings: user-recorded audio responses tied to a diagnostic
--                          attempt, with duration, transcript, manual IELTS
--                          4-criteria scoring, and a JSONB column reserved
--                          for future AI evaluation.
--
-- The module reuses the existing `diagnostic_attempts` lifecycle for resume
-- support, but stores speaking-specific outcomes (audio_url, duration,
-- transcript, manual scores, AI placeholders) in `speaking_recordings`.
--
-- Parts supported:
--   part_1 (Introduction & Interview, ~4-5 min)
--   part_2 (Individual Long Turn, prep 60s + speak 120s)
--   part_3 (Two-way Discussion, ~4-5 min)

-- ============================================================
-- 1. speaking_prompts (question bank)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.speaking_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part TEXT NOT NULL CHECK (part IN ('part_1','part_2','part_3')),
    title TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    prep_time_seconds INTEGER NOT NULL DEFAULT 0 CHECK (prep_time_seconds >= 0),
    speak_time_seconds INTEGER NOT NULL DEFAULT 60 CHECK (speak_time_seconds > 0),
    difficulty SMALLINT NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
    topics TEXT[] DEFAULT '{}',
    follow_up TEXT,                  -- Part 2 follow-up questions (optional)
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_speaking_prompts_active ON public.speaking_prompts(part, is_active);

-- ============================================================
-- 2. speaking_recordings (stored recordings + results)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.speaking_recordings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL REFERENCES public.diagnostic_attempts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    prompt_id UUID REFERENCES public.speaking_prompts(id) ON DELETE SET NULL,
    part TEXT NOT NULL DEFAULT 'part_1' CHECK (part IN ('part_1','part_2','part_3')),
    title TEXT NOT NULL DEFAULT '',
    -- the audio asset (path/URL) saved by the client
    audio_url TEXT NOT NULL DEFAULT '',
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    transcript TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (
        status IN ('in_progress','completed')
    ),
    -- Manual IELTS speaking scoring (4 criteria + overall), 0-9 in 0.5 steps
    fluency_coherence NUMERIC(3,1),
    lexical_resource NUMERIC(3,1),
    grammatical_range NUMERIC(3,1),
    pronunciation NUMERIC(3,1),
    overall_band NUMERIC(3,1),
    -- Reserved for future AI evaluation (architecture scaffold)
    ai_evaluation JSONB NOT NULL DEFAULT '{}',
    saved_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (attempt_id)
);

CREATE INDEX IF NOT EXISTS idx_speaking_recordings_user ON public.speaking_recordings(user_id);
CREATE INDEX IF NOT EXISTS idx_speaking_recordings_attempt ON public.speaking_recordings(attempt_id);
CREATE INDEX IF NOT EXISTS idx_speaking_recordings_part ON public.speaking_recordings(part);

-- ============================================================
-- updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_speaking_recordings_updated_at ON public.speaking_recordings;
CREATE TRIGGER update_speaking_recordings_updated_at BEFORE UPDATE ON public.speaking_recordings
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.speaking_prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.speaking_recordings ENABLE ROW LEVEL SECURITY;

-- Prompts readable by authenticated users (shared bank).
DROP POLICY IF EXISTS "Users can view speaking prompts" ON public.speaking_prompts;
CREATE POLICY "Users can view speaking prompts" ON public.speaking_prompts FOR SELECT
    USING (auth.uid() IS NOT NULL);

-- Recordings owner-scoped.
DROP POLICY IF EXISTS "Users can view own speaking recordings" ON public.speaking_recordings;
CREATE POLICY "Users can view own speaking recordings" ON public.speaking_recordings FOR SELECT
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own speaking recordings" ON public.speaking_recordings;
CREATE POLICY "Users can insert own speaking recordings" ON public.speaking_recordings FOR INSERT
    WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own speaking recordings" ON public.speaking_recordings;
CREATE POLICY "Users can update own speaking recordings" ON public.speaking_recordings FOR UPDATE
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own speaking recordings" ON public.speaking_recordings;
CREATE POLICY "Users can delete own speaking recordings" ON public.speaking_recordings FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- 3. Seed prompts (Part 1, 2, 3)
-- ============================================================
INSERT INTO public.speaking_prompts (
    part, title, prompt_text, prep_time_seconds, speak_time_seconds, difficulty, topics, follow_up, is_active
) VALUES
-- ------------------------------------------------ PART 1 (Introduction & Interview)
('part_1',
 'Part 1 — Home Town',
 'Could you tell me about the town or city where you live?',
 0, 60, 2, ARRAY['hometown','daily life'], NULL, true),
('part_1',
 'Part 1 — Work & Studies',
 'Do you work or are you a student? What do you enjoy most about it?',
 0, 60, 2, ARRAY['work','study'], NULL, true),
('part_1',
 'Part 1 — Free Time',
 'What do you like to do in your free time? Why?',
 0, 60, 2, ARRAY['leisure','hobbies'], NULL, true),
('part_1',
 'Part 1 — Technology',
 'How often do you use the internet, and what do you mostly use it for?',
 0, 60, 2, ARRAY['technology','habits'], NULL, true),

-- ------------------------------------------------ PART 2 (Individual Long Turn)
('part_2',
 'Part 2 — A Place You Visited',
 $$Describe a place you have visited that you found interesting.

You should say:
- where it is
- when you went there
- what you did there
and explain why you found it interesting.$$,
 60, 120, 3, ARRAY['travel','places'], 'Do you think people travel more now than in the past?', true),
('part_2',
 'Part 2 — A Person You Admire',
 $$Describe a person you admire.

You should say:
- who this person is
- how you know them
- what they have achieved
and explain why you admire them.$$,
 60, 120, 3, ARRAY['people','role-models'], 'Why do you think some people become role models?', true),
('part_2',
 'Part 2 — A Skill You Learned',
 $$Describe a skill you learned that was useful.

You should say:
- what the skill was
- how you learned it
- how long it took
and explain why it was useful to you.$$,
 60, 120, 3, ARRAY['skills','learning'], 'Do you think people should keep learning new skills in life?', true),

-- ------------------------------------------------ PART 3 (Two-way Discussion)
('part_3',
 'Part 3 — Cities & Urban Life',
 'In your opinion, what makes a city a good place to live? How have cities changed in recent decades?',
 0, 90, 4, ARRAY['cities','society'], NULL, true),
('part_3',
 'Part 3 — Technology & Education',
 'How has technology changed the way people learn? What are the advantages of online learning compared to traditional classrooms?',
 0, 90, 4, ARRAY['technology','education'], NULL, true),
('part_3',
 'Part 3 — Role Models & Society',
 'Why do some people become role models? Do you think celebrities should be considered role models?',
 0, 90, 4, ARRAY['society','people'], NULL, true)
ON CONFLICT (id) DO NOTHING;
