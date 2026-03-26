"""
PetCircle Phase 1 — Hygiene Preference Model

Stores grooming/hygiene frequency preferences and reminder settings
for each pet. Includes both default items (seeded on first access) and
custom user-added items.

Constraints:
    - pet_id: FK to pets(id), ON DELETE CASCADE
    - Unique constraint: (pet_id, item_id) — one preference per hygiene item per pet
    - unit: one of 'day', 'week', 'month', 'year'
    - category: 'daily' or 'periodic'
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class HygienePreference(Base):
    """
    Grooming/hygiene frequency preference for a single hygiene item.

    item_id identifies the hygiene activity (e.g., 'coat-brush', 'bath-nail', or custom slug).
    name is the display name (e.g., 'Coat Brushing', or user-typed custom name).
    icon is an emoji icon for display.
    category is 'daily' or 'periodic' to determine which section it appears in.
    is_default distinguishes seeded defaults from user-added custom items.
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
    item_id = Column(String(50), nullable=False)  # coat-brush, teeth-brush, or custom slug
    name = Column(String(100), nullable=True)  # Display name
    icon = Column(String(10), nullable=True, default="🧹")  # Emoji icon
    category = Column(String(20), nullable=True, default="daily")  # 'daily' or 'periodic'
    is_default = Column(Boolean, nullable=False, default=False)  # True for seeded defaults
    freq = Column(Integer, nullable=False, default=1)
    unit = Column(String(10), nullable=False, default="month")  # day | week | month | year
    reminder = Column(Boolean, nullable=False, default=False)
    last_done = Column(String(20), nullable=True)  # DD/MM/YYYY or null
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    pet = relationship("Pet")
