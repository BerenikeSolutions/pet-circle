# Plan: PetCircle Nudge & Reminder Agent (Excel v5 Spec)

## Context
`PetCircle_Nudges_v5.xlsx` defines a complete communication spec for two distinct outbound systems:
1. **Reminders** — health-event-driven, 4-stage lifecycle (T-7 / Due / D+3 / Overdue escalation)
2. **Nudges** — engagement-driven, user-level-based (Level 0/1/2), sent on a fixed O+N day schedule

Current codebase (`reminder_engine.py` + `nudge_engine.py` + `nudge_sender.py`) implements a simplified version: 2 reminder templates, 1 nudge template, no user leveling, no message staging. This plan closes that gap.

---

## WhatsApp Template Necessity Analysis

**Core rule:** WhatsApp Business API requires pre-approved templates for any message sent *outside* a 24-hour window of a user-initiated interaction. The 8 AM IST cron job is proactive — users have not messaged in the last 24 hours in the typical case.

**Conclusion: Templates are required for all cron-sent messages.** Free-form text is only usable for:
- Immediate bot auto-replies triggered by a user tapping a button (within 24hr window)
- Examples: "Remind me later" snooze confirmation, "Done - Log It" acknowledgement reply

**Therefore: Register all new templates with Meta.**

### Full Template Set to Register

| Env Var Name | Template Name | Purpose | Variables | Buttons |
|---|---|---|---|---|
| `WHATSAPP_TEMPLATE_REMINDER_T7` | `petcircle_reminder_t7_v1` | 7 days before due | parent_name, pet_name, item_desc, due_date | Remind Me Later · Already Done |
| `WHATSAPP_TEMPLATE_REMINDER_DUE` | `petcircle_reminder_due_v1` | Due date (10am) | parent_name, pet_name, item_desc | Done — Log It · Remind Me Later · Order Now |
| `WHATSAPP_TEMPLATE_REMINDER_D3` | `petcircle_reminder_d3_v1` | D+3 check-in | parent_name, pet_name, item_desc, original_due | Yes — Log It · Still Pending · Schedule |
| `WHATSAPP_TEMPLATE_REMINDER_OVERDUE` | `petcircle_reminder_overdue_v1` | D+7+, monthly | parent_name, pet_name, item_desc, days_overdue, consequence | Completed — Log It · Still Pending · Schedule |
| `WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT` | `petcircle_nudge_engagement_v1` | Breed engagement | breed_insight_sentence, cta_question | None (reply-based) |
| `WHATSAPP_TEMPLATE_NUDGE_BREED` | `petcircle_nudge_breed_v1` | Breed preventive care | breed_insight, cta_question | None (reply-based) |
| `WHATSAPP_TEMPLATE_NUDGE_BREED_DATA` | `petcircle_nudge_breed_data_v1` | Breed + data request | breed_insight, pet_name, record_type, reply_action | None (reply-based) |
| `WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_STATIC` | `petcircle_nudge_va_static_v1` | Level 0, no name | None (static body) | None |
| `WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL` | `petcircle_nudge_va_personal_v1` | Level 0/1, with name | pet_name (x2) | None |

**Note on consolidation:** A single generic T-7 template with variable `item_desc` can cover all 11 reminder categories (vaccine, deworming, food, etc.) — avoids 11 separate templates. Same applies to Due, D+3, and Overdue stages. - **what about the birthday wishes reminder**

**Note on existing templates:** `petcircle_reminder_v1` and `petcircle_overdue_v1` (current) will be retired once new 4-stage templates are live. `petcircle_nudge_v1` will be replaced by the 3 new nudge templates.

---

## Excel Spec Summary

### Reminders — 4 Stage Lifecycle (per category) - **all at the same time 8 am**
| Stage | Time | Behaviour |
|---|---|---|
| T-7 | 9am, 7 days before | First alert, option to snooze or log as done |
| Due Date | 10am, day of | Action prompt |
| D+3 | 9am, 3 days after | Check-in if not logged |
| D+7 (Overdue Insight) | D+7 if D+3 ignored | Breed-specific consequence + monthly after |

