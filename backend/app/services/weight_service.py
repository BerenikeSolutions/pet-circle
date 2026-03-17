"""
PetCircle Phase 1 — Weight History Service

Manages weight tracking for pets. Provides CRUD operations for
weight measurements and breed-specific ideal weight ranges.
"""

import logging
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.weight_history import WeightHistory
from app.models.pet import Pet

logger = logging.getLogger(__name__)

# Ideal weight ranges by breed and gender (kg)
IDEAL_WEIGHT_RANGES = {
    "golden retriever": {"male": {"min": 27, "max": 34}, "female": {"min": 25, "max": 32}},
    "labrador retriever": {"male": {"min": 29, "max": 36}, "female": {"min": 25, "max": 32}},
    "german shepherd": {"male": {"min": 30, "max": 40}, "female": {"min": 22, "max": 32}},
    "beagle": {"male": {"min": 10, "max": 11}, "female": {"min": 9, "max": 10}},
    "pug": {"male": {"min": 6, "max": 8}, "female": {"min": 6, "max": 8}},
    "indian spitz": {"male": {"min": 5, "max": 7}, "female": {"min": 4, "max": 6}},
}

# Default range when breed not found
DEFAULT_RANGE = {"min": 5, "max": 50}


def get_ideal_range(breed: str | None, gender: str | None) -> dict:
    """Get ideal weight range for a breed/gender combination."""
    if not breed:
        return DEFAULT_RANGE
    breed_key = breed.lower().strip()
    breed_data = IDEAL_WEIGHT_RANGES.get(breed_key)
    if not breed_data:
        return DEFAULT_RANGE
    if gender and gender.lower() in breed_data:
        return breed_data[gender.lower()]
    # Return male range as default if gender unknown
    return breed_data.get("male", DEFAULT_RANGE)


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

    ideal_range = get_ideal_range(pet.breed, pet.gender)

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
