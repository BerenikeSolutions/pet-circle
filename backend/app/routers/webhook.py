"""
PetCircle Phase 1 — WhatsApp Webhook Router (Module 4)

Route: /webhook/whatsapp

Handles incoming WhatsApp events from Meta's Cloud API.
This layer does ONLY:
    1. Signature verification (GET: token match, POST: HMAC-SHA256)
    2. Payload parsing (robust nested dictionary extraction)
    3. Message type detection (text, image, document, button)
    4. Logging ALL incoming payloads to message_logs
    5. Passing structured objects to the service layer

NO business logic lives here. No onboarding, no preventive logic,
no GPT calls. Just parsing, validation, and forwarding.
"""

import asyncio
import logging
import time
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import MAX_CONCURRENT_MESSAGE_PROCESSING, MAX_QUEUED_MESSAGES
from app.core.log_sanitizer import mask_phone, sanitize_payload
from app.core.rate_limiter import rate_limiter
from app.core.security import verify_webhook_signature
from app.database import get_db
from app.models.message_log import MessageLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entry-point concurrency control
#
# Every inbound WhatsApp message — text, button, image, document — spawns a
# background task via asyncio.create_task(). Without a gate here, a traffic
# spike of 200 messages creates 200 concurrent coroutines all immediately
# opening a DB session, exhausting the pool (ceiling: 25 connections) and
# triggering SSL termination on Supabase's pooler.
#
# _message_processing_semaphore caps active tasks at MAX_CONCURRENT_MESSAGE_PROCESSING.
# _message_queue_depth tracks active + waiting tasks so we can reject new ones
# once the queue is full (backpressure), rather than letting them pile up
# indefinitely on the semaphore.
#
# Inner semaphores (_upload_processing_semaphore, _extraction_semaphore) still
# apply per-stage limits within this outer bound — they are not replaced by this.
# ---------------------------------------------------------------------------
_message_processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_MESSAGE_PROCESSING)
_message_queue_depth: int = 0


async def _safe_process_message(message_data: dict) -> None:
    """
    Entry-point wrapper for _process_message_background.

    Acquires the global message processing semaphore before starting work,
    ensuring at most MAX_CONCURRENT_MESSAGE_PROCESSING tasks run concurrently
    across all message types. Rejects the task immediately if the queue is
    already at capacity (MAX_QUEUED_MESSAGES), sending the user a retry prompt
    instead of queuing another waiting coroutine.
    """
    global _message_queue_depth

    from_number = message_data.get("from_number", "unknown")

    if _message_queue_depth >= MAX_QUEUED_MESSAGES:
        logger.warning(
            "Message queue full (%d/%d) — dropping message from %s",
            _message_queue_depth, MAX_QUEUED_MESSAGES, mask_phone(from_number),
        )
        # Best-effort reply — if this also fails we log and move on.
        try:
            from app.database import get_fresh_session
            from app.services.whatsapp_sender import send_text_message
            _db = get_fresh_session()
            try:
                await send_text_message(
                    _db, from_number,
                    "We're a bit busy right now. Please try again in a moment.",
                )
            finally:
                _db.close()
        except Exception as _err:
            logger.error("Failed to send queue-full reply to %s: %s", mask_phone(from_number), _err)
        return

    _message_queue_depth += 1
    try:
        async with _message_processing_semaphore:
            await _process_message_background(message_data)
    finally:
        _message_queue_depth -= 1


# --- Message deduplication cache ---
# Meta may deliver the same webhook multiple times (retries, network issues).
# We track recently seen message IDs to avoid processing duplicates.
# Using OrderedDict for efficient LRU eviction.
_DEDUP_CACHE: OrderedDict[str, float] = OrderedDict()
_DEDUP_MAX_SIZE = 2000
_DEDUP_TTL_SECONDS = 3600  # 1 hour — Meta may retry webhooks for hours after failures

# --- Per-user message debounce buffer ---
# Users often send a single thought across multiple quick messages
# (e.g. "vaccines last Dec" / "deworming Jan" / "no flea treatment yet").
# Processing each independently races the state machine forward before the user
# is done. We buffer text messages per user and flush them as one combined
# message after a short idle window.
#
# Only text messages are buffered. Buttons and media bypass the buffer and
# process immediately — they represent discrete, deliberate actions.
_DEBOUNCE_SECONDS = 1.5
_DEBOUNCE_SECONDS_LONG = 3.0  # For multi-message steps: preventive history, meal details
_USER_MSG_BUFFERS: dict[str, list[dict]] = {}   # mobile → ordered list of message_data
_USER_DEBOUNCE_TASKS: dict[str, "asyncio.Task"] = {}  # mobile → pending flush task
_USER_DEBOUNCE_DURATIONS: dict[str, float] = {}  # mobile → active debounce duration

