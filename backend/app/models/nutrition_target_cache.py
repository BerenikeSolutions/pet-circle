"""
PetCircle Phase 1 — Nutrition Target Cache Model

Caches AI-generated breed-specific daily nutrition targets per
(species, breed_normalized, age_category). Shared across all pets
of the same breed combo — no pet_id FK.

Cache staleness: 365 days (same as ideal weight cache).
"""

from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from app.database import Base


class NutritionTargetCache(Base):
    """
    Cache table for OpenAI-generated breed-specific nutrition targets.

    Keyed by (species, breed_normalized, age_category) so identical
    breed combos share one cache entry across all pets.

    targets_json contains: calories, protein, fat, carbs, fibre, moisture,
    calcium, phosphorus, omega_3, omega_6, vitamin_e, vitamin_d3,
    glucosamine, probiotics.
    """

    __tablename__ = "nutrition_target_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    species = Column(String(10), nullable=False)
    breed_normalized = Column(String(100), nullable=False)
    age_category = Column(String(20), nullable=False)
    targets_json = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "species", "breed_normalized", "age_category",
            name="uq_nutrition_target_lookup",
        ),
    )
