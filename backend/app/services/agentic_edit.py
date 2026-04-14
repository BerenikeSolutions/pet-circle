"""
PetCircle — Agentic Edit Service

LLM-driven post-onboarding profile editor via WhatsApp.
Users type what they want to change in natural language; Claude understands
intent, asks clarifying questions only when needed, executes all DB writes
and downstream AI computations, then sends the dashboard link.

Architecture mirrors agentic_order.py:
    - user.edit_state = "agentic_edit" while session is active
    - user.edit_data (JSONB) stores conversation history + selected_pet_id
    - Tool-calling loop runs until finish_edit is called
    - Dashboard link sent ONLY after finish_edit + all DB commits

IMPORTANT — JSONB mutation tracking:
    SQLAlchemy does not auto-detect in-place mutations (list.append, dict.update)
    on JSONB columns. Always call flag_modified(user, "edit_data") before
    db.commit() when modifying user.edit_data.
"""

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are PetCircle's friendly profile editor on WhatsApp in India.

Your job is to help the user update their pet's information through natural conversation.

CURRENT DATA:
{pet_data}

WHAT CAN BE CHANGED:
- Pet profile: name, breed, weight (kg), gender, age or birthday, neutered/spayed status
- Diet: add, update, or remove food items (packaged food, homemade meals, supplements)
- Preventive health: add or update vaccine records, deworming, flea/tick treatments, custom supplements or medications
- Owner's name

STYLE:
- Be warm and brief. This is WhatsApp — keep messages short.
- Understand natural language: "my dog is 14 kg now", "remove the boiled chicken", "change breed to Labrador" all work.
- Accept Hindi affirmations: "haan"/"ha" = yes, "nahi"/"na" = no.
- Never use technical terms like "tool", "JSON", or "function call".
- If something is unclear (e.g., which diet item to update when there are multiple), ask one focused question.
- When you have all the information needed, call the appropriate tool(s) immediately.
- After ALL requested changes are done, call finish_edit with a brief human-readable summary.

