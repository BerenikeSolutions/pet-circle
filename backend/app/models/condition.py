"""
PetCircle Phase 1 — Condition Model

Represents a diagnosed condition (chronic, episodic, or resolved) for a pet.
Conditions are extracted from uploaded documents via GPT or added manually
from the dashboard.

Constraints:
    - pet_id: FK to pets(id), ON DELETE CASCADE
    - document_id: FK to documents(id), ON DELETE SET NULL (optional source doc)
    - condition_type: CHECK IN ('chronic', 'episodic', 'resolved')
    - source: CHECK IN ('extraction', 'manual')
    - Unique constraint: (pet_id, name) — prevents duplicate condition names per pet
    - is_active: soft delete flag
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Condition(Base):
    """
    A diagnosed medical condition for a pet.

    condition_type:
        - chronic: ongoing condition requiring long-term management
        - episodic: recurring condition that flares up periodically
        - resolved: condition that has been treated and resolved

    source:
        - extraction: automatically extracted from an uploaded document
        - manual: manually added by the user via dashboard
    """

    __tablename__ = "conditions"

    __table_args__ = (
        UniqueConstraint("pet_id", "name", name="uq_conditions_pet_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), index=True, nullable=True)

    name = Column(String(200), nullable=False)
    diagnosis = Column(String(500), nullable=True)
    condition_type = Column(String(20), nullable=False, default="chronic")  # chronic | episodic | resolved
    condition_status = Column(String(20), nullable=True)  # active | resolved | null (from Health Prompt v2)
    episode_dates = Column(JSONB, nullable=False, default=list)  # sorted list of YYYY-MM-DD strings
    diagnosed_at = Column(Date, nullable=True)
    notes = Column(String(1000), nullable=True)
    icon = Column(String(10), nullable=True)  # Emoji icon for condition display
    managed_by = Column(String(200), nullable=True)  # Managing doctor/vet name and location
    source = Column(String(20), nullable=False, default="extraction")  # extraction | manual
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    pet = relationship("Pet", back_populates="conditions")
    document = relationship("Document")
    medications = relationship("ConditionMedication", back_populates="condition", cascade="all, delete-orphan")
    monitoring = relationship("ConditionMonitoring", back_populates="condition", cascade="all, delete-orphan")
