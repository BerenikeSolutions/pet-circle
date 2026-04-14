"""
PetCircle — Signal Resolver (cart-rules-engine)

Deterministic engine that resolves food (A1-A6) and supplement (B1-B4)
products for a pet's care plan. Given a DietItem plus the owning Pet and
its active Conditions, it infers the *signal level* — how much the system
already knows about what the pet eats — and returns the appropriate
product set and CTA metadata.

This module is pure Python / SQLAlchemy — **no AI**. See
``.spec/cart-rules-engine/design.md`` (ADR-2) for the rationale, and
``.spec/cart-rules-engine/requirements.md`` for the full rule list.

Signal priority (highest → lowest):
    Brand > Product Line > Pack Size > Health Condition > Breed > Life Stage

Food signal levels:
    L5  — Brand + product_line + pack_size known
    L4  — Brand + product_line known
    L3  — Brand only
    L2c — No brand, but active health condition(s)
    L2b — No brand / no condition, but breed tag match
    L2  — No brand / no condition / no breed match, but life stage or breed size
    L1  — Nothing known

Both sides are implemented: ``resolve_food_signal`` (A1-A6) and
``resolve_supplement_signal`` (B1-B4).

Supplement signal levels:
    L5  — Brand + type + pack_size known (exact SKU)
    L4  — Brand + type known (size unknown)
    L3  — Type only known (brand unknown)
    L1  — Generic mention ("vitamins", "supplements")
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.condition import Condition
from app.models.diet_item import DietItem
from app.models.pet import Pet
from app.models.product_food import ProductFood
from app.models.product_supplement import ProductSupplement

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public enums / dataclasses
# ---------------------------------------------------------------------------


class SignalLevel(StrEnum):
    """How precisely the system can resolve a pet's diet item."""

    L5 = "L5"    # Exact SKU (brand + line + size)
    L4 = "L4"    # Product known (brand + line)
    L3 = "L3"    # Brand only
    L2 = "L2"    # Category + life stage / breed size
    L2B = "L2b"  # Breed-specific
    L2C = "L2c"  # Health condition specific
    L1 = "L1"    # No data


@dataclass
class SignalResult:
    """Container returned by ``resolve_food_signal`` / supplement counterpart."""

    level: SignalLevel
    products: list[dict] = field(default_factory=list)  # max 3 (C8)
    cta_label: str | None = None      # "Order Now →" for L2+, None for L1
    highlight_sku: str | None = None  # Pre-selected SKU (L5 / L4 most popular)
    message: str | None = None        # Info prompt shown for L1


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_OPTIONS = 3  # Rule C8 — never return more than 3 products

# L1 prompt (Rule A6). The actual WhatsApp nudge is triggered elsewhere;
# this message is what the dashboard card renders.
L1_MESSAGE = (
    "Share your pet's food brand on WhatsApp so we can help you reorder."
)

CTA_ORDER_NOW = "Order Now →"

# Rough breed → size hints. Kept intentionally small; fallback is by weight.
_LARGE_BREED_KEYWORDS = (
    "labrador", "golden retriever", "german shepherd", "rottweiler",
    "great dane", "saint bernard", "mastiff", "boxer", "doberman",
    "husky", "akita", "bernese", "newfoundland",
)
_SMALL_BREED_KEYWORDS = (
    "chihuahua", "pomeranian", "shih tzu", "pug", "dachshund",
    "maltese", "yorkie", "yorkshire", "beagle", "toy", "papillon",
    "lhasa", "bichon", "pekingese",
)

