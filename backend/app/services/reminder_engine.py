"""
PetCircle — Reminder Engine (Excel v5 4-Stage Lifecycle)

Stateless daily reminder processor. Triggered by GitHub Actions cron at 8 AM IST.

4-Stage Lifecycle per preventive record cycle:
    T-7:              7 days before due date — first alert (Remind Me Later / Already Done)
    Due:              on due date — action prompt (Done — Log It / Remind Me Later / Order Now)
    D+3:              3 days after due date — check-in if 'due' was sent but not completed
    Overdue Insight:  D+7+, monthly repeat — breed-specific consequence + escalation

11 Reminder Categories:
    From preventive_records: Vaccine · Deworming · Flea & Tick · Blood Checkup · Vet Diagnostics
    From diet_items:         Food Order · Supplement Order
    From condition_medications: Chronic Medicine
    From condition_monitoring:  Vet Follow-up
    From hygiene_preferences:   Hygiene (due-only, no T-7 or D+3)

Send Rules:
    - Max 1 reminder per pet per day
    - Min 3 days between any two sends for the same pet
    - Never send reminder + overdue_insight on same day (precedence: due > d3 > overdue > t7)
    - 3 ignored reminders → monthly_fallback = True → only overdue_insight fires monthly

Ignore Detection (runs before creating/sending new reminders):
    - A reminder is "ignored" when no inbound message is received within 24h of sending
    - message_logs is queried to find user replies after reminder.sent_at
    - ignore_count is incremented; monthly_fallback set at threshold

Routes: /internal/run-reminder-engine (full) / /internal/detect-ignores (detect only)
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import (
    REMINDER_IGNORE_THRESHOLD,
    REMINDER_MONTHLY_INTERVAL_DAYS,
    SNOOZE_DAYS_DEWORMING,
    SNOOZE_DAYS_FLEA,
    SNOOZE_DAYS_FOOD,
    SNOOZE_DAYS_HYGIENE,
    SNOOZE_DAYS_MEDICINE,
    SNOOZE_DAYS_SUPPLEMENT,
    SNOOZE_DAYS_VACCINE,
    SNOOZE_DAYS_VET_FOLLOWUP,
    STAGE_D3,
    STAGE_DUE,
    STAGE_OVERDUE,
    STAGE_PRIORITY_ORDER,
    STAGE_T7,
)
from app.core.encryption import decrypt_field
from app.core.log_sanitizer import mask_phone
from app.models.breed_consequence_library import BreedConsequenceLibrary
from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.contact import Contact
from app.models.custom_preventive_item import CustomPreventiveItem
from app.models.diet_item import DietItem
from app.models.hygiene_preference import HygienePreference
from app.models.message_log import MessageLog
from app.models.pet import Pet
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.services.care_plan_engine import get_display_name
from app.services.reminder_templates import (
    MAX_REMINDERS_PER_PET_PER_DAY,
    MIN_DAYS_BETWEEN_SAME_ITEM_REMINDERS,
    get_reminder_template,
    get_send_time,
    substitute_variables,
)
from app.utils.date_utils import IST, format_date_for_user, get_today_ist

logger = logging.getLogger(__name__)

# Vaccine-related item name keywords (case-insensitive) for batching.
# Include kennel-cough and canine-coronavirus aliases used in preventive_master.
VACCINE_KEYWORDS = (
    "vaccine",
    "vaccin",
    "dhpp",
    "rabies",
    "nobivac",
    "kennel cough",
    "bordetella",
    "coronavirus",
    "ccov",
    "fvrcp",
    "felv",
    "fiv",
)

# Item name keywords for category classification
DEWORMING_KEYWORDS = ("deworm", "worm")
FLEA_KEYWORDS = ("flea", "tick", "parasite")
BLOOD_KEYWORDS = ("blood", "cbc", "haematology")
DIAGNOSTICS_KEYWORDS = ("diagnostic", "x-ray", "ultrasound", "biopsy", "pcr", "urinalysis")


# ─────────────────────────────────────────────────────────────────────────────
#  Data class representing a reminder candidate (before DB insertion)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ReminderCandidate:
    """
    A potential reminder to send today.

    Populated by _collect_candidates(), filtered by _apply_send_rules(),
    then persisted and sent by _process_candidate().
    """
    pet: Pet
    user: User
    category: str            # vaccine | deworming | flea_tick | food | supplement |
                             # chronic_medicine | vet_followup | blood_checkup |
                             # vet_diagnostics | hygiene
    item_desc: str           # human-readable description for message body
    due_date: date           # the relevant due date / reorder date
    stage: str               # t7 | due | d3 | overdue_insight
    source_type: str         # preventive_record | diet_item | condition_medication |
                             # condition_monitoring | hygiene_preference
    source_id: UUID          # ID of the source row
    # For preventive_record sources only — used for UNIQUE constraint dedup
    preventive_record_id: UUID | None = None
    # Snooze duration for this category
    snooze_days: int = 7
    # Sub-type for food / supplement / chronic_medicine categories (v6).
    # 'supply_led' — triggered by pack supply countdown (existing behaviour)
    # 'scheduled'  — O+21 first-time prompt; selects a different WA template
    sub_type: str = "supply_led"


# ─────────────────────────────────────────────────────────────────────────────
#  Public entry points
# ─────────────────────────────────────────────────────────────────────────────

def run_reminder_engine(db: Session) -> dict:
    """
    Execute the full daily reminder engine:
        1. Detect ignores from yesterday's (and older) sent reminders
        2. Collect all reminder candidates for today across all categories
        3. Apply send rules (dedup, max-per-pet, min-gap)
        4. Create Reminder rows and send WhatsApp templates

    Returns:
        dict with: records_checked, reminders_created, reminders_sent,
                   reminders_skipped, reminders_failed, ignores_detected, errors
    """
    today = get_today_ist()
    results = {
        "records_checked": 0,
        "reminders_created": 0,
        "reminders_sent": 0,
        "reminders_skipped": 0,
        "reminders_failed": 0,
        "ignores_detected": 0,
        "errors": 0,
    }

    # Phase 1: detect ignores from sent reminders with no reply within 24h
    ignores = _detect_ignores(db, today)
    results["ignores_detected"] = ignores
    db.commit()

    # Phase 2: collect candidates from all sources
    candidates = _collect_candidates(db, today)
    results["records_checked"] = len(candidates)

    # Phase 3: apply send rules (per-pet max, min gap, precedence)
    filtered = _apply_send_rules(db, candidates, today)
    results["reminders_skipped"] = len(candidates) - len(filtered)

    # Phase 4: create & send
    now_ist = datetime.now(IST).time()
    for cand in filtered:
        send_time = get_send_time(cand.category, cand.stage)
        if now_ist < send_time:
            results["reminders_skipped"] += 1
            logger.info(
                "Reminder delayed until send window: pet=%s category=%s stage=%s now=%s target=%s",
                cand.pet.name,
                cand.category,
                cand.stage,
                now_ist.strftime("%H:%M"),
                send_time.strftime("%H:%M"),
            )
            continue

        created, sent = _process_candidate(db, cand, today)
        if created:
            results["reminders_created"] += 1
        if sent:
            results["reminders_sent"] += 1
        elif created:
            results["reminders_failed"] += 1

    db.commit()

    logger.info(
        "Reminder engine: checked=%d created=%d sent=%d skipped=%d "
        "failed=%d ignores=%d errors=%d",
        results["records_checked"], results["reminders_created"],
        results["reminders_sent"], results["reminders_skipped"],
        results["reminders_failed"], results["ignores_detected"],
        results["errors"],
    )
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 1: Ignore Detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_ignores(db: Session, today: date) -> int:
    """
    Find sent reminders older than 24h with no inbound reply from the user.
    Increment ignore_count; set monthly_fallback when threshold reached.
    """
    cutoff = datetime.now(IST) - timedelta(hours=24)

    # Find reminders that were sent > 24h ago and still have status='sent'
    sent_reminders = (
        db.query(Reminder, Pet, User)
        .join(Pet, Reminder.pet_id == Pet.id)
        .join(User, Pet.user_id == User.id)
        .filter(
            Reminder.status == "sent",
            Reminder.sent_at <= cutoff,
            Pet.is_deleted == False,
            User.is_deleted == False,
        )
        .all()
    )

    ignores = 0
    for reminder, pet, user in sent_reminders:
        if reminder.last_ignored_at and reminder.sent_at and reminder.last_ignored_at >= reminder.sent_at:
            continue

        # Check if user sent ANY inbound message after the reminder was sent
        reply_count = (
            db.query(MessageLog)
            .filter(
                MessageLog.phone_number == user.mobile_hash,
                MessageLog.direction == "inbound",
                MessageLog.created_at > reminder.sent_at,
            )
            .count()
        )

        if reply_count == 0:
            # No reply — increment ignore counter
            try:
                nested = db.begin_nested()
                reminder.ignore_count += 1
                reminder.last_ignored_at = datetime.now(IST)

                if reminder.ignore_count >= REMINDER_IGNORE_THRESHOLD:
                    reminder.monthly_fallback = True

                db.flush()
                nested.commit()
                ignores += 1

                logger.info(
                    "Reminder ignored: reminder_id=%s pet=%s count=%d fallback=%s",
                    str(reminder.id), pet.name,
                    reminder.ignore_count, reminder.monthly_fallback,
                )
            except Exception as e:
                nested.rollback()
                logger.error("Error updating ignore for reminder_id=%s: %s", str(reminder.id), str(e))

    return ignores


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 2: Collect Candidates
# ─────────────────────────────────────────────────────────────────────────────

def _collect_candidates(db: Session, today: date) -> list[ReminderCandidate]:
    """
    Collect all reminder candidates for today from all 5 source types.
    Returns a flat list of ReminderCandidate objects.
    """
    candidates: list[ReminderCandidate] = []

    # -- 2a. Standard preventive records (vaccine, deworming, flea, blood, diagnostics) --
    candidates.extend(_candidates_from_preventive_records(db, today))

    # -- 2b. Food & Supplement Order reminders --
    candidates.extend(_candidates_from_diet_items(db, today))

    # -- 2c. Chronic Medicine reminders --
    candidates.extend(_candidates_from_chronic_medicine(db, today))

    # -- 2d. Vet Follow-up reminders --
    candidates.extend(_candidates_from_vet_followup(db, today))

    # -- 2e. Hygiene reminders (due-only) --
    candidates.extend(_candidates_from_hygiene(db, today))

    return candidates


def _candidates_from_preventive_records(db: Session, today: date) -> list[ReminderCandidate]:
    """Build candidates from preventive_records with status upcoming/overdue."""
    rows = (
        db.query(PreventiveRecord, Pet, User, PreventiveMaster, CustomPreventiveItem)
        .join(Pet, PreventiveRecord.pet_id == Pet.id)
        .join(User, Pet.user_id == User.id)
        .outerjoin(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
        .outerjoin(CustomPreventiveItem, PreventiveRecord.custom_preventive_item_id == CustomPreventiveItem.id)
        .filter(
            PreventiveRecord.status.in_(["upcoming", "overdue"]),
            PreventiveRecord.next_due_date.isnot(None),
            Pet.is_deleted == False,
            User.is_deleted == False,
        )
        .all()
    )

    # Group vaccines by (pet_id, stage) for batching
    vaccine_groups: dict[tuple, list] = {}
    candidates: list[ReminderCandidate] = []

    for record, pet, user, master, custom_item in rows:
        if not record.next_due_date:
            continue

        due = record.next_due_date
        item_name = (
            (master.item_name if master else None)
            or (custom_item.item_name if custom_item else None)
            or (record.medicine_name or "Unknown")
        )
        category = _classify_item(item_name)

        # Skip non-mandatory vaccines that were never actually given (phantom entries).
        # These are recommendations, not tracked items — no reminder needed.
        if category == "vaccine" and master and not master.is_mandatory and not record.last_done_date:
            continue

        snooze = _snooze_for_category(category)

        stage = _determine_stage(db, record.id, due, today, source_type="preventive_record")
        if stage is None:
            continue

        # Vaccine: batch into groups
        if category == "vaccine":
            key = (str(pet.id), stage, str(due))
            if key not in vaccine_groups:
                vaccine_groups[key] = {"pet": pet, "user": user, "due": due,
                                        "mandatory": [], "optional": [],
                                        "record_ids": []}
            is_essential = master and master.category == "essential"
            display = get_display_name(item_name)
            if is_essential:
                vaccine_groups[key]["mandatory"].append(display)
            else:
                vaccine_groups[key]["optional"].append(display)
            vaccine_groups[key]["record_ids"].append(record.id)
            continue

        item_desc = get_display_name(item_name)
        candidates.append(ReminderCandidate(
            pet=pet, user=user,
            category=category, item_desc=item_desc,
            due_date=due, stage=stage,
            source_type="preventive_record",
            source_id=record.id,
            preventive_record_id=record.id,
            snooze_days=snooze,
        ))

    # Convert vaccine groups into single candidates
    for key, grp in vaccine_groups.items():
        pet, user, due = grp["pet"], grp["user"], grp["due"]
        stage_str = key[1]
        mandatory = grp["mandatory"]
        optional = grp["optional"]
        parts = []
        if mandatory:
            parts.append(" · ".join(mandatory) + " (mandatory)")
        if optional:
            parts.append(" · ".join(optional) + " (optional)")
        item_desc = " · ".join(parts) if parts else "Vaccination"
        # Use first record_id for dedup key
        first_id = grp["record_ids"][0]
        candidates.append(ReminderCandidate(
            pet=pet, user=user,
            category="vaccine", item_desc=item_desc,
            due_date=due, stage=stage_str,
            source_type="preventive_record",
            source_id=first_id,
            preventive_record_id=first_id,
            snooze_days=SNOOZE_DAYS_VACCINE,
        ))

    return candidates


def _candidates_from_diet_items(db: Session, today: date) -> list[ReminderCandidate]:
    """Build food order and supplement order candidates from diet_items."""
    rows = (
        db.query(DietItem, Pet, User)
        .join(Pet, DietItem.pet_id == Pet.id)
        .join(User, Pet.user_id == User.id)
        .filter(
            DietItem.type.in_(["packaged", "supplement"]),
            Pet.is_deleted == False,
            User.is_deleted == False,
        )
        .all()
    )

    candidates: list[ReminderCandidate] = []

    for item, pet, user in rows:
        category = "food" if item.type == "packaged" else "supplement"
        snooze = SNOOZE_DAYS_FOOD if category == "food" else SNOOZE_DAYS_SUPPLEMENT

        reorder_date = _calculate_reorder_date(item)
        sub_type = "supply_led"

        if reorder_date is None:
            # No pack data — check O+21 fallback (Scheduled variant)
            if item.reminder_order_at_o21 and user.onboarding_completed_at:
                o21 = (user.onboarding_completed_at.date() + timedelta(days=21))
                if today == o21:
                    reorder_date = today
                    sub_type = "scheduled"
                else:
                    continue
            else:
                continue

        stage = _determine_stage_simple(db, item.id, reorder_date, today,
                                        source_type=("diet_item_food" if category == "food" else "diet_item_supplement"))
        if stage is None:
            continue

        item_desc = item.label
        if item.brand:
            item_desc = f"{item.brand} — {item.label}"

        candidates.append(ReminderCandidate(
            pet=pet, user=user,
            category=category, item_desc=item_desc,
            due_date=reorder_date, stage=stage,
            source_type="diet_item",
            source_id=item.id,
            snooze_days=snooze,
            sub_type=sub_type,
        ))

    return candidates


def _candidates_from_chronic_medicine(db: Session, today: date) -> list[ReminderCandidate]:
    """Build chronic medicine candidates from condition_medications.refill_due_date."""
    rows = (
        db.query(ConditionMedication, Condition, Pet, User)
        .join(Condition, ConditionMedication.condition_id == Condition.id)
        .join(Pet, Condition.pet_id == Pet.id)
        .join(User, Pet.user_id == User.id)
        .filter(
            ConditionMedication.status == "active",
            Pet.is_deleted == False,
            User.is_deleted == False,
        )
        .all()
    )

    candidates: list[ReminderCandidate] = []

    for med, condition, pet, user in rows:
        if _is_course_medicine(med):
            logger.info(
                "Skipping course medicine reminders: med_id=%s name=%s",
                str(med.id),
                med.name,
            )
            continue

        sub_type = "supply_led"
        due = med.refill_due_date

        if due is None:
            # No refill date — check O+21 scheduled variant for first-time prompt
            if user.onboarding_completed_at:
                o21 = (user.onboarding_completed_at.date() + timedelta(days=21))
                if today == o21:
                    due = today
                    sub_type = "scheduled"
                else:
                    continue
            else:
                continue

        stage = _determine_stage_simple(db, med.id, due, today, source_type="condition_medication")
        if stage is None:
            continue

        item_desc = med.name
        if condition.diagnosis:
            item_desc = f"{med.name} ({condition.diagnosis})"

        candidates.append(ReminderCandidate(
            pet=pet, user=user,
            category="chronic_medicine", item_desc=item_desc,
            due_date=due, stage=stage,
            source_type="condition_medication",
            source_id=med.id,
            snooze_days=SNOOZE_DAYS_MEDICINE,
            sub_type=sub_type,
        ))

    return candidates


def _candidates_from_vet_followup(db: Session, today: date) -> list[ReminderCandidate]:
    """Build vet follow-up candidates from condition_monitoring.next_due_date."""
    rows = (
        db.query(ConditionMonitoring, Condition, Pet, User)
        .join(Condition, ConditionMonitoring.condition_id == Condition.id)
        .join(Pet, Condition.pet_id == Pet.id)
        .join(User, Pet.user_id == User.id)
        .filter(
            ConditionMonitoring.next_due_date.isnot(None),
            Pet.is_deleted == False,
            User.is_deleted == False,
        )
        .all()
    )

    candidates: list[ReminderCandidate] = []

    for monitoring, condition, pet, user in rows:
        due = monitoring.next_due_date
        stage = _determine_stage_simple(db, monitoring.id, due, today, source_type="condition_monitoring")
        if stage is None:
            continue

        # Try to get vet name from contacts
        vet = (
            db.query(Contact)
            .filter(Contact.pet_id == pet.id, Contact.role == "veterinarian")
            .order_by(Contact.created_at)
            .first()
        )
        vet_name = vet.name if vet else "your vet"

        item_desc = f"Vet Follow-up with {vet_name}: {monitoring.name}"

        candidates.append(ReminderCandidate(
            pet=pet, user=user,
            category="vet_followup", item_desc=item_desc,
            due_date=due, stage=stage,
            source_type="condition_monitoring",
            source_id=monitoring.id,
            snooze_days=SNOOZE_DAYS_VET_FOLLOWUP,
        ))

    return candidates


def _candidates_from_hygiene(db: Session, today: date) -> list[ReminderCandidate]:
    """
    Build hygiene candidates from hygiene_preferences where reminder=True.
    Groups all due hygiene items per pet into a single combined candidate.
    Hygiene: due-only stage (no T-7 or D+3 per spec).
    """
    rows = (
        db.query(HygienePreference, Pet, User)
        .join(Pet, HygienePreference.pet_id == Pet.id)
        .join(User, Pet.user_id == User.id)
        .filter(
            HygienePreference.reminder == True,
            Pet.is_deleted == False,
            User.is_deleted == False,
        )
        .all()
    )

    # Group by pet_id — one combined reminder per pet
    pet_items: dict[str, dict] = {}
    for pref, pet, user in rows:
        if not pref.last_done:
            continue

        last_done = _parse_hygiene_date(pref.last_done)
        if not last_done:
            continue

        freq_days = _freq_to_days(pref.freq, pref.unit)
        if freq_days is None:
            continue

        next_due = last_done + timedelta(days=freq_days)
        if today != next_due:
            continue

        pet_key = str(pet.id)
        if pet_key not in pet_items:
            pet_items[pet_key] = {"pet": pet, "user": user, "items": [], "due": next_due}

        # Group by category
        category_label = _hygiene_category_label(pref.item_id, pref.name)
        pet_items[pet_key]["items"].append(category_label)

    candidates: list[ReminderCandidate] = []
    for pet_key, grp in pet_items.items():
        pet, user = grp["pet"], grp["user"]
        item_desc = " · ".join(sorted(set(grp["items"])))
        due = grp["due"]

        # Check if already sent a hygiene due reminder today for this pet
        existing = (
            db.query(Reminder)
            .filter(
                Reminder.pet_id == pet.id,
                Reminder.source_type == "hygiene_preference",
                Reminder.next_due_date == due,
                Reminder.stage == STAGE_DUE,
            )
            .first()
        )
        if existing:
            continue

        candidates.append(ReminderCandidate(
            pet=pet, user=user,
            category="hygiene", item_desc=item_desc,
            due_date=due, stage=STAGE_DUE,
            source_type="hygiene_preference",
            source_id=pet.id,  # pet-level aggregation
            snooze_days=SNOOZE_DAYS_HYGIENE,
        ))

    return candidates


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3: Apply Send Rules
# ─────────────────────────────────────────────────────────────────────────────

def _apply_send_rules(db: Session, candidates: list[ReminderCandidate], today: date) -> list[ReminderCandidate]:
    """
    Apply communication limits:
    - Max one reminder per pet per day
    - Min 3-day gap between sends for the same source item
    - Dedup exact source_id + stage combinations sent today
    """
    day_start = datetime.combine(today, time.min)

    # Build set of (source_id, stage) already sent today to deduplicate per item.
    already_sent_today: set[tuple[str, str]] = set()
    pets_sent_today_count: dict[str, int] = {}
    last_sent_by_source: dict[str, datetime] = {}

    sent_today_rows = (
        db.query(Reminder.source_id, Reminder.stage, Reminder.pet_id)
        .filter(
            Reminder.status == "sent",
            Reminder.sent_at >= day_start,
        )
        .all()
    )

    for source_id, stage, pet_id in sent_today_rows:
        if source_id and stage:
            already_sent_today.add((str(source_id), stage))
        if pet_id:
            pet_key = str(pet_id)
            pets_sent_today_count[pet_key] = pets_sent_today_count.get(pet_key, 0) + 1

    candidate_source_ids = {cand.source_id for cand in candidates}
    min_gap_cutoff = datetime.combine(today - timedelta(days=MIN_DAYS_BETWEEN_SAME_ITEM_REMINDERS - 1), time.min)

    recent_sent_rows = (
        db.query(Reminder.source_id, Reminder.sent_at)
        .filter(
            Reminder.status == "sent",
            Reminder.sent_at.isnot(None),
            Reminder.source_id.in_(candidate_source_ids),
            Reminder.sent_at >= min_gap_cutoff,
        )
        .all()
    )

    for source_id, sent_at in recent_sent_rows:
        if not source_id or not sent_at:
            continue
        source_key = str(source_id)
        existing = last_sent_by_source.get(source_key)
        if existing is None or sent_at > existing:
            last_sent_by_source[source_key] = sent_at

    staged_candidates = sorted(candidates, key=lambda c: STAGE_PRIORITY_ORDER.index(c.stage))

    result: list[ReminderCandidate] = []
    for cand in staged_candidates:
        pet_key = str(cand.pet.id)

        # Max one reminder per pet per day.
        if pets_sent_today_count.get(pet_key, 0) >= MAX_REMINDERS_PER_PET_PER_DAY:
            continue

        # Per-item minimum spacing guard.
        last_sent = last_sent_by_source.get(str(cand.source_id))
        if last_sent:
            days_since_last = (today - last_sent.date()).days
            if days_since_last < MIN_DAYS_BETWEEN_SAME_ITEM_REMINDERS:
                continue

        key = (str(cand.source_id), cand.stage)
        if key not in already_sent_today:
            result.append(cand)
            pets_sent_today_count[pet_key] = pets_sent_today_count.get(pet_key, 0) + 1
            already_sent_today.add(key)

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 4: Create & Send
# ─────────────────────────────────────────────────────────────────────────────

def _process_candidate(db: Session, cand: ReminderCandidate, today: date) -> tuple[bool, bool]:
    """
    Create a Reminder row and send the WhatsApp template message.
    Returns (created: bool, sent: bool).
    """
    from app.config import settings
    from app.services.whatsapp_sender import send_template_message

    plaintext_mobile = decrypt_field(cand.user.mobile_number)
    pet_name = cand.pet.name

    # --- Insert Reminder row ---
    try:
        nested = db.begin_nested()
        reminder = Reminder(
            preventive_record_id=cand.preventive_record_id,
            pet_id=cand.pet.id,
            next_due_date=cand.due_date,
            stage=cand.stage,
            status="pending",
            source_type=cand.source_type,
            source_id=cand.source_id,
            item_desc=cand.item_desc,
            sub_type=cand.sub_type if cand.sub_type != "supply_led" else None,
        )
        db.add(reminder)
        db.flush()
        nested.commit()
    except IntegrityError:
        nested.rollback()
        logger.info("Dedup skip: source_id=%s stage=%s due=%s",
                    str(cand.source_id), cand.stage, str(cand.due_date))
        return False, False
    except Exception as e:
        nested.rollback()
        logger.error("Error creating reminder: %s", str(e))
        return False, False

    # --- Build template parameters ---
    template_name, params = _build_template_params(cand, settings, db)
    if not template_name:
        # New templates not registered yet — skip sending
        logger.warning("No template configured for stage=%s category=%s", cand.stage, cand.category)
        return True, False

    # --- Persist template details on the reminder row ---
    # Saved here (before send) so the data is always recorded regardless of send outcome.
    reminder.template_name = template_name
    reminder.template_params = params

    # Render and save the complete message body the user will receive.
    from app.services.whatsapp_sender import get_template_body, render_template_body
    body = get_template_body(db, template_name)
    if body:
        reminder.message_body = render_template_body(body, params or [])

    # --- Send WhatsApp template ---
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    try:
        coro = send_template_message(
            db=db,
            to_number=plaintext_mobile,
            template_name=template_name,
            parameters=params,
        )
        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            result = future.result(timeout=60)
        else:
            result = asyncio.run(coro)
    except Exception as e:
        logger.error("Error sending reminder for pet=%s: %s", pet_name, str(e))
        result = None

    if result:
        reminder.status = "sent"
        reminder.sent_at = datetime.now(IST)
        logger.info("Reminder sent: stage=%s category=%s pet=%s user=%s",
                    cand.stage, cand.category, pet_name, mask_phone(plaintext_mobile))
        return True, True
    else:
        logger.warning("Reminder send failed: stage=%s pet=%s", cand.stage, pet_name)
        return True, False


def _build_template_params(cand: ReminderCandidate, settings, db: Session) -> tuple[str | None, list[str]]:
    """
    Select the correct WA template and build the parameter list for the given stage.

    Template variable mapping:
        T-7:      [parent_name, pet_name, item_desc, due_date_str]
        Due:      [parent_name, pet_name, item_desc]
        D+3:      [parent_name, pet_name, item_desc, original_due_str]
        Overdue:  [parent_name, pet_name, item_desc, days_overdue_str, consequence]

    Scheduled variants (food / supplement / chronic_medicine, sub_type='scheduled'):
        Due only: [parent_name, pet_name, item_desc]
        — uses a separate template that prompts the user to check/reorder stock.
    """
    parent_name = cand.user.full_name or "Pet Parent"
    pet_name = cand.pet.name
    item_desc = cand.item_desc
    due_str = format_date_for_user(cand.due_date)
    today = get_today_ist()

    # Birthday: only send the celebration template on the due date (the birthday itself).
    # T-7, D+3, and overdue stages are not meaningful for a birthday celebration.
    if cand.category == "birthday":
        if cand.stage != STAGE_DUE:
            return None, []
        birthday_template = settings.WHATSAPP_TEMPLATE_BIRTHDAY
        if not birthday_template:
            return None, []
        return birthday_template, [pet_name, due_str]

    # Prefer category-specific registry templates first.
    sub_type = cand.sub_type
    if cand.category == "vaccine":
        sub_type = _vaccine_template_sub_type(cand)

    registry_template = get_reminder_template(cand.category, sub_type, cand.stage)
    if registry_template:
        template_name = _template_name_for_stage(cand.stage, settings)
        if template_name:
            variables = _build_variable_dict(cand, db)
            rendered_body = substitute_variables(registry_template.message_body, variables)
            return template_name, [rendered_body]

    if cand.stage == STAGE_T7:
        template = settings.WHATSAPP_TEMPLATE_REMINDER_T7
        if not template:
            return None, []
        params = [parent_name, pet_name, item_desc, due_str]

    elif cand.stage == STAGE_DUE:
        template = settings.WHATSAPP_TEMPLATE_REMINDER_DUE
        if not template:
            return None, []
        params = [parent_name, pet_name, item_desc]

    elif cand.stage == STAGE_D3:
        template = settings.WHATSAPP_TEMPLATE_REMINDER_D3
        if not template:
            return None, []
        params = [parent_name, pet_name, item_desc, due_str]

    elif cand.stage == STAGE_OVERDUE:
        template = settings.WHATSAPP_TEMPLATE_REMINDER_OVERDUE
        if not template:
            return None, []
        days_overdue = (today - cand.due_date).days
        consequence = _get_breed_consequence(db, cand.pet.breed, cand.category)
        params = [parent_name, pet_name, item_desc, str(days_overdue), consequence]

    else:
        return None, []

    return template, params


def _template_name_for_stage(stage: str, settings) -> str | None:
    """Return the configured WhatsApp template name for a stage."""
    if stage == STAGE_T7:
        return settings.WHATSAPP_TEMPLATE_REMINDER_T7
    if stage == STAGE_DUE:
        return settings.WHATSAPP_TEMPLATE_REMINDER_DUE
    if stage == STAGE_D3:
        return settings.WHATSAPP_TEMPLATE_REMINDER_D3
    if stage == STAGE_OVERDUE:
        return settings.WHATSAPP_TEMPLATE_REMINDER_OVERDUE
    return None


def _vaccine_template_sub_type(cand: ReminderCandidate) -> str:
    """Infer first-time vs booster vaccine template from pet age at due date."""
    if not cand.pet.dob:
        return "booster"
    age_days = (cand.due_date - cand.pet.dob).days
    return "first_time" if age_days <= 365 else "booster"


def _build_variable_dict(cand: ReminderCandidate, db: Session) -> dict[str, str]:
    """Build placeholder replacement values for category-specific templates."""
    parent_name = cand.user.full_name or "Pet Parent"
    pet_name = cand.pet.name
    today = get_today_ist()

    item_desc = cand.item_desc or "care item"
    condition = "care"
    if "(" in item_desc and ")" in item_desc:
        condition = item_desc[item_desc.find("(") + 1:item_desc.rfind(")")]

    vet = (
        db.query(Contact)
        .filter(Contact.pet_id == cand.pet.id, Contact.role == "veterinarian")
        .order_by(Contact.created_at)
        .first()
    )
    vet_name = vet.name if vet else "your vet"

    days_overdue = max(0, (today - cand.due_date).days)
    snooze_date = format_date_for_user(today + timedelta(days=cand.snooze_days))

    return {
        "Name": parent_name,
        "Pet": pet_name,
        "breed": cand.pet.breed or "your pet",
        "date": format_date_for_user(cand.due_date),
        "vaccineList": item_desc,
        "Brand": item_desc,
        "Supplement": item_desc,
        "Medicine": item_desc,
        "condition": condition,
        "vetName": vet_name,
        "testName": item_desc,
        "X": str(days_overdue),
        "breedSpecificConsequence": _get_breed_consequence(db, cand.pet.breed, cand.category),
        "snoozeDate": snooze_date,
    }


def _is_course_medicine(med: ConditionMedication) -> bool:
    """Identify fixed-duration course medicines from free-text duration hints."""
    duration_pattern = re.compile(
        r"\b(for|x|duration\s*:?\s*)\s*\d+\s*(day|days|week|weeks|month|months)\b",
        re.IGNORECASE,
    )
    recurring_pattern = re.compile(r"\b(every|daily|weekly|monthly|ongoing|indefinite|long[- ]term)\b", re.IGNORECASE)
    searchable = " ".join([
        med.name or "",
        med.dose or "",
        med.frequency or "",
        med.notes or "",
    ])
    if recurring_pattern.search(searchable):
        return False
    return bool(duration_pattern.search(searchable))


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _determine_stage(db: Session, record_id: UUID, due_date: date, today: date,
                     source_type: str = "preventive_record") -> str | None:
    """
    Determine which stage fires today for a preventive_record-based candidate.
    Returns None if no stage fires today.
    Respects monthly_fallback: only overdue_insight fires at 30-day intervals.
    """
    return _determine_stage_simple(db, record_id, due_date, today, source_type)


def _determine_stage_simple(db: Session, source_id: UUID, due_date: date, today: date,
                             source_type: str) -> str | None:
    """
    Generic stage determination for any source type.
    Checks existing reminder rows to decide which stage is eligible.
    """
    t7_date = due_date - timedelta(days=7)
    d3_date = due_date + timedelta(days=3)
    d7_date = due_date + timedelta(days=7)

    # Check existing reminders for this source to understand lifecycle state
    existing = (
        db.query(Reminder)
        .filter(
            Reminder.source_id == source_id,
            Reminder.next_due_date == due_date,
        )
        .all()
    )
    existing_stages = {r.stage: r for r in existing}

    # Check if on monthly_fallback — only send overdue_insight at 30-day intervals
    if any(r.monthly_fallback for r in existing):
        # Find last sent overdue reminder
        overdue_row = existing_stages.get(STAGE_OVERDUE)
        if overdue_row and overdue_row.sent_at:
            last_sent_date = overdue_row.sent_at.date()
            days_since = (today - last_sent_date).days
            if days_since >= REMINDER_MONTHLY_INTERVAL_DAYS:
                return STAGE_OVERDUE
        elif today >= d7_date:
            return STAGE_OVERDUE
        return None

    # Standard stage progression
    if today == t7_date and STAGE_T7 not in existing_stages:
        return STAGE_T7

    if today == due_date and STAGE_DUE not in existing_stages:
        return STAGE_DUE

    if today == d3_date:
        # D+3 only fires if 'due' was sent but not completed
        due_row = existing_stages.get(STAGE_DUE)
        if due_row and due_row.status in ("sent", "snoozed") and STAGE_D3 not in existing_stages:
            return STAGE_D3

    if today >= d7_date:
        # Overdue fires if D+3 was ignored (or doesn't exist and due was ignored)
        d3_row = existing_stages.get(STAGE_D3)
        due_row = existing_stages.get(STAGE_DUE)
        if STAGE_OVERDUE not in existing_stages:
            # Check if any prior stage was ignored (not completed)
            if (d3_row and d3_row.status == "sent") or \
               (not d3_row and due_row and due_row.status == "sent"):
                return STAGE_OVERDUE

    return None


def _calculate_reorder_date(item: DietItem) -> date | None:
    """Calculate the next reorder date for a food or supplement item."""
    if item.last_purchase_date is None:
        return None

    if item.type == "packaged":
        if item.pack_size_g and item.daily_portion_g and item.daily_portion_g > 0:
            days_supply = int(item.pack_size_g / item.daily_portion_g)
            return item.last_purchase_date + timedelta(days=days_supply)
    elif item.type == "supplement":
        if item.units_in_pack and item.doses_per_day and item.doses_per_day > 0:
            days_supply = int(item.units_in_pack / item.doses_per_day)
            return item.last_purchase_date + timedelta(days=days_supply)

    return None


def _get_breed_consequence(db: Session, breed: str | None, category: str) -> str:
    """Look up breed-specific consequence text for the overdue insight message."""
    # Normalize category to match breed_consequence_library
    cat_map = {
        "vaccine": "vaccine",
        "deworming": "deworming",
        "flea_tick": "flea_tick",
        "food": "food",
        "supplement": "supplement",
        "chronic_medicine": "chronic_medicine",
        "vet_followup": "vet_followup",
        "blood_checkup": "blood_checkup",
        "hygiene": "flea_tick",         # fallback hygiene to flea_tick row
        "vet_diagnostics": "blood_checkup",  # fallback diagnostics
    }
    mapped_category = cat_map.get(category, category)

    # Try breed-specific row first
    if breed:
        row = (
            db.query(BreedConsequenceLibrary)
            .filter(
                BreedConsequenceLibrary.breed == breed,
                BreedConsequenceLibrary.category == mapped_category,
            )
            .first()
        )
        if row:
            return row.consequence_text

    # Generic fallback
    fallback = (
        db.query(BreedConsequenceLibrary)
        .filter(
            BreedConsequenceLibrary.breed == "Other",
            BreedConsequenceLibrary.category == mapped_category,
        )
        .first()
    )
    if fallback:
        return fallback.consequence_text

    return "addressing this promptly ensures your pet stays healthy and protected"


def _classify_item(item_name: str) -> str:
    """Classify a preventive master item name into a reminder category."""
    name_lower = item_name.lower()
    if re.search(r"\b\d+\s*[- ]?in\s*[- ]?1\b", name_lower):
        return "vaccine"
    if any(k in name_lower for k in VACCINE_KEYWORDS):
        return "vaccine"
    if any(k in name_lower for k in DEWORMING_KEYWORDS):
        return "deworming"
    if any(k in name_lower for k in FLEA_KEYWORDS):
        return "flea_tick"
    if any(k in name_lower for k in BLOOD_KEYWORDS):
        return "blood_checkup"
    if any(k in name_lower for k in DIAGNOSTICS_KEYWORDS):
        return "vet_diagnostics"
    if "birthday" in name_lower:
        return "birthday"
    return "checkup"


def _snooze_for_category(category: str) -> int:
    """Return the snooze duration in days for a given category."""
    mapping = {
        "vaccine": SNOOZE_DAYS_VACCINE,
        "deworming": SNOOZE_DAYS_DEWORMING,
        "flea_tick": SNOOZE_DAYS_FLEA,
        "food": SNOOZE_DAYS_FOOD,
        "supplement": SNOOZE_DAYS_SUPPLEMENT,
        "chronic_medicine": SNOOZE_DAYS_MEDICINE,
        "vet_followup": SNOOZE_DAYS_VET_FOLLOWUP,
        "hygiene": SNOOZE_DAYS_HYGIENE,
    }
    return mapping.get(category, 7)


def _parse_hygiene_date(date_str: str) -> date | None:
    """Parse a hygiene last_done date string (DD/MM/YYYY) to a date object."""
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _freq_to_days(freq: int, unit: str) -> int | None:
    """Convert frequency + unit to total days."""
    if not freq or not unit:
        return None
    unit_days = {"day": 1, "week": 7, "month": 30, "year": 365}
    days_per_unit = unit_days.get(unit.lower())
    if days_per_unit is None:
        return None
    return freq * days_per_unit


def _hygiene_category_label(item_id: str, name: str | None) -> str:
    """Return a display label for a hygiene item."""
    label_map = {
        "bath-nail": "Bath, Brush & Nail Trim",
        "ear-clean": "Ear Cleaning",
        "teeth-brush": "Dental / Teeth Brushing",
        "coat-brush": "Coat Brushing",
    }
    return label_map.get(item_id, name or item_id)
