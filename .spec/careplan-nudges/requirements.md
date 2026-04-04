# Requirements: Care Plan & Nudges Enhancement

## Introduction

Enhance the PetCircle dashboard and WhatsApp engagement systems across four domains: (1) enforce detailed UI guardrails across all existing dashboard cards to ensure clinical accuracy and non-alarming tone, (2) build a new NudgesView component to render prioritized health action nudges on the dashboard, (3) harden the backend nudge scheduler with global communication rules (frequency caps, inactivity triggers, same-day conflict prevention), and (4) introduce structured WhatsApp reminder message templates with 11-category, 4-stage lifecycle support. This is brownfield work — most backend services and API endpoints already exist; the changes are refinements, new guards, and a new frontend view.

---

## Requirements

### Requirement 1: Nudge Scheduler — Global Communication Rules

**User Story:** As a pet parent, I want to receive a reasonable number of nudges so that I stay engaged without feeling spammed.

#### Acceptance Criteria

1. The system SHALL enforce a maximum of 2 nudges in any rolling 7-day window per user, excluding health reminders from this count.
2. IF a user has received 2 nudges in the last 7 days THEN the system SHALL skip all pending nudges for that user until the window clears.
3. WHEN a user has had no engagement (no WhatsApp message sent/received, no dashboard visit, no document upload) for 72+ hours THEN the system SHALL trigger a nudge evaluation for that user even outside the O+N schedule, subject to the 7-day cap.
4. The system SHALL NOT send a nudge on the same calendar day (IST) that a health reminder was sent for any pet of the same user.
5. The system SHALL NOT send a nudge on the same calendar day that a health reminder is scheduled for any pet of the same user.
6. IF a nudge is blocked by any guard (7-day cap, same-day reminder, 48hr gap) THEN the system SHALL log the skip reason and reschedule the nudge for the next eligible slot.
7. The constants `NUDGE_MAX_PER_WEEK = 2` and `NUDGE_INACTIVITY_TRIGGER_HOURS = 72` SHALL be defined in `core/constants.py`.

---

### Requirement 2: Nudge Scheduler — Topic-Based Personalization

**User Story:** As a pet parent, I want nudges that feel relevant to what I was last talking about so that they don't feel generic.

#### Acceptance Criteria

1. WHEN the system selects a nudge for a Level 2 user THEN it SHALL check the topic of the user's last engagement (dashboard visit category, WhatsApp message topic, document upload type).
2. IF the last engagement was within 72 hours and on a specific topic THEN the system SHALL prioritize nudges related to that topic, re-sequencing the default priority order.
3. The system SHALL NOT send the same nudge type consecutively — each nudge SHALL differ from the previous nudge sent to that user.
4. IF no engagement topic is detectable THEN the system SHALL fall back to the standard Level 2 priority order: General → Health-1 (Vaccination, Tick & Flea, Deworming) → Nutrition → Health-2 (Vet Rx, Meds, Lab Tests) → Grooming.

---

### Requirement 3: Care Plan — Food/Supplement CTA Differentiation

**User Story:** As a pet parent, I want the care plan to show whether I've ordered a food or supplement before so that I know if it's a new recommendation or a reorder.

#### Acceptance Criteria

1. WHEN a food or supplement item is placed in the Continue bucket THEN the system SHALL include a `cta_label` field in the API response.
2. IF the pet has no prior order for that food/supplement THEN `cta_label` SHALL be `"Order Now"`.
3. IF the pet has a prior order for that food/supplement THEN `cta_label` SHALL be `"Reorder"`.
4. IF the pet has a prior order AND the estimated supply remaining is <= 7 days THEN `status_tag` SHALL be `"Due Soon"` instead of `"Active"`.
5. IF the pet has a prior order AND the estimated supply remaining is > 7 days THEN `status_tag` SHALL remain `"Active"`.
6. The `cta_label` and `status_tag` changes SHALL only apply to items with `orderable: true` and `test_type` in `("food", "supplement")`.

---

### Requirement 4: Reminder Message Templates

**User Story:** As a pet parent, I want reminders that are specific to the type of care due so that I know exactly what to do and feel personally addressed.

#### Acceptance Criteria

1. The system SHALL maintain a template registry covering 11 reminder categories: Vaccines (first-time), Vaccines (booster), Deworming, Flea & Tick, Food Order (scheduled), Food Order (supply-led), Supplement Order (scheduled), Supplement Order (supply-led), Chronic Medicines (scheduled), Chronic Medicines (supply-led), Vet Follow-ups, Blood Checkup, Vet Diagnostics, Hygiene.
2. Each category SHALL have 4 stage templates: T-7 (7 days before due), Due Date, D+3 (3 days after due), D+Overdue (ongoing overdue).
3. Each template SHALL support variable substitution for: `[Name]`, `[Pet]`, `[breed]`, `[date]`, `[vaccineList]`, `[Brand]`, `[Supplement]`, `[Medicine]`, `[condition]`, `[vetName]`, `[testName]`, `[X]` (days overdue), `[breedSpecificConsequence]`, `[snoozeDate]`.
4. Each template SHALL include CTA buttons matching the spec (e.g., `Order Now`, `Done — Log It`, `Remind Me Later`, `Share Report`).
5. The template text SHALL match the exact wording from the spec's Reminders sheet.

