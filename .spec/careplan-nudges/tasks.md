# Implementation Plan: Care Plan & Nudges Enhancement

- [ ] 1. (task-019) Backend — Nudge Scheduler Global Communication Rules
  - Add `_count_nudges_in_window()` guard to `nudge_scheduler.py` — query `nudge_delivery_log` for sends in rolling 7-day window per user, skip if >= `NUDGE_MAX_PER_WEEK`.
  - Add `_has_reminder_scheduled_today()` guard — query `reminders` table for pending/sent reminders on today's date for user's pets, skip if found.
  - Add `_check_inactivity_trigger()` — query `message_logs` for last user activity timestamp, return True if > 72hr silence.
  - Integrate inactivity trigger into main loop: if O+N schedule says "not today" but inactivity is True and all guards pass, select next undelivered slot message.
  - Add `NUDGE_MAX_PER_WEEK = 2` and `NUDGE_INACTIVITY_TRIGGER_HOURS = 72` to `core/constants.py`.
  - Log skip reason for each blocked nudge.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_
  - _Skills: /code-writing-software-development, /python-patterns_
  - **AC:** 7-day cap blocks when 2 nudges exist in window. Inactivity trigger fires for 72hr-silent users. No nudge sent on same day as reminder. Skip reasons logged. Unit tests pass.

- [ ] 2. (task-020) Backend — Care Plan "Due Soon" Tag for Food/Supplements
  - In `care_plan_engine.py` orderable food/supplement block (~line 881), query `orders` table for pet's order history matching the diet item.
  - If prior order exists: set `cta_label: "Reorder"`. If no prior order: `cta_label: "Order Now"`.
  - If prior order exists and estimated supply <= 7 days remaining: set `status_tag: "Due Soon"`. Otherwise keep `"Active"`.
  - Wrap order query in try/except — fallback to existing behavior on failure.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  - _Skills: /code-writing-software-development, /python-patterns_
  - **AC:** Food items with no order history return `cta_label: "Order Now"`, `status_tag: "Active"`. Items with prior order return `cta_label: "Reorder"`. Items with low supply return `status_tag: "Due Soon"`. Existing tests still pass.

- [ ] 3. (task-021) Backend — WhatsApp Reminder Message Templates
  - Create `backend/app/services/reminder_templates.py` with `ReminderTemplate` dataclass and `REMINDER_TEMPLATES` registry dict keyed by `(category, sub_type, stage)`.
  - Populate all 44 templates (11 categories x 4 stages) with exact wording from Nudges Excel Reminders sheet.
  - Implement `get_reminder_template()` lookup and `substitute_variables()` for `[Name]`, `[Pet]`, `[breed]`, `[date]`, `[vaccineList]`, `[Brand]`, `[Supplement]`, `[Medicine]`, `[condition]`, `[vetName]`, `[testName]`, `[X]`, `[breedSpecificConsequence]`, `[snoozeDate]`.
  - Update `_build_template_params()` in `reminder_engine.py` to try category-specific template first, fall back to generic.
  - Add helper `_build_variable_dict()` to assemble substitution variables from `ReminderCandidate` + DB lookups.
  - Implement send rule constants: max 1/day/pet, 3-day min gap, 3-ignored → monthly, hygiene at 10am due-only, standard T-7/D+3 at 9am, due at 10am.
  - Add chronic vs course medicine distinction: chronic → T-7/Due/D+3 refill reminders, course → no reminders (log end date only).
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 6.1, 6.2, 6.3, 6.4, 6.5_
  - _Skills: /code-writing-software-development, /python-patterns_
  - **AC:** All 44 templates defined with correct wording. `get_reminder_template()` returns correct template for each (category, sub_type, stage) combo. `substitute_variables()` replaces all placeholders. `_build_template_params()` prefers category-specific template over generic. Send rules enforced. Chronic/course distinction works. Unit tests for template lookup and substitution pass.

- [ ] 4. (task-022) Frontend — NudgesView Component
  - Create `frontend/src/components/nudges/NudgesView.tsx` — main view with ViewHeader, category-grouped nudge list, loading/empty states, home floater.
  - Create `frontend/src/components/nudges/NudgeCard.tsx` — icon + title + priority badge, message body (expandable), dismiss button with confirmation, "Order Now" CTA for orderable nudges.
  - Add `"nudges"` to ViewState union in `DashboardClient.tsx`.
  - Add NudgesView render case in DashboardClient's view switch.
  - Add optional `cta_label?: string` to `CarePlanItem` interface in `lib/api.ts`.
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_
  - _Skills: /code-writing-software-development_
  - **AC:** NudgesView renders grouped nudges. Dismiss flow calls API and removes card. Orderable nudges add to cart with 1.8s feedback. Empty/loading states work. Navigation to/from nudges works. `npm run build` passes.

