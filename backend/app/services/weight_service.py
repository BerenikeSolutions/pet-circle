"""
PetCircle Phase 1 — Weight History Service

Manages weight tracking for pets. Provides CRUD operations for
weight measurements and breed-specific ideal weight ranges.

Ideal weight ranges are looked up via OpenAI (gpt-4.1) and
cached in the ideal_weight_cache table per (species, breed, gender,
age_category) combo to minimize API costs.
"""

import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import (
    OPENAI_WEIGHT_LOOKUP_MAX_TOKENS,
    OPENAI_WEIGHT_LOOKUP_MODEL,
    OPENAI_WEIGHT_LOOKUP_TEMPERATURE,
    WEIGHT_CACHE_STALENESS_DAYS,
)
from app.models.ideal_weight_cache import IdealWeightCache
from app.models.pet import Pet
from app.models.weight_history import WeightHistory
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

# Default range when breed not found or OpenAI call fails
DEFAULT_RANGE = {"min": 5, "max": 50}

# --- Anthropic client singleton (lazy) ---
_openai_weight_client = None


def _get_openai_weight_client():
    """Return a cached AI client for weight lookups (provider-agnostic, created on first call)."""
    global _openai_weight_client
    if _openai_weight_client is None:
        from app.utils.ai_client import get_ai_client  # noqa: PLC0415
        _openai_weight_client = get_ai_client()
    return _openai_weight_client


# --- System prompt for weight range lookup ---
WEIGHT_LOOKUP_SYSTEM_PROMPT = (
    "You are a veterinary reference assistant. Given a pet's species, breed, gender, "
    "and age, return the ideal healthy weight range in kilograms.\n\n"
    "Rules:\n"
    "- Return ONLY valid JSON: {\"min_kg\": <number>, \"max_kg\": <number>}\n"
    "- Values must be positive numbers rounded to 1 decimal place\n"
    "- min_kg must be less than max_kg\n"
    "- Use widely accepted veterinary breed standards\n"
    "- Account for age (puppies/kittens weigh less than adults)\n"
    "- Account for gender (males are typically heavier)\n"
    "- If the breed is unknown or not a real breed, return {\"min_kg\": null, \"max_kg\": null}\n"
    "- No explanation, no markdown — JSON only"
)


# --- Age category helpers ---

# Thresholds in years for age categories
_DOG_AGE_THRESHOLDS = {"puppy": 1, "junior": 2, "adult": 7}
_CAT_AGE_THRESHOLDS = {"kitten": 1, "junior": 2, "adult": 10}


def _calculate_weight_age_category(species: str | None, dob: date | None) -> str:
    """
    Bucket a pet into an age category for weight range lookup.

    Categories:
        Dogs: puppy (<1y), junior (1-2y), adult (2-7y), senior (7+y)
        Cats: kitten (<1y), junior (1-2y), adult (2-10y), senior (10+y)
    """
    if not dob:
        return "adult"  # Default assumption when DOB unknown

    age_years = (date.today() - dob).days / 365.25
    thresholds = _DOG_AGE_THRESHOLDS if (species or "").lower() == "dog" else _CAT_AGE_THRESHOLDS

    if age_years < thresholds.get("puppy", thresholds.get("kitten", 1)):
        return "puppy" if (species or "").lower() == "dog" else "kitten"
    elif age_years < thresholds["junior"]:
        return "junior"
    elif age_years < thresholds["adult"]:
        return "adult"
    else:
        return "senior"


def _calculate_age_description(dob: date | None) -> str:
    """
    Human-readable age string for the OpenAI prompt.

    Uses precise month-based calculation to match frontend age display:
    - Calculate total months from birth to today
    - Adjust for day-of-month if today is earlier in the month than birth day
    """
    if not dob:
        return "unknown age"

    today = date.today()
    if dob > today:
        return "unknown age"

    # Calculate precise months from DOB to today
    months = (today.year - dob.year) * 12 + (today.month - dob.month)

    # Adjust if today's day is earlier than birth day
    if today.day < dob.day:
        months -= 1

    if months < 0:
        return "unknown age"

    # Convert months to years and remaining months
    years = months // 12
    remaining_months = months % 12

    if years == 0:
        return f"{months} month{'s' if months != 1 else ''} old"
    elif remaining_months == 0:
        return f"{years} year{'s' if years != 1 else ''} old"
    else:
        return f"{years} year{'s' if years != 1 else ''} and {remaining_months} month{'s' if remaining_months != 1 else ''} old"


# --- Core lookup ---

