"""
PetCircle Phase 1 — Dashboard Router (Module 13)

Provides tokenized access to pet health dashboards. Users receive
a secure random token via WhatsApp that grants read/write access
to their pet's dashboard.

Routes:
    GET  /dashboard/{token}          — Full dashboard data.
    PATCH /dashboard/{token}/weight  — Update pet weight.
    PATCH /dashboard/{token}/preventive — Update preventive record date.

Security:
    - Token-based access — no login required for Phase 1.
    - Token validated per-request (exists + not revoked).
    - No internal IDs exposed in responses.
    - All errors return generic messages to prevent information leakage.

Rules:
    - No bucket hardcoding — file paths are storage-relative.
    - Recalculation triggered after any data update.
    - Pending reminders invalidated when dates change.
"""

import asyncio
import logging
from typing import Any

import razorpay as razorpay_sdk
import hashlib
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel, Field
import re as _re

from sqlalchemy import func as sqlfunc, or_, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import CARE_PLAN_DUE_SOON_DAYS
from app.core.encryption import encrypt_field
from app.core.rate_limiter import check_dashboard_rate_limit
from app.database import get_db
from app.models.cart_item import CartItem
from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.contact import Contact
from app.models.diet_item import DietItem
from app.models.nudge import Nudge
from app.models.pet import Pet
from app.models.product_food import ProductFood
from app.models.product_supplement import ProductSupplement
from app.models.user import User
from app.services.ai_insights_service import (
    get_or_generate_insight,
    get_or_generate_nutrition_importance,
)
from app.services.cart_service import (
    _format_last_bought_label,
    add_to_cart,
    get_cart,
    get_last_bought,
    get_recommendations,
    place_order,
    remove_from_cart,
    toggle_cart_item,
    update_quantity,
)
from app.services.condition_service import (
    add_condition_medication,
    add_condition_monitoring,
    delete_condition_medication,
    delete_condition_monitoring,
    get_condition_recommendations,
    get_condition_timeline,
    get_last_vet_visit,
    update_condition,
    update_condition_medication,
    update_condition_monitoring,
)
from app.services.dashboard_service import (
    get_dashboard_data,
    get_document_file_for_token,
    get_health_trends,
    get_pet_photo_for_token,
    retry_document_extraction,
    update_pet_weight,
    update_preventive_date,
    validate_dashboard_token,
)
from app.services.diet_service import (
    add_diet_item,
    delete_diet_item,
    get_diet_items,
    update_diet_item,
)
from app.services.precompute_service import _upsert_insight
from app.services.ai_insights_service import generate_recognition_bullets
from app.services.health_trends_service import get_health_trends as get_health_trends_v2
from app.services.hygiene_service import (
    add_hygiene_item,
    delete_hygiene_item,
    get_hygiene_preferences,
    update_hygiene_date,
    upsert_hygiene_preference,
)
from app.services.nudge_engine import generate_nudges
from app.services.nutrition_service import analyze_nutrition
from app.services.razorpay_service import create_razorpay_payment, verify_razorpay_payment
from app.services.records_service import get_records as get_records_v2
from app.services.signal_resolver import (
    SUPPLEMENT_TYPE_KEYWORDS,
    resolve_food_signal,
    resolve_supplement_signal,
)
from app.services.weight_service import add_weight_entry, get_weight_history
from app.utils.date_utils import parse_date

logger = logging.getLogger(__name__)

# Extraction semaphore — shared with the WhatsApp upload path.
# Imported from document_upload (single source of truth) so tuning
# MAX_CONCURRENT_EXTRACTIONS in constants.py applies to both paths at once.
from app.services.document_upload import get_extraction_semaphore as _get_extraction_semaphore  # noqa: E402

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(check_dashboard_rate_limit)],
)


class WeightUpdateRequest(BaseModel):
    """
    Request body for updating pet weight.

    Fields:
        weight: New weight in kg (positive number, max 2 decimal places).
    """

    weight: float = Field(
        ...,
        gt=0,
        le=999.99,
        description="New weight in kg (positive, max 999.99)",
    )


class PreventiveDateUpdateRequest(BaseModel):
    """
    Request body for updating a preventive record's last done date.

    Fields:
        item_name: Name of the preventive item (must match preventive_master).
        last_done_date: New date string (accepted formats from date_utils).
    """

    item_name: str = Field(
        ...,
        min_length=1,
        description="Preventive item name (e.g., 'Rabies Vaccine')",
    )
    last_done_date: str = Field(
        ...,
        min_length=1,
        description="New last done date (DD/MM/YYYY, DD-MM-YYYY, "
                    "12 March 2024, or YYYY-MM-DD)",
    )


class CartAddRequest(BaseModel):
    """Request body for adding a product to cart by SKU."""

    sku_id: str = Field(..., min_length=1, description="Product SKU (e.g. F002, S005)")
    quantity: int = Field(1, ge=1, description="Quantity to add (default 1)")


class DashboardHealthTrendsV2Response(BaseModel):
    """Response schema for GET /dashboard/{token}/health-trends-v2."""

    ask_vet: dict[str, Any] | None = None
    signals: dict[str, Any] | None = None
    cadence: dict[str, Any] | None = None


class DashboardRecordsV2Response(BaseModel):
    """Response schema for GET /dashboard/{token}/records-v2."""

    vet_visits: list[dict[str, Any]] = Field(default_factory=list)
    records: list[dict[str, Any]] = Field(default_factory=list)
    failed_documents: list[dict[str, Any]] = Field(default_factory=list)


def _get_pet_for_dashboard_token(db: Session, token: str) -> Pet:
    """Validate token and return the active pet for dashboard data routes."""
    dashboard_token = validate_dashboard_token(db, token)
    pet = db.query(Pet).filter(Pet.id == dashboard_token.pet_id).first()
    if not pet or pet.is_deleted:
        raise ValueError("Pet not found or has been removed.")
    return pet


@router.get("/{token}")
async def dashboard_get(
    token: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Retrieve full dashboard data for a pet via access token.

    Returns pet profile, preventive records, reminders, documents,
    and health score. No internal IDs are exposed.

    Token validation:
        - Token must exist in dashboard_tokens table.
        - Token must not be revoked.
        - Token must not be expired.

    ETag + 304: browser may cache the response body; it must revalidate
    before use (Cache-Control: no-cache). If data is unchanged the server
    returns 304 with no body — saves bandwidth and latency on refreshes.

    Args:
        token: Dashboard access token from URL path.
        request: FastAPI Request for reading If-None-Match header.
        response: FastAPI Response object for setting headers.
        db: SQLAlchemy database session (injected).

    Returns:
        Complete dashboard data dictionary, or 304 if unchanged.

    Raises:
        HTTPException 404: If token is invalid, revoked, or expired.
    """
    try:
        data = await get_dashboard_data(db, token)

        # Compute ETag from content so identical payloads get 304 on refresh.
        etag = hashlib.md5(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()

        if request.headers.get("If-None-Match") == etag:
            return Response(status_code=304)

        # no-cache: browser may store but must revalidate — enables ETag flow.
        # Sensitive data is still protected because every request is verified.
        response.headers["Cache-Control"] = "no-cache"
        response.headers["ETag"] = etag
        return data
    except ValueError as e:
        error_msg = str(e)
        logger.warning(
            "Dashboard access failed: token=%s..., error=%s",
            token[:8] if len(token) >= 8 else token,
            error_msg,
        )
        # Return specific messages so the frontend can show helpful context.
        # These don't leak internal IDs — only explain the token state.
        if "revoked" in error_msg.lower():
            detail = "This dashboard link has been revoked. Send 'dashboard' in WhatsApp to get a new link."
        elif "expired" in error_msg.lower():
            detail = "This dashboard link has expired. Send 'dashboard' in WhatsApp to get a new link."
        else:
            detail = "Dashboard not found or link has expired."
        raise HTTPException(status_code=404, detail=detail)
    except Exception as e:
        logger.error(
            "Dashboard load error: token=%s..., error=%s",
            token[:8] if len(token) >= 8 else token,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Dashboard is temporarily unavailable. Please try again shortly.",
        )


@router.get("/{token}/health-trends-v2", response_model=DashboardHealthTrendsV2Response)
async def dashboard_health_trends_v2(
    token: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Return v2 health trends payload for the dashboard rebuild."""
    try:
        pet = _get_pet_for_dashboard_token(db, token)
        payload = await get_health_trends_v2(db, pet)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return payload
    except ValueError as e:
        logger.warning(
            "Health trends v2 access failed: token=%s..., error=%s",
            token[:8] if len(token) >= 8 else token,
            str(e),
        )
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Health trends v2 error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Health trends are temporarily unavailable. Please try again shortly.",
        )


