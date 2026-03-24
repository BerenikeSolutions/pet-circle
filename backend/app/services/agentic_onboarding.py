"""
PetCircle — Agentic Onboarding Service

An LLM-driven alternative to the deterministic onboarding state machine.
Activated when AGENTIC_ONBOARDING_ENABLED=true and OPENAI_API_KEY is set.

Architecture:
    - One AgentOnboardingSession row per user stores the full OpenAI message
      history and a structured "collected_data" snapshot.
    - On each incoming WhatsApp message, we append the user turn, call the
      OpenAI tool-calling API, execute any tool calls (which write to
      collected_data in-memory), persist the updated session, and send the
      assistant reply back via WhatsApp.
    - When the model decides all required data is collected, it calls the
      complete_onboarding tool, which atomically writes everything to the DB
      (User, Pet, diet_items, hygiene_preferences, preventive_records,
      dashboard_token) and transitions the user to awaiting_documents.
    - After that, the existing awaiting_documents handler in message_router
      takes over unchanged.

IMPORTANT — JSONB mutation tracking:
    SQLAlchemy does not auto-detect in-place mutations (list.append, dict.update)
    on JSONB columns. Always call flag_modified() before db.commit() when
    modifying session.messages or session.collected_data.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.core.constants import DOC_UPLOAD_WINDOW_SECONDS, MAX_PETS_PER_USER
from app.core.encryption import encrypt_field
from app.models.agent_onboarding_session import AgentOnboardingSession
from app.models.user import User
from app.services.onboarding import (
    _get_openai_onboarding_client,
    _ai_identify_pet_from_photo,
    generate_dashboard_token,
    seed_preventive_records_for_pet,
)
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI health check cache
# ---------------------------------------------------------------------------

_openai_health_cache: dict = {"result": None, "checked_at": None}
_OPENAI_HEALTH_TTL = 300  # seconds — re-check every 5 minutes


def is_openai_available() -> bool:
    """
    Verify the OpenAI API key is valid and the API is reachable.

    Makes a minimal synchronous call (list models — no tokens billed) and
    caches the result for 5 minutes to avoid per-message latency.

    Returns False on any error so the deterministic flow takes over silently.
    """
    now = time.monotonic()
    cached = _openai_health_cache
    if (
        cached["result"] is not None
        and cached["checked_at"] is not None
        and now - cached["checked_at"] < _OPENAI_HEALTH_TTL
    ):
        return cached["result"]

    try:
        import asyncio

        client = _get_openai_onboarding_client()

        async def _ping():
            return await client.models.list()

        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an async context — run as a fire-and-forget check via
            # a fresh thread-safe future. Fallback: assume available if loop busy.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _ping())
                future.result(timeout=4)
        else:
            loop.run_until_complete(asyncio.wait_for(_ping(), timeout=3.0))

        _openai_health_cache.update({"result": True, "checked_at": now})
        return True
    except Exception as e:
        logger.warning(
            "OpenAI health check failed — falling back to deterministic onboarding: %s", str(e)
        )
        _openai_health_cache.update({"result": False, "checked_at": now})
        return False


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are PetCircle's friendly onboarding assistant on WhatsApp in India.

Your job is to collect the following details through natural conversation:

MANDATORY (you must have these before calling complete_onboarding):
1. User's full name
2. Pet's name
3. Pet's species — must be "dog" or "cat" only

OPTIONAL (collect as many as the user is willing to share):
- User's 6-digit Indian pincode
- Pet breed, gender (male/female), date of birth, weight in kg, whether neutered/spayed
- Diet: packaged food brands/quantities, homemade food descriptions, supplements or medications
- Grooming: activities like bathing, brushing, nail trim, with how often they do it

STYLE:
- Be warm and conversational. This is WhatsApp — keep messages short and friendly.
- You can ask multiple questions at once or one at a time — whatever feels natural.
- Use the available tools to store information the moment the user provides it.
- If the user skips, says "don't know", or leaves something blank — accept it and move on.
- Never use technical terms like "tool", "function", "JSON", or "state machine".
- Do not ask for consent — the user has already given it.

DATA RULES:
- Species: only "dog" or "cat". Politely clarify if the user says something else.
- Dates: accept any format (15/03/2022, March 15 2022, 3 years ago, etc.) and convert to YYYY-MM-DD before storing.
- Weight: 0.1 to 200 kg. If it seems very unusual, ask once to confirm.
- Gender: store as "male" or "female" only.
- Pincode: exactly 6 digits.
- India context: accept Hindi affirmations like "haan"/"ha" as yes, "nahi"/"na" as no.

FLOW:
- After collecting mandatory fields and giving the user a reasonable opportunity to share optional details, call complete_onboarding.
- If a pet photo was uploaded, the AI has already detected species/breed — confirm with the user before storing.
- After calling complete_onboarding, tell the user they can now upload pet health records (vaccination cards, prescriptions, lab reports) — up to 5 files (JPEG, PNG, or PDF, max 10 MB each). They have 5 minutes, or they can type "skip".
"""

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_ONBOARDING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_user_info",
            "description": (
                "Store the user's name and/or pincode. "
                "Call this as soon as either is mentioned. "
                "Omit fields that were not provided."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {
                        "type": "string",
                        "description": "User's full name as they stated it.",
                    },
                    "pincode": {
                        "type": "string",
                        "description": "6-digit Indian pincode.",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_pet_info",
            "description": (
                "Store pet details. Call whenever the user provides any pet field. "
                "All parameters are optional — only pass what the user provided. "
                "species must be 'dog' or 'cat'. "
                "dob must be YYYY-MM-DD. "
                "weight must be a float in kg. "
                "gender must be 'male' or 'female'. "
                "neutered is a boolean."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name":     {"type": "string"},
                    "species":  {"type": "string", "enum": ["dog", "cat"]},
                    "breed":    {"type": "string"},
                    "gender":   {"type": "string", "enum": ["male", "female"]},
                    "dob":      {"type": "string", "description": "YYYY-MM-DD"},
                    "weight":   {"type": "number", "description": "Weight in kg"},
                    "neutered": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_diet_items",
            "description": (
                "Add one or more food or supplement items to the pet's diet. "
                "type must be 'packaged', 'homemade', or 'supplement'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type":   {"type": "string", "enum": ["packaged", "homemade", "supplement"]},
                                "label":  {"type": "string"},
                                "detail": {"type": "string"},
                            },
                            "required": ["type", "label"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_grooming_items",
            "description": (
                "Add grooming activities with how often they happen. "
                "unit must be 'day', 'week', 'month', or 'year'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "freq": {"type": "integer", "minimum": 1},
                                "unit": {"type": "string", "enum": ["day", "week", "month", "year"]},
                            },
                            "required": ["name", "freq", "unit"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_pet_photo",
            "description": (
                "Record the storage path of an uploaded pet photo and any "
                "AI-detected species/breed. Called by the system after photo upload."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "photo_path":       {"type": "string"},
                    "detected_species": {"type": "string"},
                    "detected_breed":   {"type": "string"},
                },
                "required": ["photo_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_onboarding",
            "description": (
                "Call this when you have collected the user's name, the pet's name, "
                "and the pet's species (mandatory), AND the user has had a chance to "
                "share optional details. This triggers all DB writes. "
                "Do NOT call this before mandatory fields are confirmed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why collection is complete.",
                    },
                },
                "required": ["reason"],
                "additionalProperties": False,
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def _get_or_create_session(db: Session, user: User) -> AgentOnboardingSession:
    """
    Load the active agentic session for the user, or create a new one.

    A new session starts with the system prompt as the first message.
    """
    session = (
        db.query(AgentOnboardingSession)
        .filter(
            AgentOnboardingSession.user_id == user.id,
            AgentOnboardingSession.is_complete == False,  # noqa: E712
        )
        .first()
    )
    if session is None:
        session = AgentOnboardingSession(
            user_id=user.id,
            messages=[{"role": "system", "content": _SYSTEM_PROMPT}],
            collected_data={},
            is_complete=False,
        )
        db.add(session)
        db.flush()
    return session


def _save_session(db: Session, session: AgentOnboardingSession) -> None:
    """
    Persist the updated session to PostgreSQL.

    flag_modified() is required because SQLAlchemy cannot detect in-place
    mutations on JSONB columns (list.append, dict update). Without it, changes
    to messages and collected_data would be silently lost.
    """
    flag_modified(session, "messages")
    flag_modified(session, "collected_data")
    try:
        db.commit()
    except Exception as e:
        logger.error("Failed to save agent session: %s", str(e))
        try:
            db.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Media preprocessing
# ---------------------------------------------------------------------------


async def _preprocess_pet_photo(
    db: Session,
    user: User,
    session: AgentOnboardingSession,
    message_data: dict,
) -> str:
    """
    Download the pet photo from WhatsApp, upload to Supabase, run vision AI.

    Stores photo_path + detected species/breed in collected_data.

    Returns a context string injected into the LLM user turn.
    """
    from app.services.whatsapp_sender import download_whatsapp_media
    from app.services.document_upload import upload_to_supabase

    media_id = message_data.get("media_id")
    if not media_id:
        return "[System: User sent an image but no media_id found. Ask them to resend.]"

    try:
        media_result = await download_whatsapp_media(media_id)
        if not media_result:
            return "[System: Photo download failed. Continue without photo.]"

        file_bytes, mime_type = media_result
        ext = "jpg" if "jpeg" in mime_type else "png"
        storage_path = f"{user.id}/pending_photo_{media_id}.{ext}"

        try:
            await upload_to_supabase(file_bytes, storage_path, mime_type)
        except Exception as e:
            logger.error("Photo upload to Supabase failed: %s", str(e))
            return "[System: Photo upload failed. Continue without photo.]"

        # Vision AI detection
        ai_result: dict = {"species": None, "breed": None}
        try:
            ai_result = await _ai_identify_pet_from_photo(file_bytes, mime_type)
        except Exception as e:
            logger.warning("Pet photo AI detection failed: %s", str(e))

        # Store in collected_data directly (same effect as set_pet_photo tool)
        pet_data = session.collected_data.setdefault("pet", {})
        pet_data["photo_path"] = storage_path
        if ai_result.get("species") in ("dog", "cat"):
            pet_data.setdefault("species", ai_result["species"])
        if ai_result.get("breed"):
            pet_data.setdefault("breed", ai_result["breed"])

        species_str = ai_result.get("species") or "unknown"
        breed_str = ai_result.get("breed") or "unknown breed"
        return (
            f"[System: User sent a pet photo. "
            f"AI detected: species={species_str}, breed={breed_str}. "
            f"Photo saved. Please confirm these details with the user before storing.]"
        )

    except Exception as e:
        logger.error("Photo preprocessing failed: %s", str(e), exc_info=True)
        return "[System: Photo processing failed. Continue without photo.]"


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------


def _trim_messages(messages: list, max_turns: int = 10) -> list:
    """Return system prompt + last max_turns non-system messages for the API call.

    session.messages is NOT mutated — full history is still persisted to DB.
    This only trims what is sent to OpenAI, preventing unbounded context growth.
    """
    system_msgs = [m for m in messages if m.get("role") == "system"]
    turn_msgs = [m for m in messages if m.get("role") != "system"]
    return system_msgs + turn_msgs[-max_turns:]


async def _call_openai_with_tools(messages: list) -> object:
    """
    Single OpenAI chat completion call with tool support.

    Uses gpt-4.1 at temperature=0 for consistent extraction.
    """
    client = _get_openai_onboarding_client()

    async def _make_call():
        return await client.chat.completions.create(
            model="gpt-4.1",
            temperature=0,
            max_tokens=500,
            tools=_ONBOARDING_TOOLS,
            tool_choice="auto",
            messages=messages,
        )

    return await retry_openai_call(_make_call)


# ---------------------------------------------------------------------------
# Finalization
# ---------------------------------------------------------------------------


async def _finalize_agentic_onboarding(
    db: Session,
    user: User,
    session: AgentOnboardingSession,
) -> str:
    """
    Write all collected data to PostgreSQL atomically.

    Steps:
        1. Validate mandatory fields (user name, pet name, species).
        2. Write user.full_name and user.pincode.
        3. Create the Pet row.
        4. Write diet items via diet_service.add_diet_item.
        5. Write grooming items via hygiene_service.add_hygiene_item.
        6. Seed preventive records.
        7. Generate dashboard token.
        8. Transition user to awaiting_documents with 5-min upload window.
        9. Mark session complete.

    Returns:
        "__COMPLETE__" sentinel on success, or an error string if mandatory
        fields are missing (model will ask again).
    """
    from app.models.pet import Pet
    from app.services.diet_service import add_diet_item
    from app.services.hygiene_service import add_hygiene_item
    from app.utils.date_utils import parse_date

    cd = session.collected_data
    user_data = cd.get("user", {})
    pet_data = cd.get("pet", {})

    # --- Validate mandatory fields ---
    if not user_data.get("full_name"):
        return "Error: user full_name is missing. Ask the user for their name before completing."
    if not pet_data.get("name"):
        return "Error: pet name is missing. Ask the user for their pet's name before completing."
    if pet_data.get("species") not in ("dog", "cat"):
        return "Error: pet species must be 'dog' or 'cat'. Confirm with the user before completing."

    try:
        # --- Write user fields ---
        user.full_name = user_data["full_name"]
        if user_data.get("pincode"):
            user.pincode = encrypt_field(user_data["pincode"])

        # --- Guard: max pets per user ---
        pet_count = (
            db.query(Pet)
            .filter(Pet.user_id == user.id, Pet.is_deleted == False)  # noqa: E712
            .count()
        )
        if pet_count >= MAX_PETS_PER_USER:
            user.onboarding_state = "complete"
            session.is_complete = True
            db.commit()
            logger.warning(
                "Agentic onboarding: user %s already at max pets (%d)", str(user.id), MAX_PETS_PER_USER
            )
            return "__COMPLETE__"

        # --- Parse DOB ---
        dob = None
        if pet_data.get("dob"):
            try:
                dob = parse_date(pet_data["dob"])
            except Exception:
                dob = None

        # --- Create Pet row ---
        pet = Pet(
            user_id=user.id,
            name=pet_data["name"],
            species=pet_data["species"],
            breed=pet_data.get("breed"),
            gender=pet_data.get("gender"),
            dob=dob,
            weight=pet_data.get("weight"),
            neutered=pet_data.get("neutered"),
            photo_path=pet_data.get("photo_path"),
            weight_flagged=False,
        )
        db.add(pet)
        db.flush()  # Assign pet.id before referencing it below

        # --- Diet items ---
        diet = cd.get("diet", {})
        for bucket, food_type in (
            ("packaged", "packaged_food"),
            ("homemade", "homemade_food"),
            ("supplements", "supplement"),
        ):
            for item in diet.get(bucket, []):
                try:
                    await add_diet_item(
                        db,
                        pet.id,
                        food_type,
                        item["label"],
                        item.get("detail") or "",
                    )
                except Exception as e:
                    logger.error("Failed to save diet item '%s': %s", item.get("label"), str(e))

        # --- Grooming items ---
        for g in cd.get("grooming", []):
            try:
                await add_hygiene_item(
                    db,
                    pet.id,
                    g["name"],
                    freq=g.get("freq", 1),
                    unit=g.get("unit", "month"),
                )
            except Exception as e:
                logger.error("Failed to save grooming item '%s': %s", g.get("name"), str(e))

        # --- Seed preventive records ---
        try:
            seed_preventive_records_for_pet(db, pet)
        except Exception as e:
            logger.error("Preventive record seeding failed: %s", str(e))

        # --- Generate dashboard token ---
        try:
            generate_dashboard_token(db, pet.id)
        except Exception as e:
            logger.error("Dashboard token generation failed: %s", str(e))

        # --- Transition to awaiting_documents ---
        user.onboarding_state = "awaiting_documents"
        user.doc_upload_deadline = datetime.now(timezone.utc) + timedelta(
            seconds=DOC_UPLOAD_WINDOW_SECONDS
        )

        session.is_complete = True

        db.commit()

        logger.info(
            "Agentic onboarding finalized: user_id=%s pet=%s (%s)",
            str(user.id),
            pet.name,
            pet.species,
        )
        return "__COMPLETE__"

    except Exception as e:
        logger.error("Agentic finalization failed: %s", str(e), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return f"Error during finalization: {str(e)}. Please retry."


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_tool_call(
    db: Session,
    user: User,
    session: AgentOnboardingSession,
    tool_name: str,
    arguments_json: str,
) -> str:
    """
    Execute a tool call from the model.

    All tools except complete_onboarding write only to collected_data
    (in-memory). The DB write happens atomically in _finalize_agentic_onboarding.

    Returns:
        Result string to feed back as a tool role message.
        "__COMPLETE__" sentinel when complete_onboarding succeeds.
    """
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return "Error: could not parse tool arguments."

    if tool_name == "set_user_info":
        data = session.collected_data.setdefault("user", {})
        if args.get("full_name"):
            data["full_name"] = args["full_name"]
        if args.get("pincode"):
            data["pincode"] = args["pincode"]
        return f"Stored user info: {args}"

    elif tool_name == "set_pet_info":
        data = session.collected_data.setdefault("pet", {})
        for field in ("name", "species", "breed", "gender", "dob", "weight", "neutered"):
            if field in args:
                data[field] = args[field]
        return f"Stored pet info: {args}"

    elif tool_name == "add_diet_items":
        diet = session.collected_data.setdefault(
            "diet", {"packaged": [], "homemade": [], "supplements": []}
        )
        items = args.get("items", [])
        for item in items:
            bucket = item.get("type", "packaged")
            diet.setdefault(bucket, []).append(
                {"label": item["label"], "detail": item.get("detail", "")}
            )
        return f"Stored {len(items)} diet item(s)."

    elif tool_name == "add_grooming_items":
        grooming = session.collected_data.setdefault("grooming", [])
        items = args.get("items", [])
        for item in items:
            grooming.append(
                {"name": item["name"], "freq": item["freq"], "unit": item["unit"]}
            )
        return f"Stored {len(items)} grooming item(s)."

    elif tool_name == "set_pet_photo":
        pet_data = session.collected_data.setdefault("pet", {})
        pet_data["photo_path"] = args["photo_path"]
        if args.get("detected_species") in ("dog", "cat"):
            pet_data.setdefault("species", args["detected_species"])
        if args.get("detected_breed"):
            pet_data.setdefault("breed", args["detected_breed"])
        return "Photo path stored."

    elif tool_name == "complete_onboarding":
        return await _finalize_agentic_onboarding(db, user, session)

    else:
        logger.warning("Unknown tool call: %s", tool_name)
        return f"Error: unknown tool '{tool_name}'."


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


async def _run_agent_loop(
    db: Session,
    user: User,
    session: AgentOnboardingSession,
) -> str | None:
    """
    Execute the OpenAI tool-calling loop for one user turn.

    Runs until:
    - The model produces a text reply (no tool call) → return the text.
    - complete_onboarding fires → finalize, let model produce closing message, return it.
    - Max iterations exceeded → return a safe fallback.

    Returns:
        The text to send to the user, or None on unexpected failure.
    """
    MAX_ITERATIONS = 5

    for iteration in range(MAX_ITERATIONS):
        response = await _call_openai_with_tools(_trim_messages(session.messages))
        choice = response.choices[0]
        message = choice.message

        # Build assistant message dict
        assistant_msg: dict = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        session.messages.append(assistant_msg)

        # No tool calls → model is speaking directly to the user
        if not message.tool_calls:
            return message.content or ""

        # Execute each tool call
        completion_triggered = False
        for tc in message.tool_calls:
            result = await _dispatch_tool_call(
                db, user, session, tc.function.name, tc.function.arguments
            )
            if result == "__COMPLETE__":
                completion_triggered = True
                result = "Onboarding records written to database successfully."

            session.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

        if completion_triggered:
            # Let the model produce the closing message to the user.
            final_response = await _call_openai_with_tools(session.messages)
            final_text = final_response.choices[0].message.content or ""
            session.messages.append({"role": "assistant", "content": final_text})
            return final_text

    logger.warning("Agent loop exceeded max iterations for user %s", str(user.id))
    return (
        "I had trouble processing that. Please reply *hi* to continue where you left off."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def handle_agentic_onboarding_step(
    db: Session,
    user: User,
    message_data: dict,
    send_fn,
) -> None:
    """
    Main entry point for agentic onboarding. Called from message_router.

    Handles all WhatsApp message types:
    - text  → append to history, run agent loop
    - image → download + vision AI, inject photo context, run agent loop
    - document → acknowledge receipt, run agent loop

    Args:
        db:           SQLAlchemy session.
        user:         User model with _plaintext_mobile set.
        message_data: Flat dict from webhook (_extract_message_data).
        send_fn:      async send_text_message(db, mobile, text)
    """
    mobile = getattr(user, "_plaintext_mobile", None)
    msg_type = message_data.get("type", "text")

    session = _get_or_create_session(db, user)

    # --- Preprocess media before building the user turn ---
    injected_context: str | None = None

    if msg_type == "image":
        injected_context = await _preprocess_pet_photo(db, user, session, message_data)
    elif msg_type == "document":
        injected_context = (
            "[System: User uploaded a document. Acknowledge receipt briefly and continue collection.]"
        )

    # Build user-turn content
    text = (message_data.get("text") or "").strip()

    if injected_context and text:
        user_content = f"{injected_context}\n\nUser message: {text}"
    elif injected_context:
        user_content = injected_context
    else:
        user_content = text

    if not user_content:
        # Non-actionable message (e.g., status update, empty body)
        await send_fn(db, mobile, "Please send a text message to continue your setup.")
        return

    session.messages.append({"role": "user", "content": user_content})

    # --- Run the agent loop ---
    reply_text = await _run_agent_loop(db, user, session)

    # --- Persist session ---
    _save_session(db, session)

    # --- Send reply ---
    if reply_text and mobile:
        await send_fn(db, mobile, reply_text)
