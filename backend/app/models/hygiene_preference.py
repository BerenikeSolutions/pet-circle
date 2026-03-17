"""
PetCircle Phase 1 — Hygiene Preference Model

Stores grooming/hygiene frequency preferences and reminder settings
for each pet. Items include coat brushing, teeth brushing, ear cleaning,
eye wipes, bath/nail trim, and anal gland cleaning.

Constraints:
    - pet_id: FK to pets(id), ON DELETE CASCADE
    - Unique constraint: (pet_id, item_id) — one preference per hygiene item per pet
    - unit: one of 'day', 'week', 'month', 'year'
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class HygienePreference(Base):
    """
    Grooming/hygiene frequency preference for a single hygiene item.

    item_id identifies the hygiene activity (e.g., 'coat-brush', 'bath-nail').
    freq + unit define the frequency (e.g., freq=1, unit='day' = once daily).
    reminder toggles WhatsApp reminder notifications.
    last_done tracks when the activity was last performed.
    """

    __tablename__ = "hygiene_preferences"

    __table_args__ = (
        UniqueConstraint("pet_id", "item_id", name="uq_hygiene_pref"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False)
    item_id = Column(String(50), nullable=False)  # coat-brush, teeth-brush, etc.
    freq = Column(Integer, nullable=False, default=1)
    unit = Column(String(10), nullable=False, default="month")  # day | week | month | year
    reminder = Column(Boolean, nullable=False, default=False)
    last_done = Column(String(20), nullable=True)  # DD/MM/YYYY or null
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    pet = relationship("Pet")
