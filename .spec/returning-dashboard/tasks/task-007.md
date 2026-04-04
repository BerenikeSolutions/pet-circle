---
task: 007
feature: returning-dashboard
status: pending
depends_on: [006]
---

# Task 007: Wire Conditional Rendering in DashboardClient.tsx

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Add the `isReturning` check in `DashboardClient.tsx` to conditionally render `ReturningDashboardView` vs `DashboardView` based on whether the user has uploaded documents.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```tsx
// [Current dashboard case in renderView — from frontend/src/components/DashboardClient.tsx:257-272]
case "dashboard":
  return (
    <DashboardView
      data={data}
      cartCount={cartCount}
      cartTotal={cartTotal}
      getCartQty={getCartQty}
      onGoToReminders={() => setView("reminders")}
      onGoToTrends={() => setView("trends")}
      onGoToRecords={() => setView("records")}
      onGoToNudges={() => setView("nudges")}
      onGoToCart={() => setView("cart")}
      onAddToCart={addToCart}
      nudgeCount={nudgeCount}
    />
  );
```

```tsx
// [Existing imports — from DashboardClient.tsx:11]
import DashboardView from "./dashboard/DashboardView";
```

```tsx
// [DashboardData.documents type — from frontend/src/lib/api.ts:493]
documents: DocumentItem[];
```

### Key Patterns in Use
- **Both views receive identical props** — same `DashboardViewProps` interface.
- **`data.documents`** is always an array (per `DashboardData` type), but guard with `?.length ?? 0` for defensive coding.
- **Import convention**: dashboard components imported from `./dashboard/`.

---

## Handoff from Previous Task
> Populated by /task-handoff after task-006 completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Add import at top of `DashboardClient.tsx`:
   ```tsx
   import ReturningDashboardView from "./dashboard/ReturningDashboardView";
   ```

2. In `renderView()`, modify the `case "dashboard"` block:
   ```tsx
   case "dashboard": {
     const isReturning = (data.documents?.length ?? 0) > 0;
     const ViewComponent = isReturning ? ReturningDashboardView : DashboardView;
     return (
       <ViewComponent
         data={data}
         cartCount={cartCount}
         cartTotal={cartTotal}
         getCartQty={getCartQty}
         onGoToReminders={() => setView("reminders")}
         onGoToTrends={() => setView("trends")}
         onGoToRecords={() => setView("records")}
         onGoToNudges={() => setView("nudges")}
         onGoToCart={() => setView("cart")}
         onAddToCart={addToCart}
         nudgeCount={nudgeCount}
       />
     );
   }
   ```

3. Verify both props interfaces match (ReturningDashboardView imports `DashboardViewProps` from DashboardView).

_Requirements: 1.1, 1.2, 1.3, 8.1, 8.2_
_Skills: /code-writing-software-development_

---

## Acceptance Criteria

- [ ] `ReturningDashboardView` imported in DashboardClient
- [ ] `isReturning` check uses `(data.documents?.length ?? 0) > 0`
- [ ] Pet WITH documents → returning layout renders
- [ ] Pet WITHOUT documents → first-time layout renders (unchanged)
- [ ] Both views receive identical props
- [ ] `npm run build` passes with zero TypeScript errors
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
