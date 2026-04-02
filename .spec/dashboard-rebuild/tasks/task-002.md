---
task: 002
feature: dashboard-rebuild
status: pending
depends_on: [1]
---

# Task 002: Care Plan Classification Engine

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /python-patterns, /code-writing-software-development, /tdd-workflow
Commands: /verify, /task-handoff

---

## Objective

Create `backend/app/services/care_plan_engine.py` implementing the full 7-step classification algorithm that assigns each preventive test_type to Continue/Attend To/Suggested buckets per pet. This is the core backend logic for the care plan card.

---

## Codebase Context

### Key Code Snippets

```python
# [PreventiveRecord model — from backend/app/models/preventive_record.py:25-123]
class PreventiveRecord(Base):
    __tablename__ = "preventive_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True)
    preventive_master_id = Column(UUID(as_uuid=True), ForeignKey("preventive_master.id"), nullable=True)
    custom_preventive_item_id = Column(UUID(as_uuid=True), ForeignKey("custom_preventive_items.id", ondelete="CASCADE"), nullable=True)
    last_done_date = Column(Date, nullable=True)
    next_due_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False)
    custom_recurrence_days = Column(Integer, nullable=True)
    medicine_name = Column(String(200), nullable=True)
    # Relationships
    pet = relationship("Pet", back_populates="preventive_records")
    preventive_master = relationship("PreventiveMaster", back_populates="preventive_records")
```

```python
# [Pet model key fields — from backend/app/models/pet.py:25-75]
class Pet(Base):
    __tablename__ = "pets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    species = Column(String(10), nullable=False)
    breed = Column(String(100), nullable=True)
    gender = Column(String(10), nullable=True)
    dob = Column(Date, nullable=True)
    weight = Column(Numeric(5, 2), nullable=True)
```

```python
# [DiagnosticTestResult model — from backend/app/models/diagnostic_test_result.py:15-36]
class DiagnosticTestResult(Base):
    __tablename__ = "diagnostic_test_results"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"))
    test_type = Column(String(30), nullable=False)  # blood | urine
    parameter_name = Column(String(120), nullable=False)
    observed_at = Column(Date, nullable=True)
    status_flag = Column(String(20), nullable=True)  # low | normal | high | abnormal
```

```python
# [Condition model — from backend/app/models/condition.py:27-69]
class Condition(Base):
    __tablename__ = "conditions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"))
    name = Column(String(200), nullable=False)
    condition_type = Column(String(20), nullable=False, default="chronic")
    medications = relationship("ConditionMedication", back_populates="condition")
```

### Key Patterns in Use
- **Service pattern:** Functions accept `db: Session` + domain objects, return typed dicts
- **GPT calls:** Wrapped in `retry_openai_call()`, lazy-init client via `_get_openai_client()`
- **Error isolation:** All external calls wrapped in try/except, never crash the dashboard

### Architecture Decisions Affecting This Task
- Classification runs INDEPENDENTLY per test_type per pet
- Conflict resolution: ATTEND TO > CONTINUE > SUGGESTED
- Items due next year: record but EXCLUDE from response
- Baseline overridden by observed periodic frequency when periodic reports qualify

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Create `backend/app/services/care_plan_engine.py` with:
   - `BreedSize` enum (mini_toy, small, medium, large, extra_large)
   - `LifeStage` enum (puppy, junior, adult, senior)
   - `Classification` enum (NO_HISTORY, SINGLE, SPORADIC, PERIODIC, PERIODIC_INSUFFICIENT, PRESCRIPTION_ACTIVE)
   - `BREED_SIZE_BOUNDARIES` dict mapping breed size → weight thresholds + life stage boundaries
   - `BASELINE_PROTOCOL` dict mapping (life_stage, test_type) → interval_days

2. Implement helper functions:
   - `_get_breed_size(weight_kg, breed)` → BreedSize
   - `_get_life_stage(age_months, breed_size)` → LifeStage
   - `_get_baseline_protocol(life_stage, test_type)` → int (days)
   - `_filter_redundant_reports(reports)` → filtered list (remove same-day dups, <30 day non-Rx)

3. Implement 7-step classification:
   - `_classify_test(reports, baseline_days, prescription)` → Classification
   - Step 1: Count valid reports → n
   - Step 2: n=0 → NO_HISTORY; n=1 → SINGLE; n≥2 → continue
   - Step 3: Sort by date, calculate consecutive gaps
   - Step 4: Any gap > 2× baseline → SPORADIC
   - Step 5: Tolerance = 0.40 × baseline. All gaps within → candidate PERIODIC
   - Step 6: median_gap ≤ baseline + tolerance → PERIODIC. Else → SPORADIC
   - Step 7: PERIODIC + median_gap > baseline → PERIODIC_INSUFFICIENT

4. Implement prescription override and conflict resolution

5. Implement `compute_care_plan(db, pet)` → CarePlanV2:
   - For each test_type: fetch reports, classify, compute next_due
   - Map to buckets (PERIODIC→Continue, PRESCRIPTION→Attend, rest→Suggested)
   - Exclude items due next year
   - Add orderable food/supplements to Continue

6. Write comprehensive unit tests covering all 7 paths + edge cases

_Requirements: 8, 9_
_Skills: /python-patterns, /code-writing-software-development, /tdd-workflow_

---

## Acceptance Criteria
- [ ] All 7 classification paths tested with fixture data
- [ ] Redundancy guards work (same-day dups removed, <30 day non-Rx excluded)
- [ ] Prescription overrides classify as ATTEND TO
- [ ] Conflict resolution prevents items in two buckets
- [ ] Items due next year excluded from response
- [ ] Orderable food/supplements placed in Continue bucket
- [ ] All existing tests pass
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
