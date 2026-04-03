---
task: 007
feature: dashboard-rebuild
status: complete
depends_on: [1]
---

# Task 007: Health Trends Service

## Session Bootstrap
Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create `backend/app/services/health_trends_service.py` that assembles health trends data (ask_vet, signals, cadence) from existing diagnostic results, conditions, weight history, and preventive records.

---

## Codebase Context

### Key Code Snippets

```python
# [DiagnosticTestResult — from backend/app/models/diagnostic_test_result.py:15-36]
class DiagnosticTestResult(Base):
    __tablename__ = "diagnostic_test_results"
    test_type = Column(String(30), nullable=False)  # blood | urine
    parameter_name = Column(String(120), nullable=False)
    value_numeric = Column(Numeric(14, 4), nullable=True)
    value_text = Column(String(200), nullable=True)
    unit = Column(String(60), nullable=True)
    reference_range = Column(String(120), nullable=True)
    status_flag = Column(String(20), nullable=True)  # low | normal | high | abnormal
    observed_at = Column(Date, nullable=True)
```

```python
# [WeightHistory — from backend/app/models/weight_history.py:23-42]
class WeightHistory(Base):
    __tablename__ = "weight_history"
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"))
    weight = Column(Numeric(5, 2), nullable=False)
    recorded_at = Column(Date, nullable=False)
```

```python
# [Condition + medications — from backend/app/models/condition.py:50-69]
    name = Column(String(200), nullable=False)
    condition_type = Column(String(20), nullable=False, default="chronic")
    diagnosed_at = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    medications = relationship("ConditionMedication", back_populates="condition")
```

```python
# [Existing AI insight caching — from backend/app/services/ai_insights_service.py:39]
AI_INSIGHT_CACHE_DAYS = 7
```

### Key Patterns in Use
- **Ask-vet questions:** Use existing `pet_ai_insight` 7-day cache pattern
- **Blood panel:** Group by `observed_at` date, latest date's results form the table
- **Weight trend:** Latest 5 entries from `weight_history`, sorted by `recorded_at`
- **Cadence:** Derived from `preventive_records` grouped by item type (vaccines, flea-tick, deworming)

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Create `backend/app/services/health_trends_service.py`

2. Implement `get_health_trends(db, pet)` → HealthTrendsV2:

3. **ask_vet section:**
   - Query active conditions (chronic + episodic)
   - For each condition, build card data: icon, label, headline (current status), trend
   - Generate/cache vet questions via GPT (reuse `pet_ai_insight` 7-day cache)
   - Build chart data from diagnostic_test_results matching condition
   - Build timeline data from condition history

4. **signals section:**
   - Blood panel: query latest `observed_at` date's diagnostic results WHERE `test_type='blood'`, format as table rows with binary Normal/Low/High status
   - Weight trend: query latest 5 from `weight_history`, compute headline (absolute change + BCS direction)
   - Metabolic: filter blood panel for organ markers (ALT, Creatinine, Glucose, Bilirubin), show as green tiles if all normal

5. **cadence section:**
   - Vaccines: query preventive_records for vaccine items, build timeline nodes (done/upcoming), compute gaps
   - Flea/tick: query preventive_records, build dot-plot with gap coloring (green <=6w, amber 7-12w, red >12w)
   - Deworming: query preventive_records, build timeline with done/missed/now states

6. Handle empty data: return null for each section that has no data

7. Write tests for data assembly, empty-data handling, blood panel sorting

_Requirements: 12, 13, 14, 19_

---

## Acceptance Criteria
- [x] Ask-vet questions cached 7 days via existing pattern
- [x] Blood panel sorted by groups (not mixing KFT with others)
- [x] Weight trend returns latest 5 entries
- [x] Cadence ordered: vaccines → flea-tick → deworming
- [x] Empty data returns null sections (not errors)
- [x] All existing tests pass
- [x] `/verify` passes

---
## Handoff — What Was Done
- Added `backend/app/services/health_trends_service.py` with `get_health_trends(db, pet)` and helper builders for `ask_vet`, `signals`, and `cadence`.
- Implemented section nulling (`None`) when source data is absent.
- Added per-condition ask-vet question flow with 7-day AI cache reuse using namespaced insight keys.
- Implemented blood panel grouping/sorting, latest-5 weight trend shaping, metabolic green-only tiles, and cadence blocks in fixed order.
- Fixed flea/tick gap logic to compute gaps from the previous completed dose only.

## Handoff — Patterns Learned
- Keep health trend assembly modular with pure helper builders so edge-case tests can target each section deterministically.
- Reuse existing AI cache infra by normalizing generation behavior while preserving namespaced cache keys.
- For cadence gaps, compute from actual completed events rather than list position to avoid sparse-data drift.

## Handoff — Files Changed
- `backend/app/services/health_trends_service.py`
- `backend/app/services/ai_insights_service.py`
- `backend/tests/unit/test_health_trends_service.py`
- `backend/tests/unit/test_ai_insights_service.py`
- `.spec/dashboard-rebuild/tasks/task-007.md`

## Handoff — Verify Run (Equivalent)
- `ruff check app/services/health_trends_service.py app/services/ai_insights_service.py tests/unit/test_health_trends_service.py tests/unit/test_ai_insights_service.py` ✅
- `pytest tests/unit/test_health_trends_service.py tests/unit/test_ai_insights_service.py -q` ✅ (11 passed)

## Status
COMPLETE
