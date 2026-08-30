-- IELTS AI Coach - Admin Resource Dashboard Schema (v15)
-- Run this in your Supabase SQL editor after 014_resource_quality.sql
--
-- Creates tables for:
-- - resource_views (user resource view tracking)
-- - resource_completions (user resource completion tracking)
-- - resource_likes (user resource likes)
-- - resource_ratings (user resource ratings)
-- - resource_suggestions (community resource suggestions)
-- - resource_verification_log (admin verification audit trail)

-- ============================================================
-- 1. resource_views (track which users viewed which resources)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_views (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    viewed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, resource_id, viewed_at)
);

-- ============================================================
-- 2. resource_completions (track which users completed which resources)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_completions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    completed_at TIMESTAMPTZ DEFAULT NOW(),
    completion_percent NUMERIC(5,2) DEFAULT 100.0 CHECK (completion_percent BETWEEN 0 AND 100),
    UNIQUE (user_id, resource_id)
);

-- ============================================================
-- 3. resource_likes (track user likes on resources)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_likes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    liked_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, resource_id)
);

-- ============================================================
-- 4. resource_ratings (track user ratings on resources)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    rating NUMERIC(2,1) NOT NULL CHECK (rating >= 0.0 AND rating <= 5.0),
    review TEXT,
    rated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, resource_id)
);

-- ============================================================
-- 5. resource_suggestions (community-submitted resource suggestions)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
    description TEXT,
    type TEXT NOT NULL CHECK (type IN ('Video','PDF','Website','Quiz','Flashcard')),
    source TEXT,
    author TEXT,
    url TEXT CHECK (url IS NULL OR url ~* '^https?://'),
    thumbnail TEXT CHECK (thumbnail IS NULL OR thumbnail ~* '^https?://'),
    skill TEXT NOT NULL CHECK (skill IN ('Reading','Listening','Writing','Speaking','Vocabulary','Grammar')),
    sub_skill TEXT,
    minimum_band NUMERIC(2,1) CHECK (minimum_band IS NULL OR (minimum_band >= 0.0 AND minimum_band <= 9.0)),
    maximum_band NUMERIC(2,1) CHECK (maximum_band IS NULL OR (maximum_band >= 0.0 AND maximum_band <= 9.0)),
    difficulty TEXT CHECK (difficulty IN ('beginner','intermediate','advanced','all_levels')),
    estimated_time INTEGER CHECK (estimated_time IS NULL OR estimated_time >= 0),
    tags TEXT[] NOT NULL DEFAULT '{}',
    language TEXT NOT NULL DEFAULT 'en',
    is_free BOOLEAN NOT NULL DEFAULT true,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    admin_notes TEXT,
    approved_by UUID REFERENCES public.users(id),
    approved_at TIMESTAMPTZ,
    rejected_by UUID REFERENCES public.users(id),
    rejected_at TIMESTAMPTZ,
    resource_id UUID REFERENCES public.resources(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 6. resource_verification_log (audit trail for verification actions)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resource_verification_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id UUID NOT NULL REFERENCES public.resources(id) ON DELETE CASCADE,
    admin_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('verified','unverified')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_resource_views_user ON public.resource_views(user_id);
CREATE INDEX IF NOT EXISTS idx_resource_views_resource ON public.resource_views(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_views_viewed_at ON public.resource_views(viewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_resource_completions_user ON public.resource_completions(user_id);
CREATE INDEX IF NOT EXISTS idx_resource_completions_resource ON public.resource_completions(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_completions_completed_at ON public.resource_completions(completed_at DESC);

CREATE INDEX IF NOT EXISTS idx_resource_likes_user ON public.resource_likes(user_id);
CREATE INDEX IF NOT EXISTS idx_resource_likes_resource ON public.resource_likes(resource_id);

CREATE INDEX IF NOT EXISTS idx_resource_ratings_user ON public.resource_ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_resource_ratings_resource ON public.resource_ratings(resource_id);

CREATE INDEX IF NOT EXISTS idx_resource_suggestions_status ON public.resource_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_resource_suggestions_user ON public.resource_suggestions(user_id);
CREATE INDEX IF NOT EXISTS idx_resource_suggestions_created_at ON public.resource_suggestions(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_resource_verification_log_resource ON public.resource_verification_log(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_verification_log_admin ON public.resource_verification_log(admin_id);
CREATE INDEX IF NOT EXISTS idx_resource_verification_log_created_at ON public.resource_verification_log(created_at DESC);

-- ============================================================
-- updated_at trigger for resource_suggestions
-- ============================================================
DROP TRIGGER IF EXISTS update_resource_suggestions_updated_at ON public.resource_suggestions;
CREATE TRIGGER update_resource_suggestions_updated_at BEFORE UPDATE ON public.resource_suggestions
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
