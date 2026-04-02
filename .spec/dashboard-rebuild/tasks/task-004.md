---
task: 004
feature: dashboard-rebuild
status: pending
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
- [ ] Primary vet correctly identified by mention count
- [ ] Last visit date derived from most recent document with that vet
- [ ] Tie-breaking works (most recent document wins)
- [ ] None returned when no vet contacts exist
- [ ] All existing tests pass
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
