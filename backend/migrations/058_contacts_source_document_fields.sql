-- Migration 058: Add source document fields to contacts table
-- Denormalizes document_name and document_category from the source document
-- onto each contact row for easy display without joins.
-- Both columns are nullable — manual contacts will have NULL values.

ALTER TABLE contacts
  ADD COLUMN IF NOT EXISTS source_document_name VARCHAR(200),
  ADD COLUMN IF NOT EXISTS source_document_category VARCHAR(30);
