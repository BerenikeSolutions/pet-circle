"""
PetCircle Phase 1 — Nutrition Analysis Service

Computes detailed nutrition breakdown based on a pet's diet items
matched against the product catalog + AI-estimated nutrition for
unknown foods. Uses AI-generated breed-specific targets (cached in DB)
instead of hardcoded breed dicts.

Pipeline:
    1. Get breed-specific targets (DB cache → GPT → fallback)
    2. Match diet items to product catalog (multi-strategy matching)
    3. For unmatched items, estimate nutrition via GPT (DB cache → GPT)
    4. Aggregate, compare against targets, generate recommendations
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import (
    FOOD_CACHE_STALENESS_DAYS,
    NUTRITION_CACHE_STALENESS_DAYS,
    OPENAI_FOOD_ESTIMATION_MAX_TOKENS,
    OPENAI_NUTRITION_LOOKUP_MAX_TOKENS,
    OPENAI_NUTRITION_REC_MAX_TOKENS,
    OPENAI_NUTRITION_REC_TEMPERATURE,
    OPENAI_QUERY_MODEL,
)
from app.models.condition import Condition
from app.models.diet_item import DietItem
from app.models.food_nutrition_cache import FoodNutritionCache
from app.models.nutrition_target_cache import NutritionTargetCache
from app.models.pet import Pet
from app.services.diet_service import split_diet_items_by_type
from app.services.weight_service import DEFAULT_RANGE as DEFAULT_IDEAL_WEIGHT_RANGE
from app.services.weight_service import get_ideal_range
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

# In-process TTL cache for nutrition recommendations.
# Key: SHA-256 of (pet_name, breed, sorted_conditions, gap_summary).
# Value: (recommendation_text, timestamp). TTL = 4 hours.
_REC_CACHE: dict[str, tuple[str, float]] = {}
_REC_CACHE_TTL_SECONDS = 4 * 3600

# Default targets used as fallback when GPT call fails
DEFAULT_TARGETS = {
    "calories": 1200,
    "protein": 25,
    "fat": 14,
    "carbs": 50,
    "fibre": 4,
    "moisture": 10,
    "calcium": 1.0,
    "phosphorus": 0.8,
    "omega_3": 300,
    "omega_6": 1500,
    "vitamin_e": 300,
    "vitamin_d3": 400,
    "glucosamine": 500,
    "probiotics": False,
}

# Required keys in AI-generated targets JSON
REQUIRED_TARGET_KEYS = {
    "calories", "protein", "fat", "carbs", "fibre", "moisture",
    "calcium", "phosphorus", "omega_3", "omega_6", "vitamin_e",
    "vitamin_d3", "glucosamine", "probiotics",
}

# --- Anthropic client singleton (lazy) ---
_openai_nutrition_client = None


def _get_openai_client():
    """Return a cached AsyncAnthropic client (created on first call)."""
    global _openai_nutrition_client
    if _openai_nutrition_client is None:
        from anthropic import AsyncAnthropic
        _openai_nutrition_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _openai_nutrition_client


# --- Age category helpers (reused from weight_service pattern) ---

_DOG_AGE_THRESHOLDS = {"puppy": 1, "junior": 2, "adult": 7}
_CAT_AGE_THRESHOLDS = {"kitten": 1, "junior": 2, "adult": 10}


def _calculate_age_category(species: str | None, dob: date | None) -> str:
    """Bucket a pet into an age category for nutrition target lookup."""
    if not dob:
        return "adult"
    age_years = (date.today() - dob).days / 365.25
    thresholds = _DOG_AGE_THRESHOLDS if (species or "").lower() == "dog" else _CAT_AGE_THRESHOLDS
    first_key = "puppy" if (species or "").lower() == "dog" else "kitten"
    if age_years < thresholds.get(first_key, 1):
        return first_key
    elif age_years < thresholds["junior"]:
        return "junior"
    elif age_years < thresholds["adult"]:
        return "adult"
    else:
        return "senior"


def _calculate_age_description(dob: date | None) -> str:
    """
    Human-readable age string for OpenAI prompts.

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
    return f"{years} year{'s' if years != 1 else ''} and {remaining_months} month{'s' if remaining_months != 1 else ''} old"


def _normalize_gender_for_lookup(gender: str | None) -> str | None:
    """Normalize gender to male/female; treat unknown values as absent."""
    if not gender:
        return None
    normalized = gender.lower().strip()
    if normalized in {"male", "m", "boy"}:
        return "male"
    if normalized in {"female", "f", "girl"}:
        return "female"
    return None


def _midpoint_from_confident_ideal_range(weight_range: dict | None) -> float | None:
    """Return midpoint only when the ideal-weight range is likely trustworthy."""
    if not isinstance(weight_range, dict):
        return None

    min_w = weight_range.get("min")
    max_w = weight_range.get("max")
    if not isinstance(min_w, (int, float)) or not isinstance(max_w, (int, float)):
        return None
    if min_w <= 0 or max_w <= min_w:
        return None

    default_min = float(DEFAULT_IDEAL_WEIGHT_RANGE.get("min", 0))
    default_max = float(DEFAULT_IDEAL_WEIGHT_RANGE.get("max", 0))
    if float(min_w) == default_min and float(max_w) == default_max:
        return None

    return round((float(min_w) + float(max_w)) / 2, 1)


# --- System Prompts ---

NUTRITION_TARGET_SYSTEM_PROMPT = (
    "You are a board-certified veterinary nutritionist. Given a pet's species, breed, "
    "age, weight, and gender (when provided), return the recommended DAILY nutritional targets.\n\n"
    "Rules:\n"
    "- Return ONLY valid JSON with these exact keys:\n"
    "  calories (int, kcal/day), protein (int, % of diet), fat (int, %), carbs (int, %), "
    "fibre (int, %), moisture (int, %), calcium (float, %), phosphorus (float, %), "
    "omega_3 (int, mg/day), omega_6 (int, mg/day), vitamin_e (int, IU/day), "
    "vitamin_d3 (int, IU/day), glucosamine (int, mg/day), probiotics (bool, whether recommended)\n"
    "- Use established AAFCO/FEDIAF/NRC standards for the specific breed\n"
    "- Account for breed-specific predispositions (e.g., joint issues in large breeds)\n"
    "- Account for age category (puppies need more protein, seniors need joint support)\n"
    "- Account for body weight when estimating calorie and nutrient requirements\n"
    "- Account for gender-related body composition differences when gender is provided\n"
    "- No explanation, no markdown — JSON only"
)

