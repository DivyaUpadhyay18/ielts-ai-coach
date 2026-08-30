-- IELTS AI Coach - Resource Notes & Highlights (v12)
-- Run this in your Supabase SQL editor after 011_schedule_history.sql
--
-- Creates tables for user notes, highlights, and revision reminders
-- on resources from the public catalog.

-- ============================================================
-- 1. resource_notes
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    color TEXT DEFAULT 'yellow',
    is_highlighted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. resource_highlights
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_highlights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    selected_text TEXT NOT NULL,
    color TEXT DEFAULT 'yellow',
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. revision_reminders
-- ============================================================
CREATE TABLE IF NOT EXISTS public.revision_reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    note_id UUID REFERENCES public.resource_notes(id) ON DELETE CASCADE,
    reminder_date DATE NOT NULL,
    reminder_time TIME,
    title TEXT NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_resource_notes_user ON public.resource_notes(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resource_notes_resource ON public.resource_notes(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_highlights_user ON public.resource_highlights(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resource_highlights_resource ON public.resource_highlights(resource_id);
CREATE INDEX IF NOT EXISTS idx_revision_reminders_user ON public.revision_reminders(user_id, reminder_date);
CREATE INDEX IF NOT EXISTS idx_revision_reminders_resource ON public.revision_reminders(resource_id);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.resource_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resource_highlights ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.revision_reminders ENABLE ROW LEVEL SECURITY;

-- resource_notes policies
DROP POLICY IF EXISTS "Users can view own notes" ON public.resource_notes;
CREATE POLICY "Users can view own notes" ON public.resource_notes FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own notes" ON public.resource_notes;
CREATE POLICY "Users can insert own notes" ON public.resource_notes FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own notes" ON public.resource_notes;
CREATE POLICY "Users can update own notes" ON public.resource_notes FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own notes" ON public.resource_notes;
CREATE POLICY "Users can delete own notes" ON public.resource_notes FOR DELETE USING (auth.uid() = user_id);

-- resource_highlights policies
DROP POLICY IF EXISTS "Users can view own highlights" ON public.resource_highlights;
CREATE POLICY "Users can view own highlights" ON public.resource_highlights FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own highlights" ON public.resource_highlights;
CREATE POLICY "Users can insert own highlights" ON public.resource_highlights FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own highlights" ON public.resource_highlights;
CREATE POLICY "Users can delete own highlights" ON public.resource_highlights FOR DELETE USING (auth.uid() = user_id);

-- revision_reminders policies
DROP POLICY IF EXISTS "Users can view own reminders" ON public.revision_reminders;
CREATE POLICY "Users can view own reminders" ON public.revision_reminders FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own reminders" ON public.revision_reminders;
CREATE POLICY "Users can insert own reminders" ON public.revision_reminders FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own reminders" ON public.revision_reminders;
CREATE POLICY "Users can update own reminders" ON public.revision_reminders FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own reminders" ON public.revision_reminders;
CREATE POLICY "Users can delete own reminders" ON public.revision_reminders FOR DELETE USING (auth.uid() = user_id);