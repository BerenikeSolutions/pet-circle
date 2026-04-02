-- Migration 035: Create pet_life_stage_traits cache table for life-stage GPT traits
--
-- Stores one cached traits payload per (pet, life_stage).

BEGIN;

CREATE TABLE IF NOT EXISTS pet_life_stage_traits (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id         UUID        NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    life_stage     VARCHAR(20) NOT NULL,
    breed_size     VARCHAR(20) NOT NULL,
    traits         JSONB       NOT NULL,
    essential_care JSONB       NOT NULL,
    generated_at   TIMESTAMP   NOT NULL,
    created_at     TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pet_life_stage_trait_pet_stage UNIQUE (pet_id, life_stage)
);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'pet_life_stage_traits' AND indexname = 'ix_pet_life_stage_traits_pet_id'
  ) THEN
    CREATE INDEX ix_pet_life_stage_traits_pet_id ON pet_life_stage_traits (pet_id);
  END IF;
END $$;

COMMIT;