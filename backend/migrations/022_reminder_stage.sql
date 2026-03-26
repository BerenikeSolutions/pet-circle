-- Migration 022: Reminder 4-Stage Lifecycle
--
-- Adds stage, ignore tracking, and monthly fallback to the reminders table.
-- Updates the UNIQUE constraint to include stage so that t7/due/d3/overdue_insight
-- can coexist for the same preventive record on the same due date cycle.
--
-- Stages: t7 (7 days before), due (due date), d3 (D+3 check-in), overdue_insight (D+7+)
-- ignore_count: incremented each time a sent reminder has no inbound reply within 24h
-- monthly_fallback: set TRUE when ignore_count >= 2; only overdue_insight fires monthly
--
-- NOTE: Clear the reminders table before applying (S3 decision: no existing data to migrate).

BEGIN;

-- 1. Add stage column (default 'due' for any legacy rows if present)
ALTER TABLE reminders
  ADD COLUMN IF NOT EXISTS stage VARCHAR(20) NOT NULL DEFAULT 'due';

ALTER TABLE reminders
  DROP CONSTRAINT IF EXISTS reminders_stage_check;
ALTER TABLE reminders
  ADD CONSTRAINT reminders_stage_check
    CHECK (stage IN ('t7', 'due', 'd3', 'overdue_insight'));

-- 2. Add ignore tracking columns
ALTER TABLE reminders
  ADD COLUMN IF NOT EXISTS ignore_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE reminders
  ADD COLUMN IF NOT EXISTS monthly_fallback BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE reminders
  ADD COLUMN IF NOT EXISTS last_ignored_at TIMESTAMPTZ;

-- 3. Replace old UNIQUE(preventive_record_id, next_due_date) with
--    UNIQUE(preventive_record_id, next_due_date, stage)
ALTER TABLE reminders
  DROP CONSTRAINT IF EXISTS uq_reminder_record_duedate;

ALTER TABLE reminders
  ADD CONSTRAINT uq_reminder_record_duedate_stage
    UNIQUE (preventive_record_id, next_due_date, stage);

-- 4. Index for fast stage-based queries in reminder engine
CREATE INDEX IF NOT EXISTS idx_reminders_stage
  ON reminders (stage, status);

CREATE INDEX IF NOT EXISTS idx_reminders_monthly_fallback
  ON reminders (monthly_fallback, status)
  WHERE monthly_fallback = TRUE;

COMMIT;
