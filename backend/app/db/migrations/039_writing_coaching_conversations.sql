-- IELTS AI Coach — Writing Coach: Coaching Conversations (v39)
-- Run this in your Supabase SQL editor after 038_writing_evaluation_attempt_number.sql
--
-- Stores context-aware Q&A conversations between the student and the Writing
-- Coach. Each coaching session is linked to a specific writing evaluation so
-- the AI can ground answers in the student essay + band feedback.
--
-- Reuses the mentor_messages table pattern (role + content + structured) but
-- keeps coaching in its own table so queries are scoped and cheap.

-- ============================================================
-- 1. writing_coaching_conversations
-- ============================================================
CREATE TABLE IF NOT EXISTS public.writing_coaching_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    evaluation_id UUID NOT NULL REFERENCES public.writing_evaluations(id) ON DELETE CASCADE,
    submission_id UUID NOT NULL REFERENCES public.writing_workspace_submissions(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Writing coaching session',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. writing_coaching_messages
-- ============================================================
CREATE TABLE IF NOT EXISTS public.writing_coaching_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES public.writing_coaching_conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'coach')),
    content TEXT NOT NULL,
    structured JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTSZ DEFAULT NOW()
);

-- ============================================================
-- 3. Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_writing_coaching_conv_user
    ON public.writing_coaching_conversations(user_id);

CREATE INDEX IF NOT EXISTS idx_writing_coaching_conv_eval
    ON public.writing_coaching_conversations(evaluation_id);

CREATE INDEX IF NOT EXISTS idx_writing_coaching_conv_submission
    ON public.writing_coaching_conversations(submission_id);

CREATE INDEX IF NOT EXISTS idx_writing_coaching_msg_conv
    ON public.writing_coaching_messages(conversation_id, created_at);

-- ============================================================
-- 4. Triggers
-- ============================================================
DROP TRIGGER IF EXISTS update_writing_coaching_conv_updated ON public.writing_coaching_conversations;
CREATE TRIGGER update_writing_coaching_conv_updated BEFORE UPDATE ON public.writing_coaching_conversations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 5. RLS
-- ============================================================
ALTER TABLE public.writing_coaching_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.writing_coaching_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own writing coaching conversations" ON public.writing_coaching_conversations;
CREATE POLICY "Users can view own writing coaching conversations"
    ON public.writing_coaching_conversations FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create own writing coaching conversations" ON public.writing_coaching_conversations;
CREATE POLICY "Users can create own writing coaching conversations"
    ON public.writing_coaching_conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own writing coaching messages" ON public.writing_coaching_messages;
CREATE POLICY "Users can view own writing coaching messages"
    ON public.writing_coaching_messages FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own writing coaching messages" ON public.writing_coaching_messages;
CREATE POLICY "Users can insert own writing coaching messages"
    ON public.writing_coaching_messages FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ============================================================
-- 6. Grants
-- ============================================================
GRANT ALL ON public.writing_coaching_conversations TO authenticated;
GRANT ALL ON public.writing_coaching_messages TO authenticated;
