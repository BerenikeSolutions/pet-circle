---
task: 008
feature: dashboard-rebuild
status: pending
depends_on: [1]
---

# Task 008: Records Service

## Session Bootstrap
Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create `backend/app/services/records_service.py` that structures health records by type (vet visits, lab reports, imaging, WhatsApp) for the Records view.

---

## Codebase Context

### Key Code Snippets

```python
# [Document model — from backend/app/models/document.py:24-107]
class Document(Base):
    __tablename__ = "documents"
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"))
    document_name = Column(String(200), nullable=True)
    document_category = Column(String(30), nullable=True)  # Vaccination, Prescription, Diagnostic, Other
    doctor_name = Column(String(200), nullable=True)
    hospital_name = Column(String(200), nullable=True)
    extraction_status = Column(String(20), nullable=False)
    event_date = Column(Date, nullable=True)
```

```python
# [ConditionMedication — dose/frequency for vet visit cards]
class ConditionMedication(Base):
    __tablename__ = "condition_medications"
    name = Column(String(200), nullable=False)
    dose = Column(String(100), nullable=True)
    frequency = Column(String(100), nullable=True)
    route = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="active")
```

### Key Patterns in Use
- **Documents grouped by category:** `document_category` field determines type
- **Vet visits = Prescription category documents:** Enriched with medications from conditions
- **Event date ordering:** Sort by `event_date` descending (latest first)

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. Create `backend/app/services/records_service.py`
2. Implement `get_records(db, pet)` → RecordsV2:
   - Query all documents for pet WHERE `extraction_status='success'`
   - **Vet visits:** Filter `document_category='Prescription'`, enrich with:
     - Rx summary from document extraction data
     - Medications from `condition_medications` linked via condition → document
     - Notes from condition notes
     - Sort by event_date DESC
   - **Records:** Group remaining documents:
     - `Diagnostic` → lab reports
     - Imaging-related → imaging
     - WhatsApp source → whatsapp channel
   - Assign tag, tag_color, tag_bg based on category
   - Each record: `{ id, icon, type, title, date, tag, tag_color, tag_bg }`
3. Write tests for type grouping, medication enrichment, empty data

_Requirements: 17, 20_

---

## Acceptance Criteria
- [ ] Vet visits include medications and Rx summary
- [ ] Records grouped by type correctly
- [ ] Correct tag colors per category
- [ ] Sorted by event_date descending
- [ ] Empty data returns empty lists (not errors)
- [ ] All existing tests pass
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
