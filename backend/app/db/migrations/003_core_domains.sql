-- IELTS AI Coach - Core Domain Schema (v3)
-- Run this in your Supabase SQL editor after 001_users.sql and 002_onboarding.sql
--
-- Creates canonical tables per DATABASE.md for the full backend database
-- integration: study_plans, daily_plans, tasks, resources, task_resources,
-- progress, achievements, user_achievements, notifications.
--
-- NOTE: The existing legacy roadmaps / roadmap_phases / roadmap_tasks tables
-- are intentionally left untouched (Option A: parallel placeholder feature).

-- ============================================================
-- 0. shared updated_at trigger (if not already created by 001)
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 1. study_plans
-- ============================================================
CREATE TABLE IF NOT EXISTS public.study_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    source_diagnostic_id UUID,
    target_band NUMERIC(2,1) NOT NULL CHECK ((target_band * 2)::int = (target_band * 2)),
    start_band NUMERIC(2,1) NOT NULL CHECK ((start_band * 2)::int = (start_band * 2)),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','completed')),
    total_weeks SMALLINT NOT NULL CHECK (total_weeks BETWEEN 2 AND 52),
    meta JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, version)
);

-- ============================================================
-- 2. daily_plans
-- ============================================================
CREATE TABLE IF NOT EXISTS public.daily_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    study_plan_id UUID NOT NULL REFERENCES public.study_plans(id) ON DELETE CASCADE,
    plan_date DATE NOT NULL,
    total_tasks SMALLINT NOT NULL DEFAULT 0 CHECK (total_tasks >= 0),
    completed_tasks SMALLINT NOT NULL DEFAULT 0 CHECK (completed_tasks >= 0 AND completed_tasks <= total_tasks),
    total_minutes SMALLINT NOT NULL DEFAULT 0 CHECK (total_minutes BETWEEN 0 AND 1440),
    completed_minutes SMALLINT NOT NULL DEFAULT 0 CHECK (completed_minutes >= 0 AND completed_minutes <= total_minutes),
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','in_progress','completed','missed','rolled_forward')),
    is_rest_day BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, plan_date)
);

-- ============================================================
-- 3. resources (public catalog - NO RLS, readable by anon)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
    description TEXT,
    type TEXT NOT NULL CHECK (type IN ('video','article','pdf','practice_test','guide','flashcard_set')),
    skill TEXT NOT NULL CHECK (skill IN ('writing','speaking','reading','listening','vocabulary','grammar','general')),
    module TEXT NOT NULL DEFAULT 'academic' CHECK (module IN ('academic','general','both')),
    difficulty TEXT NOT NULL DEFAULT 'intermediate' CHECK (difficulty IN ('beginner','intermediate','advanced','all_levels')),
    provider TEXT,
    url TEXT NOT NULL CHECK (url ~* '^https://'),
    duration_minutes SMALLINT CHECK (duration_minutes IS NULL OR duration_minutes BETWEEN 1 AND 600),
    tags TEXT[] NOT NULL DEFAULT '{}',
    is_published BOOLEAN NOT NULL DEFAULT true,
    view_count BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 4. tasks
-- ============================================================
CREATE TABLE IF NOT EXISTS public.tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    study_plan_id UUID REFERENCES public.study_plans(id) ON DELETE CASCADE,
    daily_plan_id UUID REFERENCES public.daily_plans(id) ON DELETE SET NULL,
    phase_index SMALLINT CHECK (phase_index IS NULL OR phase_index >= 0),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
    skill TEXT NOT NULL CHECK (skill IN ('writing','speaking','reading','listening','vocabulary','grammar','mock','general')),
    task_type TEXT NOT NULL CHECK (task_type IN ('writing_task1','writing_task2','speaking_part1','speaking_part2','speaking_part3','vocab_set','grammar_lesson','mock_section','full_mock','video','article','practice_test','review')),
    content_payload JSONB,
    resource_id UUID REFERENCES public.resources(id) ON DELETE SET NULL,
    duration_minutes SMALLINT NOT NULL CHECK (duration_minutes BETWEEN 1 AND 240),
    scheduled_date DATE,
    priority SMALLINT NOT NULL DEFAULT 1 CHECK (priority BETWEEN 1 AND 5),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','missed','rescheduled','skipped')),
    is_mandatory BOOLEAN NOT NULL DEFAULT false,
    due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    order_index SMALLINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. task_resources (N:M join)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.task_resources (
    task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'supplementary' CHECK (relation IN ('primary','required','supplementary')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (task_id, resource_id)
);

-- ============================================================
-- 6. progress
-- ============================================================
CREATE TABLE IF NOT EXISTS public.progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('diagnostic','assessment','mock_test')),
    source_id UUID,
    criterion TEXT NOT NULL CHECK (criterion IN ('task_response','coherence_cohesion','lexical_resource','grammar','fluency_coherence','pronunciation','listening','reading','overall')),
    band_score NUMERIC(2,1) NOT NULL CHECK ((band_score * 2)::int = (band_score * 2)),
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 7. achievements (catalog) + user_achievements (earned)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    description TEXT,
    category TEXT NOT NULL DEFAULT 'general' CHECK (category IN ('streak','tasks','assessments','band','general')),
    icon TEXT,
    points SMALLINT NOT NULL DEFAULT 10 CHECK (points >= 0),
    criteria JSONB DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.user_achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    achievement_id UUID NOT NULL REFERENCES public.achievements(id) ON DELETE CASCADE,
    earned_at TIMESTAMPTZ DEFAULT NOW(),
    meta JSONB DEFAULT '{}',
    UNIQUE (user_id, achievement_id)
);

