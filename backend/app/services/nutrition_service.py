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
from app.services.diet_service import (
    expand_supplement_labels,
    resolve_supplement_coverage,
    split_diet_items_by_type,
)
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
    """Return a cached AI client (provider-agnostic, created on first call)."""
    global _openai_nutrition_client
    if _openai_nutrition_client is None:
        from app.utils.ai_client import get_ai_client  # noqa: PLC0415
        _openai_nutrition_client = get_ai_client()
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


# ─── JSON / weight helpers ──────────────────────────────────────────

def _parse_json_from_response(raw: str) -> dict | None:
    """Parse JSON from AI response, stripping markdown code fences and trailing text."""
    if not raw or not isinstance(raw, str):
        return None

    # Strip markdown code fence wrappers: ```json ... ``` or ``` ... ```
    # Also handle preamble text before the fence (e.g. "Here is the result:\n```json\n{...}")
    text = raw.strip()
    fence_pos = text.find("```")
    if fence_pos > 0:
        text = text[fence_pos:]
    if text.startswith("```"):
        # Remove opening fence (optionally with language tag like ```json)
        lines = text.split("\n")
        # Only strip the last line if it is a closing fence — not JSON content.
        # If GPT omits the closing fence (truncated response), lines[-1] is
        # actual JSON and must be kept.
        has_closing_fence = lines[-1].strip() == "```"
        if len(lines) > 1:
            end = -1 if has_closing_fence else len(lines)
            text = "\n".join(lines[1:end])
        else:
            text = ""

    text = text.strip()
    if not text:
        return None

    # Truncate any trailing text after the last closing brace (LLM sometimes
    # adds commentary or URGENT RECOMMENDATION notes after the JSON object).
    last_brace = text.rfind("}")
    if last_brace != -1:
        text = text[: last_brace + 1]

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


# ─── Step 3c: Combined Meal Analysis ────────────────────────────────
# Analyses ALL diet items together in a single LLM call so the model can
# see the full diet, weight macros by caloric contribution, and assess
# micronutrients against what the combined diet actually provides.

