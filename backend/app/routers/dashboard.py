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

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.rate_limiter import check_dashboard_rate_limit
from app.services.dashboard_service import (
    get_dashboard_data,
    get_health_trends,
    update_pet_weight,
    update_preventive_date,
    retry_document_extraction,
    get_document_file_for_token,
    get_pet_photo_for_token,
    validate_dashboard_token,
)
from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.contact import Contact
from app.models.diet_item import DietItem
from app.models.hygiene_preference import HygienePreference
from app.models.nudge import Nudge
from app.models.cart_item import CartItem
from app.utils.date_utils import parse_date
from app.services.weight_service import get_weight_history, add_weight_entry
from app.services.diet_service import get_diet_items, add_diet_item, update_diet_item, delete_diet_item
from app.services.hygiene_service import get_hygiene_preferences, upsert_hygiene_preference, update_hygiene_date, add_hygiene_item, delete_hygiene_item
from app.services.nutrition_service import analyze_nutrition
from app.services.nudge_engine import generate_nudges
from app.services.ai_insights_service import get_or_generate_insight, get_or_generate_nutrition_importance, AI_INSIGHT_CACHE_DAYS
from app.models.pet_ai_insight import PetAiInsight
from app.services.cart_service import get_cart, toggle_cart_item, update_quantity, initialize_cart, place_order, add_to_cart, remove_from_cart, get_recommendations, get_last_bought, _format_last_bought_label
from app.services.razorpay_service import create_razorpay_payment, verify_razorpay_payment
from app.services.condition_service import (
    get_condition_timeline,
    get_condition_recommendations,
    get_last_vet_visit,
    update_condition,
    add_condition_medication,
    update_condition_medication,
    delete_condition_medication,
    add_condition_monitoring,
    update_condition_monitoring,
    delete_condition_monitoring,
)


logger = logging.getLogger(__name__)


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


