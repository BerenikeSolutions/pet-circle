-- Migration 011: Mark Kennel Cough and Canine Coronavirus as mandatory (essential) for dogs
--
-- Business rule: Kennel Cough (Nobivac KC) and Canine Coronavirus (CCoV)
-- are recommended for ALL dogs and puppies in India and should be displayed
-- as mandatory vaccines, not optional.
--
-- Safe to re-run: UPDATE is idempotent.

BEGIN;

UPDATE preventive_master
SET    category = 'essential'
WHERE  species   = 'dog'
  AND  item_name IN ('Kennel Cough (Nobivac KC)', 'Canine Coronavirus (CCoV)');

COMMIT;
