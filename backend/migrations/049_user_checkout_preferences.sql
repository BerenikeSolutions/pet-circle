-- Migration 049: Add checkout preference columns to users table
--
-- Adds three nullable columns to persist last-used checkout details:
--   delivery_address     - free-text delivery address (last used)
--   payment_method_pref  - last payment method: 'cod' | 'upi' | 'card'
--   saved_upi_id         - Fernet-encrypted UPI VPA fetched from Razorpay after payment
--
-- These are saved automatically after every successful order so the next
-- checkout can prefill the address and pre-select the payment method.
--
-- Safe to re-run: uses IF NOT EXISTS.
-- Prerequisite: migrations 001_initial_schema.sql must have run.

BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS delivery_address    TEXT,
    ADD COLUMN IF NOT EXISTS payment_method_pref VARCHAR(10),
    ADD COLUMN IF NOT EXISTS saved_upi_id        VARCHAR(500);

-- Sanity check
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'delivery_address'
    ) THEN
        RAISE EXCEPTION 'Migration 049 failed: delivery_address column not found';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'payment_method_pref'
    ) THEN
        RAISE EXCEPTION 'Migration 049 failed: payment_method_pref column not found';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'saved_upi_id'
    ) THEN
        RAISE EXCEPTION 'Migration 049 failed: saved_upi_id column not found';
    END IF;

    RAISE NOTICE 'Migration 049 complete: delivery_address, payment_method_pref, saved_upi_id added to users';
END $$;

COMMIT;
