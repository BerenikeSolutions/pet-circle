"""
PetCircle Phase 1 — AI Insights Service

Generates and caches GPT-driven insights shown on the Conditions dashboard tab:

    1. health_summary  — 3-4 sentence rich health narrative displayed at the
                         top of the Conditions tab alongside the health score ring.
    2. vet_questions   — Prioritised list of questions the pet owner should raise
                         at the next vet visit, shown in the "Ask the Vet" section.

Caching rules:
    - Insights are stored in pet_ai_insights (one row per pet per insight_type).
    - An insight older than AI_INSIGHT_CACHE_DAYS (7 days) is considered stale
      and re-generated on the next request.
    - force=True bypasses the cache regardless of age (used by the regenerate
      endpoint triggered from the dashboard).

Model: OPENAI_QUERY_MODEL (gpt-4.1) — used for structured text generation.

Failure behaviour: If GPT or the DB call fails, the error is logged and a
sensible default payload is returned so the dashboard never crashes.
"""

import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import OPENAI_QUERY_MODEL
from app.models.condition import Condition
from app.models.custom_preventive_item import CustomPreventiveItem
from app.models.diet_item import DietItem
from app.models.pet import Pet
from app.models.pet_ai_insight import PetAiInsight
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.services.care_plan_engine import _get_breed_size, _get_life_stage, _get_pet_age_months
from app.services.nutrition_service import get_diet_summary
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

# Re-generate if the cached insight is older than this many days.
AI_INSIGHT_CACHE_DAYS = 7

# Keywords used to classify a PreventiveMaster.item_name as a vaccine for the
# "What We Found" bullet. Case-insensitive substring match. Must include every
# canonical vaccine item_name shipped in preventive_master so none get misfiled
# as "other preventive items". See Bug 2.
_VACCINE_BULLET_TERMS: list[str] = [
    "vaccine", "rabies", "dhpp", "bordetella", "feline core",
    "kennel cough", "nobivac",
    "coronavirus", "ccov",
]

# Nutrition importance note is stable — re-generate only when pet ages significantly.
NUTRITION_IMPORTANCE_CACHE_DAYS = 30

# --------------------------------------------------------------------------- #
#  Lazy OpenAI client                                                           #
# --------------------------------------------------------------------------- #

_openai_client = None  # Anthropic AsyncAnthropic client (lazy-initialised)


class Bullet(TypedDict):
    """Single recognition bullet used by the What We Found card."""

    icon: str
    label: str


_DIET_SPLIT_RE = re.compile(r"\s*[·,;|]\s*", re.IGNORECASE)
_NOISE_CHUNK_RE = re.compile(
    r"(times?\s+a\s+day|x\s*\d+\s*/\s*day|\d+\s*/\s*day|per\s+day|"
    r"/\s*day|\bday\b|morning|afternoon|evening|night|treat|snack)",
    re.IGNORECASE,
)
_FREQUENCY_FRAGMENT_RE = re.compile(
    r"("
    r"\bx\s*\d+(?:\.\d+)?\s*/\s*(?:day|week|month)\b|"
    r"\b\d+(?:\.\d+)?\s*x\s*/\s*(?:day|week|month)\b|"
    r"\b(?:once|twice|thrice|\d+\s*times?)\s*(?:a|per)\s*(?:day|week|month)\b|"
    r"/\s*(?:day|week|month)\b"
    r")",
    re.IGNORECASE,
)
_FREQUENCY_QUALIFIER_RE = re.compile(
    r"^\s*(?:occasional(?:ly)?|sometimes|rarely|infrequently)\s+",
    re.IGNORECASE,
)
_STANDALONE_FREQUENCY_QUALIFIER_RE = re.compile(
    r"^\s*(?:occasional(?:ly)?|sometimes|rarely|infrequently)\s*$",
    re.IGNORECASE,
)
_MEASURE_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:g|kg|ml|l|cups?|tbsp|tsp|x)\b", re.IGNORECASE)


def _sentence_case(text: str) -> str:
    """Return text with first letter uppercased and trailing punctuation removed."""
    cleaned = text.strip().strip(". ")
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def _canonical_diet_item_text(text: str) -> str:
    """Return a canonical representation for cross-list diet item matching."""
    canonical = (text or "").lower().strip()
    canonical = re.sub(r"[^a-z0-9]+", " ", canonical)
    return re.sub(r"\s+", " ", canonical).strip()


def _is_food_item_covered_by_supplements(food_item: str, supplement_items: list[str]) -> bool:
    """Return True if a food item semantically overlaps with any supplement label."""
    food_canonical = _canonical_diet_item_text(food_item)
    if not food_canonical:
        return False

    food_tokens = set(food_canonical.split())
    if not food_tokens:
        return False

    for supplement in supplement_items:
        supplement_canonical = _canonical_diet_item_text(supplement)
        if not supplement_canonical:
            continue
        if food_canonical == supplement_canonical:
            return True

        supplement_tokens = set(supplement_canonical.split())
        if not supplement_tokens:
            continue
        # Keep only one-way subset matching to avoid suppressing legitimate foods
        # that merely contain a generic supplement token.
        if food_tokens.issubset(supplement_tokens):
            return True

    return False


