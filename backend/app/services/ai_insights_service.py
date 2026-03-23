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

Model: OPENAI_QUERY_MODEL (gpt-4.1-mini) — sufficient for structured text
generation; cheaper than the extraction model.

Failure behaviour: If GPT or the DB call fails, the error is logged and a
sensible default payload is returned so the dashboard never crashes.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import OPENAI_QUERY_MODEL
from app.models.pet_ai_insight import PetAiInsight
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

# Re-generate if the cached insight is older than this many days.
AI_INSIGHT_CACHE_DAYS = 7

# --------------------------------------------------------------------------- #
#  Lazy OpenAI client                                                           #
# --------------------------------------------------------------------------- #

_openai_client = None


def _get_openai_client():
    """Lazy-initialise AsyncOpenAI client (avoids import-time errors)."""
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
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
        response = await client.chat.completions.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or "{}"

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
        response = await client.chat.completions.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=500,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or "{}"

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
        response = await client.chat.completions.create(
            model=OPENAI_QUERY_MODEL,
            temperature=0,
            max_tokens=800,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or "[]"

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


def _build_pet_context(pet, conditions: list, health_score: dict) -> str:
    """
    Build a compact plain-text context string for GPT prompts.

    Includes: species, breed, age, active conditions, medications,
    overdue monitoring items, and the health score.
    """
    from datetime import date

    today = date.today()
    lines = []

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

    # Health score
    score = health_score.get("score", 0)
    label = health_score.get("label", "Unknown")
    lines.append(f"Health score: {score}/100 ({label})")
    draggers = health_score.get("draggers", [])
    if draggers:
        dragger_names = ", ".join(d.get("category", "") for d in draggers)
        lines.append(f"Weak areas: {dragger_names}")

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
#  Public API                                                                   #
# --------------------------------------------------------------------------- #

async def get_or_generate_insight(
    db: Session,
    pet_id: UUID,
    insight_type: str,
    pet: dict,
    conditions: list,
    health_score: dict,
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
        if insight_type == "conditions_summary":
            content = await _generate_conditions_summary_gpt(pet_context)
        elif insight_type == "health_summary":
            content = await _generate_health_summary_gpt(pet_context)
        elif insight_type == "vet_questions":
            content = await _generate_vet_questions_gpt(pet_context)
        else:
            logger.error("Unknown insight_type: %s", insight_type)
            return {}
    except Exception as exc:
        logger.error("GPT insight generation failed for %s/%s: %s", pet_id, insight_type, exc)
        # Return graceful defaults rather than crashing
        if insight_type in ("health_summary", "conditions_summary"):
            return {"summary": "Summary is currently unavailable."}
        return []

    # Upsert to DB (INSERT … ON CONFLICT DO UPDATE)
    try:
        db.execute(
            text("""
                INSERT INTO pet_ai_insights (pet_id, insight_type, content_json, generated_at)
                VALUES (:pet_id, :insight_type, :content_json::jsonb, NOW())
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
