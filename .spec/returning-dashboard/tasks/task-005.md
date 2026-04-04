---
task: 005
feature: returning-dashboard
status: pending
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

- [ ] Component renders heading with pet name
- [ ] 3 colored pills with correct colors and labels
- [ ] Hidden when all counts are zero
- [ ] Pills with zero count are hidden
- [ ] `npm run build` passes
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