def _extract_main_food_items(*texts: str, apply_noise_filter: bool = True) -> list[str]:
    """Extract main food labels while removing quantity/frequency/noise fragments."""
    items: list[str] = []

    for raw_text in texts:
        if not raw_text:
            continue

        normalized = raw_text.replace("×", "x")
        chunks = _DIET_SPLIT_RE.split(normalized)
        for chunk in chunks:
            # Strip frequency snippets so labels stay as clean food names.
            chunk = _FREQUENCY_FRAGMENT_RE.sub("", chunk)
            chunk = _FREQUENCY_QUALIFIER_RE.sub("", chunk)
            standalone_probe = re.sub(r"\s+", " ", chunk).strip(" .,!?:;-")
            if _STANDALONE_FREQUENCY_QUALIFIER_RE.match(standalone_probe):
                continue
            chunk = _MEASURE_TOKEN_RE.sub("", chunk)
            chunk = re.sub(r"\b\d+\b", "", chunk)
            chunk = re.sub(r"\s+", " ", chunk).strip(" .,-")
            if not chunk:
                continue
            if apply_noise_filter and _NOISE_CHUNK_RE.search(chunk):
                continue

            main_item = _sentence_case(chunk)
            if not main_item:
                continue
            if main_item.lower() not in {i.lower() for i in items}:
                items.append(main_item)

    return items


def _format_found_diet_summary(food_items: list[DietItem], supplement_items: list[DietItem]) -> str:
    """Format the What We Found diet line as a natural sentence with quantities.

    Example output: "Royal Canin hypoallergenic (280g x 2/day) and Fur+ along
    with Vitamin D3 and Glucosamine supplements"
    """
    # Build food descriptions using label + detail (for quantity/portion info).
    seen_foods: set[str] = set()
    food_descriptions: list[str] = []
    for food in food_items:
        label = (food.label or "").strip()
        if not label:
            continue
        key = label.lower()
        if key in seen_foods:
            continue
        seen_foods.add(key)
        detail = (food.detail or "").strip()
        if detail and detail.lower() != label.lower():
            food_descriptions.append(f"{label} ({detail})")
        else:
            food_descriptions.append(label)

    # Build supplement descriptions.
    seen_supps: set[str] = set()
    supp_descriptions: list[str] = []
    for supp in supplement_items:
        label = (supp.label or "").strip()
        if not label:
            continue
        key = label.lower()
        if key in seen_supps:
            continue
        seen_supps.add(key)
        # Skip supplements that are already covered by food item names.
        supp_names_for_check = [s for s in supp_descriptions]
        if _is_food_item_covered_by_supplements(label, supp_names_for_check):
            continue
        supp_descriptions.append(label)

    # Join foods into a natural sentence.
    if len(food_descriptions) == 0:
        food_str = "No food items recorded"
    elif len(food_descriptions) == 1:
        food_str = food_descriptions[0]
    elif len(food_descriptions) == 2:
        food_str = f"{food_descriptions[0]} and {food_descriptions[1]}"
    else:
        food_str = ", ".join(food_descriptions[:-1]) + f" and {food_descriptions[-1]}"

    # Append supplements.
    if supp_descriptions:
        if len(supp_descriptions) == 1:
            supp_str = supp_descriptions[0]
        elif len(supp_descriptions) == 2:
            supp_str = f"{supp_descriptions[0]} and {supp_descriptions[1]}"
        else:
            supp_str = ", ".join(supp_descriptions[:-1]) + f" and {supp_descriptions[-1]}"
        suffix = "supplement" if len(supp_descriptions) == 1 else "supplements"
        return f"{food_str} along with {supp_str} {suffix}"

    return food_str


def _get_openai_client():
    """Lazy-initialise AI client (provider-agnostic, avoids import-time errors)."""
    global _openai_client
    if _openai_client is None:
        from app.utils.ai_client import get_ai_client  # noqa: PLC0415
        _openai_client = get_ai_client()
    return _openai_client


# --------------------------------------------------------------------------- #
#  GPT generation helpers                                                       #
# --------------------------------------------------------------------------- #

async def _generate_conditions_summary_gpt(pet_context: str) -> dict:
    """
    Call GPT to produce a 2-3 sentence summary focused only on the pet's conditions.

    If no active conditions exist, returns a short "no conditions" message.

    Args:
        pet_context: Structured text description of the pet's health status.

    Returns:
        {"summary": "<conditions-focused narrative>"}
    """
    client = _get_openai_client()

    system_prompt = (
        "You are a veterinary health assistant writing for a pet owner's conditions dashboard. "
        "Given a pet's profile and active health conditions, write a 2-3 sentence summary "
        "focused ONLY on the pet's conditions. Do NOT mention vaccines, nutrition, grooming, "
        "checkups, or the overall health score. Structure it as follows:\n"
        "1. Name and briefly describe each active condition and its type (chronic/episodic).\n"
        "2. State which medications or monitoring items are being managed and their current status.\n"
        "3. What the owner should act on next (overdue monitoring, refill due, unmanaged condition).\n"
        "If no active conditions are present, return: "
        "{\"summary\": \"No active conditions detected. Your pet is currently condition-free — keep up the great preventive care!\"}\n"
        "Tone: warm, factual, parent-friendly. Never alarming. "
        "Respond with ONLY valid JSON: {\"summary\": \"<text>\"}. "
        "Do not include any explanation outside the JSON object."
    )

    user_prompt = f"Pet health context:\n{pet_context}"

    async def _call() -> str:
        response = await client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=300,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.content[0].text or "{}"

    raw = await retry_openai_call(_call)
    try:
        parsed = json.loads(raw)
        if "summary" not in parsed:
            raise ValueError("Missing 'summary' key")
        return parsed
    except Exception as exc:
        logger.warning("conditions_summary JSON parse failed: %s | raw=%s", exc, raw)
        return {"summary": "Conditions summary is being updated."}


