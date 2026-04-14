"""
PetCircle Phase 1 — Condition Monitoring Model

Tracks monitoring/follow-up checks for a specific condition
(e.g., "Blood Work every 6 months", "Vet Visit quarterly").

Constraints:
    - condition_id: FK to conditions(id), ON DELETE CASCADE
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ConditionMonitoring(Base):
    """A monitoring check scheduled for a condition."""

    __tablename__ = "condition_monitoring"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition_id = Column(UUID(as_uuid=True), ForeignKey("conditions.id", ondelete="CASCADE"), index=True, nullable=False)

    name = Column(String(200), nullable=False)
    frequency = Column(String(100), nullable=True)
    next_due_date = Column(Date, nullable=True)  # When next check is due
    recheck_due_date = Column(Date, nullable=True)  # Explicit follow-up date from prescription
    last_done_date = Column(Date, nullable=True)  # When last performed
    result_summary = Column(String(200), nullable=True)  # Short finding from last check

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    condition = relationship("Condition", back_populates="monitoring")