**11 reminder categories:** Vaccine First Time · Vaccine Booster · Deworming · Flea & Tick · Food Order · Supplement Order · Chronic Medicine · Vet Follow-up · Blood Checkup · Vet Diagnostics · Hygiene (due-only, no T-7 or D+3)

**Send Rules:**
- Max 1 reminder per day per pet; min 3 days between sends
- 2 ignored at same level → drop to monthly only
- Never fire reminder + overdue insight on same day

### Nudges — User Level System
**3 levels (recalculated on every trigger: upload, reply, dashboard visit, cron):**
- **Level 0**: Cold Start — no breed, no health data
- **Level 1**: Breed available, no health records
- **Level 2**: Breed + data from ≥1 category

**Level 0 & 1 — Fixed O+N schedule:**
| Slot | Level 0 | Level 1 |
|---|---|---|
| O+1 | Value Add | Value Add |
| O+5 | Value Add | Engagement Only |
| O+10 | Value Add | Value Add |
| O+20 | Value Add | Engagement Only |
| O+30 | Value Add | Breed Only |
| After O+30 | 1 msg/30 days if no engagement | 1 msg/30 days if no engagement |

**Level 2 — Communication-rule-driven:**
- Slots 1-3: Breed + Data (completion nudges, by data priority order)
- Slots 4-5: Personalized (see OQ3)
- After slot 5: engagement-based frequency

**Level 2 data priority for Breed + Data nudges:**
1. Vaccination · 2. Tick & Flea · 3. Deworming · 4. Nutrition (food) · 5. Supplements · 6. Vet Prescription · 7. Ongoing medication · 8. Lab/Diagnostics · 9. Grooming

**Global Communication Rules (Level 2):**
1. Reminders always take precedence — never nudge on same day as reminder
2. 48hr+ gap since last engagement (chat reply, upload, dashboard visit)
3. Max 2 nudges per 7-day window (excluding reminders)
4. Topic of last engagement → re-sequence priority if relevant

---

## Pending Decisions (Required Before Implementation)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Nudge system architecture | A: Replace · B: Parallel · C: Merge | A (cleanest) |
| D2 | Code vs Agent | 1: Pure Code · 2: LLM Agent · 3: Hybrid | 3 (Hybrid) |
| OQ1 | O (Onboarding Day) definition | A: `onboarding_completed_at` · B: first pet `created_at` | A |
| OQ2 | Level 2 threshold | A: any `preventive_record` · B: Health-1 only · C: any data | A |
| OQ3 | Level 2 Personalized slots (4-5) | A: GPT insight · B: top health nudge · C: skip/fallback | C (skip for now) |
| OQ4 | Same-day rule scope | Per-pet · Per-user | Per-user |
| OQ5 | "Schedule For ()" button | A: fixed snooze · B: custom date prompt · C: interactive list | — |
| OQ6 | breedSpecificConsequence | A: lookup table · B: GPT · C: generic fallback | C (v1 fallback) |

---

## Nudge System Architecture — 3 Options

### Option A — Replace (cleanest, recommended)
- Remove WhatsApp sending from `nudge_engine.py` / `nudge_sender.py`
- New `nudge_scheduler.py` drives ALL WhatsApp nudge sends (level-based)
- `nudge_engine.py` still generates health nudges for **dashboard display only**
- **Pros:** Clean separation; no double-messaging; matches Excel spec exactly
- **Cons:** Loses the reactive "you have a vaccine overdue" WA nudge

---

## Code vs Agent: How Should the Scheduler Run?


### Option 2 — LLM Agent (GPT orchestrates)
- GPT reads user profile and decides level, message type, and content
- Similar to `agentic_onboarding.py` / `agentic_order.py` already in codebase
- **Pros:** Handles edge cases; "Personalized" slots trivially solved
- **Cons:** GPT cost × all active users; latency; unpredictable; if GPT fails, no nudge sent
---

## Open Questions — Detailed

### OQ1 — What is O (Onboarding Day)?