RULES:
- Core preventive items (vaccines, deworming, flea/tick) cannot be deleted — their dates or names can be updated, or you can explain they cannot be removed.
- Weight must be between 0.5 and 150 kg.
- Gender must be male or female.
- For age/birthday, accept "3 years", "8 months", or dates like "11/02/2022".
- If the user has multiple pets and doesn't specify which one, ask before making any changes.
"""


def _build_system_prompt(pet_data_str: str) -> str:
    """Build the Claude system prompt with embedded pet data."""
    return _SYSTEM_PROMPT_TEMPLATE.format(pet_data=pet_data_str)


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic format — no "type"/"function" wrapper)
# ---------------------------------------------------------------------------

_EDIT_TOOLS = [
    {
        "name": "update_pet_field",
        "description": (
            "Update a field on the pet's profile. "
            "Fields: name, breed, weight (number in kg), gender (male/female), "
            "age_or_dob (age text like '3 years' or date like '11/02/2022'), "
            "neutered (true/false)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": ["name", "breed", "weight", "gender", "age_or_dob", "neutered"],
                    "description": "Which field to update.",
                },
                "value": {
                    "type": "string",
                    "description": "The new value as a string.",
                },
                "pet_name": {
                    "type": "string",
                    "description": "Name of the pet (only needed when user has multiple pets).",
                },
            },
            "required": ["field", "value"],
        },
    },
    {
        "name": "update_diet_item",
        "description": (
            "Update an existing diet item. "
            "Identify by current_label (partial match is fine). "
            "Provide new_label and/or new_detail to change."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "current_label": {
                    "type": "string",
                    "description": "Current label of the diet item (used to find it).",
                },
                "new_label": {
                    "type": "string",
                    "description": "New label/name for the item. Optional.",
                },
                "new_detail": {
                    "type": "string",
                    "description": "New detail description (e.g. portion size). Optional.",
                },
            },
            "required": ["current_label"],
        },
    },
    {
        "name": "add_diet_item",
        "description": "Add a new diet item for the pet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Name of the food (e.g., 'Royal Canin Adult').",
                },
                "detail": {
                    "type": "string",
                    "description": "Details like quantity/frequency (e.g., 'Dry kibble - 200g/day'). Optional.",
                },
                "type": {
                    "type": "string",
                    "enum": ["packaged", "homemade", "supplement"],
                    "description": "Type of diet item.",
                },
            },
            "required": ["label", "type"],
        },
    },
    {
        "name": "remove_diet_item",
        "description": "Remove an existing diet item. Identify by label (partial match is fine).",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Label of the diet item to remove.",
                },
            },
            "required": ["label"],
        },
    },
    {
        "name": "update_preventive_record",
        "description": (
            "Update a vaccine, deworming, flea/tick, or supplement record. "
            "Can update last_done_date and/or medicine/product name. "
            "Identify by item_name (partial match is fine)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of the preventive item (e.g., 'Rabies', 'Deworming').",
                },
                "new_date": {
                    "type": "string",
                    "description": "New last done date (DD/MM/YYYY or YYYY-MM-DD). Optional.",
                },
                "new_medicine_name": {
                    "type": "string",
                    "description": "New medicine/product name. Optional.",
                },
            },
            "required": ["item_name"],
        },
    },
    {
        "name": "add_preventive_record",
        "description": (
            "Add a new custom supplement, medication, or vaccine record for the pet. "
            "Use for items not already in the pet's history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of the supplement, medication, or vaccine.",
                },
                "last_done_date": {
                    "type": "string",
                    "description": "Date last done (DD/MM/YYYY or YYYY-MM-DD). Optional.",
                },
                "recurrence_days": {
                    "type": "integer",
                    "description": "How often in days (e.g., 30 for monthly). Defaults to 30.",
                },
            },
            "required": ["item_name"],
        },
    },
    {
        "name": "remove_preventive_record",
        "description": (
            "Remove a CUSTOM supplement or medication record. "
            "Core preventive items (vaccines, deworming, flea/tick from the standard schedule) "
            "cannot be removed — use update_preventive_record to update their dates instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of the custom item to remove.",
                },
            },
            "required": ["item_name"],
        },
    },
    {
        "name": "update_owner_name",
        "description": "Update the owner's (user's) full name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "new_name": {
                    "type": "string",
                    "description": "The owner's new full name.",
                },
            },
            "required": ["new_name"],
        },
    },
    {
        "name": "finish_edit",
        "description": (
            "Call this once ALL requested changes have been successfully made. "
            "Provide a brief human-readable summary of what was changed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Brief summary of changes (e.g., 'Updated Max's weight to 14 kg.').",
                },
            },
            "required": ["summary"],
        },
    },
]

# ---------------------------------------------------------------------------
# Claude API call helpers
# ---------------------------------------------------------------------------

_MAX_TURNS = 12  # Maximum message turns kept in API call (full history in DB)


def _trim_messages(messages: list, max_turns: int = _MAX_TURNS) -> list:
    """Return last max_turns non-system messages for the API call."""
    return [m for m in messages if m.get("role") != "system"][-max_turns:]


async def _call_claude_with_tools(messages: list, system_prompt: str) -> object:
    """Single Anthropic chat completion call with tool support."""
    from app.services.onboarding import _get_openai_onboarding_client
    from app.utils.retry import retry_openai_call

    client = _get_openai_onboarding_client()

    async def _make_call():
        return await client.messages.create(
            model="claude-sonnet-4-6",
            temperature=0,
            max_tokens=600,
            tools=_EDIT_TOOLS,
            tool_choice={"type": "auto"},
            system=system_prompt,
            messages=_trim_messages(messages),
        )

    return await retry_openai_call(_make_call)


async def _call_claude_text_only(messages: list, system_prompt: str) -> object:
    """Anthropic call that forces a plain text response — used for the cancel reply."""
    from app.services.onboarding import _get_openai_onboarding_client
    from app.utils.retry import retry_openai_call

    client = _get_openai_onboarding_client()

    async def _make_call():
        return await client.messages.create(
            model="claude-sonnet-4-6",
            temperature=0,
            max_tokens=300,
            system=system_prompt,
            messages=_trim_messages(messages),
        )

    return await retry_openai_call(_make_call)


# ---------------------------------------------------------------------------
# Mobile helper (mirrors message_router._get_mobile)
# ---------------------------------------------------------------------------


def _get_mobile(user) -> str:
    """Get the plaintext mobile number for sending WhatsApp messages."""
    from app.core.encryption import decrypt_field

    cached = getattr(user, "_plaintext_mobile", None)
    if cached:
        return cached
    return decrypt_field(user.mobile_number)


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def _build_pet_data_context(db: Session, user, pets: list, primary_pet) -> str:
    """
    Build a human-readable summary of the pet's current profile, diet, and
    preventive records to inject into the Claude system prompt.
    """
    from app.models.diet_item import DietItem
    from app.models.preventive_record import PreventiveRecord
    from app.models.preventive_master import PreventiveMaster

    pet = primary_pet
    lines = []

    # --- Pet profile ---
    age_display = pet.age_text or (str(pet.dob) if pet.dob else "Not recorded")
    neutered_display = (
        "Yes" if pet.neutered is True
        else "No" if pet.neutered is False
        else "Not recorded"
    )
    lines += [
        f"Pet name: {pet.name}",
        f"Species: {pet.species or 'Not specified'}",
        f"Breed: {pet.breed or 'Not specified'}",
        f"Gender: {pet.gender or 'Not specified'}",
        f"Age: {age_display}",
        f"Weight: {pet.weight} kg" if pet.weight else "Weight: Not recorded",
        f"Neutered/Spayed: {neutered_display}",
    ]

    # --- Multi-pet info ---
    if len(pets) > 1:
        others = [p.name for p in pets if p.id != pet.id]
        lines.append(f"Other pets: {', '.join(others)}")

    # --- Diet items ---
    diet_items = (
        db.query(DietItem)
        .filter(DietItem.pet_id == pet.id)
        .order_by(DietItem.created_at.asc())
        .all()
    )
    if diet_items:
        lines.append("\nDiet items:")
        for item in diet_items:
            detail_part = f" — {item.detail}" if item.detail else ""
            lines.append(f"  [{item.type}] {item.label}{detail_part}")
    else:
        lines.append("\nNo diet items recorded.")

    # --- Preventive records ---
    records = (
        db.query(PreventiveRecord, PreventiveMaster)
        .outerjoin(
            PreventiveMaster,
            PreventiveRecord.preventive_master_id == PreventiveMaster.id,
        )
        .filter(PreventiveRecord.pet_id == pet.id)
        .order_by(PreventiveRecord.last_done_date.desc().nullslast())
        .limit(25)
        .all()
    )
    if records:
        lines.append("\nPreventive records:")
        for record, master in records:
            name = master.item_name if master else "Custom item"
            last_done = str(record.last_done_date) if record.last_done_date else "date unknown"
            lines.append(f"  {name}: last done {last_done}, status: {record.status}")
    else:
        lines.append("\nNo preventive records.")

    # --- Owner ---
    lines.append(f"\nOwner name: {user.full_name or 'Not recorded'}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


async def _dispatch_tool(
    db: Session,
    user,
    pet,
    tool_name: str,
    tool_input: dict,
) -> str:
    """
    Execute a single tool call and return a result string for the tool_result message.

    Returns "__COMPLETE__" when finish_edit is called.
    Never raises — errors are returned as descriptive strings.

    Precompute is scheduled here (in the async context) rather than inside the
    synchronous tool functions, because asyncio.create_task requires a running
    event loop which is only guaranteed inside async coroutines.
    """
    try:
        if tool_name == "update_pet_field":
            result = _tool_update_pet_field(db, pet, tool_input)

        elif tool_name == "update_diet_item":
            result = _tool_update_diet_item(db, pet, tool_input)

        elif tool_name == "add_diet_item":
            result = _tool_add_diet_item(db, pet, tool_input)

        elif tool_name == "remove_diet_item":
            result = _tool_remove_diet_item(db, pet, tool_input)

        elif tool_name == "update_preventive_record":
            result = _tool_update_preventive_record(db, pet, tool_input)

        elif tool_name == "add_preventive_record":
            result = _tool_add_preventive_record(db, user, pet, tool_input)

        elif tool_name == "remove_preventive_record":
            result = _tool_remove_preventive_record(db, pet, tool_input)

        elif tool_name == "update_owner_name":
            result = _tool_update_owner_name(db, user, tool_input)

        elif tool_name == "finish_edit":
            # Return sentinel — caller handles the dashboard link send
            return "__COMPLETE__"

        else:
            logger.warning("agentic_edit: unknown tool %s", tool_name)
            return f"Unknown tool: {tool_name}"

        # Schedule dashboard enrichment refresh for tools that change pet health data.
        # Called here (async context) — safe to use asyncio.create_task.
        if tool_name in _PRECOMPUTE_TOOLS:
            _schedule_precompute(str(pet.id))

        return result

    except Exception as exc:
        logger.error("agentic_edit _dispatch_tool %s error: %s", tool_name, exc, exc_info=True)
        return f"Error executing {tool_name}: {exc}"


# ---------------------------------------------------------------------------
# Individual tool implementations
# ---------------------------------------------------------------------------


def _tool_update_pet_field(db: Session, pet, tool_input: dict) -> str:
    """Update a single field on the pets table."""
    from app.models.pet import Pet

    field = tool_input.get("field", "")
    value = tool_input.get("value", "").strip()

    if not value:
        return "No value provided."

    if field == "name":
        if len(value) > 100:
            return "Name too long (max 100 characters)."
        old = pet.name
        pet.name = value
        db.commit()
        return f"Pet name updated from '{old}' to '{value}'."

    elif field == "breed":
        if len(value) > 100:
            return "Breed too long (max 100 characters)."
        old = pet.breed or "not set"
        pet.breed = value
        db.commit()
        return f"Breed updated from '{old}' to '{value}'."

    elif field == "weight":
        try:
            weight_val = float(value.replace("kg", "").replace("Kg", "").strip())
        except ValueError:
            return f"'{value}' is not a valid weight. Please provide a number in kg."
        if not (0.5 <= weight_val <= 150):
            return f"Weight {weight_val} kg is outside the valid range (0.5–150 kg)."
        old = pet.weight
        pet.weight = weight_val
        pet.weight_flagged = False
        db.commit()
        return f"Weight updated from {old} kg to {weight_val} kg."

    elif field == "gender":
        normalized = _parse_gender(value)
        if not normalized:
            return f"Could not recognise '{value}' as a gender. Please say male or female."
        old = pet.gender or "not set"
        pet.gender = normalized
        db.commit()
        return f"Gender updated from '{old}' to '{normalized}'."

    elif field == "age_or_dob":
        dob, age_text = _parse_age_or_dob(value)
        if dob is None and age_text is None:
            return f"Could not parse '{value}' as an age or date. Try '3 years' or '15/04/2021'."
        pet.age_text = age_text or value
        if dob:
            pet.dob = dob
        db.commit()
        display = str(dob) if dob else age_text
        return f"Age/birthday updated to {display}."

    elif field == "neutered":
        neutered = _parse_bool(value)
        if neutered is None:
            return f"Could not parse '{value}' as yes or no."
        old = pet.neutered
        pet.neutered = neutered
        db.commit()
        label = "neutered/spayed" if neutered else "not neutered/spayed"
        return f"Updated: {pet.name} is now {label}."

    else:
        return f"Unknown field: {field}"


def _tool_update_diet_item(db: Session, pet, tool_input: dict) -> str:
    """Update an existing diet item by label (case-insensitive partial match)."""
    from app.models.diet_item import DietItem

    current_label = tool_input.get("current_label", "").strip()
    new_label = tool_input.get("new_label", "").strip() or None
    new_detail = tool_input.get("new_detail", "").strip() or None

    if not current_label:
        return "current_label is required."

    item = _find_diet_item(db, pet.id, current_label)
    if not item:
        return f"No diet item matching '{current_label}' found."

    old_label = item.label
    if new_label:
        item.label = new_label
    if new_detail:
        item.detail = new_detail
    db.commit()
    changed = new_label or old_label
    return f"Diet item '{old_label}' updated to '{changed}'."


def _tool_add_diet_item(db: Session, pet, tool_input: dict) -> str:
    """Add a new diet item."""
    from app.models.diet_item import DietItem

    label = tool_input.get("label", "").strip()
    detail = tool_input.get("detail", "").strip() or None
    item_type = tool_input.get("type", "packaged")

    if not label:
        return "label is required."

    _ICONS = {"packaged": "🛍️", "homemade": "🍳", "supplement": "💊"}
    icon = _ICONS.get(item_type, "🍽️")

    # Check for duplicate
    existing = _find_diet_item(db, pet.id, label)
    if existing and existing.label.lower() == label.lower():
        return f"A diet item called '{label}' already exists."

    item = DietItem(pet_id=pet.id, type=item_type, icon=icon, label=label, detail=detail)
    db.add(item)
    db.commit()
    return f"Added diet item: '{label}'."


def _tool_remove_diet_item(db: Session, pet, tool_input: dict) -> str:
    """Remove a diet item by label (partial match)."""
    from app.models.diet_item import DietItem

    label = tool_input.get("label", "").strip()
    if not label:
        return "label is required."

    item = _find_diet_item(db, pet.id, label)
    if not item:
        return f"No diet item matching '{label}' found."

    removed_label = item.label
    db.delete(item)
    db.commit()
    return f"Removed diet item: '{removed_label}'."


def _tool_update_preventive_record(db: Session, pet, tool_input: dict) -> str:
    """Update a preventive record's last_done_date and/or medicine_name."""
    from app.models.preventive_record import PreventiveRecord
    from app.models.preventive_master import PreventiveMaster
    from app.models.reminder import Reminder
    from app.services.preventive_calculator import compute_next_due_date, compute_status

    item_name = tool_input.get("item_name", "").strip()
    new_date_str = tool_input.get("new_date", "").strip() or None
    new_medicine = tool_input.get("new_medicine_name", "").strip() or None

    if not item_name:
        return "item_name is required."
    if not new_date_str and not new_medicine:
        return "Provide at least new_date or new_medicine_name."

    record, master = _find_preventive_record(db, pet.id, item_name)
    if not record:
        return f"No preventive record matching '{item_name}' found."

    changes = []

    if new_medicine:
        record.medicine_name = new_medicine
        changes.append(f"medicine updated to '{new_medicine}'")

    if new_date_str:
        new_date = _parse_date(new_date_str)
        if not new_date:
            return f"Could not parse date '{new_date_str}'. Use DD/MM/YYYY or YYYY-MM-DD."

        old_next_due = record.next_due_date
        record.last_done_date = new_date

        # Recalculate next_due_date and status.
        # For custom items (master is None), look up the CustomPreventiveItem
        # to get the correct recurrence_days rather than falling back to 365.
        if master is None and record.custom_preventive_item_id:
            from app.models.custom_preventive_item import CustomPreventiveItem
            custom_item = (
                db.query(CustomPreventiveItem)
                .filter(CustomPreventiveItem.id == record.custom_preventive_item_id)
                .first()
            )
            recurrence = record.custom_recurrence_days or (custom_item.recurrence_days if custom_item else 365)
            reminder_before = custom_item.reminder_before_days if custom_item else 7
        else:
            recurrence = record.custom_recurrence_days or (master.recurrence_days if master else 365)
            reminder_before = master.reminder_before_days if master else 7

        record.next_due_date = compute_next_due_date(new_date, recurrence)
        record.status = compute_status(record.next_due_date, reminder_before)

        # Invalidate stale reminders that targeted the old next_due_date
        if old_next_due and old_next_due != record.next_due_date:
            stale = (
                db.query(Reminder)
                .filter(
                    Reminder.preventive_record_id == record.id,
                    Reminder.next_due_date == old_next_due,
                    Reminder.status.in_(["pending", "sent"]),
                )
                .all()
            )
            for r in stale:
                r.status = "completed"

        changes.append(
            f"last done {new_date}, next due {record.next_due_date}, status: {record.status}"
        )

    db.commit()
    name_display = master.item_name if master else item_name
    return f"Updated '{name_display}': {'; '.join(changes)}."


