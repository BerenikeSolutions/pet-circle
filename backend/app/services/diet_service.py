"""
PetCircle Phase 1 — Diet Service

CRUD operations for pet diet items (packaged food, homemade food, supplements).
Auto-classifies food type based on brand keyword matching.
Parses free-text nutrition detail into standardised format.
"""

import logging
import re

from sqlalchemy.orm import Session

from app.models.diet_item import DietItem

logger = logging.getLogger(__name__)


async def _refresh_recognition_bullets_for_pet(db: Session, pet_id) -> None:
    """Recompute and cache recognition_bullets after a diet item change.

    Imported lazily to avoid circular imports (ai_insights_service → diet_item model,
    not diet_service). Called after any write to diet items so all callers
    (dashboard API, WhatsApp onboarding flow, agentic edit) stay consistent.
    """
    try:
        from app.models.pet import Pet
        from app.services.ai_insights_service import generate_recognition_bullets
        from app.services.precompute_service import _upsert_insight

        pet = db.query(Pet).filter(Pet.id == pet_id).first()
        if not pet:
            return
        bullets = await generate_recognition_bullets(db, pet)
        _upsert_insight(db, pet_id, "recognition_bullets", bullets)
    except Exception as exc:
        logger.warning("Failed to refresh recognition_bullets for pet=%s: %s", pet_id, exc)

# Keywords that indicate packaged food
PACKAGED_KW = [
    "royal canin", "pedigree", "hills", "drools", "purina", "kibble",
    "wet food", "can", "pouch", "whiskas", "iams", "eukanuba",
    "orijen", "acana", "farmina", "science diet", "pro plan",
]

# Keywords that indicate homemade / home-cooked food
HOMEMADE_KW = [
    # Explicit markers
    "home", "homemade", "home made", "home-made", "ghar ka",
    # Grains & staples
    "khichdi", "dal", "roti", "rice", "chapati", "paratha", "dalia",
    "oats", "porridge", "upma", "idli", "dosa",
    # Proteins
    "chicken", "egg", "mutton", "fish", "paneer", "tofu",
    "liver", "keema",
    # Vegetables
    "carrot", "pumpkin", "lauki", "bottle gourd", "sweet potato",
    "potato", "beans", "spinach", "palak", "beetroot", "broccoli",
    "zucchini", "cucumber", "cabbage", "cauliflower",
    # Dairy
    "curd", "yogurt", "yoghurt", "dahi", "buttermilk", "chaas",
    "cottage cheese",
    # Cooking methods (indicate homemade)
    "boiled", "cooked", "steamed", "baked", "mashed", "grilled",
    "sauteed", "stewed",
    # Fruits (given as home treats)
    "apple", "banana", "watermelon", "papaya", "mango",
]

# ── Supplement ambiguity resolution ─────────────────────────────────
SUPPLEMENT_AMBIGUITY_MAP: dict[str, list[str]] = {
    "omega": ["Omega-3", "Omega-6", "Omega-9"],
    "vitamin b": ["B1", "B2", "B3", "B5", "B6", "B7", "B9", "B12", "B-complex"],
    "collagen": ["Type I", "Type II", "Type III"],
    "probiotics": ["Lactobacillus spp.", "Bifidobacterium spp.", "Enterococcus spp.", "multi-strain blends"],
    "joint supplement": ["Glucosamine", "Chondroitin", "MSM", "Hyaluronic acid", "combination formulas"],
    "calming supplement": ["L-theanine", "Melatonin", "Chamomile", "Valerian root", "Tryptophan blends"],
    "skin & coat supplement": ["Omega fatty acids", "Biotin", "Zinc", "Vitamin E", "combination formulas"],
    "digestive supplement": ["Probiotics", "Prebiotics", "Digestive enzymes", "fiber blends"],
    "immune support": ["Beta-glucans", "Colostrum", "Vitamins", "Herbal blends"],
    "herbal supplement": ["Ginseng types", "Ashwagandha extracts", "Turmeric/curcumin forms"],
}


