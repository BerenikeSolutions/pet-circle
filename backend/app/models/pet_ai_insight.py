"""
PetCircle Phase 1 — Pet AI Insight Model

Caches GPT-generated insights per pet so we don't call the API on every
dashboard load. Each (pet_id, insight_type) pair has at most one row;
re-generation uses upsert (ON CONFLICT DO UPDATE).

insight_type values:
    'health_summary'        — 1-2 sentence plain-text health insight (Conditions tab).
    'vet_questions'         — JSON list of prioritised questions for the vet visit.
    'diet_summary'          — Aggregated nutrition breakdown (Nutrition tab). Precomputed
                              by precompute_service before the dashboard link is sent.
    'recognition_bullets'   — "What We Found" bullets (Overview tab). Precomputed by
                              precompute_service; pure DB, no API calls.
    'care_plan_reasons'     — Map of item_id → reason sentence for orderable care plan
                              items. Precomputed by precompute_service; 1h TTL.
    'nutrition_importance'  — 3-4 sentence nutrition note (Nutrition tab). 30-day TTL.

content_json schema by insight_type:
    health_summary        : {"summary": "<string>"}
    vet_questions         : [{"priority": "urgent|high|medium", "icon": "<emoji>",
                              "q": "<question>", "context": "<explanation>"}, ...]
    diet_summary          : {"macros": [...], "missing_micros": [...], ...}
    recognition_bullets   : [{"icon": "<emoji>", "label": "<string>"}, ...]
    care_plan_reasons     : {"reasons": {"<item_id>": "<sentence>", ...}}
    nutrition_importance  : {"note": "<string>"}
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class PetAiInsight(Base):
    """Cached GPT-generated insight for a pet."""

    __tablename__ = "pet_ai_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    insight_type = Column(String(50), nullable=False)       # health_summary | vet_questions
    content_json = Column(JSONB, nullable=False)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
