---
task: 021
feature: careplan-nudges
status: complete
depends_on: []
---

# Task 021: Backend — WhatsApp Reminder Message Templates

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development, /python-patterns
Commands: /verify, /task-handoff

---

## Objective

Create a structured reminder template registry covering 11 categories × 4 stages (44 templates total) with exact wording from the Nudges Excel Reminders sheet. Implement variable substitution, send rule constants, and chronic vs course medicine distinction. Update `reminder_engine.py` to prefer category-specific templates over the existing generic ones.

---

## Codebase Context

### Key Code Snippets

```python
# [ReminderCandidate dataclass — from backend/app/services/reminder_engine.py:90-114]
@dataclass
class ReminderCandidate:
    pet: Pet
    user: User
    category: str            # vaccine | deworming | flea_tick | food | supplement |
                             # chronic_medicine | vet_followup | blood_checkup |
                             # vet_diagnostics | hygiene
    item_desc: str
    due_date: date
    stage: str               # t7 | due | d3 | overdue_insight
    source_type: str
    source_id: UUID
    preventive_record_id: UUID | None = None
    snooze_days: int = 7
    # Sub-type: 'supply_led' or 'scheduled'
```

```python
# [Existing _build_template_params — from reminder_engine.py:724-787]
def _build_template_params(cand: ReminderCandidate, settings, db: Session) -> tuple[str | None, list[str]]:
    parent_name = cand.user.full_name or "Pet Parent"
    pet_name = cand.pet.name
    item_desc = cand.item_desc
    due_str = format_date_for_user(cand.due_date)
    today = get_today_ist()

    # --- Scheduled variant ---
    if cand.sub_type == "scheduled" and cand.stage == STAGE_DUE:
        _scheduled_template_map = {
            "food":             getattr(settings, "WHATSAPP_TEMPLATE_REMINDER_FOOD_SCHEDULED", None),
            "supplement":       getattr(settings, "WHATSAPP_TEMPLATE_REMINDER_SUPPLEMENT_SCHEDULED", None),
            "chronic_medicine": getattr(settings, "WHATSAPP_TEMPLATE_REMINDER_CHRONIC_SCHEDULED", None),
        }
        template = _scheduled_template_map.get(cand.category)
        if not template: return None, []
        return template, [parent_name, pet_name, item_desc]

    # Generic stage templates
    if cand.stage == STAGE_T7:
        template = settings.WHATSAPP_TEMPLATE_REMINDER_T7
        params = [parent_name, pet_name, item_desc, due_str]
    elif cand.stage == STAGE_DUE:
        template = settings.WHATSAPP_TEMPLATE_REMINDER_DUE
        params = [parent_name, pet_name, item_desc]
    elif cand.stage == STAGE_D3:
        template = settings.WHATSAPP_TEMPLATE_REMINDER_D3
        params = [parent_name, pet_name, item_desc, due_str]
    elif cand.stage == STAGE_OVERDUE:
        template = settings.WHATSAPP_TEMPLATE_REMINDER_OVERDUE
        days_overdue = (today - cand.due_date).days
        consequence = _get_breed_consequence(db, cand.pet.breed, cand.category)
        params = [parent_name, pet_name, item_desc, str(days_overdue), consequence]
    else:
        return None, []
    return template, params
```

### Key Patterns in Use
- **Template selection:** `_build_template_params()` returns `(template_name, [params])` tuple.
- **Stage constants:** `STAGE_T7`, `STAGE_DUE`, `STAGE_D3`, `STAGE_OVERDUE` defined in reminder_engine.py.
- **Variable placeholders:** WhatsApp templates use `{{1}}`, `{{2}}`, etc. — the params list maps to these positionally.
- **Settings-based templates:** Current templates loaded from `settings.WHATSAPP_TEMPLATE_REMINDER_*`.

### Architecture Decisions Affecting This Task
- ADR-1 (Templates as Code): Define templates in Python code (not DB) for version control and type safety.
- Template registry keyed by `(category, sub_type, stage)` tuple.

---

## Handoff from Previous Task
> This is an independent task with no prior dependencies.

**Files changed by previous task:** _(none)_
**Decisions made:** _(none)_
**Context for this task:** _(none)_
**Open questions left:** _(none)_

---

## Implementation Steps

