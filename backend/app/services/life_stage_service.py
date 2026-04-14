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
from app.models.condition import Condition
from app.models.diet_item import DietItem
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
_GENERIC_TRAIT_TOKENS = {
    "energetic", "active", "playful", "friendly", "loyal", "curious", "social",
    "calm", "happy", "alert",
    "metabolism", "appetite", "vision decline", "slower",
    "supplement", "supplements", "nutrition", "diet", "portion", "kibble", "feed",
}
_STAGE_SPECIFIC_TOKENS = {
    "joint", "mobility", "dental", "weight", "bcs", "muscle",
    "digestion", "stool", "coat", "heart", "kidney", "immunity", "mature",
    "senior", "puppy", "junior", "adult", "hormone", "stiff", "recovery",
    "screening", "screen", "panel", "cardiac", "thyroid", "hip", "elbow",
    "patella", "ocular", "respiratory", "gait", "lameness",
}
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
    """Lazy-initialise AsyncAnthropic client."""
    global _openai_client
    if _openai_client is None:
        from anthropic import AsyncAnthropic

        _openai_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
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
    documented_risks: list[str],
) -> _LifeStageTraitsPayload:
    """Generate stage-specific traits from GPT and normalize the response."""
    client = _get_openai_client()
    safe_breed = (breed or "mixed breed").strip()

    system_prompt = (
        "You generate breed- and life-stage-specific health insights for a pet dashboard.\n"
        "Return ONLY a valid JSON object matching this exact schema:\n"
        '{"lifeStage": {"insights": [{\"text\": \"...\", \"color\": \"orange\"|\"green\"|\"neutral\"}]}}\n\n'
        "LIFE STAGE DETERMINATION:\n"
        "Before determining life stage, estimate age-to-life-stage mapping using "
        "breed-specific thresholds — large and giant breeds are considered senior "
        "earlier (6–7 years) than small breeds (10–11 years).\n\n"
        "INSIGHT RULES:\n"
        "Include only breed- and life-stage-specific watch-outs and vet screenings.\n\n"
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
        "RANKING & SELECTION:\n"
        "Rank all candidate insights by clinical importance to this specific breed at "
        "this specific age. Select ONLY the top 3 — do not pad if fewer than 3 genuine "
        "issues exist. If two insights are of equal clinical weight, prefer the one more "
        "specific to the breed over the generic one.\n"
        "Mix home watch-outs and vet screenings based on what is most clinically "
        "relevant — do not force a fixed ratio.\n\n"
        "FORMAT:\n"
        "Each text is ONE complete sentence, maximum 12 words. "
        "Keep language calm, specific, and non-generic. "
        "Do not label insights as 'home' or 'vet' in the output.\n\n"
        "COLOR ASSIGNMENT:\n"
        "  orange — watch-out or early warning the parent should actively monitor\n"
        "  green  — positive milestone or condition being managed well at this stage\n"
        "  neutral — vet screening indicated but not urgent\n"
    )

    user_prompt = (
        f"Breed: {safe_breed}\n"
        f"Age months: {age_months}\n"
        f"Life stage: {stage}\n"
        "Documented risks (use only these as evidence for essential care):\n"
        f"- " + "\n- ".join(documented_risks)
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


def _is_stage_specific_trait(label: str) -> bool:
    """Return True when trait text carries age/stage-specific value."""
    value = (label or "").strip().lower()
    if not value:
        return False
    if any(token in value for token in _STAGE_SPECIFIC_TOKENS):
        return True
    return not any(token in value for token in _GENERIC_TRAIT_TOKENS)



def _collect_documented_risks(db: Session, pet: Pet) -> list[str]:
    """Collect deterministic risk facts from pet profile and current records."""
    risks: list[str] = []

    if bool(getattr(pet, "weight_flagged", False)):
        risks.append("Body condition concern: weight flagged during onboarding")

    try:
        active_conditions = (
            db.query(Condition)
            .filter(Condition.pet_id == pet.id, Condition.is_active == True)
            .order_by(Condition.created_at.desc())
            .all()
        )
        for cond in active_conditions[:2]:
            if getattr(cond, "name", None):
                risks.append(f"Active condition: {cond.name}")
    except Exception:
        logger.warning("Could not fetch active conditions for life-stage risks", exc_info=True)

    try:
        diet_items = db.query(DietItem).filter(DietItem.pet_id == pet.id).all()
        has_packaged_food = any((getattr(item, "type", "") or "").lower() == "packaged" for item in diet_items)
        has_supplement = any((getattr(item, "type", "") or "").lower() == "supplement" for item in diet_items)
        if has_packaged_food and not has_supplement:
            risks.append("Diet risk: packaged/kibble-heavy diet without supplement support")
    except Exception:
        logger.warning("Could not fetch diet items for life-stage risks", exc_info=True)

    if not risks:
        risks.append("Life-stage transition risk: preventive and nutrition needs shift with age")

    return risks[:4]


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
    documented_risks = _collect_documented_risks(db, pet)

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

        logger.info(
            "Refreshing cached life-stage insights for pet=%s (empty cache row)",
            pet.id,
        )

    try:
        generated = await _generate_life_stage_traits_gpt(
            pet.breed or "mixed breed",
            age_months,
            stage.value,
            documented_risks,
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

    filtered_insights = [
        i for i in generated.insights if _is_stage_specific_trait(i.get("text", ""))
    ][:_MAX_TRAITS]

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
