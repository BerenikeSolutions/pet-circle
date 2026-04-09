"""
PetCircle Phase 1 — Food Nutrition Cache Model

Caches AI-estimated nutritional content for homemade or unknown foods.
Keyed by (food_label_normalized, food_type) to avoid redundant GPT
calls for the same food item.

Cache staleness: 365 days.
"""

from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from app.database import Base


class FoodNutritionCache(Base):
    """
    Cache table for AI-estimated nutritional content of unknown foods.

    nutrition_json contains per-daily-serving estimates: calories_per_serving,
    protein_pct, fat_pct, fibre_pct, moisture_pct, calcium, phosphorus,
    omega_3_mg, omega_6_mg, vitamin_e_iu, vitamin_d3_iu, glucosamine_mg,
    probiotics.
    """

    __tablename__ = "food_nutrition_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    food_label_normalized = Column(String(200), nullable=False)
    food_type = Column(String(20), nullable=False)
    nutrition_json = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "food_label_normalized", "food_type",
            name="uq_food_nutrition_lookup",
        ),
    )
