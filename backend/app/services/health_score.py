"""
PetCircle Phase 1 — Health Score Engine (Module 12)

Health score scoring has been removed. This module is retained for import
compatibility only. All callers receive None.
"""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def classify_preventive_item(item_name: str) -> str:
    """Classify a preventive item name. Retained for any external callers."""
    return "checkups"


def compute_health_score(
    db: Session,
    pet_id: UUID,
    *,
    preloaded_preventive: list | None = None,
    preloaded_conditions: list | None = None,
    preloaded_diet_count: int | None = None,
) -> None:
    """Health score scoring has been removed. Returns None."""
    return None