-- ============================================================
-- 8. notifications
-- ============================================================
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('ai_feedback','reminder','system','gamification','streak')),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
    body TEXT,
    is_read BOOLEAN NOT NULL DEFAULT false,
    read_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_study_plans_user_status ON public.study_plans(user_id, status);
CREATE INDEX IF NOT EXISTS idx_daily_plans_user_date ON public.daily_plans(user_id, plan_date);
CREATE INDEX IF NOT EXISTS idx_daily_plans_status ON public.daily_plans(status);
CREATE INDEX IF NOT EXISTS idx_tasks_user_date ON public.tasks(user_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_tasks_daily_plan ON public.tasks(daily_plan_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON public.tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_plan_phase ON public.tasks(study_plan_id, phase_index);
CREATE INDEX IF NOT EXISTS idx_tasks_user_pending ON public.tasks(user_id) WHERE status IN ('pending','rescheduled');
CREATE INDEX IF NOT EXISTS idx_resources_type_skill ON public.resources(type, skill);
CREATE INDEX IF NOT EXISTS idx_resources_published ON public.resources(is_published) WHERE is_published = true;
CREATE INDEX IF NOT EXISTS idx_resources_tags ON public.resources USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_task_resources_resource ON public.task_resources(resource_id);
CREATE INDEX IF NOT EXISTS idx_progress_user_criterion_date ON public.progress(user_id, criterion, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_progress_source ON public.progress(source_id);
CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON public.user_achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON public.notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON public.notifications(user_id) WHERE is_read = false;

-- ============================================================
-- updated_at triggers
-- ============================================================
DROP TRIGGER IF EXISTS update_study_plans_updated_at ON public.study_plans;
CREATE TRIGGER update_study_plans_updated_at BEFORE UPDATE ON public.study_plans
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_daily_plans_updated_at ON public.daily_plans;
CREATE TRIGGER update_daily_plans_updated_at BEFORE UPDATE ON public.daily_plans
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_tasks_updated_at ON public.tasks;
CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON public.tasks
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_resources_updated_at ON public.resources;
CREATE TRIGGER update_resources_updated_at BEFORE UPDATE ON public.resources
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_achievements_updated_at ON public.achievements;
CREATE TRIGGER update_achievements_updated_at BEFORE UPDATE ON public.achievements
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_notifications_updated_at ON public.notifications;
CREATE TRIGGER update_notifications_updated_at BEFORE UPDATE ON public.notifications
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.study_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.achievements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_achievements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
-- resources is a public catalog => RLS stays DISABLED (readable by anon)

-- study_plans
DROP POLICY IF EXISTS "Users can view own study plans" ON public.study_plans;
CREATE POLICY "Users can view own study plans" ON public.study_plans FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own study plans" ON public.study_plans;
CREATE POLICY "Users can insert own study plans" ON public.study_plans FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own study plans" ON public.study_plans;
CREATE POLICY "Users can update own study plans" ON public.study_plans FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own study plans" ON public.study_plans;
CREATE POLICY "Users can delete own study plans" ON public.study_plans FOR DELETE USING (auth.uid() = user_id);

-- daily_plans
DROP POLICY IF EXISTS "Users can view own daily plans" ON public.daily_plans;
CREATE POLICY "Users can view own daily plans" ON public.daily_plans FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own daily plans" ON public.daily_plans;
CREATE POLICY "Users can insert own daily plans" ON public.daily_plans FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own daily plans" ON public.daily_plans;
CREATE POLICY "Users can update own daily plans" ON public.daily_plans FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own daily plans" ON public.daily_plans;
CREATE POLICY "Users can delete own daily plans" ON public.daily_plans FOR DELETE USING (auth.uid() = user_id);

-- tasks
DROP POLICY IF EXISTS "Users can view own tasks" ON public.tasks;
CREATE POLICY "Users can view own tasks" ON public.tasks FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own tasks" ON public.tasks;
CREATE POLICY "Users can insert own tasks" ON public.tasks FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own tasks" ON public.tasks;
CREATE POLICY "Users can update own tasks" ON public.tasks FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own tasks" ON public.tasks;
CREATE POLICY "Users can delete own tasks" ON public.tasks FOR DELETE USING (auth.uid() = user_id);

-- task_resources (owner via task)
DROP POLICY IF EXISTS "Users can view own task_resources" ON public.task_resources;
CREATE POLICY "Users can view own task_resources" ON public.task_resources FOR SELECT
    USING (task_id IN (SELECT id FROM public.tasks WHERE user_id = auth.uid()));
DROP POLICY IF EXISTS "Users can insert own task_resources" ON public.task_resources;
CREATE POLICY "Users can insert own task_resources" ON public.task_resources FOR INSERT
    WITH CHECK (task_id IN (SELECT id FROM public.tasks WHERE user_id = auth.uid()));
DROP POLICY IF EXISTS "Users can delete own task_resources" ON public.task_resources;
CREATE POLICY "Users can delete own task_resources" ON public.task_resources FOR DELETE
    USING (task_id IN (SELECT id FROM public.tasks WHERE user_id = auth.uid()));

-- progress
DROP POLICY IF EXISTS "Users can view own progress" ON public.progress;
CREATE POLICY "Users can view own progress" ON public.progress FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own progress" ON public.progress;
CREATE POLICY "Users can insert own progress" ON public.progress FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own progress" ON public.progress;
CREATE POLICY "Users can update own progress" ON public.progress FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own progress" ON public.progress;
CREATE POLICY "Users can delete own progress" ON public.progress FOR DELETE USING (auth.uid() = user_id);

-- achievements catalog (readable by everyone; insert/update/delete admin/service-role only)
DROP POLICY IF EXISTS "Anyone can view achievements" ON public.achievements;
CREATE POLICY "Anyone can view achievements" ON public.achievements FOR SELECT USING (true);

-- user_achievements
DROP POLICY IF EXISTS "Users can view own user_achievements" ON public.user_achievements;
CREATE POLICY "Users can view own user_achievements" ON public.user_achievements FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own user_achievements" ON public.user_achievements;
CREATE POLICY "Users can insert own user_achievements" ON public.user_achievements FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own user_achievements" ON public.user_achievements;
CREATE POLICY "Users can delete own user_achievements" ON public.user_achievements FOR DELETE USING (auth.uid() = user_id);

-- notifications
DROP POLICY IF EXISTS "Users can view own notifications" ON public.notifications;
CREATE POLICY "Users can view own notifications" ON public.notifications FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own notifications" ON public.notifications;
CREATE POLICY "Users can insert own notifications" ON public.notifications FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own notifications" ON public.notifications;
CREATE POLICY "Users can update own notifications" ON public.notifications FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own notifications" ON public.notifications;
CREATE POLICY "Users can delete own notifications" ON public.notifications FOR DELETE USING (auth.uid() = user_id);

-- ============================================================
-- Seed achievements catalog
-- ============================================================
INSERT INTO public.achievements (code, title, description, category, icon, points, criteria)
VALUES
    ('first_login', 'First Steps', 'Complete your first day of study', 'general', '🚀', 10, '{"type": "login", "count": 1}'),
    ('streak_3', 'On a Roll', 'Maintain a 3-day study streak', 'streak', '🔥', 20, '{"type": "streak", "count": 3}'),
    ('streak_7', 'Week Warrior', 'Maintain a 7-day study streak', 'streak', '⚡', 50, '{"type": "streak", "count": 7}'),
    ('streak_30', 'Unstoppable', 'Maintain a 30-day study streak', 'streak', '🏆', 200, '{"type": "streak", "count": 30}'),
    ('tasks_10', 'Task Taker', 'Complete 10 study tasks', 'tasks', '✅', 30, '{"type": "tasks", "count": 10}'),
    ('tasks_50', 'Task Master', 'Complete 50 study tasks', 'tasks', '🎯', 100, '{"type": "tasks", "count": 50}'),
    ('tasks_100', 'Century Club', 'Complete 100 study tasks', 'tasks', '💯', 250, '{"type": "tasks", "count": 100}'),
    ('assess_1', 'First Assessment', 'Submit your first writing/speaking assessment', 'assessments', '📝', 15, '{"type": "assessments", "count": 1}'),
    ('assess_10', 'Assessment Addict', 'Submit 10 assessments', 'assessments', '🧠', 100, '{"type": "assessments", "count": 10}'),
    ('band_6', 'Band 6 Achieved', 'Reach an overall band of 6.0', 'band', '🎖️', 150, '{"type": "band", "value": 6.0}'),
    ('band_7', 'Band 7 Achieved', 'Reach an overall band of 7.0', 'band', '🥇', 300, '{"type": "band", "value": 7.0}'),
    ('band_8', 'Band 8 Achieved', 'Reach an overall band of 8.0', 'band', '👑', 500, '{"type": "band", "value": 8.0}')
ON CONFLICT (code) DO NOTHING;

