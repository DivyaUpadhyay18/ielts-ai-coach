-- IELTS AI Coach - Mission Reflections (v31)
-- Run this in your Supabase SQL editor after 030_motivation_engine.sql
--
-- After a daily mission is completed, the ReflectionEngine synthesises a
-- structured reflection (strengths / mistakes / areas to revise / tomorrow's
-- focus / confidence / estimated improvement) from the learner's existing
-- data and persists one row per completed mission.
--
-- Design:
--   - One reflection per (user_id, mission_id) — idempotent: completing a
--     mission again regenerates (updates) the existing reflection.
--   - strengths / mistakes / areas_to_revise are JSONB arrays of strings.
--   - estimated_improvement is numeric (band steps, 0.25 granularity) with a
--     human-readable companion text.
--   - context_snapshot JSONB captures the learner context at reflection time
--     (mirrors mentor_conversations.context_snapshot for auditability).
--
-- No AI. All fields are derived deterministically from the learner's stored
-- data (profile, diagnostic, roadmap, study history, missed tasks, prediction).

-- ============================================================
-- 1. mission_reflections
-- ============================================================
CREATE TABLE IF NOT EXISTS public.mission_reflections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    mission_id UUID NOT NULL REFERENCES public.daily_missions(id) ON DELETE CASCADE,
    mission_date DATE NOT NULL,
    skill TEXT NOT NULL,
    strengths JSONB NOT NULL DEFAULT '[]'::jsonb,
    mistakes JSONB NOT NULL DEFAULT '[]'::jsonb,
    areas_to_revise JSONB NOT NULL DEFAULT '[]'::jsonb,
    tomorrow_focus TEXT NOT NULL,
    confidence_level SMALLINT NOT NULL CHECK (confidence_level BETWEEN 1 AND 10),
    estimated_improvement NUMERIC(3, 2) NOT NULL DEFAULT 0,
    estimated_improvement_text TEXT NOT NULL,
    context_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    -- One reflection per (user, mission) — idempotency guarantee.
    UNIQUE (user_id, mission_id)
);

CREATE INDEX IF NOT EXISTS idx_mission_reflections_user_created
    ON public.mission_reflections(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mission_reflections_user_mission
    ON public.mission_reflections(user_id, mission_id);
CREATE INDEX IF NOT EXISTS idx_mission_reflections_skill
    ON public.mission_reflections(user_id, skill, created_at DESC);

-- ============================================================
-- 2. updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_mission_reflections_updated_at ON public.mission_reflections;
CREATE TRIGGER update_mission_reflections_updated_at BEFORE UPDATE ON public.mission_reflections
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 3. Row Level Security
-- ============================================================
ALTER TABLE public.mission_reflections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own mission reflections" ON public.mission_reflections;
CREATE POLICY "Users can view own mission reflections" ON public.mission_reflections
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own mission reflections" ON public.mission_reflections;
CREATE POLICY "Users can insert own mission reflections" ON public.mission_reflections
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own mission reflections" ON public.mission_reflections;
CREATE POLICY "Users can update own mission reflections" ON public.mission_reflections
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own mission reflections" ON public.mission_reflections;
CREATE POLICY "Users can delete own mission reflections" ON public.mission_reflections
    FOR DELETE USING (auth.uid() = user_id);

GRANT ALL ON public.mission_reflections TO authenticated;