def _build_food_estimation_prompt(
    species: str | None = None,
    breed: str | None = None,
    weight_kg: float | None = None,
    age_description: str | None = None,
    gender: str | None = None,
    conditions: list[str] | None = None,
) -> str:
    """
    Build veterinary nutritionist prompt for food analysis.

    Returns the core prompt for nutrition analysis that:
    1. Resolves food identity
    2. Determines serving size with strict rules
    3. Handles mixed diets properly
    4. Estimates daily nutrition intake
    5. Analyzes micronutrient gaps qualitatively
    6. Returns top 4 micronutrient gaps
    """
    return (
        "You are a board-certified veterinary nutritionist.\n\n"
        "Your task:\n"
        "Given food items, pet details, and optionally user-provided quantities, estimate DAILY nutritional intake and identify the most important micronutrient gaps.\n\n"
        "You must follow this strict decision framework:\n\n"
        "-----------------------------------\n"
        "STEP 1 — RESOLVE FOOD IDENTITY\n"
        "-----------------------------------\n"
        "- Identify the most likely specific product based on:\n"
        "- food name\n"
        "- species\n"
        "- age (puppy / adult / senior)\n"
        "- Example:\n"
        "\"Pedigree\" + adult dog → Pedigree Adult Dog Food\n"
        "- If multiple variants are possible, choose the most common one and reduce confidence\n"
        "- If product identity is highly ambiguous, reduce confidence\n\n"
        "-----------------------------------\n"
        "STEP 2 — DETERMINE SERVING SIZE\n"
        "-----------------------------------\n\n"
        "CASE A: USER PROVIDED QUANTITY (any food)\n"
        "- Use EXACTLY the user-provided quantity (e.g., \"2 cups/day\", \"1 bowl/day\")\n"
        "- Do NOT override, scale, or reinterpret it\n\n"
        "CASE B: COMMERCIAL / PACKAGED FOOD AND NO QUANTITY PROVIDED\n"
        "- Use ONLY official brand feeding guidelines\n"
        "- Use pet weight and age ONLY to select the correct feeding range\n"
        "- Choose a reasonable midpoint within that range\n"
        "- Do NOT invent or extrapolate beyond brand guidance\n\n"
        "CASE C: HOMEMADE / GENERIC FOOD AND NO QUANTITY PROVIDED\n"
        "- DO NOT estimate or assume any serving size\n"
        "- Mark portion as UNKNOWN\n\n"
        "IF serving size cannot be determined with confidence:\n"
        "- Set confidence < 0.6\n"
        "- RETURN NO ANALYSIS (see fail-safe)\n\n"
        "-----------------------------------\n"
        "STEP 3 — MIXED DIET HANDLING\n"
        "-----------------------------------\n\n"
        "If BOTH commercial food AND homemade food are present:\n\n"
        "- Treat commercial food as the PRIMARY diet anchor:\n"
        "- Use it for:\n"
        "- calories_per_day\n"
        "- macronutrient percentages (protein, fat, fibre)\n\n"
        "- For homemade food WITHOUT quantity:\n"
        "- DO NOT include in:\n"
        "- calories\n"
        "- macronutrient calculations\n"
        "- ONLY use it for qualitative micronutrient signals if possible\n\n"
        "- If homemade food HAS quantity:\n"
        "- Include it fully in all calculations\n\n"
        "-----------------------------------\n"
        "STEP 4 — NUTRITION ESTIMATION\n"
        "-----------------------------------\n"
        "- Estimate TOTAL DAILY intake based on determined serving size\n"
        "- Ensure values are realistic and internally consistent\n"
        "- Prevent extreme or biologically impossible outputs\n"
        "- Macro percentages must remain within realistic biological limits\n"
        "- Total calories must fall within realistic daily intake ranges\n\n"
        "-----------------------------------\n"
        "STEP 5 — MICRONUTRIENT GAP ANALYSIS\n"
        "-----------------------------------\n\n"
        "- Identify micronutrient gaps dynamically based on:\n"
        "- pet nutritional requirements\n"
        "- current diet composition\n\n"
        "- Use ONLY this controlled list of nutrient names:\n"
        "omega_3, omega_6, vitamin_e, vitamin_d3, glucosamine, calcium, phosphorus, iron, zinc, taurine, fibre\n\n"
        "- For each nutrient:\n"
        "- Assign ONLY one of the following statuses:\n"
        "- \"sufficient\"\n"
        "- \"low\"\n"
        "- \"missing\"\n\n"
        "- DO NOT include nutrients where status cannot be confidently determined\n"
        "- DO NOT output \"unknown\" under any condition\n\n"
        "- DO NOT output numeric values, units, or requirements for micronutrients\n"
        "- Micronutrients are strictly qualitative signals\n\n"
        "- Assign a severity_score (0–1) based on:\n"
        "- deficiency severity (missing > low > sufficient)\n"
        "- relevance to pet conditions\n"
        "- confidence in assessment\n\n"
        "-----------------------------------\n"
        "STEP 6 — SELECT TOP MICRONUTRIENTS\n"
        "-----------------------------------\n\n"
        "- Rank micronutrients by severity_score\n"
        "- Return ONLY the TOP 4 most important micronutrient gaps\n"
        "- EXCLUDE all nutrients marked as \"sufficient\"\n"
        "- If fewer than 4 meaningful gaps exist, return fewer\n\n"
        "-----------------------------------\n"
        "OUTPUT FORMAT\n"
        "-----------------------------------\n\n"
        "Return ONLY valid JSON with these keys:\n\n"
        "resolved_name (string),\n"
        "confidence (float 0–1),\n"
        "serving_description (string),\n"
        "calories_per_day (int),\n"
        "protein_pct (float),\n"
        "fat_pct (float),\n"
        "fibre_pct (float),\n\n"
        "micronutrient_gaps: [\n"
        "{\n"
        "name (string),\n"
        "status (string: sufficient | low | missing),\n"
        "severity_score (float 0–1),\n"
        "supplement (string | null — specific product name if supplementation is advised, null if sufficient or no supplement needed),\n"
        "reason (string — one concise sentence explaining why this gap matters for this specific pet, diet, and conditions)\n"
        "}\n"
        "]\n\n"
        "-----------------------------------\n"
        "CRITICAL RULES\n"
        "-----------------------------------\n\n"
        "- NEVER estimate serving size arbitrarily\n"
        "- NEVER assume portion size for homemade food\n"
        "- NEVER scale portions beyond brand guidelines\n"
        "- NEVER include homemade food in calorie or macro calculations unless quantity is provided\n"
        "- NEVER fabricate precision where data is missing\n"
        "- Maintain internal consistency across all outputs\n\n"
        "-----------------------------------\n"
        "FAIL-SAFE\n"
        "-----------------------------------\n\n"
        "If ANY of the following:\n"
        "- product identity is ambiguous OR\n"
        "- serving size is missing or unclear OR\n"
        "- confidence < 0.6\n\n"
        "THEN RETURN:\n\n"
        "{\n"
        '\"confidence\": <value>,\n'
        '\"error\": \"INSUFFICIENT_DATA\",\n'
        '\"message\": \"Provide exact SKU or serving size for accurate diet analysis\"\n'
        "}\n\n"
        "-----------------------------------\n"
        "GENERAL\n"
        "-----------------------------------\n\n"
        "- No explanation\n"
        "- No markdown\n"
        "- JSON only"
    )


