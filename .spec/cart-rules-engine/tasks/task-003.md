---
task: 003
feature: cart-rules-engine
status: completed
depends_on: [002]
---

# Task 003: Signal resolver service — food rules (A1-A6)

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective
Create `backend/app/services/signal_resolver.py` with the `SignalLevel` enum, `SignalResult` dataclass, and `resolve_food_signal()` function implementing all 6 food signal rules (A1-A6). This is the core deterministic engine — no AI.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```python
# [DietItem model — from backend/app/models/diet_item.py:32-83]
class DietItem(Base):
    __tablename__ = "diet_items"
    __table_args__ = (
        UniqueConstraint("pet_id", "label", "type", name="uq_diet_item"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False)
    type = Column(String(20), nullable=False)  # packaged | homemade | supplement
    icon = Column(String(10), nullable=True)
    label = Column(String(200), nullable=False)  # e.g. "Royal Canin Golden Retriever Adult"
    detail = Column(String(200), nullable=True)  # e.g. "Dry kibble - 280g x 2/day"
    brand = Column(String(200), nullable=True)
    pack_size_g = Column(Integer, nullable=True)
    daily_portion_g = Column(Integer, nullable=True)
```

```python
# [Pet model — from backend/app/models/pet.py:25-60]
class Pet(Base):
    __tablename__ = "pets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    species = Column(String(10), nullable=False)  # dog, cat
    breed = Column(String(100), nullable=True)
    gender = Column(String(10), nullable=True)
    dob = Column(Date, nullable=True)
    # weight is Numeric(5,2)
```

```python
# [Condition model — from backend/app/models/condition.py:27-40]
class Condition(Base):
    __tablename__ = "conditions"
    # Key fields: name (String), condition_type (chronic/episodic/resolved), is_active (Boolean)
```

```python
# [ProductFood model — created in task-002]
class ProductFood(Base):
    __tablename__ = "product_food"
    sku_id = Column(String(10), primary_key=True)
    brand_id = Column(String(10), nullable=False)
    brand_name = Column(String(100), nullable=False)
    product_line = Column(String(200), nullable=False)
    life_stage = Column(String(20), nullable=False)
    breed_size = Column(String(20), nullable=False)
    pack_size_kg = Column(Numeric(5, 1), nullable=False)
    mrp = Column(Integer, nullable=False)
    discounted_price = Column(Integer, nullable=False)
    condition_tags = Column(Text, nullable=True)
    breed_tags = Column(Text, nullable=True)
    vet_diet_flag = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True)
    popularity_rank = Column(Integer, nullable=False)
    in_stock = Column(Boolean, nullable=False, default=True)
```

### Key Patterns in Use
- **Service convention:** Standalone functions (not classes), `db: Session` as first param
- **Breed size mapping:** Pet.breed → breed size (large/medium/small) — derive from breed name or weight
- **Life stage mapping:** Pet.dob → age → puppy (<1yr) / adult (1-7yr) / senior (7+yr)
- **OOS rule (C2):** Never show out-of-stock as primary recommendation
- **Max options (C8):** Never return more than 3 products

### Architecture Decisions Affecting This Task
- **ADR-2:** Deterministic signal resolution, no AI. Pure Python logic.
- Signal priority order: Brand > Product Line > Pack Size > Health Condition > Breed > Life Stage

---

## Handoff from Previous Task
> Populated by /task-handoff after prior task completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps
1. Create `backend/app/services/signal_resolver.py`
2. Define `SignalLevel(str, Enum)` with values: L5, L4, L3, L2, L2B, L2C, L1
3. Define `SignalResult` dataclass with: level, products (list[dict]), cta_label (str|None), highlight_sku (str|None), message (str|None)
4. Implement helper `_extract_brand(diet_item) -> str|None` — case-insensitive match of `diet_item.brand` or `diet_item.label` against known brand names in product_food
5. Implement helper `_extract_product_line(diet_item, brand_name) -> str|None` — substring match of label against product_line values for that brand
6. Implement helper `_extract_pack_size(diet_item) -> float|None` — parse from detail field or convert pack_size_g to kg
7. Implement helper `_get_pet_life_stage(pet) -> str` — derive from DOB (puppy/adult/senior)
8. Implement helper `_get_breed_size(pet) -> str` — derive from breed name or weight
9. Implement `resolve_food_signal(db, diet_item, pet, conditions)`:
   - Call extraction helpers to determine known signals
   - Apply signal level classification (L5 > L4 > L3 > L2c > L2b > L2 > L1)
   - For each level, query `product_food` with appropriate filters
   - Apply OOS filtering: exclude `in_stock=False` from primary position; if all OOS, show nearest in-stock
   - Apply ranking per rules (condition_match > life_stage > breed_size > popularity_rank)
   - Trim to max 3
   - Return `SignalResult`
10. Implement `_serialize_food_product(product: ProductFood, is_highlighted: bool) -> dict` — standard product dict for API response

_Requirements: 2.1, 2.3, 2.4, 2.5, 3.1-3.14, 5.2, 5.3, 5.11_
_Skills: /python-patterns, /code-writing-software-development_

---

## Acceptance Criteria
- [ ] `signal_resolver.py` exists with `SignalLevel` enum and `SignalResult` dataclass
- [ ] `resolve_food_signal()` correctly classifies: L5 (brand+line+size), L4 (brand+line), L3 (brand only), L2c (health condition), L2b (breed), L2 (life stage/size), L1 (nothing)
- [ ] A1: L5 returns exact SKU + up to 2 alt sizes
- [ ] A2: L4 returns pack sizes sorted by popularity, max 3
- [ ] A3: L3 returns brand's product lines ranked by profile match, max 3
- [ ] A4: L2/L2c returns top 3 brands with most relevant product each
- [ ] A5: L2b returns breed-specific lines first, fallback to breed_size
- [ ] A6: L1 returns empty products with info prompt message
- [ ] OOS products excluded from primary position (C2)
- [ ] Max 3 products returned at every level (C8)
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
