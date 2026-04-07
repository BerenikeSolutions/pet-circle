"""
PetCircle Phase 1 — Medicine Recurrence Service

Determines the recommended recurrence interval for a medicine/product.

Strategy:
  1. Look up the product in product_catalog by matching the medicine name
     against "brand product_name". If found and the catalog has a parseable
     frequency value, use it directly — no AI call needed.
  2. Fall back to OpenAI GPT only when the product is not in the catalog
     or the catalog frequency cannot be parsed into days.
"""

import json
import logging
import re

from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

# --- OpenAI client singleton (lazy) ---
_openai_medicine_client = None


def _get_openai_client():
    """Return a cached OpenAI client (created on first call)."""
    global _openai_medicine_client
    if _openai_medicine_client is None:
        from openai import OpenAI
        _openai_medicine_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_medicine_client


# ---------------------------------------------------------------------------
# Frequency string → days parser
# ---------------------------------------------------------------------------

def _parse_frequency_to_days(frequency: str | None) -> int | None:
    """
    Parse a human-readable frequency/duration string into an integer number of days.

    Handles patterns like:
      "30 days", "Every 3 months", "1 month", "3 months", "12 weeks",
      "monthly", "quarterly", "annually", "Once a month"
    """
    if not frequency:
        return None

    text = frequency.strip().lower()

    # Direct day values: "30 days", "90 days", "every 30 days"
    m = re.search(r'(\d+)\s*days?', text)
    if m:
        return int(m.group(1))

    # Week values: "4 weeks", "every 12 weeks"
    m = re.search(r'(\d+)\s*weeks?', text)
    if m:
        return int(m.group(1)) * 7

    # Month values: "3 months", "every 1 month", "once a month"
    m = re.search(r'(\d+)\s*months?', text)
    if m:
        return int(m.group(1)) * 30

    # Named frequencies
    if 'weekly' in text:
        return 7
    if 'fortnightly' in text or 'bi-weekly' in text or 'biweekly' in text:
        return 14
    if 'monthly' in text or 'once a month' in text:
        return 30
    if 'quarterly' in text:
        return 90
    if 'semi-annual' in text or 'semiannual' in text or 'bi-annual' in text:
        return 180
    if 'annual' in text or 'yearly' in text:
        return 365

    return None


def _infer_catalog_categories(item_type: str | None) -> list[str]:
    """Infer product catalog categories from preventive item text."""
    item_norm = (item_type or "").strip().lower()
    categories: list[str] = []
    if "deworm" in item_norm:
        categories.append("deworming")
    if "flea" in item_norm or "tick" in item_norm:
        categories.append("flea_tick")
    return categories


def _is_dual_use_medicine(medicine_name: str | None) -> bool:
    """Return True when medicine can target both deworming and flea/tick."""
    if not isinstance(medicine_name, str) or not medicine_name.strip():
        return False

    try:
        from app.services.gpt_extraction import _get_preventive_categories_for_medicine

        categories = _get_preventive_categories_for_medicine(medicine_name)
    except Exception:
        return False

    return {"deworming", "flea_tick"}.issubset(categories)


# ---------------------------------------------------------------------------
# Catalog lookup
# ---------------------------------------------------------------------------

