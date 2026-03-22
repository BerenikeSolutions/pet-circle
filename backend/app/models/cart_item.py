"""
PetCircle Phase 1 — Cart Item Model

Represents an item in a pet's shopping cart. Cart items are
pre-populated from nudges and product catalog, and users can
toggle items in/out and adjust quantities.

Constraints:
    - pet_id: FK to pets(id), ON DELETE CASCADE
    - Unique constraint: (pet_id, product_id) — one entry per product per pet
    - quantity: minimum 1
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class CartItem(Base):
    """
    A product in a pet's shopping cart.

    product_id maps to cart_item_id in product_catalog (e.g., 'c2', 'c3').
    in_cart indicates whether the item is currently selected for purchase.
    tag/tag_color provide visual urgency indicators (OVERDUE, CRITICAL REFILL, etc.).
    """

    __tablename__ = "cart_items"

    __table_args__ = (
        UniqueConstraint("pet_id", "product_id", name="uq_cart_item"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id = Column(String(100), nullable=False)  # UUID from product_catalog
    icon = Column(String(50), nullable=True)
    name = Column(String(200), nullable=False)
    sub = Column(String(200), nullable=True)
    price = Column(Integer, nullable=False)
    tag = Column(String(100), nullable=True)
    tag_color = Column(String(50), nullable=True)
    in_cart = Column(Boolean, nullable=False, default=False)
    quantity = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    pet = relationship("Pet")
