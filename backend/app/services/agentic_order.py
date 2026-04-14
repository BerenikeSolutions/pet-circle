"""
PetCircle — Agentic Order Service

An LLM-driven alternative to the deterministic order state machine.
Activated when AGENTIC_ORDER_ENABLED=true and ANTHROPIC_API_KEY is set.

Architecture:
    - One AgentOrderSession row per user stores the full Anthropic message
      history and a structured "collected_data" snapshot.
    - On each incoming WhatsApp message, we append the user turn, call the
      Anthropic tool-calling API, execute any tool calls (which write to
      collected_data in-memory), persist the updated session, and send the
      assistant reply back via WhatsApp.
    - When the model decides the order is ready to confirm, it calls the
      confirm_order tool, which atomically creates the Order row, notifies
      the admin, and schedules the post-order recommendations task.
    - After that, user.order_state is cleared and the normal post-order
      handler takes over.

IMPORTANT — JSONB mutation tracking:
    SQLAlchemy does not auto-detect in-place mutations (list.append, dict.update)
    on JSONB columns. Always call flag_modified() before db.commit() when
    modifying session.messages or session.collected_data.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.encryption import decrypt_field
from app.models.agent_order_session import AgentOrderSession
from app.models.order import Order
from app.models.pet import Pet
from app.models.user import User
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are PetCircle's friendly pet supply assistant on WhatsApp in India.

Your job is to help the user place an order for their pet — naturally, through conversation.

WHAT YOU NEED TO COLLECT:
1. What they want to order (items list) — mandatory before confirming
2. Which pet the order is for — mandatory only if the user has more than one pet
3. Category — infer from the items (medicines / food_nutrition / supplements). Ask only if unclear.

STYLE:
- Be warm and brief. This is WhatsApp — keep messages short.
- Understand natural language: "usual stuff", "same as last time", "something for ticks" all work.
- Accept Hindi affirmations: "haan"/"ha" = yes, "nahi"/"na" = no.
- Never use technical terms like "tool", "JSON", or "function call".
- Do not show numbered category buttons — just ask conversationally.

FLOW:
1. If the user names items → call set_items immediately.
2. If category is ambiguous → ask once, then call set_category.
3. If user has multiple pets → call get_pet_list to fetch names, then ask which pet.
4. Once you have items (and pet if needed) → call get_recommendations to show personalized
   suggestions from their history. The user may add/change items after seeing suggestions.
5. Show a brief order summary and ask for confirmation.
6. On confirmation → call confirm_order.
7. If the user wants to cancel at any point → call cancel_order.

CATEGORIES:
- medicines: prescription drugs, flea/tick treatments, dewormers, ear drops, etc.
- food_nutrition: kibble, wet food, treats, meal toppers
- supplements: vitamins, probiotics, omega oils, joint supplements

RECOMMENDATIONS:
- After calling get_recommendations, present the results naturally (not as a numbered menu).
- Results have a "source" field: "preference" = from past orders, "ai" = AI suggestion.
- User can say "add all", select by name, or skip suggestions.
- When adding items that came from get_recommendations results, call set_items with source="recommendation".
- When adding items the user typed themselves, call set_items with source="custom" (the default).

IMPORTANT:
- Never confirm an order without items.
- Never hardcode pet names — always fetch with get_pet_list.
- After confirm_order succeeds, tell the user their order is placed and the team will call shortly.
"""

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

