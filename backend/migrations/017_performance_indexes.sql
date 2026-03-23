-- Migration 017: Performance indexes for dashboard query optimization
-- Run this in the Supabase SQL editor.
-- All indexes use IF NOT EXISTS — safe to run multiple times.

-- Preventive records: common filters in dashboard load and health score
CREATE INDEX IF NOT EXISTS idx_preventive_records_pet_status
    ON preventive_records(pet_id, status);

CREATE INDEX IF NOT EXISTS idx_preventive_records_pet_next_due
    ON preventive_records(pet_id, next_due_date ASC);

-- Reminders: no pet_id — filtered by preventive_record_id + status
CREATE INDEX IF NOT EXISTS idx_reminders_record_status
    ON reminders(preventive_record_id, status);

-- Documents: filtered by pet + extraction_status
CREATE INDEX IF NOT EXISTS idx_documents_pet_extraction
    ON documents(pet_id, extraction_status);

-- Diagnostic results: filtered by pet, ordered by observed_at
CREATE INDEX IF NOT EXISTS idx_diagnostic_test_results_pet
    ON diagnostic_test_results(pet_id);

-- Conditions: filtered by pet + is_active
CREATE INDEX IF NOT EXISTS idx_conditions_pet_active
    ON conditions(pet_id, is_active);

-- Condition child tables: used by selectinload eager loading
CREATE INDEX IF NOT EXISTS idx_condition_medications_condition
    ON condition_medications(condition_id);

CREATE INDEX IF NOT EXISTS idx_condition_monitoring_condition
    ON condition_monitoring(condition_id);

-- Contacts: filtered by pet
CREATE INDEX IF NOT EXISTS idx_contacts_pet
    ON contacts(pet_id);

-- Conflict flags: no pet_id — filtered by preventive_record_id + status
CREATE INDEX IF NOT EXISTS idx_conflict_flags_record_status
    ON conflict_flags(preventive_record_id, status);

-- Dashboard tokens: primary access path for every dashboard request
CREATE INDEX IF NOT EXISTS idx_dashboard_tokens_token
    ON dashboard_tokens(token);

-- AI insights: cache lookup by pet + type + generated_at (no expires_at column)
CREATE INDEX IF NOT EXISTS idx_pet_ai_insights_pet_type
    ON pet_ai_insights(pet_id, insight_type, generated_at);
