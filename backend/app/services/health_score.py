"""
PetCircle Phase 1 — Health Score Engine (Module 12)

Computes a pet's health score using a 6-category weighted formula.
This is the single source of truth for health scoring across the system.

Formula:
    Score = sum((category_score / 100) * category_weight for each category)

Categories and weights:
    Vaccines           25%  — ratio of up_to_date vaccine preventive records
    Deworming & Flea   20%  — ratio of up_to_date deworming/flea records
    Conditions         20%  — ratio of managed medications + monitored items
    Nutrition          20%  — based on diet item count (0→0%, 1-2→60%, 3+→100%)
    Grooming           10%  — ratio of hygiene preferences with last_done recorded
    Checkups            5%  — ratio of up_to_date checkup records

Item classification uses keyword matching on preventive_master.item_name.
Cancelled records are excluded from all calculations.

Labels:
    >= 85  → Excellent
    >= 65  → Good
    >= 45  → Fair
    <  45  → Poor

Return structure:
    {
        "score": int,           # 0–100 weighted total
        "label": str,           # Excellent | Good | Fair | Poor
        "breakdown": [          # 6 items, one per category
            {
                "category": str,
                "key": str,
                "weight": int,
                "score": int,
                "done": int | None,
                "total": int | None,
            }
        ],
        "draggers": [           # categories with score < 50
            {"category": str, "score": int, "weight": int}
        ],
    }
"""

import logging
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.preventive_record import PreventiveRecord
from app.models.preventive_master import PreventiveMaster


logger = logging.getLogger(__name__)

# --- Category keywords for classifying preventive items ---
_VACCINE_KW = {"vaccine", "rabies", "dhpp", "core vaccine", "feline core", "bordetella"}
_DEWORMING_KW = {"deworming", "deworm"}
_FLEA_TICK_KW = {"tick", "flea"}
_CHECKUP_KW = {"checkup", "annual", "wellness", "blood test", "preventive blood"}

# --- Category weights (must sum to 1.0) ---
_CATEGORY_WEIGHTS = {
    "vaccines": 0.25,
    "deworming_flea": 0.20,
    "conditions": 0.20,
    "nutrition": 0.20,
    "grooming": 0.10,
    "checkups": 0.05,
}


def classify_preventive_item(item_name: str) -> str:
    """
    Classify a preventive item name into a health score category bucket.

    Uses keyword matching against item_name (case-insensitive).
    Returns 'checkups' as the default for unclassified items.

    Args:
        item_name: The preventive master item name to classify.

    Returns:
        One of: 'vaccines', 'deworming_flea', 'checkups'.
    """
    name_lower = item_name.lower()
    for kw in _VACCINE_KW:
        if kw in name_lower:
            return "vaccines"
    for kw in _DEWORMING_KW:
        if kw in name_lower:
            return "deworming_flea"
    for kw in _FLEA_TICK_KW:
        if kw in name_lower:
            return "deworming_flea"
    for kw in _CHECKUP_KW:
        if kw in name_lower:
            return "checkups"
    return "checkups"


