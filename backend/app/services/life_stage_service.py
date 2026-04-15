"""
PetCircle Dashboard Rebuild — Life Stage Service

Computes life stage metadata for a pet and returns stage-specific traits.
Trait payloads are generated via GPT and cached in pet_life_stage_traits.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import OPENAI_QUERY_MODEL
from app.models.pet import Pet
from app.models.pet_life_stage_trait import PetLifeStageTrait
from app.services.care_plan_engine import (
    BREED_SIZE_BOUNDARIES,
    _get_breed_size,
    _get_life_stage,
    _get_pet_age_months,
)
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

_ALLOWED_TRAIT_COLORS = {"orange", "green", "neutral"}
_MAX_TRAITS = 3
_openai_client = None


@dataclass
class LifeStageData:
    """Life stage payload returned to dashboard service."""

    stage: str
    age_months: int
    breed_size: str
    stage_boundaries: dict[str, int]
    insights: list[dict[str, str]]


@dataclass
class _LifeStageTraitsPayload:
    """Internal normalized GPT payload for persistence/response."""

    insights: list[dict[str, str]]


def _get_openai_client():
    """Lazy-initialise AI client (provider-agnostic)."""
    global _openai_client
    if _openai_client is None:
        from app.utils.ai_client import get_ai_client  # noqa: PLC0415
        _openai_client = get_ai_client()
    return _openai_client


def _coerce_traits_payload(raw_payload: Any) -> _LifeStageTraitsPayload:
    """Validate and clamp model output to the expected response contract."""
    insights: list[dict[str, str]] = []

    # Accept either top-level list under "lifeStage.insights" or flat "insights".
    if isinstance(raw_payload, dict):
        life_stage_obj = raw_payload.get("lifeStage")
        if isinstance(life_stage_obj, dict):
            raw_insights = life_stage_obj.get("insights")
        else:
            raw_insights = raw_payload.get("insights")
    else:
        raw_insights = None

    if isinstance(raw_insights, list):
        for item in raw_insights:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            color = str(item.get("color", "")).strip().lower()
            if not text or color not in _ALLOWED_TRAIT_COLORS:
                continue
            # Enforce max-12-word contract at parse time.
            words = text.split()
            if len(words) > 12:
                text = " ".join(words[:12])
            insights.append({"text": text, "color": color})
            if len(insights) >= _MAX_TRAITS:
                break

    return _LifeStageTraitsPayload(insights=insights)


async def _generate_life_stage_traits_gpt(
    breed: str,
    age_months: int,
    stage: str,
) -> _LifeStageTraitsPayload:
    """Generate stage-specific traits from GPT and normalize the response."""
    client = _get_openai_client()
    safe_breed = (breed or "mixed breed").strip()

    system_prompt = (
        "You generate breed- and life-stage-specific health insights for a pet dashboard.\n"
        "Return ONLY a valid JSON object matching this exact schema:\n"
        '{"lifeStage": {"insights": [{"text": "...", "color": "orange"|"green"|"neutral"}]}}\n\n'
        "LIFE STAGE DETERMINATION:\n"
        "Before determining life stage, estimate age-to-life-stage mapping using "
        "breed-specific thresholds — large and giant breeds are considered senior "
        "earlier (6–7 years) than small breeds (10–11 years).\n\n"
        "STRICT INPUT CONSTRAINT:\n"
        "Use ONLY the following inputs:\n"
        "  - Breed\n"
        "  - Age (or derived life stage)\n"
        "Do NOT use or infer:\n"
        "  - Existing health conditions\n"
        "  - Symptoms\n"
        "  - Weight or activity level\n"
        "  - Medical history\n"
        "  - Any external or assumed data beyond breed and age\n"
        "All insights must be derived purely from typical life stage progression for this breed.\n\n"
        "DO NOT include:\n"
        "  - Normal aging observations (energy, metabolism, appetite, vision decline)\n"
        "  - Supplement or nutrition recommendations (handled separately)\n"
        "  - Generic advice applicable to all dogs\n\n"
        "Two types of insights allowed:\n"
        "  (A) HOME WATCH-OUTS — things the parent can observe: changes in gait, "
        "breathing patterns, weight shifts, behavioural changes. "
        "Frame as: what to look for and what it might signal.\n"
        "  (B) VET SCREENINGS — for conditions not observable at home but this breed "
        "is predisposed to: cardiac checks, thyroid panels, eye screenings etc. "
        "Frame as: what to screen for and why it's relevant at this age/breed.\n\n"
        "ORDERING RULE (MANDATORY):\n"
        "Do NOT rank purely by clinical importance.\n"
        "Structure insights in this exact order:\n"
        "  1. First insight: A positive or reassuring life-stage observation (green)\n"
        "  2. Second insight: A mild or early watch-out (orange or neutral)\n"
        "  3. Third insight: A more serious or long-term risk (orange)\n"
        "This ordering must always be followed, even if clinical importance differs.\n"
        "If two insights are of equal clinical weight, prefer the one more specific to the breed.\n"
        "Mix home watch-outs and vet screenings based on what is most relevant — do not force a fixed ratio.\n\n"
        "FRAMING:\n"
        "Avoid naming specific diseases unless absolutely necessary. "
        "Prefer observable patterns or functional changes over diagnostic labels. "
        "Keep language calm, specific, and non-generic. "
        "Frame insights as part of a natural life-stage progression, not isolated risks. "
        "Avoid alarmist or clinical tone. "
        "Do not label insights as 'home' or 'vet' in the output.\n\n"
        "FORMAT:\n"
        "Each text is ONE complete sentence, maximum 12 words. "
        "No markdown, no explanation, no preamble.\n\n"
        "COLOR ASSIGNMENT:\n"
        "  orange — watch-out or early warning the parent should actively monitor\n"
        "  green  — positive milestone or condition being managed well at this stage\n"
        "  neutral — vet screening indicated but not urgent\n\n"
        "RULES:\n"
        "  - Maximum 3 insights — prioritise ruthlessly\n"
        "  - Every insight must be breed- and age-specific\n"
        "  - Each text is one complete sentence, maximum 12 words\n"
        "  - No supplements or diet recommendations\n"
    )

    user_prompt = (
        f"Breed: {safe_breed}\n"
        f"Age months: {age_months}\n"
        f"Life stage: {stage}\n"
    )

    async def _call() -> str:
        response = await client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=700,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.content[0].text or "{}"

    raw = await retry_openai_call(_call)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        parsed = json.loads(cleaned)
    except Exception as exc:
        logger.warning("Life stage trait parse failed: %s | raw=%s", exc, raw)
        return _LifeStageTraitsPayload(insights=[])

    return _coerce_traits_payload(parsed)




async def get_life_stage_data(db: Session, pet: Pet) -> LifeStageData:
    """
    Compute life stage fields and return cached or newly generated trait payload.

    If GPT generation fails, returns empty trait lists and does not raise.
    """
    age_months = _get_pet_age_months(pet)
    weight_kg = float(pet.weight) if pet.weight is not None else None
    breed_size = _get_breed_size(weight_kg, pet.breed)
    stage = _get_life_stage(age_months, breed_size)
    boundaries = BREED_SIZE_BOUNDARIES[breed_size]

    existing_rows = db.query(PetLifeStageTrait).filter_by(pet_id=pet.id).all()
    exact_row = next(
        (
            row
            for row in existing_rows
            if row.life_stage == stage.value and row.breed_size == breed_size.value
        ),
        None,
    )

    if exact_row:
        cached_insights = exact_row.traits if isinstance(exact_row.traits, list) else []

        if cached_insights:
            return LifeStageData(
                stage=stage.value,
                age_months=age_months,
                breed_size=breed_size.value,
                stage_boundaries={
                    "junior_start": int(boundaries["junior_start"]),
                    "adult_start": int(boundaries["adult_start"]),
                    "senior_start": int(boundaries["senior_start"]),
                },
                insights=cached_insights,
            )

        # Cache row exists but has no insights (previously filtered to empty).
        # Only regenerate if the row is older than 10 minutes to avoid hammering
        # the Claude API on every dashboard request.
        generated_at = getattr(exact_row, "generated_at", None)
        if generated_at is not None:
            age_seconds = (datetime.now(UTC).replace(tzinfo=None) - generated_at).total_seconds()
            if age_seconds < 600:
                logger.info(
                    "Skipping life-stage regeneration for pet=%s (empty cache row is recent, %.0fs old)",
                    pet.id, age_seconds,
                )
                return LifeStageData(
                    stage=stage.value,
                    age_months=age_months,
                    breed_size=breed_size.value,
                    stage_boundaries={
                        "junior_start": int(boundaries["junior_start"]),
                        "adult_start": int(boundaries["adult_start"]),
                        "senior_start": int(boundaries["senior_start"]),
                    },
                    insights=[],
                )

        logger.info(
            "Refreshing cached life-stage insights for pet=%s (empty cache row)",
            pet.id,
        )

    try:
        generated = await _generate_life_stage_traits_gpt(
            pet.breed or "mixed breed",
            age_months,
            stage.value,
        )
    except Exception as exc:
        logger.warning("Life stage insight generation failed for pet=%s: %s", pet.id, exc)
        return LifeStageData(
            stage=stage.value,
            age_months=age_months,
            breed_size=breed_size.value,
            stage_boundaries={
                "junior_start": int(boundaries["junior_start"]),
                "adult_start": int(boundaries["adult_start"]),
                "senior_start": int(boundaries["senior_start"]),
            },
            insights=[],
        )

    filtered_insights = generated.insights[:_MAX_TRAITS]

    for row in existing_rows:
        if row is not exact_row:
            db.delete(row)

    if exact_row:
        exact_row.breed_size = breed_size.value
        exact_row.traits = filtered_insights
        exact_row.generated_at = datetime.now(UTC).replace(tzinfo=None)
    else:
        cache_row = PetLifeStageTrait(
            pet_id=pet.id,
            life_stage=stage.value,
            breed_size=breed_size.value,
            traits=filtered_insights,
            generated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(cache_row)
    db.commit()

    return LifeStageData(
        stage=stage.value,
        age_months=age_months,
        breed_size=breed_size.value,
        stage_boundaries={
            "junior_start": int(boundaries["junior_start"]),
            "adult_start": int(boundaries["adult_start"]),
            "senior_start": int(boundaries["senior_start"]),
        },
        insights=filtered_insights,
    )
