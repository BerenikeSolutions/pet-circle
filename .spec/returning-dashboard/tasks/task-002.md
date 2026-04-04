---
task: 002
feature: returning-dashboard
status: pending
depends_on: [001]
---

# Task 002: Add `compact` Prop to Analysis Cards

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Add an optional `compact?: boolean` prop to `LifeStageCard`, `HealthConditionsCard`, and `DietAnalysisCard`. When `compact={true}`, each card renders its content without the outer `<div className="card">` wrapper, allowing clean nesting inside `AnalysisSummaryCard`'s `CollapsibleCard`.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```tsx
// [LifeStageCard wrapper — from frontend/src/components/dashboard/LifeStageCard.tsx:12-14, 66-67, 150-151]
interface LifeStageCardProps {
  data: DashboardData;
}
// ...
  return (
    <div className="card" style={{ paddingBottom: 12 }}>
      {/* ... card content ... */}
    </div>
  );
```

```tsx
// [HealthConditionsCard wrapper — from frontend/src/components/dashboard/HealthConditionsCard.tsx:6-9, 22-23, 84-86]
interface HealthConditionsCardProps {
  data: DashboardData;
  onGoToTrends: () => void;
}
// ...
  return (
    <div className="card">
      {/* ... card content ... */}
    </div>
  );
```

```tsx
// [DietAnalysisCard wrapper — from frontend/src/components/dashboard/DietAnalysisCard.tsx:8-10, 23-24, 102-103]
interface DietAnalysisCardProps {
  data: DashboardData;
}
// ...
  return (
    <div className="card">
      {/* ... card content ... */}
    </div>
  );
```

### Key Patterns in Use
- **All 3 cards use `<div className="card">` as their outermost element** — this is the wrapper to conditionally suppress.
- **Props interfaces are defined inline** in each file, not shared.
- **Existing call sites pass no `compact` prop** — default `false` preserves current behavior.

---

## Handoff from Previous Task
> Populated by /task-handoff after task-001 completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. **LifeStageCard.tsx:**
   - Add `compact?: boolean` to `LifeStageCardProps`.
   - Destructure `compact` in the component.
   - Change outer wrapper: `const Wrapper = compact ? "div" : "div"` — when `compact`, use `<div style={{ paddingBottom: 12 }}>` (no `className="card"`); when not compact, keep `<div className="card" style={{ paddingBottom: 12 }}>`.

2. **HealthConditionsCard.tsx:**
   - Add `compact?: boolean` to `HealthConditionsCardProps`.
   - Destructure `compact` in the component.
   - When `compact`, outer wrapper becomes `<div>` (no `className="card"`); otherwise unchanged.

3. **DietAnalysisCard.tsx:**
   - Add `compact?: boolean` to `DietAnalysisCardProps`.
   - Destructure `compact` in the component.
   - When `compact`, outer wrapper becomes `<div>` (no `className="card"`); otherwise unchanged.

_Requirements: 3.3_
_Skills: /code-writing-software-development_

---

## Acceptance Criteria

- [ ] All 3 cards accept optional `compact?: boolean` prop
- [ ] Without `compact` (or `compact={false}`), rendering is identical to current
- [ ] With `compact={true}`, no `.card` class on outer wrapper
- [ ] All existing call sites (DashboardView) are unaffected
- [ ] `npm run build` passes
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
