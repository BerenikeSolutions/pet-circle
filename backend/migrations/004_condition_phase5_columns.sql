-- Phase 5: Add missing columns for Conditions Tab full parity
-- Adds refill tracking to medications, due dates to monitoring, and display fields to conditions

-- Conditions: icon and managed_by for display
ALTER TABLE conditions ADD COLUMN IF NOT EXISTS icon VARCHAR(10);
ALTER TABLE conditions ADD COLUMN IF NOT EXISTS managed_by VARCHAR(200);

-- Condition Medications: refill tracking
ALTER TABLE condition_medications ADD COLUMN IF NOT EXISTS refill_due_date DATE;
ALTER TABLE condition_medications ADD COLUMN IF NOT EXISTS price VARCHAR(20);

-- Condition Monitoring: due date tracking
ALTER TABLE condition_monitoring ADD COLUMN IF NOT EXISTS next_due_date DATE;
ALTER TABLE condition_monitoring ADD COLUMN IF NOT EXISTS last_done_date DATE;
