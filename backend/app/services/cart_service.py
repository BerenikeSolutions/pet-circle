"""
PetCircle Phase 8 — Cart & Orders Service

Manages the pet's shopping cart. Cart items are added by users or
generated as recommendations based on species, breed, and nutritional
deficiencies from the nutrition analysis pipeline.

Key design:
    - No hardcoded cart items — everything from DB
    - Recommendations pulled from product_catalog based on pet profile
    - Nutritional gap analysis drives supplement recommendations
    - Orders stored in the orders table for admin processing
"""

import logging
import uuid
from datetime import datetime, date, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.models.cart_item import CartItem
from app.models.product_catalog import ProductCatalog
from app.models.pet import Pet
from app.models.condition import Condition
from app.models.order import Order
from app.models.pet_preference import PetPreference

logger = logging.getLogger(__name__)

# --- Constants ---
FREE_DELIVERY_THRESHOLD = 500  # Free delivery for orders >= ₹500
DELIVERY_FEE = 49


# --- Cart CRUD ---

async def get_cart(db: Session, pet_id) -> dict:
    """
    Get all cart items for a pet, separated into user-added and in-cart items.

    Returns:
        {
            "items": [...],
            "summary": { "count": int, "subtotal": int }
        }
    """
    items = (
        db.query(CartItem)
        .filter(CartItem.pet_id == pet_id)
        .order_by(CartItem.created_at.asc())
        .all()
    )

    cart_items = [_serialize_cart_item(item) for item in items]
    in_cart = [i for i in cart_items if i["in_cart"]]

    return {
        "items": cart_items,
        "summary": {
            "count": len(in_cart),
            "subtotal": sum(i["price"] * i["quantity"] for i in in_cart),
        },
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

    # Item not in cart_items yet — look up in product_catalog and add it
    product = (
        db.query(ProductCatalog)
        .filter(ProductCatalog.cart_item_id == product_id)
        .first()
    )
    if not product:
        # Try by UUID
        try:
            product = db.query(ProductCatalog).filter(ProductCatalog.id == product_id).first()
        except Exception:
            pass

    if not product:
        raise ValueError(f"Product {product_id} not found")

    price = _parse_price(product.mrp)
    new_item = CartItem(
        pet_id=pet_id,
        product_id=product_id,
        icon=_category_icon(product.category),
        name=f"{product.brand} {product.product_name}".strip(),
        sub=product.description or product.indication or "",
        price=price,
        tag=None,
        tag_color=None,
        in_cart=True,
        quantity=1,
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
    Get recommended products based on pet's species, breed, and nutritional gaps.

    Pulls from product_catalog and filters by:
    1. Species/breed size compatibility (life_stage, breed_size)
    2. Nutritional deficiencies (supplements for gaps)
    3. Preventive needs (deworming, flea/tick based on conditions)

    Returns products NOT already in the pet's cart.
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

    recommendations = []

    # 1. Supplement recommendations based on nutrition gaps
    if nutrition_gaps:
        recommendations.extend(
            _recommend_supplements(db, pet, nutrition_gaps, existing_ids)
        )

    # 2. Deworming products
    recommendations.extend(
        _recommend_by_category(db, pet, "deworming", existing_ids)
    )

    # 3. Flea & tick products
    recommendations.extend(
        _recommend_by_category(db, pet, "flea_tick", existing_ids)
    )

    # 4. Condition-specific medicines
    if conditions:
        recommendations.extend(
            _recommend_condition_products(db, pet, condition_names, existing_ids)
        )

    # 5. Food recommendations based on breed size and life stage
    recommendations.extend(
        _recommend_food(db, pet, existing_ids)
    )

    # Exclude previously bought items
    bought_names = _get_bought_names(db, pet_id)
    recommendations = [
        r for r in recommendations
        if not _is_previously_bought(r["name"], bought_names)
    ]

    # Deduplicate by product ID
    seen = set()
    unique = []
    for rec in recommendations:
        if rec["product_id"] not in seen:
            seen.add(rec["product_id"])
            unique.append(rec)

    return unique[:15]  # Cap at 15 recommendations


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
        Empty list if no history or all history is excluded (caller should hide the section).
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


def _recommend_supplements(
    db: Session,
    pet: Pet,
    nutrition_gaps: dict,
    existing_ids: set,
) -> list[dict]:
    """Recommend supplements based on nutritional deficiencies."""
    recs = []

    # Map nutrient gaps to product categories/keywords
    gap_to_keywords = {
        "omega_3": ["omega", "salmon", "fish oil"],
        "omega_6": ["omega", "fatty acid"],
        "glucosamine": ["glucosamine", "joint", "cosequin"],
        "vitamin_e": ["vitamin e", "vit e"],
        "vitamin_d3": ["vitamin d", "calcitriol", "vit d"],
        "probiotics": ["probiotic", "fortiflora", "digestive"],
        "calcium": ["calcium", "bone"],
    }

    for nutrient, info in nutrition_gaps.items():
        if not isinstance(info, dict):
            continue
        status = info.get("status", "").lower()
        if status in ("low", "missing"):
            keywords = gap_to_keywords.get(nutrient, [])
            for kw in keywords:
                products = (
                    db.query(ProductCatalog)
                    .filter(
                        sqlfunc.lower(ProductCatalog.product_name).contains(kw)
                        | sqlfunc.lower(ProductCatalog.active_ingredient).contains(kw)
                        | sqlfunc.lower(ProductCatalog.description).contains(kw)
                    )
                    .limit(2)
                    .all()
                )
                for p in products:
                    pid = p.cart_item_id or str(p.id)
                    if pid not in existing_ids:
                        priority = "urgent" if status == "missing" else "high"
                        recs.append(_product_to_recommendation(
                            p, pid,
                            reason=f"{nutrient.replace('_', ' ').title()} {status} in diet",
                            priority=priority,
                            tag=status.upper(),
                            tag_color="#FF3B30" if status == "missing" else "#FF9500",
                        ))
                        existing_ids.add(pid)
                if recs:
                    break  # Found a match for this nutrient

    return recs


def _recommend_by_category(
    db: Session,
    pet: Pet,
    category: str,
    existing_ids: set,
) -> list[dict]:
    """Recommend top products from a category filtered by breed size."""
    breed_size = _infer_breed_size(pet.breed)

    query = db.query(ProductCatalog).filter(ProductCatalog.category == category)

    # Filter by breed size if available
    if breed_size:
        query = query.filter(
            (sqlfunc.lower(ProductCatalog.breed_size).contains(breed_size))
            | (ProductCatalog.breed_size == None)
            | (sqlfunc.lower(ProductCatalog.breed_size).contains("all"))
        )

    products = query.limit(3).all()
    recs = []
    for p in products:
        pid = p.cart_item_id or str(p.id)
        if pid not in existing_ids:
            recs.append(_product_to_recommendation(
                p, pid,
                reason=f"Recommended {category.replace('_', ' ')} for {pet.breed or pet.species or 'your pet'}",
                priority="medium",
            ))
            existing_ids.add(pid)

    return recs


def _recommend_condition_products(
    db: Session,
    pet: Pet,
    condition_names: list[str],
    existing_ids: set,
) -> list[dict]:
    """Recommend medicines relevant to pet's conditions."""
    recs = []
    for cond in condition_names:
        products = (
            db.query(ProductCatalog)
            .filter(
                ProductCatalog.category == "medicine",
                sqlfunc.lower(ProductCatalog.indication).contains(cond)
            )
            .limit(2)
            .all()
        )
        for p in products:
            pid = p.cart_item_id or str(p.id)
            if pid not in existing_ids:
                recs.append(_product_to_recommendation(
                    p, pid,
                    reason=f"For {cond.title()} management",
                    priority="high",
                    tag="CONDITION",
                    tag_color="#FF9500",
                ))
                existing_ids.add(pid)

    return recs


def _recommend_food(
    db: Session,
    pet: Pet,
    existing_ids: set,
) -> list[dict]:
    """Recommend food products based on breed size and life stage."""
    breed_size = _infer_breed_size(pet.breed)
    life_stage = _infer_life_stage(pet)

    query = db.query(ProductCatalog).filter(ProductCatalog.category == "food")

    if breed_size:
        query = query.filter(
            (sqlfunc.lower(ProductCatalog.breed_size).contains(breed_size))
            | (ProductCatalog.breed_size == None)
            | (sqlfunc.lower(ProductCatalog.breed_size).contains("all"))
        )

    if life_stage:
        query = query.filter(
            (sqlfunc.lower(ProductCatalog.life_stage).contains(life_stage))
            | (ProductCatalog.life_stage == None)
            | (sqlfunc.lower(ProductCatalog.life_stage).contains("all"))
        )

    products = query.limit(3).all()
    recs = []
    for p in products:
        pid = p.cart_item_id or str(p.id)
        if pid not in existing_ids:
            recs.append(_product_to_recommendation(
                p, pid,
                reason=f"Suited for {breed_size or ''} breed {life_stage or ''} stage".strip(),
                priority="low",
            ))
            existing_ids.add(pid)

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

    # Build items description
    items_desc = "; ".join(
        f"{item.name} x{item.quantity} (₹{item.price * item.quantity})"
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
    # Look up product category from catalog; fall back to "dashboard_order".
    from app.services.recommendation_service import record_preference
    for item in in_cart:
        product = (
            db.query(ProductCatalog)
            .filter(
                (ProductCatalog.cart_item_id == item.product_id)
                | (ProductCatalog.id == item.product_id)
            )
            .first()
        )
        item_category = (product.category if product else None) or "dashboard_order"
        record_preference(db, pet_id, item_category, item.name, "custom")

    # Clear cart
    for item in in_cart:
        db.delete(item)

    db.commit()

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


def _product_to_recommendation(
    product: ProductCatalog,
    product_id: str,
    reason: str,
    priority: str = "medium",
    tag: str | None = None,
    tag_color: str | None = None,
) -> dict:
    """Convert a ProductCatalog entry to a recommendation dict."""
    price = _parse_price(product.mrp)
    return {
        "product_id": product_id,
        "icon": _category_icon(product.category),
        "name": f"{product.brand} {product.product_name}".strip(),
        "sub": product.description or product.indication or product.formulation or "",
        "price": price,
        "tag": tag,
        "tag_color": tag_color,
        "reason": reason,
        "priority": priority,
        "category": product.category,
    }


def _parse_price(mrp_str: str | None) -> int:
    """Extract first price from MRP string like 'Rs.1,499 / Rs.4,599'."""
    if not mrp_str:
        return 0
    import re
    match = re.search(r'[\d,]+', mrp_str.replace(' ', ''))
    if match:
        try:
            return int(match.group().replace(',', ''))
        except ValueError:
            return 0
    return 0


def _category_icon(category: str) -> str:
    """Return an icon for a product category."""
    icons = {
        "food": "🥣",
        "deworming": "🪱",
        "flea_tick": "🐛",
        "medicine": "💊",
    }
    return icons.get(category, "📦")


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
