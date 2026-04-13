"""
PetCircle Phase 1 — Internal Router

Provides internal-only endpoints for cron jobs and system operations.
These endpoints are NOT exposed to users — they are called by GitHub
Actions cron jobs or admin scripts.

Routes:
    POST /internal/run-reminder-engine      — 4-stage reminder lifecycle + conflict expiry.
    POST /internal/run-nudge-scheduler      — Level 0/1/2 nudge scheduler (Excel v5).
    POST /internal/run-extraction-replay    — Retry failed document extractions (batch).

Security:
    - Protected by the same X-ADMIN-KEY header as admin routes.
    - GitHub Actions cron jobs must include the admin key in their requests.
    - No public access.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.rate_limiter import check_admin_rate_limit
from app.core.security import validate_admin_key
from app.database import get_db
from app.services.conflict_expiry import expire_pending_conflicts
from app.services.nudge_engine import run_nudge_engine
from app.services.nudge_sender import check_inactivity_nudges
from app.services.reminder_engine import run_reminder_engine

logger = logging.getLogger(__name__)


# All routes require admin authentication and IP-based rate limiting.
# GitHub Actions cron jobs must include X-ADMIN-KEY header.
router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(check_admin_rate_limit), Depends(validate_admin_key)],
)


@router.post("/run-reminder-engine")
def execute_reminder_engine(db: Session = Depends(get_db)):
    """
    Execute the daily reminder engine and conflict expiry.

    This endpoint is called by GitHub Actions cron at 8 AM IST daily.
    It performs two operations in sequence:

    1. Conflict expiry (Module 19):
        - Auto-resolve pending conflicts older than 5 days.
        - Strategy: KEEP_EXISTING, status='auto_resolved'.

    2. Reminder creation (Module 10):
        - Find preventive records with 'upcoming' or 'overdue' status.
        - Create reminders (deduplicated by UNIQUE constraint).

    3. Reminder sending (Module 10):
        - Send WhatsApp templates for pending reminders.
        - Update status to 'sent' with sent_at timestamp.

    Conflict expiry runs first to ensure stale conflicts are resolved
    before the reminder engine processes records.

    Returns:
        Combined results from all three operations.
    """
    # Each step runs independently so one failure doesn't block the others.
    # This ensures reminders are still sent even if conflict expiry crashes,
    # and vice versa.

    # --- Step 1: Expire stale conflicts ---
    conflicts_resolved = 0
    conflict_error = None
    try:
        conflicts_resolved = expire_pending_conflicts(db)
    except Exception as e:
        conflict_error = str(e)
        logger.error("Conflict expiry failed: %s", str(e), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    # --- Step 2: Create reminders for due records ---
    reminder_results = {"records_checked": 0, "reminders_created": 0, "reminders_skipped": 0, "errors": 0}
    reminder_error = None
    try:
        reminder_results = run_reminder_engine(db)
    except Exception as e:
        reminder_error = str(e)
        logger.error("Reminder engine failed: %s", str(e), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    # send_results derived from reminder_results (run_reminder_engine handles sending)
    send_results = {
        "reminders_sent": reminder_results.get("reminders_sent", 0),
        "reminders_failed": reminder_results.get("reminders_failed", 0),
    }
    send_error = reminder_error

    # --- Step 4: Generate nudges for all active pets ---
    nudge_results = {"pets_processed": 0, "total_nudges": 0, "errors": 0}
    nudge_error = None
    try:
        nudge_results = run_nudge_engine(db)
    except Exception as e:
        nudge_error = str(e)
        logger.error("Nudge engine failed: %s", str(e), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    # --- Step 5: Check for inactive users and create re-engagement nudges ---
    # (WhatsApp nudge sending moved to /internal/run-nudge-scheduler)
    inactivity_results = {"inactivity_nudges_created": 0}
    inactivity_error = None
    try:
        inactivity_results = check_inactivity_nudges(db)
    except Exception as e:
        inactivity_error = str(e)
        logger.error("Inactivity nudge check failed: %s", str(e), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    logger.info(
        "Daily cron completed: conflicts_resolved=%d, "
        "reminders_created=%d, reminders_sent=%d, "
        "nudges_generated=%d, "
        "errors=[conflict=%s, reminder=%s, send=%s, nudge=%s, inactivity=%s]",
        conflicts_resolved,
        reminder_results["reminders_created"],
        send_results["reminders_sent"],
        nudge_results["total_nudges"],
        conflict_error,
        reminder_error,
        send_error,
        nudge_error,
        inactivity_error,
    )

    return {
        "conflicts_resolved": conflicts_resolved,
        "reminder_engine": reminder_results,
        "reminder_sending": send_results,
        "nudge_engine": nudge_results,
        "inactivity_nudges": inactivity_results,
        "errors": {
            "conflict_expiry": conflict_error,
            "reminder_engine": reminder_error,
            "reminder_sending": send_error,
            "nudge_engine": nudge_error,
            "inactivity_nudges": inactivity_error,
        },
    }


@router.post("/run-extraction-replay")
async def execute_extraction_replay(db: Session = Depends(get_db)):
    """
    Replay failed document extractions that are eligible for automatic retry.

    Called by GitHub Actions cron every 6 hours.  Queries documents with:
        - extraction_status = 'failed'
        - retry_count < EXTRACTION_MAX_AUTO_RETRIES

    Processes up to 20 documents per run to avoid long-running requests.
    Each document is downloaded, status reset to 'pending', and extraction
    re-attempted with the full pipeline.

    Returns:
        Dict with replayed, skipped, and per-document errors.
    """
    from app.core.constants import EXTRACTION_MAX_AUTO_RETRIES
    from app.models.document import Document
    from app.services.document_upload import download_from_supabase
    from app.services.gpt_extraction import extract_and_process_document
    from app.services.document_upload import get_extraction_semaphore

    BATCH_LIMIT = 20

    eligible = (
        db.query(Document)
        .filter(
            Document.extraction_status == "failed",
            Document.retry_count < EXTRACTION_MAX_AUTO_RETRIES,
        )
        .order_by(Document.created_at.asc())
        .limit(BATCH_LIMIT)
        .all()
    )

    replayed = 0
    skipped = 0
    errors: list[str] = []

    for doc in eligible:
        try:
            # Download file bytes from storage.
            file_bytes = await download_from_supabase(
                doc.file_path,
                backend=doc.storage_backend or "supabase",
            )
            if not file_bytes:
                logger.warning(
                    "Extraction replay: could not download file for document_id=%s, skipping",
                    str(doc.id),
                )
                skipped += 1
                continue

            # Reset status to pending before re-extraction.
            doc.extraction_status = "pending"
            db.commit()

            semaphore = get_extraction_semaphore()
            async with semaphore:
                result = await extract_and_process_document(
                    db=db,
                    document_id=doc.id,
                    document_text="",
                    file_bytes=file_bytes,
                )

            if result.get("status") == "success":
                replayed += 1
            else:
                skipped += 1
                if result.get("errors"):
                    errors.append(f"doc {doc.id}: {result['errors']}")

        except Exception as e:
            skipped += 1
            errors.append(f"doc {doc.id}: {str(e)}")
            logger.error(
                "Extraction replay failed for document_id=%s: %s",
                str(doc.id), str(e),
            )
            try:
                db.rollback()
            except Exception:
                pass

    logger.info(
        "Extraction replay completed: eligible=%d, replayed=%d, skipped=%d, errors=%d",
        len(eligible), replayed, skipped, len(errors),
    )

    return {
        "eligible": len(eligible),
        "replayed": replayed,
        "skipped": skipped,
        "errors": errors,
    }


@router.post("/run-nudge-scheduler")
async def execute_nudge_scheduler(db: Session = Depends(get_db)):
    """
    Execute the Level 0/1/2 nudge scheduler (Excel v5 spec).

    Called by GitHub Actions cron at 8 AM IST daily, after /run-reminder-engine.
    Sends WhatsApp nudge templates per user level and O+N slot schedule.

    Returns:
        Dict with sent, skipped, and failed counts.
    """
    from app.services.nudge_scheduler import run_nudge_scheduler

    try:
        results = await run_nudge_scheduler(db)
        logger.info("Nudge scheduler completed: %s", results)
        return results
    except Exception as e:
        logger.error("Nudge scheduler failed: %s", str(e), exc_info=True)
        return {"sent": 0, "skipped": 0, "failed": 1}

