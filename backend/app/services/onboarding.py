"""
PetCircle Phase 1 — Onboarding Service (Deterministic Flow v2)

Handles the 9-step WhatsApp conversation for user registration and
pet profile creation. State is tracked via user.onboarding_state.

Conversation flow:
    1. New number → Create user (welcome) → ask pet name
    2. Pet name → state=awaiting_breed_age → ask breed + age (combined)
    3. Breed+age → state=awaiting_gender_weight → ask gender + weight only
    4. Gender/weight → AI decides neuter question → state=awaiting_neuter_spay
    4b. Neuter/spay → state=awaiting_food_type
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

import calendar
import json
import logging
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, func, or_
from sqlalchemy.exc import SQLAlchemyError
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
    OPENAI_QUERY_MODEL,
)
from app.core.encryption import decrypt_field, encrypt_field, hash_field
from app.core.log_sanitizer import mask_phone
from app.database import get_fresh_session
from app.models.condition import Condition
from app.models.custom_preventive_item import CustomPreventiveItem
from app.models.dashboard_token import DashboardToken
from app.models.deferred_care_plan_pending import DeferredCarePlanPending
from app.models.document import Document
from app.models.pet import Pet
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.services.diet_service import HOMEMADE_KW, add_diet_item
from app.services.preventive_seeder import seed_preventive_master
from app.utils.breed_normalizer import normalize_breed, normalize_breed_with_ai
from app.utils.date_utils import (
    get_today_ist,
    parse_date,
    parse_date_with_ai,
)
from app.utils.file_reader import encode_image_base64
from app.utils.ai_client import get_ai_client
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

_openai_onboarding_client = None

def _get_openai_onboarding_client():
    """Return a cached AI client for onboarding checks (provider-agnostic)."""
    global _openai_onboarding_client
    if _openai_onboarding_client is None:
        _openai_onboarding_client = get_ai_client()
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


_CARE_PLAN_VACCINE_TERMS = [
    "vaccine", "rabies", "dhpp", "bordetella", "feline core",
    "coronavirus", "kennel cough", "leptospirosis", "nobivac",
]


def _count_tracked_preventive_items(db: Session, pet_id) -> int:
    """Return tracked preventive items count used across care-plan surfaces."""
    return (
        db.query(PreventiveRecord)
        .outerjoin(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
        .outerjoin(CustomPreventiveItem, PreventiveRecord.custom_preventive_item_id == CustomPreventiveItem.id)
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveRecord.last_done_date.isnot(None),
            or_(
                PreventiveMaster.is_core.is_(True),
                CustomPreventiveItem.id.isnot(None),
            ),
        )
        .count()
    )


def _count_tracked_preventive_items_split(db: Session, pet_id) -> tuple[int, int]:
    """Return (vaccine_count, other_count) for tracked core/custom preventive items.

    Splits the total tracked count into vaccines (matched by keyword) and all
    other preventive items so care-plan messages can reference each separately.
    """
    from sqlalchemy import or_ as _or
    base_q = (
        db.query(PreventiveRecord)
        .outerjoin(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
        .outerjoin(CustomPreventiveItem, PreventiveRecord.custom_preventive_item_id == CustomPreventiveItem.id)
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveRecord.last_done_date.isnot(None),
            _or(
                PreventiveMaster.is_core.is_(True),
                CustomPreventiveItem.id.isnot(None),
            ),
        )
    )
    # Match vaccine keywords against BOTH PreventiveMaster.item_name and
    # CustomPreventiveItem.item_name.  Vaccines logged as custom items (e.g.
    # when the extractor couldn't map them to a master) have master=NULL after
    # the outer-join, so a filter on PreventiveMaster.item_name alone would
    # undercount them to zero — which surfaces as "N preventive care items"
    # with no vaccine split in the care-plan message.
    vaccine_filter = _or(
        *[PreventiveMaster.item_name.ilike(f"%{kw}%") for kw in _CARE_PLAN_VACCINE_TERMS],
        *[CustomPreventiveItem.item_name.ilike(f"%{kw}%") for kw in _CARE_PLAN_VACCINE_TERMS],
    )
    vaccine_count = base_q.filter(vaccine_filter).count()
    total = base_q.count()
    return vaccine_count, total - vaccine_count

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
    "not right now",
    "not now",
    "later",
    "maybe later",
    "do it later",
    "upload later",
    "ill upload later",
    "i'll upload later",
    "move on",
    "moving on",
    "lets move on",
    "let's move on",
    "continue",
    "next",
    "what next",
    "what's next",
    "whats next",
    "proceed",
    "go ahead",
    "carry on",
)
_DOC_UPLOAD_INTENT_WORDS = ("upload", "sending", "send", "attach", "attached")

_SPECIES_INTENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "dog": (r"\bdog\b", r"\bdogs\b", r"\bpuppy\b", r"\bcanine\b"),
    "cat": (r"\bcat\b", r"\bcats\b", r"\bkitten\b", r"\bfeline\b"),
    "rabbit": (r"\brabbit\b", r"\brabbits\b", r"\bbunny\b", r"\bbunnies\b", r"\bholland\s+lop\b"),
    "bird": (r"\bbird\b", r"\bbirds\b", r"\bparrot\b", r"\bparakeet\b", r"\bcockatiel\b"),
    "fish": (r"\bfish\b", r"\bfishes\b", r"\bgoldfish\b", r"\bbetta\b"),
    "hamster": (r"\bhamster\b", r"\bhamsters\b"),
    "guinea pig": (r"\bguinea\s+pig\b", r"\bguinea\s+pigs\b"),
    "turtle": (r"\bturtle\b", r"\btortoise\b"),
}


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
    # Strip trailing punctuation (and whitespace around it) so "what next ?" → "what next".
    stripped = re.sub(r"[\s.!?]+$", "", collapsed)
    for phrase in _DOC_SKIP_PHRASES:
        if stripped == phrase:
            return True

    return False


def _detect_species_intent(text_lower: str) -> str | None:
    """Detect explicit species mention from free-text onboarding input."""
    normalized = (text_lower or "").strip().lower()
    if not normalized:
        return None

    shorthand_map = {
        "d": "dog",
        "dog": "dog",
        "c": "cat",
        "cat": "cat",
        "r": "rabbit",
    }
    if normalized in shorthand_map:
        return shorthand_map[normalized]

    def _is_negated_match(source_text: str, match_start: int) -> bool:
        """Return True when species keyword is immediately negated."""
        prefix = source_text[max(0, match_start - 12):match_start]
        return bool(re.search(r"(?:^|\b)(?:not|no)\b(?:\s+\w+){0,2}\s*$", prefix))

    matched_species: list[str] = []
    for species, patterns in _SPECIES_INTENT_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match and not _is_negated_match(normalized, match.start()):
                matched_species.append(species)
                break

    if not matched_species:
        # Fallback: check if input is a known breed name in breed dictionaries.
        inferred = _infer_species_from_breed(normalized)
        if inferred:
            return inferred
        return None

    if "dog" in matched_species:
        return "dog"
    return matched_species[0]


async def _send_dog_only_scope_message(
    db: Session,
    mobile: str,
    send_fn,
    pet_name: str,
    species_label: str,
) -> None:
    """Send a graceful out-of-scope message for non-dog onboarding."""
    await send_fn(
        db,
        mobile,
        f"Thanks for sharing. Right now, PetCircle onboarding supports *dogs only*. "
        f"I noted that {pet_name} is a *{species_label}*. "
        "We'll notify you when support opens for more species.",
    )


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

    # --- Irrelevant-input suppression ---
    # Silently swallow casual ack words ("yes", "ok", "thanks", etc.) when the
    # current step expects substantive input (breed, weight, food, etc.).
    if _is_irrelevant_noise_for_state(state, text_lower, _get_onboarding_data(user)):
        logger.info(
            "Suppressing irrelevant input %r during onboarding state=%s for user=%s",
            text_lower[:40], state, str(user.id),
        )
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

    # Allow mid-onboarding typo corrections for pet name.
    if state not in {"welcome", "complete"}:
        pending_pet = _get_pending_pet(db, user.id)
        corrected_name = _extract_pet_name_correction(text)
        if (
            pending_pet
            and not corrected_name
            and _looks_like_name_correction_intent(text_lower)
        ):
            corrected_name = await _ai_extract_pet_name_correction(text, pending_pet.name)
        if (
            pending_pet
            and corrected_name
            and corrected_name.strip().lower() != (pending_pet.name or "").strip().lower()
        ):
            pending_pet.name = corrected_name
            db.commit()
            resume_q = _get_question_for_state(state, pending_pet, _get_onboarding_data(user))
            await send_fn(
                db,
                mobile,
                f"Aww no worries at all. Thanks for correcting me. "
                f"I'll use *{corrected_name}* from now on.\n\n{resume_q}",
            )
            return

    if state == "welcome":
        await _step_welcome(db, user, text, send_fn, message_data=message_data)

    elif state == "awaiting_breed_age":
        await _step_breed_age(db, user, text, send_fn)

    elif state == "awaiting_gender_weight":
        await _step_gender_weight(db, user, text, send_fn)

    elif state == "awaiting_neuter_spay":
        await _step_neuter_spay(db, user, text, send_fn)

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

    elif state == "awaiting_vaccine_type":
        await _step_vaccine_type(db, user, text, send_fn)

    elif state == "awaiting_flea_brand":
        await _step_flea_brand(db, user, text, send_fn)

    elif state == "awaiting_documents":
        await _step_awaiting_documents(db, user, text_lower, send_fn)

    else:
        # Unknown or legacy state — reset.
        logger.warning("Unknown onboarding state '%s' for user %s — resetting to welcome", state, mobile)
        user.onboarding_state = "welcome"
        user.onboarding_data = None
        db.commit()
        profile_name = user.full_name if user.full_name != "_pending" else "there"
        await send_fn(db, mobile, build_welcome_message(profile_name))


def build_welcome_message(name: str) -> str:
    """Return the PetCircle welcome message personalised with the given name."""
    return (
        f"Hi {name}, welcome to PetCircle — your pet care companion.\n\n"
        "We're here to make pet parenting simpler, helping you stay on top of your pet's health, nutrition, and everyday wellness.\n\n"
        "Here's how we support you:\n"
        "• Organise health records\n"
        "• Timely reminders & one-click ordering\n"
        "• Personalised diet & nutrition\n"
        "• Health insights & what to ask your vet\n\n"
        "Because your pet deserves the very best care.\n\n"
        "Let's get started — what's your pet's name?"
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


def _get_onboarding_timestamp(data: dict, key: str) -> float | None:
    """Read a numeric timestamp from onboarding_data safely."""
    raw = data.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


# --- Irrelevant-input noise suppression ---
#
# Casual ack words that are *never* a valid response to the substantive
# onboarding questions (breed, weight, food, supplements, preventive care).
# These are treated as noise and trigger a re-ask (once) before being
# silently swallowed.
_NOISE_WORDS: frozenset[str] = frozenset({
    "yes", "y", "yeah", "yea", "yep", "yup", "ya", "yah", "haan", "ha",
    "no", "n", "nah", "nope", "nay", "na", "nahi",
    "ok", "okay", "k", "kk", "okk",
    "thanks", "thank you", "ty", "thx",
    "got it", "alright", "aight", "cool", "nice", "great", "good",
    "sure", "fine",
    "hmm", "hm", "hmmm", "uh", "um", "uhh", "umm",
})

# States during which casual ack words are *legitimate* user responses and
# must NOT be suppressed. The welcome step's consent question and the
# document upload window (where "no/skip" is meaningful) need them.
_NOISE_ALLOWED_STATES: frozenset[str] = frozenset({
    "welcome",
    "awaiting_documents",
})


def _has_pending_confirmation_prompt(state: str, onboarding_data: dict | None) -> bool:
    """
    Return True when the current state is explicitly waiting for a yes/no style
    confirmation reply.

    This protects legit short replies like "y"/"yes" from being swallowed by
    global onboarding noise suppression.
    """
    data = onboarding_data or {}
    if not data:
        return False

    # Any active "*_confirm_pending" marker means this state is waiting for
    # a short confirmation reply and must not treat yes/no as noise.
    for key, value in data.items():
        if key.endswith("_confirm_pending") and bool(value):
            return True
    return False


def _is_irrelevant_noise_for_state(
    state: str,
    text_lower: str,
    onboarding_data: dict | None = None,
) -> bool:
    """
    Return True if `text_lower` is a casual ack word that cannot possibly
    answer the question being asked in the current onboarding state.

    If the step has an active confirmation prompt, yes/no replies are valid
    and must not be suppressed.
    """
    if not text_lower:
        return False

    normalized = re.sub(r"[.!?,]+$", "", text_lower.strip().lower())

    # In neuter/spay step, yes/no are the expected answers.
    if state == "awaiting_neuter_spay" and (
        normalized in _YES_INPUTS or normalized in _NO_INPUTS
    ):
        return False

    # In supplements step, explicit negative replies are legitimate answers
    # to "Is <pet> on any supplements right now?" and must be processed.
    if state == "awaiting_supplements" and (
        normalized in _NO_INPUTS or normalized in _NONE_KEYWORDS
    ):
        return False

    # In preventive steps, explicit negative replies are valid because users
    # can answer "no"/"none" to indicate no history for missing categories.
    if state in {"awaiting_preventive", "awaiting_prev_retry"} and (
        normalized in _NO_INPUTS or normalized in _NONE_KEYWORDS
    ):
        return False

    if state in _NOISE_ALLOWED_STATES:
        return False
    if _has_pending_confirmation_prompt(state, onboarding_data):
        return False
    return normalized in _NOISE_WORDS


def _resolve_binary_confirmation_reply(text_lower: str) -> str | None:
    """
    Parse a short confirmation reply into deterministic intent.

    Returns:
        - "yes" for affirmative replies
        - "no" for negative replies
        - None when reply is not a plain yes/no
    """
    normalized = re.sub(r"[.!?,]+$", "", (text_lower or "").strip().lower())
    if normalized in _YES_INPUTS:
        return "yes"
    if normalized in _NO_INPUTS:
        return "no"
    return None


def _sanitize_pet_name_candidate(candidate: str) -> str:
    """Normalize a pet-name candidate and strip trailing correction chatter."""
    cleaned = re.sub(r"\s+", " ", (candidate or "").strip())
    if not cleaned:
        return ""

    cleaned = re.split(
        r"\b(?:i\s+typed\s+(?:it\s+)?wrong|typed\s+wrong|type\s+wrong|that\s+was\s+wrong|my\s+bad|sorry)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    cleaned = re.split(r"[.,!?;]", cleaned, maxsplit=1)[0].strip()
    cleaned = cleaned.strip("\"'` ")

    return cleaned[:100]


def _extract_pet_name_correction(text: str) -> str | None:
    """Extract corrected pet name from messages like 'actually his name is Mocha'."""
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return None

    patterns = (
        r"\b(?:actually\s+)?(?:his|her|their)\s+name\s+is\s+([a-zA-Z][a-zA-Z\s'\-]{0,49})",
        r"\b(?:i\s+typed\s+(?:it\s+)?wrong[, ]*)?(?:actually\s+)?name\s+is\s+([a-zA-Z][a-zA-Z\s'\-]{0,49})",
        r"\b(?:pet'?s?\s+)?name\s+(?:should\s+be|is\s+actually)\s+([a-zA-Z][a-zA-Z\s'\-]{0,49})",
        r"\brename\s+(?:him|her|them|it|to\s+)?([a-zA-Z][a-zA-Z\s'\-]{0,49})",
        r"\bchange\s+(?:the\s+)?name\s+to\s+([a-zA-Z][a-zA-Z\s'\-]{0,49})",
        r"\bcall\s+(?:him|her|them|it)\s+([a-zA-Z][a-zA-Z\s'\-]{0,49})",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = re.sub(r"\s+", " ", (match.group(1) or "").strip(" .,!?:;"))
        candidate = re.split(r"\b(?:and|but|because|so)\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        candidate = _sanitize_pet_name_candidate(candidate)
        if not candidate:
            continue
        words = candidate.split()
        if len(words) > 4:
            continue
        return candidate[:100].title()
    return None


def _looks_like_name_correction_intent(text_lower: str) -> bool:
    """Return True when the message likely attempts to correct pet name text."""
    normalized = re.sub(r"\s+", " ", (text_lower or "").strip().lower())
    if not normalized:
        return False

    signals = (
        "name",
        "typed wrong",
        "type wrong",
        "wrong name",
        "not ",
        "instead",
        "correction",
        "correct name",
        "meant",
        "actually",
        "call him",
        "call her",
        "call them",
        "rename",
        "change name",
        "change the name",
        "should be",
        "it's ",
        "its ",
        "sorry",
    )
    return any(signal in normalized for signal in signals)


async def _ai_extract_pet_name_correction(text: str, current_name: str | None = None) -> str | None:
    """Use AI to infer corrected pet name from free-form typo/correction messages."""
    client = _get_openai_onboarding_client()
    prompt = (
        "You are extracting a corrected pet name from a WhatsApp onboarding message. "
        "The user may say they typed the name wrong and provide the corrected name in informal wording. "
        "Return ONLY valid JSON with this schema: "
        '{"is_correction": true|false, "corrected_name": string|null}. '
        "If no clear corrected name is present, set corrected_name to null and is_correction to false. "
        "Use title case for names. Keep only the pet's name words, not extra phrases. "
        "Do not hallucinate names.\n\n"
        f"Current registered name: {current_name or 'unknown'}\n"
        f"User message: {text}"
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=80,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        corrected = str(data.get("corrected_name") or "").strip()
        if not corrected:
            return None
        corrected = _sanitize_pet_name_candidate(corrected)
        corrected = corrected[:100].title()
        if not corrected:
            return None
        words = corrected.split()
        if len(words) > 4:
            return None
        return corrected
    except Exception as e:
        logger.warning("AI pet-name correction parse failed: %s", str(e))
        return None


def _build_gender_neuter_confirmation(
    text: str,
    parsed_gender: str | None,
    parsed_neutered: bool | None,
    pet_name: str,
) -> dict | None:
    """Return a clarification prompt when gender/procedure details are inconsistent."""
    normalized_text = re.sub(r"\s+", " ", (text or "").lower())
    normalized = f" {normalized_text} "

    male_terms = (" male ", " boy ", " he ", " him ", " his ")
    female_terms = (" female ", " girl ", " she ", " her ", " hers ")
    mentions_spayed = re.search(r"\bspay(?:ed|ing)?\b", normalized) is not None

    male_indicated = parsed_gender == "male" or any(term in normalized for term in male_terms)
    female_indicated = parsed_gender == "female" or any(term in normalized for term in female_terms)

    # Example: "he weighs ... she is spayed" -> don't assume silently.
    if male_indicated and female_indicated:
        if mentions_spayed or (parsed_gender == "female" and parsed_neutered is True):
            return {
                "prompt": f"Just to confirm — {pet_name} is female and spayed, right?",
                "confirm_mode": "binary",
                "confirm_payload": {"gender": "female", "neutered": True},
            }
        return {
            "prompt": f"I noticed both 'he' and 'she' in your message. Please reply with just male or female for {pet_name}.",
            "confirm_mode": "gender_choice",
            "confirm_payload": None,
        }

    # Example: "male ... spayed" -> gentle terminology correction.
    if male_indicated and mentions_spayed:
        return {
            "prompt": (
                f"For male dogs the procedure is neutering, not spaying. "
                f"Is {pet_name} neutered?"
            ),
            "confirm_mode": "binary",
            "confirm_payload": {"gender": "male", "neutered": True},
        }

    return None


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

    next_question = _get_question_for_state(state, pet, _get_onboarding_data(user))
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


def _build_supplements_example(onboarding_data: dict | None = None) -> str:
    """Build supplements examples, omitting omega when already captured in meal details."""
    labels = (onboarding_data or {}).get("meal_supplement_labels") or []
    has_omega = any(
        re.search(r"\bomega\s*[- ]?\s*3\b", str(label).strip().lower()) is not None
        for label in labels
    )
    if has_omega:
        return "joint support, calcium, probiotics"
    return "joint support, Omega-3, calcium"


def _supplements_question_for_pet(pet_name: str, onboarding_data: dict | None = None) -> str:
    """Return the supplements question with context-aware examples."""
    example_text = _build_supplements_example(onboarding_data)
    return (
        f"Is {pet_name} on any supplements right now? "
        f"(e.g., {example_text} — or just say None)"
    )


def _get_question_for_state(state: str, pet=None, onboarding_data: dict | None = None) -> str:
    """Return the question prompt corresponding to the current onboarding state."""
    pet_name = pet.name if pet else "your pet"

    if state == "awaiting_supplements":
        return _supplements_question_for_pet(pet_name, onboarding_data)

    prompts = {
        "welcome": "What's your pet's name?",
        "awaiting_breed_age": (
            f"What breed is {pet_name} and how old are they? "
            f"DOB or approximate age is fine (e.g., golden retriever, Nov 2024 or 2 years)"
        ),
        "awaiting_gender_weight": (
            f"What's {pet_name}'s gender and approximate weight? "
            f"(e.g., male, 22 kg)"
        ),
        "awaiting_neuter_spay": (
            f"Is {pet_name} neutered or spayed?"
        ),
        "awaiting_food_type": (
            f"What does {pet_name} usually eat — home food, packaged, or a mix?"
        ),
        "awaiting_meal_details": (
            f"What does {pet_name}'s typical daily diet look like?"
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
            "Do you have any health records handy — a vaccination card, "
            "vet prescription, or lab report? Share a photo or PDF and I'll pull "
            "the details in automatically. No worries if not, we can always add them later."
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

    pet_name = _sanitize_pet_name_candidate(text).title()
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
        f"Love that name! 🐾 " + _get_question_for_state("awaiting_breed_age", pet),
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

    if text_lower == "waitlist" and od.get("non_dog_waitlist_prompted"):
        await send_fn(
            db,
            mobile,
            "You're on our waitlist for non-dog species support. We'll share updates here.",
        )
        return

    # Handle species sub-question: if we're waiting for dog/cat answer.
    if od.get("needs_species"):
        detected_species = _detect_species_intent(text_lower)
        if detected_species == "dog":
            pet.species = "dog"
            _set_onboarding_data(user, "needs_species", False)
            _set_onboarding_data(user, "gender_weight_attempts", 0)
            user.onboarding_state = "awaiting_gender_weight"
            db.commit()
            await send_fn(
                db, mobile,
                f"Got it. What's {pet.name}'s gender and approximate weight? "
                f"(e.g., male, 22 kg)",
            )
            return
        if detected_species and detected_species != "dog":
            _set_onboarding_data(user, "non_dog_waitlist_prompted", True)
            db.commit()
            await _send_dog_only_scope_message(db, mobile, send_fn, pet.name, detected_species)
            return
        await send_fn(
            db,
            mobile,
            "Please reply *dog* to continue. We currently support dogs only.",
        )
        return

    # Handle skip.
    if text_lower in _SKIP_INPUTS:
        _set_onboarding_data(user, "gender_weight_attempts", 0)
        user.onboarding_state = "awaiting_gender_weight"
        db.commit()
        await send_fn(
            db, mobile,
            f"No worries! What's {pet.name}'s gender and approximate weight? "
            f"(e.g., male, 22 kg)",
        )
        return

    explicit_species = _detect_species_intent(text_lower)
    if explicit_species and explicit_species != "dog":
        _set_onboarding_data(user, "non_dog_waitlist_prompted", True)
        db.commit()
        await _send_dog_only_scope_message(db, mobile, send_fn, pet.name, explicit_species)
        return

    # GPT parse breed + age.
    parsed = await _parse_breed_age(text)
    breed_raw = parsed.get("breed")
    species_gpt = parsed.get("species")
    age_years = parsed.get("age_years")
    age_text_raw = parsed.get("age_text")

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
    if species_gpt == "dog":
        pet.species = species_gpt
    elif species_gpt and species_gpt != "dog":
        _set_onboarding_data(user, "non_dog_waitlist_prompted", True)
        db.commit()
        await _send_dog_only_scope_message(db, mobile, send_fn, pet.name, str(species_gpt))
        return

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
        # When only age is provided, use first day of current month in the birth year.
        # This ensures consistent age calculation and avoids day-of-month edge cases.
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
        _breed_age_prior = f"What's {pet.name}'s breed and approximate age?"
        _breed_age_next = "ask for the pet's gender and approximate weight"
        if not has_breed and not has_age:
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context="the pet's breed and approximate age",
                expected_format="e.g., golden retriever, 4 years",
                pet_name=pet.name,
                prior_assistant_message=_breed_age_prior,
                next_step_description=_breed_age_next,
            )
        elif not has_breed:
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context=f"the pet's breed (age already noted as {pet.age_text})",
                expected_format="e.g., golden retriever, labrador, or just say 'mixed'",
                pet_name=pet.name,
                prior_assistant_message=_breed_age_prior,
                next_step_description=_breed_age_next,
            )
        else:
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context=f"the pet's age (breed already noted as {pet.breed})",
                expected_format="e.g., 4 years, 6 months, puppy",
                pet_name=pet.name,
                prior_assistant_message=_breed_age_prior,
                next_step_description=_breed_age_next,
            )
        await send_fn(db, mobile, clarification)
        return

    # If species still unknown, ask as sub-question.
    if pet.species in (None, "_pending"):
        _set_onboarding_data(user, "needs_species", True)
        db.commit()
        await send_fn(
            db, mobile,
            f"Got it! Is {pet.name} a *dog*? We currently support dogs only.",
        )
        return

    # All good — advance to next step.
    _set_onboarding_data(user, "gender_weight_attempts", 0)
    user.onboarding_state = "awaiting_gender_weight"
    db.commit()

    await send_fn(
        db, mobile,
        f"Got it. What's {pet.name}'s gender and approximate weight? "
        f"(e.g., male, 22 kg)",
    )


async def _step_gender_weight(db, user, text, send_fn):
    """
    Step 3: Collect gender + weight only (GPT-parsed).
    Clarifies once via AI if nothing can be parsed.
    After collecting, an AI agent decides whether/how to ask about
    neutering or spaying based on gender, age, and breed, then transitions
    to awaiting_neuter_spay.
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
        parsed = await _parse_gender_weight(text)
        gender = parsed.get("gender")
        weight_kg = parsed.get("weight_kg")

        # If nothing parsed on the first attempt, ask AI to clarify once.
        if gender is None and weight_kg is None and gw_attempts < 1:
            _set_onboarding_data(user, "gender_weight_attempts", 1)
            db.commit()
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context="the pet's gender and approximate weight",
                expected_format="e.g., male, 22 kg",
                pet_name=pet.name,
                prior_assistant_message=(
                    f"What's {pet.name}'s gender and approximate weight? (e.g., male, 22 kg)"
                ),
                next_step_description=(
                    "decide whether to ask about neutering/spaying based on gender & age, "
                    "then move to food type"
                ),
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
                    # AI weight check — non-blocking, flag if unusual.
                    ai_result = await _ai_check_weight(
                        species=pet.species, breed=pet.breed,
                        dob=pet.dob, weight_kg=w,
                    )
                    if ai_result and not ai_result.get("reasonable", True):
                        pet.weight_flagged = True
            except (ValueError, TypeError):
                pass

    # AI agent decides whether to ask about neutering/spaying and crafts the
    # gender-appropriate question (neutered for males, spayed for females).
    _set_onboarding_data(user, "gender_weight_attempts", 0)
    neuter_decision = await _ai_decide_neuter_question(
        pet_name=pet.name,
        gender=pet.gender,
        species=pet.species,
        breed=pet.breed,
        age_text=pet.age_text,
    )

    if neuter_decision.get("should_ask", True):
        _set_onboarding_data(user, "neuter_spay_attempts", 0)
        user.onboarding_state = "awaiting_neuter_spay"
        db.commit()
        await send_fn(db, mobile, neuter_decision["question"])
    else:
        # Pet is too young or neuter status is not relevant — skip to food.
        user.onboarding_state = "awaiting_food_type"
        _set_onboarding_data(user, "food_type_attempts", 0)
        db.commit()
        await send_fn(
            db, mobile,
            f"What does {pet.name} usually eat — home food, packaged, or a mix?",
        )


