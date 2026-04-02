"""
PetCircle Phase 1 — Vet Summary Service

Identifies the primary vet contact for a pet by analysing care contacts
extracted from uploaded documents.

Primary vet selection rules:
    1. Count distinct document references per vet name (mention count).
    2. Vet with the highest mention count is selected as primary.
    3. Tie-break: vet with the most recent document event_date wins.
    4. If event_dates are also tied, result is non-deterministic (acceptable
       for Phase 1 — no clinical impact).

Returns a VetSummary (name + last_visit date) or None when no veterinarian
contacts exist for the pet.
"""

import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.document import Document

logger = logging.getLogger(__name__)

# Role constant — matches the value stored in contacts.role
ROLE_VETERINARIAN = "veterinarian"


@dataclass
class VetSummary:
    """Primary vet identified for a pet."""

    name: str
    last_visit: date | None


def get_vet_summary(db: Session, pet_id: UUID) -> VetSummary | None:
    """
    Return the primary vet for *pet_id*, or None if no vet contacts exist.

    Primary vet = the vet name that appears across the greatest number of
    distinct uploaded documents.  Tie-break: the vet associated with the
    most recent document event_date wins.

    The query performs a single aggregation pass:
      - LEFT JOIN documents so that contacts whose document was deleted (SET
        NULL) are included in the mention count but contribute NULL to the
        date aggregation.
      - GROUP BY contact name, then order by mention_count DESC, last_visit
        DESC NULLS LAST so the desired candidate is always rows[0].

    Args:
        db:      Active SQLAlchemy session.
        pet_id:  UUID of the pet to query.

    Returns:
        VetSummary with name and most-recent visit date, or None.
    """
    rows = (
        db.query(
            Contact.name,
            func.count(Contact.document_id.distinct()).label("mention_count"),
            func.max(Document.event_date).label("last_visit"),
        )
        .outerjoin(Document, Document.id == Contact.document_id)
        .filter(
            Contact.pet_id == pet_id,
            Contact.role == ROLE_VETERINARIAN,
        )
        .group_by(Contact.name)
        .order_by(
            # Most-mentioned vet first
            func.count(Contact.document_id.distinct()).desc(),
            # Tie-break: newest event_date first; NULLs pushed to end
            func.max(Document.event_date).desc().nullslast(),
        )
        .all()
    )

    if not rows:
        return None

    top = rows[0]
    return VetSummary(name=top.name, last_visit=top.last_visit)
