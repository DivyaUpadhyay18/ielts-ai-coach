-- IELTS AI Coach - Community Resource Suggestions Enhancements (v18)
-- Run this in your Supabase SQL editor after 017_recommendation_engine.sql
--
-- Enhances the resource_suggestions table (created in 015_admin_resource_dashboard.sql)
-- to support a full community suggestion workflow:
--   - Adds `category`   : YouTube Video, PDF, Website, Practice Test, Vocabulary List
--   - Adds `reason`     : user's justification for the suggestion
--   - Adds `votes`      : running vote count
--   - Creates resource_suggestion_votes table (unique user+suggestion => one vote per user)
--   - Adds RLS policies for users to submit & vote on suggestions

-- ============================================================
-- 1. Add category / reason / votes columns to resource_suggestions
-- ============================================================
ALTER TABLE public.resource_suggestions
    ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'Website'
    CHECK (category IN ('YouTube Video', 'PDF', 'Website', 'Practice Test', 'Vocabulary List'));

ALTER TABLE public.resource_suggestions
    ADD COLUMN IF NOT EXISTS reason TEXT;

ALTER TABLE public.resource_suggestions
    ADD COLUMN IF NOT EXISTS votes INTEGER NOT NULL DEFAULT 0 CHECK (votes >= 0);

-- Index for category-based filtering
CREATE INDEX IF NOT EXISTS idx_resource_suggestions_category
    ON public.resource_suggestions(category);

-- Index for voting / popularity ordering
CREATE INDEX IF NOT EXISTS idx_resource_suggestions_votes
    ON public.resource_suggestions(votes DESC);

-- ============================================================
-- 2. resource_suggestion_votes (one vote per user per suggestion)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_suggestion_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    suggestion_id UUID NOT NULL REFERENCES public.resource_suggestions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, suggestion_id)
);

CREATE INDEX IF NOT EXISTS idx_suggestion_votes_user
    ON public.resource_suggestion_votes(user_id);

CREATE INDEX IF NOT EXISTS idx_suggestion_votes_suggestion
    ON public.resource_suggestion_votes(suggestion_id);

-- ============================================================
-- 3. Row Level Security for resource_suggestions
--    - anyone (authenticated) can view approved suggestions
--    - users can submit suggestions
--    - users can view/update/delete their own submissions
--    - admins can view/update all
-- ============================================================
ALTER TABLE public.resource_suggestions ENABLE ROW LEVEL SECURITY;

-- Anyone can view approved suggestions (community browse)
DROP POLICY IF EXISTS "Anyone can view approved suggestions" ON public.resource_suggestions;
CREATE POLICY "Anyone can view approved suggestions" ON public.resource_suggestions
    FOR SELECT USING (status = 'approved');

-- Users can view their own suggestions (any status)
DROP POLICY IF EXISTS "Users can view own suggestions" ON public.resource_suggestions;
CREATE POLICY "Users can view own suggestions" ON public.resource_suggestions
    FOR SELECT USING (auth.uid() = user_id);

-- Users can submit suggestions (status forced to pending by app)
DROP POLICY IF EXISTS "Users can insert suggestions" ON public.resource_suggestions;
CREATE POLICY "Users can insert suggestions" ON public.resource_suggestions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can update/withdraw their own pending suggestions
DROP POLICY IF EXISTS "Users can update own suggestions" ON public.resource_suggestions;
CREATE POLICY "Users can update own suggestions" ON public.resource_suggestions
    FOR UPDATE USING (auth.uid() = user_id AND status = 'pending');

-- Users can delete their own pending suggestions
DROP POLICY IF EXISTS "Users can delete own suggestions" ON public.resource_suggestions;
CREATE POLICY "Users can delete own suggestions" ON public.resource_suggestions
    FOR DELETE USING (auth.uid() = user_id AND status = 'pending');

-- Admins can view all suggestions
DROP POLICY IF EXISTS "Admins can view all suggestions" ON public.resource_suggestions;
CREATE POLICY "Admins can view all suggestions" ON public.resource_suggestions
    FOR SELECT USING (public.is_admin());

-- Admins can update any suggestion (approve/reject/edit)
DROP POLICY IF EXISTS "Admins can update any suggestion" ON public.resource_suggestions;
CREATE POLICY "Admins can update any suggestion" ON public.resource_suggestions
    FOR UPDATE USING (public.is_admin());

-- Admins can delete any suggestion
DROP POLICY IF EXISTS "Admins can delete any suggestion" ON public.resource_suggestions;
CREATE POLICY "Admins can delete any suggestion" ON public.resource_suggestions
    FOR DELETE USING (public.is_admin());

-- ============================================================
-- 4. RLS for resource_suggestion_votes
-- ============================================================
ALTER TABLE public.resource_suggestion_votes ENABLE ROW LEVEL SECURITY;

-- Users can view their own votes
DROP POLICY IF EXISTS "Users can view own suggestion votes" ON public.resource_suggestion_votes;
CREATE POLICY "Users can view own suggestion votes" ON public.resource_suggestion_votes
    FOR SELECT USING (auth.uid() = user_id);

-- Users can cast their own vote (unique constraint enforces one-per-user)
DROP POLICY IF EXISTS "Users can insert own suggestion votes" ON public.resource_suggestion_votes;
CREATE POLICY "Users can insert own suggestion votes" ON public.resource_suggestion_votes
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can remove their own vote
DROP POLICY IF EXISTS "Users can delete own suggestion votes" ON public.resource_suggestion_votes;
CREATE POLICY "Users can delete own suggestion votes" ON public.resource_suggestion_votes
    FOR DELETE USING (auth.uid() = user_id);

-- ============================================================
-- 5. Database trigger: increment/decrement votes atomically
-- ============================================================

-- Increment votes when a vote row is inserted
CREATE OR REPLACE FUNCTION public.increment_suggestion_votes()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.resource_suggestions
    SET votes = votes + 1
    WHERE id = NEW.suggestion_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS increment_suggestion_votes_trigger ON public.resource_suggestion_votes;
CREATE TRIGGER increment_suggestion_votes_trigger
    AFTER INSERT ON public.resource_suggestion_votes
    FOR EACH ROW EXECUTE FUNCTION public.increment_suggestion_votes();

-- Decrement votes when a vote row is removed
CREATE OR REPLACE FUNCTION public.decrement_suggestion_votes()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.resource_suggestions
    SET votes = GREATEST(votes - 1, 0)
    WHERE id = OLD.suggestion_id;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS decrement_suggestion_votes_trigger ON public.resource_suggestion_votes;
CREATE TRIGGER decrement_suggestion_votes_trigger
    AFTER DELETE ON public.resource_suggestion_votes
    FOR EACH ROW EXECUTE FUNCTION public.decrement_suggestion_votes();
