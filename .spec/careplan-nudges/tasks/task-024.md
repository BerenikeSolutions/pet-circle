---
task: 024
feature: careplan-nudges
status: complete
depends_on: []
---

# Task 024: Frontend — Dashboard Card Guardrails

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Apply JSX Guardrail rules to existing dashboard cards: (1) sort health conditions by severity+recency, (2) add puppy preventive inclusion, (3) cap trait pills to 2 lines with behavior-first ordering, (4) verify/fix diet analysis thresholds.

---

## Codebase Context

### Key Code Snippets

```typescript
// [HealthConditionsCard — from frontend/src/components/dashboard/HealthConditionsCard.tsx:10-19]
function shouldLimitInsights(items: HealthConditionSummary[]): boolean {
  return !items.some((item) => {
    const label = (item.trend_label || "").toLowerCase();
    return label.includes("active") || label.includes("recurrent") || label.includes("recurring");
  });
}

export default function HealthConditionsCard({ data, onGoToTrends }: HealthConditionsCardProps) {
  const allConditions = normalizeConditions(data);
  const visible = shouldLimitInsights(allConditions) ? allConditions.slice(0, 2) : allConditions;
  // Currently no severity+recency sort applied
```

```typescript
// [LifeStageCard traits — from frontend/src/components/dashboard/LifeStageCard.tsx:44]
const traits = (lifeStage?.traits || []).slice(0, 8);
// No 2-line cap, no behavior-first ordering
```

```typescript
// [DashboardView render order — HealthConditionsCard at line 91]
<HealthConditionsCard data={data} onGoToTrends={onGoToTrends} />
// Puppy preventive gaps not included as pseudo-conditions
```

### Key Patterns in Use
- **`normalizeConditions(data)`:** In `dashboard-utils.ts` — extracts conditions from dashboard data. Currently does NOT sort by severity.
- **`HealthConditionSummary`:** Has `id`, `title`, `trend_label`, `severity`, `first_detected`, `last_detected` fields.
- **Trait pills:** Rendered as small rounded spans. No CSS overflow control currently.
- **`macroStatus()`:** In `DietAnalysisCard.tsx` or `dashboard-utils.ts` — maps nutrient percentages to status colors.

---

## Handoff from Previous Task
> This is an independent task with no prior dependencies.

**Files changed by previous task:** _(none)_
**Decisions made:** _(none)_
**Context for this task:** _(none)_
**Open questions left:** _(none)_

---

## Implementation Steps

### HealthConditionsCard Guardrails

1. **Update `normalizeConditions()` in `dashboard-utils.ts`:**
   - Sort by severity (red/high first) then by recency (`last_detected` or `first_detected`, most recent first).
   - Severity mapping: "critical"/"severe" → 0, "moderate" → 1, "mild" → 2, unknown → 3.

2. **Add puppy preventive inclusion:**
   - Check `data.life_stage?.stage === "puppy"` (or similar field).
   - If puppy: query overdue preventive items from `data.care_plan` and include as pseudo-conditions in the conditions list.
   - Pseudo-condition format: `{ id: "prev_xxx", title: "Deworming overdue", trend_label: "preventive gap", severity: "high" }`.

3. **Ensure no medication recommendations:**
   - Scan condition insight text — if it mentions specific drug names, strip or replace with "ask your vet" phrasing.
   - Replace any "Urgent" text with "High Priority".

### LifeStageCard Guardrails

4. **Cap trait pills to 2 rows:**
   - Add CSS: `maxHeight: "52px"`, `overflow: "hidden"` to the traits container.

5. **Sort traits behavior-first:**
   - Define category order: behavior/energy first → appetite/physiology → clinical.
   - Sort `traits` array before rendering using keyword matching (e.g., "energy", "playful", "anxiety" → behavior; "appetite", "weight" → physiology; "joint", "dental" → clinical).

### DietAnalysisCard Guardrails

6. **Verify `macroStatus()` thresholds:**
   - Read `DietAnalysisCard.tsx` and locate `macroStatus()` or equivalent.
   - Confirm: Calories >100% = amber, ≤100% = green.
   - Confirm: Other macros >110% = amber, <80% = red, 80-110% = green.
   - Fix if thresholds don't match spec.

7. **Verify build:**
   - `cd frontend && npm run build` — zero errors.

---

## Acceptance Criteria
- [x] Conditions sorted by severity (red first) then recency (most recent first)
- [x] Puppy dashboard shows overdue preventive items as pseudo-conditions
- [x] No alarming language ("Urgent" → "High Priority", no specific drug recommendations)
- [x] Trait pills limited to 2 lines (CSS overflow hidden)
- [x] Traits ordered: behavior/energy → appetite/physiology → clinical
- [x] Diet thresholds: calories >100% = amber, others >110% = amber, <80% = red
- [x] `npm run build` passes

## Handoff — What Was Done
- Implemented severity + recency sorting in `normalizeConditions()` and added puppy-only preventive gap pseudo-conditions from `care_plan_v2.attend` when items are truly overdue.
- Added language guardrails for condition text by replacing "Urgent" with "High Priority" and replacing drug/dosage-specific insights with neutral "ask your vet" guidance.
- Added behavior-first trait ordering and strict 2-row trait pill cap in `LifeStageCard`, and aligned `macroStatus()` thresholds to the spec (calories: >100 amber, else green; others: >110 amber, <80 red).

## Handoff — Patterns Learned
- Dashboard condition summaries can carry recency metadata indirectly; fallback recency from `conditions.diagnosed_at/created_at` keeps ordering stable.
- `care_plan_v2.attend` is a reliable source for preventive gap extraction, but overdue filtering must avoid matching "due soon/upcoming".
- Guardrail sanitization should be minimal and targeted to avoid flattening safe, informative clinical text.

## Handoff — Files Changed
- frontend/src/components/dashboard/dashboard-utils.ts
- frontend/src/components/dashboard/LifeStageCard.tsx
- .spec/careplan-nudges/tasks/task-024.md

## Status
COMPLETE