def resolve_supplement_coverage(label: str) -> list[str] | None:
    """Return covered sub-types for a generic supplement label, or None if specific.

    Matching rule: normalized label equals a key, OR starts with a key where
    the next character is NOT a hyphen or digit (which indicates a specific
    variant, e.g. "Omega-3" or "B12").
    Keys are tested longest-first to avoid shorter keys shadowing longer ones.
    """
    normalized = label.strip().lower()
    for key in sorted(SUPPLEMENT_AMBIGUITY_MAP, key=len, reverse=True):
        if normalized == key:
            return SUPPLEMENT_AMBIGUITY_MAP[key]
        if normalized.startswith(key) and len(normalized) > len(key):
            next_char = normalized[len(key)]
            if next_char != "-" and not next_char.isdigit():
                return SUPPLEMENT_AMBIGUITY_MAP[key]
    return None


def expand_supplement_labels(labels: list[str]) -> list[str]:
    """Expand ambiguous generic supplement labels to their covered sub-types.

    Specific labels are kept as-is. Result is deduplicated (insertion order).
    Example: ["Omega", "Omega-3"] → ["Omega-3", "Omega-6", "Omega-9"]
    ("Omega-3" is dropped because it was already added when "Omega" expanded.)
    """
    seen: set[str] = set()
    result: list[str] = []
    for label in labels:
        expanded = resolve_supplement_coverage(label)
        entries = expanded if expanded is not None else [label]
        for entry in entries:
            if entry not in seen:
                seen.add(entry)
                result.append(entry)
    return result


# ── Frequency word → multiplier and period ──────────────────────────
_FREQ_WORDS: dict[str, tuple[int, str]] = {
    "daily": (1, "day"),
    "everyday": (1, "day"),
    "once a day": (1, "day"),
    "once daily": (1, "day"),
    "twice a day": (2, "day"),
    "twice daily": (2, "day"),
    "two times a day": (2, "day"),
    "two times per day": (2, "day"),
    "two times daily": (2, "day"),
    "thrice a day": (3, "day"),
    "thrice daily": (3, "day"),
    "three times a day": (3, "day"),
    "three times per day": (3, "day"),
    "three times daily": (3, "day"),
    "once a week": (1, "week"),
    "once weekly": (1, "week"),
    "weekly": (1, "week"),
    "twice a week": (2, "week"),
    "twice weekly": (2, "week"),
    "two times a week": (2, "week"),
    "two times per week": (2, "week"),
    "two times weekly": (2, "week"),
    "thrice a week": (3, "week"),
    "thrice weekly": (3, "week"),
    "three times a week": (3, "week"),
    "three times per week": (3, "week"),
    "three times weekly": (3, "week"),
    "four times a week": (4, "week"),
    "five times a week": (5, "week"),
    "once a month": (1, "month"),
    "monthly": (1, "month"),
    "twice a month": (2, "month"),
    "alternate days": (1, "alternate day"),
    "every other day": (1, "alternate day"),
}

# Regex: "Nx/day", "2x/week", "3x daily" etc.
_RE_NX = re.compile(
    r'(\d+)\s*(?:x|times)\s*/?\s*(day|week|month|daily|weekly|monthly)',
    re.IGNORECASE,
)

# Regex: quantity like "280g", "100 ml", "50 gm", "2 cups", "1 tablet", "1 scoop"
_RE_QTY = re.compile(
    r'(\d+(?:\.\d+)?)\s*(g|gm|gms|grams?|kg|ml|l|ltr|cups?|tablets?|tabs?|scoops?|tsp|tbsp|pieces?|pcs?)\b',
    re.IGNORECASE,
)

# Regex: "qty unit x N/period" — already formatted (pass through)
_RE_ALREADY_FORMATTED = re.compile(
    r'(\d+(?:\.\d+)?)\s*(g|kg|ml|L|cups?|tablets?|scoops?|tsp|tbsp)\s*x\s*\d+\s*/\s*(day|week|month)',
    re.IGNORECASE,
)

