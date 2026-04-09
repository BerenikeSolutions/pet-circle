---
task: 002
feature: cart-rules-engine
status: pending
depends_on: [001]
---

# Task 002: Product models and seed script

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective
Create `ProductFood` and `ProductSupplement` SQLAlchemy models, remove the old `ProductCatalog` model, update all imports across the codebase (12 files), and write a seed script that inserts all 41 SKUs from the Excel data.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```python
# [Model registration pattern — from backend/app/models/__init__.py:42,48-87]
from app.models.product_catalog import ProductCatalog
# ... in __all__:
"ProductCatalog",
```

```python
# [Database Base import — from backend/app/database.py]
from app.database import Base
# All models inherit from Base
```

```python
# [Old seed script pattern — from backend/scripts/seed_product_catalog.py]
# Reads from Excel, maps columns, inserts via SQLAlchemy session
# Uses CART_ID_MAP for manual cart_item_id mapping
```

```python
# [Files that import ProductCatalog — grep results]
# 1. backend/app/services/onboarding.py
# 2. backend/app/services/nutrition_service.py
# 3. backend/app/routers/dashboard.py (line 44)
# 4. backend/app/services/medicine_recurrence_service.py
# 5. backend/scripts/clear_database.sql
# 6. backend/app/models/__init__.py (line 42)
# 7. backend/app/services/cart_service.py (line 27)
# 8. backend/app/models/food_nutrition_cache.py
# 9. backend/app/models/cart_item.py
# 10. backend/app/models/product_catalog.py
# 11. backend/migrations/001_add_dashboard_tables.sql
# 12. backend/scripts/seed_product_catalog.py
```

```python
# [cart_service.py import and usage — from backend/app/services/cart_service.py:27, 123-127]
from app.models.product_catalog import ProductCatalog
# ...
product = (
    db.query(ProductCatalog)
    .filter(ProductCatalog.cart_item_id == product_id)
    .first()
)
```

```python
# [dashboard.py import — from backend/app/routers/dashboard.py:44]
from app.models.product_catalog import ProductCatalog
```

### Key Patterns in Use
- **Model convention:** All models use `from app.database import Base`, UUID PKs (except new product tables use VARCHAR sku_id)
- **Model registration:** Import in `__init__.py`, add to `__all__`
- **Seed scripts:** Located in `backend/scripts/`, run manually

### Architecture Decisions Affecting This Task
- **ADR-1:** Two tables — `ProductFood` and `ProductSupplement` with different schemas
- `cart_items.product_id` will store `sku_id` directly (e.g., "F001", "S003")

---

## Handoff from Previous Task
> Populated by /task-handoff after prior task completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps
1. Create `backend/app/models/product_food.py` — `ProductFood(Base)` with all columns matching migration 044
2. Create `backend/app/models/product_supplement.py` — `ProductSupplement(Base)` with all columns matching migration 044
3. Delete or gut `backend/app/models/product_catalog.py` (remove the class, keep file if needed for backwards compat or just delete)
4. Update `backend/app/models/__init__.py`:
   - Remove `ProductCatalog` import and `__all__` entry
   - Add `ProductFood` and `ProductSupplement` imports and `__all__` entries
5. Update all 12 files that import `ProductCatalog`:
   - `cart_service.py`: Replace `ProductCatalog` queries with `ProductFood` / `ProductSupplement` lookups using sku_id prefix (F→food, S→supplement)
   - `dashboard.py`: Replace import
   - `nutrition_service.py`, `onboarding.py`, `medicine_recurrence_service.py`: Replace or remove ProductCatalog references
   - `food_nutrition_cache.py`: Update if it references ProductCatalog
   - `cart_item.py`: Remove ProductCatalog reference in docstring if any
6. Write new `backend/scripts/seed_product_catalog.py`:
   - Insert 25 food rows (F001–F025) with exact data from Excel Sheet 3
   - Insert 16 supplement rows (S001–S016) with exact data from Excel Sheet 4
   - Use upsert pattern (ON CONFLICT DO UPDATE) for idempotency

_Requirements: 1.2, 1.3, 1.4, 1.5, 8.5_
_Skills: /python-patterns, /code-writing-software-development_

---

## Excel Data Reference (embed for seed script)

