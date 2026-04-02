---
task: 005
feature: dashboard-rebuild
status: pending
depends_on: [1]
---

# Task 005: Extend nutrition_service.py — Diet Summary

## Session Bootstrap
Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Add `get_diet_summary()` to `backend/app/services/nutrition_service.py` that formats existing nutrition analysis data as donut summaries with guardrail-compliant thresholds.

---

## Codebase Context

### Key Code Snippets

```python
# [Nutrition service pipeline — from backend/app/services/nutrition_service.py:1-14]
"""
Pipeline:
    1. Get breed-specific targets (DB cache → GPT → fallback)
    2. Match diet items to product catalog (multi-strategy matching)
    3. For unmatched items, estimate nutrition via GPT (DB cache → GPT)
    4. Aggregate, compare against targets, generate recommendations
"""
```

```python
# [Default targets fallback — from backend/app/services/nutrition_service.py:52-60]
DEFAULT_TARGETS = {
    "calories": 1200,
    "protein": 25,
    "fat": 14,
    "carbs": 50,
    "fibre": 4,
    "moisture": 10,
    "calcium": 1.0,
    "phosphorus": 0.8,
}
```

### Key Patterns in Use
- **Nutrition pipeline:** Already computes targets, matches diet items, aggregates totals
- **Caching:** Uses `NutritionTargetCache` and `FoodNutritionCache` tables
- **New method adds formatting layer on top of existing computation**

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Add `async def get_diet_summary(db, pet)` → DietSummary to `nutrition_service.py`
2. Use existing nutrition analysis pipeline to get totals and targets
3. Compute % of need for 4 macros: Calories, Protein, Omega-3, Fat
4. Apply guardrail thresholds:
   - Calories: >100% = amber, ≤100% = green
   - Protein/Fat: >110% = amber, <80% = red, else green
   - Omega-3: at 15% = RED (critical deficiency), <80% = red, >110% = amber
   - Green NOT used for >110%
5. Generate `note` field for each macro (e.g., "Critical gap", "On track", "Slightly over")
6. Compute missing micronutrients (max 3) with icon + name + reason from existing gap analysis
7. Return `{ macros: [...], missing_micros: [...] }`
8. Write unit tests for threshold logic (especially Omega-3 at 15% = RED)

_Requirements: 7, 18_

---

## Acceptance Criteria
- [ ] Donut data has correct thresholds for all 4 macros
- [ ] Omega-3 at 15% returns RED (not amber)
- [ ] Green NOT used for >110%
- [ ] Max 3 missing micronutrients returned
- [ ] Graceful fallback if nutrition data unavailable
- [ ] All existing tests pass
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
