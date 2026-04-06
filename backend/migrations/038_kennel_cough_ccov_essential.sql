-- Migration 038: Revert Kennel Cough (Nobivac KC) and Canine Coronavirus (CCoV)
--               back to essential (mandatory) for dogs.
--
-- Business rule change: These vaccines should always be visible on the
-- dashboard alongside Rabies and DHPPi, not hidden as optional.
--
-- Reverses migration 021 which set them to 'complete' (optional).
-- Safe to re-run: UPDATE is idempotent.

BEGIN;

UPDATE preventive_master
SET    category = 'essential'
WHERE  species   = 'dog'
  AND  item_name IN ('Kennel Cough (Nobivac KC)', 'Canine Coronavirus (CCoV)');

COMMIT;
