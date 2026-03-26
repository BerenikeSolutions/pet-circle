-- Migration 029: nudge_delivery_log — add nudge_level, make nudge_id nullable
--
-- Purpose:
--   nudge_scheduler.py creates delivery log rows that are not linked to a
--   dashboard nudge row (nudge_id=NULL). This migration makes nudge_id nullable
--   and adds nudge_level (0/1/2) for slot-counter queries in nudge_scheduler.
--
-- Safe to run on an empty or populated table.

BEGIN;

-- Allow NULL nudge_id for scheduler-generated rows (no dashboard nudge row).
ALTER TABLE nudge_delivery_log
    ALTER COLUMN nudge_id DROP NOT NULL;

-- Add nudge_level for O+N slot tracking per level (Level 0/1/2 system).
ALTER TABLE nudge_delivery_log
    ADD COLUMN IF NOT EXISTS nudge_level INTEGER;

-- Index for efficient slot-counter query in _completed_slots().
CREATE INDEX IF NOT EXISTS idx_nudge_delivery_log_user_level
    ON nudge_delivery_log (user_id, nudge_level);

COMMIT;
