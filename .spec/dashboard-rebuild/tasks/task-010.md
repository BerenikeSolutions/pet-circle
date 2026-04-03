---
task: 010
feature: dashboard-rebuild
status: complete
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
- [x] CSS variables match JSX reference exactly
- [x] All new types compile without errors
- [x] API fetch functions follow existing pattern
- [x] Existing components not broken by CSS changes
- [x] `npm run build` passes
- [ ] `/verify` passes (blocked: E2E suite requires running backend/token availability)

---

## Handoff to Next Task

**Files changed:**
- `frontend/src/app/globals.css`
- `frontend/src/lib/api.ts`
- `frontend/src/components/HealthTrendsSection.tsx`

**Decisions made:**
- Preserved backward compatibility by introducing `fetchLegacyHealthTrends` for existing legacy component usage.
- Promoted `fetchHealthTrends` to the new v2 endpoint and added `fetchRecords` for records-v2.
- Extended `DashboardData` with optional v2 fields to avoid rollout breakage.

**Context for next task:**
- New v2 dashboard/trends/records interfaces are available in `api.ts` and can be consumed by rebuilt views.
- Legacy `HealthTrendsSection` now calls `fetchLegacyHealthTrends`; future migration can point it to v2 when UI is replaced.

**Open questions:**
- Should legacy `HealthTrendsSection` be migrated directly to v2 in task-011, or replaced by a new trends view component?

## Handoff — What Was Done
- Added dashboard-rebuild design tokens (`--orange`, `--amber`, tints, text, radii) to `:root` while keeping existing tokens for compatibility.
- Added new enriched interfaces in `api.ts` for dashboard v2 payloads, health trends v2, and records v2.
- Implemented v2 fetchers with AbortController + 30s timeout: `fetchHealthTrends` and `fetchRecords`; kept legacy fetch path for existing UI.

## Handoff — Patterns Learned
- In this codebase, introducing v2 API client contracts is safest when legacy functions are preserved and callsites are switched incrementally.
- Next.js build currently surfaces repo-wide lint warnings unrelated to this task; they do not block build success.
- Full Playwright run depends on backend availability and valid dashboard tokens in local environment.

## Handoff — Files Changed
- `frontend/src/app/globals.css`
- `frontend/src/lib/api.ts`
- `frontend/src/components/HealthTrendsSection.tsx`
- `.spec/dashboard-rebuild/tasks/task-010.md`

## Status
COMPLETE
