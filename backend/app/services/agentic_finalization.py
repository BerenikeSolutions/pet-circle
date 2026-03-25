"""
PetCircle — Agentic Finalization Service

Composes the final WhatsApp message sent after onboarding profile build and
document extraction complete.

When AGENTIC_FINALIZATION_ENABLED=true (and OpenAI is reachable), a single
gpt-4.1-mini call composes a warm, natural message that summarises the pet's
profile setup, the health records found, and the dashboard link — including a
fun fact about the pet's breed.

When the flag is false, OpenAI is unavailable, or the call fails, the caller
falls back to the existing templated finalization message. This service never
raises — it always returns either an LLM-composed string or None (to signal
fallback).

This is NOT a multi-turn agent loop.  All data is already in the database;
the only job here is to compose one coherent, conversational message from
structured inputs.
"""

import logging
from typing import Any

from app.config import settings
from app.core.constants import OPENAI_QUERY_MODEL
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy OpenAI client
# ---------------------------------------------------------------------------

_openai_client = None


def _get_client():
    """Return (and lazily create) the AsyncOpenAI client."""
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


# ---------------------------------------------------------------------------
# Decision gate
# ---------------------------------------------------------------------------

def _should_use_agentic_finalization() -> bool:
    """
    Return True only when the feature flag is on, an API key exists,
    and the OpenAI API is currently reachable.

    Reuses the health-check cache from agentic_onboarding so no extra
    network call is made.
    """
    flag = getattr(settings, "AGENTIC_FINALIZATION_ENABLED", "false")
    has_key = bool(getattr(settings, "OPENAI_API_KEY", None))
    if flag.lower() != "true" or not has_key:
        return False
    try:
        from app.services.agentic_onboarding import is_openai_available
        return is_openai_available()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are PetCircle's friendly WhatsApp assistant in India.
Your job: write ONE warm, celebratory WhatsApp message to a pet parent whose
pet's health profile has just been set up.

Rules:
- Address the pet by name.
- Mention the health records or vaccinations found (if any), with the next due
  date where available.  Be specific — "Rabies vaccine done, next due 10 Apr 2025"
  is better than "vaccination found".
- Include the dashboard link on its own line.
- End the message with the fun fact on its own line, prefixed with "✨".
- Tone: warm, brief, like a message from a knowledgeable friend — not a
  system notification.  No markdown headers, no bullet symbols, no asterisks
  for bold (WhatsApp will render *bold* but keep it minimal).
- Total message must be under 400 characters (excluding the dashboard URL and
  the fun fact line).
- Do NOT mention items that were NOT found.
- Do NOT include the word "dashboard" as a command hint — the URL is enough.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def compose_finalization_message(
    pet_name: str,
    species: str,
    breed: str | None,
    docs_uploaded: int,
    items_extracted: list[dict[str, Any]],  # [{item_name, last_done_date, next_due_date}]
    diet_count: int,
    dashboard_url: str,
    extraction_failed: bool,
    fun_fact: str,
    reminders_count: int = 0,
) -> str | None:
    """
    Compose a warm, personalised finalization message via a single LLM call.

    Returns the composed message string if successful, or None if the feature
    flag is off, OpenAI is unavailable, or the call fails (caller should fall
    back to the templated message in that case).

    Args:
        pet_name:          Registered name of the pet.
        species:           "dog", "cat", etc.
        breed:             Breed name, or None if unknown.
        docs_uploaded:     Number of documents uploaded during the window.
        items_extracted:   List of preventive items found, each with keys:
                           item_name, last_done_date (str "DD/MM/YYYY"),
                           next_due_date (str "DD/MM/YYYY" or None).
        diet_count:        Number of diet/supplement items recorded.
        dashboard_url:     Full URL to the pet's dashboard.
        extraction_failed: True if at least one document failed extraction.
        fun_fact:          Pre-fetched breed fun fact string to include.
        reminders_count:   Number of active WhatsApp reminders scheduled (0 if none).
    """
    if not _should_use_agentic_finalization():
        return None

    # Build a compact context string for the LLM.
    reminder_status = (
        f"{reminders_count} active reminder(s) scheduled"
        if reminders_count > 0
        else "Reminder engine ready"
    )
    context_lines = [
        f"Pet name: {pet_name}",
        f"Species: {species}",
        f"Breed: {breed or 'unknown'}",
        f"Documents uploaded: {docs_uploaded}",
        f"Diet/supplement items recorded: {diet_count}",
        f"WhatsApp reminder schedule: {reminder_status}",
        f"Dashboard URL: {dashboard_url}",
        f"Fun fact (include verbatim, prefixed with ✨): {fun_fact}",
    ]

    if items_extracted:
        context_lines.append("Health records found:")
        for item in items_extracted:
            next_due = item.get("next_due_date") or "not set"
            context_lines.append(
                f"  - {item['item_name']}: last done {item['last_done_date']}, "
                f"next due {next_due}"
            )
    else:
        context_lines.append("Health records found: none (docs processed but no preventive items)")

    if extraction_failed:
        context_lines.append("Note: at least one document could not be processed.")

    user_content = "\n".join(context_lines)

    async def _call() -> str:
        client = _get_client()
        response = await client.chat.completions.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0.3,
            max_tokens=300,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    try:
        result = await retry_openai_call(_call)
        if result:
            logger.info(
                "agentic_finalization: composed message for pet=%s (%d chars)",
                pet_name, len(result),
            )
        return result or None
    except Exception as exc:
        logger.warning(
            "agentic_finalization: LLM call failed for pet=%s, falling back: %s",
            pet_name, exc,
        )
        return None
