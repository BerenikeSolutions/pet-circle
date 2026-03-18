"""
PetCircle Phase 1 — Condition Service

Provides condition management logic:
    - get_condition_timeline: Builds chronological timeline from conditions,
      medications, and preventive records for the management chronology view.
    - get_condition_recommendations: Generates smart health recommendations
      from conditions, medications, monitoring, and preventive records.
    - update_condition: Updates an existing condition's fields.
    - add_condition_medication: Adds a medication to a condition.
    - update_condition_medication: Updates an existing medication.
    - delete_condition_medication: Removes a medication.
    - add_condition_monitoring: Adds a monitoring item to a condition.
    - update_condition_monitoring: Updates a monitoring item.
    - delete_condition_monitoring: Removes a monitoring item.
"""

import logging
from datetime import date, timedelta
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.preventive_record import PreventiveRecord
from app.models.contact import Contact

logger = logging.getLogger(__name__)


async def get_condition_timeline(db: Session, pet_id: UUID) -> dict:
    """
    Build a chronological management timeline for all conditions.

    Combines:
        - Condition diagnosis events
        - Medication start dates
        - Preventive record events (deworming, vaccines, etc.)

    Returns:
        {"events": [{"date": str, "type": str, "icon": str, "title": str, "detail": str, "tag": str}]}
    """
    events = []

    # Condition diagnosis events
    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .all()
    )

    for cond in conditions:
        event_date = str(cond.diagnosed_at) if cond.diagnosed_at else str(cond.created_at.date()) if cond.created_at else None
        if event_date:
            # Build detail with managing vet info
            detail_parts = []
            if cond.diagnosis:
                detail_parts.append(cond.diagnosis)
            if cond.managed_by:
                detail_parts.append(cond.managed_by)
            events.append({
                "date": event_date,
                "type": "diagnostic",
                "icon": cond.icon or "🏥",
                "title": f"{cond.name} diagnosed",
                "detail": ". ".join(detail_parts) if detail_parts else cond.condition_type,
                "tag": "Diagnosis",
            })

        # Medication start events — tagged as Treatment
        for med in cond.medications:
            med_date = str(med.started_at) if med.started_at else str(med.created_at.date()) if med.created_at else None
            if med_date:
                events.append({
                    "date": med_date,
                    "type": "treatment",
                    "icon": "💊",
                    "title": f"Started {med.name}",
                    "detail": f"{med.dose or ''} {med.frequency or ''}".strip() or None,
                    "tag": "Treatment",
                })

        # Monitoring events — upcoming or overdue checks
        for mon in cond.monitoring:
            if mon.next_due_date:
                today = date.today()
                if mon.next_due_date < today:
                    tag = "Overdue"
                elif mon.next_due_date <= today + timedelta(days=30):
                    tag = "Upcoming"
                else:
                    tag = "Upcoming"
                events.append({
                    "date": str(mon.next_due_date),
                    "type": "diagnostic",
                    "icon": "🩺",
                    "title": f"{mon.name} due",
                    "detail": f"Scheduled follow-up for {cond.name}. {'Not yet completed.' if mon.next_due_date < today else ''}".strip(),
                    "tag": tag,
                })

    # Preventive record events (vaccines, deworming, etc.)
    preventive_rows = (
        db.query(PreventiveRecord)
        .filter(PreventiveRecord.pet_id == pet_id, PreventiveRecord.last_done_date != None)
        .all()
    )

    for rec in preventive_rows:
        item_name = rec.preventive_master.item_name if rec.preventive_master else "Preventive"
        category = rec.preventive_master.category if rec.preventive_master else "other"

        icon_map = {
            "vaccination": "💉",
            "deworming": "🪱",
            "flea_tick": "🐛",
        }

        # Map preventive categories to timeline tags
        tag_map = {
            "vaccination": "Vet Visit",
            "deworming": "Treatment",
            "flea_tick": "Treatment",
        }
        events.append({
            "date": str(rec.last_done_date),
            "type": "vet" if category == "vaccination" else "preventive",
            "icon": icon_map.get(category, "✅"),
            "title": item_name,
            "detail": f"Status: {rec.status}" if rec.status else None,
            "tag": tag_map.get(category, "Treatment"),
        })

    # Sort chronologically (most recent first)
    events.sort(key=lambda e: e["date"], reverse=True)

    return {"events": events}


def update_condition(db: Session, pet_id: UUID, condition_id: UUID, updates: dict) -> dict:
    """Update an existing condition's fields."""
    condition = (
        db.query(Condition)
        .filter(Condition.id == condition_id, Condition.pet_id == pet_id, Condition.is_active == True)
        .first()
    )
    if not condition:
        raise ValueError("Condition not found")

    allowed_fields = {"name", "diagnosis", "condition_type", "diagnosed_at", "notes", "icon", "managed_by"}
    for key, value in updates.items():
        if key in allowed_fields and value is not None:
            setattr(condition, key, value)

    db.commit()
    return {"status": "updated", "condition_id": str(condition.id)}


