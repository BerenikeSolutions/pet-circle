# Product Medicines Table Integration Guide

## Status

✅ **COMPLETED**
- Created `backend/app/models/product_medicines.py` model
- Applied migrations 051_create_product_medicines.sql and 052_seed_product_medicines.sql
- Updated `backend/app/routers/dashboard.py` — medicine options now query `product_medicines`
- Updated `backend/app/services/gpt_extraction.py` — medicine mapping now dynamically loads from `product_medicines`

🔄 **REMAINING** (6 files) — See implementation steps below

---

## Overview

The `product_medicines` table (54 SKUs, active medicines) is now the single source of truth for tick, flea, deworming, and antibiotic products. Previous hardcoded lists have been replaced with dynamic database queries.

**Key Changes Made**:
- Dashboard medicine dropdown now queries `product_medicines` (active products, ordered by popularity)
- GPT extraction medicine mapping now loads from `product_medicines` at runtime
- "Other" option always available for unmapped/custom medicines

---

## Remaining Implementation Tasks

### 1. `recommendation_service.py` — Add medicine recommendations

**File**: `backend/app/services/recommendation_service.py`

**What to do**: When category="medicines", include top products from `product_medicines` sorted by popularity_rank.

**Implementation**:

```python
# Add this import at the top
from app.models.product_medicines import ProductMedicines

# Add this helper function
def _fetch_product_medicines_suggestions(
    db: Session,
    species: str,
    condition_tags: list[str],
    life_stage: str,
    limit: int = 5
) -> list[dict]:
    """Fetch medicine suggestions from product_medicines table."""
    query = db.query(ProductMedicines).filter(
        ProductMedicines.active == True
    )

    # Filter by species (dog, cat, both)
    if species:
        query = query.filter(
            ProductMedicines.life_stage_tags.ilike(f"%{species}%")
        )

    # Filter by life stage if available
    if life_stage:
        query = query.filter(
            ProductMedicines.life_stage_tags.ilike(f"%{life_stage}%")
        )

    # Order by popularity and return top results
    products = query.order_by(
        ProductMedicines.popularity_rank.asc(),
        ProductMedicines.in_stock.desc()
    ).limit(limit).all()

    return [
        {
            "name": p.product_name,
            "description": f"{p.brand_name} ({p.form})",
            "reason": f"Recommended for {p.life_stage_tags} — {p.condition_tags or 'general health'}",
            "sku": p.sku_id,
            "price": round(p.discounted_paise / 100, 2) if p.discounted_paise else None
        }
        for p in products
    ]

# In the main recommendation function, modify the category handling:
def get_or_generate_recommendations(db: Session, pet: Pet, category: str):
    # ... existing code ...
    
    if category == "medicines":
        # NEW: First try product_medicines suggestions
        medicines = _fetch_product_medicines_suggestions(
            db,
            species=pet.species,
            condition_tags=pet.condition_names or [],
            life_stage=pet.life_stage,
            limit=5
        )
        if medicines:
            return medicines
    
    # ... rest of existing logic ...
```

**Testing**:
- Call `get_or_generate_recommendations(db, pet, "medicines")`
- Verify it returns products from `product_medicines` ordered by popularity

---

### 2. `medicine_recurrence_service.py` — Use product_medicines repeat_frequency

**File**: `backend/app/services/medicine_recurrence_service.py`

**What to do**: When determining recurrence for a medicine, check if it exists in `product_medicines` and use its `repeat_frequency` field.

**Implementation**:

```python
# Add this import
from app.models.product_medicines import ProductMedicines

# Modify the main function
def get_medicine_recurrence(
    species: str,
    item_type: str,
    medicine_name: str | None,
    default_days: int,
    db: Session = None  # Add optional DB parameter
) -> int:
    """Determine recurrence for a medicine.
    
    First checks product_medicines table for repeat_frequency.
    Falls back to GPT-based inference if not found.
    """
    if not medicine_name or not db:
        return default_days

    try:
        # Query product_medicines for the medicine
        med = db.query(ProductMedicines).filter(
            ProductMedicines.product_name.ilike(f"%{medicine_name}%")
        ).first()

        if med and med.repeat_frequency:
            # Parse repeat_frequency string to days
            freq_lower = med.repeat_frequency.lower()
            
            # Simple mapping
            if "weekly" in freq_lower:
                # Extract number: "Every 2 weeks" -> 14
                import re
                match = re.search(r"(\d+)\s*week", freq_lower)
                if match:
                    weeks = int(match.group(1))
                    return weeks * 7
                return 14  # Default 2 weeks
            elif "monthly" in freq_lower:
                return 30
            elif "3 month" in freq_lower or "quarter" in freq_lower:
                return 90
            elif "12 week" in freq_lower:
                return 84  # 12 weeks
            elif "3 week" in freq_lower:
                return 21
            elif "6 week" in freq_lower:
                return 42

    except Exception as e:
        logger.warning("Could not fetch recurrence from product_medicines: %s", str(e))

    # Fallback to existing GPT-based logic
    return _gpt_infer_recurrence(species, item_type, medicine_name, default_days)
```

**Testing**:
- Get a known medicine from `product_medicines` (e.g., "NexGard Spectra 2–3.5 kg" with repeat_frequency="Monthly")
- Call `get_medicine_recurrence(..., medicine_name="NexGard Spectra", db=db)`
- Verify it returns 30 days (Monthly)

---

### 3. `order_service.py` — Dynamic example text

**File**: `backend/app/services/order_service.py`

**What to do**: When showing example text for medicines orders, pull top products from `product_medicines` instead of hardcoded "Nexgard 3 tablets, Drontal 1 tablet".

**Implementation**:

```python
# Add import
from app.models.product_medicines import ProductMedicines

# Add this helper function
def _get_example_medicines_text(db: Session, pet_species: str) -> str:
    """Generate example medicine order text from top products."""
    try:
        medicines = db.query(ProductMedicines).filter(
            ProductMedicines.active == True,
            ProductMedicines.life_stage_tags.ilike(f"%{pet_species}%")
        ).order_by(
            ProductMedicines.popularity_rank.asc()
        ).limit(3).all()

        if medicines:
            examples = ", ".join([m.product_name for m in medicines[:2]])
            return f"_Example: {examples}_"
    except Exception:
        pass

    return "_Example: Your preferred medicine names_"

# In handle_order_category() or wherever example text is used, replace hardcoded:
# OLD: "_Example: Nexgard 3 tablets, Drontal 1 tablet_"
# NEW:
example_text = _get_example_medicines_text(db, pet.species)
# Use example_text in response
```

**Testing**:
- Trigger order flow for "Medicines" category
- Verify example text shows real product names from `product_medicines` (not hardcoded)

---

### 4. `health_trends_service.py` — Enrich cadence with medicine metadata

**File**: `backend/app/services/health_trends_service.py`

**What to do**: When building cadence for flea/tick or deworming, optionally include medicine details (ingredients, dosage, warnings) from `product_medicines`.

**Implementation**:

```python
# Add import
from app.models.product_medicines import ProductMedicines

# Add helper function
def _enrich_cadence_medicine_info(medicine_name: str | None, db: Session) -> dict | None:
    """Fetch medicine metadata from product_medicines for cadence enrichment."""
    if not medicine_name:
        return None

    try:
        med = db.query(ProductMedicines).filter(
            ProductMedicines.product_name.ilike(f"%{medicine_name}%")
        ).first()

        if med:
            return {
                "product_name": med.product_name,
                "brand_name": med.brand_name,
                "form": med.form,
                "ingredients": med.key_ingredients,
                "dosage": med.dosage,
                "repeat_frequency": med.repeat_frequency,
                "warnings": med.notes,
                "price_display": f"₹{med.discounted_paise / 100:.0f}" if med.discounted_paise else None
            }
    except Exception as e:
        logger.debug("Could not enrich cadence medicine info: %s", str(e))

    return None

# In _build_flea_tick_cadence() or _build_deworming_cadence():
# After building the base cadence structure, optionally add medicine metadata:
if medicine_name and db:
    med_info = _enrich_cadence_medicine_info(medicine_name, db)
    if med_info:
        cadence["medicine_info"] = med_info
```

