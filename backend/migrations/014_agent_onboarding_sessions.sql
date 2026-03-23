-- Migration 014: Create agent_onboarding_sessions table
--
-- Stores the LLM conversation history and structured extraction snapshot
-- for each user going through the agentic onboarding flow.
--
-- One row per user; the partial unique index enforces only one active
-- (is_complete=FALSE) session per user at a time.
--
-- Safe to re-run: uses IF NOT EXISTS throughout.

BEGIN;

CREATE TABLE IF NOT EXISTS agent_onboarding_sessions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The user this session belongs to.
    -- ON DELETE CASCADE ensures cleanup when a user is deleted.
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- OpenAI message array: [{"role": "system"|"user"|"assistant"|"tool", "content": "..."}]
    -- Appended on every webhook turn; read in full on every incoming message.
    messages       JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Structured snapshot of what the agent has confirmed so far.
    -- Written by tool calls; flushed to DB rows by _finalize_agentic_onboarding().
    -- Schema: { user: {full_name, pincode}, pet: {name, species, breed, ...},
    --           diet: {packaged: [], homemade: [], supplements: []},
    --           grooming: [{name, freq, unit}] }
    collected_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Set TRUE when complete_onboarding tool fires successfully.
    -- Prevents re-entry into the agentic loop after finalization.
    is_complete    BOOLEAN NOT NULL DEFAULT FALSE,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Only one active session per user at a time.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'agent_onboarding_sessions'
      AND indexname = 'uq_agent_session_user'
  ) THEN
    CREATE UNIQUE INDEX uq_agent_session_user
        ON agent_onboarding_sessions (user_id)
        WHERE is_complete = FALSE;
  END IF;
END $$;

-- Fast lookup by user_id (only query pattern needed).
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'agent_onboarding_sessions'
      AND indexname = 'idx_agent_session_user_id'
  ) THEN
    CREATE INDEX idx_agent_session_user_id
        ON agent_onboarding_sessions (user_id);
  END IF;
END $$;

COMMIT;
