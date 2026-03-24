-- Migration 018: Add storage_backend column to documents table
-- Tracks whether a document is stored in GCP (primary) or Supabase (fallback/legacy)
-- Required by: backend/app/models/document.py (Document.storage_backend)

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(20) NOT NULL DEFAULT 'supabase';

ALTER TABLE documents
    ADD CONSTRAINT documents_storage_backend_check
    CHECK (storage_backend IN ('gcp', 'supabase'));

CREATE INDEX IF NOT EXISTS ix_documents_storage_backend
    ON documents(storage_backend);