async def _step_neuter_spay(db, user, text, send_fn):
    """
    Step 3b: Collect neutered/spayed status via a binary yes/no reply.
    The question was already phrased correctly for the pet's gender
    (neutered for males, spayed for females) by _ai_decide_neuter_question.
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
    attempts = od.get("neuter_spay_attempts", 0)

    if text_lower not in _SKIP_INPUTS:
        reply = _resolve_binary_confirmation_reply(text_lower)

        if reply == "yes":
            pet.neutered = True
        elif reply == "no":
            pet.neutered = False
        else:
            # Unclear answer — clarify once, then default to None on second miss.
            if attempts < 1:
                _set_onboarding_data(user, "neuter_spay_attempts", 1)
                db.commit()
                # Re-ask with the gender-appropriate term.
                term = "neutered" if pet.gender == "male" else "spayed"
                await send_fn(
                    db, mobile,
                    f"Just reply *yes* or *no* — is {pet.name} {term}?",
                )
                return
            # Second miss — leave neutered as None and continue.

    # Advance to food type question.
    user.onboarding_state = "awaiting_food_type"
    _set_onboarding_data(user, "food_type_attempts", 0)
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
        if attempts >= 1:
            food_type = "mix"  # Default on second unrecognized attempt.
        else:
            _set_onboarding_data(user, "food_type_attempts", attempts + 1)
            db.commit()
            clarification = await _ai_clarify_input(
                user_message=text,
                step_context="what type of food the pet eats",
                expected_format="Reply with *home food*, *packaged food*, or *mix*",
                pet_name=pet.name,
                prior_assistant_message=(
                    f"What does {pet.name} usually eat — home food, packaged, or a mix?"
                ),
                next_step_description="ask for a typical daily meal breakdown",
            )
            await send_fn(db, mobile, clarification)
            return

    _set_onboarding_data(user, "food_type", food_type)
    _set_onboarding_data(user, "meal_details_attempts", 0)
    _set_onboarding_data(user, "meal_confirm_pending", False)
    _set_onboarding_data(user, "meal_supplement_labels", [])
    user.onboarding_state = "awaiting_meal_details"

    # Contextual meal details question — store the example so we can
    # reference it if the user says "same".
    _MEAL_EXAMPLES = {
        "home": "boiled chicken + rice in the morning, dal + roti at night, occasional egg",
        "packaged": "Royal Canin Adult kibble 50g × 3 times a day, small treat in the evening",
        "mix": "Royal Canin kibble 2 cups/day + 1 cup cooked carrot",
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
            binary_reply = _resolve_binary_confirmation_reply(text_lower)
            if binary_reply == "no":
                db.commit()
                await send_fn(
                    db, mobile,
                    f"No problem! Could you describe what {pet.name} actually eats "
                    f"in a typical day?",
                )
                return

            # Use AI to interpret: plain yes → use example as-is,
            # yes-with-changes → modify example, no → re-ask.
            final_diet = example_shown if binary_reply == "yes" else await _ai_resolve_example_confirmation(
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
            meal_supp_labels = await _store_meal_supplement_items(db, pet, final_diet)
            _set_onboarding_data(user, "meal_supplement_labels", meal_supp_labels)

        if text_lower in _SKIP_INPUTS:
            _set_onboarding_data(user, "meal_supplement_labels", [])

        user.onboarding_state = "awaiting_supplements"
        db.commit()
        await send_fn(
            db, mobile,
            f"Noted. {_supplements_question_for_pet(pet.name, _get_onboarding_data(user))}",
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
                prior_assistant_message=(
                    f"What does {pet.name}'s typical daily diet look like?"
                    + (f" (e.g., {example_shown})" if example_shown else "")
                ),
                next_step_description="ask about supplements the pet currently takes",
            )
            await send_fn(db, mobile, clarification)
            return

        items = await _parse_diet_input(text)
        await _store_meal_items(db, pet, items, food_type)
        meal_supp_labels = await _store_meal_supplement_items(db, pet, text)
        _set_onboarding_data(user, "meal_supplement_labels", meal_supp_labels)
    else:
        _set_onboarding_data(user, "meal_supplement_labels", [])

    user.onboarding_state = "awaiting_supplements"
    db.commit()

    await send_fn(
        db, mobile,
        f"Noted. {_supplements_question_for_pet(pet.name, _get_onboarding_data(user))}",
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
    normalized = re.sub(r"[.!?,]+$", "", text_lower)

    if (
        normalized not in _SKIP_INPUTS
        and normalized not in _NONE_KEYWORDS
        and normalized not in _NO_INPUTS
    ):
        # Guard: if the user sent preventive care info (flea/tick brands, deworming
        # medicines) during the supplements step, save it as a prefill for the upcoming
        # preventive step rather than misclassifying it as a dietary supplement.
        _PREVENTIVE_KEYWORDS = {
            "flea", "tick", "deworming", "deworm", "worm", "simparica", "nexgard",
            "bravecto", "frontline", "drontal", "milbemax", "panacur", "advocate",
            "revolution", "credelio", "seresto", "advantix", "fipronil", "ivermectin",
            "fenbendazole", "pyrantel", "albendazole", "prazitel", "verminator",
            "blood test", "blood tests", "vaccine", "vaccination",
        }
        if any(kw in text_lower for kw in _PREVENTIVE_KEYWORDS):
            prefill = await _parse_preventive_care(text)
            existing_prefill = _get_onboarding_data(user).get("preventive_prefill") or {}
            # Merge: only fill keys not already set.
            for k, v in prefill.items():
                if k != "missing" and v and not existing_prefill.get(k):
                    existing_prefill[k] = v
            _set_onboarding_data(user, "preventive_prefill", existing_prefill)
            db.commit()
            # Re-ask supplements so the user still gets a chance to answer it.
            await send_fn(
                db, mobile,
                f"Got it, noted that for {pet.name}'s care plan! "
                + _supplements_question_for_pet(pet.name, _get_onboarding_data(user)),
            )
            return

        # Guard against late-arriving meal messages: if the user sent food items
        # (e.g. "boiled egg whites") across multiple messages and the second message
        # arrived after the state already advanced to awaiting_supplements, detect this
        # and save as additional diet items instead of misclassifying as supplements.
        is_food_not_supplement = await _ai_is_food_not_supplement(text)
        if is_food_not_supplement:
            od = _get_onboarding_data(user)
            food_type = od.get("food_type", "mix")
            extra_items = await _parse_diet_input(text)
            await _store_meal_items(db, pet, extra_items, food_type)
            extra_supp_labels = await _store_meal_supplement_items(db, pet, text)
            existing_labels = od.get("meal_supplement_labels") or []
            _set_onboarding_data(
                user,
                "meal_supplement_labels",
                existing_labels + extra_supp_labels,
            )
            db.commit()
            # Re-ask supplements so the user still gets a chance to answer.
            await send_fn(
                db, mobile,
                f"Got it, added that to {pet.name}'s diet. "
                + _supplements_question_for_pet(pet.name, _get_onboarding_data(user)),
            )
            return

        # Use supplement-specific extractor instead of food parser
        supplements = await _extract_meal_supplement_items(text)
        # If supplement extractor returns no items (e.g., "omega" not recognized),
        # fall back to treating the input as a supplement label directly.
        if not supplements and text_lower and text_lower not in _SKIP_INPUTS:
            supplements = [(text.strip(), "")]

        for label, detail in supplements:
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
    # Start at -1 so a queued message that arrives before the user sees the
    # question gets one free pass (increments to 0) instead of triggering
    # an immediate clarification.
    _PREVENTIVE_EXAMPLE = "vaccines last Dec, deworming Jan, flea 2 months ago, no blood test yet"
    user.onboarding_state = "awaiting_preventive"
    _set_onboarding_data(user, "preventive_attempts", 0)
    _set_onboarding_data(user, "preventive_confirm_pending", False)
    _set_onboarding_data(user, "preventive_example_shown", _PREVENTIVE_EXAMPLE)
    # Flag flea/tick as excluded from expectations when the puppy is under 8 weeks —
    # most products are not safe at that age so we should not prompt for it.
    _age_wks = _get_age_in_weeks(pet)
    _set_onboarding_data(
        user, "preventive_flea_excluded",
        bool(_age_wks is not None and _age_wks < 8),
    )
    db.commit()

    _puppy_q = _age_appropriate_preventive_question(pet)
    await send_fn(
        db, mobile,
        _puppy_q if _puppy_q else (
            f"What do you remember about {pet.name}'s vaccines, deworming, flea & tick, "
            f"and blood tests? (e.g., {_PREVENTIVE_EXAMPLE} — rough is fine)."
        ),
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
    normalized = re.sub(r"[.!?,]+$", "", text_lower)
    od = _get_onboarding_data(user)
    confirm_pending = od.get("preventive_confirm_pending", False)
    example_shown = od.get("preventive_example_shown", "")
    flea_excluded = od.get("preventive_flea_excluded", False)

    # --- Handle confirmation reply (user was asked "Is this your pet's history?") ---
    if confirm_pending:
        _set_onboarding_data(user, "preventive_confirm_pending", False)
        if text_lower not in _SKIP_INPUTS:
            binary_reply = _resolve_binary_confirmation_reply(text_lower)
            if binary_reply == "no":
                db.commit()
                _preventive_items = (
                    "vaccines, deworming, and blood tests"
                    if flea_excluded
                    else "vaccines, deworming, flea & tick, and blood tests"
                )
                await send_fn(
                    db, mobile,
                    f"No problem! Could you share what you remember about {pet.name}'s "
                    f"{_preventive_items}?",
                )
                return

            final_preventive = (
                example_shown
                if binary_reply == "yes"
                else await _ai_resolve_example_confirmation(
                    text, example_shown, pet.name, "preventive",
                )
            )
            if final_preventive == "__reject__":
                db.commit()
                _reject_items = (
                    "vaccines, deworming, and blood tests"
                    if flea_excluded
                    else "vaccines, deworming, flea & tick, and blood tests"
                )
                await send_fn(
                    db, mobile,
                    f"No problem! Could you share what you remember about {pet.name}'s "
                    f"{_reject_items}?",
                )
                return
            # Parse the confirmed/modified preventive text.
            parsed = await _parse_preventive_care(final_preventive)
            conf_attempts = od.get("preventive_attempts", 0)

            # Apply the same follow-up question checks as the normal flow so that
            # a user who provides fresh data via the confirm-pending path still gets
            # asked which vaccines they use and which flea brand they apply.
            needs_vaccine_type_q = _is_generic_vaccine_mention(parsed)
            needs_flea_brand_q = _is_flea_without_brand(parsed)

            if needs_vaccine_type_q:
                _set_onboarding_data(user, "pending_preventive_parsed", parsed)
                _set_onboarding_data(user, "pending_flea_brand_needed", needs_flea_brand_q)
                _set_onboarding_data(user, "preventive_attempts", conf_attempts)
                _set_onboarding_data(user, "preventive_missing", [])
                user.onboarding_state = "awaiting_vaccine_type"
                db.commit()
                _vax_age_wks = _get_age_in_weeks(pet)
                _vax_q = (
                    _puppy_vaccine_question(pet.name, _vax_age_wks)
                    if _vax_age_wks is not None and _vax_age_wks < 52
                    else _vaccine_type_question(pet.name)
                )
                await send_fn(db, mobile, _vax_q)
                return

            if needs_flea_brand_q:
                _set_onboarding_data(user, "pending_preventive_parsed", parsed)
                _set_onboarding_data(user, "pending_flea_brand_needed", True)
                _set_onboarding_data(user, "preventive_attempts", conf_attempts)
                _set_onboarding_data(user, "preventive_missing", [])
                user.onboarding_state = "awaiting_flea_brand"
                db.commit()
                await send_fn(db, mobile, _flea_brand_question(pet.name))
                return

            conf_ambiguous = await _store_preventive_data(db, pet, parsed)
            # If confirmed text still had unparseable dates, treat as missing for retry.
            if conf_ambiguous and conf_attempts < 1:
                _set_onboarding_data(user, "preventive_attempts", 1)
                user.onboarding_state = "awaiting_prev_retry"
                _set_onboarding_data(user, "preventive_missing", conf_ambiguous)
                db.commit()
                _CONF_AMB_NAMES = {
                    "vaccines": "vaccines",
                    "deworming": "deworming",
                    "flea_tick": "flea & tick treatment",
                    "blood_test": "blood tests",
                }
                amb_str = " and ".join(_CONF_AMB_NAMES.get(k, k) for k in conf_ambiguous)
                await send_fn(db, mobile, f"Got it! What about {amb_str}?")
                return

        await _transition_to_documents(db, user, pet, send_fn)
        return

    # Skip / nothing done.
    if (
        normalized in _SKIP_INPUTS
        or normalized in _NONE_KEYWORDS
        or normalized in _NO_INPUTS
        or normalized in {"nothing done", "no idea", "don't remember", "dont remember"}
    ):
        await _transition_to_documents(db, user, pet, send_fn)
        return

    # Guard against late-arriving diet/supplement messages from prior steps.
    # Run before the grace pass so that food/supplement data is saved rather than discarded.
    prior_classification = await _classify_prior_step_input(text, "awaiting_preventive")
    if prior_classification in ("food", "supplement"):
        _reask_preventive_items = (
            "vaccines, deworming, and blood tests"
            if flea_excluded
            else "vaccines, deworming, flea & tick, and blood tests"
        )
        reask = (
            f"Got it, added that to {pet.name}'s "
            f"{'diet' if prior_classification == 'food' else 'supplements'}. "
            f"What do you remember about {pet.name}'s {_reask_preventive_items}? (rough is fine)."
        )
        await _save_prior_step_dietary_input(
            db, user, pet, text, prior_classification, send_fn, reask
        )
        return

    attempts = od.get("preventive_attempts", 0)

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

    # Merge any preventive care data saved as prefill from an earlier step
    # (e.g. user mentioned flea/tick brand during the supplements step).
    prefill = od.get("preventive_prefill") or {}
    if prefill:
        for k, v in prefill.items():
            if k != "missing" and v and not parsed.get(k):
                parsed[k] = v
        # Recalculate missing after merge.
        # Exclude flea_tick for puppies under 8 weeks (products not safe yet).
        all_fields_check = (
            {"vaccines", "deworming", "blood_test"}
            if flea_excluded
            else {"vaccines", "deworming", "flea_tick", "blood_test"}
        )
        parsed["missing"] = [
            f for f in all_fields_check if not parsed.get(f) or parsed.get(f) == "none"
        ]
        _set_onboarding_data(user, "preventive_prefill", {})

    missing = parsed.get("missing", [])

    # If ALL fields are missing (nothing parsed at all), clarify with AI first.
    all_fields = (
        {"vaccines", "deworming", "blood_test"}
        if flea_excluded
        else {"vaccines", "deworming", "flea_tick", "blood_test"}
    )
    if set(missing) == all_fields and attempts < 1:
        _set_onboarding_data(user, "preventive_attempts", 1)
        db.commit()
        _clarify_context = (
            "the pet's preventive care history — vaccines, deworming, and blood tests"
            if flea_excluded
            else "the pet's preventive care history — vaccines, deworming, flea & tick treatment, and blood tests"
        )
        _default_fmt = (
            "e.g., vaccines last Dec, deworming Jan, no blood test yet"
            if flea_excluded
            else "e.g., vaccines last Dec, deworming Jan, flea 2 months ago, no blood test yet"
        )
        clarification = await _ai_clarify_input(
            user_message=text,
            step_context=_clarify_context,
            expected_format=f"e.g., {example_shown}" if example_shown else _default_fmt,
            pet_name=pet.name,
            prior_assistant_message=(
                f"When was {pet.name}'s last vaccination, deworming, "
                + ("and blood test? " if flea_excluded else "flea & tick treatment, and blood test? ")
                + "(rough dates are fine)"
            ),
            next_step_description=(
                "offer the optional health-record document upload window before finalizing onboarding"
            ),
        )
        await send_fn(db, mobile, clarification)
        return

    # --- Detect generic vaccine mention and flea without brand ---
    needs_vaccine_type_q = _is_generic_vaccine_mention(parsed)
    needs_flea_brand_q = _is_flea_without_brand(parsed)

    if needs_vaccine_type_q:
        # Save parsed data for use after vaccine type answer.
        _set_onboarding_data(user, "pending_preventive_parsed", parsed)
        _set_onboarding_data(user, "pending_flea_brand_needed", needs_flea_brand_q)
        _set_onboarding_data(user, "preventive_attempts", attempts)
        _set_onboarding_data(user, "preventive_missing", missing)
        user.onboarding_state = "awaiting_vaccine_type"
        db.commit()
        # Use a puppy-series question for dogs under 1 year; adults get the standard question.
        _vax_age_wks = _get_age_in_weeks(pet)
        _vax_q = (
            _puppy_vaccine_question(pet.name, _vax_age_wks)
            if _vax_age_wks is not None and _vax_age_wks < 52
            else _vaccine_type_question(pet.name)
        )
        await send_fn(db, mobile, _vax_q)
        return

    if needs_flea_brand_q:
        # Save parsed data for use after flea brand answer.
        _set_onboarding_data(user, "pending_preventive_parsed", parsed)
        _set_onboarding_data(user, "pending_flea_brand_needed", True)
        _set_onboarding_data(user, "preventive_attempts", attempts)
        _set_onboarding_data(user, "preventive_missing", missing)
        user.onboarding_state = "awaiting_flea_brand"
        db.commit()
        await send_fn(db, mobile, _flea_brand_question(pet.name))
        return

    # Store whatever was parsed; collect categories that had a value but unparseable date.
    ambiguous = await _store_preventive_data(db, pet, parsed)
    # Treat ambiguous like missing so they get re-asked in the retry step.
    for key in ambiguous:
        if key not in missing:
            missing.append(key)

    # If some fields are missing (or ambiguous) and this is the first attempt, re-ask once.
    if missing and attempts < 1:
        _set_onboarding_data(user, "preventive_attempts", 1)
        _set_onboarding_data(user, "preventive_missing", missing)
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


async def _extract_meal_supplement_items(text: str) -> list[tuple[str, str]]:
    """Extract supplement-only items from meal details without hardcoded names."""
    client = _get_openai_onboarding_client()
    prompt = (
        "A pet parent shared their pet's meal details. Extract ONLY supplement items. "
        "Supplements include capsules/oils/powders/tablets/herbal add-ons and health "
        "support additives, even when mixed into food (like a measured pinch, drops, or dose). "
        "Do NOT include normal staple foods/meals. "
        "Return JSON only with format: "
        '{"supplements": [{"label": "short name", "detail": "dose/frequency or empty"}]}. '
        "If none found, return {\"supplements\": []}.\n\n"
        f"Meal text: {text}"
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=350,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        items = data.get("supplements", [])
        return [
            (item.get("label", "").strip(), (item.get("detail", "") or "").strip())
            for item in items
            if (item.get("label") or "").strip()
        ]
    except Exception as e:
        logger.warning("Meal supplement extraction failed: %s", str(e))
        return []


async def _store_meal_supplement_items(db, pet, meal_text: str) -> list[str]:
    """Persist supplement items inferred from meal-details response."""
    supplements = await _extract_meal_supplement_items(meal_text)
    stored_labels: list[str] = []
    for label, detail in supplements:
        try:
            await add_diet_item(db, pet.id, "supplement", label, detail or None)
            stored_labels.append(label)
        except Exception as e:
            logger.error("Failed to save meal-derived supplement for pet %s: %s", str(pet.id), str(e))
    return stored_labels


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
    normalized = re.sub(r"[.!?,]+$", "", text_lower)

    # Read onboarding data once at the top — needed in both skip and non-skip paths.
    od = _get_onboarding_data(user)

    # Even if skip / none, just proceed.
    if (
        normalized not in _SKIP_INPUTS
        and normalized not in _NONE_KEYWORDS
        and normalized not in _NO_INPUTS
    ):
        # Guard against late-arriving diet/supplement messages from prior steps.
        prior_classification = await _classify_prior_step_input(text, "awaiting_prev_retry")
        if prior_classification in ("food", "supplement"):
            missing = list(od.get("preventive_missing") or [])
            _MISSING_NAMES = {
                "vaccines": "vaccines",
                "deworming": "deworming",
                "flea_tick": "flea & tick treatment",
                "blood_test": "blood tests",
            }
            missing_str = " and ".join(_MISSING_NAMES.get(m, m) for m in missing)
            reask = (
                f"Got it, added that to {pet.name}'s "
                f"{'diet' if prior_classification == 'food' else 'supplements'}. "
            ) + (f"What about {missing_str}?" if missing_str else "Any other preventive care details?")
            await _save_prior_step_dietary_input(
                db, user, pet, text, prior_classification, send_fn, reask
            )
            return

        # Pass the missing categories as context so GPT can attribute an ambiguous
        # positive reply (e.g. "done this month") to the right categories.
        missing_context = list(od.get("preventive_missing") or [])
        _CONTEXT_NAMES = {
            "vaccines": "vaccines",
            "deworming": "deworming",
            "flea_tick": "flea & tick treatment",
            "blood_test": "blood tests",
        }
        context_labels = [_CONTEXT_NAMES.get(m, m) for m in missing_context]
        parsed = await _parse_preventive_care(text, context_categories=context_labels or None)

        # Apply the same generic vaccine / flea-without-brand detection as
        # in _step_preventive, but since this is the final retry step we
        # don't loop — vaccine type and flea brand questions still apply.
        needs_vaccine_type_q = _is_generic_vaccine_mention(parsed)
        needs_flea_brand_q = _is_flea_without_brand(parsed)

        if needs_vaccine_type_q:
            _set_onboarding_data(user, "pending_preventive_parsed", parsed)
            _set_onboarding_data(user, "pending_flea_brand_needed", needs_flea_brand_q)
            _set_onboarding_data(user, "preventive_missing", [])
            _set_onboarding_data(user, "preventive_attempts", 1)
            user.onboarding_state = "awaiting_vaccine_type"
            db.commit()
            await send_fn(db, mobile, _vaccine_type_question(pet.name))
            return

        if needs_flea_brand_q:
            _set_onboarding_data(user, "pending_preventive_parsed", parsed)
            _set_onboarding_data(user, "pending_flea_brand_needed", True)
            _set_onboarding_data(user, "preventive_missing", [])
            _set_onboarding_data(user, "preventive_attempts", 1)
            user.onboarding_state = "awaiting_flea_brand"
            db.commit()
            await send_fn(db, mobile, _flea_brand_question(pet.name))
            return

        ambiguous = await _store_preventive_data(db, pet, parsed)

        # If user mentioned categories but date was unparseable, ask once for a
        # clearer date.  The `preventive_date_clarify_sent` flag prevents looping.
        date_clarify_sent = od.get("preventive_date_clarify_sent", False)
        if ambiguous and not date_clarify_sent:
            _set_onboarding_data(user, "preventive_date_clarify_sent", True)
            db.commit()
            _AMB_NAMES = {
                "vaccines": "vaccines",
                "deworming": "deworming",
                "flea_tick": "flea & tick treatment",
                "blood_test": "blood tests",
            }
            amb_str = " and ".join(_AMB_NAMES.get(k, k) for k in ambiguous)
            await send_fn(
                db, mobile,
                f"Got it — just need a clearer date for {amb_str}. "
                f"Could you share it as 'Month YYYY'? E.g., 'April 2026' or 'March 2026'.",
            )
            return  # stay in awaiting_prev_retry; next reply re-enters this handler

    await _transition_to_documents(db, user, pet, send_fn)


# ---------------------------------------------------------------------------
# Vaccine type selection helpers (new vaccine-specific question flow)
# ---------------------------------------------------------------------------

_GENERIC_VAX_LABELS: frozenset[str] = frozenset({
    "vaccine", "vaccines", "shot", "shots", "jab", "jabs",
    "vaccinated", "vaccination", "annual vaccine", "annual vaccines",
})


def _is_generic_vaccine_mention(parsed: dict) -> bool:
    """
    Return True if the parsed data contains a generic vaccine mention with no
    specific vaccine name provided by the user.  In that case we must ask which
    vaccines their pet actually receives.

    Handles two scenarios:
    1. GPT correctly put the generic date in the top-level ``vaccines`` field and
       left ``vaccine_specifics`` empty (the normal case).
    2. GPT erroneously put a generic label (e.g. "vaccines", "shots") as an entry
       in ``vaccine_specifics`` instead of the top-level field — we still treat it
       as generic so the follow-up question is always asked.
    """
    generic = parsed.get("vaccines")
    vaccine_specifics = parsed.get("vaccine_specifics") or []

    # Case 1: top-level vaccines field is set — check there are no real specifics.
    if generic and generic != "none":
        real_specifics = [
            s for s in vaccine_specifics
            if isinstance(s, dict)
            and str(s.get("name") or "").strip().lower() not in _GENERIC_VAX_LABELS
            and str(s.get("date") or "").strip()
        ]
        return len(real_specifics) == 0

    # Case 2: vaccines field is null/none — check if vaccine_specifics has only
    # generic labels (GPT mis-classified a generic mention as a specific vaccine).
    generic_entries = [
        s for s in vaccine_specifics
        if isinstance(s, dict)
        and str(s.get("name") or "").strip().lower() in _GENERIC_VAX_LABELS
        and str(s.get("date") or "").strip()
    ]
    real_entries = [
        s for s in vaccine_specifics
        if isinstance(s, dict)
        and str(s.get("name") or "").strip().lower() not in _GENERIC_VAX_LABELS
        and str(s.get("date") or "").strip()
    ]
    return bool(generic_entries) and not real_entries


def _is_flea_without_brand(parsed: dict) -> bool:
    """
    Return True if GPT detected a flea/tick date but no medicine/brand name.
    In that case we must ask for the brand so reminders use the right interval.
    """
    flea_tick = parsed.get("flea_tick")
    if not flea_tick or flea_tick == "none":
        return False
    if isinstance(flea_tick, dict):
        date_val = (flea_tick.get("date") or "").strip()
        medicine = (flea_tick.get("medicine") or "").strip()
        return bool(date_val) and not medicine
    # Plain string date — no medicine.
    return bool(str(flea_tick).strip())


def _vaccine_type_question(pet_name: str) -> str:
    """Build the vaccine type selection question for the given pet name."""
    return (
        f"Which vaccines does {pet_name} receive?\n\n"
        f"(In India, Rabies and DHPPi are mandatory. Corona and Kennel Cough are "
        f"optional based on your vet's advice.)\n\n"
        f"Reply with:\n"
        f"1️⃣ Mandatory only (Rabies + DHPPi)\n"
        f"2️⃣ Mandatory + Corona\n"
        f"3️⃣ Mandatory + Kennel Cough\n"
        f"4️⃣ All four (Rabies, DHPPi, Corona, Kennel Cough)"
    )


def _puppy_vaccine_question(pet_name: str, age_weeks: float) -> str:
    """Build a vaccine question tuned for the puppy dose-series stage (< 52 weeks)."""
    if age_weeks < 10:
        return (
            f"Which DHPP dose has {pet_name} received so far?\n\n"
            f"The typical puppy vaccine schedule:\n"
            f"• 1st dose: 6–8 weeks\n"
            f"• 2nd booster: 10 weeks\n"
            f"• 3rd dose + Rabies: 14–16 weeks\n\n"
            f"Reply with:\n"
            f"1️⃣ 1st dose given\n"
            f"2️⃣ 1st + 2nd doses given\n"
            f"3️⃣ All three doses + Rabies completed\n"
            f"4️⃣ Not started yet"
        )
    if age_weeks < 16:
        return (
            f"Which vaccines has {pet_name} received?\n\n"
            f"At this age, the 3rd DHPP dose and first Rabies are typically due.\n\n"
            f"Reply with:\n"
            f"1️⃣ 1st dose only\n"
            f"2️⃣ 1st + 2nd doses\n"
            f"3️⃣ All three DHPP doses + Rabies completed\n"
            f"4️⃣ Not started yet"
        )
    # 16 weeks to < 1 year — series likely complete; use the standard question.
    return _vaccine_type_question(pet_name)


def _flea_brand_question(pet_name: str) -> str:
    """Build the flea/tick brand question for the given pet name."""
    return (
        f"Which brand do you use for flea and tick protection?\n\n"
        f"(This helps us set the frequency right — for example, if {pet_name} is on "
        f"*Simparica*, reminder will be set to every 2 months)\n\n"
        f"Reply with the brand name, or type *not sure* if you don't remember."
    )


_PENDING_VACCINE_PHRASES = (
    "should be given", "need to give", "needs to give", "not yet given",
    "not yet", "pending", "to be given", "yet to give", "yet to be given",
    "supposed to", "have to give", "has to be given", "will give", "will be given",
)


def _is_pending_vaccine_intent(raw: str | None) -> bool:
    """True if the user expressed a 'vaccines not yet given' intent rather than a date."""
    if not raw:
        return False
    n = str(raw).strip().lower()
    if not n:
        return False
    return any(phrase in n for phrase in _PENDING_VACCINE_PHRASES)


def _looks_like_vaccine_selection(text: str) -> bool:
    """Return True if the text is a deliberate vaccine type selection (options 1-4 or keywords).

    Used in _step_vaccine_type to distinguish a vaccine selection reply from
    additional free-text health data the user sends before answering the question.
    """
    t = text.strip().lower()
    t = re.sub(r"[.!?,]+$", "", t)

    # Explicit numeric options.
    never_keywords = {
        "never", "never done", "not vaccinated", "no vaccine", "no vaccines",
        "none", "nope", "n/a", "na", "skip", "not done", "not sure",
    }
    # Named vaccine-selection phrases.
    vaccine_phrases = {
        "mandatory", "mandatory only", "only mandatory",
        "rabies and dhppi", "rabies + dhppi", "dhppi and rabies",
        "mandatory + corona", "corona", "mandatory + coronavirus",
        "mandatory + kennel cough", "kennel cough", "mandatory + kennel",
        "all", "all four", "all 4", "all vaccines", "all four vaccines",
    }
    # Vaccine-name keywords present in the text.
    vaccine_keywords = any(kw in t for kw in ("kennel", "corona", "rabies", "dhppi", "bordetella"))

    return (
        t in {"1", "2", "3", "4"}
        or t in never_keywords
        or _is_pending_vaccine_intent(t)
        or t in vaccine_phrases
        or vaccine_keywords
    )


def _resolve_vaccine_type_selection(text: str) -> list[str]:
    """
    Map the user's reply to a list of vaccine master item_names to update.

    Returns [] if the user says they have not vaccinated (never done).
    Returns the appropriate list based on option 1–4 or keyword match.
    """
    t = text.strip().lower()
    t = re.sub(r"[.!?,]+$", "", t)

    # "Never done" / skip variants → no vaccines to record.
    never_keywords = {
        "never", "never done", "not vaccinated", "no vaccine", "no vaccines",
        "none", "nope", "n/a", "na", "skip", "not done", "not sure",
    }
    if t in never_keywords:
        return []

    # Pending intent ("mandatory vaccines should be given", "not yet", etc.)
    # always maps to Option 1 — the mandatory pair. Must come BEFORE the
    # other option checks since "should be given" contains no digit/keyword.
    if _is_pending_vaccine_intent(t):
        return ["Rabies Vaccine", "DHPPi"]

    # Option 4 — All four.
    if t in {"4", "all", "all four", "all 4", "all vaccines", "all four vaccines"}:
        return [
            "Rabies Vaccine",
            "DHPPi",
            "Canine Coronavirus (CCoV)",
            "Kennel Cough (Nobivac KC)",
        ]
    # Option 3 — Mandatory + Kennel Cough.
    if (
        t in {"3", "mandatory + kennel cough", "kennel cough", "mandatory + kennel"}
        or ("kennel" in t and "corona" not in t)
    ):
        return ["Rabies Vaccine", "DHPPi", "Kennel Cough (Nobivac KC)"]
    # Option 2 — Mandatory + Corona.
    if (
        t in {"2", "mandatory + corona", "corona", "mandatory + coronavirus"}
        or ("corona" in t and "kennel" not in t)
    ):
        return ["Rabies Vaccine", "DHPPi", "Canine Coronavirus (CCoV)"]
    # Option 1 — Mandatory only (default / most common).
    if t in {
        "1", "mandatory", "mandatory only", "only mandatory",
        "rabies and dhppi", "rabies + dhppi", "dhppi and rabies",
    }:
        return ["Rabies Vaccine", "DHPPi"]

    # If all four keywords present, treat as option 4.
    if "kennel" in t and "corona" in t:
        return [
            "Rabies Vaccine",
            "DHPPi",
            "Canine Coronavirus (CCoV)",
            "Kennel Cough (Nobivac KC)",
        ]

    # Default fallback — mandatory only.
    return ["Rabies Vaccine", "DHPPi"]


async def _step_vaccine_type(db, user, text, send_fn):
    """
    Handle the user's vaccine type selection reply.

    Reads the pending parsed data from onboarding_data, applies the selected
    vaccine list, then either asks the flea brand question or stores data and
    transitions to documents.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)
    if not pet:
        user.onboarding_state = "welcome"
        db.commit()
        await send_fn(db, mobile, "Something went wrong. Let's start — what's your pet's name?")
        return

    od = _get_onboarding_data(user)
    parsed = dict(od.get("pending_preventive_parsed") or {})
    flea_brand_needed = od.get("pending_flea_brand_needed", False)
    missing = od.get("preventive_missing", [])
    attempts = od.get("preventive_attempts", 0)

    # If the user sent additional health data instead of a vaccine selection, parse and
    # merge it, then re-ask the vaccine type question — never silently discard health info.
    if not _looks_like_vaccine_selection(text):
        # Guard: detect late-arriving diet/supplement before attempting preventive merge.
        prior_classification = await _classify_prior_step_input(text, "awaiting_vaccine_type")
        if prior_classification in ("food", "supplement"):
            reask = (
                f"Got it, added that to {pet.name}'s "
                f"{'diet' if prior_classification == 'food' else 'supplements'}. "
                + _vaccine_type_question(pet.name)
            )
            await _save_prior_step_dietary_input(
                db, user, pet, text, prior_classification, send_fn, reask
            )
            return

        additional = await _parse_preventive_care(text)
        for key in ("deworming", "flea_tick", "blood_test"):
            if additional.get(key) and parsed.get(key) is None:
                parsed[key] = additional[key]
        # Recalculate missing: remove categories now present in parsed.
        missing = [cat for cat in missing if parsed.get(cat) is None]
        needs_flea_brand_q = _is_flea_without_brand(parsed)
        _set_onboarding_data(user, "pending_preventive_parsed", parsed)
        _set_onboarding_data(user, "pending_flea_brand_needed", needs_flea_brand_q)
        _set_onboarding_data(user, "preventive_missing", missing)
        db.commit()
        await send_fn(db, mobile, _vaccine_type_question(pet.name))
        return

    # Resolve which vaccine names the user selected.
    vaccine_names = _resolve_vaccine_type_selection(text)
    parsed["vaccine_names_to_update"] = vaccine_names

    if flea_brand_needed:
        # Store updated parsed data and ask flea brand question next.
        _set_onboarding_data(user, "pending_preventive_parsed", parsed)
        _set_onboarding_data(user, "pending_flea_brand_needed", True)
        _set_onboarding_data(user, "preventive_missing", missing)
        _set_onboarding_data(user, "preventive_attempts", attempts)
        user.onboarding_state = "awaiting_flea_brand"
        db.commit()
        await send_fn(db, mobile, _flea_brand_question(pet.name))
        return

    # No flea brand needed — store and proceed.
    ambiguous = await _store_preventive_data(db, pet, parsed)
    # Treat ambiguous like missing so they get re-asked in the retry step.
    for key in ambiguous:
        if key not in missing:
            missing.append(key)

    if missing and attempts < 1:
        _set_onboarding_data(user, "preventive_attempts", 1)
        user.onboarding_state = "awaiting_prev_retry"
        db.commit()
        missing_names = {
            "vaccines": "vaccines",
            "deworming": "deworming",
            "flea_tick": "flea & tick treatment",
            "blood_test": "blood tests",
        }
        missing_readable = [missing_names.get(m, m) for m in missing]
        missing_str = " and ".join(missing_readable)
        await send_fn(db, mobile, f"Got it! What about {missing_str}?")
        return

    await _transition_to_documents(db, user, pet, send_fn)


