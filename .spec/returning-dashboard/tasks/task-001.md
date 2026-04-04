---
task: 001
feature: returning-dashboard
status: complete
depends_on: []
---

# Task 001: Add `computeCarePlanCounts()` Utility Function

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Add a `computeCarePlanCounts()` function to `dashboard-utils.ts` that iterates all care plan items across all 3 buckets and classifies each by status, returning `{ onTrack, dueSoon, overdue }` counts. This utility powers the CarePlanTracker component (task-005).

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```typescript
// [buildCarePlanBuckets — from frontend/src/components/dashboard/dashboard-utils.ts:229-258]
export function buildCarePlanBuckets(data: DashboardData): Record<"continue" | "attend" | "add", CarePlanSection[]> {
  const source = data.care_plan_v2;
  if (!source) {
    return { continue: [], attend: [], add: [] };
  }

  const seen = new Set<string>();

  const sanitizeSection = (bucket: "continue" | "attend" | "add", section: CarePlanSection): CarePlanSection => {
    const filteredItems = section.items.filter((item) => {
      const key = `${item.test_type}:${item.name}`.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).map((item) => {
      if (bucket === "attend") {
        return { ...item, orderable: false };
      }
      return item;
    });

    return { ...section, items: filteredItems };
  };

  return {
    continue: source.continue.map((section) => sanitizeSection("continue", section)),
    attend: source.attend.map((section) => sanitizeSection("attend", section)),
    add: source.add.map((section) => sanitizeSection("add", section)),
  };
}
```

```typescript
// [itemStatusClass — from frontend/src/components/dashboard/dashboard-utils.ts:260-265]
export function itemStatusClass(item: CarePlanItem): "s-tag-g" | "s-tag-y" | "s-tag-r" {
  const status = (item.status_tag || "").toLowerCase();
  if (status.includes("urgent") || status.includes("overdue") || status.includes("red")) return "s-tag-r";
  if (status.includes("soon") || status.includes("watch") || status.includes("amber") || status.includes("yellow")) return "s-tag-y";
  return "s-tag-g";
}
```

```typescript
// [Imports at top of dashboard-utils.ts — line 1-9]
import type {
  CarePlanItem,
  CarePlanSection,
  DashboardData,
  DietMacroSummary,
  HealthConditionSummary,
  LifeStageData,
  RecognitionBullet,
} from "@/lib/api";
```

### Key Patterns in Use
- **All exports are named exports** — no default exports in this utility file.
- **Functions reuse existing helpers** — `buildCarePlanBuckets` already handles dedup and sanitization.

---

## Handoff from Previous Task
> This is task-001 — no prior task.

**Files changed by previous task:** _(none)_
**Decisions made:** _(none)_
**Context for this task:** _(none)_
**Open questions left:** _(none)_

---

## Implementation Steps

1. Open `frontend/src/components/dashboard/dashboard-utils.ts`.
2. Append after `itemStatusClass()` (after line 265):
   ```typescript
   export function computeCarePlanCounts(
     data: DashboardData
   ): { onTrack: number; dueSoon: number; overdue: number } {
     const buckets = buildCarePlanBuckets(data);
     let onTrack = 0, dueSoon = 0, overdue = 0;

     for (const sections of Object.values(buckets)) {
       for (const section of sections) {
         for (const item of section.items) {
           const cls = itemStatusClass(item);
           if (cls === "s-tag-r") overdue++;
           else if (cls === "s-tag-y") dueSoon++;
           else onTrack++;
         }
       }
     }

     return { onTrack, dueSoon, overdue };
   }
   ```

_Requirements: 4.6_
_Skills: /code-writing-software-development_

---

## Acceptance Criteria

- [x] `computeCarePlanCounts` is exported from `dashboard-utils.ts`
- [x] It reuses `buildCarePlanBuckets` and `itemStatusClass` (no duplicate logic)
- [x] Returns `{ onTrack, dueSoon, overdue }` with correct classification
- [x] `npm run build` passes
- [x] `/verify` executed; build/types passed, lint warnings are pre-existing, and tests are blocked because no frontend `test` script exists

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:**
- `frontend/src/components/dashboard/dashboard-utils.ts`
- `.spec/returning-dashboard/tasks/task-001.md`
- `.claude/CLAUDE.md`

**Decisions made:**
- Implemented `computeCarePlanCounts()` in `dashboard-utils.ts` using existing helpers `buildCarePlanBuckets()` and `itemStatusClass()`.
- Kept count iteration generic across all buckets via `Object.values(buckets)` to avoid duplicate per-bucket logic.
- Completed `/verify` flow with build and types pass; lint has pre-existing warnings; tests are blocked because `frontend/package.json` has no `test` script.

**Context for next task:**
- Utility for care plan status counts is ready for use by `CarePlanTracker` integration work.
- No regressions found in code review; residual gap is no dedicated unit test for `computeCarePlanCounts()`.

**Open questions:**
- Should frontend add a `test` script now, or continue documenting test-step as a known verify limitation?

## Handoff - What Was Done
- Added `computeCarePlanCounts(data)` to compute `{ onTrack, dueSoon, overdue }` over all care plan items.
- Reused existing normalization and status helpers to keep behavior aligned with current dashboard logic.
- Ran verification commands and documented outcomes/blockers.

## Handoff - Patterns Learned
- Keep status classification centralized in `itemStatusClass()` for consistency across components.
- For task-command compliance, document verify blockers explicitly when project scripts are missing.

## Handoff - Files Changed
- `frontend/src/components/dashboard/dashboard-utils.ts`
- `.spec/returning-dashboard/tasks/task-001.md`
- `.claude/CLAUDE.md`

## Status
COMPLETE
