---
task: 004
feature: cart-rules-engine
status: completed
depends_on: [002, 003]
---

# Task 004: Signal resolver service — supplement rules (B1-B4)

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective
Add `resolve_supplement_signal()` to `signal_resolver.py` implementing all 4 supplement signal rules (B1-B4).

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```python
# [ProductSupplement model — created in task-002]
class ProductSupplement(Base):
    __tablename__ = "product_supplement"
    sku_id = Column(String(10), primary_key=True)
    brand_id = Column(String(10), nullable=False)
    brand_name = Column(String(100), nullable=False)
    product_name = Column(String(200), nullable=False)
    type = Column(String(50), nullable=False)   # fish_oil, joint_supplement, multivitamin, etc.
    form = Column(String(30), nullable=False)   # liquid, chew, powder, paste, tablet
    pack_size = Column(String(50), nullable=False)  # "300 ml", "90 chews"
    mrp = Column(Integer, nullable=False)
    discounted_price = Column(Integer, nullable=False)
    key_ingredients = Column(Text, nullable=True)
    condition_tags = Column(Text, nullable=True)
    life_stage_tags = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    popularity_rank = Column(Integer, nullable=False)
    price_per_unit = Column(Integer, nullable=True)
    in_stock = Column(Boolean, nullable=False, default=True)
```

```python
# [DietItem supplement example — from diet_items table]
# type = "supplement", label = "Honst Fish Oil 300ml", brand = "Honst"
# type = "supplement", label = "fish oil", brand = None  (L3 case)
# type = "supplement", label = "vitamins", brand = None  (L1/B4 case)
```

```python
# [Supplement type values in DB]
# fish_oil, joint_supplement, multivitamin, milk_replacer, coat_supplement,
# skin_supplement, kidney_supplement, probiotic, urinary_supplement,
# growth_supplement, calming
```

```python
# [SignalLevel and SignalResult — from task-003, signal_resolver.py]
class SignalLevel(str, Enum):
    L5 = "L5"; L4 = "L4"; L3 = "L3"; L2 = "L2"; L2B = "L2b"; L2C = "L2c"; L1 = "L1"

@dataclass
class SignalResult:
    level: SignalLevel
    products: list[dict]
    cta_label: str | None
    highlight_sku: str | None
    message: str | None
```

### Key Patterns in Use
- **B3 ranking:** 2 bestsellers (lowest popularity_rank) + 1 budget option (lowest discounted_price)
- **Type keyword mapping:** "fish oil" → fish_oil, "joint" → joint_supplement, "multivitamin"/"vitamin" → multivitamin, "probiotic" → probiotic, etc.
- **OOS rule (C2):** Exclude in_stock=False from primary position
- **Max 3 rule (C8):** Always trim to 3

---

## Handoff from Previous Task
> Populated by /task-handoff after prior task completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps
1. Add supplement type keyword map to `signal_resolver.py`:
   ```python
   SUPPLEMENT_TYPE_KEYWORDS = {
       "fish oil": "fish_oil", "omega": "fish_oil", "salmon oil": "fish_oil",
       "joint": "joint_supplement", "glucosamine": "joint_supplement", "mobility": "joint_supplement",
       "multivitamin": "multivitamin", "vitamin": "multivitamin",
       "probiotic": "probiotic", "gut": "probiotic",
       "coat": "coat_supplement", "skin": "skin_supplement",
       "kidney": "kidney_supplement", "renal": "kidney_supplement",
       "urinary": "urinary_supplement", "bladder": "urinary_supplement",
       "calming": "calming", "anxiety": "calming", "cbd": "calming",
       "milk": "milk_replacer", "growth": "growth_supplement",
   }
   ```
2. Implement `_extract_supplement_type(diet_item) -> str|None` — match label keywords against type map
3. Implement `_extract_supplement_brand(diet_item, db) -> str|None` — match against product_supplement.brand_name
4. Implement `resolve_supplement_signal(db, diet_item, pet)`:
   - Extract brand, type, form, pack_size from diet_item
   - Classify: brand+type+size → L5, brand+type → L4, type only → L3, generic → L1
   - B1 (L5): Exact match query, return single product + closest variant if not found
   - B2 (L4): Filter by brand+type, return pack size options sorted by popularity, max 3
   - B3 (L3): Filter by type, select 2 bestsellers (popularity_rank ASC) + 1 budget (price ASC), max 3
   - B4 (L1): Return empty products with info-capture prompt
   - Apply OOS filter and max 3 trim
5. Implement `_serialize_supplement_product(product: ProductSupplement, is_highlighted: bool) -> dict`

_Requirements: 2.2, 2.3, 2.4, 4.1-4.9, 5.2, 5.11_
_Skills: /python-patterns, /code-writing-software-development_

---

## Acceptance Criteria
- [x] `resolve_supplement_signal()` exists in `signal_resolver.py`
- [x] B1: L5 returns exact SKU with qty=1; fallback shows closest variant
- [x] B2: L4 returns pack size options sorted by popularity, max 3
- [x] B3: L3 returns 2 bestsellers + 1 budget option for the supplement type
- [x] B4: L1 returns empty products with info-capture prompt message
- [x] OOS products excluded from primary position (C2)
- [x] Max 3 products at every level (C8)
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** `backend/app/services/signal_resolver.py` (added ~280 lines: supplement type keyword map, extraction helpers, B1-B4 resolvers, serializer, `resolve_supplement_signal()` entry point)
**Decisions made:**
- Supplement L5 uses form as a soft hint (tighten query if matches exist, ignore otherwise) rather than a hard filter, so users aren't penalised for omitting form info.
- B3 (L3) selects 2 bestsellers by `popularity_rank` + 1 budget by `discounted_price`, each from a distinct brand where possible.
- `pet` and `conditions` args accepted for API parity with `resolve_food_signal` but unused by current B1-B4 rules.
- Pack size comparison is normalized-string equality (not numeric) since supplement pack_size is free-text ("300 ml", "90 chews").
**Context for next task:** Both `resolve_food_signal()` and `resolve_supplement_signal()` are now complete in `signal_resolver.py`. The next task can wire these into the cart service / dashboard API endpoint.
**Open questions:** None
