---
task: 006
feature: returning-dashboard
status: pending
depends_on: [003, 004, 005]
---

# Task 006: Create `ReturningDashboardView.tsx` and Remove HealthRecordsNav

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create the returning customer layout component that composes all new and existing components in the correct order. Also remove HealthRecordsNav from the existing DashboardView (affects all users).

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```tsx
// [DashboardViewProps interface — from frontend/src/components/dashboard/DashboardView.tsx:16-28]
interface DashboardViewProps {
  data: DashboardData;
  cartCount: number;
  cartTotal: number;
  getCartQty: (item: CarePlanItem, sectionTitle: string) => number;
  onGoToReminders: () => void;
  onGoToTrends: () => void;
  onGoToRecords: () => void;
  onGoToNudges: () => void;
  onGoToCart: () => void;
  onAddToCart: (item: CarePlanItem, sectionTitle: string) => void;
  nudgeCount: number;
}
```

```tsx
// [Cart animation logic to duplicate — from DashboardView.tsx:30-89]
function cartItemId(item: CarePlanItem, sectionTitle: string): string {
  return `${sectionTitle}:${item.test_type}:${item.name}`.toLowerCase();
}

// Inside component:
const containerRef = useRef<HTMLDivElement | null>(null);
const [floaterUnlocked, setFloaterUnlocked] = useState(false);
const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});
const timerIdsRef = useRef<number[]>([]);

const buckets = useMemo(() => buildCarePlanBuckets(data), [data]);

useEffect(() => {
  if (floaterUnlocked) return;
  const btn = containerRef.current?.querySelector(".order-btn");
  if (!btn) return;
  const obs = new IntersectionObserver(
    ([entry]) => {
      if (entry.isIntersecting) {
        setFloaterUnlocked(true);
        obs.disconnect();
      }
    },
    { threshold: 0.1 }
  );
  obs.observe(btn);
  return () => obs.disconnect();
}, [floaterUnlocked]);

useEffect(() => {
  return () => {
    timerIdsRef.current.forEach((id) => window.clearTimeout(id));
    timerIdsRef.current = [];
  };
}, []);

const handleAddToCart = (item: CarePlanItem, sectionTitle: string) => {
  const id = cartItemId(item, sectionTitle);
  onAddToCart(item, sectionTitle);
  setAddedIds((prev) => ({ ...prev, [id]: true }));
  const timeoutId = window.setTimeout(() => {
    setAddedIds((prev) => ({ ...prev, [id]: false }));
  }, 1800);
  timerIdsRef.current.push(timeoutId);
};
```

```tsx
// [HealthRecordsNav render to remove — from DashboardView.tsx:110-114]
<HealthRecordsNav
  petName={data.pet.name}
  reportCount={data.recognition?.report_count ?? data.documents?.length ?? 0}
  onGoToRecords={onGoToRecords}
/>
```

```tsx
// [HealthRecordsNav import to remove — from DashboardView.tsx:12]
import HealthRecordsNav from "./HealthRecordsNav";
```

### Key Patterns in Use
- **`DashboardViewProps` must be exported** from DashboardView (or redefined) so ReturningDashboardView can use it.
- **`cartItemId` helper** is defined inside DashboardView — must be duplicated or extracted.
- **Report count fallback**: `data.recognition?.report_count ?? data.documents?.length ?? 0`

---

## Handoff from Previous Task
> Populated by /task-handoff after task-005 completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. **Export `DashboardViewProps` from DashboardView.tsx:**
   - Change `interface DashboardViewProps` to `export interface DashboardViewProps` (line 16).

2. **Create `frontend/src/components/dashboard/ReturningDashboardView.tsx`:**
   - Import `DashboardViewProps` from `./DashboardView`.
   - Import: `ProfileBanner`, `CompactRecordsCard`, `AnalysisSummaryCard`, `CarePlanTracker`, `CarePlanCard`, `CartFloater`.
   - Import `buildCarePlanBuckets`, `computeCarePlanCounts` from `./dashboard-utils`.
   - Duplicate `cartItemId` helper function.
   - Duplicate cart animation logic (containerRef, floaterUnlocked, addedIds, timerIdsRef, IntersectionObserver, handleAddToCart).
   - Compute `reportCount`: `data.recognition?.report_count ?? data.documents?.length ?? 0`.
   - Compute care plan counts via `computeCarePlanCounts(data)`.
   - Render layout order:
     ```
     ProfileBanner
     CompactRecordsCard
     AnalysisSummaryCard
     CarePlanTracker
     CarePlanCard
     CartFloater
     ```

3. **Remove HealthRecordsNav from DashboardView.tsx:**
   - Remove import on line 12.
   - Remove render on lines 110-114.

_Requirements: 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3_
_Skills: /code-writing-software-development_

---

## Acceptance Criteria

- [ ] `ReturningDashboardView` renders correct layout order
- [ ] No NudgeBanner, no RecognitionCard, no HealthRecordsNav in returning layout
- [ ] Cart animation (floater, addedIds flash, timers) works identically
- [ ] `DashboardViewProps` is exported from DashboardView
- [ ] HealthRecordsNav removed from DashboardView (first-time layout)
- [ ] RecognitionCard still provides "View all reports" in first-time layout
- [ ] `npm run build` passes
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
