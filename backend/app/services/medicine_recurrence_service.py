"""
PetCircle Phase 1 — Medicine Recurrence Service

Determines the recommended recurrence interval for a medicine/product
via OpenAI GPT.

Note: The legacy product_catalog table (which included a frequency
column for deworming/flea-tick medicines) has been replaced by the
signal-level cart tables (product_food + product_supplement). Neither
carries dosing frequency, so the fast-path catalog lookup has been
removed and this service now always calls GPT. See
.spec/cart-rules-engine/design.md.
"""

import json
import logging
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import OPENAI_QUERY_MODEL

logger = logging.getLogger(__name__)

# --- Anthropic client singleton (lazy) ---
_openai_medicine_client = None


def _get_openai_client():
    """Return a cached sync AI client (provider-agnostic, created on first call)."""
    global _openai_medicine_client
    if _openai_medicine_client is None:
        from app.utils.ai_client import get_sync_ai_client  # noqa: PLC0415
        _openai_medicine_client = get_sync_ai_client()
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
    Look up repeat_frequency from product_medicines table.

    Queries product_medicines for a matching medicine name, then parses the
    human-readable repeat_frequency string (e.g. "Monthly", "Every 3 months")
    into an integer number of days. Returns None when no match is found so
    callers fall through to GPT.
    """
    if not medicine_name or not db:
        return None

    try:
        from app.models.product_medicines import ProductMedicines

        med = (
            db.query(ProductMedicines)
            .filter(
                ProductMedicines.active == True,
                ProductMedicines.product_name.ilike(f"%{medicine_name}%"),
            )
            .first()
        )
        if med and med.repeat_frequency:
            days = _parse_frequency_to_days(med.repeat_frequency)
            if days:
                logger.info(
                    "product_medicines frequency for %r: %r -> %d days",
                    medicine_name, med.repeat_frequency, days,
                )
                return days
    except Exception as e:
        logger.debug("product_medicines lookup failed for %r: %s", medicine_name, str(e))

    return None


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

        response = client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0.0,
            max_tokens=100,
            system=MEDICINE_RECURRENCE_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = response.content[0].text.strip()
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