async def _step_flea_brand(db, user, text, send_fn):
    """
    Handle the user's flea/tick brand reply.

    Reads the pending parsed data, injects the brand into flea_tick.medicine,
    stores all preventive data, then transitions to documents.
    """
    mobile = user._plaintext_mobile
    pet = _get_pending_pet(db, user.id)
    if not pet:
        user.onboarding_state = "welcome"
        db.commit()
        await send_fn(db, mobile, "Something went wrong. Let's start — what's your pet's name?")
        return

    od = _get_onboarding_data(user)
    parsed = dict(od.get("pending_preventive_parsed") or {})
    missing = od.get("preventive_missing", [])
    attempts = od.get("preventive_attempts", 0)

    # Guard against late-arriving diet/supplement messages from prior steps.
    prior_classification = await _classify_prior_step_input(text, "awaiting_flea_brand")
    if prior_classification in ("food", "supplement"):
        reask = (
            f"Got it, added that to {pet.name}'s "
            f"{'diet' if prior_classification == 'food' else 'supplements'}. "
            + _flea_brand_question(pet.name)
        )
        await _save_prior_step_dietary_input(
            db, user, pet, text, prior_classification, send_fn, reask
        )
        return

    # Inject brand into flea_tick entry (unless user said "not sure").
    brand = text.strip()
    skip_keywords = {"not sure", "don't know", "dont know", "no idea", "skip", "n/a", "na"}
    if brand.lower() not in skip_keywords and brand:
        flea_tick = parsed.get("flea_tick")
        if isinstance(flea_tick, dict):
            flea_tick["medicine"] = brand
            parsed["flea_tick"] = flea_tick
        elif isinstance(flea_tick, str) and flea_tick and flea_tick != "none":
            # Convert plain-string date to dict form with medicine.
            parsed["flea_tick"] = {"date": flea_tick, "medicine": brand}

    ambiguous = await _store_preventive_data(db, pet, parsed)
    # Treat ambiguous like missing so they get re-asked in the retry step.
    for key in ambiguous:
        if key not in missing:
            missing.append(key)

    if missing and attempts < 1:
        _set_onboarding_data(user, "preventive_attempts", 1)
        user.onboarding_state = "awaiting_prev_retry"
        db.commit()
        missing_names = {
            "vaccines": "vaccines",
            "deworming": "deworming",
            "flea_tick": "flea & tick treatment",
            "blood_test": "blood tests",
        }
        missing_readable = [missing_names.get(m, m) for m in missing]
        missing_str = " and ".join(missing_readable)
        await send_fn(db, mobile, f"Got it! What about {missing_str}?")
        return

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


