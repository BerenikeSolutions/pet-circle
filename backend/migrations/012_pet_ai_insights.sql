-- Migration 012: Create pet_ai_insights table for GPT-generated health summaries and vet questions
--
-- Stores AI-generated insights per pet, cached for 7 days.
-- insight_type: 'vet_questions' | 'health_summary'
-- content_json: JSONB payload (structure depends on insight_type)
--
-- Safe to re-run: CREATE TABLE IF NOT EXISTS + DO $$ idiom for index.

BEGIN;

CREATE TABLE IF NOT EXISTS pet_ai_insights (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id         UUID        NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    insight_type   VARCHAR(50) NOT NULL,
    content_json   JSONB       NOT NULL,
    generated_at   TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pet_ai_insight UNIQUE (pet_id, insight_type)
);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'pet_ai_insights' AND indexname = 'ix_pet_ai_insights_pet_id'
  ) THEN
    CREATE INDEX ix_pet_ai_insights_pet_id ON pet_ai_insights (pet_id);
  END IF;
END $$;

COMMIT;
