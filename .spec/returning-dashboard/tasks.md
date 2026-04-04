# Implementation Plan: Returning Customer Dashboard

- [ ] 1. Add `computeCarePlanCounts()` utility function
  - Append `computeCarePlanCounts(data: DashboardData)` to `frontend/src/components/dashboard/dashboard-utils.ts` after `itemStatusClass()` (line 265).
  - Iterate all items across all 3 buckets from `buildCarePlanBuckets()`, classify each via `itemStatusClass()`, return `{ onTrack, dueSoon, overdue }`.
  - _Requirements: 4.6_
  - _Skills: /code-writing-software-development_
  - **AC:** Function exported. `npm run build` passes. Counts match manual inspection of care plan items.

- [ ] 2. Add `compact` prop to LifeStageCard, HealthConditionsCard, DietAnalysisCard
  - Add `compact?: boolean` to each card's props interface (defaults to `false`).
  - When `compact={true}`, render content without the outer `<div className="card">` wrapper — use a fragment or plain `<div>` without the card class.
  - Existing call sites pass no `compact` prop, so behavior is unchanged.
  - **Files:**
    - `frontend/src/components/dashboard/LifeStageCard.tsx`
    - `frontend/src/components/dashboard/HealthConditionsCard.tsx`
    - `frontend/src/components/dashboard/DietAnalysisCard.tsx`
  - _Requirements: 3.3_
  - _Skills: /code-writing-software-development_
  - **AC:** All 3 cards accept `compact` prop. Without it, rendering is identical to current. With `compact={true}`, no `.card` wrapper. `npm run build` passes.

- [ ] 3. Create `CompactRecordsCard.tsx`
  - New file: `frontend/src/components/dashboard/CompactRecordsCard.tsx`
  - Single-row card: left "Organized Health Records" + report count, right "View All" button.
  - Props: `reportCount: number`, `onGoToRecords: () => void`.
  - ~25 lines. Uses `.card` class, minimal padding.
  - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - _Skills: /code-writing-software-development_
  - **AC:** Component renders single-row card. "View All" calls `onGoToRecords`. `npm run build` passes.

- [ ] 4. Create `AnalysisSummaryCard.tsx`
  - New file: `frontend/src/components/dashboard/AnalysisSummaryCard.tsx`
  - Uses `CollapsibleCard` with title "Analysis", `defaultOpen={false}`.
  - Renders `LifeStageCard`, `HealthConditionsCard`, `DietAnalysisCard` inside with `compact={true}`.
  - Props: `data: DashboardData`, `onGoToTrends: () => void`.
  - ~25 lines.
  - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - _Skills: /code-writing-software-development_
  - **AC:** Collapsed by default. Expands on tap. 3 cards render without double card borders. `npm run build` passes.

- [ ] 5. Create `CarePlanTracker.tsx`
  - New file: `frontend/src/components/dashboard/CarePlanTracker.tsx`
  - Heading: "{petName}'s Care Plan" + 3 colored inline pills.
  - Props: `petName: string`, `onTrack: number`, `dueSoon: number`, `overdue: number`.
  - Hidden if all counts are zero.
  - ~40 lines.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  - _Skills: /code-writing-software-development_
  - **AC:** Renders 3 pills with correct colors. Hidden when all zero. `npm run build` passes.

- [ ] 6. Create `ReturningDashboardView.tsx` and remove HealthRecordsNav from DashboardView
  - New file: `frontend/src/components/dashboard/ReturningDashboardView.tsx`
  - Same props as `DashboardViewProps` (export the interface from DashboardView or co-locate).
  - Layout: ProfileBanner → CompactRecordsCard → AnalysisSummaryCard → CarePlanTracker → CarePlanCard → CartFloater.
  - Duplicate cart animation logic (IntersectionObserver, addedIds, timerIds) from DashboardView.
  - Compute `reportCount` and care plan counts in this component.
  - Remove `HealthRecordsNav` import and render from `DashboardView.tsx` (lines 12, 110-114).
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3_
  - _Skills: /code-writing-software-development_
  - **AC:** ReturningDashboardView renders correct layout order. No NudgeBanner, no RecognitionCard, no HealthRecordsNav. Cart works. DashboardView no longer renders HealthRecordsNav. `npm run build` passes.

- [ ] 7. Wire up conditional rendering in DashboardClient.tsx
  - Import `ReturningDashboardView`.
  - In `renderView()` case `"dashboard"`: check `(data.documents?.length ?? 0) > 0`.
  - If true → `<ReturningDashboardView ...props />`. If false → `<DashboardView ...props />`.
  - Both receive identical props.
  - _Requirements: 1.1, 1.2, 1.3, 8.1, 8.2_
  - _Skills: /code-writing-software-development_
  - **AC:** Pet with documents → returning layout. Pet without documents → first-time layout. `npm run build` passes with zero errors.
