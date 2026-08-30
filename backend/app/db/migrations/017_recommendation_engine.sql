-- IELTS AI Coach - Recommendation Engine Schema (v17)
-- Run this in your Supabase SQL editor after 016_admin_roles.sql
--
-- Creates tables for the Recommendation Engine:
--   - recommendation_logs: logs of recommendation runs
--   - recommendation_interactions: tracks user interactions with recommendations

-- ============================================================
-- 1. recommendation_logs
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
    resource_count INTEGER NOT NULL DEFAULT 0,
    top_resource_id UUID REFERENCES public.resources(id) ON DELETE SET NULL,
    top_score NUMERIC(5,2),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. recommendation_interactions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.recommendation_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    recommendation_log_id UUID REFERENCES public.recommendation_logs(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN ('viewed', 'clicked', 'completed', 'dismissed')),
    session_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_recommendation_logs_user ON public.recommendation_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_logs_run_date ON public.recommendation_logs(run_date DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_interactions_user ON public.recommendation_interactions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_interactions_resource ON public.recommendation_interactions(resource_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_interactions_log ON public.recommendation_interactions(recommendation_log_id);

-- ============================================================
-- updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_recommendation_logs_updated_at ON public.recommendation_logs;
CREATE TRIGGER update_recommendation_logs_updated_at BEFORE UPDATE ON public.recommendation_logs
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.recommendation_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recommendation_interactions ENABLE ROW LEVEL SECURITY;

-- recommendation_logs policies
DROP POLICY IF EXISTS "Users can view own recommendation logs" ON public.recommendation_logs;
CREATE POLICY "Users can view own recommendation logs" ON public.recommendation_logs FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own recommendation logs" ON public.recommendation_logs;
CREATE POLICY "Users can insert own recommendation logs" ON public.recommendation_logs FOR INSERT WITH CHECK (auth.uid() = user_id);

-- recommendation_interactions policies
DROP POLICY IF EXISTS "Users can view own interactions" ON public.recommendation_interactions;
CREATE POLICY "Users can view own interactions" ON public.recommendation_interactions FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own interactions" ON public.recommendation_interactions;
CREATE POLICY "Users can insert own interactions" ON public.recommendation_interactions FOR INSERT WITH CHECK (auth.uid() = user_id);

</parameter>
<task_progress>
- [x] Read and understand Resource Engine documentation
- [x] Identify all issues
- [ ] Fix critical issues
- [ ] Test CRUD operations
- [ ] Test Recommendation Engine
- [ ] Test Bookmarks functionality
- [ ] Test Notes functionality
- [ ] Test Search functionality
- [ ] Test Analytics
- [ ] Test Quality Score
- [ ] Test Admin Panel
- [ ] Run build
- [ ] Generate implementation report
- [ ] Commit changes
</task_progress>
</write_to_file>