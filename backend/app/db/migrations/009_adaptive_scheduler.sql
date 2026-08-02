-- IELTS AI Coach - Adaptive Scheduler (v9)
-- Run this in your Supabase SQL editor after 008_study_plan_engine.sql
--
-- Adds the infrastructure required by the deterministic Adaptive Scheduler:
--   - schedule_runs       : one row per rollover run (midnight / app open / manual)
--   - schedule_adjustments: every reschedule/move + reason ("what changed & why")
--   - tasks               : + source_task_id (lineage for carry-forward clones)
--                           + missed_at (when a task transitioned to missed)
--
-- No AI. All scheduling logic is deterministic and stored for auditability.

-- ============================================================
-- 1. Extend tasks with scheduler lineage / audit columns
-- ============================================================
ALTER TABLE public.tasks
    ADD COLUMN IF NOT EXISTS source_task_id UUID REFERENCES public.tasks(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS missed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_tasks_source_task ON public.tasks(source_task_id) WHERE source_task_id IS NOT NULL;

-- ============================================================
-- 2. schedule_runs (one row per scheduler rollover)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.schedule_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    study_plan_id UUID REFERENCES public.study_plans(id) ON DELETE CASCADE,
    trigger_type TEXT NOT NULL DEFAULT 'midnight' CHECK (trigger_type IN ('midnight','app_open','manual')),
    run_date DATE NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}',
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. schedule_adjustments (audit trail of every change)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.schedule_adjustments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES public.schedule_runs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    task_id UUID REFERENCES public.tasks(id) ON DELETE SET NULL,
    task_title TEXT,
    from_date DATE,
    to_date DATE,
    action TEXT NOT NULL DEFAULT 'rescheduled' CHECK (action IN ('rescheduled','carried_forward','deprioritized','spread','merged','kept')),
    reason TEXT NOT NULL,
    priority_delta SMALLINT NOT NULL DEFAULT 0 CHECK (priority_delta BETWEEN -5 AND 5),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_schedule_runs_user_date ON public.schedule_runs(user_id, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_schedule_runs_user ON public.schedule_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_schedule_adjustments_run ON public.schedule_adjustments(run_id);
CREATE INDEX IF NOT EXISTS idx_schedule_adjustments_user ON public.schedule_adjustments(user_id);
CREATE INDEX IF NOT EXISTS idx_schedule_adjustments_task ON public.schedule_adjustments(task_id) WHERE task_id IS NOT NULL;

-- ============================================================
-- updated_at trigger for schedule_runs
-- ============================================================
DROP TRIGGER IF EXISTS update_schedule_runs_updated_at ON public.schedule_runs;
CREATE TRIGGER update_schedule_runs_updated_at BEFORE UPDATE ON public.schedule_runs
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.schedule_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.schedule_adjustments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own schedule runs" ON public.schedule_runs;
CREATE POLICY "Users can view own schedule runs" ON public.schedule_runs FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own schedule runs" ON public.schedule_runs;
CREATE POLICY "Users can insert own schedule runs" ON public.schedule_runs FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own schedule runs" ON public.schedule_runs;
CREATE POLICY "Users can update own schedule runs" ON public.schedule_runs FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own schedule runs" ON public.schedule_runs;
CREATE POLICY "Users can delete own schedule runs" ON public.schedule_runs FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own schedule adjustments" ON public.schedule_adjustments;
CREATE POLICY "Users can view own schedule adjustments" ON public.schedule_adjustments FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert own schedule adjustments" ON public.schedule_adjustments;
CREATE POLICY "Users can insert own schedule adjustments" ON public.schedule_adjustments FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can update own schedule adjustments" ON public.schedule_adjustments;
CREATE POLICY "Users can update own schedule adjustments" ON public.schedule_adjustments FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete own schedule adjustments" ON public.schedule_adjustments;
CREATE POLICY "Users can delete own schedule adjustments" ON public.schedule_adjustments FOR DELETE USING (auth.uid() = user_id);

