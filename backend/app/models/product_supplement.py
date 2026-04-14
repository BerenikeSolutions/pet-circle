"""
PetCircle — ProductSupplement Model (cart-rules-engine)

Supplement SKUs for the signal-level cart resolver. Replaces the
supplement/medicine categories of the old monolithic product_catalog
table.

Schema matches migration 044_cart_rules_product_tables.sql.
See .spec/cart-rules-engine/design.md (ADR-1).
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class ProductSupplement(Base):
    """A supplement SKU in the PetCircle catalog (S017..S116)."""

    __tablename__ = "product_supplement"

    sku_id = Column(String(10), primary_key=True)          # S017, S018, ...
    brand_id = Column(String(10), nullable=False)
    brand_name = Column(String(100), nullable=False)
    product_name = Column(String(200), nullable=False)
    type = Column(String(50), nullable=False)              # fish_oil, joint_supplement, ...
    form = Column(String(30), nullable=False)              # liquid, chew, powder, paste, tablet
    pack_size = Column(String(50), nullable=False)         # "300 ml", "90 chews", ...
    mrp = Column(Integer, nullable=False)                  # Rs.
    discounted_price = Column(Integer, nullable=False)     # Rs.
    key_ingredients = Column(Text, nullable=True)
    condition_tags = Column(Text, nullable=True)           # comma-separated
    life_stage_tags = Column(Text, nullable=True)          # comma-separated
    active = Column(Boolean, nullable=False, default=True)
    popularity_rank = Column(Integer, nullable=False)
    monthly_units = Column(Integer, nullable=True)
    price_per_unit = Column(Integer, nullable=True)        # Rs.
    in_stock = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