@router.get("/{token}/records-v2", response_model=DashboardRecordsV2Response)
async def dashboard_records_v2(
    token: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Return v2 structured records payload for the dashboard rebuild."""
    try:
        pet = _get_pet_for_dashboard_token(db, token)
        payload = await get_records_v2(db, pet)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return payload
    except ValueError as e:
        logger.warning(
            "Records v2 access failed: token=%s..., error=%s",
            token[:8] if len(token) >= 8 else token,
            str(e),
        )
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Records v2 error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Records are temporarily unavailable. Please try again shortly.",
        )


@router.patch("/{token}/weight")
def dashboard_update_weight(
    token: str,
    body: WeightUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Update pet weight via dashboard token.

    Weight is a simple field update — no recalculation needed.

    Args:
        token: Dashboard access token from URL path.
        body: WeightUpdateRequest with new weight value.
        db: SQLAlchemy database session (injected).

    Returns:
        Confirmation dictionary with old and new weight.

    Raises:
        HTTPException 404: If token is invalid or pet not found.
    """
    try:
        result = update_pet_weight(db, token, body.weight)
        return result
    except ValueError as e:
        logger.warning(
            "Dashboard weight update failed: token=%s..., error=%s",
            token[:8] if len(token) >= 8 else token,
            str(e),
        )
        raise HTTPException(
            status_code=404,
            detail="Dashboard not found or link has expired.",
        )
    except Exception as e:
        logger.error("Weight update error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Update failed due to a temporary issue. Please try again.",
        )


@router.patch("/{token}/preventive")
def dashboard_update_preventive(
    token: str,
    body: PreventiveDateUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Update a preventive record's last done date via dashboard token.

    Triggers full recalculation:
        - next_due_date recalculated from recurrence_days (DB).
        - status recalculated based on new next_due_date.
        - Pending reminders for old due date are invalidated.

    Date format validation uses parse_date() from date_utils,
    which accepts DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY, and YYYY-MM-DD.

    Args:
        token: Dashboard access token from URL path.
        body: PreventiveDateUpdateRequest with item name and new date.
        db: SQLAlchemy database session (injected).

    Returns:
        Confirmation dictionary with updated record details.

    Raises:
        HTTPException 400: If date format is invalid.
        HTTPException 404: If token invalid or record not found.
    """
    # --- Parse and validate the date ---
    # parse_date raises ValueError for invalid formats.
    try:
        new_date = parse_date(body.last_done_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use DD/MM/YYYY, DD-MM-YYYY, or YYYY-MM-DD.",
        )

    # Last done date cannot be in the future.
    from datetime import date as date_type
    if new_date > date_type.today():
        raise HTTPException(
            status_code=400,
            detail="Last done date cannot be in the future.",
        )

    try:
        result = update_preventive_date(
            db, token, body.item_name, new_date
        )
        return result
    except ValueError as e:
        logger.warning(
            "Dashboard preventive update failed: token=%s..., "
            "item=%s, error=%s",
            token[:8] if len(token) >= 8 else token,
            body.item_name,
            str(e),
        )
        raise HTTPException(
            status_code=404,
            detail="Dashboard not found or record not found.",
        )
    except Exception as e:
        logger.error("Preventive update error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Update failed due to a temporary issue. Please try again.",
        )



@router.get("/{token}/pet-photo")
async def dashboard_get_pet_photo(
    token: str,
    db: Session = Depends(get_db),
):
    """Serve the pet's profile photo for the dashboard."""
    try:
        file_bytes, mime_type = await get_pet_photo_for_token(db, token)
        headers = {
            "Content-Disposition": 'inline; filename="pet_photo"',
            "Cache-Control": "private, max-age=3600",
        }
        return FastAPIResponse(content=file_bytes, media_type=mime_type, headers=headers)
    except ValueError:
        raise HTTPException(status_code=404, detail="Pet photo not found.")
    except Exception:
        raise HTTPException(status_code=503, detail="Could not load pet photo.")


@router.get("/{token}/document/{document_id}")
async def dashboard_get_document(
    token: str,
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Stream a document inline in the browser for dashboard viewing.
    """
    try:
        file_bytes, mime_type, filename = await get_document_file_for_token(db, token, document_id)
        headers = {
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        return FastAPIResponse(content=file_bytes, media_type=mime_type, headers=headers)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=503, detail="Could not open document right now.")

@router.post("/{token}/retry-extraction/{document_id}")
async def dashboard_retry_extraction(
    token: str,
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Retry GPT extraction for a failed document via dashboard token.

    Downloads the file from Supabase, resets status to pending, and
    re-runs the extraction pipeline. Only works for documents with
    extraction_status='failed'.

    Args:
        token: Dashboard access token from URL path.
        document_id: UUID of the document to retry.
        db: SQLAlchemy database session (injected).

    Returns:
        Extraction result dictionary.

    Raises:
        HTTPException 404: If token invalid or document not found.
        HTTPException 400: If document is not in failed state.
        HTTPException 503: If extraction fails.
    """
    try:
        result = await retry_document_extraction(db, token, document_id)
        return result
    except ValueError as e:
        error_msg = str(e)
        logger.warning(
            "Dashboard retry extraction failed: token=%s..., doc=%s, error=%s",
            token[:8] if len(token) >= 8 else token,
            document_id,
            error_msg,
        )
        if "only failed" in error_msg.lower():
            raise HTTPException(status_code=400, detail=error_msg)
        if "extraction failed" in error_msg.lower():
            raise HTTPException(status_code=503, detail=error_msg)
        raise HTTPException(status_code=404, detail="Document not found or link has expired.")
    except Exception as e:
        logger.error("Retry extraction error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Extraction retry failed. Please try again later.",
        )


@router.post("/{token}/retry-all-failed")
async def dashboard_retry_all_failed(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Retry GPT extraction for all failed documents belonging to this pet.

    Iterates every document with extraction_status='failed', re-downloads
    from storage, and re-runs the extraction pipeline. Returns per-document
    outcomes so the frontend can report partial success.
    """
    try:
        pet = _get_pet_for_dashboard_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")

    import asyncio as _asyncio

    from app.models.document import Document as DocumentModel
    from app.services.document_upload import download_from_supabase
    from app.services.gpt_extraction import extract_and_process_document

    failed_docs = (
        db.query(DocumentModel)
        .filter(
            DocumentModel.pet_id == pet.id,
            DocumentModel.extraction_status == "failed",
        )
        .all()
    )

    if not failed_docs:
        return {"retried": 0, "results": []}

    outcomes = []
    for doc in failed_docs:
        try:
            file_bytes = await download_from_supabase(
                doc.file_path,
                backend=getattr(doc, "storage_backend", "supabase"),
            )
            if not file_bytes:
                outcomes.append({"id": str(doc.id), "status": "skipped", "reason": "download_failed"})
                continue

            doc.extraction_status = "pending"
            db.commit()

            result = await _asyncio.wait_for(
                extract_and_process_document(
                    db, doc.id,
                    f"[file: {doc.file_path}]",
                    file_bytes=file_bytes,
                ),
                timeout=120,
            )
            outcomes.append({"id": str(doc.id), "status": result.get("status", "unknown")})
        except Exception as e:
            doc.extraction_status = "failed"
            try:
                db.commit()
            except Exception:
                db.rollback()
            outcomes.append({"id": str(doc.id), "status": "failed", "reason": str(e)})
            logger.error("Bulk retry failed for doc %s: %s", str(doc.id), str(e))

    return {"retried": len(failed_docs), "results": outcomes}


@router.delete("/{token}/document/{document_id}")
async def dashboard_delete_document(
    token: str,
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete a document from the dashboard — removes from storage and DB.

    Args:
        token: Dashboard access token from URL path.
        document_id: UUID of the document to delete.
        db: SQLAlchemy database session (injected).

    Returns:
        { "deleted": true }

    Raises:
        HTTPException 404: If token invalid or document not found for this pet.
    """
    from app.models.document import Document
    from app.services.storage_service import delete_file

    try:
        dt = validate_dashboard_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.pet_id == dt.pet_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Delete from storage (best-effort — proceed with DB delete even if storage fails)
    await delete_file(document.file_path, document.storage_backend or "supabase")

    db.delete(document)
    db.commit()
    logger.info(
        "Document deleted via dashboard: document_id=%s, pet_id=%s",
        document_id,
        str(dt.pet_id),
    )
    return {"deleted": True}


@router.post("/{token}/upload-document")
async def dashboard_upload_document(
    token: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a document from the dashboard and trigger GPT extraction."""
    from app.services.document_upload import process_document_upload

    try:
        dt = validate_dashboard_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")

    from app.models.pet import Pet

    pet = db.query(Pet).filter(Pet.id == dt.pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found.")

    # Read file content
    file_content = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    filename = file.filename or "upload"

    # Validate, upload to storage, and create the DB record — all via the
    # shared pipeline in document_upload.py.  Any fix there applies to both
    # WhatsApp and dashboard uploads automatically.
    try:
        document = await process_document_upload(
            db=db,
            pet_id=pet.id,
            user_id=pet.user_id,
            filename=filename,
            file_content=file_content,
            mime_type=mime_type,
            pet_name=pet.name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError:
        raise HTTPException(status_code=503, detail="File upload failed. Please try again.")

    # Trigger GPT extraction via RabbitMQ queue.
    # The in-process consumer (document_consumer.py) picks up the job and calls
    # run_extraction_batch(), which is gated by the shared extraction semaphore.
    # Falls back to a direct asyncio task if the queue is unavailable.
    try:
        from app.services import queue_service
        _published = await queue_service.publish_extraction_job(
            pet_id=str(pet.id),
            document_ids=[str(document.id)],
            user_id=str(pet.user_id),
            from_number=None,  # Dashboard upload — no WhatsApp reply needed.
            pet_name=pet.name,
            source="dashboard",
        )
    except Exception as _q_exc:
        logger.warning("Dashboard queue publish failed: %s", _q_exc)
        _published = False

    if not _published:
        # Fallback: run extraction directly if queue is unavailable.
        async def _run_extraction():
            from app.database import SessionLocal
            from app.services.gpt_extraction import extract_and_process_document
            async with _get_extraction_semaphore():
                extraction_db = SessionLocal()
                try:
                    await extract_and_process_document(
                        db=extraction_db,
                        document_id=document.id,
                        document_text="",
                        file_bytes=file_content,
                    )
                except Exception as exc:
                    logger.error("Dashboard extraction fallback failed: doc=%s, error=%s", document.id, exc)
                finally:
                    extraction_db.close()

        asyncio.create_task(_run_extraction())

    return {
        "id": str(document.id),
        "document_name": document.document_name,
        "mime_type": document.mime_type,
        "extraction_status": document.extraction_status,
        "uploaded_at": document.created_at.isoformat() if document.created_at else None,
    }


@router.get("/{token}/trends")
def dashboard_health_trends(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Get health trend data for the dashboard trends chart.

    Returns monthly completion counts derived from preventive record
    last_done_dates, a per-item timeline, and current status summary.

    Args:
        token: Dashboard access token from URL path.
        db: SQLAlchemy database session (injected).

    Returns:
        Trend data dictionary with monthly_completions, item_timeline,
        and status_summary.
    """
    try:
        return get_health_trends(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Health trends error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load trend data.")


# --- Condition CRUD ---

class ConditionMedicationInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    dose: str | None = Field(None, max_length=100)
    frequency: str | None = Field(None, max_length=100)
    route: str | None = Field(None, max_length=50)
    refill_due_date: str | None = None
    price: str | None = Field(None, max_length=20)

class ConditionMonitoringInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    frequency: str | None = Field(None, max_length=100)
    next_due_date: str | None = None
    last_done_date: str | None = None

class AddConditionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    diagnosis: str | None = Field(None, max_length=500)
    condition_type: str = Field("chronic", pattern=r"^(chronic|episodic|resolved)$")
    diagnosed_at: str | None = None
    notes: str | None = Field(None, max_length=1000)
    icon: str | None = Field(None, max_length=10)
    managed_by: str | None = Field(None, max_length=200)
    medications: list[ConditionMedicationInput] = []
    monitoring: list[ConditionMonitoringInput] = []


@router.post("/{token}/conditions")
def dashboard_add_condition(
    token: str,
    body: AddConditionRequest,
    db: Session = Depends(get_db),
):
    """Add a condition manually via dashboard."""
    try:
        dashboard_token = validate_dashboard_token(db, token)
        pet_id = dashboard_token.pet_id

        diagnosed_at = None
        if body.diagnosed_at:
            try:
                diagnosed_at = parse_date(body.diagnosed_at)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format for diagnosed_at.")

        # Check for duplicate condition name.
        existing = (
            db.query(Condition)
            .filter(Condition.pet_id == pet_id, Condition.name == body.name)
            .first()
        )
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.condition_type = body.condition_type
                existing.diagnosis = body.diagnosis
                existing.diagnosed_at = diagnosed_at
                existing.notes = body.notes
                existing.icon = body.icon
                existing.managed_by = body.managed_by
                existing.source = "manual"
                db.commit()
                return {"status": "reactivated", "condition_id": str(existing.id)}
            raise HTTPException(status_code=409, detail=f"Condition '{body.name}' already exists.")

        condition = Condition(
            pet_id=pet_id,
            name=body.name,
            diagnosis=body.diagnosis,
            condition_type=body.condition_type,
            diagnosed_at=diagnosed_at,
            notes=body.notes,
            icon=body.icon,
            managed_by=body.managed_by,
            source="manual",
        )
        db.add(condition)
        db.flush()

        for med in body.medications:
            med_refill = None
            if med.refill_due_date:
                try:
                    med_refill = parse_date(med.refill_due_date)
                except ValueError:
                    pass
            db.add(ConditionMedication(
                condition_id=condition.id,
                name=med.name,
                dose=med.dose,
                frequency=med.frequency,
                route=med.route,
                refill_due_date=med_refill,
                price=med.price,
            ))

        for mon in body.monitoring:
            mon_next = None
            mon_last = None
            if mon.next_due_date:
                try:
                    mon_next = parse_date(mon.next_due_date)
                except ValueError:
                    pass
            if mon.last_done_date:
                try:
                    mon_last = parse_date(mon.last_done_date)
                except ValueError:
                    pass
            db.add(ConditionMonitoring(
                condition_id=condition.id,
                name=mon.name,
                frequency=mon.frequency,
                next_due_date=mon_next,
                last_done_date=mon_last,
            ))

        db.commit()
        return {"status": "created", "condition_id": str(condition.id)}

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Add condition error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not add condition.")


@router.delete("/{token}/conditions/{condition_id}")
def dashboard_delete_condition(
    token: str,
    condition_id: str,
    db: Session = Depends(get_db),
):
    """Soft-deactivate a condition (set is_active=False)."""
    try:
        dashboard_token = validate_dashboard_token(db, token)
        condition = (
            db.query(Condition)
            .filter(Condition.id == condition_id, Condition.pet_id == dashboard_token.pet_id)
            .first()
        )
        if not condition:
            raise HTTPException(status_code=404, detail="Condition not found.")

        condition.is_active = False
        db.commit()
        return {"status": "deactivated", "condition_id": condition_id}

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Delete condition error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not delete condition.")


class UpdateConditionRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    diagnosis: str | None = Field(None, max_length=500)
    condition_type: str | None = Field(None, pattern=r"^(chronic|episodic|resolved)$")
    diagnosed_at: str | None = None
    notes: str | None = Field(None, max_length=1000)
    icon: str | None = Field(None, max_length=10)
    managed_by: str | None = Field(None, max_length=200)


@router.put("/{token}/conditions/{condition_id}")
def dashboard_update_condition(
    token: str,
    condition_id: str,
    body: UpdateConditionRequest,
    db: Session = Depends(get_db),
):
    """Update an existing condition."""
    try:
        dt = validate_dashboard_token(db, token)
        updates = body.dict(exclude_unset=True)
        if "diagnosed_at" in updates and updates["diagnosed_at"]:
            try:
                updates["diagnosed_at"] = parse_date(updates["diagnosed_at"])
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format.")
        return update_condition(db, dt.pet_id, condition_id, updates)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Update condition error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update condition.")


@router.post("/{token}/conditions/{condition_id}/medications")
def dashboard_add_medication(
    token: str,
    condition_id: str,
    body: ConditionMedicationInput,
    db: Session = Depends(get_db),
):
    """Add a medication to an existing condition."""
    try:
        dt = validate_dashboard_token(db, token)
        return add_condition_medication(db, dt.pet_id, condition_id, body.dict())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Add medication error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not add medication.")


@router.put("/{token}/medications/{medication_id}")
def dashboard_update_medication(
    token: str,
    medication_id: str,
    body: ConditionMedicationInput,
    db: Session = Depends(get_db),
):
    """Update an existing medication."""
    try:
        dt = validate_dashboard_token(db, token)
        return update_condition_medication(db, dt.pet_id, medication_id, body.dict(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Update medication error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update medication.")


@router.delete("/{token}/medications/{medication_id}")
def dashboard_delete_medication(
    token: str,
    medication_id: str,
    db: Session = Depends(get_db),
):
    """Delete a medication."""
    try:
        dt = validate_dashboard_token(db, token)
        return delete_condition_medication(db, dt.pet_id, medication_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Delete medication error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not delete medication.")


@router.post("/{token}/conditions/{condition_id}/monitoring")
def dashboard_add_monitoring(
    token: str,
    condition_id: str,
    body: ConditionMonitoringInput,
    db: Session = Depends(get_db),
):
    """Add a monitoring item to an existing condition."""
    try:
        dt = validate_dashboard_token(db, token)
        return add_condition_monitoring(db, dt.pet_id, condition_id, body.dict())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Add monitoring error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not add monitoring item.")


@router.put("/{token}/monitoring/{monitoring_id}")
def dashboard_update_monitoring(
    token: str,
    monitoring_id: str,
    body: ConditionMonitoringInput,
    db: Session = Depends(get_db),
):
    """Update a monitoring item."""
    try:
        dt = validate_dashboard_token(db, token)
        return update_condition_monitoring(db, dt.pet_id, monitoring_id, body.dict(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Update monitoring error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update monitoring item.")


@router.delete("/{token}/monitoring/{monitoring_id}")
def dashboard_delete_monitoring(
    token: str,
    monitoring_id: str,
    db: Session = Depends(get_db),
):
    """Delete a monitoring item."""
    try:
        dt = validate_dashboard_token(db, token)
        return delete_condition_monitoring(db, dt.pet_id, monitoring_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Delete monitoring error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not delete monitoring item.")


# --- Contact CRUD ---

class AddContactRequest(BaseModel):
    role: str = Field("veterinarian", pattern=r"^(veterinarian|groomer|trainer|specialist|other)$")
    name: str = Field(..., min_length=1, max_length=200)
    clinic_name: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=500)

class UpdateContactRequest(BaseModel):
    role: str | None = Field(None, pattern=r"^(veterinarian|groomer|trainer|specialist|other)$")
    name: str | None = Field(None, min_length=1, max_length=200)
    clinic_name: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=500)


@router.post("/{token}/contacts")
def dashboard_add_contact(
    token: str,
    body: AddContactRequest,
    db: Session = Depends(get_db),
):
    """Add a contact manually via dashboard."""
    try:
        dashboard_token = validate_dashboard_token(db, token)
        pet_id = dashboard_token.pet_id

        existing = (
            db.query(Contact)
            .filter(Contact.pet_id == pet_id, Contact.name == body.name, Contact.role == body.role)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail=f"Contact '{body.name}' ({body.role}) already exists.")

        contact = Contact(
            pet_id=pet_id,
            role=body.role,
            name=body.name,
            clinic_name=body.clinic_name,
            phone=body.phone,
            email=body.email,
            address=body.address,
            source="manual",
        )
        db.add(contact)
        db.commit()
        return {"status": "created", "contact_id": str(contact.id)}

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Add contact error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not add contact.")


@router.put("/{token}/contacts/{contact_id}")
def dashboard_update_contact(
    token: str,
    contact_id: str,
    body: UpdateContactRequest,
    db: Session = Depends(get_db),
):
    """Update a contact via dashboard."""
    try:
        dashboard_token = validate_dashboard_token(db, token)
        contact = (
            db.query(Contact)
            .filter(Contact.id == contact_id, Contact.pet_id == dashboard_token.pet_id)
            .first()
        )
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found.")

        if body.role is not None:
            contact.role = body.role
        if body.name is not None:
            contact.name = body.name
        if body.clinic_name is not None:
            contact.clinic_name = body.clinic_name
        if body.phone is not None:
            contact.phone = body.phone
        if body.email is not None:
            contact.email = body.email
        if body.address is not None:
            contact.address = body.address

        db.commit()
        return {"status": "updated", "contact_id": contact_id}

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Update contact error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update contact.")


@router.delete("/{token}/contacts/{contact_id}")
def dashboard_delete_contact(
    token: str,
    contact_id: str,
    db: Session = Depends(get_db),
):
    """Delete a contact via dashboard."""
    try:
        dashboard_token = validate_dashboard_token(db, token)
        contact = (
            db.query(Contact)
            .filter(Contact.id == contact_id, Contact.pet_id == dashboard_token.pet_id)
            .first()
        )
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found.")

        db.delete(contact)
        db.commit()
        return {"status": "deleted", "contact_id": contact_id}

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Delete contact error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not delete contact.")


# --- Weight History ---

class WeightEntryRequest(BaseModel):
    weight: float = Field(..., gt=0, le=999.99)
    recorded_at: str = Field(..., min_length=1)
    note: str | None = Field(None, max_length=255)


@router.get("/{token}/weight-history")
async def dashboard_weight_history(
    token: str,
    db: Session = Depends(get_db),
):
    """Get weight history entries and ideal range for a pet."""
    try:
        dt = validate_dashboard_token(db, token)
        from app.models.pet import Pet
        pet = db.query(Pet).filter(Pet.id == dt.pet_id).first()
        return await get_weight_history(db, dt.pet_id, pet)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Weight history error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load weight history.")


@router.post("/{token}/weight-history")
async def dashboard_add_weight(
    token: str,
    body: WeightEntryRequest,
    db: Session = Depends(get_db),
):
    """Add a weight measurement entry."""
    try:
        dt = validate_dashboard_token(db, token)
        return await add_weight_entry(db, dt.pet_id, body.weight, body.recorded_at, body.note)
    except ValueError as e:
        if "date" in str(e).lower():
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Add weight error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not add weight entry.")


# --- Preventive Frequency ---

class PreventiveFrequencyRequest(BaseModel):
    item_name: str = Field(..., min_length=1)
    recurrence_days: int = Field(..., gt=0, le=1095)


@router.patch("/{token}/preventive-frequency")
def dashboard_update_frequency(
    token: str,
    body: PreventiveFrequencyRequest,
    db: Session = Depends(get_db),
):
    """Update custom recurrence for a preventive item (e.g., vaccine frequency)."""
    try:
        dt = validate_dashboard_token(db, token)
        from app.models.preventive_master import PreventiveMaster
        from app.models.preventive_record import PreventiveRecord

        result = (
            db.query(PreventiveRecord, PreventiveMaster)
            .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
            .filter(
                PreventiveRecord.pet_id == dt.pet_id,
                PreventiveMaster.item_name == body.item_name,
                PreventiveRecord.status != "cancelled",
            )
            .order_by(
                PreventiveRecord.last_done_date.desc().nullslast(),
                PreventiveRecord.next_due_date.desc().nullslast(),
                PreventiveRecord.created_at.desc().nullslast(),
                PreventiveRecord.id.desc(),
            )
            .first()
        )
        if not result:
            raise HTTPException(status_code=404, detail="Preventive record not found.")

        record, master = result
        record.custom_recurrence_days = body.recurrence_days

        # Recalculate next_due_date if last_done_date exists
        if record.last_done_date:
            from datetime import date as date_type
            from datetime import timedelta
            record.next_due_date = record.last_done_date + timedelta(days=body.recurrence_days)
            today = date_type.today()
            if record.next_due_date < today:
                record.status = "overdue"
            elif (record.next_due_date - today).days <= CARE_PLAN_DUE_SOON_DAYS:
                record.status = "upcoming"
            else:
                record.status = "up_to_date"
        db.commit()

        return {
            "status": "updated",
            "item_name": body.item_name,
            "recurrence_days": body.recurrence_days,
            "next_due_date": str(record.next_due_date) if record.next_due_date else None,
            "record_status": record.status,
        }

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Frequency update error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update frequency.")


# --- Medicine Resolve for Cart (ProductSelectorCard) ---

def _medicine_suitable_for_pet(medicine, pet, today) -> bool:
    """
    Return False when the medicine's notes or product_name explicitly disqualify
    this pet based on species, minimum weight, weight range, or minimum age.

    Filtering rules (all skipped when the relevant pet field is None):
    - Species exclusion: "not for cats" / "toxic to cats" in notes
    - Min weight:        "min weight Xkg" in notes
    - Weight range:      "X–Y kg" in product_name (only when pet.weight is known)
    - Min age:           "min age X weeks" / "from X weeks of age" in notes
    """
    import re
    notes_lower = (medicine.notes or "").lower()

    # Species exclusion (life_stage_tags already pre-filters, but some notes
    # contain explicit cross-species toxicity warnings, e.g. Advantix)
    if pet.species == "cat" and ("not for cats" in notes_lower or "toxic to cats" in notes_lower):
        return False
    if pet.species == "dog" and "not for dogs" in notes_lower:
        return False

    if pet.weight is not None:
        pet_weight = float(pet.weight)

        # Minimum weight floor from notes: "min weight 2kg", "min weight 1.5kg"
        m = re.search(r"min(?:imum)?\s*weight\s*(\d+(?:\.\d+)?)\s*kg", notes_lower)
        if m and pet_weight < float(m.group(1)):
            return False

        # Weight range from product_name: "NexGard 2–4 kg", "Frontline Plus 2–10 kg"
        # Unicode en-dash (–) and ASCII hyphen (-) both matched
        r = re.search(
            r"(\d+(?:\.\d+)?)\s*[–\-]\s*(\d+(?:\.\d+)?)\s*kg",
            medicine.product_name.lower(),
        )
        if r:
            rmin, rmax = float(r.group(1)), float(r.group(2))
            if not (rmin <= pet_weight <= rmax):
                return False

    if pet.dob is not None:
        age_weeks = (today - pet.dob).days // 7

        # "min age 8 weeks", "minimum age 7 weeks"
        m = re.search(r"min(?:imum)?\s*age\s*(\d+)\s*weeks?", notes_lower)
        if m and age_weeks < int(m.group(1)):
            return False

        # "for puppies from 2 weeks of age"
        m2 = re.search(r"from\s*(\d+)\s*weeks?\s*of\s*age", notes_lower)
        if m2 and age_weeks < int(m2.group(1)):
            return False

    return True


@router.get("/{token}/medicines/resolve")
def dashboard_resolve_medicines(
    token: str,
    item_name: str,
    db: Session = Depends(get_db),
):
    """
    Return medicine products (from product_medicines) for a Flea & Tick or
    Deworming Quick Fix item.  Products are filtered by:
      1. item type  (tick_flea or deworming — combined medicines appear in both)
      2. pet species via life_stage_tags
      3. pet details via notes-based suitability filter (_medicine_suitable_for_pet)

    Response shape matches products/resolve-by-micronutrient so ProductSelectorCard
    can be reused without changes.
    """
    from app.models.product_medicines import ProductMedicines
    from datetime import date as _date
    from sqlalchemy import or_

    try:
        pet = _get_pet_for_dashboard_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")

    item_name_norm = (item_name or "").strip().lower()
    is_tick_flea = "tick" in item_name_norm or "flea" in item_name_norm
    is_deworming = "deworm" in item_name_norm

    if not is_tick_flea and not is_deworming:
        return {"products": []}

    query = db.query(ProductMedicines).filter(ProductMedicines.active.is_(True))

    if is_tick_flea:
        # Include pure tick/flea AND combined products (Flea+Deworming, Tick+Flea+Deworming)
        query = query.filter(
            or_(
                ProductMedicines.type.ilike("%Tick%"),
                ProductMedicines.type.ilike("%Flea%"),
            )
        )
    else:
        # Include pure deworming AND all combined products that cover deworming
        query = query.filter(ProductMedicines.type.ilike("%Deworming%"))

    # Filter by pet species via life_stage_tags
    query = query.filter(ProductMedicines.life_stage_tags.ilike(f"%{pet.species}%"))

    medicines = query.order_by(ProductMedicines.popularity_rank.asc()).all()

    # Apply notes + weight-range suitability filter
    today = _date.today()
    suitable = [m for m in medicines if _medicine_suitable_for_pet(m, pet, today)]

    if not suitable:
        return {"products": []}

    min_rank = min(m.popularity_rank for m in suitable if m.popularity_rank is not None) if any(
        m.popularity_rank is not None for m in suitable
    ) else None

    products = []
    for m in suitable:
        discounted = m.discounted_paise // 100
        mrp = m.mrp_paise // 100
        ppu_paise = m.price_per_unit_paise if m.price_per_unit_paise else m.discounted_paise
        price_per_unit = ppu_paise // 100

        is_highlighted = (
            m.popularity_rank is not None and m.popularity_rank == min_rank
        )

        products.append({
            "sku_id": m.sku_id,
            "category": "medicine",
            "brand_name": m.brand_name,
            "product_name": m.product_name,
            "pack_size": m.pack_size or "",
            "mrp": mrp,
            "discounted_price": discounted,
            "price_per_unit": price_per_unit,
            "unit_label": "tablet",
            "in_stock": bool(m.in_stock),
            "vet_diet_flag": False,
            "is_highlighted": is_highlighted,
            "highlight_reason": "Most Popular" if is_highlighted else None,
            "medicine_type": m.type,
            "notes": m.notes or None,
        })

    logger.info(
        "medicines/resolve item_name=%r pet_species=%s -> %d products",
        item_name, pet.species, len(products),
    )
    return {"products": products}


# --- Medicine Name Update (AI-based due date) ---

class MedicineNameRequest(BaseModel):
    item_name: str = Field(..., min_length=1)
    medicine_name: str = Field(..., min_length=1, max_length=200)


@router.get("/{token}/preventive-medicine-options")
def dashboard_get_preventive_medicine_options(
    token: str,
    item_name: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Return medicine options for medicine-dependent preventive items.

    Medicines are dynamically sourced from the product_medicines table,
    filtered by type (deworming, tick/flea) and active status.
    """
    from app.models.product_medicines import ProductMedicines

    try:
        _get_pet_for_dashboard_token(db, token)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        item_name_norm = (item_name or "").strip().lower()
        if not item_name_norm:
            raise HTTPException(status_code=400, detail="item_name is required")

        # Determine preventive type from item_name
        is_deworming = "deworm" in item_name_norm
        is_flea_tick = "flea" in item_name_norm or "tick" in item_name_norm

        if not (is_deworming or is_flea_tick):
            # Unknown item type
            options = ["Other"]
            logger.warning("Unknown preventive item type: %s", item_name)
            return {"item_name": item_name, "options": options}

        # Query product_medicines for matching type
        query = db.query(ProductMedicines).filter(
            ProductMedicines.active == True
        )

        if is_deworming:
            # Filter for deworming products
            query = query.filter(
                ProductMedicines.type.contains("Deworming")
            )
        else:  # is_flea_tick
            # Filter for tick/flea products (include combined products)
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    ProductMedicines.type.contains("Tick"),
                    ProductMedicines.type.contains("Flea")
                )
            )

        medicines = query.order_by(ProductMedicines.popularity_rank.asc()).all()
        options = [m.product_name for m in medicines]
        options.append("Other")  # Always include custom option

        logger.info(
            "medicine_options request item_name=%r -> %d options from product_medicines",
            item_name, len(options) - 1,
        )
        return {"item_name": item_name, "options": options}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Preventive medicine options error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load medicine options.")


@router.patch("/{token}/preventive-medicine")
def dashboard_update_medicine_name(
    token: str,
    body: MedicineNameRequest,
    db: Session = Depends(get_db),
):
    """
    Update medicine name for a medicine-dependent preventive item.
    Uses AI to calculate the recommended recurrence based on species + medicine.
    """
    try:
        dt = validate_dashboard_token(db, token)
        from app.models.pet import Pet
        from app.models.preventive_master import PreventiveMaster
        from app.models.preventive_record import PreventiveRecord

        result = (
            db.query(PreventiveRecord, PreventiveMaster)
            .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
            .filter(
                PreventiveRecord.pet_id == dt.pet_id,
                PreventiveMaster.item_name == body.item_name,
                PreventiveRecord.status != "cancelled",
            )
            .order_by(
                PreventiveRecord.last_done_date.desc().nullslast(),
                PreventiveRecord.next_due_date.desc().nullslast(),
                PreventiveRecord.created_at.desc().nullslast(),
                PreventiveRecord.id.desc(),
            )
            .first()
        )
        if not result:
            raise HTTPException(status_code=404, detail="Preventive record not found.")

        record, master = result

        if not master.medicine_dependent:
            raise HTTPException(status_code=400, detail="This preventive item does not support medicine updates.")

        pet = db.query(Pet).filter(Pet.id == dt.pet_id).first()
        species = pet.species if pet else "dog"

        # Save the medicine name
        record.medicine_name = body.medicine_name

        def _normalize_medicine(value: str | None) -> str:
            return " ".join((value or "").strip().lower().split())

        def _recompute_record_status(target_record: PreventiveRecord, recurrence_days: int) -> None:
            if not target_record.last_done_date:
                return

            from datetime import date as date_type
            from datetime import timedelta

            target_record.next_due_date = target_record.last_done_date + timedelta(days=recurrence_days)
            today = date_type.today()
            if target_record.next_due_date < today:
                target_record.status = "overdue"
            elif (target_record.next_due_date - today).days <= CARE_PLAN_DUE_SOON_DAYS:
                target_record.status = "upcoming"
            else:
                target_record.status = "up_to_date"

        # Look up recurrence from product catalog; fall back to GPT for unknown medicines.
        from app.services.medicine_recurrence_service import get_medicine_recurrence
        ai_days = get_medicine_recurrence(
            species=species,
            item_type=master.item_name,
            medicine_name=body.medicine_name,
            default_days=master.recurrence_days,
            db=db,
        )

        record.custom_recurrence_days = ai_days

        # Recalculate next_due_date/status for updated record.
        _recompute_record_status(record, ai_days)

        # Dual-use medicines (deworming + flea/tick) must share one recurrence
        # when both records use the same medicine; different medicines keep
        # independent frequencies.
        from app.services.gpt_extraction import _get_preventive_categories_for_medicine

        medicine_categories = _get_preventive_categories_for_medicine(body.medicine_name)
        is_dual_medicine = {"deworming", "flea_tick"}.issubset(medicine_categories)
        selected_name_norm = _normalize_medicine(body.medicine_name)

        if is_dual_medicine:
            current_item_norm = (master.item_name or "").strip().lower()
            if "deworm" in current_item_norm:
                opposite_item_pattern = "%flea%"
            elif "flea" in current_item_norm or "tick" in current_item_norm:
                opposite_item_pattern = "%deworm%"
            else:
                opposite_item_pattern = None

            sibling_result = None
            if opposite_item_pattern:
                sibling_result = (
                    db.query(PreventiveRecord, PreventiveMaster)
                    .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
                    .filter(
                        PreventiveRecord.pet_id == dt.pet_id,
                        PreventiveRecord.id != record.id,
                        PreventiveRecord.status != "cancelled",
                        PreventiveMaster.medicine_dependent.is_(True),
                        sqlfunc.lower(PreventiveMaster.item_name).like(opposite_item_pattern),
                    )
                    .order_by(
                        PreventiveRecord.last_done_date.desc().nullslast(),
                        PreventiveRecord.next_due_date.desc().nullslast(),
                        PreventiveRecord.created_at.desc().nullslast(),
                        PreventiveRecord.id.desc(),
                    )
                    .first()
                )

            if sibling_result:
                sibling_record, _ = sibling_result
                sibling_name_norm = _normalize_medicine(sibling_record.medicine_name)
                if sibling_name_norm and sibling_name_norm == selected_name_norm:
                    sibling_record.custom_recurrence_days = ai_days
                    _recompute_record_status(sibling_record, ai_days)

        db.commit()

        return {
            "status": "updated",
            "item_name": body.item_name,
            "medicine_name": body.medicine_name,
            "recurrence_days": ai_days,
            "next_due_date": str(record.next_due_date) if record.next_due_date else None,
            "record_status": record.status,
        }

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Medicine name update error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update medicine name.")


# --- Diet Items CRUD ---

class DietItemRequest(BaseModel):
    type: str = Field("packaged", pattern=r"^(packaged|homemade|supplement)$")
    label: str = Field(..., min_length=1, max_length=200)
    detail: str | None = Field(None, max_length=200)
    icon: str | None = Field(None, max_length=10)

class DietItemUpdateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    detail: str | None = Field(None, max_length=200)


@router.get("/{token}/diet-items")
async def dashboard_diet_items(
    token: str,
    db: Session = Depends(get_db),
):
    """Get diet items for a pet."""
    try:
        dt = validate_dashboard_token(db, token)
        return await get_diet_items(db, dt.pet_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Diet items error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load diet items.")


async def _refresh_recognition_bullets(pet_id) -> None:
    """Recompute and cache recognition_bullets after a diet item change.

    Opens its own DB session so it can safely run after the request session closes.
    Pure-DB call — no GPT.
    """
    from app.database import SessionLocal
    from uuid import UUID as _UUID
    _db = SessionLocal()
    try:
        _pet = _db.query(Pet).filter(Pet.id == pet_id).first()
        if not _pet:
            return
        bullets = await generate_recognition_bullets(_db, _pet)
        _upsert_insight(_db, pet_id, "recognition_bullets", bullets)
    except Exception as exc:
        logger.warning("Failed to refresh recognition_bullets for pet=%s: %s", pet_id, exc)
    finally:
        _db.close()


async def _refresh_nutrition_analysis(pet_id) -> None:
    """Recompute and cache nutrition_analysis after a diet item change.

    Opens its own DB session so it can safely run after the request session closes.
    AI-generated — may take up to 30s.
    """
    from app.database import SessionLocal
    from app.services.nutrition_service import analyze_nutrition
    _db = SessionLocal()
    try:
        analysis = await analyze_nutrition(_db, pet_id)
        _upsert_insight(_db, pet_id, "nutrition_analysis", analysis)
        logger.info("Refreshed nutrition_analysis cache for pet=%s", pet_id)
    except Exception as exc:
        logger.warning("Failed to refresh nutrition_analysis for pet=%s: %s", pet_id, exc)
    finally:
        _db.close()


@router.post("/{token}/diet-items")
async def dashboard_add_diet_item(
    token: str,
    body: DietItemRequest,
    db: Session = Depends(get_db),
):
    """Add a diet item."""
    try:
        dt = validate_dashboard_token(db, token)
        result = await add_diet_item(db, dt.pet_id, body.type, body.label, body.detail, body.icon)
        asyncio.create_task(_refresh_recognition_bullets(dt.pet_id))
        asyncio.create_task(_refresh_nutrition_analysis(dt.pet_id))
        return result
    except ValueError as e:
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Add diet item error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not add diet item.")


@router.put("/{token}/diet-items/{item_id}")
async def dashboard_update_diet_item(
    token: str,
    item_id: str,
    body: DietItemUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update a diet item."""
    try:
        dt = validate_dashboard_token(db, token)
        result = await update_diet_item(db, item_id, dt.pet_id, body.label, body.detail)
        asyncio.create_task(_refresh_recognition_bullets(dt.pet_id))
        asyncio.create_task(_refresh_nutrition_analysis(dt.pet_id))
        return result
    except ValueError:
        raise HTTPException(status_code=404, detail="Diet item not found.")
    except Exception as e:
        logger.error("Update diet item error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update diet item.")


@router.delete("/{token}/diet-items/{item_id}")
async def dashboard_delete_diet_item(
    token: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    """Delete a diet item."""
    try:
        dt = validate_dashboard_token(db, token)
        await delete_diet_item(db, item_id, dt.pet_id)
        asyncio.create_task(_refresh_recognition_bullets(dt.pet_id))
        asyncio.create_task(_refresh_nutrition_analysis(dt.pet_id))
        return {"status": "deleted"}
    except ValueError:
        raise HTTPException(status_code=404, detail="Diet item not found.")
    except Exception as e:
        logger.error("Delete diet item error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not delete diet item.")


# --- Hygiene Preferences ---

class HygienePreferenceRequest(BaseModel):
    freq: int = Field(..., gt=0, le=365)
    unit: str = Field("month", pattern=r"^(day|week|month|year)$")
    reminder: bool = False
    last_done: str | None = None

class HygieneAddRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    icon: str = Field("🧹", max_length=10)
    category: str = Field("daily", pattern=r"^(daily|periodic)$")
    freq: int = Field(1, gt=0, le=365)
    unit: str = Field("month", pattern=r"^(day|week|month|year)$")

class HygieneDateRequest(BaseModel):
    last_done: str = Field(..., min_length=1)


@router.get("/{token}/hygiene-preferences")
async def dashboard_hygiene_preferences(
    token: str,
    db: Session = Depends(get_db),
):
    """Get hygiene preferences for a pet, with AI-generated tips."""
    try:
        dt = validate_dashboard_token(db, token)
        # Fetch pet info for breed-specific tip generation
        from app.models.pet import Pet
        pet = db.query(Pet).filter(Pet.id == dt.pet_id).first()
        species = pet.species if pet else None
        breed = pet.breed if pet else None
        dob = pet.dob if pet else None
        return await get_hygiene_preferences(db, dt.pet_id, species=species, breed=breed, dob=dob)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Hygiene preferences error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load hygiene preferences.")


@router.put("/{token}/hygiene-preferences/{item_id}")
async def dashboard_update_hygiene(
    token: str,
    item_id: str,
    body: HygienePreferenceRequest,
    db: Session = Depends(get_db),
):
    """Update or create a hygiene preference."""
    try:
        dt = validate_dashboard_token(db, token)
        return await upsert_hygiene_preference(db, dt.pet_id, item_id, body.freq, body.unit, body.reminder, body.last_done)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Update hygiene error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update hygiene preference.")


@router.post("/{token}/hygiene-preferences")
async def dashboard_add_hygiene_item(
    token: str,
    body: HygieneAddRequest,
    db: Session = Depends(get_db),
):
    """Add a custom hygiene item for a pet."""
    try:
        dt = validate_dashboard_token(db, token)
        return await add_hygiene_item(db, dt.pet_id, body.name, body.icon, body.category, body.freq, body.unit)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("Add hygiene item error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not add hygiene item.")


@router.patch("/{token}/hygiene-preferences/{item_id}/date")
async def dashboard_update_hygiene_date(
    token: str,
    item_id: str,
    body: HygieneDateRequest,
    db: Session = Depends(get_db),
):
    """Update last done date for a hygiene item."""
    try:
        dt = validate_dashboard_token(db, token)
        return await update_hygiene_date(db, dt.pet_id, item_id, body.last_done)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Update hygiene date error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update hygiene date.")


@router.delete("/{token}/hygiene-preferences/{item_id}")
async def dashboard_delete_hygiene_item(
    token: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    """Delete a custom hygiene item. Default items cannot be deleted."""
    try:
        dt = validate_dashboard_token(db, token)
        return await delete_hygiene_item(db, dt.pet_id, item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Delete hygiene item error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not delete hygiene item.")


# --- Nutrition Analysis ---

@router.get("/{token}/nutrition-analysis")
async def dashboard_nutrition_analysis(
    token: str,
    db: Session = Depends(get_db),
):
    """Get nutrition analysis for a pet based on their diet items.

    Served from the pet_ai_insights cache (populated by precompute_service);
    falls back to a live compute if the cache row is missing.
    """
    try:
        dt = validate_dashboard_token(db, token)
        cached = db.execute(
            text(
                "SELECT content_json FROM pet_ai_insights "
                "WHERE pet_id = :pet_id AND insight_type = 'nutrition_analysis' "
                "LIMIT 1"
            ),
            {"pet_id": str(dt.pet_id)},
        ).fetchone()
        if cached and cached[0]:
            return cached[0]
        return await analyze_nutrition(db, dt.pet_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Nutrition analysis error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not generate nutrition analysis.")


@router.get("/{token}/nutrition-importance")
async def dashboard_nutrition_importance(
    token: str,
    db: Session = Depends(get_db),
):
    """Return an AI-generated note on why nutrition matters for this specific pet (cached 30 days)."""
    try:
        dt = validate_dashboard_token(db, token)
        return await get_or_generate_nutrition_importance(db, dt.pet_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Nutrition importance error: %s", str(e))
        return {
            "note": (
                "Good nutrition is the foundation of your pet's health at every life stage. "
                "The right balance of proteins, fats, vitamins, and minerals supports their "
                "energy, immune system, and long-term wellbeing."
            )
        }


# --- Condition Timeline ---

@router.get("/{token}/condition-timeline")
async def dashboard_condition_timeline(
    token: str,
    db: Session = Depends(get_db),
):
    """Get chronological condition management timeline."""
    try:
        dt = validate_dashboard_token(db, token)
        return await get_condition_timeline(db, dt.pet_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Condition timeline error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load condition timeline.")


# --- Condition Recommendations ---

@router.get("/{token}/condition-recommendations")
async def dashboard_condition_recommendations(
    token: str,
    db: Session = Depends(get_db),
):
    """Get AI-generated health recommendations based on conditions."""
    try:
        dt = validate_dashboard_token(db, token)
        return await get_condition_recommendations(db, dt.pet_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Condition recommendations error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not generate recommendations.")


# --- Last Vet Visit ---

@router.get("/{token}/last-vet-visit")
def dashboard_last_vet_visit(
    token: str,
    db: Session = Depends(get_db),
):
    """Get last vet visit info for condition management."""
    try:
        dt = validate_dashboard_token(db, token)
        return get_last_vet_visit(db, dt.pet_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Last vet visit error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load vet visit info.")


# --- AI Insights: Health Summary ---

@router.get("/{token}/health-summary")
async def dashboard_health_summary(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Return a GPT-generated 1-2 sentence health insight for the Conditions tab.

    Cached for 7 days per pet. Generates on first call.
    Returns: {"summary": "<text>"}
    """
    try:
        dt = validate_dashboard_token(db, token)
        # get_or_generate_insight handles cache check internally — no need to duplicate it here
        data = await get_dashboard_data(db, token)
        return await get_or_generate_insight(
            db=db,
            pet_id=dt.pet_id,
            insight_type="conditions_summary",
            pet=data["pet"],
            conditions=data["conditions"],
            health_score=data.get("health_score"),
            force=False,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Health summary error: %s", str(e), exc_info=True)
        return {"summary": "Health summary is currently unavailable."}


# --- AI Insights: Vet Questions ---

@router.get("/{token}/vet-questions")
async def dashboard_vet_questions(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Return GPT-generated "Ask the Vet" questions for the Conditions tab.

    Cached for 7 days per pet. Generates on first call.
    Returns: list of {priority, icon, q, context}
    """
    try:
        dt = validate_dashboard_token(db, token)
        # get_or_generate_insight handles cache check internally — no need to duplicate it here
        data = await get_dashboard_data(db, token)
        result = await get_or_generate_insight(
            db=db,
            pet_id=dt.pet_id,
            insight_type="vet_questions",
            pet=data["pet"],
            conditions=data["conditions"],
            health_score=data.get("health_score"),
            force=False,
        )
        return result if isinstance(result, list) else []
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Vet questions error: %s", str(e), exc_info=True)
        return []


@router.post("/{token}/vet-questions/regenerate")
async def dashboard_regenerate_vet_questions(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Force-regenerate GPT vet questions and update the DB cache.

    Triggered by the "Regenerate" button in the dashboard.
    Returns: list of {priority, icon, q, context}
    """
    try:
        dt = validate_dashboard_token(db, token)
        data = await get_dashboard_data(db, token)
        result = await get_or_generate_insight(
            db=db,
            pet_id=dt.pet_id,
            insight_type="vet_questions",
            pet=data["pet"],
            conditions=data["conditions"],
            health_score=data.get("health_score"),
            force=True,
        )
        return result if isinstance(result, list) else []
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Regenerate vet questions error: %s", str(e), exc_info=True)
        return []


# --- Nudges ---

@router.get("/{token}/nudges")
def dashboard_nudges(
    token: str,
    db: Session = Depends(get_db),
):
    """Get actionable health nudges for a pet."""
    try:
        dt = validate_dashboard_token(db, token)
        return generate_nudges(db, dt.pet_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Nudges error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not generate nudges.")


@router.patch("/{token}/nudges/{nudge_id}/dismiss")
def dashboard_dismiss_nudge(
    token: str,
    nudge_id: str,
    db: Session = Depends(get_db),
):
    """Dismiss a nudge."""
    try:
        dt = validate_dashboard_token(db, token)
        nudge = (
            db.query(Nudge)
            .filter(Nudge.id == nudge_id, Nudge.pet_id == dt.pet_id)
            .first()
        )
        if not nudge:
            raise HTTPException(status_code=404, detail="Nudge not found.")
        nudge.dismissed = True
        db.commit()
        return {"status": "dismissed"}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Dismiss nudge error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not dismiss nudge.")


# --- Cart & Orders ---

@router.get("/{token}/cart")
async def dashboard_cart(
    token: str,
    db: Session = Depends(get_db),
):
    """Get cart items for a pet."""
    try:
        dt = validate_dashboard_token(db, token)
        return await get_cart(db, dt.pet_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Cart error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load cart.")


@router.post("/{token}/cart/toggle/{product_id}")
async def dashboard_toggle_cart(
    token: str,
    product_id: str,
    db: Session = Depends(get_db),
):
    """Toggle an item in/out of cart."""
    try:
        dt = validate_dashboard_token(db, token)
        return await toggle_cart_item(db, dt.pet_id, product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Cart item not found.")
    except Exception as e:
        logger.error("Toggle cart error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not toggle cart item.")


class QuantityRequest(BaseModel):
    quantity: int = Field(..., ge=1, le=99)


@router.patch("/{token}/cart/{product_id}/quantity")
async def dashboard_update_quantity(
    token: str,
    product_id: str,
    body: QuantityRequest,
    db: Session = Depends(get_db),
):
    """Update cart item quantity."""
    try:
        dt = validate_dashboard_token(db, token)
        return await update_quantity(db, dt.pet_id, product_id, body.quantity)
    except ValueError:
        raise HTTPException(status_code=404, detail="Cart item not found.")
    except Exception as e:
        logger.error("Update quantity error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not update quantity.")


# Valid coupon codes and their discount percentages
VALID_COUPONS: dict[str, int] = {
    "PETCIRCLE10": 10,
    "WELCOME10": 10,
    "SAVE10": 10,
    "CARE10": 10,
}


class CouponRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)


@router.post("/{token}/cart/apply-coupon")
async def dashboard_apply_coupon(
    token: str,
    body: CouponRequest,
    db: Session = Depends(get_db),
):
    """Apply coupon code to cart. Returns discount_percent for valid codes, valid=False otherwise."""
    try:
        validate_dashboard_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")

    code = body.code.strip().upper()
    discount = VALID_COUPONS.get(code)
    if discount is None:
        return {"valid": False, "discount_percent": 0, "code": code}
    return {"valid": True, "discount_percent": discount, "code": code}


class PlaceOrderRequest(BaseModel):
    payment_method: str = Field(..., pattern=r"^(upi|card|netbanking|cod)$")
    address: dict | None = None
    coupon: str | None = None


@router.post("/{token}/place-order")
async def dashboard_place_order(
    token: str,
    body: PlaceOrderRequest,
    db: Session = Depends(get_db),
):
    """Place a COD order. For UPI/card/netbanking use /create-payment instead."""
    try:
        dt = validate_dashboard_token(db, token)
        result = await place_order(db, dt.pet_id, dt.user_id, body.payment_method, body.address, body.coupon)
        # Save checkout preferences so next checkout can prefill these fields.
        # Best-effort — never blocks the order response.
        try:
            user = db.query(User).filter(User.id == dt.user_id).first()
            if user:
                if body.address and body.address.get("address"):
                    user.delivery_address = body.address["address"]
                user.payment_method_pref = "cod"
                db.commit()
        except Exception as pref_err:
            logger.warning("Failed to save COD checkout preferences: %s", str(pref_err))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Place order error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not place order.")


class CreatePaymentRequest(BaseModel):
    payment_method: str = Field(..., pattern=r"^(upi|card|netbanking)$")
    address: dict | None = None
    coupon: str | None = None
    coupon_discount_percent: int = Field(default=0, ge=0, le=100)


class VerifyPaymentRequest(BaseModel):
    order_db_id: str = Field(..., min_length=1)
    razorpay_order_id: str = Field(..., min_length=1)
    razorpay_payment_id: str = Field(..., min_length=1)
    razorpay_signature: str = Field(..., min_length=1)


@router.post("/{token}/create-payment")
async def dashboard_create_payment(
    token: str,
    body: CreatePaymentRequest,
    db: Session = Depends(get_db),
):
    """
    Create a Razorpay order for UPI / card / netbanking payments.

    Returns razorpay_order_id, amount (paise), currency, key_id.
    Frontend opens Razorpay checkout with these details.
    On payment success, call /verify-payment to confirm.
    """
    try:
        dt = validate_dashboard_token(db, token)
        result = await create_razorpay_payment(
            db,
            pet_id=dt.pet_id,
            user_id=dt.user_id,
            payment_method=body.payment_method,
            address=body.address,
            coupon=body.coupon,
            coupon_discount_percent=body.coupon_discount_percent,
        )
        # Save address and payment method preference eagerly so the next
        # checkout can prefill them even if payment is abandoned.
        # Best-effort — never blocks the response.
        try:
            user = db.query(User).filter(User.id == dt.user_id).first()
            if user:
                if body.address and body.address.get("address"):
                    user.delivery_address = body.address["address"]
                user.payment_method_pref = body.payment_method
                db.commit()
        except Exception as pref_err:
            logger.warning("Failed to save payment method preference: %s", str(pref_err))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error("Razorpay config error: %s", str(e))
        raise HTTPException(status_code=503, detail="Payment gateway not configured.")
    except Exception as e:
        logger.error("Create payment error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not initiate payment.")


@router.post("/{token}/verify-payment")
async def dashboard_verify_payment(
    token: str,
    body: VerifyPaymentRequest,
    db: Session = Depends(get_db),
):
    """
    Verify Razorpay payment signature and confirm the order.

    Called by frontend after Razorpay checkout succeeds.
    Verifies the HMAC-SHA256 signature, marks order as paid, clears cart.
    After verification, fetches UPI VPA from Razorpay API and saves it
    encrypted so the next UPI checkout can prefill the VPA.
    """
    try:
        dt = validate_dashboard_token(db, token)
        result = await verify_razorpay_payment(
            db,
            pet_id=dt.pet_id,
            order_db_id=body.order_db_id,
            razorpay_order_id=body.razorpay_order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
        )
        # Fetch payment details from Razorpay to get the UPI VPA and save
        # it encrypted for next-checkout prefill. Best-effort — never blocks.
        try:
            if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
                rzp_client = razorpay_sdk.Client(
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
                )
                payment_details = rzp_client.payment.fetch(body.razorpay_payment_id)
                if payment_details.get("method") == "upi" and payment_details.get("vpa"):
                    user = db.query(User).filter(User.id == dt.user_id).first()
                    if user:
                        user.saved_upi_id = encrypt_field(payment_details["vpa"])
                        db.commit()
        except Exception as pref_err:
            logger.warning("Failed to save UPI VPA preference: %s", str(pref_err))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error("Razorpay verify config error: %s", str(e))
        raise HTTPException(status_code=503, detail="Payment gateway not configured.")
    except Exception as e:
        logger.error("Verify payment error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Payment verification failed.")



@router.delete("/{token}/cart/{product_id}")
async def dashboard_remove_from_cart(
    token: str,
    product_id: str,
    db: Session = Depends(get_db),
):
    """Remove a product from the pet's cart entirely."""
    try:
        dt = validate_dashboard_token(db, token)
        return await remove_from_cart(db, dt.pet_id, product_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Remove from cart error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not remove from cart.")


@router.get("/{token}/cart/recommendations")
async def dashboard_cart_recommendations(
    token: str,
    db: Session = Depends(get_db),
):
    """Get product recommendations based on pet species, breed, and nutrition gaps."""
    try:
        dt = validate_dashboard_token(db, token)

        # Get nutrition gaps for smarter recommendations
        nutrition_gaps = None
        try:
            analysis = await analyze_nutrition(db, dt.pet_id)
            # Build gaps dict from vitamins, minerals, others
            gaps = {}
            for section in ["vitamins", "minerals", "others"]:
                for nutrient in analysis.get(section, []):
                    name_key = nutrient["name"].lower().replace("-", "_").replace(" ", "_")
                    if nutrient.get("priority") in ("urgent", "high", "medium"):
                        gaps[name_key] = {"status": nutrient["status"]}
            if gaps:
                nutrition_gaps = gaps
        except Exception as e:
            logger.warning("Could not get nutrition analysis for recommendations: %s", e)

        recommendations = await get_recommendations(db, dt.pet_id, nutrition_gaps)

        # Build set of names currently in cart to exclude from last_bought
        cart_names = set()
        cart_rows = (
            db.query(CartItem.name)
            .filter(CartItem.pet_id == dt.pet_id, CartItem.in_cart == True)
            .all()
        )
        for row in cart_rows:
            if row[0]:
                cart_names.add(row[0].strip().lower())

        last_bought_raw = get_last_bought(db, dt.pet_id, exclude_names=cart_names)
        last_bought = [
            {
                "name": item["name"],
                "used_count": item["used_count"],
                "last_bought_label": _format_last_bought_label(item["last_bought_at"]),
                "category": item["category"],
            }
            for item in last_bought_raw
        ]

        return {"last_bought": last_bought, "recommendations": recommendations}
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Recommendations error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load recommendations.")


# ---------------------------------------------------------------------------
# Product resolution & search (cart-rules-engine task-006)
# ---------------------------------------------------------------------------


@router.get("/{token}/products/resolve")
async def resolve_product_endpoint(
    token: str,
    diet_item_id: str = Query(..., description="UUID of the diet item to resolve"),
    db: Session = Depends(get_db),
):
    """
    Resolve the best matching products for a diet item using the signal
    resolver. Returns signal level, up to 3 products, CTA label, and
    advisory flags (vet_diet_warning, pack_size_suggestion).
    """
    try:
        pet = _get_pet_for_dashboard_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")

    # Fetch diet item — must belong to this pet
    diet_item = (
        db.query(DietItem)
        .filter(DietItem.id == diet_item_id, DietItem.pet_id == pet.id)
        .first()
    )
    if not diet_item:
        raise HTTPException(status_code=404, detail="Diet item not found.")

    # Fetch active conditions for the pet
    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet.id, Condition.is_active == True)
        .all()
    )

    # Route to the correct resolver based on diet item type
    if diet_item.type == "supplement":
        result = resolve_supplement_signal(db, diet_item, pet, conditions)
    else:
        result = resolve_food_signal(db, diet_item, pet, conditions)

    # C5: vet_diet_warning — true if any returned product has vet_diet_flag
    vet_diet_warning = any(
        p.get("vet_diet_flag", False) for p in result.products
    )

    # C7: pack_size_suggestion when L4 and pet weight known
    pack_size_suggestion: str | None = None
    if result.level.value == "L4" and pet.weight:
        try:
            weight_kg = float(pet.weight)
            # 10g per kg per day * 30 days / 1000 = monthly kg
            monthly_kg = weight_kg * 10 * 30 / 1000
            pack_size_suggestion = f"~{monthly_kg:.1f} kg/month based on {weight_kg:.0f} kg body weight"
        except (TypeError, ValueError):
            pass

    return {
        "level": result.level.value,
        "products": result.products,
        "cta_label": result.cta_label,
        "highlight_sku": result.highlight_sku,
        "message": result.message,
        "vet_diet_warning": vet_diet_warning,
        "pack_size_suggestion": pack_size_suggestion,
    }


def _build_ingredient_conditions(term: str) -> list:
    """
    Return SQLAlchemy filter conditions for key_ingredients matching.

    Expansion rules applied in order:

    Fix A — "Vit X" abbreviation:
        "vit d3" → also search "vitamin d3" and carry that expanded form forward.

    Fix B — Vitamin singular ↔ plural:
        "vitamin a"  → also "vitamins a"; "vitamins a" → also "vitamin a".

    Fix C — Vitamin letter-list regex (covers plain and numbered suffixes):
        "vitamin d3" → regex matches "Vitamins A D3 E B-complex" even though
        "vitamins d3" is not a direct substring (the letters are space-separated).
        Pattern: ``vitamins?\\s+(?:[a-z]\\d*\\s+)*<suffix>(\\s|$|,|-)``

    Fix D — Hyphenated L-/N-/DL- amino-acid prefixes:
        Normalization strips hyphens from the search term but the DB retains them.
        "l carnitine" → also ILIKE "%l-carnitine%".

    Returns a list of conditions suitable for ``or_(*conditions)``.
    """
    conditions: list = [ProductSupplement.key_ingredients.ilike(f"%{term}%")]

    # Fix A: "vit X" → "vitamin X"
    expanded = term
    if _re.match(r"^vit\s+", term, _re.IGNORECASE) and not _re.match(r"^vita", term, _re.IGNORECASE):
        expanded = "vitamin " + term[4:]
        conditions.append(ProductSupplement.key_ingredients.ilike(f"%{expanded}%"))

    # Fix B: vitamin singular ↔ plural
    if expanded.startswith("vitamin ") and not expanded.startswith("vitamins "):
        plural = "vitamins " + expanded[8:]
        conditions.append(ProductSupplement.key_ingredients.ilike(f"%{plural}%"))
    elif expanded.startswith("vitamins "):
        singular = "vitamin " + expanded[9:]
        conditions.append(ProductSupplement.key_ingredients.ilike(f"%{singular}%"))

    # Fix C: vitamin letter-list regex — handles both single letters ("a", "e")
    # and numbered suffixes ("d3", "b12", "k2") in space-separated lists.
    m = _re.match(r"^vitamins?\s+([a-z]\d*)$", expanded, _re.IGNORECASE)
    if m:
        suffix = _re.escape(m.group(1))  # e.g. "d3", "b12", "a"
        # Walk through the space-separated letter[+digit] entries in the list
        # until the target suffix is found, terminated by space / comma / hyphen / end.
        regex_pat = rf"vitamins?\s+(?:[a-z]\d*\s+)*{suffix}(\s|$|,|-)"
        conditions.append(ProductSupplement.key_ingredients.op("~*")(regex_pat))

    # Fix D: hyphenated L-/N-/DL- amino-acid prefixes
    # e.g. "l carnitine" (hyphens stripped by normalizer) → also "%l-carnitine%"
    for prefix in ("dl ", "l ", "n "):
        if term.startswith(prefix):
            hyphenated = prefix.rstrip() + "-" + term[len(prefix):]
            conditions.append(ProductSupplement.key_ingredients.ilike(f"%{hyphenated}%"))
            break

    return conditions


@router.get("/{token}/products/resolve-by-micronutrient")
async def resolve_supplement_by_micronutrient(
    token: str,
    micronutrient: str = Query(..., description="Micronutrient name (e.g. 'glucosamine', 'vitamin d3')"),
    db: Session = Depends(get_db),
):
    """
    Resolve supplement products for a missing micronutrient.

    Used by the Quick Fixes to Add section when the user clicks on a
    micronutrient-based supplement recommendation (which has no diet_item_id).

    Two-pass resolution:
      1. Type match: maps micronutrient name → canonical supplement type via
         SUPPLEMENT_TYPE_KEYWORDS; queries product_supplement by type.
      2. Ingredient match: searches key_ingredients ILIKE '%<micronutrient>%'
         to find products that literally contain the nutrient.
    Results are merged (type-match first), deduped, and capped at 3 products.

    Returns the same shape as /products/resolve so the frontend ProductSelectorCard
    can be reused unchanged.
    """
    try:
        _get_pet_for_dashboard_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")

    # --- Step 1: type-based match via SUPPLEMENT_TYPE_KEYWORDS ---
    # Longest whole-word match wins (word-boundary prevents "renal" matching
    # inside "adrenal", and "milk" matching inside "milk thistle").
    haystack = micronutrient.lower().strip()
    sup_type: str | None = None
    best_len = 0
    for keyword, canonical in SUPPLEMENT_TYPE_KEYWORDS.items():
        if len(keyword) <= best_len:
            continue
        if _re.search(r"\b" + _re.escape(keyword) + r"\b", haystack):
            sup_type = canonical
            best_len = len(keyword)

    # Normalise the micronutrient for a key_ingredients ILIKE search:
    # replace underscores and hyphens with spaces so "omega-3" → "omega 3",
    # then strip generic trailing words ("supplement", "tablet", "capsule",
    # "oil") that appear in item names but not in key_ingredients.
    _STRIP_SUFFIXES = ("supplement", "tablet", "capsule", "capsules", "oil", "chew", "chews", "powder")
    ingredient_term = haystack.replace("_", " ").replace("-", " ")
    for _suffix in _STRIP_SUFFIXES:
        if ingredient_term.endswith(f" {_suffix}"):
            ingredient_term = ingredient_term[: -(len(_suffix) + 1)].strip()
            break

    # --- Step 2: ingredient-level search ---
    # Uses OR conditions generated by _build_ingredient_conditions so that:
    #   • "vitamin a"  matches both "Vitamin A capsule" and "Vitamins A D E B-complex"
    #   • "vitamin b"  matches "Vitamin B-complex" and "Vitamins A D E B-complex"
    #   • "omega 3"    matches "Omega 3 & 6, Vitamins A D E B-complex"
    #   • "zinc"       matches any product whose key_ingredients contains "zinc"
    ingredient_rows: list = []
    if ingredient_term:
        ingredient_conditions = _build_ingredient_conditions(ingredient_term)
        ingredient_rows = (
            db.query(ProductSupplement)
            .filter(
                ProductSupplement.active == True,
                or_(*ingredient_conditions),
            )
            .order_by(ProductSupplement.popularity_rank)
            .limit(5)
            .all()
        )

    # --- Step 3: type-based rows (primary) ---
    type_rows: list = []
    if sup_type:
        type_rows = (
            db.query(ProductSupplement)
            .filter(
                ProductSupplement.active == True,
                ProductSupplement.type == sup_type,
            )
            .order_by(ProductSupplement.popularity_rank)
            .limit(3)
            .all()
        )

    # --- Step 4: merge — type-match first, ingredient-match fills remaining slots ---
    # Dedup by sku_id; type-match products are preferred (they're the most targeted type).
    seen_skus: set[str] = set()
    merged: list = []
    for p in type_rows:
        if p.sku_id not in seen_skus:
            seen_skus.add(p.sku_id)
            merged.append(p)
    for p in ingredient_rows:
        if p.sku_id not in seen_skus and len(merged) < 3:
            seen_skus.add(p.sku_id)
            merged.append(p)

    if not merged:
        return {
            "level": "L1",
            "products": [],
            "cta_label": None,
            "highlight_sku": None,
            "message": "Share the supplement name on WhatsApp so we can help you reorder.",
            "vet_diet_warning": False,
            "pack_size_suggestion": None,
        }

    highlight_sku = merged[0].sku_id
    products = [
        {
            "sku_id": p.sku_id,
            "category": "supplement",
            "brand_name": p.brand_name,
            "product_name": p.product_name,
            "pack_size": p.pack_size,
            "mrp": int(p.mrp),
            "discounted_price": int(p.discounted_price),
            "price_per_unit": int(p.price_per_unit or 0),
            "unit_label": "per unit",
            "in_stock": bool(p.in_stock),
            "vet_diet_flag": False,
            "is_highlighted": p.sku_id == highlight_sku,
            "highlight_reason": "Most Popular" if p.sku_id == highlight_sku else None,
        }
        for p in merged
    ]

    return {
        "level": "L3",
        "products": products,
        "cta_label": "Order Now",
        "highlight_sku": highlight_sku,
        "message": None,
        "vet_diet_warning": False,
        "pack_size_suggestion": None,
    }


@router.get("/{token}/products/search")
async def search_products_endpoint(
    token: str,
    q: str = Query(..., min_length=2, description="Search query (min 2 characters)"),
    db: Session = Depends(get_db),
):
    """
    Search food, supplement, and medicine products by brand or product name.
    Returns up to 10 results, in-stock items first.
    Medicines are filtered by pet species and exclude prescription-only antibiotics.
    """
    try:
        pet = _get_pet_for_dashboard_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")

    pattern = f"%{q}%"

    # Search food products
    food_rows = (
        db.query(ProductFood)
        .filter(
            ProductFood.active == True,
            (ProductFood.brand_name.ilike(pattern) | ProductFood.product_line.ilike(pattern)),
        )
        .all()
    )

    # Search supplement products
    supplement_rows = (
        db.query(ProductSupplement)
        .filter(
            ProductSupplement.active == True,
            (ProductSupplement.brand_name.ilike(pattern) | ProductSupplement.product_name.ilike(pattern)),
        )
        .all()
    )

    # Search medicine products — filter by species and exclude antibiotics
    from app.models.product_medicines import ProductMedicines
    medicine_rows = (
        db.query(ProductMedicines)
        .filter(
            ProductMedicines.active.is_(True),
            ~ProductMedicines.type.ilike("%Antibiotic%"),
            ProductMedicines.life_stage_tags.ilike(f"%{pet.species}%"),
            (
                ProductMedicines.brand_name.ilike(pattern)
                | ProductMedicines.product_name.ilike(pattern)
            ),
        )
        .all()
    )

    # Combine and serialize
    results: list[dict] = []
    for p in food_rows:
        results.append({
            "sku_id": p.sku_id,
            "category": "food",
            "brand_name": p.brand_name,
            "product_name": p.product_line,
            "name": f"{p.brand_name} {p.product_line}".strip(),
            "pack_size": f"{float(p.pack_size_kg):g} kg",
            "mrp": int(p.mrp),
            "discounted_price": int(p.discounted_price),
            "in_stock": bool(p.in_stock),
        })
    for p in supplement_rows:
        results.append({
            "sku_id": p.sku_id,
            "category": "supplement",
            "brand_name": p.brand_name,
            "product_name": p.product_name,
            "name": f"{p.brand_name} {p.product_name}".strip(),
            "pack_size": p.pack_size,
            "mrp": int(p.mrp),
            "discounted_price": int(p.discounted_price),
            "in_stock": bool(p.in_stock),
        })
    for p in medicine_rows:
        results.append({
            "sku_id": p.sku_id,
            "category": "medicine",
            "brand_name": p.brand_name,
            "product_name": p.product_name,
            "name": f"{p.brand_name} {p.product_name}".strip(),
            "pack_size": p.pack_size or "",
            "mrp": p.mrp_paise // 100,
            "discounted_price": p.discounted_paise // 100,
            "in_stock": bool(p.in_stock),
            "medicine_type": p.type,
            "notes": p.notes or None,
        })

    # Sort: in_stock first, then by name
    results.sort(key=lambda r: (not r["in_stock"], r["name"]))

    return {"results": results[:10]}


@router.post("/{token}/cart/add")
async def cart_add_endpoint(
    token: str,
    body: CartAddRequest,
    db: Session = Depends(get_db),
):
    """
    Add a product to the pet's cart by SKU ID. Price is always read
    from the DB — never trusted from the client (rule C1: qty default 1).
    """
    try:
        pet = _get_pet_for_dashboard_token(db, token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")

    sku_id = body.sku_id.strip().upper()
    prefix = sku_id[:1]

    # Look up the product by SKU prefix
    if prefix == "F":
        product = db.query(ProductFood).filter(ProductFood.sku_id == sku_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")
        price = int(product.discounted_price)
        name = f"{product.brand_name} {product.product_line}".strip()
        sub = f"{float(product.pack_size_kg):g} kg"
        icon = "🥣"
    elif prefix == "S":
        product = db.query(ProductSupplement).filter(ProductSupplement.sku_id == sku_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")
        price = int(product.discounted_price)
        name = product.product_name
        sub = f"{product.brand_name} · {product.pack_size}" if product.pack_size else product.brand_name
        icon = "💊"
    elif sku_id.startswith("SKU-"):
        from app.models.product_medicines import ProductMedicines
        product = db.query(ProductMedicines).filter(ProductMedicines.sku_id == sku_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")
        price = product.discounted_paise // 100
        name = product.product_name
        sub = f"{product.brand_name} · {product.pack_size}" if product.pack_size else product.brand_name
        icon = "💊"
    else:
        raise HTTPException(status_code=404, detail="Product not found.")

    return await add_to_cart(
        db,
        pet_id=pet.id,
        product_id=sku_id,
        name=name,
        price=price,
        icon=icon,
        sub=sub,
    )
