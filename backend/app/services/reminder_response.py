"""
PetCircle Phase 1 — Reminder Response State Machine (Module 11)

Handles user responses to reminder WhatsApp interactive buttons.
Each response triggers a specific state transition on the reminder
and its linked preventive record.

Payload IDs (from constants — never hardcoded):
    - REMINDER_DONE:          "Done — Log It" (Due stage) — mark done today
    - REMINDER_ALREADY_DONE:  "Already Done" (T-7 stage) — same as DONE
    - REMINDER_SNOOZE_7:      "Remind Me Later" — snooze by category-specific days
    - REMINDER_ORDER_NOW:     "Order Now" — trigger agentic_order flow
    - REMINDER_STILL_PENDING: "Still Pending" — acknowledge but do nothing
    - REMINDER_SCHEDULE:      "Schedule For ()" — set awaiting_reschedule_date state
    - REMINDER_RESCHEDULE:    Legacy — same as REMINDER_SCHEDULE
    - REMINDER_CANCEL:        Cancel this preventive item entirely

State transitions:

    REMINDER_DONE / REMINDER_ALREADY_DONE:
        → For preventive_record sources:
          preventive_record.last_done_date = today
          Recalculate next_due_date and status from DB recurrence_days.
        → For diet_item sources: diet_item.last_purchase_date = today
        → For condition_medication: refill_due_date advanced by recurrence
        → For condition_monitoring: last_done_date = today
        → reminder.status = 'completed'

    REMINDER_SNOOZE_7 ("Remind Me Later"):
        → preventive_record.next_due_date += snooze_days (category-specific)
        → reminder.status = 'snoozed'

    REMINDER_ORDER_NOW:
        → Triggers agentic_order flow (caller must initiate)
        → reminder.status = 'snoozed' (pending order)

    REMINDER_STILL_PENDING:
        → reminder.last_ignored_at = now (updates ignore tracking)
        → No status change — reminder stays 'sent'

    REMINDER_SCHEDULE / REMINDER_RESCHEDULE:
        → Returns signal to caller to set user.active_reminder_id and state
        → No reminder status change until date received

    REMINDER_CANCEL:
        → preventive_record.status = 'cancelled'
        → reminder.status = 'completed'
"""

import logging
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import (
    REMINDER_ALREADY_DONE,
    REMINDER_CANCEL,
    REMINDER_DONE,
    REMINDER_ORDER_NOW,
    REMINDER_PAYLOADS,
    REMINDER_RESCHEDULE,
    REMINDER_SCHEDULE,
    REMINDER_SNOOZE_7,
    REMINDER_STILL_PENDING,
)
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.diet_item import DietItem
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.reminder import Reminder
from app.services.preventive_calculator import (
    compute_next_due_date,
    compute_status,
)
from app.utils.date_utils import format_date_for_user, get_today_ist

logger = logging.getLogger(__name__)


# All valid reminder button payload IDs (from constants).
VALID_REMINDER_PAYLOADS = REMINDER_PAYLOADS


def handle_reminder_response(
    db: Session,
    reminder_id: UUID,
    payload: str,
) -> dict:
    """
    Process a user's response to a reminder WhatsApp button.

    Routes the response to the appropriate handler based on the
    button payload ID. Each handler implements a specific state
    transition on the reminder and its linked preventive record.

    Args:
        db: SQLAlchemy database session.
        reminder_id: UUID of the reminder being responded to.
        payload: The button payload ID (from WhatsApp interactive button).

    Returns:
        Dictionary with the result of the state transition:
            - status: result status string
            - reminder_id: the processed reminder ID
            - action: the payload that was processed
            - Additional fields depending on the action.

    Raises:
        ValueError: If the reminder is not found, already completed,
            or the payload is invalid.
    """
    # Validate the payload against known constants.
    # Reject unknown payloads to prevent unexpected behavior.
    if payload not in VALID_REMINDER_PAYLOADS:
        raise ValueError(
            f"Unknown reminder payload: '{payload}'. "
            f"Valid payloads: {VALID_REMINDER_PAYLOADS}"
        )

    # Load the reminder.
    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id)
        .first()
    )

    if not reminder:
        raise ValueError(f"Reminder not found: {reminder_id}")

    # Only 'sent' reminders can be responded to.
    # 'pending' reminders haven't been delivered yet.
    # 'completed' and 'snoozed' reminders are already processed.
    if reminder.status != "sent":
        raise ValueError(
            f"Reminder {reminder_id} cannot be responded to "
            f"(current status: {reminder.status}). "
            f"Only 'sent' reminders accept responses."
        )

    # Route to the appropriate handler.
    if payload in (REMINDER_DONE, REMINDER_ALREADY_DONE):
        return _handle_done(db, reminder)
    elif payload == REMINDER_SNOOZE_7:
        return _handle_snooze(db, reminder)
    elif payload == REMINDER_ORDER_NOW:
        return _handle_order_now(db, reminder)
    elif payload == REMINDER_STILL_PENDING:
        return _handle_still_pending(db, reminder)
    elif payload in (REMINDER_SCHEDULE, REMINDER_RESCHEDULE):
        return _handle_reschedule_request(db, reminder)
    elif payload == REMINDER_CANCEL:
        return _handle_cancel(db, reminder)