### Food SKUs (F001–F025)
| sku_id | brand_id | brand_name | product_line | life_stage | breed_size | pack_size_kg | mrp | discounted_price | condition_tags | breed_tags | vet_diet | popularity_rank | monthly_units_sold | price_per_kg | in_stock | notes |
|--------|----------|------------|-------------|-----------|-----------|-------------|-----|-----------------|---------------|-----------|---------|----------------|-------------------|-------------|---------|-------|
| F001 | BR01 | Royal Canin | Hypoallergenic | All | All | 2 | 1690 | 1520 | allergy,skin,hypoallergenic | all | Yes | 3 | 210 | 760 | Yes | Prescription range |
| F002 | BR01 | Royal Canin | Hypoallergenic | All | All | 7 | 4990 | 4490 | allergy,skin,hypoallergenic | all | Yes | 1 | 420 | 641 | Yes | Most popular pack |
| F003 | BR01 | Royal Canin | Hypoallergenic | All | All | 14 | 8900 | 7990 | allergy,skin,hypoallergenic | all | Yes | 4 | 85 | 571 | Yes | Value pack |
| F004 | BR01 | Royal Canin | Labrador Adult | Adult | Large | 3 | 2100 | 1890 | joint,weight | labrador | No | 2 | 310 | 630 | No | Breed-specific |
| F005 | BR01 | Royal Canin | Labrador Adult | Adult | Large | 12 | 7200 | 6480 | joint,weight | labrador | No | 5 | 90 | 540 | No | |
| F006 | BR01 | Royal Canin | Large Adult | Adult | Large | 4 | 2400 | 2160 | joint,digestive | large_breed | No | 6 | 180 | 540 | No | |
| F007 | BR01 | Royal Canin | Large Puppy | Puppy | Large | 4 | 2600 | 2340 | growth | large_breed | No | 7 | 150 | 585 | No | |
| F008 | BR01 | Royal Canin | Renal | All | All | 2 | 2100 | 1890 | kidney,renal | all | Yes | 8 | 45 | 945 | Yes | Prescription |
| F009 | BR01 | Royal Canin | Renal | All | All | 7 | 6500 | 5850 | kidney,renal | all | Yes | 9 | 30 | 836 | Yes | |
| F010 | BR01 | Royal Canin | Gastrointestinal | All | All | 2 | 2200 | 1980 | digestive,IBD,gastrointestinal | all | Yes | 10 | 60 | 990 | Yes | |
| F011 | BR02 | Hills Science Diet | i/d Digestive | All | All | 1.5 | 1800 | 1620 | digestive,IBD | all | Yes | 11 | 55 | 1080 | Yes | |
| F012 | BR02 | Hills Science Diet | k/d Kidney Care | All | All | 1.5 | 2100 | 1890 | kidney,renal | all | Yes | 12 | 40 | 1260 | Yes | Prescription renal |
| F013 | BR02 | Hills Science Diet | z/d Allergy | All | All | 3.5 | 4200 | 3780 | allergy,skin | all | Yes | 13 | 35 | 1080 | Yes | |
| F014 | BR02 | Hills Science Diet | Large Breed Adult | Adult | Large | 6 | 3800 | 3420 | joint | large_breed | No | 14 | 120 | 570 | No | |
| F015 | BR02 | Hills Science Diet | Large Breed Puppy | Puppy | Large | 6 | 4100 | 3690 | growth | large_breed | No | 15 | 95 | 615 | None | |
| F016 | BR03 | Drools | Focus Adult Large | Adult | Large | 3 | 1200 | 1080 | joint | large_breed | No | 16 | 380 | 360 | None | Value India brand |
| F017 | BR03 | Drools | Focus Adult Large | Adult | Large | 12 | 4200 | 3780 | joint | large_breed | No | 17 | 160 | 315 | None | |
| F018 | BR03 | Drools | Focus Puppy Large | Puppy | Large | 3 | 1350 | 1215 | growth | large_breed | No | 18 | 290 | 405 | None | |
| F019 | BR03 | Drools | Absolute Calcium | Puppy | All | 3 | 1100 | 990 | growth,bone | all | No | 19 | 210 | 330 | None | |
| F020 | BR04 | Pedigree | Adult | Adult | All | 10 | 2200 | 1980 | None | all | No | 20 | 850 | 198 | None | Mass market |
| F021 | BR04 | Pedigree | Puppy | Puppy | All | 3 | 750 | 675 | growth | all | No | 21 | 620 | 225 | None | |
| F022 | BR05 | Farmina N&D | GF Ancestral Grain Boar | Adult | Medium | 3 | 3900 | 3510 | skin,coat,grain_free | all | No | 22 | 70 | 1170 | None | Premium grain-free |
| F023 | BR05 | Farmina N&D | Ocean Cod Puppy | Puppy | All | 2.5 | 3200 | 2880 | growth,skin | all | No | 23 | 45 | 1152 | None | |
| F024 | BR06 | Acana | Regionals Meadowland | Adult | All | 2 | 3500 | 3150 | skin,coat | all | No | 24 | 30 | 1575 | None | Super-premium import |
| F025 | BR01 | Royal Canin | Satiety Weight Mgmt | All | All | 1.5 | 1900 | 1710 | obesity,weight | all | Yes | 25 | 65 | 1140 | None | Prescription weight |

