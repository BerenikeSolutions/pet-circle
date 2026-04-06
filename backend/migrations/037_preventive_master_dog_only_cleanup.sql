-- Migration 037: Preventive master cleanup (dog-only, no grooming/dental/fecal)
--
-- Applies the current temporary business scope:
--   1) Keep only dog preventive master rows
--   2) Remove grooming-related items
--   3) Remove dental and fecal test items
--
-- Note: Preventive records linked to removed preventive_master rows are also
-- deleted to satisfy FK constraints.

BEGIN;

CREATE TABLE IF NOT EXISTS preventive_master_archive_037 AS
SELECT * FROM preventive_master WHERE FALSE;

CREATE TABLE IF NOT EXISTS preventive_records_archive_037 AS
SELECT * FROM preventive_records WHERE FALSE;

WITH target_master AS (
    SELECT id
    FROM preventive_master
    WHERE species <> 'dog'
       OR item_name IN (
            'Bath & Grooming',
            'Nail Trimming',
            'Ear Cleaning',
            'Dental Check',
            'Fecal Test',
            'Fecal Examination',
            'Stool Test'
        )
),
deleted_records AS (
    DELETE FROM preventive_records pr
    USING target_master tm
    WHERE pr.preventive_master_id = tm.id
    RETURNING pr.*
),
archived_records AS (
    INSERT INTO preventive_records_archive_037
    SELECT * FROM deleted_records
    RETURNING id
),
deleted_master AS (
    DELETE FROM preventive_master pm
    USING target_master tm
    WHERE pm.id = tm.id
    RETURNING pm.*
)
INSERT INTO preventive_master_archive_037
SELECT * FROM deleted_master;

COMMIT;
