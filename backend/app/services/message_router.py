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
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import (
    ACKNOWLEDGMENTS,
    APP_WELCOME_HEADING,
    CONFLICT_KEEP_EXISTING,
    CONFLICT_USE_NEW,
    FAREWELLS,
    GREETINGS,
    HELP_COMMANDS,
    NOTHING_MORE_PHRASES,
    MAX_CONCURRENT_EXTRACTIONS,
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
)
from app.core.encryption import decrypt_field
from app.core.log_sanitizer import mask_phone
from app.utils.breed_fun_facts import get_breed_fun_fact

# Semaphore to limit concurrent background extraction tasks.
# Prevents DB connection pool exhaustion when many documents are uploaded.
_extraction_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXTRACTIONS)

# --- Batch upload tracking ---
# Tracks recent upload timestamps per pet to enforce the 5-file batch limit.
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
    _generate_care_plan_message,
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


def _has_pending_deferred_care_plan(db: Session, pet_id, user=None) -> bool:
    """Return True when per-pet marker or legacy user pending flag indicates deferred send."""
    marker = (
        db.query(DeferredCarePlanPending.id)
        .filter(
            DeferredCarePlanPending.pet_id == pet_id,
            DeferredCarePlanPending.is_cleared == False,
        )
        .first()
    )
    if marker is not None:
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


