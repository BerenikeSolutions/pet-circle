"""
PetCircle — Nudge Message Library Model

Central library of WhatsApp nudge message content for the nudge_scheduler.
Stores template variable content per user level, slot, message type, and breed.

Level definitions:
    0 — Cold Start (no breed, no health data)
    1 — Breed available, no health records
    2 — Breed + at least one preventive_record row

Message types:
    value_add       — generic pet care tip (Level 0 / Level 1 non-breed slots)
    engagement_only — breed-specific fun fact + engagement CTA (Level 1)
    breed_only      — breed-specific preventive care insight (Level 1 O+30)
    breed_data      — breed + data completion nudge (Level 2 slots 1–3)

Template mapping (scheduler fills pet_name from DB at send time):
    value_add       → WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL
                      {{1}} = pet_name, {{2}} = template_var_1 (tip text)
    engagement_only → WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT
                      {{1}} = template_var_1, {{2}} = template_var_2
    breed_only      → WHATSAPP_TEMPLATE_NUDGE_BREED
                      {{1}} = template_var_1, {{2}} = template_var_2
    breed_data      → WHATSAPP_TEMPLATE_NUDGE_BREED_DATA
                      {{1}} = template_var_1, {{2}} = pet_name,
                      {{3}} = template_var_3, {{4}} = template_var_4
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class NudgeMessageLibrary(Base):
    """
    A single nudge message template entry in the library.

    The UNIQUE constraint on (level, slot_day, seq, message_type, breed) ensures
    each slot has a deterministic message when breed matches. The scheduler
    selects by level + message_type + breed, ordered by seq, to cycle through
    available messages.
    """

    __tablename__ = "nudge_message_library"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User engagement level — 0, 1, or 2.
    level = Column(Integer, nullable=False)

    # O+N slot day — 1, 5, 10, 20, 30, or 0 (post-30 cycling).
    slot_day = Column(Integer, nullable=False, default=0)

    # Sequence within same level+slot_day+message_type+breed.
    # Used to cycle messages when multiple are available for the same slot.
    seq = Column(Integer, nullable=False, default=1)

    # Message type — determines which WA template is used.
    # value_add | engagement_only | breed_only | breed_data
    message_type = Column(String(30), nullable=False)

    # Breed specificity. 'All' = applies to any breed (fallback).
    # Named breed = used when pet.breed matches exactly.
    breed = Column(String(100), nullable=False, default="All")

    # Data category for Level 2 breed_data messages (maps to NUDGE_L2_DATA_PRIORITY).
    # NULL for Level 0/1 messages.
    category = Column(String(50), nullable=True)

    # WhatsApp template environment variable name.
    # e.g. 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT'
    template_key = Column(String(100), nullable=False)

    # Template variable content (mapped to WA {{1}}–{{4}} at send time).
    # See module docstring for per-type mappings.
    template_var_1 = Column(Text, nullable=True)
    template_var_2 = Column(Text, nullable=True)
    template_var_3 = Column(Text, nullable=True)
    template_var_4 = Column(Text, nullable=True)

    # Optional internal notes for content review.
    notes = Column(Text, nullable=True)

    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())

    __table_args__ = (
        UniqueConstraint(
            "level", "slot_day", "seq", "message_type", "breed",
            name="uq_nudge_library_slot"
        ),
    )
