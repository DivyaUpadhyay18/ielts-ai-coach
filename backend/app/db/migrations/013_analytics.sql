-- IELTS AI Coach - Analytics & Event Tracking (v13)
-- Run this in your Supabase SQL editor after 012_resource_notes.sql
--
-- Creates the tables that back the Analytics system:
--   - analytics_events   : append-only event log (views, completions, likes, ratings)
--   - resource_analytics : per-resource aggregate counters (views, bookmarks, likes, ratings)
--   - user_analytics     : per-user aggregate counters (views, completions, study time)
-- Everything is stored in the database and derived through this schema.

-- ============================================================
-- 1. analytics_events (append-only event ledger)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    entity_type TEXT,                -- 'resource' | 'task' | 'mission' | 'page' | 'assessment'
    entity_id TEXT,
    properties JSONB DEFAULT '{}',
    session_id TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_user ON public.analytics_events(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_event ON public.analytics_events(event, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_entity ON public.analytics_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_date ON public.analytics_events(timestamp::date);

-- ============================================================
-- 2. resource_analytics (per-resource aggregate counters)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_analytics (
    resource_id UUID PRIMARY KEY REFERENCES public.resources(id) ON DELETE CASCADE,
    view_count INTEGER NOT NULL DEFAULT 0 CHECK (view_count >= 0),
    bookmark_count INTEGER NOT NULL DEFAULT 0 CHECK (bookmark_count >= 0),
    like_count INTEGER NOT NULL DEFAULT 0 CHECK (like_count >= 0),
    rating_sum NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (rating_sum >= 0),
    rating_count INTEGER NOT NULL DEFAULT 0 CHECK (rating_count >= 0),
    completion_count INTEGER NOT NULL DEFAULT 0 CHECK (completion_count >= 0),
    avg_rating NUMERIC(3,2) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. user_analytics (per-user aggregate counters)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_analytics (
    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    total_views INTEGER NOT NULL DEFAULT 0 CHECK (total_views >= 0),
    total_completions INTEGER NOT NULL DEFAULT 0 CHECK (total_completions >= 0),
    total_bookmarks INTEGER NOT NULL DEFAULT 0 CHECK (total_bookmarks >= 0),
    total_likes INTEGER NOT NULL DEFAULT 0 CHECK (total_likes >= 0),
    total_ratings INTEGER NOT NULL DEFAULT 0 CHECK (total_ratings >= 0),
    total_study_minutes INTEGER NOT NULL DEFAULT 0 CHECK (total_study_minutes >= 0),
    total_tasks_completed INTEGER NOT NULL DEFAULT 0 CHECK (total_tasks_completed >= 0),
    total_sessions INTEGER NOT NULL DEFAULT 0 CHECK (total_sessions >= 0),
    last_active_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 4. resource_likes (user-resource like tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_likes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_resource_likes_user ON public.resource_likes(user_id);
CREATE INDEX IF NOT EXISTS idx_resource_likes_resource ON public.resource_likes(resource_id);

-- ============================================================
-- 5. resource_ratings (user-resource rating tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_resource_ratings_user ON public.resource_ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_resource_ratings_resource ON public.resource_ratings(resource_id);

-- ============================================================
-- 6. user_resource_completions (user-resource completion tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_resource_completions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    completed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_user_resource_completions_user ON public.user_resource_completions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_resource_completions_resource ON public.user_resource_completions(resource_id);

-- ============================================================
-- updated_at trigger (shared function from v3)
-- ============================================================
DROP TRIGGER IF EXISTS update_resource_analytics_updated_at ON public.resource_analytics;
CREATE TRIGGER update_resource_analytics_updated_at BEFORE UPDATE ON public.resource_analytics
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_analytics_updated_at ON public.user_analytics;
CREATE TRIGGER update_user_analytics_updated_at BEFORE UPDATE ON public.user_analytics
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_resource_ratings_updated_at ON public.resource_ratings;
CREATE TRIGGER update_resource_ratings_updated_at BEFORE UPDATE ON public.resource_ratings
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.analytics_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_likes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_resource_completions ENABLE ROW LEVEL SECURITY;

-- analytics_events
DROP POLICY IF EXISTS "Users can view own analytics events" ON public.analytics_events;
CREATE POLICY "Users can view own analytics events" ON public.analytics_events FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own analytics events" ON public.analytics_events;
CREATE POLICY "Users can insert own analytics events" ON public.analytics_events FOR INSERT WITH CHECK (auth.uid() = user_id);

-- resource_analytics (public read for catalog, admin write)
DROP POLICY IF EXISTS "Anyone can view resource analytics" ON public.resource_analytics;
CREATE POLICY "Anyone can view resource analytics" ON public.resource_analytics FOR SELECT USING (true);
DROP POLICY IF EXISTS "Service can update resource analytics" ON public.resource_analytics;
CREATE POLICY "Service can update resource analytics" ON public.resource_analytics FOR ALL USING (true) WITH CHECK (true);

-- user_analytics
DROP POLICY IF EXISTS "Users can view own analytics" ON public.user_analytics;
CREATE POLICY "Users can view own analytics" ON public.user_analytics FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own analytics" ON public.user_analytics;
CREATE POLICY "Users can insert own analytics" ON public.user_analytics FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own analytics" ON public.user_analytics;
CREATE POLICY "Users can update own analytics" ON public.user_analytics FOR UPDATE USING (auth.uid() = user_id);

-- resource_likes
DROP POLICY IF EXISTS "Users can view own likes" ON public.resource_likes;
CREATE POLICY "Users can view own likes" ON public.resource_likes FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own likes" ON public.resource_likes;
CREATE POLICY "Users can insert own likes" ON public.resource_likes FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own likes" ON public.resource_likes;
CREATE POLICY "Users can delete own likes" ON public.resource_likes FOR DELETE USING (auth.uid() = user_id);

-- resource_ratings
DROP POLICY IF EXISTS "Users can view own ratings" ON public.resource_ratings;
CREATE POLICY "Users can view own ratings" ON public.resource_ratings FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own ratings" ON public.resource_ratings;
CREATE POLICY "Users can insert own ratings" ON public.resource_ratings FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own ratings" ON public.resource_ratings;
CREATE POLICY "Users can update own ratings" ON public.resource_ratings FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own ratings" ON public.resource_ratings;
CREATE POLICY "Users can delete own ratings" ON public.resource_ratings FOR DELETE USING (auth.uid() = user_id);

-- user_resource_completions
DROP POLICY IF EXISTS "Users can view own completions" ON public.user_resource_completions;
CREATE POLICY "Users can view own completions" ON public.user_resource_completions FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own completions" ON public.user_resource_completions;
CREATE POLICY "Users can insert own completions" ON public.user_resource_completions FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own completions" ON public.user_resource_completions;
CREATE POLICY "Users can delete own completions" ON public.user_resource_completions FOR DELETE USING (auth.uid() = user_id);