"""
PetCircle Phase 8 — Cart & Orders Service

Manages the pet's shopping cart. Cart items are added by users or
generated as recommendations based on species, breed, life stage and
any diagnosed health conditions.

Key design:
    - No hardcoded cart items — everything from DB
    - Recommendations pulled from product_food + product_supplement
      (signal-level catalog tables, see .spec/cart-rules-engine/design.md)
    - Orders stored in the orders table for admin processing
    - cart_items.product_id stores the sku_id of a ProductFood (F###)
      or ProductSupplement (S###) row — the prefix disambiguates which
      table to query.
"""

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.models.cart_item import CartItem
from app.models.condition import Condition
from app.models.order import Order
from app.models.pet import Pet
from app.models.pet_preference import PetPreference
from app.models.product_food import ProductFood
from app.models.product_supplement import ProductSupplement
from app.models.user import User

logger = logging.getLogger(__name__)

# --- Constants ---
FREE_DELIVERY_THRESHOLD = 500  # Free delivery for orders >= Rs.500
DELIVERY_FEE = 49


# --- Catalog lookup helpers ---

def _lookup_sku(db: Session, sku_id: str):
    """
    Return the catalog row for a sku_id from product_food or product_supplement.

    The sku_id prefix determines the table (F### = food, S### = supplement).
    Returns a tuple (row, category) or (None, None) when not found.
    """
    if not sku_id:
        return None, None
    prefix = sku_id[:1].upper()
    if prefix == "F":
        row = db.query(ProductFood).filter(ProductFood.sku_id == sku_id).first()
        return row, "food"
    if prefix == "S":
        row = db.query(ProductSupplement).filter(ProductSupplement.sku_id == sku_id).first()
        return row, "supplement"
    return None, None


def _food_display_name(product: ProductFood) -> str:
    return f"{product.brand_name} {product.product_line}".strip()


def _supplement_display_name(product: ProductSupplement) -> str:
    return product.product_name


def _food_sub(product: ProductFood) -> str:
    return f"{product.pack_size_kg} kg • {product.life_stage} / {product.breed_size}"


def _supplement_sub(product: ProductSupplement) -> str:
    base = f"{product.brand_name} · {product.pack_size}" if product.pack_size else product.brand_name
    return f"{base} · {product.type.replace('_', ' ')}"


def _category_icon(category: str) -> str:
    """Return an icon for a product category."""
    icons = {
        "food": "🥣",
        "supplement": "💊",
    }
    return icons.get(category, "📦")


# --- Cart CRUD ---

async def get_cart(db: Session, pet_id) -> dict:
    """
    Get all non-expired cart items for a pet.

    C6: Items with cart_expires_at < now() are excluded.
    If non-expired items exist, a resume_prompt is included in the response.

    Returns:
        {
            "items": [...],
            "summary": { "count": int, "subtotal": int },
            "resume_prompt": str | None
        }
    """
    now = datetime.utcnow()
    items = (
        db.query(CartItem)
        .filter(
            CartItem.pet_id == pet_id,
            # Include rows with NULL cart_expires_at (legacy) and non-expired rows
            (CartItem.cart_expires_at.is_(None)) | (CartItem.cart_expires_at > now),
        )
        .order_by(CartItem.created_at.asc())
        .all()
    )

    cart_items = [_serialize_cart_item(item) for item in items]
    in_cart = [i for i in cart_items if i["in_cart"]]

    # C6: Surface resume prompt when items are waiting in cart
    resume_prompt: str | None = None
    if cart_items:
        pet = db.query(Pet).filter(Pet.id == pet_id).first()
        pet_name = pet.name if pet else "your pet"
        resume_prompt = f"Resume your order for {pet_name}?"

    return {
        "items": cart_items,
        "summary": {
            "count": len(in_cart),
            "subtotal": sum(i["price"] * i["quantity"] for i in in_cart),
        },
        "resume_prompt": resume_prompt,
    }