def _tool_add_preventive_record(db: Session, user, pet, tool_input: dict) -> str:
    """Add a new custom preventive record (supplement, medication, or vaccine)."""
    from app.models.custom_preventive_item import CustomPreventiveItem
    from app.models.preventive_record import PreventiveRecord
    from app.services.preventive_calculator import compute_next_due_date, compute_status

    item_name = tool_input.get("item_name", "").strip()
    date_str = tool_input.get("last_done_date", "").strip() or None
    recurrence_days = max(1, min(int(tool_input.get("recurrence_days") or 30), 3650))

    if not item_name:
        return "item_name is required."

    # Get or create the CustomPreventiveItem for this user
    species = pet.species or "both"
    custom_item = (
        db.query(CustomPreventiveItem)
        .filter(
            CustomPreventiveItem.user_id == user.id,
            CustomPreventiveItem.item_name == item_name,
        )
        .first()
    )
    if not custom_item:
        custom_item = CustomPreventiveItem(
            user_id=user.id,
            item_name=item_name,
            category="complete",
            circle="health",
            species=species,
            recurrence_days=recurrence_days,
            reminder_before_days=7,
            overdue_after_days=7,
        )
        db.add(custom_item)
        db.flush()

    # Parse date
    last_done = _parse_date(date_str) if date_str else None

    # Compute next_due and status
    if last_done:
        next_due = compute_next_due_date(last_done, recurrence_days)
        status = compute_status(next_due, 7)
    else:
        next_due = None
        status = "upcoming"

    record = PreventiveRecord(
        pet_id=pet.id,
        custom_preventive_item_id=custom_item.id,
        last_done_date=last_done,
        next_due_date=next_due,
        status=status,
    )
    db.add(record)
    db.commit()
    date_display = f", last done {last_done}" if last_done else ""
    return f"Added custom record '{item_name}'{date_display}."


