"""
PetCircle Phase 1 — Condition Medication Model

Tracks medications prescribed for a specific condition.
Linked to a condition via condition_id FK.

Constraints:
    - condition_id: FK to conditions(id), ON DELETE CASCADE
    - status: CHECK IN ('active', 'discontinued')
"""

import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class ConditionMedication(Base):
    """A medication prescribed for a condition."""

    __tablename__ = "condition_medications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition_id = Column(UUID(as_uuid=True), ForeignKey("conditions.id", ondelete="CASCADE"), index=True, nullable=False)

    name = Column(String(200), nullable=False)
    dose = Column(String(100), nullable=True)
    frequency = Column(String(100), nullable=True)
    route = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active | discontinued
    started_at = Column(Date, nullable=True)
    notes = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    condition = relationship("Condition", back_populates="medications")
