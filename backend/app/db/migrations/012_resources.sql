-- IELTS AI Coach - Resource Management System (v12)
-- Run this in your Supabase SQL editor after 011_schedule_history.sql
--
-- Creates the resources table for the Resource Management System:
--   - Full resource catalog with type, skill, subSkill, band range
--   - Verified/official/free flags, ratings, popularity
--   - CRUD support with RLS
--   - Performance indexes

-- ============================================================
-- 1. resources table
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL CHECK (
        type IN (
            'Video',
            'PDF',
            'Website',
            'Quiz',
            'Flashcard'
        )
    ),
    source TEXT,
    author TEXT,
    url TEXT,
    thumbnail TEXT,
    skill TEXT NOT NULL CHECK (
        skill IN (
            'Reading',
            'Listening',
            'Writing',
            'Speaking',
            'Vocabulary',
            'Grammar'
        )
    ),
    sub_skill TEXT,
    minimum_band REAL CHECK (minimum_band >= 0.0 AND minimum_band <= 9.0),
    maximum_band REAL CHECK (maximum_band >= 0.0 AND maximum_band <= 9.0),
    difficulty TEXT CHECK (
        difficulty IN ('beginner', 'intermediate', 'advanced', 'all_levels')
    ),
    estimated_time INTEGER CHECK (estimated_time >= 0),
    tags TEXT[] DEFAULT '{}',
    language TEXT DEFAULT 'en',
    verified BOOLEAN DEFAULT FALSE,
    official BOOLEAN DEFAULT FALSE,
    is_free BOOLEAN DEFAULT TRUE,
    rating REAL CHECK (rating >= 0.0 AND rating <= 5.0),
    popularity_score INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. Indexes for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_resources_skill ON public.resources(skill);
CREATE INDEX IF NOT EXISTS idx_resources_type ON public.resources(type);
CREATE INDEX IF NOT EXISTS idx_resources_difficulty ON public.resources(difficulty);
CREATE INDEX IF NOT EXISTS idx_resources_skill_type ON public.resources(skill, type);
CREATE INDEX IF NOT EXISTS idx_resources_band_range ON public.resources(minimum_band, maximum_band);
CREATE INDEX IF NOT EXISTS idx_resources_popularity ON public.resources(popularity_score DESC);
CREATE INDEX IF NOT EXISTS idx_resources_rating ON public.resources(rating DESC);
CREATE INDEX IF NOT EXISTS idx_resources_verified ON public.resources(verified);
CREATE INDEX IF NOT EXISTS idx_resources_official ON public.resources(official);
CREATE INDEX IF NOT EXISTS idx_resources_is_free ON public.resources(is_free);
CREATE INDEX IF NOT EXISTS idx_resources_language ON public.resources(language);
CREATE INDEX IF NOT EXISTS idx_resources_created_at ON public.resources(created_at DESC);

-- ============================================================
-- 3. updated_at trigger
-- ============================================================
DROP TRIGGER IF EXISTS update_resources_updated_at ON public.resources;
CREATE TRIGGER update_resources_updated_at BEFORE UPDATE ON public.resources
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 4. Row Level Security
-- ============================================================
ALTER TABLE public.resources ENABLE ROW LEVEL SECURITY;

-- Public read access for all resources
DROP POLICY IF EXISTS "Anyone can view resources" ON public.resources;
CREATE POLICY "Anyone can view resources"
    ON public.resources FOR SELECT
    USING (true);

-- Authenticated users can insert resources (admin in production)
DROP POLICY IF EXISTS "Authenticated users can insert resources" ON public.resources;
CREATE POLICY "Authenticated users can insert resources"
    ON public.resources FOR INSERT
    WITH CHECK (auth.uid() IS NOT NULL);

-- Authenticated users can update resources (admin in production)
DROP POLICY IF EXISTS "Authenticated users can update resources" ON public.resources;
CREATE POLICY "Authenticated users can update resources"
    ON public.resources FOR UPDATE
    USING (auth.uid() IS NOT NULL);

-- Authenticated users can delete resources (admin in production)
DROP POLICY IF EXISTS "Authenticated users can delete resources" ON public.resources;
CREATE POLICY "Authenticated users can delete resources"
    ON public.resources FOR DELETE
    USING (auth.uid() IS NOT NULL);

-- ============================================================
-- 5. Grant permissions
-- ============================================================
GRANT ALL ON public.resources TO authenticated;
GRANT ALL ON public.resources TO service_role;

-- ============================================================
-- 6. Helper function: search resources with filters
-- ============================================================
CREATE OR REPLACE FUNCTION public.search_resources(
    p_skill TEXT DEFAULT NULL,
    p_type TEXT DEFAULT NULL,
    p_difficulty TEXT DEFAULT NULL,
    p_min_band REAL DEFAULT NULL,
    p_max_band REAL DEFAULT NULL,
    p_is_free BOOLEAN DEFAULT NULL,
    p_verified BOOLEAN DEFAULT NULL,
    p_official BOOLEAN DEFAULT NULL,
    p_search TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 20,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    description TEXT,
    type TEXT,
    source TEXT,
    author TEXT,
    url TEXT,
    thumbnail TEXT,
    skill TEXT,
    sub_skill TEXT,
    minimum_band REAL,
    maximum_band REAL,
    difficulty TEXT,
    estimated_time INTEGER,
    tags TEXT[],
    language TEXT,
    verified BOOLEAN,
    official BOOLEAN,
    is_free BOOLEAN,
    rating REAL,
    popularity_score INTEGER,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT r.*
    FROM public.resources r
    WHERE
        (p_skill IS NULL OR r.skill = p_skill)
        AND (p_type IS NULL OR r.type = p_type)
        AND (p_difficulty IS NULL OR r.difficulty = p_difficulty)
        AND (p_min_band IS NULL OR r.minimum_band >= p_min_band)
        AND (p_max_band IS NULL OR r.maximum_band <= p_max_band)
        AND (p_is_free IS NULL OR r.is_free = p_is_free)
        AND (p_verified IS NULL OR r.verified = p_verified)
        AND (p_official IS NULL OR r.official = p_official)
        AND (p_search IS NULL OR r.title ILIKE '%' || p_search || '%' OR r.description ILIKE '%' || p_search || '%')
    ORDER BY r.popularity_score DESC, r.rating DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- 7. Helper function: get resource statistics
-- ============================================================
CREATE OR REPLACE FUNCTION public.get_resource_stats()
RETURNS TABLE (
    total_resources BIGINT,
    by_type JSONB,
    by_skill JSONB,
    by_difficulty JSONB,
    avg_rating FLOAT,
    free_count BIGINT,
    verified_count BIGINT,
    official_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_resources,
        jsonb_object_agg(type, type_count) as by_type,
        jsonb_object_agg(skill, skill_count) as by_skill,
        jsonb_object_agg(difficulty, diff_count) as by_difficulty,
        ROUND(AVG(rating)::FLOAT, 2) as avg_rating,
        COUNT(*) FILTER (WHERE is_free)::BIGINT as free_count,
        COUNT(*) FILTER (WHERE verified)::BIGINT as verified_count,
        COUNT(*) FILTER (WHERE official)::BIGINT as official_count
    FROM public.resources;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- 8. Grant permissions for helper functions
-- ============================================================
GRANT EXECUTE ON FUNCTION public.search_resources TO authenticated;
GRANT EXECUTE ON FUNCTION public.search_resources TO service_role;
GRANT EXECUTE ON FUNCTION public.get_resource_stats TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_resource_stats TO service_role;