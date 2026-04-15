"""
PetCircle Phase 1 — Message Router

Routes incoming WhatsApp messages to the appropriate service handler
based on message type, user state, and conversation context.

Routing logic:
    1. New user (no DB record) → Create pending user, start onboarding
    2. User in onboarding (state != 'complete') → Continue onboarding
    3. Button payload (reminder) → Reminder response handler
    4. Button payload (conflict) → Conflict resolution handler
    5. Image/Document → Document upload + GPT extraction pipeline
    6. Text "add pet" → Start new pet onboarding
    7. Text "dashboard" → Send dashboard links
    8. Text → Query engine (pet health questions)

Rules:
    - No business logic in this file — only routing decisions.
    - Errors are caught and friendly messages sent back.
    - Never crashes on individual message failures.
"""

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import (
    ACKNOWLEDGMENTS,
    CONFLICT_KEEP_EXISTING,
    CONFLICT_USE_NEW,
    FAREWELLS,
    GREETINGS,
    HELP_COMMANDS,
    MAX_CONCURRENT_UPLOAD_PROCESSING,
    MAX_DOCS_PER_SESSION,
    MAX_QUEUED_UPLOADS,
    MAX_PENDING_DOCS_PER_PET,
    MAX_PETS_PER_USER,
    NUDGE_ACTION,
    NUDGE_DISMISS,
    NUDGE_PAYLOADS,
    NUDGE_VIEW_DASHBOARD,
    ORDER_CATEGORY_PAYLOADS,
    ORDER_COMMANDS,
    ORDER_CONFIRM_PAYLOADS,
    ORDER_FULFILL_NO,
    ORDER_FULFILL_NO_PREFIX,
    ORDER_FULFILL_YES,
    ORDER_FULFILL_YES_PREFIX,
    REMINDER_ALREADY_DONE,
    REMINDER_CANCEL,
    REMINDER_DONE,
    REMINDER_ORDER_NOW,
    REMINDER_RESCHEDULE,
    REMINDER_SCHEDULE,
    REMINDER_SNOOZE_7,
    REMINDER_STILL_PENDING,
)
from app.core.constants import (
    REMINDER_PAYLOADS as _REMINDER_PAYLOADS_CONST,
    AI_QUERY_MODEL,
)
from app.core.encryption import decrypt_field
from app.core.log_sanitizer import mask_phone

# Extraction semaphore — shared across ALL upload paths (WhatsApp + dashboard).
# Imported from document_upload so any tuning change applies everywhere at once.
from app.services.document_upload import get_extraction_semaphore as _get_extraction_semaphore  # noqa: E402

# Semaphore to limit concurrent document upload *processing* tasks system-wide.
# When a user sends 20 files at once, 20 background tasks would simultaneously
# check out DB connections AND download WhatsApp media. Capping at 8 means at
# most 8 connections are held for upload work, leaving headroom in the pool for
# webhook handler sessions and other background tasks.
_upload_processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOAD_PROCESSING)

# Backpressure counter — tracks how many upload tasks are currently active OR
# waiting to acquire _upload_processing_semaphore. When this exceeds
# MAX_QUEUED_UPLOADS, new uploads are rejected immediately rather than queued.
# This bounds the number of coroutines blocked on the semaphore so an upload
# spike cannot exhaust event loop memory with hundreds of waiting tasks.
# Counter is incremented before semaphore acquisition and decremented in finally.
_upload_queue_depth: int = 0

# --- Batch upload tracking ---
# Tracks recent upload timestamps per pet to enforce the per-session batch limit.
# Key: str(pet_id), Value: list of upload timestamps (epoch seconds).
# This is in-memory to avoid DB race conditions when many files arrive at once.
_recent_uploads: dict[str, list[float]] = {}

# Tracks whether a batch rejection message was already sent for a pet.
# Prevents spamming the user with repeated "too many files" messages.
# Key: str(pet_id), Value: True if rejection was sent this batch.
_rejection_sent: dict[str, bool] = {}

# Tracks the last inbound message token that already got a generic error reply.
# Prevents duplicate "Sorry, something went wrong" during webhook retries for
# the same inbound message, while still allowing one apology for a new message.
# Key: from_number, Value: dedup token for the failed inbound message.
_error_sent: dict[str, str] = {}

# Window in seconds for counting a "batch" of uploads.
# Files uploaded within this window are considered one batch.
_UPLOAD_BATCH_WINDOW_SECONDS: int = 120

# --- Conversation history buffer for query engine ---
# Stores the last N query turns per user so follow-up questions can be
# resolved in context (e.g. "what about X?", "tell me more", "is that normal?").
# This is intentionally in-memory: conversation context is session-scoped,
# not business state, and need not survive server restarts.
# Key: mobile_number, Value: {"turns": [...], "last_updated": float}
_query_history: dict[str, dict] = {}

# Maximum number of prior Q&A pairs to keep per user (user + assistant = 2 messages each).
_QUERY_HISTORY_MAX_PAIRS: int = 3

# Seconds of inactivity before history is discarded.
_QUERY_HISTORY_TTL_SECONDS: int = 3600  # 1 hour


def _get_query_history(mobile_number: str) -> list[dict]:
    """
    Return recent conversation turns for a user, or [] if none / expired.

    Each entry is {"role": "user"|"assistant", "content": str}.
    Expired entries (idle > TTL) are purged on access.
    """
    entry = _query_history.get(mobile_number)
    if not entry:
        return []
    if time.time() - entry["last_updated"] > _QUERY_HISTORY_TTL_SECONDS:
        _query_history.pop(mobile_number, None)
        return []
    return list(entry["turns"])


def _update_query_history(mobile_number: str, question: str, answer: str) -> None:
    """
    Append a user question and assistant answer to the conversation buffer.

    Trims the buffer to the most recent _QUERY_HISTORY_MAX_PAIRS pairs
    so memory usage stays bounded.
    """
    entry = _query_history.setdefault(
        mobile_number, {"turns": [], "last_updated": 0.0}
    )
    turns: list[dict] = entry["turns"]
    turns.append({"role": "user", "content": question})
    turns.append({"role": "assistant", "content": answer})
    # Keep only the last N pairs (2 messages per pair).
    max_messages = _QUERY_HISTORY_MAX_PAIRS * 2
    if len(turns) > max_messages:
        turns = turns[-max_messages:]
    entry["turns"] = turns
    entry["last_updated"] = time.time()

# Debounce timers for batch extraction per pet.
# Key: str(pet_id), Value: asyncio.Task that waits then extracts.
_extraction_timers: dict[str, asyncio.Task] = {}

# Deadline timers for onboarding document window per user.
# Key: str(user_id), Value: asyncio.Task that waits until upload deadline
# and auto-finalizes onboarding if no document was uploaded.
_document_window_timers: dict[str, asyncio.Task] = {}

# Tracks document IDs uploaded in the active WhatsApp batch per pet.
# Ensures the extractor only processes files from the current user upload burst,
# and avoids including unrelated pending documents from other channels.
# Key: str(pet_id), Value: list of Document.id values.
_batch_document_ids: dict[str, list] = {}

# Tracks whether the active WhatsApp upload burst for a pet originated from
# onboarding's awaiting_documents state. This is captured at upload time so
# delayed extraction does not depend on mutable user state later.
# Key: str(pet_id), Value: True if batch started during awaiting_documents.
_batch_is_onboarding: dict[str, bool] = {}

# Tracks how many documents in the current batch were rejected due to an
# unsupported MIME type (e.g. .docx, .xlsx). These are not sent as per-file
# error messages; instead they are surfaced in the single acknowledgment
# message when extraction starts.
# Key: str(pet_id), Value: count of unsupported-format files in this batch.
_unsupported_format_count: dict[str, int] = {}

# Tracks whether a user has explicitly asked to keep uploading more documents
# during the awaiting_documents window. When True, batch extraction will NOT
# auto-finalize onboarding — the user stays in the upload window until they
# type 'skip' or the deadline expires.
# Key: str(user_id), Value: True if user asked to add more files.
_upload_window_extended: dict[str, bool] = {}

def mark_upload_window_extended(user_id) -> None:
    """Mark that a user explicitly asked to add more documents."""
    _upload_window_extended[str(user_id)] = True


def is_upload_window_extended(user_id) -> bool:
    """Return True if user asked to keep uploading during awaiting_documents."""
    return _upload_window_extended.get(str(user_id), False)


def clear_upload_window_extended(user_id) -> None:
    """Clear the 'asked to add more' flag (on finalize or skip)."""
    _upload_window_extended.pop(str(user_id), None)


def get_recent_upload_count(pet_id) -> int:
    """
    Return the in-memory count of uploads for a pet within the current batch
    window. Used to avoid DB race conditions when text messages arrive before
    async upload processing has committed the Document rows.
    """
    pet_key = str(pet_id)
    cutoff = time.time() - _UPLOAD_BATCH_WINDOW_SECONDS
    entries = _recent_uploads.get(pet_key, [])
    return sum(1 for ts in entries if ts > cutoff)

# Seconds to wait after the last upload before starting batch extraction.
# Gives the user time to finish sending all files in a batch.
_EXTRACTION_DELAY_SECONDS: int = 15
_document_window_sweeper_task: asyncio.Task | None = None
_DOCUMENT_WINDOW_SWEEP_INTERVAL_SECONDS: int = 60
from app.models.conflict_flag import ConflictFlag
from app.models.deferred_care_plan_pending import DeferredCarePlanPending
from app.models.document import Document
from app.models.pet import Pet
from app.models.reminder import Reminder
from app.models.user import User
from app.services.onboarding import (
    _count_tracked_preventive_items,
    _generate_care_plan_message,
    build_welcome_message,
    create_pending_user,
    get_or_create_user,
    handle_onboarding_step,
    is_doc_upload_deadline_expired,
)
from app.services.whatsapp_sender import (
    download_whatsapp_media,
    send_text_message,
)

logger = logging.getLogger(__name__)


def _cancel_document_window_timer(user_id) -> None:
    """Cancel the pending no-upload auto-finalization timer for a user."""
    user_key = str(user_id)
    existing = _document_window_timers.get(user_key)
    if existing and not existing.done():
        existing.cancel()


def _schedule_document_window_timer(user_id, from_number, deadline) -> None:
    """
    Schedule (or reschedule) auto-finalization at the upload deadline.

    This guarantees onboarding continues after the 5-minute document window
    even if the user sends no additional messages.
    """
    user_key = str(user_id)

    _cancel_document_window_timer(user_id)

    if not deadline:
        return

    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)

    wait_seconds = max(0.0, (deadline - datetime.now(UTC)).total_seconds())
    _document_window_timers[user_key] = asyncio.create_task(
        _auto_finalize_onboarding_after_deadline(user_id, from_number, wait_seconds)
    )


async def _auto_finalize_onboarding_after_deadline(user_id, from_number, wait_seconds: float) -> None:
    """Finalize onboarding once the document upload window expires."""
    user_key = str(user_id)

    try:
        await asyncio.sleep(wait_seconds)

        from app.database import get_fresh_session
        from app.services.onboarding import _finalize_onboarding

        bg_db = get_fresh_session()
        try:
            user = bg_db.query(User).filter(User.id == user_id).first()
            if not user:
                return
            if user.onboarding_state != "awaiting_documents":
                return
            if not is_doc_upload_deadline_expired(user.doc_upload_deadline):
                return

            user._plaintext_mobile = from_number
            clear_upload_window_extended(user.id)
            await _finalize_onboarding(bg_db, user, send_text_message)
        finally:
            bg_db.close()
    except asyncio.CancelledError:
        return
    except Exception as e:
        logger.warning(
            "Document-window auto-finalization failed for user %s: %s",
            str(user_id),
            str(e),
        )
    finally:
        # Only clear the timer entry if this exact task is still the active
        # one for this user. Prevents older canceled tasks from removing a
        # newer timer scheduled later.
        current_task = asyncio.current_task()
        if _document_window_timers.get(user_key) is current_task:
            _document_window_timers.pop(user_key, None)


