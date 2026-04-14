# PetCircle — Webhook & Document Processing Architecture

## Overview

Every inbound WhatsApp message flows through a strict two-layer pipeline:

1. **Webhook Layer** (`app/routers/webhook.py`) — receive, verify, deduplicate, dispatch. No business logic.
2. **Background Processing Layer** — all real work runs in `asyncio` background tasks so the webhook always returns `200 OK` immediately to Meta.

---

## Full Flow Diagram

```
Meta WhatsApp Cloud API
        │
        ▼
POST /webhook/whatsapp
        │
        ├─ Signature verification (HMAC-SHA256)
        ├─ Deduplication check (1h cache)
        ├─ Rate limit check (20 msg/min per number)
        ├─ Log to message_logs table
        └─ Return 200 OK immediately
                │
                ▼
        asyncio.create_task(_safe_process_message)
                │
                ▼
        Entry-point semaphore (max 20 concurrent)
        Queue depth check (max 50 queued)
                │
                ▼
        _process_message_background
                │
                ├─ Open fresh DB session
                ├─ 120s timeout
                └─ route_message(db, message_data)
                        │
                        ├─ Text message → onboarding / query engine
                        ├─ Button press → reminder / conflict / nudge handler
                        └─ Image / Document → _handle_media → document pipeline
```

---

## Layer 1: Webhook Reception (`webhook.py`)

### Endpoint: `POST /webhook/whatsapp`

**What it does (in order):**

1. **Signature Verification**
   - Validates `X-Hub-Signature-256` header against request body using HMAC-SHA256
   - Rejects immediately with `403` if invalid
   - Source: `app/core/security.py: verify_webhook_signature`

2. **Message Deduplication**
   - In-memory `OrderedDict` cache (`_DEDUP_CACHE`) keyed by `message_id`
   - TTL: 1 hour (Meta may retry webhooks for hours after failures)
   - Max size: 2000 entries (LRU eviction)
   - Duplicate messages are silently skipped

3. **Rate Limiting**
   - Max 20 messages per minute per phone number (rolling window)
   - Source: `app/core/rate_limiter.py`

4. **Payload Parsing**
   - Extracts: `from_number`, `message_id`, `type`, `text`, `media_id`, `filename`, `caption`, `button_payload`, `timestamp`
   - Handles all WhatsApp message types: `text`, `image`, `document`, `button`

5. **Message Logging**
   - All incoming payloads written to `message_logs` table unconditionally
   - Sanitized before logging (PII masked)

6. **Return `200 OK`**
   - Always returned before any background work begins
   - Prevents Meta from timing out and triggering phantom retries

### Debounce Buffer (Text Messages Only)

Users often send a single thought across several rapid messages. Text messages are held in a per-user buffer and flushed as **one combined message** after an idle window:

| State | Debounce Window |
|-------|----------------|
| Normal states | 1.5s |
| `awaiting_preventive`, `awaiting_meal_details` | 3.0s (users type more) |

Buttons and media **bypass the buffer** — they are discrete, deliberate actions and processed immediately.

---

## Layer 2: Entry-Point Concurrency Control (`webhook.py`)

### `_safe_process_message(message_data)`

Every `asyncio.create_task(...)` call goes through this wrapper — **no exceptions**.

```
New message task created
        │
        ▼
_message_queue_depth >= MAX_QUEUED_MESSAGES (50)?
        │
       YES → Send "We're busy, try again" message → return
        │
       NO
        │
        ▼
_message_queue_depth += 1
        │
        ▼
async with _message_processing_semaphore  (max 20 concurrent)
        │
        ▼
await _process_message_background(message_data)
        │
        ▼
finally: _message_queue_depth -= 1  ← always runs
```

