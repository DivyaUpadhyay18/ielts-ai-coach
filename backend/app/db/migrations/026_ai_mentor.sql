-- IELTS AI Coach — AI Mentor (v26)
-- Run this in your Supabase SQL editor after 025_band_estimation.sql
--
-- Creates the tables that back the AI Mentor coaching service:
--   - mentor_conversations : one row per coaching session (mode + context snapshot)
--   - mentor_messages      : the actual user/mentor turns inside a conversation
--
-- The AI Mentor NEVER generates a study plan from scratch. It analyses the
-- existing roadmap (study_plans / daily_plans / tasks / schedule_adjustments)
-- and coaches the student within that roadmap. Conversations persist a compact
-- context_snapshot JSONB at coaching time so the audit trail shows exactly which
-- learner state produced each coaching message.

-- ============================================================
-- 1. mentor_conversations
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mentor_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'daily_coaching' CHECK (
        mode IN ('daily_coaching','roadmap_analysis','risk_check','ask_mentor','general')
    ),
    title TEXT NOT NULL DEFAULT 'Coaching session',
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('active','archived')
    ),
    context_snapshot JSONB NOT NULL DEFAULT '{}',
    meta JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mentor_conversations_user ON public.mentor_conversations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mentor_conversations_user_mode ON public.mentor_conversations(user_id, mode);

-- ============================================================
-- 2. mentor_messages
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mentor_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES public.mentor_conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','mentor')),
    content TEXT NOT NULL,
    structured JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mentor_messages_conversation ON public.mentor_messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_mentor_messages_user ON public.mentor_messages(user_id, created_at DESC);

-- ============================================================
-- updated_at trigger (shared function from v3)
-- ============================================================
DROP TRIGGER IF EXISTS update_mentor_conversations_updated_at ON public.mentor_conversations;
CREATE TRIGGER update_mentor_conversations_updated_at BEFORE UPDATE ON public.mentor_conversations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.mentor_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mentor_messages ENABLE ROW LEVEL SECURITY;

-- mentor_conversations
DROP POLICY IF EXISTS "Users can view own mentor conversations" ON public.mentor_conversations;
CREATE POLICY "Users can view own mentor conversations" ON public.mentor_conversations FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own mentor conversations" ON public.mentor_conversations;
CREATE POLICY "Users can insert own mentor conversations" ON public.mentor_conversations FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own mentor conversations" ON public.mentor_conversations;
CREATE POLICY "Users can update own mentor conversations" ON public.mentor_conversations FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own mentor conversations" ON public.mentor_conversations;
CREATE POLICY "Users can delete own mentor conversations" ON public.mentor_conversations FOR DELETE USING (auth.uid() = user_id);

-- mentor_messages
DROP POLICY IF EXISTS "Users can view own mentor messages" ON public.mentor_messages;
CREATE POLICY "Users can view own mentor messages" ON public.mentor_messages FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own mentor messages" ON public.mentor_messages;
CREATE POLICY "Users can insert own mentor messages" ON public.mentor_messages FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own mentor messages" ON public.mentor_messages;
CREATE POLICY "Users can update own mentor messages" ON public.mentor_messages FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own mentor messages" ON public.mentor_messages;
CREATE POLICY "Users can delete own mentor messages" ON public.mentor_messages FOR DELETE USING (auth.uid() = user_id);