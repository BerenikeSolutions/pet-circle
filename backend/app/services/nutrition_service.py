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
import json
import logging
import hashlib
import time
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.models.diet_item import DietItem
from app.models.product_catalog import ProductCatalog
from app.models.pet import Pet
from app.models.condition import Condition
from app.models.nutrition_target_cache import NutritionTargetCache
from app.models.food_nutrition_cache import FoodNutritionCache
from app.config import settings
from app.core.constants import (
    OPENAI_QUERY_MODEL,
    OPENAI_NUTRITION_LOOKUP_MAX_TOKENS,
    NUTRITION_CACHE_STALENESS_DAYS,
    OPENAI_FOOD_ESTIMATION_MAX_TOKENS,
    FOOD_CACHE_STALENESS_DAYS,
    OPENAI_NUTRITION_REC_MAX_TOKENS,
    OPENAI_NUTRITION_REC_TEMPERATURE,
)
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

# --- OpenAI client singleton (lazy) ---
_openai_nutrition_client = None


def _get_openai_client():
    """Return a cached AsyncOpenAI client (created on first call)."""
    global _openai_nutrition_client
    if _openai_nutrition_client is None:
        from openai import AsyncOpenAI
        _openai_nutrition_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
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
    """Human-readable age string for OpenAI prompts."""
    if not dob:
        return "unknown age"
    total_days = (date.today() - dob).days
    if total_days < 0:
        return "unknown age"
    years = total_days // 365
    months = (total_days % 365) // 30
    if years == 0:
        return f"{months} month{'s' if months != 1 else ''} old"
    elif months == 0:
        return f"{years} year{'s' if years != 1 else ''} old"
    return f"{years} year{'s' if years != 1 else ''} and {months} month{'s' if months != 1 else ''} old"


# --- System Prompts ---

NUTRITION_TARGET_SYSTEM_PROMPT = (
    "You are a board-certified veterinary nutritionist. Given a pet's species, breed, "
    "and age, return the recommended DAILY nutritional targets.\n\n"
    "Rules:\n"
    "- Return ONLY valid JSON with these exact keys:\n"
    "  calories (int, kcal/day), protein (int, % of diet), fat (int, %), carbs (int, %), "
    "fibre (int, %), moisture (int, %), calcium (float, %), phosphorus (float, %), "
    "omega_3 (int, mg/day), omega_6 (int, mg/day), vitamin_e (int, IU/day), "
    "vitamin_d3 (int, IU/day), glucosamine (int, mg/day), probiotics (bool, whether recommended)\n"
    "- Use established AAFCO/FEDIAF/NRC standards for the specific breed\n"
    "- Account for breed-specific predispositions (e.g., joint issues in large breeds)\n"
    "- Account for age category (puppies need more protein, seniors need joint support)\n"
    "- No explanation, no markdown — JSON only"
)

FOOD_ESTIMATION_SYSTEM_PROMPT = (
    "You are a pet food nutrition expert. Given a food product name and type, "
    "estimate its nutritional content per typical daily serving for a medium-sized dog.\n\n"
    "Rules:\n"
    "- Return ONLY valid JSON with these keys:\n"
    "  calories_per_serving (int), protein_pct (float), fat_pct (float), fibre_pct (float), "
    "moisture_pct (float), calcium (float, %), phosphorus (float, %), "
    "omega_3_mg (int), omega_6_mg (int), vitamin_e_iu (int), vitamin_d3_iu (int), "
    "glucosamine_mg (int), probiotics (bool)\n"
    "- For packaged food, estimate based on typical commercial pet food values\n"
    "- For homemade food, estimate based on common home-cooked dog food recipes\n"
    "- For supplements, provide the nutrient the supplement is known for\n"
    "- Be conservative with estimates\n"
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
) -> dict:
    """
    Get breed-specific daily nutrition targets, using cached AI lookups.

    Pipeline: DB cache check → OpenAI call → cache result → fallback to DEFAULT_TARGETS.
    """
    if not breed or not species:
        return dict(DEFAULT_TARGETS)

    breed_normalized = breed.lower().strip()
    species_normalized = species.lower().strip()
    age_category = _calculate_age_category(species_normalized, dob)

    # 1. Check DB cache
    try:
        cached = (
            db.query(NutritionTargetCache)
            .filter(
                NutritionTargetCache.species == species_normalized,
                NutritionTargetCache.breed_normalized == breed_normalized,
                NutritionTargetCache.age_category == age_category,
            )
            .first()
        )
        if cached:
            staleness_cutoff = datetime.utcnow() - timedelta(days=NUTRITION_CACHE_STALENESS_DAYS)
            if cached.created_at.replace(tzinfo=None) > staleness_cutoff:
                logger.info(
                    "Nutrition target cache hit: %s %s %s",
                    species_normalized, breed_normalized, age_category,
                )
                return cached.targets_json
            else:
                db.delete(cached)
                db.commit()
                logger.info("Deleted stale nutrition target cache for %s %s", breed_normalized, age_category)
    except Exception as e:
        logger.warning("Nutrition target cache lookup failed: %s", e)

    # 2. Call OpenAI
    age_description = _calculate_age_description(dob)
    try:
        result = await retry_openai_call(
            _call_openai_nutrition_targets,
            species_normalized, breed_normalized, age_description,
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
            age_category=age_category,
            targets_json=result,
        )
        db.add(cache_entry)
        db.commit()
        logger.info("Cached nutrition targets for %s %s %s", species_normalized, breed_normalized, age_category)
    except Exception as e:
        db.rollback()
        logger.info("Nutrition target cache race condition (already cached): %s", e)

    return result


