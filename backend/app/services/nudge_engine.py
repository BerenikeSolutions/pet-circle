"""
PetCircle Phase 1 — Nudge Engine Service

Generates prioritized health action nudges for pets across 7 categories:
vaccine, deworming, flea, condition, nutrition, grooming, checkup.

Two entry points:
    - generate_nudges(db, pet_id): For dashboard — returns cached or fresh nudges
    - run_nudge_engine(db): For daily cron — regenerates nudges for all active pets
"""

import logging
import re
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.constants import (
    NUDGE_CACHE_HOURS,
    NUDGE_PRIORITY_ORDER,
    NUDGE_SOURCE_ORDER,
    NUDGE_TRIGGER_CRON,
)
from app.models.condition import Condition
from app.models.diagnostic_test_result import DiagnosticTestResult
from app.models.diet_item import DietItem
from app.models.hygiene_preference import HygienePreference
from app.models.nudge import Nudge
from app.models.pet import Pet
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.user import User
from app.services.nudge_config_service import get_nudge_config_int

logger = logging.getLogger(__name__)

# Keyword sets for matching preventive_master items to nudge categories.
# Keep this in sync with reminder and trends classifiers so generic
# "vaccines done" updates include all dog/cat vaccine variants.
VACCINE_KEYWORDS = {
    "vaccine",
    "rabies",
    "dhpp",
    "core vaccine",
    "feline core",
    "bordetella",
    "kennel cough",
    "nobivac",
    "coronavirus",
    "ccov",
}
DEWORMING_KEYWORDS = {"deworming", "deworm"}
FLEA_KEYWORDS = {"tick", "flea"}
CHECKUP_KEYWORDS = {"checkup", "annual", "wellness", "blood test", "preventive blood"}


def _classify_item(item_name: str) -> str | None:
    """Classify a preventive_master item_name into a nudge category."""
    name_lower = item_name.lower()
    if re.search(r"\b\d+\s*[- ]?in\s*[- ]?1\b", name_lower):
        return "vaccine"
    for kw in VACCINE_KEYWORDS:
        if kw in name_lower:
            return "vaccine"
    for kw in DEWORMING_KEYWORDS:
        if kw in name_lower:
            return "deworming"
    for kw in FLEA_KEYWORDS:
        if kw in name_lower:
            return "flea"
    for kw in CHECKUP_KEYWORDS:
        if kw in name_lower:
            return "checkup"
    return None


def _record_item_name(record: PreventiveRecord) -> str:
    """Resolve a human-readable preventive item name for master/custom records."""
    if record.preventive_master and record.preventive_master.item_name:
        return record.preventive_master.item_name
    if record.custom_preventive_item and record.custom_preventive_item.item_name:
        return record.custom_preventive_item.item_name
    return record.medicine_name or "Unknown"


def _make_nudge(pet_id, category: str, priority: str, title: str, message: str,
                mandatory: bool = False, icon: str | None = None,
                source: str = "record", trigger_type: str = NUDGE_TRIGGER_CRON) -> Nudge:
    """Create a Nudge object (not yet added to session)."""
    return Nudge(
        pet_id=pet_id,
        category=category,
        priority=priority,
        icon=icon,
        title=title,
        message=message,
        mandatory=mandatory,
        source=source,
        trigger_type=trigger_type,
    )


# ──────────────────────────────────────────────────────────────────
# Category generators
# ──────────────────────────────────────────────────────────────────

def _generate_vaccine_nudges(db: Session, pet_id, pet_name: str, species: str) -> list[Nudge]:
    """Generate nudges for overdue/upcoming/missing vaccines."""
    nudges = []
    today = date.today()
    records = (
        db.query(PreventiveRecord)
        .options(
            selectinload(PreventiveRecord.preventive_master),
            selectinload(PreventiveRecord.custom_preventive_item),
        )
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveRecord.status != "cancelled",
        )
        .all()
    )

    for rec in records:
        item_name = _record_item_name(rec)
        if _classify_item(item_name) != "vaccine":
            continue

        if rec.status == "overdue":
            nudges.append(_make_nudge(
                pet_id, "vaccine", "urgent",
                f"{item_name} is overdue",
                f"{pet_name}'s {item_name} is past due. Please schedule it soon.",
                mandatory=True, icon="💉",
            ))
        elif rec.next_due_date and (rec.next_due_date - today).days <= 7 and rec.status != "up_to_date":
            nudges.append(_make_nudge(
                pet_id, "vaccine", "high",
                f"{item_name} due soon",
                f"{pet_name}'s {item_name} is due within 7 days.",
                icon="💉",
            ))

    # Check for vaccines with no record at all
    masters = (
        db.query(PreventiveMaster)
        .filter(PreventiveMaster.species.in_([species, "both"]))
        .all()
    )
    recorded_master_ids = {r.preventive_master_id for r in records}
    for m in masters:
        if _classify_item(m.item_name) == "vaccine" and m.id not in recorded_master_ids:
            nudges.append(_make_nudge(
                pet_id, "vaccine", "medium",
                f"No {m.item_name} record",
                f"We have no record of {m.item_name} for {pet_name}. Upload a document or update manually.",
                icon="💉",
            ))

    return nudges