COMBINED_MEAL_SYSTEM_PROMPT = (
    "You are a board-certified veterinary nutritionist.\n"
    "Your task: Given food items, pet details, and optionally user-provided quantities, estimate\n"
    "DAILY nutritional intake and identify the most important nutritional gaps.\n\n"
    "-----------------------------------\n"
    "STEP 1 — RESOLVE FOOD IDENTITY\n"
    "-----------------------------------\n"
    "- Identify the most likely specific product based on: food name, species, age (puppy / adult / senior)\n"
    "  Example: \"Pedigree\" + adult dog → Pedigree Adult Dog Food\n"
    "- If multiple variants are possible, choose the most common one for that species and age,\n"
    "  and note it in resolved_name. Reduce product_confidence only — do NOT reduce overall\n"
    "  analysis confidence if serving size can still be determined via brand feeding guidelines (see Step 2 Case B).\n"
    "- If product identity cannot be resolved to any specific brand at all, reduce confidence and apply the Fail-Safe.\n"
    "- Before determining life stage, estimate age-to-life-stage mapping using breed-specific thresholds —\n"
    "  large and giant breeds are considered senior earlier (6–7 years) than small breeds (10–11 years).\n"
    "- If user mentions a vet-prescribed diet, extract and store the prescription_context\n"
    "  (e.g., \"low protein for kidney disease\", \"hypoallergenic for allergies\").\n"
    "- This context must carry forward into gap analysis and improvement framing.\n\n"
    "-----------------------------------\n"
    "STEP 2 — DETERMINE SERVING SIZE\n"
    "-----------------------------------\n\n"
    "CASE A: USER PROVIDED QUANTITY (any food)\n"
    "- Use EXACTLY the user-provided quantity (e.g., \"2 cups/day\", \"1 bowl/day\").\n"
    "- Do NOT override, scale, or reinterpret it.\n\n"
    "CASE B: COMMERCIAL / PACKAGED FOOD, NO QUANTITY PROVIDED\n"
    "- Use ONLY official brand feeding guidelines.\n"
    "- Use pet weight and age ONLY to select the correct feeding range.\n"
    "- Choose a reasonable midpoint within that range.\n"
    "- Do NOT invent or extrapolate beyond brand guidance.\n\n"
    "⚠ If the pet's age and weight are provided, this is sufficient to determine serving size from brand\n"
    "feeding guidelines. Set confidence ≥ 0.75 in this case. Do NOT treat the absence of a user-provided\n"
    "quantity as missing serving size — brand guidelines ARE the serving size source for commercial food.\n\n"
    "CASE C: HOMEMADE / GENERIC FOOD, NO QUANTITY PROVIDED\n"
    "- DO NOT estimate or assume any serving size.\n"
    "- Mark portion as UNKNOWN.\n"
    "If serving size cannot be determined with confidence:\n"
    "- Set confidence < 0.6.\n"
    "- RETURN NO ANALYSIS (see Fail-Safe).\n"
    "⚠ This does NOT apply to Case B when age and weight are provided. Commercial packaged food with\n"
    "known brand guidelines never has a \"missing\" serving size if the pet's weight and age are available.\n\n"
    "-----------------------------------\n"
    "STEP 3 — MIXED DIET HANDLING\n"
    "-----------------------------------\n\n"
    "If BOTH commercial food AND homemade food are present:\n"
    "Treat commercial food as the PRIMARY diet anchor:\n"
    "- Use it for calories_per_day and macronutrient percentages.\n"
    "For homemade food WITHOUT quantity:\n"
    "- DO NOT include in calories or macronutrient calculations.\n"
    "- ONLY use it for qualitative micronutrient signals if possible.\n"
    "If homemade food HAS quantity:\n"
    "- Include it fully in all calculations.\n\n"
    "-----------------------------------\n"
    "STEP 4 — NUTRITION ESTIMATION\n"
    "-----------------------------------\n"
    "- Estimate TOTAL DAILY intake based on determined serving size.\n"
    "- Ensure values are realistic and internally consistent.\n"
    "- Prevent extreme or biologically impossible outputs.\n"
    "- Total calories must fall within realistic daily intake ranges.\n"
    "- For protein_pct, fat_pct, carbs_pct, fibre_pct: express each as\n"
    "  % of the pet's DAILY REQUIREMENT met by this diet (NOT % of calories).\n"
    "  Example: if a 22kg adult dog needs 50g protein/day and the diet provides 33g → protein_pct = 66.\n"
    "  Values can exceed 100 if the diet overshoots the requirement.\n\n"
    "-----------------------------------\n"
    "STEP 5 — SHOW WARNING FLAG\n"
    "-----------------------------------\n\n"
    "Set show_warning: true ONLY if ANY of the following apply:\n"
    "- Diet includes homemade or generic food (with or without quantity).\n"
    "- Diet is mixed (commercial + homemade).\n"
    "- Commercial food was identified without an exact SKU (brand-level match only).\n"
    "- Confidence < 0.6.\n\n"
    "Set show_warning: false if:\n"
    "- Diet is 100% commercial food AND exact SKU was matched with confidence.\n\n"
    "When show_warning is true, select warning_message based on diet type:\n"
    "  Homemade / generic food only:\n"
    "    \"Estimates vary by portion, cooking method and ingredient type.\"\n"
    "  Mixed diet (commercial + homemade):\n"
    "    \"Commercial values from brand data; home-cooked portions are approximated.\"\n"
    "  Commercial food, brand-level match only (no exact SKU):\n"
    "    \"Values based on brand averages. May vary by product variant.\"\n"
    "  Confidence < 0.6:\n"
    "    \"Insufficient data for diet analysis. Share food portions and/or brand SKU on WhatsApp.\"\n\n"
    "When show_warning is false:\n"
    "  Omit warning_message from output entirely.\n\n"
    "-----------------------------------\n"
    "STEP 6 — MICRONUTRIENT GAP ANALYSIS\n"
    "-----------------------------------\n\n"
    "SUPPLEMENT COVERAGE RULE (Check First):\n"
    "Before assigning any nutrient status, check the supplements input.\n"
    "For any nutrient covered by a supplement, assign status \"sufficient\" with a low severity_score (0.1–0.2).\n"
    "Do NOT flag it as a gap and do NOT recommend it in top_improvements.\n\n"
    "- Identify micronutrient gaps dynamically based on pet nutritional requirements, current diet\n"
    "  composition, and pet life stage.\n\n"
    "Life stage MUST influence severity scoring:\n"
    "- Puppies: prioritise calcium, phosphorus, omega_3 (DHA), zinc.\n"
    "- Adults: prioritise omega_3, taurine, fibre, zinc.\n"
    "- Seniors: prioritise omega_3, glucosamine, vitamin_d3, fibre.\n\n"
    "Use ONLY this controlled list of nutrient names:\n"
    "  omega_3, omega_6, vitamin_e, vitamin_d3, glucosamine, calcium, phosphorus, iron, zinc, taurine, fibre\n\n"
    "- For each nutrient, assign ONLY one of: \"sufficient\", \"low\", \"missing\".\n"
    "- DO NOT output \"unknown\" under any condition.\n"
    "- DO NOT include nutrients where status cannot be confidently determined.\n"
    "- DO NOT output numeric values, units, or requirements for micronutrients.\n"
    "- Micronutrients are strictly qualitative signals.\n\n"
    "Assign a severity_score (0–1) based on:\n"
    "- Deficiency severity (missing > low > sufficient).\n"
    "- Relevance to pet conditions and life stage.\n"
    "- Confidence in assessment.\n\n"
    "If a nutrient gap is intentional due to a vet-prescribed diet:\n"
    "- Do NOT increase severity_score for that nutrient.\n"
    "- Add prescribed: true to that nutrient's output.\n\n"
    "-----------------------------------\n"
    "STEP 7 — SELECT TOP 3 PRIORITY IMPROVEMENTS\n"
    "-----------------------------------\n\n"
    "Identify the TOP 3 most important improvements across ALL of:\n"
    "- Calorie adequacy (is total intake significantly above or below daily requirement?).\n"
    "- Macronutrients (protein, fat, carbs, fibre — flag only if meaningfully off target).\n"
    "- Micronutrients (from gap analysis, life-stage weighted).\n\n"
    "Rank by clinical importance to this specific pet.\n"
    "For each improvement:\n"
    "- title: short label (e.g. \"Protein too low\", \"Calcium missing\", \"Calories under target\").\n"
    "- detail: ONE line only — specific, actionable, no more than 15 words.\n"
    "- severity: \"high\" | \"medium\" | \"prescribed\".\n\n"
    "If an improvement relates to a prescribed nutrient gap:\n"
    "- DO NOT suppress it — include it.\n"
    "- Set severity to \"prescribed\".\n"
    "- Frame detail neutrally, e.g. \"Low by prescription — continue monitoring with your vet\".\n"
    "- Never suggest correcting a prescribed gap.\n\n"
    "- DO NOT pad to 3 if fewer than 3 genuine issues exist.\n"
    "- DO NOT include improvements for nutrients already marked sufficient.\n"
    "top_improvements must span calories, macros, AND micros — do not pull from one category only.\n\n"
    "-----------------------------------\n"
    "CRITICAL RULES\n"
    "-----------------------------------\n\n"
    "- NEVER estimate serving size arbitrarily.\n"
    "- NEVER assume portion size for homemade food.\n"
    "- NEVER scale portions beyond brand guidelines.\n"
    "- NEVER include homemade food in calorie or macro calculations unless quantity is provided.\n"
    "- NEVER fabricate precision where data is missing.\n"
    "- NEVER suggest correcting a gap that is vet-prescribed.\n"
    "- Maintain internal consistency across all outputs.\n"
    "- top_improvements must span calories, macros, AND micros — do not pull from one category only.\n"
    "- detail in top_improvements must be ONE line, max 15 words, specific and actionable.\n\n"
    "-----------------------------------\n"
    "FAIL-SAFE\n"
    "-----------------------------------\n\n"
    "Return INSUFFICIENT_DATA ONLY IF no food in the list has determinable identity AND serving size.\n"
    "If at least ONE commercial food can be analysed via brand feeding guidelines, return results based\n"
    "on what is known — do NOT return INSUFFICIENT_DATA because homemade or generic add-ons lack quantities.\n\n"
    "Trigger INSUFFICIENT_DATA only when ALL foods in the list meet one of these conditions:\n"
    "  (a) Cannot be resolved to any specific brand at all, OR\n"
    "  (b) Are homemade/generic with no user-provided quantity.\n\n"
    "⚠ Homemade or generic foods without quantities do NOT trigger this fail-safe.\n"
    "  They follow Case C rules: excluded from calorie/macro calculations, show_warning set to true.\n"
    "⚠ For commercial packaged food where the pet's age and weight are provided, serving size is NEVER\n"
    "  treated as missing. Brand feeding guidelines apply and the Fail-Safe does not trigger on this basis alone.\n\n"
    '{"confidence": <value>, "show_warning": true, '
    '"warning_message": "Insufficient data for diet analysis. Share food portions and/or brand SKU on WhatsApp.", '
    '"error": "INSUFFICIENT_DATA"}\n\n'
    "-----------------------------------\n"
    "OUTPUT FORMAT\n"
    "-----------------------------------\n\n"
    "Return ONLY valid JSON with these exact keys:\n\n"
    "{\n"
    '  "resolved_name": string,\n'
    '  "confidence": float (0-1),\n'
    '  "serving_description": string,\n'
    '  "prescription_context": string (omit if not applicable),\n'
    '  "show_warning": boolean,\n'
    '  "warning_message": string (omit if show_warning is false),\n'
    '  "calories_per_day": int,\n'
    '  "calorie_target": int,\n'
    '  "calorie_gap_pct": int (positive = over, negative = under),\n'
    '  "protein_pct": float (% of daily protein REQUIREMENT met, e.g. 65 means 65% of need — NOT % of calories),\n'
    '  "fat_pct": float (% of daily fat REQUIREMENT met),\n'
    '  "carbs_pct": float (% of daily carbohydrate REQUIREMENT met),\n'
    '  "fibre_pct": float (% of daily fibre REQUIREMENT met),\n'
    '  "micronutrient_gaps": [\n'
    '    {\n'
    '      "name": string,\n'
    '      "status": "sufficient" | "low" | "missing",\n'
    '      "severity_score": float (0-1),\n'
    '      "prescribed": boolean (omit if false)\n'
    '    }\n'
    "  ],\n"
    '  "top_improvements": [\n'
    '    {\n'
    '      "title": string,\n'
    '      "detail": string (ONE line, max 15 words),\n'
    '      "severity": "high" | "medium" | "prescribed"\n'
    '    }\n'
    "  ]\n"
    "}\n\n"
    "CRITICAL:\n"
    "- severity_score MUST be a float between 0.0 and 1.0 (e.g. 0.72, NOT 7 or 72)\n"
    "- top_improvements MUST be an array (empty array [] if no improvements needed)\n"
    "- Return ONLY the JSON object — no text, notes, or recommendations after the closing brace\n"
    "- No extra fields beyond the schema\n"
    "- No markdown, no code fences, no explanation"
)


