---
task: 003
feature: returning-dashboard
status: pending
depends_on: [001]
---

# Task 003: Create `CompactRecordsCard.tsx`

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create a minimal single-row card component that shows "Organized Health Records" with a report count and a "View All" button. This replaces the full RecognitionCard in the returning customer layout.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```tsx
// [RecognitionCard for reference — from frontend/src/components/dashboard/RecognitionCard.tsx:11-69]
// The CompactRecordsCard replaces this in the returning layout.
// It should use the same .card class and similar brand styling.
export default function RecognitionCard({ data, onGoToRecords }: RecognitionCardProps) {
  const bullets = normalizeRecognitionBullets(data).slice(0, 3);
  const reportCount = data.recognition?.report_count ?? data.documents?.length ?? 0;

  return (
    <div className="card">
      <div className="sec-lbl">What We Found</div>
      {/* ... full multi-line content ... */}
    </div>
  );
}
```

```tsx
// [NudgeBanner "View All" button style reference — from frontend/src/components/dashboard/NudgeBanner.tsx:41-57]
<button
  type="button"
  style={{
    border: "none",
    borderRadius: 10,
    padding: "8px 12px",
    fontSize: 12,
    fontWeight: 700,
    color: "#FFFFFF",
    background: "var(--brand-gradient)",
    whiteSpace: "nowrap",
  }}
>
  View All
</button>
```

### Key Patterns in Use
- **`.card` class** provides border-radius, shadow, border, and padding — all dashboard cards use it.
- **Brand gradient** `var(--brand-gradient)` is used for primary action buttons.
- **`sec-lbl` class** is used for section labels inside cards.

---

## Handoff from Previous Task
> Populated by /task-handoff after task-002 completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Create `frontend/src/components/dashboard/CompactRecordsCard.tsx`.
2. Define props: `reportCount: number`, `onGoToRecords: () => void`.
3. Render a single-row `.card` with:
   - Left: "Organized Health Records" text + report count badge
   - Right: "View All" button styled with brand gradient
4. Use `display: flex; align-items: center; justify-content: space-between` for the row layout.
5. Keep padding minimal (`10px 14px`) for negligible vertical space.

_Requirements: 2.1, 2.2, 2.3, 2.4_
_Skills: /code-writing-software-development_

---

## Acceptance Criteria

- [ ] Component renders single-row card with "Organized Health Records" and report count
- [ ] "View All" button calls `onGoToRecords` on click
- [ ] Card takes minimal vertical space (single row)
- [ ] `npm run build` passes
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
