-- IELTS AI Coach - Onboarding & Roadmap Schema
-- Run this in your Supabase SQL editor

-- ============================================================
-- 1. Extend users table with onboarding fields
-- ============================================================

-- Add current band (0.0 - 9.0, step 0.5)
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS current_band NUMERIC(2,1) CHECK (
        current_band IS NULL OR (current_band * 2)::int = (current_band * 2)
    );

-- Preferred study time of day
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS preferred_study_time TEXT CHECK (
        preferred_study_time IS NULL OR preferred_study_time IN ('morning','afternoon','evening','night','anytime')
    );

-- Weakest / strongest skills (multi-select)
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS weakest_skill TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS strongest_skill TEXT[] DEFAULT '{}';

-- Previous IELTS attempt
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS previous_ielts_attempt BOOLEAN DEFAULT false;

-- ============================================================
-- 2. roadmaps table (placeholder roadmap storage)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.roadmaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL DEFAULT 'Personalized Study Roadmap',
    source_diagnostic_id UUID,
    target_band NUMERIC(2,1) NOT NULL CHECK ((target_band * 2)::int = (target_band * 2)),
    start_band NUMERIC(2,1) NOT NULL CHECK ((start_band * 2)::int = (start_band * 2)),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','completed')),
    total_weeks SMALLINT NOT NULL DEFAULT 8 CHECK (total_weeks BETWEEN 2 AND 52),
    meta JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, version)
);

-- ============================================================
-- 3. roadmap_phases table
-- ============================================================
CREATE TABLE IF NOT EXISTS public.roadmap_phases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    roadmap_id UUID NOT NULL REFERENCES public.roadmaps(id) ON DELETE CASCADE,
    order_index SMALLINT NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'locked' CHECK (status IN ('locked','active','completed')),
    duration_days INTEGER NOT NULL DEFAULT 7,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (roadmap_id, order_index)
);

-- ============================================================
-- 4. roadmap_tasks table
-- ============================================================
CREATE TABLE IF NOT EXISTS public.roadmap_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phase_id UUID NOT NULL REFERENCES public.roadmap_phases(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    skill TEXT NOT NULL CHECK (skill IN ('writing','speaking','reading','listening','vocabulary','grammar','mock','general')),
    duration_minutes SMALLINT NOT NULL DEFAULT 15 CHECK (duration_minutes BETWEEN 1 AND 240),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','missed','rescheduled')),
    resource_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_roadmaps_user ON public.roadmaps(user_id, status);
CREATE INDEX IF NOT EXISTS idx_roadmap_phases_roadmap ON public.roadmap_phases(roadmap_id, order_index);
CREATE INDEX IF NOT EXISTS idx_roadmap_tasks_phase ON public.roadmap_tasks(phase_id);

-- ============================================================
-- 6. RLS Policies
-- ============================================================
ALTER TABLE public.roadmaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roadmap_phases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roadmap_tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own roadmaps"
    ON public.roadmaps FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own roadmaps"
    ON public.roadmaps FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own roadmaps"
    ON public.roadmaps FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own roadmap phases"
    ON public.roadmap_phases FOR SELECT
    USING (roadmap_id IN (SELECT id FROM public.roadmaps WHERE user_id = auth.uid()));
CREATE POLICY "Users can insert own roadmap phases"
    ON public.roadmap_phases FOR INSERT
    WITH CHECK (roadmap_id IN (SELECT id FROM public.roadmaps WHERE user_id = auth.uid()));
CREATE POLICY "Users can update own roadmap phases"
    ON public.roadmap_phases FOR UPDATE
    USING (roadmap_id IN (SELECT id FROM public.roadmaps WHERE user_id = auth.uid()));

CREATE POLICY "Users can view own roadmap tasks"
    ON public.roadmap_tasks FOR SELECT
    USING (phase_id IN (SELECT p.id FROM public.roadmap_phases p
                        JOIN public.roadmaps r ON r.id = p.roadmap_id
                        WHERE r.user_id = auth.uid()));
CREATE POLICY "Users can insert own roadmap tasks"
    ON public.roadmap_tasks FOR INSERT
    WITH CHECK (phase_id IN (SELECT p.id FROM public.roadmap_phases p
                             JOIN public.roadmaps r ON r.id = p.roadmap_id
                             WHERE r.user_id = auth.uid()));
CREATE POLICY "Users can update own roadmap tasks"
    ON public.roadmap_tasks FOR UPDATE
    USING (phase_id IN (SELECT p.id FROM public.roadmap_phases p
                        JOIN public.roadmaps r ON r.id = p.roadmap_id
                        WHERE r.user_id = auth.uid()));

-- Auto-update updated_at trigger for roadmaps
CREATE OR REPLACE FUNCTION update_roadmap_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_roadmaps_updated_at
    BEFORE UPDATE ON public.roadmaps
    FOR EACH ROW
    EXECUTE FUNCTION update_roadmap_updated_at();

