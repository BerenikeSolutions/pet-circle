---
task: 003
feature: dashboard-rebuild
status: complete
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
- [x] Correct life stage for all 5 breed sizes at boundary ages
- [x] Traits cached in DB after first GPT call
- [x] Cache invalidated when life stage changes
- [x] Fallback returns empty traits on GPT failure
- [ ] All existing tests pass (blocked by pre-existing unrelated failures in dashboard/onboarding tests)
- [ ] `/verify` passes fully (type check tool unavailable; global lint/test failures pre-exist this task)

---

## Handoff to Next Task

**Files changed:**
- `backend/app/services/life_stage_service.py`
- `backend/tests/unit/test_life_stage_service.py`

**Decisions made:**
- Reused breed-size and life-stage boundary logic from `care_plan_engine.py` to keep one source of truth.
- Cache is now treated as valid only when both `life_stage` and `breed_size` match current computation.
- On cache miss, stale rows for prior stage/size are deleted and a fresh row is inserted.

**Context for next task:**
- `LifeStageData` is ready for `dashboard_service` integration (stage, age_months, breed_size, traits, essential_care).
- Traits GPT output is normalized and clamped (max 5 traits, max 2 essential care items, color whitelist).
- Unit tests cover boundaries, cache hit, cache miss, breed-size mismatch invalidation, and GPT fallback.

**Open questions:**
- Decide whether to migrate this service to `AsyncSession` in a later refactor for fully non-blocking DB I/O.

## Handoff — What Was Done
- Implemented `life_stage_service` with life stage computation, GPT trait generation, JSON normalization, and DB caching.
- Added robust fallback behavior so GPT/parsing failures return empty trait payloads without breaking dashboard flow.
- Added dedicated unit tests for acceptance criteria and cache invalidation edge cases.

## Handoff — Patterns Learned
- For this dashboard rebuild, cache validity must include both stage and size context; stage-only checks can return stale insights.
- Lightweight fake DB sessions are sufficient for service-level unit tests if query filters are actually enforced in the fake.

## Handoff — Files Changed
- `backend/app/services/life_stage_service.py`
- `backend/tests/unit/test_life_stage_service.py`
- `.spec/dashboard-rebuild/tasks/task-003.md`

## Status
COMPLETE
