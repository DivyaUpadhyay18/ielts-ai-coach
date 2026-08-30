-- IELTS AI Coach — Writing Diagnostic Module (v22)
-- Run this in your Supabase SQL editor after 021_listening_diagnostic.sql
--
-- Adds a dedicated Writing diagnostic subsystem:
--   - writing_prompts : Task 1 & Task 2 prompts (the question bank)
--   - writing_essays  : user-submitted essays tied to a diagnostic attempt,
--                       with live auto-save, word count, timer, manual
--                       IELTS 4-criteria scoring, and JSONB columns reserved
--                       for future AI evaluation (grammar, vocabulary,
--                       full AI band assessment).
--
-- The module reuses the existing `diagnostic_attempts` lifecycle for resume
-- support, but stores writing-specific outcomes (essay text, word count,
-- time, manual scores, AI placeholders) in `writing_essays`.
--
-- Tasks supported:
--   task_1 (Academic report / General letter, ~150 words, 20 minutes)
--   task_2 (Essay, ~250 words, 40 minutes)

-- ============================================================
-- 1. writing_prompts (question bank)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.writing_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type TEXT NOT NULL CHECK (task_type IN ('task_1','task_2')),
    title TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    word_limit INTEGER NOT NULL DEFAULT 150 CHECK (word_limit > 0),
    time_limit_seconds INTEGER NOT NULL DEFAULT 1200 CHECK (time_limit_seconds > 0),
    difficulty SMALLINT NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
    topics TEXT[] DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_writing_prompts_active ON public.writing_prompts(task_type, is_active);

-- ============================================================
-- 2. writing_essays (stored essays + results)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.writing_essays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL REFERENCES public.diagnostic_attempts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    prompt_id UUID REFERENCES public.writing_prompts(id) ON DELETE SET NULL,
    task_type TEXT NOT NULL DEFAULT 'task_2' CHECK (task_type IN ('task_1','task_2')),
    title TEXT NOT NULL DEFAULT '',
    -- the essay body (auto-saved as the user types)
    essay_text TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    time_seconds_spent INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (
        status IN ('in_progress','completed')
    ),
    -- Manual IELTS scoring (4 criteria + overall), 0-9 in 0.5 steps
    task_response NUMERIC(3,1),
    coherence_cohesion NUMERIC(3,1),
    lexical_resource NUMERIC(3,1),
    grammatical_range NUMERIC(3,1),
    overall_band NUMERIC(3,1),
    -- Reserved for future AI evaluation (architecture scaffold)
    grammar_feedback JSONB NOT NULL DEFAULT '{}',
    vocabulary_feedback JSONB NOT NULL DEFAULT '{}',
    ai_evaluation JSONB NOT NULL DEFAULT '{}',
    saved_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (attempt_id)
);

CREATE INDEX IF NOT EXISTS idx_writing_essays_user ON public.writing_essays(user_id);
CREATE INDEX IF NOT EXISTS idx_writing_essays_attempt ON public.writing_essays(attempt_id);
CREATE INDEX IF NOT EXISTS idx_writing_essays_task ON public.writing_essays(task_type);

-- ============================================================
-- updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_writing_essays_updated_at ON public.writing_essays;
CREATE TRIGGER update_writing_essays_updated_at BEFORE UPDATE ON public.writing_essays
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.writing_prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.writing_essays ENABLE ROW LEVEL SECURITY;

-- Prompts readable by authenticated users (shared bank).
DROP POLICY IF EXISTS "Users can view writing prompts" ON public.writing_prompts;
CREATE POLICY "Users can view writing prompts" ON public.writing_prompts FOR SELECT
    USING (auth.uid() IS NOT NULL);

-- Essays owner-scoped.
DROP POLICY IF EXISTS "Users can view own writing essays" ON public.writing_essays;
CREATE POLICY "Users can view own writing essays" ON public.writing_essays FOR SELECT
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own writing essays" ON public.writing_essays;
CREATE POLICY "Users can insert own writing essays" ON public.writing_essays FOR INSERT
    WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own writing essays" ON public.writing_essays;
CREATE POLICY "Users can update own writing essays" ON public.writing_essays FOR UPDATE
    USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own writing essays" ON public.writing_essays;
CREATE POLICY "Users can delete own writing essays" ON public.writing_essays FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- 3. Seed prompts
-- ============================================================
INSERT INTO public.writing_prompts (
    task_type, title, prompt_text, word_limit, time_limit_seconds, difficulty, topics, is_active
) VALUES
-- ------------------------------------------------ TASK 1 (Academic report)
('task_1',
 'Task 1 — Line Graph: Energy Consumption',
 $$The graph below shows household energy consumption by fuel type in the UK between 1980 and 2020.

Summarise the information by selecting and reporting the main features, and make comparisons where relevant.$$,
 150, 1200, 3, ARRAY['energy','trends'], true),
('task_1',
 'Task 1 — Bar Chart: Internet Usage',
 $$The bar chart illustrates the percentage of people using the internet by age group in 2010 and 2020 in two countries.

Summarise the information by selecting and reporting the main features, and make comparisons where relevant.$$,
 150, 1200, 3, ARRAY['technology','age'], true),

-- ------------------------------------------------ TASK 2 (Essay)
('task_2',
 'Task 2 — Opinion: Accepting Bad Situations',
 $$Some people believe that it is best to accept a bad situation, such as an unsatisfactory job or shortage of money. Others argue that it is better to try and improve such situations.

Discuss both these views and give your own opinion.$$,
 250, 2400, 3, ARRAY['society','personal'], true),
('task_2',
 'Task 2 — Discussion: Remote Work',
 $$An increasing number of people now work from home instead of working in a traditional office.

What are the advantages and disadvantages of this development?$$,
 250, 2400, 3, ARRAY['work','technology'], true)
ON CONFLICT (id) DO NOTHING;