**Constants:**

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_CONCURRENT_MESSAGE_PROCESSING` | 20 | Max active background tasks |
| `MAX_QUEUED_MESSAGES` | 50 | Max tasks waiting on semaphore before rejection |

**Why this matters:** Without this gate, 200 simultaneous messages create 200 concurrent coroutines all immediately opening a DB session, exhausting the pool ceiling of 25 connections.

---

## Layer 3: Background Message Processing (`webhook.py: _process_message_background`)

Runs inside `_safe_process_message` after acquiring the entry-point semaphore.

- Opens its own **fresh DB session** (`get_fresh_session()`) — request-scoped session is closed after webhook returns
- Applies a **120s timeout** via `asyncio.wait_for`
- **Retries once** on `OperationalError` (SSL connection drop between checkout and first query) with a fresh session
- On `TimeoutError` or unhandled exception: sends user a friendly error message, never crashes

---

## Layer 4: Message Router (`message_router.py: route_message`)

Routes the message to the correct handler based on type and user state:

```
route_message
    │
    ├─ User not in DB → create pending user → start onboarding
    ├─ onboarding_state != 'complete' → continue onboarding flow
    ├─ Button payload (REMINDER_*) → reminder response handler
    ├─ Button payload (CONFLICT_*) → conflict resolution handler
    ├─ Button payload (NUDGE_*) → nudge handler
    ├─ Button payload (ORDER_*) → order flow handler
    ├─ Image / Document → _handle_media → document upload pipeline
    ├─ Text "add pet" → start new pet onboarding
    ├─ Text "dashboard" → send dashboard token link
    └─ Text (anything else) → query engine (GPT-4.1 pet health Q&A)
```

---

## Layer 5: Document Upload Pipeline

### Step 1: `_handle_media` — Pre-download Guards

Before any file is downloaded:

1. **Pet lookup** — find user's most recently active pet
2. **Ghost record prevention (primary dedup)** — check if `Document.source_wamid == message_id` already exists. One Document per WhatsApp message ID, regardless of filename or server restarts.
3. **Secondary dedup** — check by filename (last 24h) or `media_id` (embedded in file path)
4. **Batch limit check (in-memory)** — count uploads within the last 120s window. Max `MAX_DOCS_PER_SESSION` (5) per batch. Rejection message sent **once** per batch to avoid spamming.

### Step 2: Backpressure Check

```
_upload_queue_depth >= MAX_QUEUED_UPLOADS (30)?
    YES → pop from recent_uploads, send "try again" message, return
    NO  → _upload_queue_depth += 1
```

### Step 3: Upload Processing Semaphore

```
async with _upload_processing_semaphore  (max 15 concurrent)
```

Gates download + DB write work. Prevents 20 simultaneous uploads from holding 20 DB connections concurrently.

**Why separate from entry-point semaphore:** The entry-point semaphore (max 20) covers all message types. The upload semaphore (max 15) gives additional protection specifically for the expensive download+store work.

### Step 4: Media Download (`whatsapp_sender.py: download_whatsapp_media`)

Two-step HTTP process:

1. `GET https://graph.facebook.com/v21.0/{media_id}` → obtain CDN URL + MIME type
2. Stream file content from CDN URL in **8KB chunks**

**Streaming with size guard:**
```python
async with client.stream("GET", media_url, timeout=60.0) as response:
    async for chunk in response.aiter_bytes(8192):
        total_bytes += len(chunk)
        if total_bytes > MAX_UPLOAD_BYTES:
            # Abort — do not load the rest into memory
            return None
        buffer.write(chunk)
```

Files exceeding `MAX_UPLOAD_BYTES` (10MB) are **aborted mid-stream** — the full oversize file is never loaded into memory.

**Retry policy:** 3 attempts with exponential backoff (1s, 2s, 4s) + ±0.5s jitter to prevent thundering herd when multiple concurrent downloads fail simultaneously.

### Step 5: Validation (`document_upload.py`)

| Check | Rule | Error |
|-------|------|-------|
| File size | `<= MAX_UPLOAD_BYTES` (10MB) | `ValueError` |
| MIME type | `image/jpeg`, `image/png`, `application/pdf` only | `ValueError` |
| Daily limit | `<= MAX_UPLOADS_PER_PET_PER_DAY` (10) per pet | `ValueError` |

Daily limit counts only `pending` or `success` documents — failed extractions do not block re-uploads.

### Step 6: Content Hash Dedup

SHA-256 hash of raw file bytes computed before storage.