- [ ] 5. (task-023) Frontend — Dashboard Nudge Entry Point
  - Create `frontend/src/components/dashboard/NudgeBanner.tsx` — compact banner showing nudge count with "View All" CTA.
  - Add `onGoToNudges` and `nudgeCount` props to `DashboardView.tsx`.
  - Render NudgeBanner between HealthConditionsCard and CarePlanCard.
  - In `DashboardClient.tsx`, fetch nudge count on dashboard load via `getNudges(token)`, pass count to DashboardView.
  - On return from NudgesView, refetch nudge count to update banner.
  - _Requirements: 8.1, 8.2, 8.3, 8.4_
  - _Skills: /code-writing-software-development_
  - **AC:** Banner shows when nudgeCount > 0. Banner hidden when 0. Tapping navigates to NudgesView. Count updates after dismissals. `npm run build` passes.

- [ ] 6. (task-024) Frontend — Dashboard Card Guardrails
  - **HealthConditionsCard.tsx:** Sort conditions by severity (red first) then recency. Add puppy preventive inclusion logic. Replace "Urgent" with "High Priority". Block medication recommendations in insights.
  - **dashboard-utils.ts:** Update `normalizeConditions()` to sort by severity+recency. Add `isPuppy()` helper.
  - **LifeStageCard.tsx:** Cap trait pills to 2 rows (`maxHeight: "52px"`, `overflow: "hidden"`). Sort traits: behavior/energy → appetite/physiology → clinical.
  - **DietAnalysisCard.tsx:** Verify `macroStatus()` thresholds match spec (calories >100% = amber, others >110% = amber, <80% = red). Fix if needed.
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 10.1, 10.2, 10.3, 10.4, 15.1, 15.2, 15.3_
  - _Skills: /code-writing-software-development_
  - **AC:** Conditions sorted by severity+recency. Puppy dashboard shows preventive gaps. Traits limited to 2 lines, behavior-first. Diet thresholds match spec. No alarming language. `npm run build` passes.

- [ ] 7. (task-025) Frontend — CarePlan Food/Supplement CTA Enhancements
  - In `CarePlanCard.tsx`, read `item.cta_label` for button text (default "Order Now").
  - Render amber `s-tag-y` badge when `item.status_tag === "Due Soon"`.
  - Ensure food/supplement rows in Continue bucket match Vaccines & Preventive Care row styling (visual parity).
  - Ensure "reason" field builds connectivity with health/nutrition insights shown above.
  - _Requirements: 11.1, 11.2, 11.3, 11.4_
  - _Skills: /code-writing-software-development_
  - **AC:** First-time food items show "Order Now". Repeat items show "Reorder". Low-supply items show "Due Soon" amber badge. Food/supplement rows visually match vaccine rows. `npm run build` passes.

- [ ] 8. (task-026) Frontend — Health Trends Guardrails
  - **AskVetSection.tsx:** Cap vet questions to 2 per condition (`.slice(0, 2)`), show "1 more question" overflow indicator if truncated. Verify suggestive tone.
  - **SignalsSection.tsx:** Verify render order — blood panel → metabolic → weight chart (weight always last). Verify table format for CBC, concise format for imaging/urine.
  - **CareCadenceSection.tsx:** Verify/enforce order — vaccination first, tick & flea second, deworming third. Add additional cadence charts if pattern visible.
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 13.1, 13.2, 13.3, 13.4_
  - _Skills: /code-writing-software-development_
  - **AC:** Max 2 questions per condition. Weight chart last in Signals. Cadence order enforced. No prescriptive medication language. `npm run build` passes.

- [ ] 9. (task-027) Frontend — Records View Guardrails
  - **RecordsView.tsx:** Verify tab order (Vet Visits, Lab Reports, Imaging, WhatsApp Channel). Verify each record card shows key finding pill + "View" button.
  - **VetVisitCard.tsx:** Verify collapsible behavior — latest expanded, others collapsed. Verify expanded view shows Rx summary, medication rows, notes. Add link to full Rx document if available.
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  - _Skills: /code-writing-software-development_
  - **AC:** Tab order matches spec. Vet visits collapsible with latest open. Medication rows show in expanded view. Key finding pills on all record cards. `npm run build` passes.

- [ ] 10. (task-028) Integration Testing and Polish
  - Verify dashboard loads with nudge banner when nudges exist.
  - Verify NudgesView renders all 7 categories, dismiss works, cart integration works.
  - Verify care plan food/supplement "Due Soon" tags render correctly.
  - Verify all guardrail rules visually correct at 430px viewport.
  - Verify backend scheduler guards work (7-day cap, 72hr trigger, no same-day conflict).
  - Verify reminder templates render correctly with variable substitution.
  - Run `npm run build` — zero errors.
  - Run `python -m pytest` — all tests pass.
  - Fix any visual inconsistencies, type errors, or edge cases found.
  - _Requirements: all (1–15)_
  - _Skills: /code-writing-software-development, /verify_
  - **AC:** Full end-to-end flow works. Build passes. Tests pass. All acceptance criteria from tasks 019–027 verified. No regressions.
