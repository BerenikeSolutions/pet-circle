---
task: 027
feature: careplan-nudges
status: complete
depends_on: []
---

# Task 027: Frontend — Records View Guardrails

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Apply guardrail refinements to the Records view: verify tab order (Vet Visits, Lab Reports, Imaging, WhatsApp Channel), ensure each record card shows key finding pill + "View" button, implement collapsible vet visit cards (latest expanded, others collapsed), and show medication rows in expanded view.

---

## Codebase Context

### Key Code Snippets

```typescript
// [RecordsView — frontend/src/components/records/RecordsView.tsx]
// Has 4 tabs for different record types
// Tab order should be: Vet Visits, Lab Reports, Imaging, WhatsApp Channel
```

```typescript
// [VetVisitCard — frontend/src/components/records/VetVisitCard.tsx]
// Vet visit cards should be collapsible
// Latest visit expanded by default, others collapsed
// Expanded view: Rx summary, medication rows (name, dose, duration), notes
```

### Key Patterns in Use
- **Tab pattern:** Tabs rendered as horizontal scrollable row, active tab highlighted.
- **CollapsibleCard:** `components/ui/CollapsibleCard.tsx` already exists — reuse for vet visits.
- **Key finding pill:** Small colored badge with summary text (e.g., "Elevated WBC").
- **View button:** Links to the full report detail page or document.

---

## Handoff from Previous Task
> This is an independent task with no prior dependencies.

**Files changed by previous task:** _(none)_
**Decisions made:** _(none)_
**Context for this task:** _(none)_
**Open questions left:** _(none)_

---

## Implementation Steps

1. **Verify tab order in `RecordsView.tsx`:**
   - Read the file and check tab definitions.
   - Ensure order is: Vet Visits, Lab Reports, Imaging, WhatsApp Channel.
   - Fix if order differs.

2. **Verify key finding pills on record cards:**
   - Each record card should show a colored badge with summary text.
   - Check if this already exists; add if missing.

3. **Implement collapsible vet visit cards:**
   - Read `VetVisitCard.tsx` (or equivalent component).
   - Use `CollapsibleCard` UI primitive or implement expand/collapse state.
   - Latest visit (index 0 or most recent date) → expanded by default.
   - All others → collapsed by default.

4. **Expanded vet visit view content:**
   - Show Rx/prescription summary at top.
   - Show medication rows: name, dose, duration in a structured list.
   - Show clinical notes.
   - If a prescription document is linked → show "View Rx" link.

5. **Verify "View" button on all record cards:**
   - Each record card should have a "View" button linking to the full report.
   - Check all 4 tab types.

6. **Verify build:**
   - `cd frontend && npm run build` — zero errors.

---

## Acceptance Criteria
- [x] Tab order: Vet Visits, Lab Reports, Imaging, WhatsApp Channel
- [x] Latest vet visit card expanded by default, others collapsed
- [x] Expanded view shows Rx summary, medication rows, notes
- [x] Link to full Rx document if available
- [x] Key finding pills on all record cards
- [x] "View" button on all record cards
- [x] `npm run build` passes

## Handoff — What Was Done
- Added document View links on all records cards, including collapsed vet visit cards.
- Added key-finding pill support end-to-end (`records-v2` payload + frontend rendering with safe fallback).
- Kept existing collapsible behavior (latest visit expanded by default) and preserved expanded Rx summary, medications, and notes.

## Handoff — Patterns Learned
- `records-v2` supports additive fields safely because the response model uses `dict[str, Any]` for item payloads.
- Frontend verification in this repo should rely on `npm.cmd`/`npx.cmd` task execution on Windows.
- Build can pass with pre-existing warnings; treat warnings separately unless task requires cleanup.

## Handoff — Files Changed
- backend/app/services/records_service.py
- frontend/src/lib/api.ts
- frontend/src/components/records/RecordsView.tsx
- frontend/src/components/records/VetVisitCard.tsx

## Status
COMPLETE
