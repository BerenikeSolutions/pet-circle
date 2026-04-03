---
task: 016
feature: dashboard-rebuild
status: complete
depends_on: [10]
---

# Task 016: Frontend — Records View (Page 5)

## Session Bootstrap
Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create the Records view with 4 tab pills (Vet Visits, Lab Reports, Imaging, WhatsApp Channel), collapsible vet visit cards, and record cards. Fetches data from `/records-v2` on navigation.

---

## Codebase Context

### Key Code Snippets

```typescript
// [ViewHeader pattern — from project details/PetDashboard_3103_4.jsx:273-278]
const ViewHeader = ({ title, onBack }) => (
  <div className="vh">
    <button className="back-btn" onClick={onBack}>←</button>
    <span className="vh-title">{title}</span>
  </div>
);
```

```typescript
// [Nav pill styling — from project details/PetDashboard_3103_4.jsx:84-86]
.npill { padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600;
         border: 1.5px solid var(--border); background: var(--white); }
.npill.active { background: var(--black); color: #fff; border-color: var(--black); }
```

### Key Patterns in Use
- **Tab pills:** Scrollable horizontal, active=black bg, inactive=white with border
- **Collapsible cards:** Chevron toggle, latest visit open by default
- **Data fetched on navigation:** `fetchRecords(token)` called when view mounts

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. Create `frontend/src/components/records/RecordsView.tsx`:
   - ViewHeader: "[Name]'s Health Records"
   - Scrollable tab pills: Vet Visits | Lab Reports | Imaging | WhatsApp Channel (THIS ORDER)
   - Active pill: black bg, white text. Inactive: white bg, border
   - Fetch data from `/records-v2` on mount
   - Home floater (black circle, 🏠)

2. Create `frontend/src/components/records/VetVisitCard.tsx`:
   - Collapsible card with chevron toggle
   - Header: icon (40px), title, date, tag pill
   - Expanded: Rx summary (orange bg tile), Medications table (name/dose/duration), Notes
   - Latest visit OPEN by default, rest COLLAPSED

3. Record cards for other tabs:
   - Each: icon + title + date + tag pill + "View →"
   - Tag pill colored by category

_Requirements: 17_

---

## Acceptance Criteria
- [x] 4 tab pills in correct order (Vet Visits | Lab Reports | Imaging | WhatsApp Channel)
- [x] Vet visit cards collapse/expand with chevron
- [x] Latest vet visit open by default
- [x] Rx summary + medications table + notes in expanded view
- [x] Other tabs show record cards with icon, title, date, tag, "View →"
- [x] Home floater navigates to dashboard
- [x] `npm run build` passes
- [ ] `/verify` passes (tests blocked: Playwright global setup requires local backend + valid token)

---

## Handoff — What Was Done
- Implemented a new records page component at `frontend/src/components/records/RecordsView.tsx` with view header, tab pills in required order, records fetch via `fetchRecords(token)` on mount, and a dashboard home floater.
- Implemented collapsible vet-visit cards at `frontend/src/components/records/VetVisitCard.tsx` with latest visit open by default, Rx summary tile, medications table, and notes section.
- Added accessibility semantics requested by review: tablist/tab/tabpanel roles and aria-selected on tabs, plus aria-expanded/aria-controls disclosure wiring on vet-visit collapsibles.

## Handoff — Patterns Learned
- Existing dashboard-rebuild sub-views rely on shared global utility classes (`.vh`, `.npill`, `.floater`) and inline tokenized styles; matching this keeps the view visually consistent without adding new CSS files.
- In this repo, task-scoped sub-view components can be delivered before orchestrator integration; `DashboardClient` routing replacement is explicitly handled later in task 017.
- `/verify` full pass currently depends on local backend availability for Playwright global setup, even when frontend build/types/lint are healthy.

## Handoff — Files Changed
- `frontend/src/components/records/RecordsView.tsx` (new)
- `frontend/src/components/records/VetVisitCard.tsx` (new)
- `.spec/dashboard-rebuild/tasks/task-016.md`

## Status
COMPLETE