def _handle_done(db: Session, reminder: Reminder) -> dict:
    """
    Handle REMINDER_DONE / REMINDER_ALREADY_DONE — user confirms the action is done.

    Routes to the correct handler based on reminder.source_type:
        - preventive_record:      update last_done_date, recalculate next_due
        - diet_item:              update last_purchase_date to today
        - condition_medication:   mark as refilled (advance refill_due_date by 30 days)
        - condition_monitoring:   update last_done_date on monitoring row
        - hygiene_preference:     update last_done on hygiene pref row
        - (None/unknown):         fallback to preventive_record logic

    In all cases: reminder.status = 'completed'
    """
    today = get_today_ist()
    source_type = reminder.source_type or "preventive_record"

    if source_type == "diet_item" and reminder.source_id:
        return _handle_done_diet_item(db, reminder, today)
    elif source_type == "condition_medication" and reminder.source_id:
        return _handle_done_condition_medication(db, reminder, today)
    elif source_type == "condition_monitoring" and reminder.source_id:
        return _handle_done_condition_monitoring(db, reminder, today)
    elif source_type == "hygiene_preference":
        # Hygiene done: mark reminder completed; last_done will be set by user via dashboard
        reminder.status = "completed"
        db.commit()
        logger.info("Reminder DONE (hygiene): reminder_id=%s", str(reminder.id))
        return {
            "status": "completed",
            "reminder_id": str(reminder.id),
            "action": REMINDER_DONE,
            "message": "Logged! Great job keeping up with grooming.",
        }
    else:
        return _handle_done_preventive_record(db, reminder, today)


def _handle_done_preventive_record(db: Session, reminder: Reminder, today: date) -> dict:
    """Handle Done for preventive_record-sourced reminders."""
    record = (
        db.query(PreventiveRecord)
        .filter(PreventiveRecord.id == reminder.preventive_record_id)
        .first()
    )
    if not record:
        raise ValueError(f"Preventive record not found for reminder: {reminder.id}")

    master = (
        db.query(PreventiveMaster)
        .filter(PreventiveMaster.id == record.preventive_master_id)
        .first()
    )
    if not master:
        raise ValueError(f"Preventive master not found for record: {record.id}")

    record.last_done_date = today
    record.next_due_date = compute_next_due_date(today, master.recurrence_days)
    record.status = compute_status(record.next_due_date, master.reminder_before_days)
    reminder.status = "completed"
    db.commit()

    logger.info(
        "Reminder DONE: reminder_id=%s, record_id=%s, "
        "last_done=%s, next_due=%s, new_status=%s",
        str(reminder.id), str(record.id),
        str(today), str(record.next_due_date), record.status,
    )
    return {
        "status": "completed",
        "reminder_id": str(reminder.id),
        "action": REMINDER_DONE,
        "last_done_date": format_date_for_user(today),
        "next_due_date": format_date_for_user(record.next_due_date),
        "record_status": record.status,
    }


def _handle_done_diet_item(db: Session, reminder: Reminder, today: date) -> dict:
    """Handle Done for diet_item-sourced (food/supplement) reminders."""
    item = db.query(DietItem).filter(DietItem.id == reminder.source_id).first()
    if item:
        item.last_purchase_date = today
    reminder.status = "completed"
    db.commit()
    logger.info("Reminder DONE (diet_item): reminder_id=%s source_id=%s",
                str(reminder.id), str(reminder.source_id))
    return {
        "status": "completed",
        "reminder_id": str(reminder.id),
        "action": REMINDER_DONE,
        "message": "Restock logged! We'll remind you when the next reorder is due.",
    }


def _handle_done_condition_medication(db: Session, reminder: Reminder, today: date) -> dict:
    """Handle Done for chronic medicine reminders — advance refill_due_date by 30 days."""
    med = db.query(ConditionMedication).filter(ConditionMedication.id == reminder.source_id).first()
    if med and med.refill_due_date:
        med.refill_due_date = med.refill_due_date + timedelta(days=30)
    reminder.status = "completed"
    db.commit()
    next_due = med.refill_due_date if med else None
    logger.info("Reminder DONE (medicine): reminder_id=%s", str(reminder.id))
    return {
        "status": "completed",
        "reminder_id": str(reminder.id),
        "action": REMINDER_DONE,
        "next_refill_date": format_date_for_user(next_due) if next_due else None,
        "message": "Medicine refill logged.",
    }


