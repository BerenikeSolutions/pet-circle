-- Migration 059: Persist extraction fields that were previously dropped
--
-- Gap 1: documents.diagnostic_summary
--   GPT extracts a 1–2 sentence plain-language summary for Diagnostic
--   documents (blood panels, imaging, etc.). Previously this was only
--   returned in the API response and discarded after the webhook cycle.
--
-- Gap 2: documents.non_diet_recommendations
--   GPT extracts activity, rest, follow_up and other vet recommendations.
--   Previously only the diet sub-type was saved (to diet_items).
--   Non-diet recs are now stored as JSONB on the document row so they
--   can be surfaced on the dashboard without a separate join.
--
-- Gap 3: preventive_records.vaccination_metadata
--   GPT extracts rich vaccine metadata (dose, dose_unit, route,
--   manufacturer, batch_number, administered_by, notes) from vaccination
--   certificates but only the date was ever saved.  This column stores
--   the full detail as JSONB so nothing is lost.

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS diagnostic_summary TEXT,
  ADD COLUMN IF NOT EXISTS non_diet_recommendations JSONB;

ALTER TABLE preventive_records
  ADD COLUMN IF NOT EXISTS vaccination_metadata JSONB;

-- Gap 4: condition_medications.item_type
--   GPT classifies every medication as "medicine" or "supplement" via item_type.
--   Supplements are routed to diet_items; medicines land in condition_medications.
--   The classification was extracted but never stored — this column preserves it.
ALTER TABLE condition_medications
  ADD COLUMN IF NOT EXISTS item_type VARCHAR(20) NOT NULL DEFAULT 'medicine';
