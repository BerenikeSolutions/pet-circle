"""
PetCircle Phase 1 — Diet Service

CRUD operations for pet diet items (packaged food, homemade food, supplements).
Auto-classifies food type based on brand keyword matching.
"""

import logging
from sqlalchemy.orm import Session

from app.models.diet_item import DietItem

logger = logging.getLogger(__name__)

# Keywords that indicate packaged food
PACKAGED_KW = [
    "royal canin", "pedigree", "hills", "drools", "purina", "kibble",
    "wet food", "can", "pouch", "whiskas", "iams", "eukanuba",
    "orijen", "acana", "farmina", "science diet", "pro plan",
]


def classify_food(label: str, food_type: str) -> tuple[str, str]:
    """
    Auto-classify food type and assign icon.

    Returns (type, icon) tuple.
    """
    if food_type == "supplement":
        return "supplement", "💊"

    label_lower = label.lower()
    for kw in PACKAGED_KW:
        if kw in label_lower:
            return "packaged", "🥣"
    return food_type, "🥗" if food_type == "homemade" else "🥣"


async def get_diet_items(db: Session, pet_id) -> list[dict]:
    """Returns all diet items for a pet."""
    items = (
        db.query(DietItem)
        .filter(DietItem.pet_id == pet_id)
        .order_by(DietItem.created_at)
        .all()
    )
    return [
        {
            "id": str(item.id),
            "type": item.type,
            "icon": item.icon,
            "label": item.label,
            "detail": item.detail,
        }
        for item in items
    ]


async def add_diet_item(db: Session, pet_id, food_type: str, label: str, detail: str = None, icon: str = None) -> dict:
    """Add a food or supplement item to a pet's diet."""
    classified_type, default_icon = classify_food(label, food_type)

    item = DietItem(
        pet_id=pet_id,
        type=classified_type,
        icon=icon or default_icon,
        label=label,
        detail=detail,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    logger.info("Diet item added for pet %s: %s (%s)", pet_id, label, classified_type)
    return {
        "id": str(item.id),
        "type": item.type,
        "icon": item.icon,
        "label": item.label,
        "detail": item.detail,
    }


async def update_diet_item(db: Session, item_id, pet_id, label: str, detail: str = None) -> dict:
    """Update an existing diet item."""
    item = (
        db.query(DietItem)
        .filter(DietItem.id == item_id, DietItem.pet_id == pet_id)
        .first()
    )
    if not item:
        raise ValueError("Diet item not found")

    item.label = label
    item.detail = detail
    # Re-classify based on new label
    new_type, new_icon = classify_food(label, item.type)
    item.type = new_type
    item.icon = new_icon

    db.commit()
    return {
        "id": str(item.id),
        "type": item.type,
        "icon": item.icon,
        "label": item.label,
        "detail": item.detail,
    }


async def delete_diet_item(db: Session, item_id, pet_id) -> None:
    """Delete a diet item."""
    item = (
        db.query(DietItem)
        .filter(DietItem.id == item_id, DietItem.pet_id == pet_id)
        .first()
    )
    if not item:
        raise ValueError("Diet item not found")

    db.delete(item)
    db.commit()
    logger.info("Diet item deleted for pet %s: %s", pet_id, item.label)
