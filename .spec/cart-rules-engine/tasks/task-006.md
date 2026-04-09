---
task: 006
feature: cart-rules-engine
status: done
depends_on: [003, 004]
---

# Task 006: Dashboard API endpoints for product resolution

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /api-design, /python-patterns
Commands: /verify, /task-handoff

---

## Objective
Add three new endpoints to the dashboard router: product resolution (GET), product search (GET), and cart add (POST). These connect the signal resolver to the frontend.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```python
# [Dashboard router pattern — from backend/app/routers/dashboard.py:1-50]
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Token validation pattern used everywhere:
# token_data = validate_dashboard_token(db, token)
# pet = db.query(Pet).filter(Pet.id == token_data.pet_id).first()
```

```python
# [Existing cart endpoints in dashboard.py — pattern to follow]
@router.get("/{token}/cart")
async def get_cart_endpoint(token: str, db: Session = Depends(get_db)):
    token_data = validate_dashboard_token(db, token)
    result = await get_cart(db, token_data.pet_id)
    return result

@router.post("/{token}/cart/toggle/{product_id}")
async def toggle_cart_endpoint(token: str, product_id: str, db: Session = Depends(get_db)):
    token_data = validate_dashboard_token(db, token)
    return await toggle_cart_item(db, token_data.pet_id, product_id)
```

```python
# [Signal resolver API — from tasks 003/004]
from app.services.signal_resolver import resolve_food_signal, resolve_supplement_signal, SignalResult
```

```python
# [CartItem creation pattern — from cart_service.py:139-154]
new_item = CartItem(
    pet_id=pet_id,
    product_id=product_id,  # Will be sku_id like "F002"
    icon=_category_icon(product.category),
    name=f"{product.brand} {product.product_name}".strip(),
    sub=product.description or "",
    price=price,
    in_cart=True,
    quantity=1,
)
```

### Key Patterns in Use
- **Token validation:** Every endpoint starts with `validate_dashboard_token(db, token)`
- **Pydantic models:** Request bodies use Pydantic `BaseModel` classes
- **Response format:** Direct dict/list returns (FastAPI auto-serializes)
- **Price rule:** Always read price from DB, never trust client

### Architecture Decisions Affecting This Task
- SKU prefix convention: F → product_food, S → product_supplement
- C5: Include `vet_diet_warning` boolean in resolve response
- C7: Include `pack_size_suggestion` when L4 and pet weight known

---

## Handoff from Previous Task
> Populated by /task-handoff after prior task completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps
1. Add Pydantic request model: `CartAddRequest(BaseModel): sku_id: str, quantity: int = 1`
2. Add `GET /dashboard/{token}/products/resolve`:
   - Query param: `diet_item_id` (UUID)
   - Validate token, get pet
   - Fetch diet_item by ID (must belong to pet)
   - Fetch active conditions for pet
   - Call `resolve_food_signal()` or `resolve_supplement_signal()` based on `diet_item.type`
   - Add `vet_diet_warning: bool` if any product has vet_diet_flag
   - Add `pack_size_suggestion: str|None` if L4 and pet weight known (C7: weight_kg * 10g/kg/day * 30 days / 1000 = monthly kg)
   - Return JSON per design spec
3. Add `GET /dashboard/{token}/products/search`:
   - Query param: `q` (string, min length 2)
   - Search `product_food` by brand_name ILIKE or product_line ILIKE
   - Search `product_supplement` by brand_name ILIKE or product_name ILIKE
   - Combine results, in_stock first, max 10
   - Return `{ "results": [...] }`
4. Add `POST /dashboard/{token}/cart/add`:
   - Body: `CartAddRequest`
   - Validate token, get pet
   - Determine table by prefix: F → product_food, S → product_supplement
   - Look up product, get price from `discounted_price`
   - Create/update CartItem with price from DB (C1: qty default 1, never auto > 1)
   - Return serialized CartItem

_Requirements: 5.4, 5.6, 5.7, 5.10, 6.9_
_Skills: /api-design, /python-patterns_

---

## Acceptance Criteria
- [x] `GET /products/resolve` returns correct signal level and products for a diet item
- [x] `GET /products/search` returns matching products from both tables, in_stock first
- [x] `POST /cart/add` creates CartItem with DB price, not client price
- [x] Token validation on all three endpoints
- [x] C5: vet_diet_warning included in resolve response
- [x] C7: pack_size_suggestion included when applicable
- [x] C1: quantity defaults to 1
- [x] 404 returned for invalid diet_item_id or sku_id
- [x] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** `backend/app/routers/dashboard.py` (added CartAddRequest model, 3 new endpoints, imports for DietItem/ProductFood/ProductSupplement/signal_resolver/Query)
**Decisions made:** Resolve endpoint routes supplement vs food by `diet_item.type == "supplement"`. Search uses ILIKE with `%q%` pattern across both tables. Cart add normalizes sku_id to uppercase before lookup.
**Context for next task:** The three endpoints are in place: `/products/resolve`, `/products/search`, `/cart/add`. Frontend can now wire up product resolution from diet items, search, and add-to-cart by SKU.
**Open questions:** None
