"""
PetCircle Phase 1 — Nudge Config Model

Key-value store for nudge engine configuration.
All rate limits and interval settings are DB-configurable
rather than hardcoded constants.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class NudgeConfig(Base):
    """DB-configurable nudge engine settings (key-value pairs)."""

    __tablename__ = "nudge_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
