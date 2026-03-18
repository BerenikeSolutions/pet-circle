"""
PetCircle Phase 1 — Hygiene Service

CRUD operations for pet grooming/hygiene preferences.
Seeds default hygiene items for new pets on first access.
Supports user-added custom items per pet.
"""

import re
import logging
from sqlalchemy.orm import Session

from app.models.hygiene_preference import HygienePreference

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


def _pref_to_dict(p: HygienePreference) -> dict:
    """Convert a HygienePreference ORM object to a response dict."""
    return {
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
    }


def _slugify(name: str) -> str:
    """Generate a URL-safe slug from a name for use as item_id."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return slug.strip("-")[:50]


async def get_hygiene_preferences(db: Session, pet_id) -> list[dict]:
    """
    Returns hygiene preferences for a pet.
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

    return [_pref_to_dict(p) for p in prefs]


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
