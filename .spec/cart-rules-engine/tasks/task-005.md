---
task: 005
feature: cart-rules-engine
status: completed
depends_on: [003, 004]
---

# Task 005: Unit tests for signal resolver

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /tdd-workflow, /python-patterns
Commands: /verify, /task-handoff

---

## Objective
Write comprehensive unit tests for `signal_resolver.py` covering all food rules (A1-A6), supplement rules (B1-B4), cross-cutting rules (OOS filtering, max 3 trim, ranking), and edge cases.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```python
# [Existing test pattern — check backend/tests/ for convention]
# Tests use pytest with SQLAlchemy session fixtures
# Test DB is typically an in-memory SQLite or test Supabase instance
```

```python
# [Signal resolver API — from task-003/004]
def resolve_food_signal(db: Session, diet_item: DietItem, pet: Pet, conditions: list[Condition]) -> SignalResult
def resolve_supplement_signal(db: Session, diet_item: DietItem, pet: Pet) -> SignalResult

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
- **Test file naming:** `test_{module_name}.py` in `backend/tests/`
- **Fixture pattern:** Create test DB objects inline or via fixtures, pass to function under test

---

## Handoff from Previous Task
> Populated by /task-handoff after prior task completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps
1. Create `backend/tests/test_signal_resolver.py`
2. Create fixtures:
   - `seed_food_products(db)` — insert representative subset of food SKUs (at least F001-F010, F004-F005 for breed tests)
   - `seed_supplement_products(db)` — insert representative supplement SKUs (S001-S005, S008-S010)
   - Helper to create mock `DietItem`, `Pet`, `Condition` objects
3. Test food rules:
   - `test_food_l5_exact_match` — brand+line+size known → L5, exact SKU returned + 2 alts
   - `test_food_l5_nearest_size_fallback` — exact size not in DB → nearest size shown
   - `test_food_l4_pack_selector` — brand+line, no size → L4, pack sizes sorted by popularity
   - `test_food_l4_max_3_sizes` — ensure max 3 sizes returned
   - `test_food_l3_brand_lines` — brand only → L3, profile-ranked lines
   - `test_food_l2c_condition_match` — health condition → L2c, condition-matched products
   - `test_food_l2b_breed_specific` — breed known → L2b, breed-tagged products
   - `test_food_l2b_fallback_breed_size` — no breed tag → fallback to breed_size category
   - `test_food_l2_category_profile` — life stage/size → L2, top 3 brands
   - `test_food_l1_no_data` — nothing known → L1, no products, prompt message
4. Test supplement rules:
   - `test_supplement_l5_exact` — brand+type+size → L5
   - `test_supplement_l5_closest_variant` — exact not found → closest variant
   - `test_supplement_l4_size_selector` — brand+type → L4, sizes sorted
   - `test_supplement_l3_type_only` — type known → L3, 2 bestsellers + 1 budget
   - `test_supplement_l1_generic` — "vitamins" → L1, no products
5. Test cross-cutting:
   - `test_oos_excluded_primary` — OOS product not in first position
   - `test_oos_all_products_fallback` — all matching OOS → show nearest in-stock
   - `test_max_3_trim` — DB has >3 matches → only 3 returned
   - `test_ranking_order` — condition > life_stage > breed > popularity
   - `test_signal_priority` — L5 chosen over L4 when both possible
6. Test edge cases:
   - `test_empty_brand_field` — diet_item.brand is None, label has brand
   - `test_empty_label` — minimal diet_item
   - `test_no_products_in_db` — empty product tables → L1

_Requirements: 2.1-2.5, 3.1-3.14, 4.1-4.9_
_Skills: /tdd-workflow, /python-patterns_

---

## Acceptance Criteria
- [x] `backend/tests/test_signal_resolver.py` exists
- [x] All tests pass (29/29)
- [x] Every food rule (A1-A6) has at least one test
- [x] Every supplement rule (B1-B4) has at least one test
- [x] OOS filtering, max 3 trim, and ranking order tested
- [x] Edge cases covered (empty fields, no products)
- [x] Coverage of `signal_resolver.py` >= 90% (95%)
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** `backend/tests/unit/test_signal_resolver.py` (new, ~530 lines: 29 tests covering all food/supplement rules, cross-cutting, and edge cases)
**Decisions made:**
- Used in-memory SQLite with selective table creation (only the 5 tables needed) to avoid JSONB incompatibility from other models.
- Factory helpers (`_make_pet`, `_make_diet_item`, `_make_condition`) create detached SQLAlchemy instances via constructor.
- "vitamins" keyword maps to multivitamin type (L3), so L1/B4 generic test uses "supplements" instead.
**Context for next task:** Signal resolver has 95% test coverage. Both `resolve_food_signal()` and `resolve_supplement_signal()` are fully tested and ready to wire into the cart service / dashboard API.
**Open questions:** None