def _lookup_catalog_frequency(db: Session, medicine_name: str, item_type: str) -> int | None:
    """
    Search product_catalog for a matching product and return parsed frequency in days.

    Rule:
      - Dual-use medicines: resolve medicine-centrically across categories.
      - Non-dual medicines: keep previous category-specific lookup behavior.
    """
    from app.models.product_catalog import ProductCatalog

    is_dual = _is_dual_use_medicine(medicine_name)
    categories = _infer_catalog_categories(item_type)
    if is_dual:
        allowed_categories = ["deworming", "flea_tick"]
    else:
        allowed_categories = categories

    if not allowed_categories:
        return None

    # Match "Brand ProductName" against catalog rows.
    medicine_lower = medicine_name.strip().lower()

    rows = (
        db.query(
            ProductCatalog.category,
            ProductCatalog.brand,
            ProductCatalog.product_name,
            ProductCatalog.frequency,
        )
        .filter(
            ProductCatalog.category.in_(allowed_categories),
            ProductCatalog.product_name.isnot(None),
        )
        .all()
    )

    matched_days: set[int] = set()
    for category, brand, product_name, frequency in rows:
        brand_text = (brand or "").strip()
        product_text = (product_name or "").strip()
        label = f"{brand_text} {product_text}".strip().lower()
        if label == medicine_lower:
            days = _parse_frequency_to_days(frequency)
            if days and days > 0:
                matched_days.add(days)
            else:
                logger.warning(
                    "Catalog match for %s but unparseable frequency: '%s'",
                    medicine_name, frequency,
                )

    if not matched_days:
        return None

    if len(matched_days) > 1:
        logger.warning(
            "Catalog contains multiple recurrence values for %s (%s); using minimum days for consistency.",
            medicine_name,
            sorted(matched_days),
        )

    result_days = min(matched_days)
    logger.info(
        "Catalog recurrence for %s (%s): %d days",
        medicine_name,
        item_type,
        result_days,
    )
    return result_days


# ---------------------------------------------------------------------------
# GPT fallback
# ---------------------------------------------------------------------------

MEDICINE_RECURRENCE_SYSTEM_PROMPT = (
    "You are a veterinary pharmacology assistant. Given a pet species, "
    "preventive care type, and specific medicine/product name, return the "
    "recommended interval between doses or applications in days.\n\n"
    "Rules:\n"
    "- Return ONLY valid JSON: {\"recurrence_days\": <integer>}\n"
    "- Use standard veterinary dosing guidelines\n"
    "- For deworming products: typical range is 30-90 days\n"
    "- For flea/tick products: typical range is 30-90 days depending on product\n"
    "- For supplements: typical range is 30-180 days\n"
    "- If the medicine name is unrecognized, return {\"recurrence_days\": null}\n"
    "- No explanation, no markdown — JSON only"
)


def _gpt_recurrence(
    species: str,
    item_type: str,
    medicine_name: str,
    default_days: int,
    include_item_type: bool,
) -> int:
    """Call OpenAI GPT to determine recurrence days. Returns default_days on failure."""
    try:
        client = _get_openai_client()

        user_prompt_parts = [f"Species: {species}"]
        if include_item_type:
            user_prompt_parts.append(f"Preventive type: {item_type}")
        user_prompt_parts.append(f"Medicine/Product: {medicine_name}")
        user_prompt = "\n".join(user_prompt_parts) + (
            "\n\nWhat is the recommended interval between doses/applications in days?"
        )

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0.0,
            max_tokens=100,
            messages=[
                {"role": "system", "content": MEDICINE_RECURRENCE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        days = data.get("recurrence_days")

        if days is not None and isinstance(days, (int, float)) and days > 0:
            result = int(days)
            logger.info(
                "AI recurrence for %s (%s, %s): %d days",
                medicine_name, species, item_type, result,
            )
            return result

        logger.warning(
            "AI returned null/invalid for %s (%s, %s), using default %d",
            medicine_name, species, item_type, default_days,
        )
        return default_days

    except Exception as e:
        logger.error(
            "Medicine recurrence lookup failed for %s: %s",
            medicine_name, str(e),
        )
        return default_days


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_medicine_recurrence(
    species: str,
    item_type: str,
    medicine_name: str,
    default_days: int,
    db: Session | None = None,
) -> int:
    """
    Determine recommended recurrence days for a medicine.

    1. If a DB session is provided, check product_catalog first (instant).
    2. If not found in catalog, fall back to GPT (slow, ~2-10s).
    3. On any failure, return default_days.
    """
    is_dual = _is_dual_use_medicine(medicine_name)

    # Step 1: catalog lookup (fast path)
    if db is not None:
        catalog_days = _lookup_catalog_frequency(db, medicine_name, item_type)
        if catalog_days is not None:
            return catalog_days

    # Step 2: GPT fallback for unknown medicines
    return _gpt_recurrence(
        species,
        item_type,
        medicine_name,
        default_days,
        include_item_type=not is_dual,
    )