---

### Requirement 5: Reminder Send Rules

**User Story:** As a pet parent, I want reminders that are well-timed and not repetitive so that I don't ignore them.

#### Acceptance Criteria

1. The system SHALL send at most 1 reminder per day per pet.
2. The system SHALL enforce a minimum 3-day gap between reminders for the same item.
3. IF a reminder has been ignored 3 times at the same stage THEN the system SHALL reduce frequency to monthly only.
4. Hygiene reminders SHALL be sent at 10:00 AM IST on the due date only (no T-7 or D+3).
5. Standard T-7 and D+3 reminders SHALL be sent at 09:00 AM IST.
6. Due Date reminders SHALL be sent at 10:00 AM IST.
7. The system SHALL NOT fire a reminder and an overdue insight on the same day.
8. WHEN a user taps "Remind Me Later" THEN the system SHALL immediately reply with a confirmation message including the snooze date, and reschedule accordingly.

---

### Requirement 6: Reminder — Medicine Classification Rules

**User Story:** As a pet parent with a pet on medication, I want reminders to help me refill chronic medicines but not bother me about short courses.

#### Acceptance Criteria

1. IF a medicine is classified as "chronic" (ongoing, no end date) THEN the system SHALL generate refill reminders using the T-7, Due, D+3 sequence.
2. IF a medicine is classified as "course" (fixed duration, e.g., "5 days") THEN the system SHALL NOT generate reminders. The system SHALL only log the end date and display "Course Completed" on the dashboard after that date.
3. WHEN a medicine duration is stated in a document (e.g., "10 days") THEN the system SHALL auto-classify it as "course".
4. IF no duration is stated THEN the system SHALL classify it as "chronic" by default, and prompt the user to confirm during onboarding.
5. Supply calculation for chronic medicines SHALL use: `quantity / doses_per_day = days_supply`. Reorder reminder fires at 7 days remaining.

---

### Requirement 7: NudgesView — Frontend Component

**User Story:** As a pet parent, I want to see a list of health actions I should take for my pet so that I know what's important right now.

#### Acceptance Criteria

1. The system SHALL render a new view accessible from the dashboard, showing all undismissed nudges for the current pet.
2. Nudges SHALL be grouped by category in this order: vaccine, deworming, flea, condition, nutrition, grooming, checkup.
3. Each nudge card SHALL display: icon, title, priority badge (urgent = red, high = amber, medium = neutral), and message body.
4. IF a nudge is not mandatory THEN the system SHALL show a dismiss button. WHEN the user confirms dismissal THEN the system SHALL call `PATCH /nudges/{id}/dismiss` and remove the nudge from the list optimistically.
5. IF a nudge is mandatory THEN no dismiss button SHALL appear.
6. IF a nudge is orderable THEN the system SHALL show an "Order Now" CTA that adds the item to the cart, with a 1.8-second green "Added" feedback animation.
7. IF all nudges are dismissed or none exist THEN the system SHALL display an empty state: "All caught up! No actions needed right now."
8. The view SHALL include a loading spinner during the initial fetch and a home floater button to return to the dashboard.
9. `DashboardClient.tsx` SHALL add `"nudges"` to its ViewState union and render NudgesView when active.

---

### Requirement 8: Dashboard — Nudge Entry Point

**User Story:** As a pet parent, I want to see at a glance if there are action items waiting for me so that I don't miss important care tasks.

#### Acceptance Criteria

1. WHEN the dashboard loads AND the pet has > 0 undismissed nudges THEN the system SHALL render a banner between HealthConditionsCard and CarePlanCard showing "You have N action items for [petName]" with a "View All" CTA.
2. IF the pet has 0 undismissed nudges THEN the banner SHALL NOT render.
3. WHEN the user taps the banner THEN the system SHALL navigate to the NudgesView.
4. WHEN the user returns from NudgesView after dismissing nudges THEN the banner count SHALL update to reflect the current undismissed count.

---

### Requirement 9: Dashboard Guardrails — Health Conditions Card

**User Story:** As a pet parent, I want health conditions displayed by importance so that I focus on what matters most.

#### Acceptance Criteria

