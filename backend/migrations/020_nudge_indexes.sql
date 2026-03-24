-- Migration 020: Indexes for nudge engine pet-level queries
-- Migration 005 only indexed nudge_delivery_log, not the nudges table itself.
-- The nudge engine queries nudges by (pet_id, dismissed) and (pet_id, created_at)
-- on every dashboard open, making these two indexes critical for performance.

CREATE INDEX IF NOT EXISTS idx_nudges_pet_dismissed
    ON nudges(pet_id, dismissed);

CREATE INDEX IF NOT EXISTS idx_nudges_pet_created
    ON nudges(pet_id, created_at DESC);