def _get_medicine_warning(medicine_name: str | None, db: Session) -> str:
    """Return a warning suffix from product_medicines.notes for the given medicine.

    Returns an empty string when medicine_name is absent or not found in catalog.
    Only TOXIC warnings (e.g., "TOXIC TO CATS") are included in nudge messages.
    """
    if not medicine_name:
        return ""
    try:
        from app.models.product_medicines import ProductMedicines

        med = (
            db.query(ProductMedicines)
            .filter(
                ProductMedicines.active == True,
                ProductMedicines.product_name.ilike(f"%{medicine_name}%"),
            )
            .first()
        )
        if med and med.notes and "toxic" in med.notes.lower():
            return f" ⚠️ {med.notes}"
    except Exception:
        pass
    return ""


def _generate_deworming_nudges(db: Session, pet_id, pet_name: str, species: str) -> list[Nudge]:
    """Generate nudges for overdue/upcoming deworming."""
    nudges = []
    today = date.today()
    records = (
        db.query(PreventiveRecord)
        .options(
            selectinload(PreventiveRecord.preventive_master),
            selectinload(PreventiveRecord.custom_preventive_item),
        )
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveRecord.status != "cancelled",
        )
        .all()
    )

    for rec in records:
        item_name = _record_item_name(rec)
        if _classify_item(item_name) != "deworming":
            continue

        warning = _get_medicine_warning(rec.medicine_name, db)
        if rec.status == "overdue":
            nudges.append(_make_nudge(
                pet_id, "deworming", "urgent",
                f"{item_name} is overdue",
                f"{pet_name}'s {item_name} is past due.{warning}",
                mandatory=True, icon="💊",
            ))
        elif rec.next_due_date and (rec.next_due_date - today).days <= 7 and rec.status != "up_to_date":
            nudges.append(_make_nudge(
                pet_id, "deworming", "high",
                f"{item_name} due soon",
                f"{pet_name}'s {item_name} is due within 7 days.{warning}",
                icon="💊",
            ))

    return nudges


def _generate_flea_nudges(db: Session, pet_id, pet_name: str, species: str) -> list[Nudge]:
    """Generate nudges for overdue/upcoming flea & tick treatment."""
    nudges = []
    today = date.today()
    records = (
        db.query(PreventiveRecord)
        .options(
            selectinload(PreventiveRecord.preventive_master),
            selectinload(PreventiveRecord.custom_preventive_item),
        )
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveRecord.status != "cancelled",
        )
        .all()
    )

    for rec in records:
        item_name = _record_item_name(rec)
        if _classify_item(item_name) != "flea":
            continue

        warning = _get_medicine_warning(rec.medicine_name, db)
        if rec.status == "overdue":
            nudges.append(_make_nudge(
                pet_id, "flea", "urgent",
                f"{item_name} is overdue",
                f"{pet_name}'s {item_name} is past due.{warning}",
                icon="🐛",
            ))
        elif rec.next_due_date and (rec.next_due_date - today).days <= 7 and rec.status != "up_to_date":
            nudges.append(_make_nudge(
                pet_id, "flea", "high",
                f"{item_name} due soon",
                f"{pet_name}'s {item_name} is due within 7 days.{warning}",
                icon="🐛",
            ))

    return nudges


def _generate_condition_nudges(db: Session, pet_id, pet_name: str) -> list[Nudge]:
    """Generate nudges for medication refills and monitoring tasks."""
    nudges = []
    today = date.today()

    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .all()
    )

    for cond in conditions:
        # Medication refill nudges
        for med in cond.medications:
            if med.status != "active":
                continue
            if med.refill_due_date and med.refill_due_date <= today:
                nudges.append(_make_nudge(
                    pet_id, "condition", "urgent",
                    f"Refill {med.name}",
                    f"{pet_name}'s {med.name} for {cond.name} needs a refill.",
                    mandatory=True, icon="💊",
                ))

        # Monitoring overdue nudges
        for mon in cond.monitoring:
            if mon.next_due_date and mon.next_due_date < today:
                nudges.append(_make_nudge(
                    pet_id, "condition", "high",
                    f"{mon.name} overdue for {cond.name}",
                    f"{pet_name}'s {mon.name} monitoring for {cond.name} is overdue.",
                    icon="📋",
                ))

        # No vet visit > 180 days
        last_monitoring = None
        for mon in cond.monitoring:
            if mon.last_done_date:
                if last_monitoring is None or mon.last_done_date > last_monitoring:
                    last_monitoring = mon.last_done_date

        if last_monitoring and (today - last_monitoring).days > 180:
            nudges.append(_make_nudge(
                pet_id, "condition", "medium",
                f"Schedule vet visit for {cond.name}",
                f"No vet check for {cond.name} in over 6 months.",
                icon="🏥",
            ))

    return nudges


