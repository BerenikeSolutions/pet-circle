"""
PetCircle Phase 1 — Condition Service

Provides condition management logic:
    - get_condition_timeline: Builds chronological timeline from conditions,
      medications, and preventive records for the management chronology view.
    - update_condition: Updates an existing condition's fields.
    - add_condition_medication: Adds a medication to a condition.
    - update_condition_medication: Updates an existing medication.
    - delete_condition_medication: Removes a medication.
    - add_condition_monitoring: Adds a monitoring item to a condition.
    - update_condition_monitoring: Updates a monitoring item.
    - delete_condition_monitoring: Removes a monitoring item.
"""

import logging
from datetime import date
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.preventive_record import PreventiveRecord

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
            events.append({
                "date": event_date,
                "type": "diagnosis",
                "icon": "🏥",
                "title": f"{cond.name} diagnosed",
                "detail": cond.diagnosis or cond.condition_type,
                "tag": cond.condition_type,
            })

        # Medication start events
        for med in cond.medications:
            med_date = str(med.started_at) if med.started_at else str(med.created_at.date()) if med.created_at else None
            if med_date:
                events.append({
                    "date": med_date,
                    "type": "medication",
                    "icon": "💊",
                    "title": f"Started {med.name}",
                    "detail": f"{med.dose or ''} {med.frequency or ''}".strip() or None,
                    "tag": med.status,
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

        events.append({
            "date": str(rec.last_done_date),
            "type": "preventive",
            "icon": icon_map.get(category, "✅"),
            "title": item_name,
            "detail": f"Status: {rec.status}" if rec.status else None,
            "tag": category,
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

    allowed_fields = {"name", "diagnosis", "condition_type", "diagnosed_at", "notes"}
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

    med = ConditionMedication(
        condition_id=condition.id,
        name=data["name"],
        dose=data.get("dose"),
        frequency=data.get("frequency"),
        route=data.get("route"),
        started_at=data.get("started_at"),
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

    allowed_fields = {"name", "dose", "frequency", "route", "status", "started_at", "notes"}
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

    mon = ConditionMonitoring(
        condition_id=condition.id,
        name=data["name"],
        frequency=data.get("frequency"),
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