1. The system SHALL sort conditions by severity (red first) then recency (most recent first) before displaying.
2. The system SHALL display at most 2 conditions unless any condition has a trend label containing "active", "recurrent", or "recurring" — in that case, all matching conditions SHALL be shown.
3. IF the pet's life stage is "puppy" THEN the system SHALL include overdue preventive items (e.g., missed vaccinations, deworming) as pseudo-conditions in this card.
4. IF the pet's life stage is "adult" or "senior" THEN preventive items SHALL appear in Health Conditions ONLY IF there is a documented health impact or actionable gap (e.g., "Deworming overdue — increased parasite risk").
5. IF the pet has no active conditions THEN the system SHALL display: "No active concerns · Routine care maintained".
6. The system SHALL NOT recommend specific medications in condition insights. Diagnostic/test recommendations MAY be made but SHALL always include "ask your vet" phrasing.
7. The system SHALL NOT use the word "Urgent" — "High Priority" is acceptable.

---

### Requirement 10: Dashboard Guardrails — Life Stage Card

**User Story:** As a pet parent, I want age-appropriate trait information so that I understand my pet's current needs.

#### Acceptance Criteria

1. Trait pills SHALL be limited to at most 2 rows (CSS max-height with overflow hidden).
2. Trait pills SHALL be ordered: behavior/energy traits first → appetite/physiology change traits → clinical traits.
3. Trait pills SHALL NEVER use alarming phrases. They SHALL inform how the pet's behavior or body is changing and what the parent could monitor.
4. Essential care items (max 2) SHALL be linked to the trait pills shown above — they explain what must evolve in the pet's care or diet.

---

### Requirement 11: Dashboard Guardrails — Care Plan Card

**User Story:** As a pet parent, I want the care plan to clearly explain why each item matters so that I don't feel sold to.

#### Acceptance Criteria

1. The "reason" field on orderable items SHALL build connectivity between health/nutrition insights shown earlier on the dashboard and the care plan recommendation.
2. Food and supplement items in the Continue bucket SHALL display using the same row layout as Vaccines & Preventive Care items (visual parity).
3. WHEN `status_tag` is `"Due Soon"` THEN the system SHALL render an amber badge next to the status tag.
4. The system SHALL use the `cta_label` field from the API response for the button text, defaulting to `"Order Now"` if absent.

---

### Requirement 12: Health Trends Guardrails — Ask Your Vet

**User Story:** As a pet parent, I want vet discussion questions that are tactful and not overwhelming.

#### Acceptance Criteria

1. Each condition in the Ask Your Vet section SHALL show at most 2 questions. IF a 3rd question exists AND is clinically essential THEN it MAY be shown; otherwise it SHALL be hidden behind a "1 more question" overflow indicator.
2. Questions SHALL be phrased in a suggestive tone that can be directly asked to a vet without causing offence (e.g., "Would it be worth checking..." not "You need to...").
3. The sequence within each condition card SHALL be: condition pill → headline → Ask Vet questions → health marker trend chart → condition timeline.
4. Condition pills SHALL link to the corresponding Health Conditions entry on the dashboard (shared condition identifier).

---

### Requirement 13: Health Trends Guardrails — Signals & Cadence

**User Story:** As a pet parent, I want health signals and care cadence charts in a logical, consistent order.

#### Acceptance Criteria

1. In the Signals section, the weight chart SHALL always render last (after blood panel and metabolic cards).
2. CBC and blood chemistry reports SHALL render as a table format. Other report types (imaging, urine culture) SHALL use a concise summary format.
3. In the Care Cadence section, charts SHALL render in this fixed order: Vaccination first, Tick & Flea second, Deworming third.
4. IF additional cadence patterns are detectable from records (e.g., regular lab tests, vet visits) THEN the system SHALL render additional cadence charts after the third.

---

### Requirement 14: Records View Guardrails

**User Story:** As a pet parent, I want my pet's medical records organized by type with key findings visible at a glance.

#### Acceptance Criteria

1. Record tabs SHALL appear in this order: Vet Visits, Lab Reports, Imaging, WhatsApp Channel.
2. Each record card SHALL display a key finding pill (colored badge with summary text) and a "View" button linking to the individual report.
3. Vet visit cards SHALL be collapsible. The latest visit SHALL be expanded by default; all others SHALL be collapsed.
4. The expanded vet visit view SHALL show: Rx/prescription summary, medication rows (name, dose, duration), and clinical notes.
5. IF a prescription document is linked to the vet visit THEN the card SHALL include a link to view the full Rx.

---

### Requirement 15: Diet Analysis Guardrails

**User Story:** As a pet parent, I want nutritional analysis thresholds that match clinical standards.

#### Acceptance Criteria

1. For Calories: >100% of need SHALL display as amber. <=100% SHALL display as green.
2. For Protein, Omega-3, Fat, and all other macros: >110% SHALL display as amber. <80% SHALL display as red. 80-110% SHALL display as green.
3. The Omega-3 threshold SHALL follow the general rule (<80% = red) — no special-case override.