- If a document with the same hash already exists for this pet with `extraction_status IN ('success', 'partially_extracted')` → skip upload, return existing document
- Prevents processing the same file twice if user resends it

### Step 7: Storage (`storage_service.py`)

**Primary: GCP Cloud Storage**

- Credentials from `GCP_CREDENTIALS_JSON` (base64-encoded service account JSON)
- GCP client initialized once, cached at module level
- SDK calls run in `asyncio.run_in_executor()` to avoid blocking the event loop

**Fallback: Supabase Private Bucket**

- Triggered automatically if GCP is unavailable or misconfigured
- Supabase SDK calls also run in thread pool via `run_in_executor`
- No public URLs — files accessed only through authenticated API

**Path format:** `{user_id}/{pet_id}/{unix_timestamp}_{filename}`

Timestamp prefix prevents duplicate path conflicts when the same file is uploaded multiple times.

**`storage_backend` column** on the `documents` table records which backend holds each file, so downloads always route correctly.

### Step 8: Document Record Creation

```sql
INSERT INTO documents (
    pet_id, file_path, mime_type, document_name,
    extraction_status,   -- 'pending'
    source_wamid,        -- WhatsApp message ID for dedup
    storage_backend,     -- 'gcp' or 'supabase'
    content_hash         -- SHA-256 for content dedup
)
```

### Step 9: Batch Extraction Timer

After each successful upload, a **deferred batch extraction** timer is set/reset:

- Timer fires after `_EXTRACTION_DELAY_SECONDS` of no new uploads for this pet
- Each new upload **cancels and restarts** the timer (debounce)
- When the timer fires, all `pending` documents for the pet are extracted together in one pass

This prevents per-file GPT calls — a user sending 5 files in 10 seconds gets **one extraction run**, not five.

---

## Layer 6: GPT Extraction (`gpt_extraction.py`)

### Extraction Semaphore

```
async with _extraction_semaphore  (max 8 concurrent, shared: WhatsApp + Dashboard)
```

Both WhatsApp batch extraction and dashboard direct uploads use **the same semaphore** (`document_upload.get_extraction_semaphore()`), so they compete fairly for the DB pool budget. No per-path limits that could together exhaust the pool.

### Extraction Pipeline

```
pending documents for pet
        │
        ▼
For each document:
    1. Download file from storage (GCP or Supabase, routes by storage_backend column)
    2. Base64-encode content
    3. Build GPT prompt with medicine guide (loaded from product_medicines table)
    4. Call claude-opus-4-6 (temperature=0, max_tokens=6144)
    5. Parse + validate JSON response
    6. Normalize all dates to YYYY-MM-DD
    7. Route extracted data
```

**Retry policy:** 3 attempts (1s, 2s backoff). On final failure: `extraction_status = 'failed'`, log error, continue. Never crashes the application.

**Low confidence threshold:** `0.65` — documents below this score are flagged as `partially_extracted` for manual review.

### What GPT Extracts

| Category | Data extracted |
|----------|---------------|
| Preventive care | Vaccine dates, deworming dates, flea/tick treatment dates, medicine names |
| Weight | Weight readings with dates |
| Checkups | Vet visit dates and notes |
| Conditions | Diagnoses with onset date, severity, status |
| Medications | Name, dosage, frequency, start/end dates |
| Monitoring | Instructions (e.g. "check blood glucose weekly") |
| Diagnostic tests | Test name, result, reference range, date |
| Contacts | Vet name, clinic, phone |

### Conflict Detection

If extracted preventive date **differs** from an existing record for the same item:

1. `ConflictFlag` record created with `status = 'pending'`
2. User receives WhatsApp button message: "Keep existing date / Use new date"
3. User taps button → `resolve_conflict()` applies decision
4. **Auto-resolve:** Unresolved conflicts expire after 5 days → `KEEP_EXISTING`, logged

---

## Concurrency Architecture Summary

