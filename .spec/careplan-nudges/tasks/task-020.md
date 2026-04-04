---
task: 020
feature: careplan-nudges
status: complete
depends_on: []
---

# Task 020: Backend — Care Plan "Due Soon" Tag for Food/Supplements

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development, /python-patterns
Commands: /verify, /task-handoff

---

## Objective

Differentiate first-time vs repeat food/supplement items in the Continue bucket of the care plan. Add `cta_label` field ("Order Now" vs "Reorder") and `status_tag: "Due Soon"` for items with low estimated supply (≤7 days remaining). Query the `orders` table for pet order history to make this determination.

---

## Codebase Context

### Key Code Snippets

```python
# [Orderable food/supplement block — from backend/app/services/care_plan_engine.py:881-910]
# ── Add orderable food / supplements to Continue bucket ──────────────
# Requirement 9.12: place ongoing food and supplements in Continue.
try:
    diet_rows = (
        db.query(DietItem)
        .filter(DietItem.pet_id == pet.id)
        .all()
    )
    for diet_item in diet_rows:
        if not diet_item.label:
            continue
        # Map diet type to care plan test_type.
        tt = "supplement" if diet_item.type == "supplement" else "food"
        item_key = f"diet_{diet_item.id}"
        continue_items[item_key] = {
            "name": diet_item.label,
            "test_type": tt,
            "freq": "Daily",
            "next_due": None,
            "status_tag": "Active",
            "classification": Classification.PERIODIC.value,
            "reason": None,
            "orderable": True,
        }
except Exception:
    logger.warning(
        "Failed to load diet items for care plan of pet %s",
        pet.id,
        exc_info=True,
    )
```

```python
# [CarePlanItem interface on frontend — from frontend/src/lib/api.ts:263-275]
# Currently has: name, test_type, product_id, icon, price, freq, next_due,
#                status_tag, classification, reason, orderable
# Needs: cta_label?: string
```

### Key Patterns in Use
- **Order model:** `orders` table has `user_id`, `pet_id`, `product_name`, `created_at`, `quantity`, `pack_days` (estimated days per pack).
- **Classification enum:** `Classification.PERIODIC` for ongoing items.
- **Error handling:** Wrap order query in try/except — fallback to existing behavior on failure.
- **Supply calculation:** `pack_days - (today - order_date).days` gives estimated remaining supply.

### Architecture Decisions Affecting This Task
- Only apply `cta_label` and `status_tag` changes to items with `orderable: True` and `test_type` in `("food", "supplement")`.
- 7-day threshold for "Due Soon" matches the reminder T-7 trigger.

---

## Handoff from Previous Task
> This is an independent task with no prior dependencies.

**Files changed by previous task:** _(none)_
**Decisions made:** _(none)_
**Context for this task:** _(none)_
**Open questions left:** _(none)_

---

## Implementation Steps

1. **Read the `Order` model** to understand available fields (check `backend/app/models/` for orders model).

2. **Modify the orderable block in `care_plan_engine.py` (~line 881):**
   - After fetching `diet_rows`, for each `diet_item`:
     - Query `orders` table for the pet's most recent order matching the diet item (by product name or product_id).
     - If prior order exists: set `cta_label: "Reorder"`. If no prior order: set `cta_label: "Order Now"`.
     - If prior order exists: calculate estimated supply remaining = `pack_days - (today - order_date).days`.
     - If supply ≤ 7 days: set `status_tag: "Due Soon"`. Otherwise keep `"Active"`.
   - Wrap the order query in try/except so failure falls back to existing behavior (`cta_label: "Order Now"`, `status_tag: "Active"`).

3. **Add `cta_label` to the item dict:**
   ```python
   continue_items[item_key] = {
       "name": diet_item.label,
       "test_type": tt,
       "freq": "Daily",
       "next_due": None,
       "status_tag": status_tag,  # "Active" or "Due Soon"
       "classification": Classification.PERIODIC.value,
       "reason": None,
       "orderable": True,
       "cta_label": cta_label,  # "Order Now" or "Reorder"
   }
   ```

4. **Write unit tests:**
   - Food item with no order history → `cta_label: "Order Now"`, `status_tag: "Active"`.
   - Food item with prior order, supply > 7 days → `cta_label: "Reorder"`, `status_tag: "Active"`.
   - Food item with prior order, supply ≤ 7 days → `cta_label: "Reorder"`, `status_tag: "Due Soon"`.
   - Order query failure → falls back to default behavior.
   - Existing care plan tests still pass.

---

## Acceptance Criteria
- [x] Food/supplement items with no order history return `cta_label: "Order Now"`, `status_tag: "Active"`
- [x] Items with prior order return `cta_label: "Reorder"`
- [x] Items with low supply (≤7 days) return `status_tag: "Due Soon"`
- [x] Items with sufficient supply return `status_tag: "Active"`
- [x] Order query failure falls back gracefully
- [x] Existing tests still pass (`python -m pytest`)

## Handoff — What Was Done
- Added backend order-history signal resolution for orderable food/supplement care-plan rows, including `cta_label` derivation and low-supply `Due Soon` tagging.
- Added qualifying order-status filtering and strict safe fallback to `Order Now` + `Active` on lookup/estimation failures.
- Added/expanded unit tests for no history, reorder active, reorder due-soon, cancelled-order guard, malformed supply data fallback, and query failure fallback.

## Handoff — Patterns Learned
- For care-plan orderability logic, keep helper-level failure isolation: never block plan generation on order-history issues.
- In this codebase, broad repo lint/type checks contain unrelated legacy noise; validate changed modules directly plus feature-specific tests.
- Keep frontend API typings in lockstep with backend payload evolution (`CarePlanItem` optional fields).

## Handoff — Files Changed
- backend/app/services/care_plan_engine.py
- backend/tests/unit/test_care_plan_engine.py
- frontend/src/lib/api.ts

## Status
COMPLETE