async def _generate_health_summary_gpt(pet_context: str) -> dict:
    """
    Call GPT to produce a rich 3-4 sentence health narrative for the pet.

    Args:
        pet_context: Structured text description of the pet's health status.

    Returns:
        {"summary": "<rich 3-4 sentence narrative>"}
    """
    client = _get_openai_client()

    system_prompt = (
        "You are a veterinary health assistant writing for a pet owner's dashboard. "
        "Given a pet's profile, active health conditions, and health score, write a "
        "rich 3-4 sentence health narrative. Structure it as follows:\n"
        "1. Overall health standing — reference the score and label naturally.\n"
        "2. Key active conditions and what they mean for the pet's daily life.\n"
        "3. What is going well (e.g. vaccines up to date, medications being managed).\n"
        "4. What the owner should focus on next (e.g. overdue monitoring, refill due, "
        "missing record to add).\n"
        "Tone: warm, factual, parent-friendly. Never alarming. "
        "Respond with ONLY valid JSON: {\"summary\": \"<text>\"}. "
        "Do not include any explanation outside the JSON object."
    )

    user_prompt = f"Pet health context:\n{pet_context}"

    async def _call() -> str:
        response = await client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=500,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.content[0].text or "{}"

    raw = await retry_openai_call(_call)
    try:
        parsed = json.loads(raw)
        if "summary" not in parsed:
            raise ValueError("Missing 'summary' key")
        return parsed
    except Exception as exc:
        logger.warning("health_summary JSON parse failed: %s | raw=%s", exc, raw)
        return {"summary": "Health summary is being updated."}


async def _generate_vet_questions_gpt(pet_context: str) -> list:
    """
    Call GPT to produce a prioritised list of vet consultation questions.

    Args:
        pet_context: Structured text description of the pet's health status.

    Returns:
        List of {"priority", "icon", "q", "context"} dicts.
    """
    client = _get_openai_client()

    system_prompt = (
        "You are a veterinary health assistant. "
        "Given a pet's active conditions, medications, and overdue monitoring checks, "
        "generate a list of 2-5 prioritised questions the owner should raise at the "
        "next vet visit. "
        "Rules:\n"
        "- priority must be one of: 'urgent', 'high', 'medium'\n"
        "- icon must be a single relevant emoji\n"
        "- q is the question (≤15 words)\n"
        "- context is a 1-3 sentence explanation (factual, no alarming language)\n"
        "Respond with ONLY valid JSON array: "
        "[{\"priority\":\"...\",\"icon\":\"...\",\"q\":\"...\",\"context\":\"...\"}]"
    )

    user_prompt = f"Pet health context:\n{pet_context}"

    async def _call() -> str:
        response = await client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=800,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.content[0].text or "[]"

    raw = await retry_openai_call(_call)
    try:
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        parsed = json.loads(cleaned)
        if not isinstance(parsed, list):
            raise ValueError("Expected a JSON array")
        # Validate each item
        valid_priorities = {"urgent", "high", "medium"}
        questions = []
        for item in parsed:
            if isinstance(item, dict) and "q" in item and "context" in item:
                questions.append({
                    "priority": item.get("priority", "medium") if item.get("priority") in valid_priorities else "medium",
                    "icon": item.get("icon", "🩺"),
                    "q": str(item["q"])[:200],
                    "context": str(item["context"])[:800],
                })
        return questions
    except Exception as exc:
        logger.warning("vet_questions JSON parse failed: %s | raw=%s", exc, raw)
        return []


def _build_pet_context(pet, conditions: list, health_score: dict | None) -> str:
    """
    Build a compact plain-text context string for GPT prompts.

    Includes: species, breed, age, active conditions, medications,
    and overdue monitoring items.
    """
    from datetime import date

    today = date.today()
    lines = []
    health_score = health_score or {}

    # Pet basics
    age_str = ""
    if pet.get("dob"):
        try:
            dob = datetime.strptime(pet["dob"], "%Y-%m-%d").date()
            age_years = (today - dob).days // 365
            age_str = f", {age_years} years old"
        except ValueError:
            pass

    neutered = "neutered" if pet.get("neutered") else "intact"
    lines.append(
        f"Pet: {pet.get('name', 'Unknown')}, {pet.get('species', '')} ({pet.get('breed', '')})"
        f"{age_str}, {pet.get('gender', '')}, {neutered}"
    )

    # Active conditions
    if not conditions:
        lines.append("Active conditions: None")
    else:
        lines.append(f"Active conditions ({len(conditions)}):")
        for cond in conditions:
            lines.append(f"  - {cond.get('name', '?')} ({cond.get('condition_type', '')})"
                         f" diagnosed {cond.get('diagnosed_at', 'unknown date')}")

            # Medications
            meds = cond.get("medications", [])
            active_meds = [m for m in meds if m.get("status") == "active"]
            if active_meds:
                med_names = ", ".join(m.get("name", "?") for m in active_meds)
                lines.append(f"    Medications (active): {med_names}")
            elif not meds:
                lines.append("    Medications: none recorded")

            # Overdue monitoring
            monitoring = cond.get("monitoring", [])
            for mon in monitoring:
                next_due = mon.get("next_due_date")
                if next_due:
                    try:
                        due_date = datetime.strptime(next_due, "%Y-%m-%d").date()
                        if due_date < today:
                            days_overdue = (today - due_date).days
                            lines.append(
                                f"    OVERDUE monitoring: {mon.get('name', '?')} "
                                f"({days_overdue} days overdue)"
                            )
                    except ValueError:
                        pass
                elif not mon.get("last_done_date"):
                    lines.append(f"    Monitoring: {mon.get('name', '?')} — never done")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Document Aggregation Layer (Health Prompt 5 input builder)                   #
# --------------------------------------------------------------------------- #