def compute_health_score(db: Session, pet_id: UUID) -> dict:
    """
    Compute the 6-category health score for a pet.

    This is the single authoritative health score used across the system
    (dashboard, query engine, AI insights). All categories and weights
    are defined in this module — never duplicated elsewhere.

    Args:
        db: SQLAlchemy database session.
        pet_id: UUID of the pet to compute score for.

    Returns:
        Dict with keys: score, label, breakdown, draggers.
        See module docstring for full structure.
    """
    # --- Preventive records: vaccines / deworming_flea / checkups buckets ---
    records = (
        db.query(PreventiveRecord, PreventiveMaster)
        .join(
            PreventiveMaster,
            PreventiveRecord.preventive_master_id == PreventiveMaster.id,
        )
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveRecord.status != "cancelled",
        )
        .all()
    )

    score_buckets: dict[str, dict[str, int]] = {
        "vaccines": {"done": 0, "total": 0},
        "deworming_flea": {"done": 0, "total": 0},
        "checkups": {"done": 0, "total": 0},
    }
    for record, master in records:
        bucket = classify_preventive_item(master.item_name)
        score_buckets[bucket]["total"] += 1
        if record.status == "up_to_date":
            score_buckets[bucket]["done"] += 1

    def _bucket_pct(bucket: dict[str, int]) -> float:
        if bucket["total"] == 0:
            return 0.0
        return (bucket["done"] / bucket["total"]) * 100

    vaccines_pct = _bucket_pct(score_buckets["vaccines"])
    deworming_flea_pct = _bucket_pct(score_buckets["deworming_flea"])
    checkups_pct = _bucket_pct(score_buckets["checkups"])

    # --- Conditions score (20%) ---
    # Full score if no active conditions.
    # Otherwise: ratio of managed medications + monitored items with last_done_date.
    from app.models.condition import Condition
    condition_rows = (
        db.query(Condition)
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .all()
    )
    conditions_score = 100.0
    if condition_rows:
        cond_done = 0
        cond_total = 0
        for cond in condition_rows:
            for med in cond.medications:
                cond_total += 1
                if med.status in ("active", "completed"):
                    cond_done += 1
            for mon in cond.monitoring:
                cond_total += 1
                if mon.last_done_date:
                    cond_done += 1
        if cond_total > 0:
            conditions_score = (cond_done / cond_total) * 100
        else:
            # Conditions exist but no meds/monitoring tracked — partial credit.
            conditions_score = 50.0

    # --- Nutrition score (20%) ---
    # Based on diet item count: 0 items → 0%, 1–2 → 60%, 3+ → 100%.
    from app.models.diet_item import DietItem
    diet_count = db.query(DietItem).filter(DietItem.pet_id == pet_id).count()
    if diet_count >= 3:
        nutrition_score = 100.0
    elif diet_count >= 1:
        nutrition_score = 60.0
    else:
        nutrition_score = 0.0

    # --- Grooming score (10%) ---
    # Ratio of hygiene preference items that have a last_done date recorded.
    from app.models.hygiene_preference import HygienePreference
    hygiene_items = (
        db.query(HygienePreference)
        .filter(HygienePreference.pet_id == pet_id)
        .all()
    )
    if hygiene_items:
        hygiene_done = sum(1 for h in hygiene_items if h.last_done)
        grooming_score = (hygiene_done / len(hygiene_items)) * 100
    else:
        grooming_score = 0.0

    # --- Build breakdown ---
    breakdown = [
        {
            "category": "Vaccines",
            "key": "vaccines",
            "weight": 25,
            "score": round(vaccines_pct),
            "done": score_buckets["vaccines"]["done"],
            "total": score_buckets["vaccines"]["total"],
        },
        {
            "category": "Deworming & Flea",
            "key": "deworming_flea",
            "weight": 20,
            "score": round(deworming_flea_pct),
            "done": score_buckets["deworming_flea"]["done"],
            "total": score_buckets["deworming_flea"]["total"],
        },
        {
            "category": "Conditions",
            "key": "conditions",
            "weight": 20,
            "score": round(conditions_score),
            "done": None,
            "total": None,
        },
        {
            "category": "Nutrition",
            "key": "nutrition",
            "weight": 20,
            "score": round(nutrition_score),
            "done": None,
            "total": None,
        },
        {
            "category": "Grooming",
            "key": "grooming",
            "weight": 10,
            "score": round(grooming_score),
            "done": sum(1 for h in hygiene_items if h.last_done) if hygiene_items else 0,
            "total": len(hygiene_items) if hygiene_items else 0,
        },
        {
            "category": "Checkups",
            "key": "checkups",
            "weight": 5,
            "score": round(checkups_pct),
            "done": score_buckets["checkups"]["done"],
            "total": score_buckets["checkups"]["total"],
        },
    ]

    # --- Weighted total ---
    raw_score = sum((b["score"] / 100) * b["weight"] for b in breakdown)

    # --- Label ---
    if raw_score >= 85:
        label = "Excellent"
    elif raw_score >= 65:
        label = "Good"
    elif raw_score >= 45:
        label = "Fair"
    else:
        label = "Poor"

    # --- Draggers: categories pulling score below 50% ---
    draggers = [
        {"category": b["category"], "score": b["score"], "weight": b["weight"]}
        for b in breakdown
        if b["score"] < 50
    ]

    score = round(raw_score)

    logger.info(
        "Health score computed: pet_id=%s, score=%d (%s)",
        str(pet_id),
        score,
        label,
    )

    return {
        "score": score,
        "label": label,
        "breakdown": breakdown,
        "draggers": draggers,
    }
