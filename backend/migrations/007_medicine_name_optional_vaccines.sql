-- Migration 007: Add medicine_name to preventive_records + optional vaccines
-- Run against Supabase PostgreSQL

-- 1. Add medicine_name column to preventive_records
ALTER TABLE preventive_records
ADD COLUMN IF NOT EXISTS medicine_name VARCHAR(200);

-- 2. Insert optional vaccines into preventive_master (only if they don't exist)

-- Dogs: Bordetella
INSERT INTO preventive_master (id, item_name, category, circle, species, recurrence_days, medicine_dependent, reminder_before_days, overdue_after_days)
SELECT gen_random_uuid(), 'Bordetella', 'complete', 'health', 'dog', 365, false, 30, 14
WHERE NOT EXISTS (SELECT 1 FROM preventive_master WHERE item_name = 'Bordetella' AND species = 'dog');

-- Dogs: Leptospirosis
INSERT INTO preventive_master (id, item_name, category, circle, species, recurrence_days, medicine_dependent, reminder_before_days, overdue_after_days)
SELECT gen_random_uuid(), 'Leptospirosis', 'complete', 'health', 'dog', 365, false, 30, 14
WHERE NOT EXISTS (SELECT 1 FROM preventive_master WHERE item_name = 'Leptospirosis' AND species = 'dog');

-- Dogs: Canine Influenza
INSERT INTO preventive_master (id, item_name, category, circle, species, recurrence_days, medicine_dependent, reminder_before_days, overdue_after_days)
SELECT gen_random_uuid(), 'Canine Influenza', 'complete', 'health', 'dog', 365, false, 30, 14
WHERE NOT EXISTS (SELECT 1 FROM preventive_master WHERE item_name = 'Canine Influenza' AND species = 'dog');

-- Cats: FeLV Vaccine
INSERT INTO preventive_master (id, item_name, category, circle, species, recurrence_days, medicine_dependent, reminder_before_days, overdue_after_days)
SELECT gen_random_uuid(), 'FeLV Vaccine', 'complete', 'health', 'cat', 365, false, 30, 14
WHERE NOT EXISTS (SELECT 1 FROM preventive_master WHERE item_name = 'FeLV Vaccine' AND species = 'cat');

-- Cats: FIV Vaccine
INSERT INTO preventive_master (id, item_name, category, circle, species, recurrence_days, medicine_dependent, reminder_before_days, overdue_after_days)
SELECT gen_random_uuid(), 'FIV Vaccine', 'complete', 'health', 'cat', 365, false, 30, 14
WHERE NOT EXISTS (SELECT 1 FROM preventive_master WHERE item_name = 'FIV Vaccine' AND species = 'cat');
