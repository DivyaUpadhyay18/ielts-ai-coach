-- IELTS AI Coach - Schedule History (v11)
-- Run this in your Supabase SQL editor after 009_adaptive_scheduler.sql
--
-- Adds comprehensive schedule history tracking:
--   - schedule_history: Complete audit trail of schedule changes
--   - Tracks previous/new schedules, reasons, timestamps, user actions
--   - Enables comparison between different schedule versions

-- ============================================================
-- 1. schedule_history table
-- ============================================================
CREATE TABLE IF NOT EXISTS public.schedule_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    study_plan_id UUID REFERENCES public.study_plans(id) ON DELETE CASCADE,
    run_id UUID REFERENCES public.schedule_runs(id) ON DELETE SET NULL,
    
    -- Schedule snapshots (JSONB for flexibility)
    previous_schedule JSONB NOT NULL DEFAULT '{}',
    new_schedule JSONB NOT NULL DEFAULT '{}',
    
    -- Change metadata
    change_reason TEXT NOT NULL,
    change_type TEXT NOT NULL DEFAULT 'scheduler_run' CHECK (
        change_type IN (
            'scheduler_run',
            'exam_date_update',
            'manual_reschedule',
            'study_plan_regeneration',
            'task_modification',
            'user_override'
        )
    ),
    
    -- Trigger information
    trigger_type TEXT CHECK (trigger_type IN ('midnight','app_open','manual','system','user')),
    
    -- User action tracking
    user_action TEXT CHECK (user_action IN ('accepted','rejected','modified','pending','auto_applied')),
    user_action_at TIMESTAMPTZ,
    user_action_notes TEXT,
    
    -- Metrics snapshot
    metrics_before JSONB DEFAULT '{}',
    metrics_after JSONB DEFAULT '{}',
    
    -- Summary and metadata
    summary TEXT,
    adjustments_count INTEGER DEFAULT 0,
    tasks_affected INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. Indexes for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_schedule_history_user_date 
    ON public.schedule_history(user_id, created_at DESC);
    
CREATE INDEX IF NOT EXISTS idx_schedule_history_user_plan 
    ON public.schedule_history(user_id, study_plan_id);
    
CREATE INDEX IF NOT EXISTS idx_schedule_history_run 
    ON public.schedule_history(run_id) WHERE run_id IS NOT NULL;
    
CREATE INDEX IF NOT EXISTS idx_schedule_history_change_type 
    ON public.schedule_history(change_type);
    
CREATE INDEX IF NOT EXISTS idx_schedule_history_user_action 
    ON public.schedule_history(user_action);

-- ============================================================
-- 3. updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_schedule_history_updated_at ON public.schedule_history;
CREATE TRIGGER update_schedule_history_updated_at BEFORE UPDATE ON public.schedule_history
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 4. Row Level Security
-- ============================================================
ALTER TABLE public.schedule_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own schedule history" ON public.schedule_history;
CREATE POLICY "Users can view own schedule history" 
    ON public.schedule_history FOR SELECT 
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own schedule history" ON public.schedule_history;
CREATE POLICY "Users can insert own schedule history" 
    ON public.schedule_history FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own schedule history" ON public.schedule_history;
CREATE POLICY "Users can update own schedule history" 
    ON public.schedule_history FOR UPDATE 
    USING (auth.uid() = user_id);

-- ============================================================
-- 5. Helper function to get comparison data
-- ============================================================
CREATE OR REPLACE FUNCTION public.get_schedule_comparison(
    p_user_id UUID,
    p_history_id_1 UUID,
    p_history_id_2 UUID
)
RETURNS TABLE (
    history_1_id UUID,
    history_2_id UUID,
    history_1_date TIMESTAMPTZ,
    history_2_date TIMESTAMPTZ,
    history_1_change_type TEXT,
    history_2_change_type TEXT,
    tasks_added INTEGER,
    tasks_removed INTEGER,
    tasks_rescheduled INTEGER,
    workload_change_minutes INTEGER,
    completion_rate_change FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        h1.id as history_1_id,
        h2.id as history_2_id,
        h1.created_at as history_1_date,
        h2.created_at as history_2_date,
        h1.change_type as history_1_change_type,
        h2.change_type as history_2_change_type,
        -- Calculate differences
        COALESCE(jsonb_array_length(h2.new_schedule->'tasks') - jsonb_array_length(h1.new_schedule->'tasks'), 0) as tasks_added,
        COALESCE(jsonb_array_length(h1.new_schedule->'tasks') - jsonb_array_length(h2.new_schedule->'tasks'), 0) as tasks_removed,
        COALESCE(
            (SELECT COUNT(*) FROM jsonb_array_elements(h2.new_schedule->'tasks') t2
             WHERE EXISTS (
                 SELECT 1 FROM jsonb_array_elements(h1.new_schedule->'tasks') t1
                 WHERE t1->>'id' = t2->>'id' 
                 AND t1->>'scheduled_date' != t2->>'scheduled_date'
             )),
            0
        ) as tasks_rescheduled,
        COALESCE(
            (h2.metrics_after->>'new_workload_minutes')::INTEGER - 
            (h1.metrics_after->>'new_workload_minutes')::INTEGER,
            0
        ) as workload_change_minutes,
        COALESCE(
            (h2.metrics_after->>'completion_rate')::FLOAT - 
            (h1.metrics_after->>'completion_rate')::FLOAT,
            0.0
        ) as completion_rate_change
    FROM public.schedule_history h1
    JOIN public.schedule_history h2 ON h2.user_id = p_user_id
    WHERE h1.id = p_history_id_1 
      AND h2.id = p_history_id_2
      AND h1.user_id = p_user_id
      AND h2.user_id = p_user_id;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- 6. Grant permissions
-- ============================================================
GRANT ALL ON public.schedule_history TO authenticated;
GRANT ALL ON public.schedule_history TO service_role;
GRANT EXECUTE ON FUNCTION public.get_schedule_comparison TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_schedule_comparison TO service_role;