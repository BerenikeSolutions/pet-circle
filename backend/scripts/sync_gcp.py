"""
PetCircle — GCP Storage Sync Script

Migrates document files from Supabase (fallback) to GCP Cloud Storage (primary).

For each document where storage_backend='supabase':
    1. Download file bytes from Supabase.
    2. Upload bytes to GCP Cloud Storage.
    3. Verify GCP blob exists (blob.exists() check).
    4. Update documents.storage_backend = 'gcp' in the database.
    5. Delete the file from Supabase.

Design:
    - Idempotent: safe to re-run; rows with storage_backend='gcp' are skipped.
    - Atomic per document: DB update only after confirmed GCP upload + verification.
    - Fault-tolerant: one failed document never stops the rest.
    - Processes in batches of 50 to avoid large in-memory result sets.

Usage:
    cd backend
    python scripts/sync_gcp.py                    # migrate up to 500 docs
    python scripts/sync_gcp.py --dry-run          # log without modifying anything
    python scripts/sync_gcp.py --limit 100        # migrate at most 100 docs

Environment:
    Reads from envs/.env.{APP_ENV} (or env vars injected by hosting provider).
    Required: DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
              SUPABASE_BUCKET_NAME, GCP_CREDENTIALS_JSON, GCP_BUCKET_NAME.
"""

import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sync_gcp")

BATCH_SIZE = 50


async def sync_all_documents(
    limit: int = 500,
    dry_run: bool = False,
) -> dict:
    """
    Migrate all Supabase-stored documents to GCP, up to `limit` documents.

    Args:
        limit: Maximum number of documents to migrate in this run.
        dry_run: If True, log what would be done but make no changes.

    Returns:
        Summary dict: {total, migrated, failed, skipped}.
    """
    from app.database import SessionLocal
    from app.services.storage_service import is_gcp_available, sync_document_to_gcp
    from sqlalchemy import text

    if not is_gcp_available():
        logger.error(
            "GCP is not available — check GCP_CREDENTIALS_JSON and GCP_BUCKET_NAME env vars. "
            "Aborting sync."
        )
        return {"total": 0, "migrated": 0, "failed": 0, "skipped": 0}

    db = SessionLocal()
    total = 0
    migrated = 0
    failed = 0
    skipped = 0

    try:
        offset = 0
        while total < limit:
            batch_limit = min(BATCH_SIZE, limit - total)

            rows = db.execute(
                text(
                    "SELECT id, file_path, mime_type "
                    "FROM documents "
                    "WHERE storage_backend = 'supabase' "
                    "ORDER BY created_at ASC "
                    "LIMIT :lim OFFSET :off"
                ),
                {"lim": batch_limit, "off": offset},
            ).fetchall()

            if not rows:
                break

            for row in rows:
                doc_id = str(row.id)
                file_path = row.file_path
                mime_type = row.mime_type
                total += 1

                if dry_run:
                    logger.info(
                        "dry-run: would migrate doc_id=%s path=%s", doc_id, file_path
                    )
                    skipped += 1
                    continue

                logger.info("sync: starting doc_id=%s path=%s", doc_id, file_path)
                success = await sync_document_to_gcp(db, doc_id, file_path, mime_type)
                if success:
                    migrated += 1
                    logger.info("sync: done doc_id=%s result=migrated", doc_id)
                else:
                    failed += 1
                    logger.warning("sync: done doc_id=%s result=failed", doc_id)

            # If the batch was smaller than requested, we've exhausted the results.
            if len(rows) < batch_limit:
                break

            # Advance offset only for dry_run (live run rows are no longer 'supabase').
            if dry_run:
                offset += batch_limit

    finally:
        db.close()

    summary = {
        "total": total,
        "migrated": migrated,
        "failed": failed,
        "skipped": skipped,
    }
    logger.info(
        "sync complete: total=%d migrated=%d failed=%d skipped=%d",
        total, migrated, failed, skipped,
    )
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Migrate PetCircle documents from Supabase to GCP Cloud Storage."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be migrated without making any changes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum number of documents to migrate (default: 500).",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("Running in dry-run mode — no changes will be made.")

    summary = asyncio.run(sync_all_documents(limit=args.limit, dry_run=args.dry_run))

    if summary["failed"] > 0:
        logger.warning(
            "%d document(s) failed to migrate. Re-run the script to retry.",
            summary["failed"],
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