def _aggregate_conditions_for_health_prompt(conditions: list[dict]) -> list[dict]:
    """
    Collapse multi-document condition data into the lean structure expected by
    Health Prompt 5.

    Per the aggregation spec only 5 signals are extracted:
        1. episode_dates  — merged, deduplicated, sorted
        2. latest_record_date — max date across all conditions (set at root)
        3. medications.end_date — only end_date is kept
        4. monitoring.recheck_due_date — only recheck_due_date is kept
        5. diagnostic_values — minimal: parameter_name, status_flag, observed_at

    Args:
        conditions: list of condition dicts from DB (as returned by dashboard_service).

    Returns:
        Aggregated list ready for Health Prompt 5 user message.
    """
    conditions_map: dict[str, dict] = {}
    all_dates: list[str] = []

    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        name = str(cond.get("name") or cond.get("condition_name") or "").strip().lower()
        if not name:
            continue

        if name not in conditions_map:
            # Condition type: carry forward, prefer chronic > recurrent > episodic.
            conditions_map[name] = {
                "name": cond.get("name") or cond.get("condition_name") or name,
                "condition_type": cond.get("condition_type") or "episodic",
                "episode_dates": [],
                "medications": [],
                "monitoring": [],
                "diagnostic_values": [],
            }

        entry = conditions_map[name]

        # Resolve type conflicts: chronic > recurrent > episodic/acute.
        _type_rank = {"chronic": 3, "recurrent": 2, "episodic": 1, "acute": 1}
        existing_rank = _type_rank.get(entry["condition_type"], 0)
        incoming_rank = _type_rank.get(cond.get("condition_type") or "episodic", 0)
        if incoming_rank > existing_rank:
            entry["condition_type"] = cond.get("condition_type")

        # Merge episode_dates.
        for d in (cond.get("episode_dates") or []):
            if d and isinstance(d, str):
                entry["episode_dates"].append(d)
                all_dates.append(d)

        # Extract only end_date from medications.
        for med in (cond.get("medications") or []):
            if not isinstance(med, dict):
                continue
            if med.get("end_date"):
                entry["medications"].append({"end_date": med["end_date"]})
                all_dates.append(med["end_date"])

        # Extract only recheck_due_date from monitoring.
        for mon in (cond.get("monitoring") or []):
            if not isinstance(mon, dict):
                continue
            if mon.get("recheck_due_date"):
                entry["monitoring"].append({"recheck_due_date": mon["recheck_due_date"]})
                all_dates.append(mon["recheck_due_date"])

        # Minimal diagnostic_values.
        for dv in (cond.get("diagnostic_values") or []):
            if not isinstance(dv, dict):
                continue
            if dv.get("observed_at"):
                all_dates.append(dv["observed_at"])
            entry["diagnostic_values"].append({
                "parameter_name": dv.get("parameter_name") or "",
                "status_flag": dv.get("status_flag"),
                "observed_at": dv.get("observed_at"),
            })

    # Post-process: deduplicate and sort episode_dates.
    for entry in conditions_map.values():
        entry["episode_dates"] = sorted(set(entry["episode_dates"]))

    # Compute latest_record_date across all dates.
    valid_dates = [d for d in all_dates if d and isinstance(d, str)]
    latest_record_date = max(valid_dates) if valid_dates else None

    result = list(conditions_map.values())

    # Attach latest_record_date to the first entry so the prompt can see it.
    if result and latest_record_date:
        result[0]["latest_record_date"] = latest_record_date

    return result


# --------------------------------------------------------------------------- #
#  Health Prompt 5 — GPT-driven condition classification and status             #
# --------------------------------------------------------------------------- #

