"""
PetCircle — Dashboard Precompute Service

Pre-warms the pet_ai_insights cache with all enrichments that the dashboard
needs but that are expensive to compute on demand (Anthropic API calls).

Trigger this BEFORE sending the dashboard link to the user so that the first
dashboard load reads entirely from DB with no blocking API calls.

Hook points:
    1. gpt_extraction.extract_and_process_document — after extraction success
    2. message_router._send_dashboard_links — before sending each pet's URL
    3. Any service that changes diet items (diet_service CRUD)

All functions are fire-and-forget (use asyncio.create_task) — failures are
logged but never propagate.
"""

import json
import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# TTLs for each precomputed enrichment stored in pet_ai_insights.
_DIET_SUMMARY_TTL_HOURS = 24
_RECOGNITION_BULLETS_TTL_HOURS = 24
# care_plan_reasons TTL is owned by ai_insights_service (1h) — not overridden here.


def _upsert_insight(db: Session, pet_id: UUID, insight_type: str, content: dict | list) -> None:
    """Persist an enrichment to pet_ai_insights via upsert."""
    try:
        db.execute(
            text("""
                INSERT INTO pet_ai_insights (pet_id, insight_type, content_json, generated_at)
                VALUES (:pet_id, :insight_type, CAST(:content_json AS jsonb), NOW())
                ON CONFLICT (pet_id, insight_type)
                DO UPDATE SET content_json = EXCLUDED.content_json,
                              generated_at = NOW()
            """),
            {
                "pet_id": str(pet_id),
                "insight_type": insight_type,
                "content_json": json.dumps(content),
            },
        )
        db.commit()
    except Exception as exc:
        logger.error("_upsert_insight failed pet=%s type=%s: %s", pet_id, insight_type, exc)
        db.rollback()


async def precompute_dashboard_enrichments(pet_id_str: str) -> None:
    """
    Warm all dashboard enrichments for a pet into the pet_ai_insights cache.

    Runs get_diet_summary, generate_recognition_bullets, and
    generate_care_plan_reasons sequentially — each result is persisted so the
    dashboard endpoint can read from DB without any blocking API calls.

    Args:
        pet_id_str: String UUID of the pet to precompute for.

    Returns:
        None. All failures are logged; the function never raises.
    """
    from app.database import SessionLocal
    from app.models.pet import Pet

    db: Session = SessionLocal()
    diet_summary: dict | None = None

    try:
        pet_id = UUID(pet_id_str)
        pet = db.query(Pet).filter(Pet.id == pet_id).first()
        if not pet:
            logger.warning("precompute_dashboard_enrichments: pet %s not found", pet_id_str)
            return

        logger.info("precompute_dashboard_enrichments: starting for pet=%s", pet_id_str)

        # --- 1. diet_summary (Anthropic-intensive) ---
        try:
            from app.services.nutrition_service import get_diet_summary
            diet_summary = await get_diet_summary(db, pet)
            _upsert_insight(db, pet_id, "diet_summary", diet_summary)
            logger.info("precompute: diet_summary cached for pet=%s", pet_id_str)
        except Exception as exc:
            logger.warning("precompute: diet_summary failed for pet=%s: %s", pet_id_str, exc)
            diet_summary = {"macros": [], "missing_micros": []}

        # --- 2. recognition_bullets (pure DB — fast, but cache to avoid repeated reads) ---
        try:
            from app.services.ai_insights_service import generate_recognition_bullets
            bullets = await generate_recognition_bullets(db, pet)
            _upsert_insight(db, pet_id, "recognition_bullets", bullets)
            logger.info("precompute: recognition_bullets cached for pet=%s", pet_id_str)
        except Exception as exc:
            logger.warning("precompute: recognition_bullets failed for pet=%s: %s", pet_id_str, exc)

        # --- 3. care_plan_reasons (Anthropic, 1h TTL via generate_care_plan_reasons) ---
        try:
            from app.services.care_plan_engine import compute_care_plan
            from app.services.ai_insights_service import generate_care_plan_reasons
            # _normalize_care_plan_shape and _collect_orderable_items are helpers in dashboard_service
            # Import them to avoid duplicating logic.
            from app.services.dashboard_service import (
                _normalize_care_plan_shape,
                _collect_orderable_items,
            )

            care_plan_raw = compute_care_plan(db, pet)
            care_plan = _normalize_care_plan_shape(care_plan_raw)
            orderable_items = _collect_orderable_items(care_plan)

            if orderable_items:
                await generate_care_plan_reasons(
                    db, pet, orderable_items, diet_summary=diet_summary
                )
                logger.info("precompute: care_plan_reasons cached for pet=%s", pet_id_str)
        except Exception as exc:
            logger.warning("precompute: care_plan_reasons failed for pet=%s: %s", pet_id_str, exc)

        logger.info("precompute_dashboard_enrichments: completed for pet=%s", pet_id_str)

    except Exception as exc:
        logger.error("precompute_dashboard_enrichments: fatal error for pet=%s: %s", pet_id_str, exc)
    finally:
        db.close()
