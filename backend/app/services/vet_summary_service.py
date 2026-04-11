"""
PetCircle Phase 1 — Vet Summary Service

Identifies the primary vet contact for a pet by analysing care contacts
extracted from uploaded documents.

Primary vet selection rules:
    1. Only documents in the "Prescription" or "Vaccination" categories are
       considered — diagnostic reports and other document types are excluded
       because they do not reliably indicate the treating vet.
    2. Among eligible documents, the vet name on the single most recent
       document (by event_date, fallback to created_at) is selected.
    3. last_visit is the event_date of that most-recent document.

Returns a VetSummary (name + last_visit date) or None when no eligible
veterinarian contacts exist for the pet.
"""

import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.document import Document

logger = logging.getLogger(__name__)

# Role constant — matches the value stored in contacts.role
ROLE_VETERINARIAN = "veterinarian"

# Only these document categories may supply the primary vet name.
# Diagnostic reports, generic "Other" docs, etc. are deliberately excluded.
ELIGIBLE_CATEGORIES = ("Prescription", "Vaccination")


@dataclass
class VetSummary:
    """Primary vet identified for a pet."""

    name: str
    last_visit: date | None


def get_vet_summary(db: Session, pet_id: UUID) -> VetSummary | None:
    """
    Return the primary vet for *pet_id*, or None if no eligible contacts exist.

    Primary vet = the veterinarian contact linked to the most recent
    "Prescription" or "Vaccination" document for this pet.  Diagnostic
    reports and all other document categories are ignored.

    Ordering: event_date DESC NULLS LAST, then created_at DESC so that
    documents without an explicit event date are ranked below dated ones
    but still participate when no dated documents exist.

    Args:
        db:      Active SQLAlchemy session.
        pet_id:  UUID of the pet to query.

    Returns:
        VetSummary with name and most-recent visit date, or None.
    """
    row = (
        db.query(
            Contact.name,
            Document.event_date.label("last_visit"),
        )
        # INNER JOIN — contact must be linked to a document to be eligible
        .join(Document, Document.id == Contact.document_id)
        .filter(
            Contact.pet_id == pet_id,
            Contact.role == ROLE_VETERINARIAN,
            # Only vet-visit prescriptions and vaccination records count
            Document.document_category.in_(ELIGIBLE_CATEGORIES),
        )
        .order_by(
            # Most recent document first; push null event_dates to the end
            Document.event_date.desc().nullslast(),
            # Secondary sort on upload time for documents with the same event_date
            Document.created_at.desc(),
        )
        .first()
    )

    if row is None:
        return None

    return VetSummary(name=row.name, last_visit=row.last_visit)