```
Webhook (POST /webhook/whatsapp)
        │
        ▼  [returns 200 immediately]
        │
asyncio.create_task(_safe_process_message)
        │
        ▼
┌─────────────────────────────────────────────┐
│  ENTRY-POINT GATE                           │
│  _message_processing_semaphore (max 20)     │
│  _message_queue_depth check (max 50)        │
└─────────────────────────────────────────────┘
        │
        ▼
_process_message_background (fresh DB session, 120s timeout)
        │
        └─ [document upload path only]
                │
                ▼
        ┌───────────────────────────────────────┐
        │  UPLOAD STAGE GATE                    │
        │  _upload_processing_semaphore (max 15)│
        │  _upload_queue_depth check (max 30)   │
        └───────────────────────────────────────┘
                │
                ▼
        Download → Validate → Store → Create DB record
                │
                ▼ [deferred, after batch settles]
        ┌───────────────────────────────────────┐
        │  EXTRACTION STAGE GATE                │
        │  _extraction_semaphore (max 8)        │
        │  shared: WhatsApp + Dashboard paths   │
        └───────────────────────────────────────┘
                │
                ▼
        GPT extraction → conflict check → DB write
```

### Constants Reference

| Constant | Value | File | Purpose |
|----------|-------|------|---------|
| `MAX_CONCURRENT_MESSAGE_PROCESSING` | 20 | constants.py | Entry-point semaphore |
| `MAX_QUEUED_MESSAGES` | 50 | constants.py | Entry-point queue depth cap |
| `MAX_CONCURRENT_UPLOAD_PROCESSING` | 15 | constants.py | Upload stage semaphore |
| `MAX_QUEUED_UPLOADS` | 30 | constants.py | Upload queue depth cap |
| `MAX_CONCURRENT_EXTRACTIONS` | 8 | constants.py | GPT extraction semaphore |
| `MAX_UPLOAD_BYTES` | 10MB | constants.py | Per-file size limit |
| `MAX_UPLOADS_PER_PET_PER_DAY` | 10 | constants.py | Daily upload limit |
| `MAX_DOCS_PER_SESSION` | 5 | constants.py | Per-batch upload limit |
| `EXTRACTION_MAX_AUTO_RETRIES` | 3 | constants.py | GPT retry attempts |
| `EXTRACTION_LOW_CONFIDENCE_THRESHOLD` | 0.65 | constants.py | Partial extraction flag |

---

## Failure Handling

| Failure | Behaviour |
|---------|-----------|
| Invalid signature | `403` — webhook rejected |
| Duplicate message ID | Silent skip (no processing, no reply) |
| Rate limit exceeded | Drop message, log warning |
| Queue full (50+ queued messages) | "We're busy" reply, task dropped |
| Upload queue full (30+ queued uploads) | "Try again" reply, upload dropped |
| File too large (detected mid-stream) | Download aborted at 10MB, user notified |
| Unsupported MIME type | Counted in batch, reported in batch summary |
| Daily upload limit reached | Immediate error message to user |
| GCP storage failure | Auto-fallback to Supabase, transparent to user |
| Both storages fail | `RuntimeError` caught, user notified |
| GPT extraction failure (all retries) | `extraction_status = 'failed'`, logged, flow continues |
| Background task timeout (120s) | "Request taking longer than expected" reply |
| DB SSL drop on first query | Single retry with fresh session |
| Conflict detected | User prompted via button; auto-resolves after 5 days |

---

## Key Files

| File | Role |
|------|------|
| `app/routers/webhook.py` | Webhook endpoint, dedup cache, debounce buffer, entry-point semaphore, `_safe_process_message`, `_process_message_background` |
| `app/services/message_router.py` | Route messages to handlers, upload batch tracking, upload semaphore, backpressure counter |
| `app/services/whatsapp_sender.py` | `download_whatsapp_media` — streaming download with size guard |
| `app/services/document_upload.py` | Validation, content hash dedup, storage path, DB record creation, extraction semaphore |
| `app/services/storage_service.py` | GCP + Supabase upload/download abstraction |
| `app/services/gpt_extraction.py` | GPT extraction pipeline, conflict routing, DB writes |
| `app/services/conflict_engine.py` | Conflict creation, resolution, auto-expiry |
| `app/core/constants.py` | All limits and thresholds — never hardcoded elsewhere |
