"""
PetCircle — Agent Order Session Model

Persists the LLM conversation history and structured extraction snapshot
for a user going through the agentic order flow.

One row per user. The partial unique index in the migration enforces only
one active (is_complete=FALSE) session per user at a time.

IMPORTANT: SQLAlchemy does not auto-detect mutations inside JSONB columns
(list.append, dict.update). Always call flag_modified(session, "messages")
and flag_modified(session, "collected_data") before db.commit() when
modifying these columns in-place.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class AgentOrderSession(Base):
    """
    LLM conversation history and collected data for one agentic order flow run.

    messages:       OpenAI message array appended on each webhook turn.
    collected_data: Structured snapshot written by tool calls; flushed to
                    DB rows atomically when confirm_order fires.
    is_complete:    True once _finalize_agentic_order() succeeds or cancel fires.
    """

    __tablename__ = "agent_order_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # References users.id. No ORM relationship to avoid circular imports.
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # OpenAI message array: [{"role": "...", "content": "..."}]
    messages = Column(JSONB, nullable=False, default=list)

    # Structured extraction snapshot.
    # Schema: {
    #   "pet_id":   str | null,
    #   "category": "medicines" | "food_nutrition" | "supplements" | null,
    #   "items":    [str, ...],
    # }
    collected_data = Column(JSONB, nullable=False, default=dict)

    # True once finalization has run or the user cancelled.
    is_complete = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