# Kept for backward compatibility / fallback when pet context is unavailable.
FOOD_ESTIMATION_SYSTEM_PROMPT = _build_food_estimation_prompt(None, None, None, None)

RECOMMENDATION_SYSTEM_PROMPT = (
    "You are a friendly veterinary nutritionist. Generate a short, personalized "
    "nutrition recommendation for a pet parent.\n\n"
    "Rules:\n"
    "- 1-2 sentences maximum\n"
    "- Mention specific nutrients that need attention\n"
    "- Be encouraging but factual\n"
    "- No markdown, no bullet points — plain text only"
)


# ─── Step 3a: AI Breed Targets ──────────────────────────────────────

async def get_nutrition_targets(
    db: Session,
    species: str | None,
    breed: str | None,
    dob: date | None,
    weight_kg: float | None,
    gender: str | None,
) -> dict:
    """
    Get breed-specific daily nutrition targets, using cached AI lookups.

    Pipeline: DB cache check → OpenAI call → cache result → fallback to DEFAULT_TARGETS.
    """
    if not breed or not species:
        return dict(DEFAULT_TARGETS)

    breed_normalized = breed.lower().strip()
    species_normalized = species.lower().strip()
    age_category = _calculate_age_category(species_normalized, dob) if dob else "na"
    gender_normalized = _normalize_gender_for_lookup(gender)

    # If weight is missing, approximate from breed + age (+ gender when available).
    # When age/gender are missing, they are ignored as requested.
    effective_weight_kg = weight_kg if (weight_kg and weight_kg > 0) else None
    if effective_weight_kg is None:
        try:
            if gender_normalized:
                ideal_range = await get_ideal_range(
                    db,
                    species_normalized,
                    breed_normalized,
                    gender_normalized,
                    dob,
                )
                effective_weight_kg = _midpoint_from_confident_ideal_range(ideal_range)
            else:
                male_range = await get_ideal_range(db, species_normalized, breed_normalized, "male", dob)
                female_range = await get_ideal_range(db, species_normalized, breed_normalized, "female", dob)
                candidates: list[float] = []
                for r in (male_range, female_range):
                    midpoint = _midpoint_from_confident_ideal_range(r)
                    if midpoint is not None:
                        candidates.append(midpoint)
                if candidates:
                    effective_weight_kg = round(sum(candidates) / len(candidates), 1)
        except Exception as e:
            logger.warning("Could not approximate weight for nutrition targets: %s", e)

    weight_bucket = _weight_bucket(effective_weight_kg)
    gender_tag = (gender_normalized[0] if gender_normalized else "u")
    age_context_key = f"{age_category}|{gender_tag}|{weight_bucket}"

    # 1. Check DB cache
    try:
        cached = (
            db.query(NutritionTargetCache)
            .filter(
                NutritionTargetCache.species == species_normalized,
                NutritionTargetCache.breed_normalized == breed_normalized,
                NutritionTargetCache.age_category == age_context_key,
            )
            .first()
        )
        if cached:
            staleness_cutoff = datetime.utcnow() - timedelta(days=NUTRITION_CACHE_STALENESS_DAYS)
            if cached.created_at.replace(tzinfo=None) > staleness_cutoff:
                logger.info(
                    "Nutrition target cache hit: %s %s %s",
                    species_normalized, breed_normalized, age_context_key,
                )
                return cached.targets_json
            else:
                db.delete(cached)
                db.commit()
                logger.info("Deleted stale nutrition target cache for %s %s", breed_normalized, age_context_key)
    except Exception as e:
        logger.warning("Nutrition target cache lookup failed: %s", e)

    # 2. Call OpenAI
    age_description = _calculate_age_description(dob) if dob else None
    try:
        result = await retry_openai_call(
            _call_openai_nutrition_targets,
            species_normalized,
            breed_normalized,
            age_description,
            effective_weight_kg,
            gender_normalized,
        )
    except Exception as e:
        logger.error("OpenAI nutrition target lookup failed: %s", e)
        return dict(DEFAULT_TARGETS)

    if not result:
        return dict(DEFAULT_TARGETS)

    # 3. Validate required keys
    if not REQUIRED_TARGET_KEYS.issubset(result.keys()):
        missing = REQUIRED_TARGET_KEYS - result.keys()
        logger.warning("OpenAI nutrition targets missing keys: %s, using defaults", missing)
        return dict(DEFAULT_TARGETS)

    # 4. Cache the result
    try:
        cache_entry = NutritionTargetCache(
            species=species_normalized,
            breed_normalized=breed_normalized,
            age_category=age_context_key,
            targets_json=result,
        )
        db.add(cache_entry)
        db.commit()
        logger.info("Cached nutrition targets for %s %s %s", species_normalized, breed_normalized, age_context_key)
    except Exception as e:
        db.rollback()
        logger.info("Nutrition target cache race condition (already cached): %s", e)

    return result


