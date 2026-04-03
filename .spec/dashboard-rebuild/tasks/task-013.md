---
task: 013
feature: dashboard-rebuild
status: complete
depends_on: [11]
---

# Task 013: Frontend — Health Trends View (Page 2)

## Session Bootstrap
Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create the Health Trends view with sticky header, 3 scroll-synced tabs (Ask Your Vet, Signals, Care Cadence), and all sub-components. Match JSX reference pixel-for-pixel.

---

## Codebase Context

### Key Code Snippets

```typescript
// [Sticky header + scroll sync — from project details/PetDashboard_3103_4.jsx:782-800]
<div style={{ background: 'var(--bg)', position: 'sticky', top: 0, zIndex: 50 }}>
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
    <button className="back-btn" onClick={onBack}>←</button>
    <span style={{ fontSize: 15, fontWeight: 700 }}>{pet.name}'s Health Trends 🐕</span>
  </div>
  <div style={{ overflowX: 'auto', scrollbarWidth: 'none' }}>
    <div style={{ display: 'flex', gap: 8 }}>
      {TABS.map(t => (
        <button key={t.id} onClick={() => scrollTo(t.id)}
          style={{ background: activeTab === t.id ? 'var(--orange)' : '#fff',
                   color: activeTab === t.id ? '#fff' : 'var(--t2)' }}>
          {t.label}
        </button>
      ))}
    </div>
  </div>
</div>
```

```typescript
// [IntersectionObserver scroll sync — from project details/PetDashboard_3103_4.jsx:752-765]
useEffect(() => {
  const observers = [];
  TABS.forEach(({ id }) => {
    const el = sectionRefs.current[id];
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) setActiveTab(id); },
      { rootMargin: '-40% 0px -55% 0px', threshold: 0 }
    );
    obs.observe(el);
    observers.push(obs);
  });
  return () => observers.forEach(o => o.disconnect());
}, []);
```

```typescript
// [Blood panel data structure — from project details/PetDashboard_3103_4.jsx:168-180]
bloodPanel: {
  label: 'BLOOD PANEL · 10 SEP 2025', labelColor: '#FF3B30',
  headline: 'All markers normal except platelets.',
  rows: [
    { marker: 'Platelets', range: '≥200K/cmm', value: '160K', status: 'Low' },
    { marker: 'Haemoglobin', range: '12–18 g/dl', value: '16.3', status: 'Normal' },
  ],
}
```

```typescript
// [Cadence charts — from project details/PetDashboard_3103_4.jsx:215-258]
// Vaccines: rounds with done/upcoming, gaps between nodes
// Flea/tick: numbered doses with gap coloring
// Deworming: done/missed/now states with severity headlines
```

### Key Patterns in Use
- **Scroll-sync:** IntersectionObserver with rootMargin '-40% 0px -55% 0px'
- **Section scroll margin:** `scrollMarginTop: 130px` for each section
- **Data fetched on navigation:** `fetchHealthTrends(token)` called when view mounts

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. Create `frontend/src/components/trends/HealthTrendsView.tsx`:
   - Sticky header with back button + title + scrollable pill tabs
   - IntersectionObserver scroll-sync per section
   - Fetches `/health-trends-v2` on mount

2. Create `frontend/src/components/trends/AskVetSection.tsx`:
   - Share banner: "🩺 Share this section with Dr. [Vet Name]"
   - Renders AskVetConditionCards

3. Create `frontend/src/components/trends/AskVetConditionCard.tsx`:
   - Condition tag pill, headline, sub-highlight
   - "ASK YOUR VET" header, max 2-3 questions in amber/purple cards
   - Embedded charts (BarChart for pus cells, LineChart for platelets)
   - Timeline swim-lanes (max 5 nodes)

4. Create `frontend/src/components/trends/SignalsSection.tsx` (wrapper)

5. Create `frontend/src/components/trends/BloodPanelTable.tsx`:
   - Header with date, headline, table rows
   - Binary green/red status (no amber)
   - Out-of-range: red on BOTH value and status

6. Create `frontend/src/components/trends/WeightTrendCard.tsx`:
   - LineChart with amber fill, red final point
   - Headline: absolute change + BCS
   - Recommendation box

