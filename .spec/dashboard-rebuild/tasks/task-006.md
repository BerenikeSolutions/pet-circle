---
task: 006
feature: dashboard-rebuild
status: pending
depends_on: [1]
---

# Task 006: Extend ai_insights_service.py — Recognition + Care Plan Reasons

## Session Bootstrap
Skills: /python-patterns, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Add two new methods to `backend/app/services/ai_insights_service.py`: `generate_recognition_bullets()` for the "What We Found" card, and `generate_care_plan_reasons()` for orderable item context in the Care Plan card.

---

## Codebase Context

### Key Code Snippets

```python
# [Existing GPT call pattern — from backend/app/services/ai_insights_service.py:87-100]
async def _generate_conditions_summary_gpt(pet_context: str) -> dict:
    client = _get_openai_client()
    system_prompt = "You are a veterinary health assistant..."
    async def _call() -> str:
        response = await client.chat.completions.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or "{}"
    raw = await retry_openai_call(_call)
```

```python
# [Document model — counts for recognition — from backend/app/models/document.py:24-30]
class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pet_id = Column(UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE"))
    extraction_status = Column(String(20), nullable=False)
```

### Key Patterns in Use
- **GPT JSON mode:** `response_format={"type": "json_object"}` with strict system prompts
- **Retry wrapper:** `retry_openai_call(_call)` handles transient failures
- **Graceful fallback:** Always return sensible default on GPT failure

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Add `generate_recognition_bullets(db, pet)` → list[Bullet]:
   - Count documents with `extraction_status='success'` for `report_count`
   - Query conditions (active), preventive_records (on schedule count), diet_items
   - Build max 3 bullets, ordered: conditions first, preventive second, diet last
   - Each bullet: `{ icon, label }` — ONE line, observational tone
   - Use "active health conditions" (not "active conditions")
   - No GPT needed — derive directly from DB counts

2. Add `generate_care_plan_reasons(db, pet, orderable_items)` → dict[str, str]:
   - Build context string: pet's life stage, active conditions, nutrition gaps
   - GPT prompt: "For each orderable item, generate a 1-sentence reason connecting life stage + health + nutrition insights"
   - Output: `{ item_id: reason_text }`
   - Fresh per load (not cached)
   - Fallback: return empty dict if GPT fails (items render without reason)

3. Write tests for bullet ordering, reason generation, fallback behavior

_Requirements: 4, 8, 18_

---

## Acceptance Criteria
- [ ] Recognition bullets max 3, correct order (conditions → preventive → diet)
- [ ] Uses "active health conditions" label
- [ ] Observational tone, no inference or recommendations
- [ ] Care plan reasons generated for all orderable items
- [ ] Graceful fallback if GPT fails (empty dict, no crash)
- [ ] All existing tests pass
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
