"""
PetCircle — Agentic Onboarding Service

An LLM-driven alternative to the deterministic onboarding state machine.
Activated when AGENTIC_ONBOARDING_ENABLED=true and OPENAI_API_KEY is set.

Architecture:
    - One AgentOnboardingSession row per user stores the full OpenAI message
      history (non-system turns only) and a structured "collected_data" snapshot.
    - On each incoming WhatsApp message, we append the user turn, call the
      OpenAI tool-calling API (with a freshly-built system message containing
      the current session state), execute any tool calls (which write to
      collected_data in-memory), persist the updated session, and send the
      assistant reply back via WhatsApp.
    - When the model decides all required data is collected, it calls the
      complete_onboarding tool, which atomically writes everything to the DB
      (User, Pet, diet_items, hygiene_preferences, preventive_records,
      dashboard_token) and transitions the user to awaiting_documents.
    - After that, the existing awaiting_documents handler in message_router
      takes over unchanged.

Flow paths (v4):
    Path A — Guided questions: Common Entry → Health round → Nutrition round
             → Grooming round → Closing.
    Path B — Records upload: Common Entry → User uploads doc(s) → AI extracts
             → fill gaps → Nutrition round → Grooming round → Closing.

IMPORTANT — JSONB mutation tracking:
    SQLAlchemy does not auto-detect in-place mutations (list.append, dict.update)
    on JSONB columns. Always call flag_modified() before db.commit() when
    modifying session.messages or session.collected_data.
"""

import asyncio
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
    _ai_check_weight,
    _ai_identify_pet_from_photo,
    generate_dashboard_token,
    seed_preventive_records_for_pet,
)
from app.utils.breed_normalizer import normalize_breed
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI health check cache
# ---------------------------------------------------------------------------

_openai_health_cache: dict = {"result": None, "checked_at": None}
_OPENAI_HEALTH_TTL = 300  # seconds — re-check every 5 minutes

# ---------------------------------------------------------------------------
# Document batch debounce (Path B multi-upload)
# ---------------------------------------------------------------------------
# When a user uploads multiple docs in quick succession, each webhook fires
# separately. We buffer extraction results per user and only run the agent
# loop once after uploads settle (_DOC_DEBOUNCE_SECONDS of silence).

_pending_doc_contexts: dict[str, list[str]] = {}  # key: str(user.id)
_doc_timers: dict[str, asyncio.Task] = {}          # key: str(user.id)
_DOC_DEBOUNCE_SECONDS: int = 12


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