def _tool_remove_preventive_record(db: Session, pet, tool_input: dict) -> str:
    """Remove a custom preventive record. Core master records cannot be removed."""
    from app.models.preventive_record import PreventiveRecord

    item_name = tool_input.get("item_name", "").strip()
    if not item_name:
        return "item_name is required."

    record, master = _find_preventive_record(db, pet.id, item_name)
    if not record:
        return f"No preventive record matching '{item_name}' found."

    # Reject removal of core (master) items
    if record.preventive_master_id is not None:
        name = master.item_name if master else item_name
        return (
            f"'{name}' is a core preventive item and cannot be removed. "
            "I can update its last done date instead — would you like that?"
        )

    db.delete(record)
    db.commit()
    return f"Removed custom record '{item_name}'."


def _tool_update_owner_name(db: Session, user, tool_input: dict) -> str:
    """Update the user's full_name."""
    new_name = tool_input.get("new_name", "").strip()
    if not new_name:
        return "new_name is required."
    if len(new_name) > 120:
        return "Name too long (max 120 characters)."

    old = user.full_name or "not set"
    user.full_name = new_name
    db.commit()
    return f"Owner name updated from '{old}' to '{new_name}'."


# ---------------------------------------------------------------------------
# finish_edit — dashboard link send
# ---------------------------------------------------------------------------


