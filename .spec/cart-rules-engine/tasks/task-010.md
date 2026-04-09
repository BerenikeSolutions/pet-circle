---
task: 010
feature: cart-rules-engine
status: pending
depends_on: [006]
---

# Task 010: Cart persistence (72h) and WhatsApp order confirmation

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective
Implement cart persistence (C6: 72-hour expiry with resume prompt) and WhatsApp order confirmation (C4: send message after order placed).

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```python
# [CartItem model — from backend/app/models/cart_item.py:38-50]
class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"))
    product_id = Column(String(100), nullable=False)
    name = Column(String(200), nullable=False)
    price = Column(Integer, nullable=False)
    in_cart = Column(Boolean, nullable=False, default=False)
    quantity = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Need to add: cart_expires_at column
```

```python
# [get_cart function — from backend/app/services/cart_service.py:38-60]
async def get_cart(db: Session, pet_id) -> dict:
    items = (
        db.query(CartItem)
        .filter(CartItem.pet_id == pet_id)
        .order_by(CartItem.created_at.asc())
        .all()
    )
    # Need to add: filter out expired items (created_at + 72h < now)
    # Need to add: resume_prompt if items exist
```

```python
# [place_order function — from backend/app/services/cart_service.py:523-617]
async def place_order(db, pet_id, user_id, payment_method, address=None, coupon=None):
    # ... creates Order, clears cart ...
    # Need to add: after commit, send WhatsApp confirmation
```

```python
# [WhatsApp sender — from backend/app/services/whatsapp_sender.py]
# Has send_template() and send_text_message() functions
# Template messages require template name and parameters
# Text messages: send_text_message(phone_number, message_text)
```

```python
# [User model has phone — for WhatsApp sending]
# user.phone_number — the WhatsApp number
```

### Key Patterns in Use
- **WhatsApp sending:** `from app.services.whatsapp_sender import send_text_message`
- **Background task:** WhatsApp calls should be in `asyncio.create_task()` to not block response
- **Cart expiry:** Filter by `created_at` + 72 hours vs current time

---

## Handoff from Previous Task
> Populated by /task-handoff after prior task completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

### Cart Persistence (C6)
1. Write migration `backend/migrations/045_cart_expires_at.sql`:
   - Add `cart_expires_at TIMESTAMPTZ` column to `cart_items`
   - Default: `created_at + INTERVAL '72 hours'`
   - Backfill existing rows: `UPDATE cart_items SET cart_expires_at = created_at + INTERVAL '72 hours'`
2. Update `CartItem` model: add `cart_expires_at = Column(DateTime, nullable=True)`
3. Update `get_cart()` in `cart_service.py`:
   - Add filter: `CartItem.cart_expires_at > datetime.utcnow()` (or `CartItem.cart_expires_at.is_(None)`)
   - If items exist, add `resume_prompt` to response: `"Resume your order for {pet_name}?"`
4. Update cart item creation (in `add_to_cart` / new `add_from_signal`):
   - Set `cart_expires_at = datetime.utcnow() + timedelta(hours=72)`

### WhatsApp Confirmation (C4)
5. Update `place_order()` in `cart_service.py`:
   - After successful commit, fetch user phone number and pet name
   - Build confirmation message: `"Your {product_names} for {pet_name} has been ordered! Expected delivery: {date}."`
   - Send via `asyncio.create_task(send_text_message(phone, message))` — non-blocking
   - Log the message send attempt
6. Handle errors gracefully — WhatsApp send failure must not rollback the order

_Requirements: 5.5, 5.8, 5.9_
_Skills: /python-patterns, /code-writing-software-development_

---

## Acceptance Criteria
- [ ] Migration 045 adds `cart_expires_at` column to `cart_items`
- [ ] `CartItem` model includes `cart_expires_at`
- [ ] `get_cart()` filters out items where `cart_expires_at < now()`
- [ ] Cart response includes `resume_prompt` when non-expired items exist
- [ ] New cart items have `cart_expires_at` set to creation + 72 hours
- [ ] `place_order()` sends WhatsApp confirmation message after order commit
- [ ] WhatsApp send runs as background task (non-blocking)
- [ ] WhatsApp failure does not rollback the order
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