# Base prompt text — never injected alone. Always use _build_system_prompt().
_BASE_SYSTEM_PROMPT = """## ROLE & IDENTITY

You are the PetCircle WhatsApp concierge — a warm, knowledgeable pet care
assistant helping pet parents set up their pet's care profile. You are not
a generic chatbot. You speak like a trusted friend who genuinely loves
animals. You are attentive, never robotic, and always personalise responses
using the pet's name.

You have one job during onboarding: collect the pet's profile in a natural,
friendly conversation, then celebrate the moment with a dashboard snapshot.
After onboarding, you remain available for any pet care question.


## FLOW OVERVIEW

Two onboarding paths exist. Every conversation starts with the Common Entry
Sequence, then branches on the user's choice.

- Path A (user replies 1): Guided questions — Health → Nutrition → Grooming
- Path B (user replies 2): Records upload → AI extracts → fill gaps →
  Nutrition → Grooming

NEVER offer a third path. NEVER mention a "hybrid" option.


## COMMON ENTRY SEQUENCE

Step 1 — Confirm parent name:
  "Thank you for your consent! Let's get you set up. Your WhatsApp name is
  {whatsapp_name}. Should I use this as your name? Reply yes or enter a
  different name."

Step 2 — Pet name:
  "Thanks, {parent_name}! What is your pet's name?"

Step 3 — Photo request:
  "Love that name! Do you have a photo of {pet_name} you'd like to share?
  We'd love to meet them!"

Step 3a — If photo shared:
  The system will analyse the image and inject a [System: AI detected: species=..., breed=...] context.
  Use the detected species and breed silently — do NOT tell the user you identified them from the photo.
  Respond warmly and personally about the photo.
  CRITICAL: NEVER assume or imply the pet's sex/gender at this point — you
  do not know it yet. Use neutral language only: {pet_name}, "they",
  "this one", "absolutely adorable", "what a face".
  NEVER say: "gorgeous boy", "good girl", "he", "she" before sex is confirmed.
  CORRECT: "Oh, what a happy dog! Look at that face! {pet_name} looks like
  a Golden Retriever — absolutely adorable. They are going to get the best care."
  If AI detected species and breed confidently: ask only gender and DOB.
  If AI could NOT detect species (species=unknown or null): ask species, breed, gender, and DOB.
  If AI detected species but NOT breed (breed=unknown): ask breed, gender, and DOB.

Step 3b — If no photo (user declines or says skip/later):
  "No worries — you can always add one later! A couple of quick questions:
  1. Is {pet_name} a dog or a cat?
  2. What breed is {pet_name}?
  3. Is {pet_name} male or female?
  4. Date of birth? (approximately is fine)"

Step 4 — Present setup options (ALWAYS exactly 2, never 3):
  "Perfect! Setting up {pet_name}'s profile takes less than a minute —
  pick what works best for you:

  1️⃣  Answer a few quick questions here on WhatsApp
  2️⃣  Share {pet_name}'s vet records and I'll do the rest

  Reply 1 or 2."


## PATH A — GUIDED SETUP

Round 1 of 3 — Health:
  Always list vaccine names explicitly. Use the pet's species from session state.

  FOR DOGS (adult, age ≥ 1 year):
    "Let's start with {pet_name}'s health. Answer here on WhatsApp —
    skip anything you're not sure of:
    1. Mandatory vaccines — Rabies, DHPPi (7-in-1 / 9-in-1). When was each last
       given? (If both were done on the same date, just share that one date!)
    2. Optional vaccines — Kennel Cough (Nobivac KC), Canine Coronavirus (CCoV),
       Leptospirosis, Canine Influenza. Has {pet_name} had any of these? If yes,
       when?
    3. Last deworming date?
    4. Flea and tick prevention — product used and last dose?
    5. Any recent blood tests? (date and key findings)
    6. Any allergies or ongoing medications?"

  FOR DOGS (puppy, age < 1 year — infer from DOB in session state):
    "Let's start with {pet_name}'s health. Answer here on WhatsApp —
    skip anything you're not sure of:
    1. Puppy mandatory vaccines — DHPPi 1st Dose, DHPPi 2nd Dose, DHPPi 3rd
       Dose, Puppy Booster, Rabies. Which have been given and when?
       (If multiple doses were given on the same date, just share that one date!)
    2. Optional vaccines — Kennel Cough (Nobivac KC), Canine Coronavirus (CCoV),
       Leptospirosis, Canine Influenza. Has {pet_name} had any of these? If yes,
       when?
    3. Last deworming date?
    4. Flea and tick prevention — product used and last dose?
    5. Any recent blood tests? (date and key findings)
    6. Any allergies or ongoing medications?"

  FOR CATS:
    "Let's start with {pet_name}'s health. Answer here on WhatsApp —
    skip anything you're not sure of:
    1. Mandatory vaccines — Rabies, Feline Core (FVRCP). When was each last given?
       (If both were done on the same date, just share that one date!)
    2. Optional vaccines — FeLV Vaccine, FIV Vaccine. Has {pet_name} had any of
       these? If yes, when?
    3. Last deworming date?
    4. Flea and tick prevention — product used and last dose?
    5. Any recent blood tests? (date and key findings)
    6. Any allergies or ongoing medications?"

  VACCINE DATE INFERENCE RULES (apply to all species):
  - If user gives ONE date for mandatory vaccines with no per-vaccine breakdown →
    assume that date applies to ALL mandatory vaccines and record it for each.
    Do NOT ask them to repeat it per vaccine.
  - If user gives ONE date for optional vaccines with no per-vaccine breakdown →
    ask once to confirm: "Was that date for both [optional vaccine names]?" then
    apply accordingly based on the reply.
  - If user mentions a specific vaccine name along with a date → record it
    immediately; do NOT ask about that vaccine again separately.
  - If user says a vaccine was not given / they don't have it → skip it cleanly;
    do not push.

  After response: "All saved! Moving on."

Round 2 of 3 — Nutrition:
  "Great, almost done! A few quick questions about what {pet_name} eats:
  1. What does {pet_name} eat? (kibble / home-cooked / raw / mixed)
  2. Brand name if kibble?
  3. How many meals per day?
  4. Any treats or toppers?
  5. Any food sensitivities or foods you avoid?"

  After response: "Got it! {pet_name}'s current diet is saved. You'll be able to see the full nutrition profile on the dashboard."

Round 3 of 3 — Grooming:
  "Last one — a couple of quick questions about {pet_name}'s grooming:
  1. How often does {pet_name} get a bath?
  2. Any other grooming you'd like us to track? (e.g. haircuts, nail trims,
     dental, ear cleaning — whatever matters to you)"

  CRITICAL: Keep grooming to these 2 questions only. Do NOT expand question 2
  into a prescriptive numbered sub-list of dental/nails/ears. The user decides
  what they want tracked.

  Then go directly to the Closing Sequence.


## PATH B — RECORDS UPLOAD

Step 1 — Request records:
  "Please share {pet_name}'s health or vaccination records here on WhatsApp
  — any format works (PDF, photo, screenshot, multiple files, anything you have)."

  CRITICAL: NEVER say "upload". Say "share here on WhatsApp", "send", or
  "drop it here". ALWAYS reassure the user that ALL formats are accepted —
  do not list a limited set of file types.

Step 2 — Acknowledge and surface findings:
  When a [System: Document extracted...] context message arrives, use the
  findings to say:
  "Thanks! Here is what I found:
  Vaccines: {extracted or "Not found in records"}
  Deworming: {extracted or "Not found in records"}
  Flea and Tick: {extracted or "Not found in records"}
  Blood tests: {extracted or "Not found in records"}

  A few quick gaps to fill: [ask ONLY for fields marked Not found]"

  CRITICAL: NEVER say "I am reading..." unless a document was just received.
  Use the extraction results already provided in the system context.

Step 3 — Fill health gaps:
  Ask only for information not found in the records. Call add_health_records
  with source="document_extraction" for extracted data and source="user_input"
  for gap answers.
  After gaps filled: "Got it! Health profile is complete."

Step 4 — Nutrition (go straight in, no permission gate):
  "Now let's quickly note what {pet_name} eats — just a few questions
  here on WhatsApp:
  1. What does {pet_name} eat? (kibble / home-cooked / raw / mixed)
  2. Brand name if kibble?
  3. How many meals per day?
  4. Any treats or toppers?
  5. Any food sensitivities or foods you avoid?"

  CRITICAL: Do NOT say "Would you like to add nutrition details? Reply YES
  or SKIP." Go straight into the questions.

Step 5 — Grooming (go straight in, no permission gate):
  After nutrition is saved:
  "Nutrition saved! One last section — just two quick questions about
  {pet_name}'s grooming here on WhatsApp:
  1. How often does {pet_name} get a bath?
  2. Any other grooming you'd like us to track? (e.g. haircuts, nail trims,
     dental, ear cleaning — whatever matters to you)"

Step 5a — No-response nudge:
  If no reply after a long pause, send this message ONCE:
  "Still here! 🐾 Just waiting on {pet_name}'s grooming details — take your
  time. Reply SKIP if you'd like to finish here and add this later."

  CRITICAL: Send the nudge ONCE only. Never repeat it. The nudge_sent flag
  in the session state tracks whether it has been sent. If user replies SKIP,
  proceed to the Closing Sequence with whatever data has been collected.


## CLOSING SEQUENCE — ALL PATHS

Send this after all sections are complete (or after SKIP):

  "{pet_name}'s full profile is ready! Here is the dashboard we created
  — with the photo.

  {pet_name} | {breed} | {sex} | {age}

  HEALTH
  {health_summary}

  NUTRITION
  {nutrition_summary}

  HYGIENE
  {grooming_summary}

  🔗 View {pet_name}'s full dashboard: petcircle.app/dashboard/{pet_name_slug}

  I will remind you for every care item — vaccinations, deworming, flea
  treatment, grooming, and more.

  You can ask me any pet care question here, anytime — trusted advice is
  just a message away. Type HELP to see what I can do."

CRITICAL: NEVER close with a plain text summary only. Always include:
  - The dashboard link: petcircle.app/dashboard/{pet_name_lowercased}
  - The care reminder commitment
  - The invitation to ask pet care questions
Note: After calling complete_onboarding the system will provide the actual
dashboard link. Use it directly in your closing message.


## DATA COLLECTION RULES

- Never repeat a question already answered earlier in the conversation
- Always use the pet's name — never "your pet" or "it"
- Species detection priority: (1) AI photo analysis result (system-injected), (2) user explicitly states it, (3) inferred from breed name. Only ask the user directly if none of these yield a species.
- Infer safely: if the user said "Bruno, dog" or the photo was already analysed, do not ask species again
- If the user says "not sure" or "skip", accept it and move on without pushing
- Store all collected data using the available tools the moment it is provided
- Species: only "dog" or "cat". Politely clarify if the user says something else.
- Dates: accept any format (15/03/2022, March 15 2022, 3 years ago, etc.)
  and convert to YYYY-MM-DD before storing.
- Weight: 0.1 to 200 kg. If it seems very unusual, ask once to confirm.
- Gender: store as "male" or "female" only.
- Pincode: exactly 6 digits.
- India context: accept Hindi affirmations like "haan"/"ha" as yes, "nahi"/"na" as no.
- After onboarding is complete, answer any pet care question warmly and helpfully


## COMMANDS — RECOGNISE AT ANY POINT

HELP    → List available commands and invite the user to ask any pet care question
SKIP    → Skip the current question or section; save what is collected; move forward
UPDATE  → Re-open the profile for editing; ask which field they want to change
RESTART → Clear session and start onboarding from Step 1


## EDGE CASES

- Unexpected message mid-flow: acknowledge briefly and warmly, return to current step
- Pet care question mid-onboarding: answer it briefly, then say
  "Now, back to getting {pet_name} set up —" and resume
- Multiple files sent at once: process all together in a single extraction pass
- Records in a foreign language: extract what you can, note what was unclear,
  ask for the specific missing fields only
- User skips everything: save whatever data was collected; still send the
  full closing sequence with the dashboard link
- Breed not detectable from photo: "I couldn't quite make out the breed from
  the photo — could you tell me? Any guess is fine!"
- No photo and no breed offered: record breed as unknown and continue;
  do not block progress on missing breed
"""


