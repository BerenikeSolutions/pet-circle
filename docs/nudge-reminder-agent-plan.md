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

**Note on consolidation:** A single generic T-7 template with variable `item_desc` can cover all 11 reminder categories (vaccine, deworming, food, etc.) — avoids 11 separate templates. Same applies to Due, D+3, and Overdue stages.

**Note on existing templates:** `petcircle_reminder_v1` and `petcircle_overdue_v1` (current) will be retired once new 4-stage templates are live. `petcircle_nudge_v1` will be replaced by the 3 new nudge templates.

---

## Excel Spec Summary

### Reminders — 4 Stage Lifecycle (per category)
| Stage | Time | Behaviour |
|---|---|---|
| T-7 | 9am, 7 days before | First alert, option to snooze or log as done |
| Due Date | 10am, day of | Action prompt |
| D+3 | 9am, 3 days after | Check-in if not logged |
| D+7 (Overdue Insight) | D+7 if D+3 ignored | Breed-specific consequence + monthly after |

**11 reminder categories:** Vaccine First Time · Vaccine Booster · Deworming · Flea & Tick · Food Order · Supplement Order · Chronic Medicine · Vet Follow-up · Blood Checkup · Vet Diagnostics · Hygiene (due-only, no T-7 or D+3)

**Send Rules:**
- Max 1 reminder per day per pet; min 3 days between sends
- 3 ignored at same level → drop to monthly only
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

### Option B — Parallel (two independent systems)
- Keep existing nudge_engine + nudge_sender sending health nudges via WA
- New `nudge_scheduler.py` runs additionally for level-based engagement nudges
- **Pros:** No regression; adds engagement layer on top
- **Cons:** User could get 2 WA messages/day; complex rate limit coordination

### Option C — Merge (scheduler wraps engine)
- `nudge_scheduler.py` calls `nudge_engine.py` to get health nudges for Level 2 "Personalized" slots
- For Level 0/1, sends engagement nudges; for Level 2 slots 4-5, uses top health nudge from engine
- **Pros:** Natural fit for "Personalized" = health nudge; reuses existing engine
- **Cons:** Slightly more complex orchestration

---

## Code vs Agent: How Should the Scheduler Run?

### Option 1 — Pure Code (Deterministic Python)
- All routing via `if/elif` branching; message selection is a DB lookup
- No LLM involved in deciding what to send
- **Pros:** Fast, cheap, predictable, fully testable
- **Cons:** Rule changes require code deploys

### Option 2 — LLM Agent (GPT orchestrates)
- GPT reads user profile and decides level, message type, and content
- Similar to `agentic_onboarding.py` / `agentic_order.py` already in codebase
- **Pros:** Handles edge cases; "Personalized" slots trivially solved
- **Cons:** GPT cost × all active users; latency; unpredictable; if GPT fails, no nudge sent

### Option 3 — Hybrid (Recommended)
- Code handles all routing logic deterministically (level calc, comm rules, message library lookup)
- GPT called only for: Level 2 Personalized slots (4-5) and optionally `breedSpecificConsequence`
- **Matches WAT architecture:** "probabilistic AI handles reasoning while deterministic code handles execution"

---

## Open Questions — Detailed

### OQ1 — What is O (Onboarding Day)?

**Option A: `onboarding_completed_at` on User model**
- Date the user finished onboarding conversation
- User model has `onboarding_state` enum but no timestamp — need to add `onboarding_completed_at` column
- **Impact:** 1 new column in migration

**Option B: Date first pet was created**
- `MIN(pets.created_at) WHERE user_id = X` — no schema change needed
- Slightly earlier than Option A (pet created before `state = complete`)

**Recommendation:** Option A — semantically cleaner.

---

### OQ2 — What Counts as "Level 2"?

**Option A: Any `preventive_record` with `last_done_date IS NOT NULL`**
- 1 SQL query; covers vaccines, deworming, flea, vet visits, medicines
- Any uploaded health document qualifies

**Option B: Health-1 records only (vaccine OR deworming OR flea)**
- Stricter; requires keyword matching on `preventive_master.item_name` (same logic as `nudge_engine.py`)

**Option C: Broad — any data including diet, conditions, weight, diagnostics**
- 4+ queries with UNION; most inclusive

**Recommendation:** Option A for v1 — 1 query, pragmatic, extensible later.

---

### OQ3 — Level 2 Personalized Nudges (Slots 4 & 5)

No message content defined in Excel for these slots.

**Option A: GPT-generated health insight**
- Prompt: pet's breed + weight + conditions + last health events → 2-sentence WA message
- 1 GPT call per user hitting slot 4 or 5

