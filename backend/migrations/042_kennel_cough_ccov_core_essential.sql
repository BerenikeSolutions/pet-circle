-- Migration 042: Ensure Kennel Cough and CCoV are essential + is_core
--
-- Consolidates the intent of migrations 038 (category=essential) and
-- 039 (is_core=TRUE) into a single idempotent statement.
-- Fixes the bug where these vaccines were missing from the care plan
-- because they had no preventive_record and the care plan engine only
-- injected items with is_core=TRUE from preventive_master.
--
-- Safe to re-run: UPDATEs are idempotent.

BEGIN;

UPDATE preventive_master
SET    category = 'essential',
       is_core  = TRUE
WHERE  species   = 'dog'
  AND  item_name IN ('Kennel Cough (Nobivac KC)', 'Canine Coronavirus (CCoV)');

COMMIT;
