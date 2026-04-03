-- Migration 036: Per-pet deferred care-plan marker for deterministic onboarding
--
-- Replaces user-level deferred-link semantics with persistent per-pet markers
-- so concurrent onboarding across multiple pets under one user cannot cross-wire.

BEGIN;

CREATE TABLE IF NOT EXISTS deferred_care_plan_pending (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    reason VARCHAR(64) NOT NULL DEFAULT 'pending_extractions',
    is_cleared BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    cleared_at TIMESTAMP NULL
);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'deferred_care_plan_pending' AND indexname = 'ix_deferred_care_plan_pending_pet'
  ) THEN
    CREATE INDEX ix_deferred_care_plan_pending_pet ON deferred_care_plan_pending (pet_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'deferred_care_plan_pending' AND indexname = 'ix_deferred_care_plan_pending_user'
  ) THEN
    CREATE INDEX ix_deferred_care_plan_pending_user ON deferred_care_plan_pending (user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'deferred_care_plan_pending' AND indexname = 'ix_deferred_care_plan_pending_uncleared'
  ) THEN
    CREATE INDEX ix_deferred_care_plan_pending_uncleared
        ON deferred_care_plan_pending (is_cleared, pet_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND tablename = 'deferred_care_plan_pending'
      AND indexname = 'uq_deferred_care_plan_pending_pet_active'
  ) THEN
    CREATE UNIQUE INDEX uq_deferred_care_plan_pending_pet_active
      ON deferred_care_plan_pending (pet_id)
      WHERE is_cleared = FALSE;
  END IF;
END $$;

-- Backfill active deferred markers from legacy user-level pending flag.
-- We map to each user's most recently created non-deleted pet, which is the
-- same pet selected by onboarding finalization logic during rollout.
INSERT INTO deferred_care_plan_pending (user_id, pet_id, reason, is_cleared, created_at)
SELECT
  u.id,
  p.id,
  'legacy_user_pending',
  FALSE,
  NOW()
FROM users u
JOIN LATERAL (
  SELECT id
  FROM pets
  WHERE pets.user_id = u.id AND pets.is_deleted = FALSE
  ORDER BY pets.created_at DESC
  LIMIT 1
) p ON TRUE
WHERE u.dashboard_link_pending = TRUE
ON CONFLICT DO NOTHING;

COMMIT;
