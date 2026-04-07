"""
PetCircle Phase 1 — Onboarding Service (Deterministic Flow v2)

Handles the 9-step WhatsApp conversation for user registration and
pet profile creation. State is tracked via user.onboarding_state.

Conversation flow:
    1. New number → Create user (welcome) → ask pet name
    2. Pet name → state=awaiting_breed_age → ask breed + age (combined)
    3. Breed+age → state=awaiting_gender_weight → ask gender + weight + neutered (combined)
    4. Gender/weight/neutered → auto-send life stage note → state=awaiting_food_type
    5. Food type → state=awaiting_meal_details → ask meal details (contextual)
    6. Meal details → state=awaiting_supplements → ask supplements
    7. Supplements → auto-send progress note → state=awaiting_preventive
    8. Preventive → if partial, state=awaiting_prev_retry (one re-ask) → state=awaiting_documents
    9. Documents / skip / timeout → state=complete → send care plan ready message

Rules:
    - Max 5 pets per user (from constants).
    - Consent is implicit (user sends first message).
    - Combined inputs parsed via light GPT-4.1-mini calls.
    - Species inferred from breed; asked only if ambiguous.
    - "skip" accepted for optional fields.
"""

import json
import logging
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import (
    APP_RETURNING_HEADING,
    DASHBOARD_TOKEN_BYTES,
    DASHBOARD_TOKEN_EXPIRY_DAYS,
    DOC_UPLOAD_WINDOW_SECONDS,
    GREETINGS,
    MAX_PENDING_DOCS_PER_PET,
    MAX_PET_WEIGHT_KG,
    MAX_PETS_PER_USER,
)
from app.core.encryption import decrypt_field, encrypt_field, hash_field
from app.core.log_sanitizer import mask_phone
from app.models.dashboard_token import DashboardToken
from app.models.deferred_care_plan_pending import DeferredCarePlanPending
from app.models.condition import Condition
from app.models.document import Document
from app.models.pet import Pet
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.services.diet_service import HOMEMADE_KW, add_diet_item, split_diet_items_by_type
from app.services.hygiene_service import add_hygiene_item
from app.services.nutrition_service import get_diet_summary
from app.services.preventive_seeder import seed_preventive_master
from app.utils.breed_normalizer import normalize_breed, normalize_breed_with_ai
from app.utils.date_utils import (
    get_today_ist,
    is_ambiguous_date_input,
    parse_date,
    parse_date_with_ai,
)
from app.utils.file_reader import encode_image_base64
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

_openai_onboarding_client = None

def _get_openai_onboarding_client() -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client for onboarding checks."""
    global _openai_onboarding_client
    if _openai_onboarding_client is None:
        _openai_onboarding_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_onboarding_client

def is_doc_upload_deadline_expired(deadline: datetime | None) -> bool:
    """
    Return True when the upload deadline has passed in UTC.

    Handles both timezone-aware and timezone-naive values defensively:
    - aware: compared directly with UTC-aware now
    - naive: treated as UTC to avoid naive/aware comparison crashes

    Naive timestamps can exist in legacy rows created before strict
    timezone handling was enforced.
    """
    if not deadline:
        return False

    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)

    return datetime.now(UTC) > deadline

# --- Colloquial input sets ---
# Accepted variations for yes/no across all onboarding steps.
_YES_INPUTS = frozenset({
    "yes", "y", "yeah", "yea", "yep", "yup", "ya", "yah",
    "sure", "ok", "okay", "agree", "alright", "aight",
    "absolutely", "definitely", "of course", "haan", "ha",
})
_NO_INPUTS = frozenset({
    "no", "n", "nah", "nope", "nay", "na", "not really",
    "disagree", "nahi",
})
# Accepted variations for skip across all onboarding steps.
_SKIP_INPUTS = frozenset({"skip", "s"})
_DOC_SKIP_PHRASES = (
    "not uploading",
    "not uploading now",
    "no documents",
    "no document",
    "no docs",
    "no records",
    "no health records",
    "nothing to upload",
    "don't have",
    "dont have",
)
_DOC_UPLOAD_INTENT_WORDS = ("upload", "sending", "send", "attach", "attached")


def _is_doc_skip_intent(text_lower: str) -> bool:
    """Return True when the user indicates they are skipping document upload."""
    normalized = (text_lower or "").strip()
    if normalized in _SKIP_INPUTS:
        return True
    # Treat explicit "no" / "nahi" / "nope" etc. as skip intent.
    if normalized in _NO_INPUTS:
        return True
    # Avoid false positives such as: "I don't have card, uploading report now".
    if any(word in normalized for word in _DOC_UPLOAD_INTENT_WORDS):
        return False

    collapsed = re.sub(r"\s+", " ", normalized)
    for phrase in _DOC_SKIP_PHRASES:
        if collapsed == phrase:
            return True
        if re.fullmatch(rf"{re.escape(phrase)}[.!?]*", collapsed):
            return True

    return False


def get_or_create_user(db: Session, mobile_number: str) -> tuple[User | None, bool]:
    """
    Look up an existing user by mobile number hash, or return None if new.

    Uses deterministic SHA-256 hash for lookups instead of querying
    the encrypted mobile_number column directly.

    Also checks for soft-deleted users with the same hash and includes
    them in the lookup — see notes on create_pending_user.

    Args:
        db: SQLAlchemy database session.
        mobile_number: WhatsApp phone number (plaintext from webhook).

    Returns:
        Tuple of (User or None, is_existing: bool).
    """
    mobile_h = hash_field(mobile_number)
    user = (
        db.query(User)
        .filter(User.mobile_hash == mobile_h, User.is_deleted == False)
        .first()
    )
    if user:
        return user, True
    return None, False


def create_pending_user(db: Session, mobile_number: str) -> User:
    """
    Create a new user record in awaiting_consent state.

    Handles race conditions: if two webhooks arrive simultaneously for
    the same new number, the second call re-checks for an existing user
    before inserting. If a duplicate IntegrityError occurs, falls back
    to returning the existing record.

    Also reactivates soft-deleted users (consent previously denied)
    instead of creating a duplicate row.

    Args:
        db: SQLAlchemy database session.
        mobile_number: WhatsApp phone number (plaintext).

    Returns:
        The created or existing User model instance.
    """
    mobile_h = hash_field(mobile_number)

    # --- Guard against duplicates ---
    # Re-check inside create to handle race conditions where two webhook
    # calls pass get_or_create_user simultaneously for a new number.
    existing = (
        db.query(User)
        .filter(User.mobile_hash == mobile_h)
        .first()
    )
    if existing:
        if existing.is_deleted:
            # Reactivate a previously soft-deleted user (consent denied earlier).
            existing.is_deleted = False
            existing.onboarding_state = "welcome"
            existing.consent_given = True
            existing.onboarding_data = None
            db.commit()
            logger.info(
                "Reactivated soft-deleted user: id=%s, mobile=%s",
                str(existing.id), mask_phone(mobile_number),
            )
            return existing
        # Active user already exists — return it (race condition resolved).
        logger.info(
            "User already exists (race condition): id=%s, mobile=%s",
            str(existing.id), mask_phone(mobile_number),
        )
        return existing

    user = User(
        mobile_number=encrypt_field(mobile_number),
        mobile_hash=hash_field(mobile_number),
        mobile_display=mobile_number,
        full_name="_pending",
        onboarding_state="welcome",
        consent_given=True,
    )
    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        # IntegrityError from unique constraint — another request created it first.
        db.rollback()
        logger.warning("Duplicate user insert caught: %s", str(e))
        existing = (
            db.query(User)
            .filter(User.mobile_hash == mobile_h, User.is_deleted == False)
            .first()
        )
        if existing:
            return existing
        raise  # Re-raise if we still can't find the user.

    logger.info("Pending user created: id=%s, mobile=%s", str(user.id), mask_phone(mobile_number))
    return user


async def handle_onboarding_step(
    db: Session,
    user: User,
    text: str,
    send_fn,
    message_data: dict | None = None,
) -> None:
    """
    Process one step of the deterministic onboarding conversation.

    Routes to the correct handler based on user.onboarding_state.
    New flow (9 steps): welcome → breed_age → gender_weight → food_type →
    meal_details → supplements → preventive → prev_retry → documents → complete.

    Args:
        db: SQLAlchemy database session.
        user: The User model instance.
        text: The user's message text (stripped).
        send_fn: Async function to send WhatsApp text messages.
            Signature: send_fn(db, to_number, text) -> None
        message_data: Optional dict from webhook with profile_name etc.
    """
    state = user.onboarding_state or "welcome"
    mobile = getattr(user, "_plaintext_mobile", None) or decrypt_field(user.mobile_number)
    user._plaintext_mobile = mobile
    text_lower = text.lower().strip()

    # Detect greetings mid-onboarding — show progress summary and re-ask current question.
    if _is_greeting(text_lower):
        await _send_onboarding_resume(db, user, state, send_fn)
        return

    # If the user asks for their dashboard / care plan link at ANY point
    # before onboarding is complete, tell them it's still being built
    # rather than silently routing the message into the current step
    # handler (which would reply with an unrelated question).
    _DASHBOARD_REQUEST_KEYWORDS = (
        "dashboard", "my link", "share link", "care plan link",
        "my plan", "send link", "pet plan",
    )
    if state != "complete" and any(
        kw in text_lower for kw in _DASHBOARD_REQUEST_KEYWORDS
    ):
        pet_for_msg = (
            db.query(Pet)
            .filter(Pet.user_id == user.id)
            .order_by(Pet.created_at.desc())
            .first()
        )
        pet_name = pet_for_msg.name if pet_for_msg else "your pet"
        await send_fn(
            db, mobile,
            f"{pet_name}'s care plan is still being built 🐾 "
            f"You'll receive the dashboard link as soon as it's ready. "
            f"Let's finish the remaining details first!",
        )
        return

    if state == "welcome":
        await _step_welcome(db, user, text, send_fn, message_data=message_data)

    elif state == "awaiting_breed_age":
        await _step_breed_age(db, user, text, send_fn)

    elif state == "awaiting_gender_weight":
        await _step_gender_weight(db, user, text, send_fn)

    elif state == "awaiting_food_type":
        await _step_food_type(db, user, text, send_fn)

    elif state == "awaiting_meal_details":
        await _step_meal_details(db, user, text, send_fn)

    elif state == "awaiting_supplements":
        await _step_supplements_v2(db, user, text, send_fn)

    elif state == "awaiting_preventive":
        await _step_preventive(db, user, text, send_fn)

    elif state == "awaiting_prev_retry":
        await _step_prev_retry(db, user, text, send_fn)

    elif state == "awaiting_documents":
        await _step_awaiting_documents(db, user, text_lower, send_fn)

    else:
        # Unknown or legacy state — reset.
        logger.warning("Unknown onboarding state '%s' for user %s — resetting to welcome", state, mobile)
        user.onboarding_state = "welcome"
        user.onboarding_data = None
        db.commit()
        profile_name = user.full_name if user.full_name != "_pending" else "there"
        await send_fn(
            db, mobile,
            f"Hello {profile_name}! 👋 Welcome to PetCircle — your pet's personalised "
            f"care companion, right here on WhatsApp. I'm here to make sure your pet "
            f"never misses the care they deserve.\n\n"
            f"Let's start — what's your pet's name?",
        )


def _is_greeting(text_lower: str) -> bool:
    """Check if the message is a greeting rather than onboarding input."""
    return text_lower in GREETINGS


# --- Food type keyword sets for deterministic matching ---
_HOME_FOOD_KEYWORDS = frozenset({
    "home", "homemade", "home food", "ghar ka", "ghar ka khana", "home cooked",
    "homecooked", "home made",
})
_PACKAGED_FOOD_KEYWORDS = frozenset({
    "packaged", "kibble", "branded", "dry food", "wet food", "canned",
    "commercial", "store bought",
})
_MIX_FOOD_KEYWORDS = frozenset({
    "mix", "both", "mixed", "combination", "dono",
})
_NONE_KEYWORDS = frozenset({
    "none", "no", "nope", "nothing", "na", "nahi", "nil", "n/a",
})

# --- Onboarding data helpers ---

def _get_onboarding_data(user) -> dict:
    """Get onboarding_data dict, defaulting to empty dict if None."""
    return user.onboarding_data or {}


def _set_onboarding_data(user, key: str, value):
    """Set a key in onboarding_data, creating the dict if needed."""
    from sqlalchemy.orm.attributes import flag_modified
    data = dict(user.onboarding_data or {})
    data[key] = value
    user.onboarding_data = data
    flag_modified(user, "onboarding_data")


async def _send_onboarding_resume(db, user, state, send_fn):
    """
    Send a welcome-back message showing only the last collected field,
    then re-ask the current onboarding question.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)

    last_saved = _get_last_saved_detail(user, pet, db)

    greeting = f"{APP_RETURNING_HEADING}\n\nLet's continue setting up your profile."
    if last_saved:
        greeting += f"\n\nLast saved: {last_saved}."

    next_question = _get_question_for_state(state, pet)
    await send_fn(db, mobile, f"{greeting}\n\n{next_question}")