async def sweep_expired_document_windows_once(batch_size: int = 50) -> int:
    """Finalize expired awaiting_documents users if in-memory timers were lost."""
    from app.database import get_fresh_session
    from app.services.onboarding import _finalize_onboarding

    finalized_count = 0
    bg_db = get_fresh_session()
    try:
        expired_users = (
            bg_db.query(User)
            .filter(
                User.onboarding_state == "awaiting_documents",
                User.doc_upload_deadline.isnot(None),
            )
            .order_by(User.doc_upload_deadline.asc())
            .limit(batch_size)
            .all()
        )

        for expired_user in expired_users:
            if not is_doc_upload_deadline_expired(expired_user.doc_upload_deadline):
                continue

            try:
                from_number = decrypt_field(expired_user.mobile_number)
                expired_user._plaintext_mobile = from_number
                clear_upload_window_extended(expired_user.id)
                await _finalize_onboarding(bg_db, expired_user, send_text_message)
                finalized_count += 1
            except Exception as user_err:
                logger.warning(
                    "Expired document-window finalize failed for user %s: %s",
                    str(expired_user.id),
                    str(user_err),
                )
                try:
                    bg_db.rollback()
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Expired document-window sweep failed: %s", str(e))
        try:
            bg_db.rollback()
        except Exception:
            pass
    finally:
        bg_db.close()

    return finalized_count


async def _document_window_sweeper_loop() -> None:
    """Background loop for durable document-window expiry recovery."""
    await sweep_expired_document_windows_once()

    while True:
        await asyncio.sleep(_DOCUMENT_WINDOW_SWEEP_INTERVAL_SECONDS)
        await sweep_expired_document_windows_once()


def start_document_window_sweeper() -> None:
    """Start durable document-window sweeper if not running."""
    global _document_window_sweeper_task
    if _document_window_sweeper_task and not _document_window_sweeper_task.done():
        return
    _document_window_sweeper_task = asyncio.create_task(_document_window_sweeper_loop())


async def stop_document_window_sweeper() -> None:
    """Stop durable document-window sweeper on shutdown."""
    global _document_window_sweeper_task
    if not _document_window_sweeper_task:
        return

    _document_window_sweeper_task.cancel()
    try:
        await _document_window_sweeper_task
    except asyncio.CancelledError:
        pass
    _document_window_sweeper_task = None


_DEFERRED_MARKER_STALE_MINUTES: int = 30  # Auto-clear threshold (no pending docs + age)


def _has_pending_deferred_care_plan(db: Session, pet_id, user=None) -> bool:
    """Return True when per-pet marker or legacy user pending flag indicates deferred send.

    Stale markers (older than _DEFERRED_MARKER_STALE_MINUTES with no pending documents)
    are auto-cleared so users are never permanently locked out if the extraction
    pipeline fails before reaching _send_deferred_care_plan.
    """
    marker = (
        db.query(DeferredCarePlanPending)
        .filter(
            DeferredCarePlanPending.pet_id == pet_id,
            DeferredCarePlanPending.is_cleared == False,
        )
        .first()
    )
    if marker is not None:
        # Auto-clear stale marker: if it's been more than the threshold and
        # there are no pending documents left, the extraction pipeline is done
        # (success, failure, or lost) — unblock the user.
        stale_cutoff = datetime.utcnow() - timedelta(minutes=_DEFERRED_MARKER_STALE_MINUTES)
        if marker.created_at and marker.created_at < stale_cutoff:
            pending_doc_count = (
                db.query(Document)
                .filter(Document.pet_id == pet_id, Document.extraction_status == "pending")
                .count()
            )
            if pending_doc_count == 0:
                logger.info(
                    "Auto-clearing stale deferred marker for pet=%s (age > %dmin, no pending docs)",
                    str(pet_id), _DEFERRED_MARKER_STALE_MINUTES,
                )
                try:
                    marker.is_cleared = True
                    marker.cleared_at = datetime.utcnow()
                    db.commit()
                except Exception as _clr_err:
                    logger.warning("Failed to auto-clear stale marker: %s", _clr_err)
                    try:
                        db.rollback()
                    except Exception:
                        pass
                return False
        return True

    # Backward compatibility during rollout from user-level pending flag.
    if user is not None and getattr(user, "dashboard_link_pending", False):
        try:
            db.add(
                DeferredCarePlanPending(
                    user_id=user.id,
                    pet_id=pet_id,
                    reason="legacy_user_pending",
                    is_cleared=False,
                    cleared_at=None,
                )
            )
            db.flush()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        return True

    return False


