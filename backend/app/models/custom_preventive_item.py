"""
PetCircle Phase 1 — Custom Preventive Item Model

User-scoped preventive items (medicines, supplements, vaccines) that are NOT
part of the frozen preventive_master table. Each custom item belongs to a
specific user and is visible only to that user's pets.

The preventive_master table remains frozen and shared across all users.
Custom items mirror the same fields so preventive_records can reference
either source interchangeably.

Constraints:
    - user_id: FK to users(id), ON DELETE CASCADE
    - category: CHECK IN ('essential', 'complete')
    - circle: CHECK IN ('health', 'nutrition', 'hygiene')
    - species: CHECK IN ('dog', 'cat', 'both')
    - UNIQUE(user_id, item_name, species) — no duplicate custom items per user per species
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class CustomPreventiveItem(Base):
    """
    User-specific preventive item that supplements the frozen preventive_master.

    When a user adds a custom medicine, supplement, or vaccine, it is stored
    here — never in preventive_master. Preventive records can reference
    either preventive_master_id OR custom_preventive_item_id (exactly one).
    """

    __tablename__ = "custom_preventive_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Owner — scopes this item to a single user.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Name of the custom preventive item (e.g., "Heartgard Plus", "Fish Oil").
    item_name = Column(String(120), nullable=False)

    # 'essential' or 'complete' — UI classification matching preventive_master.
    # 'essential' = mandatory, 'complete' = recommended. Not used for health score weighting.
    category = Column(String(20), nullable=False, server_default="complete")

    # Dashboard ring grouping: 'health', 'nutrition', or 'hygiene'.
    circle = Column(String(20), nullable=False, server_default="health")

    # Species this item applies to: 'dog', 'cat', or 'both'.
    species = Column(String(10), nullable=False)

    # Days between occurrences.
    recurrence_days = Column(Integer, nullable=False)

    # Whether recurrence depends on the specific medicine/product used.
    medicine_dependent = Column(Boolean, default=False)

    # Days before next_due_date to send first reminder.
    reminder_before_days = Column(Integer, nullable=False, server_default="7")

    # Days after next_due_date before marking as overdue.
    overdue_after_days = Column(Integer, nullable=False, server_default="7")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "item_name", "species", name="uq_custom_preventive_user_item_species"),
    )

    # Relationships
    user = relationship("User", back_populates="custom_preventive_items")
    preventive_records = relationship("PreventiveRecord", back_populates="custom_preventive_item")