def _get_last_saved_detail(user, pet, db) -> str:
    """
    Return a human-readable string for the most recently collected onboarding field.
    Checks in reverse collection order so the highest-priority collected field wins.
    """
    from app.models.diet_item import DietItem

    pet_name = pet.name if pet else "your pet"

    if pet:
        diet_count = db.query(DietItem).filter(DietItem.pet_id == pet.id).count()
        if diet_count > 0:
            return f"{pet_name}'s diet — {diet_count} item(s) recorded"
        if pet.neutered is not None:
            return f"{pet_name}'s neutered status — {'Yes' if pet.neutered else 'No'}"
        if pet.weight:
            return f"{pet_name}'s weight — {pet.weight} kg"
        if pet.age_text:
            return f"{pet_name}'s age — {pet.age_text}"
        if pet.gender:
            return f"{pet_name}'s gender — {pet.gender.capitalize()}"
        if pet.breed:
            return f"{pet_name}'s breed — {pet.breed}"
        if pet.species and pet.species != "_pending":
            return f"{pet_name}'s species — {pet.species.capitalize()}"
        return f"Pet name — {pet_name}"

    if user.full_name and user.full_name != "_pending":
        return f"Your name — {user.full_name}"
    return ""


def _get_question_for_state(state: str, pet=None) -> str:
    """Return the question prompt corresponding to the current onboarding state."""
    pet_name = pet.name if pet else "your pet"

    prompts = {
        "welcome": "What's your pet's name?",
        "awaiting_breed_age": (
            f"What breed is {pet_name} and how old are they? "
            f"An approximate age is fine (e.g., golden retriever, 4)"
        ),
        "awaiting_gender_weight": (
            f"What's {pet_name}'s gender and approximate weight? "
            f"Are they neutered or spayed? (e.g., male, 22, neutered)"
        ),
        "awaiting_food_type": (
            f"What does {pet_name} usually eat — home food, packaged, or a mix?"
        ),
        "awaiting_meal_details": (
            f"What does {pet_name}'s typical daily diet look like?"
        ),
        "awaiting_supplements": (
            f"Is {pet_name} on any supplements right now? "
            f"(e.g., joint support, Omega-3, calcium — or just say None)"
        ),
        "awaiting_preventive": (
            f"What do you remember about {pet_name}'s vaccines, deworming, "
            f"flea & tick, and blood tests? (e.g., vaccines last Dec, deworming Jan, "
            f"flea 2 months ago, no blood test yet — rough is fine)."
        ),
        "awaiting_prev_retry": (
            f"Any more details about {pet_name}'s preventive care?"
        ),
        "awaiting_documents": (
            f"Do you have any health records handy — a vaccination card, "
            f"vet prescription, or lab report? Share a photo or PDF and I'll pull "
            f"the details in automatically. No worries if not, we can always add them later."
        ),
    }
    return prompts.get(state, "Let's continue setting up your profile.")


# =====================================================================
# NEW DETERMINISTIC ONBOARDING STEP HANDLERS (9-step flow from flow.txt)
# =====================================================================


async def _step_welcome(db, user, text, send_fn, message_data: dict | None = None):
    """
    Step 1: Collect pet name. The welcome message was already sent by the router.
    User's reply IS the pet name.
    """
    mobile = user._plaintext_mobile

    # Use WhatsApp profile name as user's full_name if still pending.
    if user.full_name == "_pending":
        profile_name = (message_data or {}).get("profile_name")
        if profile_name:
            user.full_name = profile_name.strip().title()

    pet_name = text.strip().title()
    if len(pet_name) < 1 or len(pet_name) > 100:
        await send_fn(db, mobile, "Please enter a valid pet name.")
        return

    # Check pet limit.
    pet_count = (
        db.query(Pet)
        .filter(Pet.user_id == user.id, Pet.is_deleted == False)
        .count()
    )
    if pet_count >= MAX_PETS_PER_USER:
        await send_fn(
            db, mobile,
            f"You already have {MAX_PETS_PER_USER} pets registered. That's the maximum!",
        )
        user.onboarding_state = "complete"
        db.commit()
        return

    # Create pet with placeholder species.
    pet = Pet(user_id=user.id, name=pet_name, species="_pending")
    db.add(pet)

    user.onboarding_state = "awaiting_breed_age"
    _set_onboarding_data(user, "breed_age_attempts", 0)
    db.commit()

    await send_fn(
        db, mobile,
        f"Love that name! 🐾 What breed is {pet_name} and how old are they? "
        f"An approximate age is fine (e.g., golden retriever, 4)",
    )


async def _step_breed_age(db, user, text, send_fn):
    """
    Step 2: Collect breed + approximate age (combined input, GPT-parsed).
    Validates breed via normalize_breed, infers species from breed dicts.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)
    if not pet:
        user.onboarding_state = "welcome"
        db.commit()
        await send_fn(db, mobile, "Something went wrong. Let's start — what's your pet's name?")
        return

    text_lower = text.strip().lower()
    od = _get_onboarding_data(user)
    attempts = od.get("breed_age_attempts", 0)

    # Handle species sub-question: if we're waiting for dog/cat answer.
    if od.get("needs_species"):
        species_map = {"d": "dog", "dog": "dog", "c": "cat", "cat": "cat"}
        species = species_map.get(text_lower)
        if species:
            pet.species = species
            _set_onboarding_data(user, "needs_species", False)
            _set_onboarding_data(user, "gender_weight_attempts", 0)
            user.onboarding_state = "awaiting_gender_weight"
            db.commit()
            await send_fn(
                db, mobile,
                f"Got it. What's {pet.name}'s gender and approximate weight? "
                f"Are they neutered or spayed? (e.g., male, 22, neutered)",
            )
            return
        await send_fn(db, mobile, f"Please reply *dog* or *cat*.")
        return

    # Handle skip.
    if text_lower in _SKIP_INPUTS:
        _set_onboarding_data(user, "gender_weight_attempts", 0)
        user.onboarding_state = "awaiting_gender_weight"
        db.commit()
        await send_fn(
            db, mobile,
            f"No worries! What's {pet.name}'s gender and approximate weight? "
            f"Are they neutered or spayed? (e.g., male, 22, neutered)",
        )
        return

    # GPT parse breed + age.
    parsed = await _parse_breed_age(text)
    breed_raw = parsed.get("breed")
    species_gpt = parsed.get("species")
    age_years = parsed.get("age_years")
    age_text_raw = parsed.get("age_text")
    confident = parsed.get("confident", False)

    # Normalize and save breed if provided.
    if breed_raw:
        normalized = normalize_breed(breed_raw, species=species_gpt)
        if normalized == breed_raw.strip().title():
            try:
                normalized = await normalize_breed_with_ai(breed_raw, species=species_gpt)
            except Exception:
                pass
        pet.breed = normalized

        # Infer species from breed dictionaries if GPT didn't provide it.
        if not species_gpt:
            species_gpt = _infer_species_from_breed(breed_raw)

    # Set species if newly identified.
    if species_gpt in {"dog", "cat"}:
        pet.species = species_gpt

    # Save age if provided.
    # Prefer explicit DOB from GPT (user gave a birth date like "11/11/2021").
    from datetime import date as date_type
    explicit_dob = parsed.get("dob")
    if explicit_dob:
        try:
            parsed_dob = date_type.fromisoformat(str(explicit_dob))
            if parsed_dob <= date_type.today():
                pet.dob = parsed_dob
                pet.age_text = _age_text_from_dob(parsed_dob)
        except (ValueError, TypeError):
            explicit_dob = None  # fall through to age_years logic

    if not explicit_dob and age_years is not None:
        pet.age_text = age_text_raw or f"{age_years} years"
        # Compute approximate DOB for scheduling.
        approx_dob = date_type(
            date_type.today().year - int(age_years),
            max(1, min(12, date_type.today().month)),
            1,
        )
        if approx_dob > date_type.today():
            # If age < 1 year, subtract months instead.
            months = max(1, int(age_years * 12))
            y = date_type.today().year
            m = date_type.today().month - months
            while m <= 0:
                m += 12
                y -= 1
            approx_dob = date_type(y, m, 1)
        pet.dob = approx_dob
        # Ensure age_text is human-readable from the computed DOB.
        if pet.dob:
            pet.age_text = _age_text_from_dob(pet.dob)

    # Re-ask ONCE for whichever piece is missing. On the 2nd attempt
    # (attempts >= 1), advance regardless of what's still missing.
    has_breed = bool(pet.breed)
    has_age = bool(pet.age_text) or bool(pet.dob)

    if attempts < 1 and (not has_breed or not has_age):
        _set_onboarding_data(user, "breed_age_attempts", attempts + 1)
        db.commit()
        if not has_breed and not has_age:
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context="the pet's breed and approximate age",
                expected_format="e.g., golden retriever, 4 years",
                pet_name=pet.name,
            )
        elif not has_breed:
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context=f"the pet's breed (age already noted as {pet.age_text})",
                expected_format="e.g., golden retriever, labrador, or just say 'mixed'",
                pet_name=pet.name,
            )
        else:
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context=f"the pet's age (breed already noted as {pet.breed})",
                expected_format="e.g., 4 years, 6 months, puppy",
                pet_name=pet.name,
            )
        await send_fn(db, mobile, clarification)
        return

    # If species still unknown, ask as sub-question.
    if pet.species in (None, "_pending"):
        _set_onboarding_data(user, "needs_species", True)
        db.commit()
        await send_fn(
            db, mobile,
            f"Got it! Is {pet.name} a *dog* or a *cat*?",
        )
        return

    # All good — advance to next step.
    _set_onboarding_data(user, "gender_weight_attempts", 0)
    user.onboarding_state = "awaiting_gender_weight"
    db.commit()

    await send_fn(
        db, mobile,
        f"Got it. What's {pet.name}'s gender and approximate weight? "
        f"Are they neutered or spayed? (e.g., male, 22, neutered)",
    )


async def _step_gender_weight(db, user, text, send_fn):
    """
    Step 3: Collect gender + weight + neutered (combined input, GPT-parsed).
    Clarifies once via AI if nothing can be parsed, then accepts whatever is provided.
    Auto-sends life stage note + food question.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)
    if not pet:
        user.onboarding_state = "welcome"
        db.commit()
        await send_fn(db, mobile, "Something went wrong. Let's start — what's your pet's name?")
        return

    text_lower = text.strip().lower()

    od = _get_onboarding_data(user)
    gw_attempts = od.get("gender_weight_attempts", 0)

    if text_lower not in _SKIP_INPUTS:
        parsed = await _parse_gender_weight_neutered(text)
        gender = parsed.get("gender")
        weight_kg = parsed.get("weight_kg")
        neutered = parsed.get("neutered")

        # If nothing at all was parsed and this is the first attempt, clarify.
        if gender is None and weight_kg is None and neutered is None and gw_attempts < 1:
            _set_onboarding_data(user, "gender_weight_attempts", 1)
            db.commit()
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context="the pet's gender, approximate weight, and neutered/spayed status",
                expected_format="e.g., male, 22 kg, neutered",
                pet_name=pet.name,
            )
            await send_fn(db, mobile, clarification)
            return

        # Validate and store gender.
        if gender in ("male", "female"):
            pet.gender = gender

        # Validate and store weight.
        if weight_kg is not None:
            try:
                w = float(weight_kg)
                if 0 < w <= MAX_PET_WEIGHT_KG:
                    pet.weight = w
                    pet.weight_flagged = False
                    # AI weight check — non-blocking, just flag if unusual.
                    ai_result = await _ai_check_weight(
                        species=pet.species, breed=pet.breed,
                        dob=pet.dob, weight_kg=w,
                    )
                    if ai_result and not ai_result.get("reasonable", True):
                        pet.weight_flagged = True
            except (ValueError, TypeError):
                pass

        # Store neutered.
        if neutered is not None:
            pet.neutered = bool(neutered)

    # Compute and send life stage note.
    age_years = None
    if pet.dob:
        today = date.today()
        age_years = (today - pet.dob).days / 365.25
    elif pet.age_text:
        # Try to extract age_years from age_text.
        import re
        nums = re.findall(r"[\d.]+", pet.age_text)
        if nums:
            try:
                age_years = float(nums[0])
            except ValueError:
                pass

    life_stage = _compute_life_stage(age_years)
    if life_stage:
        stage_name, one_liner = life_stage
        await send_fn(
            db, mobile,
            f"{pet.name} is a {stage_name} — {one_liner}",
        )

    # Advance to food type question.
    # Start at -1 so a queued message that arrives before the user sees the
    # question gets one free pass (increments to 0) instead of triggering
    # an immediate clarification.
    user.onboarding_state = "awaiting_food_type"
    _set_onboarding_data(user, "food_type_attempts", -1)
    db.commit()

    await send_fn(
        db, mobile,
        f"What does {pet.name} usually eat — home food, packaged, or a mix?",
    )


