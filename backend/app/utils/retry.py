"""
PetCircle Phase 1 — Retry Utilities (Module 17)

Provides retry wrappers for external API calls (Claude/Anthropic, WhatsApp).
Each wrapper has a specific retry policy tuned to the service's
failure characteristics.

Retry policies:
    - Claude/Anthropic: 3 attempts with 1s, 2s backoff (transient errors).
      429 rate-limit errors use longer 10s, 20s backoffs to allow TPM window
      recovery. A global semaphore (CLAUDE_API_CONCURRENCY) caps concurrent
      in-flight calls to prevent exhausting the token-per-minute quota.
      The semaphore is released during sleep so other callers can proceed
      while a rate-limited slot is waiting to retry.
    - WhatsApp: 2 attempts (1 retry). Log failure, continue.
    - Database: No retry — failures indicate constraint violations
      or connection issues that should not be silently retried.

These utilities ensure external API failures are isolated and
do not crash the main application flow.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from app.core.constants import (
    CLAUDE_API_CONCURRENCY,
    OPENAI_RATE_LIMIT_BACKOFFS,
    OPENAI_RETRY_BACKOFFS,
    WHATSAPP_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Global semaphore — limits concurrent in-flight Claude/Anthropic API calls
# across the whole process. Prevents TPM quota exhaustion under request bursts.
_claude_semaphore: asyncio.Semaphore | None = None


def _get_claude_semaphore() -> asyncio.Semaphore:
    """Return (or lazily create) the process-wide Claude concurrency semaphore."""
    global _claude_semaphore
    if _claude_semaphore is None:
        _claude_semaphore = asyncio.Semaphore(CLAUDE_API_CONCURRENCY)
    return _claude_semaphore


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if *exc* is a 429 rate-limit error from Anthropic or OpenAI."""
    try:
        from anthropic import RateLimitError as AnthropicRateLimitError  # noqa: PLC0415
        if isinstance(exc, AnthropicRateLimitError):
            return True
    except ImportError:
        pass
    try:
        from openai import RateLimitError as OpenAIRateLimitError  # noqa: PLC0415
        if isinstance(exc, OpenAIRateLimitError):
            return True
    except ImportError:
        pass
    # Fallback: match status code or error type string.
    err_str = str(exc)
    return "rate_limit_error" in err_str or "429" in err_str


async def retry_openai_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Retry wrapper for Claude/Anthropic API calls.

    Retry policy:
        - Attempt 1: immediate (under semaphore)
        - Attempt 2: after 1s backoff  (10s for 429) — semaphore released during sleep
        - Attempt 3: after 2s backoff  (20s for 429) — semaphore released during sleep
        - If all 3 fail, raise the last exception

    The semaphore is acquired per-attempt and released before sleeping.
    This ensures sleeping retriers do not starve other callers waiting
    for a concurrency slot.

    Args:
        func: The async callable that makes the Claude/Anthropic API call.
        *args: Positional arguments passed to func.
        **kwargs: Keyword arguments passed to func.

    Returns:
        The result of the successful API call.

    Raises:
        Exception: The last exception if all retry attempts fail.
    """
    last_exception = None
    # Total attempts = 1 (initial) + len(backoffs) retries
    total_attempts = 1 + len(OPENAI_RETRY_BACKOFFS)
    pending_backoff: float | None = None

    for attempt in range(total_attempts):
        # Sleep OUTSIDE the semaphore so the slot is free for other callers.
        if pending_backoff is not None:
            await asyncio.sleep(pending_backoff)
            pending_backoff = None

        async with _get_claude_semaphore():
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < len(OPENAI_RETRY_BACKOFFS):
                    # Use longer backoffs for rate-limit errors so the TPM
                    # window has time to reset before we retry.
                    if _is_rate_limit_error(e):
                        pending_backoff = OPENAI_RATE_LIMIT_BACKOFFS[attempt]
                    else:
                        pending_backoff = OPENAI_RETRY_BACKOFFS[attempt]
                    logger.warning(
                        "Claude/Anthropic call failed (attempt %d/%d), retrying in %ss: %s",
                        attempt + 1, total_attempts, pending_backoff, str(e)
                    )
                else:
                    # Final attempt failed — log and raise.
                    logger.error(
                        "Claude/Anthropic call failed after %d attempts: %s",
                        total_attempts, str(e)
                    )

    raise last_exception  # type: ignore[misc]


async def retry_whatsapp_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Retry wrapper for WhatsApp Cloud API calls.

    Retry policy:
        - Attempt 1: immediate
        - Attempt 2: immediate retry (no backoff)
        - If both fail, log the failure and return None
        - Never raises — WhatsApp failures must not crash the flow

    WhatsApp message delivery is best-effort. If a template message
    fails to send after 1 retry, the failure is logged but the
    application continues processing. This prevents WhatsApp outages
    from blocking the entire pipeline.

    Args:
        func: The async callable that makes the WhatsApp API call.
        *args: Positional arguments passed to func.
        **kwargs: Keyword arguments passed to func.

    Returns:
        The result of the successful API call, or None if all attempts fail.
    """
    total_attempts = 1 + WHATSAPP_MAX_RETRIES

    for attempt in range(total_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt < WHATSAPP_MAX_RETRIES:
                logger.warning(
                    "WhatsApp call failed (attempt %d/%d), retrying: %s",
                    attempt + 1, total_attempts, str(e)
                )
                # Brief pause before retry — prevents simultaneous burst failures
                # from all retrying at the same instant and colliding again.
                await asyncio.sleep(0.5)
            else:
                # Final attempt failed — log error but do not raise.
                # WhatsApp failures must never crash the processing flow.
                logger.error(
                    "WhatsApp call failed after %d attempts. "
                    "Continuing without sending message: %s",
                    total_attempts, str(e)
                )

    return None
