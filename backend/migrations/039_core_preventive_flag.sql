-- Migration 039: Add is_core flag to preventive_master
--
-- Marks the default preventive items that every pet of a given species
-- should have tracked.  The recognition bullet on the dashboard counts
-- how many of these core items have last_done_date filled.
--
-- Dogs (6): Rabies Vaccine, DHPPi, Deworming, Tick/Flea,
--           Kennel Cough (Nobivac KC), Canine Coronavirus (CCoV)
-- Cats (4): Rabies Vaccine, Feline Core, Deworming, Tick/Flea
--
-- Safe to re-run: column ADD uses IF NOT EXISTS, UPDATEs are idempotent.

BEGIN;

-- 1. Add the column (default FALSE so existing rows are unaffected)
ALTER TABLE preventive_master
    ADD COLUMN IF NOT EXISTS is_core BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Mark core items for dogs
UPDATE preventive_master
SET    is_core = TRUE
WHERE  species = 'dog'
  AND  item_name IN (
         'Rabies Vaccine',
         'DHPPi',
         'Deworming',
         'Tick/Flea',
         'Kennel Cough (Nobivac KC)',
         'Canine Coronavirus (CCoV)'
       );

-- 3. Mark core items for cats
UPDATE preventive_master
SET    is_core = TRUE
WHERE  species = 'cat'
  AND  item_name IN (
         'Rabies Vaccine',
         'Feline Core',
         'Deworming',
         'Tick/Flea'
       );

COMMIT;