async def _handle_finish_edit(db: Session, user, pet, summary: str, send_text_message) -> None:
    """
    Send the confirmation message with the dashboard link.

    Called after finish_edit tool fires. All DB writes for this session
    are already committed at this point.
    """
    from app.config import settings
    from app.services.onboarding import get_or_create_active_dashboard_token

    mobile = _get_mobile(user)

    try:
        token = get_or_create_active_dashboard_token(db, pet.id)
        dashboard_url = f"{settings.FRONTEND_URL}/dashboard/{token}"

        msg = (
            f"Done! Here's what I updated for {pet.name}:\n\n"
            f"{summary}\n\n"
            f"View {pet.name}'s updated profile:\n"
            f"{dashboard_url}\n\n"
            f"\U0001f4cc Tip: Pin this message so you can always find {pet.name}'s care plan link."
        )
        await send_text_message(db, mobile, msg)

    except Exception as exc:
        logger.error("agentic_edit: failed to send finish_edit confirmation: %s", exc)
        await send_text_message(
            db, mobile,
            f"Done! {summary}\n\nSend *dashboard* anytime to get {pet.name}'s updated profile link.",
        )


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def _clear_edit_state(user, db: Session) -> None:
    """Clear edit session state and commit."""
    user.edit_state = None
    user.edit_data = None
    try:
        db.commit()
    except Exception as exc:
        logger.error("agentic_edit: failed to clear edit state: %s", exc)
        db.rollback()