async def _call_openai_nutrition_targets(
    species: str,
    breed: str,
    age_description: str | None,
    weight_kg: float | None,
    gender: str | None,
) -> dict | None:
    """Call OpenAI for breed-specific daily nutrition targets."""
    client = _get_openai_client()
    prompt_lines = [
        f"Species: {species}",
        f"Breed: {breed}",
    ]
    if age_description:
        prompt_lines.append(f"Age: {age_description}")
    if isinstance(weight_kg, (int, float)) and weight_kg > 0:
        prompt_lines.append(f"Weight_kg: {float(weight_kg):g}")
    if gender:
        prompt_lines.append(f"Gender: {gender}")
    user_prompt = "\n".join(prompt_lines)

    response = await client.messages.create(
        model=OPENAI_QUERY_MODEL,
        temperature=0.0,
        max_tokens=OPENAI_NUTRITION_LOOKUP_MAX_TOKENS,
        system=NUTRITION_TARGET_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = response.content[0].text
    logger.debug("OpenAI nutrition targets raw: %s", raw)
    result = _parse_json_from_response(raw)
    if result is None:
        logger.error("Failed to parse nutrition targets response — raw: %s", raw)
    return result


# ─── Step 3b: AI Food Estimation ────────────────────────────────────

def _parse_json_from_response(raw: str) -> dict | None:
    """Parse JSON from AI response, stripping markdown code fences if present."""
    if not raw or not isinstance(raw, str):
        return None

    # Strip markdown code fence wrappers: ```json ... ``` or ``` ... ```
    text = raw.strip()
    if text.startswith("```"):
        # Remove opening fence (optionally with language tag like ```json)
        lines = text.split("\n")
        if len(lines) > 2:
            text = "\n".join(lines[1:-1])  # Skip first and last line
        else:
            text = ""

    text = text.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _weight_bucket(weight_kg: float | None) -> str:
    """Bucket weight so similar-sized pets can share cache entries."""
    if not weight_kg or weight_kg <= 0:
        return "unk"
    if weight_kg < 5:
        return "xs"
    if weight_kg < 12:
        return "s"
    if weight_kg < 25:
        return "m"
    if weight_kg < 40:
        return "l"
    return "xl"


async def estimate_food_nutrition(
    db: Session,
    food_label: str,
    food_type: str,
    species: str | None = None,
    breed: str | None = None,
    weight_kg: float | None = None,
    age_description: str | None = None,
    gender: str | None = None,
    conditions: list[str] | None = None,
    daily_portion_g: int | None = None,
    detail: str | None = None,
) -> dict | None:
    """
    Estimate nutrition for foods not matched in product_catalog.

    Pipeline: DB cache check → OpenAI call → cache result.
    Returns nutrition dict or None on failure.

    The cache key embeds species + weight bucket + a hash of the pet's
    diagnosed conditions so a 5kg cat, a 40kg healthy dog, and a 40kg dog
    with kidney disease never share an estimate for the same food label.
    """
    species_norm = (species or "dog").lower().strip()
    bucket = _weight_bucket(weight_kg)
    conditions_sorted = sorted(c.lower().strip() for c in (conditions or []) if c)
    cond_hash = (
        hashlib.sha1(",".join(conditions_sorted).encode()).hexdigest()[:8]
        if conditions_sorted else "none"
    )
    # Encode pet context into the cache key (avoids a schema migration).
    # v3 prefix invalidates v2 entries which lacked pet context in the user prompt.
    portion_key = str(daily_portion_g) if daily_portion_g and daily_portion_g > 0 else "unset"
    # Include detail in cache key so different quantities for the same food are cached separately.
    detail_key = hashlib.sha1((detail or "").lower().strip().encode()).hexdigest()[:8]
    label_normalized = (
        f"v3|{species_norm}|{bucket}|{cond_hash}|{portion_key}|{detail_key}|{food_label.lower().strip()}"
    )

    # 1. Check DB cache
    try:
        cached = (
            db.query(FoodNutritionCache)
            .filter(
                FoodNutritionCache.food_label_normalized == label_normalized,
                FoodNutritionCache.food_type == food_type,
            )
            .first()
        )
        if cached:
            staleness_cutoff = datetime.utcnow() - timedelta(days=FOOD_CACHE_STALENESS_DAYS)
            if cached.created_at.replace(tzinfo=None) > staleness_cutoff:
                logger.info("Food nutrition cache hit: %s (%s)", label_normalized, food_type)
                return cached.nutrition_json
            else:
                db.delete(cached)
                db.commit()
    except Exception as e:
        logger.warning("Food nutrition cache lookup failed: %s", e)

    # 2. Call OpenAI
    try:
        result = await retry_openai_call(
            _call_openai_food_estimation,
            food_label, food_type,
            species, breed, weight_kg, age_description, gender, conditions_sorted,
            daily_portion_g, detail,
        )
    except Exception as e:
        logger.error("OpenAI food estimation failed: %s", e)
        return None

    if not result:
        return None

    # 3. Cache the result
    try:
        cache_entry = FoodNutritionCache(
            food_label_normalized=label_normalized,
            food_type=food_type,
            nutrition_json=result,
        )
        db.add(cache_entry)
        db.commit()
        logger.info("Cached food nutrition for: %s (%s)", label_normalized, food_type)
    except Exception as e:
        db.rollback()
        logger.info("Food nutrition cache race condition: %s", e)

    return result


async def _call_openai_food_estimation(
    food_label: str,
    food_type: str,
    species: str | None = None,
    breed: str | None = None,
    weight_kg: float | None = None,
    age_description: str | None = None,
    gender: str | None = None,
    conditions: list[str] | None = None,
    daily_portion_g: int | None = None,
    detail: str | None = None,
) -> dict | None:
    """Call OpenAI to estimate nutritional content of a food item."""
    client = _get_openai_client()
    system_prompt = _build_food_estimation_prompt(
        species=species,
        breed=breed,
        weight_kg=weight_kg,
        age_description=age_description,
        gender=gender,
        conditions=conditions,
    )
    # Build user prompt with full pet context so CASE B (brand feeding guidelines)
    # can correctly select the right feeding range using pet weight and age.
    prompt_parts = []
    if species:
        prompt_parts.append(f"Species: {species}")
    if breed:
        prompt_parts.append(f"Breed: {breed}")
    if age_description:
        prompt_parts.append(f"Age: {age_description}")
    if isinstance(weight_kg, (int, float)) and weight_kg > 0:
        prompt_parts.append(f"Weight: {float(weight_kg):g} kg")
    if gender:
        prompt_parts.append(f"Gender: {gender}")
    if conditions:
        prompt_parts.append(f"Conditions: {', '.join(conditions)}")
    prompt_parts.append(f"Food name: {food_label}")
    prompt_parts.append(f"Type: {food_type}")
    if daily_portion_g and daily_portion_g > 0:
        prompt_parts.append(f"User-provided daily portion: {daily_portion_g}g")
    elif detail and detail.strip():
        # detail stores the user-provided quantity text (e.g. "2 cups . kibble /day", "1 cup")
        prompt_parts.append(f"User-provided quantity: {detail.strip()}")
    user_prompt = "\n".join(prompt_parts)

    response = await client.messages.create(
        model=OPENAI_QUERY_MODEL,
        temperature=0.0,
        max_tokens=OPENAI_FOOD_ESTIMATION_MAX_TOKENS,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = response.content[0].text
    logger.debug("OpenAI food estimation raw: %s", raw)
    result = _parse_json_from_response(raw)
    if result is None:
        logger.error("Failed to parse food estimation response — raw: %s", raw)
        return None

    # Fail-safe: reject low-confidence or error responses
    if result.get("error") == "INSUFFICIENT_DATA":
        logger.warning("Insufficient data for food: %s — %s", food_label, result.get("message"))
        return None
    confidence = result.get("confidence", 1.0)
    if isinstance(confidence, (int, float)) and confidence < 0.6:
        logger.warning("Low confidence (%.2f) for food: %s", confidence, food_label)
        return None

    return result


# ─── Step 3d: AI Recommendation ─────────────────────────────────────

async def generate_recommendation(
    pet_name: str,
    breed: str,
    conditions: list[str],
    gap_summary: str,
    foods: list[str] | None = None,
    supplements: list[str] | None = None,
) -> str:
    """
    Generate a personalized 1-2 sentence nutrition recommendation via GPT.

    Results are cached in-process for 4 hours keyed by inputs to avoid
    redundant OpenAI calls when multiple tabs trigger analyze_nutrition()
    in the same session. Falls back to a template string on failure.
    """
    # Build a stable cache key from all inputs
    key_raw = (
        f"{pet_name}|{breed}|{','.join(sorted(conditions))}|{gap_summary}|"
        f"{','.join(sorted(foods or []))}|{','.join(sorted(supplements or []))}"
    )
    cache_key = hashlib.sha256(key_raw.encode()).hexdigest()

    cached = _REC_CACHE.get(cache_key)
    if cached and (time.time() - cached[1]) < _REC_CACHE_TTL_SECONDS:
        return cached[0]

    try:
        client = _get_openai_client()
        context = f"Pet: {pet_name}, Breed: {breed}"
        if conditions:
            context += f", Conditions: {', '.join(conditions)}"
        if foods:
            context += f"\nCurrent foods: {', '.join(foods[:5])}"
        if supplements:
            context += f"\nCurrent supplements: {', '.join(supplements[:5])}"
        context += f"\nNutritional gaps: {gap_summary}"
        if supplements:
            context += (
                "\nDo not suggest a supplement already listed under current supplements."
            )

        response = await client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=OPENAI_NUTRITION_REC_TEMPERATURE,
            max_tokens=OPENAI_NUTRITION_REC_MAX_TOKENS,
            system=RECOMMENDATION_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": context},
            ],
        )
        text = response.content[0].text.strip()
        if text:
            _REC_CACHE[cache_key] = (text, time.time())
            return text
    except Exception as e:
        logger.error("Nutrition recommendation generation failed: %s", e)

    # Fallback (not cached — allow retry on next call)
    return f"Consider consulting your vet about {pet_name}'s nutritional needs based on breed-specific requirements."


