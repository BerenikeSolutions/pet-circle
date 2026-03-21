"""
PetCircle Phase 1 — Hygiene Tip Cache Model

Caches AI-generated one-line reasons (tips) explaining why a hygiene
activity matters for a specific species + breed combination.

Cache key: (species, breed_normalized, item_id).
Shared across all pets of the same breed — no pet_id FK.
Cache staleness: 365 days (same pattern as nutrition caches).
"""

from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP

from app.database import Base


class HygieneTipCache(Base):
    """
    Cache table for OpenAI-generated hygiene activity tips.

    Stores a short one-line reason explaining why a specific hygiene
    activity is important for a given species + breed combo.

    Example:
        species='dog', breed='golden retriever', item_id='coat-brush'
        → tip='Golden Retrievers have a dense double coat that sheds
               heavily and mats without regular brushing.'
    """

    __tablename__ = "hygiene_tip_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    species = Column(String(10), nullable=False)
    breed_normalized = Column(String(100), nullable=False)
    item_id = Column(String(50), nullable=False)
    tip = Column(String(300), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "species", "breed_normalized", "item_id",
            name="uq_hygiene_tip_lookup",
        ),
    )
