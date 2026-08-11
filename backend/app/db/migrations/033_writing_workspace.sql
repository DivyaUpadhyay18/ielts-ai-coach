-- IELTS AI Coach — Writing Workspace (v33)
-- Run this in your Supabase SQL editor after 032_mentor_memory.sql
--
-- The Writing Workspace is a practice environment separate from the
-- diagnostic module.  Users can pick Task 1 or Task 2, write in a
-- full-screen editor with a live timer and word counter, auto-save
-- drafts, and submit for (future) evaluation.
--
-- Reuses the existing writing_prompts question bank (v022) so there is
-- a single source of truth for prompts.
--
-- Table:
--   writing_workspace_submissions
--     → per-user essay submissions tied to a writing_prompt
--     → stores the essay body, word count, time spent, and a
--       pre-submission summary (warnings, time spent, word count)
--     → is_locked = true once submitted (immutable)
--     → reserved JSONB columns for future AI evaluation

-- ============================================================
-- 1. writing_workspace_submissions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.writing_workspace_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    prompt_id UUID NOT NULL REFERENCES public.writing_prompts(id) ON DELETE RESTRICT,
    task_type TEXT NOT NULL CHECK (task_type IN ('task_1', 'task_2')),
    title TEXT NOT NULL DEFAULT '',
    prompt_text TEXT NOT NULL DEFAULT '',
    word_limit INTEGER NOT NULL DEFAULT 250,
    time_limit_seconds INTEGER NOT NULL DEFAULT 2400,
    -- the essay body (auto-saved as the user types)
    essay_text TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    time_seconds_spent INTEGER NOT NULL DEFAULT 0,
    -- pre-submission summary captured at submit time
    submission_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- state machine: draft → submitted (locked)
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'submitted')
    ),
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    -- reserved for future AI evaluation
    ai_evaluation JSONB NOT NULL DEFAULT '{}'::jsonb,
    grammar_feedback JSONB NOT NULL DEFAULT '{}'::jsonb,
    vocabulary_feedback JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_at TIMESTAMPTZ
);

-- ============================================================
-- 2. Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_ww_submissions_user
    ON public.writing_workspace_submissions(user_id);

CREATE INDEX IF NOT EXISTS idx_ww_submissions_user_status
    ON public.writing_workspace_submissions(user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ww_submissions_prompt
    ON public.writing_workspace_submissions(prompt_id);

CREATE INDEX IF NOT EXISTS idx_ww_submissions_task_type
    ON public.writing_workspace_submissions(task_type);

-- ============================================================
-- 3. updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_writing_workspace_updated_at ON public.writing_workspace_submissions;
CREATE TRIGGER update_writing_workspace_updated_at BEFORE UPDATE ON public.writing_workspace_submissions
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 4. Row Level Security
-- ============================================================
ALTER TABLE public.writing_workspace_submissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own writing submissions" ON public.writing_workspace_submissions;
CREATE POLICY "Users can view own writing submissions"
    ON public.writing_workspace_submissions FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own writing submissions" ON public.writing_workspace_submissions;
CREATE POLICY "Users can insert own writing submissions"
    ON public.writing_workspace_submissions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own drafts" ON public.writing_workspace_submissions;
CREATE POLICY "Users can update own drafts"
    ON public.writing_workspace_submissions FOR UPDATE
    USING (auth.uid() = user_id AND is_locked = FALSE);

DROP POLICY IF EXISTS "Users can delete own drafts" ON public.writing_workspace_submissions;
CREATE POLICY "Users can delete own drafts"
    ON public.writing_workspace_submissions FOR DELETE
    USING (auth.uid() = user_id AND status = 'draft');

-- ============================================================
-- 5. Grants
-- ============================================================
GRANT ALL ON public.writing_workspace_submissions TO authenticated;