def _clear_deferred_care_plan_marker(db: Session, pet_id, user=None) -> None:
    """Clear all active deferred markers for a pet and legacy user-level pending flag."""
    (
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
    has_key = bool(getattr(settings, "OPENAI_API_KEY", None))
    if flag.lower() != "true" or not has_key:
        return False
    return True


def _get_mobile(user) -> str:
    """
    Get the plaintext mobile number for sending messages.

    Prefers the cached plaintext from the current request (set by route_message).
    Falls back to decrypting the stored encrypted mobile_number.
    """
    return getattr(user, "_plaintext_mobile", None) or decrypt_field(user.mobile_number)


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

    # Silently ignore non-actionable message types (reactions, stickers,
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
                await send_text_message(
                    db, from_number,
                    f"Hello {greeting_name}! 👋 Welcome to PetCircle — your pet's "
                    f"personalised care companion, right here on WhatsApp. I'm here "
                    f"to make sure your pet never misses the care they deserve.\n\n"
                    f"Let's start — what's your pet's name?",
                )
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
                text = (message_data.get("text") or "").strip()
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
            text = (message_data.get("text") or "").strip()
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

    # --- "Nothing more" while care plan is being prepared ---
    # If user says "nothing more" / "that's all" etc. and their care plan
    # hasn't been delivered yet (deferred extraction), let them know.
    if text_lower in NOTHING_MORE_PHRASES:
        pet = (
            db.query(Pet)
            .filter(Pet.user_id == user.id, Pet.is_deleted == False)
            .order_by(Pet.created_at.desc())
            .first()
        )
        if pet and _has_pending_deferred_care_plan(db, pet.id, user=user):
            await send_text_message(
                db, from_number,
                f"{pet.name}'s care plan is still being prepared — "
                f"we're finishing up the health analysis from your uploaded documents. "
                f"You'll receive it shortly! 🐾",
            )
            return

    # --- Check for pending reschedule before any other routing ---
    # If user recently pressed "Reschedule" on a reminder, route the
    # next text message as a date input to apply_reschedule_date().
    reschedule_result = await _try_handle_reschedule_date(db, user, text, from_number)
    if reschedule_result:
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

    # --- Acknowledgments (thanks, ok, got it) — canned reply ---
    if text_lower in ACKNOWLEDGMENTS:
        await send_text_message(
            db, from_number,
            "You're welcome! Let me know if you need anything else.",
        )
        return

    # --- Farewells (bye, see you) — canned reply ---
    if text_lower in FAREWELLS:
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
        pet = (
            db.query(Pet)
            .filter(Pet.user_id == user.id, Pet.is_deleted == False)
            .order_by(Pet.created_at.desc())
            .first()
        )

        has_deferred_care_plan = (
            bool(pet) and _has_pending_deferred_care_plan(db, pet.id, user=user)
        )

        # Guard against race conditions where deferred marker persistence fails.
        # Only hold dashboard links while in deferred state, or right after
        # onboarding completion when extraction can still be in-flight.
        onboarding_completed_at = getattr(user, "onboarding_completed_at", None)
        if pet and (has_deferred_care_plan or bool(onboarding_completed_at)):
            pending_docs = (
                db.query(Document.id)
                .filter(
                    Document.pet_id == pet.id,
                    Document.extraction_status == "pending",
                )
                .count()
            )
            if pending_docs > 0:
                await send_text_message(
                    db,
                    from_number,
                    f"{pet.name}'s care plan is still being prepared — "
                    f"we're finishing up the health analysis from your uploaded documents. "
                    f"You'll receive it shortly! 🐾",
                )
                return

        if pet and has_deferred_care_plan:
            active_marker = _get_active_deferred_marker(db, pet.id)

            docs_query = db.query(Document).filter(Document.pet_id == pet.id)
            if active_marker and active_marker.created_at:
                docs_query = docs_query.filter(Document.created_at >= active_marker.created_at)
            docs_in_scope = docs_query.all()
            success_count = sum(1 for doc in docs_in_scope if doc.extraction_status == "success")
            failed_docs = [
                doc for doc in docs_in_scope
                if doc.extraction_status in ("failed", "rejected")
            ]
            failed_doc_names = [
                (doc.file_path or "Document")
                .replace("\\", "/")
                .rsplit("/", 1)[-1]
                for doc in failed_docs
            ]

            await _send_deferred_care_plan(
                db,
                user,
                pet,
                from_number,
                all_results=[],
                success_count=success_count,
                fail_count=len(failed_docs),
                failed_doc_names=failed_doc_names,
            )
            return

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

    # General query — route to GPT query engine
    await _handle_query(db, user, text)


async def _send_help_menu(db: Session, from_number: str, user=None) -> None:
    """Send the help/commands menu to the user, personalised with pet name."""
    pet_name = None
    if user:
        from app.models.pet import Pet
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

    if recent_count >= MAX_PENDING_DOCS_PER_PET:
        # Only send the rejection message once per batch to avoid spamming.
        if not _rejection_sent.get(pet_key):
            _rejection_sent[pet_key] = True
            await send_text_message(
                db, from_number,
                f"Too many files! You've sent {recent_count} documents for "
                f"{pet.name} already.\n\n"
                f"Please upload maximum *{MAX_PENDING_DOCS_PER_PET} files at a time* "
                f"and wait for extraction to finish before sending more.",
            )
        return

    # Track this upload in the in-memory batch window.
    _recent_uploads[pet_key].append(now)

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
        await send_text_message(db, from_number, str(e))
    except RuntimeError:
        _recent_uploads[pet_key].pop()
        await send_text_message(db, from_number, "Upload failed. Please try again later.")


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


async def _delayed_batch_extraction(
    pet_id, pet_name, user_id, from_number,
) -> None:
    """
    Wait for uploads to settle, then extract all pending documents for the pet.

    Waits _EXTRACTION_DELAY_SECONDS, then queries all pending documents
    for the pet and extracts them one-by-one (each under the semaphore).
    Sends a single batch summary when all extractions are done.
    """
    await asyncio.sleep(_EXTRACTION_DELAY_SECONDS)

    pet_key = str(pet_id)

    # Clean up the extraction timer entry.
    _extraction_timers.pop(pet_key, None)

    from app.database import get_fresh_session
    from app.services.gpt_extraction import extract_and_process_document

    bg_db = get_fresh_session()
    try:
        # Fetch only documents explicitly uploaded in this WhatsApp batch.
        # This prevents unrelated pending documents (e.g. dashboard uploads)
        # from being included in the current extraction summary.
        batched_doc_ids = list(_batch_document_ids.get(pet_key, []))
        if not batched_doc_ids:
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
            _batch_document_ids.pop(pet_key, None)
            _batch_is_onboarding.pop(pet_key, None)
            return

        total = len(pending_docs)
        logger.info(
            "Starting batch extraction for pet %s: %d pending documents",
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
        _batch_is_onboarding.pop(pet_key, None)

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

        # Per user request, the "Got it — I received N documents", "The below
        # files are saved", and "I will now start extracting health data"
        # acknowledgement messages have been removed from the flow entirely.
        # Extraction proceeds silently and the user sees only the finalization
        # / care plan message at the end.

        success_count = 0
        fail_count = 0
        failed_doc_names = []
        all_results = []

        # Extract each document sequentially under the semaphore.
        # Each extraction is given a 120s timeout to prevent one stuck GPT
        # call from blocking the entire pipeline for all other users.
        for idx, doc in enumerate(pending_docs, 1):
            async with _extraction_semaphore:
                try:
                    # Download file content from storage (GCP or Supabase) for GPT processing.
                    from app.services.document_upload import download_from_supabase
                    file_bytes = await download_from_supabase(
                        doc.file_path,
                        backend=getattr(doc, "storage_backend", "supabase"),
                    )

                    if not file_bytes:
                        fail_count += 1
                        doc_label = doc.document_name or doc.file_path.split("/")[-1]
                        failed_doc_names.append(doc_label)
                        doc.extraction_status = "failed"
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

                    if result.get("status") == "failed":
                        fail_count += 1
                        doc_label = doc.document_name or doc.file_path.split("/")[-1]
                        # Only show document name — no error details to the user.
                        failed_doc_names.append(doc_label)
                    elif result.get("status") == "rejected":
                        # Rejected docs (not pet-related or wrong pet name) are
                        # shown on dashboard with reason; counted separately so they
                        # don't inflate fail_count or trigger the failure-only message.
                        pass
                    else:
                        success_count += 1

                    logger.info(
                        "Extracted doc %d/%d (id=%s) for pet %s: status=%s",
                        idx, total, str(doc.id), str(pet_id),
                        result.get("status"),
                    )
                except TimeoutError:
                    fail_count += 1
                    doc_label = doc.document_name or doc.file_path.split("/")[-1]
                    failed_doc_names.append(doc_label)
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
                    doc_label = doc.document_name or doc.file_path.split("/")[-1]
                    failed_doc_names.append(doc_label)
                    logger.error(
                        "Extraction failed for doc %s (%d/%d): %s",
                        str(doc.id), idx, total, str(e),
                    )
                    try:
                        bg_db.rollback()
                    except Exception:
                        pass
                    # Mark as failed so it doesn't get re-extracted in
                    # future batches. Without this, the document stays
                    # 'pending' and gets picked up by the next upload's
                    # batch extraction — causing ghost re-processing.
                    try:
                        doc.extraction_status = "failed"
                        bg_db.commit()
                    except Exception:
                        try:
                            bg_db.rollback()
                        except Exception:
                            pass

        # --- Send ONE consolidated summary after all extractions complete ---
        if user and pet:
            user._plaintext_mobile = from_number

            if _has_pending_deferred_care_plan(bg_db, pet.id, user=user):
                await _send_deferred_care_plan(
                    bg_db, user, pet, from_number,
                    all_results=all_results,
                    success_count=success_count,
                    fail_count=fail_count,
                    failed_doc_names=failed_doc_names,
                )
            else:
                await _send_batch_summary(
                    bg_db, user, pet, from_number,
                    all_results, success_count, fail_count, failed_doc_names,
                )

        # Clear the batch counter and rejection flag so user can upload again.
        _recent_uploads.pop(pet_key, None)
        _rejection_sent.pop(pet_key, None)
        _batch_document_ids.pop(pet_key, None)
        _batch_is_onboarding.pop(pet_key, None)

    except Exception as e:
        logger.error(
            "Batch extraction failed for pet %s: %s", str(pet_id), str(e),
        )
        try:
            bg_db.rollback()
        except Exception:
            pass
        try:
            await send_text_message(
                bg_db, from_number,
                f"Extraction encountered an issue for {pet_name}. "
                f"Try uploading again.",
            )
        except Exception:
            pass
        # Clear batch counter even on failure so user isn't stuck.
        _recent_uploads.pop(pet_key, None)
        _batch_document_ids.pop(pet_key, None)
        _batch_is_onboarding.pop(pet_key, None)
    finally:
        bg_db.close()


async def _handle_query(db: Session, user, text: str) -> None:
    """Handle a general text query via GPT query engine."""
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

    try:
        # 45s timeout prevents a stuck GPT call from hanging the user's session.
        result = await asyncio.wait_for(
            answer_pet_question(db, pet.id, text),
            timeout=45,
        )
        answer = result.get("answer", "Sorry, I couldn't find an answer.")
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


async def _send_batch_summary(
    db: Session, user, pet, from_number: str,
    all_results: list[dict], success_count: int, fail_count: int,
    failed_doc_names: list[str],
) -> None:
    """
    Send ONE consolidated message summarizing the entire batch extraction.

    Rules:
        - If entire batch failed: one error message with dashboard link.
        - If partial failure: list which docs failed by name.
        - If all succeeded: show extraction summary with items found.
    """
    success_count + fail_count

    # --- Check for rejected documents (not pet-related or wrong pet name) ---
    # Send one WhatsApp message per rejection type if any were found.
    not_pet_results = [r for r in all_results if r.get("document_type") == "not_pet_related"]
    mismatch_results = [r for r in all_results if r.get("document_type") == "pet_name_mismatch"]

    if not_pet_results:
        await send_text_message(
            db, from_number,
            "⚠️ One or more documents you sent don't appear to be pet or veterinary records "
            "(e.g. a human medical report, invoice, or unrelated photo). "
            "Please only upload vet records, vaccination certificates, lab reports, or prescriptions. "
            "These documents have been removed from the dashboard."
        )

    if mismatch_results:
        # Use the reason from the first mismatch result for a specific message.
        reason = (mismatch_results[0].get("errors") or [""])[0]
        msg = (
            f"⚠️ A document you uploaded could not be added to *{mismatch_results[0].get('pet_name', 'your pet')}*'s records "
            f"because it appears to belong to a different pet."
        )
        if reason:
            msg += f"\n\n_{reason}_"
        msg += "\n\nPlease upload documents that belong to this pet only."
        await send_text_message(db, from_number, msg)

    if success_count == 0 and fail_count > 0:
        # Entire batch failed — one error message.
        dashboard_link = _get_dashboard_link(db, pet)
        msg = (
            f"Extraction could not process the below documents for *{pet.name}*.\n\n"
        )
        if failed_doc_names:
            for name in failed_doc_names:
                msg += f"  - {name}\n"
            msg += "\n"
        msg += "You can update records manually via the dashboard."
        if dashboard_link:
            msg += f"\n{dashboard_link}"
        msg += (
            "\n\nNeed medicines, food, or supplements? "
            "Type *order* to place an order with us."
        )
        msg += "\n\nType *add pet* to register another pet."
        await send_text_message(db, from_number, msg)
        return

    # Aggregate results from all successful extractions.
    total_extracted = sum(r.get("items_extracted", 0) for r in all_results)
    total_processed = sum(r.get("items_processed", 0) for r in all_results)
    total_extra_vaccines = sum(len(r.get("extra_vaccines", []) or []) for r in all_results)
    total_extra_vaccines_saved = sum(int(r.get("extra_vaccines_saved", 0) or 0) for r in all_results)

    if (
        total_extracted == 0
        and total_extra_vaccines == 0
        and total_extra_vaccines_saved == 0
        and success_count > 0
    ):
        # All docs processed successfully but no preventive items found.
        dashboard_link = _get_dashboard_link(db, pet)
        msg = (
            f"Processed {success_count} document(s) for *{pet.name}*, "
            f"but no preventive health items were found.\n\n"
            f"These may be lab reports or prescriptions without preventive items. "
            f"You can update records manually from the dashboard."
        )
        if fail_count > 0 and failed_doc_names:
            msg += f"\n\n{fail_count} document(s) failed:\n"
            for name in failed_doc_names:
                msg += f"  - {name}\n"
        if dashboard_link:
            msg += f"\n{dashboard_link}"
        msg += (
            "\n\nNeed medicines, food, or supplements? "
            "Type *order* to place an order with us."
        )
        msg += "\n\nType *add pet* to register another pet."
        await send_text_message(db, from_number, msg)
        return

    # At least some items were found — show detailed summary.
    # Pick the last successful result with items for the detailed view.
    best_result = None
    for r in reversed(all_results):
        if (
            r.get("items_processed", 0) > 0
            or (r.get("extra_vaccines") or [])
            or int(r.get("extra_vaccines_saved", 0) or 0) > 0
        ):
            best_result = r
            break

    if best_result:
        merged_extra_vaccines: list[dict] = []
        for r in all_results:
            for detail in (r.get("extra_vaccines") or []):
                if isinstance(detail, dict):
                    merged_extra_vaccines.append(detail)

        summary_result = dict(best_result)
        if merged_extra_vaccines:
            summary_result["extra_vaccines"] = merged_extra_vaccines
        summary_result["extra_vaccines_saved"] = total_extra_vaccines_saved

        await _send_extraction_summary(
            db,
            user,
            pet,
            summary_result,
            total_processed,
            fail_count,
            failed_doc_names,
        )
    else:
        dashboard_link = _get_dashboard_link(db, pet)
        msg = f"Extraction complete for *{pet.name}*: {success_count} processed, {fail_count} failed."
        if dashboard_link:
            msg += f"\n\n{dashboard_link}"
        msg += (
            "\n\nNeed medicines, food, or supplements? "
            "Type *order* to place an order with us."
        )
        msg += "\n\nType *add pet* to register another pet."
        await send_text_message(db, from_number, msg)


async def _send_deferred_care_plan(
    db: Session,
    user,
    pet,
    from_number: str,
    all_results: list[dict],
    success_count: int,
    fail_count: int,
    failed_doc_names: list[str],
) -> None:
    """
    Send the deterministic care-plan finalization message after document
    extraction completes for onboarding users whose dashboard link was deferred.
    """
    try:
        # If this path was triggered manually via a dashboard request (no
        # extraction payload attached), send the standard transition message
        # before the final care-plan text for a consistent user experience.
        if not all_results and not (success_count == 0 and fail_count > 0):
            await send_text_message(
                db,
                from_number,
                f"That's everything. 🐾 Building {pet.name}'s personalised care plan now "
                f"— their health dashboard, care reminders, and nutrition breakdown "
                f"will be ready in just a moment.",
            )

        # If everything failed, keep the explicit extraction-failure summary.
        # _send_batch_summary already emits rejection warnings, so return early
        # to avoid duplicate warning messages.
        if success_count == 0 and fail_count > 0:
            await _send_batch_summary(
                db, user, pet, from_number,
                all_results=all_results,
                success_count=success_count,
                fail_count=fail_count,
                failed_doc_names=failed_doc_names,
            )
            if _has_pending_deferred_care_plan(db, pet.id, user=user):
                try:
                    _clear_deferred_care_plan_marker(db, pet.id, user=user)
                    db.commit()
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
            return

        # Always surface incorrect-document rejections before care-plan finalization.
        not_pet_results = [r for r in all_results if r.get("document_type") == "not_pet_related"]
        mismatch_results = [r for r in all_results if r.get("document_type") == "pet_name_mismatch"]

        if not_pet_results:
            await send_text_message(
                db, from_number,
                "⚠️ One or more documents you sent don't appear to be pet or veterinary records "
                "(e.g. a human medical report, invoice, or unrelated photo). "
                "Please only upload vet records, vaccination certificates, lab reports, or prescriptions. "
                "These documents have been removed from the dashboard."
            )

        if mismatch_results:
            reason = (mismatch_results[0].get("errors") or [""])[0]
            msg = (
                f"⚠️ A document you uploaded could not be added to *{mismatch_results[0].get('pet_name', 'your pet')}*'s records "
                f"because it appears to belong to a different pet."
            )
            if reason:
                msg += f"\n\n_{reason}_"
            msg += "\n\nPlease upload documents that belong to this pet only."
            await send_text_message(db, from_number, msg)

        from app.models.condition import Condition
        from app.models.diet_item import DietItem
        from app.models.preventive_master import PreventiveMaster
        from app.models.preventive_record import PreventiveRecord

        diet_count = db.query(DietItem).filter(DietItem.pet_id == pet.id).count()
        supplement_count = db.query(DietItem).filter(
            DietItem.pet_id == pet.id,
            DietItem.type == "supplement",
        ).count()
        # Count preventive records with an actual date logged across health
        # and hygiene circles (hygiene includes Tick/Flea which is clinically
        # a health item). Nutrition items are excluded.
        record_count = (
            db.query(PreventiveRecord)
            .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
            .filter(
                PreventiveRecord.pet_id == pet.id,
                PreventiveRecord.last_done_date.isnot(None),
                PreventiveMaster.circle.in_(["health", "hygiene"]),
            )
            .count()
        )
        docs_uploaded = db.query(Document).filter(Document.pet_id == pet.id).count()
        conditions = (
            db.query(Condition)
            .filter(Condition.pet_id == pet.id, Condition.is_active == True)
            .order_by(Condition.created_at.asc())
            .all()
        )

        diet_items = db.query(DietItem).filter(DietItem.pet_id == pet.id).all()

        care_plan_msg = await _generate_care_plan_message(
            db=db,
            pet=pet,
            diet_count=diet_count,
            supplement_count=supplement_count,
            record_count=record_count,
            docs_uploaded=docs_uploaded,
            conditions=conditions,
            diet_items=diet_items,
        )

        dashboard_link = _get_dashboard_link(db, pet)
        if fail_count > 0:
            care_plan_msg += (
                f"\n\nWe couldn't fully read {fail_count} uploaded document"
                f"{'s' if fail_count != 1 else ''}. You can still update those details in the dashboard."
            )
        if dashboard_link:
            care_plan_msg += f"\n\nView {pet.name}'s full care plan here 👇\n{dashboard_link}"
        else:
            care_plan_msg += f"\n\nSend *dashboard* anytime to get {pet.name}'s care plan link."

        # Clear pending marker before sending to avoid duplicate sends on retries.
        try:
            _clear_deferred_care_plan_marker(db, pet.id, user=user)
            db.commit()
        except Exception as flag_err:
            logger.warning(
                "Could not clear deferred marker for pet=%s: %s",
                str(pet.id), flag_err,
            )
            try:
                db.rollback()
            except Exception:
                pass

        await send_text_message(db, from_number, care_plan_msg)
    except Exception as exc:
        logger.warning(
            "Deferred care-plan send failed for user=%s pet=%s: %s",
            str(user.id), str(pet.id), exc,
        )
        await _send_batch_summary(
            db, user, pet, from_number,
            all_results=all_results,
            success_count=success_count,
            fail_count=fail_count,
            failed_doc_names=failed_doc_names,
        )
        if _has_pending_deferred_care_plan(db, pet.id, user=user):
            try:
                _clear_deferred_care_plan_marker(db, pet.id, user=user)
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass


async def _send_extraction_summary(
    db: Session, user, pet, result: dict,
    batch_total_processed: int = 0, batch_fail_count: int = 0,
    failed_doc_names: list[str] | None = None,
) -> None:
    """
    Send a WhatsApp summary after GPT extraction completes.

    Includes:
        - Count of items extracted and processed.
        - List of extracted item names with dates.
        - Any errors or unmatched items.
        - Dashboard link to view updated records.
    """
    from_number = _get_mobile(user)
    extracted = result.get("items_extracted", 0)
    processed = result.get("items_processed", 0)
    errors = result.get("errors", [])
    status = result.get("status", "failed")
    vaccination_details = result.get("vaccination_details", [])
    extra_vaccines = result.get("extra_vaccines", [])
    extra_vaccines_saved = result.get("extra_vaccines_saved", 0)

    if status == "failed":
        # Check for pet name mismatch — show a specific, clear message.
        pet_name_errors = [e for e in errors if "Pet name mismatch" in e]
        if pet_name_errors:
            await send_text_message(db, from_number, pet_name_errors[0])
            return

        dashboard_link = _get_dashboard_link(db, pet)
        msg = (
            "Document saved but extraction encountered an issue. "
            "You can update details manually via the dashboard."
        )
        if dashboard_link:
            msg += f"\n\nView *{pet.name}'s Dashboard*:\n{dashboard_link}"
        msg += (
            "\n\nNeed medicines, food, or supplements? "
            "Type *order* to place an order with us."
        )
        msg += "\n\nType *add pet* to register another pet."
        await send_text_message(db, from_number, msg)
        return

    if extracted == 0 and not extra_vaccines and not extra_vaccines_saved:
        await send_text_message(
            db, from_number,
            f"No preventive health items were found in {pet.name}'s document.\n\n"
            f"If this looks wrong, you can update records manually from the dashboard.\n\n"
            f"Need medicines, food, or supplements? Type *order* to place an order with us.\n"
            f"Type *add pet* to register another pet.",
        )
        return

    # Build extraction details from the preventive records in DB.
    # Re-query the latest records to show accurate current state.
    from app.models.preventive_master import PreventiveMaster
    from app.models.preventive_record import PreventiveRecord

    records = (
        db.query(PreventiveRecord, PreventiveMaster)
        .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
        .filter(
            PreventiveRecord.pet_id == pet.id,
            PreventiveRecord.last_done_date.isnot(None),
        )
        .order_by(PreventiveRecord.last_done_date.desc())
        .all()
    )

    lines = []
    for record, master in records:
        done_date = record.last_done_date.strftime("%d-%m-%Y") if record.last_done_date else "—"
        next_due = record.next_due_date.strftime("%d-%m-%Y") if record.next_due_date else "—"
        lines.append(f"  • {master.item_name}: done {done_date}, next due {next_due}")

    # Use batch total if available, else single-doc count.
    display_processed = batch_total_processed if batch_total_processed > 0 else processed

    msg = f"Extraction complete for *{pet.name}*!\n\n"
    msg += f"*{display_processed} item(s)* updated.\n"

    if lines:
        msg += "\n*Health Records:*\n" + "\n".join(lines) + "\n"

    if vaccination_details:
        msg += "\n*Vaccination Details Found:*\n"
        for detail in vaccination_details[:5]:
            if not isinstance(detail, dict):
                continue
            vaccine_name = detail.get("vaccine_name") or detail.get("vaccine_name_raw") or "Vaccine"
            dose = detail.get("dose")
            batch = detail.get("batch_number")
            parts = [str(vaccine_name)]
            if dose:
                parts.append(f"dose {dose}")
            if batch:
                parts.append(f"batch {batch}")
            msg += "  • " + ", ".join(parts) + "\n"

    if extra_vaccines:
        msg += "\n*Extra Vaccines (unmapped):*\n"
        for detail in extra_vaccines[:5]:
            if not isinstance(detail, dict):
                continue
            vaccine_name = detail.get("vaccine_name") or "Vaccine"
            done_date = detail.get("date")
            parts = [str(vaccine_name)]
            if done_date:
                parts.append(f"date {done_date}")
            msg += "  • " + ", ".join(parts) + "\n"
        if extra_vaccines_saved:
            msg += f"Saved {extra_vaccines_saved} extra vaccine entr{'y' if extra_vaccines_saved == 1 else 'ies'} for this pet.\n"

    if errors:
        unmatched = [e.replace("No match for item: ", "") for e in errors if "No match" in e]
        if unmatched:
            msg += f"\nCould not map these document terms to tracked preventive items: {', '.join(unmatched)}\n"
            msg += "(Usually this means lab-only or non-preventive terms; no preventive record was updated for them.)\n"

    # Include per-document failure details from the batch.
    if batch_fail_count > 0 and failed_doc_names:
        msg += f"\n{batch_fail_count} document(s) could not be processed:\n"
        for name in failed_doc_names:
            msg += f"  - {name}\n"

    dashboard_link = _get_dashboard_link(db, pet)
    if dashboard_link:
        msg += f"\nView *{pet.name}'s Dashboard*:\n{dashboard_link}"

    msg += (
        "\n\nNeed medicines, food, or supplements? "
        "Type *order* to place an order with us."
    )
    msg += "\n\nType *add pet* to register another pet."

    await send_text_message(db, from_number, msg)


def _mime_to_ext(mime_type: str) -> str:
    """Convert MIME type to file extension."""
    return {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}.get(
        mime_type, "bin"
    )
