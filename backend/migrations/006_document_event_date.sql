-- Migration 006: Add event_date column to documents table
-- Stores the date when the vaccination/test/procedure was actually performed
-- (as opposed to created_at which is the upload timestamp).

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS event_date DATE;

-- Backfill event_date from document_name where date was appended
-- (format: "Document Name - DD-MM-YYYY")
-- This is best-effort; new extractions will populate it properly.
COMMENT ON COLUMN documents.event_date IS 'Date the medical event occurred (vaccination, test, etc.), extracted by GPT. Distinct from created_at (upload date).';
