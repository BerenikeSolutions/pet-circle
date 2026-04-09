"""
PetCircle — ProductFood Model (cart-rules-engine)

Food SKUs for the signal-level cart resolver. Replaces the food
category of the old monolithic product_catalog table.

Schema matches migration 044_cart_rules_product_tables.sql.
See .spec/cart-rules-engine/design.md (ADR-1) for the rationale
behind splitting food and supplements into separate tables.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, Text

from app.database import Base


class ProductFood(Base):
    """A food SKU in the PetCircle catalog (F001..F025)."""

    __tablename__ = "product_food"

    sku_id = Column(String(10), primary_key=True)          # F001, F002, ...
    brand_id = Column(String(10), nullable=False)          # BR01, BR02, ...
    brand_name = Column(String(100), nullable=False)
    product_line = Column(String(200), nullable=False)
    life_stage = Column(String(20), nullable=False)        # Puppy, Adult, Senior, All
    breed_size = Column(String(20), nullable=False)        # Small, Medium, Large, All
    pack_size_kg = Column(Numeric(5, 1), nullable=False)
    mrp = Column(Integer, nullable=False)                  # Rs.
    discounted_price = Column(Integer, nullable=False)     # Rs.
    condition_tags = Column(Text, nullable=True)           # comma-separated
    breed_tags = Column(Text, nullable=True)               # comma-separated
    vet_diet_flag = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True)
    popularity_rank = Column(Integer, nullable=False)
    monthly_units_sold = Column(Integer, nullable=True)
    price_per_kg = Column(Integer, nullable=True)          # Rs.
    in_stock = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