# ─── Helpers ─────────────────────────────────────────────────────────

def _status_for_ratio(ratio: float) -> str:
    """Determine status based on actual/target ratio."""
    if ratio >= 0.9:
        return "Adequate"
    elif ratio >= 0.6:
        return "Low"
    return "Missing"


def _priority_for_status(status: str, is_critical: bool = False) -> str:
    """Determine priority based on status."""
    if status == "Missing":
        return "urgent" if is_critical else "high"
    elif status == "Low":
        return "high" if is_critical else "medium"
    return "ok"


def _safe_ratio(actual: float, target: float) -> float:
    """Safe division for ratio calculation."""
    if not target:
        return 1.0
    return actual / target


# ─── Step 3e: Main Analysis Function ────────────────────────────────

async def analyze_nutrition(db: Session, pet_id) -> dict:
    """
    Analyze a pet's nutrition based on diet items, product catalog, and AI.

    Returns a comprehensive breakdown with macros, vitamins, minerals,
    improvements, and personalized recommendation.
    """
    # Get pet info
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise ValueError("Pet not found")

    breed_key = (pet.breed or "").lower().strip()

    # All DB reads done synchronously up front
    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .all()
    )
    condition_names = [c.name.lower() for c in conditions]
    has_hip_dysplasia = any("hip" in c or "dysplasia" in c for c in condition_names)

    diet_items = (
        db.query(DietItem)
        .filter(DietItem.pet_id == pet_id)
        .all()
    )

    # The new cart-rules product tables (product_food / product_supplement)
    # no longer carry per-SKU nutrition. All diet items go through AI
    # estimation (cached in food_nutrition_cache).
    unmatched_items: list = list(diet_items)

    # Fire breed-targets lookup and all per-item AI estimations in parallel.
    # Pass the full pet context (species, breed, weight, age, gender, and any
    # diagnosed conditions) so estimates are tailored rather than generic.
    pet_weight_kg = float(pet.weight) if getattr(pet, "weight", None) else None
    pet_age_desc = _calculate_age_description(pet.dob)
    pet_gender = getattr(pet, "gender", None)
    condition_full_names = [c.name for c in conditions] if conditions else []

    # Run targets lookup and all food estimations in parallel.
    # All DB operations inside these coroutines are synchronous (SQLAlchemy sync
    # session), so they only yield control during Claude API calls — no concurrent
    # session mutations occur.
    async def _safe_targets() -> dict:
        try:
            return await get_nutrition_targets(
                db,
                pet.species,
                pet.breed,
                pet.dob,
                pet_weight_kg,
                pet_gender,
            )
        except Exception as e:
            logger.error("Nutrition target lookup failed in analysis: %s", e)
            return dict(DEFAULT_TARGETS)

    async def _safe_estimate(item: DietItem) -> dict | None:
        try:
            return await estimate_food_nutrition(
                db,
                item.label,
                item.type,
                species=pet.species,
                breed=pet.breed,
                weight_kg=pet_weight_kg,
                age_description=pet_age_desc,
                gender=pet_gender,
                conditions=condition_full_names,
                daily_portion_g=getattr(item, "daily_portion_g", None),
                detail=getattr(item, "detail", None),
            )
        except Exception as e:
            logger.error("Food estimation failed for %s: %s", item.label, e)
            return None

    parallel_results = await asyncio.gather(
        _safe_targets(),
        *(_safe_estimate(item) for item in unmatched_items),
    )
    targets: dict = parallel_results[0]
    estimations: list[dict | None] = list(parallel_results[1:])

    # Aggregate nutritional values
    actual = {
        "calories": 0, "protein": 0, "fat": 0, "fibre": 0,
        # Qualitative micronutrient gaps from prompt: {name: {status, severity_score}}
        # Status: "missing" | "low" | "sufficient"
        "gaps": {},
    }

    for estimated in estimations:
        if estimated:
            _accumulate_from_estimation(actual, estimated)

    # If no items at all, provide minimal estimates
    if not diet_items:
        pass  # actual stays at zeros — will show all gaps

    # Calculate calorie status
    target_cal = targets.get("calories", 1200)
    cal_ratio = actual["calories"] / target_cal if target_cal else 1
    cal_status = "adequate" if cal_ratio >= 0.9 else ("low" if cal_ratio >= 0.6 else "deficit")

    # Build macros array
    macros = _build_macros(actual, targets, breed_key)

    # Build vitamins, minerals, others dynamically from prompt gap output
    vitamins, minerals, others = _build_micronutrient_sections(actual, targets, has_hip_dysplasia)

    # Build improvements list
    all_nutrients = minerals + others + vitamins
    improvements = _build_improvements(all_nutrients)
    gap_count = sum(1 for n in all_nutrients if n.get("priority") in ("urgent", "high", "medium"))

    # Generate personalized recommendation via AI
    gap_summary = ", ".join(
        f"{n['name']} ({n['status'].lower()})"
        for n in all_nutrients
        if n.get("priority") in ("urgent", "high", "medium")
    ) or "none"

    split_items = split_diet_items_by_type(diet_items)
    food_labels = split_items["foods"] + split_items["other"]
    supplement_labels = split_items["supplements"]

    recommendation = await generate_recommendation(
        pet.name,
        pet.breed or "mixed breed",
        [c.name for c in conditions],
        gap_summary,
        foods=food_labels,
        supplements=supplement_labels,
    )

    # Overall assessment
    if gap_count == 0:
        overall_label = "excellent"
    elif gap_count <= 2:
        overall_label = "good"
    elif gap_count <= 4:
        overall_label = "moderate"
    else:
        overall_label = "needs_attention"

    breed_label = pet.breed or "your pet's breed"
    condition_context = " + " + conditions[0].name if conditions else ""

    # Build explicit diet summary describing current diet and its strengths
    if food_labels or supplement_labels:
        food_list = ", ".join(food_labels[:5]) if food_labels else "not provided"
        supplements_text = (
            f" Supplements: {', '.join(supplement_labels[:5])}."
            if supplement_labels else ""
        )
        # Strengths: nutrients the LLM explicitly marked as sufficient
        sufficient_nutrients = [
            _NUTRIENT_META[name]["display"]
            for name, gap in actual["gaps"].items()
            if gap.get("status") == "sufficient" and name in _NUTRIENT_META
        ]
        strength_text = (" Strengths: " + ", ".join(sufficient_nutrients) + ".") if sufficient_nutrients else ""
        diet_summary = f"Current food: {food_list}.{supplements_text}{strength_text}"
    else:
        diet_summary = "No diet items added yet. Add your pet's food in the Nutrition tab for a detailed analysis."

    return {
        "calories": {"actual": actual["calories"], "target": target_cal, "status": cal_status},
        "macros": macros,
        "vitamins": vitamins,
        "minerals": minerals,
        "others": others,
        "improvements": improvements,
        "overall_label": overall_label,
        "recommendation": recommendation,
        "diet_summary": diet_summary,
        "analysis_context": f"Analysis based on {breed_label} breed profile{condition_context}",
        "gap_count": gap_count,
    }


