-- Migration 010: Dog vaccine updates — DHPPi rename, puppy series, optional vaccines
--
-- Changes:
--   1. Rename "Core Vaccine" (dog) → "DHPPi".
--      Alternate common names: 7-in-1 / 9-in-1 vaccination.
--   2. Rename "Bordetella" (dog) → "Kennel Cough (Nobivac KC)".
--   3. Insert 4 mandatory puppy vaccination items (dogs only):
--      - DHPPi 1st Dose  (6–8 weeks)
--      - DHPPi 2nd Dose  (9–12 weeks)
--      - DHPPi 3rd Dose  (12–16 weeks, given with first Rabies dose)
--      - Puppy Booster   (1 year — DHPPi & Rabies combined booster)
--      recurrence_days=36500 marks these as effectively one-time items.
--   4. Insert 2 optional vaccines (dogs only):
--      - Canine Coronavirus (CCoV)  — annual
--      - (Kennel Cough already handled by rename above)
--
-- Safe to re-run: UPDATEs are idempotent; INSERTs use ON CONFLICT DO NOTHING.

BEGIN;

-- 1. Rename Core Vaccine → DHPPi (dog row only)
UPDATE preventive_master
SET    item_name = 'DHPPi'
WHERE  item_name = 'Core Vaccine'
  AND  species   = 'dog';

-- 2. Rename Bordetella → Kennel Cough (Nobivac KC) (dog row only)
UPDATE preventive_master
SET    item_name = 'Kennel Cough (Nobivac KC)'
WHERE  item_name = 'Bordetella'
  AND  species   = 'dog';

-- 3. Puppy vaccination series + optional vaccines
INSERT INTO preventive_master
    (id, item_name, category, circle, species,
     recurrence_days, medicine_dependent, reminder_before_days, overdue_after_days)
VALUES
    -- DHPPi 1st Dose (6–8 weeks)
    (gen_random_uuid(), 'DHPPi 1st Dose', 'essential', 'health', 'dog',
     36500, FALSE, 14, 21),

    -- DHPPi 2nd Dose (9–12 weeks)
    (gen_random_uuid(), 'DHPPi 2nd Dose', 'essential', 'health', 'dog',
     36500, FALSE, 14, 21),

    -- DHPPi 3rd Dose (12–16 weeks; given together with first Rabies dose)
    (gen_random_uuid(), 'DHPPi 3rd Dose', 'essential', 'health', 'dog',
     36500, FALSE, 14, 21),

    -- Puppy Booster (1 year — DHPPi & Rabies; transitions to annual cycle after)
    (gen_random_uuid(), 'Puppy Booster', 'essential', 'health', 'dog',
     36500, FALSE, 30, 14),

    -- Canine Coronavirus / CCoV (optional, annual)
    (gen_random_uuid(), 'Canine Coronavirus (CCoV)', 'complete', 'health', 'dog',
     365, FALSE, 30, 14)

ON CONFLICT (item_name, species) DO NOTHING;

COMMIT;
