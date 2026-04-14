-- Migration 057: Add 'vital' to allowed test_type values in diagnostic_test_results
--
-- The GPT extraction service stores clinical exam data (temperature, pulse, respiration,
-- mucous membranes, in-clinic test values) as DiagnosticTestResult rows with
-- test_type='vital', but the original constraint only allowed 'blood' and 'urine'.
-- This migration widens the constraint to include 'vital'.

ALTER TABLE diagnostic_test_results
  DROP CONSTRAINT chk_diagnostic_test_type;

ALTER TABLE diagnostic_test_results
  ADD CONSTRAINT chk_diagnostic_test_type
    CHECK (test_type IN ('blood', 'urine', 'vital'));
