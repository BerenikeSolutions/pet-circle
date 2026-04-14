-- Migration 055: Drop essential_care column from pet_life_stage_traits
--
-- essential_care was removed from the life stage service in favour of
-- the new insights-only contract ({text, color} on the traits column).
-- The column is no longer written and its NOT NULL constraint blocks inserts.

BEGIN;

ALTER TABLE pet_life_stage_traits
    DROP COLUMN IF EXISTS essential_care;

COMMIT;
