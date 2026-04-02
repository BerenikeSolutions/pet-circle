---
task: 011
feature: dashboard-rebuild
status: pending
depends_on: [10]
---

# Task 011: Frontend — Shared SVG Chart Components

## Session Bootstrap
Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create 5 reusable SVG chart components in `frontend/src/components/charts/` that will be used by the dashboard and health trends views. Match the JSX reference pixel-for-pixel.

---

## Codebase Context

### Key Code Snippets

```typescript
// [Donut from JSX reference — from project details/PetDashboard_3103_4.jsx:280-293]
const Donut = ({ pct, status, size = 80 }) => {
  const sw = 7, r = (size - sw * 2) / 2, circ = 2 * Math.PI * r;
  const fill = circ * (Math.min(pct, 100) / 100), cx = size / 2;
  const color = nutrColor[status] || '#8A8A8A';
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="#E8E4DF" strokeWidth={sw} />
      <circle cx={cx} cy={cx} r={r} fill="none" stroke={color} strokeWidth={sw}
        strokeDasharray={`${fill} ${circ - fill}`} strokeLinecap="round" transform={`rotate(-90 ${cx} ${cx})`} />
      <text x={cx} y={cx - 3} textAnchor="middle" fontSize="11" fontWeight="700" fill="#1A1A1A">{pct}%</text>
      <text x={cx} y={cx + 9} textAnchor="middle" fontSize="9" fill="#8A8A8A">of need</text>
    </svg>
  );
};
```

```typescript
// [Color constants — from project details/PetDashboard_3103_4.jsx:271]
const nutrColor = { green: '#34C759', amber: '#FF9F1C', red: '#FF3B30' };
```

### Key Patterns in Use
- **SVG inline components:** React functional components returning `<svg>` elements
- **Color-coded status:** green/amber/red mapped to hex colors
- **Responsive sizing:** Components accept size props, compute internal geometry

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. Create `frontend/src/components/charts/Donut.tsx`:
   - SVG ring, default 64px, stroke width 7, % center text, "of need" sub-text
   - Color by status: green=#34C759, amber=#FF9F1C, red=#FF3B30
   - Props: `{ pct: number, status: string, size?: number }`

2. Create `frontend/src/components/charts/LineChart.tsx`:
   - Weight trend: N data points, line connecting them
   - Amber gradient fill under line
   - Final data point: RED circle
   - Optional dashed reference line (e.g., 200K for platelets)
   - Props: `{ points, headline?, referenceValue?, referenceLabel? }`

3. Create `frontend/src/components/charts/BarChart.tsx`:
   - Pus cell bars, vertical bars with labels
   - Color by threshold: red (>5 HPF), amber (1-5), green (nil/0)
   - Real dates on X-axis
   - Props: `{ bars: { label, value, display, status }[] }`

4. Create `frontend/src/components/charts/TimelineSVG.tsx`:
   - Horizontal node timeline (vaccination/deworming)
   - Done nodes: solid green circles
   - Upcoming: dashed grey circles
   - Missed: red ✗ dashed
   - Now: amber ! dashed
   - Gap labels between nodes above connecting line
   - Props: `{ nodes, gaps?, legend? }`

5. Create `frontend/src/components/charts/DotPlotSVG.tsx`:
   - Tick/flea dose dot-plot with numbered circles
   - Colors: green (<=6w), amber (7-12w), red (>12w)
   - Critical gap bracket annotations with red text
   - Gap duration labels below non-first dots
   - Props: `{ doses, footer? }`

6. Verify all components render at 430px width. `npm run build` passes.

_Requirements: 7, 13, 14_

---

## Acceptance Criteria
- [ ] All 5 chart components created and render correctly
- [ ] Donut matches JSX reference (stroke width, text position, colors)
- [ ] Line chart has gradient fill + red final point
- [ ] Bar chart uses correct thresholds (>5=red, 1-5=amber, nil=green)
- [ ] Timeline shows done/upcoming/missed/now states correctly
- [ ] Dot-plot shows gap annotations and color-coded doses
- [ ] `npm run build` passes
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