async def get_ideal_range(
    db: Session,
    species: str | None,
    breed: str | None,
    gender: str | None,
    dob: date | None,
) -> dict:
    """
    Get ideal weight range for a pet, using cached AI lookups.

    Pipeline: DB cache check → OpenAI call → cache result → fallback to default.

    Args:
        db: Database session.
        species: 'dog' or 'cat'.
        breed: Breed name (e.g. 'Golden Retriever').
        gender: 'male' or 'female'.
        dob: Date of birth (for age-based range adjustments).

    Returns:
        {"min": <float>, "max": <float>}
    """
    if not breed or not species:
        return DEFAULT_RANGE

    breed_normalized = breed.lower().strip()
    gender_normalized = (gender or "male").lower().strip()
    species_normalized = species.lower().strip()
    age_category = _calculate_weight_age_category(species_normalized, dob)

    # 1. Check DB cache
    try:
        cached = (
            db.query(IdealWeightCache)
            .filter(
                IdealWeightCache.species == species_normalized,
                IdealWeightCache.breed_normalized == breed_normalized,
                IdealWeightCache.gender == gender_normalized,
                IdealWeightCache.age_category == age_category,
            )
            .first()
        )

        if cached:
            staleness_cutoff = datetime.utcnow() - timedelta(days=WEIGHT_CACHE_STALENESS_DAYS)
            if cached.created_at.replace(tzinfo=None) > staleness_cutoff:
                logger.info(
                    "Weight range cache hit: %s %s %s %s → %.1f-%.1f kg",
                    species_normalized, breed_normalized, gender_normalized,
                    age_category, cached.min_weight, cached.max_weight,
                )
                return {"min": float(cached.min_weight), "max": float(cached.max_weight)}
            else:
                # Stale entry — delete it so we re-fetch
                db.delete(cached)
                db.commit()
                logger.info("Deleted stale weight cache entry for %s %s", breed_normalized, age_category)
    except Exception as e:
        logger.warning("Weight cache lookup failed, proceeding to OpenAI: %s", e)

    # 2. Call OpenAI
    age_description = _calculate_age_description(dob)
    try:
        result = await retry_openai_call(
            _call_openai_weight_lookup,
            species_normalized, breed_normalized, gender_normalized, age_description,
        )
    except Exception as e:
        logger.error("OpenAI weight lookup failed after retries: %s", e)
        return DEFAULT_RANGE

    if not result:
        return DEFAULT_RANGE

    min_kg = result.get("min_kg")
    max_kg = result.get("max_kg")

    # 3. Sanity check
    if (
        min_kg is None or max_kg is None
        or not isinstance(min_kg, (int, float))
        or not isinstance(max_kg, (int, float))
        or min_kg <= 0 or max_kg <= 0
        or min_kg >= max_kg
        or max_kg > 200
    ):
        logger.warning(
            "OpenAI returned invalid weight range for %s %s: min=%s max=%s, using default",
            breed_normalized, gender_normalized, min_kg, max_kg,
        )
        return DEFAULT_RANGE

    # 4. Cache the result
    try:
        cache_entry = IdealWeightCache(
            species=species_normalized,
            breed_normalized=breed_normalized,
            gender=gender_normalized,
            age_category=age_category,
            min_weight=Decimal(str(round(min_kg, 2))),
            max_weight=Decimal(str(round(max_kg, 2))),
        )
        db.add(cache_entry)
        db.commit()
        logger.info(
            "Cached weight range: %s %s %s %s → %.1f-%.1f kg",
            species_normalized, breed_normalized, gender_normalized,
            age_category, min_kg, max_kg,
        )
    except Exception as e:
        # Race condition on UNIQUE constraint — another request cached it first
        db.rollback()
        logger.info("Weight cache insert race condition (already cached): %s", e)

    return {"min": round(min_kg, 1), "max": round(max_kg, 1)}


async def _call_openai_weight_lookup(
    species: str, breed: str, gender: str, age_description: str,
) -> dict | None:
    """
    Call OpenAI to get ideal weight range for a breed.

    Returns:
        Parsed dict with min_kg/max_kg, or None on failure.
    """
    client = _get_openai_weight_client()

    user_prompt = (
        f"Species: {species}\n"
        f"Breed: {breed}\n"
        f"Gender: {gender}\n"
        f"Age: {age_description}"
    )

    response = await client.messages.create(
        model=OPENAI_WEIGHT_LOOKUP_MODEL,
        temperature=OPENAI_WEIGHT_LOOKUP_TEMPERATURE,
        max_tokens=OPENAI_WEIGHT_LOOKUP_MAX_TOKENS,
        system=WEIGHT_LOOKUP_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = response.content[0].text
    logger.debug("OpenAI weight lookup raw response: %s", raw)

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("Failed to parse OpenAI weight response: %s — raw: %s", e, raw)
        return None


# --- Weight history CRUD ---

async def get_weight_history(db: Session, pet_id, pet: Pet) -> dict:
    """
    Returns weight history entries and ideal range for a pet.

    Returns:
        {"entries": [...], "ideal_range": {"min": X, "max": Y}}
    """
    entries = (
        db.query(WeightHistory)
        .filter(WeightHistory.pet_id == pet_id)
        .order_by(desc(WeightHistory.recorded_at))
        .all()
    )

    ideal_range = await get_ideal_range(db, pet.species, pet.breed, pet.gender, pet.dob)

    return {
        "entries": [
            {
                "id": str(e.id),
                "weight": float(e.weight),
                "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
                "note": e.note,
            }
            for e in entries
        ],
        "ideal_range": ideal_range,
    }


async def add_weight_entry(db: Session, pet_id, weight: float, recorded_at: str, note: str = None) -> dict:
    """
    Add a weight measurement entry.

    Args:
        recorded_at: Date string in DD/MM/YYYY, DD-MM-YYYY, or YYYY-MM-DD format
        weight: Weight in kg (0.01 - 999.99)

    Returns:
        The created entry as a dict
    """
    # Parse date
    parsed_date = _parse_date(recorded_at)

    entry = WeightHistory(
        pet_id=pet_id,
        weight=Decimal(str(weight)),
        recorded_at=parsed_date,
        note=note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info("Weight entry added for pet %s: %.2f kg on %s", pet_id, weight, parsed_date)

    return {
        "id": str(entry.id),
        "weight": float(entry.weight),
        "recorded_at": entry.recorded_at.isoformat(),
        "note": entry.note,
    }


def _parse_date(date_str: str) -> date:
    """Parse date from multiple supported formats."""
    from app.core.constants import ACCEPTED_DATE_FORMATS
    for fmt in ACCEPTED_DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    # Try ISO format as final fallback
    try:
        return date.fromisoformat(date_str.strip())
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}")
