---
task: 028
feature: careplan-nudges
status: pending
depends_on: [019, 020, 021, 022, 023, 024, 025, 026, 027]
---

# Task 028: Integration Testing and Polish

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify

---

## Objective

End-to-end verification of all careplan-nudges changes. Run builds, run tests, verify all acceptance criteria from tasks 019-027, and fix any regressions or edge cases.

---

## Codebase Context

This task depends on ALL previous tasks (019-027) being complete. It is a verification and polish pass, not a feature implementation.

### What to Verify

**Backend (tasks 019-021):**
- Nudge scheduler 7-day cap blocks when 2 nudges in window
- Inactivity trigger fires for 72hr-silent users
- No nudge sent on same day as reminder (sent or scheduled)
- Skip reasons logged
- Care plan food items show correct `cta_label` and `status_tag`
- Reminder templates resolve for all 44 category×stage combos
- Chronic medicines get reminders, course medicines don't
- Send rules enforced

**Frontend (tasks 022-027):**
- NudgesView renders grouped nudges, dismiss works, cart integration works
- Dashboard nudge banner shows count, navigates, updates on return
- Conditions sorted by severity+recency
- Puppy dashboard shows preventive gaps
- Trait pills 2-line cap, behavior-first
- Diet thresholds match spec
- CarePlan food items show "Order Now"/"Reorder"/"Due Soon"
- Vet questions capped at 2 per condition
- Weight chart last in Signals
- Cadence order: vaccination → flea → deworming
- Records tab order correct, vet visits collapsible

---

## Handoff from Previous Task
> All 9 prior tasks must be complete.

---

## Implementation Steps

1. **Run frontend build:**
   ```bash
   cd frontend && npm run build
   ```
   - Fix any TypeScript errors or build failures.

2. **Run backend tests:**
   ```bash
   cd backend && python -m pytest
   ```
   - Fix any test failures.

3. **Verify backend functionality:**
   - Review nudge_scheduler.py guards manually.
   - Review care_plan_engine.py food/supplement CTA logic.
   - Review reminder_templates.py template coverage.

4. **Verify frontend at 430px viewport:**
   - Check all dashboard cards render correctly.
   - Check NudgesView renders all categories.
   - Check dismiss and cart flows.
   - Check all guardrail rules visually correct.

5. **Fix regressions:**
   - Address any type errors, visual inconsistencies, or edge cases found.

6. **Final verification:**
   - `npm run build` — zero errors.
   - `python -m pytest` — all tests pass.
   - All AC from tasks 019-027 confirmed.

---

## Acceptance Criteria
- [ ] `npm run build` — zero errors
- [ ] `python -m pytest` — all tests pass
- [ ] All acceptance criteria from tasks 019-027 verified
- [ ] No visual regressions at 430px viewport
- [ ] No type errors