# Anthropic tool format: {"name", "description", "input_schema"} — no "type"/"function" wrapper.
_ORDER_TOOLS = [
    {
        "name": "set_items",
        "description": (
            "Store the list of items the user wants to order. "
            "Call this as soon as the user mentions what they want. "
            "Each item should be a plain string (e.g., 'Nexgard 3 tablets', 'Royal Canin 1kg'). "
            "Use source='recommendation' when items were selected from get_recommendations results. "
            "Use source='custom' (default) when the user typed items themselves."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of item names/descriptions.",
                },
                "source": {
                    "type": "string",
                    "enum": ["custom", "recommendation"],
                    "description": "How these items were identified. Default: custom.",
                },
            },
            "required": ["items"],
        },
    },
    {
        "name": "set_category",
        "description": (
            "Set the order category once it is clear. "
            "Infer from items when possible — only ask the user if truly ambiguous."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["medicines", "food_nutrition", "supplements"],
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "set_pet",
        "description": (
            "Set which pet this order is for. "
            "Only needed when the user has more than one pet. "
            "Pass the pet_id string from the get_pet_list result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_id": {
                    "type": "string",
                    "description": "UUID string of the pet.",
                },
            },
            "required": ["pet_id"],
        },
    },
    {
        "name": "get_pet_list",
        "description": (
            "Fetch the user's active pets as a list of {pet_id, name} objects. "
            "Call this before asking the user to select a pet. "
            "If there is only one pet, call set_pet automatically without asking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_recommendations",
        "description": (
            "Fetch personalized product recommendations for the selected pet and category. "
            "Returns a list of {name, reason} objects. "
            "Present these to the user naturally and offer to add them to the order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "confirm_order",
        "description": (
            "Finalize and place the order. Call this only after the user explicitly confirms. "
            "Requires items to be set. If user has multiple pets, pet must also be set."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "cancel_order",
        "description": "Cancel the order flow. Call when the user says they don't want to order.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


_SESSION_TTL_DAYS = 7  # Abandon incomplete sessions older than this


def _get_or_create_session(db: Session, user: User) -> AgentOrderSession:
    """
    Load the active agentic order session for the user, or create a new one.

    Stale sessions (older than _SESSION_TTL_DAYS) are expired so the user
    always starts fresh after abandoning an order. A new session also creates
    a draft Order row and sets user.active_order_id so the order is visible
    to admin tooling and external checks throughout the conversation.
    """

    session = (
        db.query(AgentOrderSession)
        .filter(
            AgentOrderSession.user_id == user.id,
            AgentOrderSession.is_complete == False,  # noqa: E712
        )
        .first()
    )

    # Expire sessions older than TTL so abandoned conversations don't persist.
    if session is not None:
        cutoff = datetime.now(UTC).replace(tzinfo=None)  # naive UTC
        created = session.created_at
        if created and hasattr(created, "tzinfo") and created.tzinfo:
            created = created.replace(tzinfo=None)  # normalise to naive
        if created and (cutoff - created).days >= _SESSION_TTL_DAYS:
            logger.info(
                "Expiring stale agentic order session %s for user %s (age %d days)",
                str(session.id), str(user.id),
                (cutoff - created).days,
            )
            session.is_complete = True
            # Delete the associated draft Order (no items, never confirmed).
            if user.active_order_id:
                stale_order = (
                    db.query(Order).filter(Order.id == user.active_order_id).first()
                )
                if stale_order and not stale_order.items_description:
                    db.delete(stale_order)
            user.order_state = None
            user.active_order_id = None
            try:
                db.commit()
            except Exception:
                db.rollback()
            session = None  # Fall through to create a fresh session

    if session is None:
        # Create a draft Order row immediately so user.active_order_id is
        # always set for the lifetime of the agentic order conversation.
        # items_description is empty until confirm_order fires.
        draft_order = Order(
            user_id=user.id,
            category="medicines",   # default; overwritten by set_category tool
            items_description="",
            status="pending",
            payment_status="pending",
        )
        db.add(draft_order)
        db.flush()  # Assign draft_order.id before setting active_order_id

        user.active_order_id = draft_order.id
        user.order_state = "awaiting_agentic_order"

        session = AgentOrderSession(
            user_id=user.id,
            messages=[],  # System prompt passed directly to client.messages.create(system=...)
            collected_data={
                "pet_id": None,
                "category": None,
                "items": [],
                "items_sources": {},   # {item_name: "custom" | "recommendation"}
                "draft_order_id": str(draft_order.id),
            },
            is_complete=False,
        )
        db.add(session)
        db.flush()
        try:
            db.commit()
        except Exception as e:
            logger.error("Failed to create agentic order session: %s", str(e))
            db.rollback()

    return session


def _save_session(db: Session, session: AgentOrderSession) -> None:
    """
    Persist the updated session to PostgreSQL.

    flag_modified() is required because SQLAlchemy cannot detect in-place
    mutations on JSONB columns (list.append, dict update).
    """
    flag_modified(session, "messages")
    flag_modified(session, "collected_data")
    try:
        db.commit()
    except Exception as e:
        logger.error("Failed to save agent order session: %s", str(e))
        try:
            db.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------


def _trim_messages(messages: list, max_turns: int = 10) -> list:
    """Return last max_turns non-system messages for the API call.

    The system prompt is passed separately via the system= parameter.
    session.messages is NOT mutated — full history is still persisted to DB.
    This only trims what is sent to Claude, preventing unbounded context growth.
    """
    # Filter out any legacy system messages (from old OpenAI sessions stored in DB).
    turn_msgs = [m for m in messages if m.get("role") != "system"]
    return turn_msgs[-max_turns:]


async def _call_openai_with_tools(messages: list) -> object:
    """
    Single OpenAI chat completion call with tool support.

    Uses gpt-4.1 at temperature=0 for consistent extraction.
    """
    from app.services.onboarding import _get_openai_onboarding_client

    client = _get_openai_onboarding_client()

    async def _make_call():
        return await client.messages.create(
            model="claude-sonnet-4-6",
            temperature=0,
            max_tokens=500,
            tools=_ORDER_TOOLS,
            tool_choice={"type": "auto"},
            system=_SYSTEM_PROMPT,
            messages=[m for m in messages if m.get("role") != "system"],
        )

    return await retry_openai_call(_make_call)


async def _call_openai_text_only(messages: list) -> object:
    """
    OpenAI call that forces a plain text response (tool_choice='none').

    Used exclusively for the closing message after confirm_order / cancel_order
    fires, so the model cannot call another tool and produce a blank reply.
    """
    from app.services.onboarding import _get_openai_onboarding_client

    client = _get_openai_onboarding_client()

    async def _make_call():
        # No tools passed — forces a pure text response (no tool calls possible).
        return await client.messages.create(
            model="claude-sonnet-4-6",
            temperature=0,
            max_tokens=500,
            system=_SYSTEM_PROMPT,
            messages=[m for m in messages if m.get("role") != "system"],
        )

    return await retry_openai_call(_make_call)


# ---------------------------------------------------------------------------
# Finalization
# ---------------------------------------------------------------------------


async def _finalize_agentic_order(
    db: Session,
    user: User,
    session: AgentOrderSession,
) -> str:
    """
    Finalise the order atomically and trigger post-order tasks.

    Steps:
        1. Validate mandatory fields (items non-empty).
        2. Resolve pet_id: if not set and user has exactly 1 pet, auto-select.
        3. Update the draft Order row created by _get_or_create_session.
        4. Record per-item preferences with correct source (recommendation/custom).
        5. Notify admin via WhatsApp.
        6. Schedule post-order recommendations background task.
        7. Clear user.order_state / active_order_id and mark session complete.

    Returns:
        "__COMPLETE__" sentinel on success, or an error string if mandatory
        fields are missing (model will ask again).
    """
    from app.services.order_service import _notify_admin_whatsapp, _send_post_order_recommendations

    cd = session.collected_data
    items: list = cd.get("items") or []
    pet_id = cd.get("pet_id")
    category = cd.get("category") or "medicines"
    items_sources: dict = cd.get("items_sources", {})

    # --- Validate items ---
    if not items:
        return "Error: no items selected. Ask the user what they want to order before confirming."

    # --- Auto-detect single pet ---
    pet = None
    if not pet_id:
        pets = (
            db.query(Pet)
            .filter(Pet.user_id == user.id, Pet.is_deleted == False)  # noqa: E712
            .all()
        )
        if len(pets) == 1:
            pet_id = str(pets[0].id)
            pet = pets[0]
        elif len(pets) == 0:
            return "Error: no pet profile found. The user cannot place an order without adding a pet first. Let them know they need to complete pet onboarding before ordering."
        elif len(pets) > 1:
            return "Error: multiple pets found but no pet selected. Ask the user which pet this is for."
    else:
        try:
            from uuid import UUID as _UUID
            pet = db.query(Pet).filter(Pet.id == _UUID(pet_id)).first()
        except Exception:
            pet = None

    # --- Validate category enum ---
    valid_categories = {"medicines", "food_nutrition", "supplements"}
    if category not in valid_categories:
        category = "medicines"

    order = None
    try:
        mobile = getattr(user, "_plaintext_mobile", None) or decrypt_field(user.mobile_number)

        # --- Update the draft Order row (created by _get_or_create_session) ---
        # Prefer the draft order tracked in collected_data; fall back to active_order_id.
        from uuid import UUID as _UUID
        draft_order_id_str = cd.get("draft_order_id")
        order = None
        if draft_order_id_str:
            try:
                order = db.query(Order).filter(Order.id == _UUID(draft_order_id_str)).first()
            except Exception:
                order = None
        if order is None and user.active_order_id:
            order = db.query(Order).filter(Order.id == user.active_order_id).first()

        if order is not None:
            # Update the draft in place.
            order.pet_id = pet.id if pet else None
            order.category = category
            order.items_description = ", ".join(items)[:2000]
            order.status = "pending"
            order.payment_status = "pending"
        else:
            # No draft found (e.g., expired or deleted) — create a fresh row.
            order = Order(
                user_id=user.id,
                pet_id=pet.id if pet else None,
                category=category,
                items_description=", ".join(items)[:2000],
                status="pending",
                payment_status="pending",
            )
            db.add(order)

        # --- Record preferences with correct source per item ---
        if pet:
            from app.services.recommendation_service import record_preference
            for item in items:
                item_str = str(item).strip()
                if item_str:
                    source = items_sources.get(item_str, "custom")
                    record_preference(db, pet.id, category, item_str, source)

        # --- Clear user state and mark session complete ---
        user.order_state = None
        user.active_order_id = None
        session.is_complete = True

        db.commit()

        logger.info(
            "Agentic order finalized: order_id=%s user=%s",
            str(order.id),
            str(user.id),
        )

        # --- Post-order recommendations (non-blocking background task) ---
        if pet is not None:
            asyncio.create_task(
                _send_post_order_recommendations(db, user, order, pet, mobile)
            )

    except Exception as e:
        logger.error("Agentic order finalization failed: %s", str(e), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return f"Error during order placement: {str(e)}. Please try again."

    # --- Notify admin after successful commit (best-effort, outside commit try/except) ---
    # Kept separate so a notification failure never rolls back an already-committed order
    # or causes the LLM to tell the user "please try again" for a placed order.
    if order is not None:
        try:
            await _notify_admin_whatsapp(db, order, user, pet)
        except Exception as e:
            logger.warning(
                "Admin WhatsApp notification failed for order %s (order still placed): %s",
                str(order.id), str(e),
            )

    return "__COMPLETE__"


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_tool_call(
    db: Session,
    user: User,
    session: AgentOrderSession,
    tool_name: str,
    arguments_json: str,
) -> str:
    """
    Execute a tool call from the model.

    All tools except confirm_order and cancel_order write only to
    collected_data (in-memory). The DB write happens atomically in
    _finalize_agentic_order.

    Returns:
        Result string to feed back as a tool role message.
        "__COMPLETE__" sentinel when confirm_order succeeds.
        "__CANCELLED__" sentinel when cancel_order fires.
    """
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return "Error: could not parse tool arguments."

    if tool_name == "set_items":
        items = args.get("items", [])
        source = args.get("source", "custom")
        if source not in ("custom", "recommendation"):
            source = "custom"
        clean_items = [str(i).strip() for i in items if str(i).strip()]
        # Replace items list; update per-item source map.
        session.collected_data["items"] = clean_items
        sources: dict = session.collected_data.setdefault("items_sources", {})
        for item in clean_items:
            sources[item] = source
        return f"Items stored: {clean_items} (source={source})"

    elif tool_name == "set_category":
        category = args.get("category")
        valid = {"medicines", "food_nutrition", "supplements"}
        if category not in valid:
            return f"Error: category must be one of {valid}."
        session.collected_data["category"] = category
        return f"Category set to '{category}'."

    elif tool_name == "set_pet":
        pet_id = args.get("pet_id", "").strip()
        if not pet_id:
            return "Error: pet_id is required."
        session.collected_data["pet_id"] = pet_id
        return f"Pet set to '{pet_id}'."

    elif tool_name == "get_pet_list":
        pets = (
            db.query(Pet)
            .filter(Pet.user_id == user.id, Pet.is_deleted == False)  # noqa: E712
            .order_by(Pet.name)
            .all()
        )
        if not pets:
            return "[]"
        result = [{"pet_id": str(p.id), "name": p.name} for p in pets]
        return json.dumps(result)

    elif tool_name == "get_recommendations":
        pet_id = session.collected_data.get("pet_id")
        category = session.collected_data.get("category") or "medicines"

        if not pet_id:
            return "[]  # No pet selected yet — set pet first."

        try:
            from uuid import UUID as _UUID

            from app.services.recommendation_service import (
                get_or_generate_recommendations,
                get_pet_top_preferences,
            )
            pet_uuid = _UUID(pet_id)

            # Build merged list: saved order history first, then AI recs.
            # Mirrors deterministic _get_numbered_suggestions in order_service.py.
            combined = []
            seen: set = set()

            preferences = get_pet_top_preferences(db, pet_uuid, category, limit=5)
            for pref in preferences:
                name = str(pref.get("name", "")).strip()
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())
                combined.append({
                    "name": name,
                    "reason": f"Previously ordered {pref.get('used_count', 0)} time(s)",
                    "source": "preference",
                })

            ai_recs = await get_or_generate_recommendations(
                db,
                pet_id=pet_uuid,
                category=category,
                increment_on_hit=True,
            )
            for rec in (ai_recs or []):
                name = str(rec.get("name", "")).strip()
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())
                combined.append({
                    "name": name,
                    "reason": rec.get("reason", ""),
                    "source": "ai",
                })

            if not combined:
                return "[]"
            return json.dumps(combined)
        except Exception as e:
            logger.warning("Agentic order: recommendation fetch failed: %s", str(e))
            return "[]"

    elif tool_name == "confirm_order":
        return await _finalize_agentic_order(db, user, session)

    elif tool_name == "cancel_order":
        # Delete the draft Order row (no items were confirmed — nothing to keep).
        from uuid import UUID as _UUID
        draft_order_id_str = session.collected_data.get("draft_order_id")
        if draft_order_id_str:
            try:
                draft = db.query(Order).filter(Order.id == _UUID(draft_order_id_str)).first()
                if draft and not draft.items_description:
                    db.delete(draft)
            except Exception as e:
                logger.warning("Cancel: could not delete draft order: %s", str(e))
        elif user.active_order_id:
            try:
                draft = db.query(Order).filter(Order.id == user.active_order_id).first()
                if draft and not draft.items_description:
                    db.delete(draft)
            except Exception as e:
                logger.warning("Cancel: could not delete draft order via active_order_id: %s", str(e))

        session.is_complete = True
        user.order_state = None
        user.active_order_id = None
        db.commit()
        logger.info("Agentic order cancelled for user %s", str(user.id))
        return "__CANCELLED__"

    else:
        logger.warning("Unknown tool call in agentic order: %s", tool_name)
        return f"Error: unknown tool '{tool_name}'."


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


async def _run_agent_loop(
    db: Session,
    user: User,
    session: AgentOrderSession,
) -> str | None:
    """
    Execute the Anthropic tool-calling loop for one user turn.

    Runs until:
    - The model produces a text reply (no tool call) → return the text.
    - confirm_order fires → finalize, let model produce closing message, return it.
    - cancel_order fires → let model produce closing message, return it.
    - Max iterations exceeded → return a safe fallback.

    Returns:
        The text to send to the user, or None on unexpected failure.
    """
    MAX_ITERATIONS = 5

    for iteration in range(MAX_ITERATIONS):
        response = await _call_openai_with_tools(_trim_messages(session.messages))

        # Anthropic response: response.content is a list of content blocks.
        # Blocks can be TextBlock (type="text") or ToolUseBlock (type="tool_use").
        content_blocks = response.content or []
        tool_use_blocks = [b for b in content_blocks if getattr(b, "type", None) == "tool_use"]
        text_blocks = [b for b in content_blocks if getattr(b, "type", None) == "text"]

        # Persist the assistant turn as the raw content list (for multi-turn context).
        # The Anthropic SDK returns content blocks; store them as serialisable dicts.
        assistant_content = []
        for block in content_blocks:
            if getattr(block, "type", None) == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif getattr(block, "type", None) == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        session.messages.append({"role": "assistant", "content": assistant_content})

        # No tool calls → model is speaking directly to the user
        if not tool_use_blocks:
            return text_blocks[0].text if text_blocks else ""

        # Execute each tool call
        terminal_signal: str | None = None
        tool_results = []
        for tc in tool_use_blocks:
            result = await _dispatch_tool_call(
                db, user, session, tc.name,
                json.dumps(tc.input) if isinstance(tc.input, dict) else (tc.input or "{}")
            )

            if result == "__COMPLETE__":
                terminal_signal = "COMPLETE"
                result = "Order placed in database successfully."
            elif result == "__CANCELLED__":
                terminal_signal = "CANCELLED"
                result = "Order cancelled."

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result,
            })

        # Append all tool results in one user message (Anthropic requirement).
        session.messages.append({"role": "user", "content": tool_results})

        if terminal_signal:
            # Let the model produce the closing message to the user.
            # Use tool_choice="any" (forces a tool call) → but here we want text only.
            # Re-use the text-only call path.
            final_response = await _call_openai_text_only(
                _trim_messages(session.messages)
            )
            final_content = final_response.content or []
            final_text = ""
            for block in final_content:
                if getattr(block, "type", None) == "text":
                    final_text = block.text
                    break
            session.messages.append({"role": "assistant", "content": final_text})
            return final_text

    logger.warning("Agent order loop exceeded max iterations for user %s", str(user.id))
    return "I had trouble processing that. Please type *order* to try again."


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def handle_agentic_order_step(
    db: Session,
    user: User,
    message_data: dict,
    send_fn,
) -> None:
    """
    Main entry point for agentic order flow. Called from message_router.

    Handles text and button messages. Buttons are forwarded as their
    display label so the model understands what the user tapped.

    Args:
        db:           SQLAlchemy session.
        user:         User model with _plaintext_mobile set.
        message_data: Flat dict from webhook (_extract_message_data).
        send_fn:      async send_text_message(db, mobile, text)
    """
    mobile = getattr(user, "_plaintext_mobile", None)
    msg_type = message_data.get("type", "text")

    session = _get_or_create_session(db, user)

    # Build user-turn content
    if msg_type == "button":
        # Forward button taps as natural language so the model handles them
        button_text = message_data.get("button_text") or message_data.get("button_payload") or ""
        user_content = button_text.strip() if button_text else ""
    elif msg_type == "text":
        user_content = (message_data.get("text") or "").strip()
    else:
        # Non-text, non-button (image, document, etc.) — acknowledge and continue
        user_content = "[System: User sent a non-text message. Acknowledge briefly and continue.]"

    if not user_content:
        await send_fn(db, mobile, "Please send a text message to continue your order.")
        return

    session.messages.append({"role": "user", "content": user_content})

    # --- Run the agent loop ---
    reply_text: str | None = None
    try:
        reply_text = await _run_agent_loop(db, user, session)
    except Exception as e:
        logger.error(
            "Agent order loop failed for user %s: %s", str(user.id), str(e), exc_info=True
        )
        reply_text = "I ran into a problem. Please type *order* to try again."
    finally:
        # Always persist — even on failure, saves partial state (items, category, etc.)
        _save_session(db, session)

    # --- Send reply ---
    if reply_text and mobile:
        await send_fn(db, mobile, reply_text)
