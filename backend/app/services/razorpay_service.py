"""
PetCircle — Razorpay Payment Service

Handles all Razorpay interactions:
  - Creating a Razorpay order before payment (UPI / card / netbanking)
  - Verifying the payment signature after user completes payment
  - COD orders bypass Razorpay entirely

Flow:
  1. Frontend hits POST /{token}/create-payment
     → Backend creates Razorpay order (server-side API call)
     → Creates an Order row in DB with payment_status='awaiting_payment'
     → Returns {razorpay_order_id, amount, currency, key_id} to frontend

  2. Frontend opens Razorpay checkout.js
     → User pays via UPI / card / netbanking
     → Razorpay calls handler({razorpay_payment_id, razorpay_order_id, razorpay_signature})

  3. Frontend hits POST /{token}/verify-payment
     → Backend verifies HMAC-SHA256 signature
     → Updates Order to payment_status='paid', stores razorpay_payment_id
     → Clears cart items
     → Returns confirmed order summary

Security:
  - Signature = HMAC-SHA256(razorpay_order_id + "|" + razorpay_payment_id, key_secret)
  - Never expose key_secret to the frontend
  - key_id is safe to expose (used only to open the checkout)
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime

import razorpay
from sqlalchemy.orm import Session

from app.config import settings
from app.models.cart_item import CartItem
from app.models.order import Order

logger = logging.getLogger(__name__)

# Delivery constants — must match cart_service.py
FREE_DELIVERY_THRESHOLD = 500
DELIVERY_FEE = 49


def _get_razorpay_client() -> razorpay.Client:
    """
    Return an authenticated Razorpay client.

    Raises:
        RuntimeError: If Razorpay credentials are not configured.
    """
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise RuntimeError(
            "Razorpay credentials not configured. "
            "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in your environment."
        )
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


async def create_razorpay_payment(
    db: Session,
    pet_id,
    user_id,
    payment_method: str,
    address: dict | None,
    coupon: str | None,
    coupon_discount_percent: int = 0,
) -> dict:
    """
    Create a Razorpay order for the cart items and persist a pending Order row.

    Args:
        db: Database session.
        pet_id: UUID of the pet whose cart is being checked out.
        user_id: UUID of the owner.
        payment_method: 'upi' | 'card' | 'netbanking'
        address: Optional delivery address dict.
        coupon: Optional coupon code string.
        coupon_discount_percent: Discount % from a validated coupon (0–100).

    Returns:
        {
            "razorpay_order_id": str,
            "amount": int,          # in paise (INR * 100)
            "currency": "INR",
            "key_id": str,          # safe to expose to frontend
            "order_db_id": str,     # internal Order.id for verification step
            "subtotal": int,
            "discount": int,
            "delivery": int,
            "total": int,
        }

    Raises:
        ValueError: If cart is empty.
        RuntimeError: If Razorpay credentials are missing.
    """
    in_cart = (
        db.query(CartItem)
        .filter(CartItem.pet_id == pet_id, CartItem.in_cart == True)
        .all()
    )
    if not in_cart:
        raise ValueError("No items in cart")

    # Calculate totals
    subtotal = sum(item.price * item.quantity for item in in_cart)
    discount = round(subtotal * coupon_discount_percent / 100) if coupon else 0
    delivery = 0 if subtotal >= FREE_DELIVERY_THRESHOLD else DELIVERY_FEE
    total = subtotal - discount + delivery

    # Amount in paise (Razorpay requires smallest currency unit)
    amount_paise = total * 100

    # Create Razorpay order
    client = _get_razorpay_client()
    rzp_order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1,  # Auto-capture on payment success
        "notes": {
            "pet_id": str(pet_id),
            "user_id": str(user_id),
            "coupon": coupon or "",
        },
    })

    razorpay_order_id = rzp_order["id"]

    # Build items description for Order row
    items_desc = "; ".join(
        f"{item.name} x{item.quantity} (Rs.{item.price * item.quantity})"
        for item in in_cart
    )

    order_db_id = uuid.uuid4()
    order = Order(
        id=order_db_id,
        user_id=user_id,
        pet_id=pet_id,
        category="dashboard_order",
        items_description=items_desc,
        status="pending",
        payment_status="awaiting_payment",
        razorpay_order_id=razorpay_order_id,
        admin_notes=(
            f"Payment: {payment_method} | Total: Rs.{total}"
            + (f" | Coupon: {coupon} (-Rs.{discount})" if coupon else "")
            + (f" | Address: {address}" if address else "")
        ),
    )
    db.add(order)
    db.commit()

    logger.info(
        "Razorpay order created: rzp=%s db=%s total=%d",
        razorpay_order_id, order_db_id, total,
    )

    return {
        "razorpay_order_id": razorpay_order_id,
        "amount": amount_paise,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
        "order_db_id": str(order_db_id),
        "subtotal": subtotal,
        "discount": discount,
        "delivery": delivery,
        "total": total,
    }


async def verify_razorpay_payment(
    db: Session,
    pet_id,
    order_db_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> dict:
    """
    Verify Razorpay payment signature and finalise the order.

    Signature formula (Razorpay spec):
        HMAC-SHA256(razorpay_order_id + "|" + razorpay_payment_id, key_secret)

    On success:
      - Updates Order.payment_status to 'paid'
      - Stores razorpay_payment_id on the Order row
      - Sets Order.status to 'confirmed'
      - Deletes all in_cart CartItems for this pet

    Returns confirmed order summary dict.

    Raises:
        ValueError: Signature mismatch, order not found, or already processed.
        RuntimeError: Razorpay credentials missing.
    """
    if not settings.RAZORPAY_KEY_SECRET:
        raise RuntimeError("Razorpay credentials not configured.")

    # Verify signature
    payload = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, razorpay_signature):
        logger.warning(
            "Razorpay signature mismatch for order %s payment %s",
            razorpay_order_id, razorpay_payment_id,
        )
        raise ValueError("Payment verification failed — invalid signature.")

    # Find the pending order
    order = db.query(Order).filter(Order.id == order_db_id).first()
    if not order:
        raise ValueError(f"Order {order_db_id} not found.")
    if order.payment_status == "paid":
        # Idempotent — already processed (e.g., webhook arrived first)
        return _order_summary(order)
    if order.payment_status != "awaiting_payment":
        raise ValueError(f"Order is not awaiting payment (status={order.payment_status}).")

    # Collect cart items for the response before deleting
    in_cart = (
        db.query(CartItem)
        .filter(CartItem.pet_id == pet_id, CartItem.in_cart == True)
        .all()
    )
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

    # Finalise order
    order.razorpay_payment_id = razorpay_payment_id
    order.payment_status = "paid"
    order.status = "confirmed"
    order.updated_at = datetime.utcnow()

    # Clear cart
    for item in in_cart:
        db.delete(item)

    db.commit()

    logger.info(
        "Payment verified and order confirmed: db=%s rzp_payment=%s",
        order_db_id, razorpay_payment_id,
    )

    return {
        "order_id": f"PC-{str(order.id)[:8].upper()}",
        "items": order_items,
        "subtotal": sum(i["total"] for i in order_items),
        "discount": 0,   # Discount already factored into amount charged
        "delivery": 0,
        "total": sum(i["total"] for i in order_items),
        "payment_method": "razorpay",
        "payment_status": "paid",
        "status": "confirmed",
    }


def _order_summary(order: Order) -> dict:
    """Build a minimal summary dict from an already-confirmed order."""
    return {
        "order_id": f"PC-{str(order.id)[:8].upper()}",
        "items": [],
        "subtotal": 0,
        "discount": 0,
        "delivery": 0,
        "total": 0,
        "payment_method": "razorpay",
        "payment_status": order.payment_status,
        "status": order.status,
    }
