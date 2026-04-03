# Workflow: Onboard Pet Parent

## Objective

Register a new pet parent and their first pet via WhatsApp conversation. Capture consent, collect pet details, create database records, generate a dashboard token, and confirm onboarding.

## Trigger

User sends their **first message** to the PetCircle WhatsApp number. The system detects no existing user record for the incoming phone number.

## Required Inputs

- User's WhatsApp phone number (from webhook payload)
- User's name (collected via conversation)
- Consent acknowledgment (implicit on first inbound message)
- Pet details:
  - Name
  - Species (dog / cat)
  - Breed
  - Date of birth (accepted formats: DD/MM/YYYY, DD-MM-YYYY, 12 March 2024, ISO)
  - Weight (kg)

## Steps

1. **Detect new user**
   - Incoming message arrives at webhook.
   - Query `users` table by phone number.
   - If no record exists, begin onboarding flow.
   - Service: `onboarding.py`

2. **Capture consent (implicit)**
   - Treat the first inbound WhatsApp message as consent for Phase 1 onboarding.
   - Set `users.consent_given=True` when creating the user.
   - Service: `onboarding.py`

3. **Create user record**
   - Insert into `users` table with phone number, onboarding defaults, and consent status.
   - Service: `onboarding.py`

4. **Collect pet details**
   - Prompt for pet name, species, breed, DOB, and weight through sequential messages.
   - Validate each input as received.
   - Parse date into `YYYY-MM-DD` format for storage.
   - Service: `onboarding.py`, `whatsapp_sender.py`

5. **Create pet record**
   - Insert into `pets` table linked to the user.
   - Enforce maximum of 5 pets per user.
   - Service: `onboarding.py`

6. **Generate dashboard token**
   - Create a 128-bit random token, store in `dashboard_tokens` table.
   - Token must be unique and revocable (soft delete only).
   - If generation fails during transition, continue onboarding and recover before/at finalization.
   - Service: `onboarding.py`

7. **Send onboarding complete message**
   - Send deterministic care-plan completion message with dashboard link.
   - If document extraction is still pending, defer the care-plan link and send it after extraction completes.
   - Service: `whatsapp_sender.py`

8. **Log activity**
   - Log all sent/received messages in `message_logs` table.
   - Service: `onboarding.py`

## Expected Output

- `users` record created with `consent_given=True`.
- `pets` record created with validated details.
- `dashboard_tokens` record created.
- User receives deterministic onboarding completion message with dashboard link.

## Edge Cases

- **Consent decline branch:** Not used in deterministic Phase 1 (implicit consent model).
- **User already exists:** Skip onboarding. Route to normal message handling.
- **Invalid date format:** Re-prompt with accepted formats. Do not guess.
- **Pet limit reached (5):** Inform user that maximum pets have been registered. Do not create another.
- **Duplicate phone number:** Reject creation. Return existing user context.
- **Message delivery failure:** Log failure. Retry once via `whatsapp_sender.py`.
- **Incomplete onboarding (user stops responding):** Conversation state persists in DB. Resume on next message.
