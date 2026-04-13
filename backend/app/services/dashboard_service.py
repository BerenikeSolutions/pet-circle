"""
PetCircle Phase 1 — Dashboard Service (Module 13)

Provides data retrieval and update logic for the tokenized pet dashboard.
The dashboard is accessed via a secure random token — no login required
for Phase 1.

Token validation:
    - Token must exist in dashboard_tokens table.
    - Token must not be revoked (revoked=False).
    - Token maps to a single pet via pet_id.

Data returned:
    - Pet profile (no internal IDs exposed to frontend).
    - Preventive summary (records with status, dates, master item names).
    - Active reminders.
    - Uploaded documents (metadata only — no direct storage URLs).
    - Health score (computed by health_score service).

Editable operations:
    - Update pet weight.
    - Update preventive record dates (triggers recalculation).
    - Date changes invalidate pending reminders.

Rules:
    - No internal UUIDs exposed in API responses — use token only.
    - Recalculation after every update (next_due_date, status).
    - Pending reminders invalidated when dates change.
    - No bucket hardcoding — file paths are storage-relative.
    - All recurrence values from DB preventive_master — never hardcoded.
"""

import asyncio
import logging
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.encryption import decrypt_field
from app.models.condition import Condition
from app.models.conflict_flag import ConflictFlag
from app.models.contact import Contact
from app.models.dashboard_token import DashboardToken
from app.models.diagnostic_test_result import DiagnosticTestResult
from app.models.diet_item import DietItem
from app.models.document import Document
from app.models.pet import Pet
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.services.ai_insights_service import (
    AI_INSIGHT_CACHE_DAYS,
    generate_care_plan_reasons,
    generate_recognition_bullets,
)
from app.services.care_plan_engine import compute_care_plan
from app.services.document_upload import download_from_supabase
from app.services.gpt_extraction import _infer_document_category, _resolve_document_category
from app.services.life_stage_service import get_life_stage_data
from app.services.nutrition_service import get_diet_summary
from app.services.preventive_calculator import (
    compute_next_due_date,
    compute_status,
)
from app.services.vet_summary_service import get_vet_summary

logger = logging.getLogger(__name__)

_CORE_VACCINE_NAMES = frozenset(
    {
        "rabies vaccine",
        "rabies (nobivac rl)",
        "dhppi",
        "dhppi (nobivac)",
        "kennel cough (nobivac kc)",
        "canine coronavirus (ccov)",
    }
)


def _is_vaccine_item_name(item_name: str | None) -> bool:
    """Return True when a preventive master item_name represents a vaccine."""
    if not item_name:
        return False
    name = item_name.strip().lower()
    vaccine_keywords = (
        "vaccine",
        "vaccination",
        "rabies",
        "dhppi",
        "kennel cough",
        "bordetella",
        "coronavirus",
        "ccov",
        "leptospirosis",
        "influenza",
        "nobivac",
        "feline core",
        "fvrcp",
        "felv",
        "fiv",
    )
    return any(keyword in name for keyword in vaccine_keywords)


def _is_core_vaccine(master: PreventiveMaster | None) -> bool:
    """Return True when a preventive master row is both core and a vaccine."""
    if not master:
        return False
    normalized_name = (master.item_name or "").strip().lower()
    return bool(master.is_core) and normalized_name in _CORE_VACCINE_NAMES


