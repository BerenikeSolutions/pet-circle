-- Migration 021: Revert Kennel Cough (Nobivac KC) and Canine Coronavirus (CCoV)
--               back to optional (category = 'complete') for dogs.
--
-- Business rule change: These vaccines are NOT universally required for all dogs.
-- They are situationally recommended (boarding, parks, high-exposure environments)
-- and should be treated as optional, not mandatory.
--
-- Safe to re-run: UPDATE is idempotent.

BEGIN;

UPDATE preventive_master
SET    category = 'complete'
WHERE  species   = 'dog'
  AND  item_name IN ('Kennel Cough (Nobivac KC)', 'Canine Coronavirus (CCoV)');

COMMIT;
