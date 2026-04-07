-- Migration 041: Add columns for health trends guardrail compliance
-- Adds: weight_history.bcs, condition_monitoring.result_summary

-- BCS (Body Condition Score) stored alongside each weight measurement.
-- Integer 1-9 scale; NULL means not recorded for that visit.
ALTER TABLE weight_history
  ADD COLUMN IF NOT EXISTS bcs SMALLINT DEFAULT NULL
  CHECK (bcs IS NULL OR (bcs >= 1 AND bcs <= 9));

-- Short result summary for a monitoring check (e.g. "pus cells nil",
-- "platelet 210K"). Displayed as a finding subtitle on timeline nodes.
ALTER TABLE condition_monitoring
  ADD COLUMN IF NOT EXISTS result_summary VARCHAR(200) DEFAULT NULL;
