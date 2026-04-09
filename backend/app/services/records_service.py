"""
PetCircle Dashboard Rebuild — Records Service

Builds Records V2 payload for the records view:
    - vet_visits: prescription documents enriched with Rx context
    - records: all other successful documents grouped by record type
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models.condition import Condition
from app.models.document import Document
from app.models.pet import Pet

_TAG_STYLES: dict[str, dict[str, str]] = {
    "prescription": {"tag": "Vet Visit", "tag_color": "#B45309", "tag_bg": "#FFF3E0"},
    "diagnostic": {"tag": "Lab Report", "tag_color": "#0F766E", "tag_bg": "#E6FFFA"},
    "imaging": {"tag": "Imaging", "tag_color": "#1D4ED8", "tag_bg": "#E8F0FF"},
    "other": {"tag": "Record", "tag_color": "#374151", "tag_bg": "#F3F4F6"},
    "whatsapp": {"tag": "WhatsApp", "tag_color": "#166534", "tag_bg": "#E9FBEF"},
}

_IMAGING_PATTERNS = (
    re.compile(r"\bx-?ray\b"),
    re.compile(r"\bultrasound\b"),
    re.compile(r"\busg\b"),
    re.compile(r"\bmri\b"),
    re.compile(r"\bct\s*scan\b"),
    re.compile(r"\bradiograph(?:y|ic)?\b"),
    re.compile(r"\bsonograph(?:y|ic)?\b"),
)


def _sort_key_by_event_date(document: Document) -> date:
    """Return sortable event date, defaulting missing dates to minimum."""
    return document.event_date or date.min


def _style_for_category(document_category: str | None) -> dict[str, str]:
    """Map persisted category to records-view tag styling."""
    category = (document_category or "").strip().lower()
    if category == "prescription":
        return _TAG_STYLES["prescription"]
    if category == "diagnostic":
        return _TAG_STYLES["diagnostic"]
    if category == "imaging":
        return _TAG_STYLES["imaging"]
    return _TAG_STYLES["other"]


def _record_type_for_document(document: Document) -> tuple[str, str]:
    """Classify non-prescription document into records-v2 type and icon."""
    category = (document.document_category or "").strip().lower()
    doc_name = (document.document_name or "").strip().lower()

    if category == "diagnostic":
        return "lab_reports", "🧪"

    is_imaging = category == "imaging" or any(pattern.search(doc_name) for pattern in _IMAGING_PATTERNS)
    if is_imaging:
        return "imaging", "🩻"

    if document.source_wamid:
        return "whatsapp", "💬"

    return "lab_reports", "📄"


def _extract_rx_summary(document: Document, conditions: list[Condition]) -> str:
    """Build a concise Rx summary from linked condition extraction data.

    Prefers active medication names joined by ' · ' (compact pill display),
    falls back to diagnoses, then document name.
    """
    med_names = [
        med.name.strip()
        for condition in conditions
        for med in condition.medications
        if med.name and med.name.strip() and (med.status or "active") == "active"
    ]
    if med_names:
        return " · ".join(dict.fromkeys(med_names))

    diagnoses = [
        condition.diagnosis.strip()
        for condition in conditions
        if condition.diagnosis and condition.diagnosis.strip()
    ]
    if diagnoses:
        return "; ".join(dict.fromkeys(diagnoses))

    if document.document_name:
        return document.document_name

    return "Prescription reviewed"


def _extract_medications(conditions: list[Condition]) -> list[dict[str, str | None]]:
    """Flatten active medications linked to conditions extracted from the visit."""
    medications: list[dict[str, str | None]] = []
    for condition in conditions:
        for medication in condition.medications:
            if (medication.status or "active") != "active":
                continue
            medications.append(
                {
                    "name": medication.name,
                    "dose": medication.dose,
                    "duration": medication.frequency,
                }
            )
    return medications


def _extract_notes(conditions: list[Condition]) -> str | None:
    """Combine non-empty condition notes into a single display string."""
    notes = [condition.notes.strip() for condition in conditions if condition.notes and condition.notes.strip()]
    if not notes:
        return None
    return " | ".join(dict.fromkeys(notes))


def _extract_visit_key_finding(document: Document, conditions: list[Condition]) -> str:
    """Build compact key-finding text for vet visit pill display."""
    diagnoses = [
        condition.diagnosis.strip()
        for condition in conditions
        if condition.diagnosis and condition.diagnosis.strip()
    ]
    if diagnoses:
        return diagnoses[0]

    for condition in conditions:
        for medication in condition.medications:
            if (medication.status or "active") != "active":
                continue
            if medication.name and medication.name.strip():
                return f"Rx: {medication.name.strip()}"

    if document.document_name and document.document_name.strip():
        return document.document_name.strip()

    return "Prescription reviewed"


def _extract_record_key_finding(document: Document, record_type: str) -> str:
    """Provide concise key-finding fallback text for non-prescription records."""
    if document.document_name and document.document_name.strip():
        return document.document_name.strip()

    if record_type == "lab_reports":
        return "Lab report reviewed"
    if record_type == "imaging":
        return "Imaging findings reviewed"
    if record_type == "whatsapp":
        return "Shared on WhatsApp"

    return "Record reviewed"


def _fetch_documents(db: Session, pet_id: Any) -> list[Document]:
    """Load successful documents for one pet, newest event first."""
    return (
        db.query(Document)
        .filter(
            Document.pet_id == pet_id,
            Document.extraction_status == "success",
        )
        .order_by(Document.event_date.desc().nullslast())
        .all()
    )


def _fetch_conditions_for_documents(
    db: Session,
    pet_id: Any,
    document_ids: list[Any],
) -> dict[Any, list[Condition]]:
    """Load active conditions keyed by source document id."""
    if not document_ids:
        return {}

    rows = (
        db.query(Condition)
        .options(selectinload(Condition.medications))
        .filter(
            Condition.pet_id == pet_id,
            Condition.is_active.is_(True),
            Condition.document_id.in_(document_ids),
        )
        .all()
    )

    grouped: dict[Any, list[Condition]] = {}
    for row in rows:
        grouped.setdefault(row.document_id, []).append(row)
    return grouped


async def get_records(db: Session, pet: Pet) -> dict[str, Any]:
    """
    Return Records V2 payload with vet visits and typed records.

    The async signature is intentional for interface consistency with other
    dashboard-rebuild service entrypoints that are awaited by async routes.
    """
    documents = _fetch_documents(db, pet.id)

    prescription_docs = [
        document
        for document in documents
        if (document.document_category or "").strip().lower() == "prescription"
    ]
    non_prescription_docs = [
        document
        for document in documents
        if (document.document_category or "").strip().lower() != "prescription"
    ]

    condition_map = _fetch_conditions_for_documents(
        db,
        pet.id,
        [document.id for document in prescription_docs],
    )

    vet_visits: list[dict[str, Any]] = []
    for document in sorted(prescription_docs, key=_sort_key_by_event_date, reverse=True):
        style = _style_for_category(document.document_category)
        linked_conditions = condition_map.get(document.id, [])

        vet_visits.append(
            {
                "id": str(document.id),
                "title": document.document_name or "Vet visit",
                "date": document.event_date.isoformat() if document.event_date else None,
                "tag": style["tag"],
                "tag_color": style["tag_color"],
                "tag_bg": style["tag_bg"],
                "key_finding": _extract_visit_key_finding(document, linked_conditions),
                "rx": _extract_rx_summary(document, linked_conditions),
                "medications": _extract_medications(linked_conditions),
                "notes": _extract_notes(linked_conditions),
            }
        )

    records: list[dict[str, Any]] = []
    for document in sorted(non_prescription_docs, key=_sort_key_by_event_date, reverse=True):
        record_type, icon = _record_type_for_document(document)
        style = _style_for_category(document.document_category)
        if record_type == "whatsapp":
            style = _TAG_STYLES["whatsapp"]

        records.append(
            {
                "id": str(document.id),
                "icon": icon,
                "type": record_type,
                "title": document.document_name or "Health record",
                "date": document.event_date.isoformat() if document.event_date else None,
                "tag": style["tag"],
                "tag_color": style["tag_color"],
                "tag_bg": style["tag_bg"],
                "key_finding": _extract_record_key_finding(document, record_type),
            }
        )

    return {"vet_visits": vet_visits, "records": records}