async def _call_openai_nutrition_targets(
    species: str, breed: str, age_description: str,
) -> dict | None:
    """Call OpenAI for breed-specific daily nutrition targets."""
    client = _get_openai_client()
    user_prompt = f"Species: {species}\nBreed: {breed}\nAge: {age_description}"

    response = await client.chat.completions.create(
        model=OPENAI_QUERY_MODEL,
        temperature=0.0,
        max_tokens=OPENAI_NUTRITION_LOOKUP_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": NUTRITION_TARGET_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = response.choices[0].message.content
    logger.debug("OpenAI nutrition targets raw: %s", raw)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("Failed to parse nutrition targets response: %s — raw: %s", e, raw)
        return None


# ─── Step 3b: Product Catalog Matching ──────────────────────────────

def _match_product_from_catalog(catalog: list, label: str, item_type: str) -> "ProductCatalog | None":
    """
    In-memory multi-strategy matching against a pre-loaded product catalog slice.
    The caller loads the catalog once; this function never issues DB queries.

    Strategies (in order):
    1. Exact product_name match (label ⊆ product_name or product_name ⊆ label)
    2. Keyword match — any significant word in label appears in product_name
    3. Brand-only match — first word of label matches brand
    4. Reverse match — brand or product_name contained in label
    """
    label_lower = label.lower().strip()
    words = [w for w in label_lower.split() if len(w) > 2]

    for p in catalog:
        name_l = (p.product_name or "").lower()
        brand_l = (p.brand or "").lower()
        # Strategy 1: exact substring match
        if label_lower[:50] in name_l or name_l[:50] in label_lower:
            return p

    for p in catalog:
        name_l = (p.product_name or "").lower()
        # Strategy 2: any significant keyword
        for word in words:
            if word in name_l:
                return p

    first_word = label_lower.split()[0] if label_lower.split() else ""
    for p in catalog:
        brand_l = (p.brand or "").lower()
        # Strategy 3: brand match on first word
        if first_word and first_word in brand_l:
            return p

    for p in catalog:
        brand_l = (p.brand or "").lower()
        name_l = (p.product_name or "").lower()
        # Strategy 4: reverse — brand/name contained in label
        if brand_l and brand_l in label_lower:
            return p
        if name_l and name_l[:30] in label_lower:
            return p

    return None


# ─── Step 3c: AI Food Estimation ────────────────────────────────────

async def estimate_food_nutrition(
    db: Session, food_label: str, food_type: str,
) -> dict | None:
    """
    Estimate nutrition for foods not matched in product_catalog.

    Pipeline: DB cache check → OpenAI call → cache result.
    Returns nutrition dict or None on failure.
    """
    label_normalized = food_label.lower().strip()

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
    food_label: str, food_type: str,
) -> dict | None:
    """Call OpenAI to estimate nutritional content of a food item."""
    client = _get_openai_client()
    user_prompt = f"Food name: {food_label}\nType: {food_type}"

    response = await client.chat.completions.create(
        model=OPENAI_QUERY_MODEL,
        temperature=0.0,
        max_tokens=OPENAI_FOOD_ESTIMATION_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": FOOD_ESTIMATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = response.choices[0].message.content
    logger.debug("OpenAI food estimation raw: %s", raw)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("Failed to parse food estimation response: %s — raw: %s", e, raw)
        return None


# ─── Step 3d: AI Recommendation ─────────────────────────────────────

async def generate_recommendation(
    pet_name: str, breed: str, conditions: list[str], gap_summary: str,
) -> str:
    """
    Generate a personalized 1-2 sentence nutrition recommendation via GPT.

    Results are cached in-process for 4 hours keyed by inputs to avoid
    redundant OpenAI calls when multiple tabs trigger analyze_nutrition()
    in the same session. Falls back to a template string on failure.
    """
    # Build a stable cache key from all inputs
    key_raw = f"{pet_name}|{breed}|{','.join(sorted(conditions))}|{gap_summary}"
    cache_key = hashlib.sha256(key_raw.encode()).hexdigest()

    cached = _REC_CACHE.get(cache_key)
    if cached and (time.time() - cached[1]) < _REC_CACHE_TTL_SECONDS:
        return cached[0]

    try:
        client = _get_openai_client()
        context = f"Pet: {pet_name}, Breed: {breed}"
        if conditions:
            context += f", Conditions: {', '.join(conditions)}"
        context += f"\nNutritional gaps: {gap_summary}"

        response = await client.chat.completions.create(
            model=OPENAI_QUERY_MODEL,
            temperature=OPENAI_NUTRITION_REC_TEMPERATURE,
            max_tokens=OPENAI_NUTRITION_REC_MAX_TOKENS,
            messages=[
                {"role": "system", "content": RECOMMENDATION_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
        )
        text = response.choices[0].message.content.strip()
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

    # Load the food product catalog once — avoids N+1 queries in per-item matching
    food_catalog = db.query(ProductCatalog).filter(ProductCatalog.category == "food").all()

    # Separate items needing AI estimation from those matched in the product catalog
    catalog_items: list[tuple] = []   # (item, product)
    unmatched_items: list = []        # items needing AI estimation
    for item in diet_items:
        product = _match_product_from_catalog(food_catalog, item.label, item.type)
        if product:
            catalog_items.append((item, product))
        else:
            unmatched_items.append(item)

    # Fire breed-targets lookup and all per-item AI estimations in parallel
    targets_coro = get_nutrition_targets(db, pet.species, pet.breed, pet.dob)
    estimation_coros = [estimate_food_nutrition(db, item.label, item.type) for item in unmatched_items]

    results = await asyncio.gather(targets_coro, *estimation_coros, return_exceptions=True)
    targets = results[0] if not isinstance(results[0], Exception) else dict(DEFAULT_TARGETS)
    estimations = [
        r if not isinstance(r, Exception) else None
        for r in results[1:]
    ]

    # Aggregate nutritional values
    actual = {
        "calories": 0, "protein": 0, "fat": 0, "fibre": 0, "moisture": 0,
        "calcium": 0.0, "phosphorus": 0.0, "omega_3": 0, "omega_6": 0,
        "vitamin_e": 0, "vitamin_d3": 0, "glucosamine": 0, "probiotics": False,
    }

    matched_count = len(catalog_items)
    for _, product in catalog_items:
        _accumulate_from_product(actual, product)

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

    # Build vitamins array
    vitamins = _build_vitamins(actual, targets)

    # Build minerals array
    minerals = _build_minerals(actual, targets, has_hip_dysplasia)

    # Build others array
    others = _build_others(actual, targets, has_hip_dysplasia)

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

    recommendation = await generate_recommendation(
        pet.name,
        pet.breed or "mixed breed",
        [c.name for c in conditions],
        gap_summary,
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
    diet_labels = [item.label for item in diet_items if item.label]
    if diet_labels:
        diet_list = ", ".join(diet_labels[:5])
        strengths = []
        if actual["protein"] >= targets.get("protein_min", 20):
            strengths.append("good protein levels")
        if actual["omega_3"] > 0:
            strengths.append("omega-3 support")
        if actual.get("probiotics"):
            strengths.append("probiotic support")
        if actual["fibre"] >= targets.get("fibre_min", 3):
            strengths.append("adequate fibre")
        if actual["calcium"] >= targets.get("calcium_min", 0.8):
            strengths.append("sufficient calcium")
        strength_text = (". Strengths: " + ", ".join(strengths)) if strengths else ""
        diet_summary = f"Current diet: {diet_list}{strength_text}."
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

def _accumulate_from_product(actual: dict, product: ProductCatalog) -> None:
    """Accumulate nutritional values from a matched product catalog entry."""
    if product.crude_protein:
        actual["protein"] = max(actual["protein"], float(product.crude_protein))
    if product.crude_fat:
        actual["fat"] = max(actual["fat"], float(product.crude_fat))
    if product.crude_fibre:
        actual["fibre"] = max(actual["fibre"], float(product.crude_fibre))
    if product.moisture:
        actual["moisture"] = max(actual["moisture"], float(product.moisture))
    if product.energy_kcal:
        actual["calories"] += int(product.energy_kcal * 0.28)  # Rough portion estimate
    if product.calcium:
        actual["calcium"] = max(actual["calcium"], float(product.calcium))
    if product.phosphorus:
        actual["phosphorus"] = max(actual["phosphorus"], float(product.phosphorus))
    if product.omega_3:
        actual["omega_3"] += product.omega_3
    if product.omega_6:
        actual["omega_6"] += product.omega_6
    if product.vitamin_e:
        actual["vitamin_e"] += product.vitamin_e
    if product.vitamin_d3:
        actual["vitamin_d3"] += product.vitamin_d3
    if product.glucosamine:
        actual["glucosamine"] += product.glucosamine
    if product.probiotics and product.probiotics != "-":
        actual["probiotics"] = True


def _accumulate_from_estimation(actual: dict, est: dict) -> None:
    """Accumulate nutritional values from AI-estimated food nutrition."""
    actual["calories"] += int(est.get("calories_per_serving", 0))
    actual["protein"] = max(actual["protein"], float(est.get("protein_pct", 0)))
    actual["fat"] = max(actual["fat"], float(est.get("fat_pct", 0)))
    actual["fibre"] = max(actual["fibre"], float(est.get("fibre_pct", 0)))
    actual["moisture"] = max(actual["moisture"], float(est.get("moisture_pct", 0)))
    actual["calcium"] = max(actual["calcium"], float(est.get("calcium", 0)))
    actual["phosphorus"] = max(actual["phosphorus"], float(est.get("phosphorus", 0)))
    actual["omega_3"] += int(est.get("omega_3_mg", 0))
    actual["omega_6"] += int(est.get("omega_6_mg", 0))
    actual["vitamin_e"] += int(est.get("vitamin_e_iu", 0))
    actual["vitamin_d3"] += int(est.get("vitamin_d3_iu", 0))
    actual["glucosamine"] += int(est.get("glucosamine_mg", 0))
    if est.get("probiotics"):
        actual["probiotics"] = True


# ─── Builder Helpers ─────────────────────────────────────────────────

def _build_macros(actual: dict, targets: dict, breed_key: str) -> list[dict]:
    """Build macronutrients array for the response."""
    target_protein = targets.get("protein", 25)
    target_fat = targets.get("fat", 14)
    target_carbs = targets.get("carbs", 50)
    target_fibre = targets.get("fibre", 4)
    target_moisture = targets.get("moisture", 10)

    carbs_actual = max(0, 100 - actual["protein"] - actual["fat"] - actual["fibre"] - actual["moisture"])

    return [
        {
            "name": "Protein", "icon": "\U0001f969",
            "actual": actual["protein"], "target": target_protein, "unit": "%",
            "status": _status_for_ratio(_safe_ratio(actual["protein"], target_protein)),
            "note": "Good protein content" if actual["protein"] >= target_protein * 0.9 else "Consider protein-rich supplements",
        },
        {
            "name": "Fat", "icon": "\U0001f9c8",
            "actual": actual["fat"], "target": target_fat, "unit": "%",
            "status": _status_for_ratio(_safe_ratio(actual["fat"], target_fat)),
            "note": "Essential for energy and coat health",
        },
        {
            "name": "Carbohydrates", "icon": "\U0001f33e",
            "actual": carbs_actual, "target": target_carbs, "unit": "%",
            "status": "Adequate",
            "note": "Derived from remaining macronutrient balance",
        },
        {
            "name": "Fibre", "icon": "\U0001f966",
            "actual": actual["fibre"], "target": target_fibre, "unit": "%",
            "status": _status_for_ratio(_safe_ratio(actual["fibre"], target_fibre)),
            "note": "Supports digestive regularity",
        },
        {
            "name": "Moisture", "icon": "\U0001f4a7",
            "actual": actual["moisture"], "target": target_moisture, "unit": "%",
            "status": _status_for_ratio(_safe_ratio(actual["moisture"], target_moisture)),
            "note": "Ensure fresh water is always available",
        },
    ]


def _build_vitamins(actual: dict, targets: dict) -> list[dict]:
    """Build vitamins gap analysis array."""
    vit_e_target = targets.get("vitamin_e", 300)
    vit_d_target = targets.get("vitamin_d3", 400)

    vit_e_status = _status_for_ratio(_safe_ratio(actual["vitamin_e"], vit_e_target))
    vit_d_status = _status_for_ratio(_safe_ratio(actual["vitamin_d3"], vit_d_target))

    return [
        {
            "name": "Vitamin E", "status": vit_e_status,
            "supplement": "Vit E 400 IU Softgel" if vit_e_status != "Adequate" else None,
            "price": "Rs.349/mo" if vit_e_status != "Adequate" else None,
            "priority": _priority_for_status(vit_e_status),
        },
        {
            "name": "Vitamin D3", "status": vit_d_status,
            "supplement": "Sun Pharma Calcitriol" if vit_d_status != "Adequate" else None,
            "price": "Rs.299/mo" if vit_d_status != "Adequate" else None,
            "priority": _priority_for_status(vit_d_status),
        },
    ]


def _build_minerals(actual: dict, targets: dict, has_hip_dysplasia: bool) -> list[dict]:
    """Build minerals array."""
    gluc_target = targets.get("glucosamine", 500)
    calc_target = targets.get("calcium", 1.0)
    phos_target = targets.get("phosphorus", 0.8)

    gluc_status = _status_for_ratio(_safe_ratio(actual["glucosamine"], gluc_target))
    calc_status = _status_for_ratio(_safe_ratio(actual["calcium"], calc_target))
    phos_status = _status_for_ratio(_safe_ratio(actual["phosphorus"], phos_target))

    return [
        {
            "name": "Glucosamine", "icon": "\U0001f9b4",
            "status": gluc_status,
            "priority": _priority_for_status(gluc_status, is_critical=has_hip_dysplasia),
            "reason": "Critical for hip joint support" if has_hip_dysplasia else "Supports joint health",
            "actual": actual["glucosamine"], "target": gluc_target,
            "supplement": "Nutramax Cosequin DS Chewable" if gluc_status != "Adequate" else None,
            "price": "Rs.799/mo" if gluc_status != "Adequate" else None,
        },
        {
            "name": "Calcium", "icon": "\U0001f9b7",
            "status": calc_status,
            "priority": _priority_for_status(calc_status),
            "reason": "Essential for bones and teeth",
            "actual": actual["calcium"], "target": calc_target,
            "supplement": None, "price": None,
        },
        {
            "name": "Phosphorus", "icon": "\u26a1",
            "status": phos_status,
            "priority": _priority_for_status(phos_status),
            "reason": "Works with calcium for bone health",
            "actual": actual["phosphorus"], "target": phos_target,
            "supplement": None, "price": None,
        },
    ]


def _build_others(actual: dict, targets: dict, has_hip_dysplasia: bool) -> list[dict]:
    """Build other nutrients array."""
    omega3_target = targets.get("omega_3", 300)
    omega6_target = targets.get("omega_6", 1500)

    omega3_status = _status_for_ratio(_safe_ratio(actual["omega_3"], omega3_target))
    omega6_status = _status_for_ratio(_safe_ratio(actual["omega_6"], omega6_target))
    prob_status = "Adequate" if actual["probiotics"] else "Low"

    return [
        {
            "name": "Omega-3", "icon": "\U0001f41f",
            "status": omega3_status,
            "actual": actual["omega_3"], "target": omega3_target,
            "supplement": "Zesty Paws Salmon Oil" if omega3_status != "Adequate" else None,
            "price": "Rs.349/mo" if omega3_status != "Adequate" else None,
            "priority": _priority_for_status(omega3_status, is_critical=has_hip_dysplasia),
        },
        {
            "name": "Omega-6", "icon": "\U0001f33b",
            "status": omega6_status,
            "actual": actual["omega_6"], "target": omega6_target,
            "supplement": None, "price": None,
            "priority": _priority_for_status(omega6_status),
        },
        {
            "name": "Probiotics", "icon": "\U0001f9a0",
            "status": prob_status,
            "supplement": "Purina FortiFlora" if prob_status != "Adequate" else None,
            "price": "Rs.649/mo" if prob_status != "Adequate" else None,
            "priority": _priority_for_status(prob_status),
        },
    ]


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
