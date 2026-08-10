-- IELTS AI Coach - Mentor Memory (v32)
-- Run this in your Supabase SQL editor after 031_mission_reflections.sql
--
-- The AI Mentor Memory system stores long-term learner insights extracted
-- from conversations, mistakes, and performance data. This allows the mentor
-- to provide increasingly personalized coaching across sessions.
--
-- Tables:
--   - mentor_memory           → per-user memory entries (typed insights)
--   - mentor_memory_events    → raw event log for audit/extraction pipeline
--
-- Design:
--   - Owner-scoped (user_id) for IDOR safety
--   - JSONB for flexible structured data per memory type
--   - Confidence/weighting system for memory reliability
--   - TTL support for time-sensitive memories
--   - Full-text search on content for FAQ retrieval

-- ============================================================
-- 1. mentor_memory
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mentor_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL,  -- recurring_mistake | faq | weak_grammar | weak_vocabulary | learning_preference | motivation_style | conversation_insight
    category TEXT,              -- e.g. "writing", "listening", "vocabulary", "grammar"
    subcategory TEXT,           -- e.g. "tenses", "reading_strategy", "note-taking"
    content TEXT NOT NULL,      -- the memory content (question, mistake, preference, etc.)
    structured_data JSONB NOT NULL DEFAULT '{}'::jsonb,  -- flexible structured data
    confidence NUMERIC(3,2) NOT NULL DEFAULT 0.5,  -- 0.00-1.00 reliability score
    weight INTEGER NOT NULL DEFAULT 1,  -- occurrence count / importance
    context JSONB NOT NULL DEFAULT '{}'::jsonb,  -- when/where this memory was formed
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    accessed_count INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ,  -- NULL = permanent, else TTL
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. mentor_memory_events (audit log for extraction pipeline)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mentor_memory_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES public.mentor_conversations(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,  -- question_asked | mistake_made | preference_detected | skill_weakness | coaching_interaction
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_mentor_memory_user_type
    ON public.mentor_memory(user_id, memory_type, is_active);

CREATE INDEX IF NOT EXISTS idx_mentor_memory_user_category
    ON public.mentor_memory(user_id, category, is_active);

CREATE INDEX IF NOT EXISTS idx_mentor_memory_user_accessed
    ON public.mentor_memory(user_id, last_accessed_at DESC);

CREATE INDEX IF NOT EXISTS idx_mentor_memory_events_user_processed
    ON public.mentor_memory_events(user_id, processed, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mentor_memory_events_conversation
    ON public.mentor_memory_events(conversation_id);

-- ============================================================
-- 4. updated_at triggers
-- ============================================================
DROP TRIGGER IF EXISTS update_mentor_memory_updated_at ON public.mentor_memory;
CREATE TRIGGER update_mentor_memory_updated_at BEFORE UPDATE ON public.mentor_memory
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 5. Row Level Security
-- ============================================================
ALTER TABLE public.mentor_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mentor_memory_events ENABLE ROW LEVEL SECURITY;

-- Memory policies
DROP POLICY IF EXISTS "Users can view own mentor memory" ON public.mentor_memory;
CREATE POLICY "Users can view own mentor memory" ON public.mentor_memory
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own mentor memory" ON public.mentor_memory;
CREATE POLICY "Users can insert own mentor memory" ON public.mentor_memory
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own mentor memory" ON public.mentor_memory;
CREATE POLICY "Users can update own mentor memory" ON public.mentor_memory
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own mentor memory" ON public.mentor_memory;
CREATE POLICY "Users can delete own mentor memory" ON public.mentor_memory
    FOR DELETE USING (auth.uid() = user_id);

-- Memory events policies
DROP POLICY IF EXISTS "Users can view own mentor memory events" ON public.mentor_memory_events;
CREATE POLICY "Users can view own mentor memory events" ON public.mentor_memory_events
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "System can insert mentor memory events" ON public.mentor_memory_events;
CREATE POLICY "System can insert mentor memory events" ON public.mentor_memory_events
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ============================================================
-- 6. Grants
-- ============================================================
GRANT ALL ON public.mentor_memory TO authenticated;
GRANT ALL ON public.mentor_memory_events TO authenticated;