def _build_system_prompt(session: "AgentOnboardingSession") -> str:
    """
    Build the system prompt for the current turn by injecting current session
    state at the top of the base prompt.

    The AI has no memory between calls — the session state JSON tells it
    exactly what has been collected so far so it never re-asks answered questions.
    """
    state = _build_session_state_for_prompt(session)
    state_json = json.dumps(state, indent=2, default=str)
    return f"## CURRENT SESSION STATE\n{state_json}\n\n{_BASE_SYSTEM_PROMPT}"


def _build_session_state_for_prompt(session: "AgentOnboardingSession") -> dict:
    """
    Flatten collected_data into the canonical session-state schema the
    system prompt references. Returns a dict the AI can read to understand
    what it still needs to collect.
    """
    cd = session.collected_data
    user = cd.get("user", {})
    pet = cd.get("pet", {})
    health = cd.get("health", {})
    diet = cd.get("diet", {})
    grooming = cd.get("grooming", [])

    return {
        "whatsapp_name": user.get("whatsapp_name", ""),
        "parent_name": user.get("full_name", ""),
        "pet_name": pet.get("name", ""),
        "species": pet.get("species", ""),
        "breed": pet.get("breed", ""),
        "sex": pet.get("gender", "unknown"),
        "dob": pet.get("dob", ""),
        "photo_url": pet.get("photo_path", ""),
        "path": cd.get("path", ""),
        "current_step": cd.get("current_step", "entry"),
        "health": {
            "vaccines": health.get("vaccines", ""),
            "deworming": health.get("deworming", ""),
            "flea_tick": health.get("flea_tick", ""),
            "blood_tests": health.get("blood_tests", ""),
            "allergies_medications": health.get("allergies_medications", ""),
        },
        "nutrition": {
            "packaged": diet.get("packaged", []),
            "homemade": diet.get("homemade", []),
            "supplements": diet.get("supplements", []),
        },
        "grooming": grooming,
        "records_shared": cd.get("records_shared", False),
        "nudge_sent": cd.get("nudge_sent", False),
        "onboarding_complete": cd.get("onboarding_complete", False),
    }


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Greeting resume helper
# ---------------------------------------------------------------------------


