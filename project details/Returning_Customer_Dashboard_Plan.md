# Returning Customer Dashboard Redesign

## Context
Stakeholder Anu requested a streamlined dashboard for returning customers. The current layout shows 8 full-size cards sequentially. Returning customers (those with uploaded documents) should see a compact view: shrunk health records card, collapsed analysis section, a care plan status tracker, and no duplicate health records nav.

First-time customers keep the current layout unchanged.

## New Layout (top → bottom)
1. **ProfileBanner** — no change
2. **CompactRecordsCard** — single row: "Organized Health Records" + "View All →" button (navigates to Records view)
3. **AnalysisSummaryCard** — CollapsibleCard wrapping LifeStageCard + HealthConditionsCard + DietAnalysisCard (collapsed by default)
4. **CarePlanTracker** — "{petName}'s Care Plan" with 3 count pills: green "X On Track", amber "Y Due Soon", red "Z Overdue"
5. **CarePlanCard** — existing 3-bucket card (labels unchanged: Continue / Attend to / Quick Fixes to Add)
6. **CartFloater** — existing floating cart button
7. ~~HealthRecordsNav~~ — **removed for ALL customers** (duplicate — RecognitionCard already links to Records)
8. ~~NudgeBanner~~ — **replaced** by CarePlanTracker (returning only)

## Implementation Steps

### Step 1: Add `computeCarePlanCounts()` to dashboard-utils.ts
- New function that iterates all items across all 3 care plan buckets
- Uses existing `itemStatusClass()` to classify: `s-tag-r` → overdue, `s-tag-y` → dueSoon, else → onTrack
- Returns `{ onTrack: number, dueSoon: number, overdue: number }`
- **File:** `frontend/src/components/dashboard/dashboard-utils.ts` — append after line 265

### Step 2: Create `CompactRecordsCard.tsx`
- Compact single-row card: left side shows "Organized Health Records" with report count, right side shows "View All" button
- Props: `reportCount: number`, `onGoToRecords: () => void`
- ~25 lines
- **File:** new `frontend/src/components/dashboard/CompactRecordsCard.tsx`

### Step 3: Create `AnalysisSummaryCard.tsx`
- Uses existing `CollapsibleCard` UI primitive (defaultOpen=false)
- Wraps `LifeStageCard`, `HealthConditionsCard`, `DietAnalysisCard` inside
- Add `compact?: boolean` prop to those 3 cards to suppress outer `.card` wrapper when rendered inside the collapsible
- Props: `data: DashboardData`, `onGoToTrends: () => void`
- **Files:**
  - New `frontend/src/components/dashboard/AnalysisSummaryCard.tsx`
  - Modify `frontend/src/components/dashboard/LifeStageCard.tsx` — add optional `compact` prop
  - Modify `frontend/src/components/dashboard/HealthConditionsCard.tsx` — add optional `compact` prop
  - Modify `frontend/src/components/dashboard/DietAnalysisCard.tsx` — add optional `compact` prop

### Step 4: Create `CarePlanTracker.tsx`
- Displays "{petName}'s Care Plan" heading + 3 colored count pills in a row
- Green pill: "X On Track", Amber pill: "Y Due Soon", Red pill: "Z Overdue"
- Hidden if all counts are zero
- Props: `petName: string`, `onTrack: number`, `dueSoon: number`, `overdue: number`
- ~40 lines
- **File:** new `frontend/src/components/dashboard/CarePlanTracker.tsx`

### Step 5: Create `ReturningDashboardView.tsx`
- Same props interface as `DashboardView` (`DashboardViewProps`)
- Layout: ProfileBanner → CompactRecordsCard → AnalysisSummaryCard → CarePlanTracker → CarePlanCard → CartFloater
- Reuses the same cart animation logic (IntersectionObserver, addedIds, timerIds) — either duplicate the ~30 lines or extract a shared hook
- **File:** new `frontend/src/components/dashboard/ReturningDashboardView.tsx`

### Step 6: Remove HealthRecordsNav from DashboardView.tsx
- Remove the `<HealthRecordsNav>` render and its import from the existing `DashboardView` (affects first-time customers too — it's a duplicate)
- **File:** `frontend/src/components/dashboard/DashboardView.tsx` — remove lines 110-114 and the import

### Step 7: Wire up in DashboardClient.tsx
- Add `isReturning` check: `(data.documents?.length ?? 0) > 0`
- Conditionally render `ReturningDashboardView` vs `DashboardView`
- **File:** `frontend/src/components/DashboardClient.tsx` — modify the "dashboard" case in view rendering

## Files Summary

| File | Action |
|------|--------|
| `frontend/src/components/dashboard/dashboard-utils.ts` | Add `computeCarePlanCounts()` |
| `frontend/src/components/dashboard/CompactRecordsCard.tsx` | **New** ~25 lines |
| `frontend/src/components/dashboard/AnalysisSummaryCard.tsx` | **New** ~25 lines |
| `frontend/src/components/dashboard/CarePlanTracker.tsx` | **New** ~40 lines |
| `frontend/src/components/dashboard/ReturningDashboardView.tsx` | **New** ~70 lines |
| `frontend/src/components/dashboard/LifeStageCard.tsx` | Add `compact` prop |
| `frontend/src/components/dashboard/HealthConditionsCard.tsx` | Add `compact` prop |
| `frontend/src/components/dashboard/DietAnalysisCard.tsx` | Add `compact` prop |
| `frontend/src/components/dashboard/DashboardView.tsx` | Remove HealthRecordsNav |
| `frontend/src/components/DashboardClient.tsx` | Add isReturning conditional |

## Reuse
- `CollapsibleCard` from `components/ui/` — for Analysis section
- `itemStatusClass()` from `dashboard-utils.ts` — for tracker count classification
- `buildCarePlanBuckets()` from `dashboard-utils.ts` — same bucket building
- `BUCKET_META` — unchanged labels
- Existing `ProfileBanner`, `CarePlanCard`, `CartFloater` — used as-is

## Verification
1. `npm run build` — confirm no TypeScript/build errors
2. Open dashboard with a token for a pet WITH documents → should see compact returning layout
3. Open dashboard with a token for a pet WITHOUT documents → should see original layout unchanged
4. Click "View All" on Organized Health Records → navigates to Records view
5. Click Analysis chevron → expands to show LifeStage + HealthConditions + DietAnalysis cards
6. Verify tracker counts match the status tags in the care plan items below
7. Cart functionality (add to cart, floater) works identically in both views