def _clear_deferred_care_plan_marker(db: Session, pet_id, user=None) -> int:
    """
    Clear all active deferred markers for a pet and legacy user-level pending flag.

    Returns the number of marker rows transitioned from active to cleared.
    Callers can use this as a "claim" check to ensure only one concurrent
    sender wins the race to deliver the deferred care plan.
    """
    rows_cleared = (
        db.query(DeferredCarePlanPending)
        .filter(
            DeferredCarePlanPending.pet_id == pet_id,
            DeferredCarePlanPending.is_cleared == False,
        )
        .update(
            {
                DeferredCarePlanPending.is_cleared: True,
                DeferredCarePlanPending.cleared_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
    )
    if user is not None and getattr(user, "dashboard_link_pending", False):
        user.dashboard_link_pending = False
        rows_cleared = max(rows_cleared, 1)
    return int(rows_cleared or 0)


def _get_active_deferred_marker(db: Session, pet_id):
    """Return the active deferred care-plan marker row for a pet, if any."""
    return (
        db.query(DeferredCarePlanPending)
        .filter(
            DeferredCarePlanPending.pet_id == pet_id,
            DeferredCarePlanPending.is_cleared == False,
        )
        .order_by(DeferredCarePlanPending.created_at.desc())
        .first()
    )


def _should_use_agentic_order() -> bool:
    """
    Return True when AGENTIC_ORDER_ENABLED='true' and the OpenAI API
    is reachable. Evaluated per-message so the flag can be toggled via env
    var update + redeploy without code changes.

    Falls back to False (deterministic state machine) on any error.
    """
    flag = getattr(settings, "AGENTIC_ORDER_ENABLED", "false")
    has_key = bool(getattr(settings, "ANTHROPIC_API_KEY", None))
    return flag.lower() == "true" and has_key


def _get_mobile(user) -> str:
    """
    Get the plaintext mobile number for sending messages.

    Prefers the cached plaintext from the current request (set by route_message).
    Falls back to decrypting the stored encrypted mobile_number.
    """
    return getattr(user, "_plaintext_mobile", None) or decrypt_field(user.mobile_number)


# Edit-intent trigger words. Conservative set — avoids intercepting legitimate
# health questions that happen to use "change" or "update" in a sentence.
_EDIT_EXACT = frozenset({
    "update", "edit", "change", "modify", "fix", "correct",
    "update details", "edit details", "change details",
    "update profile", "edit profile", "update my profile", "edit my profile",
    "update pet", "edit pet", "update my pet", "edit my pet",
})

_EDIT_STARTS_WITH = (
    "update ", "edit ", "change my ", "fix my ", "correct my ",
    "i want to update", "i want to change", "i want to edit",
    "i need to update", "i need to change", "i need to edit",
)

_EDIT_WRONG_PHRASES = (
    "wrong name", "wrong breed", "wrong weight", "wrong gender",
    "wrong age", "wrong birthday", "wrong food", "wrong vaccine",
    "wrong date", "wrong species",
)


def _is_edit_intent(text_lower: str) -> bool:
    """
    Return True when the user's text clearly signals intent to update pet or owner data.

    Conservative: does NOT match open-ended questions like "how do I change my dog's diet?"
    or "can I edit" — those still fall through to the query engine.
    """
    if text_lower in _EDIT_EXACT:
        return True
    for prefix in _EDIT_STARTS_WITH:
        if text_lower.startswith(prefix):
            return True
    for phrase in _EDIT_WRONG_PHRASES:
        if phrase in text_lower:
            return True
    return False


# ── Vet-diet intent detection ─────────────────────────────────────────────────
# Phrases that clearly indicate the user is sharing a vet dietary recommendation
# via chat rather than uploading a prescription document.
_VET_DIET_PHRASES = (
    "vet prescribed", "vet recommended", "vet said to give", "vet told to give",
    "vet says to give", "vet said to feed", "vet told to feed",
    "vet said to avoid", "vet told to avoid", "vet says to avoid",
    "doctor prescribed", "doctor recommended", "doctor said to give",
    "doctor told to give", "doctor says to give",
    "doctor said to avoid", "doctor told to avoid",
    "prescribed by vet", "prescribed by doctor", "prescribed by my vet",
    "vet put on", "vet has put", "vet wants", "vet wants to",
    "vet is recommending", "vet suggested", "vet advises",
    "prescription diet", "therapeutic diet", "vet advised",
    "on a vet diet", "on vet prescribed",
)

_VET_DIET_EXTRACT_SYSTEM_PROMPT = (
    "You are a data extraction assistant for a pet health app.\n\n"
    "Extract vet-prescribed dietary items from a pet parent's message.\n\n"
    "Return ONLY a valid JSON array. Each item:\n"
    "  food_label  — food, diet, or supplement name (e.g. 'Royal Canin Renal', 'fish oil')\n"
    "  food_type   — one of: 'packaged' | 'homemade' | 'supplement' | 'avoid'\n"
    "    packaged: branded or commercial pet food\n"
    "    homemade: home-cooked, raw, or generic food\n"
    "    supplement: vitamins, oils, probiotics, treats\n"
    "    avoid: food the vet said to restrict or avoid\n"
    "  detail      — feeding instruction or quantity if mentioned, null otherwise\n\n"
    "Rules:\n"
    "- Only extract items the user says are vet-prescribed or vet-recommended\n"
    "- If nothing vet-prescribed is found, return []\n"
    "- No explanation, no markdown — JSON array only"
)


def _is_vet_diet_intent(text_lower: str) -> bool:
    """Return True when the user's message contains a vet dietary recommendation."""
    return any(phrase in text_lower for phrase in _VET_DIET_PHRASES)


async def _extract_vet_diet_from_chat(text: str) -> list[dict]:
    """
    Use a lightweight LLM call to extract vet-prescribed diet items from a chat message.

    Returns a list of dicts: [{food_label, food_type, detail}].
    Returns [] on parse failure or if nothing vet-prescribed is detected.
    """
    import json
    from app.services.nutrition_service import _parse_json_from_response
    from app.utils.ai_client import get_ai_client

    try:
        client = get_ai_client()
        response = await client.messages.create(
            model=AI_QUERY_MODEL,
            temperature=0.0,
            max_tokens=400,
            system=_VET_DIET_EXTRACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = response.content[0].text.strip()
        result = _parse_json_from_response(raw)
        if isinstance(result, list):
            return result
        # If the LLM returned a top-level object, look for an array inside
        if isinstance(result, dict):
            for v in result.values():
                if isinstance(v, list):
                    return v
    except Exception as exc:
        logger.warning("_extract_vet_diet_from_chat failed: %s", exc)
    return []


async def _handle_vet_diet_chat(
    db: Session, user, text: str, from_number: str, pet
) -> None:
    """
    Handle a chat message that contains a vet dietary recommendation.

    Extracts diet items from the message, persists them tagged as
    'Vet prescribed (chat)', sends a confirmation, then also routes
    to the query engine in case the message contains a question.
    """
    from app.services.diet_service import add_diet_item

    items = await _extract_vet_diet_from_chat(text)
    saved_labels: list[str] = []

    for raw in items:
        if not isinstance(raw, dict):
            continue
        food_label = str(raw.get("food_label") or "").strip()[:200]
        if not food_label:
            continue
        food_type = str(raw.get("food_type") or "homemade").strip().lower()
        raw_detail = str(raw.get("detail") or "").strip()

        if food_type == "avoid":
            item_type = "homemade"
            detail = f"Avoid – {raw_detail}" if raw_detail else "Avoid (vet advised)"
            detail = f"{detail} · Vet prescribed (chat)"[:200]
        elif food_type == "supplement":
            item_type = "supplement"
            detail = f"{raw_detail} · Vet prescribed (chat)"[:200] if raw_detail else "Vet prescribed (chat)"
        elif food_type == "packaged":
            item_type = "packaged"
            detail = f"{raw_detail} · Vet prescribed (chat)"[:200] if raw_detail else "Vet prescribed (chat)"
        else:
            item_type = "homemade"
            detail = f"{raw_detail} · Vet prescribed (chat)"[:200] if raw_detail else "Vet prescribed (chat)"

        try:
            await add_diet_item(
                db=db, pet_id=pet.id, food_type=item_type, label=food_label, detail=detail
            )
            saved_labels.append(food_label)
            logger.info(
                "Vet diet item saved from chat for pet=%s: '%s' (%s)",
                pet.id, food_label, item_type,
            )
        except Exception as exc:
            logger.warning(
                "Failed to save vet diet item '%s' from chat for pet=%s: %s",
                food_label, pet.id, exc,
            )

    if saved_labels:
        items_text = ", ".join(saved_labels)
        confirm = (
            f"Got it! I've noted {items_text} as vet-prescribed for {pet.name} "
            f"and added it to the diet list. It will show up in the Diet Analysis card "
            f"with a vet-prescribed tag."
        )
        await send_text_message(db, from_number, confirm)

    # Also route to query engine — the message may contain a follow-up question
    await _handle_query(db, user, text)


def _build_error_dedup_token(message_data: dict) -> str:
    """Build a stable token to identify a specific inbound message retry."""
    message_id = message_data.get("message_id")
    if message_id:
        return f"wamid:{message_id}"

    msg_type = message_data.get("type") or "unknown"
    if msg_type == "text":
        return f"text:{(message_data.get('text') or '').strip().lower()}"
    if msg_type in ("image", "document"):
        media_id = message_data.get("media_id") or ""
        filename = message_data.get("filename") or ""
        return f"media:{msg_type}:{media_id}:{filename}"
    if msg_type == "button":
        return f"button:{message_data.get('button_payload') or ''}"

    return f"type:{msg_type}"


# All valid reminder payload IDs — sourced from constants to keep in sync
REMINDER_PAYLOADS = _REMINDER_PAYLOADS_CONST

# All valid conflict payload IDs
CONFLICT_PAYLOADS = {CONFLICT_USE_NEW, CONFLICT_KEEP_EXISTING}


async def route_message(db: Session, message_data: dict) -> None:
    """
    Route an incoming WhatsApp message to the appropriate handler.

    Args:
        db: SQLAlchemy database session.
        message_data: Flat dictionary from webhook's _extract_message_data().
    """
    from_number = message_data.get("from_number")
    msg_type = message_data.get("type")

    if not from_number:
        logger.warning("Message has no from_number — skipping.")
        return

    # Voice messages are not supported — reply with a text prompt so the user
    # knows to switch to chat instead of getting silently stuck.
    if msg_type == "audio":
        logger.info("Voice message received from %s — sending unsupported-type reply", mask_phone(from_number))
        await send_text_message(
            db,
            from_number,
            "I'm not able to listen to voice messages just yet 🙏\n\n"
            "Please type your message in the chat and I'll be happy to help!",
        )
        return

    # Silently ignore other non-actionable message types (reactions, stickers,
    # location, contacts, etc.) — these should never trigger onboarding
    # prompts or GPT calls.
    _ACTIONABLE_TYPES = {"text", "image", "document", "button"}
    if msg_type not in _ACTIONABLE_TYPES:
        logger.info("Ignoring non-actionable message type '%s' from %s", msg_type, mask_phone(from_number))
        return

    # Admin-only WhatsApp order status updates from ORDER_NOTIFICATION_PHONE.
    # Handles both fixed template button payloads (ORDER_FULFILL_YES/NO) and
    # legacy dynamic payloads with order_id suffix (ORDER_FULFILL_YES:/NO: prefix).
    if msg_type == "button" and _is_order_admin_number(from_number):
        payload = message_data.get("button_payload", "")
        is_fulfill_payload = (
            payload in (ORDER_FULFILL_YES, ORDER_FULFILL_NO)
            or payload.startswith(ORDER_FULFILL_YES_PREFIX)
            or payload.startswith(ORDER_FULFILL_NO_PREFIX)
        )
        if is_fulfill_payload:
            from app.services.order_service import handle_admin_order_status_feedback
            await handle_admin_order_status_feedback(db, from_number, payload)
            return

    try:
        # --- Step 1: Look up or create user ---
        user, is_existing = get_or_create_user(db, from_number)

        if not is_existing:
            # Brand new user — create pending record, send welcome.
            # create_pending_user handles race conditions: if another webhook
            # already created this user, it returns the existing record.
            user = create_pending_user(db, from_number)

            # Only send welcome if user is truly new (welcome state).
            # If race condition returned an existing user mid-onboarding, skip welcome.
            if user.onboarding_state == "welcome":
                # Use WhatsApp profile name for personalised greeting.
                profile_name = message_data.get("profile_name", "").strip() if message_data else ""
                if profile_name:
                    user.full_name = profile_name.title()
                    try:
                        db.commit()
                    except Exception:
                        try:
                            db.rollback()
                        except Exception:
                            pass
                greeting_name = profile_name.split()[0] if profile_name else "there"
                await send_text_message(db, from_number, build_welcome_message(greeting_name))
                return
            # Otherwise fall through to handle user as existing.

        # Attach plaintext number for downstream sending.
        # user.mobile_number is encrypted in DB; from_number is plaintext from webhook.
        user._plaintext_mobile = from_number

        # --- Step 2: Check if user is still onboarding ---
        if user.onboarding_state and user.onboarding_state != "complete":

            # --- Special handling for awaiting_documents state ---
            # During the upload window, allow image/document uploads alongside text.
            if user.onboarding_state == "awaiting_documents":


                # Check deadline expiry on any incoming message.
                if is_doc_upload_deadline_expired(user.doc_upload_deadline):
                    from app.services.onboarding import _finalize_onboarding
                    _cancel_document_window_timer(user.id)
                    await _finalize_onboarding(db, user, send_text_message)
                    return
                # Allow document/image uploads during this state.
                if msg_type in ("image", "document"):
                    await _handle_media(db, user, message_data)
                    return
                # Text input → route to onboarding handler (handles "skip" + rejection).
                text = (message_data.get("text") or message_data.get("button_payload") or "").strip()
                if text:
                    await handle_onboarding_step(db, user, text, send_text_message, message_data=message_data)
                    if user.onboarding_state == "awaiting_documents":
                        _schedule_document_window_timer(
                            user_id=user.id,
                            from_number=from_number,
                            deadline=user.doc_upload_deadline,
                        )
                return

            # --- All other onboarding states: block non-text ---
            text = (message_data.get("text") or message_data.get("button_payload") or "").strip()
            if not text:
                # Only send the "please send text" prompt once per user.
                # Check message_logs for whether we already sent it.
                # If already sent, silently ignore non-text messages.
                from sqlalchemy import String, cast

                from app.models.message_log import MessageLog
                already_sent = (
                    db.query(MessageLog.id)
                    .filter(
                        MessageLog.mobile_number == from_number,
                        MessageLog.direction == "outgoing",
                        MessageLog.message_type == "text",
                        cast(MessageLog.payload["text"]["body"], String).like(
                            "%Please send a text%"
                        ),
                    )
                    .first()
                )
                if not already_sent:
                    await send_text_message(
                        db, from_number,
                        "Please send a text message to continue setup.",
                    )
                return
            await handle_onboarding_step(db, user, text, send_text_message, message_data=message_data)
            if user.onboarding_state == "awaiting_documents":
                _schedule_document_window_timer(
                    user_id=user.id,
                    from_number=from_number,
                    deadline=user.doc_upload_deadline,
                )
            return

        # --- Step 3: User is fully onboarded — route by message type ---
        if msg_type == "button":
            await _handle_button(db, user, message_data)

        elif msg_type in ("image", "document"):
            await _handle_media(db, user, message_data)

        elif msg_type == "text":
            await _handle_text(db, user, message_data)

        else:
            # Safety net — non-actionable types are filtered at the top of
            # route_message(), so this branch should be unreachable.
            logger.info("Unhandled message type '%s' from %s", msg_type, mask_phone(from_number))

        # Clear error state on successful processing
        _error_sent.pop(from_number, None)

    except Exception as e:
        logger.error("Error routing message from %s: %s", mask_phone(from_number), str(e))
        # Rollback any dirty transaction state before attempting to send error message.
        try:
            db.rollback()
        except Exception:
            pass
        try:
            dedup_token = _build_error_dedup_token(message_data)
            should_send = _error_sent.get(from_number) != dedup_token
            if should_send:
                _error_sent[from_number] = dedup_token
                await send_text_message(
                    db, from_number,
                    "Sorry, something went wrong. Please try again.",
                )
        except Exception:
            pass


async def _handle_text(db: Session, user, message_data: dict) -> None:
    """
    Handle a text message from a fully onboarded user.

    Routing (in order):
        1. Empty text → ignore
        2. Pending reschedule → apply_reschedule_date()
        3. Greeting → canned menu
        4. Acknowledgment (thanks, ok) → canned reply
        5. Farewell (bye) → canned reply
        6. Help/menu → show commands
        7. "add pet" / "new pet" → start new pet onboarding
        8. "dashboard" / "link" → send dashboard links
        9. anything else → query engine
    """
    text = (message_data.get("text") or "").strip()
    text_lower = text.lower()
    from_number = _get_mobile(user)

    # --- Guard: empty text should not trigger GPT ---
    if not text:
        return

    # --- Global suppression while care plan delivery is in progress ---
    # When a deferred care-plan marker is active, no question is being
    # asked of the user. Any incoming text (yes/no/ok/dashboard/anything)
    # is irrelevant noise and is silently swallowed so it cannot derail
    # the in-flight delivery flow. The care plan + dashboard link will
    # be sent automatically when generation/extraction completes.
    _deferred_pet = (
        db.query(Pet)
        .filter(Pet.user_id == user.id, Pet.is_deleted == False)
        .order_by(Pet.created_at.desc())
        .first()
    )
    if _deferred_pet and _has_pending_deferred_care_plan(db, _deferred_pet.id, user=user):
        logger.info(
            "Suppressing user message %r for pet=%s — care plan delivery in progress",
            text_lower[:40], str(_deferred_pet.id),
        )
        return

    # --- Check for pending reschedule before any other routing ---
    # If user recently pressed "Reschedule" on a reminder, route the
    # next text message as a date input to apply_reschedule_date().
    reschedule_result = await _try_handle_reschedule_date(db, user, text, from_number)
    if reschedule_result:
        return

    # --- Agentic edit flow (in-progress) ---
    # Route all messages to the edit agent while user.edit_state is active.
    # Checked before order routing so "cancel" inside an edit session is handled correctly.
    if getattr(user, "edit_state", None) == "agentic_edit":
        from app.services.agentic_edit import handle_agentic_edit_step
        await handle_agentic_edit_step(db, user, message_data, send_text_message)
        return

    # --- Agentic order flow — route all text to the agent ---
    if user.order_state == "agentic_order":
        if text_lower in ("cancel", "stop"):
            # Let the agent handle the cancellation gracefully
            pass
        from app.services.agentic_order import handle_agentic_order_step
        await handle_agentic_order_step(db, user, message_data, send_text_message)
        return

    # --- Active order flow — intercept text for items or pet selection ---
    if user.order_state in (
        "awaiting_pet_reco",
        "awaiting_reco_sel",
        "awaiting_order_items",
        "awaiting_order_pet",
        "awaiting_order_confirm",
    ):
        # Allow user to cancel mid-flow by typing "cancel" or "stop".
        if text_lower in ("cancel", "stop"):
            from app.services.order_service import cancel_order_flow
            await cancel_order_flow(db, user)
            return

        if user.order_state == "awaiting_pet_reco":
            from app.services.order_service import handle_order_pet_for_recommendation
            await handle_order_pet_for_recommendation(db, user, text)
            return
        elif user.order_state == "awaiting_reco_sel":
            from app.services.order_service import handle_recommendation_selection
            await handle_recommendation_selection(db, user, text)
            return
        elif user.order_state == "awaiting_order_items":
            from app.services.order_service import handle_order_items
            await handle_order_items(db, user, text)
            return
        elif user.order_state == "awaiting_order_pet":
            from app.services.order_service import handle_order_pet_selection
            await handle_order_pet_selection(db, user, text)
            return
        elif user.order_state == "awaiting_order_confirm":
            # User typed text instead of tapping a button — remind them.
            await send_text_message(
                db, from_number,
                "Please tap *Confirm Order* or *Cancel* above to proceed.",
            )
            return

    # --- Greeting — canned menu, no GPT call ---
    if text_lower in GREETINGS:
        await _send_help_menu(db, from_number, user=user)
        return

    # --- Acknowledgments (thanks, ok, cool, great …) ---
    # If the user is mid-conversation (has query history), route to the query
    # engine so it can respond in context (e.g. "cool" after a vaccination
    # answer → "Glad that helps! Let me know if you need anything else about Max.").
    # If there is no prior context, fall back to the canned reply.
    if text_lower in ACKNOWLEDGMENTS:
        if _get_query_history(from_number):
            await _handle_query(db, user, text)
        else:
            await send_text_message(
                db, from_number,
                "You're welcome! Let me know if you need anything else.",
            )
        return

    # --- Farewells (bye, see you) ---
    # Mid-conversation: let the LLM close the conversation in context
    # (e.g. "Bye! Hope Max's vaccination goes well next week! 🐾").
    # No prior context: canned reply is appropriate.
    if text_lower in FAREWELLS:
        if _get_query_history(from_number):
            await _handle_query(db, user, text)
        else:
            await send_text_message(
                db, from_number,
                "Bye! I'm always here when you need me. Take care! 🐾",
            )
        return

    # --- Help / Menu — show available commands ---
    if text_lower in HELP_COMMANDS:
        await _send_help_menu(db, from_number, user=user)
        return

    # "add pet" command — restart pet portion of onboarding
    if text_lower in ("add pet", "new pet", "add another pet"):
        pet_count = (
            db.query(Pet)
            .filter(Pet.user_id == user.id, Pet.is_deleted == False)
            .count()
        )
        if pet_count >= MAX_PETS_PER_USER:
            await send_text_message(
                db, from_number,
                f"You already have {pet_count} pets registered. "
                f"Maximum is {MAX_PETS_PER_USER}.",
            )
        else:
            user.onboarding_state = "welcome"
            user.onboarding_data = None
            db.commit()
            await send_text_message(
                db, from_number,
                "Let's add another pet! What's your pet's name?",
            )
        return

    # "dashboard" / "link" command — exact match or phrase detection.
    # Handles: "dashboard", "link", "my dashboard", "send me the link",
    # "send dashboard link", "show link for ahu", etc.
    # Word-boundary check avoids false positives like "blinking".
    _dashboard_exact = {"dashboard", "link", "my dashboard"}
    _dashboard_phrases = ("dashboard", " link", "link ")
    if text_lower in _dashboard_exact or text_lower.startswith("link") or any(
        phrase in text_lower for phrase in _dashboard_phrases
    ):
        # Note: deferred care-plan suppression is handled globally near the
        # top of this function, so by the time we reach here we know no
        # deferred delivery is in progress and it's safe to send the link.
        await _send_dashboard_links(db, user)
        return

    # "order" / "shop" / "buy" command — start product ordering flow.
    # When AGENTIC_ORDER_ENABLED=true and OpenAI is reachable, use the
    # LLM-driven flow; otherwise fall back to the deterministic state machine.
    if text_lower in ORDER_COMMANDS:
        if _should_use_agentic_order():
            user.order_state = "agentic_order"
            db.commit()
            from app.services.agentic_order import handle_agentic_order_step
            await handle_agentic_order_step(db, user, message_data, send_text_message)
        else:
            from app.services.order_service import start_order_flow
            await start_order_flow(db, user)
        return

    # --- Edit intent detection ---
    # Trigger the agentic edit flow when the user wants to update pet or owner details.
    # Checked last so it doesn't intercept order/dashboard/help commands above.
    # Does NOT fire when the user is in an active order flow.
    if not user.order_state and _is_edit_intent(text_lower):
        from app.services.agentic_edit import handle_agentic_edit_intent
        await handle_agentic_edit_intent(db, user, message_data, send_text_message)
        return

    # --- Vet diet recommendation via chat ---
    # When the user mentions a vet-prescribed food in a message, extract and
    # persist it as a tagged diet item, then also answer any question present.
    if _is_vet_diet_intent(text_lower):
        chat_pet = (
            db.query(Pet)
            .filter(Pet.user_id == user.id, Pet.is_deleted == False)
            .order_by(Pet.created_at.desc())
            .first()
        )
        if chat_pet:
            await _handle_vet_diet_chat(db, user, text, from_number, chat_pet)
            return

    # General query — route to GPT query engine
    await _handle_query(db, user, text)


async def _send_help_menu(db: Session, from_number: str, user=None) -> None:
    """Send the help/commands menu to the user, personalised with pet name."""
    pet_name = None
    if user:
        pet = db.query(Pet).filter(Pet.user_id == user.id).order_by(Pet.created_at.desc()).first()
        if pet:
            pet_name = pet.name

    greeting = f"Hi there! How can I help with *{pet_name}*? 🐾" if pet_name else "Hi there! How can I help you today? 🐾"
    pet_possessive = f"{pet_name}'s" if pet_name else "your pet's"
    await send_text_message(
        db, from_number,
        f"{greeting}\n\n"
        "You can:\n"
        f"• Ask me anything about {pet_possessive} health\n"
        "• Send *add pet* to register another pet\n"
        f"• Send *dashboard* to view {pet_possessive} records\n"
        "• Send *order* to buy medicines, food, or supplements\n"
        "• Send *help* to see this menu\n"
        "• Upload a vet document for extraction",
    )


async def _try_handle_reschedule_date(
    db: Session, user, text: str, from_number: str,
) -> bool:
    """
    Check if user has a pending reschedule and route date input accordingly.

    A reschedule is pending when user.active_reminder_id is set.
    This is set by _handle_reminder_button when REMINDER_SCHEDULE is tapped.

    Returns True if the message was consumed as a reschedule date, False otherwise.
    """
    from app.services.reminder_response import apply_reschedule_date
    from app.utils.date_utils import parse_date, parse_date_with_ai

    # No pending reschedule state.
    if not getattr(user, "active_reminder_id", None):
        return False

    reminder_id = user.active_reminder_id

    # Verify the reminder still exists and belongs to this user.
    reminder = (
        db.query(Reminder)
        .join(Pet, Reminder.pet_id == Pet.id)
        .filter(
            Reminder.id == reminder_id,
            Pet.user_id == user.id,
            Pet.is_deleted == False,
        )
        .first()
    )

    if not reminder:
        # Stale state — clear it and do not consume the message.
        user.active_reminder_id = None
        db.commit()
        return False

    # Try to parse the user's text as a date — standard formats first, AI fallback.
    new_date = None
    try:
        new_date = parse_date(text.strip())
    except ValueError:
        try:
            new_date = await parse_date_with_ai(text.strip())
        except ValueError:
            await send_text_message(
                db, from_number,
                "I couldn't understand that date. Please try something like '15 April 2026' or '15/04/2026'.",
            )
            return True  # Consumed the message (even though it failed)

    try:
        result = apply_reschedule_date(db, reminder.id, new_date)
        # Clear the reschedule state only after a successful reschedule.
        user.active_reminder_id = None
        db.commit()
        await send_text_message(
            db, from_number,
            f"Rescheduled! New due date: {result.get('new_due_date', 'N/A')}",
        )
    except ValueError as e:
        await send_text_message(db, from_number, str(e))

    return True


async def _handle_button(db: Session, user, message_data: dict) -> None:
    """Handle a button response — route to reminder, conflict, or order handler."""
    payload = message_data.get("button_payload", "")
    from_number = _get_mobile(user)

    # --- Agentic order flow: forward button taps to the agent ---
    if user.order_state == "agentic_order":
        from app.services.agentic_order import handle_agentic_order_step
        await handle_agentic_order_step(db, user, message_data, send_text_message)
        return

    if payload in REMINDER_PAYLOADS:
        await _handle_reminder_button(db, user, payload)
    elif payload in CONFLICT_PAYLOADS:
        await _handle_conflict_button(db, user, payload)
    elif payload in ORDER_CATEGORY_PAYLOADS:
        from app.services.order_service import handle_order_category
        await handle_order_category(db, user, payload)
    elif payload in ORDER_CONFIRM_PAYLOADS:
        from app.services.order_service import handle_order_confirmation
        await handle_order_confirmation(db, user, payload)
    elif payload in NUDGE_PAYLOADS:
        await _handle_nudge_button(db, user, payload)
    else:
        logger.warning("Unknown button payload '%s' from %s", payload, from_number)
        await send_text_message(
            db, from_number,
            "Sorry, I didn't understand that response.",
        )


def _is_order_admin_number(from_number: str) -> bool:
    """Return True if sender number matches ORDER_NOTIFICATION_PHONE (digit-insensitive)."""
    configured = settings.ORDER_NOTIFICATION_PHONE or ""
    if not configured:
        return False

    configured_digits = "".join(ch for ch in configured if ch.isdigit())
    sender_digits = "".join(ch for ch in from_number if ch.isdigit())
    return bool(configured_digits) and sender_digits.endswith(configured_digits)


async def _handle_reminder_button(db: Session, user, payload: str) -> None:
    """
    Handle a reminder button response.

    Supports all 8 reminder payloads (Excel v5 4-stage lifecycle):
        REMINDER_DONE / REMINDER_ALREADY_DONE — mark completed, log next due
        REMINDER_SNOOZE_7                     — snooze by category days
        REMINDER_ORDER_NOW                    — snooze + trigger order flow
        REMINDER_STILL_PENDING                — update last_ignored_at, keep sent
        REMINDER_SCHEDULE / REMINDER_RESCHEDULE — prompt for new date
        REMINDER_CANCEL                       — mark snoozed / dismissed

    Uses Reminder.pet_id for the join (added in migration 028) to support
    reminders from all 5 source types (preventive_record, diet_item, etc.).
    """
    from app.services.reminder_response import handle_reminder_response

    from_number = _get_mobile(user)

    # Find the latest sent reminder for this user's pets via pet_id FK.
    # Reminder.pet_id was backfilled by migration 028 for all source types.
    reminder = (
        db.query(Reminder)
        .join(Pet, Reminder.pet_id == Pet.id)
        .filter(
            Pet.user_id == user.id,
            Pet.is_deleted == False,
            Reminder.status == "sent",
        )
        .order_by(Reminder.sent_at.desc())
        .first()
    )

    if not reminder:
        await send_text_message(db, from_number, "No active reminder found to respond to.")
        return

    try:
        result = handle_reminder_response(db, reminder.id, payload)

        if payload in (REMINDER_DONE, REMINDER_ALREADY_DONE):
            next_due = result.get("next_due_date", "N/A")
            await send_text_message(
                db, from_number,
                f"Marked as done! Next due: {next_due}",
            )
            # Refresh recognition bullets — marking done sets last_done_date, which
            # changes the preventive care bullet count in "What We Found".
            try:
                from app.services.precompute_service import precompute_dashboard_enrichments
                asyncio.create_task(precompute_dashboard_enrichments(str(reminder.pet_id)))
            except Exception as _exc:
                logger.warning("reminder DONE: failed to schedule recognition refresh: %s", _exc)

        elif payload == REMINDER_SNOOZE_7:
            new_due = result.get("new_due_date", "N/A")
            await send_text_message(
                db, from_number,
                f"Got it — I'll remind you again on {new_due}.",
            )

        elif payload == REMINDER_ORDER_NOW:
            # Reminder handler marks it snoozed; now initiate the order flow.
            if _should_use_agentic_order():
                user.order_state = "agentic_order"
                db.commit()
                from app.services.agentic_order import handle_agentic_order_step
                await handle_agentic_order_step(db, user, {}, send_text_message)
            else:
                from app.services.order_service import start_order_flow
                await start_order_flow(db, user)

        elif payload == REMINDER_STILL_PENDING:
            await send_text_message(
                db, from_number,
                "Noted! I'll check in again soon.",
            )

        elif payload in (REMINDER_SCHEDULE, REMINDER_RESCHEDULE):
            # Store reminder ID on user so _try_handle_reschedule_date can find it.
            user.active_reminder_id = reminder.id
            db.commit()
            await send_text_message(
                db, from_number,
                "What new date works for you? Reply in any format — e.g. 15 April 2026, 15/04/2026, Apr 15.",
            )

        elif payload == REMINDER_CANCEL:
            await send_text_message(db, from_number, "Reminder dismissed.")

    except ValueError as e:
        await send_text_message(db, from_number, str(e))


async def _handle_conflict_button(db: Session, user, payload: str) -> None:
    """Handle a conflict resolution button response."""
    from app.models.preventive_record import PreventiveRecord
    from app.services.conflict_engine import resolve_conflict

    from_number = _get_mobile(user)

    # Find the latest pending conflict for this user's pets via direct JOIN
    # (avoids separate pet query).
    conflict = (
        db.query(ConflictFlag)
        .join(PreventiveRecord, ConflictFlag.preventive_record_id == PreventiveRecord.id)
        .join(Pet, PreventiveRecord.pet_id == Pet.id)
        .filter(
            Pet.user_id == user.id,
            Pet.is_deleted == False,
            ConflictFlag.status == "pending",
        )
        .order_by(ConflictFlag.created_at.desc())
        .first()
    )

    if not conflict:
        await send_text_message(db, from_number, "No pending conflicts found.")
        return

    try:
        resolve_conflict(db, conflict.id, payload)
        if payload == CONFLICT_USE_NEW:
            await send_text_message(db, from_number, "Updated to the new date.")
        else:
            await send_text_message(db, from_number, "Kept the existing date.")
        # Preventive record date changed — refresh dashboard cache.
        try:
            from app.services.precompute_service import precompute_dashboard_enrichments
            pet_for_conflict = (
                db.query(Pet)
                .join(PreventiveRecord, Pet.id == PreventiveRecord.pet_id)
                .join(ConflictFlag, ConflictFlag.preventive_record_id == PreventiveRecord.id)
                .filter(ConflictFlag.id == conflict.id)
                .first()
            )
            if pet_for_conflict:
                asyncio.create_task(precompute_dashboard_enrichments(str(pet_for_conflict.id)))
        except Exception as _pre_exc:
            logger.warning("conflict resolve: failed to schedule precompute: %s", _pre_exc)
    except ValueError as e:
        await send_text_message(db, from_number, str(e))


async def _handle_nudge_button(db: Session, user, payload: str) -> None:
    """Handle a nudge button response (action, dismiss, view dashboard)."""
    from app.models.dashboard_token import DashboardToken
    from app.services.nudge_sender import record_nudge_engagement
    from app.services.whatsapp_sender import send_text_message

    from_number = _get_mobile(user)

    # Find user's active pet
    pet = (
        db.query(Pet)
        .filter(Pet.user_id == user.id, Pet.is_deleted == False)
        .first()
    )

    if not pet:
        await send_text_message(db, from_number, "No active pet found.")
        return

    if payload == NUDGE_ACTION:
        record_nudge_engagement(db, user.id, pet.id)
        await send_text_message(
            db, from_number,
            "Great! Open your dashboard to take action on this health recommendation.",
        )
    elif payload == NUDGE_DISMISS:
        # Dismiss the most recent undismissed nudge
        from app.models.nudge import Nudge
        nudge = (
            db.query(Nudge)
            .filter(
                Nudge.pet_id == pet.id,
                Nudge.dismissed == False,
                Nudge.mandatory == False,
            )
            .order_by(Nudge.created_at.desc())
            .first()
        )
        if nudge:
            nudge.dismissed = True
            db.commit()
            await send_text_message(db, from_number, "Nudge dismissed.")
        else:
            await send_text_message(db, from_number, "No dismissible nudges found.")
    elif payload == NUDGE_VIEW_DASHBOARD:
        record_nudge_engagement(db, user.id, pet.id)
        token = (
            db.query(DashboardToken)
            .filter(DashboardToken.pet_id == pet.id, DashboardToken.is_active == True)
            .first()
        )
        if token:
            from app.config import settings
            url = f"{settings.FRONTEND_URL}/dashboard/{token.token}"
            await send_text_message(db, from_number, f"Here's your dashboard:\n{url}")
        else:
            await send_text_message(
                db, from_number,
                "Type *dashboard* to get a fresh link to your pet's health dashboard.",
            )


async def _handle_media(db: Session, user, message_data: dict) -> None:
    """
    Handle image or document uploads with batch limiting.

    Enforces a strict per-pet batch limit (MAX_PENDING_DOCS_PER_PET) using
    an in-memory counter to avoid DB race conditions when many files arrive
    concurrently. Files beyond the limit are rejected BEFORE downloading.

    Extraction is deferred: after the last upload in a batch settles
    (no new files for _EXTRACTION_DELAY_SECONDS), all pending documents
    for the pet are extracted together. This prevents per-file GPT calls
    from exhausting DB connections and API rate limits.
    """
    from app.services.document_upload import process_document_upload

    from_number = _get_mobile(user)
    media_id = message_data.get("media_id")
    original_filename = message_data.get("filename")
    caption = message_data.get("caption")

    if not media_id:
        await send_text_message(db, from_number, "Couldn't process that file. Please try again.")
        return

    # If the document/image was sent without any caption, that's fine —
    # but log it so we can track standalone uploads vs. captioned ones.
    if not caption:
        logger.info(
            "Document sent without caption from %s (media_id=%s)",
            mask_phone(from_number), media_id,
        )

    # Find user's most recent active pet.
    pet = (
        db.query(Pet)
        .filter(Pet.user_id == user.id, Pet.is_deleted == False)
        .order_by(Pet.created_at.desc())
        .first()
    )

    if not pet:
        await send_text_message(db, from_number, "Please register a pet first.")
        return

    # --- Ghost record prevention ---
    # Primary dedup: check if a Document with this wamid already exists.
    # This is the strongest dedup — one Document per WhatsApp message,
    # regardless of filename, media_id, or server restarts.
    message_id = message_data.get("message_id")

    if message_id:
        existing_by_wamid = (
            db.query(Document.id)
            .filter(Document.source_wamid == message_id)
            .first()
        )
        if existing_by_wamid:
            logger.info(
                "Duplicate document detected (wamid dedup): wamid=%s, "
                "pet_id=%s — skipping.",
                message_id, str(pet.id),
            )
            return

    # Secondary dedup: check by filename or media_id as fallback.
    from datetime import datetime, timedelta
    dedup_cutoff = datetime.utcnow() - timedelta(hours=24)

    if original_filename:
        existing_doc = (
            db.query(Document.id)
            .filter(
                Document.pet_id == pet.id,
                Document.document_name == original_filename,
                Document.created_at >= dedup_cutoff,
            )
            .first()
        )
        if existing_doc:
            logger.info(
                "Duplicate document detected (filename dedup): filename=%s, "
                "pet_id=%s, message_id=%s — skipping.",
                original_filename, str(pet.id), message_id,
            )
            return
    elif media_id:
        existing_doc = (
            db.query(Document.id)
            .filter(
                Document.pet_id == pet.id,
                Document.file_path.like(f"%{media_id}%"),
                Document.created_at >= dedup_cutoff,
            )
            .first()
        )
        if existing_doc:
            logger.info(
                "Duplicate image detected (media_id dedup): media_id=%s, "
                "pet_id=%s, message_id=%s — skipping.",
                media_id, str(pet.id), message_id,
            )
            return

    # --- Batch limit check (in-memory, race-safe) ---
    # Count recent uploads for this pet within the batch window.
    pet_key = str(pet.id)
    now = time.time()
    cutoff = now - _UPLOAD_BATCH_WINDOW_SECONDS

    # Clean up old entries outside the batch window.
    if pet_key in _recent_uploads:
        _recent_uploads[pet_key] = [
            ts for ts in _recent_uploads[pet_key] if ts > cutoff
        ]
    else:
        _recent_uploads[pet_key] = []

    recent_count = len(_recent_uploads[pet_key])

    if recent_count >= MAX_DOCS_PER_SESSION:
        # Only send the rejection message once per batch to avoid spamming.
        if not _rejection_sent.get(pet_key):
            _rejection_sent[pet_key] = True
            await send_text_message(
                db, from_number,
                f"I've got these — let's continue with {pet.name}'s care plan. "
                f"You can send more once I've processed this batch.",
            )
        return

    # Track this upload in the in-memory batch window.
    _recent_uploads[pet_key].append(now)

    # --- Backpressure check ---
    # If too many tasks are already waiting on the semaphore, reject this
    # upload immediately instead of queuing another coroutine. This prevents
    # event loop overload during traffic spikes (e.g. a user bulk-forwarding
    # 50 files) without silently dropping messages — the user gets a clear
    # "try again" message rather than an indefinite wait.
    global _upload_queue_depth
    if _upload_queue_depth >= MAX_QUEUED_UPLOADS:
        logger.warning(
            "Upload queue full (%d/%d) — rejecting upload for pet=%s mobile=%s",
            _upload_queue_depth, MAX_QUEUED_UPLOADS,
            pet_key, mask_phone(from_number),
        )
        _recent_uploads[pet_key].pop()
        await send_text_message(
            db, from_number,
            "We're receiving a lot of uploads right now. "
            "Please try again in a moment.",
        )
        return

    _upload_queue_depth += 1
    try:
        # Gate download + DB writes so at most MAX_CONCURRENT_UPLOAD_PROCESSING
        # tasks run this section at once. Without this, 20 simultaneous uploads
        # would check out 20 DB connections concurrently, overwhelming the pool
        # and triggering SSL termination on Supabase's side.
        async with _upload_processing_semaphore:
            # --- Download media from WhatsApp ---
            media_result = await download_whatsapp_media(media_id)
            if not media_result:
                # Remove the tracked upload since download failed.
                _recent_uploads[pet_key].pop()
                await send_text_message(db, from_number, "Failed to download the file. Please try again.")
                return

            file_content, detected_mime = media_result

            try:
                filename = original_filename or f"{media_id}.{_mime_to_ext(detected_mime)}"
                document = await process_document_upload(
                    db=db,
                    pet_id=pet.id,
                    user_id=user.id,
                    filename=filename,
                    file_content=file_content,
                    mime_type=detected_mime,
                    pet_name=pet.name,
                    source_wamid=message_id,
                )

                # Track this exact document in the current in-memory batch so the
                # deferred extractor doesn't accidentally sweep unrelated pending docs.
                _batch_document_ids.setdefault(pet_key, []).append(document.id)

                # --- Immediate post-onboarding upload acknowledgement ---
                # When a user sends documents AFTER onboarding, they wait through a
                # 15s batch window + extraction time with no feedback.  Send a quick
                # "Got it 🐾" on the FIRST document of a post-onboarding batch so the
                # user knows their upload was received.  The detailed processing
                # message still fires from the batch extractor once the window closes.
                is_first_in_batch = len(_batch_document_ids[pet_key]) == 1
                if is_first_in_batch and user.onboarding_state != "awaiting_documents":
                    try:
                        await send_text_message(
                            db,
                            from_number,
                            f"Got it 🐾 I'll update {pet.name}'s records once I've gone through "
                            "what you sent. Feel free to share more documents — I'll process "
                            "them together.",
                        )
                    except Exception as ack_exc:
                        logger.warning(
                            "Immediate upload ack failed for pet=%s: %s", str(pet.id), ack_exc
                        )

                # Persist onboarding intent for this batch at upload time. The
                # extraction pass later decides whether to finalize onboarding based
                # on this flag AND whether the user asked to keep uploading more
                # (see `is_upload_window_extended`).
                if user.onboarding_state == "awaiting_documents":
                    _batch_is_onboarding[pet_key] = True
                    # Keep the deadline timer alive so auto-finalization still fires
                    # at the end of the window if the user goes silent.
                    _schedule_document_window_timer(
                        user_id=user.id,
                        from_number=from_number,
                        deadline=user.doc_upload_deadline,
                    )
                else:
                    _batch_is_onboarding.setdefault(pet_key, False)

                # Schedule (or reschedule) a deferred batch extraction.
                # The timer resets with each new upload so extraction only starts
                # after uploads have settled (_EXTRACTION_DELAY_SECONDS of silence).
                _schedule_batch_extraction(
                    pet_id=pet.id,
                    pet_name=pet.name,
                    user_id=user.id,
                    from_number=from_number,
                )

            except ValueError as e:
                # Remove the tracked upload since storage failed.
                _recent_uploads[pet_key].pop()
                error_str = str(e)
                if "not allowed" in error_str or "File type" in error_str:
                    # Unsupported MIME type (e.g. .docx): suppress per-file message.
                    # Track the count so it appears in the batch acknowledgment instead.
                    _unsupported_format_count[pet_key] = (
                        _unsupported_format_count.get(pet_key, 0) + 1
                    )
                    # Schedule a timer so the acknowledgment fires even if no valid
                    # documents are added to the batch.
                    _schedule_batch_extraction(
                        pet_id=pet.id,
                        pet_name=pet.name,
                        user_id=user.id,
                        from_number=from_number,
                    )
                else:
                    # File-size or daily-limit errors: send immediately — these are
                    # batch-level constraints the user needs to know about right away.
                    await send_text_message(db, from_number, error_str)
            except RuntimeError:
                _recent_uploads[pet_key].pop()
                # Always schedule the extraction timer even when this individual doc
                # failed — other docs in the batch may have already succeeded and
                # still need extraction + summary. Without this call, a DB error on
                # one doc would leave successfully-uploaded docs with no timer and
                # no user feedback.
                _schedule_batch_extraction(
                    pet_id=pet.id,
                    pet_name=pet.name,
                    user_id=user.id,
                    from_number=from_number,
                )
                await send_text_message(db, from_number, "Upload failed. Please try again later.")
    finally:
        # Always decrement the backpressure counter, whether the upload
        # succeeded, failed, or was rejected by an exception. This ensures
        # the counter stays accurate across all exit paths so future uploads
        # are not incorrectly throttled by stale counts.
        _upload_queue_depth -= 1


def _schedule_batch_extraction(
    pet_id, pet_name, user_id, from_number,
) -> None:
    """
    Schedule (or reschedule) a deferred batch extraction for a pet.

    Each new upload resets the timer. Extraction only starts after
    _EXTRACTION_DELAY_SECONDS of no new uploads, ensuring the full
    batch is received before processing begins.
    """
    pet_key = str(pet_id)

    # Cancel existing timer for this pet (debounce).
    existing = _extraction_timers.get(pet_key)
    if existing and not existing.done():
        existing.cancel()

    # Schedule a new delayed extraction.
    _extraction_timers[pet_key] = asyncio.create_task(
        _delayed_batch_extraction(pet_id, pet_name, user_id, from_number)
    )


async def run_extraction_batch(
    pet_id: str,
    document_ids: list,
    user_id: str,
    from_number,
    pet_name: str,
) -> None:
    """
    Run GPT extraction for a batch of pending documents and send the result summary.

    This is the core extraction loop, decoupled from the debounce timer so it
    can be called by the in-process RabbitMQ consumer (document_consumer.py) or
    directly as a fallback when the queue is unavailable.

    Args:
        pet_id:        UUID string of the pet.
        document_ids:  List of Document UUID strings to extract.
        user_id:       UUID string of the owning user.
        from_number:   WhatsApp mobile number for replies (None = dashboard upload).
        pet_name:      Pet's display name for error messages.
    """
    from app.database import get_fresh_session
    from app.models.user import User
    from app.services.gpt_extraction import extract_and_process_document

    pet_key = str(pet_id)
    bg_db = get_fresh_session()

    try:
        pending_docs = (
            bg_db.query(Document)
            .filter(
                Document.pet_id == pet_id,
                Document.extraction_status == "pending",
                Document.id.in_(document_ids),
            )
            .order_by(Document.created_at.asc())
            .all()
        )

        if not pending_docs:
            logger.info(
                "[extraction] No pending docs found for pet=%s (already processed?)",
                pet_key,
            )
            # Docs were processed by another consumer or path — still clear any
            # lingering deferred marker so the user is not permanently locked out.
            user = bg_db.query(User).filter(User.id == user_id).first()
            pet = bg_db.query(Pet).filter(Pet.id == pet_id).first()
            if pet and _has_pending_deferred_care_plan(bg_db, pet.id, user=user):
                try:
                    _clear_deferred_care_plan_marker(bg_db, pet.id, user=user)
                    bg_db.commit()
                    logger.info(
                        "[extraction] Cleared stale deferred marker for pet=%s (no pending docs)",
                        pet_key,
                    )
                except Exception as _clr_exc:
                    logger.warning(
                        "[extraction] Could not clear stale deferred marker for pet=%s: %s",
                        pet_key, _clr_exc,
                    )
                    try:
                        bg_db.rollback()
                    except Exception:
                        pass

            # If all batch docs were already extracted, notify the user so they
            # know the upload was received (rather than getting no response at all).
            if document_ids and from_number and pet:
                try:
                    duplicate_count = (
                        bg_db.query(Document)
                        .filter(
                            Document.id.in_(document_ids),
                            Document.extraction_status.in_(["success", "partially_extracted"]),
                        )
                        .count()
                    )
                    if duplicate_count > 0:
                        pet_display = (pet.name if pet else None) or pet_name
                        dashboard_link = _get_dashboard_link(bg_db, pet)
                        msg = (
                            f"These documents are already in {pet_display}'s records — "
                            f"no changes needed."
                        )
                        if dashboard_link:
                            msg += f"\n\nYou can view all records here:\n{dashboard_link}"
                        await send_text_message(bg_db, from_number, msg)
                except Exception as _dup_exc:
                    logger.warning(
                        "[extraction] Could not check duplicate count for pet=%s: %s",
                        pet_key, _dup_exc,
                    )
            return

        total = len(pending_docs)
        user = bg_db.query(User).filter(User.id == user_id).first()
        pet = bg_db.query(Pet).filter(Pet.id == pet_id).first()
        if user and from_number:
            user._plaintext_mobile = from_number

        logger.info(
            "[extraction] Starting batch: pet=%s, %d docs", pet_key, total
        )

        success_count = 0
        fail_count = 0
        failed_docs: list[dict] = []
        all_results = []

        doc_id_to_name: dict[str, str] = {
            str(doc.id): (doc.document_name or doc.file_path.split("/")[-1])
            for doc in pending_docs
        }

        for idx, doc in enumerate(pending_docs, 1):
            async with _get_extraction_semaphore():
                try:
                    from app.services.document_upload import download_from_supabase
                    file_bytes = await download_from_supabase(
                        doc.file_path,
                        backend=getattr(doc, "storage_backend", "supabase"),
                    )

                    if not file_bytes:
                        fail_count += 1
                        doc_label = doc_id_to_name.get(str(doc.id), doc.file_path.split("/")[-1])
                        failed_docs.append({"name": doc_label, "reason": "download_failed", "extra": ""})
                        doc.extraction_status = "failed"
                        logger.error(
                            "File download returned None for doc %s (backend=%s, path=%s)",
                            str(doc.id), getattr(doc, "storage_backend", "supabase"), doc.file_path,
                        )
                        bg_db.commit()
                        continue

                    result = await asyncio.wait_for(
                        extract_and_process_document(
                            bg_db, doc.id,
                            f"[file: {doc.file_path}]",
                            file_bytes=file_bytes,
                        ),
                        timeout=120,
                    )
                    all_results.append(result)

                    doc_label = doc_id_to_name.get(str(doc.id), doc.file_path.split("/")[-1])
                    if result.get("status") == "failed":
                        fail_count += 1
                        failed_docs.append({"name": doc_label, "reason": "unclear", "extra": ""})
                    elif result.get("status") == "rejected":
                        doc_type = result.get("document_type", "")
                        if doc_type == "not_pet_related":
                            failed_docs.append({"name": doc_label, "reason": "not_health", "extra": ""})
                        elif doc_type == "pet_name_mismatch":
                            errors = result.get("errors") or []
                            other_pet = ""
                            for err in errors:
                                if "appears to be for" in err:
                                    import re
                                    m = re.search(r"appears to be for ['\"]?([^'\",.]+)['\"]?", err)
                                    if m:
                                        other_pet = m.group(1).strip()
                                    break
                            failed_docs.append({"name": doc_label, "reason": "wrong_pet", "extra": other_pet})
                        else:
                            failed_docs.append({"name": doc_label, "reason": "unclear", "extra": ""})
                    else:
                        success_count += 1

                    logger.info(
                        "Extracted doc %d/%d (id=%s) for pet %s: status=%s",
                        idx, total, str(doc.id), str(pet_id), result.get("status"),
                    )

                except TimeoutError:
                    fail_count += 1
                    doc_label = doc_id_to_name.get(str(doc.id), doc.file_path.split("/")[-1])
                    failed_docs.append({"name": doc_label, "reason": "timeout", "extra": ""})
                    logger.error(
                        "Extraction timed out for doc %s (%d/%d) pet %s",
                        str(doc.id), idx, total, str(pet_id),
                    )
                    try:
                        doc.extraction_status = "failed"
                        bg_db.commit()
                    except Exception:
                        try:
                            bg_db.rollback()
                        except Exception:
                            pass

                except Exception as e:
                    fail_count += 1
                    doc_label = doc_id_to_name.get(str(doc.id), doc.file_path.split("/")[-1])
                    failed_docs.append({"name": doc_label, "reason": "unclear", "extra": ""})
                    logger.error(
                        "Extraction failed for doc %s (%d/%d): %s",
                        str(doc.id), idx, total, str(e),
                    )
                    try:
                        bg_db.rollback()
                    except Exception:
                        pass
                    try:
                        doc.extraction_status = "failed"
                        bg_db.commit()
                    except Exception:
                        try:
                            bg_db.rollback()
                        except Exception:
                            pass

        # Send one consolidated summary after all extractions complete.
        # Only send via WhatsApp if we have a phone number (dashboard uploads skip this).
        if from_number and user and pet:
            user._plaintext_mobile = from_number
            if _has_pending_deferred_care_plan(bg_db, pet.id, user=user):
                await _send_deferred_care_plan(
                    bg_db, user, pet, from_number,
                    all_results=all_results,
                    success_count=success_count,
                    fail_count=fail_count,
                    failed_docs=failed_docs,
                    doc_id_to_name=doc_id_to_name,
                )
            else:
                await _send_batch_summary(
                    bg_db, user, pet, from_number,
                    all_results, success_count, fail_count, failed_docs,
                )

    except Exception as e:
        logger.error("[extraction] Batch failed for pet=%s: %s", pet_key, str(e))
        try:
            bg_db.rollback()
        except Exception:
            pass
        if from_number:
            try:
                from app.database import get_fresh_session as _get_fresh_session
                _err_db = _get_fresh_session()
                try:
                    await send_text_message(
                        _err_db, from_number,
                        f"Extraction encountered an issue for {pet_name}. "
                        f"Try uploading again.",
                    )
                finally:
                    _err_db.close()
            except Exception:
                pass
    finally:
        bg_db.close()


async def _delayed_batch_extraction(
    pet_id, pet_name, user_id, from_number,
) -> None:
    """
    Wait for uploads to settle, then hand off to the RabbitMQ extraction queue.

    Handles the debounce window (15s sleep), onboarding finalization, and the
    pre-extraction acknowledgment. The actual GPT extraction loop is handled by
    the in-process consumer via run_extraction_batch(). Falls back to a direct
    asyncio task if the queue is unavailable (no CLOUDAMQP_URL configured).
    """
    await asyncio.sleep(_EXTRACTION_DELAY_SECONDS)

    pet_key = str(pet_id)

    # Clean up the extraction timer entry.
    _extraction_timers.pop(pet_key, None)

    from app.database import get_fresh_session

    bg_db = get_fresh_session()
    try:
        # Fetch only documents explicitly uploaded in this WhatsApp batch.
        # This prevents unrelated pending documents (e.g. dashboard uploads)
        # from being included in the current extraction summary.
        batched_doc_ids = list(_batch_document_ids.get(pet_key, []))
        if not batched_doc_ids:
            # All files in this batch were rejected before reaching the DB
            # (e.g. unsupported MIME type). Send a single message if any
            # unsupported-format files were tracked.
            unsupported_count = _unsupported_format_count.pop(pet_key, 0)
            if unsupported_count > 0:
                await send_text_message(
                    bg_db, from_number,
                    f"Those {unsupported_count} file(s) couldn't be read as they're "
                    f"in an unsupported format (like .docx). You can share these as "
                    f"an image or PDF and I'll pick them up right away.",
                )
            _batch_is_onboarding.pop(pet_key, None)
            return

        pending_docs = (
            bg_db.query(Document)
            .filter(
                Document.pet_id == pet_id,
                Document.extraction_status == "pending",
                Document.id.in_(batched_doc_ids),
            )
            .order_by(Document.created_at.asc())
            .all()
        )

        if not pending_docs:
            # DB has no pending docs in this batch (already extracted or failed).
            # Check how many were already-processed duplicates so we can tell
            # the user their documents are already on record.
            duplicate_count = 0
            if batched_doc_ids and from_number:
                duplicate_count = (
                    bg_db.query(Document)
                    .filter(
                        Document.id.in_(batched_doc_ids),
                        Document.extraction_status.in_(["success", "partially_extracted"]),
                    )
                    .count()
                )
            unsupported_count = _unsupported_format_count.pop(pet_key, 0)
            _batch_document_ids.pop(pet_key, None)
            _batch_is_onboarding.pop(pet_key, None)
            if from_number:
                if duplicate_count > 0:
                    pet_obj = bg_db.query(Pet).filter(Pet.id == pet_id).first()
                    pet_display = (pet_obj.name if pet_obj else None) or pet_name
                    dashboard_link = _get_dashboard_link(bg_db, pet_obj) if pet_obj else None
                    msg = (
                        f"These documents are already in {pet_display}'s records — "
                        f"no changes needed."
                    )
                    if dashboard_link:
                        msg += f"\n\nYou can view all records here:\n{dashboard_link}"
                    await send_text_message(bg_db, from_number, msg)
                elif unsupported_count > 0:
                    await send_text_message(
                        bg_db, from_number,
                        f"Those {unsupported_count} file(s) couldn't be read as they're "
                        f"in an unsupported format (like .docx). You can share these as "
                        f"an image or PDF and I'll pick them up right away.",
                    )
            return

        total = len(pending_docs)
        logger.info(
            "Debounce settled for pet %s: %d docs ready for queue",
            str(pet_id), total,
        )

        from app.models.user import User

        user = bg_db.query(User).filter(User.id == user_id).first()
        pet = bg_db.query(Pet).filter(Pet.id == pet_id).first()
        if user:
            user._plaintext_mobile = from_number

        # Decide whether to finalize onboarding after this batch.
        #
        # Rule: if the user uploaded documents during `awaiting_documents` and
        # did NOT explicitly ask to add more, finalize onboarding now (the
        # normal "That's everything..." flow).
        #
        # If the user explicitly asked to add more (detected earlier and
        # recorded via `mark_upload_window_extended`), keep them in the upload
        # window — they'll stay until they type 'skip' or the deadline expires.
        should_finalize_onboarding = (
            bool(_batch_is_onboarding.get(pet_key, False))
            and user is not None
            and user.onboarding_state == "awaiting_documents"
            and not is_upload_window_extended(user.id)
        )
        # Read unsupported count before clearing state.
        unsupported_count = _unsupported_format_count.pop(pet_key, 0)

        # --- Clear in-memory batch state (the batch window is now closed) ---
        # Do this before publishing so the state is never stale if the
        # publish raises an exception and we re-enter via the fallback path.
        _recent_uploads.pop(pet_key, None)
        _rejection_sent.pop(pet_key, None)
        _batch_document_ids.pop(pet_key, None)
        _batch_is_onboarding.pop(pet_key, None)

        # --- Onboarding finalization (must happen before extraction starts) ---
        if should_finalize_onboarding:
            try:
                from app.services.onboarding import _finalize_onboarding
                _cancel_document_window_timer(user.id)
                clear_upload_window_extended(user.id)
                await _finalize_onboarding(bg_db, user, send_text_message)
            except Exception as e:
                logger.warning(
                    "Could not finalize onboarding after extraction for user=%s: %s",
                    str(user.id), str(e),
                )
                try:
                    bg_db.rollback()
                except Exception:
                    pass
                should_finalize_onboarding = False

        # --- Send acknowledgment before extraction starts (post-onboarding only) ---
        # Onboarding batches already have the "That's everything, building care
        # plan..." transition message, so we skip the ack there.
        if not should_finalize_onboarding and pet and user:
            ack = (
                f"Got it — I've received your documents 🐾\n\n"
                f"I'm starting to process them now to update {pet.name}'s records."
            )
            if unsupported_count > 0:
                _they_re = "they're" if unsupported_count != 1 else "it's"
                _these = "these" if unsupported_count != 1 else "this"
                _them = "them" if unsupported_count != 1 else "it"
                ack += (
                    f"\n\nJust a heads up: Some documents couldn't be read as {_they_re} "
                    f"in an unsupported format (like .docx). You can share "
                    f"{_these} as an image or PDF and I'll pick {_them} "
                    f"up right away.\n\nGive me a few seconds while I go through the rest."
                )
            else:
                ack += "\n\nGive me a few seconds while I go through the rest."
            try:
                await send_text_message(bg_db, from_number, ack)
            except Exception as _ack_err:
                # An SSL drop or pool error here must not abort extraction — the
                # user will still get the batch summary at the end even if the
                # pre-extraction acknowledgment failed to deliver.
                logger.warning(
                    "Pre-extraction ack failed for pet=%s, continuing: %s",
                    str(pet_id), _ack_err,
                )

        # --- Publish extraction job to RabbitMQ ---
        # The consumer (document_consumer.py) picks this up and calls
        # run_extraction_batch(). Falls back to a direct asyncio task
        # when CLOUDAMQP_URL is not set (local dev / broker down).
        doc_ids_str = [str(d.id) for d in pending_docs]
        try:
            from app.services import queue_service
            published = await queue_service.publish_extraction_job(
                pet_id=str(pet_id),
                document_ids=doc_ids_str,
                user_id=str(user_id),
                from_number=from_number,
                pet_name=pet_name,
                source="whatsapp",
            )
        except Exception as _q_exc:
            logger.warning("[queue] publish_extraction_job raised: %s", _q_exc)
            published = False

        if not published:
            # Queue unavailable — run extraction directly in this process.
            logger.info(
                "[queue] Fallback: running extraction directly for pet=%s", str(pet_id)
            )
            asyncio.create_task(run_extraction_batch(
                pet_id=str(pet_id),
                document_ids=doc_ids_str,
                user_id=str(user_id),
                from_number=from_number,
                pet_name=pet_name,
            ))

    except Exception as e:
        logger.error(
            "Delayed batch extraction setup failed for pet %s: %s", str(pet_id), str(e),
        )
        try:
            bg_db.rollback()
        except Exception:
            pass
        # Clear batch counter even on failure so user is never stuck.
        _recent_uploads.pop(pet_key, None)
        _batch_document_ids.pop(pet_key, None)
        _batch_is_onboarding.pop(pet_key, None)
        _unsupported_format_count.pop(pet_key, None)
    finally:
        bg_db.close()


async def _handle_query(db: Session, user, text: str) -> None:
    """Handle a general text query via GPT query engine.

    Passes the last few conversation turns so the model can resolve
    follow-up questions in context (e.g. "tell me more", "what about X?").
    Updates the per-user history buffer after each successful answer.
    """
    from app.services.query_engine import answer_pet_question

    from_number = _get_mobile(user)

    pet = (
        db.query(Pet)
        .filter(Pet.user_id == user.id, Pet.is_deleted == False)
        .order_by(Pet.created_at.desc())
        .first()
    )

    if not pet:
        await send_text_message(db, from_number, "Please register a pet first.")
        return

    # Retrieve recent conversation turns for context-aware answering.
    history = _get_query_history(from_number)

    try:
        # 45s timeout prevents a stuck GPT call from hanging the user's session.
        result = await asyncio.wait_for(
            answer_pet_question(db, pet.id, text, conversation_history=history),
            timeout=45,
        )
        answer = result.get("answer", "Sorry, I couldn't find an answer.")

        # Persist this exchange so future messages can reference it.
        if result.get("status") == "success":
            _update_query_history(from_number, text, answer)

        await send_text_message(db, from_number, answer)
    except TimeoutError:
        logger.error("Query engine timed out for pet %s", str(pet.id))
        await send_text_message(
            db, from_number,
            "Your question is taking too long to process. Please try again.",
        )
    except Exception as e:
        logger.error("Query engine error: %s", str(e))
        await send_text_message(
            db, from_number,
            "Sorry, I couldn't process your question. Please try again later.",
        )


async def _send_dashboard_links(db, user) -> None:
    """
    Send dashboard links for all user's pets.

    Auto-regenerates expired or revoked tokens so the user always
    receives a working link.
    Includes active reminders for each pet.
    """
    from datetime import datetime

    from app.config import settings
    from app.models.dashboard_token import DashboardToken
    from app.models.preventive_master import PreventiveMaster
    from app.models.preventive_record import PreventiveRecord
    from app.models.reminder import Reminder
    from app.services.onboarding import refresh_dashboard_token

    from_number = _get_mobile(user)

    pets = db.query(Pet).filter(
        Pet.user_id == user.id, Pet.is_deleted == False
    ).all()

    if not pets:
        await send_text_message(db, from_number, "No pets found.")
        return

    # Batch-load all active tokens for user's pets to avoid N+1 queries.
    pet_ids = [p.id for p in pets]
    tokens = (
        db.query(DashboardToken)
        .filter(DashboardToken.pet_id.in_(pet_ids), DashboardToken.revoked == False)
        .all()
    )
    token_by_pet = {t.pet_id: t for t in tokens}

    messages = []
    for pet in pets:
        try:
            token_record = token_by_pet.get(pet.id)

            # Auto-refresh if token is expired or missing.
            if token_record and token_record.expires_at and datetime.utcnow() > token_record.expires_at:
                new_token = refresh_dashboard_token(db, pet.id)
                dashboard_url = f"{settings.FRONTEND_URL}/dashboard/{new_token}"
            elif token_record:
                dashboard_url = f"{settings.FRONTEND_URL}/dashboard/{token_record.token}"
            else:
                # No token at all — generate a fresh one.
                new_token = refresh_dashboard_token(db, pet.id)
                dashboard_url = f"{settings.FRONTEND_URL}/dashboard/{new_token}"

            pet_msg = f"*{pet.name}'s Dashboard*:\n{dashboard_url}"

            # Pre-warm dashboard cache so the first load reads from DB with no API calls.
            try:
                import asyncio as _asyncio
                from app.services.precompute_service import precompute_dashboard_enrichments
                _asyncio.create_task(precompute_dashboard_enrichments(str(pet.id)))
            except Exception as _pre_exc:
                logger.warning("precompute task scheduling failed for pet=%s: %s", pet.id, _pre_exc)

            # Fetch and append active reminders for this pet
            try:
                reminders = (
                    db.query(Reminder, PreventiveRecord, PreventiveMaster)
                    .join(PreventiveRecord, Reminder.preventive_record_id == PreventiveRecord.id)
                    .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
                    .filter(
                        PreventiveRecord.pet_id == pet.id,
                        Reminder.status.in_(["pending", "sent"]),
                    )
                    .order_by(Reminder.next_due_date.asc())
                    .all()
                )

                if reminders:
                    pet_msg += "\n\nActive Reminders:"
                    for reminder, record, master in reminders:
                        due_date_str = reminder.next_due_date.strftime("%d/%m/%Y")
                        pet_msg += f"\n• {master.item_name}: Due {due_date_str}"
            except Exception as e:
                logger.error("Failed to fetch reminders for pet %s: %s", str(pet.id), str(e))

            messages.append(pet_msg)
        except Exception as e:
            logger.error("Failed to get/refresh token for pet %s: %s", str(pet.id), str(e))
            messages.append(f"*{pet.name}'s Dashboard*: Link temporarily unavailable")
            try:
                db.rollback()
            except Exception:
                pass

    await send_text_message(
        db, from_number,
        "Your pet dashboards:\n\n" + "\n\n".join(messages),
    )


def _get_dashboard_link(db: Session, pet) -> str | None:
    """
    Get the active dashboard link for a pet.

    Returns the full URL if a valid token exists, None otherwise.
    Auto-refreshes expired tokens. Never raises — returns None on any error.
    """
    try:
        from datetime import datetime

        from app.models.dashboard_token import DashboardToken
        from app.services.onboarding import refresh_dashboard_token

        token_record = (
            db.query(DashboardToken)
            .filter(DashboardToken.pet_id == pet.id, DashboardToken.revoked == False)
            .first()
        )

        if not token_record:
            return None

        # Auto-refresh expired tokens.
        if token_record.expires_at and datetime.utcnow() > token_record.expires_at:
            new_token = refresh_dashboard_token(db, pet.id)
            return f"{settings.FRONTEND_URL}/dashboard/{new_token}"

        return f"{settings.FRONTEND_URL}/dashboard/{token_record.token}"
    except Exception as e:
        logger.error("Failed to get dashboard link for pet %s: %s", str(pet.id), str(e))
        return None


# Maps GPT-extracted document_category values to the user-facing display label
# used in the "Here's what I read:" section of the confirmation message.
_CATEGORY_DISPLAY: dict[str, str] = {
    "Prescription": "Vet prescription",
    "Blood Report": "Lab report",
    "Urine Report": "Lab report",
    "Imaging": "Lab report",
    "PCR & Parasite Panel": "Lab report",
    "Vaccination": "Vaccination record",
}


def _build_doc_type_counts(all_results: list[dict]) -> dict[str, int]:
    """
    Count successfully extracted documents by user-facing display category.

    Only results that are not failed/rejected are counted. Categories map to
    "Vet prescription", "Lab report", "Vaccination record", or "document"
    for unmapped types.
    """
    counts: dict[str, int] = {}
    for r in all_results:
        if r.get("status") in ("failed", "rejected"):
            continue
        raw_cat = r.get("document_category") or ""
        label = _CATEGORY_DISPLAY.get(raw_cat, "document")
        counts[label] = counts.get(label, 0) + 1
    return counts


def _format_error_lines(failed_docs: list[dict], pet_name: str) -> list[str]:
    """
    Format error bullet lines for the confirmation message.

    Groups documents by reason and produces friendly, WhatsApp-ready lines.
    Each reason type gets one line (using plural/singular based on count).

    Reasons:
        "unclear"         — GPT extraction failed (image unreadable or poor quality)
        "download_failed" — file could not be retrieved from storage
        "timeout"         — extraction exceeded the 120s processing limit
        "wrong_pet"       — document belongs to a different pet
        "not_health"      — document is not a health record
    """
    lines: list[str] = []

    # Group by reason
    unclear = [d for d in failed_docs if d.get("reason") == "unclear"]
    download_failed = [d for d in failed_docs if d.get("reason") == "download_failed"]
    timeout = [d for d in failed_docs if d.get("reason") == "timeout"]
    wrong_pet = [d for d in failed_docs if d.get("reason") == "wrong_pet"]
    not_health = [d for d in failed_docs if d.get("reason") == "not_health"]

    for doc in unclear:
        lines.append(
            f"• '{doc['name']}' couldn't be processed as the image was unclear. "
            f"You can share a clearer picture and I'll update it right away."
        )

    for doc in download_failed:
        lines.append(
            f"• '{doc['name']}' couldn't be accessed from storage. "
            f"Please try uploading it again and I'll process it right away."
        )

    for doc in timeout:
        lines.append(
            f"• '{doc['name']}' took too long to process. "
            f"Please try uploading it again and I'll process it right away."
        )

    for doc in wrong_pet:
        other = doc.get("extra") or "another pet"
        lines.append(
            f"• '{doc['name']}' seems to belong to {other}. "
            f"Do you want me to still add it to {pet_name}'s records, "
            f"or should I skip it?"
        )

    for doc in not_health:
        lines.append(
            f"• '{doc['name']}' doesn't seem to be a health-related record. "
            f"It might have been uploaded by mistake — you can check and share "
            f"the right document and I'll update it for you."
        )

    return lines


async def _send_batch_summary(
    db: Session, user, pet, from_number: str,
    all_results: list[dict], success_count: int, fail_count: int,
    failed_docs: list[dict],
) -> None:
    """
    Send ONE consolidated confirmation message after all batch extractions complete.

    Format:
        Thanks for waiting — I've gone through the documents 🐾

        Here's what I read:
        • {#} Vet prescription(s)
        • {#} Lab report(s)
        • {#} Vaccination record(s)

        [error lines, only if any failures]

        Everything [else] has been added to your pet's records.

        You can view the updated Care Plan and all Health Records here: {link}
    """
    dashboard_link = _get_dashboard_link(db, pet)

    # --- Build "Here's what I read:" section ---
    type_counts = _build_doc_type_counts(all_results)
    read_lines: list[str] = []
    # Preferred display order
    for label in ("Vet prescription", "Lab report", "Vaccination record", "document"):
        count = type_counts.get(label, 0)
        if count > 0:
            if label == "document":
                read_lines.append(f"• {count} other document{'s' if count != 1 else ''}")
            else:
                read_lines.append(f"• {count} {label}{'s' if count != 1 else ''}")

    # --- Build error section ---
    error_lines = _format_error_lines(failed_docs, pet.name)

    # --- Compose message ---
    msg = "Thanks for waiting — I've gone through the documents 🐾"

    if read_lines:
        msg += "\n\nHere's what I read:\n" + "\n".join(read_lines)

    if error_lines:
        msg += "\n\n" + "\n".join(error_lines)

    # Closing line
    if read_lines and error_lines:
        msg += "\n\nEverything else has been added to your pet's records."
    elif read_lines:
        msg += "\n\nEverything has been added to your pet's records."
    else:
        # Only failures — no successful reads
        msg += "\n\nUnfortunately, none of the documents could be added to your pet's records."

    if dashboard_link:
        msg += (
            f"\n\nYou can view the updated Care Plan and all Health Records here:\n"
            f"{dashboard_link}"
        )

    await send_text_message(db, from_number, msg)


async def _send_deferred_care_plan(
    db: Session,
    user,
    pet,
    from_number: str,
    all_results: list[dict],
    success_count: int,
    fail_count: int,
    failed_docs: list[dict],
    doc_id_to_name: dict[str, str] | None = None,
) -> None:
    """
    Send the deterministic care-plan finalization message after document
    extraction completes for onboarding users whose dashboard link was deferred.

    Atomically "claims" the deferred marker up front so that concurrent
    callers (e.g. extraction-completion handler racing with a manual
    "dashboard" request) cannot both deliver the care plan.
    """
    try:
        # --- Atomic claim ---
        # The first caller to flip the marker from active -> cleared wins.
        # Everyone else returns silently to avoid duplicate sends.
        try:
            claimed_rows = _clear_deferred_care_plan_marker(db, pet.id, user=user)
            db.commit()
        except Exception as claim_err:
            logger.warning(
                "Could not claim deferred marker for pet=%s: %s",
                str(pet.id), claim_err,
            )
            try:
                db.rollback()
            except Exception:
                pass
            claimed_rows = 0

        if claimed_rows <= 0:
            logger.info(
                "Deferred care plan already claimed for pet=%s — skipping duplicate send",
                str(pet.id),
            )
            return

        # _finalize_onboarding has already sent the "That's everything …"
        # transition message before deferring, so we never re-send it here.

        # If everything failed, keep the explicit extraction-failure summary.
        # _send_batch_summary already emits rejection warnings, so return early
        # to avoid duplicate warning messages.
        if success_count == 0 and fail_count > 0:
            # Marker already claimed at the top of this function.
            await _send_batch_summary(
                db, user, pet, from_number,
                all_results=all_results,
                success_count=success_count,
                fail_count=fail_count,
                failed_docs=failed_docs,
            )
            return

        # Surface any document errors before the care-plan finalization message,
        # using the same friendly tone as post-onboarding batches.
        _name_map = doc_id_to_name or {}
        import re as _re

        for r in all_results:
            if r.get("status") != "rejected":
                continue
            doc_type = r.get("document_type", "")
            doc_name = _name_map.get(str(r.get("document_id", "")), "A document")
            if doc_type == "not_pet_related":
                await send_text_message(
                    db, from_number,
                    f"• '{doc_name}' doesn't seem to be a health-related record. "
                    f"It might have been uploaded by mistake — you can check and share "
                    f"the right document and I'll update it for you.",
                )
            elif doc_type == "pet_name_mismatch":
                errors = r.get("errors") or []
                other_pet = ""
                for err in errors:
                    if "appears to be for" in err:
                        m = _re.search(r"appears to be for ['\"]?([^'\",.]+)['\"]?", err)
                        if m:
                            other_pet = m.group(1).strip()
                        break
                other_pet = other_pet or "another pet"
                await send_text_message(
                    db, from_number,
                    f"• '{doc_name}' seems to belong to {other_pet}. "
                    f"Do you want me to still add it to {pet.name}'s records, "
                    f"or should I skip it?",
                )

        from app.models.condition import Condition
        from app.models.diet_item import DietItem

        diet_count = db.query(DietItem).filter(DietItem.pet_id == pet.id).count()
        supplement_count = db.query(DietItem).filter(
            DietItem.pet_id == pet.id,
            DietItem.type == "supplement",
        ).count()
        # Use the same tracked preventive counting logic as onboarding and
        # dashboard "What's Found" to keep user-visible counts consistent.
        record_count = _count_tracked_preventive_items(db, pet.id)
        docs_uploaded = db.query(Document).filter(Document.pet_id == pet.id).count()
        conditions = (
            db.query(Condition)
            .filter(Condition.pet_id == pet.id, Condition.is_active == True)
            .order_by(Condition.created_at.asc())
            .all()
        )

        diet_items = db.query(DietItem).filter(DietItem.pet_id == pet.id).all()

        # Pre-warm dashboard cache concurrently with care plan message assembly.
        # Both are awaited together so the cache is guaranteed to be warm before
        # the dashboard link is sent — the user never clicks into a cold cache.
        from app.services.precompute_service import precompute_dashboard_enrichments

        care_plan_msg, _ = await asyncio.gather(
            _generate_care_plan_message(
                db=db,
                pet=pet,
                diet_count=diet_count,
                supplement_count=supplement_count,
                record_count=record_count,
                docs_uploaded=docs_uploaded,
                conditions=conditions,
                diet_items=diet_items,
            ),
            precompute_dashboard_enrichments(str(pet.id)),
        )

        dashboard_link = _get_dashboard_link(db, pet)
        if fail_count > 0:
            # Surface failed-doc names in the care plan message using friendly tone.
            for doc in failed_docs:
                reason = doc.get("reason", "unclear")
                if reason == "download_failed":
                    care_plan_msg += (
                        f"\n\n• '{doc['name']}' couldn't be accessed from storage. "
                        f"Please try uploading it again and I'll process it right away."
                    )
                elif reason == "timeout":
                    care_plan_msg += (
                        f"\n\n• '{doc['name']}' took too long to process. "
                        f"Please try uploading it again and I'll process it right away."
                    )
                elif reason == "unclear":
                    care_plan_msg += (
                        f"\n\n• '{doc['name']}' couldn't be processed as the image was unclear. "
                        f"You can share a clearer picture and I'll update it right away."
                    )
        if dashboard_link:
            care_plan_msg += f"\n\nView {pet.name}'s full care plan here 👇\n{dashboard_link}"
            care_plan_msg += (
                f"\n\n📌 *Tip:* Pin this message so you can always find "
                f"{pet.name}'s care plan link."
            )
        else:
            care_plan_msg += f"\n\nSend *dashboard* anytime to get {pet.name}'s care plan link."

        # Marker was already claimed (cleared) at the top of this function,
        # so we can send safely without the risk of a duplicate delivery.
        await send_text_message(db, from_number, care_plan_msg)
    except Exception as exc:
        logger.warning(
            "Deferred care-plan send failed for user=%s pet=%s: %s",
            str(user.id), str(pet.id), exc,
        )
        # Marker already claimed at the top of the function — fall back to
        # the simple batch summary so the user still gets a confirmation.
        await _send_batch_summary(
            db, user, pet, from_number,
            all_results=all_results,
            success_count=success_count,
            fail_count=fail_count,
            failed_docs=failed_docs,
        )


def _mime_to_ext(mime_type: str) -> str:
    """Convert MIME type to file extension."""
    return {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}.get(
        mime_type, "bin"
    )
