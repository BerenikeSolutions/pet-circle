"""
PetCircle — Database Migration: GCP Storage Backend Column

Adds `storage_backend` column to the `documents` table to track whether
each document file is stored in GCP Cloud Storage (primary) or Supabase (fallback).

All existing rows are backfilled to 'supabase' via the column DEFAULT.

Usage:
    cd backend
    python scripts/migrate_gcp_storage.py
"""

import logging
from sqlalchemy import text
from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add storage_backend column to documents table."""
    migration_sql = """
    -- Add storage backend tracking column.
    -- DEFAULT 'supabase' backfills all existing rows automatically.
    ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(20) NOT NULL DEFAULT 'supabase';

    -- Enforce valid values — only 'gcp' or 'supabase' are allowed.
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'documents_storage_backend_check'
        ) THEN
            ALTER TABLE documents
                ADD CONSTRAINT documents_storage_backend_check
                CHECK (storage_backend IN ('gcp', 'supabase'));
        END IF;
    END$$;

    -- Index for sync job queries: WHERE storage_backend = 'supabase'
    CREATE INDEX IF NOT EXISTS ix_documents_storage_backend
        ON documents(storage_backend)
    """

    try:
        with engine.begin() as connection:
            for statement in migration_sql.split(';'):
                statement = statement.strip()
                if statement:
                    logger.info(f"Executing: {statement[:60]}...")
                    connection.execute(text(statement))

        logger.info("Migration completed successfully — storage_backend column added to documents")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = migrate()
    exit(0 if success else 1)
