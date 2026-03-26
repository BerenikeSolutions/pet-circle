"""
PetCircle Phase 1 — Diet Item Model

Represents a food item or supplement in a pet's daily diet.
Items are classified as packaged food, homemade food, or supplements.

Constraints:
    - pet_id: FK to pets(id), ON DELETE CASCADE
    - type: one of 'packaged', 'homemade', 'supplement'
    - Unique constraint: (pet_id, label, type) — prevents duplicate entries
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class DietItem(Base):
    """
    A single food or supplement item in a pet's diet.

    type:
        - packaged: commercial dog/cat food (kibble, wet food, etc.)
        - homemade: home-cooked meals
        - supplement: vitamins, oils, probiotics, etc.
    """

    __tablename__ = "diet_items"

    __table_args__ = (
        UniqueConstraint("pet_id", "label", "type", name="uq_diet_item"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False)
    type = Column(String(20), nullable=False)  # packaged | homemade | supplement
    icon = Column(String(10), nullable=True)   # emoji icon
    label = Column(String(200), nullable=False)  # e.g. "Royal Canin Golden Retriever Adult"
    detail = Column(String(200), nullable=True)  # e.g. "Dry kibble - 280g x 2/day"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- Food Order Reminder Fields ---
    # Brand name for use in reminder message body.
    brand = Column(String(200), nullable=True)

    # Pack size in grams — used to calculate reorder date: pack_size_g / daily_portion_g = days.
    # Applies to packaged food items.
    pack_size_g = Column(Integer, nullable=True)

    # Daily portion in grams — portion fed per day.
    daily_portion_g = Column(Integer, nullable=True)

    # Date of last confirmed purchase/restock.
    # Set when user taps "Done — Log It" on a Food Order reminder.
    last_purchase_date = Column(Date, nullable=True)

    # --- Supplement Order Reminder Fields ---
    # Units per pack (e.g., 60 capsules per bottle).
    units_in_pack = Column(Integer, nullable=True)

    # Doses per day (e.g., 2 capsules/day).
    doses_per_day = Column(Integer, nullable=True)

    # Fallback flag: set True by nudge_scheduler at O+21 when pack/portion data is missing.
    # Triggers an O+21 generic food/supplement reminder instead of calculated reorder date.
    reminder_order_at_o21 = Column(Boolean, nullable=False, default=False)

    # Relationships
    pet = relationship("Pet")