**Option A: `onboarding_completed_at` on User model**
- Date the user finished onboarding conversation
- User model has `onboarding_state` enum but no timestamp — need to add `onboarding_completed_at` column
- **Impact:** 1 new column in migration


### OQ2 — What Counts as "Level 2"?

breed + data from anyone category

---

### OQ3 — Level 2 Personalized Nudges (Slots 4 & 5)

**Option A: GPT-generated health insight** - selected we need to save it in db for reference 
- Prompt: pet's breed + weight + conditions + last health events → 2-sentence WA message - based on what information we have
- 1 GPT call per user hitting slot 4 or 5


---

### OQ4 — Same-Day Rule: Per-Pet or Per-User?

**Per-pet:** Pet A reminder today → Pet A skips nudge; Pet B can still get one
---

### OQ5 — "Schedule For ()" Button

Appears on Due, D+3, Overdue reminders. Not currently implemented.
**Option B: Custom date prompt** — bot asks for date, new user state `awaiting_reschedule_date` + parser in `message_router.py` - selected

---

### OQ6 — breedSpecificConsequence

In Overdue Insight: `"[Pet]'s [item] was due [X] days ago — [breedSpecificConsequence]."`

**Option A: Static lookup table** — `breed_consequence_library` DB table, ~75 rows (15 breeds × 5 categories) - table only. generate a table based on the excel information. if any breed not available for any category add a generic message for now. so user comes breed available from table message breed not available then generic message which is stored in table

---

### REMINDER SYSTEM

**R1 — Cron Timing Conflict**
The cron runs at 8 AM IST. The spec says T-7 and D+3 at 9 AM, Due Date and Hygiene at 10 AM. With one cron run we can't send at two different times.
- Option C: Keep single 8 AM cron everuthing one time

**R2 — Food Order Reminder: No Structured Pack Size Data**
`diet_items` table has: `label`, `detail` (free text like "280g x 2/day"), `type`. It has **no** `pack_size_g` or `daily_portion_g` columns. The Excel says reorder trigger = `pack_size ÷ daily_portion = days remaining, fire at 7 days`.

- Option A: Add `pack_size_g`, `daily_portion_g`, `brand` columns to `diet_items` (new migration + frontend input) - add this to the table
- if pack size or daily portion not available - At O+21 (1 month after onboarding)?

**R3 — Supplement Order Reminder: Same Data Gap**
`diet_items` where `type = 'supplement'` also has no `units_in_pack` or `doses_per_day`. Same problem as R2.
- add required info to db
- At O+21 (1 month after onboarding)?

**R4 — Chronic Medicine Reminder: Data Source Confirmed**
`condition_medications.refill_due_date` (Date, nullable) exists — this can drive the T-7 reminder directly without calculation. No question here, just confirming: **Chronic Medicine reminders read from `condition_medications.refill_due_date`**. Agree? yes

**R5 — Vet Follow-up Reminder: What Table Drives This?**
The spec says "date from document or manual entry." There is no dedicated `vet_followup` table. Possible sources:
- `condition_monitoring.next_due_date` (monitoring tasks per condition)


**R6 — [vetName] Variable: Which Contact to Use?**
A pet can have multiple contacts with `role = 'veterinarian'`. The `[vetName]` variable in the reminder message needs exactly one name.
- Use a generic "your vet" if more than one exists or none found? 

**R7 — Vaccine List: One Record or Multiple?**
The Excel says `vaccineList = "filtered to due vaccines only, joined with · separator"` (e.g., "DHPPi · Rabies"). There are separate entries in `preventive_master` for each vaccine (DHPPi, Rabies, Kennel Cough, CCV etc.). Does each vaccine have its own `preventive_record` row per pet, allowing individual due-date tracking? Or is there a combined "Vaccines" record? - one entry per vaccine - but when reminders go it should go as a single combined message of the vaccines dues separated by mandatory and optional