async def _step_food_type(db, user, text, send_fn):
    """
    Step 4: Collect food type (home / packaged / mix) — deterministic keyword matching.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)
    if not pet:
        user.onboarding_state = "welcome"
        db.commit()
        await send_fn(db, mobile, "Something went wrong. Let's start — what's your pet's name?")
        return

    text_lower = text.strip().lower()
    od = _get_onboarding_data(user)
    attempts = od.get("food_type_attempts", 0)

    # Match food type.
    food_type = None
    if text_lower in _HOME_FOOD_KEYWORDS:
        food_type = "home"
    elif text_lower in _PACKAGED_FOOD_KEYWORDS:
        food_type = "packaged"
    elif text_lower in _MIX_FOOD_KEYWORDS:
        food_type = "mix"
    elif text_lower in _SKIP_INPUTS:
        food_type = "mix"  # Default to mix on skip.

    if not food_type:
        # Try AI parsing for ambiguous input (e.g., "same", "sampe", "like before").
        ai_food_type = await _ai_parse_food_type(text, pet.name)
        if ai_food_type in ("home", "packaged", "mix"):
            food_type = ai_food_type

    if not food_type:
        if attempts >= 1 or attempts < 0:
            food_type = "mix"  # Default on grace pass (queued msg) or second unrecognized.
        else:
            _set_onboarding_data(user, "food_type_attempts", attempts + 1)
            db.commit()
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context="what type of food the pet eats",
                expected_format="Reply with *home food*, *packaged food*, or *mix*",
                pet_name=pet.name,
            )
            await send_fn(db, mobile, clarification)
            return

    _set_onboarding_data(user, "food_type", food_type)
    _set_onboarding_data(user, "meal_details_attempts", 0)
    _set_onboarding_data(user, "meal_confirm_pending", False)
    user.onboarding_state = "awaiting_meal_details"

    # Contextual meal details question — store the example so we can
    # reference it if the user says "same".
    _MEAL_EXAMPLES = {
        "home": "boiled chicken + rice in the morning, dal + roti at night, occasional egg",
        "packaged": "Royal Canin Adult kibble 50g × 3 times a day, small treat in the evening",
        "mix": "Pedigree kibble in the morning, home-cooked khichdi at night, egg twice a week",
    }
    example_text = _MEAL_EXAMPLES.get(food_type, _MEAL_EXAMPLES["mix"])
    _set_onboarding_data(user, "meal_example_shown", example_text)
    db.commit()

    await send_fn(
        db, mobile,
        f"What does {pet.name}'s typical daily diet look like? (e.g., {example_text})",
    )


async def _step_meal_details(db, user, text, send_fn):
    """
    Step 5: Collect meal details. Parsed via existing _parse_diet_input, stored as DietItems.

    Handles 'same as example' flow:
    - User says 'same' → confirm the example shown → user says yes/yes-but → capture.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)
    if not pet:
        user.onboarding_state = "welcome"
        db.commit()
        await send_fn(db, mobile, "Something went wrong. Let's start — what's your pet's name?")
        return

    od = _get_onboarding_data(user)
    food_type = od.get("food_type", "mix")
    meal_attempts = od.get("meal_details_attempts", 0)
    confirm_pending = od.get("meal_confirm_pending", False)
    example_shown = od.get("meal_example_shown", "")
    text_lower = text.strip().lower()

    # --- Handle confirmation reply (user was asked "Is this what X eats?") ---
    if confirm_pending:
        _set_onboarding_data(user, "meal_confirm_pending", False)
        if text_lower in _SKIP_INPUTS:
            # Skip — proceed without saving.
            pass
        else:
            # Use AI to interpret: plain yes → use example as-is,
            # yes-with-changes → modify example, no → re-ask.
            final_diet = await _ai_resolve_example_confirmation(
                text, example_shown, pet.name, "diet",
            )
            if final_diet == "__reject__":
                # User said no / something completely different — re-ask.
                db.commit()
                await send_fn(
                    db, mobile,
                    f"No problem! Could you describe what {pet.name} actually eats "
                    f"in a typical day?",
                )
                return
            # Parse the resolved diet text into items.
            items = await _parse_diet_input(final_diet)
            await _store_meal_items(db, pet, items, food_type)

        user.onboarding_state = "awaiting_supplements"
        db.commit()
        await send_fn(
            db, mobile,
            f"Noted. Is {pet.name} on any supplements right now? "
            f"(e.g., joint support, Omega-3, calcium — or just say None)",
        )
        return

    # --- Normal meal details input ---
    if text_lower not in _SKIP_INPUTS:
        # Detect "same" / "same as example" type responses.
        if example_shown and _is_same_as_example_intent(text_lower):
            _set_onboarding_data(user, "meal_confirm_pending", True)
            db.commit()
            await send_fn(
                db, mobile,
                f"Just to confirm — is this what {pet.name} eats?\n\n"
                f"_{example_shown}_\n\n"
                f"You can share any corrections if needed "
                f"(e.g., 'yes but no egg' or 'yes and also curd').",
            )
            return

        # Check if input actually describes food/diet or is ambiguous/irrelevant.
        is_diet = await _ai_check_diet_relevance(text, pet.name)
        if not is_diet and meal_attempts < 1:
            _set_onboarding_data(user, "meal_details_attempts", meal_attempts + 1)
            db.commit()
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context=f"what {pet.name}'s typical daily diet looks like — the actual meals they eat",
                expected_format=f"e.g., {example_shown}" if example_shown else "e.g., boiled chicken + rice in the morning, dal + roti at night",
                pet_name=pet.name,
            )
            await send_fn(db, mobile, clarification)
            return

        items = await _parse_diet_input(text)
        await _store_meal_items(db, pet, items, food_type)

    user.onboarding_state = "awaiting_supplements"
    db.commit()

    await send_fn(
        db, mobile,
        f"Noted. Is {pet.name} on any supplements right now? "
        f"(e.g., joint support, Omega-3, calcium — or just say None)",
    )


async def _step_supplements_v2(db, user, text, send_fn):
    """
    Step 6: Collect supplements. Then auto-send progress indicator + preventive care question.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)
    if not pet:
        user.onboarding_state = "welcome"
        db.commit()
        await send_fn(db, mobile, "Something went wrong. Let's start — what's your pet's name?")
        return

    text_lower = text.strip().lower()

    if text_lower not in _SKIP_INPUTS and text_lower not in _NONE_KEYWORDS:
        items = await _parse_diet_input(text)
        for label, detail in items:
            try:
                await add_diet_item(db, pet.id, "supplement", label, detail or None)
            except Exception as e:
                logger.error("Failed to save supplement for pet %s: %s", str(pet.id), str(e))

    # Progress indicator message.
    await send_fn(
        db, mobile,
        f"Thanks for sharing. 🐾 I'll check how {pet.name}'s diet is working "
        f"for their specific needs and build it into the care plan.\n\n"
        f"One last information and we're done — preventive care.",
    )

    # Preventive care question.
    _PREVENTIVE_EXAMPLE = "vaccines last Dec, deworming Jan, flea 2 months ago, no blood test yet"
    user.onboarding_state = "awaiting_preventive"
    _set_onboarding_data(user, "preventive_attempts", 0)
    _set_onboarding_data(user, "preventive_confirm_pending", False)
    _set_onboarding_data(user, "preventive_example_shown", _PREVENTIVE_EXAMPLE)
    db.commit()

    await send_fn(
        db, mobile,
        f"What do you remember about {pet.name}'s vaccines, deworming, flea & tick, "
        f"and blood tests? (e.g., {_PREVENTIVE_EXAMPLE} — rough is fine).",
    )


async def _step_preventive(db, user, text, send_fn):
    """
    Step 7: Collect preventive care info. If partial, re-ask missing fields ONCE.

    Handles 'same as example' flow for preventive care.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)
    if not pet:
        user.onboarding_state = "welcome"
        db.commit()
        await send_fn(db, mobile, "Something went wrong. Let's start — what's your pet's name?")
        return

    text_lower = text.strip().lower()
    od = _get_onboarding_data(user)
    confirm_pending = od.get("preventive_confirm_pending", False)
    example_shown = od.get("preventive_example_shown", "")

    # --- Handle confirmation reply (user was asked "Is this your pet's history?") ---
    if confirm_pending:
        _set_onboarding_data(user, "preventive_confirm_pending", False)
        if text_lower not in _SKIP_INPUTS:
            final_preventive = await _ai_resolve_example_confirmation(
                text, example_shown, pet.name, "preventive",
            )
            if final_preventive == "__reject__":
                db.commit()
                await send_fn(
                    db, mobile,
                    f"No problem! Could you share what you remember about {pet.name}'s "
                    f"vaccines, deworming, flea & tick, and blood tests?",
                )
                return
            # Parse the confirmed/modified preventive text.
            parsed = await _parse_preventive_care(final_preventive)
            await _store_preventive_data(db, pet, parsed)

        await _transition_to_documents(db, user, pet, send_fn)
        return

    # Skip / nothing done.
    if text_lower in _SKIP_INPUTS or text_lower in _NONE_KEYWORDS or text_lower in {"nothing done", "no idea", "don't remember", "dont remember"}:
        await _transition_to_documents(db, user, pet, send_fn)
        return

    # Detect "same as example" intent.
    if example_shown and _is_same_as_example_intent(text_lower):
        _set_onboarding_data(user, "preventive_confirm_pending", True)
        db.commit()
        await send_fn(
            db, mobile,
            f"Just to confirm — is this {pet.name}'s preventive care history?\n\n"
            f"_{example_shown}_\n\n"
            f"You can share any corrections if needed "
            f"(e.g., 'yes but deworming was 2 months ago').",
        )
        return

    # GPT parse preventive care.
    parsed = await _parse_preventive_care(text)

    missing = parsed.get("missing", [])
    attempts = od.get("preventive_attempts", 0)

    # If ALL fields are missing (nothing parsed at all), clarify with AI first.
    all_fields = {"vaccines", "deworming", "flea_tick", "blood_test"}
    if set(missing) == all_fields and attempts < 1:
        _set_onboarding_data(user, "preventive_attempts", 1)
        db.commit()
        clarification = await _ai_clarify_input(
            user_message=text,
            step_context="the pet's preventive care history — vaccines, deworming, flea & tick treatment, and blood tests",
            expected_format=f"e.g., {example_shown}" if example_shown else "e.g., vaccines last Dec, deworming Jan, flea 2 months ago, no blood test yet",
            pet_name=pet.name,
        )
        await send_fn(db, mobile, clarification)
        return

    # Store whatever was parsed.
    await _store_preventive_data(db, pet, parsed)

    # If some fields are missing and this is the first attempt, re-ask once.
    if missing and attempts < 1:
        _set_onboarding_data(user, "preventive_attempts", 1)
        user.onboarding_state = "awaiting_prev_retry"
        db.commit()

        # Build a friendly list of what's missing.
        missing_names = {
            "vaccines": "vaccines",
            "deworming": "deworming",
            "flea_tick": "flea & tick treatment",
            "blood_test": "blood tests",
        }
        missing_readable = [missing_names.get(m, m) for m in missing]
        missing_str = " and ".join(missing_readable)

        # Acknowledge what was provided.
        provided = []
        if parsed.get("vaccines") and parsed["vaccines"] != "none":
            provided.append("vaccines")
        if parsed.get("deworming") and parsed["deworming"] != "none":
            provided.append("deworming")
        if parsed.get("flea_tick") and parsed["flea_tick"] != "none":
            provided.append("flea & tick")
        if parsed.get("blood_test") and parsed["blood_test"] != "none":
            provided.append("blood tests")

        ack = ""
        if provided:
            ack = f"Got it — {' and '.join(provided)} noted! "

        # Build examples only for missing categories
        missing_examples = {
            "vaccines": "vaccines last Dec",
            "deworming": "deworming 3 months ago",
            "flea_tick": "flea drops 2 months ago",
            "blood_test": "no blood test yet",
        }
        eg_parts = [missing_examples[m] for m in missing if m in missing_examples]
        eg_str = f" (e.g., {', '.join(eg_parts)})" if eg_parts else ""

        await send_fn(
            db, mobile,
            f"{ack}What about {missing_str}?{eg_str}",
        )
        return

    # All provided or second attempt — proceed to documents.
    await _transition_to_documents(db, user, pet, send_fn)


