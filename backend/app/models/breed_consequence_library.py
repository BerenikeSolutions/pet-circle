"""
PetCircle — Breed Consequence Library Model

Stores breed-specific consequence text used in the Overdue Insight (D+7+)
reminder message:
    "[Pet]'s [item] was due [X] days ago — [consequence_text]."

breed = 'Other' rows serve as a generic fallback for any unlisted breed.
UNIQUE(breed, category) — one consequence per breed+category combination.

Categories match the 8 reminder categories that have Overdue Insight stage:
    vaccine, deworming, flea_tick, food, supplement,
    chronic_medicine, vet_followup, blood_checkup
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class BreedConsequenceLibrary(Base):
    """
    A single breed × category consequence text entry.

    The reminder engine looks up consequence by (breed, category) to fill the
    [consequence_text] variable in the WHATSAPP_TEMPLATE_REMINDER_OVERDUE template.
    Falls back to breed='Other' if no breed-specific row exists.
    """

    __tablename__ = "breed_consequence_library"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Breed name (must match pet.breed exactly) or 'Other' for generic fallback.
    breed = Column(String(100), nullable=False)

    # Reminder category. One of:
    # vaccine | deworming | flea_tick | food | supplement |
    # chronic_medicine | vet_followup | blood_checkup
    category = Column(String(50), nullable=False)

    # Consequence text shown in the overdue insight message.
    # Written as a clause: "Goldens are prone to... — early treatment is critical."
    consequence_text = Column(Text, nullable=False)

    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())

    __table_args__ = (
        UniqueConstraint("breed", "category", name="uq_breed_consequence"),
    )
