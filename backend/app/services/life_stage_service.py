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
from app.services.care_plan_engine import _get_breed_size, _get_life_stage, _get_pet_age_months
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

_ALLOWED_TRAIT_COLORS = {"green", "yellow", "red", "neutral"}
_MAX_TRAITS = 5
_MAX_ESSENTIAL_CARE_ITEMS = 2
_openai_client = None


@dataclass
class LifeStageData:
    """Life stage payload returned to dashboard service."""

    stage: str
    age_months: int
    breed_size: str
    traits: list[dict[str, str]]
    essential_care: list[dict[str, str]]


@dataclass
class _LifeStageTraitsPayload:
    """Internal normalized GPT payload for persistence/response."""

    traits: list[dict[str, str]]
    essential_care: list[dict[str, str]]


def _get_openai_client():
    """Lazy-initialise AsyncOpenAI client."""
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI

        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def _coerce_traits_payload(raw_payload: Any) -> _LifeStageTraitsPayload:
    """Validate and clamp model output to the expected response contract."""
    traits: list[dict[str, str]] = []
    essential_care: list[dict[str, str]] = []

    raw_traits = raw_payload.get("traits") if isinstance(raw_payload, dict) else None
    if isinstance(raw_traits, list):
        for item in raw_traits:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            color = str(item.get("color", "")).strip().lower()
            if not label or color not in _ALLOWED_TRAIT_COLORS:
                continue
            traits.append({"label": label[:100], "color": color})
            if len(traits) >= _MAX_TRAITS:
                break

    raw_essential = raw_payload.get("essential_care") if isinstance(raw_payload, dict) else None
    if isinstance(raw_essential, list):
        for item in raw_essential:
            if not isinstance(item, dict):
                continue
            icon = str(item.get("icon", "")).strip()[:16]
            title = str(item.get("title", "")).strip()[:80]
            detail = str(item.get("detail", "")).strip()[:180]
            if not title or not detail:
                continue
            essential_care.append({"icon": icon, "title": title, "detail": detail})
            if len(essential_care) >= _MAX_ESSENTIAL_CARE_ITEMS:
                break

    return _LifeStageTraitsPayload(traits=traits, essential_care=essential_care)


async def _generate_life_stage_traits_gpt(
    breed: str,
    age_months: int,
    stage: str,
) -> _LifeStageTraitsPayload:
    """Generate stage-specific traits from GPT and normalize the response."""
    client = _get_openai_client()
    safe_breed = (breed or "mixed breed").strip()

    system_prompt = (
        "Generate breed-specific traits for a pet in the provided life stage. "
        "Respond with ONLY valid JSON object with keys: "
        "traits and essential_care. "
        "Rules: traits must be a list of up to 5 items and each item must have "
        "{label, color}. color must be one of: green, yellow, red, neutral. "
        "Use non-alarming language that explains body/behavior changes and what to watch. "
        "essential_care must be a list of up to 2 items and each item must have "
        "{icon, title, detail}. Keep detail to one concise line."
    )

    user_prompt = (
        f"Breed: {safe_breed}\n"
        f"Age months: {age_months}\n"
        f"Life stage: {stage}\n"
    )

    async def _call() -> str:
        response = await client.chat.completions.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=700,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or "{}"

    raw = await retry_openai_call(_call)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        parsed = json.loads(cleaned)
    except Exception as exc:
        logger.warning("Life stage trait parse failed: %s | raw=%s", exc, raw)
        return _LifeStageTraitsPayload(traits=[], essential_care=[])

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

    existing_rows = db.query(PetLifeStageTrait).filter_by(pet_id=pet.id).all()
    current_row = next((row for row in existing_rows if row.life_stage == stage.value), None)

    if current_row and current_row.breed_size == breed_size.value:
        return LifeStageData(
            stage=stage.value,
            age_months=age_months,
            breed_size=breed_size.value,
            traits=current_row.traits if isinstance(current_row.traits, list) else [],
            essential_care=(
                current_row.essential_care if isinstance(current_row.essential_care, list) else []
            ),
        )

    try:
        generated = await _generate_life_stage_traits_gpt(pet.breed or "mixed breed", age_months, stage.value)
    except Exception as exc:
        logger.warning("Life stage trait generation failed for pet=%s: %s", pet.id, exc)
        return LifeStageData(
            stage=stage.value,
            age_months=age_months,
            breed_size=breed_size.value,
            traits=[],
            essential_care=[],
        )

    for row in existing_rows:
        if row.life_stage != stage.value or row.breed_size != breed_size.value:
            db.delete(row)

    cache_row = PetLifeStageTrait(
        pet_id=pet.id,
        life_stage=stage.value,
        breed_size=breed_size.value,
        traits=generated.traits,
        essential_care=generated.essential_care,
        generated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(cache_row)
    db.commit()

    return LifeStageData(
        stage=stage.value,
        age_months=age_months,
        breed_size=breed_size.value,
        traits=generated.traits,
        essential_care=generated.essential_care,
    )
