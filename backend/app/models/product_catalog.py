"""
PetCircle Phase 1 — Product Catalog Model

Stores the complete product catalog imported from the nutrition Excel database.
Covers food products, deworming medicines, flea & tick products, and disease medicines.

Categories:
    - food: Dog/cat food with full nutritional breakdown
    - deworming: Deworming medications with dosage info
    - flea_tick: Flea and tick prevention products
    - medicine: Disease-specific medications
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ProductCatalog(Base):
    """
    A product in the PetCircle catalog.

    Nutritional columns (crude_protein, crude_fat, etc.) are populated
    for food items. Medicine-specific columns (active_ingredient, dosage,
    etc.) are populated for deworming, flea_tick, and medicine items.

    cart_item_id maps to the CartItem product_id for ordering integration.
    """

    __tablename__ = "product_catalog"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(30), nullable=False, index=True)  # food, deworming, flea_tick, medicine
    brand = Column(String(100), nullable=False)
    product_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Nutritional data (food items)
    crude_protein = Column(Numeric(5, 2), nullable=True)
    crude_fat = Column(Numeric(5, 2), nullable=True)
    crude_fibre = Column(Numeric(5, 2), nullable=True)
    moisture = Column(Numeric(5, 2), nullable=True)
    ash = Column(Numeric(5, 2), nullable=True)
    calcium = Column(Numeric(5, 3), nullable=True)
    phosphorus = Column(Numeric(5, 3), nullable=True)
    omega_3 = Column(Integer, nullable=True)       # mg/kg
    omega_6 = Column(Integer, nullable=True)       # mg/kg
    vitamin_e = Column(Integer, nullable=True)     # IU/kg
    vitamin_d3 = Column(Integer, nullable=True)    # IU/kg
    glucosamine = Column(Integer, nullable=True)   # mg/kg
    probiotics = Column(String(30), nullable=True) # CFU/g as string
    energy_kcal = Column(Integer, nullable=True)   # kcal/kg

    # Medicine-specific
    active_ingredient = Column(Text, nullable=True)
    indication = Column(Text, nullable=True)
    dosage = Column(Text, nullable=True)
    frequency = Column(String(200), nullable=True)
    formulation = Column(String(50), nullable=True)
    prescription_required = Column(Boolean, nullable=True)

    # Common
    life_stage = Column(String(50), nullable=True)
    breed_size = Column(String(50), nullable=True)
    type = Column(String(50), nullable=True)       # Dry Kibble, Chewable Tablet, etc.
    pack_size = Column(String(100), nullable=True)
    mrp = Column(String(100), nullable=True)       # e.g. "Rs.1,499 / Rs.4,599"
    notes = Column(Text, nullable=True)
    cart_item_id = Column(String(10), nullable=True)  # c2, c3, etc. for cart mapping

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