async def _step_prev_retry(db, user, text, send_fn):
    """
    Step 8: Collect remaining preventive info. Never re-asks again.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)
    if not pet:
        user.onboarding_state = "welcome"
        db.commit()
        await send_fn(db, mobile, "Something went wrong. Let's start — what's your pet's name?")
        return

    text_lower = text.strip().lower()

    # Even if skip / none, just proceed.
    if text_lower not in _SKIP_INPUTS and text_lower not in _NONE_KEYWORDS:
        parsed = await _parse_preventive_care(text)
        await _store_preventive_data(db, pet, parsed)

    await _transition_to_documents(db, user, pet, send_fn)


async def _parse_preventive_date_value(raw: str, pet: Pet) -> date | None:
    """
    Parse a free-text preventive-care date and validate against pet DOB.

    Returns None if the value cannot be parsed or is before the pet's DOB.
    """
    if not raw:
        return None

    parsed_date = None
    try:
        parsed_date = parse_date(raw)
    except (ValueError, TypeError):
        pass
    if parsed_date is None:
        try:
            parsed_date = await parse_date_with_ai(raw)
        except (ValueError, TypeError):
            pass

    if parsed_date is None:
        logger.warning("Could not parse preventive date: '%s'", raw)
        return None

    # DOB-based reasonableness: date can't be before pet was born.
    if pet.dob and parsed_date < pet.dob:
        logger.warning(
            "Preventive date %s is before pet DOB %s, skipping", parsed_date, pet.dob,
        )
        return None

    return parsed_date


def _upsert_preventive_record(db, pet, master, parsed_date, medicine_name: str | None = None) -> None:
    """
    Create or update a PreventiveRecord for (pet, master), keeping the most
    recent last_done_date. Caller is responsible for committing.

    Computes next_due_date and status so the NOT NULL constraint on
    PreventiveRecord.status is satisfied.
    """
    from app.services.preventive_calculator import compute_next_due_date, compute_status

    recurrence_days = master.recurrence_days or 365
    reminder_before_days = master.reminder_before_days or 30
    next_due = compute_next_due_date(parsed_date, recurrence_days)
    status = compute_status(next_due, reminder_before_days)

    existing = (
        db.query(PreventiveRecord)
        .filter(
            PreventiveRecord.pet_id == pet.id,
            PreventiveRecord.preventive_master_id == master.id,
        )
        .first()
    )
    if existing:
        if not existing.last_done_date or parsed_date > existing.last_done_date:
            existing.last_done_date = parsed_date
            existing.next_due_date = next_due
            existing.status = status
        if medicine_name and not existing.medicine_name:
            existing.medicine_name = medicine_name
    else:
        record = PreventiveRecord(
            pet_id=pet.id,
            preventive_master_id=master.id,
            last_done_date=parsed_date,
            next_due_date=next_due,
            status=status,
            medicine_name=medicine_name,
        )
        db.add(record)


def _essential_annual_vaccine_masters(db: Session, species: str) -> list[PreventiveMaster]:
    """
    Return all recurring annual vaccine masters for the species.

    Filters: circle='health', recurrence_days <= 730,
    and item name classified as 'vaccine' by nudge_engine._classify_item.
    Excludes puppy dose series (recurrence_days=36500) and non-vaccines
    (e.g. Deworming, Annual Checkup).

    Includes both mandatory and optional annual vaccines so generic
    onboarding inputs like "vaccines last Dec" apply to all vaccine rows,
    including Kennel Cough (Nobivac KC).
    """
    from app.services.nudge_engine import _classify_item

    rows = (
        db.query(PreventiveMaster)
        .filter(
            PreventiveMaster.species.in_([species, "both"]),
            PreventiveMaster.circle == "health",
            PreventiveMaster.recurrence_days <= 730,
        )
        .all()
    )
    return [m for m in rows if _classify_item(m.item_name) == "vaccine"]


def _resolve_vaccine_item_name(name: str) -> str | None:
    """Resolve a free-text vaccine alias to a canonical preventive item name."""
    from app.services.gpt_extraction import _VACCINE_DETAIL_TO_ITEM

    normalized = (name or "").strip().lower()
    if not normalized:
        return None

    # Prefer exact alias keys, then fallback to keyword containment matching.
    exact = _VACCINE_DETAIL_TO_ITEM.get(normalized)
    if exact:
        return exact

    for keyword, item_name in _VACCINE_DETAIL_TO_ITEM.items():
        if keyword in normalized:
            return item_name

    return None


def _match_specific_vaccine_master(
    db: Session, species: str, name: str,
) -> PreventiveMaster | None:
    """
    Map a free-text vaccine name ('rabies', 'dhppi', '7 in 1') to a single
    PreventiveMaster row. Reuses gpt_extraction._VACCINE_DETAIL_TO_ITEM as
    the single source of truth for name aliases.
    """
    item_name = _resolve_vaccine_item_name(name)
    if not item_name:
        return None
    return (
        db.query(PreventiveMaster)
        .filter(
            PreventiveMaster.item_name == item_name,
            PreventiveMaster.species.in_([species, "both"]),
        )
        .first()
    )


async def _store_preventive_data(db, pet, parsed: dict):
    """
    Store parsed preventive care data as preventive records.

    Vaccine handling:
        - Generic "vaccines" date → bulk update all essential annual vaccine
          masters for the species (puppy dose series excluded).
        - "vaccine_specifics" list → update only the named vaccine master(s).
          Processed AFTER the generic block so user-named dates can override
          (newer wins via _upsert_preventive_record).

    Other categories (deworming, flea_tick, blood_test) each have exactly
    one master per species, so they continue to use the single-match loop.
    """
    # --- Generic vaccine mention → update all essential annual vaccines ---
    generic = parsed.get("vaccines")
    if generic and generic != "none":
        gen_date = await _parse_preventive_date_value(generic, pet)
        if gen_date:
            masters = _essential_annual_vaccine_masters(db, pet.species)
            if not masters:
                logger.warning(
                    "No essential annual vaccine masters found for species=%s",
                    pet.species,
                )
            for master in masters:
                _upsert_preventive_record(db, pet, master, gen_date)

    # --- Specific vaccines → update only the named master(s) ---
    for spec in parsed.get("vaccine_specifics") or []:
        if not isinstance(spec, dict):
            continue
        master = _match_specific_vaccine_master(db, pet.species, spec.get("name", ""))
        if master is None:
            continue
        spec_date = await _parse_preventive_date_value(spec.get("date") or "", pet)
        if spec_date:
            _upsert_preventive_record(db, pet, master, spec_date)

    # --- Remaining categories: one master per species ---
    _ITEM_NAME_MAP = {
        "deworming": "Deworming",
        "flea_tick": "Tick/Flea",
        "blood_test": "Preventive Blood Test",
    }
    for key, item_pattern in _ITEM_NAME_MAP.items():
        value = parsed.get(key)
        if not value or value == "none":
            continue

        # Support both string dates and {"date": "...", "medicine": "..."} format.
        medicine_name = None
        if isinstance(value, dict):
            medicine_name = (value.get("medicine") or "").strip() or None
            value = value.get("date") or ""
            if not value or value == "none":
                continue

        parsed_date = await _parse_preventive_date_value(value, pet)
        if parsed_date is None:
            continue

        master = (
            db.query(PreventiveMaster)
            .filter(
                PreventiveMaster.item_name.ilike(item_pattern),
                PreventiveMaster.species.in_([pet.species, "both"]),
            )
            .first()
        )
        if not master:
            logger.warning(
                "No preventive master for pattern=%s species=%s",
                item_pattern, pet.species,
            )
            continue

        _upsert_preventive_record(db, pet, master, parsed_date, medicine_name=medicine_name)

    try:
        db.commit()
    except Exception as e:
        logger.error("Failed to store preventive records: %s", str(e))
        try:
            db.rollback()
        except Exception:
            pass


async def _transition_to_documents(db, user, pet, send_fn):
    """
    Shared transition: acknowledge preventive info, seed records, generate token,
    enter document upload window.
    """
    mobile = user._plaintext_mobile

    await send_fn(
        db, mobile,
        f"Got it, I'll organise this into {pet.name}'s care plan and remind you "
        f"at the right time for each one.",
    )

    # Seed preventive records for items not yet tracked.
    try:
        seed_preventive_records_for_pet(db, pet)
    except Exception as e:
        logger.error("Preventive seeding failed for pet %s: %s", str(pet.id), str(e), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    # Generate dashboard token.
    try:
        get_or_create_active_dashboard_token(db, pet.id)
    except Exception as e:
        logger.error("Dashboard token generation failed for pet %s: %s", str(pet.id), str(e), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    # Enter document upload window.
    user.onboarding_state = "awaiting_documents"
    user.doc_upload_deadline = datetime.now(UTC) + timedelta(seconds=DOC_UPLOAD_WINDOW_SECONDS)
    db.commit()

    await send_fn(
        db, mobile,
        f"Do you have any health records handy — a vaccination card, vet prescription, "
        f"or lab report? Share a photo or PDF and I'll pull the details in automatically. "
        f"No worries if not, we can always add them later.",
    )


async def _ai_clarify_input(
    user_message: str,
    step_context: str,
    expected_format: str,
    pet_name: str = "your pet",
) -> str:
    """
    Use GPT to generate a friendly clarifying question when user input
    doesn't match the expected format for the current onboarding step.

    Args:
        user_message: The user's original message that couldn't be parsed.
        step_context: Description of what information is being collected.
        expected_format: Examples of valid input for this step.
        pet_name: The pet's name for personalization.

    Returns:
        A friendly, concise clarifying question (AI-generated).
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "You are a friendly pet care assistant on WhatsApp helping a user register their pet. "
        f"The user's pet is named {pet_name}.\n\n"
        f"You are currently asking about: {step_context}\n"
        f"Expected input format/examples: {expected_format}\n"
        f"The user replied: \"{user_message}\"\n\n"
        "Their reply doesn't clearly match what's needed. "
        "Generate a short, warm, clarifying question (1-2 sentences max) that:\n"
        "- Acknowledges what they said without being dismissive\n"
        "- Gently asks for the specific information needed\n"
        "- Gives a concrete example if helpful\n"
        "- Uses a conversational WhatsApp tone (not formal)\n"
        "- Does NOT use emojis excessively (max 1)\n\n"
        "Return ONLY the clarifying message text, nothing else."
    )
    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )
        clarification = response.choices[0].message.content.strip()
        if clarification:
            return clarification
    except Exception as e:
        logger.warning("AI clarification failed: %s", str(e))

    # Fallback to a generic re-ask if AI fails.
    return f"I didn't quite catch that. Could you rephrase? {expected_format}"


_SAME_AS_EXAMPLE_PHRASES = frozenset({
    "same", "same as example", "same as above", "same thing",
    "same as that", "sampe", "sme", "like that", "like the example",
    "that one", "that", "this", "this one", "like above", "as above",
    "what you said", "what u said", "wahi", "wohi", "vahi",
    "same hi", "same only", "haan wahi", "haan same",
})


def _is_same_as_example_intent(text_lower: str) -> bool:
    """Return True if the user is referencing the example shown to them."""
    normalized = re.sub(r"[.!?,]+$", "", text_lower.strip())
    if normalized in _SAME_AS_EXAMPLE_PHRASES:
        return True
    # Partial match for "same as ..." patterns.
    if normalized.startswith("same") and len(normalized) < 30:
        return True
    return False


