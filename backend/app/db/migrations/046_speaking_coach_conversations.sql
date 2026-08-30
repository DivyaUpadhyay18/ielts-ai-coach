-- IELTS AI Coach — Speaking Interactive Coach (v046)
--
-- After evaluation, users can ask the AI Speaking Coach questions like:
--   "Why did I get 6.5?"
--   "How can I improve fluency?"
--   "Was this answer too short?"
--   "How could I answer this Part 2 question?"
--   "What vocabulary should I use?"
--   "Why was my grammar score low?"
--
-- The coach uses the actual question, transcript, evaluation, previous
-- attempts, target band, and current weaknesses. All conversation history
-- is stored. Integrated with the AI Mentor.

CREATE TABLE IF NOT EXISTS public.speaking_coach_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- The practice session or test response this conversation is about.
    context_type TEXT NOT NULL CHECK (context_type IN ('practice_session', 'test_response', 'reattempt')),
    context_id UUID NOT NULL,

    -- The practice mode or test part.
    practice_mode TEXT,
    part TEXT,

    -- Target band (from user profile / study plan).
    target_band NUMERIC(3,1),

    -- Current weaknesses (from evaluation / error analysis).
    current_weaknesses JSONB DEFAULT '[]'::jsonb,

    -- The conversation messages (user + assistant turns).
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Summary of the conversation for quick retrieval.
    summary TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spp_coach_user
    ON public.speaking_coach_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_spp_coach_context
    ON public.speaking_coach_conversations(context_type, context_id);
CREATE INDEX IF NOT EXISTS idx_spp_coach_created
    ON public.speaking_coach_conversations(created_at DESC);

-- updated_at trigger
DROP TRIGGER IF EXISTS update_speaking_coach_conversations_updated_at
    ON public.speaking_coach_conversations;
CREATE TRIGGER update_speaking_coach_conversations_updated_at
    BEFORE UPDATE ON public.speaking_coach_conversations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Row Level Security
ALTER TABLE public.speaking_coach_conversations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own speaking coach conversations"
    ON public.speaking_coach_conversations;
CREATE POLICY "Users can view own speaking coach conversations"
    ON public.speaking_coach_conversations FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own speaking coach conversations"
    ON public.speaking_coach_conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own speaking coach conversations"
    ON public.speaking_coach_conversations FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own speaking coach conversations"
    ON public.speaking_coach_conversations FOR DELETE
    USING (auth.uid() = user_id);

GRANT ALL ON public.speaking_coach_conversations TO authenticated;
