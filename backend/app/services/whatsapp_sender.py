"""
PetCircle Phase 1 — WhatsApp Message Sending Utility

Sends messages and templates via the WhatsApp Cloud API.
Used by the reminder engine, conflict notifications, onboarding,
and general reply flows.

All credentials loaded from environment config — never hardcoded.

Message types:
    - Text reply: plain text response to a user message
    - Template message: pre-approved template (reminders, overdue, conflict)
    - Interactive buttons: buttons for reminder/conflict responses

Rate limiting:
    - MAX_MESSAGES_PER_MINUTE per phone number (rolling window)
    - Enforced at the sender level to prevent quota violations

Retry policy:
    - Uses retry_whatsapp_call (1 retry, never raises)
    - Failures are logged but never crash the calling flow
"""

import hashlib
import logging
import time
from collections import OrderedDict

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.core.log_sanitizer import mask_phone, sanitize_payload
from app.core.rate_limiter import rate_limiter
from app.models.message_log import MessageLog
from app.utils.retry import retry_whatsapp_call

logger = logging.getLogger(__name__)

# ── Outbound message dedup ─────────────────────────────────────────────
# Prevents sending the exact same message to the same recipient within
# a short window (e.g., race between timer and user "skip" both
# triggering finalize, or Meta webhook retries causing double processing).
_OUTBOUND_DEDUP_TTL = 10  # seconds
_OUTBOUND_DEDUP_MAX = 500
_outbound_dedup_cache: OrderedDict[str, float] = OrderedDict()


def _is_outbound_duplicate(to_number: str, text: str) -> bool:
    """Return True if the same message was sent to the same number recently."""
    key = hashlib.sha256(f"{to_number}:{text}".encode()).hexdigest()
    now = time.monotonic()

    # Evict stale entries.
    while _outbound_dedup_cache:
        oldest_key, oldest_ts = next(iter(_outbound_dedup_cache.items()))
        if now - oldest_ts > _OUTBOUND_DEDUP_TTL:
            _outbound_dedup_cache.pop(oldest_key)
        else:
            break

    if key in _outbound_dedup_cache:
        logger.info("Outbound dedup: skipping duplicate message to %s", mask_phone(to_number))
        return True

    _outbound_dedup_cache[key] = now
    # Cap size.
    while len(_outbound_dedup_cache) > _OUTBOUND_DEDUP_MAX:
        _outbound_dedup_cache.popitem(last=False)

    return False


def get_template_body(db: Session, template_name: str) -> str:
    """
    Look up the approved template body text from whatsapp_template_configs.

    Returns empty string if the template is not found or body_text is empty.
    Never raises — logging failures must not block the send flow.
    """
    try:
        from app.models.whatsapp_template_config import WhatsappTemplateConfig

        row = (
            db.query(WhatsappTemplateConfig)
            .filter(WhatsappTemplateConfig.template_name == template_name)
            .first()
        )
        return row.body_text if row and row.body_text else ""
    except Exception:
        logger.debug("get_template_body failed for template '%s'", template_name)
        return ""


def render_template_body(body_text: str, params: list[str]) -> str:
    """
    Render a WhatsApp template body by substituting {{1}}, {{2}}, ... with params.

    WhatsApp uses 1-indexed double-brace placeholders ({{1}}, {{2}}, etc.).
    Returns the rendered string; returns body_text unchanged if params is empty.
    """
    result = body_text
    for i, value in enumerate(params, 1):
        result = result.replace(f"{{{{{i}}}}}", value)
    return result


# WhatsApp Cloud API base URL
WHATSAPP_API_URL = (
    f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
)

# Headers for all WhatsApp API calls
WHATSAPP_HEADERS = {
    "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
    "Content-Type": "application/json",
}


# Shared httpx client for WhatsApp API calls.
# Reusing a single client avoids the overhead of creating a new TCP
# connection and SSL handshake for every outgoing message. Critical
# when 100+ users trigger messages simultaneously.
_whatsapp_http_client: httpx.AsyncClient | None = None


def _get_whatsapp_client() -> httpx.AsyncClient:
    """Return a shared httpx.AsyncClient, created on first use."""
    global _whatsapp_http_client
    if _whatsapp_http_client is None or _whatsapp_http_client.is_closed:
        _whatsapp_http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )
    return _whatsapp_http_client