async def _ai_resolve_example_confirmation(
    user_reply: str,
    example_text: str,
    pet_name: str,
    context_type: str,
) -> str:
    """
    Interpret the user's reply to an example confirmation prompt.

    Returns:
        - The example_text as-is if user said plain yes.
        - A modified version if user said 'yes but...' with changes.
        - '__reject__' if user said no or gave completely unrelated input.
    """
    client = _get_openai_onboarding_client()
    context_labels = {
        "diet": "daily diet/meals",
        "preventive": "preventive care (vaccines, deworming, flea & tick, blood tests)",
    }
    prompt = (
        f"A pet parent was shown this example {context_labels.get(context_type, context_type)} "
        f"for their pet {pet_name}:\n"
        f"\"{example_text}\"\n\n"
        f"They were asked to confirm if this matches. They replied:\n"
        f"\"{user_reply}\"\n\n"
        "Determine their intent:\n"
        "1. If they confirmed (yes, yeah, haan, correct, etc.) with NO changes → "
        f"return the example exactly as-is\n"
        "2. If they confirmed WITH modifications (yes but no egg, yes and also curd, "
        "yes but deworming was 2 months ago not 3) → return the MODIFIED version "
        "reflecting their changes\n"
        "3. If they rejected (no, nope) or gave a completely different answer → "
        "return __reject__\n\n"
        'Return ONLY valid JSON: {"result": "the final text or __reject__"}'
    )
    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
        )
        raw = _strip_json_fences(response.choices[0].message.content.strip())
        data = json.loads(raw)
        return data.get("result", example_text)
    except Exception as e:
        logger.warning("AI example confirmation parse failed: %s", str(e))
        # On failure, accept common natural affirmations as confirmation.
        normalized_reply = re.sub(r"\s+", " ", user_reply.strip().lower())
        negative_markers = (
            "not ",
            "n't",
            "no ",
            "wrong",
            "different",
            "change",
        )
        extra_yes_phrases = (
            "looks good",
            "all good",
            "sounds good",
            "that's right",
            "thats right",
            "correct",
        )
        if normalized_reply in _NO_INPUTS or any(marker in normalized_reply for marker in negative_markers):
            return "__reject__"
        if normalized_reply in _YES_INPUTS or any(p in normalized_reply for p in extra_yes_phrases):
            return example_text
        return "__reject__"


async def _store_meal_items(db, pet, items: list, food_type: str):
    """Store parsed diet items for a pet."""
    for label, detail in items:
        item_type = food_type if food_type != "mix" else "packaged"
        label_lower = label.lower()
        if any(kw in label_lower for kw in HOMEMADE_KW):
            item_type = "homemade"
        elif food_type == "home":
            item_type = "homemade"
        try:
            await add_diet_item(db, pet.id, item_type, label, detail or None)
        except Exception as e:
            logger.error("Failed to save diet item for pet %s: %s", str(pet.id), str(e))


async def _ai_check_diet_relevance(text: str, pet_name: str) -> bool:
    """
    Use GPT to check if the user's message actually describes food/diet/meals.

    Returns True if the input describes diet items, False if it's ambiguous,
    irrelevant, or a vague reference like 'same', 'ok', 'yes'.
    """
    client = _get_openai_onboarding_client()
    prompt = (
        f"A pet parent was asked: 'What does {pet_name}'s typical daily diet look like?'\n"
        f"They replied: \"{text}\"\n\n"
        "Does this reply actually describe food, meals, or diet items? "
        "Answer YES if it mentions specific foods, brands, ingredients, or meal descriptions. "
        "Answer NO if it's vague ('same', 'ok', 'yes', 'like before'), irrelevant, "
        "gibberish, or doesn't describe actual food.\n\n"
        'Return ONLY valid JSON: {"is_diet": true|false}'
    )
    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        raw = _strip_json_fences(response.choices[0].message.content.strip())
        data = json.loads(raw)
        return bool(data.get("is_diet", True))
    except Exception as e:
        logger.warning("AI diet relevance check failed: %s", str(e))
        return True  # Default to accepting on failure.


async def _ai_parse_food_type(text: str, pet_name: str) -> str | None:
    """
    Use GPT to interpret ambiguous food-type input (e.g. 'same', 'like before',
    typos, shorthand) and map it to one of: home, packaged, mix.

    Returns 'home', 'packaged', 'mix', or None if the intent is unclear.
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "A pet parent is registering their pet on WhatsApp. "
        f"The pet's name is {pet_name}. "
        "They were asked: 'What does your pet usually eat — home food, packaged, or a mix?'\n\n"
        f"They replied: \"{text}\"\n\n"
        "Determine which food type they mean. Consider:\n"
        "- Typos and shorthand (e.g. 'hme' → home, 'pckgd' → packaged)\n"
        "- References like 'same', 'same as before', 'like I said' — these are UNCLEAR, return null\n"
        "- Descriptions that imply a type (e.g. 'I cook for him' → home, 'Royal Canin' → packaged)\n"
        "- If the intent is genuinely unclear or ambiguous, return null\n\n"
        'Return ONLY valid JSON: {"food_type": "home"|"packaged"|"mix"|null, '
        '"reasoning": "one line why"}'
    )
    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
        )
        raw = _strip_json_fences(response.choices[0].message.content.strip())
        data = json.loads(raw)
        result = data.get("food_type")
        if result in ("home", "packaged", "mix"):
            logger.info("AI parsed food type '%s' from input '%s': %s", result, text, data.get("reasoning", ""))
            return result
        return None
    except Exception as e:
        logger.warning("AI food type parse failed: %s", str(e))
        return None


async def _parse_diet_input(text: str) -> list[tuple[str, str]]:
    """
    Use GPT to extract structured diet items from free-text input.

    Returns list of (label, detail) tuples.
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "Extract food/supplement items from the user's message. "
        "Return a JSON object with an 'items' array. Each item has 'label' (short name, e.g. brand or food name) "
        "and 'detail' (quantity, frequency, or other details). "
        "If the message is vague, use the whole text as a single item label with empty detail. "
        "Return ONLY valid JSON, no markdown.\n\n"
        f"User message: {text}"
    )

    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        data = json.loads(raw)
        items = data.get("items", [])
        return [(item.get("label", text), item.get("detail", "")) for item in items if item.get("label")]
    except Exception as e:
        logger.warning("Diet GPT parse failed, using raw text: %s", str(e))
        return [(text.strip(), "")]


def _strip_json_fences(raw: str) -> str:
    """Strip markdown code fences from GPT JSON output."""
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    return raw


def _age_text_from_dob(dob: date) -> str:
    """Compute a human-readable age string from a date of birth."""
    today = date.today()
    years = today.year - dob.year
    months = today.month - dob.month
    if today.day < dob.day:
        months -= 1
    if months < 0:
        years -= 1
        months += 12
    if years <= 0 and months <= 0:
        days = (today - dob).days
        if days < 0:
            return "newborn"
        return f"{max(1, days // 7)} weeks" if days < 60 else "1 month"
    if years == 0:
        return f"{months} month{'s' if months != 1 else ''}"
    if months == 0:
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{years} year{'s' if years != 1 else ''} {months} month{'s' if months != 1 else ''}"


async def _parse_breed_age(text: str) -> dict:
    """
    Use GPT-4.1-mini to extract breed and approximate age from combined input.

    Returns dict with keys:
        breed (str|None), species ("dog"|"cat"|None),
        age_years (float|None), age_text (str|None),
        dob (str|None — ISO date if explicitly given), confident (bool)
    """
    client = _get_openai_onboarding_client()
    today_str = date.today().isoformat()
    prompt = (
        f"Today's date is {today_str}. "
        "Extract the pet breed and approximate age from this message. "
        "Also determine if this is a dog or cat breed. "
        'Return ONLY valid JSON, no markdown: '
        '{"breed": "...", "species": "dog"|"cat"|null, '
        '"age_years": number|null, "age_text": "original age text", '
        '"dob": "YYYY-MM-DD"|null, "confident": true|false}. '
        "If the breed is clearly identifiable, set confident=true. "
        "If the breed is ambiguous or unrecognizable, set confident=false. "
        "For age, accept years, months, or life stage words "
        '(puppy=0.5, kitten=0.5, junior=1.5, adult=4, senior=9). '
        "If the user provides a date of birth (like '11/11/2021', '11 Nov 21', etc.), "
        "convert it to ISO format (YYYY-MM-DD) in the 'dob' field AND compute age_years "
        "from today's date. Use the 2-digit year rule: 00-30 = 2000s, 31-99 = 1900s. "
        "If no age is given, set age_years, age_text, and dob to null.\n\n"
        f"User message: {text}"
    )
    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        raw = _strip_json_fences(response.choices[0].message.content.strip())
        data = json.loads(raw)
        return {
            "breed": data.get("breed"),
            "species": data.get("species"),
            "age_years": data.get("age_years"),
            "age_text": data.get("age_text"),
            "dob": data.get("dob"),
            "confident": data.get("confident", False),
        }
    except Exception as e:
        logger.warning("Breed/age GPT parse failed: %s", str(e))
        return {"breed": None, "species": None, "age_years": None, "age_text": None, "dob": None, "confident": False}