_HEALTH_CONDITIONS_V2_SYSTEM_PROMPT = """\
You are a veterinary health assistant writing for a pet owner's conditions dashboard. You receive chronological medical records and must classify conditions, assign statuses, and write a 2-3 sentence summary focused ONLY on the pet's conditions. Do NOT mention vaccines, nutrition, grooming, checkups, or the overall health score.

STEP 1 --- CLASSIFY CONDITION TYPE
Similarity rule: Group complaints by clinical presentation and body system, not exact label. "Loose stools," "GI upset," "diarrhoea," and "colitis" are the same family. "Ear discharge," "itchy ear," and "otitis externa" are the same. Apply clinical judgement --- do not string match.
Terminology note: "acute" and "episodic" are interchangeable. If input data carries condition_type "episodic", treat it identically to "acute" in all rules below.

acute --- Single self-limiting episode, no prior similar history.
recurrent --- Repeated episodes of the same or similar complaint with symptom-free gaps. Threshold: >=2 episodes in last 15 months OR >=3 in last 24 months; provided at least one episode falls within the most recent 15 months window. Below threshold: classify acute, set recurrence_watch: true.
  To count episodes, use the episode_dates[] arrays from all input records for the same condition. Merge episode_dates across documents before applying the threshold.
  Override rule: If a condition arrives with condition_type "recurrent" explicitly set by the vet in the source document (i.e., the vet labelled it recurrent), classify it as recurrent directly without requiring the episode threshold to be met.
chronic --- Persistent condition requiring ongoing management. Identify via, in priority order:
  1. Explicit vet/prescription label (hypothyroidism, diabetes, CKD, cardiac, etc.)
  2. Same organ system or marker flagged across 2+ diagnostic reports on different dates
  3. Lifelong management drug prescribed (thyroxine, insulin, enalapril, phenobarbitone, etc.)

STEP 2 --- ASSIGN CONDITION STATUS
Severity ladder (highest to lowest): needs_attention > active > monitoring > managed > resolved
When a condition qualifies for multiple statuses, assign the highest.

needs_attention --- Assign if any of these are true:
  - Chronic: latest results significantly outside normal range with no treatment adjustment on record
  - Any type: a recheck_due_date is present in monitoring[] and that date has passed with no new record of the recheck occurring
  - Any type: same abnormal marker appears across 2+ tests with no workup or explanation
  - Recurrent: threshold crossed with no investigation of underlying cause

active --- Ongoing episode or treatment course where the end date has not yet passed.
  - If medications[].end_date is present and has passed -> set resolved + soft_resolution: true
  - If no end_date is defined and last record is older than 6 weeks -> set resolved + soft_resolution: true
  - soft_resolution only applies to acute and recurrent types. Never to chronic.

monitoring --- No active treatment but a watchout exists:
  - Acute: abnormal lab finding from episode with no confirmed follow-up result
  - Recurrent: between episodes, vet has noted to monitor frequency; or recurrence_watch: true and a second episode has now occurred
  - Chronic: marker mildly outside range, vet has not initiated treatment. Never use for a stable chronic condition on consistent medication --- that is managed.

managed --- Chronic or recurrent only. Stable, on medication or regular rechecks, no missed intervals, no unresolved findings.

resolved --- Confirmed treatment end, no recurrence, no pending findings. Never apply to chronic without explicit vet confirmation. Silence on a chronic condition is never resolved.

STEP 3 --- BUILD DISPLAY LIST
Order: Severity ladder descending, most recent first within each group.
Display Line:
  - Chronic: [Condition] since [year] --- [one-line management status]
  - Recurrent: [N] episodes of [condition] since [year] --- last episode [month year]
  - Acute (last 30 days): condition, treatment, expected resolution
  - Acute (1-3 months ago): condition and resolution in one clause
  - Acute (beyond 3 months, no recurrence): collapse to resolved
Caps:
  - needs_attention / active / monitoring: show all
  - managed: all chronic; recurrent capped at 2 most recent
  - resolved: show only if fewer than 2 conditions exist in higher states; cap at 1
  - clean: nothing shown
Each condition must include a display_line that is complete and independently understandable when shown alone.
Generate a trend_label (<= 4 words) for each condition:
  acute: "Ongoing" or "Recent episode"
  recurrent: "Last episode [month year]"
  chronic: "Since [year]"
Ensure final conditions[] is fully pre-sorted and capped as per rules above (frontend will not reorder or cap).
Assign severity to each condition based on its final status:
  - "red" -> needs_attention
  - "yellow" -> active | monitoring
  - "green" -> managed | resolved

STEP 4 --- HEADLINE STATE
Highest status across all conditions: needs_attention > active > monitoring > managed > resolved > clean
This will be used directly for UI subtitle generation; ensure it reflects the highest severity condition accurately.

STEP 5 --- WRITE SUMMARY
Write a 2-3 sentence summary using the pet's name.
TONE: Warm, calm, and clear. Reassuring but informative. Do not use alarming or urgent language. If attention is needed, phrase it as a gentle suggestion (e.g., "worth discussing with your vet").
Content: Focus only on conditions and their current state. Do not repeat the display list verbatim. Add light context or continuity (past -> present where relevant). Never mention vaccines, nutrition, grooming, or health score.
For each condition, also generate an insight:
  1-2 short sentences. Explain current state and what it means. No alarming tone. Do not repeat display_line.

STEP 6 --- OUTPUT
Respond with valid JSON only. No prose outside the block.
{
  "headline_state": "needs_attention | active | monitoring | managed | resolved | clean",
  "conditions": [
    {
      "id": "string",
      "name": "string",
      "type": "chronic | recurrent | acute",
      "status": "needs_attention | active | monitoring | managed | resolved",
      "severity": "red | yellow | green",
      "trend_label": "string",
      "insight": "string",
      "display_line": "string",
      "recurrence_watch": true,
      "soft_resolution": true
    }
  ],
  "summary": "string",
  "meta": {
    "total_conditions": 0,
    "red_count": 0,
    "yellow_count": 0,
    "green_count": 0
  }
}
"""

_HEALTH_CONDITIONS_V2_FALLBACK: dict = {
    "headline_state": "clean",
    "conditions": [],
    "summary": "No active conditions on record. Keep up the great preventive care!",
    "meta": {"total_conditions": 0, "red_count": 0, "yellow_count": 0, "green_count": 0},
}


async def _generate_health_conditions_v2_gpt(
    aggregated_conditions: list[dict],
    pet_name: str,
) -> dict:
    """
    Call GPT with Health Prompt 5 to classify conditions, assign statuses,
    and build the structured conditions dashboard payload.

    Args:
        aggregated_conditions: Output of _aggregate_conditions_for_health_prompt().
        pet_name: Pet's name for personalised summary.

    Returns:
        Structured dict: {headline_state, conditions[], summary, meta}.
    """
    if not aggregated_conditions:
        fallback = dict(_HEALTH_CONDITIONS_V2_FALLBACK)
        fallback["summary"] = (
            f"{pet_name} has no active conditions on record. Keep up the great preventive care!"
            if pet_name else fallback["summary"]
        )
        return fallback

    client = _get_openai_client()
    today_str = date.today().isoformat()

    user_payload = {
        "today": today_str,
        "pet_name": pet_name or "your pet",
        "conditions": aggregated_conditions,
    }

    async def _call() -> str:
        response = await client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=1500,
            system=_HEALTH_CONDITIONS_V2_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(user_payload)}],
        )
        return response.content[0].text or "{}"

    raw = await retry_openai_call(_call)

    # Strip markdown fences if model wraps JSON.
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw.strip())

    try:
        parsed = json.loads(raw)
        # Validate required top-level keys.
        if "headline_state" not in parsed or "conditions" not in parsed:
            raise ValueError("Missing required keys in Health Prompt 5 response")
        # Ensure meta exists.
        if "meta" not in parsed:
            conditions_list = parsed.get("conditions") or []
            parsed["meta"] = {
                "total_conditions": len(conditions_list),
                "red_count": sum(1 for c in conditions_list if c.get("severity") == "red"),
                "yellow_count": sum(1 for c in conditions_list if c.get("severity") == "yellow"),
                "green_count": sum(1 for c in conditions_list if c.get("severity") == "green"),
            }
        return parsed
    except Exception as exc:
        logger.warning(
            "health_conditions_v2 JSON parse failed: %s | raw=%s", exc, raw[:500]
        )
        return _HEALTH_CONDITIONS_V2_FALLBACK


# --------------------------------------------------------------------------- #
#  Public API                                                                   #
# --------------------------------------------------------------------------- #

