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
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.core.constants import CARE_PLAN_DUE_SOON_DAYS
from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.contact import Contact
from app.models.document import Document
from app.models.preventive_record import PreventiveRecord

logger = logging.getLogger(__name__)


async def get_condition_timeline(db: Session, pet_id: UUID) -> dict:
    """
    Build a chronological management timeline for all conditions.

    Combines:
        - Condition diagnosis events
        - Medication start dates
        - Monitoring check events (done and upcoming)
        - Preventive record events (deworming, vaccines, etc.)

    Each event now includes extra fields for the zayn-style two-column
    timeline card UI:
        label_color  — hex color string driven by event type
        border       — same as label_color (used for card border)
        sublabel     — short secondary label (e.g. "Episode 1", "Prescribed")
        source_text  — formatted attribution line
        pills        — list of {t, c, bg} key-finding chips

    Returns:
        {"events": [...], "total": int}
    """
    # Color palette for event types
    COLORS = {
        "diagnosis": "#FF3B30",
        "treatment":  "#007AFF",
        "vet_visit":  "#34C759",
        "monitoring": "#FF9500",
        "vaccine":    "#8E44AD",
        "preventive": "#8E8E93",
    }

    def _make_pill(text: str, color: str, bg: str) -> dict:
        return {"t": text, "c": color, "bg": bg}

    events = []

    # ── Condition diagnosis + medication + monitoring events ──────────────────
    conditions = (
        db.query(Condition)
        .options(selectinload(Condition.medications), selectinload(Condition.monitoring))
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .all()
    )

    for cond in conditions:
        color = COLORS["diagnosis"]
        event_date = str(cond.diagnosed_at) if cond.diagnosed_at else (
            str(cond.created_at.date()) if cond.created_at else None
        )
        if event_date:
            pills = []
            if cond.condition_type:
                pills.append(_make_pill(cond.condition_type.capitalize(), "#8E8E93", "#F2F2F7"))
            if cond.diagnosis:
                pills.append(_make_pill(cond.diagnosis[:60], color, color + "12"))
            events.append({
                "date": event_date,
                "type": "diagnostic",
                "icon": cond.icon or "🏥",
                "title": f"{cond.name} diagnosed",
                "detail": cond.diagnosis or cond.condition_type,
                "tag": "Diagnosis",
                "label_color": color,
                "border": color,
                "sublabel": "Diagnosed",
                "source_text": cond.managed_by or "",
                "pills": pills,
            })

        # Medication events
        for med in cond.medications:
            med_date = str(med.started_at) if getattr(med, "started_at", None) else (
                str(med.created_at.date()) if med.created_at else None
            )
            if med_date:
                mcolor = COLORS["treatment"]
                dose_info = f"{med.dose or ''} {med.frequency or ''}".strip()
                pills = [_make_pill(med.name, mcolor, mcolor + "12")]
                if dose_info:
                    pills.append(_make_pill(dose_info, "#8E8E93", "#F2F2F7"))
                events.append({
                    "date": med_date,
                    "type": "treatment",
                    "icon": "💊",
                    "title": f"Started {med.name}",
                    "detail": dose_info or None,
                    "tag": "Treatment",
                    "label_color": mcolor,
                    "border": mcolor,
                    "sublabel": "Prescribed",
                    "source_text": cond.managed_by or "",
                    "pills": pills,
                })

        # Monitoring events — last_done and upcoming/overdue
        today = date.today()
        for mon in cond.monitoring:
            # Last done event
            if mon.last_done_date:
                mcolor = COLORS["vet_visit"]
                pills = [_make_pill(f"Done: {mon.last_done_date}", mcolor, "#F0FFF4")]
                if mon.next_due_date:
                    pills.append(_make_pill(f"Next: {mon.next_due_date}", "#8E8E93", "#F2F2F7"))
                events.append({
                    "date": str(mon.last_done_date),
                    "type": "monitoring",
                    "icon": "🩺",
                    "title": mon.name,
                    "detail": f"Follow-up for {cond.name}",
                    "tag": "Vet Visit",
                    "label_color": mcolor,
                    "border": mcolor,
                    "sublabel": "Completed",
                    "source_text": cond.managed_by or "",
                    "pills": pills,
                })
            # Upcoming / overdue event (next_due_date only when not done)
            elif mon.next_due_date:
                days_diff = (mon.next_due_date - today).days
                if days_diff < 0:
                    tag = "Overdue"
                    mcolor = "#FF3B30"
                    due_text = f"Overdue since: {mon.next_due_date}"
                elif days_diff <= CARE_PLAN_DUE_SOON_DAYS:
                    tag = "Due Soon"
                    mcolor = COLORS["monitoring"]
                    due_text = f"Due: {mon.next_due_date}"
                else:
                    tag = "On Track"
                    mcolor = COLORS["vet_visit"]
                    due_text = f"Due: {mon.next_due_date}"
                pills = [_make_pill(
                    due_text,
                    mcolor, mcolor + "12",
                )]
                events.append({
                    "date": str(mon.next_due_date),
                    "type": "monitoring",
                    "icon": "🩺",
                    "title": f"{mon.name} due",
                    "detail": f"Scheduled follow-up for {cond.name}.",
                    "tag": tag,
                    "label_color": mcolor,
                    "border": mcolor,
                    "sublabel": tag,
                    "source_text": cond.managed_by or "",
                    "pills": pills,
                })

    # ── Preventive record events ──────────────────────────────────────────────
    preventive_rows = (
        db.query(PreventiveRecord)
        .filter(PreventiveRecord.pet_id == pet_id, PreventiveRecord.last_done_date != None)
        .all()
    )

    cat_icon = {"vaccination": "💉", "deworming": "🪱", "flea_tick": "🐛"}
    cat_color = {"vaccination": COLORS["vaccine"], "deworming": COLORS["treatment"], "flea_tick": COLORS["treatment"]}
    cat_tag = {"vaccination": "Vet Visit", "deworming": "Treatment", "flea_tick": "Treatment"}

    for rec in preventive_rows:
        item_name = rec.preventive_master.item_name if rec.preventive_master else "Preventive"
        category = rec.preventive_master.category if rec.preventive_master else "other"
        rcolor = cat_color.get(category, COLORS["preventive"])
        pills = [_make_pill(rec.status.replace("_", " ").title() if rec.status else "Done", rcolor, rcolor + "12")]
        if rec.next_due_date:
            pills.append(_make_pill(f"Next: {rec.next_due_date}", "#8E8E93", "#F2F2F7"))
        events.append({
            "date": str(rec.last_done_date),
            "type": "vet" if category == "vaccination" else "preventive",
            "icon": cat_icon.get(category, "✅"),
            "title": item_name,
            "detail": f"Status: {rec.status}" if rec.status else None,
            "tag": cat_tag.get(category, "Treatment"),
            "label_color": rcolor,
            "border": rcolor,
            "sublabel": category.replace("_", " ").title() if category else "",
            "source_text": "",
            "pills": pills,
        })

    # Sort chronologically (most recent first)
    events.sort(key=lambda e: e["date"], reverse=True)

    return {"events": events, "total": len(events)}


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

    # Simple text fields
    for key in ("name", "frequency"):
        if key in updates and updates[key] is not None:
            setattr(mon, key, updates[key])

    # Date fields — parse string → date object
    for date_field in ("last_done_date", "next_due_date"):
        if date_field in updates and updates[date_field] is not None:
            raw = updates[date_field]
            if isinstance(raw, str):
                try:
                    from app.utils.date_utils import parse_date
                    setattr(mon, date_field, parse_date(raw))
                except (ValueError, ImportError):
                    logger.warning("Could not parse %s value '%s'", date_field, raw)
            else:
                setattr(mon, date_field, raw)

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

    # Load active conditions with relationships — eager-load to avoid N+1 on medications/monitoring
    conditions = (
        db.query(Condition)
        .options(selectinload(Condition.medications), selectinload(Condition.monitoring))
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
    # Find vet contact — prefer the one linked to the latest prescription.
    vet = None
    latest_prescription = (
        db.query(Document)
        .filter(
            Document.pet_id == pet_id,
            Document.document_category.ilike("prescription"),
            Document.event_date.isnot(None),
        )
        .order_by(Document.event_date.desc())
        .first()
    )

    # Pull vet contact from the prescription's doctor/clinic info when available.
    if latest_prescription and latest_prescription.doctor_name:
        vet = (
            db.query(Contact)
            .filter(
                Contact.pet_id == pet_id,
                Contact.role == "veterinarian",
                Contact.name == latest_prescription.doctor_name,
            )
            .first()
        )
    if not vet:
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
    # Use the latest prescription event_date as the primary last_visit_date.
    last_visit_date = (
        str(latest_prescription.event_date) if latest_prescription and latest_prescription.event_date else None
    )
    next_due_date = None
    notes = None

    for cond in conditions:
        if cond.managed_by and vet and vet.name and vet.name.lower() in cond.managed_by.lower():
            managing_condition = cond.name
            managing_since = str(cond.diagnosed_at) if cond.diagnosed_at else None
            if not last_visit_date:
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
        if not last_visit_date:
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
        elif days_diff <= CARE_PLAN_DUE_SOON_DAYS:
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