**Option B: Top health nudge from `nudge_engine.py`**
- `generate_nudges(db, pet_id)` → take top-priority unsent nudge
- No GPT; reuses existing engine (natural fit for Architecture Option C)

**Option C: Skip for now — fall back to Breed Only**
- Unblocks everything else; revisit when content is defined

---

### OQ4 — Same-Day Rule: Per-Pet or Per-User?

**Per-pet:** Pet A reminder today → Pet A skips nudge; Pet B can still get one
**Per-user:** Any pet has reminder today → user gets no nudge at all (max 1 WA/day)

**Recommendation:** Per-user.

---

### OQ5 — "Schedule For ()" Button

Appears on Due, D+3, Overdue reminders. Not currently implemented.

**Option A: Fixed 7-day snooze** — reuses existing `REMINDER_SNOOZE_7`, zero new code
**Option B: Custom date prompt** — bot asks for date, new user state `awaiting_reschedule_date` + parser in `message_router.py`
**Option C: Interactive snooze list** — "In 3 days / Next week / In 2 weeks" via `send_interactive_buttons()`

---

### OQ6 — breedSpecificConsequence

In Overdue Insight: `"[Pet]'s [item] was due [X] days ago — [breedSpecificConsequence]."`

**Option A: Static lookup table** — `breed_consequence_library` DB table, ~75 rows (15 breeds × 5 categories)
**Option B: GPT at send time** — 1 GPT call per overdue insight fired
**Option C: Generic fallback v1** — "Staying on schedule protects [Pet]'s long-term health." — zero new code

**Recommendation:** Option C for v1, upgrade to Option A once copy is written.

---

## Proposed New Components

### New Services
| File | Purpose |
|---|---|
| `backend/app/services/user_level_service.py` | Calculates Level 0/1/2 per user/pet; returns data availability map |
| `backend/app/services/nudge_scheduler.py` | Main agent: level check → comm rule checks → message selection → delegate send |
| `backend/app/services/nudge_message_library.py` | Loads message content from DB (Engagement Only, Breed Only, Breed+Data, Value Add) |

### Modified Services
| File | Changes |
|---|---|
| `backend/app/services/reminder_engine.py` | Add T-7, D+3, Overdue Insight stages; `stage` enum; `ignored_count` tracking |
| `backend/app/services/nudge_sender.py` | Accept template name + vars from scheduler; remove self-directed type selection |
| `backend/app/routers/internal.py` | Replace `run_nudge_engine()` + `send_pending_nudges()` with `run_nudge_scheduler()` |

### New Migration (`018_nudge_scheduler.sql`)
```sql
-- Reminder staging
ALTER TABLE reminders ADD COLUMN stage VARCHAR(20) DEFAULT 't7';
  -- values: t7 | due | d3 | overdue_insight
ALTER TABLE reminders ADD COLUMN ignored_count INT DEFAULT 0;
ALTER TABLE reminders ADD COLUMN last_sent_stage VARCHAR(20);

-- Nudge sequence tracking
ALTER TABLE nudge_engagement ADD COLUMN sequence_position INT DEFAULT 0;
ALTER TABLE nudge_engagement ADD COLUMN onboarding_date DATE;
ALTER TABLE nudge_engagement ADD COLUMN last_nudge_type VARCHAR(30);
ALTER TABLE nudge_engagement ADD COLUMN last_nudge_date DATE;
ALTER TABLE nudge_engagement ADD COLUMN weekly_nudge_count INT DEFAULT 0;
ALTER TABLE nudge_engagement ADD COLUMN weekly_window_start DATE;

-- Message library
CREATE TABLE nudge_message_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_type VARCHAR(30),   -- value_add_l0_static | value_add_personal | engagement_only | breed_only | breed_data
    breed VARCHAR(100),         -- NULL for static/generic
    data_field VARCHAR(50),     -- for breed_data: vaccination | deworming | flea | etc.
    message_index INT,          -- 1 or 2 (some breeds have 2 messages)
    body_v1 TEXT,
    body_v2 TEXT,
    body_v3 TEXT,
    body_v4 TEXT,
    template_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### New Seed Script
`backend/scripts/seed_nudge_messages.py` — imports all message content from Excel into `nudge_message_library`.

### New Env Vars (`.env.example`)
```
WHATSAPP_TEMPLATE_REMINDER_T7=petcircle_reminder_t7_v1
WHATSAPP_TEMPLATE_REMINDER_DUE=petcircle_reminder_due_v1
WHATSAPP_TEMPLATE_REMINDER_D3=petcircle_reminder_d3_v1
WHATSAPP_TEMPLATE_REMINDER_OVERDUE=petcircle_reminder_overdue_v1
WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT=petcircle_nudge_engagement_v1
WHATSAPP_TEMPLATE_NUDGE_BREED=petcircle_nudge_breed_v1
WHATSAPP_TEMPLATE_NUDGE_BREED_DATA=petcircle_nudge_breed_data_v1
WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_STATIC=petcircle_nudge_va_static_v1
WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL=petcircle_nudge_va_personal_v1
```

---

## Data Flow (8 AM IST Cron)

```
GitHub Actions → POST /internal/run-reminder-engine
  ↓