# Life stage thresholds (years)
_PUPPY_MAX_YEARS = 1
_SENIOR_MIN_YEARS = 7


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _normalize(text: str | None) -> str:
    """Lowercase + collapse whitespace for case-insensitive matching."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def _extract_brand(db: Session, diet_item: DietItem) -> str | None:
    """
    Return the canonical ``brand_name`` from ``product_food`` that matches
    the diet item's brand/label, or ``None`` if no brand is recognised.

    Matching is case-insensitive substring. We compare against every
    distinct brand_name currently in product_food (a small set — ~10 rows
    — so the round-trip is cheap and always current).
    """
    haystack = " ".join(filter(None, [diet_item.brand, diet_item.label]))
    haystack_norm = _normalize(haystack)
    if not haystack_norm:
        return None

    brand_rows = db.query(ProductFood.brand_name).distinct().all()
    # Prefer the longest match so "Hills Science Diet" wins over "Hills".
    best: str | None = None
    best_len = 0
    for (brand,) in brand_rows:
        if not brand:
            continue
        if _normalize(brand) in haystack_norm and len(brand) > best_len:
            best = brand
            best_len = len(brand)
    return best


def _extract_product_line(
    db: Session, diet_item: DietItem, brand_name: str
) -> str | None:
    """
    Case-insensitive substring match of ``diet_item.label`` against the
    product_line values belonging to ``brand_name``. Longest match wins
    (so "Labrador Adult" wins over "Adult").
    """
    label_norm = _normalize(diet_item.label)
    if not label_norm:
        return None

    line_rows = (
        db.query(ProductFood.product_line)
        .filter(ProductFood.brand_name == brand_name)
        .distinct()
        .all()
    )
    best: str | None = None
    best_len = 0
    for (line,) in line_rows:
        if not line:
            continue
        if _normalize(line) in label_norm and len(line) > best_len:
            best = line
            best_len = len(line)
    return best


def _extract_pack_size_kg(diet_item: DietItem) -> float | None:
    """
    Return pack size in kilograms parsed from the diet item.

    Preference order:
        1. ``pack_size_g`` column (authoritative, stored in grams)
        2. A numeric ``kg`` / ``g`` token in the free-text ``detail`` field
    """
    if diet_item.pack_size_g:
        return round(diet_item.pack_size_g / 1000.0, 2)

    detail = diet_item.detail or ""
    # Look for "<num> kg" or "<num>kg" first (e.g. "7 kg", "1.5kg")
    kg_match = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", detail, re.IGNORECASE)
    if kg_match:
        return float(kg_match.group(1))

    g_match = re.search(r"(\d+(?:\.\d+)?)\s*g\b", detail, re.IGNORECASE)
    if g_match:
        return round(float(g_match.group(1)) / 1000.0, 2)

    return None


# ---------------------------------------------------------------------------
# Pet profile helpers
# ---------------------------------------------------------------------------


def _get_pet_life_stage(pet: Pet) -> str:
    """Derive life stage from DOB. Returns 'Puppy' / 'Adult' / 'Senior'."""
    if not pet.dob:
        return "Adult"  # safe default when DOB unknown
    today = date.today()
    years = (today - pet.dob).days / 365.25
    if years < _PUPPY_MAX_YEARS:
        return "Puppy"
    if years >= _SENIOR_MIN_YEARS:
        return "Senior"
    return "Adult"


def _get_breed_size(pet: Pet) -> str:
    """
    Derive breed size ('Small' / 'Medium' / 'Large') from breed name or
    weight. Falls back to weight when the breed string is unrecognised.
    """
    breed_norm = _normalize(pet.breed)
    if breed_norm:
        if any(kw in breed_norm for kw in _LARGE_BREED_KEYWORDS):
            return "Large"
        if any(kw in breed_norm for kw in _SMALL_BREED_KEYWORDS):
            return "Small"

    # Weight-based fallback. pet.weight is Numeric(5,2) → cast safely.
    try:
        weight_kg = float(pet.weight) if pet.weight is not None else None
    except (TypeError, ValueError):
        weight_kg = None

    if weight_kg is not None:
        if weight_kg >= 25:
            return "Large"
        if weight_kg <= 10:
            return "Small"
        return "Medium"

    return "Medium"  # default when neither breed nor weight are usable


def _condition_tags(conditions: Iterable[Condition]) -> set[str]:
    """Return active condition names, lowercased, as a set of tag tokens."""
    tags: set[str] = set()
    for cond in conditions or []:
        if not cond or not getattr(cond, "is_active", True):
            continue
        if cond.name:
            tags.add(cond.name.strip().lower())
    return tags


def _row_tag_list(raw: str | None) -> list[str]:
    """Split a comma-separated tag column into a lowercase token list."""
    if not raw:
        return []
    return [t.strip().lower() for t in raw.split(",") if t.strip()]


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def _score_product(
    product: ProductFood,
    *,
    condition_tags: set[str],
    life_stage: str,
    breed_size: str,
    breed_norm: str,
) -> tuple:
    """
    Ranking key — LOWER is better, so sort ascending.

    Order of precedence (requirement 3.9):
        condition_match > life_stage > breed_size > popularity_rank.
    """
    cond_hit = 0 if (condition_tags & set(_row_tag_list(product.condition_tags))) else 1
    life_hit = 0 if product.life_stage in (life_stage, "All") else 1
    size_hit = 0 if product.breed_size in (breed_size, "All") else 1
    breed_hit = 0
    if breed_norm:
        product_breed_tags = _row_tag_list(product.breed_tags)
        # e.g. "labrador retriever" should hit the "labrador" tag
        breed_hit = 0 if any(tag in breed_norm for tag in product_breed_tags) else 1
    return (cond_hit, life_hit, size_hit, breed_hit, product.popularity_rank or 999)


def _filter_active(query):
    """Add the always-on active filter to a ProductFood query."""
    return query.filter(ProductFood.active.is_(True))


def _apply_oos_rule(products: list[ProductFood]) -> list[ProductFood]:
    """
    C2: exclude out-of-stock from primary position. If *every* candidate
    is OOS, return the original list so the caller can still surface a
    'nearest in-stock' alternative via serialize.
    """
    in_stock = [p for p in products if p.in_stock]
    return in_stock if in_stock else products


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize_food_product(product: ProductFood, is_highlighted: bool) -> dict:
    """
    Standard product dict returned in ``SignalResult.products``.

    Keys match the API contract in design.md §API — ``/products/resolve``.
    """
    return {
        "sku_id": product.sku_id,
        "category": "food",
        "brand_name": product.brand_name,
        "product_line": product.product_line,
        "pack_size": f"{_format_pack_size(product.pack_size_kg)} kg",
        "pack_size_kg": float(product.pack_size_kg),
        "mrp": int(product.mrp),
        "discounted_price": int(product.discounted_price),
        "price_per_unit": int(product.price_per_kg) if product.price_per_kg else None,
        "unit_label": "per kg",
        "in_stock": bool(product.in_stock),
        "vet_diet_flag": bool(product.vet_diet_flag),
        "is_highlighted": is_highlighted,
    }


def _format_pack_size(value) -> str:
    """Render Numeric(5,1) as "7" or "1.5" — trim trailing zeros."""
    num = float(value)
    if num.is_integer():
        return str(int(num))
    return f"{num:g}"


# ---------------------------------------------------------------------------
# Level-specific resolvers (A1 – A6)
# ---------------------------------------------------------------------------


def _resolve_l5(
    db: Session,
    brand_name: str,
    product_line: str,
    pack_size_kg: float,
) -> list[ProductFood]:
    """
    A1: exact SKU first, then up to 2 alternative pack sizes of the same
    line. If the requested pack size isn't found, the 'nearest' pack will
    still surface via the alt-size list and be highlighted instead.
    """
    lines = (
        _filter_active(db.query(ProductFood))
        .filter(
            ProductFood.brand_name == brand_name,
            ProductFood.product_line == product_line,
        )
        .all()
    )
    if not lines:
        return []

    # Exact match (tolerate Numeric vs float rounding).
    exact = [p for p in lines if abs(float(p.pack_size_kg) - pack_size_kg) < 0.05]
    alts = [p for p in lines if p not in exact]

    # Nearest first for alternatives, closest size wins.
    alts.sort(key=lambda p: abs(float(p.pack_size_kg) - pack_size_kg))

    primary = exact or alts[:1]       # A1.2: nearest when exact missing
    remaining = [p for p in lines if p not in primary]
    remaining.sort(key=lambda p: abs(float(p.pack_size_kg) - pack_size_kg))

    ordered = primary + remaining
    return _apply_oos_rule(ordered)[:MAX_OPTIONS]


def _resolve_l4(
    db: Session, brand_name: str, product_line: str
) -> list[ProductFood]:
    """A2: all pack sizes for the (brand, line) pair sorted by popularity."""
    rows = (
        _filter_active(db.query(ProductFood))
        .filter(
            ProductFood.brand_name == brand_name,
            ProductFood.product_line == product_line,
        )
        .order_by(ProductFood.popularity_rank.asc())
        .all()
    )
    return _apply_oos_rule(rows)[:MAX_OPTIONS]


def _resolve_l3(
    db: Session,
    brand_name: str,
    *,
    condition_tags: set[str],
    life_stage: str,
    breed_size: str,
    breed_norm: str,
) -> list[ProductFood]:
    """
    A3: brand is known, product line isn't. Show up to 3 distinct product
    lines from that brand, ranked by profile match.
    """
    rows = (
        _filter_active(db.query(ProductFood))
        .filter(ProductFood.brand_name == brand_name)
        .all()
    )
    rows = _apply_oos_rule(rows)
    rows.sort(
        key=lambda p: _score_product(
            p,
            condition_tags=condition_tags,
            life_stage=life_stage,
            breed_size=breed_size,
            breed_norm=breed_norm,
        )
    )

    # De-duplicate by product_line — show one SKU per line.
    seen_lines: set[str] = set()
    unique: list[ProductFood] = []
    for p in rows:
        if p.product_line in seen_lines:
            continue
        seen_lines.add(p.product_line)
        unique.append(p)
        if len(unique) == MAX_OPTIONS:
            break
    return unique


def _resolve_l2c(
    db: Session,
    *,
    condition_tags: set[str],
    life_stage: str,
    breed_size: str,
    breed_norm: str,
) -> list[ProductFood]:
    """A4 (condition variant): top 3 brands, one best product per brand."""
    rows = _filter_active(db.query(ProductFood)).all()

    # Keep only condition-matching rows.
    matched = [
        p
        for p in rows
        if condition_tags & set(_row_tag_list(p.condition_tags))
    ]
    matched = _apply_oos_rule(matched)
    matched.sort(
        key=lambda p: _score_product(
            p,
            condition_tags=condition_tags,
            life_stage=life_stage,
            breed_size=breed_size,
            breed_norm=breed_norm,
        )
    )

    return _pick_one_per_brand(matched)


def _resolve_l2b(
    db: Session,
    *,
    life_stage: str,
    breed_size: str,
    breed_norm: str,
    condition_tags: set[str],
) -> list[ProductFood]:
    """
    A5: breed known. Prefer lines whose ``breed_tags`` match the breed
    name; fall back to matching ``breed_size``.
    """
    rows = _filter_active(db.query(ProductFood)).all()

    breed_specific: list[ProductFood] = []
    if breed_norm:
        for p in rows:
            tags = _row_tag_list(p.breed_tags)
            if any(tag and tag != "all" and tag in breed_norm for tag in tags):
                breed_specific.append(p)

    if not breed_specific:
        breed_specific = [
            p for p in rows if p.breed_size in (breed_size, "All")
        ]

    breed_specific = _apply_oos_rule(breed_specific)
    breed_specific.sort(
        key=lambda p: _score_product(
            p,
            condition_tags=condition_tags,
            life_stage=life_stage,
            breed_size=breed_size,
            breed_norm=breed_norm,
        )
    )
    return _pick_one_per_brand(breed_specific)


def _resolve_l2(
    db: Session,
    *,
    condition_tags: set[str],
    life_stage: str,
    breed_size: str,
    breed_norm: str,
) -> list[ProductFood]:
    """
    A4 (profile variant): life stage / breed size known, no breed-tag
    match, no condition. Top 3 brands by profile fit.
    """
    rows = _filter_active(db.query(ProductFood)).all()
    rows = [
        p
        for p in rows
        if p.life_stage in (life_stage, "All")
        and p.breed_size in (breed_size, "All")
    ]
    rows = _apply_oos_rule(rows)
    rows.sort(
        key=lambda p: _score_product(
            p,
            condition_tags=condition_tags,
            life_stage=life_stage,
            breed_size=breed_size,
            breed_norm=breed_norm,
        )
    )
    return _pick_one_per_brand(rows)


def _pick_one_per_brand(products: list[ProductFood]) -> list[ProductFood]:
    """Take at most MAX_OPTIONS products, one per distinct brand_name."""
    seen_brands: set[str] = set()
    picked: list[ProductFood] = []
    for p in products:
        if p.brand_name in seen_brands:
            continue
        seen_brands.add(p.brand_name)
        picked.append(p)
        if len(picked) == MAX_OPTIONS:
            break
    return picked


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def resolve_food_signal(
    db: Session,
    diet_item: DietItem,
    pet: Pet,
    conditions: list[Condition] | None = None,
) -> SignalResult:
    """
    Resolve the food signal level and product set for ``diet_item``.

    Args:
        db: SQLAlchemy session.
        diet_item: The care-plan diet item to resolve. Must be of type
            'packaged' or 'homemade' — supplements are handled by
            ``resolve_supplement_signal``.
        pet: Owning pet (for life stage, breed, weight).
        conditions: Active conditions to consider for L2c / ranking.

    Returns:
        ``SignalResult`` with up to 3 products, never more (rule C8).
    """
    conditions = conditions or []
    cond_tags = _condition_tags(conditions)
    life_stage = _get_pet_life_stage(pet)
    breed_size = _get_breed_size(pet)
    breed_norm = _normalize(pet.breed)

    brand_name = _extract_brand(db, diet_item)
    product_line: str | None = None
    pack_size_kg: float | None = None
    if brand_name:
        product_line = _extract_product_line(db, diet_item, brand_name)
        if product_line:
            pack_size_kg = _extract_pack_size_kg(diet_item)

    # ---- L5 ----------------------------------------------------------------
    if brand_name and product_line and pack_size_kg is not None:
        products = _resolve_l5(db, brand_name, product_line, pack_size_kg)
        if products:
            return _build_result(SignalLevel.L5, products)

    # ---- L4 ----------------------------------------------------------------
    if brand_name and product_line:
        products = _resolve_l4(db, brand_name, product_line)
        if products:
            return _build_result(SignalLevel.L4, products)

    # ---- L3 ----------------------------------------------------------------
    if brand_name:
        products = _resolve_l3(
            db,
            brand_name,
            condition_tags=cond_tags,
            life_stage=life_stage,
            breed_size=breed_size,
            breed_norm=breed_norm,
        )
        if products:
            return _build_result(SignalLevel.L3, products)

    # ---- L2c (condition) ---------------------------------------------------
    if cond_tags:
        products = _resolve_l2c(
            db,
            condition_tags=cond_tags,
            life_stage=life_stage,
            breed_size=breed_size,
            breed_norm=breed_norm,
        )
        if products:
            return _build_result(SignalLevel.L2C, products)

    # ---- L2b (breed) -------------------------------------------------------
    if breed_norm:
        products = _resolve_l2b(
            db,
            life_stage=life_stage,
            breed_size=breed_size,
            breed_norm=breed_norm,
            condition_tags=cond_tags,
        )
        if products:
            return _build_result(SignalLevel.L2B, products)

    # ---- L2 (life stage / breed size) --------------------------------------
    if pet.dob or pet.weight is not None:
        products = _resolve_l2(
            db,
            condition_tags=cond_tags,
            life_stage=life_stage,
            breed_size=breed_size,
            breed_norm=breed_norm,
        )
        if products:
            return _build_result(SignalLevel.L2, products)

    # ---- L1 (no data) ------------------------------------------------------
    return SignalResult(
        level=SignalLevel.L1,
        products=[],
        cta_label=None,
        highlight_sku=None,
        message=L1_MESSAGE,
    )


def _build_result(level: SignalLevel, products: list[ProductFood]) -> SignalResult:
    """Wrap a ranked, trimmed product list into a ``SignalResult``."""
    products = products[:MAX_OPTIONS]
    highlight_sku = products[0].sku_id if products else None
    serialized = [
        _serialize_food_product(p, is_highlighted=(p.sku_id == highlight_sku))
        for p in products
    ]
    return SignalResult(
        level=level,
        products=serialized,
        cta_label=CTA_ORDER_NOW,
        highlight_sku=highlight_sku,
        message=None,
    )


# ===========================================================================
# Supplement resolver (B1 – B4)
# ===========================================================================


# Label keyword → canonical ``product_supplement.type`` value.
# Longest-matching keyword wins so "fish oil" beats "oil", and
# "multivitamin" beats "vitamin".
SUPPLEMENT_TYPE_KEYWORDS: dict[str, str] = {
    # ── Omega / fish oil ────────────────────────────────────────────────────
    "fish oil": "fish_oil",
    "salmon oil": "fish_oil",
    "omega": "fish_oil",
    # ── Joint support ───────────────────────────────────────────────────────
    "joint": "joint_supplement",
    "glucosamine": "joint_supplement",
    "mobility": "joint_supplement",
    # ── Vitamins / multivitamin ──────────────────────────────────────────────
    "multivitamin": "multivitamin",
    "vitamin": "multivitamin",
    "methylcobalamin": "multivitamin",   # B12 supplement without "vitamin" in label
    "cobalamin": "multivitamin",
    # ── Probiotics / digestive ───────────────────────────────────────────────
    "probiotic": "probiotic",
    "prebiotic": "probiotic",
    "gut": "probiotic",
    "lactobacillus": "probiotic",
    "enterococcus": "probiotic",
    "bacillus": "probiotic",
    "saccharomyces": "probiotic",
    "psyllium": "digestive_supplement",
    "pectin": "digestive_supplement",
    # ── Coat / skin ─────────────────────────────────────────────────────────
    "coat": "coat_supplement",
    "skin": "skin_supplement",
    # ── Kidney / urinary ────────────────────────────────────────────────────
    "kidney": "kidney_supplement",
    "renal": "kidney_supplement",        # word-boundary checked in extractor
    "urinary": "urinary_supplement",
    "bladder": "urinary_supplement",
    # ── Calming ─────────────────────────────────────────────────────────────
    "calming": "calming",
    "anxiety": "calming",
    "cbd": "calming",
    "chamomile": "calming",
    "valerian": "calming",
    "ashwagandha": "calming",
    # ── Liver support ───────────────────────────────────────────────────────
    "milk thistle": "liver_supplement",  # longer than "milk"; wins longest-match
    "silymarin": "liver_supplement",
    "silybum": "liver_supplement",
    "ursodeoxycholic": "liver_supplement",
    # ── Bone / mineral ──────────────────────────────────────────────────────
    "calcium": "bone_supplement",
    "phosphorus": "bone_supplement",
    # ── Anti-inflammatory ───────────────────────────────────────────────────
    "curcumin": "anti_inflammatory",
    "turmeric": "anti_inflammatory",
    # ── Milk replacer ───────────────────────────────────────────────────────
    "milk": "milk_replacer",             # "milk thistle" entry above wins first
    # ── Growth / performance ────────────────────────────────────────────────
    "growth": "growth_supplement",
    "creatine": "performance_supplement",
}

# Generic tokens that indicate L1 (user mentioned "supplement" with no
# identifiable type — e.g. "vitamins", "supplements"). These are checked
# only *after* the specific keyword map has failed.
_SUPPLEMENT_GENERIC_TOKENS = ("supplement", "supplements", "vitamins")

# Supplement form tokens (used as a hint during L5 matching).
_SUPPLEMENT_FORM_KEYWORDS = (
    "liquid", "chew", "chews", "powder", "paste", "tablet", "capsule",
)

# L1 info-capture prompt (Rule B4).
SUPPLEMENT_L1_MESSAGE = (
    "Share the supplement name on WhatsApp so we can help you reorder."
)


def _extract_supplement_type(diet_item: DietItem) -> str | None:
    """
    Map the free-text label/detail of a supplement diet item to a canonical
    ``product_supplement.type`` value. Returns ``None`` when the label is
    generic ("vitamins") or unrecognised.
    """
    haystack = _normalize(
        " ".join(filter(None, [diet_item.label, diet_item.detail]))
    )
    if not haystack:
        return None

    # Longest whole-word match wins (word-boundary check prevents "renal"
    # firing inside "adrenal", and "milk" firing inside "milk thistle").
    best_type: str | None = None
    best_len = 0
    for keyword, canonical in SUPPLEMENT_TYPE_KEYWORDS.items():
        if len(keyword) <= best_len:
            continue
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, haystack):
            best_type = canonical
            best_len = len(keyword)
    return best_type


def _extract_supplement_brand(
    db: Session, diet_item: DietItem
) -> str | None:
    """
    Return the canonical ``brand_name`` from ``product_supplement`` that
    matches the diet item's brand/label field. Longest match wins.
    """
    haystack = _normalize(
        " ".join(filter(None, [diet_item.brand, diet_item.label]))
    )
    if not haystack:
        return None

    brand_rows = db.query(ProductSupplement.brand_name).distinct().all()
    best: str | None = None
    best_len = 0
    for (brand,) in brand_rows:
        if not brand:
            continue
        if _normalize(brand) in haystack and len(brand) > best_len:
            best = brand
            best_len = len(brand)
    return best


def _extract_supplement_pack_size(diet_item: DietItem) -> str | None:
    """
    Extract a pack-size-like token from the diet item (e.g. ``"300 ml"``,
    ``"90 chews"``). Matches ``<num> <unit>`` where unit is one of
    ml / l / g / kg / chews / tablets / capsules / caps.

    Supplement pack_size is stored as a free-text string in the DB
    (``"300 ml"``, ``"90 chews"``), so we compare by normalized substring
    rather than a numeric parse.
    """
    text = " ".join(filter(None, [diet_item.detail, diet_item.label]))
    if not text:
        return None
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(ml|l|g|kg|chews?|tablets?|capsules?|caps)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return f"{match.group(1)} {match.group(2).lower()}"


def _extract_supplement_form(diet_item: DietItem) -> str | None:
    """Detect a form token (liquid/chew/powder/paste/tablet) in the label."""
    haystack = _normalize(
        " ".join(filter(None, [diet_item.label, diet_item.detail]))
    )
    if not haystack:
        return None
    for form in _SUPPLEMENT_FORM_KEYWORDS:
        if form in haystack:
            # Normalize chews → chew for DB match.
            return form.rstrip("s")
    return None


def _pack_sizes_match(dietitem_size: str, product_size: str) -> bool:
    """
    Loose comparison between a free-text pack-size token extracted from a
    diet item (e.g. "300 ml") and the catalog value ("300 ml"). Case- and
    whitespace-insensitive.
    """
    return _normalize(dietitem_size) == _normalize(product_size)


def _apply_oos_rule_supplement(
    products: list[ProductSupplement],
) -> list[ProductSupplement]:
    """C2: drop OOS for primary position; keep all if every candidate is OOS."""
    in_stock = [p for p in products if p.in_stock]
    return in_stock if in_stock else products


def _filter_active_supplement(query):
    """Always-on active filter for ProductSupplement queries."""
    return query.filter(ProductSupplement.active.is_(True))


def _serialize_supplement_product(
    product: ProductSupplement, is_highlighted: bool
) -> dict:
    """Standard product dict for ``SignalResult.products`` (supplement variant)."""
    return {
        "sku_id": product.sku_id,
        "category": "supplement",
        "brand_name": product.brand_name,
        "product_name": product.product_name,
        "type": product.type,
        "form": product.form,
        "pack_size": product.pack_size,
        "mrp": int(product.mrp),
        "discounted_price": int(product.discounted_price),
        "price_per_unit": int(product.price_per_unit) if product.price_per_unit else None,
        "unit_label": "per unit",
        "in_stock": bool(product.in_stock),
        "vet_diet_flag": False,  # Supplements do not require vet-diet warning
        "is_highlighted": is_highlighted,
        "highlight_reason": "Most Popular" if is_highlighted else None,
    }


# ---------------------------------------------------------------------------
# Level-specific resolvers (B1 – B4)
# ---------------------------------------------------------------------------


def _resolve_supplement_l5(
    db: Session,
    brand_name: str,
    sup_type: str,
    pack_size: str,
    form: str | None,
) -> list[ProductSupplement]:
    """
    B1: exact SKU lookup. Returns the exact match (plus up to 2 sibling
    pack sizes of the same brand+type as fall-back alternatives). If the
    exact pack size is not in stock, the nearest sibling is surfaced.
    """
    query = _filter_active_supplement(db.query(ProductSupplement)).filter(
        ProductSupplement.brand_name == brand_name,
        ProductSupplement.type == sup_type,
    )
    if form:
        # Form is a hint — tighten the query only if there are matches.
        form_filtered = query.filter(ProductSupplement.form == form).all()
        siblings = form_filtered or query.all()
    else:
        siblings = query.all()

    if not siblings:
        return []

    exact = [p for p in siblings if _pack_sizes_match(pack_size, p.pack_size)]
    alts = [p for p in siblings if p not in exact]
    # Stable alt ordering by popularity (closest sibling surfaces first).
    alts.sort(key=lambda p: p.popularity_rank or 999)

    primary = exact or alts[:1]  # B1.2: nearest variant when exact missing
    remaining = [p for p in siblings if p not in primary]
    remaining.sort(key=lambda p: p.popularity_rank or 999)

    ordered = primary + remaining
    return _apply_oos_rule_supplement(ordered)[:MAX_OPTIONS]


def _resolve_supplement_l4(
    db: Session, brand_name: str, sup_type: str
) -> list[ProductSupplement]:
    """B2: all pack sizes for (brand, type) sorted by popularity."""
    rows = (
        _filter_active_supplement(db.query(ProductSupplement))
        .filter(
            ProductSupplement.brand_name == brand_name,
            ProductSupplement.type == sup_type,
        )
        .order_by(ProductSupplement.popularity_rank.asc())
        .all()
    )
    return _apply_oos_rule_supplement(rows)[:MAX_OPTIONS]


def _resolve_supplement_l3(
    db: Session, sup_type: str
) -> list[ProductSupplement]:
    """
    B3: type known, brand unknown. Return 2 bestsellers (lowest
    popularity_rank) + 1 budget option (lowest discounted_price), each
    from a distinct brand where possible. Never more than 3.
    """
    rows = (
        _filter_active_supplement(db.query(ProductSupplement))
        .filter(ProductSupplement.type == sup_type)
        .all()
    )
    rows = _apply_oos_rule_supplement(rows)
    if not rows:
        return []

    # Two bestsellers: lowest popularity_rank, distinct brands.
    by_popularity = sorted(rows, key=lambda p: p.popularity_rank or 999)
    bestsellers: list[ProductSupplement] = []
    seen_brands: set[str] = set()
    for p in by_popularity:
        if p.brand_name in seen_brands:
            continue
        bestsellers.append(p)
        seen_brands.add(p.brand_name)
        if len(bestsellers) == 2:
            break

    # Budget: cheapest remaining SKU not already picked.
    picked_ids = {p.sku_id for p in bestsellers}
    remaining = [p for p in rows if p.sku_id not in picked_ids]
    budget: list[ProductSupplement] = []
    if remaining:
        cheapest = min(remaining, key=lambda p: int(p.discounted_price))
        budget.append(cheapest)

    return (bestsellers + budget)[:MAX_OPTIONS]


# ---------------------------------------------------------------------------
# Entry point — supplement
# ---------------------------------------------------------------------------


def resolve_supplement_signal(
    db: Session,
    diet_item: DietItem,
    pet: Pet,
    conditions: list[Condition] | None = None,
) -> SignalResult:
    """
    Resolve the supplement signal level and product set for ``diet_item``.

    Args:
        db: SQLAlchemy session.
        diet_item: Care-plan item with ``type='supplement'``.
        pet: Owning pet (unused today but kept parallel to the food API
            so callers can switch resolvers without changing the call
            site, and so future rules — e.g. life-stage filtering — have
            the data they need).
        conditions: Active conditions (reserved for future use).

    Returns:
        ``SignalResult`` with up to 3 products, never more (rule C8).
    """
    # ``pet`` and ``conditions`` are accepted for API parity; they are not
    # consulted by the current B1-B4 rules but will be needed if / when
    # B-side gains a profile-match tier.
    del pet, conditions

    brand_name = _extract_supplement_brand(db, diet_item)
    sup_type = _extract_supplement_type(diet_item)
    pack_size = _extract_supplement_pack_size(diet_item)
    form = _extract_supplement_form(diet_item)

    # ---- L5 ----------------------------------------------------------------
    if brand_name and sup_type and pack_size:
        products = _resolve_supplement_l5(
            db, brand_name, sup_type, pack_size, form
        )
        if products:
            return _build_supplement_result(SignalLevel.L5, products)

    # ---- L4 ----------------------------------------------------------------
    if brand_name and sup_type:
        products = _resolve_supplement_l4(db, brand_name, sup_type)
        if products:
            return _build_supplement_result(SignalLevel.L4, products)

    # ---- L3 ----------------------------------------------------------------
    if sup_type:
        products = _resolve_supplement_l3(db, sup_type)
        if products:
            return _build_supplement_result(SignalLevel.L3, products)

    # ---- Ingredient fallback -----------------------------------------------
    # When no products match by type (L3 empty), search key_ingredients using
    # the supplement label text.  This recovers products whose DB type column
    # differs from the SUPPLEMENT_TYPE_KEYWORDS mapping but whose
    # key_ingredients DO mention the nutrient (e.g. a product typed
    # "coat_supplement" that lists "Omega 3 & 6" in key_ingredients).
    # Uses SUPPLEMENT_AMBIGUITY_MAP to expand generic labels before searching
    # (e.g. "omega" → also search "omega 3", "omega 6", "omega 9").
    _STRIP_SUFFIXES = (
        "supplement", "tablet", "capsule", "capsules",
        "oil", "chew", "chews", "powder",
    )
    ingredient_term = _normalize(
        " ".join(filter(None, [diet_item.label, diet_item.detail]))
    ).replace("-", " ")
    for _suffix in _STRIP_SUFFIXES:
        if ingredient_term.endswith(f" {_suffix}"):
            ingredient_term = ingredient_term[: -(len(_suffix) + 1)].strip()
            break

    if ingredient_term:
        from app.services.diet_service import SUPPLEMENT_AMBIGUITY_MAP  # avoid circular at module level

        # Build a list of search terms: the base term + any expansions from the
        # ambiguity map (e.g. "omega" → ["omega 3", "omega 6", "omega 9"]).
        search_terms: list[str] = [ingredient_term]
        for key, expansions in SUPPLEMENT_AMBIGUITY_MAP.items():
            if ingredient_term == key or ingredient_term.startswith(key + " "):
                for exp in expansions:
                    search_terms.append(exp.lower().replace("-", " "))
                break

        conditions = [
            ProductSupplement.key_ingredients.ilike(f"%{t}%")
            for t in search_terms
        ]
        rows = (
            _filter_active_supplement(db.query(ProductSupplement))
            .filter(or_(*conditions))
            .order_by(ProductSupplement.popularity_rank)
            .limit(3)
            .all()
        )
        rows = _apply_oos_rule_supplement(rows)
        if rows:
            return _build_supplement_result(SignalLevel.L3, rows)

    # ---- L1 (generic mention) ----------------------------------------------
    return SignalResult(
        level=SignalLevel.L1,
        products=[],
        cta_label=None,
        highlight_sku=None,
        message=SUPPLEMENT_L1_MESSAGE,
    )


def _build_supplement_result(
    level: SignalLevel, products: list[ProductSupplement]
) -> SignalResult:
    """Wrap a ranked, trimmed supplement list into a ``SignalResult``."""
    products = products[:MAX_OPTIONS]
    highlight_sku = products[0].sku_id if products else None
    serialized = [
        _serialize_supplement_product(
            p, is_highlighted=(p.sku_id == highlight_sku)
        )
        for p in products
    ]
    return SignalResult(
        level=level,
        products=serialized,
        cta_label=CTA_ORDER_NOW,
        highlight_sku=highlight_sku,
        message=None,
    )
