-- IELTS AI Coach - Learning Session Mode (v14)
-- Run this in your Supabase SQL editor after 013_recommendation_engine.sql
--
-- Creates tables for tracking learning session state:
--   - learning_session_notes: notes taken during learning sessions
--   - learning_session_bookmarks: bookmarked resources within sessions
--   - learning_session_state: session progress tracking (progress bar, completion)
--

-- ============================================================
-- 1. learning_session_notes - notes taken during learning sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.learning_session_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    mission_id UUID REFERENCES public.daily_missions(id) ON DELETE SET NULL,
    resource_id UUID REFERENCES public.resources(id) ON DELETE SET NULL,
    session_id UUID,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. learning_session_bookmarks - bookmarked resources within sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.learning_session_bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    mission_id UUID REFERENCES public.daily_missions(id) ON DELETE SET NULL,
    session_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, resource_id, mission_id)
);

-- ============================================================
-- 3. learning_session_state - session progress tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS public.learning_session_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    mission_id UUID NOT NULL REFERENCES public.daily_missions(id) ON DELETE CASCADE,
    session_id UUID,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    progress_percent INTEGER DEFAULT 0 CHECK (progress_percent >= 0 AND progress_percent <= 100),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    notes_count INTEGER DEFAULT 0,
    bookmarked_resources INTEGER DEFAULT 0,
    xp_earned INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 4. Indexes for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_session_notes_user ON public.learning_session_notes(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_notes_mission ON public.learning_session_notes(mission_id);
CREATE INDEX IF NOT EXISTS idx_session_notes_resource ON public.learning_session_notes(resource_id);
CREATE INDEX IF NOT EXISTS idx_session_bookmarks_user ON public.learning_session_bookmarks(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_bookmarks_resource ON public.learning_session_bookmarks(resource_id);
CREATE INDEX IF NOT EXISTS idx_session_bookmarks_mission ON public.learning_session_bookmarks(mission_id);
CREATE INDEX IF NOT EXISTS idx_session_state_user ON public.learning_session_state(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_state_mission ON public.learning_session_state(mission_id);
CREATE INDEX IF NOT EXISTS idx_session_state_status ON public.learning_session_state(status);

-- ============================================================
-- 5. updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_learning_session_notes_updated_at ON public.learning_session_notes;
CREATE TRIGGER update_learning_session_notes_updated_at BEFORE UPDATE ON public.learning_session_notes
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_learning_session_state_updated_at ON public.learning_session_state;
CREATE TRIGGER update_learning_session_state_updated_at BEFORE UPDATE ON public.learning_session_state
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 6. Row Level Security
-- ============================================================
ALTER TABLE public.learning_session_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_session_bookmarks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_session_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own session notes" ON public.learning_session_notes;
CREATE POLICY "Users can view own session notes"
    ON public.learning_session_notes FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own session notes" ON public.learning_session_notes;
CREATE POLICY "Users can insert own session notes"
    ON public.learning_session_notes FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own session notes" ON public.learning_session_notes;
CREATE POLICY "Users can update own session notes"
    ON public.learning_session_notes FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own session notes" ON public.learning_session_notes;
CREATE POLICY "Users can delete own session notes"
    ON public.learning_session_notes FOR DELETE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own session bookmarks" ON public.learning_session_bookmarks;
CREATE POLICY "Users can view own session bookmarks"
    ON public.learning_session_bookmarks FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own session bookmarks" ON public.learning_session_bookmarks;
CREATE POLICY "Users can insert own session bookmarks"
    ON public.learning_session_bookmarks FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own session bookmarks" ON public.learning_session_bookmarks;
CREATE POLICY "Users can update own session bookmarks"
    ON public.learning_session_bookmarks FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own session state" ON public.learning_session_state;
CREATE POLICY "Users can view own session state"
    ON public.learning_session_state FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own session state" ON public.learning_session_state;
CREATE POLICY "Users can insert own session state"
    ON public.learning_session_state FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own session state" ON public.learning_session_state;
CREATE POLICY "Users can update own session state"
    ON public.learning_session_state FOR UPDATE
    USING (auth.uid() = user_id);

-- ============================================================
-- 7. Grant permissions
-- ============================================================
GRANT ALL ON public.learning_session_notes TO authenticated;
GRANT ALL ON public.learning_session_notes TO service_role;
GRANT ALL ON public.learning_session_bookmarks TO authenticated;
GRANT ALL ON public.learning_session_bookmarks TO service_role;
GRANT ALL ON public.learning_session_state TO authenticated;
GRANT ALL ON public.learning_session_state TO service_role;