7. Create `frontend/src/components/trends/MetabolicCard.tsx`:
   - 2x2 green tiles, reassuring headline
   - Appears AFTER blood panel and weight

8. Create `frontend/src/components/trends/CareCadenceSection.tsx` (wrapper)

9. Create cadence charts in `components/charts/`:
   - `VaccinationCadence.tsx` — SVG timeline with round nodes + gap labels
   - `TickFleaCadence.tsx` — SVG dot-plot with color-coded gaps
   - `DewormingCadence.tsx` — SVG timeline with done/missed/now

_Requirements: 12, 13, 14_

---

## Acceptance Criteria
- [ ] Sticky header with scroll-synced pill tabs
- [ ] Ask-vet: share banner, max 2-3 questions per condition
- [ ] Blood panel: binary green/red, out-of-range red on both columns
- [ ] Weight chart: red final point, no "obese" label
- [ ] Metabolic: appears after blood panel + weight, green tiles only
- [ ] Cadence order: vaccines → flea-tick → deworming
- [ ] Scroll sync with rootMargin '-40% 0px -55% 0px'
- [ ] `npm run build` passes
- [ ] `/verify` passes

---

## Handoff — What Was Done

- Added the full Page-2 Health Trends component tree under `frontend/src/components/trends/` with sticky header, orange active pill navigation, scroll-sync, and section wrappers for Ask Your Vet, Signals, and Care Cadence.
- Added three cadence chart wrappers in `frontend/src/components/charts/` to adapt the existing shared SVG primitives to the V2 API payloads.
- Extended `LineChart.tsx` in a backward-compatible way so platelet charts can override dot, stroke, and fill colors while existing weight-chart callers keep the prior default behavior.
- Kept loading and error states inside the trends view shell so back/home navigation remains available even when fetches fail.

## Handoff — Patterns Learned

- The V2 health-trends payload is already available in `frontend/src/lib/api.ts`, so the trends page can stay isolated from the older legacy trends section.
- The existing shared SVG primitives are sufficient for this page when wrapped with small API-shaping adapters instead of creating duplicate chart implementations.
- Build verification on this Windows environment is most reliable when command output is redirected; the completed build surfaced existing repo warnings unrelated to this task.

## Handoff — Files Changed

- `frontend/src/components/charts/LineChart.tsx`
- `frontend/src/components/charts/VaccinationCadence.tsx`
- `frontend/src/components/charts/TickFleaCadence.tsx`
- `frontend/src/components/charts/DewormingCadence.tsx`
- `frontend/src/components/trends/trend-utils.ts`
- `frontend/src/components/trends/HealthTrendsView.tsx`
- `frontend/src/components/trends/AskVetSection.tsx`
- `frontend/src/components/trends/AskVetConditionCard.tsx`
- `frontend/src/components/trends/SignalsSection.tsx`
- `frontend/src/components/trends/BloodPanelTable.tsx`
- `frontend/src/components/trends/WeightTrendCard.tsx`
- `frontend/src/components/trends/MetabolicCard.tsx`
- `frontend/src/components/trends/CareCadenceSection.tsx`

## Handoff — Verification

- `npm run build` completed successfully. The build surfaced existing frontend warnings outside this task, including `img` lint warnings and several admin-panel `react-hooks/exhaustive-deps` warnings.
- `npm run lint` completed without new blocking errors in the changed trends files.
- VS Code diagnostics for the new and modified trends files are clean.
- Code review was run. Remaining reachability work for mounting `HealthTrendsView` into `DashboardClient` belongs to the later navigation/routing task.

## Status

COMPLETE

---

## Handoff to Next Task

**Files changed:** `frontend/src/components/charts/LineChart.tsx`, `frontend/src/components/charts/VaccinationCadence.tsx`, `frontend/src/components/charts/TickFleaCadence.tsx`, `frontend/src/components/charts/DewormingCadence.tsx`, `frontend/src/components/trends/*`
**Decisions made:** Kept Health Trends isolated as a page component and did not mount it into `DashboardClient`, because client view-state replacement is covered by the later routing task.
**Context for next task:** `HealthTrendsView` is ready to plug into the future view-state router; it expects `token`, `petName`, `species`, `vetSummary`, and `onBack` props.
**Open questions:** None for this task; only the planned dashboard routing integration remains.
