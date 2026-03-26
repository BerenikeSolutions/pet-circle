-- Migration 028: Reminder Source Columns
--
-- Extends the reminders table to support 4 additional reminder categories
-- that do not originate from preventive_records:
--   diet_item         → Food Order + Supplement Order reminders
--   condition_medication → Chronic Medicine reminders
--   condition_monitoring → Vet Follow-up reminders
--   hygiene_preference   → Hygiene reminders
--
-- Changes:
--   - preventive_record_id becomes nullable (was implicitly required)
--   - source_type: identifies which table this reminder originated from
--   - source_id:   UUID of the source row (no FK — multiple tables)
--   - item_desc:   cached human-readable description for message building
--   - pet_id:      direct pet reference (avoids join through preventive_record)
--
-- Constraint: exactly one of preventive_record_id or source_id must be set.
-- This is enforced at the application layer, not DB level.

BEGIN;

-- 1. Make preventive_record_id nullable (it was NOT NULL implicitly in app layer)
ALTER TABLE reminders
  ALTER COLUMN preventive_record_id DROP NOT NULL;

-- 2. Add source tracking columns
ALTER TABLE reminders
  ADD COLUMN IF NOT EXISTS source_type VARCHAR(30);
-- Values: 'preventive_record' | 'diet_item' | 'condition_medication'
--         | 'condition_monitoring' | 'hygiene_preference'

ALTER TABLE reminders
  ADD COLUMN IF NOT EXISTS source_id UUID;
-- UUID of the source row; no FK constraint (multiple possible tables)

ALTER TABLE reminders
  ADD COLUMN IF NOT EXISTS item_desc VARCHAR(300);
-- Cached human-readable description for building the WA reminder message body.
-- e.g. "Rabies · DHPPi (mandatory) · Kennel Cough (optional)"

-- 3. Add direct pet_id for efficient querying (avoids join through preventive_record)
ALTER TABLE reminders
  ADD COLUMN IF NOT EXISTS pet_id UUID REFERENCES pets(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_reminders_pet_id
  ON reminders (pet_id, status, sent_at);

-- 4. Backfill pet_id for existing preventive_record-based reminders
UPDATE reminders r
SET    pet_id = pr.pet_id,
       source_type = 'preventive_record',
       source_id = r.preventive_record_id
FROM   preventive_records pr
WHERE  r.preventive_record_id = pr.id
  AND  r.pet_id IS NULL;

COMMIT;
