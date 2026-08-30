-- IELTS AI Coach — AI Mentor missed-day coaching mode (v27)
-- Run this in your Supabase SQL editor after 026_ai_mentor.sql
--
-- Adds 'missed_day' to the allowed values of mentor_conversations.mode.
-- 'missed_day' is the coaching flow invoked when a student returns after
-- missing one or more study days (see
-- backend/app/services/ai_mentor_service.py -> _template_missed_day).
--
-- PostgreSQL auto-names an inline column CHECK as "<table>_<column>_check",
-- so we drop that constraint by its default name and re-add a named one that
-- includes the new mode. IF EXISTS makes this idempotent across every branch.
ALTER TABLE public.mentor_conversations
    DROP CONSTRAINT IF EXISTS mentor_conversations_mode_check;

ALTER TABLE public.mentor_conversations
    ADD CONSTRAINT mentor_conversations_mode_check
    CHECK (mode IN (
        'daily_coaching',
        'roadmap_analysis',
        'risk_check',
        'ask_mentor',
        'general',
        'missed_day'
    ));

COMMENT ON COLUMN public.mentor_conversations.mode IS
    'Coaching session mode; missed_day = recovery briefing after missed days';
