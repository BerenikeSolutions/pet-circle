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

Performance: all 6 enrichment steps run in parallel via asyncio.gather.
Each step opens its own DB session so concurrent Anthropic API calls cannot
corrupt shared session state. Total wall-clock time drops from ~10–25 s
(sequential) to ~5 s (parallel, bottlenecked by the slowest Anthropic call).
"""

import asyncio
import json
import logging
from datetime import datetime
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

    All six enrichment steps run in parallel via asyncio.gather. Each step
    opens its own DB session to avoid concurrent access on a shared session.
    diet_summary is awaited first because care_plan_reasons depends on it;
    the remaining five steps run concurrently.

    Args:
        pet_id_str: String UUID of the pet to precompute for.

    Returns:
        None. All failures are logged; the function never raises.
    """
    from app.database import SessionLocal
    from app.models.pet import Pet

    # Quick existence check — abort early if pet is gone.
    db_check: Session = SessionLocal()
    try:
        pet_id = UUID(pet_id_str)
        if not db_check.query(Pet).filter(Pet.id == pet_id).first():
            logger.warning("precompute_dashboard_enrichments: pet %s not found", pet_id_str)
            return
    except Exception as exc:
        logger.error("precompute_dashboard_enrichments: setup failed for pet=%s: %s", pet_id_str, exc)
        return
    finally:
        db_check.close()

    logger.info("precompute_dashboard_enrichments: starting for pet=%s", pet_id_str)

    # ------------------------------------------------------------------
    # Helper: each step loads its own Pet + Session so concurrent tasks
    # never share session state.
    # ------------------------------------------------------------------

    async def _run_diet_summary(analysis: dict) -> dict:
        """Reformat a pre-computed nutrition analysis into the diet_summary shape.

        Accepts the already-computed analysis dict from _run_nutrition_analysis so
        analyze_nutrition() is not called a second time.
        """
        db: Session = SessionLocal()
        try:
            pet = db.query(Pet).filter(Pet.id == pet_id).first()
            if not pet:
                return {"macros": [], "missing_micros": []}
            from app.services.nutrition_service import get_diet_summary
            result = await get_diet_summary(db, pet, analysis=analysis)
            _upsert_insight(db, pet_id, "diet_summary", result)
            logger.info("precompute: diet_summary cached for pet=%s", pet_id_str)
            return result
        except Exception as exc:
            logger.warning("precompute: diet_summary failed for pet=%s: %s", pet_id_str, exc)
            return {"macros": [], "missing_micros": []}
        finally:
            db.close()

    async def _run_recognition_bullets() -> None:
        db: Session = SessionLocal()
        try:
            pet = db.query(Pet).filter(Pet.id == pet_id).first()
            if not pet:
                return
            from app.services.ai_insights_service import generate_recognition_bullets
            bullets = await generate_recognition_bullets(db, pet)
            _upsert_insight(db, pet_id, "recognition_bullets", bullets)
            logger.info("precompute: recognition_bullets cached for pet=%s", pet_id_str)
        except Exception as exc:
            logger.warning("precompute: recognition_bullets failed for pet=%s: %s", pet_id_str, exc)
        finally:
            db.close()

    async def _run_nutrition_analysis() -> dict:
        """Compute and cache nutrition_analysis; returns the analysis for reuse by _run_diet_summary."""
        db: Session = SessionLocal()
        try:
            from app.services.nutrition_service import analyze_nutrition
            analysis = await analyze_nutrition(db, pet_id)
            _upsert_insight(db, pet_id, "nutrition_analysis", analysis)
            logger.info("precompute: nutrition_analysis cached for pet=%s", pet_id_str)
            return analysis
        except Exception as exc:
            logger.warning("precompute: nutrition_analysis failed for pet=%s: %s", pet_id_str, exc)
            return {}
        finally:
            db.close()

    async def _run_life_stage() -> None:
        db: Session = SessionLocal()
        try:
            pet = db.query(Pet).filter(Pet.id == pet_id).first()
            if not pet:
                return
            from app.services.life_stage_service import get_life_stage_data
            await get_life_stage_data(db, pet)
            logger.info("precompute: life_stage_insights cached for pet=%s", pet_id_str)
        except Exception as exc:
            logger.warning("precompute: life_stage_insights failed for pet=%s: %s", pet_id_str, exc)
        finally:
            db.close()

    async def _run_health_conditions_v2() -> None:
        db: Session = SessionLocal()
        try:
            from app.models.condition import Condition
            from app.services.ai_insights_service import (
                _aggregate_conditions_for_health_prompt,
                _generate_health_conditions_v2_gpt,
            )
            from sqlalchemy.orm import selectinload

            condition_rows = (
                db.query(Condition)
                .options(
                    selectinload(Condition.medications),
                    selectinload(Condition.monitoring),
                )
                .filter(Condition.pet_id == pet_id, Condition.is_active == True)
                .order_by(Condition.diagnosed_at.asc().nullslast())
                .all()
            )

            conditions_for_prompt = []
            for cond in condition_rows:
                meds = [
                    {"end_date": str(m.end_date) if m.end_date else None}
                    for m in (cond.medications or [])
                ]
                monitoring = [
                    {"recheck_due_date": str(m.recheck_due_date) if m.recheck_due_date else None}
                    for m in (cond.monitoring or [])
                ]
                conditions_for_prompt.append({
                    "name": cond.name,
                    "condition_type": cond.condition_type,
                    "episode_dates": cond.episode_dates or [],
                    "medications": meds,
                    "monitoring": monitoring,
                    "diagnostic_values": [],
                })

            aggregated = _aggregate_conditions_for_health_prompt(conditions_for_prompt)
            result = await _generate_health_conditions_v2_gpt(aggregated, "")
            _upsert_insight(db, pet_id, "health_conditions_v2", result)
            logger.info("precompute: health_conditions_v2 cached for pet=%s", pet_id_str)
        except Exception as exc:
            logger.warning("precompute: health_conditions_v2 failed for pet=%s: %s", pet_id_str, exc)
        finally:
            db.close()

    async def _run_vet_questions() -> None:
        """Pre-warm per-condition ask-vet questions for every active condition.

        Uses the same insight_type key pattern (vet_questions:{condition_id}) and
        condition filter (chronic/episodic) as _get_condition_questions in
        health_trends_service so the health-trends endpoint always hits cache.
        """
        db: Session = SessionLocal()
        try:
            pet = db.query(Pet).filter(Pet.id == pet_id).first()
            if not pet:
                return
            from app.models.condition import Condition
            from app.services.ai_insights_service import get_or_generate_insight
            from sqlalchemy.orm import selectinload

            condition_rows = (
                db.query(Condition)
                .options(
                    selectinload(Condition.medications),
                    selectinload(Condition.monitoring),
                )
                .filter(
                    Condition.pet_id == pet_id,
                    Condition.is_active == True,
                    Condition.condition_type.in_({"chronic", "episodic"}),
                )
                .all()
            )

            if not condition_rows:
                return

            pet_dict = {"name": pet.name, "species": pet.species, "breed": pet.breed}

            async def _warm_one(cond: Condition) -> None:
                condition_payload = {
                    "name": cond.name,
                    "condition_type": cond.condition_type,
                    "medications": [
                        {"name": m.name, "dose": m.dose, "frequency": m.frequency}
                        for m in (cond.medications or [])
                    ],
                    "monitoring": [
                        {
                            "name": m.name,
                            "next_due_date": m.next_due_date.isoformat() if m.next_due_date else None,
                            "last_done_date": m.last_done_date.isoformat() if m.last_done_date else None,
                        }
                        for m in (cond.monitoring or [])
                    ],
                }
                await get_or_generate_insight(
                    db=db,
                    pet_id=pet.id,
                    insight_type=f"vet_questions:{cond.id}",
                    pet=pet_dict,
                    conditions=[condition_payload],
                    health_score={"score": None},
                    force=False,
                )

            # Warm all conditions concurrently — each uses a different insight_type key.
            await asyncio.gather(*[_warm_one(cond) for cond in condition_rows])
            logger.info(
                "precompute: vet_questions cached for pet=%s (%d conditions)",
                pet_id_str, len(condition_rows),
            )
        except Exception as exc:
            logger.warning("precompute: vet_questions failed for pet=%s: %s", pet_id_str, exc)
        finally:
            db.close()

    async def _run_care_plan_reasons(diet_summary: dict) -> None:
        db: Session = SessionLocal()
        try:
            pet = db.query(Pet).filter(Pet.id == pet_id).first()
            if not pet:
                return
            from app.services.care_plan_engine import compute_care_plan
            from app.services.ai_insights_service import generate_care_plan_reasons
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
        finally:
            db.close()

    try:
        # Phase 1: run all independent AI enrichments in parallel.
        # _run_nutrition_analysis returns the analysis dict so Phase 2 can reuse it
        # without a second analyze_nutrition() call.
        analysis, *_ = await asyncio.gather(
            _run_nutrition_analysis(),
            _run_recognition_bullets(),
            _run_life_stage(),
            _run_health_conditions_v2(),
            _run_vet_questions(),
        )

        # Phase 2: diet_summary reformats the already-computed analysis (no AI call).
        diet_summary = await _run_diet_summary(analysis)

        # Phase 3: care_plan_reasons depends on diet_summary.
        await _run_care_plan_reasons(diet_summary)

        logger.info("precompute_dashboard_enrichments: completed for pet=%s", pet_id_str)

    except Exception as exc:
        logger.error("precompute_dashboard_enrichments: fatal error for pet=%s: %s", pet_id_str, exc)
