-- Migration 045: Add cart_expires_at column to cart_items
-- Cart state persists for 72 hours (C6). Items older than 72h are hidden.

ALTER TABLE cart_items
    ADD COLUMN IF NOT EXISTS cart_expires_at TIMESTAMPTZ;

-- Backfill existing rows: expiry = created_at + 72 hours
UPDATE cart_items
SET cart_expires_at = created_at + INTERVAL '72 hours'
WHERE cart_expires_at IS NULL;

-- Set NOT NULL default going forward (applied after backfill)
ALTER TABLE cart_items
    ALTER COLUMN cart_expires_at SET DEFAULT NOW() + INTERVAL '72 hours';
