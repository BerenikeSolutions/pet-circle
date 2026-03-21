"""
PetCircle Phase 1 — Medicine Recurrence Service

Uses OpenAI GPT to determine the recommended recurrence interval
for a specific medicine/product based on pet species and item type
(deworming, flea/tick, supplements).

The AI returns the number of days between doses/applications,
which is then used as custom_recurrence_days for the preventive record.
"""

import json
import logging
import asyncio
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


def get_medicine_recurrence(
    species: str,
    item_type: str,
    medicine_name: str,
    default_days: int,
) -> int:
    """
    Look up recommended recurrence days for a medicine using GPT.

    Args:
        species: Pet species ('dog' or 'cat').
        item_type: Preventive item type (e.g., 'Deworming', 'Tick/Flea').
        medicine_name: Name of the medicine/product.
        default_days: Fallback recurrence from preventive_master.

    Returns:
        Recommended recurrence in days (int). Falls back to default_days
        if AI call fails or medicine is unrecognized.
    """
    try:
        client = _get_openai_client()

        user_prompt = (
            f"Species: {species}\n"
            f"Preventive type: {item_type}\n"
            f"Medicine/Product: {medicine_name}\n\n"
            f"What is the recommended interval between doses/applications in days?"
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
