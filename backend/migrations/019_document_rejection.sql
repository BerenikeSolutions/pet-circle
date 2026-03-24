-- Migration 019: Add rejection support to documents table
-- Allows invalid documents (not pet-related or wrong pet name) to be flagged
-- with a reason visible on the dashboard before the user dismisses them.

-- Add rejection_reason column (null for normal docs, set for rejected ones)
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(200);

-- Extend extraction_status CHECK to include 'rejected'
ALTER TABLE documents
    DROP CONSTRAINT IF EXISTS documents_extraction_status_check;

ALTER TABLE documents
    ADD CONSTRAINT documents_extraction_status_check
    CHECK (extraction_status IN ('pending', 'success', 'failed', 'rejected'));
