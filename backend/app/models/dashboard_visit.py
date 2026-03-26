"""
PetCircle — Dashboard Visit Model

Records every authenticated dashboard token access.

Used by:
    - nudge_scheduler.py: recalculate nudge level on dashboard visit (N8)
    - nudge_scheduler.py: check 48h engagement gap before sending nudge
    - nudge_scheduler.py: Level 2 topic detection (N9) — GPT reads recent visits
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class DashboardVisit(Base):
    """
    A single authenticated dashboard page load.

    Inserted in backend/app/routers/dashboard.py after successful token validation.
    One row per token-authenticated GET request.
    """

    __tablename__ = "dashboard_visits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # The user who owns the dashboard token.
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The pet whose dashboard was visited.
    pet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The token string used (stored for audit; not the secret itself — token is hashed).
    token = Column(String(200), nullable=False)

    # Timestamp of the visit.
    visited_at = Column(String(50), default=lambda: datetime.utcnow().isoformat(), nullable=False)

    # Relationships
    user = relationship("User")
    pet = relationship("Pet")
