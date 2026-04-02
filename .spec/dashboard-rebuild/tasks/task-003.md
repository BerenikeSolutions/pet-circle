---
task: 003
feature: dashboard-rebuild
status: pending
depends_on: [1]
---

# Task 003: Life Stage Service

## Session Bootstrap
Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create `backend/app/services/life_stage_service.py` that computes life stage data (stage, age_months, breed_size) and generates/caches breed-specific traits via GPT in the `pet_life_stage_traits` table.

---

## Codebase Context

### Key Code Snippets

```python
# [Pet model DOB + breed + weight — from backend/app/models/pet.py:48-60]
breed = Column(String(100), nullable=True)
dob = Column(Date, nullable=True)
weight = Column(Numeric(5, 2), nullable=True)
```

```python
# [GPT call pattern — from backend/app/services/ai_insights_service.py:58-62]
_openai_client = None
def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client
```

```python
# [retry pattern — from backend/app/services/ai_insights_service.py:100]
raw = await retry_openai_call(_call)
```

### Key Patterns in Use
- **GPT caching:** `pet_ai_insight` table caches insights with staleness check. Same pattern for life stage traits.
- **Breed size boundaries:** Defined in care_plan_engine.py (task 002). Reuse or import from there.
- **Fallback on GPT failure:** Return empty traits, log warning. Never crash.

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Create `backend/app/services/life_stage_service.py`
2. Implement `get_life_stage_data(db, pet)` → LifeStageData:
   - Compute `age_months` from `pet.dob`
   - Determine `breed_size` from `pet.weight` / `pet.breed` (reuse logic from care_plan_engine or import)
   - Determine `stage` using breed-size-aware boundaries
   - Check `pet_life_stage_traits` for cached traits matching current `life_stage`
   - If cache hit and same life_stage → return cached traits
   - If cache miss or life_stage changed → generate via GPT, store in DB, return
3. GPT prompt for traits:
   - System: "Generate breed-specific traits for a [breed] at [age] in the [stage] life stage"
   - Output: JSON `{ traits: [{ label, color }], essential_care: [{ icon, title, detail }] }`
   - Max 5 traits (2 lines of pills), max 2 essential_care items
   - Colors: green (positive), yellow (watch), red (concern), neutral (personality)
   - No alarming phrases — inform how body is changing
4. Fallback: if GPT fails, return `{ traits: [], essential_care: [] }`
5. Write unit tests for breed size, stage classification, cache hit/miss

_Requirements: 5_

---

## Acceptance Criteria
- [ ] Correct life stage for all 5 breed sizes at boundary ages
- [ ] Traits cached in DB after first GPT call
- [ ] Cache invalidated when life stage changes
- [ ] Fallback returns empty traits on GPT failure
- [ ] All existing tests pass
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
