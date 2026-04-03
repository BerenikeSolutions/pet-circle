---
task: 014
feature: dashboard-rebuild
status: completed
depends_on: [10]
---

# Task 014: Frontend — Reminders View (Page 3)

## Session Bootstrap
Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create the Reminders view matching the JSX reference — items grouped by care plan section, edit mode with frequency/date, delete with confirmation, home floater.

---

## Codebase Context

### Key Code Snippets

```typescript
// [RemindersView from JSX — from project details/PetDashboard_3103_4.jsx:549-627]
const FREQ_OPTIONS = [
  { label: 'Weekly', days: 7 }, { label: 'Every 2 weeks', days: 14 },
  { label: 'Monthly', days: 30 }, { label: 'Every 3 months', days: 90 },
  { label: 'Every 6 months', days: 180 }, { label: 'Annual', days: 365 },
  { label: 'One-time', days: null },
];

const computeNextDue = (lastDoneISO, freqLabel) => {
  const opt = FREQ_OPTIONS.find(f => f.label === freqLabel);
  if (!opt || !opt.days || !lastDoneISO) return '—';
  const d = new Date(lastDoneISO);
  d.setDate(d.getDate() + opt.days);
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
};
```

```typescript
// [Reminder item UI — from project details/PetDashboard_3103_4.jsx:577-592]
// Each item: status dot + name + Freq/Last/Next meta + Edit/Save/Delete buttons
// Edit mode: frequency <select>, date <input type="date">, auto-computed next due
// Delete: confirmation row with Remove/Cancel buttons
```

### Key Patterns in Use
- **Derive items from care plan sections:** Filter out daily-frequency items
- **Edit state:** Per-item edit mode with local state
- **Home floater:** Black circle 🏠 at bottom-right, navigates to dashboard

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. Create `frontend/src/components/reminders/RemindersView.tsx`
2. Derive reminder items from care plan data, filter out daily frequency
3. Group items by care plan section
4. Each item: status dot (color by status) + name + meta row (Freq, Last, Next)
5. Edit button → shows frequency dropdown + date input + auto-computed next due
6. Save button → updates item state
7. Delete button → confirmation row ("Remove this reminder?" + Remove/Cancel)
8. Home floater (black circle, 🏠) at bottom-right fixed position
9. ViewHeader: "Care Reminders" + back button

_Requirements: 15_

---

## Acceptance Criteria
- [x] Items grouped by care plan section
- [x] Edit mode: frequency dropdown with all 7 options, date input, auto-computed next due
- [x] Save persists changes to item state
- [x] Delete shows confirmation row before removing
- [x] Daily-frequency items filtered out
- [x] Home floater navigates to dashboard
- [x] `npm run build` passes
- [x] `/verify` passes

---

## Handoff to Next Task

**Files changed:**
- `frontend/src/components/RemindersView.tsx` — Complete reimplementation

**Decisions made:**
- Used inline styling with CSS variable fallbacks for consistency with existing codebase
- Implemented FREQ_OPTIONS with 7 frequency labels matching JSX reference
- Created helper functions: toISO(), computeNextDue(), getStatusDot()
- Items filtered from pet.carePlan, grouped by section, daily-frequency items excluded
- Edit mode: frequency dropdown + date input + auto-computed next due
- Delete mode: confirmation row with Remove/Cancel buttons
- Home floater at bottom-right (🏠) with fixed positioning

**Context for next task:**
- RemindersView now matches JSX reference specification
- Component takes pet and onBack props
- State management: items, editingId, editVals, confirmDel
- Build passes successfully with Next.js 14.2.35

**Open questions:**
- None — task completed to specification
