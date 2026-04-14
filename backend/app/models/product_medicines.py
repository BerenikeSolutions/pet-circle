"""
PetCircle — ProductMedicines Model

Tick, flea, deworming, and antibiotic products for preventive care.
Schema matches migration 051_create_product_medicines.sql and 052_seed_product_medicines.sql.

This table provides a unified, maintainable catalog of all medicines used in the
preventive care system, replacing hardcoded lists in services and routers.

SKU Range: SKU-001 to SKU-054 (54 total products)
- Tick & Flea Protection
- Deworming
- Flea & Deworming (Combined)
- Tick, Flea & Deworming (Combined)
- Antibiotics (Bacterial Infections)
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class ProductMedicines(Base):
    """A medicine SKU in the PetCircle catalog (SKU-001..SKU-054)."""

    __tablename__ = "product_medicines"

    sku_id = Column(String(10), primary_key=True)              # SKU-001, SKU-002, ...
    brand_id = Column(String(10), nullable=False)              # BR-001, BR-002, ...
    brand_name = Column(String(100), nullable=False)
    product_name = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)                 # Tick & Flea, Deworming, Combined, Antibiotic, etc.
    form = Column(String(50), nullable=False)                  # Chewables, Spot-on, Tablets, Syrup, Collar, Spray, etc.
    pack_size = Column(String(100), nullable=False)            # "Box of 1", "3 pipettes", "Strip of 10", etc.
    mrp_paise = Column(Integer, nullable=False)                # MRP in paise (₹ × 100)
    discounted_paise = Column(Integer, nullable=False)         # Discounted price in paise
    key_ingredients = Column(Text, nullable=True)
    condition_tags = Column(Text, nullable=True)               # comma-separated: ticks,fleas,heartworm,roundworm,etc.
    life_stage_tags = Column(Text, nullable=True)              # comma-separated: dog,cat,puppy,adult,senior
    active = Column(Boolean, nullable=False, default=True)
    popularity_rank = Column(Integer, nullable=True)
    monthly_units_sold = Column(Integer, nullable=True)
    price_per_unit_paise = Column(Integer, nullable=True)      # calculated price per unit (in paise)
    in_stock = Column(Boolean, nullable=False, default=True)
    dosage = Column(Text, nullable=True)                       # Dosage instructions
    repeat_frequency = Column(String(100), nullable=True)      # Frequency: Monthly, Every 3 months, Every 12 weeks, etc.
    notes = Column(Text, nullable=True)                        # Special notes, warnings, restrictions
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
