-- IELTS AI Coach - Resource Quality Scoring & Moderation (v14)
-- Run this in your Supabase SQL editor after 013_analytics.sql
--
-- Creates the tables that back the Resource Quality Scoring system:
--   - resource_feedback      : user feedback (broken links, suggestions, corrections)
--   - resource_quality_scores: per-resource computed scores (quality, popularity, completion, recommendation)
--   - resource_moderation_log: admin moderation audit trail
-- Everything is stored in the database and derived through this schema.

-- ============================================================
-- 1. resource_feedback (user-submitted feedback)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('broken_link', 'better_resource', 'correction', 'rating')),
    -- For 'broken_link': details about what's broken
    -- For 'better_resource': suggested_url + suggested_title
    -- For 'correction': field + suggested_value + reason
    -- For 'rating': rating (1-5)
    title TEXT,
    description TEXT,
    suggested_url TEXT,
    suggested_title TEXT,
    field_name TEXT,
    suggested_value TEXT,
    reason TEXT,
    rating SMALLINT CHECK (rating IS NULL OR (rating BETWEEN 1 AND 5)),
    -- Moderation status
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'resolved', 'dismissed')),
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    admin_notes TEXT,
    moderated_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    moderated_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resource_feedback_user ON public.resource_feedback(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resource_feedback_resource ON public.resource_feedback(resource_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resource_feedback_status ON public.resource_feedback(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resource_feedback_type ON public.resource_feedback(feedback_type, status);
CREATE INDEX IF NOT EXISTS idx_resource_feedback_priority ON public.resource_feedback(priority, status);

-- ============================================================
-- 2. resource_quality_scores (per-resource computed scores)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_quality_scores (
    resource_id UUID PRIMARY KEY REFERENCES public.resources(id) ON DELETE CASCADE,
    -- Quality Score (0-100): weighted avg of ratings, adjusted for broken links, corrections, verified status
    quality_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (quality_score >= 0 AND quality_score <= 100),
    -- Popularity Score (0-100): normalized views, bookmarks, likes
    popularity_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (popularity_score >= 0 AND popularity_score <= 100),
    -- Completion Score (0-100): completion rate normalized
    completion_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (completion_score >= 0 AND completion_score <= 100),
    -- Recommendation Score (0-100): combined weighted mix of quality, popularity, completion, minus broken link penalty
    recommendation_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (recommendation_score >= 0 AND recommendation_score <= 100),
    -- Component breakdown for transparency
    avg_rating NUMERIC(3,2) DEFAULT 0,
    rating_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    bookmark_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    completion_count INTEGER DEFAULT 0,
    broken_link_count INTEGER DEFAULT 0,
    correction_count INTEGER DEFAULT 0,
    suggestion_count INTEGER DEFAULT 0,
    -- Computation metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resource_quality_recommendation ON public.resource_quality_scores(recommendation_score DESC);
CREATE INDEX IF NOT EXISTS idx_resource_quality_quality ON public.resource_quality_scores(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_resource_quality_popularity ON public.resource_quality_scores(popularity_score DESC);

-- ============================================================
-- 3. resource_moderation_log (admin audit trail)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_moderation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_id UUID NOT NULL REFERENCES public.resource_feedback(id) ON DELETE CASCADE,
    admin_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('approved', 'rejected', 'resolved', 'dismissed', 'escalated', 'commented')),
    old_status TEXT,
    new_status TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_moderation_log_feedback ON public.resource_moderation_log(feedback_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_moderation_log_admin ON public.resource_moderation_log(admin_id, created_at DESC);

-- ============================================================
-- updated_at triggers
-- ============================================================
DROP TRIGGER IF EXISTS update_resource_feedback_updated_at ON public.resource_feedback;
CREATE TRIGGER update_resource_feedback_updated_at BEFORE UPDATE ON public.resource_feedback
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_resource_quality_scores_updated_at ON public.resource_quality_scores;
CREATE TRIGGER update_resource_quality_scores_updated_at BEFORE UPDATE ON public.resource_quality_scores
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.resource_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_quality_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_moderation_log ENABLE ROW LEVEL SECURITY;

-- resource_feedback policies
DROP POLICY IF EXISTS "Users can view own feedback" ON public.resource_feedback;
CREATE POLICY "Users can view own feedback" ON public.resource_feedback FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own feedback" ON public.resource_feedback;
CREATE POLICY "Users can insert own feedback" ON public.resource_feedback FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own feedback" ON public.resource_feedback;
CREATE POLICY "Users can update own feedback" ON public.resource_feedback FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own feedback" ON public.resource_feedback;
CREATE POLICY "Users can delete own feedback" ON public.resource_feedback FOR DELETE USING (auth.uid() = user_id);

-- resource_quality_scores (public read, service write)
DROP POLICY IF EXISTS "Anyone can view quality scores" ON public.resource_quality_scores;
CREATE POLICY "Anyone can view quality scores" ON public.resource_quality_scores FOR SELECT USING (true);
DROP POLICY IF EXISTS "Service can update quality scores" ON public.resource_quality_scores;
CREATE POLICY "Service can update quality scores" ON public.resource_quality_scores FOR ALL USING (true) WITH CHECK (true);

-- resource_moderation_log (admin only)
DROP POLICY IF EXISTS "Admins can view moderation log" ON public.resource_moderation_log;
CREATE POLICY "Admins can view moderation log" ON public.resource_moderation_log FOR SELECT USING (true);
DROP POLICY IF EXISTS "Service can insert moderation log" ON public.resource_moderation_log;
CREATE POLICY "Service can insert moderation log" ON public.resource_moderation_log FOR INSERT WITH CHECK (true);

-- ============================================================
-- Helper: auto-set priority based on feedback type
-- ============================================================
CREATE OR REPLACE FUNCTION public.set_feedback_priority()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.feedback_type = 'broken_link' THEN
        NEW.priority = 'high';
    ELSIF NEW.feedback_type = 'correction' THEN
        NEW.priority = 'normal';
    ELSIF NEW.feedback_type = 'better_resource' THEN
        NEW.priority = 'low';
    ELSE
        NEW.priority = COALESCE(NEW.priority, 'normal');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_feedback_priority_trigger ON public.resource_feedback;
CREATE TRIGGER set_feedback_priority_trigger BEFORE INSERT ON public.resource_feedback
    FOR EACH ROW EXECUTE FUNCTION public.set_feedback_priority();