def _upsert_pending_preventive_record(db, pet, master) -> None:
    """
    Create a PreventiveRecord representing 'not yet done' — due today.

    Used when the user expresses pending-vaccine intent (e.g. "mandatory
    vaccines should be given") without providing a date. Idempotent: if a
    record already exists and has a real last_done_date, leave it alone.
    Caller is responsible for committing.
    """
    from datetime import date as _date

    from app.services.preventive_calculator import compute_status

    reminder_before_days = master.reminder_before_days or 30
    today = _date.today()

    existing = (
        db.query(PreventiveRecord)
        .filter(
            PreventiveRecord.pet_id == pet.id,
            PreventiveRecord.preventive_master_id == master.id,
        )
        .first()
    )
    if existing:
        if existing.last_done_date:
            # Real record already exists — do not downgrade it.
            return
        existing.next_due_date = today
        existing.status = compute_status(today, reminder_before_days)
        return

    db.add(
        PreventiveRecord(
            pet_id=pet.id,
            preventive_master_id=master.id,
            last_done_date=None,
            next_due_date=today,
            status=compute_status(today, reminder_before_days),
        )
    )


def _normalize_custom_vaccine_name(name: str | None) -> str:
    """Normalize a user-mentioned custom vaccine label for persistence."""
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    return cleaned[:120]


def _prefer_user_scoped_custom_vaccine(name: str | None) -> bool:
    """Return True when a vaccine should be stored as a user-scoped custom item."""
    normalized = (name or "").strip().lower()
    # Combo labels like 5-in-1/7-in-1 are user phrasing and should not fan out
    # into shared core masters unless explicitly mapped by product evidence.
    return not normalized or bool(re.search(r"\b\d+\s*[- ]?in\s*[- ]?1\b", normalized))


