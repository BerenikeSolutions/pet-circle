# Fix: Supplement Capture Issue (Omega-3 Still Recommended)

## Problem
When users provided supplement information (e.g., "omega") either in:
- The meal details question ("What does Zayn eat?")
- The dedicated supplements question ("Is Zayn on any supplements?")

The supplement data wasn't being captured and stored, so the nutrition analysis would still recommend those nutrients.

**Example**: User said "omega" → Dashboard still recommended "Omega-3 supplement"

## Root Causes

### Issue 1: Supplements Step Using Wrong Extractor
**File**: `backend/app/services/onboarding.py:1662-1669` (before fix)

The `_step_supplements_v2()` function was using `_parse_diet_input()` - a **food-specific** parser that classifies items into:
- "brand" (e.g., Royal Canin, Pedigree)
- "ingredient" (e.g., chicken, rice)
- "generic_treat" (e.g., small treat, biscuit)

When users said "omega", it didn't match any food pattern, so GPT returned empty results → supplement was never stored.

### Issue 2: No Fallback for Unrecognized Supplements
Both paths (meal details and supplements) had no fallback when the extractors couldn't identify a supplement.

## Solution

### Change 1: Use Supplement-Specific Extractor
**File**: `backend/app/services/onboarding.py:1662-1675`

Changed from food parser to `_extract_meal_supplement_items()`:
```python
# BEFORE: Used food-specific parser
items = await _parse_diet_input(text)

# AFTER: Uses supplement-specific extractor
supplements = await _extract_meal_supplement_items(text)
```

The supplement extractor has a better prompt that recognizes:
- Capsules, oils, powders, tablets
- Herbal add-ons and health support additives
- Even when mixed into food

### Change 2: Add Fallback for Unrecognized Supplements
**File**: `backend/app/services/onboarding.py:1668-1670`

```python
# If supplement extractor returns no items, 
# treat raw input as a supplement label
if not supplements and text_lower and text_lower not in _SKIP_INPUTS:
    supplements = [(text.strip(), "")]
```

## How It Works Now

### Path 1: Supplement Mentioned in Meal Details
1. User: "boiled chicken, rice, and omega"
2. `_parse_diet_input()` → extracts food items
3. `_extract_meal_supplement_items()` → recognizes "omega" as supplement
4. Both are stored as DietItems

### Path 2: Supplement in Dedicated Question
1. User: "omega"
2. `_extract_meal_supplement_items()` → recognizes "omega" as supplement
3. If GPT returns empty → fallback treats it as supplement label
4. Stored as DietItem(type='supplement', label='omega')

### Path 3: Nutrition Analysis
1. DietItem retrieved with type='supplement', label='omega'
2. `resolve_supplement_coverage('omega')` → returns ['Omega-3', 'Omega-6', 'Omega-9']
3. LLM prompt includes: `[covers: Omega-3, Omega-6, Omega-9]`
4. Per SUPPLEMENT COVERAGE RULE, LLM marks these as "sufficient"
5. Dashboard no longer recommends Omega-3

## Benefits

✓ Supplements from BOTH meal details AND supplements questions are now captured
✓ Uses proper supplement-specific extractor (better recognition)
✓ Has fallback for edge cases (unrecognized generic supplements)
✓ Consistent handling across both input paths
✓ Reduces false positive supplement recommendations

## Testing

The supplement coverage logic has been verified:
- ✓ "omega" expands to Omega-3, Omega-6, Omega-9
- ✓ Case-insensitive ("OMEGA", "Omega", "omega" all work)
- ✓ Specific supplements like "Omega-3" stay as-is
- ✓ Works with other supplements (probiotics, vitamins, collagen, etc.)
- ✓ Fallback handles unparseable supplements

## Files Changed

- `backend/app/services/onboarding.py`: Line 1662-1675 (`_step_supplements_v2()`)
  - Changed from `_parse_diet_input()` to `_extract_meal_supplement_items()`
  - Added fallback for unrecognized supplements

## Related Code

### Supplement Coverage Resolution
**File**: `backend/app/services/diet_service.py:71-101`
- `SUPPLEMENT_AMBIGUITY_MAP`: Maps generic supplement names to their sub-types
- `resolve_supplement_coverage()`: Case-insensitive resolution
- Example: "omega" → ["Omega-3", "Omega-6", "Omega-9"]

### Nutrition Analysis Integration
**File**: `backend/app/services/nutrition_service.py:697-700`
- Includes coverage info in LLM prompt: `[covers: Omega-3, Omega-6, Omega-9]`

### LLM Instruction
**File**: `backend/app/services/nutrition_service.py:524-527`
- System prompt rule: "For any nutrient covered by a supplement, assign status 'sufficient'"

## Backward Compatibility

This change is fully backward compatible:
- Existing supplement data is unaffected
- The meal details extraction path (which was working) is unchanged
- Only the supplements step extraction improved
