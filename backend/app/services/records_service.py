"""
PetCircle Dashboard Rebuild — Records Service

Builds Records V2 payload for the records view:
    - vet_visits: prescription documents enriched with Rx context
    - records: all other successful documents grouped by record type
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models.condition import Condition
from app.models.diagnostic_test_result import DiagnosticTestResult
from app.models.document import Document
from app.models.pet import Pet

_VACCINE_MED_KEYWORDS = ("nobivac", "dhpp", "rabies", "lepto", "bordetella", "fvrcp", "booster", "ccov", "vaccine", "vaccin")

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

# Icon selection by document name keywords
_BLOOD_KEYWORDS = ("blood", "cbc", "cbp", "haemogram", "hemogram", "platelet", "haemo", "hemo")
_URINE_KEYWORDS = ("urine", "urinalysis", "urocult", "urinary")
_SNAP_KEYWORDS = ("snap", "4dx", "pcr", "tick", "anaplasma", "ehrlichia", "heartworm", "lyme", "leishmania")
_CULTURE_KEYWORDS = ("culture", "sensitivity", "c&s", "c/s")

# Lab result classification
_ABNORMAL_FLAGS = frozenset({"low", "high", "abnormal"})
_VECTOR_BORNE_KEYWORDS = ("anaplasma", "ehrlichia", "heartworm", "lyme", "leishmania", "babesia", "toxoplasma")
_CULTURE_POSITIVE_RE = re.compile(r"\b(\+ve|positive|detected|growth)\b", re.IGNORECASE)
_NEAR_CLEAR_RE = re.compile(r"\bnear\s*clear\b", re.IGNORECASE)


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


def _lab_icon_for_document(document: Document) -> str:
    """Select a relevant emoji icon based on the document name keywords."""
    doc_name = (document.document_name or "").lower()
    if any(kw in doc_name for kw in _SNAP_KEYWORDS):
        return "🧬"
    if any(kw in doc_name for kw in _URINE_KEYWORDS) and any(kw in doc_name for kw in _CULTURE_KEYWORDS):
        return "🧫"
    if any(kw in doc_name for kw in _URINE_KEYWORDS):
        return "💧"
    if any(kw in doc_name for kw in _BLOOD_KEYWORDS):
        return "🩸"
    if any(kw in doc_name for kw in _CULTURE_KEYWORDS):
        return "🧫"
    return "🧪"


def _record_type_for_document(document: Document) -> tuple[str, str]:
    """Classify non-prescription document into records-v2 type and icon."""
    category = (document.document_category or "").strip().lower()
    doc_name = (document.document_name or "").strip().lower()

    if category == "diagnostic":
        return "lab_reports", _lab_icon_for_document(document)

    is_imaging = category == "imaging" or any(pattern.search(doc_name) for pattern in _IMAGING_PATTERNS)
    if is_imaging:
        return "imaging", "🩻"

    if document.source_wamid:
        return "whatsapp", "💬"

    return "lab_reports", _lab_icon_for_document(document)


def _is_vaccine_visit(conditions: list[Condition]) -> bool:
    """Return True if any active medication in the visit contains a vaccine keyword."""
    for condition in conditions:
        for medication in condition.medications:
            if (medication.status or "active") != "active":
                continue
            name_lower = (medication.name or "").lower()
            if any(keyword in name_lower for keyword in _VACCINE_MED_KEYWORDS):
                return True
    return False


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


def _extract_visit_key_finding(document: Document, conditions: list[Condition]) -> tuple[str, str, str]:
    """
    Return (finding_text, tag_color, tag_bg) for a vet visit pill.

    Priority:
      1. Diagnosis present  → first diagnosis, amber
      2. Non-vaccine med     → "{med_name} prescribed", amber
      3. No conditions      → "Routine", green
    """
    diagnoses = [
        condition.diagnosis.strip()
        for condition in conditions
        if condition.diagnosis and condition.diagnosis.strip()
    ]
    if diagnoses:
        return diagnoses[0], "#B45309", "#FFF3E0"

    for condition in conditions:
        for medication in condition.medications:
            if (medication.status or "active") != "active":
                continue
            name = (medication.name or "").strip()
            if name:
                return f"{name} prescribed", "#B45309", "#FFF3E0"

    return "Routine", "#166534", "#E9FBEF"


def _extract_lab_key_finding(
    document: Document,
    results: list[DiagnosticTestResult],
) -> tuple[str, str, str]:
    """
    Return (finding_text, tag_color, tag_bg) for a lab/imaging record.

    Priority:
      1. Abnormal numeric results → most significant one, amber or red
      2. Positive culture / PCR text → organism name, red
      3. Near-clear text           → "Near clear", green
      4. All normal                → "All clear", green
      5. No results                → neutral gray
    """
    if not results:
        return "Lab reviewed", "#374151", "#F3F4F6"

    abnormal = [r for r in results if (r.status_flag or "").lower() in _ABNORMAL_FLAGS]

    # Check for positive text results (culture, PCR)
    for result in results:
        text = (result.value_text or "").strip()
        if _CULTURE_POSITIVE_RE.search(text):
            param = result.parameter_name.strip()
            param_lower = param.lower()
            label = f"{param} +ve" if len(param) <= 20 else "+ve detected"
            if any(kw in param_lower for kw in _VECTOR_BORNE_KEYWORDS):
                return label, "#7C3AED", "#F5F3FF"  # purple for vector-borne
            return label, "#DC2626", "#FEE2E2"  # red for infection

    # Near-clear urinalysis
    for result in results:
        text = (result.value_text or "").strip()
        if _NEAR_CLEAR_RE.search(text):
            return "Near clear", "#166534", "#E9FBEF"

    if not abnormal:
        return "All clear", "#166534", "#E9FBEF"

    # Pick most significant abnormal: prefer by known priority params
    _PRIORITY_PARAMS = ("platelet", "haemoglobin", "hemoglobin", "creatinine", "alt", "wbc", "rbc")
    chosen = abnormal[0]
    for result in abnormal:
        param_lower = result.parameter_name.lower()
        if any(p in param_lower for p in _PRIORITY_PARAMS):
            chosen = result
            break

    # Format label
    param_name = chosen.parameter_name.strip()
    if "platelet" in param_name.lower() and chosen.value_numeric is not None:
        val = int(chosen.value_numeric)
        label = f"Platelets {val // 1000}K" if val >= 1000 else f"Platelets {val}"
    elif chosen.value_numeric is not None:
        val_f = float(chosen.value_numeric)
        label = f"{param_name} {val_f:g}"
    else:
        flag = (chosen.status_flag or "").capitalize()
        label = f"{param_name} {flag}".strip()

    flag = (chosen.status_flag or "").lower()
    if flag == "high":
        return label, "#DC2626", "#FEE2E2"
    return label, "#B45309", "#FFF3E0"  # low / abnormal → amber


def _fetch_diagnostic_results_for_documents(
    db: Session,
    pet_id: Any,
    document_ids: list[Any],
) -> dict[Any, list[DiagnosticTestResult]]:
    """Load diagnostic test results keyed by source document id."""
    if not document_ids:
        return {}
    rows = (
        db.query(DiagnosticTestResult)
        .filter(
            DiagnosticTestResult.pet_id == pet_id,
            DiagnosticTestResult.document_id.in_(document_ids),
        )
        .all()
    )
    grouped: dict[Any, list[DiagnosticTestResult]] = {}
    for row in rows:
        grouped.setdefault(row.document_id, []).append(row)
    return grouped


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
    diagnostic_map = _fetch_diagnostic_results_for_documents(
        db,
        pet.id,
        [document.id for document in non_prescription_docs],
    )
    # Load conditions for non-prescription docs to surface notes in record cards
    non_prescription_condition_map = _fetch_conditions_for_documents(
        db,
        pet.id,
        [document.id for document in non_prescription_docs],
    )

    vet_visits: list[dict[str, Any]] = []
    for document in sorted(prescription_docs, key=_sort_key_by_event_date, reverse=True):
        style = _style_for_category(document.document_category)
        linked_conditions = condition_map.get(document.id, [])

        if _is_vaccine_visit(linked_conditions):
            key_finding, tag_color, tag_bg = "Vaccines done", "#166534", "#E9FBEF"
        else:
            key_finding, tag_color, tag_bg = _extract_visit_key_finding(document, linked_conditions)

        vet_visits.append(
            {
                "id": str(document.id),
                "title": document.document_name or "Vet visit",
                "date": document.event_date.isoformat() if document.event_date else None,
                "tag": style["tag"],
                "tag_color": tag_color,
                "tag_bg": tag_bg,
                "key_finding": key_finding,
                "rx": _extract_rx_summary(document, linked_conditions),
                "medications": _extract_medications(linked_conditions),
                "notes": _extract_notes(linked_conditions),
            }
        )

    records: list[dict[str, Any]] = []
    for document in sorted(non_prescription_docs, key=_sort_key_by_event_date, reverse=True):
        record_type, icon = _record_type_for_document(document)
        linked_results = diagnostic_map.get(document.id, [])
        key_finding, tag_color, tag_bg = _extract_lab_key_finding(document, linked_results)

        if record_type == "whatsapp":
            style = _TAG_STYLES["whatsapp"]
            tag_color = style["tag_color"]
            tag_bg = style["tag_bg"]
            key_finding = "Shared on WhatsApp"
        else:
            style = _style_for_category(document.document_category)
            if record_type == "imaging" and not linked_results:
                # Default imaging to "All clear" when no diagnostic results
                pass  # key_finding already set from _extract_lab_key_finding fallback

        # Serialize diagnostic test results for inline expanded view
        def _format_numeric(v: Decimal | None) -> str:
            if v is None:
                return ""
            f = float(v)
            return str(int(f)) if f == int(f) else f"{f:g}"

        serialized_results = [
            {
                "parameter": result.parameter_name,
                "value": _format_numeric(result.value_numeric) if result.value_numeric is not None else (result.value_text or ""),
                "unit": result.unit,
                "range": result.reference_range,
                "flag": result.status_flag,
            }
            for result in linked_results
        ]

        # Notes from any conditions linked to this document
        linked_conditions = non_prescription_condition_map.get(document.id, [])
        notes = _extract_notes(linked_conditions)

        records.append(
            {
                "id": str(document.id),
                "icon": icon,
                "type": record_type,
                "title": document.document_name or "Health record",
                "date": document.event_date.isoformat() if document.event_date else None,
                "tag": style["tag"],
                "tag_color": tag_color,
                "tag_bg": tag_bg,
                "key_finding": key_finding,
                "results": serialized_results,
                "notes": notes,
            }
        )

    return {"vet_visits": vet_visits, "records": records}