async def get_or_generate_insight(
    db: Session,
    pet_id: UUID,
    insight_type: str,
    pet: dict,
    conditions: list,
    health_score: dict | None,
    force: bool = False,
) -> dict:
    """
    Return a cached AI insight or generate a fresh one.

    If a cached insight exists and is less than AI_INSIGHT_CACHE_DAYS old
    (and force is False), return it immediately without calling GPT.
    Otherwise call GPT, persist the result, and return it.

    Args:
        db:           SQLAlchemy session.
        pet_id:       Pet UUID.
        insight_type: 'health_summary' or 'vet_questions'.
        pet:          Pet dict (from dashboard data).
        conditions:   List of condition dicts (from dashboard data).
        health_score: Health score dict (from dashboard data).
        force:        If True, bypass cache and re-generate.

    Returns:
        content_json dict (structure depends on insight_type).
    """
    stale_cutoff = datetime.utcnow() - timedelta(days=AI_INSIGHT_CACHE_DAYS)

    # Check cache
    if not force:
        existing = (
            db.query(PetAiInsight)
            .filter(
                PetAiInsight.pet_id == pet_id,
                PetAiInsight.insight_type == insight_type,
                PetAiInsight.generated_at >= stale_cutoff,
            )
            .first()
        )
        if existing:
            return existing.content_json

    # Generate fresh content
    pet_context = _build_pet_context(pet, conditions, health_score)
    try:
        normalized_insight_type = insight_type
        if insight_type.startswith("vet_questions"):
            # Allow per-condition cache keys like "vet_questions:<condition_id>".
            normalized_insight_type = "vet_questions"

        if normalized_insight_type == "health_conditions_v2":
            # Aggregate condition data from DB and run Health Prompt 5.
            aggregated = _aggregate_conditions_for_health_prompt(conditions)
            pet_name = pet.get("name") or "" if isinstance(pet, dict) else ""
            content = await _generate_health_conditions_v2_gpt(aggregated, pet_name)
        elif normalized_insight_type == "conditions_summary":
            content = await _generate_conditions_summary_gpt(pet_context)
        elif normalized_insight_type == "health_summary":
            content = await _generate_health_summary_gpt(pet_context)
        elif normalized_insight_type == "vet_questions":
            content = await _generate_vet_questions_gpt(pet_context)
        else:
            logger.error("Unknown insight_type: %s", insight_type)
            return {}
    except Exception as exc:
        logger.error("GPT insight generation failed for %s/%s: %s", pet_id, insight_type, exc)
        # Return graceful defaults rather than crashing
        if insight_type == "health_conditions_v2":
            return dict(_HEALTH_CONDITIONS_V2_FALLBACK)
        if insight_type in ("health_summary", "conditions_summary"):
            return {"summary": "Summary is currently unavailable."}
        return []

    # Upsert to DB (INSERT … ON CONFLICT DO UPDATE)
    try:
        db.execute(
            text("""
                INSERT INTO pet_ai_insights (pet_id, insight_type, content_json, generated_at)
                VALUES (:pet_id, :insight_type, CAST(:content_json AS jsonb), NOW())
                ON CONFLICT (pet_id, insight_type)
                DO UPDATE SET content_json = EXCLUDED.content_json,
                              generated_at = NOW()
            """),
            {
                "pet_id": str(pet_id),
                "insight_type": insight_type,
                "content_json": json.dumps(content),
            },
        )
        db.commit()
    except Exception as exc:
        logger.error("Failed to upsert AI insight to DB: %s", exc)
        db.rollback()

    return content


# --------------------------------------------------------------------------- #
#  Nutrition Importance — separate cache with longer TTL                        #
# --------------------------------------------------------------------------- #

_NUTRITION_IMPORTANCE_FALLBACK = (
    "Good nutrition is the foundation of your pet's health at every life stage. "
    "The right balance of proteins, fats, vitamins, and minerals supports their "
    "energy levels, immune system, coat condition, and long-term organ health. "
    "Every meal is an opportunity to invest in a longer, healthier life for your pet."
)


async def _generate_nutrition_importance_gpt(pet: Pet) -> dict:
    """
    Generate a warm 3-4 sentence note on why nutrition matters for this specific pet.

    Personalised to species, breed, and age so the note feels relevant rather than generic.

    Returns:
        {"note": "<3-4 sentence plain-text note>"}
    """
    age_years: float = (date.today() - pet.dob).days / 365.25 if pet.dob else 2.0
    breed_str = pet.breed or pet.species

    system_prompt = (
        "You are a friendly pet nutritionist writing a short note for a pet owner's health dashboard. "
        "Write a warm, practical 3-4 sentence note explaining why good nutrition is especially important "
        f"for a {age_years:.1f}-year-old {pet.species} of the {breed_str} breed. "
        "Cover their life stage, species-specific dietary needs, and the long-term health benefits. "
        "Be encouraging and parent-friendly. Plain text only — no bullets, headers, or markdown."
    )

    client = _get_openai_client()

    async def _call() -> str:
        response = await client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0.6,
            max_tokens=200,
            system=system_prompt,
            messages=[{"role": "user", "content": "Generate the nutrition importance note."}],
        )
        return response.content[0].text or ""

    try:
        note = await retry_openai_call(_call)
        note = note.strip()
        if not note:
            raise ValueError("Empty response")
        return {"note": note}
    except Exception as exc:
        logger.warning("nutrition_importance GPT failed: %s", exc)
        return {"note": _NUTRITION_IMPORTANCE_FALLBACK}


