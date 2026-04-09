"""
PetCircle Phase 1 — Cart Item Model

Represents an item in a pet's shopping cart. Cart items are
pre-populated from nudges and the product catalog (product_food /
product_supplement), and users can toggle items in/out and adjust
quantities.

Constraints:
    - pet_id: FK to pets(id), ON DELETE CASCADE
    - Unique constraint: (pet_id, product_id) — one entry per product per pet
    - quantity: minimum 1
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class CartItem(Base):
    """
    A product in a pet's shopping cart.

    product_id stores the sku_id of a ProductFood (F###) or
    ProductSupplement (S###) row. The prefix determines which
    table to look up.
    in_cart indicates whether the item is currently selected for purchase.
    tag/tag_color provide visual urgency indicators (OVERDUE, CRITICAL REFILL, etc.).
    """

    __tablename__ = "cart_items"

    __table_args__ = (
        UniqueConstraint("pet_id", "product_id", name="uq_cart_item"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id = Column(String(100), nullable=False)  # sku_id from product_food/product_supplement
    icon = Column(String(50), nullable=True)
    name = Column(String(200), nullable=False)
    sub = Column(String(200), nullable=True)
    price = Column(Integer, nullable=False)
    tag = Column(String(100), nullable=True)
    tag_color = Column(String(50), nullable=True)
    in_cart = Column(Boolean, nullable=False, default=False)
    quantity = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # C6: Cart persists for 72 hours. NULL means no expiry (legacy rows).
    cart_expires_at = Column(DateTime, nullable=True)

    # Relationships
    pet = relationship("Pet")