def _handle_done_condition_monitoring(db: Session, reminder: Reminder, today: date) -> dict:
    """Handle Done for vet follow-up reminders."""
    monitoring = db.query(ConditionMonitoring).filter(
        ConditionMonitoring.id == reminder.source_id).first()
    if monitoring:
        monitoring.last_done_date = today
        # Clear next_due_date (vet will set new one at the visit)
        monitoring.next_due_date = None
    reminder.status = "completed"
    db.commit()
    logger.info("Reminder DONE (vet_followup): reminder_id=%s", str(reminder.id))
    return {
        "status": "completed",
        "reminder_id": str(reminder.id),
        "action": REMINDER_DONE,
        "message": "Vet follow-up logged! Great work staying on top of this.",
    }


def _handle_snooze(db: Session, reminder: Reminder) -> dict:
    """
    Handle REMINDER_SNOOZE_7 ("Remind Me Later") — snooze by category-specific days.

    For preventive_record sources: push next_due_date forward.
    For other sources: no date change (snooze is informational).
    In all cases: reminder.status = 'snoozed'.
    """
    from app.services.reminder_engine import _snooze_for_category
    snooze_days = _snooze_for_category(reminder.source_type or "preventive_record")

    old_due = reminder.next_due_date
    new_due = old_due + timedelta(days=snooze_days) if old_due else None

    # Update the source record's due date (preventive_record only)
    if reminder.preventive_record_id:
        record = db.query(PreventiveRecord).filter(
            PreventiveRecord.id == reminder.preventive_record_id
        ).first()
        if record and record.next_due_date:
            record.next_due_date = record.next_due_date + timedelta(days=snooze_days)
    elif reminder.source_type == "diet_item" and reminder.source_id:
        from app.models.diet_item import DietItem
        item = db.query(DietItem).filter(DietItem.id == reminder.source_id).first()
        if item and item.last_purchase_date:
            item.last_purchase_date = item.last_purchase_date + timedelta(days=snooze_days)

    reminder.status = "snoozed"
    db.commit()

    logger.info(
        "Reminder SNOOZED: reminder_id=%s snooze_days=%d old_due=%s new_due=%s",
        str(reminder.id), snooze_days, str(old_due), str(new_due),
    )
    return {
        "status": "snoozed",
        "reminder_id": str(reminder.id),
        "action": REMINDER_SNOOZE_7,
        "old_due_date": format_date_for_user(old_due) if old_due else None,
        "new_due_date": format_date_for_user(new_due) if new_due else None,
        "snooze_days": snooze_days,
    }


def _handle_order_now(db: Session, reminder: Reminder) -> dict:
    """
    Handle REMINDER_ORDER_NOW — user wants to order via WhatsApp.

    Marks the reminder as snoozed (pending order).
    The caller (message_router) is responsible for initiating the agentic_order flow.
    """
    reminder.status = "snoozed"
    db.commit()
    logger.info("Reminder ORDER_NOW: reminder_id=%s", str(reminder.id))
    return {
        "status": "order_initiated",
        "reminder_id": str(reminder.id),
        "action": REMINDER_ORDER_NOW,
        "initiate_order": True,  # signal to caller to start agentic_order
    }


def _handle_still_pending(db: Session, reminder: Reminder) -> dict:
    """
    Handle REMINDER_STILL_PENDING — user acknowledges but hasn't done it yet.

    Updates last_ignored_at to prevent false ignore detection.
    Does NOT change reminder.status — it stays 'sent' for future follow-up.
    """
    from datetime import datetime

    from app.utils.date_utils import IST
    reminder.last_ignored_at = datetime.now(IST)
    # Don't increment ignore_count — user actively acknowledged it
    db.commit()
    logger.info("Reminder STILL_PENDING: reminder_id=%s", str(reminder.id))
    return {
        "status": "acknowledged",
        "reminder_id": str(reminder.id),
        "action": REMINDER_STILL_PENDING,
        "message": "Got it — we'll follow up soon.",
    }