async def get_or_generate_nutrition_importance(db: Session, pet_id: UUID) -> dict:
    """
    Return a cached 'why nutrition matters' note for this pet, or generate a fresh one.

    Cached for NUTRITION_IMPORTANCE_CACHE_DAYS (30 days). Stored in pet_ai_insights
    with insight_type='nutrition_importance'.

    Args:
        db:     SQLAlchemy session.
        pet_id: Pet UUID.

    Returns:
        {"note": "<plain-text nutrition importance note>"}
    """
    stale_cutoff = datetime.utcnow() - timedelta(days=NUTRITION_IMPORTANCE_CACHE_DAYS)

    existing = (
        db.query(PetAiInsight)
        .filter(
            PetAiInsight.pet_id == pet_id,
            PetAiInsight.insight_type == "nutrition_importance",
            PetAiInsight.generated_at >= stale_cutoff,
        )
        .first()
    )
    if existing:
        return existing.content_json

    # Load pet for personalisation
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        return {"note": _NUTRITION_IMPORTANCE_FALLBACK}

    content = await _generate_nutrition_importance_gpt(pet)

    try:
        db.execute(
            text("""
                INSERT INTO pet_ai_insights (pet_id, insight_type, content_json, generated_at)
                VALUES (:pet_id, :insight_type, CAST(:content_json AS jsonb), NOW())
                ON CONFLICT (pet_id, insight_type)
                DO UPDATE SET content_json = EXCLUDED.content_json,
                              generated_at = NOW()
            """),
            {
                "pet_id": str(pet_id),
                "insight_type": "nutrition_importance",
                "content_json": json.dumps(content),
            },
        )
        db.commit()
    except Exception as exc:
        logger.error("Failed to upsert nutrition_importance insight: %s", exc)
        db.rollback()

    return content