async def add_to_cart(
    db: Session,
    pet_id,
    product_id: str,
    name: str,
    price: int,
    icon: str | None = None,
    sub: str | None = None,
    tag: str | None = None,
    tag_color: str | None = None,
) -> dict:
    """Add a product to the pet's cart. If already exists, set in_cart=True."""
    existing = (
        db.query(CartItem)
        .filter(CartItem.pet_id == pet_id, CartItem.product_id == product_id)
        .first()
    )
    if existing:
        existing.in_cart = True
        db.commit()
        db.refresh(existing)
        return _serialize_cart_item(existing)

    item = CartItem(
        pet_id=pet_id,
        product_id=product_id,
        icon=icon,
        name=name,
        sub=sub,
        price=price,
        tag=tag,
        tag_color=tag_color,
        in_cart=True,
        quantity=1,
        cart_expires_at=datetime.utcnow() + timedelta(hours=72),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_cart_item(item)


async def toggle_cart_item(db: Session, pet_id, product_id: str) -> dict:
    """Toggle in_cart status for a cart item. Creates entry if from recommendations."""
    item = (
        db.query(CartItem)
        .filter(CartItem.pet_id == pet_id, CartItem.product_id == product_id)
        .first()
    )

    if item:
        item.in_cart = not item.in_cart
        db.commit()
        db.refresh(item)
        return _serialize_cart_item(item)

    # Item not in cart_items yet — look up in the SKU tables by product_id.
    product, category = _lookup_sku(db, product_id)
    if not product:
        raise ValueError(f"Product {product_id} not found")

    if category == "food":
        name = _food_display_name(product)
        sub = _food_sub(product)
    else:
        name = _supplement_display_name(product)
        sub = _supplement_sub(product)

    new_item = CartItem(
        pet_id=pet_id,
        product_id=product_id,
        icon=_category_icon(category),
        name=name,
        sub=sub,
        price=int(product.discounted_price),
        tag=None,
        tag_color=None,
        in_cart=True,
        quantity=1,
        cart_expires_at=datetime.utcnow() + timedelta(hours=72),
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return _serialize_cart_item(new_item)


async def update_quantity(db: Session, pet_id, product_id: str, quantity: int) -> dict:
    """Update quantity for a cart item."""
    item = (
        db.query(CartItem)
        .filter(CartItem.pet_id == pet_id, CartItem.product_id == product_id)
        .first()
    )
    if not item:
        raise ValueError(f"Cart item {product_id} not found")

    item.quantity = max(1, quantity)
    db.commit()
    db.refresh(item)
    return _serialize_cart_item(item)


async def remove_from_cart(db: Session, pet_id, product_id: str) -> dict:
    """Remove item from cart entirely."""
    item = (
        db.query(CartItem)
        .filter(CartItem.pet_id == pet_id, CartItem.product_id == product_id)
        .first()
    )
    if not item:
        raise ValueError(f"Cart item {product_id} not found")

    db.delete(item)
    db.commit()
    return {"status": "deleted", "product_id": product_id}


async def initialize_cart(db: Session, pet_id) -> dict:
    """No-op — cart initializes empty. Users add items themselves."""
    return await get_cart(db, pet_id)


# --- Recommendations ---

async def get_recommendations(
    db: Session,
    pet_id,
    nutrition_gaps: dict | None = None,
) -> list[dict]:
    """
    Get recommended products based on pet's species, breed, life stage,
    diagnosed conditions and (optionally) detected nutritional gaps.

    Pulls from product_food and product_supplement, filtered by:
    1. Life stage / breed size (food)
    2. Condition tags from diagnosed conditions (food + supplements)
    3. Nutrient gaps mapped to supplement condition_tags

    Returns products NOT already in the pet's cart. Capped at 15.
    """
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        return []

    # Get existing cart product_ids to exclude
    existing_ids = set(
        row[0] for row in
        db.query(CartItem.product_id)
        .filter(CartItem.pet_id == pet_id)
        .all()
    )

    # Get pet conditions for context
    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .all()
    )
    condition_names = [c.name.lower() for c in conditions]

    recommendations: list[dict] = []

    # 1. Supplements for nutrition gaps
    if nutrition_gaps:
        recommendations.extend(
            _recommend_supplements_for_gaps(db, nutrition_gaps, existing_ids)
        )

    # 2. Condition-specific supplements (e.g. joint for arthritis)
    if condition_names:
        recommendations.extend(
            _recommend_supplements_for_conditions(db, condition_names, existing_ids)
        )

    # 3. Food — life stage + breed size aware, condition-tag aware
    recommendations.extend(
        _recommend_food(db, pet, condition_names, existing_ids)
    )

    # Exclude previously bought items by name similarity
    bought_names = _get_bought_names(db, pet_id)
    recommendations = [
        r for r in recommendations
        if not _is_previously_bought(r["name"], bought_names)
    ]

    # Deduplicate by product_id
    seen: set[str] = set()
    unique: list[dict] = []
    for rec in recommendations:
        if rec["product_id"] not in seen:
            seen.add(rec["product_id"])
            unique.append(rec)

    return unique[:15]


def _get_bought_names(db: Session, pet_id) -> set:
    """Return set of lowercased item names from pet_preferences for this pet."""
    rows = (
        db.query(PetPreference.item_name)
        .filter(PetPreference.pet_id == pet_id)
        .all()
    )
    return {row[0].strip().lower() for row in rows if row[0]}


def _is_previously_bought(product_name: str, bought_names: set) -> bool:
    """
    Return True if this product name matches any previously bought item name.
    Uses substring matching in both directions (case-insensitive).
    """
    product_lower = product_name.strip().lower()
    for bought in bought_names:
        if bought in product_lower or product_lower in bought:
            return True
    return False


def get_last_bought(
    db: Session,
    pet_id,
    exclude_names: set | None = None,
) -> list[dict]:
    """
    Return previously bought items for a pet from pet_preferences.

    Args:
        exclude_names: Set of lowercased names to exclude (e.g. items currently
                       in cart, or items just ordered).

    Returns:
        List of {name, used_count, last_bought_at, category}
        Empty list if no history or all history is excluded.
    """
    rows = (
        db.query(PetPreference)
        .filter(PetPreference.pet_id == pet_id)
        .order_by(PetPreference.updated_at.desc())
        .limit(10)
        .all()
    )
    result = []
    for row in rows:
        name = (row.item_name or "").strip()
        if not name:
            continue
        if exclude_names and name.lower() in exclude_names:
            continue
        result.append({
            "name": name,
            "used_count": int(row.used_count or 0),
            "last_bought_at": row.updated_at,
            "category": row.category,
        })
    return result


def _format_last_bought_label(last_bought_at) -> str:
    """Convert a datetime to a human-readable recency label."""
    if not last_bought_at:
        return ""
    today = date.today()
    try:
        if hasattr(last_bought_at, "date"):
            bought_date = last_bought_at.date()
        else:
            bought_date = last_bought_at
        delta = (today - bought_date).days
        if delta == 0:
            return "Today"
        elif delta == 1:
            return "Yesterday"
        else:
            return f"{delta} days ago"
    except Exception:
        return ""


# --- Internal recommendation builders ---

# Nutrient gap -> supplement condition_tags / type hints
_GAP_TO_TAGS = {
    "omega_3": ["omega3", "coat", "skin"],
    "omega_6": ["omega6", "skin", "coat"],
    "glucosamine": ["joint", "hip", "arthritis"],
    "vitamin_e": ["immunity", "general_health"],
    "vitamin_d3": ["bone", "general_health"],
    "probiotics": ["digestive", "gut_health"],
    "calcium": ["bone", "growth"],
}


def _supplement_matches_any_tag(product: ProductSupplement, tags: list[str]) -> bool:
    haystack = " ".join(
        (t or "").lower()
        for t in (product.condition_tags, product.type, product.key_ingredients)
    )
    return any(tag in haystack for tag in tags)


def _recommend_supplements_for_gaps(
    db: Session,
    nutrition_gaps: dict,
    existing_ids: set,
) -> list[dict]:
    """Recommend supplements whose condition_tags cover nutrient gaps."""
    recs: list[dict] = []
    # Load the active supplement set once — the catalog is small (<20 rows)
    supplements = (
        db.query(ProductSupplement)
        .filter(ProductSupplement.active.is_(True), ProductSupplement.in_stock.is_(True))
        .order_by(ProductSupplement.popularity_rank.asc())
        .all()
    )

    for nutrient, info in nutrition_gaps.items():
        if not isinstance(info, dict):
            continue
        status = (info.get("status") or "").lower()
        if status not in ("low", "missing"):
            continue

        tags = _GAP_TO_TAGS.get(nutrient, [])
        if not tags:
            continue

        for p in supplements:
            if p.sku_id in existing_ids:
                continue
            if not _supplement_matches_any_tag(p, tags):
                continue
            priority = "urgent" if status == "missing" else "high"
            recs.append(_supplement_to_recommendation(
                p,
                reason=f"{nutrient.replace('_', ' ').title()} {status} in diet",
                priority=priority,
                tag=status.upper(),
                tag_color="#FF3B30" if status == "missing" else "#FF9500",
            ))
            existing_ids.add(p.sku_id)
            break  # one supplement per nutrient gap
    return recs


def _recommend_supplements_for_conditions(
    db: Session,
    condition_names: list[str],
    existing_ids: set,
) -> list[dict]:
    """Recommend supplements whose condition_tags match diagnosed conditions."""
    recs: list[dict] = []
    supplements = (
        db.query(ProductSupplement)
        .filter(ProductSupplement.active.is_(True), ProductSupplement.in_stock.is_(True))
        .order_by(ProductSupplement.popularity_rank.asc())
        .all()
    )

    for cond in condition_names:
        cond_key = cond.strip().lower()
        if not cond_key:
            continue
        for p in supplements:
            if p.sku_id in existing_ids:
                continue
            tag_hay = (p.condition_tags or "").lower()
            if cond_key not in tag_hay:
                continue
            recs.append(_supplement_to_recommendation(
                p,
                reason=f"For {cond.title()} management",
                priority="high",
                tag="CONDITION",
                tag_color="#FF9500",
            ))
            existing_ids.add(p.sku_id)
            break  # one supplement per condition
    return recs


def _recommend_food(
    db: Session,
    pet: Pet,
    condition_names: list[str],
    existing_ids: set,
) -> list[dict]:
    """Recommend food products based on life stage, breed size and conditions."""
    breed_size = _infer_breed_size(pet.breed)
    life_stage = _infer_life_stage(pet)

    query = (
        db.query(ProductFood)
        .filter(ProductFood.active.is_(True), ProductFood.in_stock.is_(True))
    )

    if breed_size:
        query = query.filter(
            (sqlfunc.lower(ProductFood.breed_size) == breed_size)
            | (sqlfunc.lower(ProductFood.breed_size) == "all")
        )

    if life_stage:
        # Food life_stage uses "Puppy" / "Adult" / "Senior" / "All".
        # Map our inferred stage (including "kitten") to these buckets.
        mapped = {"puppy": "puppy", "kitten": "puppy", "adult": "adult", "senior": "senior"}.get(life_stage)
        if mapped:
            query = query.filter(
                (sqlfunc.lower(ProductFood.life_stage) == mapped)
                | (sqlfunc.lower(ProductFood.life_stage) == "all")
            )

    products = (
        query.order_by(ProductFood.popularity_rank.asc()).limit(6).all()
    )

    # Prefer rows whose condition_tags overlap diagnosed conditions
    if condition_names:
        def _cond_score(p: ProductFood) -> int:
            tags = (p.condition_tags or "").lower()
            return sum(1 for c in condition_names if c and c in tags)
        products.sort(key=lambda p: (-_cond_score(p), p.popularity_rank))

    recs: list[dict] = []
    for p in products[:3]:
        if p.sku_id in existing_ids:
            continue
        recs.append(_food_to_recommendation(
            p,
            reason=(
                f"Suited for {breed_size or 'your pet'} "
                f"{life_stage or ''}".strip()
            ),
            priority="low",
        ))
        existing_ids.add(p.sku_id)

    return recs


# --- Place Order ---

async def place_order(
    db: Session,
    pet_id,
    user_id,
    payment_method: str,
    address: dict | None = None,
    coupon: str | None = None,
) -> dict:
    """
    Place an order from items currently in cart (in_cart=True).

    Creates an Order record and clears cart items.
    """
    in_cart = (
        db.query(CartItem)
        .filter(CartItem.pet_id == pet_id, CartItem.in_cart == True)
        .all()
    )
    if not in_cart:
        raise ValueError("No items in cart")

    items_desc = "; ".join(
        f"{item.name} x{item.quantity} (Rs.{item.price * item.quantity})"
        for item in in_cart
    )

    subtotal = sum(item.price * item.quantity for item in in_cart)
    discount = round(subtotal * 0.1) if coupon else 0
    delivery = 0 if subtotal >= FREE_DELIVERY_THRESHOLD else DELIVERY_FEE
    total = subtotal - discount + delivery

    order_id = f"PC-{uuid.uuid4().hex[:8].upper()}"

    # Determine payment status — COD confirmed immediately, online handled via Razorpay
    pay_status = "cod" if payment_method == "cod" else "pending"

    # Create order record
    order = Order(
        user_id=user_id,
        pet_id=pet_id,
        category="dashboard_order",
        items_description=items_desc,
        status="pending",
        payment_status=pay_status,
        admin_notes=f"Order {order_id} | Payment: {payment_method} | Total: Rs.{total}"
                    + (f" | Coupon: {coupon} (-Rs.{discount})" if coupon else "")
                    + (f" | Address: {address}" if address else ""),
    )
    db.add(order)

    # Build response items before clearing
    order_items = [
        {
            "product_id": item.product_id,
            "name": item.name,
            "icon": item.icon,
            "price": item.price,
            "quantity": item.quantity,
            "total": item.price * item.quantity,
        }
        for item in in_cart
    ]

    # Record each ordered item into pet_preferences so purchase history is tracked.
    # Look up the SKU to tag the preference category; fall back to "dashboard_order".
    from app.services.recommendation_service import record_preference
    for item in in_cart:
        _product, sku_category = _lookup_sku(db, item.product_id)
        item_category = sku_category or "dashboard_order"
        record_preference(db, pet_id, item_category, item.name, "custom")

    # Clear cart
    for item in in_cart:
        db.delete(item)

    db.commit()

    # C4: Send WhatsApp confirmation — non-blocking, failure must not rollback order
    asyncio.create_task(_send_order_confirmation(db, user_id, pet_id, order_items, total))

    return {
        "order_id": order_id,
        "items": order_items,
        "subtotal": subtotal,
        "discount": discount,
        "delivery": delivery,
        "total": total,
        "payment_method": payment_method,
        "status": "confirmed",
    }


async def _send_order_confirmation(
    db: Session,
    user_id,
    pet_id,
    order_items: list[dict],
    total: int,
) -> None:
    """
    Send a WhatsApp order confirmation message to the user.

    C4: "Your [Product Name] for [Pet Name] has been ordered! Expected delivery: [date]."
    Runs as a background task — any failure is logged but never raises.
    """
    from app.services.whatsapp_sender import send_text_message

    try:
        user = db.query(User).filter(User.id == user_id).first()
        pet = db.query(Pet).filter(Pet.id == pet_id).first()
        if not user or not user.mobile_display:
            logger.warning("Order confirmation skipped — no phone for user %s", user_id)
            return

        pet_name = pet.name if pet else "your pet"
        product_names = ", ".join(i["name"] for i in order_items[:3])
        if len(order_items) > 3:
            product_names += f" and {len(order_items) - 3} more"

        # Expected delivery: 3–5 business days
        delivery_date = (datetime.utcnow() + timedelta(days=5)).strftime("%d %b %Y")

        message = (
            f"Your {product_names} for {pet_name} has been ordered! "
            f"Expected delivery: {delivery_date}. "
            f"Total paid: Rs.{total}. Thank you for ordering with PetCircle! \U0001f43e"
        )

        await send_text_message(db, user.mobile_display, message)
        logger.info("Order confirmation sent to %s for pet %s", user.mobile_display, pet_id)
    except Exception as exc:
        # Never raise — order is already committed
        logger.error("Failed to send order confirmation: %s", exc)


# --- Helpers ---

def _serialize_cart_item(item: CartItem) -> dict:
    """Serialize a CartItem to a dict for API response."""
    return {
        "id": str(item.id),
        "product_id": item.product_id,
        "icon": item.icon,
        "name": item.name,
        "sub": item.sub,
        "price": item.price,
        "tag": item.tag,
        "tag_color": item.tag_color,
        "in_cart": item.in_cart,
        "quantity": item.quantity,
    }


def _food_to_recommendation(
    product: ProductFood,
    reason: str,
    priority: str = "medium",
    tag: str | None = None,
    tag_color: str | None = None,
) -> dict:
    """Convert a ProductFood row to a recommendation dict."""
    return {
        "product_id": product.sku_id,
        "icon": _category_icon("food"),
        "name": _food_display_name(product),
        "sub": _food_sub(product),
        "price": int(product.discounted_price),
        "tag": tag,
        "tag_color": tag_color,
        "reason": reason,
        "priority": priority,
        "category": "food",
    }


def _supplement_to_recommendation(
    product: ProductSupplement,
    reason: str,
    priority: str = "medium",
    tag: str | None = None,
    tag_color: str | None = None,
) -> dict:
    """Convert a ProductSupplement row to a recommendation dict."""
    return {
        "product_id": product.sku_id,
        "icon": _category_icon("supplement"),
        "name": _supplement_display_name(product),
        "sub": _supplement_sub(product),
        "price": int(product.discounted_price),
        "tag": tag,
        "tag_color": tag_color,
        "reason": reason,
        "priority": priority,
        "category": "supplement",
    }


# Known large breed names
_LARGE_BREEDS = {
    "golden retriever", "labrador", "german shepherd", "rottweiler",
    "great dane", "saint bernard", "bernese mountain", "mastiff",
    "husky", "malamute", "akita", "newfoundland", "boxer",
}

_SMALL_BREEDS = {
    "chihuahua", "pomeranian", "shih tzu", "maltese", "yorkshire",
    "dachshund", "pekingese", "papillon", "toy poodle", "miniature pinscher",
    "lhasa apso", "havanese", "bichon frise",
}


def _infer_breed_size(breed: str | None) -> str | None:
    """Infer breed size category from breed name."""
    if not breed:
        return None
    breed_lower = breed.lower().strip()
    for large in _LARGE_BREEDS:
        if large in breed_lower:
            return "large"
    for small in _SMALL_BREEDS:
        if small in breed_lower:
            return "small"
    return "medium"


def _infer_life_stage(pet: Pet) -> str | None:
    """Infer life stage from pet DOB."""
    if not pet.dob:
        return None
    from datetime import date
    age_years = (date.today() - pet.dob).days / 365.25
    if age_years < 1:
        return "puppy" if (pet.species or "").lower() == "dog" else "kitten"
    elif age_years < 7:
        return "adult"
    else:
        return "senior"