def _upsert_user_custom_vaccine_record(db: Session, pet: Pet, vaccine_name: str, parsed_date: date) -> None:
    """Create/update a per-user custom vaccine item and pet preventive record."""
    from app.services.preventive_calculator import compute_next_due_date, compute_status

    custom_name = _normalize_custom_vaccine_name(vaccine_name)
    if not custom_name:
        return

    custom_item = (
        db.query(CustomPreventiveItem)
        .filter(
            CustomPreventiveItem.user_id == pet.user_id,
            func.lower(CustomPreventiveItem.item_name) == custom_name.lower(),
            CustomPreventiveItem.species == pet.species,
        )
        .first()
    )
    if custom_item is None:
        custom_item = CustomPreventiveItem(
            user_id=pet.user_id,
            item_name=custom_name,
            category="complete",
            circle="health",
            species=pet.species,
            recurrence_days=365,
            medicine_dependent=False,
            reminder_before_days=30,
            overdue_after_days=14,
        )
        db.add(custom_item)
        db.flush()

    recurrence_days = custom_item.recurrence_days or 365
    reminder_before_days = custom_item.reminder_before_days or 30
    next_due = compute_next_due_date(parsed_date, recurrence_days)
    status = compute_status(next_due, reminder_before_days)

    existing = (
        db.query(PreventiveRecord)
        .filter(
            PreventiveRecord.pet_id == pet.id,
            PreventiveRecord.custom_preventive_item_id == custom_item.id,
        )
        .first()
    )
    if existing:
        if not existing.last_done_date or parsed_date > existing.last_done_date:
            existing.last_done_date = parsed_date
            existing.next_due_date = next_due
            existing.status = status
        return

    db.add(
        PreventiveRecord(
            pet_id=pet.id,
            custom_preventive_item_id=custom_item.id,
            last_done_date=parsed_date,
            next_due_date=next_due,
            status=status,
        )
    )


def _essential_annual_vaccine_masters(db: Session, species: str) -> list[PreventiveMaster]:
    """
    Return recurring annual core-vaccine masters for the species.

    Generic onboarding inputs like "vaccines last Dec" should only fan out
    to canonical core vaccines, never optional vaccines.

    Primary selection requires both:
      - canonical core vaccine name
      - is_core = TRUE

    Fallback keeps canonical-name protection even if is_core flags are stale.
    """
    canonical_core_vaccines = {
        "rabies vaccine",
        "rabies (nobivac rl)",
        "dhppi",
        "dhppi (nobivac)",
        "kennel cough (nobivac kc)",
        "canine coronavirus (ccov)",
    }

    rows = (
        db.query(PreventiveMaster)
        .filter(
            PreventiveMaster.species.in_([species, "both"]),
            PreventiveMaster.circle == "health",
            PreventiveMaster.recurrence_days <= 730,
        )
        .all()
    )

    core_vaccines = [
        m
        for m in rows
        if bool(m.is_core)
        and (m.item_name or "").strip().lower() in canonical_core_vaccines
    ]
    if core_vaccines:
        return core_vaccines

    # Fallback for environments where is_core flags are stale/missing.
    fallback = [
        m
        for m in rows
        if (m.item_name or "").strip().lower() in canonical_core_vaccines
    ]
    if fallback:
        logger.warning(
            "Core-vaccine fallback used for species=%s; verify preventive_master.is_core flags",
            species,
        )
    return fallback


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
            PreventiveMaster.is_core.is_(True),
        )
        .order_by(
            case(
                (PreventiveMaster.species == species, 0),
                else_=1,
            ),
            PreventiveMaster.id.asc(),
        )
        .first()
    )


def _infer_preventive_categories_from_catalog(db: Session, medicine_name: str | None) -> set[str]:
    """Legacy catalog-backed category inference.

    The product_catalog table (which held deworming/flea_tick medicine
    rows) was dropped as part of the cart-rules-engine rebuild. This
    helper now always returns an empty set so callers fall back to
    their existing heuristics / GPT-driven inference.
    """
    return set()


def _enrich_preventive_categories_from_catalog(db: Session, parsed: dict) -> dict:
    """Backfill missing deworming/flea_tick buckets from catalog-inferred categories."""
    normalized = dict(parsed or {})

    def _copy_bucket(target_key: str, source_value: dict) -> None:
        existing = normalized.get(target_key)
        if isinstance(existing, dict):
            if not existing.get("date") and source_value.get("date"):
                existing["date"] = source_value.get("date")
            if not existing.get("medicine") and source_value.get("medicine"):
                existing["medicine"] = source_value.get("medicine")
            return
        normalized[target_key] = {
            "date": source_value.get("date"),
            "medicine": source_value.get("medicine"),
            "prevention_targets": source_value.get("prevention_targets") or [],
        }

    for source_key in ("deworming", "flea_tick"):
        source_value = normalized.get(source_key)
        if not isinstance(source_value, dict):
            continue

        categories = _infer_preventive_categories_from_catalog(db, source_value.get("medicine"))
        if "deworming" in categories:
            _copy_bucket("deworming", source_value)
        if "flea_tick" in categories:
            _copy_bucket("flea_tick", source_value)

    return normalized


def _ensure_preventive_master_seeded_for_store() -> None:
    """Best-effort preventive_master self-heal in isolated DB session."""
    seed_db = get_fresh_session()
    try:
        seed_preventive_master(seed_db)
    except SQLAlchemyError as e:
        try:
            seed_db.rollback()
        except Exception as rollback_err:
            logger.debug("Preventive seeding rollback failed: %s", str(rollback_err))
        logger.warning("Preventive master self-heal seeding failed: %s", str(e), exc_info=True)
    except Exception as e:
        try:
            seed_db.rollback()
        except Exception as rollback_err:
            logger.debug("Preventive seeding rollback failed: %s", str(rollback_err))
        logger.warning("Unexpected preventive seeding failure: %s", str(e), exc_info=True)
    finally:
        try:
            seed_db.close()
        except Exception as close_err:
            logger.debug("Preventive seeding session close failed: %s", str(close_err))


async def _store_preventive_data(db, pet, parsed: dict) -> list[str]:
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

    Returns a list of category keys (e.g. ["flea_tick", "blood_test"]) where
    the user provided a non-null value but the date could not be parsed.
    Callers can use this to ask a targeted clarification rather than silently
    dropping the data.
    """
    # Self-heal before lookups if preventive_master was truncated or partly missing.
    # Runs in a separate session so onboarding transaction boundaries stay intact.
    _ensure_preventive_master_seeded_for_store()

    has_species_masters = (
        db.query(PreventiveMaster.id)
        .filter(PreventiveMaster.species.in_([pet.species, "both"]))
        .first()
        is not None
    )
    if not has_species_masters:
        logger.error(
            "Preventive master unavailable for species=%s; skipping preventive persistence for pet_id=%s",
            pet.species,
            str(pet.id),
        )
        return []

    parsed = _enrich_preventive_categories_from_catalog(db, parsed)

    # Tracks categories where user provided a value but date could not be parsed.
    ambiguous: list[str] = []

    # --- Generic vaccine mention → update all essential annual vaccines ---
    # If user provided specific vaccine name+date entries, do NOT fan out the
    # generic value to all vaccines. This keeps chat behavior precise:
    # specific mention updates only that vaccine.
    specific_with_dates = [
        spec
        for spec in (parsed.get("vaccine_specifics") or [])
        if isinstance(spec, dict) and str(spec.get("name") or "").strip() and str(spec.get("date") or "").strip()
    ]

    generic = parsed.get("vaccines")
    vaccine_names_to_update = parsed.get("vaccine_names_to_update")  # Set by vaccine type Q&A
    if generic and generic != "none" and not specific_with_dates:
        gen_date = await _parse_preventive_date_value(generic, pet)
        if gen_date:
            if vaccine_names_to_update is not None:
                # User was asked which vaccines — only update the ones they selected.
                for vname in vaccine_names_to_update:
                    master = _match_specific_vaccine_master(db, pet.species, vname)
                    if master:
                        _upsert_preventive_record(db, pet, master, gen_date)
                    else:
                        logger.warning(
                            "No master found for selected vaccine '%s' species=%s",
                            vname, pet.species,
                        )
            else:
                # Legacy path: no vaccine type Q&A ran — fan out to all essential vaccines.
                masters = _essential_annual_vaccine_masters(db, pet.species)
                if not masters:
                    logger.warning(
                        "No essential annual vaccine masters found for species=%s",
                        pet.species,
                    )
                for master in masters:
                    _upsert_preventive_record(db, pet, master, gen_date)
        elif _is_pending_vaccine_intent(generic) and vaccine_names_to_update:
            # User expressed "not yet given" intent without a date → create
            # pending records (last_done_date=NULL, next_due=today) for the
            # selected vaccines so they surface as overdue on the dashboard.
            logger.info(
                "Pending vaccine intent detected for pet_id=%s; creating pending records for %s",
                str(pet.id), vaccine_names_to_update,
            )
            for vname in vaccine_names_to_update:
                master = _match_specific_vaccine_master(db, pet.species, vname)
                if master:
                    _upsert_pending_preventive_record(db, pet, master)
                else:
                    logger.warning(
                        "No master for selected vaccine '%s' species=%s",
                        vname, pet.species,
                    )
        else:
            # User mentioned vaccines but the date couldn't be parsed — flag for clarification.
            ambiguous.append("vaccines")

    # --- Specific vaccines → update only the named master(s) ---
    for spec in parsed.get("vaccine_specifics") or []:
        if not isinstance(spec, dict):
            continue
        raw_vaccine_name = str(spec.get("name") or "").strip()
        if not raw_vaccine_name:
            continue
        master = None
        if not _prefer_user_scoped_custom_vaccine(raw_vaccine_name):
            master = _match_specific_vaccine_master(db, pet.species, raw_vaccine_name)
        spec_date = await _parse_preventive_date_value(spec.get("date") or "", pet)
        if spec_date:
            if master is not None:
                _upsert_preventive_record(db, pet, master, spec_date)
            else:
                _upsert_user_custom_vaccine_record(db, pet, raw_vaccine_name, spec_date)

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
            # User mentioned this category but the date couldn't be parsed.
            # Track it so callers can ask a targeted clarification.
            ambiguous.append(key)
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

    return ambiguous


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

    now_ts = datetime.now(UTC).timestamp()
    _set_onboarding_data(user, "awaiting_docs_prompt_at", now_ts)
    _set_onboarding_data(user, "awaiting_docs_last_reply_at", now_ts)
    _set_onboarding_data(user, "awaiting_docs_last_reply_text", "upload_prompt")
    db.commit()

    await send_fn(
        db, mobile,
        "Do you have any health records handy — a vaccination card, vet prescription, "
        "or lab report? Share a photo or PDF and I'll pull the "
        "details in automatically. No worries if not, we can always add them later.",
    )


async def _ai_clarify_input(
    user_message: str,
    step_context: str,
    expected_format: str,
    pet_name: str = "your pet",
    prior_assistant_message: str = "",
    next_step_description: str = "",
) -> str:
    """
    Use GPT to generate a friendly clarifying question when user input
    doesn't match the expected format for the current onboarding step.

    The LLM is given the surrounding conversational context — the previous
    assistant message, what the current step collects, and what happens
    next — so the clarification is phrased in a way that makes sense in the
    flow rather than in isolation.

    Args:
        user_message: The user's original message that couldn't be parsed.
        step_context: Description of what information is being collected (current step purpose).
        expected_format: Examples of valid input for this step.
        pet_name: The pet's name for personalization.
        prior_assistant_message: The assistant's previous message (the question the user was
            replying to). Helps the LLM understand the user's reply relative to what was asked.
        next_step_description: Short description of what comes after the current step,
            so the LLM can frame the clarification without contradicting the flow.

    Returns:
        A friendly, concise clarifying question (AI-generated).
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "You are a friendly pet care assistant on WhatsApp helping a user register their pet. "
        f"The user's pet is named {pet_name}.\n\n"
        "CONTEXT (use to interpret the user's reply in relation to the flow):\n"
        f"- Previous assistant message: \"{prior_assistant_message or '(not available)'}\"\n"
        f"- Current step purpose: {step_context}\n"
        f"- What happens next if the user moves on: {next_step_description or '(not specified)'}\n"
        f"- Expected input format/examples: {expected_format}\n\n"
        f"The user replied: \"{user_message}\"\n\n"
        "Their reply doesn't clearly match what's needed. Interpret their meaning against "
        "the previous assistant message and the next step before phrasing your clarification. "
        "Generate a short, clear clarifying question (1-2 sentences max) that:\n"
        "- Starts by saying you didn't fully understand/catch their reply\n"
        "- Does NOT sound congratulatory or appreciative (avoid phrases like 'Great', 'Awesome', 'Thanks for sharing', 'Got it')\n"
        "- Gently asks for the specific information needed\n"
        "- If you include an example, reuse the same pattern/topic as the expected_format above (do not switch to a different style)\n"
        "- Uses a conversational WhatsApp tone (not formal)\n"
        "- Does NOT use emojis excessively (max 1)\n\n"
        "Return ONLY the clarifying message text, nothing else."
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )
        clarification = response.content[0].text.strip()
        if clarification:
            return clarification
    except Exception as e:
        logger.warning("AI clarification failed: %s", str(e))

    # Fallback to a generic re-ask if AI fails.
    return (
        "I didn't quite catch that. Could you share it in this format: "
        f"{expected_format}"
    )


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
    # Partial match for "same as ..." patterns.
    return normalized in _SAME_AS_EXAMPLE_PHRASES or (normalized.startswith("same") and len(normalized) < 30)


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
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
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
    """
    Store parsed diet items for a pet.

    Rules by food_type:
    - "packaged": Only brand items saved (non-brand ingredients dropped).
    - "home": All items saved as homemade type, regardless of kind.
    - "mix": All items saved — brands as packaged, home-cooked as homemade (by keyword).

    This ensures all food the user describes is persisted to the DB.
    """
    for entry in items:
        # Support both new (label, detail, kind) triples and legacy (label, detail) tuples.
        if len(entry) == 3:
            label, detail, kind = entry
        else:
            label, detail = entry
            kind = "brand"  # Legacy callers — assume brand.

        label_lower = label.lower()

        # Determine item type: packaged or homemade
        is_homemade_keyword = any(kw in label_lower for kw in HOMEMADE_KW)
        item_type = food_type if food_type != "mix" else "packaged"
        if is_homemade_keyword or food_type == "home":
            item_type = "homemade"

        # Skip non-brand items only for pure packaged food (no home component).
        # For "home" and "mix" food types, save all items — the user explicitly
        # described what their pet eats, including home-cooked ingredients.
        if kind != "brand" and food_type == "packaged":
            logger.debug(
                "Dropping non-brand diet item for pet_id=%s: label=%r kind=%r (packaged food only allows brands)",
                str(pet.id), label, kind,
            )
            continue

        try:
            await add_diet_item(db, pet.id, item_type, label, detail or None)
        except Exception as e:
            logger.error("Failed to save diet item for pet %s: %s", str(pet.id), str(e))


