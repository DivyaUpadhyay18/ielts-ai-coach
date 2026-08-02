-- IELTS AI Coach - Resource Bookmarks (v4)
-- Run this in your Supabase SQL editor after 003_core_domains.sql
--
-- Creates the resource_bookmarks table for users to save/bookmark
-- resources from the public catalog.

-- ============================================================
-- 1. resource_bookmarks
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, resource_id)
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_resource_bookmarks_user ON public.resource_bookmarks(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resource_bookmarks_resource ON public.resource_bookmarks(resource_id);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.resource_bookmarks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own bookmarks" ON public.resource_bookmarks;
CREATE POLICY "Users can view own bookmarks" ON public.resource_bookmarks FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own bookmarks" ON public.resource_bookmarks;
CREATE POLICY "Users can insert own bookmarks" ON public.resource_bookmarks FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own bookmarks" ON public.resource_bookmarks;
CREATE POLICY "Users can delete own bookmarks" ON public.resource_bookmarks FOR DELETE USING (auth.uid() = user_id);