async def _call_openai_combined_meal_estimation(
    diet_items: list,
    species: str | None,
    breed: str | None,
    weight_kg: float | None,
    age_description: str | None,
    gender: str | None,
    conditions: list[str] | None,
) -> dict | None:
    """Call LLM with ALL diet items in a single prompt for holistic combined meal analysis."""
    client = _get_openai_client()

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
    prompt_parts.append("\nDiet items (complete daily intake):")
    for i, item in enumerate(diet_items, 1):
        line = f"{i}. {item.label} (type: {item.type})"
        portion_g = getattr(item, "daily_portion_g", None)
        detail = getattr(item, "detail", None)
        detail_str = str(detail).strip() if detail else ""

        # Detect vet-prescribed tag embedded in detail by either source
        # (document extraction appends "· Vet prescribed (doc)" and chat flow
        # appends "· Vet prescribed (chat)").
        is_vet = "vet prescribed" in detail_str.lower()
        # Strip the annotation so the remaining text is a clean quantity/instruction.
        clean_detail = detail_str
        if is_vet:
            # Remove the tag suffix (everything from "· Vet prescribed" onward)
            for tag in ("· Vet prescribed", "·Vet prescribed", "Vet prescribed"):
                idx = clean_detail.lower().find(tag.lower())
                if idx != -1:
                    clean_detail = clean_detail[:idx].strip().rstrip("·").strip()
                    break

        vet_suffix = " [Vet prescribed]" if is_vet else ""

        if portion_g and portion_g > 0:
            line += f" — Daily portion: {portion_g}g{vet_suffix}"
        elif clean_detail:
            line += f" — User-provided quantity: {clean_detail}{vet_suffix}"
        elif is_vet:
            line += f" — Quantity: not specified{vet_suffix}"
        else:
            line += " — Quantity: not specified"
        # Append coverage note for ambiguous generic supplement names so the
        # LLM does not flag covered sub-types (e.g. Omega-3/6/9) as missing.
        if item.type == "supplement":
            coverage = resolve_supplement_coverage(item.label or "")
            if coverage:
                line += f" [covers: {', '.join(coverage)}]"
        prompt_parts.append(line)

    user_prompt = "\n".join(prompt_parts)

    response = await client.messages.create(
        model=OPENAI_QUERY_MODEL,
        temperature=0.0,
        max_tokens=OPENAI_FOOD_ESTIMATION_MAX_TOKENS,
        system=COMBINED_MEAL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    if response.stop_reason == "max_tokens":
        logger.warning(
            "Combined meal estimation truncated at max_tokens=%d — increase OPENAI_FOOD_ESTIMATION_MAX_TOKENS",
            OPENAI_FOOD_ESTIMATION_MAX_TOKENS,
        )
    raw = response.content[0].text
    logger.debug("Combined meal estimation raw: %s", raw)
    result = _parse_json_from_response(raw)
    if result is None:
        logger.error("Failed to parse combined meal estimation — raw: %s", raw)
        return None
    if result.get("error") == "INSUFFICIENT_DATA":
        logger.warning("Insufficient data for combined meal: %s", result.get("message"))
        return None
    confidence = result.get("confidence", 1.0)
    if isinstance(confidence, (int, float)) and confidence < 0.15:
        # Only discard truly unusable estimates (< 0.15). Commercial foods without
        # explicit portions still reach 0.2–0.4 via official brand feeding guidelines
        # (CASE B) and produce useful calorie/macro data.
        logger.debug("Very low confidence (%.2f) for combined meal estimation — skipping", confidence)
        return None
    return result


async def estimate_complete_meal_nutrition(
    db,
    diet_items: list,
    species: str | None,
    breed: str | None,
    weight_kg: float | None,
    age_description: str | None,
    gender: str | None,
    conditions: list[str] | None,
) -> dict | None:
    """
    Estimate nutrition for ALL diet items in one combined LLM call.

    Cache key is a hash of all food items (label + type + detail) + pet profile,
    stored in food_nutrition_cache with food_type='combined_meal'.
    """
    species_norm = (species or "dog").lower().strip()
    bucket = _weight_bucket(weight_kg)
    conditions_sorted = sorted(c.lower().strip() for c in (conditions or []) if c)
    cond_hash = (
        hashlib.sha1(",".join(conditions_sorted).encode()).hexdigest()[:8]
        if conditions_sorted else "none"
    )
    # Build a stable, sorted hash of all food items
    food_fingerprints = sorted(
        f"{getattr(item, 'label', '').lower().strip()}|{getattr(item, 'type', '')}|{str(getattr(item, 'detail', '') or '').lower().strip()}"
        for item in diet_items
    )
    foods_hash = hashlib.sha1("|".join(food_fingerprints).encode()).hexdigest()[:12]
    cache_key = f"v1|meal|{species_norm}|{bucket}|{cond_hash}|{foods_hash}"
    food_type = "combined_meal"

    # 1. Check cache
    try:
        cached = (
            db.query(FoodNutritionCache)
            .filter(
                FoodNutritionCache.food_label_normalized == cache_key,
                FoodNutritionCache.food_type == food_type,
            )
            .first()
        )
        if cached:
            staleness_cutoff = datetime.utcnow() - timedelta(days=FOOD_CACHE_STALENESS_DAYS)
            if cached.created_at.replace(tzinfo=None) > staleness_cutoff:
                logger.info("Combined meal cache hit: %s", cache_key)
                return cached.nutrition_json
            else:
                db.delete(cached)
                db.commit()
    except Exception as e:
        logger.warning("Combined meal cache lookup failed: %s", e)

    # 2. Call LLM
    try:
        result = await retry_openai_call(
            _call_openai_combined_meal_estimation,
            diet_items, species, breed, weight_kg, age_description, gender, conditions_sorted,
        )
    except Exception as e:
        logger.error("Combined meal estimation failed: %s", e)
        return None

    if not result:
        return None

    # 3. Cache result
    try:
        db.add(FoodNutritionCache(
            food_label_normalized=cache_key,
            food_type=food_type,
            nutrition_json=result,
        ))
        db.commit()
        logger.info("Cached combined meal nutrition: %s", cache_key)
    except Exception as e:
        db.rollback()
        logger.info("Combined meal cache write conflict: %s", e)

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

    pet_weight_kg = float(pet.weight) if getattr(pet, "weight", None) else None
    pet_age_desc = _calculate_age_description(pet.dob)
    pet_gender = getattr(pet, "gender", None)
    condition_full_names = [c.name for c in conditions] if conditions else []

    # Run targets lookup and combined meal estimation in parallel.
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

    async def _safe_meal_estimate() -> dict | None:
        try:
            return await estimate_complete_meal_nutrition(
                db,
                diet_items,
                species=pet.species,
                breed=pet.breed,
                weight_kg=pet_weight_kg,
                age_description=pet_age_desc,
                gender=pet_gender,
                conditions=condition_full_names,
            )
        except Exception as e:
            logger.error("Combined meal estimation failed: %s", e)
            return None

    targets, meal_result = await asyncio.gather(_safe_targets(), _safe_meal_estimate())

    # Populate actual values from combined meal result
    actual = {
        "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "fibre": 0,
        "gaps": {},
        "top_improvements": [],
        "llm_calories_per_day": None,
        "llm_calorie_target": None,
        "llm_calorie_gap_pct": None,
        "llm_serving_description": None,
        "llm_show_warning": None,
        "llm_warning_message": None,
    }

    if meal_result:
        _accumulate_from_estimation(actual, meal_result)

    # If no items at all, actual stays at zeros — will show all gaps
    if not diet_items:
        pass

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
    supplement_labels = expand_supplement_labels(split_items["supplements"])

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

    # ── New flat fields for DietAnalysisCard — all sourced from LLM ─────────
    food_label_str = actual.get("llm_serving_description") or (
        ", ".join(food_labels[:3]) if food_labels else None
    )
    calorie_gap_pct = actual.get("llm_calorie_gap_pct")
    show_warning = bool(actual.get("llm_show_warning")) if actual.get("llm_show_warning") is not None else False
    warning_message: str | None = actual.get("llm_warning_message") if show_warning else None

    # prescription_context: first vet-prescribed dietary condition, then fallback
    # to vet-tagged diet items (from document extraction or chat).
    _PRESCRIPTION_KEYWORDS = (
        "prescription", "renal", "kidney", "liver", "cardiac",
        "low fat", "hypoallergenic", "gastrointestinal", "urinary",
    )
    prescription_context: str | None = None
    for cond in conditions:
        if any(kw in cond.name.lower() for kw in _PRESCRIPTION_KEYWORDS):
            prescription_context = cond.name
            break

    if not prescription_context:
        vet_item_labels = [
            item.label for item in diet_items
            if "vet prescribed" in (item.detail or "").lower()
        ]
        if vet_item_labels:
            prescription_context = ", ".join(vet_item_labels[:3])

    # micronutrient_gaps flat array for DietAnalysisCard (non-sufficient only)
    micro_gaps_flat = [
        {
            "name": name,
            "status": gap["status"],
            "severity_score": gap["severity_score"],
            "prescribed": False,
        }
        for name, gap in actual["gaps"].items()
        if gap.get("status") != "sufficient"
    ]
    # Sort by severity_score descending
    micro_gaps_flat.sort(key=lambda g: g["severity_score"], reverse=True)

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
        # ── Legacy fields (kept for backward compat: get_diet_summary, product recs) ──
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
        "has_diet_items": bool(diet_items),
        # ── New flat fields for DietAnalysisCard — sourced from LLM ─────────
        "calories_per_day": actual.get("llm_calories_per_day") or actual["calories"],
        "calorie_target": actual.get("llm_calorie_target") or target_cal,
        "calorie_gap_pct": calorie_gap_pct,
        "food_label": food_label_str,
        "show_warning": show_warning,
        "warning_message": warning_message,
        "prescription_context": prescription_context,
        "protein_pct": actual["protein"],
        "fat_pct": actual["fat"],
        "carbs_pct": actual["carbs"],
        "fibre_pct": actual["fibre"],
        "micronutrient_gaps": micro_gaps_flat,
        "top_improvements": actual.get("top_improvements") or [],
    }