async def _parse_gender_weight_neutered(text: str) -> dict:
    """
    Use GPT-4.1-mini to extract gender, weight, and neutered status from combined input.

    Returns dict with keys:
        gender ("male"|"female"|None), weight_kg (float|None), neutered (bool|None)
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "Extract gender, weight in kg, and neutered/spayed status from this message about a pet. "
        'Return ONLY valid JSON, no markdown: '
        '{"gender": "male"|"female"|null, "weight_kg": number|null, "neutered": true|false|null}. '
        "Accept colloquial inputs: 'boy'='male', 'girl'/'she'='female', "
        "'spayed'/'fixed'/'yes'=neutered true, 'intact'/'no'=neutered false. "
        "If weight is given without units, assume kg.\n\n"
        f"User message: {text}"
    )
    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
        )
        raw = _strip_json_fences(response.choices[0].message.content.strip())
        data = json.loads(raw)
        return {
            "gender": data.get("gender"),
            "weight_kg": data.get("weight_kg"),
            "neutered": data.get("neutered"),
        }
    except Exception as e:
        logger.warning("Gender/weight GPT parse failed: %s", str(e))
        return {"gender": None, "weight_kg": None, "neutered": None}


async def _parse_preventive_care(text: str) -> dict:
    """
    Use GPT-4.1-mini to extract preventive care dates and medicine names from combined input.

    Returns dict with keys:
        vaccines (str|None)         — generic "vaccines done" date
        vaccine_specifics (list)    — [{"name": "rabies", "date": "Dec 2025"}, ...]
        deworming (dict|str|None)   — {"date": "...", "medicine": "..."} or date string
        flea_tick (dict|str|None)   — {"date": "...", "medicine": "..."} or date string
        blood_test (str|None)
        missing (list[str])         — which of the 4 categories were not mentioned
    """
    client = _get_openai_onboarding_client()
    today_str = date.today().isoformat()
    prompt = (
        f"Today's date is {today_str}. "
        "Extract preventive care information from this message about a pet. "
        "Look for four categories: vaccines, deworming, flea & tick treatment, and blood tests. "
        "For each, extract the approximate date or timeframe when it was last done. "
        "IMPORTANT: Convert ALL relative dates (e.g. 'last Dec', '2 months ago', 'Jan') "
        "to absolute dates in 'Month YYYY' or 'DD Month YYYY' format using today's date as reference. "
        "For example, if today is 2026-04-06 and user says 'last Dec', return 'December 2025'. "
        "If user says '3 months ago', return 'January 2026'. Never return relative phrases.\n\n"
        "VACCINE RULES:\n"
        "- If the user names a specific vaccine (rabies, DHPPi, 7-in-1, 9-in-1, "
        "kennel cough, bordetella, feline core, FVRCP, FeLV, FIV, leptospirosis, "
        "coronavirus, core vaccine), put each one as an entry in 'vaccine_specifics' "
        "with its date. In that case 'vaccines' must stay null.\n"
        "- If the user only says generic 'vaccines' / 'shots' / 'jabs' / 'vaccinated' "
        "without naming any specific vaccine, set 'vaccines' to the date and leave "
        "'vaccine_specifics' as an empty list.\n"
        "- Specific names go in 'vaccine_specifics' even when only one is mentioned.\n\n"
        "MEDICINE NAME RULES:\n"
        "- For deworming and flea & tick, if the user mentions a specific medicine or "
        "brand name (e.g. Simparica, NexGard, Bravecto, Frontline, Milbemax, Drontal, "
        "Panacur, Advocate, Revolution, Credelio, Seresto, Advantix, Prazitel, Verminator, "
        "Fipronil, Ivermectin, Fenbendazole, Pyrantel, Albendazole), "
        "extract it as the 'medicine' field.\n"
        "- Return deworming and flea_tick as objects with 'date' and 'medicine' keys.\n\n"
        'Return ONLY valid JSON, no markdown: '
        '{"vaccines": "date or timeframe"|null, '
        '"vaccine_specifics": [{"name": "vaccine name", "date": "date or timeframe"}], '
        '"deworming": {"date": "date or timeframe", "medicine": "brand name"|null}|null, '
        '"flea_tick": {"date": "date or timeframe", "medicine": "brand name"|null}|null, '
        '"blood_test": "date or timeframe"|null, '
        '"missing": ["category names not mentioned"]}. '
        "If the user explicitly says 'none' or 'not done' for a category, "
        'set it to "none" (not null). '
        "Null means not mentioned at all. "
        "'missing' should list category names that were not mentioned.\n\n"
        f"User message: {text}"
    )
    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        raw = _strip_json_fences(response.choices[0].message.content.strip())
        data = json.loads(raw)
        # Defensive parse: vaccine_specifics must be a list of dicts with name+date.
        raw_specifics = data.get("vaccine_specifics") or []
        if not isinstance(raw_specifics, list):
            raw_specifics = []
        clean_specifics = [
            s for s in raw_specifics
            if isinstance(s, dict) and s.get("name") and s.get("date")
        ]
        return {
            "vaccines": data.get("vaccines"),
            "vaccine_specifics": clean_specifics,
            "deworming": data.get("deworming"),
            "flea_tick": data.get("flea_tick"),
            "blood_test": data.get("blood_test"),
            "missing": data.get("missing", []),
        }
    except Exception as e:
        logger.warning("Preventive care GPT parse failed: %s", str(e))
        return {
            "vaccines": None,
            "vaccine_specifics": [],
            "deworming": None,
            "flea_tick": None,
            "blood_test": None,
            "missing": [],
        }


def _compute_life_stage(age_years: float | None) -> tuple[str, str] | None:
    """
    Compute life stage and warm one-liner from age in years.

    Returns (stage_name, one_liner) or None if age is unknown.
    """
    if age_years is None:
        return None

    if age_years < 1:
        return ("Puppy", "still finding their feet and learning fast!")
    elif age_years < 2:
        return ("Junior", "growing into themselves — curious, energetic, and full of surprises!")
    elif age_years < 7:
        return ("Adult", "right in their prime and full of energy!")
    else:
        return ("Senior", "been around long enough to know exactly how to wrap you around their paw. 🐾")


def _infer_species_from_breed(breed_key: str) -> str | None:
    """
    Infer species from a breed name using the breed_normalizer dictionaries.

    Args:
        breed_key: Lowercased, stripped breed name.

    Returns:
        "dog", "cat", or None if breed is not in either dictionary.
    """
    from app.utils.breed_normalizer import _DOG_BREEDS, _CAT_BREEDS
    import re as _re
    key = _re.sub(r"[^a-z\s]", "", breed_key.lower().strip()).strip()
    if key in _DOG_BREEDS:
        return "dog"
    if key in _CAT_BREEDS:
        return "cat"
    return None


async def _parse_grooming_input(text: str) -> list[tuple[str, int, str]]:
    """
    Use GPT to extract grooming items from free-text input.

    Returns list of (name, freq, unit) tuples for periodic grooming items.
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "Extract grooming activities from the user's message about their pet. "
        "Return a JSON object with an 'items' array. Each item has: "
        "'name' (activity name, e.g. 'Haircut', 'Bath', 'Nail Trim', 'Ear Cleaning'), "
        "'freq' (integer frequency, default 1), "
        "'unit' (one of 'day', 'week', 'month', 'year', default 'month'). "
        "If the user mentions 'every 2 weeks', use freq=2, unit='week'. "
        "If no frequency is given, use reasonable defaults: bath=2 weeks, haircut=2 months, "
        "nail trim=1 month, ear cleaning=2 weeks. "
        "Return ONLY valid JSON, no markdown.\n\n"
        f"User message: {text}"
    )

    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        data = json.loads(raw)
        items = data.get("items", [])
        result = []
        for item in items:
            name = item.get("name", "").strip()
            if not name:
                continue
            freq = int(item.get("freq", 1))
            unit = item.get("unit", "month")
            if unit not in ("day", "week", "month", "year"):
                unit = "month"
            result.append((name, max(1, freq), unit))
        return result
    except Exception as e:
        logger.warning("Grooming GPT parse failed, using raw text: %s", str(e))
        return [(text.strip(), 1, "month")]


