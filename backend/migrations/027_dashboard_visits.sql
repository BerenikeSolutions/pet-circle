-- Migration 027: Dashboard Visits Tracking
--
-- Records every authenticated dashboard token access for:
--   1. Nudge level recalculation (N8) — "dashboard visit" is a trigger event
--   2. Level 2 topic detection (N9) — GPT checks recent visit context
--   3. 48h engagement gap check in nudge_scheduler
--
-- Each row = one page load by a verified token holder.

BEGIN;

CREATE TABLE IF NOT EXISTS dashboard_visits (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  pet_id     UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
  token      VARCHAR(200) NOT NULL,      -- the dashboard token used (for audit)
  visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dashboard_visits_user_visited
  ON dashboard_visits (user_id, visited_at DESC);

CREATE INDEX IF NOT EXISTS idx_dashboard_visits_pet_visited
  ON dashboard_visits (pet_id, visited_at DESC);

COMMIT;