def _handle_reschedule_request(db: Session, reminder: Reminder) -> dict:
    """
    Handle REMINDER_RESCHEDULE — user wants to pick a new date.

    This function does NOT complete the reschedule — it only marks
    the reminder as awaiting a date response. The actual date update
    happens in apply_reschedule_date() when the user sends a text
    message with the new date.

    The webhook layer detects that a reschedule is pending and routes
    the next text message to apply_reschedule_date().

    Args:
        db: SQLAlchemy database session.
        reminder: The reminder being responded to.

    Returns:
        Result dictionary indicating a date prompt should be sent.
    """
    logger.info(
        "Reminder RESCHEDULE requested: reminder_id=%s, record_id=%s. "
        "Awaiting user date input.",
        str(reminder.id),
        str(reminder.preventive_record_id),
    )

    # The reminder stays in 'sent' status until the user provides a date.
    # The service layer tracks this state and routes the next text message
    # to apply_reschedule_date().

    return {
        "status": "awaiting_date",
        "reminder_id": str(reminder.id),
        "action": REMINDER_RESCHEDULE,
        "message": "Please send the new date for this preventive item.",
    }


def apply_reschedule_date(
    db: Session,
    reminder_id: UUID,
    new_date: date,
) -> dict:
    """
    Apply a rescheduled date to a preventive record.

    Called when the user responds to a REMINDER_RESCHEDULE prompt with
    a valid date. The date must already be parsed and validated by
    the caller using parse_date() from date_utils.

    State transitions:
        - preventive_record.next_due_date = new_date
        - Recalculate preventive_record.status based on new next_due_date.
        - reminder.status = 'completed'

    Args:
        db: SQLAlchemy database session.
        reminder_id: UUID of the reminder being rescheduled.
        new_date: The validated new due date from user input.

    Returns:
        Result dictionary with updated fields.

    Raises:
        ValueError: If the reminder or its linked record is not found.
    """
    # Load the reminder.
    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id)
        .first()
    )

    if not reminder:
        raise ValueError(f"Reminder not found: {reminder_id}")

    # Load the linked preventive record.
    record = (
        db.query(PreventiveRecord)
        .filter(PreventiveRecord.id == reminder.preventive_record_id)
        .first()
    )

    if not record:
        raise ValueError(
            f"Preventive record not found for reminder: {reminder_id}"
        )

    # Load preventive master for reminder_before_days (status calculation).
    master = (
        db.query(PreventiveMaster)
        .filter(PreventiveMaster.id == record.preventive_master_id)
        .first()
    )

    if not master:
        raise ValueError(
            f"Preventive master not found for record: {record.id}"
        )

    # Update next_due_date to the user-provided date.
    old_due = record.next_due_date
    record.next_due_date = new_date

    # Recalculate status based on the new next_due_date.
    record.status = compute_status(new_date, master.reminder_before_days)

    # Mark reminder as completed — reschedule is done.
    reminder.status = "completed"

    db.commit()

    logger.info(
        "Reminder RESCHEDULED: reminder_id=%s, record_id=%s, "
        "old_due=%s, new_due=%s, new_status=%s",
        str(reminder.id),
        str(record.id),
        str(old_due),
        str(new_date),
        record.status,
    )

    return {
        "status": "rescheduled",
        "reminder_id": str(reminder.id),
        "action": REMINDER_RESCHEDULE,
        "old_due_date": format_date_for_user(old_due),
        "new_due_date": format_date_for_user(new_date),
        "record_status": record.status,
    }


def _handle_cancel(db: Session, reminder: Reminder) -> dict:
    """
    Handle REMINDER_CANCEL — user cancels this preventive item.

    State transitions:
        - preventive_record.status = 'cancelled'
        - reminder.status = 'completed'
        - Cancelled records are excluded from future reminder engine runs.
        - Cancellation is permanent for this record — a new record must be
          created if the user wants to resume tracking.

    Args:
        db: SQLAlchemy database session.
        reminder: The reminder being responded to.

    Returns:
        Result dictionary confirming cancellation.
    """
    # Load the linked preventive record.
    record = (
        db.query(PreventiveRecord)
        .filter(PreventiveRecord.id == reminder.preventive_record_id)
        .first()
    )

    if not record:
        raise ValueError(
            f"Preventive record not found for reminder: {reminder.id}"
        )

    # Cancel the preventive record.
    # Cancelled records are excluded from the reminder engine queries
    # (it only processes 'upcoming' and 'overdue' records).
    record.status = "cancelled"

    # Mark reminder as completed — cancel is a terminal action.
    reminder.status = "completed"

    db.commit()

    logger.info(
        "Reminder CANCELLED: reminder_id=%s, record_id=%s, pet_id=%s",
        str(reminder.id),
        str(record.id),
        str(record.pet_id),
    )

    return {
        "status": "cancelled",
        "reminder_id": str(reminder.id),
        "action": REMINDER_CANCEL,
        "record_id": str(record.id),
    }