# ─── Accumulation Helpers ────────────────────────────────────────────

def _accumulate_from_estimation(actual: dict, est: dict) -> None:
    """Accumulate nutritional values from AI-estimated food nutrition.

    Handles the new prompt output format:
    - Macros: calories_per_day, protein_pct, fat_pct, fibre_pct (numeric)
    - Micronutrients: micronutrient_gaps array (qualitative status + severity_score)
    """
    actual["calories"] += int(est.get("calories_per_day", 0) or est.get("calories_per_serving", 0))
    actual["protein"] = max(actual["protein"], float(est.get("protein_pct", 0)))
    actual["fat"] = max(actual["fat"], float(est.get("fat_pct", 0)))
    actual["fibre"] = max(actual["fibre"], float(est.get("fibre_pct", 0)))

    # Merge micronutrient gaps — worst status (highest severity_score) wins
    # when multiple foods report the same nutrient. Supplement suggestion is
    # carried from whichever food item had the highest severity.
    for gap in est.get("micronutrient_gaps", []):
        name = gap.get("name", "")
        status = gap.get("status", "")
        severity = float(gap.get("severity_score", 0))
        supplement = gap.get("supplement") or None
        reason = gap.get("reason") or None
        if name and status in ("missing", "low", "sufficient"):
            existing = actual["gaps"].get(name)
            if existing is None or severity > existing["severity_score"]:
                actual["gaps"][name] = {
                    "status": status,
                    "severity_score": severity,
                    "supplement": supplement,
                    "reason": reason,
                }


