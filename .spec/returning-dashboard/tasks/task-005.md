---
task: 005
feature: returning-dashboard
status: completed
depends_on: [001]
---

# Task 005: Create `CarePlanTracker.tsx`

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create a care plan status tracker that shows "{petName}'s Care Plan" heading with 3 colored count pills (green "On Track", amber "Due Soon", red "Overdue"). Hidden when all counts are zero.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```tsx
// [NudgeBanner layout pattern — from frontend/src/components/dashboard/NudgeBanner.tsx:14-62]
// CarePlanTracker replaces NudgeBanner in the returning layout.
// Similar card + pill styling, but with 3 pills instead of a single count.
<section
  className="card"
  style={{
    padding: "12px 14px",
    border: "1px solid #FFD5C2",
    background: "linear-gradient(180deg, #FFF6F1 0%, #FFFFFF 100%)",
  }}
>
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
    {/* heading + action */}
  </div>
</section>
```

```typescript
// [Status color constants used across the dashboard]
// Green: #34C759 (used in macroStatus, trait pills)
// Amber: #FF9F1C (used in NOTE_COLOR)
// Red:   #FF3B30 (used in NOTE_COLOR)
```

### Key Patterns in Use
- **`.card` class** for consistent card appearance.
- **Pill styling** follows the `trait-pill` pattern: small rounded pill with background tint and bold text.
- **Conditional render** pattern: `if (count === 0) return null` — used by NudgeBanner.

---

## Handoff from Previous Task
> Populated by /task-handoff after task-004 completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Create `frontend/src/components/dashboard/CarePlanTracker.tsx`.
2. Define props: `petName: string`, `onTrack: number`, `dueSoon: number`, `overdue: number`.
3. Return `null` if `onTrack + dueSoon + overdue === 0`.
4. Render heading: "{petName}'s Care Plan" (bold, `sec-lbl` or similar).
5. Render 3 inline pills in a flex row:
   - Green pill (`background: #E8F9EE`, `color: #1B7A3D`): "{onTrack} On Track"
   - Amber pill (`background: #FFF3E0`, `color: #E65100`): "{dueSoon} Due Soon"
   - Red pill (`background: #FFEBEE`, `color: #C62828`): "{overdue} Overdue"
6. Each pill: `border-radius: 20px`, `padding: 4px 10px`, `fontSize: 11`, `fontWeight: 700`.
7. Only show pills with count > 0 (hide zero-count pills for cleaner look).

_Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
_Skills: /code-writing-software-development_

---

## Acceptance Criteria

- [x] Component renders heading with pet name
- [x] 3 colored pills with correct colors and labels
- [x] Hidden when all counts are zero
- [x] Pills with zero count are hidden
- [x] `npm run build` passes
- [ ] `/verify` passes (tests phase blocked: no `test` script in `frontend/package.json`)

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:**
- `frontend/src/components/dashboard/CarePlanTracker.tsx` (new)
- `.spec/returning-dashboard/tasks/task-005.md` (status + handoff)
- `.claude/CLAUDE.md` (current task pointer)

**Decisions made:**
- Reused the `NudgeBanner` visual container pattern (`.card`, border, gradient) for consistency.
- Applied guard-clause rendering: hide whole component when total count is zero.
- Applied per-pill conditional rendering so zero-count statuses stay hidden.
- Used a semantic `<h3>` for the section title to improve accessibility.

**Context for next task:**
- Task 005 only introduced a standalone component; no integration wiring was done in `DashboardView` yet.
- Build and type-check pass after changes.
- `/verify` full run is partially blocked because `npm run test -- --coverage` fails with "Missing script: test" in frontend.

**Open questions:**
- Should frontend verification standardize on Playwright (`npm run e2e`) instead of `npm run test` for this project?

## Handoff — What Was Done
- Implemented `CarePlanTracker` component with required props, heading, and three status pills.
- Added conditional rendering for total zero and individual zero-count pills.
- Performed build/type/lint checks and documented test-script verification blocker.

## Handoff — Patterns Learned
- Dashboard status summary cards follow `NudgeBanner` spacing and gradient for visual consistency.
- Keep pill styles inline and compact (`borderRadius: 20`, `fontSize: 11`, `fontWeight: 700`) for this layout.

## Handoff — Files Changed
- `frontend/src/components/dashboard/CarePlanTracker.tsx`
- `.spec/returning-dashboard/tasks/task-005.md`
- `.claude/CLAUDE.md`

## Status
COMPLETE
