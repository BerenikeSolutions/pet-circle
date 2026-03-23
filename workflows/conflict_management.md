# Workflow: Conflict Management

This document covers two related flows: active conflict resolution (user-driven) and expired conflict auto-resolution (scheduled).

---

## Part 1: Handle Conflict

### Objective

When GPT-extracted preventive data conflicts with an existing record, present the user with a clear choice and resolve the conflict based on their decision. If no response is received within 5 days, auto-resolve by keeping the existing record.

### Trigger

The conflict engine detects a date discrepancy between a newly extracted preventive event and an existing record for the same pet and preventive type.

### Required Inputs

- Pet ID
- Preventive type (e.g., Rabies vaccine)
- Existing record details (date, source)
- New extracted details (date, source document)

### Steps

1. **Create conflict record**
   - Insert into `conflicts` table with:
     - Pet ID, preventive type
     - Existing date and record ID
     - New extracted date and document ID
     - Status: `PENDING`, created timestamp
   - Service: `conflict_engine.py`

2. **Send interactive message to user**
   - Send WhatsApp interactive message with two buttons:
     - `CONFLICT_USE_NEW` — "Use new date"
     - `CONFLICT_KEEP_EXISTING` — "Keep existing date"
   - Message body includes: pet name, preventive type, both dates clearly labeled.
   - Button payload IDs must not be hardcoded in service logic; load from constants.
   - Service: `whatsapp_sender.py`

3. **Wait for user response**
   - On button click, webhook receives the payload ID.
   - Match payload to the pending conflict for this user/pet.

4. **Resolve based on user choice**
   - **USE_NEW:** Update `preventive_records` with the new date. Recalculate next due date. Mark conflict as `RESOLVED_USE_NEW`.
   - **KEEP_EXISTING:** Keep current record unchanged. Mark conflict as `RESOLVED_KEEP_EXISTING`.
   - Update conflict record with resolution timestamp and method.
   - Service: `conflict_engine.py`, `preventive_calculator.py`

5. **Confirm resolution**
   - Send WhatsApp message confirming which date was kept.
   - Service: `whatsapp_sender.py`

6. **Log activity**
   - Log the conflict creation, user decision, and resolution in `message_logs`.
   - Service: `conflict_engine.py`

### Expected Output

- `conflicts` table record created and eventually resolved.
- `preventive_records` updated (if USE_NEW chosen).
- User receives confirmation of resolution.

### Edge Cases

- **No response within 5 days:** Auto-resolve with `KEEP_EXISTING`. Log as `AUTO_RESOLVED_EXPIRY`. Handled by Part 2 below.
- **User sends text instead of clicking button:** Re-send the interactive message. Do not parse free text as a decision.
- **Multiple pending conflicts for same user:** Each conflict is independent. Present and resolve separately.
- **Conflict for a pet that was deleted:** Mark conflict as `RESOLVED_PET_DELETED`. Do not send message.
- **WhatsApp delivery failure:** Retry once. If still fails, log and let expiry handle it.

---

## Part 2: Resolve Conflict Expiry

### Objective

Automatically resolve any pending conflicts that have exceeded the 5-day response window. Ensures no conflict remains unresolved indefinitely by defaulting to `KEEP_EXISTING`.

### Trigger

Daily scheduled job (runs alongside the reminder cron via GitHub Actions at 8 AM IST).

### Required Inputs

- Current date/time (IST)
- Conflicts table with `PENDING` status records

### Steps

1. **Query expired conflicts**
   - Select all records from `conflicts` table where:
     - Status is `PENDING`
     - Created timestamp is older than 5 days from now (strict: > 120 hours)
   - Service: `conflict_expiry.py`

2. **Auto-resolve each expired conflict**
   - For each expired conflict:
     - Set status to `AUTO_RESOLVED_EXPIRY`
     - Set resolution to `KEEP_EXISTING`
     - Set resolution timestamp to now
     - Do not modify the existing preventive record
     - Discard the new extracted data (never applied)
   - Use explicit database transactions. Each conflict resolved independently.
   - Service: `conflict_expiry.py`

3. **Log each resolution**
   - For each auto-resolved conflict, log: conflict ID, pet ID, preventive type, resolution method (`AUTO_RESOLVED_EXPIRY`), timestamp.
   - Logging must not block the resolution loop.
   - Service: `conflict_expiry.py`

4. **Notify user (optional)**
   - Send a WhatsApp message informing the user that a conflict was auto-resolved.
   - Include: pet name, preventive type, the date that was kept.
   - If send fails, log and continue. Do not retry.
   - Service: `whatsapp_sender.py`

### Expected Output

- All conflicts older than 5 days resolved as `AUTO_RESOLVED_EXPIRY` with `KEEP_EXISTING`.
- Existing preventive records unchanged.
- Resolution logged for each conflict.
- User optionally notified.

### Edge Cases

- **No expired conflicts:** Job completes with zero actions. Log that the run executed with no results.
- **Conflict's pet was deleted:** Mark conflict as `RESOLVED_PET_DELETED`. Do not notify.
- **DB transaction failure on one conflict:** Log error, continue processing remaining conflicts. Do not halt batch.
- **WhatsApp notification fails:** Log failure. Resolution stands regardless of notification delivery.
- **Cron fires multiple times:** Resolved conflicts have status `AUTO_RESOLVED_EXPIRY` and are not selected again. Idempotent.
- **Conflict created exactly 5 days ago:** Use strict "older than 5 days" (> 120 hours from creation). Borderline cases wait until the next run.