# ─── Builder Helpers ─────────────────────────────────────────────────

def _status_from_gap(gaps: dict, name: str, default: str = "Adequate") -> str:
    """Translate qualitative gap status to display status string.

    Falls back to `default` (Adequate) when the nutrient is not flagged as a gap,
    meaning the prompt considered it sufficient or did not assess it.
    """
    gap = gaps.get(name)
    if not gap:
        return default
    return {"missing": "Missing", "low": "Low", "sufficient": "Adequate"}.get(
        gap.get("status", "sufficient"), "Adequate"
    )


def _build_macros(actual: dict, targets: dict, breed_key: str) -> list[dict]:
    """Build macronutrients array for the response.

    Returns 4 macros showing LLM API percentages directly:
    protein_pct, fat_pct, fibre_pct.
    """
    return [
        {
            "name": "Protein", "icon": "\U0001f969",
            "value": actual["protein"], "unit": "%",
        },
        {
            "name": "Fat", "icon": "\U0001f9c8",
            "value": actual["fat"], "unit": "%",
        },
        {
            "name": "Fibre", "icon": "\U0001f966",
            "value": actual["fibre"], "unit": "%",
        },
    ]


# ─── Nutrient Metadata Registry ──────────────────────────────────────
# Maps prompt nutrient names → display metadata and category assignment.
# "fibre" is excluded here because it appears as a macro donut chart instead.
_NUTRIENT_META: dict[str, dict] = {
    # reason is intentionally absent — it comes from the LLM prompt response per gap.
    # Only display metadata (name, icon, category) and target lookup are defined here.
    "vitamin_e":   {"display": "Vitamin E",   "icon": "\U0001f33f", "category": "vitamins",
                    "target_key": "vitamin_e", "default_target": 300, "hip_critical": False},
    "vitamin_d3":  {"display": "Vitamin D3",  "icon": "\u2600\ufe0f", "category": "vitamins",
                    "target_key": "vitamin_d3", "default_target": 400, "hip_critical": False},
    "glucosamine": {"display": "Glucosamine", "icon": "\U0001f9b4", "category": "minerals",
                    "target_key": "glucosamine", "default_target": 500, "hip_critical": True},
    "calcium":     {"display": "Calcium",     "icon": "\U0001f9b7", "category": "minerals",
                    "target_key": "calcium",    "default_target": 1.0, "hip_critical": False},
    "phosphorus":  {"display": "Phosphorus",  "icon": "\u26a1",      "category": "minerals",
                    "target_key": "phosphorus", "default_target": 0.8, "hip_critical": False},
    "iron":        {"display": "Iron",        "icon": "\U0001f9a8",  "category": "minerals",
                    "target_key": "iron",       "default_target": 80,  "hip_critical": False},
    "zinc":        {"display": "Zinc",        "icon": "\U0001f9f2",  "category": "minerals",
                    "target_key": "zinc",       "default_target": 100, "hip_critical": False},
    "omega_3":     {"display": "Omega-3",     "icon": "\U0001f41f",  "category": "others",
                    "target_key": "omega_3",    "default_target": 300, "hip_critical": True},
    "omega_6":     {"display": "Omega-6",     "icon": "\U0001f33b",  "category": "others",
                    "target_key": "omega_6",    "default_target": 1500, "hip_critical": False},
    "taurine":     {"display": "Taurine",     "icon": "\U0001f496",  "category": "others",
                    "target_key": "taurine",    "default_target": 0,   "hip_critical": False},
}