async def _ai_is_food_not_supplement(text: str) -> bool:
    """
    Use GPT to decide if the text describes regular food/meal items (not supplements).

    Called in the supplements step to catch late-arriving meal messages — e.g. a user
    who typed their diet across multiple messages where the second message arrives after
    the state has already advanced to awaiting_supplements.

    Returns True  → the text is food/meal (treat as additional diet, re-ask supplements).
    Returns False → the text is a supplement, "none", or ambiguous (proceed normally).
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "A pet parent was asked: 'Is your pet on any supplements right now? "
        "(e.g., joint support, Omega-3, calcium — or just say None)'\n"
        f"They replied: \"{text}\"\n\n"
        "Determine if this reply describes regular food or meal items (eggs, chicken, "
        "curd, kibble, rice, vegetables, etc.) rather than health supplements "
        "(capsules, oils, powders, tablets, Omega-3, probiotics, joint support, etc.).\n\n"
        "Answer YES if the reply is clearly food/meals with no supplement content.\n"
        "Answer NO if it mentions supplements, says none/no/skip, or is ambiguous.\n\n"
        'Return ONLY valid JSON: {"is_food": true|false}'
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        return bool(data.get("is_food", False))
    except Exception as e:
        logger.warning("AI supplement-vs-food check failed: %s", str(e))
        return False  # Default: treat as supplement answer to avoid blocking the flow.


async def _classify_prior_step_input(text: str, current_step: str) -> str:
    """
    Classify whether text belongs to a prior onboarding step rather than the current one.

    Used from awaiting_preventive onwards to catch late-arriving diet or supplement
    messages — e.g. a user who types across multiple WhatsApp messages where a later
    message arrives after state has already advanced past the diet steps.

    Returns:
        "food"       — text is regular food/meal (belongs to awaiting_meal_details)
        "supplement" — text is a health supplement (belongs to awaiting_supplements)
        "on_topic"   — text appears to address the current step (default on failure)
    """
    _STEP_CONTEXT = {
        "awaiting_preventive": (
            "the pet's vaccination, deworming, flea & tick treatment, and blood test history"
        ),
        "awaiting_prev_retry": (
            "any remaining vaccination, deworming, flea & tick, or blood test information"
        ),
        "awaiting_vaccine_type": (
            "which type of vaccine the pet received (e.g. Rabies, DHPP, Bordetella)"
        ),
        "awaiting_flea_brand": (
            "the brand/name of flea & tick treatment the pet uses (e.g. Simparica, NexGard)"
        ),
        "awaiting_documents": "uploading or skipping vaccine/vet documents",
    }
    step_context = _STEP_CONTEXT.get(current_step, "the current onboarding question")
    client = _get_openai_onboarding_client()
    prompt = (
        f"During pet onboarding, the current question is about: {step_context}.\n"
        f"The user replied: \"{text}\"\n\n"
        "The user might have sent this message late — it could belong to an earlier "
        "question about diet or supplements. Classify this reply:\n"
        "- 'food': clearly describes regular food or meal items a pet eats "
        "(kibble, chicken, rice, eggs, vegetables, curd, etc.) — NOT health supplements\n"
        "- 'supplement': clearly describes a DIETARY supplement the pet takes "
        "(Omega-3, joint support, probiotics, calcium, fish oil capsule, multivitamin, etc.) "
        "— NOT regular food, and NOT preventive care medicines. "
        "IMPORTANT: flea/tick treatments (Simparica, NexGard, Bravecto, Frontline, Credelio, "
        "Seresto, Advantix, Revolution, Advocate, Fipronil) and deworming medicines "
        "(Drontal, Milbemax, Panacur, Prazitel, Verminator, Ivermectin, Fenbendazole, "
        "Pyrantel, Albendazole) are NOT dietary supplements — classify these as 'on_topic'.\n"
        "- 'on_topic': appears to address the current question, mentions preventive care "
        "(flea/tick treatment, deworming, vaccines, blood tests), OR is ambiguous\n\n"
        "Only return 'food' or 'supplement' when CERTAIN it is diet-related. "
        "Default to 'on_topic' if unsure.\n\n"
        'Return ONLY valid JSON: {"classification": "food"|"supplement"|"on_topic"}'
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        classification = data.get("classification", "on_topic")
        if classification not in ("food", "supplement", "on_topic"):
            return "on_topic"
        return classification
    except Exception as e:
        logger.warning("Prior-step input classification failed: %s", str(e))
        return "on_topic"  # Default: treat as on-topic to avoid blocking the flow.


async def _save_prior_step_dietary_input(
    db,
    user,
    pet,
    text: str,
    classification: str,
    send_fn,
    reask_message: str,
) -> None:
    """
    Persist a late-arriving diet or supplement message from a prior onboarding step,
    then re-ask the current step's question so the user can still answer it.

    Args:
        classification: "food" or "supplement" (as returned by _classify_prior_step_input).
        reask_message:  The question text to send after saving.
    """
    mobile = user._plaintext_mobile
    od = _get_onboarding_data(user)
    food_type = od.get("food_type", "mix")

    if classification == "food":
        extra_items = await _parse_diet_input(text)
        await _store_meal_items(db, pet, extra_items, food_type)
        # Also persist any supplement hidden inside the food message.
        extra_supp_labels = await _store_meal_supplement_items(db, pet, text)
        existing_labels = list(od.get("meal_supplement_labels") or [])
        _set_onboarding_data(
            user, "meal_supplement_labels", existing_labels + extra_supp_labels
        )
    else:  # supplement
        items = await _parse_diet_input(text)
        for entry in items:
            label = entry[0]
            detail = entry[1] if len(entry) > 1 else ""
            try:
                await add_diet_item(db, pet.id, "supplement", label, detail or None)
            except Exception as e:
                logger.error(
                    "Failed to save supplement for pet %s: %s", str(pet.id), str(e)
                )

    db.commit()
    await send_fn(db, mobile, reask_message)


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
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
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
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        result = data.get("food_type")
        if result in ("home", "packaged", "mix"):
            logger.info("AI parsed food type '%s' from input '%s': %s", result, text, data.get("reasoning", ""))
            return result
        return None
    except Exception as e:
        logger.warning("AI food type parse failed: %s", str(e))
        return None


async def _parse_diet_input(text: str) -> list[tuple[str, str, str]]:
    """
    Use GPT to extract structured diet items from free-text input.

    Returns a list of (label, detail, kind) triples where kind is one of:
      - "brand" — a recognizable commercial brand or product name
      - "ingredient" — raw/homemade ingredient or generic food name
      - "generic_treat" — a treat with no brand identifier

    Callers that want brand-only storage (diet flow) must filter kind == "brand".
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "Extract pet food/supplement items from the user's message. "
        "For EACH item, classify it with a 'kind' field:\n"
        "- \"brand\": a recognizable commercial brand or product name "
        "(e.g. Royal Canin, Pedigree, Pedigree Dentastix, Whiskas, Drools, "
        "Drools Calcium Bone, Farmina, Orijen, Hill's Science Diet, Acana, "
        "Nutro, Purina Pro Plan, IAMS, Taste of the Wild)\n"
        "- \"ingredient\": any raw ingredient, homemade food, or generic food name "
        "(chicken, rice, egg, fish, carrots, dal, curd rice, boiled chicken, "
        "home food, paneer, roti, milk, yogurt, bread)\n"
        "- \"generic_treat\": a treat with no brand identifier "
        "(e.g. \"small treat\", \"biscuit\", \"snack\", \"chew\")\n\n"
        "Be STRICT. If you cannot clearly identify a commercial brand or product "
        "name, classify as \"ingredient\" or \"generic_treat\". Do not guess.\n\n"
        "Examples:\n"
        "  Input: \"chicken, royal canin, small treat\"\n"
        "  Output: [{\"label\":\"chicken\",\"detail\":\"\",\"kind\":\"ingredient\"}, "
        "{\"label\":\"Royal Canin\",\"detail\":\"\",\"kind\":\"brand\"}, "
        "{\"label\":\"small treat\",\"detail\":\"\",\"kind\":\"generic_treat\"}]\n"
        "  Input: \"Pedigree Dentastix and rice\"\n"
        "  Output: [{\"label\":\"Pedigree Dentastix\",\"detail\":\"\",\"kind\":\"brand\"}, "
        "{\"label\":\"rice\",\"detail\":\"\",\"kind\":\"ingredient\"}]\n"
        "  Input: \"boiled chicken and carrots\"\n"
        "  Output: [{\"label\":\"boiled chicken\",\"detail\":\"\",\"kind\":\"ingredient\"}, "
        "{\"label\":\"carrots\",\"detail\":\"\",\"kind\":\"ingredient\"}]\n"
        "  Input: \"Drools Calcium Bone\"\n"
        "  Output: [{\"label\":\"Drools Calcium Bone\",\"detail\":\"\",\"kind\":\"brand\"}]\n\n"
        "Return ONLY valid JSON in this exact shape (no markdown):\n"
        "{\"items\":[{\"label\":\"...\",\"detail\":\"...\",\"kind\":\"brand|ingredient|generic_treat\"}]}\n\n"
        f"User message: {text}"
    )

    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        items = data.get("items", [])
        result: list[tuple[str, str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            detail = str(item.get("detail") or "").strip()
            kind = str(item.get("kind") or "").strip().lower()
            if kind not in ("brand", "ingredient", "generic_treat"):
                kind = "ingredient"  # Strict fallback: unknown → dropped downstream.
            result.append((label, detail, kind))
        return result
    except Exception as e:
        logger.warning("Diet GPT parse failed, using raw text: %s", str(e))
        # On parse failure, mark as ingredient so diet flow drops it (strict mode).
        return [(text.strip(), "", "ingredient")]


def _strip_json_fences(raw: str) -> str:
    """Strip markdown code fences from a model JSON response.

    Also handles the case where the model prepends explanatory text before the
    JSON object (e.g. "Here is the result:\n{...}"), which causes json.loads to
    fail with JSONDecodeError at char 0.  After fence-stripping, if the result
    does not start with '{', we scan for the outermost { ... } pair and extract
    only that portion.

    Raises ValueError when no JSON object can be found in the response.
    """
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    # If there is non-JSON preamble, extract the first complete JSON object.
    if raw and not raw.startswith("{"):
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start : end + 1]
    if not raw:
        raise ValueError("Claude returned an empty response body")
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


def _get_age_in_weeks(pet) -> float | None:
    """Return pet's age in weeks from pet.dob. Returns None if DOB is unknown."""
    if not pet.dob:
        return None
    return max(0.0, (date.today() - pet.dob).days / 7)


def _age_appropriate_preventive_question(pet) -> str | None:
    """
    Return an age-contextualised initial preventive question for puppies (< 52 weeks).

    Returns None for adults (>= 52 weeks) or unknown age so the caller falls
    through to the existing generic question unchanged.
    """
    age_weeks = _get_age_in_weeks(pet)
    if age_weeks is None or age_weeks >= 52:
        return None  # Adult / unknown — use existing question

    name = pet.name
    age_label = pet.age_text or "at this age"

    if age_weeks < 2:
        return (
            f"{name} is very young, so most preventive care hasn't started yet. "
            f"Has any deworming or vaccination been given so far? "
            f"(Most vets begin deworming from 2 weeks.)"
        )
    if age_weeks < 6:
        # 2–6 weeks: deworming only; vaccines and flea/tick not yet due
        return (
            f"At {age_label}, deworming is the key priority — typically every 2 weeks until "
            f"8 weeks. Has {name}'s deworming been started?\n\n"
            f"(Vaccination and flea & tick prevention are not yet due at this stage.)"
        )
    if age_weeks < 8:
        # 6–8 weeks: first DHPP due + deworming ongoing; flea/tick not yet safe
        return (
            f"At {age_label}, the first DHPP vaccination is typically started, and deworming "
            f"continues every 2 weeks.\n\n"
            f"Has {name}'s first DHPP dose been given? Is deworming ongoing?\n\n"
            f"_(Flea & tick prevention is not yet safe — safe options start from 8 weeks.)_"
        )
    if age_weeks < 10:
        # 8–10 weeks: first DHPP if not done + monthly deworming + flea/tick now safe
        return (
            f"At {age_label}, {name} should have the first DHPP dose (if not already done), "
            f"be on monthly deworming, and flea & tick prevention can now start safely.\n\n"
            f"What do you remember? (e.g., DHPP 1st dose done, deworming ongoing, "
            f"no flea product yet — rough is fine.)"
        )
    if age_weeks < 14:
        # 10–14 weeks: 2nd DHPP booster due
        return (
            f"At {age_label}, the 2nd DHPP booster is typically due.\n\n"
            f"Has it been given? Also, is {name} on monthly deworming and flea & tick prevention? "
            f"(e.g., 2nd DHPP given, deworming last month, Bravecto started — rough is fine.)"
        )
    # 14 weeks – 1 year: 3rd DHPP + first Rabies due
    return (
        f"At {age_label}, the 3rd DHPP dose and first Rabies vaccine are typically due "
        f"(if not already given).\n\n"
        f"Has {name} received these? Also note deworming and flea & tick status. "
        f"(e.g., 3rd DHPP + Rabies done, deworming monthly, Nexgard ongoing — rough is fine.)"
    )


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
        "If the user gives only an age in years or months (e.g. '2 years', '6 months') "
        "without an explicit birth date, set dob to null — do NOT compute a dob from the age. "
        "If no age is given, set age_years, age_text, and dob to null.\n\n"
        f"User message: {text}"
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
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


async def _parse_gender_weight(text: str) -> dict:
    """
    Use GPT to extract gender and weight (kg) from user input.

    Returns dict with keys:
        gender ("male"|"female"|None), weight_kg (float|None)
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "Extract the pet's gender and weight in kg from this message. "
        'Return ONLY valid JSON, no markdown: '
        '{"gender": "male"|"female"|null, "weight_kg": number|null}. '
        "Accept colloquial inputs: 'boy'/'he'/'him'='male', 'girl'/'she'/'her'='female'. "
        "If weight is given without units, assume kg.\n\n"
        f"User message: {text}"
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=80,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        return {
            "gender": data.get("gender"),
            "weight_kg": data.get("weight_kg"),
        }
    except Exception as e:
        logger.warning("Gender/weight GPT parse failed: %s", str(e))
        return {"gender": None, "weight_kg": None}


async def _ai_decide_neuter_question(
    pet_name: str,
    gender: str | None,
    species: str | None,
    breed: str | None,
    age_text: str | None,
) -> dict:
    """
    AI agent that decides whether to ask about neutering/spaying and crafts the
    gender-appropriate question.

    Uses the pet's gender, species, breed, and age to:
    - Ask "Is <name> neutered?" for males.
    - Ask "Is <name> spayed?" for females.
    - Ask "Is <name> neutered or spayed?" when gender is unknown.
    - Set should_ask=False only if the pet is clearly under ~3 months old
      (too young for the procedure to be relevant yet).

    Returns dict: {"should_ask": bool, "question": str}
    """
    client = _get_openai_onboarding_client()
    prompt = (
        "You are helping onboard a pet on a health tracking app. "
        "Decide whether to ask the owner about their pet's neutering or spaying status.\n\n"
        f"Pet name: {pet_name}\n"
        f"Gender: {gender or 'unknown'}\n"
        f"Species: {species or 'unknown'}\n"
        f"Breed: {breed or 'unknown'}\n"
        f"Age/DOB: {age_text or 'unknown'}\n\n"
        "Rules:\n"
        "- Use the word 'neutered' for males and 'spayed' for females.\n"
        "- If gender is unknown, use 'neutered or spayed'.\n"
        "- Set should_ask to false ONLY if the pet is clearly under 3 months old "
        "(too young for the procedure to be relevant). Otherwise always true.\n"
        "- Keep the question short and conversational.\n\n"
        'Return ONLY valid JSON, no markdown: {"should_ask": true|false, "question": "..."}'
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=120,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        should_ask = bool(data.get("should_ask", True))
        question = data.get("question") or ""
        # Fallback question if AI returned empty.
        if should_ask and not question:
            if gender == "male":
                question = f"Is {pet_name} neutered?"
            elif gender == "female":
                question = f"Is {pet_name} spayed?"
            else:
                question = f"Is {pet_name} neutered or spayed?"
        return {"should_ask": should_ask, "question": question}
    except Exception as e:
        logger.warning("Neuter question AI decision failed: %s", str(e))
        # Safe fallback — always ask with a generic question.
        if gender == "male":
            question = f"Is {pet_name} neutered?"
        elif gender == "female":
            question = f"Is {pet_name} spayed?"
        else:
            question = f"Is {pet_name} neutered or spayed?"
        return {"should_ask": True, "question": question}


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
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        return {
            "gender": data.get("gender"),
            "weight_kg": data.get("weight_kg"),
            "neutered": data.get("neutered"),
        }
    except Exception as e:
        logger.warning("Gender/weight GPT parse failed: %s", str(e))
        return {"gender": None, "weight_kg": None, "neutered": None}


def _keyword_parse_preventive_care(text: str) -> dict:
    """
    Rule-based fallback for preventive care parsing when the GPT API call fails.

    Strategy: locate each category keyword in the text by position, then assign
    each keyword a span from its position to the next keyword's position (or end).
    This correctly handles both comma-separated input ("vaccines last dec, deworming
    today") and comma-free run-on sentences ("vaccines last december deworming today
    flea 3 months back") — the latter is a common WhatsApp typing style.

    Dates are extracted from each per-category span using relative-date patterns.
    Only categories not found in the text appear in missing[].

    Returns a dict with the same shape as _parse_preventive_care().
    """
    t = (text or "").lower()
    today_d = date.today()

    _MONTH_NUMS: dict[str, int] = {
        "jan": 1, "january": 1, "feb": 2, "february": 2,
        "mar": 3, "march": 3, "apr": 4, "april": 4,
        "may": 5, "jun": 6, "june": 6,
        "jul": 7, "july": 7, "aug": 8, "august": 8,
        "sep": 9, "september": 9, "oct": 10, "october": 10,
        "nov": 11, "november": 11, "dec": 12, "december": 12,
    }

    def _extract_date(seg: str) -> str | None:
        """Return an absolute date string from a segment, or None."""
        if re.search(r"\btoday\b|\bthis\s+month\b|\bjust\s+now\b|\bnow\b", seg):
            return today_d.strftime("%d %B %Y")
        if re.search(r"\byesterday\b", seg):
            return (today_d - timedelta(days=1)).strftime("%d %B %Y")
        m = re.search(r"(\d+)\s+months?\s+(?:ago|back|earlier)", seg)
        if m:
            n = int(m.group(1))
            yr, mo = today_d.year, today_d.month - n
            while mo <= 0:
                mo += 12
                yr -= 1
            return f"{calendar.month_name[mo]} {yr}"
        m = re.search(r"(\d+)\s+weeks?\s+(?:ago|back|earlier)", seg)
        if m:
            d = today_d - timedelta(weeks=int(m.group(1)))
            return d.strftime("%d %B %Y")
        m = re.search(r"(\d+)\s+days?\s+(?:ago|back|earlier)", seg)
        if m:
            d = today_d - timedelta(days=int(m.group(1)))
            return d.strftime("%d %B %Y")
        if re.search(r"\blast\s+month\b", seg):
            yr, mo = today_d.year, today_d.month - 1
            if mo == 0:
                mo = 12
                yr -= 1
            return f"{calendar.month_name[mo]} {yr}"
        # Match month names: "last dec", "in jan", or just "jan".
        # Strict less-than: "last april" when today is April → previous year.
        for name, num in sorted(_MONTH_NUMS.items(), key=lambda x: -len(x[0])):
            if re.search(rf"\b{re.escape(name)}\b", seg):
                yr = today_d.year if num < today_d.month else today_d.year - 1
                return f"{calendar.month_name[num]} {yr}"
        return None

    _vaccine_re = re.compile(
        r"\b(?:vaccin\w*|jabs?|shots?|rabies|dhppi?|bordetella|"
        r"core\s+vaccines?|kennel\s+cough|leptospirosis|corona(?:virus)?|fvrcp|felv)\b"
    )
    _deworm_re = re.compile(r"\b(?:deworm(?:ing)?|worming|worm(?:ed|ing)?)\b")
    _flea_re = re.compile(
        r"\b(?:flea|tick|simparica|nexgard|bravecto|frontline|advocate|"
        r"revolution|credelio|seresto|advantix|fipronil|ivermectin)\b"
    )
    _blood_re = re.compile(r"\b(?:blood\s*test|blood\s*work|cbc|complete\s*blood|haemato)\b")
    _none_re = re.compile(
        r"\b(?:none|not\s+done|never|no\s+(?:vaccine|deworm|flea|tick|blood)|haven'?t|not\s+yet)\b"
    )

    result: dict = {
        "vaccines": None,
        "vaccine_specifics": [],
        "deworming": None,
        "flea_tick": None,
        "blood_test": None,
        "missing": [],
    }

    # Build a list of (category, match_start) for every category keyword found.
    # Sorting by position lets us slice text[start:next_start] as per-category spans,
    # which correctly handles comma-free run-on sentences like:
    #   "vaccines last december deworming today flea 3 months back"
    keyword_hits: list[tuple[str, int]] = []
    for cat, pat in (
        ("vaccines", _vaccine_re),
        ("deworming", _deworm_re),
        ("flea_tick", _flea_re),
        ("blood_test", _blood_re),
    ):
        m = pat.search(t)
        if m:
            keyword_hits.append((cat, m.start()))

    keyword_hits.sort(key=lambda x: x[1])

    # Assign each category the text from its keyword to the next keyword (or end).
    spans: list[tuple[str, str]] = []
    for i, (cat, start) in enumerate(keyword_hits):
        end = keyword_hits[i + 1][1] if i + 1 < len(keyword_hits) else len(t)
        spans.append((cat, t[start:end]))

    for cat, seg in spans:
        is_none = bool(_none_re.search(seg))
        dt = "none" if is_none else (_extract_date(seg) or today_d.strftime("%B %Y"))

        if cat == "vaccines":
            result["vaccines"] = dt
        elif cat == "deworming":
            result["deworming"] = {"date": dt, "medicine": None, "prevention_targets": []}
        elif cat == "flea_tick":
            result["flea_tick"] = {"date": dt, "medicine": None, "prevention_targets": []}
        elif cat == "blood_test":
            result["blood_test"] = dt

    found = {cat for cat, _ in spans}
    result["missing"] = [
        k for k in ("vaccines", "deworming", "flea_tick", "blood_test") if k not in found
    ]
    return result


async def _parse_preventive_care(
    text: str,
    context_categories: list[str] | None = None,
) -> dict:
    """
    Use GPT-4.1-mini to extract preventive care dates and medicine names from combined input.

    Args:
        text: The user's free-text message.
        context_categories: Optional list of human-readable category names the user
            is specifically responding about (e.g. ["flea & tick treatment", "blood tests"]).
            When provided, a hint is injected into the GPT prompt so that an ambiguous
            positive reply like "done this month" gets attributed to the right categories
            rather than returning null.

    Returns dict with keys:
        vaccines (str|None)         — generic "vaccines done" date
        vaccine_specifics (list)    — [{"name": "rabies", "date": "Dec 2025"}, ...]
        deworming (dict|str|None)   — {"date": "...", "medicine": "...", "prevention_targets": [...]} or date string
        flea_tick (dict|str|None)   — {"date": "...", "medicine": "...", "prevention_targets": [...]} or date string
        blood_test (str|None)
        missing (list[str])         — which of the 4 categories were not mentioned
    """
    from app.services.gpt_extraction import _build_medicine_coverage_prompt

    client = _get_openai_onboarding_client()
    today_str = date.today().isoformat()
    medicine_guide = _build_medicine_coverage_prompt()
    prompt = (
        f"Today's date is {today_str}. "
        "Extract preventive care information from this message about a pet. "
        "Look for four categories: vaccines, deworming, flea & tick treatment, and blood tests. "
        "For each, extract the approximate date or timeframe when it was last done. "
        "IMPORTANT: The user may list multiple categories in a comma-free run-on sentence "
        "(e.g. 'vaccines last december deworming today flea 3 months back'). "
        "In such cases each category keyword (vaccines, deworming, flea, blood test) "
        "should be paired with the date phrase that immediately follows it. "
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
        "- Return deworming and flea_tick as objects with 'date', 'medicine', and "
        "'prevention_targets' keys.\n"
        "- prevention_targets must be an array containing one or both of: 'deworming', "
        "'flea_tick'. Always include ALL categories listed for that medicine in the "
        "MEDICINE COVERAGE GUIDE below, regardless of how the user described it. "
        "For example, if the guide says a medicine covers both flea_tick and deworming, "
        "include both even if the user only mentioned one.\n"
        f"{medicine_guide}\n"
        "- If no medicine is provided, use an empty prevention_targets array.\n\n"
        'Return ONLY valid JSON, no markdown: '
        '{"vaccines": "date or timeframe"|null, '
        '"vaccine_specifics": [{"name": "vaccine name", "date": "date or timeframe"}], '
        '"deworming": {"date": "date or timeframe", "medicine": "brand name"|null, "prevention_targets": ["deworming"|"flea_tick"]}|null, '
        '"flea_tick": {"date": "date or timeframe", "medicine": "brand name"|null, "prevention_targets": ["deworming"|"flea_tick"]}|null, '
        '"blood_test": "date or timeframe"|null, '
        '"missing": ["category names not mentioned"]}. '
        "If the user explicitly says 'none' or 'not done' for a category, "
        'set it to "none" (not null). '
        "Null means not mentioned at all. "
        "'missing' should list category names that were not mentioned.\n\n"
        + (
            f"NOTE: The user is specifically responding about: "
            f"{', '.join(context_categories)}. "
            f"If their response is ambiguous (e.g. 'done', 'done this month', 'yes, both'), "
            f"attribute it to these categories and convert any relative timeframe to 'Month YYYY'.\n\n"
            if context_categories
            else ""
        )
        + f"User message: {text}"
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        raw = _strip_json_fences(response.content[0].text.strip())
        data = json.loads(raw)
        # Defensive parse: vaccine_specifics must be a list of dicts with name+date.
        raw_specifics = data.get("vaccine_specifics") or []
        if not isinstance(raw_specifics, list):
            raw_specifics = []
        clean_specifics = [
            s for s in raw_specifics
            if isinstance(s, dict) and s.get("name") and s.get("date")
        ]
        parsed = {
            "vaccines": data.get("vaccines"),
            "vaccine_specifics": clean_specifics,
            "deworming": data.get("deworming"),
            "flea_tick": data.get("flea_tick"),
            "blood_test": data.get("blood_test"),
            "missing": data.get("missing", []),
        }
        # Guardrail: if GPT missed a specific combo vaccine mention like
        # "5-in-1" and only returned a generic vaccines date, convert it into
        # vaccine_specifics so we do not fan out generic updates to all core vaccines.
        combo_match = re.search(r"\b(\d+\s*[- ]?in\s*[- ]?1)\b", (text or "").lower())
        if combo_match and not parsed.get("vaccine_specifics"):
            combo_name = re.sub(r"\s+", " ", combo_match.group(1)).replace(" -", "-").replace("- ", "-")
            combo_date = parsed.get("vaccines")
            if isinstance(combo_date, str) and combo_date and combo_date != "none":
                parsed["vaccine_specifics"] = [{"name": combo_name, "date": combo_date}]
                parsed["vaccines"] = None
        # Guardrail: GPT sometimes returns a generic label (e.g. "vaccines", "shots")
        # as a vaccine_specific entry instead of the top-level "vaccines" field.
        # Promote it back so _is_generic_vaccine_mention detects it and asks which
        # vaccines the pet actually receives.
        if not parsed.get("vaccines") or parsed.get("vaccines") == "none":
            specifics = parsed.get("vaccine_specifics") or []
            generic_entries = [
                s for s in specifics
                if isinstance(s, dict)
                and str(s.get("name") or "").strip().lower() in _GENERIC_VAX_LABELS
                and str(s.get("date") or "").strip()
            ]
            real_entries = [
                s for s in specifics
                if isinstance(s, dict)
                and str(s.get("name") or "").strip().lower() not in _GENERIC_VAX_LABELS
            ]
            if generic_entries and not real_entries:
                # All specifics are generic labels — promote the date to vaccines field.
                parsed["vaccines"] = generic_entries[0]["date"]
                parsed["vaccine_specifics"] = []
        parsed = _apply_all_preventive_categories_intent(text, parsed)
        return _normalize_preventive_medicine_categories(parsed)
    except Exception as e:
        logger.warning(
            "Preventive care GPT parse failed (%s: %s); falling back to keyword extraction",
            type(e).__name__,
            str(e),
        )
        # Use keyword/regex extraction so data the user already provided is
        # not silently discarded when the API is temporarily unavailable.
        # Only categories NOT detected by keyword will appear in missing[].
        # Apply the same post-processors as the main path for semantic equivalence.
        fallback = _keyword_parse_preventive_care(text)
        fallback = _apply_all_preventive_categories_intent(text, fallback)
        return _normalize_preventive_medicine_categories(fallback)


def _contains_all_preventive_categories_intent(text: str) -> bool:
    """Return True when user intent clearly covers all preventive categories."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return False

    positive_phrases = (
        "all of the above",
        "all the above",
        "all above",
        "everything above",
        "all of these",
        "all four",
    )
    if not any(phrase in lowered for phrase in positive_phrases):
        return False

    if "only" in lowered:
        return False
    if "except" in lowered or "but not" in lowered:
        return False

    # Explicit negation of any tracked category should disable global fill.
    negated_category_pattern = (
        r"\bnot\s+(vaccines?|deworm(ing)?|worms?|flea|tick|"
        r"flea\s*(and|&)\s*tick|blood\s*tests?)\b"
    )
    return not re.search(negated_category_pattern, lowered)


def _infer_preventive_timeframe_from_text(text: str) -> str | None:
    """Extract a best-effort shared timeframe phrase from user text."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return None

    if "last month" in lowered:
        return "last month"
    if "this month" in lowered:
        return "this month"
    if "today" in lowered:
        return "today"
    if "yesterday" in lowered:
        return "yesterday"

    relative_match = re.search(r"\b\d+\s+(day|days|week|weeks|month|months|year|years)\s+ago\b", lowered)
    if relative_match:
        return relative_match.group(0)

    month_match = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b",
        lowered,
    )
    if month_match:
        return month_match.group(0)

    return None


def _apply_all_preventive_categories_intent(text: str, parsed: dict) -> dict:
    """Fill missing preventive categories when user says 'all of the above'."""
    if not _contains_all_preventive_categories_intent(text):
        return parsed

    updated = dict(parsed or {})

    def _pick_shared_date(data: dict) -> str | None:
        vaccines = data.get("vaccines")
        if isinstance(vaccines, str) and vaccines and vaccines != "none":
            return vaccines

        specifics = data.get("vaccine_specifics") or []
        if isinstance(specifics, list):
            for entry in specifics:
                if isinstance(entry, dict) and entry.get("date"):
                    return entry["date"]

        for key in ("deworming", "flea_tick"):
            value = data.get(key)
            if isinstance(value, dict) and value.get("date"):
                return value.get("date")
            if isinstance(value, str) and value and value != "none":
                return value

        blood_test = data.get("blood_test")
        if isinstance(blood_test, str) and blood_test and blood_test != "none":
            return blood_test

        return _infer_preventive_timeframe_from_text(text)

    shared_date = _pick_shared_date(updated)
    if not shared_date:
        return updated

    vaccines_value = updated.get("vaccines")
    explicit_vaccine_none = isinstance(vaccines_value, str) and vaccines_value == "none"
    has_vaccine_data = bool(
        explicit_vaccine_none
        or (isinstance(vaccines_value, str) and vaccines_value and vaccines_value != "none")
        or (isinstance(updated.get("vaccine_specifics"), list) and updated.get("vaccine_specifics"))
    )
    if not has_vaccine_data:
        updated["vaccines"] = shared_date

    if not updated.get("deworming"):
        updated["deworming"] = {
            "date": shared_date,
            "medicine": None,
            "prevention_targets": [],
        }

    if not updated.get("flea_tick"):
        updated["flea_tick"] = {
            "date": shared_date,
            "medicine": None,
            "prevention_targets": [],
        }

    if not updated.get("blood_test"):
        updated["blood_test"] = shared_date

    return updated


def _normalize_preventive_medicine_categories(parsed: dict) -> dict:
    """Normalize deworming/flea_tick fields based on medicine compatibility.

    Rules:
    - Medicine compatible with only one category is moved to that category.
    - Medicine compatible with both categories is copied to the missing category.
    - Unknown medicines are left unchanged.
    """
    from app.services.gpt_extraction import _get_preventive_categories_for_medicine

    def _as_text(value) -> str:
        return value.strip() if isinstance(value, str) else ""

    def _coerce_category_value(value):
        if isinstance(value, dict):
            raw_targets = value.get("prevention_targets")
            clean_targets: list[str] = []
            if isinstance(raw_targets, list):
                for target in raw_targets:
                    token = _as_text(target).lower().replace("-", "_").replace(" ", "_")
                    if token:
                        clean_targets.append(token)
            return {
                "date": value.get("date"),
                "medicine": value.get("medicine") if isinstance(value.get("medicine"), str) else None,
                "prevention_targets": clean_targets,
            }
        if isinstance(value, str) and value and value != "none":
            return {"date": value, "medicine": None, "prevention_targets": []}
        return value

    def _is_category_present(value) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            return bool(_as_text(value.get("date")) or _as_text(value.get("medicine")))
        return True

    def _is_vaccine_present(data: dict) -> bool:
        vaccines = data.get("vaccines")
        specifics = data.get("vaccine_specifics") or []
        if isinstance(vaccines, str) and vaccines.strip():
            return True
        return bool(specifics)

    def _absorbed_by_target(target, source_date, source_medicine: str) -> bool:
        if not isinstance(target, dict):
            return False
        target_medicine = _as_text(target.get("medicine"))
        if target_medicine and target_medicine.lower() != source_medicine.lower():
            return False
        target_date = _as_text(target.get("date"))
        source_date_text = _as_text(source_date)
        return not (source_date_text and not target_date)

    normalized = dict(parsed or {})

    deworming = _coerce_category_value(normalized.get("deworming"))
    flea_tick = _coerce_category_value(normalized.get("flea_tick"))

    # Snapshot source values so cross-category moves don't mutate iteration input.
    entries = (
        ("deworming", _coerce_category_value(deworming)),
        ("flea_tick", _coerce_category_value(flea_tick)),
    )

    for source_key, source_value in entries:
        if not isinstance(source_value, dict):
            continue

        medicine = _as_text(source_value.get("medicine"))
        if not medicine:
            continue

        explicit_categories: set[str] = set()
        raw_targets = source_value.get("prevention_targets")
        if isinstance(raw_targets, list):
            for target in raw_targets:
                token = _as_text(target).lower().replace("-", "_").replace(" ", "_")
                if token in {"flea", "tick", "tick_flea", "flea_tick", "tick/flea", "flea/tick"}:
                    explicit_categories.add("flea_tick")
                elif token in {"deworm", "deworming", "worm", "worms"}:
                    explicit_categories.add("deworming")

        categories = explicit_categories | _get_preventive_categories_for_medicine(medicine)
        if not categories:
            continue

        source_date = source_value.get("date")
        source_medicine = medicine
        source_rehomed = False

        if "deworming" in categories:
            if not isinstance(deworming, dict):
                deworming = {
                    "date": source_date,
                    "medicine": source_medicine,
                    "prevention_targets": source_value.get("prevention_targets") or [],
                }
                source_rehomed = True
            else:
                before_date = deworming.get("date")
                before_medicine = deworming.get("medicine")
                if not deworming.get("date"):
                    deworming["date"] = source_date
                if not _as_text(deworming.get("medicine")):
                    deworming["medicine"] = source_medicine
                if (before_date != deworming.get("date") or before_medicine != deworming.get("medicine")
                    or _absorbed_by_target(deworming, source_date, source_medicine)):
                    source_rehomed = True

        if "flea_tick" in categories:
            if not isinstance(flea_tick, dict):
                flea_tick = {
                    "date": source_date,
                    "medicine": source_medicine,
                    "prevention_targets": source_value.get("prevention_targets") or [],
                }
                source_rehomed = True
            else:
                before_date = flea_tick.get("date")
                before_medicine = flea_tick.get("medicine")
                if not flea_tick.get("date"):
                    flea_tick["date"] = source_date
                if not _as_text(flea_tick.get("medicine")):
                    flea_tick["medicine"] = source_medicine
                if (before_date != flea_tick.get("date") or before_medicine != flea_tick.get("medicine")
                    or _absorbed_by_target(flea_tick, source_date, source_medicine)):
                    source_rehomed = True

        # Clear source bucket only when it was actually rehomed into compatible bucket(s).
        if source_key == "deworming" and "deworming" not in categories and source_rehomed:
            deworming = None
        if source_key == "flea_tick" and "flea_tick" not in categories and source_rehomed:
            flea_tick = None

    normalized["deworming"] = deworming
    normalized["flea_tick"] = flea_tick
    final_missing: list[str] = []
    if not _is_vaccine_present(normalized):
        final_missing.append("vaccines")
    if not _is_category_present(deworming):
        final_missing.append("deworming")
    if not _is_category_present(flea_tick):
        final_missing.append("flea_tick")
    if not _is_category_present(normalized.get("blood_test")):
        final_missing.append("blood_test")
    normalized["missing"] = final_missing
    return normalized


def _infer_species_from_breed(breed_key: str) -> str | None:
    """
    Infer species from a breed name using the breed_normalizer dictionaries.

    Args:
        breed_key: Lowercased, stripped breed name.

    Returns:
        "dog", "cat", or None if breed is not in either dictionary.
    """
    import re as _re

    from app.utils.breed_normalizer import _CAT_BREEDS, _DOG_BREEDS
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
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        raw = response.content[0].text.strip()
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
    at_limit = remaining <= 0
    has_uploaded_any = docs_uploaded > 0
    prompt = (
        "You are a friendly pet care assistant helping a user upload health records "
        f"for their pet {pet_name} during onboarding.\n\n"
        "CONTEXT:\n"
        f"- User has uploaded at least one file already: {has_uploaded_any}\n"
        f"- User has reached the upload limit: {at_limit}\n"
        f"- Accepted formats: JPEG, PNG, PDF\n\n"
        f"The user sent a TEXT message (not a file): \"{user_message}\"\n\n"
        "CRITICAL RULES:\n"
        "- NEVER mention any specific number of files, upload limits, remaining count, or totals. Do not include digits referring to file counts.\n"
        "- The user has NOT uploaded or shared anything with THIS message — it is text only.\n"
        "- NEVER say 'Thanks for sharing', 'Got it', 'Great', 'Awesome', or any phrase that implies they already shared a file in this message.\n"
        "- Do NOT treat words like 'sharing', 'sending', 'uploading' in their text as if they already did it.\n"
        "- If they seem to be indicating they will upload soon (e.g. 'sharing', 'sending now'), simply encourage them to go ahead and send the file.\n"
        "- If they're asking whether they can add more, say yes they can send additional files — without quoting any number.\n"
        "- If at_limit is True, let them know they've hit the upload limit without stating the number.\n\n"
        "Reply in 1-2 short, warm sentences that match the actual context. "
        "Do NOT mention 'skip', 'skipping', or any way to exit/continue the upload step. "
        "Do NOT use markdown headings. Use *bold* sparingly for key info only."
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning("Doc upload reply GPT failed, using fallback: %s", str(e))
        if not at_limit:
            return (
                f"You can go ahead and share {pet_name}'s health records "
                f"in JPEG, PNG, or PDF format whenever you're ready."
            )
        return f"You've reached the upload limit for {pet_name}."


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


_DOC_INTENT_LABELS = {"skip", "add_more", "upload_soon", "dashboard", "other"}


async def _classify_doc_upload_intent(
    user_message: str,
    pet_name: str,
    prior_assistant_message: str = "",
    current_step_purpose: str = "",
    next_step_description: str = "",
) -> str:
    """
    Use the LLM to classify a free-text reply during the document upload window.

    The classifier is given the conversational context — the previous assistant
    message, what the current step is trying to accomplish, and what happens
    next — so phrases like "what next?" or "ok" are interpreted relative to the
    flow instead of in isolation.

    Returns one of: skip, add_more, upload_soon, dashboard, other.
    Falls back to 'other' on any error so the caller degrades gracefully.
    """
    if not user_message or not user_message.strip():
        return "other"

    client = _get_openai_onboarding_client()
    prompt = (
        "You are classifying a user's WhatsApp reply inside a pet onboarding flow. "
        "Interpret the reply in context: what the assistant just asked, what this "
        "step is collecting, and what happens next if the user moves on.\n\n"
        f"Pet name: {pet_name}\n"
        f"Current step purpose: {current_step_purpose or 'collect optional health-record uploads (JPEG/PNG/PDF).'}\n"
        f"What happens next if the user moves past this step: "
        f"{next_step_description or 'onboarding finalizes and the care plan / dashboard link is generated.'}\n"
        f"Previous assistant message: \"{prior_assistant_message or '(not available)'}\"\n"
        f"User reply: \"{user_message}\"\n\n"
        "Return ONE label (lowercase, no punctuation, nothing else) from this set:\n"
        "- skip: user wants to skip uploading, do it later, move on, continue to the next step, "
        "has nothing to upload, or is otherwise signalling they do not want to share docs right now. "
        "Phrases like 'not right now', 'later', 'what next', 'move on', 'proceed', 'no' map here "
        "BECAUSE the next step is finalization — asking 'what next' implies they want to advance.\n"
        "- add_more: user is asking whether they can upload additional/more documents.\n"
        "- upload_soon: user says they are about to upload / sending now / will share a file shortly.\n"
        "- dashboard: user is asking for the dashboard link, care plan, or status of plan building.\n"
        "- other: none of the above; an ambiguous question or small-talk that does not fit above.\n\n"
        "Judge based on the user's apparent goal given the previous assistant message and what comes next, "
        "not just the literal words. Reply with exactly one word from the label set."
    )
    try:
        response = await retry_openai_call(
            client.messages.create,
            model=OPENAI_QUERY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        label = (response.content[0].text or "").strip().lower()
        label = re.sub(r"[^a-z_]", "", label)
        if label in _DOC_INTENT_LABELS:
            return label
    except Exception as e:
        logger.warning("Doc upload intent classification failed: %s", str(e))
    return "other"


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
    now_ts = datetime.now(UTC).timestamp()
    _AWAITING_DOCS_REPLY_COOLDOWN_SECONDS = 300
    _AWAITING_DOCS_SIMPLE_ACKS = _YES_INPUTS.union({"ok", "okay", "k", "thanks", "thank you", "got it"})
    od = _get_onboarding_data(user)

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
        await _finalize_onboarding(db, user, send_fn, declined_documents=True)
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
        _set_onboarding_data(user, "awaiting_docs_last_reply_at", now_ts)
        _set_onboarding_data(user, "awaiting_docs_last_reply_text", "building_status")
        db.commit()
        await send_fn(
            db, mobile,
            f"{pet_name}'s care plan is still being built 🐾 "
            f"You'll receive the dashboard link as soon as it's ready. "
            f"Reply *skip* if you don't want to upload any documents.",
        )
        return

    # Guard against late-arriving diet/supplement messages from prior onboarding steps.
    # Fetch pet early here; the variable is re-used below for upload-count logic.
    pet = db.query(Pet).filter(Pet.user_id == user.id).order_by(Pet.created_at.desc()).first()
    pet_name = pet.name if pet else "your pet"
    if pet:
        prior_classification = await _classify_prior_step_input(text_lower, "awaiting_documents")
        if prior_classification in ("food", "supplement"):
            reask = (
                f"Got it, added that to {pet_name}'s "
                f"{'diet' if prior_classification == 'food' else 'supplements'}. "
                f"You can now send any vaccination, deworming, or vet documents — "
                f"or reply *skip* to continue."
            )
            await _save_prior_step_dietary_input(
                db, user, pet, text_lower, prior_classification, send_fn, reask
            )
            return

    # Count uploads using BOTH the DB and the in-memory batch tracker.
    # The in-memory count avoids a race where a text message arrives before
    # the async upload pipeline has committed the Document rows.
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
    else:
        # Keyword fast-paths didn't match — ask the LLM to classify the user's
        # intent so replies like "what next", "move on", "later" advance the
        # flow instead of getting another upload nudge on loop. Pass the
        # conversational context so the LLM judges meaning against the previous
        # assistant prompt and what happens after this step.
        prior_assistant_msg = str(od.get("awaiting_docs_last_reply_text") or "")
        intent = await _classify_doc_upload_intent(
            user_message=text_lower,
            pet_name=pet_name,
            prior_assistant_message=prior_assistant_msg,
            current_step_purpose=(
                "Optional step: user can share vaccination cards, vet prescriptions, "
                "or lab reports (JPEG/PNG/PDF). They may also choose to skip."
            ),
            next_step_description=(
                "Onboarding finalizes. The pet's care plan is built and the dashboard "
                "link is sent over WhatsApp."
            ),
        )
        if intent == "skip":
            try:
                from app.services.message_router import clear_upload_window_extended
                clear_upload_window_extended(user.id)
            except Exception:
                pass
            await _finalize_onboarding(db, user, send_fn, declined_documents=True)
            return
        if intent == "dashboard":
            _set_onboarding_data(user, "awaiting_docs_last_reply_at", now_ts)
            _set_onboarding_data(user, "awaiting_docs_last_reply_text", "building_status")
            db.commit()
            await send_fn(
                db, mobile,
                f"{pet_name}'s care plan is still being built 🐾 "
                f"You'll receive the dashboard link as soon as it's ready. "
                f"Reply *skip* if you don't want to upload any documents.",
            )
            return
        if intent == "add_more":
            try:
                from app.services.message_router import mark_upload_window_extended
                mark_upload_window_extended(user.id)
            except Exception as e:
                logger.warning("Failed to mark upload window extended: %s", str(e))

    # Avoid duplicate low-information prompts while the user is deciding
    # whether to upload records. This prevents repeated "Great! You can upload..."
    # messages for simple acknowledgements like "yes" or "ok".
    last_reply_at = _get_onboarding_timestamp(od, "awaiting_docs_last_reply_at")
    elapsed_since_last = (now_ts - last_reply_at) if last_reply_at is not None else None
    if text_lower.strip() in _AWAITING_DOCS_SIMPLE_ACKS and elapsed_since_last is not None:
        if elapsed_since_last < _AWAITING_DOCS_REPLY_COOLDOWN_SECONDS:
            return

    reply = await _generate_doc_upload_reply(pet_name, text_lower, docs_uploaded, remaining)
    last_reply_text = str(od.get("awaiting_docs_last_reply_text") or "").strip().lower()
    if (
        last_reply_text
        and last_reply_text == reply.strip().lower()
        and elapsed_since_last is not None
        and elapsed_since_last < _AWAITING_DOCS_REPLY_COOLDOWN_SECONDS
    ):
        return

    _set_onboarding_data(user, "awaiting_docs_last_reply_at", now_ts)
    _set_onboarding_data(user, "awaiting_docs_last_reply_text", reply.strip().lower())
    db.commit()
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


async def _finalize_onboarding(db, user, send_fn, declined_documents: bool = False):
    """
    Finalize onboarding: mark complete, clear deadline, send GPT-generated
    "care plan ready" message with hardcoded fallback templates.

    Record seeding and token generation already happened in _transition_to_documents().

    If ``declined_documents`` is True and no documents were uploaded, a shorter,
    reassuring transition message is sent instead of the default one.
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
    # Keep onboarding care-plan messaging aligned with the dashboard
    # "What's Found" summary to avoid cross-surface count drift.
    record_count = _count_tracked_preventive_items(db, pet.id)
    vaccine_count, other_preventive_count = _count_tracked_preventive_items_split(db, pet.id)
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
    # Persist the deferred marker BEFORE the slow GPT call so that any
    # "dashboard" request from the user during care-plan generation is
    # silently swallowed by the dashboard handler. The care plan + link
    # will be delivered as soon as GPT returns.
    _persist_deferred_marker_with_fallback(db, user, pet)

    # Transition message first. If the user explicitly declined documents and
    # none were uploaded, use a shorter, reassuring line instead.
    if declined_documents and docs_uploaded == 0:
        transition_msg = (
            f"No problem, you can add it later. "
            f"I'm working on {pet.name}'s care plan."
        )
    else:
        transition_msg = (
            f"That's everything. 🐾 Building {pet.name}'s personalised care plan now "
            f"— their health dashboard, care reminders, and nutrition breakdown "
            f"will be ready in just a moment."
        )
    await send_fn(db, mobile, transition_msg)

    # Fetch diet items for AI supplement recommendation.
    diet_items = db.query(DietItem).filter(DietItem.pet_id == pet.id).all()

    # Pre-generate all AI enrichments (life stage, diet summary, recognition
    # bullets, care plan reasons) before building the care plan message so the
    # dashboard is fully populated the moment the user taps the link.
    # precompute_dashboard_enrichments opens its own session and handles all
    # upserts; failures are logged but never propagate.
    try:
        from app.services.precompute_service import precompute_dashboard_enrichments
        await precompute_dashboard_enrichments(str(pet.id))
    except Exception as _pre_exc:
        logger.warning("finalize: precompute failed for pet=%s: %s", str(pet.id), _pre_exc)

    # Try GPT-generated message, fall back to templates.
    care_plan_msg = await _generate_care_plan_message(
        db=db,
        pet=pet,
        diet_count=diet_count,
        supplement_count=supplement_count,
        record_count=record_count,
        vaccine_count=vaccine_count,
        other_preventive_count=other_preventive_count,
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
        care_plan_msg += (
            f"\n\n📌 *Tip:* Pin this message so you can always find "
            f"{pet.name}'s care plan link."
        )
    else:
        care_plan_msg += (
            f"\n\nSend *dashboard* anytime to get {pet.name}'s care plan link."
        )

    # Atomically claim the deferred marker before sending. If another caller
    # already claimed it (e.g. an in-flight dashboard request), bail out so
    # the user only receives the care plan once.
    try:
        from app.services.message_router import _clear_deferred_care_plan_marker
        claimed = _clear_deferred_care_plan_marker(db, pet.id, user=user)
        db.commit()
    except Exception as claim_err:
        logger.warning(
            "Could not claim deferred marker during finalize for pet=%s: %s",
            str(pet.id), str(claim_err),
        )
        try:
            db.rollback()
        except Exception:
            pass
        claimed = 1  # On claim failure, fall through and send anyway.

    if claimed <= 0:
        logger.info(
            "Care plan already delivered for pet=%s — skipping duplicate send during finalize",
            str(pet.id),
        )
        return

    await send_fn(db, mobile, care_plan_msg)


async def _generate_care_plan_message(
    pet, diet_count: int = 0, supplement_count: int = 0,
    record_count: int = 0, docs_uploaded: int = 0,
    vaccine_count: int = 0,
    other_preventive_count: int = 0,
    conditions: list | None = None,
    diet_items: list | None = None,
    db: Session | None = None,
) -> str:
    """Generate the unified "care plan ready" message."""
    if vaccine_count > 0 and other_preventive_count > 0:
        preventive_label = (
            f"{vaccine_count} vaccine{'s' if vaccine_count != 1 else ''} and "
            f"{other_preventive_count} preventive care item"
            f"{'s' if other_preventive_count != 1 else ''}"
        )
    elif vaccine_count > 0:
        preventive_label = f"{vaccine_count} vaccine{'s' if vaccine_count != 1 else ''}"
    else:
        preventive_label = (
            f"{record_count} preventive care item{'s' if record_count != 1 else ''}"
        )

    name = pet.name
    return (
        f"{name}'s care plan is ready! 🐾\n"
        f"Based on {name}'s health, life stage and current diet we've put together "
        f"a personalised care plan.\n\n"
        f"We've logged {preventive_label} for {name}.\n\n"
        f"We've also added recommendations on diet and nutrition, along with health "
        f"insights and guidance on what to ask your vet."
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

    if not getattr(settings, "ANTHROPIC_API_KEY", None):
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

        async def _make_call_chat():
            return await client.messages.create(
                model=OPENAI_QUERY_MODEL,
                system="You validate pet weights and return strict JSON only.",
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=140,
            )

        response = await retry_openai_call(_make_call_chat)
        raw = response.content[0].text.strip()

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
    if not getattr(settings, "ANTHROPIC_API_KEY", None):
        return {"species": None, "breed": None}

    if mime_type not in {"image/jpeg", "image/png"}:
        return {"species": None, "breed": None}

    client = _get_openai_onboarding_client()
    data_uri = encode_image_base64(file_bytes, mime_type)

    # Strip data URI prefix to get raw base64 and media type for Anthropic vision API.
    b64_data = data_uri
    img_media_type = mime_type
    if data_uri.startswith("data:"):
        header, _, b64_data = data_uri.partition(",")
        mime_part = header.split(";")[0].replace("data:", "")
        if mime_part:
            img_media_type = mime_part

    prompt = (
        "Identify the main pet in this photo. "
        "Return strict JSON only with this exact schema: "
        '{"species":"dog|cat|unknown","breed":"string|null"}. '
        "If the image is unclear or not a dog/cat, return species unknown and breed null."
    )

    async def _make_call() -> str:
        response = await client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=80,
            system="You classify pet photos and return strict JSON only.",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": img_media_type,
                                "data": b64_data,
                            },
                        },
                    ],
                },
            ],
        )
        return response.content[0].text

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

    # Compute pet age for age-gated seeding decisions.
    _seed_age_weeks = (
        (date.today() - pet.dob).days / 7 if pet.dob else None
    )

    count = 0
    for master in masters:
        if master.id in existing_master_ids:
            continue
        # Tick/Flea products are not safe for dogs younger than 8 weeks.
        # Skip seeding the record so the care plan does not surface it.
        # It will be seeded on the next seed run once the pet reaches 8 weeks.
        if (
            master.item_name == "Tick/Flea"
            and pet.species == "dog"
            and _seed_age_weeks is not None
            and _seed_age_weeks < 8
        ):
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
