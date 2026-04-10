---
task: 004
feature: returning-dashboard
status: complete
depends_on: [002]
---

# Task 004: Create `AnalysisSummaryCard.tsx`

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create a collapsible "Analysis" section that wraps LifeStageCard, HealthConditionsCard, and DietAnalysisCard using the existing `CollapsibleCard` primitive. Collapsed by default. Each inner card uses `compact={true}` to suppress its `.card` wrapper.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```tsx
// [CollapsibleCard — from frontend/src/components/ui/CollapsibleCard.tsx:1-53]
interface CollapsibleCardProps {
  icon?: string;
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  headerBg?: string;
  headerColor?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export default function CollapsibleCard({
  icon, title, subtitle, badge, headerBg, headerColor, defaultOpen = false, children,
}: CollapsibleCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left"
        style={{ backgroundColor: headerBg, color: headerColor }}
      >
        {/* header content + chevron */}
      </button>
      {open && (
        <div className="border-t border-gray-100 animate-slideDown">
          {children}
        </div>
      )}
    </div>
  );
}
```

```tsx
// [How LifeStageCard is called in DashboardView — line 95]
<LifeStageCard data={data} />

// [How HealthConditionsCard is called — line 96]
<HealthConditionsCard data={data} onGoToTrends={onGoToTrends} />

// [How DietAnalysisCard is called — line 98]
<DietAnalysisCard data={data} />
```

### Key Patterns in Use
- **CollapsibleCard** handles its own open/close state — no external state management needed.
- **`defaultOpen={false}`** is the default, but pass it explicitly for clarity.
- **After task-002**, all 3 analysis cards accept `compact?: boolean`.

---

## Handoff from Previous Task
> Populated by /task-handoff after task-003 completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps

1. Create `frontend/src/components/dashboard/AnalysisSummaryCard.tsx`.
2. Define props: `data: DashboardData`, `onGoToTrends: () => void`.
3. Import `CollapsibleCard` from `@/components/ui/CollapsibleCard`.
4. Import `LifeStageCard`, `HealthConditionsCard`, `DietAnalysisCard`.
5. Render:
   ```tsx
   <CollapsibleCard icon="📊" title="Analysis" defaultOpen={false}>
     <div style={{ padding: "0 16px 16px" }}>
       <LifeStageCard data={data} compact />
       <HealthConditionsCard data={data} onGoToTrends={onGoToTrends} compact />
       <DietAnalysisCard data={data} compact />
     </div>
   </CollapsibleCard>
   ```
6. Add spacing between inner cards (e.g., `marginTop` or gap via flex column).

_Requirements: 3.1, 3.2, 3.3, 3.4_
_Skills: /code-writing-software-development_

---

## Acceptance Criteria

- [x] Component renders a `CollapsibleCard` with title "Analysis"
- [x] Collapsed by default (`defaultOpen={false}`)
- [x] Expanding shows LifeStageCard, HealthConditionsCard, DietAnalysisCard in order
- [x] All 3 inner cards use `compact={true}` — no double card borders
- [x] HealthConditionsCard retains `onGoToTrends` navigation
- [x] `npm run build` passes
- [x] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:**
- `frontend/src/components/dashboard/AnalysisSummaryCard.tsx`

**Decisions made:**
- Kept the component as a pure wrapper around `CollapsibleCard` with internal spacing via a flex column `gap`.
- Passed `defaultOpen={false}` explicitly even though it is the primitive default, for clarity against requirement 3.1.

**Context for next task:**
- Analysis cards already support `compact` and are consumed in this new component.
- `npm run build` and `npx tsc --noEmit` pass; lint shows only pre-existing warnings.

**Open questions:**
- `frontend/src/components/dashboard/` is ignored for new files in `.gitignore`; future new files in this folder require `git add -f` until ignore rule is adjusted.

## Handoff — What Was Done
- Implemented `AnalysisSummaryCard` with `CollapsibleCard`, icon "📊", title "Analysis", and `defaultOpen={false}`.
- Added ordered inner rendering of `LifeStageCard`, `HealthConditionsCard`, and `DietAnalysisCard` with `compact` enabled.
- Applied consistent inner spacing so expanded content remains readable without nested `.card` borders.

## Handoff — Patterns Learned
- Existing dashboard analysis cards are already compatible with `compact` rendering for collapsible embedding.
- Verification should be run from `frontend` with `npm.cmd`/`npx.cmd` on this Windows environment.

## Handoff — Files Changed
- `frontend/src/components/dashboard/AnalysisSummaryCard.tsx`
- `.spec/returning-dashboard/tasks/task-004.md`

## Status
COMPLETE