def _build_micronutrient_sections(
    actual: dict, targets: dict, has_hip_dysplasia: bool
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Build vitamins, minerals, and others arrays dynamically from the prompt's
    micronutrient_gaps. Only nutrients that the prompt flagged appear in the output;
    nothing is hardcoded.

    Returns (vitamins, minerals, others) tuple.
    """
    gaps = actual.get("gaps", {})
    vitamins: list[dict] = []
    minerals: list[dict] = []
    others: list[dict] = []

    for nutrient_key, gap_data in gaps.items():
        meta = _NUTRIENT_META.get(nutrient_key)
        if not meta:
            continue  # Unknown nutrient name — skip

        status = _status_from_gap(gaps, nutrient_key)
        is_critical = has_hip_dysplasia and meta.get("hip_critical", False)
        priority = _priority_for_status(status, is_critical=is_critical)
        default_target = float(targets.get(meta["target_key"], meta["default_target"]))

        # Supplement and reason come from the LLM prompt response, not hardcoded
        supplement = gap_data.get("supplement") or None
        reason = gap_data.get("reason") or None

        item: dict = {
            "name": meta["display"],
            "icon": meta["icon"],
            "status": status,
            "priority": priority,
            "reason": reason,   # LLM-provided; None when not returned by prompt
            "supplement": supplement,
            "price": None,      # Pricing not provided by prompt
        }

        category = meta["category"]
        if category == "vitamins":
            vitamins.append(item)
        elif category == "minerals":
            item.update({"actual": 0, "target": default_target})
            minerals.append(item)
        else:
            item.update({"actual": 0, "target": default_target})
            others.append(item)

    return vitamins, minerals, others


def _build_improvements(all_nutrients: list[dict]) -> list[dict]:
    """Build sorted improvements list from all nutrient arrays."""
    improvements = []
    gap_colors = {"urgent": "#FF3B30", "high": "#FF9500", "medium": "#FFCC00"}

    sorted_nutrients = sorted(
        all_nutrients,
        key=lambda x: {"urgent": 0, "high": 1, "medium": 2}.get(x.get("priority", "ok"), 3),
    )

    for n in sorted_nutrients:
        if n.get("priority") in ("urgent", "high", "medium"):
            dot = gap_colors.get(n["priority"], "#FFCC00")
            reason = n.get("reason", f"{n['name']} supplementation recommended")
            supplement_text = f" \u2192 {n['supplement']}" if n.get("supplement") else ""
            improvements.append({
                "dot": dot,
                "text": f"{n['name']} {n['status'].lower()}{supplement_text} - {reason}",
            })

    return improvements


# ─── Diet Summary for Dashboard Donut ────────────────────────────────

# Threshold boundary constants for donut macro color coding
_PCT_OVER_AMBER = 110.0   # Protein / Fat / Fibre start of amber (over)
_PCT_UNDER_RED = 80.0     # Protein / Fat / Fibre start of red (under)
_PCT_CAL_AMBER = 100.0    # Calories: exceed target → amber


def _diet_summary_threshold(macro_name: str, pct_of_need: float) -> tuple[str, str]:
    """
    Compute color and note for a single donut macro based on % of daily need.

    Rules (guardrail-compliant):
    - Calories:  >100 % → amber / "Slightly over target"
                 ≤100 % → green / "On track"
    - Protein / Fat / Fibre:
                 >110 % → amber / "Slightly over"
                 <80  % → red   / "Deficient"
                 80–110% → green / "On track"
    - Green is NEVER returned for >110 %.
    """
    if macro_name == "Calories":
        if pct_of_need > _PCT_CAL_AMBER:
            return "amber", "Slightly over target"
        return "green", "On track"

    # Protein, Fat, and Fibre share the same thresholds
    if pct_of_need > _PCT_OVER_AMBER:
        return "amber", "Slightly over"
    if pct_of_need < _PCT_UNDER_RED:
        return "red", "Deficient"
    return "green", "On track"


async def get_diet_summary(db: Session, pet) -> dict:
    """
    Format existing nutrition analysis as donut summaries with guardrail thresholds.

    Calls the full analyze_nutrition pipeline, then re-formats the result into
    4 donut-chart macro segments (Calories, Protein, Fat, Fibre) plus up to 3
    missing micronutrients for the dashboard card.

    The 4 macros map directly to the new prompt output fields:
    calories_per_day, protein_pct, fat_pct, fibre_pct.

    Returns:
        {
            "macros": [
                {"name": str, "pct_of_need": float, "color": str, "note": str},
                ...   # 4 items: Calories, Protein, Fat, Fibre
            ],
            "missing_micros": [
                {"icon": str, "name": str, "reason": str},
                ...   # max 3, sorted by priority (urgent → high → medium)
            ],
        }

    Falls back to empty lists if the analysis pipeline raises an exception.
    """
    try:
        analysis = await analyze_nutrition(db, pet.id)
    except Exception as e:
        logger.error("get_diet_summary: analyze_nutrition failed for pet %s: %s", pet.id, e)
        return {"macros": [], "missing_micros": []}

    # --- Calories ---
    cal_info = analysis.get("calories", {})
    cal_actual = cal_info.get("actual", 0)
    cal_target = cal_info.get("target", DEFAULT_TARGETS["calories"])

    # --- Macros list from analyze_nutrition (Protein, Fat, Fibre) ---
    macros_list = analysis.get("macros", [])

    def _find_macro(name: str) -> dict:
        return next((m for m in macros_list if m.get("name") == name), {})

    protein_m = _find_macro("Protein")
    fat_m = _find_macro("Fat")
    fibre_m = _find_macro("Fibre")

    def _safe_pct(actual: float, target: float) -> float:
        """Return % of daily target, capped floor at 0."""
        if not target:
            return 100.0
        return round(max(0.0, actual / target) * 100, 1)

    cal_pct = _safe_pct(cal_actual, cal_target)
    protein_pct = _safe_pct(
        float(protein_m.get("actual", 0)),
        float(protein_m.get("target", DEFAULT_TARGETS["protein"])),
    )
    fat_pct = _safe_pct(
        float(fat_m.get("actual", 0)),
        float(fat_m.get("target", DEFAULT_TARGETS["fat"])),
    )
    fibre_pct = _safe_pct(
        float(fibre_m.get("actual", 0)),
        float(fibre_m.get("target", DEFAULT_TARGETS["fibre"])),
    )

    # Build 4 donut segments: Calories, Protein, Fat, Fibre
    donut_macros: list[dict] = []
    for macro_name, pct in [
        ("Calories", cal_pct),
        ("Protein", protein_pct),
        ("Fat", fat_pct),
        ("Fibre", fibre_pct),
    ]:
        color, note = _diet_summary_threshold(macro_name, pct)
        donut_macros.append({
            "name": macro_name,
            "pct_of_need": pct,
            "color": color,
            "note": note,
        })

    # --- Missing micronutrients (max 3) from gap analysis ---
    # Combine minerals + others + vitamins; filter to non-ok priorities
    all_micros = (
        analysis.get("minerals", [])
        + analysis.get("others", [])
        + analysis.get("vitamins", [])
    )
    _priority_rank = {"urgent": 0, "high": 1, "medium": 2}
    deficient = sorted(
        [n for n in all_micros if n.get("priority") in _priority_rank],
        key=lambda n: _priority_rank.get(n.get("priority", "ok"), 3),
    )
    missing_micros = [
        {
            "icon": n.get("icon", "\u26a0\ufe0f"),
            "name": n["name"],
            "reason": n.get("reason") or None,
            # LLM-recommended product name; used as care plan item name when present
            "supplement": n.get("supplement") or None,
        }
        for n in deficient[:3]
    ]

    return {"macros": donut_macros, "missing_micros": missing_micros}
