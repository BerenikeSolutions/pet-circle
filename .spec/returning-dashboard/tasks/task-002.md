---
task: 002
feature: returning-dashboard
status: complete
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

- [x] All 3 cards accept optional `compact?: boolean` prop
- [x] Without `compact` (or `compact={false}`), rendering is identical to current
- [x] With `compact={true}`, no `.card` class on outer wrapper
- [x] All existing call sites (DashboardView) are unaffected
- [x] `npm run build` passes
- [x] `/verify` executed; build/types passed, lint warnings are pre-existing, tests are blocked because no frontend `test` script exists

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:**
- `frontend/src/components/dashboard/LifeStageCard.tsx`
- `frontend/src/components/dashboard/HealthConditionsCard.tsx`
- `frontend/src/components/dashboard/DietAnalysisCard.tsx`
- `.spec/returning-dashboard/tasks/task-002.md`
- `.claude/CLAUDE.md`

**Decisions made:**
- Confirmed the compact wrapper behavior was already present in the three analysis cards and aligned with task-002 requirements.
- Verified default rendering parity by keeping `compact` optional with default `false`.
- Ran `/verify` command-equivalent checks in required order and documented known blockers/noise.

**Context for next task:**
- Analysis cards are ready for nested usage in `AnalysisSummaryCard` without double card borders via `compact={true}`.
- Verify status for this repo/frontend: build and types pass; lint returns existing warnings; tests are currently unavailable (`npm run test` missing script).

**Open questions:**
- Should frontend add a `test` script now, or continue documenting test-step as a known verify limitation?

## Handoff - What Was Done
- Completed task-002 validation for compact-mode support across `LifeStageCard`, `HealthConditionsCard`, and `DietAnalysisCard`.
- Confirmed default behavior remains unchanged when `compact` is not passed.
- Executed `/verify` flow and captured results/blockers for the next task.

## Handoff - Patterns Learned
- For wrapper suppression, using `className={compact ? undefined : "card"}` preserves markup with minimal risk.
- In this repo, `/verify` should still be run fully even when `npm run test` is unavailable; document blocker explicitly.

## Handoff - Files Changed
- `frontend/src/components/dashboard/LifeStageCard.tsx`
- `frontend/src/components/dashboard/HealthConditionsCard.tsx`
- `frontend/src/components/dashboard/DietAnalysisCard.tsx`
- `.spec/returning-dashboard/tasks/task-002.md`
- `.claude/CLAUDE.md`

## Status
COMPLETE
