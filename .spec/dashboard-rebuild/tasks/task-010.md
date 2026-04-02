---
task: 010
feature: dashboard-rebuild
status: pending
depends_on: [9]
---

# Task 010: Frontend — Design System Update + TypeScript Types

## Session Bootstrap
Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Update CSS variables in `globals.css` to match the JSX reference design system. Add all new TypeScript types and API fetch functions for the enriched dashboard, health trends, and records endpoints.

---

## Codebase Context

### Key Code Snippets

```css
/* [Current globals.css :root — from frontend/src/app/globals.css:5-14] */
:root {
  --brand-primary: #D44800;
  --brand-gradient: linear-gradient(135deg, #D44800 0%, #FF9A6C 100%);
  --bg-app: #F7F4F0;
  --status-overdue: #FF3B30;
  --status-upcoming: #FF9500;
  --status-done: #34C759;
  --status-missing: #8E8E93;
  --status-managed: #007AFF;
}
```

```typescript
// [Current DashboardData — from frontend/src/lib/api.ts:230-240]
export interface DashboardData {
  pet: PetProfile;
  owner: OwnerInfo;
  preventive_records: PreventiveRecord[];
  reminders: ReminderItem[];
  documents: DocumentItem[];
  diagnostic_results: DiagnosticResultItem[];
  conditions: ConditionItem[];
  contacts: ContactItem[];
  health_score: HealthScore;
}
```

```typescript
// [Fetch function pattern — from frontend/src/lib/api.ts:405-444]
export async function fetchDashboard(token: string): Promise<DashboardResult> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}`, { cache: "no-store", signal: controller.signal });
    // ...
```

```css
/* [JSX reference CSS variables — from project details/PetDashboard_3103_4.jsx:8-14] */
/* --orange: #FF6B35; --amber: #FF9F1C; --black: #1A1A1A;
   --green: #34C759;  --red: #FF3B30;
   --bg: #F7F4F0; --white: #FFFFFF; --warm: #FDFAF7; --border: #E8E4DF;
   --tg: #F0FFF4; --tr: #FFF0F0; --ta: #FFF6ED; --to: #FFF3EE;
   --t1: #1A1A1A; --t2: #4A4A4A; --t3: #8A8A8A;
   --radius: 16px; --rs: 10px; */
```

### Key Patterns in Use
- **API types in api.ts:** All interfaces colocated, keep existing types intact
- **Fetch with abort controller:** 30s timeout, cache fallback on failure
- **CSS custom properties:** Used throughout components via `var(--name)`

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. **Update `globals.css` :root** — add new variables alongside existing ones:
   - `--orange: #FF6B35`, `--amber: #FF9F1C`, `--black: #1A1A1A`
   - `--green: #34C759`, `--red: #FF3B30`
   - `--bg: #F7F4F0`, `--white: #FFFFFF`, `--warm: #FDFAF7`, `--border: #E8E4DF`
   - Tints: `--tg: #F0FFF4`, `--tr: #FFF0F0`, `--ta: #FFF6ED`, `--to: #FFF3EE`
   - Text: `--t1: #1A1A1A`, `--t2: #4A4A4A`, `--t3: #8A8A8A`
   - Radii: `--radius: 16px`, `--rs: 10px`
   - Keep existing variables for backwards compatibility during transition

2. **Add TypeScript types to `api.ts`:**
   - `VetSummary`, `LifeStageData`, `HealthConditionSummary`
   - `CarePlanV2`, `CarePlanSection`, `CarePlanItem`
   - `DietSummary`, `Recognition`
   - `HealthTrendsV2`, `AskVetData`, `AskVetCondition`, `SignalsData`, `CadenceData`
   - `RecordsV2`, `VetVisit`, `RecordItem`
   - Extend `DashboardData` with new optional fields (for backwards compat during rollout)

3. **Add API fetch functions:**
   - `fetchHealthTrends(token: string)` → `HealthTrendsV2`
   - `fetchRecords(token: string)` → `RecordsV2`
   - Follow existing pattern (abort controller, 30s timeout, error handling)

4. Verify build passes with `npm run build`

_Requirements: 1_

---

## Acceptance Criteria
- [ ] CSS variables match JSX reference exactly
- [ ] All new types compile without errors
- [ ] API fetch functions follow existing pattern
- [ ] Existing components not broken by CSS changes
- [ ] `npm run build` passes
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
