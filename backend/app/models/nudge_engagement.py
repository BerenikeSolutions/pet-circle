"""
PetCircle Phase 1 — Nudge Engagement Model

Tracks per-user per-pet nudge engagement stats for smart
throttling. Used to pause nudges for unresponsive users and
track action rates.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class NudgeEngagement(Base):
    """Per-user per-pet nudge engagement tracking."""

    __tablename__ = "nudge_engagement"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False)
    last_engagement_at = Column(DateTime, nullable=True)
    paused_until = Column(DateTime, nullable=True)
    total_nudges_sent = Column(Integer, default=0)
    total_acted_on = Column(Integer, default=0)

    # Relationships
    user = relationship("User")
    pet = relationship("Pet")

    __table_args__ = (
        UniqueConstraint("user_id", "pet_id", name="uq_nudge_engagement_user_pet"),
    )