### Supplement SKUs (S001–S016)
| sku_id | brand_id | brand_name | product_name | type | form | pack_size | mrp | discounted_price | key_ingredients | condition_tags | life_stage_tags | popularity_rank | monthly_units | price_per_unit | in_stock | notes |
|--------|----------|------------|-------------|------|------|----------|-----|-----------------|----------------|---------------|----------------|----------------|--------------|---------------|---------|-------|
| S001 | SB01 | Honst | Fish Oil - Salmon 300ml | fish_oil | liquid | 300 ml | 850 | 765 | Omega | coat,skin,joint,inflammation,omega3 | adult,puppy | 1 | 340 | 765 | Yes | |
| S002 | SB01 | Honst | Fish Oil - Salmon 150ml | fish_oil | liquid | 150 ml | 499 | 449 | Fish Oil | coat,skin,joint,omega3 | adult,puppy | 2 | 510 | 449 | Yes | Starter size |
| S003 | SB02 | Zesty Paws | Omega Bites - 90 chews | fish_oil | chew | 90 chews | 1800 | 1620 | UC-II & Zinc | coat,skin,omega3 | adult | 3 | 180 | 1620 | Yes | Chew form |
| S004 | SB02 | Zesty Paws | Mobility Bites - 90 chews | joint_supplement | chew | 90 chews | 2100 | 1890 | None | joint,hip,arthritis | senior,adult | 4 | 145 | 1890 | No | Glucosamine + Chondroitin |
| S005 | SB02 | Zesty Paws | Multivitamin Bites - 90 | multivitamin | chew | 90 chews | 1600 | 1440 | None | immunity,general_health | adult,puppy | 5 | 220 | 1440 | No | |
| S006 | SB03 | Beaphar | Puppy Milk | milk_replacer | powder | 500 g | 900 | 810 | None | growth,nutrition | puppy | 6 | 90 | 810 | No | For puppies < 6 weeks |
| S007 | SB03 | Beaphar | Multivitamin Syrup | multivitamin | liquid | 200 ml | 650 | 585 | None | immunity,general_health | adult,puppy,senior | 7 | 210 | 585 | No | |
| S008 | SB04 | Drools | Absolute Boneup - 500g | joint_supplement | powder | 500 g | 750 | 675 | None | joint,bone | senior,large_breed | 8 | 320 | 675 | Yes | Calcium + Phosphorus |
| S009 | SB05 | Himalaya | Erina EP Coat Supplement | coat_supplement | liquid | 200 ml | 280 | 252 | None | coat,skin | adult | 9 | 480 | 252 | Yes | Affordable India brand |
| S010 | SB06 | NutriVet | Joint Health Chews - 60 | joint_supplement | chew | 60 chews | 1400 | 1260 | None | joint,hip | senior | 10 | 95 | 1260 | Yes | |
| S011 | SB07 | Virbac | Megaderm - 250 ml | skin_supplement | liquid | 250 ml | 1100 | 990 | None | skin,allergy,coat,omega6 | adult | 11 | 75 | 990 | Yes | Dermatology-grade |
| S012 | SB07 | Virbac | Pronefra - 180 ml | kidney_supplement | liquid | 180 ml | 1800 | 1620 | None | kidney,renal | adult,senior | 12 | 30 | 1620 | Yes | Vet-grade phosphate binder |
| S013 | SB08 | Vet Activ | Probiotic Paste - 30g | probiotic | paste | 30 g | 750 | 675 | None | digestive,gut_health | adult,puppy,senior | 13 | 165 | 675 | Yes | |
| S014 | SB08 | Vet Activ | Urinary Care - 100 tabs | urinary_supplement | tablet | 100 tabs | 1200 | 1080 | None | urinary,bladder | adult | 14 | 55 | 1080 | No | D-mannose + cranberry |
| S015 | SB09 | Venkys | Gro Pet - 500g | growth_supplement | powder | 500 g | 650 | 585 | None | growth,bone | puppy | 15 | 190 | 585 | None | Value puppy supplement |
| S016 | SB10 | Pet Health | CBD Calming Chews - 30 | calming | chew | 30 chews | 2200 | 1980 | None | anxiety,stress,behaviour | adult,senior | 16 | 40 | 1980 | None | New category |

---

## Acceptance Criteria
- [ ] `ProductFood` model exists at `backend/app/models/product_food.py` matching design spec
- [ ] `ProductSupplement` model exists at `backend/app/models/product_supplement.py` matching design spec
- [ ] Old `ProductCatalog` model is removed
- [ ] `backend/app/models/__init__.py` exports `ProductFood` and `ProductSupplement`, no `ProductCatalog`
- [ ] No file in the codebase imports `ProductCatalog` (grep returns 0 results)
- [ ] Seed script inserts exactly 25 food rows and 16 supplement rows
- [ ] All existing imports compile without error
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
