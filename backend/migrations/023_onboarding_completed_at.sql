-- Migration 023: Add onboarding_completed_at to users
--
-- Required by nudge_scheduler.py to compute O (Onboarding Day) for O+N schedule.
-- Also adds active_reminder_id to support the awaiting_reschedule_date flow:
-- when a user taps "Schedule For ()" on a reminder, we store the reminder ID
-- on the user record so message_router can call apply_reschedule_date() when
-- the user replies with their chosen date.
--
-- Backfill: users who are already complete get onboarding_completed_at = created_at
-- as a reasonable approximation.

BEGIN;

-- Timestamp when user completed the onboarding conversation
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;

-- Backfill existing completed users
UPDATE users
SET onboarding_completed_at = created_at
WHERE onboarding_state = 'complete'
  AND onboarding_completed_at IS NULL;

-- Active reminder ID for the reschedule flow
-- SET NULL when reminder is deleted/completed
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS active_reminder_id UUID
    REFERENCES reminders(id) ON DELETE SET NULL;

-- Index for scheduler: only process users who have completed onboarding
CREATE INDEX IF NOT EXISTS idx_users_onboarding_completed
  ON users (onboarding_completed_at)
  WHERE onboarding_completed_at IS NOT NULL;

COMMIT;
