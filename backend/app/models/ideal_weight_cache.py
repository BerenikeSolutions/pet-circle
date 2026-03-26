"""
PetCircle Phase 1 — Ideal Weight Cache Model

Caches AI-generated ideal weight ranges per (species, breed, gender, age_category).
Shared across all pets of the same breed combo — no pet_id FK.
"""

from sqlalchemy import DECIMAL, Column, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from app.database import Base


class IdealWeightCache(Base):
    """
    Cache table for OpenAI-generated breed-specific ideal weight ranges.

    Keyed by (species, breed_normalized, gender, age_category) so identical
    breed combos share one cache entry across all pets.
    """

    __tablename__ = "ideal_weight_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    species = Column(String(10), nullable=False)
    breed_normalized = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=False)
    age_category = Column(String(20), nullable=False)
    min_weight = Column(DECIMAL(5, 2), nullable=False)
    max_weight = Column(DECIMAL(5, 2), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "species", "breed_normalized", "gender", "age_category",
            name="uq_ideal_weight_lookup",
        ),
    )