**R8 — Hygiene Reminder: Combined or Per-Item?**
`hygiene_preferences` has separate rows: `bath-nail` (Bath, brush & nail trim) and `ear-clean` (Ear Cleaning). Each has its own `reminder` boolean toggle.
The Excel says "single combined reminder covers Bath & Brush, Nail Trim and Ear Cleaning."
- Send 1 message combining all hygiene items whose `reminder = True`?
- Or send a separate message per hygiene item that has `reminder = True`?
Also: `last_done` is stored as a formatted string (DD/MM/YYYY), not a Date — the reminder engine will need to parse this string to calculate due dates. - single reminder combining all but separated based on categories 

**R9 — "Ignored" Definition for 3-Strike Monthly Fallback**
The spec: "2 ignored at same level → drop to monthly only." What counts as ignored?
- Option A: No button tapped within 24 hours of sending
- Option C: No inbound reply of any kind within 24 hours

**R10 — Blood Checkup First-Time Trigger**
The spec: "Annual / First nudge within 1 month of onboarding if never done." If a pet has no blood checkup record at all (`lastDone = null`), when does the first T-7 reminder fire?
- At O+30 (1 month after onboarding)?

**R11 — Snooze Duration Per Item Type**
Current code uses a fixed 7-day snooze (`REMINDER_SNOOZE_7`) for all reminders. The spec says "backend handles snooze duration per item type." What are the snooze durations?
- Vaccines: ? days
- Deworming: ? days
- Flea & Tick: ? days
- Food Order: ? days (food is urgent — 7 days is too long)
- Supplement: ? days
- Chronic Medicine: ? days
- Vet Follow-up: ? days
- Hygiene: ? days currenyly keep 7 days for everything but keep a separate value for everything so later i can configure as needed

**R12 — "Done — Log It" Button: New or Existing Handler?**
Current code handles `REMINDER_DONE` (updates `last_done_date`, recalculates `next_due_date`, marks reminder completed). The new spec also has `REMINDER_DONE` semantics but for new reminder categories (Food Order, Supplement, Medicine, Vet Follow-up, Hygiene). Does the existing `REMINDER_DONE` handler in `reminder_response.py` work for all new categories, or do some need different post-done logic (e.g., Food Order done = restock confirmed, no new `next_due_date` recalculation)? same

**R13 — "Order Now" Button: What Does Tapping Do?**
Several reminder categories (Deworming, Flea & Tick, Food, Supplement, Medicine) have an "Order Now" CTA. What happens when a user taps this?
- Option A: Triggers the existing agentic order flow (`agentic_order.py`)


---

### NUDGE SYSTEM

**N1 — [breed] in Template Prefix: Critical Meta Compliance Issue**
Engagement Only template: `"Here's something most [breed] parents find fascinating — {{1}} 🐾 Does this sound like your pet? {{2}}"`
Breed Only template: `"One thing most [breed] parents find out too late — {{1}} 🐾 Worth knowing for your pet. {{2}}"`

`[breed]` is **not a WhatsApp variable** — it's shown as fixed text in the Excel. But breed changes per user, so it can't literally be fixed. Two options:
- Option A: Register one template **per breed** (~15 breeds × 2 template types = **30 templates**)
- Option B: Embed breed into `{{1}}` (e.g., `{{1}} = "Goldens were bred to..."` already starts with breed context, no separate [breed] in prefix needed — redesign prefix to be fully generic: `"Here's something fascinating about your pet's breed — {{1}} 🐾 Does this sound like your pet? {{2}}"`) 

Option A = 30 templates + 30 Meta approval processes.
Option B = 2 templates, redesigned prefix, no breed variable compliance issue.
**This is the single biggest template design decision in the entire plan.** - embed breed as a whatsapp variable

**N2 — Breeds Not in the Message Library**
The Excel defines messages for ~15 specific breeds (Golden Retriever, Lab, GSD, Beagle, Shih Tzu, Pomeranian, Rottweiler, Husky, Indian dog, Dachshund, French Bulldog, Samoyed, Shiba Inu, Poodle, Bernese Mountain Dog). Cats and all other breeds have no defined messages.
- What happens when a Level 1 user's pet is a Cocker Spaniel, Persian cat, or unlisted breed? - 
- Use nearest known breed? Use a generic message (no breed name)? Skip nudge that slot?

create a table with all the values in the excel if breed not available add a value in the breed as Other and create a generic message similar to the ones existing

