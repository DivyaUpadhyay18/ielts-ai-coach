-- IELTS AI Coach - Recommendation Engine (v13)
-- Run this in your Supabase SQL editor after 012_resources.sql
--
-- Creates the recommendation_logs table for tracking recommendation requests
-- and recommendations served, plus the recommendation_resource_view for
-- tracking user interactions with recommended resources.

-- ============================================================
-- 1. recommendation_logs - audit trail of recommendation requests
-- ============================================================
CREATE TABLE IF NOT EXISTS public.recommendation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    run_date DATE NOT NULL DEFAULT CURRENT_DATE,
    current_band NUMERIC(2,1),
    target_band NUMERIC(2,1),
    weakest_skill TEXT,
    today_mission_skill TEXT,
    sub_skill TEXT,
    estimated_time INTEGER,
    remaining_days INTEGER,
    resource_count INTEGER,
    top_resource_id UUID REFERENCES public.resources(id) ON DELETE SET NULL,
    top_score NUMERIC(5,2),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. recommendation_resource_view - tracks user actions on recommendations
-- ============================================================
CREATE TABLE IF NOT EXISTS public.recommendation_resource_view (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    recommendation_log_id UUID REFERENCES public.recommendation_logs(id) ON DELETE SET NULL,
    served_at TIMESTAMPTZ DEFAULT NOW(),
    viewed BOOLEAN DEFAULT FALSE,
    clicked BOOLEAN DEFAULT FALSE,
    completed BOOLEAN DEFAULT FALSE,
    session_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. recommendation_cache - cached recommendations per user
-- ============================================================
CREATE TABLE IF NOT EXISTS public.recommendation_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    run_date DATE NOT NULL DEFAULT CURRENT_DATE,
    resources_json JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '1 hour'
);

-- ============================================================
-- 4. Indexes for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_recommendation_logs_user ON public.recommendation_logs(user_id, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_logs_skill ON public.recommendation_logs(weakest_skill, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_resource_view_user ON public.recommendation_resource_view(user_id, served_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_resource_view_resource ON public.recommendation_resource_view(resource_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_cache_user ON public.recommendation_cache(user_id, run_date DESC);

-- ============================================================
-- 5. updated_at trigger for recommendation_resource_view
-- ============================================================
DROP TRIGGER IF EXISTS update_recommendation_resource_view_updated_at ON public.recommendation_resource_view;
CREATE TRIGGER update_recommendation_resource_view_updated_at BEFORE UPDATE ON public.recommendation_resource_view
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 6. Row Level Security
-- ============================================================
ALTER TABLE public.recommendation_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recommendation_resource_view ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recommendation_cache ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own recommendation logs" ON public.recommendation_logs;
CREATE POLICY "Users can view own recommendation logs" ON public.recommendation_logs FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own recommendation logs" ON public.recommendation_logs;
CREATE POLICY "Users can insert own recommendation logs" ON public.recommendation_logs FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own recommendation views" ON public.recommendation_resource_view;
CREATE POLICY "Users can view own recommendation views" ON public.recommendation_resource_view FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own recommendation views" ON public.recommendation_resource_view;
CREATE POLICY "Users can insert own recommendation views" ON public.recommendation_resource_view FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own recommendation views" ON public.recommendation_resource_view;
CREATE POLICY "Users can update own recommendation views" ON public.recommendation_resource_view FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own recommendation cache" ON public.recommendation_cache;
CREATE POLICY "Users can view own recommendation cache" ON public.recommendation_cache FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own recommendation cache" ON public.recommendation_cache;
CREATE POLICY "Users can insert own recommendation cache" ON public.recommendation_cache FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ============================================================
-- 7. Grant permissions
-- ============================================================
GRANT ALL ON public.recommendation_logs TO authenticated;
GRANT ALL ON public.recommendation_logs TO service_role;
GRANT ALL ON public.recommendation_resource_view TO authenticated;
GRANT ALL ON public.recommendation_resource_view TO service_role;
GRANT ALL ON public.recommendation_cache TO authenticated;
GRANT ALL ON public.recommendation_cache TO service_role;