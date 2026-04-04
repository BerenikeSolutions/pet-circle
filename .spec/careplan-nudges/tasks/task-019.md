---
task: 019
feature: careplan-nudges
status: pending
depends_on: []
---

# Task 019: Backend — Nudge Scheduler Global Communication Rules

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development, /python-patterns
Commands: /verify, /task-handoff

---

## Objective

Add three missing guards to the nudge scheduler: (1) a 7-day rolling frequency cap (max 2 nudges/week per user, excluding reminders), (2) a 72-hour inactivity trigger that fires nudges for silent users even outside the O+N schedule, and (3) a same-day conflict check against *scheduled* reminders (not just sent ones). Also add the corresponding constants to `core/constants.py` and log skip reasons for all blocked nudges.

---

## Codebase Context

### Key Code Snippets

```python
# [Main nudge loop — from backend/app/services/nudge_scheduler.py:86-149]
for user in users:
    try:
        pets = (
            db.query(Pet)
            .filter(Pet.user_id == user.id, Pet.is_deleted == False)
            .all()
        )
        if not pets:
            continue
        primary_pet = pets[0]
        level = calculate_nudge_level(db, user, primary_pet)

        # --- Guard: reminder sent today? ---
        reminder_today = _reminder_sent_today(db, user.id, today)
        if reminder_today:
            skipped += 1
            continue

        # --- Guard: nudge sent recently (48h gap)? ---
        last_nudge_at = _last_nudge_sent_at(db, user.id)
        if last_nudge_at:
            gap = datetime.utcnow() - last_nudge_at
            if gap.total_seconds() < NUDGE_MIN_GAP_HOURS * 3600:
                skipped += 1
                continue

        # --- Detect level-up and reset slot counter ---
        _handle_level_transition(db, user, level)

        # --- Select next message ---
        message_info = _select_next_message(db, user, primary_pet, level, today)
        if not message_info:
            skipped += 1
            continue

        template_key, vars_ = message_info
        if not template_key:
            skipped += 1
            continue

        # --- Send WhatsApp template ---
        plaintext_mobile = decrypt_field(user.mobile_number)
        result = await send_template_message(
            db=db, to_number=plaintext_mobile,
            template_name=template_key, parameters=vars_,
        )
        if result:
            _log_nudge_delivery(db, user, primary_pet, template_key, level, template_params=vars_)
            sent += 1
        else:
            failed += 1
    except Exception:
        logger.exception("Nudge scheduler failed for user %s", str(user.id))
```

```python
# [Existing _last_nudge_sent_at helper — from nudge_scheduler.py:748-759]
def _last_nudge_sent_at(db: Session, user_id: UUID) -> datetime | None:
    log = (
        db.query(NudgeDeliveryLog)
        .filter(NudgeDeliveryLog.user_id == user_id, NudgeDeliveryLog.wa_status == "sent")
        .order_by(NudgeDeliveryLog.sent_at.desc())
        .first()
    )
    return log.sent_at if log else None
```

```python
# [Existing _reminder_sent_today — from nudge_scheduler.py:730-745]
# Checks if a reminder was SENT today. Does NOT check scheduled (pending) reminders.
```

```python
# [Constants file — from backend/app/core/constants.py:0-30]
# Already has: MAX_PETS_PER_USER, DOC_UPLOAD_WINDOW_SECONDS, file upload limits
# Needs: NUDGE_MAX_PER_WEEK, NUDGE_INACTIVITY_TRIGGER_HOURS
```

### Key Patterns in Use
- **Guard pattern:** Each guard checks a condition, increments `skipped`, and `continue`s to next user.
- **DB queries:** Direct SQLAlchemy queries against models (NudgeDeliveryLog, Reminder, MessageLog).
- **Timezone:** All date checks use IST (`get_today_ist()` helper).
- **Logging:** `logger.info()`/`logger.warning()` with structured params.

### Architecture Decisions Affecting This Task
- ADR-2 (Rolling Window): Use a rolling 7-day window (not calendar week) for the frequency cap. Query `NudgeDeliveryLog` for `sent_at >= now - 7 days`.

---

## Handoff from Previous Task
> This is the first task in the careplan-nudges feature.

**Files changed by previous task:** _(none)_
**Decisions made:** _(none)_
**Context for this task:** _(none)_
**Open questions left:** _(none)_

---

## Implementation Steps

1. **Add constants to `backend/app/core/constants.py`:**
   - `NUDGE_MAX_PER_WEEK: int = 2`
   - `NUDGE_INACTIVITY_TRIGGER_HOURS: int = 72`

2. **Add `_count_nudges_in_window()` to `nudge_scheduler.py`:**
   - Query `NudgeDeliveryLog` for `user_id` where `wa_status == "sent"` and `sent_at >= (now - 7 days)`.
   - Return count.

3. **Add `_has_reminder_scheduled_today()` to `nudge_scheduler.py`:**
   - Query `reminders` table for pending/scheduled reminders where `next_due_date == today` for any of the user's pets.
   - This complements the existing `_reminder_sent_today()` — together they prevent same-day nudge+reminder.

4. **Add `_check_inactivity_trigger()` to `nudge_scheduler.py`:**
   - Query `message_logs` for the user's most recent activity timestamp (sent or received message).
   - Return `True` if the gap exceeds `NUDGE_INACTIVITY_TRIGGER_HOURS`.

5. **Integrate guards into main loop (lines 86-149):**
   - After existing reminder-today guard, add: 7-day cap check (`_count_nudges_in_window() >= NUDGE_MAX_PER_WEEK` → skip).
   - After existing 48hr gap guard, add: scheduled-reminder-today check (`_has_reminder_scheduled_today()` → skip).
   - Add inactivity trigger integration: if O+N schedule says "not today" but `_check_inactivity_trigger()` returns True and all guards pass, select next undelivered slot message.
   - Log skip reason for each blocked nudge (e.g., `logger.info("Nudge skipped for user %s: reason=%s", user.id, "7day_cap")`).

6. **Write unit tests:**
   - Test 7-day cap blocks when 2 nudges exist in the window.
   - Test inactivity trigger fires for 72hr-silent users.
   - Test no nudge sent on same day as scheduled reminder.
   - Test skip reasons are logged correctly.

---

## Acceptance Criteria
- [ ] `NUDGE_MAX_PER_WEEK = 2` and `NUDGE_INACTIVITY_TRIGGER_HOURS = 72` in `core/constants.py`
- [ ] 7-day cap blocks when 2 nudges exist in rolling window
- [ ] Inactivity trigger fires for 72hr-silent users
- [ ] No nudge sent on same day as a reminder (sent OR scheduled)
- [ ] Skip reasons logged for every blocked nudge
- [ ] Unit tests pass
- [ ] Existing tests still pass (`python -m pytest`)
