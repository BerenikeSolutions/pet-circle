-- Migration 024: Add order-calculation fields to diet_items
--
-- Food Order reminders require: pack_size_g ÷ daily_portion_g = days remaining.
-- Supplement Order reminders require: units_in_pack ÷ doses_per_day = days remaining.
-- When these fields are NULL, the reminder engine falls back to firing at O+21
-- (flag: reminder_order_at_o21 = TRUE set by nudge_scheduler on detection).
--
-- brand: product brand name for display in reminder messages.
-- last_purchase_date: date user last confirmed a restock (set by REMINDER_DONE handler).

BEGIN;

-- Food-specific fields
ALTER TABLE diet_items
  ADD COLUMN IF NOT EXISTS brand VARCHAR(200);

ALTER TABLE diet_items
  ADD COLUMN IF NOT EXISTS pack_size_g INTEGER;

ALTER TABLE diet_items
  ADD COLUMN IF NOT EXISTS daily_portion_g INTEGER;

-- Supplement-specific fields
ALTER TABLE diet_items
  ADD COLUMN IF NOT EXISTS units_in_pack INTEGER;

ALTER TABLE diet_items
  ADD COLUMN IF NOT EXISTS doses_per_day INTEGER;

-- Date of last confirmed purchase/restock (set when user taps "Done — Log It")
ALTER TABLE diet_items
  ADD COLUMN IF NOT EXISTS last_purchase_date DATE;

-- Fallback flag: set TRUE when pack/portion data is missing at O+21 check
ALTER TABLE diet_items
  ADD COLUMN IF NOT EXISTS reminder_order_at_o21 BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