def add_condition_medication(db: Session, pet_id: UUID, condition_id: UUID, data: dict) -> dict:
    """Add a medication to an existing condition."""
    condition = (
        db.query(Condition)
        .filter(Condition.id == condition_id, Condition.pet_id == pet_id, Condition.is_active == True)
        .first()
    )
    if not condition:
        raise ValueError("Condition not found")

    # Parse refill_due_date if provided
    refill_due = data.get("refill_due_date")
    if isinstance(refill_due, str):
        try:
            from app.utils.date_utils import parse_date
            refill_due = parse_date(refill_due)
        except (ValueError, ImportError):
            refill_due = None

    med = ConditionMedication(
        condition_id=condition.id,
        name=data["name"],
        dose=data.get("dose"),
        frequency=data.get("frequency"),
        route=data.get("route"),
        started_at=data.get("started_at"),
        refill_due_date=refill_due,
        price=data.get("price"),
    )
    db.add(med)
    db.commit()
    return {"status": "created", "medication_id": str(med.id)}


def update_condition_medication(db: Session, pet_id: UUID, medication_id: UUID, updates: dict) -> dict:
    """Update an existing medication."""
    med = (
        db.query(ConditionMedication)
        .join(Condition)
        .filter(
            ConditionMedication.id == medication_id,
            Condition.pet_id == pet_id,
            Condition.is_active == True,
        )
        .first()
    )
    if not med:
        raise ValueError("Medication not found")

    allowed_fields = {"name", "dose", "frequency", "route", "status", "started_at", "notes", "refill_due_date", "price"}
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(med, key, value)

    db.commit()
    return {"status": "updated", "medication_id": str(med.id)}


def delete_condition_medication(db: Session, pet_id: UUID, medication_id: UUID) -> dict:
    """Delete a medication."""
    med = (
        db.query(ConditionMedication)
        .join(Condition)
        .filter(
            ConditionMedication.id == medication_id,
            Condition.pet_id == pet_id,
            Condition.is_active == True,
        )
        .first()
    )
    if not med:
        raise ValueError("Medication not found")

    db.delete(med)
    db.commit()
    return {"status": "deleted", "medication_id": str(medication_id)}


def add_condition_monitoring(db: Session, pet_id: UUID, condition_id: UUID, data: dict) -> dict:
    """Add a monitoring item to an existing condition."""
    condition = (
        db.query(Condition)
        .filter(Condition.id == condition_id, Condition.pet_id == pet_id, Condition.is_active == True)
        .first()
    )
    if not condition:
        raise ValueError("Condition not found")

    # Parse date fields if provided
    next_due = data.get("next_due_date")
    last_done = data.get("last_done_date")
    if isinstance(next_due, str):
        try:
            from app.utils.date_utils import parse_date
            next_due = parse_date(next_due)
        except (ValueError, ImportError):
            next_due = None
    if isinstance(last_done, str):
        try:
            from app.utils.date_utils import parse_date
            last_done = parse_date(last_done)
        except (ValueError, ImportError):
            last_done = None

    mon = ConditionMonitoring(
        condition_id=condition.id,
        name=data["name"],
        frequency=data.get("frequency"),
        next_due_date=next_due,
        last_done_date=last_done,
    )
    db.add(mon)
    db.commit()
    return {"status": "created", "monitoring_id": str(mon.id)}


def update_condition_monitoring(db: Session, pet_id: UUID, monitoring_id: UUID, updates: dict) -> dict:
    """Update an existing monitoring item."""
    mon = (
        db.query(ConditionMonitoring)
        .join(Condition)
        .filter(
            ConditionMonitoring.id == monitoring_id,
            Condition.pet_id == pet_id,
            Condition.is_active == True,
        )
        .first()
    )
    if not mon:
        raise ValueError("Monitoring item not found")

    allowed_fields = {"name", "frequency"}
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(mon, key, value)

    db.commit()
    return {"status": "updated", "monitoring_id": str(mon.id)}


def delete_condition_monitoring(db: Session, pet_id: UUID, monitoring_id: UUID) -> dict:
    """Delete a monitoring item."""
    mon = (
        db.query(ConditionMonitoring)
        .join(Condition)
        .filter(
            ConditionMonitoring.id == monitoring_id,
            Condition.pet_id == pet_id,
            Condition.is_active == True,
        )
        .first()
    )
    if not mon:
        raise ValueError("Monitoring item not found")

    db.delete(mon)
    db.commit()
    return {"status": "deleted", "monitoring_id": str(monitoring_id)}


