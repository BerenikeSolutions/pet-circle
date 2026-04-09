-- Migration 046: Add is_mandatory column to preventive_master
-- Distinguishes mandatory preventive items (always shown on dashboard)
-- from optional items (only shown when a last_done_date record exists).
--
-- Mandatory: Rabies Vaccine, DHPPi, Feline Core, Deworming, Tick/Flea
-- Optional (not set): Kennel Cough (Nobivac KC), Canine Coronavirus (CCoV)

ALTER TABLE preventive_master
    ADD COLUMN IF NOT EXISTS is_mandatory boolean NOT NULL DEFAULT false;

UPDATE preventive_master
SET is_mandatory = true
WHERE item_name IN ('Rabies Vaccine', 'DHPPi', 'Feline Core', 'Deworming', 'Tick/Flea');
