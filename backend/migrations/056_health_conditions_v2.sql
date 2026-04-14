-- Migration 056: Health Conditions v2
-- Adds fields required by the new extraction prompt (episode_dates, condition_status,
-- medications end_date, monitoring recheck_due_date) and the Health Prompt 5 pipeline.

-- conditions table
ALTER TABLE conditions
  ADD COLUMN IF NOT EXISTS condition_status VARCHAR(20),
  ADD COLUMN IF NOT EXISTS episode_dates JSONB NOT NULL DEFAULT '[]'::jsonb;

-- condition_medications table
ALTER TABLE condition_medications
  ADD COLUMN IF NOT EXISTS end_date DATE;

-- condition_monitoring table
ALTER TABLE condition_monitoring
  ADD COLUMN IF NOT EXISTS recheck_due_date DATE;