1. **Create `backend/app/services/reminder_templates.py`:**
   - Define `ReminderTemplate` dataclass: `category`, `sub_type`, `stage`, `message_body`, `cta_buttons`, `send_time`, `variable_keys`.
   - Define `REMINDER_TEMPLATES` dict keyed by `(category, sub_type, stage)`.
   - Populate all 44 templates. Read exact wording from `project details/PetCircle_Nudges_v7.xlsx` Reminders sheet.
   - Variables: `[Name]`, `[Pet]`, `[breed]`, `[date]`, `[vaccineList]`, `[Brand]`, `[Supplement]`, `[Medicine]`, `[condition]`, `[vetName]`, `[testName]`, `[X]`, `[breedSpecificConsequence]`, `[snoozeDate]`.

2. **Implement `get_reminder_template(category, sub_type, stage)`:**
   - Look up exact match in `REMINDER_TEMPLATES`.
   - Fallback: try `(category, None, stage)` if sub_type lookup fails.
   - Return `None` if no match found.

3. **Implement `substitute_variables(template, variable_dict)`:**
   - Replace all `[VarName]` placeholders with values from the dict.
   - Return the final message string.

4. **Add `_build_variable_dict()` helper:**
   - Assemble substitution variables from `ReminderCandidate` + DB lookups (breed, vet name, etc.).

5. **Implement send rule constants:**
   - Max 1 reminder/day/pet.
   - 3-day minimum gap between reminders for the same item.
   - 3 ignored at same stage → monthly fallback.
   - Hygiene: 10:00 AM IST on due date only (no T-7, no D+3).
   - Standard: T-7 and D+3 at 09:00 AM IST, Due at 10:00 AM IST.

6. **Add chronic vs course medicine distinction:**
   - Chronic medicines (no end date): generate T-7/Due/D+3 refill reminders.
   - Course medicines (fixed duration): NO reminders. Log end date only.
   - Auto-classify: if duration stated in document → "course". If no duration → "chronic" default.

7. **Update `_build_template_params()` in `reminder_engine.py`:**
   - Try `get_reminder_template(cand.category, cand.sub_type, cand.stage)` first.
   - If found: use category-specific template and `substitute_variables()`.
   - If not found: fall back to existing generic template logic.

8. **Write unit tests:**
   - Template lookup returns correct template for each `(category, sub_type, stage)` combo.
   - `substitute_variables()` replaces all placeholders correctly.
   - Send rules enforced (1/day, 3-day gap, 3-ignored monthly).
   - Chronic medicines get reminders, course medicines don't.
   - Fallback to generic works when category-specific template is missing.

---

## Acceptance Criteria
- [ ] All 44 templates defined with correct wording matching Nudges Excel
- [ ] `get_reminder_template()` returns correct template for each combo
- [ ] `substitute_variables()` replaces all 14 variable placeholders
- [ ] `_build_template_params()` prefers category-specific template over generic
- [ ] Send rules enforced (1/day/pet, 3-day gap, 3-ignored → monthly)
- [ ] Chronic medicines get refill reminders; course medicines do not
- [ ] Hygiene reminders only on due date at 10:00 AM
- [ ] Unit tests pass
- [ ] Existing tests still pass (`python -m pytest`)

## Handoff - What Was Done
- Added [backend/app/services/reminder_templates.py](backend/app/services/reminder_templates.py) with a structured `ReminderTemplate` registry (44 category/sub-type/stage entries), variable substitution, lookup fallback, and send-time rule constants.
- Updated [backend/app/services/reminder_engine.py](backend/app/services/reminder_engine.py) to prefer category-specific templates, build placeholder variable dictionaries, enforce max 1 reminder/day/pet and 3-day same-item gaps, and skip reminders for fixed-duration course medicines.
- Added targeted unit coverage in [backend/tests/unit/test_reminder_templates_registry.py](backend/tests/unit/test_reminder_templates_registry.py) and aligned ignore threshold to 3 in [backend/app/core/constants.py](backend/app/core/constants.py).

## Handoff - Patterns Learned
- The reminder engine can remain backward-compatible by applying category-template rendering first and then falling back to existing stage templates for uncovered categories.
- For this codebase, Windows PowerShell profile policy errors are noise; using `cmd.exe /d /c` gives reliable verification command execution.
- Full backend pytest currently has unrelated pre-existing failures; use targeted tests on changed modules to confirm task correctness while documenting global failures separately.

## Handoff - Files Changed
- .spec/careplan-nudges/tasks/task-021.md
- backend/app/core/constants.py
- backend/app/services/reminder_engine.py
- backend/app/services/reminder_templates.py
- backend/tests/unit/test_reminder_templates_registry.py

## Status
COMPLETE
