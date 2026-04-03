"""
PetCircle Phase 1 — Deferred Care Plan Pending Marker

Tracks per-pet deferred onboarding finalization when uploaded document
extractions are still pending. This replaces user-level deferred flags so
concurrent onboarding for multiple pets under one user cannot interfere.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class DeferredCarePlanPending(Base):
    """Persistent per-pet marker for deferred care-plan finalization."""

    __tablename__ = "deferred_care_plan_pending"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False)
    reason = Column(String(64), nullable=False, default="pending_extractions")
    is_cleared = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cleared_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_deferred_care_plan_pending_pet", "pet_id"),
        Index("ix_deferred_care_plan_pending_user", "user_id"),
        Index("ix_deferred_care_plan_pending_uncleared", "is_cleared", "pet_id"),
    )

    user = relationship("User")
    pet = relationship("Pet")
