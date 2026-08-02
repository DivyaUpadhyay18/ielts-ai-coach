-- IELTS AI Coach - Study Plan Generation Engine (v8)
-- Run this in your Supabase SQL editor after 007_streaks.sql
--
-- Extends the canonical study_plans / daily_plans / tasks tables with the
-- columns required by the deterministic Study Plan Generation Engine:
--   - tasks:       xp_reward, difficulty (1-5 ramp), week_index
--   - daily_plans: phase_index, is_revision_day, is_mock_day, xp_reward
--
-- No AI. All generation is deterministic placeholder logic.

-- ============================================================
-- 1. Extend tasks with XP / difficulty / week fields
-- ============================================================
ALTER TABLE public.tasks
    ADD COLUMN IF NOT EXISTS xp_reward SMALLINT NOT NULL DEFAULT 10 CHECK (xp_reward >= 0),
    ADD COLUMN IF NOT EXISTS difficulty SMALLINT NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5),
    ADD COLUMN IF NOT EXISTS week_index SMALLINT CHECK (week_index IS NULL OR week_index >= 0);

-- ============================================================
-- 2. Extend daily_plans with phase / day-type / XP fields
-- ============================================================
ALTER TABLE public.daily_plans
    ADD COLUMN IF NOT EXISTS phase_index SMALLINT CHECK (phase_index IS NULL OR phase_index >= 0),
    ADD COLUMN IF NOT EXISTS is_revision_day BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS is_mock_day BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS xp_reward SMALLINT NOT NULL DEFAULT 0 CHECK (xp_reward >= 0);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_tasks_plan_date ON public.tasks(study_plan_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_daily_plans_plan_date ON public.daily_plans(study_plan_id, plan_date);
CREATE INDEX IF NOT EXISTS idx_tasks_week ON public.tasks(study_plan_id, week_index);

