"""
PetCircle — Pet Life Stage Trait Model

Caches GPT-generated life-stage trait payloads for a pet.
Exactly one row is allowed per (pet_id, life_stage).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class PetLifeStageTrait(Base):
    """Cached life-stage traits generated for a pet."""

    __tablename__ = "pet_life_stage_traits"
    __table_args__ = (
        UniqueConstraint("pet_id", "life_stage", name="uq_pet_life_stage_trait_pet_stage"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    life_stage = Column(String(20), nullable=False)
    breed_size = Column(String(20), nullable=False)
    traits = Column(JSONB, nullable=False)
    generated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    pet = relationship("Pet", back_populates="life_stage_traits")