# States where users commonly split a single thought across multiple rapid messages.
_LONG_DEBOUNCE_STATES = frozenset({"awaiting_preventive", "awaiting_meal_details"})


def _is_duplicate_message(message_id: str) -> bool:
    """
    Check if a message ID was already processed recently.

    Returns True if duplicate (should skip), False if new (should process).
    """
    if not message_id:
        return False

    now = time.time()

    # Evict expired entries from the front of the OrderedDict.
    while _DEDUP_CACHE:
        oldest_key, oldest_time = next(iter(_DEDUP_CACHE.items()))
        if now - oldest_time > _DEDUP_TTL_SECONDS:
            _DEDUP_CACHE.pop(oldest_key)
        else:
            break

    if message_id in _DEDUP_CACHE:
        logger.info("Duplicate message_id %s — skipping.", message_id)
        return True

    _DEDUP_CACHE[message_id] = now

    # Cap cache size.
    if len(_DEDUP_CACHE) > _DEDUP_MAX_SIZE:
        _DEDUP_CACHE.popitem(last=False)

    return False

async def _flush_user_messages(mobile: str) -> None:
    """
    Wait for the debounce window, then process all buffered messages as one.

    Cancelled and restarted each time a new message arrives within the window,
    so only the final message in a rapid burst triggers processing.
    """
    duration = _USER_DEBOUNCE_DURATIONS.get(mobile, _DEBOUNCE_SECONDS)
    await asyncio.sleep(duration)

    messages = _USER_MSG_BUFFERS.pop(mobile, [])
    _USER_DEBOUNCE_TASKS.pop(mobile, None)
    _USER_DEBOUNCE_DURATIONS.pop(mobile, None)

    if not messages:
        return

    if len(messages) == 1:
        asyncio.create_task(_safe_process_message(messages[0]))
        return

    # Combine all buffered text into a single message.
    # Use the last message's metadata (message_id, timestamp) so dedup and
    # logging stay accurate. The joined text is what the router will process.
    combined_text = "\n".join(
        m["text"] for m in messages if m.get("text")
    )
    merged = dict(messages[-1])
    merged["text"] = combined_text
    logger.info(
        "Debounce flush: combining %d messages for %s",
        len(messages),
        mask_phone(mobile),
    )
    asyncio.create_task(_safe_process_message(merged))


def _enqueue_text_or_dispatch(message_data: dict, debounce_seconds: float = _DEBOUNCE_SECONDS) -> None:
    """
    Route a message to the debounce buffer (text) or direct dispatch (everything else).

    Text messages are held for debounce_seconds so rapid multi-message bursts
    are merged into one before the state machine sees them. Buttons and media
    are dispatched immediately — they are deliberate, discrete actions.
    """
    mobile = message_data.get("from_number")
    msg_type = message_data.get("type")

    # Non-text messages bypass debounce — process immediately.
    if msg_type != "text" or not mobile:
        asyncio.create_task(_safe_process_message(message_data))
        return

    # Cancel any pending flush for this user (they're still typing).
    existing = _USER_DEBOUNCE_TASKS.get(mobile)
    if existing and not existing.done():
        existing.cancel()

    # Append to this user's buffer and record the debounce duration for this window.
    _USER_MSG_BUFFERS.setdefault(mobile, []).append(message_data)
    _USER_DEBOUNCE_DURATIONS[mobile] = debounce_seconds

    # Schedule a fresh flush after the idle window.
    _USER_DEBOUNCE_TASKS[mobile] = asyncio.create_task(
        _flush_user_messages(mobile)
    )


