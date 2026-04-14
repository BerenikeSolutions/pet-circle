"""
PetCircle Phase 1 — Contact Model

Stores vet, groomer, specialist, and other contact information for a pet.
Contacts are extracted from uploaded documents or added manually.

Constraints:
    - pet_id: FK to pets(id), ON DELETE CASCADE
    - document_id: FK to documents(id), ON DELETE SET NULL (optional source doc)
    - role: CHECK IN ('veterinarian', 'groomer', 'trainer', 'specialist', 'other')
    - source: CHECK IN ('extraction', 'manual')
    - Unique constraint: (pet_id, name, role) — deduplicates contacts
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Contact(Base):
    """A contact (vet, groomer, specialist, etc.) associated with a pet."""

    __tablename__ = "contacts"

    __table_args__ = (
        UniqueConstraint("pet_id", "name", "role", name="uq_contacts_pet_name_role"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), index=True, nullable=True)

    role = Column(String(30), nullable=False, default="veterinarian")  # veterinarian | groomer | trainer | specialist | other
    name = Column(String(200), nullable=False)
    clinic_name = Column(String(200), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(200), nullable=True)
    address = Column(String(500), nullable=True)
    source = Column(String(20), nullable=False, default="extraction")  # extraction | manual

    # Denormalized from the source document for display without joins.
    # NULL for manually added contacts.
    source_document_name = Column(String(200), nullable=True)
    source_document_category = Column(String(30), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    pet = relationship("Pet", back_populates="contacts")
    document = relationship("Document")
