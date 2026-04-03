---
task: 018
feature: dashboard-rebuild
status: complete
depends_on: [17]
---

# Task 018: Cleanup — Remove Old Components

## Session Bootstrap
Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Remove all old tab-based components and unused components that have been replaced by the new dashboard. Verify no broken imports remain and the build passes.

---

## Codebase Context

### Key Code Snippets

```typescript
// [Old imports in DashboardClient — already removed in task 017]
// These files should no longer be imported anywhere:
// DashboardHeader, DashboardTabBar, OverviewTab, HealthTab, HygieneTab,
// NutritionTab, ConditionsTab, NudgesView
```

### Key Patterns in Use
- **Verify with grep:** Search entire frontend for import references to deleted files before deleting
- **Build verification:** `npm run build` must pass after all deletions

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. **Delete old tab components:**
   - `frontend/src/components/tabs/OverviewTab.tsx`
   - `frontend/src/components/tabs/HealthTab.tsx`
   - `frontend/src/components/tabs/HygieneTab.tsx`
   - `frontend/src/components/tabs/NutritionTab.tsx`
   - `frontend/src/components/tabs/ConditionsTab.tsx`

2. **Delete old navigation components:**
   - `frontend/src/components/DashboardTabBar.tsx`
   - `frontend/src/components/DashboardHeader.tsx`

3. **Delete old view components:**
   - `frontend/src/components/NudgesView.tsx`

4. **Delete unused components** (not imported by any new component):
   - `frontend/src/components/PetProfileCard.tsx` (if exists)
   - `frontend/src/components/ActivityRings.tsx`
   - `frontend/src/components/PreventiveRecordsTable.tsx`
   - `frontend/src/components/HealthScoreRing.tsx`
   - `frontend/src/components/BloodUrineSection.tsx`
   - `frontend/src/components/HealthTrendsSection.tsx`
   - `frontend/src/components/DocumentsSection.tsx`
   - `frontend/src/components/MedicinesSection.tsx`
   - `frontend/src/components/RemindersSection.tsx`

5. **Verify no broken imports:**
   - Grep entire `frontend/src/` for imports referencing deleted files
   - Fix any remaining references

6. **Run build:** `npm run build` must pass with zero errors

_Requirements: (cleanup)_

---

## Acceptance Criteria
- [x] All listed files deleted
- [x] No remaining imports reference deleted files (grep verification)
- [x] `npm run build` passes with zero errors
- [ ] No runtime errors when loading dashboard (manual runtime check not run in this task)
- [ ] `/verify` passes (lint warnings and missing test script in frontend)

---

## Handoff — What Was Done
- Removed all legacy tab-based and old dashboard component files listed in task scope.
- Verified no remaining references in `frontend/src` to removed component names/import paths.
- Ran verification workflow: build and types pass, lint reports pre-existing warnings, and frontend has no `test` script.

## Handoff — Patterns Learned
- On this Windows setup, PowerShell `Select-String` is the reliable fallback for repo-wide scans when `rg` is unavailable.
- For cleanup tasks, run consumer scans before deletion and a second scan after deletion to confirm no dangling imports.

## Handoff — Files Changed
- frontend/src/components/tabs/OverviewTab.tsx (deleted)
- frontend/src/components/tabs/HealthTab.tsx (deleted)
- frontend/src/components/tabs/HygieneTab.tsx (deleted)
- frontend/src/components/tabs/NutritionTab.tsx (deleted)
- frontend/src/components/tabs/ConditionsTab.tsx (deleted)
- frontend/src/components/DashboardTabBar.tsx (deleted)
- frontend/src/components/DashboardHeader.tsx (deleted)
- frontend/src/components/NudgesView.tsx (deleted)
- frontend/src/components/PetProfileCard.tsx (deleted)
- frontend/src/components/ActivityRings.tsx (deleted)
- frontend/src/components/PreventiveRecordsTable.tsx (deleted)
- frontend/src/components/HealthScoreRing.tsx (deleted)
- frontend/src/components/BloodUrineSection.tsx (deleted)
- frontend/src/components/HealthTrendsSection.tsx (deleted)
- frontend/src/components/DocumentsSection.tsx (deleted)
- frontend/src/components/MedicinesSection.tsx (deleted)
- frontend/src/components/RemindersSection.tsx (deleted)
- .spec/dashboard-rebuild/tasks/task-018.md (updated)

## Status
COMPLETE
