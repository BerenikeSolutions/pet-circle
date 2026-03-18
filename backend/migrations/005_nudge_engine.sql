-- Migration 005: Nudge Engine
-- Adds columns to nudges table, creates nudge_config, nudge_delivery_log, nudge_engagement tables

-- 1. Alter nudges table — add new columns
ALTER TABLE nudges ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'record';
ALTER TABLE nudges ADD COLUMN IF NOT EXISTS wa_status VARCHAR(20);
ALTER TABLE nudges ADD COLUMN IF NOT EXISTS wa_sent_at TIMESTAMP;
ALTER TABLE nudges ADD COLUMN IF NOT EXISTS wa_message_id VARCHAR(100);
ALTER TABLE nudges ADD COLUMN IF NOT EXISTS trigger_type VARCHAR(20) DEFAULT 'cron';
ALTER TABLE nudges ADD COLUMN IF NOT EXISTS expires_at DATE;
ALTER TABLE nudges ADD COLUMN IF NOT EXISTS acted_on BOOLEAN DEFAULT FALSE;

-- Update category CHECK to include 'checkup'
-- (Drop existing constraint if any, then add new one)
ALTER TABLE nudges DROP CONSTRAINT IF EXISTS nudges_category_check;
ALTER TABLE nudges ADD CONSTRAINT nudges_category_check
  CHECK (category IN ('vaccine', 'deworming', 'flea', 'condition', 'nutrition', 'grooming', 'checkup'));

-- 2. Create nudge_config table
CREATE TABLE IF NOT EXISTS nudge_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key VARCHAR(100) UNIQUE NOT NULL,
  value VARCHAR(200) NOT NULL,
  description TEXT,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Seed default config values
INSERT INTO nudge_config (key, value, description) VALUES
  ('max_per_24h', '1', 'Max nudges sent via WhatsApp per user per 24 hours'),
  ('max_per_7d', '3', 'Max nudges sent via WhatsApp per user per 7 days'),
  ('pause_days_if_inactive', '14', 'Days to pause nudges if user ignores them'),
  ('inactivity_threshold_days', '30', 'Days of no activity before sending re-engagement nudge'),
  ('checkup_blood_test_interval_days', '365', 'Days between recommended blood tests'),
  ('checkup_full_panel_interval_days', '365', 'Days between recommended full preventive panels')
ON CONFLICT (key) DO NOTHING;

-- 3. Create nudge_delivery_log table
CREATE TABLE IF NOT EXISTS nudge_delivery_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nudge_id UUID NOT NULL REFERENCES nudges(id) ON DELETE CASCADE,
  pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  wa_status VARCHAR(20),
  sent_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nudge_delivery_log_user_sent
  ON nudge_delivery_log (user_id, sent_at);

-- 4. Create nudge_engagement table
CREATE TABLE IF NOT EXISTS nudge_engagement (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
  last_engagement_at TIMESTAMP,
  paused_until TIMESTAMP,
  total_nudges_sent INTEGER DEFAULT 0,
  total_acted_on INTEGER DEFAULT 0,
  UNIQUE(user_id, pet_id)
);