def _generate_nutrition_nudges(db: Session, pet_id, pet_name: str) -> list[Nudge]:
    """Generate nudges for missing diet data or nutrition gaps."""
    nudges = []

    diet_count = db.query(func.count(DietItem.id)).filter(DietItem.pet_id == pet_id).scalar()

    if diet_count == 0:
        nudges.append(_make_nudge(
            pet_id, "nutrition", "high",
            "Add diet information",
            f"No diet data recorded for {pet_name}. Add food items to get nutrition insights.",
            icon="🍽️",
        ))

    return nudges


def _generate_grooming_nudges(db: Session, pet_id, pet_name: str) -> list[Nudge]:
    """Generate nudges for overdue grooming tasks."""
    nudges = []
    today = date.today()

    prefs = (
        db.query(HygienePreference)
        .filter(HygienePreference.pet_id == pet_id)
        .all()
    )

    for pref in prefs:
        if not pref.last_done:
            continue
        # Parse last_done (DD/MM/YYYY format)
        try:
            parts = pref.last_done.split("/")
            last_done = date(int(parts[2]), int(parts[1]), int(parts[0]))
        except (ValueError, IndexError):
            continue

        # Calculate expected interval in days
        freq_days = _freq_to_days(pref.freq, pref.unit)
        if freq_days and (today - last_done).days > freq_days:
            display_name = pref.name or pref.item_id
            nudges.append(_make_nudge(
                pet_id, "grooming", "medium",
                f"{display_name} overdue",
                f"{pet_name}'s {display_name} is past the scheduled frequency.",
                icon="✂️",
            ))

    return nudges


def _freq_to_days(freq: int, unit: str) -> int | None:
    """Convert frequency + unit to approximate days."""
    multipliers = {"day": 1, "week": 7, "month": 30, "year": 365}
    m = multipliers.get(unit)
    if m is None or freq <= 0:
        return None
    return freq * m


def _generate_checkup_nudges(db: Session, pet_id, pet_name: str) -> list[Nudge]:
    """Generate nudges for blood test and full panel intervals."""
    nudges = []
    today = date.today()

    # Get most recent blood test
    latest_blood = (
        db.query(func.max(DiagnosticTestResult.observed_at))
        .filter(
            DiagnosticTestResult.pet_id == pet_id,
            DiagnosticTestResult.test_type == "blood",
        )
        .scalar()
    )

    blood_interval = get_nudge_config_int(db, "checkup_blood_test_interval_days", 365)
    panel_interval = get_nudge_config_int(db, "checkup_full_panel_interval_days", 365)

    if latest_blood:
        days_since = (today - latest_blood).days
        if days_since > blood_interval:
            nudges.append(_make_nudge(
                pet_id, "checkup", "high",
                "Blood test recommended",
                f"{pet_name} hasn't had a blood test in {days_since} days.",
                icon="🩸",
            ))
    else:
        # No blood test on record at all — urgent priority
        nudges.append(_make_nudge(
            pet_id, "checkup", "urgent",
            "No blood test on record",
            f"Consider scheduling a blood test for {pet_name}.",
            icon="🩸",
        ))

    # Check full preventive panel (any checkup-classified preventive record)
    checkup_records = (
        db.query(PreventiveRecord)
        .options(
            selectinload(PreventiveRecord.preventive_master),
            selectinload(PreventiveRecord.custom_preventive_item),
        )
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveRecord.status != "cancelled",
        )
        .all()
    )
    latest_checkup_date = None
    for rec in checkup_records:
        item_name = _record_item_name(rec)
        if _classify_item(item_name) == "checkup":
            if rec.last_done_date:
                if latest_checkup_date is None or rec.last_done_date > latest_checkup_date:
                    latest_checkup_date = rec.last_done_date

    if latest_checkup_date and (today - latest_checkup_date).days > panel_interval:
        nudges.append(_make_nudge(
            pet_id, "checkup", "medium",
            "Full preventive panel due",
            f"{pet_name}'s last full checkup was over {panel_interval} days ago.",
            icon="📋",
        ))

    return nudges


# ──────────────────────────────────────────────────────────────────
# Sorting
# ──────────────────────────────────────────────────────────────────