# Regex: "qty_unit * N" or "qty_unit x N" (with unit before multiplier) e.g. "280g*2", "100ml x 3"
_RE_QTY_MULT = re.compile(
    r'(\d+(?:\.\d+)?)\s*(g|gm|gms|grams?|kg|ml|l|ltr|cups?|tablets?|tabs?|scoops?|tsp|tbsp|pieces?|pcs?)'
    r'\s*[*×]\s*(\d+)',
    re.IGNORECASE,
)

# Regex: bare multiplier like "280*2" (no unit — default to grams)
_RE_BARE_MULT = re.compile(r'(\d+(?:\.\d+)?)\s*[*×]\s*(\d+)')

# Normalise unit abbreviations
_UNIT_MAP: dict[str, str] = {
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
    "kg": "kg", "ml": "ml", "l": "L", "ltr": "L",
    "cup": "cup", "cups": "cups",
    "tablet": "tablet", "tablets": "tablets", "tab": "tablet", "tabs": "tablets",
    "scoop": "scoop", "scoops": "scoops",
    "tsp": "tsp", "tbsp": "tbsp",
    "piece": "pc", "pieces": "pcs", "pc": "pc", "pcs": "pcs",
}

# Period word normalisation for "Nx/daily" → "Nx/day"
_PERIOD_NORM: dict[str, str] = {
    "daily": "day", "weekly": "week", "monthly": "month",
    "day": "day", "week": "week", "month": "month",
}


def normalize_diet_label(value: str | None) -> str:
    """Normalize a diet/supplement label for tolerant duplicate checks."""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", (value or "").strip().lower())
    return " ".join(cleaned.split())


def split_diet_items_by_type(diet_items: list) -> dict[str, list[str]]:
    """
    Split diet items into explicit food and supplement buckets.

    Returns:
        {
            "foods": [...],        # packaged + homemade (all food types)
            "packaged": [...],     # only packaged/commercial pet products
            "supplements": [...],
            "other": [...]
        }
    """
    buckets: dict[str, list[str]] = {"foods": [], "packaged": [], "supplements": [], "other": []}
    for item in diet_items or []:
        label = (getattr(item, "label", "") or "").strip()
        if not label:
            continue
        item_type = (getattr(item, "type", "") or "").strip().lower()
        if item_type == "supplement":
            buckets["supplements"].append(label)
        elif item_type == "packaged":
            buckets["foods"].append(label)
            buckets["packaged"].append(label)
        elif item_type == "homemade":
            buckets["foods"].append(label)
        else:
            buckets["other"].append(label)
    return buckets


def _fmt_unit(raw_unit: str) -> str:
    """Normalise a unit string."""
    return _UNIT_MAP.get(raw_unit.lower(), raw_unit)


def _fmt_qty(amount: str, unit: str) -> str:
    """Format quantity: '100g' (compact) or '1 tablet' (with space)."""
    if unit in ("g", "kg", "ml", "L"):
        return f"{amount}{unit}"
    return f"{amount} {unit}"


def _remove_span(text: str, start: int, end: int) -> str:
    """Remove a span from text."""
    return text[:start] + text[end:]


def _clean_remainder(text: str) -> str:
    """Strip leading/trailing separators and whitespace."""
    return re.sub(r'^[\s\-–—.,/]+|[\s\-–—.,/]+$', '', text).strip()


