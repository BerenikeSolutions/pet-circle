---
task: 013
feature: dashboard-rebuild
status: pending
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

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