def _save_edit_messages(user, db: Session, messages: list, selected_pet_id: str | None) -> None:
    """Persist the updated conversation to user.edit_data."""
    if user.edit_data is None:
        user.edit_data = {}
    user.edit_data["messages"] = messages
    user.edit_data["selected_pet_id"] = selected_pet_id
    flag_modified(user, "edit_data")
    try:
        db.commit()
    except Exception as exc:
        logger.error("agentic_edit: failed to save messages: %s", exc)
        db.rollback()


def _serialize_block(block) -> dict:
    """Convert an Anthropic content block to a JSON-serialisable dict."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    elif block.type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    return {"type": block.type}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def _find_diet_item(db: Session, pet_id, label: str):
    """Find a diet item by case-insensitive partial label match."""
    from app.models.diet_item import DietItem

    label_lower = label.lower()
    items = db.query(DietItem).filter(DietItem.pet_id == pet_id).all()
    # Exact match first
    for item in items:
        if item.label.lower() == label_lower:
            return item
    # Partial match
    for item in items:
        if label_lower in item.label.lower() or item.label.lower() in label_lower:
            return item
    return None


def _find_preventive_record(db: Session, pet_id, item_name: str):
    """
    Find the most recent preventive record for a pet by item name (partial match).
    Returns (PreventiveRecord, PreventiveMaster | None).
    """
    from app.models.preventive_record import PreventiveRecord
    from app.models.preventive_master import PreventiveMaster
    from app.models.custom_preventive_item import CustomPreventiveItem

    name_lower = item_name.lower()

    # 1. Try master items
    rows = (
        db.query(PreventiveRecord, PreventiveMaster)
        .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
        .filter(PreventiveRecord.pet_id == pet_id)
        .order_by(PreventiveRecord.last_done_date.desc().nullslast())
        .all()
    )
    # Exact match
    for rec, master in rows:
        if master.item_name.lower() == name_lower:
            return rec, master
    # Partial match
    for rec, master in rows:
        if name_lower in master.item_name.lower() or master.item_name.lower() in name_lower:
            return rec, master

    # 2. Try custom items
    custom_rows = (
        db.query(PreventiveRecord, CustomPreventiveItem)
        .join(
            CustomPreventiveItem,
            PreventiveRecord.custom_preventive_item_id == CustomPreventiveItem.id,
        )
        .filter(PreventiveRecord.pet_id == pet_id)
        .order_by(PreventiveRecord.last_done_date.desc().nullslast())
        .all()
    )
    for rec, custom in custom_rows:
        if name_lower in custom.item_name.lower() or custom.item_name.lower() in name_lower:
            return rec, None

    return None, None


# ---------------------------------------------------------------------------
# Value parsers
# ---------------------------------------------------------------------------


def _parse_gender(value: str) -> str | None:
    """Normalise a gender string to 'male' or 'female'."""
    v = value.lower().strip()
    if v in ("male", "m", "boy", "he", "him", "unneutered male", "male dog", "male cat"):
        return "male"
    if v in ("female", "f", "girl", "she", "her", "female dog", "female cat"):
        return "female"
    return None


def _parse_bool(value: str) -> bool | None:
    """Parse yes/no/true/false string to bool."""
    v = value.lower().strip()
    if v in ("yes", "y", "true", "1", "neutered", "spayed", "haan", "ha"):
        return True
    if v in ("no", "n", "false", "0", "not neutered", "intact", "nahi", "na"):
        return False
    return None


def _parse_date(value: str) -> date | None:
    """
    Parse a date string in DD/MM/YYYY, DD-MM-YYYY, or YYYY-MM-DD format.
    Returns a date object or None if parsing fails.
    """
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    # Try named months: "15 March 2024"
    try:
        return datetime.strptime(value, "%d %B %Y").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%d %b %Y").date()
    except ValueError:
        pass
    return None


def _parse_age_or_dob(value: str) -> tuple[date | None, str | None]:
    """
    Parse an age string or date into (dob, age_text).

    Accepts:
        - "3 years" / "3 years 2 months" / "8 months" / "puppy" / "kitten"
        - "15/04/2021" / "15-04-2021" / "2021-04-15" / "15 April 2021"

    Returns:
        (dob, age_text) — dob is None if only relative age given.
    """
    # Try parsing as an explicit date first
    explicit_date = _parse_date(value)
    if explicit_date:
        today = date.today()
        diff_years = (today - explicit_date).days / 365.25
        if diff_years < 1:
            months = int((today - explicit_date).days / 30.44)
            age_text = f"{months} months"
        else:
            age_text = f"{diff_years:.1f} years".replace(".0 ", " ")
        return explicit_date, age_text

    # Relative age — estimate DOB
    v = value.lower().strip()
    life_stage_years = {
        "puppy": 0.5, "kitten": 0.5, "junior": 1.5,
        "adult": 4.0, "mature": 8.0, "senior": 10.0, "geriatric": 13.0,
    }
    for stage, years in life_stage_years.items():
        if stage in v:
            dob = date.today() - timedelta(days=int(years * 365.25))
            return dob, value

    # "3 years 2 months" / "8 months" / "2 years"
    total_days = 0
    year_match = re.search(r"(\d+)\s*year", v)
    month_match = re.search(r"(\d+)\s*month", v)
    if year_match:
        total_days += int(year_match.group(1)) * 365
    if month_match:
        total_days += int(month_match.group(1)) * 30
    if total_days > 0:
        dob = date.today() - timedelta(days=total_days)
        return dob, value

    return None, None


# ---------------------------------------------------------------------------
# Precompute helper (must be called from an async context)
# ---------------------------------------------------------------------------

# Tools whose execution should trigger a dashboard enrichment refresh.
_PRECOMPUTE_TOOLS = frozenset({
    "update_pet_field",
    "update_diet_item",
    "add_diet_item",
    "remove_diet_item",
    "update_preventive_record",
    "add_preventive_record",
    "remove_preventive_record",
})


def _schedule_precompute(pet_id_str: str) -> None:
    """
    Schedule a fire-and-forget precompute task from within an already-running
    async context (e.g., inside _dispatch_tool which is async).

    Must NOT be called from synchronous tool functions — asyncio.create_task
    requires a running event loop, which only exists inside async coroutines.
    """
    try:
        from app.services.precompute_service import precompute_dashboard_enrichments
        asyncio.create_task(precompute_dashboard_enrichments(pet_id_str))
    except Exception as exc:
        logger.warning("agentic_edit: failed to schedule precompute for pet %s: %s", pet_id_str, exc)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


async def handle_agentic_edit_intent(db: Session, user, message_data: dict, send_text_message) -> None:
    """
    Entry point called when the user expresses an edit intent for the first time.

    Initialises the edit session and hands off to handle_agentic_edit_step.
    """
    from app.models.pet import Pet

    mobile = _get_mobile(user)

    # Guard: re-entry (shouldn't happen but be safe)
    if getattr(user, "edit_state", None) == "agentic_edit":
        await handle_agentic_edit_step(db, user, message_data, send_text_message)
        return

    # Load pets
    pets = (
        db.query(Pet)
        .filter(Pet.user_id == user.id, Pet.is_deleted == False)  # noqa: E712
        .order_by(Pet.created_at.asc())
        .all()
    )
    if not pets:
        await send_text_message(
            db, mobile,
            "No active pets found. Send *add pet* to register one.",
        )
        return

    # Single pet → select immediately; multi-pet → let Claude disambiguate
    selected_pet_id = str(pets[0].id) if len(pets) == 1 else None

    user.edit_state = "agentic_edit"
    user.edit_data = {"messages": [], "selected_pet_id": selected_pet_id}
    flag_modified(user, "edit_data")
    try:
        db.commit()
    except Exception as exc:
        logger.error("agentic_edit: failed to init edit state: %s", exc)
        db.rollback()
        await send_text_message(db, mobile, "Something went wrong. Please try again.")
        return

    # Route the triggering message through the step handler
    await handle_agentic_edit_step(db, user, message_data, send_text_message)


async def handle_agentic_edit_step(db: Session, user, message_data: dict, send_text_message) -> None:
    """
    Process one turn of the agentic edit conversation.

    Called for every incoming message while user.edit_state == "agentic_edit".
    """
    from app.models.pet import Pet

    mobile = _get_mobile(user)
    text = (message_data.get("text") or "").strip()

    # Cancel guard
    if text.lower() in ("cancel", "stop"):
        _clear_edit_state(user, db)
        await send_text_message(
            db, mobile,
            "No changes made. Let me know if you need anything else. \U0001f43e",
        )
        return

    edit_data = user.edit_data or {"messages": [], "selected_pet_id": None}
    messages: list = list(edit_data.get("messages") or [])
    selected_pet_id: str | None = edit_data.get("selected_pet_id")

    # Load pets
    pets = (
        db.query(Pet)
        .filter(Pet.user_id == user.id, Pet.is_deleted == False)  # noqa: E712
        .order_by(Pet.created_at.asc())
        .all()
    )
    if not pets:
        _clear_edit_state(user, db)
        await send_text_message(db, mobile, "No active pets found.")
        return

    # Resolve primary pet
    if selected_pet_id:
        pet = next((p for p in pets if str(p.id) == selected_pet_id), pets[0])
    else:
        pet = pets[0]

    # Build system prompt with current data
    pet_data_str = _build_pet_data_context(db, user, pets, pet)
    system_prompt = _build_system_prompt(pet_data_str)

    # Append user message
    messages.append({"role": "user", "content": text})

    # --- Call Claude ---
    try:
        response = await _call_claude_with_tools(messages, system_prompt)
    except Exception as exc:
        logger.error("agentic_edit: Claude API error: %s", exc)
        await send_text_message(
            db, mobile,
            "Something went wrong. Please try again or type *cancel* to stop.",
        )
        # Save what we have so far
        _save_edit_messages(user, db, messages, selected_pet_id)
        return

    # --- Process response blocks ---
    assistant_content = []
    tool_results = []
    reply_text: str | None = None
    terminal_signal: str | None = None
    finish_summary: str | None = None

    for block in response.content:
        block_dict = _serialize_block(block)
        assistant_content.append(block_dict)

        if block.type == "text":
            reply_text = block.text

        elif block.type == "tool_use":
            result = await _dispatch_tool(db, user, pet, block.name, block.input)

            if result == "__COMPLETE__":
                terminal_signal = "__COMPLETE__"
                finish_summary = block.input.get("summary", "All changes saved.")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                # Sentinels (__COMPLETE__) must not be forwarded to the model
                "content": "Done." if result == "__COMPLETE__" else result,
            })

    # --- Append assistant turn + tool results ---
    messages.append({"role": "assistant", "content": assistant_content})
    if tool_results:
        messages.append({"role": "user", "content": tool_results})

    # --- Handle finish_edit ---
    if terminal_signal == "__COMPLETE__":
        try:
            await _handle_finish_edit(db, user, pet, finish_summary or "All changes saved.", send_text_message)
        finally:
            # Always clear state — even if _handle_finish_edit's fallback send_text raises.
            _clear_edit_state(user, db)
        return

    # --- If Claude responded with tools only (no text), get a closing text reply ---
    # This happens when Claude fires one or more tools in a single turn without
    # accompanying text. We make a second text-only call so the user gets feedback.
    if not reply_text and tool_results:
        try:
            text_response = await _call_claude_text_only(messages, system_prompt)
            for block in text_response.content:
                if block.type == "text" and block.text.strip():
                    reply_text = block.text
                    # Append this closing text to history so the next turn has context
                    messages.append({"role": "assistant", "content": [_serialize_block(block)]})
                    break
        except Exception as exc:
            logger.warning("agentic_edit: failed to get text-only response after tools: %s", exc)

    # --- Persist messages for next turn ---
    _save_edit_messages(user, db, messages, selected_pet_id)

    # --- Send text reply to user ---
    if reply_text:
        await send_text_message(db, mobile, reply_text)
