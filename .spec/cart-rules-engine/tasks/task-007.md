---
task: 007
feature: cart-rules-engine
status: pending
depends_on: [003, 004]
---

# Task 007: Update care plan engine for signal-level integration

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective
Replace `_resolve_diet_item_order_signals()` in `care_plan_engine.py` with calls to the signal resolver. The care plan API response must include `signal_level` and `has_cta` per diet item so the frontend knows whether to show "Order Now".

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```python
# [Current _resolve_diet_item_order_signals — from backend/app/services/care_plan_engine.py:754-816]
def _resolve_diet_item_order_signals(
    db: Session,
    pet_id: UUID,
    diet_label: str,
) -> tuple[str, str]:
    """Returns (cta_label, status_tag) — e.g. ("Order Now", "Active") or ("Reorder", "Due Soon")."""
    cta_label = _CTA_ORDER_NOW
    status_tag = _STATUS_ACTIVE
    try:
        # ... checks Order table for prior orders matching diet_label ...
        # ... calculates remaining_days from pack_days ...
        # ... returns ("Reorder", "Due Soon") if running low ...
    except Exception:
        return _CTA_ORDER_NOW, _STATUS_ACTIVE
    return cta_label, status_tag
```

```python
# [Where it's called — search for _resolve_diet_item_order_signals in care_plan_engine.py]
# Called per diet item in the care plan computation to determine CTA label and status tag
```

```python
# [CarePlanCard frontend — from frontend/src/components/dashboard/CarePlanCard.tsx:115-116]
const canOrder = bucketKey !== "attend" && item.orderable && !!item.reason;
const ctaText = (item.cta_label || "Order Now").replace(/\s*[→>-]+\s*$/, "");
# Frontend already reads item.cta_label — we just need to include signal_level
```

```python
# [Signal resolver API — from tasks 003/004]
from app.services.signal_resolver import resolve_food_signal, resolve_supplement_signal
# Returns SignalResult with level, products, cta_label, message
```

### Key Patterns in Use
- **Care plan item dict:** Items have `cta_label`, `orderable`, `status_tag` fields consumed by frontend
- **Existing reorder logic:** Checks `Order` table for prior orders, calculates remaining days — must be preserved
- **Signal level integration:** Add `signal_level` field to care plan item dict; frontend uses it to decide CTA visibility

---

## Handoff from Previous Task
> Populated by /task-handoff after prior task completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps
1. Import `resolve_food_signal`, `resolve_supplement_signal`, `SignalLevel` into `care_plan_engine.py`
2. Modify `_resolve_diet_item_order_signals()` or create a new wrapper function:
   - For food diet items (type="packaged"): call `resolve_food_signal(db, diet_item, pet, conditions)`
   - For supplement items (type="supplement"): call `resolve_supplement_signal(db, diet_item, pet)`
   - Extract signal level from result
   - If signal level >= L2: set `cta_label = "Order Now →"`, `orderable = True`
   - If signal level == L1: set `cta_label = None`, `orderable = False`, add `info_prompt` message
   - Preserve existing reorder logic: if prior order exists, still use "Reorder" and "Due Soon" status
3. Add `signal_level` field to the care plan item dict (alongside existing `cta_label`, `status_tag`)
4. Add `info_prompt` field (string or None) for L1 items
5. Ensure the care plan endpoint response includes these new fields
6. Handle homemade food items (type="homemade"): skip signal resolution, no CTA

_Requirements: 7.1, 7.2, 7.3, 7.4_
_Skills: /python-patterns, /code-writing-software-development_

---

## Acceptance Criteria
- [ ] Care plan API response includes `signal_level` per diet/supplement item
- [ ] L2+ items have `cta_label: "Order Now →"` and `orderable: true`
- [ ] L1 items have `cta_label: null`, `orderable: false`, and `info_prompt` message
- [ ] Existing reorder/due-soon logic preserved for items with prior orders
- [ ] Homemade food items have no CTA (as before)
- [ ] No regression in care plan computation for non-food items
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
