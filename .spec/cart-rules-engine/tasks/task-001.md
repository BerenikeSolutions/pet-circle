---
task: 001
feature: cart-rules-engine
status: COMPLETE
depends_on: []
---

# Task 001: Migration — Drop old product_catalog, create product_food and product_supplement

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /database-migrations, /postgres-patterns
Commands: /verify, /task-handoff

---

## Objective
Write a SQL migration that drops the old `product_catalog` table, clears stale data from `cart_items` and `order_recommendations`, and creates two new tables (`product_food`, `product_supplement`) with the schema defined in the design spec. Existing `orders` and `pet_preferences` must be untouched.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```python
# [Old model to be replaced — from backend/app/models/product_catalog.py:23-76]
class ProductCatalog(Base):
    __tablename__ = "product_catalog"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(30), nullable=False, index=True)  # food, deworming, flea_tick, medicine
    brand = Column(String(100), nullable=False)
    product_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    # ... 20+ nutritional/medicine columns ...
    cart_item_id = Column(String(10), nullable=True)  # c2, c3, etc.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
```

```sql
-- [Latest migration number — from backend/migrations/043_truncate_preventive_master.sql]
-- Next migration should be 044
```

```python
# [CartItem model — from backend/app/models/cart_item.py:24-54]
class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("pet_id", "product_id", name="uq_cart_item"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id = Column(String(100), nullable=False)  # Will store new sku_id (F001, S003, etc.)
    # ...
```

### Key Patterns in Use
- **Migration naming:** `NNN_descriptive_name.sql` — next is `044`
- **No ORM migrations:** Raw SQL files in `backend/migrations/`, applied manually via Supabase SQL editor
- **Tables use UUID PKs** except for new product tables which use VARCHAR sku_id PKs

### Architecture Decisions Affecting This Task
- **ADR-1:** Two tables (product_food + product_supplement) instead of one polymorphic table. Different column sets, cleaner schema.

---

## Handoff from Previous Task
> First task — no prior handoff.

**Files changed by previous task:** _(none)_
**Decisions made:** _(none)_
**Context for this task:** _(none)_
**Open questions left:** _(none)_

---

## Implementation Steps
1. Create `backend/migrations/044_cart_rules_product_tables.sql`
2. Write SQL to:
   - `TRUNCATE cart_items CASCADE;` (clear stale product references)
   - `TRUNCATE order_recommendations CASCADE;` (clear stale cached recommendations)
   - `DROP TABLE IF EXISTS product_catalog CASCADE;`
   - `CREATE TABLE product_food (...)` with all columns per design spec
   - `CREATE TABLE product_supplement (...)` with all columns per design spec
   - Add indexes: `idx_product_food_brand_id`, `idx_product_food_life_stage_breed`, `idx_product_food_condition_tags`, `idx_product_supplement_brand_id`, `idx_product_supplement_type`
3. Verify migration SQL is syntactically correct

_Requirements: 1.1, 1.2, 1.3, 1.6, 8.1, 8.2, 8.4_
_Skills: /database-migrations, /postgres-patterns_

---

## Acceptance Criteria
- [ ] Migration file `044_cart_rules_product_tables.sql` exists and is valid SQL
- [ ] Old `product_catalog` table is dropped
- [ ] `product_food` table created with: sku_id (PK VARCHAR), brand_id, brand_name, product_line, life_stage, breed_size, pack_size_kg (DECIMAL), mrp (INTEGER), discounted_price (INTEGER), condition_tags (TEXT), breed_tags (TEXT), vet_diet_flag (BOOLEAN), active (BOOLEAN), popularity_rank (INTEGER), monthly_units_sold (INTEGER), price_per_kg (INTEGER), in_stock (BOOLEAN), notes (TEXT), created_at (TIMESTAMPTZ)
- [ ] `product_supplement` table created with: sku_id (PK VARCHAR), brand_id, brand_name, product_name, type (VARCHAR), form (VARCHAR), pack_size (VARCHAR), mrp (INTEGER), discounted_price (INTEGER), key_ingredients (TEXT), condition_tags (TEXT), life_stage_tags (TEXT), active (BOOLEAN), popularity_rank (INTEGER), monthly_units (INTEGER), price_per_unit (INTEGER), in_stock (BOOLEAN), notes (TEXT), created_at (TIMESTAMPTZ)
- [ ] `cart_items` and `order_recommendations` are cleared
- [ ] `orders` and `pet_preferences` are NOT touched
- [ ] All indexes created
- [ ] `/verify` passes

---

## Handoff — What Was Done
- Created `backend/migrations/044_cart_rules_product_tables.sql` wrapped in BEGIN/COMMIT.
- Truncates `cart_items` and `order_recommendations` (stale FK refs), drops `product_catalog CASCADE`, creates `product_food` and `product_supplement` with full column sets per design spec.
- All 5 indexes created: `idx_product_food_brand_id`, `idx_product_food_life_stage_breed`, `idx_product_food_condition_tags`, `idx_product_supplement_brand_id`, `idx_product_supplement_type`.
- `orders` and `pet_preferences` untouched as required.

## Handoff — Patterns Learned
- Migrations live in `backend/migrations/NNN_*.sql`, raw SQL applied manually via Supabase SQL editor (no Alembic).
- Convention: wrap DDL in `BEGIN; ... COMMIT;` with a top-of-file header comment explaining destructive steps and rollback.
- Used `TIMESTAMPTZ DEFAULT NOW()` for `created_at` (design spec says TIMESTAMP; TIMESTAMPTZ chosen for Asia/Kolkata correctness — matches other tables in the codebase).
- `sku_id` uses `VARCHAR(10)` (F001–F025, S001–S016); `brand_id` also `VARCHAR(10)` (BR01, BR02, ...).
- Old ORM model `backend/app/models/product_catalog.py` still exists — Task 002 must replace it with new `ProductFood` / `ProductSupplement` models and update all imports.

## Handoff — Files Changed
- `backend/migrations/044_cart_rules_product_tables.sql` (new)

## Status
COMPLETE