def _build_agentic_progress_summary(session: "AgentOnboardingSession") -> str:
    """
    Build a bullet-point progress summary from the session's collected_data.

    Returns a non-empty string when at least one field has been collected
    (indicating the session is in progress), or an empty string if nothing
    has been collected yet (so greetings on a fresh session are handled by
    the LLM as a normal opening turn).
    """
    cd = session.collected_data
    user_data = cd.get("user", {})
    pet_data = cd.get("pet", {})
    diet = cd.get("diet", {})
    grooming = cd.get("grooming", [])

    lines = []

    if user_data.get("full_name"):
        lines.append(f"Your name: {user_data['full_name']}")
    if user_data.get("pincode"):
        lines.append("Pincode: Provided")

    if pet_data.get("name"):
        lines.append(f"Pet name: {pet_data['name']}")
    if pet_data.get("photo_path"):
        lines.append("Photo: Uploaded")
    if pet_data.get("species") and pet_data["species"] not in ("_pending", ""):
        lines.append(f"Species: {pet_data['species']}")
    if pet_data.get("breed"):
        lines.append(f"Breed: {pet_data['breed']}")
    if pet_data.get("gender"):
        lines.append(f"Gender: {pet_data['gender']}")
    if pet_data.get("dob"):
        lines.append(f"Date of birth: {pet_data['dob']}")
    if pet_data.get("weight") is not None:
        lines.append(f"Weight: {pet_data['weight']} kg")
    if pet_data.get("neutered") is not None:
        lines.append(f"Neutered: {'Yes' if pet_data['neutered'] else 'No'}")

    total_diet = (
        len(diet.get("packaged", []))
        + len(diet.get("homemade", []))
        + len(diet.get("supplements", []))
    )
    if total_diet > 0:
        lines.append(f"Diet/supplements: {total_diet} item(s) recorded")
    if grooming:
        lines.append(f"Grooming: {len(grooming)} item(s) recorded")

    if not lines:
        return ""
    return "\n".join(f"  • {line}" for line in lines)


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
            "name": "add_health_records",
            "description": (
                "Store health information the user provides — vaccines, deworming, "
                "flea/tick prevention, blood tests, allergies or ongoing medications. "
                "Call this as soon as the user provides any of these in Path A, or "
                "when document extraction results are available in Path B. "
                "All fields are optional — only pass what was provided or extracted. "
                "Use source='document_extraction' when data came from an uploaded file, "
                "'user_input' when the user typed it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vaccines": {
                        "type": "string",
                        "description": "Vaccine date(s) and type(s), e.g. 'Rabies Oct 2024, DHPPiL Oct 2024'",
                    },
                    "deworming": {
                        "type": "string",
                        "description": "Last deworming date and product if known",
                    },
                    "flea_tick": {
                        "type": "string",
                        "description": "Flea/tick prevention product and last dose date",
                    },
                    "blood_tests": {
                        "type": "string",
                        "description": "Blood test date and key findings",
                    },
                    "allergies_medications": {
                        "type": "string",
                        "description": "Known allergies and/or ongoing medications",
                    },
                    "source": {
                        "type": "string",
                        "enum": ["user_input", "document_extraction"],
                        "description": "How this data was obtained",
                    },
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
                "share health, nutrition, and grooming details (or explicitly skipped). "
                "This triggers all DB writes and generates the dashboard link. "
                "Do NOT call this before mandatory fields are confirmed. "
                "Do NOT call this before the nutrition and grooming rounds are complete."
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

_EMPTY_COLLECTED_DATA = {
    "user": {},
    "pet": {},
    "path": "",
    "current_step": "entry",
    "health": {},
    "diet": {"packaged": [], "homemade": [], "supplements": []},
    "grooming": [],
    "records_shared": False,
    "nudge_sent": False,
    "onboarding_complete": False,
}


def _get_or_create_session(db: Session, user: User) -> AgentOnboardingSession:
    """
    Load the active agentic session for the user, or create a new one.

    session.messages stores only non-system turns (user / assistant / tool).
    The system message is rebuilt dynamically on each API call so it always
    reflects the latest collected_data.
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
        import copy
        session = AgentOnboardingSession(
            user_id=user.id,
            messages=[],
            collected_data=copy.deepcopy(_EMPTY_COLLECTED_DATA),
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
            pet_data.setdefault(
                "breed",
                normalize_breed(ai_result["breed"], species=ai_result.get("species")),
            )

        species_str = ai_result.get("species") or "unknown"
        breed_str = ai_result.get("breed") or "unknown breed"
        return (
            f"[System: User sent a pet photo. "
            f"AI detected: species={species_str}, breed={breed_str}. "
            f"Photo saved. Please confirm these details with the user before storing. "
            f"CRITICAL: Use gender-neutral language (they/them) until sex is confirmed.]"
        )

    except Exception as e:
        logger.error("Photo preprocessing failed: %s", str(e), exc_info=True)
        return "[System: Photo processing failed. Continue without photo.]"


async def _preprocess_health_document(
    user: User,
    session: AgentOnboardingSession,
    message_data: dict,
) -> str:
    """
    Download a vet record document sent during Path B, run GPT extraction,
    and return a rich context string the LLM uses to surface findings and
    ask only for missing gaps.

    Does NOT write to the DB — the LLM calls add_health_records after
    confirming findings with the user.
    """
    from app.services.whatsapp_sender import download_whatsapp_media

    media_id = message_data.get("media_id")
    mime_type = message_data.get("mime_type", "")

    if not media_id:
        return (
            "[System: User sent a document but no media_id found. "
            "Ask them to send the file again.]"
        )

    try:
        media_result = await download_whatsapp_media(media_id)
        if not media_result:
            return (
                "[System: Document download failed. Ask the user to resend. "
                "Continue with guided questions if they cannot.]"
            )

        file_bytes, detected_mime = media_result
        effective_mime = mime_type or detected_mime

        # Mark that records were shared regardless of extraction outcome
        session.collected_data["records_shared"] = True

        # Run GPT extraction
        raw_json: str | None = None
        try:
            from app.services.gpt_extraction import (
                _call_openai_extraction,
                _call_openai_extraction_vision,
            )

            if effective_mime in ("image/jpeg", "image/png"):
                from app.utils.file_reader import encode_image_base64
                data_uri = encode_image_base64(file_bytes, effective_mime)
                raw_json = await _call_openai_extraction_vision(data_uri)
            else:
                # PDF or unknown — try text extraction first
                from app.utils.file_reader import extract_pdf_text
                pdf_text = extract_pdf_text(file_bytes)
                if pdf_text and len(pdf_text.strip()) > 20:
                    raw_json = await _call_openai_extraction(
                        f"Veterinary document text:\n\n{pdf_text}"
                    )
                else:
                    # Scanned PDF or PDF with unextractable text — render pages
                    # as actual JPEG images using PyMuPDF, then pass to vision API.
                    # NOTE: raw PDF bytes cannot be sent directly to the vision API;
                    # only PNG/JPEG/GIF/WEBP are accepted.
                    from app.utils.file_reader import render_pdf_pages_as_images
                    page_images = render_pdf_pages_as_images(file_bytes, max_pages=3)
                    if page_images:
                        raw_json = await _call_openai_extraction_vision(page_images[0])
                    # else: raw_json stays None, handled by the if not raw_json check below

        except Exception as e:
            logger.warning("GPT extraction during onboarding failed: %s", str(e))

        if not raw_json:
            return (
                "[System: Document received but extraction failed. "
                "Acknowledge receipt and ask the health questions manually (Path A style).]"
            )

        # Parse extraction results into human-readable summary for the LLM
        findings = _summarise_extraction_for_onboarding(raw_json)
        return (
            f"[System: Document extracted successfully. Here are the findings:\n"
            f"Vaccines: {findings['vaccines']}\n"
            f"Deworming: {findings['deworming']}\n"
            f"Flea and Tick: {findings['flea_tick']}\n"
            f"Blood tests: {findings['blood_tests']}\n"
            f"Other medications/allergies: {findings['allergies_medications']}\n"
            f"Please surface these findings to the user using the exact format from Path B Step 2, "
            f"then call add_health_records with source='document_extraction' for all found fields, "
            f"and ask only for fields showing 'Not found in records'.]"
        )

    except Exception as e:
        logger.error("Health document preprocessing failed: %s", str(e), exc_info=True)
        return (
            "[System: Document processing failed. Acknowledge receipt and "
            "fall back to asking health questions manually.]"
        )


def _summarise_extraction_for_onboarding(raw_json: str) -> dict:
    """
    Parse GPT extraction JSON and return a flat summary dict keyed by
    health category for injection into the LLM context.

    Returns a dict with keys: vaccines, deworming, flea_tick, blood_tests,
    allergies_medications. Each value is a human-readable string or
    "Not found in records".
    """
    NOT_FOUND = "Not found in records"
    summary = {
        "vaccines": NOT_FOUND,
        "deworming": NOT_FOUND,
        "flea_tick": NOT_FOUND,
        "blood_tests": NOT_FOUND,
        "allergies_medications": NOT_FOUND,
    }

    try:
        data = json.loads(raw_json)
        # Handle both list and {"items": [...]} wrapper
        items: list = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("items", data.get("records", []))
            # Also check top-level keys if no items array
            if not items and any(k in data for k in ("item_name", "date", "category")):
                items = [data]

        vaccine_parts = []
        deworming_parts = []
        flea_tick_parts = []
        blood_test_parts = []
        med_parts = []

        for item in items:
            if not isinstance(item, dict):
                continue
            name = (item.get("item_name") or item.get("name") or "").lower()
            date_str = item.get("date") or item.get("last_done_date") or ""
            medicine = item.get("medicine_name") or item.get("product") or ""
            category = (item.get("category") or item.get("document_category") or "").lower()

            label = item.get("item_name") or item.get("name") or ""
            entry = f"{label} ({date_str})" if date_str else label

            if any(kw in name for kw in ("vaccin", "rabies", "dhppil", "leptospira", "parvovirus", "distemper", "hepatitis", "bordetella")):
                vaccine_parts.append(entry)
            elif any(kw in name for kw in ("deworm", "deworming", "anthelmintic")):
                part = f"{medicine} ({date_str})" if medicine and date_str else (medicine or entry)
                deworming_parts.append(part)
            elif any(kw in name for kw in ("flea", "tick", "nexgard", "bravecto", "frontline", "simparica")):
                part = f"{medicine} ({date_str})" if medicine and date_str else (medicine or entry)
                flea_tick_parts.append(part)
            elif any(kw in name for kw in ("blood", "cbc", "chemistry", "haematology", "diagnostic", "test")):
                blood_test_parts.append(entry)
            else:
                # Catch-all for medications / supplements
                med_parts.append(entry)

        if vaccine_parts:
            summary["vaccines"] = ", ".join(vaccine_parts)
        if deworming_parts:
            summary["deworming"] = ", ".join(deworming_parts)
        if flea_tick_parts:
            summary["flea_tick"] = ", ".join(flea_tick_parts)
        if blood_test_parts:
            summary["blood_tests"] = ", ".join(blood_test_parts)
        if med_parts:
            summary["allergies_medications"] = ", ".join(med_parts)

    except Exception as e:
        logger.warning("Failed to summarise extraction JSON for onboarding: %s", str(e))

    return summary


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------


def _trim_messages(
    messages: list,
    session: AgentOnboardingSession,
    max_turns: int = 10,
) -> list:
    """
    Build the message list for the OpenAI API call.

    Prepends a freshly-built system message (with current session state
    injected) so the LLM always knows exactly what has been collected.

    session.messages is NOT mutated — full history is still persisted to DB.
    Only the last max_turns non-system messages are sent to prevent unbounded
    context growth.
    """
    system_content = _build_system_prompt(session)
    # Strip any stored system messages (backward compat with old sessions
    # that may have stored the system prompt in messages[0])
    turn_msgs = [m for m in messages if m.get("role") != "system"]
    sliced = turn_msgs[-max_turns:]

    # A `tool` message must always follow an `assistant` message that contains
    # `tool_calls` with a matching tool_call_id. Slicing can orphan `tool`
    # messages at ANY position in the window — not just the front — if the
    # session accumulated many turns and the backing assistant was pushed out.
    # Collect every tool_call_id that has a backing assistant in this slice,
    # then drop any tool message whose id is not in that set.
    backed_ids: set[str] = set()
    for msg in sliced:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                backed_ids.add(tc["id"])

    sliced = [
        msg for msg in sliced
        if msg.get("role") != "tool" or msg.get("tool_call_id") in backed_ids
    ]

    return [{"role": "system", "content": system_content}] + sliced


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
            max_tokens=1000,
            tools=_ONBOARDING_TOOLS,
            tool_choice="auto",
            messages=messages,
        )

    return await retry_openai_call(_make_call)


async def _call_openai_text_only(messages: list) -> object:
    """
    OpenAI call that forces a plain text response (tool_choice='none').

    Used exclusively for the closing message after complete_onboarding fires,
    so the model cannot call another tool and produce a blank reply.
    """
    client = _get_openai_onboarding_client()

    async def _make_call():
        return await client.chat.completions.create(
            model="gpt-4.1",
            temperature=0,
            max_tokens=1000,
            tools=_ONBOARDING_TOOLS,
            tool_choice="none",
            messages=messages,
        )

    return await retry_openai_call(_make_call)


# ---------------------------------------------------------------------------
# Health records → preventive records updater
# ---------------------------------------------------------------------------


def _update_preventive_records_from_health(
    db: Session,
    pet,
    health: dict,
) -> None:
    """
    After seeding empty preventive records, backfill last_done_date and
    next_due_date for any health data collected during onboarding.

    Matches collected health strings against preventive_master item_names
    using keyword heuristics. Safe — never raises; logs on failure.

    Args:
        db:     SQLAlchemy session (already in a transaction).
        pet:    The newly created Pet instance.
        health: collected_data["health"] dict with string values.
    """
    from app.models.preventive_master import PreventiveMaster
    from app.models.preventive_record import PreventiveRecord
    from app.utils.date_utils import parse_date
    from datetime import timedelta

    if not health:
        return

    # Load all preventive records seeded for this pet, with their master items.
    records = (
        db.query(PreventiveRecord)
        .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
        .filter(PreventiveRecord.pet_id == pet.id)
        .all()
    )

    # Build a lookup: normalised item_name → (record, master)
    record_lookup: dict[str, tuple] = {}
    for rec in records:
        if rec.preventive_master:
            key = rec.preventive_master.item_name.lower()
            record_lookup[key] = (rec, rec.preventive_master)

    def _try_update(keywords: list[str], raw_value: str, medicine: str | None = None) -> None:
        """Find the best matching record and update its last_done_date."""
        if not raw_value or not raw_value.strip():
            return

        # Find matching record by keyword
        matched_rec = None
        matched_master = None
        for key, (rec, master) in record_lookup.items():
            if any(kw in key for kw in keywords):
                matched_rec = rec
                matched_master = master
                break

        if matched_rec is None:
            return

        # Try to parse a date from the raw value
        # Look for date-like substrings (YYYY-MM-DD, DD/MM/YYYY, "Oct 2024", etc.)
        import re
        date_candidates = re.findall(
            r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}|'
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|'
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
            raw_value,
            re.IGNORECASE,
        )

        parsed_date = None
        for candidate in date_candidates:
            try:
                parsed_date = parse_date(candidate)
                if parsed_date:
                    break
            except Exception:
                continue

        if parsed_date is None:
            return

        try:
            matched_rec.last_done_date = parsed_date
            if matched_master and matched_master.recurrence_days:
                matched_rec.next_due_date = parsed_date + timedelta(
                    days=matched_master.recurrence_days
                )
            if medicine:
                matched_rec.medicine_name = medicine[:200]
            # Recalculate status
            from datetime import date as date_type
            today = date_type.today()
            if matched_rec.next_due_date:
                days_until = (matched_rec.next_due_date - today).days
                reminder_days = getattr(matched_master, "reminder_before_days", 14) or 14
                if days_until < 0:
                    matched_rec.status = "overdue"
                elif days_until <= reminder_days:
                    matched_rec.status = "upcoming"
                else:
                    matched_rec.status = "up_to_date"
        except Exception as e:
            logger.error(
                "Failed to update preventive record for pet=%s item=%s: %s",
                str(pet.id),
                matched_master.item_name if matched_master else "unknown",
                str(e),
            )

    # --- Vaccines ---
    vaccine_str = health.get("vaccines", "")
    if vaccine_str:
        # Multiple vaccines may be listed; update the first matching record
        _try_update(["vaccin", "rabies", "dhppil", "leptospira"], vaccine_str)

    # --- Deworming ---
    deworming_str = health.get("deworming", "")
    if deworming_str:
        # Extract medicine name heuristically (first word before a date)
        import re
        med_match = re.match(r'^([A-Za-z][A-Za-z\s\-]+?)(?:\s*[\(\d]|$)', deworming_str)
        med_name = med_match.group(1).strip() if med_match else None
        _try_update(["deworm"], deworming_str, medicine=med_name)

    # --- Flea & Tick ---
    flea_str = health.get("flea_tick", "")
    if flea_str:
        import re
        med_match = re.match(r'^([A-Za-z][A-Za-z\s\-]+?)(?:\s*[\(\d]|$)', flea_str)
        med_name = med_match.group(1).strip() if med_match else None
        _try_update(["flea", "tick", "ectoparasit"], flea_str, medicine=med_name)

    # Allergies/medications are logged but not written to preventive_records
    # (they belong to the conditions/medications tables, handled post-onboarding).
    allergies_str = health.get("allergies_medications", "")
    if allergies_str:
        logger.info(
            "Onboarding health data — allergies/medications for pet=%s: %s",
            str(pet.id),
            allergies_str,
        )


# ---------------------------------------------------------------------------
# OG image URL builder
# ---------------------------------------------------------------------------


def _build_og_image_url(dashboard_token: str) -> str | None:
    """
    Build the Next.js /api/og URL for the dashboard snapshot card.

    The frontend Edge Function at /api/og?token=<token> calls the backend
    GET /dashboard/{token} endpoint to fetch live pet data and renders a
    branded PNG card with the pet's health, nutrition, and hygiene summary.

    Returns None if FRONTEND_URL is not set in settings.
    """
    from app.config import settings
    frontend = getattr(settings, "FRONTEND_URL", "") or ""
    if not frontend or not dashboard_token:
        return None
    return f"{frontend}/api/og?token={dashboard_token}"


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
        7. Backfill preventive records with onboarding health data.
        8. Generate dashboard token.
        9. Transition user to awaiting_documents with 5-min upload window.
        10. Mark session complete.

    Returns:
        "__COMPLETE__::<dashboard_url>" sentinel on success (with the actual
        dashboard URL appended so the model can include it in the closing message),
        or an error string if mandatory fields are missing (model will ask again).
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
    if pet_data.get("gender") not in ("male", "female"):
        return "Error: pet gender is missing. Ask the user whether their pet is male or female before completing."

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
            cd["onboarding_complete"] = True
            if not user.onboarding_completed_at:
                user.onboarding_completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.warning(
                "Agentic onboarding: user %s already at max pets (%d)", str(user.id), MAX_PETS_PER_USER
            )
            return "__COMPLETE__::petcircle.app/dashboard"

        # --- Parse DOB ---
        # First try deterministic parsing; fall back to AI for fuzzy inputs
        # like "3 years ago" or "around 2022".
        # If parsing fails entirely AND the user provided a value, block finalization
        # and return an error so the LLM re-asks — never store None for a given DOB.
        dob = None
        raw_dob = pet_data.get("dob", "").strip()
        if raw_dob:
            try:
                dob = parse_date(raw_dob)
            except Exception:
                try:
                    from app.utils.date_utils import parse_date_with_ai
                    dob = await parse_date_with_ai(raw_dob)
                except Exception:
                    return (
                        f"Error: could not parse the date of birth '{raw_dob}' into a valid date. "
                        "Ask the user to re-enter the date in DD/MM/YYYY format, "
                        "or ask them to type 'skip' if they don't know it."
                    )

        # --- Create Pet row ---
        # weight_flagged is set by the set_pet_info tool when _ai_check_weight
        # deems the weight unusual. Default False if the check was skipped/passed.
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
            weight_flagged=pet_data.get("weight_flagged", False),
        )
        db.add(pet)
        db.flush()  # Assign pet.id before referencing it below

        # --- Relocate pet photo from temp path to permanent pet-linked path ---
        # _preprocess_pet_photo stores photos as "{user_id}/pending_photo_{media_id}.{ext}"
        # because pet.id is not yet known at upload time. Now that pet.id is assigned,
        # move the file to the canonical "{user_id}/{pet_id}/pet_photo.{ext}" path.
        raw_photo_path = pet_data.get("photo_path", "")
        if raw_photo_path and "pending_photo_" in raw_photo_path:
            ext = raw_photo_path.rsplit(".", 1)[-1] if "." in raw_photo_path else "jpg"
            permanent_path = f"{user.id}/{pet.id}/pet_photo.{ext}"
            mime_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
            try:
                from app.services.document_upload import _download_supabase_raw, upload_to_supabase
                photo_bytes = await _download_supabase_raw(raw_photo_path)
                if photo_bytes:
                    await upload_to_supabase(photo_bytes, permanent_path, mime_type)
                    pet.photo_path = permanent_path
                    logger.info(
                        "Pet photo relocated: %s → %s", raw_photo_path, permanent_path
                    )
                else:
                    logger.warning("Photo relocation: download returned empty for %s", raw_photo_path)
            except Exception as e:
                logger.warning(
                    "Pet photo relocation failed (%s → %s): %s — keeping temp path",
                    raw_photo_path, permanent_path, str(e),
                )

        # --- Diet items ---
        # Buckets match the keys used by add_diet_items tool ("packaged", "homemade",
        # "supplement" singular). food_type must be "packaged", "homemade", or "supplement"
        # so classify_food returns the correct type stored in the DB and shown by the
        # NutritionTab filter (type === 'packaged' || type === 'homemade').
        diet = cd.get("diet", {})
        for bucket, food_type in (
            ("packaged", "packaged"),
            ("homemade", "homemade"),
            ("supplements", "supplement"),  # legacy plural key
            ("supplement", "supplement"),   # singular key from tool enum
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

        # --- Backfill preventive records with onboarding health data ---
        health = cd.get("health", {})
        if health:
            try:
                _update_preventive_records_from_health(db, pet, health)
            except Exception as e:
                logger.error("Health record backfill failed: %s", str(e))

        # --- Generate dashboard token ---
        dashboard_url = ""
        token = None
        try:
            token = generate_dashboard_token(db, pet.id)
            if token:
                dashboard_url = f"petcircle.app/dashboard/{token}"
        except Exception as e:
            logger.error("Dashboard token generation failed: %s", str(e))

        # --- Build and store dashboard snapshot (OG image) URL ---
        # The Next.js /api/og?token=<token> edge function fetches live pet
        # data and renders a branded card PNG — sent as the WhatsApp image card.
        og_url = _build_og_image_url(token or "")
        if og_url:
            cd["og_image_url"] = og_url

        # --- Count active reminders (mirrors deterministic _finalize_onboarding) ---
        # Store count in collected_data so the LLM closing message can confirm
        # the reminder schedule was set up — same checklist line as deterministic flow.
        reminders_count = 0
        try:
            from app.models.reminder import Reminder
            from app.models.preventive_record import PreventiveRecord
            reminders_count = (
                db.query(Reminder)
                .join(PreventiveRecord, Reminder.preventive_record_id == PreventiveRecord.id)
                .filter(
                    PreventiveRecord.pet_id == pet.id,
                    Reminder.status.in_(["pending", "sent"]),
                )
                .count()
            )
            cd["reminders_count"] = reminders_count
        except Exception as e:
            logger.warning("Failed to count active reminders: %s", str(e))

        # --- Transition to awaiting_documents ---
        user.onboarding_state = "awaiting_documents"
        user.doc_upload_deadline = datetime.now(timezone.utc) + timedelta(
            seconds=DOC_UPLOAD_WINDOW_SECONDS
        )

        session.is_complete = True
        cd["onboarding_complete"] = True

        # Record when onboarding completed for nudge O+N schedule (OQ1).
        if not user.onboarding_completed_at:
            user.onboarding_completed_at = datetime.now(timezone.utc)

        db.commit()

        logger.info(
            "Agentic onboarding finalized: user_id=%s pet=%s (%s)",
            str(user.id),
            pet.name,
            pet.species,
        )
        # Include reminders status in the completion context so the LLM
        # includes it in the closing WhatsApp message.
        reminder_note = (
            f" Reminder schedule: {reminders_count} active reminder(s) mapped."
            if reminders_count > 0
            else " Reminder engine is ready."
        )
        return f"__COMPLETE__::{dashboard_url}::{reminder_note}"

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
        "__COMPLETE__::<url>" sentinel when complete_onboarding succeeds.
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
            pincode = str(args["pincode"]).strip()
            if not (pincode.isdigit() and len(pincode) == 6):
                return (
                    f"Error: pincode must be exactly 6 digits. Got '{pincode}'. "
                    "Ask the user to re-enter their pincode or type skip."
                )
            data["pincode"] = pincode
        return f"Stored user info: {args}"

    elif tool_name == "set_pet_info":
        data = session.collected_data.setdefault("pet", {})
        for field in ("name", "species", "gender", "dob", "weight", "neutered"):
            if field in args and args[field] is not None:
                data[field] = args[field]
        # Normalize breed to canonical form before storing.
        if "breed" in args and args.get("breed"):
            data["breed"] = normalize_breed(args["breed"], species=data.get("species"))

        # Run AI weight validation when weight is provided (mirrors deterministic flow).
        # Stores weight_flagged=True in collected_data so _finalize_agentic_onboarding
        # can write the correct value to the DB.
        if "weight" in args and args["weight"] is not None:
            try:
                from app.utils.date_utils import parse_date
                dob_val = None
                if data.get("dob"):
                    try:
                        dob_val = parse_date(data["dob"])
                    except Exception:
                        dob_val = None
                ai_result = await _ai_check_weight(
                    species=data.get("species"),
                    breed=data.get("breed"),
                    dob=dob_val,
                    weight_kg=float(args["weight"]),
                )
                flagged = ai_result is not None and not ai_result.get("reasonable", True)
                data["weight_flagged"] = flagged
                if flagged:
                    expected = ai_result.get("expected_range", "unknown")
                    reason = ai_result.get("reason", "")
                    flag_note = (
                        f" NOTE: AI flagged this weight as unusual for a "
                        f"{data.get('breed') or data.get('species', 'pet')}. "
                        f"Expected range: {expected}."
                        f"{' Reason: ' + reason if reason else ''} "
                        f"Please confirm this weight with the user before completing."
                    )
                    return f"Stored pet info: {args}.{flag_note}"
            except Exception as e:
                logger.warning("Agentic onboarding: weight AI check failed: %s", str(e))

        return f"Stored pet info: {args}"

    elif tool_name == "add_health_records":
        health = session.collected_data.setdefault("health", {})
        for field in ("vaccines", "deworming", "flea_tick", "blood_tests", "allergies_medications"):
            if args.get(field):
                health[field] = args[field]
        # Advance current_step to health if still at entry
        if session.collected_data.get("current_step") == "entry":
            session.collected_data["current_step"] = "health"
        return f"Stored health records: {args}"

    elif tool_name == "add_diet_items":
        diet = session.collected_data.setdefault(
            "diet", {"packaged": [], "homemade": [], "supplements": []}
        )
        items = args.get("items", [])
        added = 0
        for item in items:
            bucket = item.get("type", "packaged")
            existing_labels = {i["label"].lower() for i in diet.get(bucket, [])}
            if item.get("label", "").lower() not in existing_labels:
                diet.setdefault(bucket, []).append(
                    {"label": item["label"], "detail": item.get("detail", "")}
                )
                added += 1
        # Advance step
        if session.collected_data.get("current_step") in ("entry", "health"):
            session.collected_data["current_step"] = "nutrition"
        return f"Stored {added} diet item(s) (skipped duplicates)."

    elif tool_name == "add_grooming_items":
        grooming = session.collected_data.setdefault("grooming", [])
        items = args.get("items", [])
        added = 0
        existing_names = {g["name"].lower() for g in grooming}
        for item in items:
            if item.get("name", "").lower() not in existing_names:
                grooming.append(
                    {"name": item["name"], "freq": item["freq"], "unit": item["unit"]}
                )
                existing_names.add(item["name"].lower())
                added += 1
        if session.collected_data.get("current_step") in ("entry", "health", "nutrition"):
            session.collected_data["current_step"] = "grooming"
        return f"Stored {added} grooming item(s) (skipped duplicates)."

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
        response = await _call_openai_with_tools(
            _trim_messages(session.messages, session)
        )
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
        dashboard_url = "petcircle.app/dashboard"
        for tc in message.tool_calls:
            result = await _dispatch_tool_call(
                db, user, session, tc.function.name, tc.function.arguments
            )
            if result and result.startswith("__COMPLETE__::"):
                completion_triggered = True
                # Sentinel format: "__COMPLETE__::<url>::<reminder_note>"
                parts = result.split("::")
                dashboard_url = parts[1] if len(parts) > 1 else dashboard_url
                reminder_note = parts[2] if len(parts) > 2 else " Reminder engine is ready."
                result = (
                    f"Onboarding records written to database successfully. "
                    f"Dashboard URL: {dashboard_url}.{reminder_note} "
                    f"Mention the reminder schedule status in your closing message."
                )

            session.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

        if completion_triggered:
            # Let the model produce the closing message to the user.
            # Use tool_choice="none" to guarantee a text reply — never a blank message.
            final_response = await _call_openai_text_only(
                _trim_messages(session.messages, session)
            )
            final_text = final_response.choices[0].message.content or ""
            session.messages.append({"role": "assistant", "content": final_text})
            return final_text

    logger.warning("Agent loop exceeded max iterations for user %s", str(user.id))
    return (
        "I had trouble processing that. Please reply *hi* to continue where you left off."
    )


# ---------------------------------------------------------------------------
# Delayed document processing (debounce helper for Path B multi-upload)
# ---------------------------------------------------------------------------


async def _delayed_agentic_doc_processing(
    user_id: str,
    mobile: str,
    send_fn,
) -> None:
    """
    Run after the debounce window expires. Combines all buffered document
    extraction contexts for a user into one agent turn and runs the loop once.

    Called via asyncio.create_task() — never raises; all errors are logged.
    """
    await asyncio.sleep(_DOC_DEBOUNCE_SECONDS)

    contexts = _pending_doc_contexts.pop(str(user_id), [])
    _doc_timers.pop(str(user_id), None)

    if not contexts:
        return

    from app.database import get_fresh_session

    bg_db = get_fresh_session()
    try:
        user = bg_db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning("Delayed doc processing: user %s not found", user_id)
            return

        session = _get_or_create_session(bg_db, user)
        combined_context = "\n\n".join(contexts)
        session.messages.append({"role": "user", "content": combined_context})

        reply_text: str | None = None
        try:
            reply_text = await _run_agent_loop(bg_db, user, session)
        except Exception as loop_err:
            logger.error(
                "Agent loop failed (delayed doc) for user %s: %s",
                user_id, str(loop_err), exc_info=True,
            )
            reply_text = "I ran into a problem processing your documents. Please reply *hi* to continue."
        finally:
            _save_session(bg_db, session)

        if reply_text and mobile:
            await send_fn(bg_db, mobile, reply_text)
    except Exception as e:
        logger.error(
            "Delayed agentic doc processing failed for user %s: %s",
            user_id, str(e), exc_info=True,
        )
    finally:
        bg_db.close()


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
    - text     → append to history, run agent loop
    - image    → if during entry/photo step: pet photo preprocessing + agent loop
                 if during Path B: treat as vet record image, run health extraction
    - document → Path B health document extraction + agent loop

    Args:
        db:           SQLAlchemy session.
        user:         User model with _plaintext_mobile set.
        message_data: Flat dict from webhook (_extract_message_data).
        send_fn:      async send_text_message(db, mobile, text)
    """
    mobile = getattr(user, "_plaintext_mobile", None)
    msg_type = message_data.get("type", "text")

    # Guard: only process if still in agentic_onboarding state.
    # Prevents stale routing after state has already transitioned (e.g., awaiting_documents).
    if user.onboarding_state != "agentic_onboarding":
        logger.warning(
            "handle_agentic_onboarding_step called for user %s in state '%s' — skipping",
            str(user.id), user.onboarding_state,
        )
        return

    session = _get_or_create_session(db, user)

    # --- Seed WhatsApp profile name on first turn (Gap 1 fix) ---
    # The webhook provides the user's WhatsApp display name in message_data.
    # Store it in collected_data so the LLM knows it from the first message.
    cd = session.collected_data
    if not cd.get("user", {}).get("whatsapp_name"):
        profile_name = message_data.get("profile_name") or ""
        if profile_name:
            cd.setdefault("user", {})["whatsapp_name"] = profile_name

    # --- Path A detection (Gap 2 fix) ---
    # If the user replies "1" and no path is set yet, record Path A immediately
    # before the agent loop runs so the session state JSON reflects it.
    text_preview = (message_data.get("text") or "").strip()
    if text_preview == "1" and not cd.get("path"):
        cd["path"] = "A"
    elif text_preview == "2" and not cd.get("path"):
        cd["path"] = "B"

    # --- Preprocess media before building the user turn ---
    injected_context: str | None = None
    _thinking_sent = False  # guard — ensures at most one "thinking" message per turn

    if msg_type == "image":
        current_step = cd.get("current_step", "entry")
        path = cd.get("path", "")

        # Determine whether this image is a pet photo or a vet record:
        # - If we haven't collected pet info yet (entry step, no species) → pet photo
        # - If path is B and health is not yet complete → treat as vet record image
        pet_has_species = bool(cd.get("pet", {}).get("species"))
        if not pet_has_species and current_step == "entry":
            if mobile:
                await send_fn(db, mobile, "Aww, let me take a look! 🐾")
                _thinking_sent = True
            injected_context = await _preprocess_pet_photo(db, user, session, message_data)
        elif path == "B" and not cd.get("health"):
            # Vet record image sent during Path B — buffer and debounce.
            if mobile:
                await send_fn(db, mobile, "Got it! Reading your records, give me a moment... 📄")
                _thinking_sent = True
            doc_context = await _preprocess_health_document(user, session, message_data)
            user_key = str(user.id)
            _pending_doc_contexts.setdefault(user_key, []).append(doc_context)
            if user_key in _doc_timers:
                _doc_timers[user_key].cancel()
            _doc_timers[user_key] = asyncio.create_task(
                _delayed_agentic_doc_processing(user.id, mobile, send_fn)
            )
            _save_session(db, session)  # persist records_shared=True
            return  # no immediate reply; delayed task sends one message after all docs settle
        else:
            # Default: treat as pet photo (user may be adding one later)
            if mobile:
                await send_fn(db, mobile, "Aww, let me take a look! 🐾")
                _thinking_sent = True
            injected_context = await _preprocess_pet_photo(db, user, session, message_data)

    elif msg_type == "document":
        # All documents during onboarding are treated as vet records (Path B).
        # Buffer extraction result and debounce — only run the agent loop once
        # after all uploads in a burst have settled.
        cd["path"] = "B"
        if mobile:
            await send_fn(db, mobile, "Got it! Reading your records, give me a moment... 📄")
            _thinking_sent = True
        doc_context = await _preprocess_health_document(user, session, message_data)
        user_key = str(user.id)
        _pending_doc_contexts.setdefault(user_key, []).append(doc_context)
        if user_key in _doc_timers:
            _doc_timers[user_key].cancel()
        _doc_timers[user_key] = asyncio.create_task(
            _delayed_agentic_doc_processing(user.id, mobile, send_fn)
        )
        _save_session(db, session)  # persist path="B" and records_shared=True
        return  # no immediate reply; delayed task sends one message after all docs settle

    # Build user-turn content
    text = (message_data.get("text") or "").strip()

    # --- Greeting detection + progress resume (mirrors deterministic flow) ---
    # If the user sends a greeting while onboarding is in progress and there is
    # already some data collected, send a structured progress summary and re-ask
    # the current step — instead of passing the greeting into the LLM as-is.
    if msg_type == "text" and not injected_context:
        from app.core.constants import GREETINGS
        if text.lower() in GREETINGS:
            progress = _build_agentic_progress_summary(session)
            if progress:
                # Determine current step to re-ask
                current_step = cd.get("current_step", "entry")
                step_label = {
                    "entry": "Let's continue with your pet's profile setup.",
                    "health": "Let's continue with your pet's health records.",
                    "nutrition": "Let's continue with your pet's nutrition details.",
                    "grooming": "Let's continue with your pet's grooming routine.",
                }.get(current_step, "Let's continue where we left off.")
                resume_msg = (
                    f"Welcome back! 👋\n\n"
                    f"Here's what we have so far:\n{progress}\n\n"
                    f"{step_label}"
                )
                await send_fn(db, mobile, resume_msg)
                return

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

    # --- Send a single "thinking" indicator before any slow AI call ---
    if mobile and not _thinking_sent:
        await send_fn(db, mobile, "Give me a moment... ⏳")

    # --- Run the agent loop ---
    reply_text: str | None = None
    try:
        reply_text = await _run_agent_loop(db, user, session)
    except Exception as e:
        logger.error(
            "Agent loop failed for user %s: %s", str(user.id), str(e), exc_info=True
        )
        reply_text = "I ran into a problem. Please reply *hi* to continue where you left off."
    finally:
        # Always persist — even on failure, saves partial state (path, records_shared, etc.)
        _save_session(db, session)

    # --- Send dashboard image card on onboarding completion (Gap 3) ---
    # If complete_onboarding just fired this turn, og_image_url will be set.
    # Send the image card first, then the text closing message follows.
    if cd.get("onboarding_complete") and mobile:
        og_url = cd.get("og_image_url")
        if og_url:
            pet_name = cd.get("pet", {}).get("name", "")
            try:
                from app.services.whatsapp_sender import send_image_message
                await send_image_message(
                    db, mobile, og_url,
                    caption=f"{pet_name}'s dashboard is ready!",
                )
            except Exception as e:
                logger.warning("Failed to send dashboard image card: %s", str(e))

    # --- Send text reply ---
    if reply_text and mobile:
        await send_fn(db, mobile, reply_text)


# ---------------------------------------------------------------------------
# Grooming nudge runner (Gap 4)
# ---------------------------------------------------------------------------


async def run_grooming_nudges(db: Session) -> dict:
    """
    Find onboarding sessions that have been stuck at the grooming step for
    30+ minutes with no nudge sent yet, and dispatch one nudge per session.

    Called by POST /internal/run-grooming-nudges (GitHub Actions cron,
    every 15 minutes). Safe to call repeatedly — the nudge_sent flag
    prevents duplicates.

    Returns:
        Dict with keys: checked, nudges_sent, errors.
    """
    from datetime import timedelta
    from sqlalchemy import text as sa_text
    from app.models.user import User
    from app.core.encryption import decrypt_field
    from app.services.whatsapp_sender import send_text_message

    NUDGE_AFTER_MINUTES = 30
    cutoff = datetime.utcnow() - timedelta(minutes=NUDGE_AFTER_MINUTES)

    checked = 0
    nudges_sent = 0
    errors = 0

    try:
        sessions = (
            db.query(AgentOnboardingSession)
            .filter(
                AgentOnboardingSession.is_complete == False,  # noqa: E712
                sa_text("collected_data->>'current_step' = 'grooming'"),
                # nudge_sent absent (NULL) or explicitly false — either way, not yet sent
                sa_text(
                    "(collected_data->>'nudge_sent') IS NULL "
                    "OR (collected_data->>'nudge_sent') = 'false'"
                ),
                AgentOnboardingSession.updated_at < cutoff,
            )
            .all()
        )
    except Exception as e:
        logger.error("Grooming nudge query failed: %s", str(e))
        return {"checked": 0, "nudges_sent": 0, "errors": 1}

    for session in sessions:
        checked += 1
        try:
            user = db.query(User).filter(User.id == session.user_id).first()
            if not user or user.is_deleted:
                continue

            mobile = decrypt_field(user.mobile)
            if not mobile:
                logger.warning(
                    "Grooming nudge: could not decrypt mobile for user_id=%s", str(user.id)
                )
                continue

            pet_name = session.collected_data.get("pet", {}).get("name") or "your pet"
            nudge_text = (
                f"Still here! 🐾 Just waiting on {pet_name}'s grooming details — "
                f"take your time. Reply SKIP if you'd like to finish here and add this later."
            )

            await send_text_message(db, mobile, nudge_text)

            # Mark nudge as sent so it is never repeated
            session.collected_data["nudge_sent"] = True
            flag_modified(session, "collected_data")
            db.commit()

            nudges_sent += 1
            logger.info(
                "Grooming nudge sent: user_id=%s, pet=%s", str(user.id), pet_name
            )

        except Exception as e:
            errors += 1
            logger.error(
                "Grooming nudge failed for session_id=%s: %s",
                str(session.id), str(e),
            )
            try:
                db.rollback()
            except Exception:
                pass

    logger.info(
        "Grooming nudge run complete: checked=%d, sent=%d, errors=%d",
        checked, nudges_sent, errors,
    )
    return {"checked": checked, "nudges_sent": nudges_sent, "errors": errors}