async def generate_recognition_bullets(db: Session, pet: Pet) -> list[Bullet]:
    """
    Build deterministic recognition bullets for the dashboard's What We Found card.

    Bullets are observational and traceable to DB records only (no GPT).
    Output order is fixed: conditions first, preventive second, diet last.

    Args:
        db: SQLAlchemy session.
        pet: Pet model instance.

    Returns:
        Up to three bullets of shape {icon, label}.
    """
    if not pet:
        return []

    active_condition_count = (
        db.query(func.count(Condition.id))
        .filter(
            Condition.pet_id == pet.id,
            Condition.is_active.is_(True),
        )
        .scalar()
        or 0
    )

    # Base filter for tracked preventive items (core master + custom).
    _base_preventive_q = (
        db.query(PreventiveRecord)
        .outerjoin(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
        .outerjoin(CustomPreventiveItem, PreventiveRecord.custom_preventive_item_id == CustomPreventiveItem.id)
        .filter(
            PreventiveRecord.pet_id == pet.id,
            PreventiveRecord.last_done_date.isnot(None),
            or_(
                PreventiveMaster.is_core.is_(True),
                CustomPreventiveItem.id.isnot(None),
            ),
        )
    )
    # Match vaccine keywords against BOTH master and custom item names.
    # Vaccines logged as custom items (master=NULL after outer-join) would
    # never match a filter on PreventiveMaster.item_name alone.
    _vaccine_filter = or_(
        *[PreventiveMaster.item_name.ilike(f"%{kw}%") for kw in _VACCINE_BULLET_TERMS],
        *[CustomPreventiveItem.item_name.ilike(f"%{kw}%") for kw in _VACCINE_BULLET_TERMS],
    )
    vaccine_count = (
        _base_preventive_q.filter(_vaccine_filter).count()
    )
    on_schedule_preventive_count = _base_preventive_q.count()
    other_preventive_count = on_schedule_preventive_count - vaccine_count

    diet_items: list[DietItem] = (
        db.query(DietItem)
        .filter(DietItem.pet_id == pet.id)
        .order_by(DietItem.created_at)
        .all()
    )

    bullets: list[Bullet] = []

    # 1. Conditions — always present
    if active_condition_count > 0:
        bullets.append(
            {
                "icon": "🩺",
                "label": (
                    f"{active_condition_count} active condition"
                    f"{'s' if active_condition_count != 1 else ''} being managed"
                ),
            }
        )
    else:
        bullets.append(
            {"icon": "🩺", "label": "No health conditions found"}
        )

    # 2. Preventive care — split into vaccines vs other preventive items
    if on_schedule_preventive_count > 0:
        if vaccine_count > 0 and other_preventive_count > 0:
            label = (
                f"{vaccine_count} vaccine{'s' if vaccine_count != 1 else ''} and "
                f"{other_preventive_count} preventive care item"
                f"{'s' if other_preventive_count != 1 else ''} tracked"
            )
        elif vaccine_count > 0:
            label = f"{vaccine_count} vaccine{'s' if vaccine_count != 1 else ''} tracked"
        else:
            label = (
                f"{other_preventive_count} preventive care item"
                f"{'s' if other_preventive_count != 1 else ''} tracked"
            )
        bullets.append({"icon": "💉", "label": label})
    else:
        bullets.append(
            {"icon": "💉", "label": "0 preventive care items tracked"}
        )

    # 3. Diet — build a specific food + supplement line.
    # What We Found shows all food types (packaged + homemade).
    food_items = [d for d in diet_items if d.type in ("packaged", "homemade")]
    supplement_items = [d for d in diet_items if d.type == "supplement"]

    if food_items or supplement_items:
        bullets.append(
            {"icon": "🍽️", "label": _format_found_diet_summary(food_items, supplement_items)}
        )
    else:
        bullets.append({"icon": "🍽️", "label": "No diet entries recorded"})

    return bullets[:3]


def _extract_orderable_item_key_and_name(item: dict[str, Any]) -> tuple[str, str] | None:
    """Extract a stable id and display name from an orderable item payload."""
    if not isinstance(item, dict):
        return None
    item_id = item.get("item_id") or item.get("id") or item.get("name")
    item_name = item.get("name") or item.get("label") or item_id
    if not item_id or not item_name:
        return None
    return str(item_id), str(item_name)


async def generate_care_plan_reasons(
    db: Session,
    pet: Pet,
    orderable_items: list[dict[str, Any]],
    diet_summary: dict | None = None,
) -> dict[str, str]:
    """
    Generate one-sentence reasons for orderable care plan items.

    Results are cached in pet_ai_insights with a 1-hour TTL.  Using a short
    TTL (rather than the 7-day insight TTL) ensures reasons stay current when
    care-plan items change, while preventing every dashboard load from hitting
    the Claude API concurrently.

    Args:
        db: SQLAlchemy session.
        pet: Pet model instance.
        orderable_items: List of orderable item payloads with id/name fields.
        diet_summary: Pre-computed diet summary dict; if provided, skips the
            get_diet_summary() OpenAI call to avoid a redundant round-trip.

    Returns:
        Mapping of item_id -> reason sentence.
    """
    if not pet or not orderable_items:
        return {}

    _CARE_PLAN_REASONS_CACHE_HOURS = 1
    _CARE_PLAN_REASONS_INSIGHT_TYPE = "care_plan_reasons"

    # --- Cache check (1-hour TTL) ---
    stale_cutoff = datetime.utcnow() - timedelta(hours=_CARE_PLAN_REASONS_CACHE_HOURS)
    try:
        cached = (
            db.query(PetAiInsight)
            .filter(
                PetAiInsight.pet_id == pet.id,
                PetAiInsight.insight_type == _CARE_PLAN_REASONS_INSIGHT_TYPE,
                PetAiInsight.generated_at >= stale_cutoff,
            )
            .first()
        )
        if cached and isinstance(cached.content_json, dict):
            return cached.content_json.get("reasons", {})
    except Exception as exc:
        logger.warning("care_plan_reasons cache read failed for pet %s: %s", pet.id, exc)

    try:
        item_map: dict[str, str] = {}
        for item in orderable_items:
            extracted = _extract_orderable_item_key_and_name(item)
            if extracted:
                item_id, item_name = extracted
                item_map[item_id] = item_name

        if not item_map:
            return {}

        active_conditions = (
            db.query(Condition.name)
            .filter(
                Condition.pet_id == pet.id,
                Condition.is_active.is_(True),
            )
            .all()
        )
        condition_names = [row[0] for row in active_conditions if row and row[0]]

        age_months = _get_pet_age_months(pet)
        try:
            weight_kg = float(pet.weight) if pet.weight is not None else None
        except (TypeError, ValueError):
            weight_kg = None

        breed_size = _get_breed_size(weight_kg, pet.breed)
        life_stage = _get_life_stage(age_months, breed_size).value

        # Use caller-supplied diet_summary to avoid a redundant OpenAI call when
        # the dashboard has already fetched it in the parallel enrichment phase.
        nutrition_summary = diet_summary if diet_summary is not None else await get_diet_summary(db, pet)
        missing_micros = nutrition_summary.get("missing_micros", [])
        nutrition_gap_names = [
            str(gap.get("name"))
            for gap in missing_micros
            if isinstance(gap, dict) and gap.get("name")
        ]
    except Exception as exc:
        logger.warning("care_plan_reasons context build failed for pet %s: %s", pet.id, exc)
        return {}

    conditions_text = ", ".join(condition_names) if condition_names else "none"
    nutrition_gaps_text = ", ".join(nutrition_gap_names) if nutrition_gap_names else "none identified"
    items_text = "\n".join([f"- {item_id}: {name}" for item_id, name in item_map.items()])

    system_prompt = (
        "You are a veterinary care-plan assistant. "
        "For each orderable item id, write exactly one sentence that explains why the item is relevant "
        "based on life stage, active health context, and nutrition context. "
        "Return ONLY a valid JSON object where each key is item id and each value is the reason string. "
        "No markdown, no extra keys, no recommendations beyond context, and no alarming language."
    )

    user_prompt = (
        f"Pet: {pet.name} ({pet.species}, breed={pet.breed or 'unknown'})\n"
        f"Life stage: {life_stage}\n"
        f"Active conditions: {conditions_text}\n"
        f"Nutrition gaps: {nutrition_gaps_text}\n"
        "Orderable items:\n"
        f"{items_text}"
    )

    client = _get_openai_client()

    async def _call() -> str:
        response = await client.messages.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=500,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.content[0].text or "{}"

    try:
        raw = await retry_openai_call(_call)
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object for care plan reasons")

        reasons: dict[str, str] = {}
        for item_id in item_map:
            reason = parsed.get(item_id)
            if not isinstance(reason, str):
                continue
            one_line_reason = " ".join(reason.strip().split())
            if not one_line_reason:
                continue
            if not one_line_reason.endswith((".", "!", "?")):
                one_line_reason = f"{one_line_reason}."
            reasons[item_id] = one_line_reason

        # --- Persist to cache (only if GPT returned usable reasons) ---
        if reasons:
            try:
                db.execute(
                    text("""
                        INSERT INTO pet_ai_insights (pet_id, insight_type, content_json, generated_at)
                        VALUES (:pet_id, :insight_type, CAST(:content_json AS jsonb), NOW())
                        ON CONFLICT (pet_id, insight_type)
                        DO UPDATE SET content_json = EXCLUDED.content_json,
                                      generated_at = NOW()
                    """),
                    {
                        "pet_id": str(pet.id),
                        "insight_type": _CARE_PLAN_REASONS_INSIGHT_TYPE,
                        "content_json": json.dumps({"reasons": reasons}),
                    },
                )
                db.commit()
            except Exception as cache_exc:
                logger.warning("care_plan_reasons cache write failed for pet %s: %s", pet.id, cache_exc)
                db.rollback()

        return reasons
    except Exception as exc:
        logger.warning("care_plan_reasons generation failed for pet %s: %s", pet.id, exc)
        return {}