**Testing**:
- Call cadence endpoint for a pet with a known medicine (e.g., "NexGard Spectra 2–3.5 kg")
- Verify response includes medicine metadata (ingredients, dosage, frequency, etc.)

---

### 5. `nudge_engine.py` — Optional: Add medicine-specific nudge copy

**File**: `backend/app/services/nudge_engine.py`

**What to do**: When generating nudges for deworming/flea reminders, optionally fetch product-specific warnings or recommendations from `product_medicines.notes`.

**Implementation** (optional):

```python
# Add import
from app.models.product_medicines import ProductMedicines

# In nudge generation functions, add:
def _get_medicine_nudge_suffix(medicine_name: str | None, db: Session) -> str:
    """Get product-specific nudge suffix from product_medicines notes."""
    if not medicine_name or not db:
        return ""

    try:
        med = db.query(ProductMedicines).filter(
            ProductMedicines.product_name.ilike(f"%{medicine_name}%")
        ).first()

        if med and med.notes:
            return f"\n\n📌 {med.notes}"
    except Exception:
        pass

    return ""

# When building nudge message:
nudge_message = f"Your pet needs deworming..."
medicine_suffix = _get_medicine_nudge_suffix(preventive_record.medicine_name, db)
full_message = nudge_message + medicine_suffix
```

**Testing**:
- Generate nudges for a pet with a medicine that has warnings in `product_medicines.notes`
- Verify nudge includes the warning text

---

## Verification Checklist

After implementing each file, run:

```bash
# 1. Check migrations applied
cd backend
python -c "from app.database import engine; from app.models.product_medicines import ProductMedicines; from sqlalchemy import inspect; print([c.name for c in inspect(ProductMedicines).columns])"

# 2. Test dashboard endpoint
curl "http://localhost:8000/dashboard/{token}/preventive-medicine-options?item_name=deworming"
# Should return real products from product_medicines, not hardcoded list

# 3. Test GPT extraction
# Upload a document with "NexGard Spectra" and verify it's categorized as both flea_tick + deworming

# 4. Test recommendations
curl "http://localhost:8000/dashboard/{token}/recommendations?category=medicines"
# Should return products from product_medicines sorted by popularity

# 5. Test order service
# Trigger order flow for "Medicines" and verify example text is dynamic

# 6. Manual dashboard test
# Edit a preventive care reminder, change medicine
# Verify dropdown shows real products from product_medicines
```

---

## Important Notes

1. **Lazy Loading**: GPT extraction uses lazy initialization of `product_medicines` mapping. If DB is unavailable, it falls back to a minimal hardcoded set for safety.

2. **"Other" Option**: Always include "Other" in medicine dropdowns to allow users to enter custom/unmapped medicines.

3. **Popularity Sorting**: When querying medicines, order by `popularity_rank` to show most common products first.

4. **Price Display**: Prices stored in `mrp_paise` and `discounted_paise` (₹ × 100). Always convert to rupees when displaying: `price_paise / 100`.

5. **Backwards Compatibility**: Old hardcoded lists are completely removed. Unmapped medicines are handled via "Other" option.

---

## Files Modified Summary

| File | Changes | Status |
|------|---------|--------|
| `models/product_medicines.py` | Created | ✅ |
| `migrations/051_create_product_medicines.sql` | Created | ✅ |
| `migrations/052_seed_product_medicines.sql` | Created | ✅ |
| `routers/dashboard.py` | Query DB instead of hardcoded dict | ✅ |
| `services/gpt_extraction.py` | Dynamic mapping from product_medicines | ✅ |
| `services/recommendation_service.py` | Add product_medicines suggestions | 🔄 |
| `services/medicine_recurrence_service.py` | Use repeat_frequency from DB | 🔄 |
| `services/order_service.py` | Dynamic example text | 🔄 |
| `services/health_trends_service.py` | Enrich cadence with medicine metadata | 🔄 |
| `services/nudge_engine.py` | Add medicine-specific nudge copy | 🔄 Optional |

---

## Next Steps

1. Run tests for dashboard + gpt_extraction changes
2. Implement remaining 5 files following the patterns above
3. Run full integration test suite
4. Deploy to production

Questions? Refer back to the plan file at `.claude/plans/dazzling-skipping-aurora.md`.
