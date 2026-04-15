"""
PetCircle Phase 1 — Hygiene Service

CRUD operations for pet grooming/hygiene preferences.
Seeds default hygiene items for new pets on first access.
Supports user-added custom items per pet.
Generates AI-powered one-line tips per hygiene activity (cached by breed).
"""

import json
import logging
import re
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.constants import OPENAI_QUERY_MODEL
from app.models.hygiene_preference import HygienePreference
from app.models.hygiene_tip_cache import HygieneTipCache
from app.utils.ai_client import get_ai_client
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

# Default hygiene items seeded for new pets
DEFAULT_HYGIENE = {
    "coat-brush":  {"name": "Coat Brushing",            "icon": "🪮", "category": "daily",    "freq": 1, "unit": "day",   "reminder": True},
    "teeth-brush": {"name": "Teeth Brushing",            "icon": "🦷", "category": "daily",    "freq": 1, "unit": "day",   "reminder": True},
    "ear-clean":   {"name": "Ear Cleaning",              "icon": "👂", "category": "daily",    "freq": 6, "unit": "week",  "reminder": True},
    "eye-wipe":    {"name": "Eye Wipe",                  "icon": "👁️", "category": "daily",    "freq": 1, "unit": "month", "reminder": True},
    "bath-nail":   {"name": "Bath, brush & nail trim",   "icon": "🛁", "category": "periodic", "freq": 1, "unit": "month", "reminder": True},
    "anal-gland":  {"name": "Anal gland cleaning",       "icon": "🐾", "category": "periodic", "freq": 6, "unit": "week",  "reminder": True},
}

# Cache staleness — regenerate tips after this many days
HYGIENE_TIP_CACHE_DAYS = 365

# Lazy-initialised AI client
_openai_client = None


def _get_openai_client():
    """Lazy-init AI client (provider-agnostic)."""
    global _openai_client
    if _openai_client is None:
        _openai_client = get_ai_client()
    return _openai_client


def _pref_to_dict(p: HygienePreference, tip: str | None = None) -> dict:
    """Convert a HygienePreference ORM object to a response dict."""
    d = {
        "id": str(p.id),
        "item_id": p.item_id,
        "name": p.name or p.item_id,
        "icon": p.icon or "🧹",
        "category": p.category or "daily",
        "is_default": p.is_default,
        "freq": p.freq,
        "unit": p.unit,
        "reminder": p.reminder,
        "last_done": p.last_done,
        "tip": tip,
    }
    return d