def _sort_nudges(nudges: list[Nudge]) -> list[Nudge]:
    """Sort nudges: mandatory first → source (record > ai) → priority (urgent > high > medium)."""
    return sorted(nudges, key=lambda n: (
        0 if n.mandatory else 1,
        NUDGE_SOURCE_ORDER.get(n.source or "record", 9),
        NUDGE_PRIORITY_ORDER.get(n.priority, 9),
    ))


# ──────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────

def generate_nudges(db: Session, pet_id) -> list[dict]:
    """
    Generate nudges for a single pet (dashboard endpoint).

    Returns cached nudges if fresh (< NUDGE_CACHE_HOURS old),
    otherwise regenerates from all 7 category generators.
    """
    cache_cutoff = datetime.utcnow() - timedelta(hours=NUDGE_CACHE_HOURS)

    # Check for fresh cached nudges
    fresh_count = (
        db.query(func.count(Nudge.id))
        .filter(
            Nudge.pet_id == pet_id,
            Nudge.dismissed == False,
            Nudge.created_at >= cache_cutoff,
        )
        .scalar()
    )

    if fresh_count and fresh_count > 0:
        # Return existing nudges
        existing = (
            db.query(Nudge)
            .filter(Nudge.pet_id == pet_id, Nudge.dismissed == False, Nudge.acted_on == False)
            .all()
        )
        return [_nudge_to_dict(n) for n in _sort_nudges(existing)]

    # Regenerate
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.is_deleted == False).first()
    if not pet:
        return []

    return _regenerate_nudges_for_pet(db, pet)


def _regenerate_nudges_for_pet(db: Session, pet: Pet) -> list[dict]:
    """Run all 7 generators, dedup, persist, and return sorted nudges."""
    pet_id = pet.id
    pet_name = pet.name
    species = pet.species

    new_nudges: list[Nudge] = []
    new_nudges.extend(_generate_vaccine_nudges(db, pet_id, pet_name, species))
    new_nudges.extend(_generate_deworming_nudges(db, pet_id, pet_name, species))
    new_nudges.extend(_generate_flea_nudges(db, pet_id, pet_name, species))
    new_nudges.extend(_generate_condition_nudges(db, pet_id, pet_name))
    new_nudges.extend(_generate_nutrition_nudges(db, pet_id, pet_name))
    new_nudges.extend(_generate_grooming_nudges(db, pet_id, pet_name))
    new_nudges.extend(_generate_checkup_nudges(db, pet_id, pet_name))

    # Dedup: check existing active nudges by (pet_id, category, title)
    existing_keys = set()
    existing = (
        db.query(Nudge)
        .filter(Nudge.pet_id == pet_id, Nudge.dismissed == False, Nudge.acted_on == False)
        .all()
    )
    for n in existing:
        existing_keys.add((str(n.pet_id), n.category, n.title))

    inserted = 0
    for nudge in new_nudges:
        key = (str(nudge.pet_id), nudge.category, nudge.title)
        if key not in existing_keys:
            db.add(nudge)
            existing.append(nudge)
            existing_keys.add(key)
            inserted += 1

    if inserted > 0:
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist nudges for pet %s", pet_id)
            return [_nudge_to_dict(n) for n in _sort_nudges(existing)]

    return [_nudge_to_dict(n) for n in _sort_nudges(existing)]


def run_nudge_engine(db: Session) -> dict:
    """
    Daily cron entry point — regenerate nudges for all active pets.

    Returns summary dict with counts.
    """
    pets = (
        db.query(Pet)
        .join(User)
        .filter(
            Pet.is_deleted == False,
            User.onboarding_state == "complete",
        )
        .all()
    )

    total_generated = 0
    errors = 0

    for pet in pets:
        try:
            nudges = _regenerate_nudges_for_pet(db, pet)
            total_generated += len(nudges)
        except Exception:
            logger.exception("Nudge engine failed for pet %s", pet.id)
            errors += 1

    logger.info(
        "Nudge engine complete: %d pets processed, %d total nudges, %d errors",
        len(pets), total_generated, errors,
    )

    return {
        "pets_processed": len(pets),
        "total_nudges": total_generated,
        "errors": errors,
    }


def _nudge_to_dict(nudge: Nudge) -> dict:
    """Serialize a Nudge to a dict for API response."""
    return {
        "id": str(nudge.id),
        "category": nudge.category,
        "priority": nudge.priority,
        "icon": nudge.icon,
        "title": nudge.title,
        "message": nudge.message,
        "mandatory": nudge.mandatory,
        "orderable": nudge.orderable,
        "price": nudge.price,
        "order_type": nudge.order_type,
        "cart_item_id": nudge.cart_item_id,
        "dismissed": nudge.dismissed,
        "acted_on": nudge.acted_on or False,
        "source": nudge.source or "record",
        "trigger_type": nudge.trigger_type or "cron",
        "created_at": nudge.created_at.isoformat() if nudge.created_at else None,
    }