async def _generate_doc_upload_reply(
    pet_name: str, user_message: str, docs_uploaded: int, remaining: int,
) -> str:
    """Generate a natural GPT reply for text messages during the document upload window."""
    client = _get_openai_onboarding_client()
    prompt = (
        "You are a friendly pet care assistant helping a user upload health records "
        f"for their pet {pet_name} during onboarding.\n\n"
        f"FACTS (use these EXACT numbers — do NOT invent or change them):\n"
        f"- Files already uploaded: {docs_uploaded}\n"
        f"- Files they can still upload: {remaining}\n"
        f"- Accepted formats: JPEG, PNG, PDF\n\n"
        f"The user said: \"{user_message}\"\n\n"
        "Reply in 1-2 short, warm sentences. Address what they said naturally. "
        f"If they're asking whether they can add more, tell them they can send {remaining} more. "
        "If remaining is 0, let them know they've hit the upload limit. "
        "Do NOT mention 'skip', 'skipping', or any way to exit/continue the upload step. "
        "Do NOT use markdown headings. Use *bold* sparingly for key info only."
    )
    try:
        response = await retry_openai_call(
            client.chat.completions.create,
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("Doc upload reply GPT failed, using fallback: %s", str(e))
        if remaining > 0:
            return (
                f"You can still upload *{remaining} more* file(s) for {pet_name} "
                f"(JPEG, PNG, or PDF)."
            )
        return f"You've uploaded all {docs_uploaded} files for {pet_name}."


_ADD_MORE_KEYWORDS: tuple[str, ...] = (
    "more", "add", "another", "one more", "also", "wait",
    "hold on", "hold", "can i", "let me", "send more", "upload more",
    "additional", "extra",
)


def _is_add_more_intent(text_lower: str) -> bool:
    """Detect whether the user is asking to upload additional documents."""
    if not text_lower:
        return False
    return any(kw in text_lower for kw in _ADD_MORE_KEYWORDS)


async def _step_awaiting_documents(db, user, text_lower, send_fn):
    """
    Handle messages during the post-onboarding document upload window.

    Accepts "skip" to exit immediately. If the deadline has passed,
    auto-transitions to complete. Otherwise prompts for uploads.

    If the user asks to add more documents (detected via keywords), the
    upload window is marked as "extended" so batch extraction will NOT
    auto-finalize onboarding — the user stays in the upload window until
    they explicitly skip or the deadline expires.
    """
    mobile = user._plaintext_mobile

    # Check if deadline has expired.
    if user.doc_upload_deadline and datetime.now(UTC) > user.doc_upload_deadline:
        try:
            from app.services.message_router import clear_upload_window_extended
            clear_upload_window_extended(user.id)
        except Exception:
            pass
        await _finalize_onboarding(db, user, send_fn)
        return

    # "skip" exits the upload window immediately.
    if _is_doc_skip_intent(text_lower):
        try:
            from app.services.message_router import clear_upload_window_extended
            clear_upload_window_extended(user.id)
        except Exception:
            pass
        await _finalize_onboarding(db, user, send_fn)
        return

    # If the user is asking for the dashboard/link before the care plan is
    # ready, tell them it's being built instead of sending a generic upload
    # reply. Avoids the confusion of "I asked for the dashboard and got a
    # prompt to upload more documents."
    _DASHBOARD_KEYWORDS = ("dashboard", "link", "care plan", "my plan")
    if any(kw in text_lower for kw in _DASHBOARD_KEYWORDS):
        pet_for_msg = (
            db.query(Pet)
            .filter(Pet.user_id == user.id)
            .order_by(Pet.created_at.desc())
            .first()
        )
        pet_name = pet_for_msg.name if pet_for_msg else "your pet"
        await send_fn(
            db, mobile,
            f"{pet_name}'s care plan is still being built 🐾 "
            f"You'll receive the dashboard link as soon as it's ready. "
            f"Reply *skip* if you don't want to upload any documents.",
        )
        return

    # Count uploads using BOTH the DB and the in-memory batch tracker.
    # The in-memory count avoids a race where a text message arrives before
    # the async upload pipeline has committed the Document rows.
    pet = db.query(Pet).filter(Pet.user_id == user.id).order_by(Pet.created_at.desc()).first()
    pet_name = pet.name if pet else "your pet"
    db_count = 0
    in_memory_count = 0
    if pet:
        db_count = db.query(Document).filter(Document.pet_id == pet.id).count()
        try:
            from app.services.message_router import get_recent_upload_count
            in_memory_count = get_recent_upload_count(pet.id)
        except Exception:
            in_memory_count = 0
    docs_uploaded = max(db_count, in_memory_count)
    remaining = max(0, MAX_PENDING_DOCS_PER_PET - docs_uploaded)

    # If the user is asking to add more, mark the window as extended so the
    # batch extractor won't finalize onboarding behind their back.
    if _is_add_more_intent(text_lower):
        try:
            from app.services.message_router import mark_upload_window_extended
            mark_upload_window_extended(user.id)
        except Exception as e:
            logger.warning("Failed to mark upload window extended: %s", str(e))

    reply = await _generate_doc_upload_reply(pet_name, text_lower, docs_uploaded, remaining)
    await send_fn(db, mobile, reply)


def _get_active_reminders_text(db: Session, pet_id) -> str:
    """
    Fetch active reminders for a pet and format them for WhatsApp message.

    Returns formatted text with reminders or empty string if none exist.
    Active reminders are those with status 'pending' or 'sent'.
    """
    try:
        reminders = (
            db.query(Reminder, PreventiveRecord, PreventiveMaster)
            .join(PreventiveRecord, Reminder.preventive_record_id == PreventiveRecord.id)
            .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
            .filter(
                PreventiveRecord.pet_id == pet_id,
                Reminder.status.in_(["pending", "sent"]),
            )
            .order_by(Reminder.next_due_date.asc())
            .all()
        )

        if not reminders:
            return ""

        # Format reminders for display
        reminder_lines = []
        for reminder, record, master in reminders:
            due_date_str = reminder.next_due_date.strftime("%d/%m/%Y")
            reminder_lines.append(f"• {master.item_name}: Due {due_date_str}")

        result = "Active Reminders:\n" + "\n".join(reminder_lines) + "\n\n"
        return result
    except Exception as e:
        logger.error("Failed to fetch active reminders for pet %s: %s", str(pet_id), str(e))
        return ""


async def _finalize_onboarding(db, user, send_fn):
    """
    Finalize onboarding: mark complete, clear deadline, send GPT-generated
    "care plan ready" message with hardcoded fallback templates.

    Record seeding and token generation already happened in _transition_to_documents().
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)

    if pet:
        _recover_transition_failures(db, pet)

    # --- Mark onboarding complete and clear deadline ---
    # Guard with a conditional UPDATE so only one concurrent caller can
    # transition awaiting_documents -> complete and send final messages.
    try:
        from datetime import datetime as _dt

        rows_updated = (
            db.query(User)
            .filter(
                User.id == user.id,
                User.onboarding_state == "awaiting_documents",
            )
            .update(
                {
                    User.onboarding_state: "complete",
                    User.doc_upload_deadline: None,
                    User.onboarding_data: None,
                    User.onboarding_completed_at: _dt.utcnow(),
                },
                synchronize_session=False,
            )
        )

        if rows_updated == 0:
            try:
                db.rollback()
            except Exception:
                pass
            return

        user.onboarding_state = "complete"
        user.doc_upload_deadline = None
        user.onboarding_data = None
        if not user.onboarding_completed_at:
            user.onboarding_completed_at = _dt.utcnow()
        db.commit()
    except Exception as e:
        logger.error("Failed to mark onboarding complete: %s", str(e), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        try:
            await send_fn(
                db, mobile,
                f"{pet.name if pet else 'Your pet'}'s profile was created but we hit a temporary issue. "
                f"Please send *hi* to retry.",
            )
        except Exception:
            pass
        return

    if not pet:
        logger.error("No pet found during finalize for user %s", str(user.id))
        await send_fn(db, mobile, "All set! Type *add pet* to register your pet.")
        return

    logger.info(
        "Onboarding complete: user_id=%s, pet=%s (%s)",
        str(user.id), pet.name, pet.species,
    )

    # --- Gather data completeness flags ---
    from app.models.diet_item import DietItem

    docs_uploaded = db.query(Document).filter(Document.pet_id == pet.id).count()
    # Always resolve token through active-token helper so expired historical
    # tokens are never sent in the final onboarding dashboard link.
    token = _recover_dashboard_token_for_finalize(db, pet.id)
    # Count preventive records with an actual date logged across health
    # and hygiene circles (hygiene includes Tick/Flea which is clinically
    # a health item). Nutrition items are excluded. The last_done_date
    # filter ensures seeded placeholder rows are not counted.
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
    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet.id, Condition.is_active == True)
        .order_by(Condition.created_at.asc())
        .all()
    )
    diet_count = db.query(DietItem).filter(DietItem.pet_id == pet.id).count()
    supplement_count = db.query(DietItem).filter(
        DietItem.pet_id == pet.id, DietItem.type == "supplement"
    ).count()

    # Check for pending document extractions.
    pending_extractions = 0
    if docs_uploaded > 0:
        pending_extractions = (
            db.query(Document)
            .filter(Document.pet_id == pet.id, Document.extraction_status == "pending")
            .count()
        )

    # --- If extractions are still in-flight, defer the dashboard link ---
    if docs_uploaded > 0 and pending_extractions > 0:
        _persist_deferred_marker_with_fallback(db, user, pet)

        await send_fn(
            db, mobile,
            f"That's everything. 🐾 Building {pet.name}'s personalised care plan now "
            f"— their health dashboard, care reminders, and nutrition breakdown "
            f"will be ready in just a moment.",
        )
        return

    # --- Generate the "care plan ready" message ---
    # Transition message first.
    await send_fn(
        db, mobile,
        f"That's everything. 🐾 Building {pet.name}'s personalised care plan now "
        f"— their health dashboard, care reminders, and nutrition breakdown "
        f"will be ready in just a moment.",
    )

    # Fetch diet items for AI supplement recommendation.
    diet_items = db.query(DietItem).filter(DietItem.pet_id == pet.id).all()

    # Try GPT-generated message, fall back to templates.
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

    # Append dashboard link.
    if token:
        care_plan_msg += (
            f"\n\nView {pet.name}'s full care plan here 👇\n"
            f"{settings.FRONTEND_URL}/dashboard/{token}"
        )
    else:
        care_plan_msg += (
            f"\n\nSend *dashboard* anytime to get {pet.name}'s care plan link."
        )

    await send_fn(db, mobile, care_plan_msg)


async def _ai_supplement_recommendation(
    pet,
    diet_items: list | None,
    conditions: list | None,
) -> str | None:
    """
    Generate a personalised supplement recommendation via gpt-4.1-mini.

    Returns a single conversational sentence (no bullet points, no headers)
    or None on failure so the caller can use a deterministic fallback.
    """
    try:
        from app.core.constants import OPENAI_QUERY_MODEL
        client = _get_openai_onboarding_client()

        # Build compact context from available data.
        name = pet.name
        species = (pet.species or "dog").lower()
        breed = pet.breed or "unknown breed"
        age = pet.age_text or (str(pet.dob) if pet.dob else "unknown age")
        gender = getattr(pet, "gender", None) or "unknown"
        weight = getattr(pet, "weight_kg", None)
        weight_line = f"{weight} kg" if weight else "unknown"

        split_items = split_diet_items_by_type(diet_items or [])
        food_labels = split_items["foods"] + split_items["other"]
        existing_supplements = split_items["supplements"]
        food_summary = ", ".join(food_labels) if food_labels else "not provided"
        supplements_summary = ", ".join(existing_supplements) if existing_supplements else "none"

        active_conditions = [c for c in (conditions or []) if getattr(c, "name", None)]
        condition_names = ", ".join(c.name for c in active_conditions) if active_conditions else "none"

        already_taking_clause = ""
        if existing_supplements:
            already_taking_clause = (
                f"IMPORTANT: The pet is ALREADY taking these supplements: {supplements_summary}. "
                f"Do NOT recommend any supplement the pet is already taking. "
                f"Only recommend supplements they are NOT currently on. "
            )

        prompt = (
            f"Pet profile:\n"
            f"Name: {name}\n"
            f"Species: {species}\n"
            f"Breed: {breed}\n"
            f"Age: {age}\n"
            f"Gender: {gender}\n"
            f"Weight: {weight_line}\n"
            f"Current diet/food: {food_summary}\n"
            f"Current supplements: {supplements_summary}\n"
            f"Health conditions: {condition_names}\n\n"
            f"{already_taking_clause}"
            f"Write ONE short, warm WhatsApp message sentence (max 25 words) "
            f"recommending 1-2 specific supplements for this pet based on their "
            f"profile. Be specific to their breed, age, and diet. "
            f"No bullet points. No headers. No asterisks. No markdown. "
            f"Start with 'We'd suggest' or 'Based on [name]'s profile, we'd recommend'."
        )

        async def _call() -> str:
            response = await client.chat.completions.create(
                model=OPENAI_QUERY_MODEL,
                temperature=0.4,
                max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.choices[0].message.content or "").strip()

        result = await retry_openai_call(_call)
        return result or None
    except Exception as e:
        logger.warning("AI supplement recommendation failed: %s", str(e))
        return None


async def _generate_care_plan_message(
    pet, diet_count: int, supplement_count: int,
    record_count: int, docs_uploaded: int,
    conditions: list[Condition] | None = None,
    diet_items: list | None = None,
    db: Session | None = None,
) -> str:
    """
    Generate the "care plan ready" message.

    Supplement recommendation is derived from the same diet-summary
    micronutrient gaps used by the dashboard quick fixes. Falls back to
    AI generation, then deterministic rules if needed.

    Follows flow.txt prompt rules:
    - Open with "[pet name]'s care plan is ready! 🐾"
    - Reference only the information that was shared
    - Always make supplement recommendations based on available data
    - For anything not shared, add a one-line nudge
    - No health judgements, no headers, no bullet points
    - Warm, conversational, WhatsApp-friendly tone
    """
    # Build flags for deterministic variation selection.
    split_items = split_diet_items_by_type(diet_items or [])
    has_food = bool(split_items["foods"])
    has_preventive = record_count > 0
    has_breed = bool(pet.breed)
    has_age = bool(pet.age_text or pet.dob)
    active_conditions = [c for c in (conditions or []) if getattr(c, "name", None)]
    has_conditions = len(active_conditions) > 0
    condition_names = ", ".join(c.name for c in active_conditions[:3])
    condition_count = len(active_conditions)
    name = pet.name

    # Build condition summary line.
    if has_conditions:
        condition_line = (
            f"We noted {condition_count} health condition{'s' if condition_count != 1 else ''}"
            f" — {condition_names}. We've included some questions worth raising with your vet."
        )
    else:
        condition_line = "No active health conditions flagged."

    # Keep chat supplement recommendations aligned with dashboard quick fixes
    # by deriving from the same missing_micros payload first.
    supplement_rec = None
    if has_food and db is not None:
        try:
            diet_summary = await get_diet_summary(db, pet)
        except Exception as e:
            logger.warning("Diet summary lookup failed for care-plan message: %s", str(e))
            diet_summary = {"missing_micros": []}

        missing_micros = (diet_summary or {}).get("missing_micros") or []
        existing_supp_labels = {
            label.lower() for label in split_items["supplements"] if label
        }

        micro_aliases = {
            "omega-3": ("omega", "fish oil", "omega 3", "salmon oil"),
            "probiotics": ("probiotic", "gut", "lactobacillus", "fortiflora"),
            "glucosamine": ("glucosamine", "chondroitin", "joint"),
            "vitamin d3": ("vitamin d3", "d3", "calcitriol"),
            "vitamin e": ("vitamin e", "tocopherol"),
        }

        def _already_covered_by_existing_supplements(micro_name: str) -> bool:
            aliases = micro_aliases.get(micro_name.lower(), (micro_name.lower(),))
            return any(
                any(alias in existing for alias in aliases)
                for existing in existing_supp_labels
            )

        top_names = [
            str(m.get("name", "")).strip()
            for m in missing_micros
            if m.get("name") and not _already_covered_by_existing_supplements(str(m.get("name", "")).strip())
        ][:2]
        if top_names:
            if len(top_names) == 1:
                supplement_rec = (
                    f"We'd suggest adding {top_names[0]} supplement based on {name}'s current diet analysis."
                )
            else:
                supplement_rec = (
                    f"We'd suggest adding {top_names[0]} and {top_names[1]} supplements based on {name}'s current diet analysis."
                )
        elif missing_micros and existing_supp_labels:
            supplement_rec = (
                f"{name} is already on a strong supplement routine, so we don't suggest "
                f"adding anything new right now."
            )

    # If dashboard-driven gaps are unavailable, fall back to AI then deterministic rules.
    if not supplement_rec:
        supplement_rec = await _ai_supplement_recommendation(pet, diet_items, conditions)
    if not supplement_rec:
        # Check which supplements the user is already giving to avoid
        # recommending something they already take.
        existing_supp_labels = {
            label.lower() for label in split_items["supplements"] if label
        }

        fallback_candidates = [
            ("Omega-3", ("omega", "fish oil", "omega 3")),
            ("a probiotic", ("probiotic", "gut", "lactobacillus")),
            ("calcium", ("calcium",)),
            ("a joint supplement", ("glucosamine", "chondroitin", "joint")),
        ]

        missing_candidates: list[str] = []
        for display_name, aliases in fallback_candidates:
            if any(any(alias in existing for alias in aliases) for existing in existing_supp_labels):
                continue
            missing_candidates.append(display_name)

        if not missing_candidates:
            supplement_rec = (
                f"{name} is already on a strong supplement routine, so we don't suggest "
                f"adding anything new right now."
            )
        elif len(missing_candidates) == 1:
            fallback_supp = missing_candidates[0]
            if has_food:
                supplement_rec = (
                    f"We'd suggest adding {fallback_supp} based on {name}'s "
                    f"diet and life stage."
                )
            else:
                supplement_rec = (
                    f"We'd suggest adding {fallback_supp} based on {name}'s "
                    f"age and breed for coat health, joint support, and overall immunity."
                )
        else:
            fallback_supp = f"{missing_candidates[0]} and {missing_candidates[1]}"
            if has_food:
                supplement_rec = (
                    f"We'd suggest adding {fallback_supp} based on {name}'s "
                    f"diet and life stage."
                )
            else:
                supplement_rec = (
                    f"We'd suggest adding {fallback_supp} based on {name}'s "
                    f"age and breed for coat health, joint support, and overall immunity."
                )

    if has_conditions and has_food and has_preventive:
        # Variation 1: Conditions + food + preventive shared.
        return (
            f"{name}'s care plan is ready! 🐾 Based on {name}'s health analysis, life stage and current diet.\n\n"
            f"{condition_line}\n\n"
            f"We've logged {record_count} preventive care item{'s' if record_count != 1 else ''} for {name}.\n\n"
            f"{supplement_rec}"
        )
    elif has_food and has_preventive:
        # Variation 2: No conditions, food and preventive shared.
        return (
            f"{name}'s care plan is ready! 🐾 Based on {name}'s health analysis, "
            f"life stage and current diet.\n\n"
            f"{condition_line}\n\n"
            f"We've logged {record_count} preventive care item{'s' if record_count != 1 else ''} for {name}.\n\n"
            f"{supplement_rec}"
        )
    elif has_food and not has_preventive:
        # Variation 3: Food shared, preventive not shared.
        return (
            f"{name}'s care plan is ready! 🐾\n\n"
            f"{condition_line}\n\n"
            f"We don't have {name}'s preventive care details yet — adding these "
            f"would give us a more complete health picture.\n\n"
            f"{supplement_rec}"
        )
    elif has_breed and has_age:
        # Variation 4: No food, no preventive, but age and breed available.
        return (
            f"{name}'s care plan is ready! 🐾\n\n"
            f"{condition_line}\n\n"
            f"{supplement_rec}\n\n"
            f"To make this analysis even more personalised, sharing {name}'s current "
            f"diet and preventive care routine would give us a much fuller picture."
        )
    elif not has_food and not has_preventive:
        # Variation 5: Minimal data — no supplement rec since we have too little context.
        return (
            f"{name}'s care plan is ready! 🐾\n\n"
            f"{condition_line}\n\n"
            f"To give you a fuller picture, we'd love to know more about {name}'s "
            f"current diet and preventive care routine — adding these would help us "
            f"make the analysis much more personalised for {name}."
        )
    else:
        # Generic fallback.
        return (
            f"{name}'s care plan is ready! 🐾\n\n"
            f"We've set up {name}'s health profile based on the information shared. "
            f"The more details you add over time — diet, preventive care, health records "
            f"— the more personalised the care plan becomes."
        )


async def _ai_check_weight(
    species: str | None,
    breed: str | None,
    dob,
    weight_kg: float,
) -> dict | None:
    """Check weight reasonableness via AI. Return None when AI is unavailable."""
    species_norm = (species or "").strip().lower() or "unknown"
    breed_norm = (breed or "").strip() or None

    age_months = None
    age_years = None
    if dob:
        today = datetime.utcnow().date()
        age_months = max(0, (today.year - dob.year) * 12 + (today.month - dob.month))
        age_years = round(age_months / 12, 2)

    if not getattr(settings, "OPENAI_API_KEY", None):
        return None

    try:
        client = _get_openai_onboarding_client()

        prompt = (
            "You are validating pet weights during pet onboarding. "
            "Use species, breed (if known), age, and entered weight to decide reasonableness. "
            "Respond with strict JSON and no markdown using this schema exactly: "
            '{"reasonable": true/false, "expected_range": "X-Y kg", "reason": "..."}.\n'
            f"species={species_norm}\n"
            f"breed={breed_norm or 'unknown'}\n"
            f"age_months={age_months if age_months is not None else 'unknown'}\n"
            f"age_years={age_years if age_years is not None else 'unknown'}\n"
            f"entered_weight_kg={weight_kg}\n"
            "If uncertain, prefer conservative veterinary ranges and explain briefly."
        )

        responses_api = getattr(client, "responses", None)
        if responses_api and hasattr(responses_api, "create"):
            async def _make_call():
                return await responses_api.create(
                    model="gpt-4.1-mini",
                    input=prompt,
                    temperature=0,
                    max_output_tokens=140,
                )

            response = await retry_openai_call(_make_call)
            raw = (getattr(response, "output_text", "") or "").strip()
        else:
            async def _make_call_chat():
                return await client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You validate pet weights and return strict JSON only."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0,
                    max_tokens=140,
                )

            response = await retry_openai_call(_make_call_chat)
            raw = (
                response.choices[0].message.content
                if response and getattr(response, "choices", None)
                else ""
            )
            raw = (raw or "").strip()

        data = json.loads(raw)

        reasonable = bool(data.get("reasonable", True))
        ai_expected = str(data.get("expected_range") or "unknown")
        reason = str(data.get("reason") or "AI-derived check").strip()

        return {
            "reasonable": reasonable,
            "expected_range": ai_expected,
            "reason": reason,
        }
    except Exception as e:
        logger.warning("Weight AI check failed; accepting weight without flagging: %s", str(e))
        return None


async def _ai_identify_pet_from_photo(file_bytes: bytes, mime_type: str) -> dict[str, str | None]:
    """
    Identify species and likely breed from the uploaded pet photo.

    Returns:
        Dict with keys:
            - species: "dog", "cat", or None
            - breed: normalized breed string or None
    """
    if not getattr(settings, "OPENAI_API_KEY", None):
        return {"species": None, "breed": None}

    if mime_type not in {"image/jpeg", "image/png"}:
        return {"species": None, "breed": None}

    client = _get_openai_onboarding_client()
    data_uri = encode_image_base64(file_bytes, mime_type)

    prompt = (
        "Identify the main pet in this photo. "
        "Return strict JSON only with this exact schema: "
        '{"species":"dog|cat|unknown","breed":"string|null"}. '
        "If the image is unclear or not a dog/cat, return species unknown and breed null."
    )

    async def _make_call() -> str:
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0,
            max_tokens=80,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You classify pet photos and return strict JSON only.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri, "detail": "high"}},
                    ],
                },
            ],
        )
        return response.choices[0].message.content

    raw = await retry_openai_call(_make_call)
    try:
        parsed = json.loads((raw or "").strip())
    except json.JSONDecodeError:
        return {"species": None, "breed": None}

    species = str(parsed.get("species") or "").strip().lower()
    if species not in {"dog", "cat"}:
        species = None

    raw_breed = parsed.get("breed")
    breed = None
    if isinstance(raw_breed, str):
        candidate = raw_breed.strip()
        if candidate and candidate.lower() not in {"unknown", "none", "null", "n/a", "na"}:
            breed = candidate.title()

    return {"species": species, "breed": breed}


async def _ai_identify_species_from_photo(file_bytes: bytes, mime_type: str) -> str | None:
    """Backward-compatible wrapper returning only species."""
    result = await _ai_identify_pet_from_photo(file_bytes, mime_type)
    return result.get("species")

def _get_pending_pet(db: Session, user_id: UUID) -> Pet | None:
    """Get the most recently created pet for a user (the one being onboarded)."""
    return (
        db.query(Pet)
        .filter(Pet.user_id == user_id, Pet.is_deleted == False)
        .order_by(Pet.created_at.desc())
        .first()
    )


def generate_dashboard_token(db: Session, pet_id: UUID) -> str:
    """
    Generate a secure random dashboard token for a pet.

    Token is 128-bit (16 bytes), rendered as a 32-char hex string.
    Expires after DASHBOARD_TOKEN_EXPIRY_DAYS (30 days by default).

    Args:
        db: SQLAlchemy database session.
        pet_id: UUID of the pet.

    Returns:
        The generated hex token string.
    """
    token = secrets.token_hex(DASHBOARD_TOKEN_BYTES)

    dashboard_token = DashboardToken(
        pet_id=pet_id,
        token=token,
        revoked=False,
        expires_at=datetime.now(UTC) + timedelta(days=DASHBOARD_TOKEN_EXPIRY_DAYS),
    )
    db.add(dashboard_token)
    db.commit()

    logger.info("Dashboard token generated for pet_id=%s", str(pet_id))
    return token


def get_or_create_active_dashboard_token(db: Session, pet_id: UUID) -> str:
    """Return latest active token for a pet, creating one only when needed."""
    now_utc = datetime.now(UTC)
    token_row = (
        db.query(DashboardToken)
        .filter(
            DashboardToken.pet_id == pet_id,
            DashboardToken.revoked == False,
            DashboardToken.expires_at.isnot(None),
            DashboardToken.expires_at > now_utc,
        )
        .order_by(DashboardToken.created_at.desc())
        .first()
    )
    if token_row:
        return token_row.token
    return generate_dashboard_token(db, pet_id)


def _recover_dashboard_token_for_finalize(db: Session, pet_id: UUID) -> str | None:
    """Best-effort token recovery before sending final onboarding links."""
    try:
        return get_or_create_active_dashboard_token(db, pet_id)
    except Exception as e:
        logger.warning(
            "Could not recover dashboard token during finalization for pet %s: %s",
            str(pet_id),
            str(e),
        )
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _mark_deferred_care_plan_pending(db: Session, user_id: UUID, pet_id: UUID) -> None:
    """Create or refresh an active per-pet deferred finalization marker."""
    marker = (
        db.query(DeferredCarePlanPending)
        .filter(
            DeferredCarePlanPending.pet_id == pet_id,
            DeferredCarePlanPending.is_cleared == False,
        )
        .first()
    )
    if marker:
        marker.user_id = user_id
        marker.reason = "pending_extractions"
        marker.cleared_at = None
        return

    db.add(
        DeferredCarePlanPending(
            user_id=user_id,
            pet_id=pet_id,
            reason="pending_extractions",
            is_cleared=False,
            cleared_at=None,
        )
    )


def _persist_deferred_marker_with_fallback(db: Session, user: User, pet: Pet) -> None:
    """Persist per-pet deferred marker with legacy user-flag fallback on failure."""
    try:
        _mark_deferred_care_plan_pending(db, user.id, pet.id)
        db.commit()
        return
    except Exception as e:
        logger.warning("Could not persist deferred care-plan marker: %s", str(e))
        try:
            db.rollback()
        except Exception:
            pass

    # Keep backward-compatible durability if per-pet marker persistence fails.
    if hasattr(user, "dashboard_link_pending"):
        try:
            user.dashboard_link_pending = True
            db.commit()
            logger.warning(
                "Fell back to legacy dashboard_link_pending for user %s pet %s",
                str(user.id),
                str(pet.id),
            )
        except Exception as e:
            logger.error(
                "Legacy deferred fallback persistence failed for user %s pet %s: %s",
                str(user.id),
                str(pet.id),
                str(e),
            )
            try:
                db.rollback()
            except Exception:
                pass


def _recover_transition_failures(db: Session, pet: Pet) -> None:
    """Best-effort recovery for setup failures from transition-to-documents."""
    try:
        if pet.species in ("dog", "cat"):
            # Always run idempotent missing-only seeding so partial failures
            # from transition-to-documents are healed at finalization time.
            seed_preventive_records_for_pet(db, pet)
    except Exception as e:
        logger.warning("Preventive recovery failed for pet %s: %s", str(pet.id), str(e))
        try:
            db.rollback()
        except Exception:
            pass

    _recover_dashboard_token_for_finalize(db, pet.id)


def refresh_dashboard_token(db: Session, pet_id: UUID) -> str:
    """
    Revoke the existing token and generate a new one with fresh expiry.

    Used when a user's token has expired or been revoked and they
    request a new dashboard link via WhatsApp.

    Args:
        db: SQLAlchemy database session.
        pet_id: UUID of the pet.

    Returns:
        The newly generated hex token string.
    """
    # Batch-revoke all existing active tokens for this pet.
    revoked_count = (
        db.query(DashboardToken)
        .filter(DashboardToken.pet_id == pet_id, DashboardToken.revoked == False)
        .update({"revoked": True})
    )

    db.flush()

    logger.info("Revoked %d old token(s) for pet_id=%s", revoked_count, str(pet_id))
    return generate_dashboard_token(db, pet_id)


def seed_preventive_records_for_pet(db: Session, pet: Pet) -> int:
    """
    Create initial preventive records for a newly onboarded pet.

    Special handling for Birthday Celebration:
        - Only created if pet.dob is provided.
        - Uses next_due_date calculated from DOB via birthday_service.
        - All other items use the standard approach (empty last_done_date).

    Args:
        db: SQLAlchemy database session.
        pet: The Pet model instance.

    Returns:
        Count of preventive records created.
    """
    seed_preventive_master(db)

    masters = (
        db.query(PreventiveMaster)
        .filter(PreventiveMaster.species.in_([pet.species, "both"]))
        .all()
    )

    # Seed only missing master items. This avoids duplicates when this
    # function is retried for recovery after partial transition failures.
    existing_master_ids = {
        row[0]
        for row in (
            db.query(PreventiveRecord.preventive_master_id)
            .filter(
                PreventiveRecord.pet_id == pet.id,
                PreventiveRecord.preventive_master_id.isnot(None),
            )
            .distinct()
            .all()
        )
        if row[0] is not None
    }

    count = 0
    for master in masters:
        if master.id in existing_master_ids:
            continue
        try:
            # Use a savepoint so individual failures only roll back this insert,
            # not the entire transaction (which would lose previously flushed records).
            nested = db.begin_nested()

            # Special handling for Birthday Celebration
            if master.item_name == "Birthday Celebration":
                # Skip if no DOB provided
                if not pet.dob:
                    nested.rollback()
                    logger.debug(
                        "Skipping Birthday Celebration for pet_id=%s: no DOB",
                        str(pet.id),
                    )
                    continue

                # Import here to avoid circular dependency
                from app.services.birthday_service import calculate_next_birthday

                next_birthday = calculate_next_birthday(pet.dob)
                previous_birthday = date(
                    next_birthday.year - 1, pet.dob.month, pet.dob.day
                )
                today = get_today_ist()

                record = PreventiveRecord(
                    pet_id=pet.id,
                    preventive_master_id=master.id,
                    last_done_date=previous_birthday,
                    next_due_date=next_birthday,
                    status="upcoming" if next_birthday <= today else "up_to_date",
                )
            else:
                # Standard preventive record with empty dates
                record = PreventiveRecord(
                    pet_id=pet.id,
                    preventive_master_id=master.id,
                    status="upcoming",
                )

            db.add(record)
            db.flush()
            nested.commit()
            count += 1
        except Exception as e:
            nested.rollback()
            logger.warning(
                "Failed to create preventive record for pet=%s, item=%s: %s",
                str(pet.id), master.item_name, str(e),
            )

    db.commit()

    logger.info(
        "Seeded %d preventive records for pet_id=%s (species=%s)",
        count, str(pet.id), pet.species,
    )
    return count
