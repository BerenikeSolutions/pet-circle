-- Migration 053: Document extraction hardening
--
-- Adds three columns to support:
--   retry_count           — how many auto-replay attempts have been made
--   content_hash          — SHA-256 of file bytes for duplicate detection
--   extraction_confidence — model-rated confidence score (0.0–1.0)
--
-- Also extends the extraction_status CHECK constraint to allow
-- the new 'partially_extracted' status.

-- ── New columns ────────────────────────────────────────────────────────────
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS retry_count           INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS content_hash          VARCHAR(64),
    ADD COLUMN IF NOT EXISTS extraction_confidence FLOAT;

-- ── extraction_status constraint ────────────────────────────────────────────
-- Drop the existing CHECK constraint (name may vary by Supabase environment).
-- We recreate it with 'partially_extracted' included.
DO $$
DECLARE
    v_constraint TEXT;
BEGIN
    SELECT conname INTO v_constraint
    FROM   pg_constraint
    WHERE  conrelid = 'documents'::regclass
      AND  contype  = 'c'
      AND  conname  LIKE '%extraction_status%'
    LIMIT 1;

    IF v_constraint IS NOT NULL THEN
        EXECUTE 'ALTER TABLE documents DROP CONSTRAINT ' || quote_ident(v_constraint);
    END IF;
END;
$$;

ALTER TABLE documents
    ADD CONSTRAINT documents_extraction_status_check
    CHECK (extraction_status IN (
        'pending',
        'success',
        'partially_extracted',
        'failed',
        'rejected'
    ));

-- ── Index for replay-queue queries ──────────────────────────────────────────
-- Supports: WHERE extraction_status = 'failed' AND retry_count < N
CREATE INDEX IF NOT EXISTS idx_documents_retry_eligible
    ON documents (retry_count)
    WHERE extraction_status = 'failed';

-- ── Index for duplicate-detection queries ───────────────────────────────────
-- Supports: WHERE content_hash = ? AND pet_id = ?
CREATE INDEX IF NOT EXISTS idx_documents_content_hash
    ON documents (content_hash, pet_id)
    WHERE content_hash IS NOT NULL;

COMMENT ON COLUMN documents.retry_count           IS 'Auto-replay attempts made so far. Capped at EXTRACTION_MAX_AUTO_RETRIES.';
COMMENT ON COLUMN documents.content_hash          IS 'SHA-256 hex of raw file bytes. Used to skip re-extraction of duplicate uploads.';
COMMENT ON COLUMN documents.extraction_confidence IS 'Model-rated confidence for the extraction (0.0–1.0). Below threshold triggers a second-pass retry.';
