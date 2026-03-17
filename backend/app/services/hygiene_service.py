"""
PetCircle Phase 1 — Hygiene Service

CRUD operations for pet grooming/hygiene preferences.
Seeds default hygiene items for new pets on first access.
"""

import logging
from sqlalchemy.orm import Session

from app.models.hygiene_preference import HygienePreference

logger = logging.getLogger(__name__)

# Default hygiene items seeded for new pets
DEFAULT_HYGIENE = {
    "coat-brush":  {"freq": 1, "unit": "day",   "reminder": True},
    "teeth-brush": {"freq": 1, "unit": "day",   "reminder": True},
    "ear-clean":   {"freq": 6, "unit": "week",  "reminder": True},
    "eye-wipe":    {"freq": 1, "unit": "month", "reminder": True},
    "bath-nail":   {"freq": 1, "unit": "month", "reminder": True},
    "anal-gland":  {"freq": 6, "unit": "week",  "reminder": True},
}


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

    return [
        {
            "id": str(p.id),
            "item_id": p.item_id,
            "freq": p.freq,
            "unit": p.unit,
            "reminder": p.reminder,
            "last_done": p.last_done,
        }
        for p in prefs
    ]


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

    return {
        "id": str(pref.id),
        "item_id": pref.item_id,
        "freq": pref.freq,
        "unit": pref.unit,
        "reminder": pref.reminder,
        "last_done": pref.last_done,
    }


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