def _safe_iso_date(value: date | datetime | None) -> str | None:
    """Return ISO date string for date-like values."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def _condition_severity(condition: Condition) -> str:
    """Map condition type to UI severity color token."""
    condition_type = (condition.condition_type or "").strip().lower()
    if condition_type == "chronic":
        return "red"
    if condition_type == "episodic":
        return "yellow"
    return "green"


def _condition_trend_label(condition: Condition) -> str:
    """Build trend label text like 'Active · Since Feb 2025'."""
    if condition.diagnosed_at:
        return f"Active · Since {condition.diagnosed_at.strftime('%b %Y')}"
    return "Active"


def _condition_insight(condition: Condition) -> str:
    """Build a one-line observational insight for condition summary."""
    if condition.notes:
        note = " ".join(condition.notes.strip().split())
        if note:
            return note[:180]

    active_meds = [med for med in condition.medications if (med.status or "active") == "active"]
    if active_meds:
        first_med = active_meds[0].name or "current medication"
        return f"Current management includes {first_med}; review response trend with your vet."

    if condition.monitoring:
        first_monitor = condition.monitoring[0].name or "follow-up monitoring"
        return f"Track {first_monitor} cadence and discuss pattern changes with your vet."

    return "Observed pattern tracked from uploaded records; discuss updates with your vet."


def _build_health_conditions_summary(condition_rows: list[Condition]) -> list[dict]:
    """Build health_conditions_summary payload from active conditions."""
    summary: list[dict] = []
    for condition in condition_rows:
        summary.append(
            {
                "id": str(condition.id),
                "icon": condition.icon or "🩺",
                "title": condition.name,
                "severity": _condition_severity(condition),
                "trend_label": _condition_trend_label(condition),
                "insight": _condition_insight(condition),
            }
        )
    return summary


def _collect_orderable_items(care_plan: dict | None) -> list[dict]:
    """Collect all orderable care-plan items across buckets."""
    if not isinstance(care_plan, dict):
        return []

    items: list[dict] = []
    for bucket in ("continue", "attend", "add"):
        sections = care_plan.get(bucket, [])
        if not isinstance(sections, list):
            continue
        for section in sections:
            if not isinstance(section, dict):
                continue
            for item in section.get("items", []):
                if isinstance(item, dict) and item.get("orderable"):
                    items.append(item)
    return items


def _normalize_care_plan_shape(care_plan: dict | None) -> dict:
    """Normalize care plan keys to {continue, attend, add}."""
    if not isinstance(care_plan, dict):
        return {"continue": [], "attend": [], "add": []}

    # Already normalized.
    if all(key in care_plan for key in ("continue", "attend", "add")):
        return {
            "continue": care_plan.get("continue") or [],
            "attend": care_plan.get("attend") or [],
            "add": care_plan.get("add") or [],
        }

    # care_plan_engine currently returns *_items keys.
    return {
        "continue": care_plan.get("continue_items") or [],
        "attend": care_plan.get("attend_items") or [],
        "add": care_plan.get("add_items") or [],
    }


def _inject_supplement_recommendations(care_plan: dict, diet_summary: dict) -> dict:
    """
    Add supplement recommendations from missing micronutrients into the
    care plan 'add' (Quick Fixes to Add) bucket.

    Each missing micro becomes an orderable supplement suggestion.
    """
    if not isinstance(care_plan, dict) or not isinstance(diet_summary, dict):
        return care_plan

    missing_micros = diet_summary.get("missing_micros") or []
    if not missing_micros:
        return care_plan

    supplement_items = []
    for micro in missing_micros:
        nutrient_name = micro.get("name", "")
        cap_name = nutrient_name[0].upper() + nutrient_name[1:] if nutrient_name else nutrient_name
        # Display the micronutrient name (not the LLM product name) as the item title.
        # The LLM product name is used internally for product resolution but not shown.
        item_name = f"{cap_name} Supplement" if cap_name else "Supplement"
        # Use LLM-provided reason as the one-liner shown below the supplement name
        reason = micro.get("reason") or None
        supplement_items.append({
            "name": item_name,
            "test_type": "supplement",
            "freq": "Daily",
            "next_due": None,
            "status_tag": "Recommended",
            "classification": "suggested",
            "reason": reason,
            "orderable": True,
            "cta_label": "Order Now",
            # Raw micronutrient name used by the frontend to fetch matching
            # products from product_supplement via the resolve-by-micronutrient
            # endpoint (instead of the diet_item_id path used for food items).
            "micronutrient": nutrient_name,
        })

    if supplement_items:
        add_sections = care_plan.get("add") or []
        add_sections.append({
            "icon": "\U0001f48a",
            "title": "Supplements",
            "items": supplement_items,
        })
        care_plan["add"] = add_sections

    return care_plan


def _apply_reasons_to_care_plan(care_plan: dict, reasons: dict[str, str]) -> dict:
    """Attach GPT reasons to orderable care-plan items by id/name key."""
    if not isinstance(care_plan, dict) or not reasons:
        return care_plan

    for bucket in ("continue", "attend", "add"):
        sections = care_plan.get(bucket, [])
        if not isinstance(sections, list):
            continue
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_items = section.get("items", [])
            if not isinstance(section_items, list):
                continue
            for item in section_items:
                if not isinstance(item, dict) or not item.get("orderable"):
                    continue
                item_key = str(item.get("item_id") or item.get("id") or item.get("name") or "")
                if item_key and item_key in reasons:
                    item["reason"] = reasons[item_key]

    return care_plan


def validate_dashboard_token(db: Session, token: str) -> DashboardToken:
    """
    Validate a dashboard access token.

    Checks that the token exists and has not been revoked.
    Revoked tokens cannot be used — soft revocation is permanent
    for that token (a new token must be generated).

    Args:
        db: SQLAlchemy database session.
        token: The dashboard access token string.

    Returns:
        The valid DashboardToken record.

    Raises:
        ValueError: If token is not found or has been revoked.
    """
    dashboard_token = (
        db.query(DashboardToken)
        .filter(
            DashboardToken.token == token,
        )
        .first()
    )

    if not dashboard_token:
        raise ValueError("Invalid dashboard token.")

    # Revoked tokens cannot be reused — soft revocation only.
    if dashboard_token.revoked:
        raise ValueError("This dashboard link has been revoked.")

    # Expired tokens are rejected — user can regenerate via WhatsApp.
    if dashboard_token.expires_at and datetime.utcnow() > dashboard_token.expires_at:
        raise ValueError(
            "Dashboard link has expired. Send 'dashboard' in WhatsApp to get a new link."
        )

    return dashboard_token


async def get_dashboard_data(db: Session, token: str) -> dict:
    """
    Retrieve all dashboard data for a pet via its access token.

    Returns a comprehensive view of the pet's health status:
        - Pet profile (name, species, breed, gender, dob, weight, neutered).
        - Owner info (full_name only — no mobile number exposed).
        - Preventive records with master item names and status.
        - Active reminders with status and dates.
        - Uploaded documents (metadata only — no direct storage URLs).
        - Health score (computed inline from preventive records — no duplicate query).

    No internal IDs (UUIDs) are exposed in the response.
    The frontend uses the token as the sole identifier.

    Args:
        db: SQLAlchemy database session.
        token: The dashboard access token string.

    Returns:
        Dictionary with complete dashboard data.

    Raises:
        ValueError: If token is invalid, revoked, or pet not found.
    """
    # --- Validate token ---
    dashboard_token = validate_dashboard_token(db, token)
    pet_id = dashboard_token.pet_id

    # --- Record dashboard visit for nudge level tracking (N8) ---
    # Best-effort: never crash the dashboard load on a logging failure.
    # user_id is resolved via pet.user_id (DashboardToken has no user_id FK).
    # Count previous visits BEFORE inserting new one to determine first visit.
    is_first_visit = True
    try:
        from app.models.dashboard_visit import DashboardVisit
        _visit_pet = db.query(Pet).filter(Pet.id == pet_id).first()
        if _visit_pet:
            previous_visit_count = (
                db.query(func.count(DashboardVisit.id))
                .filter(DashboardVisit.pet_id == pet_id)
                .scalar()
                or 0
            )
            is_first_visit = previous_visit_count == 0
            visit = DashboardVisit(
                user_id=_visit_pet.user_id,
                pet_id=pet_id,
                token=token,
            )
            db.add(visit)
            db.flush()  # Write within current transaction; committed below with the rest.
    except Exception:
        logger.warning("Failed to record dashboard visit for token=%s...", token[:8])

    # --- Load pet + owner in one query via join ---
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet or pet.is_deleted:
        raise ValueError("Pet not found or has been removed.")

    user = db.query(User).filter(User.id == pet.user_id).first()

    # --- Load preventive records with master item names ---
    # Also compute health score inline to avoid a duplicate DB query.
    # Eager-load custom_preventive_item so the conflict-rows loop below
    # doesn't fire N+1 lazy queries when rendering user-scoped custom items.
    preventive_data = (
        db.query(PreventiveRecord, PreventiveMaster)
        .join(
            PreventiveMaster,
            PreventiveRecord.preventive_master_id == PreventiveMaster.id,
        )
        .options(selectinload(PreventiveRecord.custom_preventive_item))
        .filter(PreventiveRecord.pet_id == pet_id)
        .order_by(PreventiveRecord.next_due_date.asc())
        .all()
    )

    def _record_sort_key(r: PreventiveRecord) -> tuple:
        # Prefer newest completion date; fallback to next due, then created_at.
        return (
            r.last_done_date or date.min,
            r.next_due_date or date.min,
            r.created_at.date() if getattr(r, "created_at", None) else date.min,
        )

    vaccine_latest_by_name: dict[str, tuple[PreventiveRecord, PreventiveMaster]] = {}
    non_vaccine_records: list[tuple[PreventiveRecord, PreventiveMaster]] = []

    # Puppy-series items (recurrence_days >= 36500) are one-time doses.
    # Hide them for adult dogs (>= 12 months old).
    _is_adult_dog = (
        pet.species == "dog"
        and pet.dob is not None
        and (date.today() - pet.dob).days >= 365
    )

    for record, master in preventive_data:
        # Skip puppy-series records for adult dogs.
        if _is_adult_dog and master.recurrence_days and master.recurrence_days >= 36500:
            continue

        # Hide non-core vaccines unless the user has a logged completion date.
        if _is_vaccine_item_name(master.item_name) and not _is_core_vaccine(master) and not record.last_done_date:
            continue

        if _is_vaccine_item_name(master.item_name):
            existing = vaccine_latest_by_name.get(master.item_name)
            if not existing or _record_sort_key(record) >= _record_sort_key(existing[0]):
                vaccine_latest_by_name[master.item_name] = (record, master)
        else:
            non_vaccine_records.append((record, master))

    # Dashboard list: all non-vaccine records + only latest record per vaccine name.
    selected_records = non_vaccine_records + list(vaccine_latest_by_name.values())
    selected_records.sort(
        key=lambda rm: (
            rm[0].next_due_date is None,
            rm[0].next_due_date or date.max,
        )
    )

    preventive_records = []

    # --- Pre-load conditions with eager-loaded relationships ---
    # selectinload fires 2 IN-queries (medications, monitoring) instead of
    # N*2 lazy queries — one per condition row.
    condition_rows = (
        db.query(Condition)
        .options(
            selectinload(Condition.medications),
            selectinload(Condition.monitoring),
        )
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .order_by(Condition.created_at.desc())
        .all()
    )

    for record, master in selected_records:
        # Use custom recurrence if set, otherwise fall back to master default
        effective_recurrence = record.custom_recurrence_days if record.custom_recurrence_days else master.recurrence_days
        preventive_records.append({
            "item_name": master.item_name,
            "category": master.category,
            "circle": master.circle,
            "last_done_date": str(record.last_done_date) if record.last_done_date else None,
            "next_due_date": str(record.next_due_date) if record.next_due_date else None,
            "status": record.status,
            "recurrence_days": effective_recurrence,
            "custom_recurrence_days": record.custom_recurrence_days,
            "medicine_dependent": master.medicine_dependent,
            "medicine_name": record.medicine_name if hasattr(record, 'medicine_name') and record.medicine_name else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "is_core": bool(master.is_core) if master.is_core is not None else False,
        })

    # --- Inject preventive_master items that have no record yet ---
    # Ensures all health-circle items (vaccines, deworming, flea/tick, checkups) appear
    # on the dashboard even before any documents are uploaded. Items with existing
    # records are skipped to avoid duplicates.
    #
    # Puppy-series items (recurrence_days=36500) are excluded for dogs older
    # than 12 months — adults should only see the annual DHPPi + Rabies cycle.
    health_masters = (
        db.query(PreventiveMaster)
        .filter(
            PreventiveMaster.circle == "health",
            PreventiveMaster.species.in_([pet.species, "both"]),
        )
        .all()
    )
    existing_names = {r["item_name"] for r in preventive_records}
    for master in health_masters:
        # Skip puppy-series items for adult dogs.
        if _is_adult_dog and master.recurrence_days and master.recurrence_days >= 36500:
            continue

        # Inject only core vaccines by default. Non-core vaccines should
        # appear only after a logged completion date exists.
        if _is_vaccine_item_name(master.item_name) and not _is_core_vaccine(master):
            continue

        if master.item_name not in existing_names:
            preventive_records.append({
                "item_name": master.item_name,
                "category": master.category,
                "circle": master.circle,
                "last_done_date": None,
                "next_due_date": None,
                "status": "missing",
                "recurrence_days": master.recurrence_days,
                "custom_recurrence_days": None,
                "medicine_dependent": master.medicine_dependent,
                "medicine_name": None,
                "created_at": None,
                "is_core": bool(master.is_core) if master.is_core is not None else False,
            })

    # --- Health score (6-category, single source of truth) ---
    from app.services.health_score import compute_health_score
    health_score = compute_health_score(db, pet_id)

    # --- Load active reminders ---
    reminders = (
        db.query(Reminder, PreventiveRecord, PreventiveMaster)
        .join(
            PreventiveRecord,
            Reminder.preventive_record_id == PreventiveRecord.id,
        )
        .join(
            PreventiveMaster,
            PreventiveRecord.preventive_master_id == PreventiveMaster.id,
        )
        .filter(
            PreventiveRecord.pet_id == pet_id,
            Reminder.status.in_(["pending", "sent"]),
        )
        .order_by(Reminder.next_due_date.asc())
        .all()
    )

    reminder_data = []
    for reminder, record, master in reminders:
        effective_recurrence = record.custom_recurrence_days or master.recurrence_days
        reminder_data.append({
            "item_name": master.item_name,
            "next_due_date": str(reminder.next_due_date),
            "status": reminder.status,
            "sent_at": str(reminder.sent_at) if reminder.sent_at else None,
            "recurrence_days": effective_recurrence,
        })

    # --- Load documents (metadata only — no storage URLs) ---
    # Show documents with all statuses including failed — users can retry
    # failed extractions from the dashboard.
    documents = (
        db.query(Document)
        .filter(
            Document.pet_id == pet_id,
            Document.extraction_status.in_(["pending", "success", "failed", "rejected"]),
        )
        .order_by(Document.created_at.desc())
        .all()
    )

    document_data = []
    for doc in documents:
        inferred_category = _infer_document_category(
            document_name=doc.document_name,
            file_path=doc.file_path,
            items=[],
            vaccination_details=[],
            diagnostic_values=[],
        )
        document_data.append({
            "id": str(doc.id),
            "document_name": doc.document_name,
            "document_category": _resolve_document_category(
                doc.document_category,
                inferred_category,
                document_name=doc.document_name,
                file_path=doc.file_path,
            ),
            "doctor_name": doc.doctor_name,
            "hospital_name": doc.hospital_name,
            "mime_type": doc.mime_type,
            "extraction_status": doc.extraction_status,
            "rejection_reason": doc.rejection_reason,
            "uploaded_at": str(doc.created_at) if doc.created_at else None,
            "event_date": str(doc.event_date) if doc.event_date else None,
        })

    # --- Diagnostic values (blood/urine) for dashboard ---
    diagnostic_rows = (
        db.query(DiagnosticTestResult)
        .filter(DiagnosticTestResult.pet_id == pet_id)
        .order_by(DiagnosticTestResult.observed_at.desc().nullslast(), DiagnosticTestResult.created_at.desc())
        .all()
    )

    diagnostic_results = []
    for row in diagnostic_rows:
        diagnostic_results.append({
            "test_type": row.test_type,
            "parameter_name": row.parameter_name,
            "value_numeric": float(row.value_numeric) if row.value_numeric is not None else None,
            "value_text": row.value_text,
            "unit": row.unit,
            "reference_range": row.reference_range,
            "status_flag": row.status_flag,
            "observed_at": str(row.observed_at) if row.observed_at else None,
            "document_id": str(row.document_id) if row.document_id else None,
            "created_at": str(row.created_at) if row.created_at else None,
        })

    # --- Build conditions response from pre-loaded rows ---
    conditions_data = []
    for cond in condition_rows:
        medications = []
        for med in cond.medications:
            medications.append({
                "id": str(med.id),
                "name": med.name,
                "dose": med.dose,
                "frequency": med.frequency,
                "route": med.route,
                "status": med.status,
                "started_at": str(med.started_at) if med.started_at else None,
                "refill_due_date": str(med.refill_due_date) if med.refill_due_date else None,
                "price": med.price,
                "notes": med.notes,
            })

        monitoring = []
        for mon in cond.monitoring:
            monitoring.append({
                "id": str(mon.id),
                "name": mon.name,
                "frequency": mon.frequency,
                "next_due_date": str(mon.next_due_date) if mon.next_due_date else None,
                "last_done_date": str(mon.last_done_date) if mon.last_done_date else None,
            })

        conditions_data.append({
            "id": str(cond.id),
            "name": cond.name,
            "diagnosis": cond.diagnosis,
            "condition_type": cond.condition_type,
            "diagnosed_at": str(cond.diagnosed_at) if cond.diagnosed_at else None,
            "notes": cond.notes,
            "icon": cond.icon,
            "managed_by": cond.managed_by,
            "source": cond.source,
            "is_active": cond.is_active,
            "medications": medications,
            "monitoring": monitoring,
            "created_at": str(cond.created_at) if cond.created_at else None,
        })

    # --- Load contacts ---
    contact_rows = (
        db.query(Contact)
        .filter(Contact.pet_id == pet_id)
        .order_by(Contact.created_at.desc())
        .all()
    )

    contacts_data = []
    for contact in contact_rows:
        contacts_data.append({
            "id": str(contact.id),
            "role": contact.role,
            "name": contact.name,
            "clinic_name": contact.clinic_name,
            "phone": contact.phone,
            "email": contact.email,
            "address": contact.address,
            "source": contact.source,
            "created_at": str(contact.created_at) if contact.created_at else None,
        })

    # --- Load diet items (nutrition tab) ---
    diet_rows = (
        db.query(DietItem)
        .filter(DietItem.pet_id == pet_id)
        .order_by(DietItem.created_at.asc())
        .all()
    )
    diet_items_data = [
        {
            "id": str(d.id),
            "type": d.type,
            "icon": d.icon,
            "label": d.label,
            "detail": d.detail,
            "created_at": str(d.created_at) if d.created_at else None,
        }
        for d in diet_rows
    ]

    # --- Load pending conflict flags ---
    # Fetches conflicts for all preventive records belonging to this pet.
    # Only 'pending' conflicts are surfaced — resolved/auto-resolved are historical.
    # Reuse already-loaded preventive_data ORM tuples to avoid a redundant full table scan.
    conflict_rows = []
    pet_rec_map = {str(r.id): r for r, _ in preventive_data}
    if pet_rec_map:
        cf_rows = (
            db.query(ConflictFlag)
            .filter(
                ConflictFlag.preventive_record_id.in_(list(pet_rec_map.keys())),
                ConflictFlag.status == "pending",
            )
            .order_by(ConflictFlag.created_at.desc())
            .all()
        )
        for cf in cf_rows:
            rec = pet_rec_map.get(str(cf.preventive_record_id))
            item_name = None
            if rec:
                if rec.preventive_master:
                    item_name = rec.preventive_master.item_name
                elif rec.custom_preventive_item:
                    item_name = rec.custom_preventive_item.item_name
            conflict_rows.append({
                "id": str(cf.id),
                "item_name": item_name,
                "existing_date": str(rec.last_done_date) if rec and rec.last_done_date else None,
                "new_date": str(cf.new_date),
                "status": cf.status,
                "created_at": str(cf.created_at) if cf.created_at else None,
            })

    # --- Dashboard Rebuild v2 enrichments ---
    # Hard 10s timeout per enrichment. Lowered from 15s so that two sequential
    # enrichment phases (gather + care_plan_reasons) cannot together exceed the
    # 30s frontend request timeout (10s + 10s leaves 10s of headroom).
    _ENRICHMENT_TIMEOUT_SECONDS = 10

    async def _safe_async_call(label: str, default, coro):
        try:
            return await asyncio.wait_for(coro, timeout=_ENRICHMENT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.error(
                "%s timed out after %ds for pet=%s",
                label, _ENRICHMENT_TIMEOUT_SECONDS, pet_id,
            )
            return default
        except Exception as exc:
            logger.error("%s failed for pet=%s: %s", label, pet_id, exc)
            return default

    async def _safe_sync_call(label: str, default, fn, *args):
        try:
            return fn(*args)
        except Exception as exc:
            logger.error("%s failed for pet=%s: %s", label, pet_id, exc)
            return default

    empty_care_plan = {"continue_items": [], "attend_items": [], "add_items": []}

    care_plan_v2, life_stage_data, vet_summary, diet_summary, recognition_bullets = await asyncio.gather(
        _safe_sync_call("care_plan_engine.compute_care_plan", empty_care_plan, compute_care_plan, db, pet),
        _safe_async_call("life_stage_service.get_life_stage_data", None, get_life_stage_data(db, pet)),
        _safe_sync_call("vet_summary_service.get_vet_summary", None, get_vet_summary, db, pet.id),
        _safe_async_call("nutrition_service.get_diet_summary", {"macros": [], "missing_micros": []}, get_diet_summary(db, pet)),
        _safe_async_call("ai_insights_service.generate_recognition_bullets", [], generate_recognition_bullets(db, pet)),
    )

    care_plan_v2 = _normalize_care_plan_shape(care_plan_v2)

    orderable_items = _collect_orderable_items(care_plan_v2)
    care_plan_reasons = await _safe_async_call(
        "ai_insights_service.generate_care_plan_reasons",
        {},
        generate_care_plan_reasons(db, pet, orderable_items, diet_summary=diet_summary),
    )
    care_plan_v2 = _apply_reasons_to_care_plan(care_plan_v2, care_plan_reasons)
    care_plan_v2 = _inject_supplement_recommendations(care_plan_v2, diet_summary)

    life_stage_payload = None
    if life_stage_data is not None:
        life_stage_payload = {
            "stage": life_stage_data.stage,
            "age_months": life_stage_data.age_months,
            "breed_size": life_stage_data.breed_size,
            "stage_boundaries": life_stage_data.stage_boundaries,
            "traits": life_stage_data.traits,
            "essential_care": life_stage_data.essential_care,
        }

    vet_summary_payload = None
    if vet_summary is not None:
        vet_summary_payload = {
            "name": vet_summary.name,
            "last_visit": _safe_iso_date(vet_summary.last_visit),
        }

    health_conditions_summary = _build_health_conditions_summary(condition_rows)
    recognition_payload = {
        "report_count": sum(1 for doc in document_data if doc.get("extraction_status") == "success"),
        "bullets": recognition_bullets,
    }

    # --- Load cached AI insights (no GPT calls — DB lookup only) ---
    # Include health_summary and vet_questions if they exist and are fresh.
    # This lets the frontend render immediately without waiting for separate
    # /health-summary and /vet-questions API calls.
    cached_insights: dict[str, dict | None] = {"health_summary": None, "vet_questions": None}
    try:
        from app.models.pet_ai_insight import PetAiInsight
        from datetime import timedelta
        stale_cutoff = datetime.utcnow() - timedelta(days=AI_INSIGHT_CACHE_DAYS)
        insight_rows = (
            db.query(PetAiInsight)
            .filter(
                PetAiInsight.pet_id == pet_id,
                PetAiInsight.insight_type.in_(["health_summary", "vet_questions"]),
                PetAiInsight.generated_at >= stale_cutoff,
            )
            .all()
        )
        for row in insight_rows:
            cached_insights[row.insight_type] = row.content_json
    except Exception:
        logger.warning("Failed to load cached AI insights for pet=%s", pet_id)

    # --- Build response (no internal IDs exposed) ---
    # photo_url: serve via dashboard endpoint if pet has a photo, else None.
    photo_url = f"/dashboard/{token}/pet-photo" if pet.photo_path else None

    return {
        "pet": {
            "name": pet.name,
            "species": pet.species,
            "breed": pet.breed,
            "gender": pet.gender,
            "dob": str(pet.dob) if pet.dob else None,
            "weight": float(pet.weight) if pet.weight else None,
            "weight_flagged": bool(pet.weight_flagged),
            "neutered": pet.neutered,
            "photo_url": photo_url,
        },
        "owner": {
            "full_name": user.full_name if user else None,
            "pincode": decrypt_field(user.pincode) if (user and user.pincode) else None,
            "mobile_display": user.mobile_display if user else None,
            "delivery_address": user.delivery_address if user else None,
            "payment_method_pref": user.payment_method_pref if user else None,
            "saved_upi_id": decrypt_field(user.saved_upi_id) if (user and user.saved_upi_id) else None,
        },
        "preventive_records": preventive_records,
        "reminders": reminder_data,
        "documents": document_data,
        "diagnostic_results": diagnostic_results,
        "conditions": conditions_data,
        "contacts": contacts_data,
        "health_score": health_score,
        "nutrition": diet_items_data,
        "conflict_flags": conflict_rows,
        "vet_summary": vet_summary_payload,
        "life_stage": life_stage_payload,
        "health_conditions_summary": health_conditions_summary,
        "care_plan_v2": care_plan_v2,
        "diet_summary": diet_summary,
        "recognition": recognition_payload,
        "is_first_visit": is_first_visit,
        "cached_health_summary": cached_insights.get("health_summary"),
        "cached_vet_questions": cached_insights.get("vet_questions"),
        # Internal pet_id exposed only for intra-service use (not sent to frontend).
        # Allows callers to avoid a second validate_dashboard_token() call.
        "_pet_id": str(pet_id),
    }


async def get_document_file_for_token(
    db: Session,
    token: str,
    document_id: str,
) -> tuple[bytes, str, str]:
    """
    Retrieve raw document bytes for a dashboard token and document id.

    Security checks:
      - token must be valid and not revoked/expired.
      - document must belong to the token's pet.

    Returns:
      Tuple of (file_bytes, mime_type, filename).

    Raises:
      ValueError: token invalid, document missing, or file fetch failure.
    """
    dashboard_token = validate_dashboard_token(db, token)

    try:
        doc_uuid = UUID(document_id)
    except ValueError as exc:
        raise ValueError("Document not found.") from exc

    doc = (
        db.query(Document)
        .filter(
            Document.id == doc_uuid,
            Document.pet_id == dashboard_token.pet_id,
        )
        .first()
    )
    if not doc:
        raise ValueError("Document not found.")

    file_bytes = await download_from_supabase(
        doc.file_path,
        backend=getattr(doc, "storage_backend", "supabase"),
    )
    if not file_bytes:
        raise ValueError("Could not load document from storage.")

    filename = doc.file_path.split("/")[-1] if doc.file_path else "document"
    mime_type = doc.mime_type
    if not mime_type:
        ext = (doc.file_path or "").rsplit(".", 1)[-1].lower() if doc.file_path else ""
        mime_type = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
        }.get(ext, "application/octet-stream")
    return file_bytes, mime_type, filename


async def get_pet_photo_for_token(
    db: Session,
    token: str,
) -> tuple[bytes, str]:
    """
    Retrieve pet photo bytes for a dashboard token.

    Returns:
        Tuple of (file_bytes, mime_type).

    Raises:
        ValueError: If token invalid, pet has no photo, or download fails.
    """
    dashboard_token = validate_dashboard_token(db, token)

    pet = db.query(Pet).filter(Pet.id == dashboard_token.pet_id).first()
    if not pet or pet.is_deleted or not pet.photo_path:
        raise ValueError("Pet photo not found.")

    file_bytes = await download_from_supabase(pet.photo_path)
    if not file_bytes:
        raise ValueError("Could not load photo from storage.")

    # Infer MIME type from file extension.
    ext = pet.photo_path.rsplit(".", 1)[-1].lower() if "." in pet.photo_path else "jpg"
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
    mime_type = mime_map.get(ext, "image/jpeg")

    return file_bytes, mime_type


def update_pet_weight(
    db: Session,
    token: str,
    new_weight: float,
) -> dict:
    """
    Update a pet's weight via dashboard token.

    Weight is a simple field update — no recalculation needed.

    Args:
        db: SQLAlchemy database session.
        token: The dashboard access token string.
        new_weight: The new weight value (kg, Numeric(5,2)).

    Returns:
        Dictionary confirming the update.

    Raises:
        ValueError: If token is invalid or pet not found.
    """
    dashboard_token = validate_dashboard_token(db, token)
    pet = db.query(Pet).filter(Pet.id == dashboard_token.pet_id).first()

    if not pet or pet.is_deleted:
        raise ValueError("Pet not found or has been removed.")

    old_weight = pet.weight
    pet.weight = new_weight
    pet.weight_flagged = False
    db.commit()

    logger.info(
        "Pet weight updated via dashboard: pet_id=%s, "
        "old_weight=%s, new_weight=%s",
        str(pet.id),
        str(old_weight),
        str(new_weight),
    )

    return {
        "status": "updated",
        "name": pet.name,
        "old_weight": float(old_weight) if old_weight else None,
        "new_weight": float(new_weight),
    }


def update_preventive_date(
    db: Session,
    token: str,
    item_name: str,
    new_last_done_date: date,
    bulk_vaccine_update: bool = False,
) -> dict:
    """
    Update a preventive record's last_done_date via dashboard.

    This triggers a full recalculation:
        - next_due_date = last_done_date + recurrence_days (from DB)
        - status recalculated based on new next_due_date
        - Pending reminders for the old due date are invalidated

    Recurrence days are always read from preventive_master in DB
    — never hardcoded.

    Pending reminder invalidation:
        When a preventive date changes, any pending or sent reminders
        for the OLD next_due_date become stale. These reminders are
        marked as 'completed' to prevent duplicate sends. The next
        reminder engine run will create a new reminder for the
        updated due date if needed.

    Args:
        db: SQLAlchemy database session.
        token: The dashboard access token string.
        item_name: Name of the preventive item to update.
        new_last_done_date: The new last_done_date value.

    Returns:
        Dictionary with updated record details.

    Raises:
        ValueError: If token invalid, pet/record/master not found.
    """
    dashboard_token = validate_dashboard_token(db, token)
    pet_id = dashboard_token.pet_id

    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet or pet.is_deleted:
        raise ValueError("Pet not found or has been removed.")

    # Find the same record variant the dashboard currently surfaces:
    # latest active row for this item_name, preferring most recent completion.
    result = (
        db.query(PreventiveRecord, PreventiveMaster)
        .join(
            PreventiveMaster,
            PreventiveRecord.preventive_master_id == PreventiveMaster.id,
        )
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveMaster.item_name == item_name,
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
        raise ValueError(
            f"Preventive record not found for item: {item_name}"
        )

    record, master = result
    apply_to_all_vaccines = bulk_vaccine_update and _is_core_vaccine(master)

    if apply_to_all_vaccines:
        target_rows = (
            db.query(PreventiveRecord, PreventiveMaster)
            .join(
                PreventiveMaster,
                PreventiveRecord.preventive_master_id == PreventiveMaster.id,
            )
            .filter(
                PreventiveRecord.pet_id == pet_id,
                PreventiveRecord.status != "cancelled",
            )
            .all()
        )
        targets = [
            (r, m)
            for r, m in target_rows
            if _is_core_vaccine(m)
        ]
        if not targets:
            targets = [(record, master)]
    else:
        targets = [(record, master)]

    # Store old values from the first target for response compatibility.
    first_record, _first_master = targets[0]
    old_last_done = first_record.last_done_date

    invalidated_count = 0
    for target_record, target_master in targets:
        old_next_due = target_record.next_due_date

        # --- Update last_done_date ---
        target_record.last_done_date = new_last_done_date

        # --- Recalculate next_due_date ---
        # Respect custom recurrence when present; otherwise use master default.
        effective_recurrence_days = (
            target_record.custom_recurrence_days
            if target_record.custom_recurrence_days
            else target_master.recurrence_days
        )
        target_record.next_due_date = compute_next_due_date(
            new_last_done_date, effective_recurrence_days
        )

        # --- Recalculate status ---
        target_record.status = compute_status(
            target_record.next_due_date, target_master.reminder_before_days
        )

        # --- Invalidate pending reminders for old due date ---
        stale_reminders = (
            db.query(Reminder)
            .filter(
                Reminder.preventive_record_id == target_record.id,
                Reminder.next_due_date == old_next_due,
                Reminder.status.in_(["pending", "sent"]),
            )
            .all()
        )

        for reminder in stale_reminders:
            reminder.status = "completed"
            invalidated_count += 1

    db.commit()

    updated_count = len(targets)
    new_next_due = first_record.next_due_date
    new_status = first_record.status

    logger.info(
        "Preventive date updated via dashboard: pet_id=%s, item=%s, "
        "old_done=%s, new_done=%s, new_due=%s, new_status=%s, "
        "updated_records=%d, reminders_invalidated=%d",
        str(pet_id),
        item_name,
        str(old_last_done),
        str(new_last_done_date),
        str(new_next_due),
        new_status,
        updated_count,
        invalidated_count,
    )

    return {
        "status": "updated",
        "item_name": item_name,
        "old_last_done_date": str(old_last_done),
        "new_last_done_date": str(new_last_done_date),
        "new_next_due_date": str(new_next_due),
        "record_status": new_status,
        "updated_records": updated_count,
        "reminders_invalidated": invalidated_count,
    }


async def retry_document_extraction(
    db: Session,
    token: str,
    document_id: str,
) -> dict:
    """
    Retry GPT extraction for a failed document via dashboard token.

    Validates token ownership, verifies the document belongs to the
    token's pet and has extraction_status='failed', then re-downloads
    the file from Supabase and runs the extraction pipeline again.

    Args:
        db: SQLAlchemy database session.
        token: The dashboard access token string.
        document_id: UUID string of the document to retry.

    Returns:
        Dictionary with extraction result status.

    Raises:
        ValueError: If token invalid, document not found, or not in failed state.
    """
    from app.services.document_upload import download_from_supabase
    from app.services.gpt_extraction import extract_and_process_document

    dashboard_token = validate_dashboard_token(db, token)
    pet_id = dashboard_token.pet_id

    # Verify document exists, belongs to this pet, and is in failed state.
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.pet_id == pet_id,
        )
        .first()
    )

    if not doc:
        raise ValueError("Document not found.")

    if doc.extraction_status != "failed":
        raise ValueError("Only failed documents can be retried.")

    # Download file from storage (GCP or Supabase) for re-extraction.
    file_bytes = await download_from_supabase(
        doc.file_path,
        backend=getattr(doc, "storage_backend", "supabase"),
    )
    if not file_bytes:
        raise ValueError("Could not download document from storage. Please re-upload via WhatsApp.")

    # Reset status to pending before retrying.
    doc.extraction_status = "pending"
    db.commit()

    try:
        result = await asyncio.wait_for(
            extract_and_process_document(
                db, doc.id,
                f"[file: {doc.file_path}]",
                file_bytes=file_bytes,
            ),
            timeout=120,
        )

        logger.info(
            "Dashboard retry extraction succeeded: doc_id=%s, pet_id=%s",
            document_id,
            str(pet_id),
        )

        return {
            "status": "success",
            "document_id": document_id,
            "extraction_result": result,
        }
    except Exception as e:
        # Mark as failed again if extraction fails.
        doc.extraction_status = "failed"
        db.commit()
        logger.error(
            "Dashboard retry extraction failed: doc_id=%s, error=%s",
            document_id,
            str(e),
        )
        raise ValueError(f"Extraction failed: {str(e)}")


def get_health_trends(db: Session, token: str) -> dict:
    """
    Build health trend data from preventive record last_done_dates.

    Groups completed preventive items by month to show activity over time.
    Each month shows how many items were completed (last_done_date falls
    in that month) and the status breakdown at that point.

    Args:
        db: SQLAlchemy database session.
        token: The dashboard access token string.

    Returns:
        Dictionary with monthly trend data and per-item timeline.

    Raises:
        ValueError: If token is invalid or pet not found.
    """
    from collections import defaultdict

    dashboard_token = validate_dashboard_token(db, token)
    pet_id = dashboard_token.pet_id

    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet or pet.is_deleted:
        raise ValueError("Pet not found or has been removed.")

    # Load all preventive records with master info.
    preventive_data = (
        db.query(PreventiveRecord, PreventiveMaster)
        .join(
            PreventiveMaster,
            PreventiveRecord.preventive_master_id == PreventiveMaster.id,
        )
        .filter(PreventiveRecord.pet_id == pet_id)
        .all()
    )

    # --- Build per-item timeline ---
    # Each item shows its last_done_date for the timeline view.
    item_timeline = []
    for record, master in preventive_data:
        if record.last_done_date:
            item_timeline.append({
                "item_name": master.item_name,
                "category": master.category,
                "last_done_date": str(record.last_done_date),
                "status": record.status,
            })

    vaccine_item_names = {"Rabies Vaccine", "Core Vaccine", "Feline Core"}

    # --- Group completions by month ---
    # Key: "YYYY-MM", Value: count of items completed that month.
    monthly_completions: dict[str, int] = defaultdict(int)
    vaccine_monthly: dict[str, int] = defaultdict(int)
    vaccine_timeline = []
    for record, master in preventive_data:
        if record.last_done_date:
            month_key = record.last_done_date.strftime("%Y-%m")
            monthly_completions[month_key] += 1
            if master.item_name in vaccine_item_names:
                vaccine_monthly[month_key] += 1
                vaccine_timeline.append({
                    "vaccine_name": master.item_name,
                    "last_done_date": str(record.last_done_date),
                    "next_due_date": str(record.next_due_date) if record.next_due_date else None,
                })

    # Sort months chronologically.
    sorted_months = sorted(monthly_completions.keys())

    monthly_data = []
    for month in sorted_months:
        monthly_data.append({
            "month": month,
            "items_completed": monthly_completions[month],
        })

    # --- Current status summary ---
    total = len(preventive_data)
    status_counts = defaultdict(int)
    for record, master in preventive_data:
        if record.status != "cancelled" and not record.last_done_date and not record.next_due_date:
            status_counts["incomplete"] += 1
        else:
            status_counts[record.status] += 1

    # --- Diagnostic document frequency by month ---
    # Counts documents categorized as "Diagnostic" per month — aggregated in SQL.
    _diag_rows = (
        db.query(
            func.to_char(Document.created_at, "YYYY-MM").label("month"),
            func.count().label("count"),
        )
        .filter(
            Document.pet_id == pet_id,
            Document.document_category == "Diagnostic",
            Document.extraction_status == "success",
        )
        .group_by(func.to_char(Document.created_at, "YYYY-MM"))
        .order_by(func.to_char(Document.created_at, "YYYY-MM"))
        .all()
    )
    diagnostic_trends = [{"month": row.month, "count": row.count} for row in _diag_rows]

    return {
        "monthly_completions": monthly_data,
        "item_timeline": sorted(
            item_timeline,
            key=lambda x: x["last_done_date"],
            reverse=True,
        ),
        "status_summary": {
            "total": total,
            "up_to_date": status_counts.get("up_to_date", 0),
            "upcoming": status_counts.get("upcoming", 0),
            "overdue": status_counts.get("overdue", 0),
            "incomplete": status_counts.get("incomplete", 0),
            "cancelled": status_counts.get("cancelled", 0),
        },
        "diagnostic_trends": diagnostic_trends,
        "vaccine_metrics": {
            "monthly_vaccinations": [
                {"month": month, "count": vaccine_monthly[month]}
                for month in sorted(vaccine_monthly.keys())
            ],
            "vaccine_timeline": sorted(
                vaccine_timeline,
                key=lambda x: x["last_done_date"],
                reverse=True,
            ),
        },
    }