execute_reminder_engine() [internal.py]
  ├─ expire_pending_conflicts()
  ├─ run_enhanced_reminder_engine()   ← creates T-7 / Due / D+3 / Overdue records
  ├─ send_pending_reminders()         ← sends by stage, enforces per-pet daily limit
  ├─ run_nudge_scheduler()            ← NEW: level calc → comm rule checks → select + send
  └─ check_inactivity_nudges()
```

## Nudge Scheduler Decision Tree (per user)

```
1. Recalculate level (0, 1, 2) via user_level_service
2. Any reminder sent today for any of user's pets? → SKIP (scope per OQ4)
3. Last message < 48hrs ago? → SKIP
4. Weekly nudge count >= 2? → SKIP, schedule for next week
5. Level 0 or 1:
     - Days since O → find next unsent O+N slot
     - Select message type per level/slot
     - Look up message from nudge_message_library (type, breed, index not yet sent)
6. Level 2:
     - Find next unfulfilled data priority (Vaccination → Tick → Deworming → ...)
     - Position 1-3 → Breed + Data nudge for that field
     - Position 4-5 → Personalized (per OQ3)
7. Send via appropriate WhatsApp template
8. Update nudge_engagement: sequence_position++, last_nudge_type, last_nudge_date, weekly_nudge_count
```

---

## Files to Create / Modify

| File | Action |
|---|---|
| `backend/app/services/user_level_service.py` | CREATE |
| `backend/app/services/nudge_message_library.py` | CREATE |
| `backend/app/services/nudge_scheduler.py` | CREATE |
| `backend/app/services/reminder_engine.py` | MODIFY |
| `backend/app/services/nudge_sender.py` | MODIFY |
| `backend/app/routers/internal.py` | MODIFY |
| `backend/app/models/reminder.py` | MODIFY (stage, ignored_count) |
| `backend/app/models/nudge_engagement.py` | MODIFY (sequence tracking) |
| `backend/migrations/018_nudge_scheduler.sql` | CREATE |
| `backend/scripts/seed_nudge_messages.py` | CREATE |
| `backend/envs/.env.example` | MODIFY |

## Additional Clarifications Needed

These were identified by cross-referencing the Excel spec against the actual DB models. All are implementation-blockers or will produce wrong behaviour if assumed.

---

### REMINDER SYSTEM

**R1 — Cron Timing Conflict**
The cron runs at 8 AM IST. The spec says T-7 and D+3 at 9 AM, Due Date and Hygiene at 10 AM. With one cron run we can't send at two different times.
- Option A: Send everything at 8 AM IST, ignore the 9/10 AM distinction (simplest)
- Option B: Two cron runs — one at 9 AM IST, one at 10 AM IST (2 GitHub Actions schedules)
- Option C: Keep single 8 AM cron, queue Due Date messages internally and delay send by 2 hours (complex)

**R2 — Food Order Reminder: No Structured Pack Size Data**
`diet_items` table has: `label`, `detail` (free text like "280g x 2/day"), `type`. It has **no** `pack_size_g` or `daily_portion_g` columns. The Excel says reorder trigger = `pack_size ÷ daily_portion = days remaining, fire at 7 days`.
- Option A: Add `pack_size_g`, `daily_portion_g`, `brand` columns to `diet_items` (new migration + frontend input)
- Option B: Parse `detail` free text with regex/GPT to extract quantities
- Option C: Skip Food Order reminder in v1 — no structured data to calculate from

**R3 — Supplement Order Reminder: Same Data Gap**
`diet_items` where `type = 'supplement'` also has no `units_in_pack` or `doses_per_day`. Same problem as R2.
- Same options as R2

**R4 — Chronic Medicine Reminder: Data Source Confirmed**
`condition_medications.refill_due_date` (Date, nullable) exists — this can drive the T-7 reminder directly without calculation. No question here, just confirming: **Chronic Medicine reminders read from `condition_medications.refill_due_date`**. Agree?

**R5 — Vet Follow-up Reminder: What Table Drives This?**
The spec says "date from document or manual entry." There is no dedicated `vet_followup` table. Possible sources:
- `condition_monitoring.next_due_date` (monitoring tasks per condition)
- A custom `preventive_record` (user-created item)
- A new table
Which source should the Vet Follow-up reminder read from?

**R6 — [vetName] Variable: Which Contact to Use?**
A pet can have multiple contacts with `role = 'veterinarian'`. The `[vetName]` variable in the reminder message needs exactly one name.
- Use the most recently created veterinarian contact?
- Use the one linked to the most recent document?
- Use a generic "your vet" if more than one exists or none found?

**R7 — Vaccine List: One Record or Multiple?**
The Excel says `vaccineList = "filtered to due vaccines only, joined with · separator"` (e.g., "DHPPi · Rabies"). There are separate entries in `preventive_master` for each vaccine (DHPPi, Rabies, Kennel Cough, CCV etc.). Does each vaccine have its own `preventive_record` row per pet, allowing individual due-date tracking? Or is there a combined "Vaccines" record?

**R8 — Hygiene Reminder: Combined or Per-Item?**
`hygiene_preferences` has separate rows: `bath-nail` (Bath, brush & nail trim) and `ear-clean` (Ear Cleaning). Each has its own `reminder` boolean toggle.
The Excel says "single combined reminder covers Bath & Brush, Nail Trim and Ear Cleaning."
- Send 1 message combining all hygiene items whose `reminder = True`?
- Or send a separate message per hygiene item that has `reminder = True`?
Also: `last_done` is stored as a formatted string (DD/MM/YYYY), not a Date — the reminder engine will need to parse this string to calculate due dates.

**R9 — "Ignored" Definition for 3-Strike Monthly Fallback**
The spec: "3 ignored at same level → drop to monthly only." What counts as ignored?
- Option A: No button tapped within 24 hours of sending
- Option B: Specifically no "Done — Log It" tapped (snooze counts as engagement, not ignored)
- Option C: No inbound reply of any kind within 24 hours

**R10 — Blood Checkup First-Time Trigger**
The spec: "Annual / First nudge within 1 month of onboarding if never done." If a pet has no blood checkup record at all (`lastDone = null`), when does the first T-7 reminder fire?
- At O+30 (1 month after onboarding)?
- At a calculated `next_due_date = onboarding_date + 30 days`?
This needs OQ1 (what is O) resolved first, but also needs a decision on how to create this initial reminder record.

**R11 — Snooze Duration Per Item Type**
Current code uses a fixed 7-day snooze (`REMINDER_SNOOZE_7`) for all reminders. The spec says "backend handles snooze duration per item type." What are the snooze durations?
- Vaccines: ? days
- Deworming: ? days
- Flea & Tick: ? days
- Food Order: ? days (food is urgent — 7 days is too long)
- Supplement: ? days
- Chronic Medicine: ? days
- Vet Follow-up: ? days
- Hygiene: ? days

**R12 — "Done — Log It" Button: New or Existing Handler?**
Current code handles `REMINDER_DONE` (updates `last_done_date`, recalculates `next_due_date`, marks reminder completed). The new spec also has `REMINDER_DONE` semantics but for new reminder categories (Food Order, Supplement, Medicine, Vet Follow-up, Hygiene). Does the existing `REMINDER_DONE` handler in `reminder_response.py` work for all new categories, or do some need different post-done logic (e.g., Food Order done = restock confirmed, no new `next_due_date` recalculation)?

**R13 — "Order Now" Button: What Does Tapping Do?**
Several reminder categories (Deworming, Flea & Tick, Food, Supplement, Medicine) have an "Order Now" CTA. What happens when a user taps this?
- Option A: Triggers the existing agentic order flow (`agentic_order.py`)
- Option B: Sends a pre-built product link / static reply
- Option C: Launches a WhatsApp flow (separate Meta product)

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
**This is the single biggest template design decision in the entire plan.**

**N2 — Breeds Not in the Message Library**
The Excel defines messages for ~15 specific breeds (Golden Retriever, Lab, GSD, Beagle, Shih Tzu, Pomeranian, Rottweiler, Husky, Indian dog, Dachshund, French Bulldog, Samoyed, Shiba Inu, Poodle, Bernese Mountain Dog). Cats and all other breeds have no defined messages.
- What happens when a Level 1 user's pet is a Cocker Spaniel, Persian cat, or unlisted breed?
- Use nearest known breed? Use a generic message (no breed name)? Skip nudge that slot?

**N3 — Value Add: Missing Messages for O+20 and O+30 (Level 0)**
The Excel's Value Add sheet defines 3 messages for Level 0 (O+1, O+5, O+10) but the schedule has 5 slots (O+1, O+5, O+10, O+20, O+30).
- What goes at O+20 and O+30 for Level 0? Cycle messages 1–3? Use Engagement Only? Use a generic fallback?

**N4 — After O+30: Which Message Type at 30-Day Intervals?**
Both Level 0 and Level 1 drop to "1 message every 30 days if no engagement" after O+30. Which message type?
- Continue cycling Value Add / Engagement Only messages from the library?
- Switch to a fixed re-engagement message?

**N5 — "AI to Continue On-Boarding Flow If Customer Engages"**
The Excel states: when a Level 0/1 user replies to a nudge, "AI to continue on-boarding information flow if customer engages." What is this?
- Option A: Route to existing `agentic_onboarding.py` (LLM-driven onboarding conversation)
- Option B: A new lightweight reply handler that asks for the next missing field
- Option C: The existing `message_router.py` general handler (no special treatment)

**N6 — Multi-Pet Users: Weekly Cap Scope**
`nudge_engagement` tracks per `(user_id, pet_id)`. The 2-nudge weekly cap — is it:
- **Per pet**: each pet can receive 2 nudges/week independently (user with 3 pets = max 6 nudges/week)
- **Per user**: across all pets combined, max 2 nudges/week total (user with 3 pets = still only 2 nudges/week)

**N7 — Level Transition: What Happens Mid-Sequence?**
A Level 1 user is at O+5 (just received Engagement Only nudge). They upload a vaccine record → become Level 2.
- Option A: Immediately switch to Level 2 Breed+Data sequence from slot 1
- Option B: Finish the current O+N sequence (next slot = O+10 Value Add), then switch to Level 2 after O+30
- Option C: Switch to Level 2 at the next scheduled nudge slot, starting from slot 1

**N8 — Dashboard Visit Tracking: Not Implemented**
`dashboard_tokens` has no `last_visited_at` column. The spec says level is recalculated "on every trigger event including dashboard visit" and the 48hr engagement gap checks this. Dashboard visits are currently untracked.
- Option A: Add `last_visited_at` to `dashboard_tokens`, update on every `GET /dashboard/{token}` call
- Option B: Add `last_dashboard_visit` to `users` table
- Option C: Ignore dashboard visits for engagement tracking — only count WA message replies and uploads

**N9 — "Check Topic of Last Engagement" for Level 2 Re-Sequencing**
Rule 4 in Level 2 communication rules: "If any engagement on dashboard/chat/upload by user, see what the engagement topic was and re-prioritize next nudge accordingly."
- How do we detect "topic" from a WA reply? By button payload (REMINDER_DONE for vaccines = user is engaged with health)?
- Or from upload content (GPT extracted a deworming record = next nudge should skip deworming)?
- This requires defining what "topic detection" means in code — rule-based or GPT?

---

### SCHEMA / INFRA

**S1 — nudge_message_library in clear_database.sql**
The user had `clear_database.sql` open. It currently skips `nudge_config` and `preventive_master` (reference data). Should `nudge_message_library` (seeded content from Excel) also be excluded from the clear script, like `nudge_config`?

**S2 — Reminder Unique Constraint Change**
Current constraint: `UNIQUE(preventive_record_id, next_due_date)`. With 4 stages (t7, due, d3, overdue_insight), two reminders for the same record on the same date but different stages would violate this. Constraint must become `UNIQUE(preventive_record_id, next_due_date, stage)`. Confirm?

**S3 — Existing Reminder Rows Migration**
There are existing rows in the `reminders` table (current production data). When we add the `stage` column with default `'t7'`, existing rows will get `stage = 't7'` which is incorrect (they were already sent as "due" or "overdue"). How should existing rows be handled on migration?
- Set existing sent rows to `stage = 'due'` (closest to current behaviour)?
- Leave as `t7` (accept data inaccuracy in historical rows)?

---

## Verification
1. POST `/internal/run-reminder-engine` with X-ADMIN-KEY; test pet with `next_due_date = today + 7` → `reminders.stage = t7`
2. Advance 7 days → `stage = due`, sent at 10am via `petcircle_reminder_due_v1`
3. Advance 3 more days → D+3 check-in row created
4. Level 1 user (breed only) → O+1 Value Add sent; `sequence_position = 1`
5. Level 0 user (no data) → O+1 static Value Add sent
6. Level 2 user (vaccine record) → Breed+Data nudge for Vaccination sent
7. Pet with reminder today → no nudge sent for that user
8. 2 nudges already sent this week → no nudge sent until next weekly window