def _slugify(name: str) -> str:
    """Generate a URL-safe slug from a name for use as item_id."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return slug.strip("-")[:50]


def _compute_age_label(dob: date | None) -> str:
    """Compute a human-readable age label from DOB."""
    if not dob:
        return "adult"
    today = date.today()
    months = (today.year - dob.year) * 12 + (today.month - dob.month)
    if months < 6:
        return "young puppy/kitten (under 6 months)"
    if months < 12:
        return "puppy/kitten (6-12 months)"
    if months < 24:
        return "junior (1-2 years)"
    years = months // 12
    if years < 7:
        return f"adult ({years} years)"
    return f"senior ({years} years)"


async def _generate_hygiene_tips(
    db: Session,
    species: str,
    breed: str,
    age_label: str,
    item_ids_and_names: list[tuple[str, str]],
) -> dict[str, str]:
    """
    Generate one-line tips for multiple hygiene items in a single GPT call.
    Returns dict of {item_id: tip_text}.
    Checks cache first, only calls GPT for uncached items.
    """
    breed_norm = breed.lower().strip() if breed else "mixed breed"
    tips: dict[str, str] = {}

    # Batch cache lookup — one query for all items instead of N queries
    cutoff = datetime.utcnow() - timedelta(days=HYGIENE_TIP_CACHE_DAYS)
    item_ids = [item_id for item_id, _ in item_ids_and_names]
    cached_rows = (
        db.query(HygieneTipCache)
        .filter(
            HygieneTipCache.species == species,
            HygieneTipCache.breed_normalized == breed_norm,
            HygieneTipCache.item_id.in_(item_ids),
            HygieneTipCache.created_at >= cutoff,
        )
        .all()
    )
    tips = {row.item_id: row.tip for row in cached_rows}
    uncached = [(iid, name) for iid, name in item_ids_and_names if iid not in tips]

    if not uncached:
        return tips

    # Build prompt for uncached items
    items_list = "\n".join(f"- {item_id}: {name}" for item_id, name in uncached)

    try:
        client = _get_openai_client()

        async def _call():
            return await client.messages.create(
                model=OPENAI_QUERY_MODEL,
                temperature=0.4,
                max_tokens=600,
                system=(
                    "You are a veterinary grooming expert. For each hygiene activity, "
                    "write ONE short sentence (max 20 words) explaining why it's important "
                    "for this specific breed and age. Be specific to the breed's traits "
                    "(coat type, ear shape, skin folds, etc). No generic advice.\n\n"
                    "Return ONLY a JSON object mapping item_id to tip string. No markdown."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Species: {species}\n"
                            f"Breed: {breed or 'mixed breed'}\n"
                            f"Age: {age_label}\n\n"
                            f"Activities:\n{items_list}"
                        ),
                    },
                ],
            )

        resp = await retry_openai_call(_call)
        raw = resp.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        generated: dict = json.loads(raw)

        # Collect newly generated tips
        new_tips: dict[str, str] = {}
        for item_id, name in uncached:
            tip = generated.get(item_id, "")
            if tip:
                new_tips[item_id] = tip[:300]

        if new_tips:
            tips.update(new_tips)
            # Batch upsert: delete stale rows then bulk-insert fresh ones
            stale_ids = list(new_tips.keys())
            db.query(HygieneTipCache).filter(
                HygieneTipCache.species == species,
                HygieneTipCache.breed_normalized == breed_norm,
                HygieneTipCache.item_id.in_(stale_ids),
            ).delete(synchronize_session=False)
            db.add_all([
                HygieneTipCache(
                    species=species,
                    breed_normalized=breed_norm,
                    item_id=item_id,
                    tip=tip,
                )
                for item_id, tip in new_tips.items()
            ])
            db.commit()

    except Exception as e:
        logger.warning("Failed to generate hygiene tips: %s", str(e))
        # Return whatever we have — tips will be None for failed items

    return tips


async def get_hygiene_preferences(
    db: Session,
    pet_id,
    species: str | None = None,
    breed: str | None = None,
    dob: date | None = None,
) -> list[dict]:
    """
    Returns hygiene preferences for a pet with AI-generated tips.
    Seeds defaults on first access if none exist.
    """
    prefs = (
        db.query(HygienePreference)
        .filter(HygienePreference.pet_id == pet_id)
        .order_by(HygienePreference.created_at)
        .all()
    )

    # Seed defaults on first access
    if not prefs:
        for item_id, defaults in DEFAULT_HYGIENE.items():
            pref = HygienePreference(
                pet_id=pet_id,
                item_id=item_id,
                name=defaults["name"],
                icon=defaults["icon"],
                category=defaults["category"],
                is_default=True,
                freq=defaults["freq"],
                unit=defaults["unit"],
                reminder=defaults["reminder"],
            )
            db.add(pref)
        db.commit()
        prefs = (
            db.query(HygienePreference)
            .filter(HygienePreference.pet_id == pet_id)
            .order_by(HygienePreference.created_at)
            .all()
        )
        logger.info("Seeded default hygiene preferences for pet %s", pet_id)

    # Generate tips if we have species/breed info
    tips: dict[str, str] = {}
    if species:
        age_label = _compute_age_label(dob)
        item_ids_and_names = [(p.item_id, p.name or p.item_id) for p in prefs]
        try:
            tips = await _generate_hygiene_tips(db, species, breed or "mixed breed", age_label, item_ids_and_names)
        except Exception as e:
            logger.warning("Tip generation failed, returning prefs without tips: %s", str(e))

    return [_pref_to_dict(p, tip=tips.get(p.item_id)) for p in prefs]


async def add_hygiene_item(
    db: Session, pet_id, name: str, icon: str = "🧹", category: str = "daily",
    freq: int = 1, unit: str = "month"
) -> dict:
    """Add a custom hygiene item for a pet."""
    item_id = _slugify(name)

    # Check for duplicate item_id
    existing = (
        db.query(HygienePreference)
        .filter(HygienePreference.pet_id == pet_id, HygienePreference.item_id == item_id)
        .first()
    )
    if existing:
        raise ValueError(f"Hygiene item '{name}' already exists")

    pref = HygienePreference(
        pet_id=pet_id,
        item_id=item_id,
        name=name,
        icon=icon,
        category=category,
        is_default=False,
        freq=freq,
        unit=unit,
        reminder=False,
    )
    db.add(pref)
    db.commit()
    db.refresh(pref)

    logger.info("Added custom hygiene item '%s' for pet %s", name, pet_id)
    return _pref_to_dict(pref)


async def upsert_hygiene_preference(
    db: Session, pet_id, item_id: str, freq: int, unit: str, reminder: bool, last_done: str = None
) -> dict:
    """Create or update a hygiene preference."""
    pref = (
        db.query(HygienePreference)
        .filter(HygienePreference.pet_id == pet_id, HygienePreference.item_id == item_id)
        .first()
    )

    if pref:
        pref.freq = freq
        pref.unit = unit
        pref.reminder = reminder
        if last_done is not None:
            pref.last_done = last_done
    else:
        pref = HygienePreference(
            pet_id=pet_id,
            item_id=item_id,
            freq=freq,
            unit=unit,
            reminder=reminder,
            last_done=last_done,
        )
        db.add(pref)

    db.commit()
    db.refresh(pref)

    return _pref_to_dict(pref)


async def update_hygiene_date(db: Session, pet_id, item_id: str, last_done: str) -> dict:
    """Update just the last done date for a hygiene item."""
    pref = (
        db.query(HygienePreference)
        .filter(HygienePreference.pet_id == pet_id, HygienePreference.item_id == item_id)
        .first()
    )
    if not pref:
        raise ValueError(f"Hygiene preference '{item_id}' not found")

    pref.last_done = last_done
    db.commit()

    return {
        "id": str(pref.id),
        "item_id": pref.item_id,
        "last_done": pref.last_done,
    }


async def delete_hygiene_item(db: Session, pet_id, item_id: str) -> dict:
    """Delete a custom hygiene item. Default items cannot be deleted."""
    pref = (
        db.query(HygienePreference)
        .filter(HygienePreference.pet_id == pet_id, HygienePreference.item_id == item_id)
        .first()
    )
    if not pref:
        raise ValueError(f"Hygiene preference '{item_id}' not found")

    if pref.is_default:
        raise ValueError("Cannot delete default hygiene items")

    db.delete(pref)
    db.commit()

    logger.info("Deleted custom hygiene item '%s' for pet %s", item_id, pet_id)
    return {"status": "deleted", "item_id": item_id}
