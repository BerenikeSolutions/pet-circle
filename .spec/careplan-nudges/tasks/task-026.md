---
task: 026
feature: careplan-nudges
status: pending
depends_on: []
---

# Task 026: Frontend — Health Trends Guardrails

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Apply guardrail refinements to Health Trends page: cap vet questions to 2 per condition, enforce signal render order (weight chart last), and enforce care cadence order (vaccination → tick & flea → deworming).

---

## Codebase Context

### Key Code Snippets

```typescript
// [AskVetSection — frontend/src/components/trends/AskVetSection.tsx]
// Currently renders all vet questions per condition — needs .slice(0, 2) cap
// with "1 more question" overflow indicator if truncated.
```

```typescript
// [SignalsSection — frontend/src/components/trends/SignalsSection.tsx]
// Renders blood panel, metabolic, weight charts
// Weight chart should always be last
// CBC/blood chemistry → table format; imaging/urine → concise summary
```

```typescript
// [CareCadenceSection — frontend/src/components/trends/CareCadenceSection.tsx]
// Renders cadence charts
// Order should be: vaccination first, tick & flea second, deworming third
```

### Key Patterns in Use
- **Tab sections:** HealthTrendsView has 3 tabs: Ask Your Vet, Signals, Care Cadence.
- **Condition cards:** Each condition renders a card with questions, charts, timeline.
- **Chart components:** SVG chart components in `components/charts/`.
- **Question tone:** Should be suggestive ("Would it be worth checking...") not prescriptive ("You must do...").

---

## Handoff from Previous Task
> This is an independent task with no prior dependencies.

**Files changed by previous task:** _(none)_
**Decisions made:** _(none)_
**Context for this task:** _(none)_
**Open questions left:** _(none)_

---

## Implementation Steps

### AskVetSection Guardrails

1. **Cap questions to 2 per condition:**
   - Read `AskVetSection.tsx` and locate where questions are rendered per condition.
   - Add `.slice(0, 2)` to the questions array.
   - If original array length > 2, show overflow indicator: "1 more question" (or "{n} more questions").

2. **Verify question tone:**
   - Scan question text for prescriptive language ("You must", "You need to").
   - These come from the backend — if found, note for backend fix. Frontend should not filter.

### SignalsSection Guardrails

3. **Enforce render order:**
   - Read `SignalsSection.tsx` and verify the order of signal cards.
   - Sort signal cards: blood panel → metabolic → weight chart (weight always last).
   - If the sort is data-driven, add explicit ordering logic.

4. **Verify format by type:**
   - CBC/blood chemistry → table format (verify existing).
   - Imaging/urine → concise summary format (verify existing).

### CareCadenceSection Guardrails

5. **Enforce cadence order:**
   - Read `CareCadenceSection.tsx` and verify chart order.
   - Sort cadence charts: vaccination first, tick & flea second, deworming third.
   - Additional cadences (lab tests, vet visits) render after the third.

6. **Verify build:**
   - `cd frontend && npm run build` — zero errors.

---

## Acceptance Criteria
- [ ] Max 2 vet questions per condition with overflow indicator
- [ ] Weight chart renders last in Signals section
- [ ] CBC/blood chemistry uses table format
- [ ] Care Cadence order: vaccination → tick & flea → deworming
- [ ] No prescriptive medication language in questions
- [ ] `npm run build` passes
