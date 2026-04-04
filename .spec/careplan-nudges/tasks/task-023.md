---
task: 023
feature: careplan-nudges
status: complete
depends_on: [022]
---

# Task 023: Frontend — Dashboard Nudge Entry Point

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Add a compact nudge banner to the dashboard that shows the count of undismissed nudges and navigates to NudgesView. The banner renders between HealthConditionsCard and CarePlanCard when nudge count > 0.

---

## Codebase Context

### Key Code Snippets

```typescript
// [DashboardViewProps — from frontend/src/components/dashboard/DashboardView.tsx:14-24]
interface DashboardViewProps {
  data: DashboardData;
  cartCount: number;
  cartTotal: number;
  getCartQty: (item: CarePlanItem, sectionTitle: string) => number;
  onGoToReminders: () => void;
  onGoToTrends: () => void;
  onGoToRecords: () => void;
  onGoToCart: () => void;
  onAddToCart: (item: CarePlanItem, sectionTitle: string) => void;
}
// Needs: onGoToNudges: () => void, nudgeCount: number
```

```typescript
// [Dashboard render order — from DashboardView.tsx:86-112]
<div ref={containerRef}>
  <ProfileBanner data={data} onGoToReminders={onGoToReminders} />
  <RecognitionCard data={data} onGoToRecords={onGoToRecords} />
  <LifeStageCard data={data} />
  <HealthConditionsCard data={data} onGoToTrends={onGoToTrends} />
  {/* NudgeBanner goes HERE — between HealthConditionsCard and DietAnalysisCard */}
  <DietAnalysisCard data={data} />
  <CarePlanCard ... />
  <HealthRecordsNav ... />
  <CartFloater ... />
</div>
```

```typescript
// [API — from frontend/src/lib/api.ts]
// getNudges(token) returns NudgeItem[] — use .filter(n => !n.dismissed).length for count
```

### Key Patterns in Use
- **Props drilling:** DashboardClient passes callbacks (`onGoToReminders`, `onGoToTrends`, etc.) to DashboardView.
- **Count fetching:** Fetch nudges on dashboard load, pass count to DashboardView.
- **Card styling:** All dashboard cards use `className="card"` with consistent padding/margin.

---

## Handoff from Previous Task
> Depends on task-022 (NudgesView must exist for navigation to work).

**Files changed by previous task:** `DashboardClient.tsx` (ViewState includes "nudges"), `NudgesView.tsx` created, `api.ts` updated.
**Decisions made:** NudgesView is lazy-loaded, uses `getNudges(token)` API.
**Context for this task:** Navigation handler `setView("nudges")` is already wired in DashboardClient.

---

## Implementation Steps

1. **Create `frontend/src/components/dashboard/NudgeBanner.tsx`:**
   - Props: `petName: string`, `nudgeCount: number`, `onGoToNudges: () => void`.
   - Render only if `nudgeCount > 0`.
   - Text: "You have {nudgeCount} action item{s} for {petName}".
   - "View All" CTA button in brand orange.
   - Use `card` class styling, compact (less padding than full cards).

2. **Update `DashboardView.tsx`:**
   - Add `onGoToNudges: () => void` and `nudgeCount: number` to `DashboardViewProps`.
   - Import `NudgeBanner`.
   - Render `<NudgeBanner>` between `<HealthConditionsCard>` and `<DietAnalysisCard>`.

3. **Update `DashboardClient.tsx`:**
   - Add `nudgeCount` state: `const [nudgeCount, setNudgeCount] = useState(0);`
   - On dashboard load (after `fetchDashboard` succeeds), also call `getNudges(token)` and count undismissed.
   - Pass `nudgeCount` and `onGoToNudges: () => setView("nudges")` to DashboardView.
   - On return from NudgesView (when view switches back to "dashboard"), refetch nudge count.

4. **Verify build:**
   - `cd frontend && npm run build` — zero errors.

---

## Acceptance Criteria
- [x] Banner visible when nudgeCount > 0
- [x] Banner hidden when nudgeCount = 0
- [x] Banner text shows correct count and pet name
- [x] Tapping "View All" navigates to NudgesView
- [x] Count updates when returning from NudgesView after dismissals
- [x] `npm run build` passes

## Handoff — What Was Done
- Added a new compact nudge entry card component that renders only when undismissed nudge count is greater than zero and supports full-banner tap plus View All CTA navigation.
- Wired dashboard view props to accept and render nudge count + navigation callback between Health Conditions and Diet Analysis cards.
- Updated dashboard client to fetch undismissed nudge count on dashboard load and refresh it when returning from NudgesView.

## Handoff — Patterns Learned
- Keep dashboard-level nudge count fetch non-blocking relative to primary dashboard data to avoid delaying first render.
- For compact dashboard CTAs, reusing the shared card class with minimal inline overrides keeps visual consistency.
- Preserve prior nudge count on transient nudge API failures instead of forcing zero, so action visibility does not flicker away.

## Handoff — Files Changed
- frontend/src/components/dashboard/NudgeBanner.tsx
- frontend/src/components/dashboard/DashboardView.tsx
- frontend/src/components/DashboardClient.tsx
- .spec/careplan-nudges/tasks/task-023.md

## Status
COMPLETE
