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
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.core.encryption import decrypt_field
from app.models.condition import Condition
from app.models.conflict_flag import ConflictFlag
from app.models.contact import Contact
from app.models.dashboard_token import DashboardToken
from app.models.diagnostic_test_result import DiagnosticTestResult
from app.models.diet_item import DietItem
from app.models.document import Document
from app.models.pet import Pet
from app.models.pet_ai_insight import PetAiInsight
from app.models.custom_preventive_item import CustomPreventiveItem
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.services.ai_insights_service import AI_INSIGHT_CACHE_DAYS, generate_recognition_bullets
from app.services.care_plan_engine import compute_care_plan, get_preventive_baseline_days, _normalize_item_name
from app.services.document_upload import download_from_supabase
from app.services.gpt_extraction import _infer_document_category, _resolve_document_category
from app.services.life_stage_service import get_life_stage_data
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


async def _record_dashboard_visit_bg(user_id, pet_id, token: str) -> None:
    """Fire-and-forget insert of a DashboardVisit row on its own DB session.

    Separated from the main dashboard transaction so the response doesn't
    block on an extra write that the caller never reads back.
    """
    try:
        from app.models.dashboard_visit import DashboardVisit
        bg_db = SessionLocal()
        try:
            bg_db.add(DashboardVisit(user_id=user_id, pet_id=pet_id, token=token))
            bg_db.commit()
        finally:
            bg_db.close()
    except Exception:
        logger.warning("Background dashboard visit insert failed for token=%s...", token[:8])


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
    import time as _time
    _t0 = _time.monotonic()

    # --- Validate token ---
    dashboard_token = validate_dashboard_token(db, token)
    pet_id = dashboard_token.pet_id

    # --- Load Pet + User together — avoids a second round-trip for the owner row ---
    from sqlalchemy.orm import joinedload
    pet = (
        db.query(Pet)
        .options(joinedload(Pet.user))
        .filter(Pet.id == pet_id)
        .first()
    )
    if not pet or pet.is_deleted:
        raise ValueError("Pet not found or has been removed.")
    user = pet.user  # already loaded — no extra query

    # =========================================================================
    # PHASE 1 — Submit independent DB queries to thread pool
    # =========================================================================
    # With cross-region deployment (Render Oregon → Supabase Southeast) each
    # DB round-trip costs ~150 ms. 7 queries run concurrently in background
    # threads while Phase 2 executes on the event loop, collapsing ~1050 ms
    # of sequential network overhead to ~150 ms.
    # Each helper opens its own session so there is no shared-state risk.
    # =========================================================================
    _exec_loop = asyncio.get_event_loop()
    _pet_id_str = str(pet_id)
    _pet_species = pet.species

    # TTL map for AI insight cache (used inside _fetch_insights_sync below).
    _INSIGHT_TTL: dict[str, timedelta] = {
        "diet_summary":         timedelta(hours=24),
        "recognition_bullets":  timedelta(hours=24),
        "care_plan_reasons":    timedelta(hours=1),
        "health_summary":       timedelta(days=AI_INSIGHT_CACHE_DAYS),
        "vet_questions":        timedelta(days=AI_INSIGHT_CACHE_DAYS),
        "health_conditions_v2": timedelta(days=AI_INSIGHT_CACHE_DAYS),
        "nutrition_analysis":   timedelta(days=AI_INSIGHT_CACHE_DAYS),
    }

    def _fetch_conditions_sync():
        own_db = SessionLocal()
        try:
            rows = (
                own_db.query(Condition)
                .options(
                    selectinload(Condition.medications),
                    selectinload(Condition.monitoring),
                )
                .filter(Condition.pet_id == pet_id, Condition.is_active == True)
                .order_by(Condition.created_at.desc())
                .all()
            )
            own_db.expunge_all()  # detach while keeping eager-loaded attrs
            return rows
        except Exception as exc:
            logger.warning("parallel _fetch_conditions failed pet=%s: %s", _pet_id_str, exc)
            return []
        finally:
            own_db.close()

    def _fetch_diet_sync():
        own_db = SessionLocal()
        try:
            rows = (
                own_db.query(DietItem)
                .filter(DietItem.pet_id == pet_id)
                .order_by(DietItem.created_at.asc())
                .all()
            )
            own_db.expunge_all()
            return rows
        except Exception as exc:
            logger.warning("parallel _fetch_diet failed pet=%s: %s", _pet_id_str, exc)
            return []
        finally:
            own_db.close()

    def _fetch_insights_sync():
        _now_q = datetime.utcnow()
        own_db = SessionLocal()
        try:
            rows = (
                own_db.query(PetAiInsight)
                .filter(
                    PetAiInsight.pet_id == pet_id,
                    PetAiInsight.insight_type.in_(list(_INSIGHT_TTL)),
                )
                .all()
            )
            # Build cache dict in-thread (pure Python, no further I/O).
            return {
                row.insight_type: row.content_json
                for row in rows
                if row.generated_at >= _now_q - _INSIGHT_TTL.get(row.insight_type, timedelta(hours=24))
            }
        except Exception as exc:
            logger.warning("parallel _fetch_insights failed pet=%s: %s", _pet_id_str, exc)
            return {}
        finally:
            own_db.close()

    def _fetch_documents_sync():
        own_db = SessionLocal()
        try:
            docs = (
                own_db.query(Document)
                .filter(
                    Document.pet_id == pet_id,
                    Document.extraction_status.in_(["pending", "success", "failed", "rejected"]),
                )
                .order_by(Document.created_at.desc())
                .all()
            )
            result = []
            for doc in docs:
                inferred_category = _infer_document_category(
                    document_name=doc.document_name,
                    file_path=doc.file_path,
                    items=[],
                    vaccination_details=[],
                    diagnostic_values=[],
                )
                result.append({
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
            return result
        except Exception as exc:
            logger.warning("parallel _fetch_documents failed pet=%s: %s", _pet_id_str, exc)
            return []
        finally:
            own_db.close()

    def _fetch_diagnostics_sync():
        own_db = SessionLocal()
        try:
            rows = (
                own_db.query(DiagnosticTestResult)
                .filter(DiagnosticTestResult.pet_id == pet_id)
                .order_by(
                    DiagnosticTestResult.observed_at.desc().nullslast(),
                    DiagnosticTestResult.created_at.desc(),
                )
                .all()
            )
            return [
                {
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
                }
                for row in rows
            ]
        except Exception as exc:
            logger.warning("parallel _fetch_diagnostics failed pet=%s: %s", _pet_id_str, exc)
            return []
        finally:
            own_db.close()

    def _fetch_contacts_sync():
        own_db = SessionLocal()
        try:
            rows = (
                own_db.query(Contact)
                .filter(Contact.pet_id == pet_id)
                .order_by(Contact.created_at.desc())
                .all()
            )
            return [
                {
                    "id": str(c.id),
                    "role": c.role,
                    "name": c.name,
                    "clinic_name": c.clinic_name,
                    "phone": c.phone,
                    "email": c.email,
                    "address": c.address,
                    "source": c.source,
                    "source_document_name": c.source_document_name,
                    "source_document_category": c.source_document_category,
                    "created_at": str(c.created_at) if c.created_at else None,
                }
                for c in rows
            ]
        except Exception as exc:
            logger.warning("parallel _fetch_contacts failed pet=%s: %s", _pet_id_str, exc)
            return []
        finally:
            own_db.close()

    def _fetch_health_masters_sync():
        own_db = SessionLocal()
        try:
            rows = (
                own_db.query(PreventiveMaster)
                .filter(
                    PreventiveMaster.circle == "health",
                    PreventiveMaster.species.in_([_pet_species, "both"]),
                )
                .all()
            )
            own_db.expunge_all()
            return rows
        except Exception as exc:
            logger.warning("parallel _fetch_health_masters failed pet=%s: %s", _pet_id_str, exc)
            return []
        finally:
            own_db.close()

    # Submit all 7 to the default thread-pool executor.
    # They start running immediately while Phase 2 runs below.
    _fut_conditions  = _exec_loop.run_in_executor(None, _fetch_conditions_sync)
    _fut_diet        = _exec_loop.run_in_executor(None, _fetch_diet_sync)
    _fut_insights    = _exec_loop.run_in_executor(None, _fetch_insights_sync)
    _fut_documents   = _exec_loop.run_in_executor(None, _fetch_documents_sync)
    _fut_diagnostics = _exec_loop.run_in_executor(None, _fetch_diagnostics_sync)
    _fut_contacts    = _exec_loop.run_in_executor(None, _fetch_contacts_sync)
    _fut_masters     = _exec_loop.run_in_executor(None, _fetch_health_masters_sync)

    # =========================================================================
    # PHASE 2 — Sequential main-session queries (run while Phase 1 executes)
    # =========================================================================
    # Only queries with inter-dependencies stay on the main session:
    # visit_count → preventive_data → reminders → conflict_flags.
    # =========================================================================

    # --- Record dashboard visit for nudge level tracking (N8) ---
    # Best-effort: never crash the dashboard load on a logging failure.
    # Count previous visits BEFORE inserting new one to determine first visit.
    is_first_visit = True
    try:
        from app.models.dashboard_visit import DashboardVisit
        previous_visit_count = (
            db.query(func.count(DashboardVisit.id))
            .filter(DashboardVisit.pet_id == pet_id)
            .scalar()
            or 0
        )
        is_first_visit = previous_visit_count == 0
        asyncio.create_task(
            _record_dashboard_visit_bg(pet.user_id, pet_id, token)
        )
    except Exception:
        logger.warning("Failed to record dashboard visit for token=%s...", token[:8])

    # --- Load preventive records with master item names ---
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
        return (
            r.last_done_date or date.min,
            r.next_due_date or date.min,
            r.created_at.date() if getattr(r, "created_at", None) else date.min,
        )

    vaccine_latest_by_name: dict[str, tuple[PreventiveRecord, PreventiveMaster]] = {}
    non_vaccine_records: list[tuple[PreventiveRecord, PreventiveMaster]] = []

    _is_adult_dog = (
        pet.species == "dog"
        and pet.dob is not None
        and (date.today() - pet.dob).days >= 365
    )

    for record, master in preventive_data:
        if _is_adult_dog and master.recurrence_days and master.recurrence_days >= 36500:
            continue
        if _is_vaccine_item_name(master.item_name) and not master.is_mandatory and not record.last_done_date:
            continue
        if _is_vaccine_item_name(master.item_name):
            existing = vaccine_latest_by_name.get(master.item_name)
            if not existing or _record_sort_key(record) >= _record_sort_key(existing[0]):
                vaccine_latest_by_name[master.item_name] = (record, master)
        else:
            non_vaccine_records.append((record, master))

    selected_records = non_vaccine_records + list(vaccine_latest_by_name.values())
    selected_records.sort(
        key=lambda rm: (
            rm[0].next_due_date is None,
            rm[0].next_due_date or date.max,
        )
    )

    preventive_records = []
    for record, master in selected_records:
        test_type = _normalize_item_name(master.item_name)
        _LIFE_STAGE_TYPES = {"deworming", "tick_flea"}

        if record.custom_recurrence_days:
            effective_recurrence = record.custom_recurrence_days
        elif test_type in _LIFE_STAGE_TYPES:
            effective_recurrence = get_preventive_baseline_days(pet, test_type)
        else:
            effective_recurrence = master.recurrence_days

        if record.last_done_date and test_type in _LIFE_STAGE_TYPES:
            display_next_due = str(record.last_done_date + timedelta(days=effective_recurrence))
        else:
            display_next_due = str(record.next_due_date) if record.next_due_date else None

        preventive_records.append({
            "item_name": master.item_name,
            "category": master.category,
            "circle": master.circle,
            "last_done_date": str(record.last_done_date) if record.last_done_date else None,
            "next_due_date": display_next_due,
            "status": record.status,
            "recurrence_days": effective_recurrence,
            "custom_recurrence_days": record.custom_recurrence_days,
            "medicine_dependent": master.medicine_dependent,
            "medicine_name": record.medicine_name if hasattr(record, "medicine_name") and record.medicine_name else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "is_core": bool(master.is_core) if master.is_core is not None else False,
        })

    # --- Load active reminders ---
    reminders = (
        db.query(Reminder, PreventiveRecord, PreventiveMaster)
        .join(PreventiveRecord, Reminder.preventive_record_id == PreventiveRecord.id)
        .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
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

    # --- Load pending conflict flags ---
    # Store (record, master) tuples so the loop can read master.item_name
    # directly from the tuple instead of triggering a lazy load on the
    # record.preventive_master relationship.
    conflict_rows = []
    pet_rec_map = {str(r.id): (r, m) for r, m in preventive_data}
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
            r_m = pet_rec_map.get(str(cf.preventive_record_id))
            item_name = None
            if r_m:
                r, m = r_m
                item_name = m.item_name  # from tuple — no lazy load
                if not item_name and r.custom_preventive_item:
                    item_name = r.custom_preventive_item.item_name
            conflict_rows.append({
                "id": str(cf.id),
                "item_name": item_name,
                "existing_date": str(r_m[0].last_done_date) if r_m and r_m[0].last_done_date else None,
                "new_date": str(cf.new_date),
                "status": cf.status,
                "created_at": str(cf.created_at) if cf.created_at else None,
            })

    # =========================================================================
    # PHASE 3 — Await all parallel results
    # =========================================================================
    # Phase 1 queries finish in ~150 ms. By the time we reach here Phase 2
    # has taken ~4 RTTs (~600 ms), so futures are almost certainly complete
    # and this gather returns immediately.
    # =========================================================================
    (condition_rows, diet_rows, _insight_cache,
     document_data, diagnostic_results, contacts_data, health_masters) = await asyncio.gather(
        _fut_conditions, _fut_diet, _fut_insights,
        _fut_documents, _fut_diagnostics, _fut_contacts, _fut_masters,
    )

    # =========================================================================
    # PHASE 4 — Process parallel results
    # =========================================================================

    # --- Inject preventive_master items with no record yet ---
    # health_masters from parallel fetch; preventive_records built in Phase 2.
    existing_names = {r["item_name"] for r in preventive_records}
    for master in health_masters:
        if _is_adult_dog and master.recurrence_days and master.recurrence_days >= 36500:
            continue
        if _is_vaccine_item_name(master.item_name) and not master.is_mandatory:
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

    # Health score removed — not computed.
    health_score = None

    # _insight_cache already built inside _fetch_insights_sync (Phase 1 result).

    # --- Build conditions_data from parallel-fetched condition_rows ---
    # selectinload relationships (medications, monitoring) remain accessible
    # after expunge_all() because they were eagerly populated before session close.
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

    # --- Format diet items from parallel-fetched diet_rows ---
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

    # document_data, diagnostic_results, contacts_data are plain dicts
    # already built inside their respective Phase 1 sync helpers.

    # --- Dashboard Rebuild v2 enrichments ---
    # Timeout for non-DB enrichments (life_stage, vet_summary are pure-DB/sync;
    # only care_plan computation touches the DB synchronously). Kept at 8s —
    # enough for any single fast operation. GPT-intensive calls (diet_summary,
    # recognition_bullets, care_plan_reasons) are read from the pet_ai_insights
    # cache only; background precompute (precompute_service) warms them before
    # the dashboard link is sent, so cache should almost always be warm.
    _ENRICHMENT_TIMEOUT_SECONDS = 8

    async def _safe_async_call(label: str, default, coro):
        try:
            return await asyncio.wait_for(coro, timeout=_ENRICHMENT_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.error(
                "%s timed out after %ds for pet=%s",
                label, _ENRICHMENT_TIMEOUT_SECONDS, pet_id,
            )
            return default
        except Exception as exc:
            logger.error("%s failed for pet=%s: %s", label, pet_id, exc)
            return default

    async def _safe_sync_call(label: str, default, fn, *args):
        # Kept for backward compatibility — no longer used for compute_care_plan
        # or get_vet_summary (those run via _run_care_plan / _run_vet_summary).
        try:
            return fn(*args)
        except Exception as exc:
            logger.error("%s failed for pet=%s: %s", label, pet_id, exc)
            return default

    # --- Read diet_summary and recognition_bullets from pre-loaded batch cache ---
    # _insight_cache was populated in one round-trip above; no extra DB queries needed.
    _cached_diet = _insight_cache.get("diet_summary")
    diet_summary: dict = (
        _cached_diet if isinstance(_cached_diet, dict)
        else {"macros": [], "missing_micros": []}
    )

    recognition_bullets: list = []
    _cached_bullets = _insight_cache.get("recognition_bullets")
    if isinstance(_cached_bullets, list):
        # Staleness check 1: cache says "no diet entries" but diet rows now exist.
        # Use already-loaded diet_rows — avoids an extra COUNT query.
        _diet_stale = any(
            isinstance(b, dict) and "no diet entries" in (b.get("label") or "").lower()
            for b in _cached_bullets
        )
        # Staleness check 2: cache says "0 preventive" but completed core records now exist.
        # Use already-loaded preventive_data — avoids an extra COUNT query.
        _prev_stale = any(
            isinstance(b, dict) and "0 preventive" in (b.get("label") or "").lower()
            for b in _cached_bullets
        )
        _has_diet = len(diet_rows) > 0
        _has_preventive = any(
            r.last_done_date is not None and (m.is_core or r.custom_preventive_item_id is not None)
            for r, m in preventive_data
        )
        if not (_diet_stale and _has_diet) and not (_prev_stale and _has_preventive):
            recognition_bullets = _cached_bullets

    # If cache is cold/stale, regenerate inline — generate_recognition_bullets is
    # pure-DB (no GPT) so it's safe to call on the critical path.
    if not recognition_bullets:
        try:
            recognition_bullets = await generate_recognition_bullets(db, pet)
        except Exception as _exc:
            logger.warning(
                "Inline recognition_bullets generation failed for pet=%s: %s", pet_id, _exc
            )

    empty_care_plan = {"continue_items": [], "attend_items": [], "add_items": []}

    # compute_care_plan and get_vet_summary are sync functions that hit the DB.
    # Running them directly on the event loop blocks every concurrent request.
    # Each gets its own session so they can run in thread-pool workers without
    # sharing session state with each other or with the main coroutine.

    async def _run_care_plan() -> dict:
        def _sync() -> dict:
            own_db = SessionLocal()
            try:
                own_pet = own_db.query(Pet).filter(Pet.id == pet_id).first()
                return compute_care_plan(own_db, own_pet) if own_pet else empty_care_plan
            except Exception as exc:
                logger.error("compute_care_plan failed for pet=%s: %s", pet_id, exc)
                return empty_care_plan
            finally:
                own_db.close()

        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _sync),
                timeout=_ENRICHMENT_TIMEOUT_SECONDS,
            )
        except (TimeoutError, asyncio.TimeoutError):
            logger.error("compute_care_plan timed out after %ds for pet=%s", _ENRICHMENT_TIMEOUT_SECONDS, pet_id)
            return empty_care_plan

    async def _run_vet_summary():
        def _sync():
            own_db = SessionLocal()
            try:
                return get_vet_summary(own_db, pet_id)
            except Exception as exc:
                logger.error("get_vet_summary failed for pet=%s: %s", pet_id, exc)
                return None
            finally:
                own_db.close()

        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _sync),
                timeout=_ENRICHMENT_TIMEOUT_SECONDS,
            )
        except (TimeoutError, asyncio.TimeoutError):
            logger.error("get_vet_summary timed out after %ds for pet=%s", _ENRICHMENT_TIMEOUT_SECONDS, pet_id)
            return None

    care_plan_v2, life_stage_data, vet_summary = await asyncio.gather(
        _run_care_plan(),
        _safe_async_call("life_stage_service.get_life_stage_data", None, get_life_stage_data(db, pet)),
        _run_vet_summary(),
    )

    care_plan_v2 = _normalize_care_plan_shape(care_plan_v2)

    orderable_items = _collect_orderable_items(care_plan_v2)

    # --- Read care_plan_reasons from pre-loaded batch cache (1h TTL) ---
    _cached_reasons = _insight_cache.get("care_plan_reasons")
    care_plan_reasons: dict = (
        _cached_reasons.get("reasons", {}) if isinstance(_cached_reasons, dict) else {}
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
            "insights": life_stage_data.insights,
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

    # --- Serve health_summary, vet_questions, health_conditions_v2, nutrition_analysis
    #     from the pre-loaded batch cache — no extra DB query needed. ---
    cached_insights: dict[str, dict | None] = {
        "health_summary":       _insight_cache.get("health_summary"),       # type: ignore[assignment]
        "vet_questions":        _insight_cache.get("vet_questions"),         # type: ignore[assignment]
        "health_conditions_v2": _insight_cache.get("health_conditions_v2"), # type: ignore[assignment]
        "nutrition_analysis":   _insight_cache.get("nutrition_analysis"),   # type: ignore[assignment]
    }

    # --- Build response (no internal IDs exposed) ---
    # photo_url: serve via dashboard endpoint if pet has a photo, else None.
    photo_url = f"/dashboard/{token}/pet-photo" if pet.photo_path else None

    _result = {
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
        "health_conditions_v2": cached_insights.get("health_conditions_v2"),
        "nutrition_analysis": cached_insights.get("nutrition_analysis"),
        # Internal pet_id exposed only for intra-service use (not sent to frontend).
        # Allows callers to avoid a second validate_dashboard_token() call.
        "_pet_id": str(pet_id),
    }
    logger.info(
        "get_dashboard_data: pet=%s elapsed=%.3fs", str(pet_id), _time.monotonic() - _t0
    )
    return _result


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