async def _process_message_background(message_data: dict) -> None:
    """
    Process a WhatsApp message in a background task.

    Uses its own DB session since the request-scoped session is closed
    after the webhook returns 200. This ensures Meta never times out
    waiting for processing to complete, eliminating phantom retries.

    Retries once with a fresh session on OperationalError (SSL drop) —
    pool_pre_ping can't prevent the TOCTOU race where a connection dies
    between checkout and the first query.
    """
    from app.database import get_fresh_session

    from_number = message_data.get("from_number", "unknown")
    bg_db = get_fresh_session()
    try:
        from app.services.message_router import route_message
        # 120s timeout — generous since we're no longer blocking the webhook.
        await asyncio.wait_for(route_message(bg_db, message_data), timeout=120)
    except OperationalError as e:
        # SSL connection dropped on first DB hit — retry once with a fresh session.
        logger.warning(
            "Background routing SSL drop for %s — retrying with fresh session: %s",
            mask_phone(from_number), str(e)[:200],
        )
        try:
            bg_db.rollback()
        except Exception:
            pass
        try:
            bg_db.close()
        except Exception:
            pass
        bg_db = get_fresh_session()
        try:
            from app.services.message_router import route_message
            await asyncio.wait_for(route_message(bg_db, message_data), timeout=120)
        except TimeoutError:
            logger.error(
                "Background message routing timed out for %s (retry)",
                mask_phone(from_number),
            )
            try:
                from app.services.whatsapp_sender import send_text_message
                await send_text_message(
                    bg_db, from_number,
                    "Your request is taking longer than expected. "
                    "Please try again in a moment.",
                )
            except Exception:
                pass
        except Exception as retry_e:
            logger.error(
                "Background routing error for %s (retry): %s",
                mask_phone(from_number), str(retry_e), exc_info=True,
            )
            try:
                bg_db.rollback()
            except Exception:
                pass
            try:
                from app.services.whatsapp_sender import send_text_message
                await send_text_message(
                    bg_db, from_number,
                    "We're experiencing a temporary issue. "
                    "Please try again in a few minutes.",
                )
            except Exception:
                pass
    except TimeoutError:
        logger.error(
            "Background message routing timed out for %s",
            mask_phone(from_number),
        )
        try:
            from app.services.whatsapp_sender import send_text_message
            await send_text_message(
                bg_db, from_number,
                "Your request is taking longer than expected. "
                "Please try again in a moment.",
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(
            "Background routing error for %s: %s",
            mask_phone(from_number), str(e), exc_info=True,
        )
        try:
            bg_db.rollback()
        except Exception:
            pass
        try:
            from app.services.whatsapp_sender import send_text_message
            await send_text_message(
                bg_db, from_number,
                "We're experiencing a temporary issue. "
                "Please try again in a few minutes.",
            )
        except Exception:
            logger.error(
                "Failed to send error message to %s after routing failure",
                mask_phone(from_number),
            )
    finally:
        bg_db.close()


router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    WhatsApp webhook verification endpoint (GET).

    Meta sends a GET request during webhook registration to verify
    ownership. We must:
        1. Check that hub.mode is "subscribe"
        2. Verify hub.verify_token matches our WHATSAPP_VERIFY_TOKEN
        3. Return hub.challenge as the response body

    If verification fails, return 403 to reject the registration.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verification succeeded.")
        # Meta expects the challenge echoed back as plain text integer,
        # not JSON-serialized. Use PlainTextResponse to avoid quotes.
        return PlainTextResponse(content=hub_challenge or "")

    logger.warning("WhatsApp webhook verification failed — token mismatch.")
    raise HTTPException(status_code=403, detail="Verification failed.")


@router.post("/whatsapp")
async def handle_whatsapp_message(request: Request, db: Session = Depends(get_db)):
    """
    WhatsApp webhook message handler (POST).

    Receives all incoming WhatsApp events from Meta's Cloud API.
    Processing steps:
        1. Read raw body and verify X-Hub-Signature-256
        2. Parse JSON payload
        3. Extract message details using robust nested dict extraction
        4. Detect message type (text, image, document, button)
        5. Log the full payload to message_logs
        6. Pass structured message object to service layer

    Returns 200 OK immediately — Meta requires fast acknowledgment.
    Heavy processing (GPT, DB writes) is handled downstream.
    """
    # --- Step 1: Signature verification ---
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_webhook_signature(body, signature):
        logger.warning("Rejected webhook — invalid signature.")
        raise HTTPException(status_code=403, detail="Invalid signature.")

    # --- Step 2: Parse JSON payload ---
    try:
        payload = await request.json()
    except Exception:
        logger.error("Failed to parse webhook JSON payload.")
        raise HTTPException(status_code=400, detail="Invalid JSON.")

    # --- Step 3: Extract message details ---
    # Meta's webhook payload is deeply nested. We extract safely
    # to handle partial payloads (e.g., status updates without messages).
    message_data = _extract_message_data(payload)

    # --- Step 4: Dedup + Log + Forward ---
    # Only process if we have an actual message (not a status update).
    if message_data.get("has_message"):
        # Deduplicate — Meta may deliver the same webhook multiple times.
        message_id = message_data.get("message_id")

        # Fast path: in-memory cache catches most retries without a DB query.
        if _is_duplicate_message(message_id):
            return {"status": "ok"}

        # Slow path: DB-backed dedup survives server restarts.
        # Checks message_logs.wamid (unique index) for previously processed messages.
        # FAIL-OPEN on connection errors: the in-memory _DEDUP_CACHE already vetted
        # this message_id, and the wamid unique constraint at insert time is a third
        # safety net. Dropping legitimate messages (fail-closed) is worse than the
        # rare duplicate on a server-restart race — the constraint prevents phantom writes.
        if message_id:
            try:
                existing = db.query(MessageLog.id).filter(
                    MessageLog.wamid == message_id
                ).first()
                if existing:
                    logger.info("DB dedup: message_id %s already processed — skipping.", message_id)
                    return {"status": "ok"}
            except Exception as e:
                # SSL connection dropped or pool exhausted — do not drop the message.
                # In-memory dedup already passed; wamid unique constraint at insert
                # will reject any actual duplicate. Log at WARNING, not ERROR.
                logger.warning(
                    "DB dedup check unavailable (SSL/pool error) — continuing with in-memory dedup: %s",
                    str(e)[:200],
                )
                # Clear the broken transaction state so the session can be reused.
                # rollback() alone can fail when the SSL connection is completely
                # dead — so we also call close(), which discards the dead DBAPI
                # connection and returns it to the pool. The next db.add() below
                # will check out a fresh connection. Both calls are safe on a
                # dead connection and must be called in this order.
                try:
                    db.rollback()
                except Exception:
                    pass
                try:
                    db.close()
                except Exception:
                    pass

        # Log the incoming message AFTER dedup so duplicates aren't logged twice.
        # The wamid unique constraint acts as a final dedup safety net.
        try:
            log_entry = MessageLog(
                mobile_number=mask_phone(message_data.get("from_number")),
                direction="incoming",
                message_type=message_data.get("type"),
                payload=sanitize_payload(payload),
                wamid=message_id,
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            # If insert fails due to unique constraint on wamid, it's a duplicate.
            logger.error("Failed to log incoming message (possible duplicate wamid): %s", str(e))
            try:
                db.rollback()
            except Exception:
                pass
            # If we have a message_id and the insert failed, treat as duplicate
            # to prevent reprocessing on unique constraint violations.
            if message_id:
                logger.info("Treating message %s as duplicate after log insert failure.", message_id)
                return {"status": "ok"}

        from_number = message_data.get("from_number", "unknown")

        # Rate limit check — reject if this phone exceeds the limit.
        if from_number != "unknown" and not rate_limiter.check_rate_limit(from_number):
            logger.warning("Rate limited: phone=%s", mask_phone(from_number))
            return {"status": "ok"}

        logger.info(
            "Received %s message from %s",
            message_data.get("type", "unknown"),
            mask_phone(from_number),
        )

        # Route to debounce buffer (text) or immediate dispatch (button/media).
        # Text messages are held for debounce_seconds and merged with any
        # others from the same user so rapid multi-message bursts are processed
        # as one combined input rather than advancing the state machine
        # prematurely. Buttons and media bypass the buffer entirely.
        # Steps where users split a thought across many quick messages
        # (preventive history, meal details) use a longer 5s window.
        debounce_duration = _DEBOUNCE_SECONDS
        if from_number and from_number != "unknown":
            try:
                from app.core.encryption import hash_field as _hash_field
                from app.models.user import User as _User
                _mobile_hash = _hash_field(from_number)
                _row = (
                    db.query(_User.onboarding_state)
                    .filter(_User.mobile_hash == _mobile_hash, _User.is_deleted == False)  # noqa: E712
                    .first()
                )
                if _row and _row.onboarding_state in _LONG_DEBOUNCE_STATES:
                    debounce_duration = _DEBOUNCE_SECONDS_LONG
            except Exception:
                pass
        _enqueue_text_or_dispatch(message_data, debounce_seconds=debounce_duration)

    else:
        # Log non-message payloads (status updates, etc.) without dedup.
        try:
            log_entry = MessageLog(
                mobile_number=mask_phone(message_data.get("from_number")),
                direction="incoming",
                message_type=message_data.get("type"),
                payload=sanitize_payload(payload),
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error("Failed to log non-message payload: %s", str(e))
            try:
                db.rollback()
            except Exception:
                pass

    # Return 200 OK immediately — Meta requires fast acknowledgment.
    return {"status": "ok"}


def _extract_message_data(payload: dict) -> dict:
    """
    Extract message details from Meta's deeply nested webhook payload.

    Meta's WhatsApp Cloud API sends payloads with this structure:
        entry[0].changes[0].value.messages[0]

    This function safely navigates the nested structure and returns
    a flat dictionary with the relevant fields. If any level is missing,
    it returns safe defaults rather than crashing.

    Detects message types:
        - text: plain text message
        - image: image attachment
        - document: document attachment (PDF, etc.)
        - button: interactive button response (payload ID)

    Args:
        payload: The raw parsed JSON payload from Meta.

    Returns:
        A flat dictionary with keys:
            - has_message: bool — whether this payload contains a message
            - from_number: str — sender's WhatsApp number
            - message_id: str — Meta's message ID
            - type: str — message type (text/image/document/button)
            - text: str — message text (for text messages)
            - media_id: str — media ID (for image/document messages)
            - mime_type: str — MIME type (for image/document messages)
            - button_payload: str — button payload ID (for button messages)
    """
    result = {
        "has_message": False,
        "from_number": None,
        "profile_name": None,
        "message_id": None,
        "type": None,
        "text": None,
        "media_id": None,
        "mime_type": None,
        "button_payload": None,
        "filename": None,
    }

    # Safely navigate nested structure: entry → changes → value
    entries = payload.get("entry", [])
    if not entries:
        return result

    changes = entries[0].get("changes", [])
    if not changes:
        return result

    value = changes[0].get("value", {})

    # Extract contact info (sender's number and WhatsApp profile name).
    contacts = value.get("contacts", [])
    if contacts:
        result["from_number"] = contacts[0].get("wa_id")
        profile = contacts[0].get("profile", {})
        result["profile_name"] = profile.get("name")

    # Extract message — may not exist for status updates.
    messages = value.get("messages", [])
    if not messages:
        return result

    message = messages[0]
    result["has_message"] = True
    result["from_number"] = message.get("from", result["from_number"])
    result["message_id"] = message.get("id")
    result["type"] = message.get("type")

    # --- Type-specific extraction ---

    msg_type = result["type"]

    if msg_type == "text":
        # Plain text message.
        text_obj = message.get("text", {})
        result["text"] = text_obj.get("body")

    elif msg_type == "image":
        # Image attachment — extract media ID, MIME type, and caption.
        image_obj = message.get("image", {})
        result["media_id"] = image_obj.get("id")
        result["mime_type"] = image_obj.get("mime_type")
        result["caption"] = image_obj.get("caption")

    elif msg_type == "document":
        # Document attachment — extract media ID, MIME type, filename, and caption.
        doc_obj = message.get("document", {})
        result["media_id"] = doc_obj.get("id")
        result["mime_type"] = doc_obj.get("mime_type")
        result["filename"] = doc_obj.get("filename")
        result["caption"] = doc_obj.get("caption")

    elif msg_type == "button":
        # Interactive button response — extract the payload ID.
        # Payload IDs like REMINDER_DONE, CONFLICT_USE_NEW are defined
        # in constants — never hardcoded in this extraction layer.
        button_obj = message.get("button", {})
        result["button_payload"] = button_obj.get("payload")
        # Keep the human-visible button text too so onboarding can process
        # simple replies like "Yes" / "No" as regular input.
        result["text"] = button_obj.get("text")

    elif msg_type == "interactive":
        # Interactive list/button reply — different structure from simple buttons.
        interactive_obj = message.get("interactive", {})
        button_reply = interactive_obj.get("button_reply", {})
        result["button_payload"] = button_reply.get("id")
        result["text"] = button_reply.get("title")
        result["type"] = "button"  # Normalize to "button" for downstream processing.

    return result