@router.get("/{token}")
async def dashboard_get(
    token: str,
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

    Cache-Control: no-store prevents browser/CDN caching of sensitive pet data.

    Args:
        token: Dashboard access token from URL path.
        response: FastAPI Response object for setting headers.
        db: SQLAlchemy database session (injected).

    Returns:
        Complete dashboard data dictionary.

    Raises:
        HTTPException 404: If token is invalid, revoked, or expired.
    """
    try:
        data = get_dashboard_data(db, token)
        # Prevent caching of sensitive pet health data.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
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
    import asyncio
    from app.services.document_upload import (
        validate_file_upload,
        check_daily_upload_limit,
        build_storage_path,
        create_document_record,
    )
    from app.services.storage_service import upload_file as storage_upload

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

    # Validate
    try:
        validate_file_upload(len(file_content), mime_type)
        check_daily_upload_limit(db, pet.id, pet.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Upload to GCP (primary) or Supabase (fallback)
    try:
        storage_path = build_storage_path(pet.user_id, pet.id, filename)
        _, backend = await storage_upload(file_content, storage_path, mime_type)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="File upload failed. Please try again.")

    # Create DB record
    document = create_document_record(
        db, pet.id, storage_path, mime_type,
        original_filename=filename,
        storage_backend=backend,
    )

    # Trigger extraction in background
    async def _run_extraction():
        from app.database import SessionLocal
        from app.services.gpt_extraction import extract_and_process_document
        extraction_db = SessionLocal()
        try:
            await extract_and_process_document(
                db=extraction_db,
                document_id=document.id,
                document_text="",
                file_bytes=file_content,
            )
        except Exception as exc:
            logger.error("Dashboard upload extraction failed: doc=%s, error=%s", document.id, exc)
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
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Dashboard not found or link has expired.")
    except Exception as e:
        logger.error("Health trends error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not load trend data.")


# --- Condition CRUD ---

class ConditionMedicationInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    dose: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=50)
    refill_due_date: Optional[str] = None
    price: Optional[str] = Field(None, max_length=20)

class ConditionMonitoringInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    frequency: Optional[str] = Field(None, max_length=100)
    next_due_date: Optional[str] = None
    last_done_date: Optional[str] = None

class AddConditionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    diagnosis: Optional[str] = Field(None, max_length=500)
    condition_type: str = Field("chronic", pattern=r"^(chronic|episodic|resolved)$")
    diagnosed_at: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    icon: Optional[str] = Field(None, max_length=10)
    managed_by: Optional[str] = Field(None, max_length=200)
    medications: List[ConditionMedicationInput] = []
    monitoring: List[ConditionMonitoringInput] = []


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
    except ValueError as e:
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
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    diagnosis: Optional[str] = Field(None, max_length=500)
    condition_type: Optional[str] = Field(None, pattern=r"^(chronic|episodic|resolved)$")
    diagnosed_at: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    icon: Optional[str] = Field(None, max_length=10)
    managed_by: Optional[str] = Field(None, max_length=200)


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
    clinic_name: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)

class UpdateContactRequest(BaseModel):
    role: Optional[str] = Field(None, pattern=r"^(veterinarian|groomer|trainer|specialist|other)$")
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    clinic_name: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)


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
    note: Optional[str] = Field(None, max_length=255)


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
        from app.models.preventive_record import PreventiveRecord
        from app.models.preventive_master import PreventiveMaster

        result = (
            db.query(PreventiveRecord, PreventiveMaster)
            .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
            .filter(
                PreventiveRecord.pet_id == dt.pet_id,
                PreventiveMaster.item_name == body.item_name,
                PreventiveRecord.status != "cancelled",
            )
            .first()
        )
        if not result:
            raise HTTPException(status_code=404, detail="Preventive record not found.")

        record, master = result
        record.custom_recurrence_days = body.recurrence_days

        # Recalculate next_due_date if last_done_date exists
        if record.last_done_date:
            from datetime import timedelta, date as date_type
            record.next_due_date = record.last_done_date + timedelta(days=body.recurrence_days)
            today = date_type.today()
            if record.next_due_date < today:
                record.status = "overdue"
            elif (record.next_due_date - today).days <= 30:
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


# --- Medicine Name Update (AI-based due date) ---

class MedicineNameRequest(BaseModel):
    item_name: str = Field(..., min_length=1)
    medicine_name: str = Field(..., min_length=1, max_length=200)


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
        from app.models.preventive_record import PreventiveRecord
        from app.models.preventive_master import PreventiveMaster
        from app.models.pet import Pet

        result = (
            db.query(PreventiveRecord, PreventiveMaster)
            .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
            .filter(
                PreventiveRecord.pet_id == dt.pet_id,
                PreventiveMaster.item_name == body.item_name,
                PreventiveRecord.status != "cancelled",
            )
            .first()
        )
        if not result:
            raise HTTPException(status_code=404, detail="Preventive record not found.")

        record, master = result

        pet = db.query(Pet).filter(Pet.id == dt.pet_id).first()
        species = pet.species if pet else "dog"

        # Save the medicine name
        record.medicine_name = body.medicine_name

        # Use AI to calculate recommended recurrence days
        from app.services.medicine_recurrence_service import get_medicine_recurrence
        ai_days = get_medicine_recurrence(
            species=species,
            item_type=master.item_name,
            medicine_name=body.medicine_name,
            default_days=master.recurrence_days,
        )

        record.custom_recurrence_days = ai_days

        # Recalculate next_due_date if last_done_date exists
        if record.last_done_date:
            from datetime import timedelta, date as date_type
            record.next_due_date = record.last_done_date + timedelta(days=ai_days)
            today = date_type.today()
            if record.next_due_date < today:
                record.status = "overdue"
            elif (record.next_due_date - today).days <= 30:
                record.status = "upcoming"
            else:
                record.status = "up_to_date"

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
    detail: Optional[str] = Field(None, max_length=200)
    icon: Optional[str] = Field(None, max_length=10)

class DietItemUpdateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    detail: Optional[str] = Field(None, max_length=200)


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


@router.post("/{token}/diet-items")
async def dashboard_add_diet_item(
    token: str,
    body: DietItemRequest,
    db: Session = Depends(get_db),
):
    """Add a diet item."""
    try:
        dt = validate_dashboard_token(db, token)
        return await add_diet_item(db, dt.pet_id, body.type, body.label, body.detail, body.icon)
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
        return await update_diet_item(db, item_id, dt.pet_id, body.label, body.detail)
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
    last_done: Optional[str] = None

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
    """Get nutrition analysis for a pet based on their diet items."""
    try:
        dt = validate_dashboard_token(db, token)
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
        data = get_dashboard_data(db, token)
        return await get_or_generate_insight(
            db=db,
            pet_id=dt.pet_id,
            insight_type="conditions_summary",
            pet=data["pet"],
            conditions=data["conditions"],
            health_score=data["health_score"],
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
        data = get_dashboard_data(db, token)
        result = await get_or_generate_insight(
            db=db,
            pet_id=dt.pet_id,
            insight_type="vet_questions",
            pet=data["pet"],
            conditions=data["conditions"],
            health_score=data["health_score"],
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
        data = get_dashboard_data(db, token)
        result = await get_or_generate_insight(
            db=db,
            pet_id=dt.pet_id,
            insight_type="vet_questions",
            pet=data["pet"],
            conditions=data["conditions"],
            health_score=data["health_score"],
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
    address: Optional[dict] = None
    coupon: Optional[str] = None


@router.post("/{token}/place-order")
async def dashboard_place_order(
    token: str,
    body: PlaceOrderRequest,
    db: Session = Depends(get_db),
):
    """Place a COD order. For UPI/card/netbanking use /create-payment instead."""
    try:
        dt = validate_dashboard_token(db, token)
        return await place_order(db, dt.pet_id, dt.user_id, body.payment_method, body.address, body.coupon)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Place order error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not place order.")


class CreatePaymentRequest(BaseModel):
    payment_method: str = Field(..., pattern=r"^(upi|card|netbanking)$")
    address: Optional[dict] = None
    coupon: Optional[str] = None
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
        return await create_razorpay_payment(
            db,
            pet_id=dt.pet_id,
            user_id=dt.user_id,
            payment_method=body.payment_method,
            address=body.address,
            coupon=body.coupon,
            coupon_discount_percent=body.coupon_discount_percent,
        )
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
    """
    try:
        dt = validate_dashboard_token(db, token)
        return await verify_razorpay_payment(
            db,
            pet_id=dt.pet_id,
            order_db_id=body.order_db_id,
            razorpay_order_id=body.razorpay_order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error("Razorpay verify config error: %s", str(e))
        raise HTTPException(status_code=503, detail="Payment gateway not configured.")
    except Exception as e:
        logger.error("Verify payment error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Payment verification failed.")


class AddToCartRequest(BaseModel):
    product_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)
    price: int = Field(..., ge=0)
    icon: Optional[str] = None
    sub: Optional[str] = None
    tag: Optional[str] = None
    tag_color: Optional[str] = None


@router.post("/{token}/cart/add")
async def dashboard_add_to_cart(
    token: str,
    body: AddToCartRequest,
    db: Session = Depends(get_db),
):
    """Add a product to the pet's cart."""
    try:
        dt = validate_dashboard_token(db, token)
        return await add_to_cart(
            db, dt.pet_id, body.product_id, body.name, body.price,
            body.icon, body.sub, body.tag, body.tag_color,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Add to cart error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=503, detail="Could not add to cart.")


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
