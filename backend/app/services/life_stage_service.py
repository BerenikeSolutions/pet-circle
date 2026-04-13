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

_ALLOWED_TRAIT_COLORS = {"green", "yellow", "red", "neutral"}
_MAX_TRAITS = 5
_MAX_ESSENTIAL_CARE_ITEMS = 2
_GENERIC_TRAIT_TOKENS = {
    "energetic", "active", "playful", "friendly", "loyal", "curious", "social",
    "calm", "happy", "alert",
}
_STAGE_SPECIFIC_TOKENS = {
    "joint", "mobility", "dental", "weight", "bcs", "metabolism", "muscle",
    "digestion", "stool", "coat", "heart", "kidney", "immunity", "mature",
    "senior", "puppy", "junior", "adult", "hormone", "stiff", "recovery",
    "supplement", "nutrition", "portion",
}
_openai_client = None


@dataclass
class LifeStageData:
    """Life stage payload returned to dashboard service."""

    stage: str
    age_months: int
    breed_size: str
    stage_boundaries: dict[str, int]
    traits: list[dict[str, str]]
    essential_care: list[dict[str, str]]


@dataclass
class _LifeStageTraitsPayload:
    """Internal normalized GPT payload for persistence/response."""

    traits: list[dict[str, str]]
    essential_care: list[dict[str, str]]


def _get_openai_client():
    """Lazy-initialise AsyncAnthropic client."""
    global _openai_client
    if _openai_client is None:
        from anthropic import AsyncAnthropic

        _openai_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
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
    documented_risks: list[str],
) -> _LifeStageTraitsPayload:
    """Generate stage-specific traits from GPT and normalize the response."""
    client = _get_openai_client()
    safe_breed = (breed or "mixed breed").strip()

    system_prompt = (
        "Generate age-and-stage-specific traits for a pet in the provided life stage. "
        "Respond with ONLY valid JSON object with keys: "
        "traits and essential_care. "
        "Rules: traits must be a list of up to 5 items and each item must have "
        "{label, color}. color must be one of: green, yellow, red, neutral. "
        "Do not return generic traits like energetic/playful/friendly unless tied to "
        "an age-linked physiological or clinical signal. "
        "Use non-alarming language that explains body/behavior changes and what to watch. "
        "essential_care must be a list of up to 2 items and each item must have "
        "{icon, title, detail}. Keep detail to one concise line. "
        "Every essential_care detail MUST explicitly reference one documented risk fact provided by the user prompt."
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
        return _LifeStageTraitsPayload(traits=[], essential_care=[])

    return _coerce_traits_payload(parsed)


def _is_stage_specific_trait(label: str) -> bool:
    """Return True when trait text carries age/stage-specific value."""
    value = (label or "").strip().lower()
    if not value:
        return False
    if any(token in value for token in _STAGE_SPECIFIC_TOKENS):
        return True
    if any(token in value for token in _GENERIC_TRAIT_TOKENS):
        return False
    return True


def _risk_keywords(documented_risks: list[str]) -> set[str]:
    """Extract normalized keywords from risk strings for lightweight matching."""
    keywords: set[str] = set()
    for risk in documented_risks:
        for token in str(risk).lower().replace("/", " ").replace("-", " ").split():
            clean = token.strip(".,:;()[]{}")
            if len(clean) >= 4:
                keywords.add(clean)
    return keywords


def _is_risk_tied_care_item(item: dict[str, str], risk_keywords: set[str]) -> bool:
    """Return True when care item title/detail references documented risk context."""
    text = f"{item.get('title', '')} {item.get('detail', '')}".lower()
    return any(keyword in text for keyword in risk_keywords)


def _fallback_essential_care_from_risks(documented_risks: list[str]) -> list[dict[str, str]]:
    """Build deterministic essential care highlights when GPT output is not risk-grounded."""
    items: list[dict[str, str]] = []
    for risk in documented_risks[:_MAX_ESSENTIAL_CARE_ITEMS]:
        risk_l = risk.lower()
        if "weight" in risk_l or "body condition" in risk_l or "bcs" in risk_l:
            items.append({
                "icon": "⚖️",
                "title": "Weight check this stage",
                "detail": f"Body condition risk noted ({risk}); review portions and track BCS monthly.",
            })
        elif "diet" in risk_l or "micronutrient" in risk_l or "supplement" in risk_l or "kibble" in risk_l:
            items.append({
                "icon": "🥣",
                "title": "Close nutrition gaps",
                "detail": f"Diet risk noted ({risk}); discuss targeted supplements with your vet.",
            })
        elif "condition" in risk_l:
            items.append({
                "icon": "🩺",
                "title": "Condition follow-up",
                "detail": f"Existing condition risk noted ({risk}); keep follow-up checks on schedule.",
            })
        else:
            items.append({
                "icon": "📌",
                "title": "Stage-risk follow-up",
                "detail": f"Track this documented risk during {risk} and review at next vet visit.",
            })
    return items[:_MAX_ESSENTIAL_CARE_ITEMS]


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
    risk_keywords = _risk_keywords(documented_risks)
    has_specific_risks = any(
        not risk.lower().startswith("life-stage transition risk")
        for risk in documented_risks
    )

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
        cached_traits = exact_row.traits if isinstance(exact_row.traits, list) else []
        cached_essential = exact_row.essential_care if isinstance(exact_row.essential_care, list) else []
        essential_ok = (
            True
            if not has_specific_risks
            else bool(cached_essential)
            and all(_is_risk_tied_care_item(item, risk_keywords) for item in cached_essential)
        )

        if essential_ok:
            return LifeStageData(
                stage=stage.value,
                age_months=age_months,
                breed_size=breed_size.value,
                stage_boundaries={
                    "junior_start": int(boundaries["junior_start"]),
                    "adult_start": int(boundaries["adult_start"]),
                    "senior_start": int(boundaries["senior_start"]),
                },
                traits=cached_traits,
                essential_care=cached_essential,
            )

        logger.info(
            "Refreshing cached life-stage traits for pet=%s due to quality/risk mismatch",
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
        logger.warning("Life stage trait generation failed for pet=%s: %s", pet.id, exc)
        return LifeStageData(
            stage=stage.value,
            age_months=age_months,
            breed_size=breed_size.value,
            stage_boundaries={
                "junior_start": int(boundaries["junior_start"]),
                "adult_start": int(boundaries["adult_start"]),
                "senior_start": int(boundaries["senior_start"]),
            },
            traits=[],
            essential_care=[],
        )

    filtered_traits = [t for t in generated.traits if _is_stage_specific_trait(t.get("label", ""))]
    filtered_essential = [
        item for item in generated.essential_care
        if _is_risk_tied_care_item(item, risk_keywords)
    ]
    if not filtered_essential:
        filtered_essential = _fallback_essential_care_from_risks(documented_risks)

    filtered_traits = filtered_traits[:_MAX_TRAITS]
    filtered_essential = filtered_essential[:_MAX_ESSENTIAL_CARE_ITEMS]

    for row in existing_rows:
        if row is not exact_row:
            db.delete(row)

    if exact_row:
        exact_row.breed_size = breed_size.value
        exact_row.traits = filtered_traits
        exact_row.essential_care = filtered_essential
        exact_row.generated_at = datetime.now(UTC).replace(tzinfo=None)
    else:
        cache_row = PetLifeStageTrait(
            pet_id=pet.id,
            life_stage=stage.value,
            breed_size=breed_size.value,
            traits=filtered_traits,
            essential_care=filtered_essential,
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
        traits=filtered_traits,
        essential_care=filtered_essential,
    )
