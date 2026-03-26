"""
PetCircle Phase 1 — Nudge Delivery Log Model

Tracks every WhatsApp nudge delivery attempt for rate limiting
and analytics. Indexed on (user_id, sent_at) for efficient
rate limit queries.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class NudgeDeliveryLog(Base):
    """Log of every nudge sent via WhatsApp."""

    __tablename__ = "nudge_delivery_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # nullable=True — scheduler rows are not linked to a dashboard nudge row.
    nudge_id = Column(UUID(as_uuid=True), ForeignKey("nudges.id", ondelete="CASCADE"), nullable=True)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    wa_status = Column(String(20), nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Nudge level (0/1/2) — used by nudge_scheduler to count completed slots per level.
    nudge_level = Column(Integer, nullable=True)

    # --- Template Message Record (migration 031) ---
    # The WhatsApp template used for this nudge (e.g. 'petcircle_nudge_breed_v1').
    template_name = Column(String(100), nullable=True)

    # Interpolated parameter list — the values substituted into the template.
    template_params = Column(JSONB, nullable=True)

    # Fully rendered message body after substituting template_params into body_text.
    # Exact text the user received on WhatsApp.
    message_body = Column(Text, nullable=True)

    # Relationships
    nudge = relationship("Nudge")
    pet = relationship("Pet")
    user = relationship("User")

    __table_args__ = (
        Index("idx_nudge_delivery_log_user_sent", "user_id", "sent_at"),
        Index("idx_nudge_delivery_log_user_level", "user_id", "nudge_level"),
    )