# ─── Accumulation Helpers ────────────────────────────────────────────

def _accumulate_from_estimation(actual: dict, est: dict) -> None:
    """Accumulate nutritional values from AI-estimated food nutrition.

    Handles the new prompt output format:
    - Macros: calories_per_day, protein_pct, fat_pct, carbs_pct, fibre_pct (numeric)
    - Micronutrients: micronutrient_gaps array (qualitative status + severity_score)
    - top_improvements: list of {title, detail, severity} from combined meal analysis
    """
    actual["calories"] += int(est.get("calories_per_day", 0) or est.get("calories_per_serving", 0))
    actual["protein"] = max(actual["protein"], float(est.get("protein_pct", 0)))
    actual["fat"] = max(actual["fat"], float(est.get("fat_pct", 0)))
    actual["carbs"] = max(actual.get("carbs", 0), float(est.get("carbs_pct", 0)))
    actual["fibre"] = max(actual["fibre"], float(est.get("fibre_pct", 0)))

    # Capture top_improvements from combined meal result (first non-empty result wins)
    if not actual.get("top_improvements") and est.get("top_improvements"):
        actual["top_improvements"] = est["top_improvements"]

    # Capture all LLM-computed display fields (first non-None result wins)
    if actual.get("llm_calories_per_day") is None and est.get("calories_per_day"):
        actual["llm_calories_per_day"] = est["calories_per_day"]
    if actual.get("llm_calorie_target") is None and est.get("calorie_target"):
        actual["llm_calorie_target"] = est["calorie_target"]
    if actual.get("llm_calorie_gap_pct") is None and est.get("calorie_gap_pct") is not None:
        actual["llm_calorie_gap_pct"] = est["calorie_gap_pct"]
    if actual.get("llm_serving_description") is None and est.get("serving_description"):
        actual["llm_serving_description"] = est["serving_description"]
    if actual.get("llm_show_warning") is None and est.get("show_warning") is not None:
        actual["llm_show_warning"] = est["show_warning"]
        actual["llm_warning_message"] = est.get("warning_message")

    # Merge micronutrient gaps — worst status (highest severity_score) wins
    # when multiple foods report the same nutrient. Supplement suggestion is
    # carried from whichever food item had the highest severity.
    for gap in est.get("micronutrient_gaps", []):
        name = gap.get("name", "")
        status = gap.get("status", "")
        severity = float(gap.get("severity_score", 0))
        if severity > 1.0:
            severity = severity / 10.0  # Normalize LLM returning 0-10 scale instead of 0-1
        severity = min(1.0, max(0.0, severity))
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

    Returns 3 macros (Protein, Fat, Fibre) with actual percentages and targets.
    Structure matches calories for consistency: {"name", "actual", "target"}.
    """
    return [
        {
            "name": "Protein",
            "actual": actual["protein"],
            "target": targets.get("protein", DEFAULT_TARGETS["protein"]),
        },
        {
            "name": "Fat",
            "actual": actual["fat"],
            "target": targets.get("fat", DEFAULT_TARGETS["fat"]),
        },
        {
            "name": "Fibre",
            "actual": actual["fibre"],
            "target": targets.get("fibre", DEFAULT_TARGETS["fibre"]),
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


async def get_diet_summary(db: Session, pet, analysis: dict | None = None) -> dict:
    """
    Format existing nutrition analysis as donut summaries with guardrail thresholds.

    Re-formats the result into 4 donut-chart macro segments (Calories, Protein,
    Fat, Fibre) plus up to 3 missing micronutrients for the dashboard card.

    If ``analysis`` is provided (pre-computed by the caller), it is used directly
    and no AI call is made. Otherwise, analyze_nutrition() is called internally.

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
        if analysis is None:
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