async def _send_whatsapp_request(payload: dict) -> dict | None:
    """
    Send a request to the WhatsApp Cloud API.

    Wraps the HTTP call with retry_whatsapp_call (1 retry, never raises).
    Uses a shared httpx client for connection pooling.

    Args:
        payload: The JSON payload to send to the WhatsApp API.

    Returns:
        The API response dict on success, None on failure.
    """
    async def _make_call() -> dict:
        client = _get_whatsapp_client()
        response = await client.post(
            WHATSAPP_API_URL,
            headers=WHATSAPP_HEADERS,
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    return await retry_whatsapp_call(_make_call)


def _log_outgoing_message(
    db: Session,
    mobile_number: str,
    message_type: str,
    payload: dict,
) -> None:
    """
    Log an outgoing WhatsApp message to message_logs.

    Logging must never block the main flow — errors are caught silently.

    Args:
        db: SQLAlchemy database session.
        mobile_number: Recipient's WhatsApp number.
        message_type: Type of message (text, template, interactive).
        payload: The full API payload sent.
    """
    try:
        log_entry = MessageLog(
            mobile_number=mask_phone(mobile_number),
            direction="outgoing",
            message_type=message_type,
            payload=sanitize_payload(payload),
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error("Failed to log outgoing message: %s", str(e))
        try:
            db.rollback()
        except Exception:
            pass


async def send_text_message(
    db: Session,
    to_number: str,
    text: str,
) -> dict | None:
    """
    Send a plain text message via WhatsApp Cloud API.

    Args:
        db: SQLAlchemy database session (for logging).
        to_number: Recipient's WhatsApp phone number.
        text: The text message body.

    Returns:
        API response dict on success, None on failure.
    """
    # Outbound dedup: skip if the exact same message was sent recently.
    if _is_outbound_duplicate(to_number, text):
        return None

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }

    # Rate limit check before sending.
    if not rate_limiter.check_rate_limit(to_number):
        logger.warning("Outgoing rate limited for %s", mask_phone(to_number))
        return None

    result = await _send_whatsapp_request(payload)

    _log_outgoing_message(db, to_number, "text", payload)

    if result:
        logger.info("Text message sent to %s", mask_phone(to_number))
    else:
        logger.warning("Text message failed to %s", mask_phone(to_number))

    return result


async def send_image_message(
    db: Session,
    to_number: str,
    image_url: str,
    caption: str = "",
) -> dict | None:
    """
    Send a WhatsApp image message using a publicly accessible URL.

    Used to send the dashboard snapshot card after onboarding completion.
    The image is fetched by WhatsApp servers from image_url — the URL must
    be publicly reachable (e.g. a Next.js /api/og edge route on Vercel).

    Args:
        db:         SQLAlchemy session (for logging).
        to_number:  Recipient's WhatsApp phone number.
        image_url:  Publicly accessible URL of the image to send.
        caption:    Optional caption text displayed below the image.

    Returns:
        API response dict on success, None on failure.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }

    if not rate_limiter.check_rate_limit(to_number):
        logger.warning("Outgoing rate limited (image) for %s", mask_phone(to_number))
        return None

    result = await _send_whatsapp_request(payload)

    _log_outgoing_message(db, to_number, "image", payload)

    if result:
        logger.info("Image message sent to %s", mask_phone(to_number))
    else:
        logger.warning("Image message failed to %s", mask_phone(to_number))

    return result


async def send_template_message(
    db: Session,
    to_number: str,
    template_name: str,
    parameters: list[str] | None = None,
    language_code: str = "en",
) -> dict | None:
    """
    Send a template message via WhatsApp Cloud API.

    Template names are loaded from environment config — never hardcoded.

    Args:
        db: SQLAlchemy database session (for logging).
        to_number: Recipient's WhatsApp phone number.
        template_name: The approved template name (from settings).
        parameters: Optional list of parameter values for template variables.
        language_code: Language code for the template (default: en).

    Returns:
        API response dict on success, None on failure.
    """
    # Build template components
    components = []
    if parameters:
        body_params = [
            {"type": "text", "text": p} for p in parameters
        ]
        components.append({
            "type": "body",
            "parameters": body_params,
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }

    if components:
        payload["template"]["components"] = components

    # Rate limit check before sending.
    if not rate_limiter.check_rate_limit(to_number):
        logger.warning("Outgoing rate limited for %s", mask_phone(to_number))
        return None

    result = await _send_whatsapp_request(payload)

    _log_outgoing_message(db, to_number, "template", payload)

    if result:
        logger.info(
            "Template '%s' sent to %s",
            template_name, mask_phone(to_number),
        )
    else:
        logger.warning(
            "Template '%s' failed to %s",
            template_name, mask_phone(to_number),
        )

    return result


async def send_interactive_buttons(
    db: Session,
    to_number: str,
    body_text: str,
    buttons: list[dict],
) -> dict | None:
    """
    Send an interactive button message via WhatsApp Cloud API.

    Used for reminder responses and conflict resolution prompts.
    Button payload IDs are from constants — never hardcoded.

    Args:
        db: SQLAlchemy database session (for logging).
        to_number: Recipient's WhatsApp phone number.
        body_text: The message body text.
        buttons: List of button dicts, each with 'id' and 'title'.
            Example: [{"id": "REMINDER_DONE", "title": "Done"}]

    Returns:
        API response dict on success, None on failure.
    """
    button_rows = [
        {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
        for b in buttons
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": button_rows},
        },
    }

    # Rate limit check before sending.
    if not rate_limiter.check_rate_limit(to_number):
        logger.warning("Outgoing rate limited for %s", mask_phone(to_number))
        return None

    result = await _send_whatsapp_request(payload)

    _log_outgoing_message(db, to_number, "interactive", payload)

    if result:
        logger.info("Interactive buttons sent to %s", mask_phone(to_number))
    else:
        logger.warning("Interactive buttons failed to %s", mask_phone(to_number))

    return result



async def send_conflict_notification(
    db: Session,
    to_number: str,
    pet_name: str,
    item_name: str,
    existing_date: str,
    new_date: str,
) -> dict | None:
    """
    Send a conflict notification using the petcircle_conflict_v1 template.

    The template has "Keep Existing" and "Use New" Quick Reply buttons
    embedded in Meta — no separate interactive message is needed.

    Args:
        db: SQLAlchemy database session.
        to_number: Recipient's WhatsApp phone number.
        pet_name: Name of the pet.
        item_name: Name of the conflicting preventive item.
        existing_date: Current date on record.
        new_date: Newly extracted conflicting date.

    Returns:
        API response dict on success, None on failure.
    """
    return await send_template_message(
        db=db,
        to_number=to_number,
        template_name=settings.WHATSAPP_TEMPLATE_CONFLICT,
        parameters=[pet_name, item_name, existing_date, new_date],
    )


async def download_whatsapp_media(media_id: str) -> tuple[bytes, str] | None:
    """
    Download media from WhatsApp Cloud API using a media ID.

    Two-step process:
        1. GET the media URL from Meta's API.
        2. Download the actual file content.

    Args:
        media_id: The media ID from the incoming WhatsApp message.

    Returns:
        Tuple of (file_bytes, mime_type) on success, None on failure.
    """
    import asyncio as _asyncio

    # Use the shared client for connection reuse. Media downloads use a
    # separate timeout (60s) because files can be large (up to 10MB).
    client = _get_whatsapp_client()

    # Retry on transient SSL errors from Meta's CDN.
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            # Step 1: Get media URL
            media_url_response = await client.get(
                f"https://graph.facebook.com/v21.0/{media_id}",
                headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
                timeout=15.0,
            )
            media_url_response.raise_for_status()
            media_info = media_url_response.json()

            media_url = media_info.get("url")
            mime_type = media_info.get("mime_type", "application/octet-stream")

            if not media_url:
                logger.error("No URL in media response for media_id=%s", media_id)
                return None

            # Step 2: Download the file (longer timeout for large files)
            file_response = await client.get(
                media_url,
                headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
                timeout=60.0,
            )
            file_response.raise_for_status()

            logger.info(
                "Media downloaded: media_id=%s, mime=%s, size=%d",
                media_id, mime_type, len(file_response.content),
            )

            return file_response.content, mime_type

        except Exception as e:
            logger.error(
                "Failed to download media: media_id=%s, attempt=%d/%d, error=%s",
                media_id, attempt + 1, max_retries + 1, str(e),
            )
            if attempt < max_retries:
                await _asyncio.sleep(1)
            else:
                return None
