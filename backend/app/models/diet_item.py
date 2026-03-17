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
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
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

    # Relationships
    pet = relationship("Pet")