async def get_condition_recommendations(db: Session, pet_id: UUID) -> dict:
    """
    Generate smart health recommendations based on conditions, medications,
    monitoring checks, and preventive records. All data comes from DB.

    Returns:
        {"recommendations": [{"icon", "title", "reason", "priority", "cart_id"}]}
    """
    recommendations = []
    today = date.today()

    # Load active conditions with relationships
    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .all()
    )

    # Load preventive records for gap analysis
    preventive_rows = (
        db.query(PreventiveRecord)
        .filter(PreventiveRecord.pet_id == pet_id)
        .all()
    )

    for cond in conditions:
        # Check for monitoring checks that are overdue or upcoming
        for mon in cond.monitoring:
            if mon.next_due_date and mon.next_due_date < today:
                days_overdue = (today - mon.next_due_date).days
                priority = "urgent" if days_overdue > 30 else "high"
                recommendations.append({
                    "icon": "🔬",
                    "title": mon.name,
                    "reason": f"{mon.name} for {cond.name} was due {mon.next_due_date.strftime('%d %b %Y')}. "
                              f"Overdue by {days_overdue} days — book recommended.",
                    "priority": priority,
                    "cart_id": None,
                })

        # Check for medications nearing refill
        for med in cond.medications:
            if med.status == "active" and med.refill_due_date:
                days_until_refill = (med.refill_due_date - today).days
                if days_until_refill <= 0:
                    recommendations.append({
                        "icon": "💊",
                        "title": f"{med.name} Refill Critical",
                        "reason": f"{med.name} for {cond.name} refill is overdue. "
                                  f"Missing doses may worsen the condition.",
                        "priority": "urgent",
                        "cart_id": None,
                    })
                elif days_until_refill <= 7:
                    recommendations.append({
                        "icon": "💊",
                        "title": f"{med.name} Refill Due Soon",
                        "reason": f"{med.name} for {cond.name} refill is due in {days_until_refill} days. "
                                  f"Reorder to avoid gaps in treatment.",
                        "priority": "high",
                        "cart_id": None,
                    })

        # Chronic conditions without recent monitoring
        if cond.condition_type == "chronic" and len(cond.monitoring) == 0:
            recommendations.append({
                "icon": "📋",
                "title": f"Monitoring Plan for {cond.name}",
                "reason": f"{cond.name} is a chronic condition with no monitoring checks set up. "
                          f"Regular follow-ups help track progression.",
                "priority": "medium",
                "cart_id": None,
            })

    # Check for overdue preventive records
    for rec in preventive_rows:
        if rec.next_due_date and rec.next_due_date < today:
            item_name = rec.preventive_master.item_name if rec.preventive_master else "Preventive care"
            category = rec.preventive_master.category if rec.preventive_master else "other"
            days_overdue = (today - rec.next_due_date).days
            if days_overdue > 14:
                icon_map = {"vaccination": "💉", "deworming": "🪱", "flea_tick": "🐛"}
                recommendations.append({
                    "icon": icon_map.get(category, "✅"),
                    "title": f"{item_name} Overdue",
                    "reason": f"{item_name} was due {rec.next_due_date.strftime('%d %b %Y')} "
                              f"and is now {days_overdue} days overdue.",
                    "priority": "urgent" if days_overdue > 30 else "high",
                    "cart_id": None,
                })

    # Sort by priority: urgent > high > medium
    priority_order = {"urgent": 0, "high": 1, "medium": 2}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 3))

    return {"recommendations": recommendations}


def get_last_vet_visit(db: Session, pet_id: UUID) -> dict:
    """
    Build last vet visit info from contacts and conditions data.

    Returns:
        {
            "vet_name", "clinic_name", "managing_condition",
            "managing_since", "last_visit_date", "next_due_date",
            "notes", "status"
        }
    """
    # Find vet contact
    vet = (
        db.query(Contact)
        .filter(Contact.pet_id == pet_id, Contact.role == "veterinarian")
        .first()
    )

    # Find the oldest active condition managed by this vet
    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .order_by(Condition.diagnosed_at.asc().nullslast())
        .all()
    )

    managing_condition = None
    managing_since = None
    last_visit_date = None
    next_due_date = None
    notes = None

    for cond in conditions:
        if cond.managed_by and vet and vet.name and vet.name.lower() in cond.managed_by.lower():
            managing_condition = cond.name
            managing_since = str(cond.diagnosed_at) if cond.diagnosed_at else None
            last_visit_date = str(cond.diagnosed_at) if cond.diagnosed_at else None
            notes = cond.notes
            # Compute next due from monitoring checks
            for mon in cond.monitoring:
                if mon.next_due_date:
                    if next_due_date is None or str(mon.next_due_date) < next_due_date:
                        next_due_date = str(mon.next_due_date)
            break

    # If no condition match, use most recent condition for visit info
    if not managing_condition and conditions:
        cond = conditions[0]
        managing_condition = cond.name
        managing_since = str(cond.diagnosed_at) if cond.diagnosed_at else None
        last_visit_date = str(cond.diagnosed_at) if cond.diagnosed_at else None
        notes = cond.notes

    # Determine status
    today = date.today()
    status = None
    if next_due_date:
        from datetime import datetime
        nd = datetime.strptime(next_due_date, "%Y-%m-%d").date()
        days_diff = (nd - today).days
        if days_diff < 0:
            status = "overdue"
        elif days_diff <= 30:
            status = "due_soon"
        else:
            status = "on_track"

    return {
        "vet_name": vet.name if vet else None,
        "clinic_name": vet.clinic_name if vet else None,
        "address": vet.address if vet else None,
        "managing_condition": managing_condition,
        "managing_since": managing_since,
        "last_visit_date": last_visit_date,
        "next_due_date": next_due_date,
        "notes": notes,
        "status": status,
    }
