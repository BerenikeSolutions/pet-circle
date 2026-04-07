"""
PetCircle Phase 1 — Weight History Model

Tracks weight measurements over time for a pet. Each entry records
the weight in kg, the date it was measured, and an optional note.

Constraints:
    - pet_id: FK to pets(id), ON DELETE CASCADE
    - weight: DECIMAL(5,2) — supports up to 999.99 kg
    - recorded_at: DATE — when the measurement was taken
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class WeightHistory(Base):
    """
    A single weight measurement for a pet.

    Used to display weight trends on the Health tab and detect
    significant weight changes that may indicate health issues.
    """

    __tablename__ = "weight_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False)
    weight = Column(Numeric(5, 2), nullable=False)  # kg, max 999.99
    recorded_at = Column(Date, nullable=False)
    bcs = Column(SmallInteger, nullable=True)  # Body Condition Score 1-9
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    pet = relationship("Pet")