def parse_nutrition_detail(raw: str | None) -> str | None:
    """
    Parse free-text nutrition detail into a standardised short format.

    Examples:
        "280*2 - Dry kibble"  → "280g x 2/day . Dry kibble"
        "100g thrice a week"  → "100g x 3/week"
        "50g daily"           → "50g . Daily"
        "two times per week"  → "2x/week"
        "1 tablet daily"      → "1 tablet . Daily"
        "280g x 2/day"        → "280g x 2/day" (pass-through)

    Returns the normalised string, or the original if no pattern matches.
    """
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # Pass-through: already in "QTY x N/period" format
    if _RE_ALREADY_FORMATTED.search(text):
        remainder = _clean_remainder(_RE_ALREADY_FORMATTED.sub('', text))
        formatted = _RE_ALREADY_FORMATTED.search(text).group(0)  # type: ignore[union-attr]
        if remainder:
            return f"{formatted} . {remainder}"
        return formatted

    qty_str: str | None = None
    freq_str: str | None = None
    working = text

    # 1. "280g*2" or "100ml×3" — quantity with unit then multiplier
    qm = _RE_QTY_MULT.search(working)
    if qm:
        unit = _fmt_unit(qm.group(2))
        qty_str = f"{qm.group(1)}{unit} x {qm.group(3)}/day"
        working = _remove_span(working, qm.start(), qm.end())
    else:
        # 2. "280*2" — bare number multiplier (assume grams)
        bm = _RE_BARE_MULT.search(working)
        if bm:
            qty_str = f"{bm.group(1)}g x {bm.group(2)}/day"
            working = _remove_span(working, bm.start(), bm.end())

    # 3. Extract standalone quantity if not already captured via multiplier
    if not qty_str:
        qm2 = _RE_QTY.search(working)
        if qm2:
            unit = _fmt_unit(qm2.group(2))
            qty_str = _fmt_qty(qm2.group(1), unit)
            working = _remove_span(working, qm2.start(), qm2.end())

    # 4. Extract frequency — word phrases first (longest match), then Nx patterns
    lower_working = working.lower()
    for phrase, (count, period) in sorted(_FREQ_WORDS.items(), key=lambda x: -len(x[0])):
        idx = lower_working.find(phrase)
        if idx == -1:
            continue
        if period == "alternate day":
            freq_str = "Alternate days"
        elif count == 1:
            freq_str = period.capitalize()
        else:
            freq_str = f"{count}x/{period}"
        working = _remove_span(working, idx, idx + len(phrase))
        break

    if not freq_str:
        nx = _RE_NX.search(working)
        if nx:
            period = _PERIOD_NORM.get(nx.group(2).lower(), nx.group(2).lower())
            freq_str = f"{nx.group(1)}x/{period}"
            working = _remove_span(working, nx.start(), nx.end())

    # 5. Collect remaining text
    remainder = _clean_remainder(working)

    # 6. Build result: "qty_part . freq_part . remainder"
    parts: list[str] = []
    if qty_str:
        parts.append(qty_str)
    # Add freq only if qty doesn't already contain a "/period" (from multiplier)
    if freq_str and not (qty_str and "/" in qty_str):
        parts.append(freq_str)
    if remainder:
        parts.append(remainder)

    if not parts:
        return text

    return " . ".join(parts)


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
    for kw in HOMEMADE_KW:
        if kw in label_lower:
            return "homemade", "🥗"
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
    """Add a food or supplement item to a pet's diet.

    Idempotent: if a diet item with the same (pet_id, label, type) already
    exists the existing record is returned without modification.
    """
    classified_type, default_icon = classify_food(label, food_type)

    # Guard against duplicate-key violation on uq_diet_item_menu (pet_id, label, type)
    existing = (
        db.query(DietItem)
        .filter(
            DietItem.pet_id == pet_id,
            DietItem.label == label,
            DietItem.type == classified_type,
        )
        .first()
    )
    if existing:
        logger.debug(
            "Diet item already exists for pet %s: %s (%s) — skipping insert",
            pet_id, label, classified_type,
        )
        return {
            "id": str(existing.id),
            "type": existing.type,
            "icon": existing.icon,
            "label": existing.label,
            "detail": existing.detail,
        }

    item = DietItem(
        pet_id=pet_id,
        type=classified_type,
        icon=icon or default_icon,
        label=label,
        detail=parse_nutrition_detail(detail),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    logger.info("Diet item added for pet %s: %s (%s)", pet_id, label, classified_type)

    # Refresh the cached recognition bullets so "What We Found" reflects the new item.
    await _refresh_recognition_bullets_for_pet(db, pet_id)

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
    item.detail = parse_nutrition_detail(detail)
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
