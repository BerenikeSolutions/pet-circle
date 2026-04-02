---
task: 004
feature: dashboard-rebuild
status: complete
depends_on: [1]
---

# Task 004: Vet Summary Service

## Session Bootstrap
Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create `backend/app/services/vet_summary_service.py` that identifies the primary vet (most-mentioned across reports) from care contacts and returns name + last visit date.

---

## Codebase Context

### Key Code Snippets

```python
# [Contact model — from backend/app/models/contact.py:25-50]
class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("pet_id", "name", "role", name="uq_contacts_pet_name_role"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"), index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), index=True)
    role = Column(String(30), nullable=False, default="veterinarian")
    name = Column(String(200), nullable=False)
    clinic_name = Column(String(200), nullable=True)
    source = Column(String(20), nullable=False, default="extraction")
    pet = relationship("Pet", back_populates="contacts")
    document = relationship("Document")
```

```python
# [Document model event_date — from backend/app/models/document.py:85-88]
event_date = Column(Date, nullable=True)
```

### Key Patterns in Use
- **Contacts are extracted from documents:** Each contact has a `document_id` linking it to the source doc
- **Multiple vets per pet:** Same vet may appear in multiple documents
- **Primary vet = most mentions:** Count how many documents reference each vet name

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Create `backend/app/services/vet_summary_service.py`
2. Implement `get_vet_summary(db, pet_id)` → VetSummary | None:
   - Query contacts WHERE `pet_id=pet_id` AND `role='veterinarian'`
   - Group by vet `name`, count distinct `document_id` references per vet
   - Select vet with max count (tie-break by most recent document event_date)
   - Derive `last_visit` from the most recent document event_date for that vet
   - Return `{ name, last_visit }` or `None` if no vet contacts exist
3. Write unit tests for: single vet, multiple vets (picks most mentioned), tie-breaking, no contacts

_Requirements: 3, 18_

---

## Acceptance Criteria
- [x] Primary vet correctly identified by mention count
- [x] Last visit date derived from most recent document with that vet
- [x] Tie-breaking works (most recent document wins)
- [x] None returned when no vet contacts exist
- [x] All existing tests pass
- [x] `/verify` passes

---

## Handoff to Next Task

**Files changed:**
- `backend/app/services/vet_summary_service.py` — new service; exports `VetSummary` dataclass and `get_vet_summary(db, pet_id)` function.
- `backend/tests/unit/test_vet_summary_service.py` — 6 unit tests covering all acceptance-criteria scenarios.

**Decisions made:**
- Used a single aggregating SQLAlchemy query (`GROUP BY name`, `COUNT(DISTINCT document_id)`, `MAX(event_date)`) rather than Python-side grouping; the DB does the heavy lifting.
- `LEFT JOIN` documents so that contacts whose linked document was soft-deleted (SET NULL) still count as mentions.
- `NULLSLAST` on the tie-break `ORDER BY` so vets without any event dates are deprioritised but still returned when they are the only candidate.
- `@dataclass` used for `VetSummary` (consistent with existing services like `LifeStageData`).

**Context for next task:**
- `get_vet_summary(db, pet_id)` is ready to be called from the dashboard service or any dashboard API endpoint that needs primary-vet information.
- Import: `from app.services.vet_summary_service import VetSummary, get_vet_summary`

**Open questions:** None.