**N3 — Value Add: Missing Messages for O+20 and O+30 (Level 0)**
The Excel's Value Add sheet defines 3 messages for Level 0 (O+1, O+5, O+10) but the schedule has 5 slots (O+1, O+5, O+10, O+20, O+30).
- What goes at O+20 and O+30 for Level 0? Cycle messages 1–3? Use Engagement Only? Use a generic fallback?
for level 0 - create a new message now and keep for 0+20 and 0+230 similar to the the 3 slots.

**N4 — After O+30: Which Message Type at 30-Day Intervals?**
Both Level 0 and Level 1 drop to "1 message every 30 days if no engagement" after O+30. Which message type?
- Continue cycling Value Add / Engagement Only messages from the library?

**N5 — "AI to Continue On-Boarding Flow If Customer Engages"**
The Excel states: when a Level 0/1 user replies to a nudge, "AI to continue on-boarding information flow if customer engages." What is this?
- Option A: Route to existing `agentic_onboarding.py` (LLM-driven onboarding conversation)

**N6 — Multi-Pet Users: Weekly Cap Scope** - no weekly cap scope
`nudge_engagement` tracks per `(user_id, pet_id)`. The 2-nudge weekly cap — is it:
- **Per pet**: each pet can receive 2 nudges/week independently (user with 3 pets = max 6 nudges/week)
- **Per user**: across all pets combined, max 2 nudges/week total (user with 3 pets = still only 2 nudges/week)

**N7 — Level Transition: What Happens Mid-Sequence?**
A Level 1 user is at O+5 (just received Engagement Only nudge). They upload a vaccine record → become Level 2.
- Option A: Immediately switch to Level 2 Breed+Data sequence from slot 1

**N8 — Dashboard Visit Tracking: Not Implemented**
`dashboard_tokens` has no `last_visited_at` column. The spec says level is recalculated "on every trigger event including dashboard visit" and the 48hr engagement gap checks this. Dashboard visits are currently untracked.
everytime a user clicks a dashboard - update it in a separate table. so how many times visited can be tracked


**N9 — "Check Topic of Last Engagement" for Level 2 Re-Sequencing**
Rule 4 in Level 2 communication rules: "If any engagement on dashboard/chat/upload by user, see what the engagement topic was and re-prioritize next nudge accordingly."
- How do we detect "topic" from a WA reply? By button payload (REMINDER_DONE for vaccines = user is engaged with health)?
- Or from upload content (GPT extracted a deworming record = next nudge should skip deworming)?
- This requires defining what "topic detection" means in code — rule-based or GPT?
GPT - should detect topic
---

### SCHEMA / INFRA

**S1 — nudge_message_library in clear_database.sql**
The user had `clear_database.sql` open. It currently skips `nudge_config` and `preventive_master` (reference data). Should `nudge_message_library` (seeded content from Excel) also be excluded from the clear script, like `nudge_config`? yes

**S2 — Reminder Unique Constraint Change**
Current constraint: `UNIQUE(preventive_record_id, next_due_date)`. With 4 stages (t7, due, d3, overdue_insight), two reminders for the same record on the same date but different stages would violate this. Constraint must become `UNIQUE(preventive_record_id, next_due_date, stage)`. Confirm? yes

**S3 — Existing Reminder Rows Migration**
There are existing rows in the `reminders` table (current production data). When we add the `stage` column with default `'t7'`, existing rows will get `stage = 't7'` which is incorrect (they were already sent as "due" or "overdue"). How should existing rows be handled on migration?
- Set existing sent rows to `stage = 'due'` (closest to current behaviour)?
- Leave as `t7` (accept data inaccuracy in historical rows)? - no existing data i will clear db

Use the excel to generate all neccesary tables and store that information as required in tables

New items not related to nudge

1. in onboarding ask one question at a time - in each category there are separates sections like vaccines are optional and mandatory - nutrition is food and supplement - ask one question per section
2. when you give a message lets continue setting up your profile - here's what we have so far - i dont need all the detials collected only the last detail that was collected and stored in db should be shown