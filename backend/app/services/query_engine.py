"""
PetCircle Phase 1 — Strict Query Engine (Module 14)

Answers user questions about their pet's health records using OpenAI GPT.
The model is strictly grounded in the pet's data — no external knowledge,
no medical advice, no hallucinated information.

Model configuration (from constants — never hardcoded):
    - Model: OPENAI_QUERY_MODEL (gpt-4.1)
    - Temperature: 0 (deterministic responses)
    - Max tokens: 1500

System prompt enforces strict grounding:
    - Only answer using provided data.
    - If information is unavailable, say exactly:
      "I don't have that information in your pet's records."
    - No medical advice.
    - No external knowledge.

Retry policy:
    - Uses retry_openai_call() from utils/retry.py.
    - 3 attempts (1s, 2s backoff) — from constants.
    - On final failure: return error message, never crash.

Context building:
    - Pet profile (name, species, breed, age, weight).
    - Preventive records (item names, dates, statuses).
    - Reminders (upcoming items and due dates).
    - Documents (upload history and extraction status).

Rules:
    - All model config from constants.py.
    - API key from settings (env var) — never hardcoded.
    - No medical advice under any circumstances.
    - If data not available, explicit "I don't have that information" response.
"""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import (
    OPENAI_QUERY_MAX_TOKENS,
    OPENAI_QUERY_MODEL,
    OPENAI_QUERY_TEMPERATURE,
)
from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.contact import Contact
from app.models.diagnostic_test_result import DiagnosticTestResult
from app.models.diet_item import DietItem
from app.models.document import Document
from app.models.pet import Pet
from app.models.pet_ai_insight import PetAiInsight
from app.models.pet_life_stage_trait import PetLifeStageTrait
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.models.weight_history import WeightHistory
from app.services.diet_service import split_diet_items_by_type
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

_anthropic_query_client = None


def _get_openai_query_client():
    """Return a cached AI client for queries (provider-agnostic, created on first call)."""
    global _anthropic_query_client
    if _anthropic_query_client is None:
        from app.utils.ai_client import get_ai_client  # noqa: PLC0415
        _anthropic_query_client = get_ai_client()
    return _anthropic_query_client


# --- System prompt for strict query engine ---
# Enforces grounding: only use provided data, no external knowledge.
# Exact wording from Module 14 specification.
QUERY_SYSTEM_PROMPT = (
    "You are PetCircle, a friendly and knowledgeable pet health assistant on WhatsApp. "
    "You answer the pet parent's questions using ONLY the pet data provided below. "
    "You have access to the pet's full health profile including conditions, medications, "
    "diagnostic results, diet, weight history, vet contacts, and "
    "preventive care records.\n\n"
    "Rules:\n"
    "- Answer using ONLY the provided data. Never use external knowledge.\n"
    "- If information is not available, say: "
    "\"I don't have that information in your pet's records.\"\n"
    "- Do NOT provide medical advice or diagnoses. For medical concerns, "
    "suggest the parent consult their vet (include vet contact if available).\n"
    "- Be warm, concise, and helpful. Use the pet's name.\n"
    "- When discussing conditions or medications, present facts from the records "
    "without interpreting severity or recommending changes.\n"
    "- For overdue items, gently remind the parent without being alarmist.\n"
    "- Do NOT provide grooming information, grooming schedules, or grooming advice. "
    "PetCircle does not track grooming.\n"
    "- Do NOT help with scheduling vet visits or appointments. PetCircle does not "
    "provide vet visit scheduling. If asked, suggest the parent contact their vet directly.\n"
    "- Do NOT mention health score, scoring, or numeric wellness ratings in answers, even if asked.\n"
    "- Users can always add more health records by sending documents (photos, PDFs) directly "
    "in this WhatsApp chat at any time. If a user asks about adding records, uploading documents, "
    "or sharing more information, confirm they can share documents right here.\n"
    "- Distinguish between items the pet is actively tracking (items with a recorded last_done_date "
    "and due dates) and items that have no history. Items without any last_done_date are NOT "
    "'upcoming' — they are unstarted recommendations. Never describe unstarted recommendations as "
    "'upcoming' or 'not been done yet'. Only items with recorded completion history should be "
    "described as 'upcoming' or 'overdue'.\n"
    "- When summarising what has been done vs what is upcoming, keep the two lists separate: "
    "(1) completed/tracked items with dates, (2) recommended additions the parent may want to "
    "consider. Do NOT lump them into one list.\n"
    "- Format responses for WhatsApp (use *bold* for emphasis, keep it readable).\n"
    "- CONVERSATION CONTEXT: You may be given previous messages from this conversation. "
    "Use them to understand what the user is referring to. Short follow-up messages like "
    "'what about X?', 'and the next one?', 'is that normal?', or 'tell me more' refer to "
    "the topic just discussed — resolve them using the prior exchange before answering. "
    "Always interpret ambiguous or incomplete messages in light of the conversation history. "
    "Never ask the user to repeat themselves if the context makes their intent clear.\n"
    "- COLLOQUIAL RESPONSES: When the user sends a short casual message like 'cool', 'great', "
    "'ok', 'awesome', 'perfect', 'thanks', 'got it', or similar, treat it as an acknowledgment "
    "of what was just discussed. Respond warmly and briefly in context — for example, if you "
    "just told them about their pet's upcoming vaccination, a reply of 'great' should get a "
    "response like 'Glad that's helpful! Let me know if you have any other questions about "
    "[pet name].' Do NOT re-summarise the previous answer. Keep the reply short and warm.\n"
    "- FAREWELLS: When the user says goodbye ('bye', 'see you', 'cya', etc.), close the "
    "conversation warmly and in context. Reference what was just discussed if relevant — "
    "e.g. if you just reminded them about Max's deworming, say something like 'Bye! Hope "
    "Max's deworming goes smoothly! 🐾 I'm always here when you need me.' Keep it brief."
)


def _is_score_related_text(value: str) -> bool:
    """Return True when text appears to reference health scoring metrics."""
    text = (value or "").strip().lower()
    if not text:
        return False

    blocked_tokens = (
        "health score",
        "overall score",
        "wellness score",
        "score/100",
        "/100",
        "dragger",
        "breakdown",
    )
    return any(token in text for token in blocked_tokens)


def _build_pet_context(db: Session, pet_id: UUID) -> str:
    """
    Build a text context string from the pet's database records.

    This context is passed to GPT as the data source for answering
    questions. It includes all relevant information the user might
    ask about, structured for clarity.

    Data included:
        - Pet profile (name, species, breed, gender, dob, weight, neutered).
        - Preventive records (item name, last done, next due, status).
        - Active reminders (item name, due date, status).
        - Documents (count, types, extraction statuses).

    All data is read from DB — no hardcoded values.

    Args:
        db: SQLAlchemy database session.
        pet_id: UUID of the pet.

    Returns:
        Formatted text string with all pet data for GPT context.
    """
    # --- Pet profile ---
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        return "No pet data available."

    user = db.query(User).filter(User.id == pet.user_id).first()

    context_parts = []

    # Pet profile section.
    context_parts.append("=== Pet Profile ===")
    context_parts.append(f"Name: {pet.name}")
    context_parts.append(f"Species: {pet.species}")
    if pet.breed:
        context_parts.append(f"Breed: {pet.breed}")
    if pet.gender:
        context_parts.append(f"Gender: {pet.gender}")
    if pet.dob:
        context_parts.append(f"Date of Birth: {pet.dob}")
    if pet.weight:
        context_parts.append(f"Weight: {pet.weight} kg")
    if pet.neutered is not None:
        context_parts.append(f"Neutered: {'Yes' if pet.neutered else 'No'}")
    if user:
        context_parts.append(f"Owner: {user.full_name}")

    # --- Preventive records ---
    # Recurrence and item data always from preventive_master in DB.
    records = (
        db.query(PreventiveRecord, PreventiveMaster)
        .join(
            PreventiveMaster,
            PreventiveRecord.preventive_master_id == PreventiveMaster.id,
        )
        .filter(PreventiveRecord.pet_id == pet_id)
        .order_by(PreventiveRecord.next_due_date.asc())
        .all()
    )

    context_parts.append("\n=== Preventive Health Records ===")
    if records:
        for record, master in records:
            if record.last_done_date:
                context_parts.append(
                    f"- {master.item_name} ({master.category}): "
                    f"Last done: {record.last_done_date}, "
                    f"Next due: {record.next_due_date}, "
                    f"Status: {record.status}"
                )
            else:
                context_parts.append(
                    f"- {master.item_name} ({master.category}): "
                    f"(no history — recommendation only, not yet started by owner)"
                )
    else:
        context_parts.append("No preventive records found.")

    # --- Reminders ---
    reminders = (
        db.query(Reminder, PreventiveRecord, PreventiveMaster)
        .join(
            PreventiveRecord,
            Reminder.preventive_record_id == PreventiveRecord.id,
        )
        .join(
            PreventiveMaster,
            PreventiveRecord.preventive_master_id == PreventiveMaster.id,
        )
        .filter(
            PreventiveRecord.pet_id == pet_id,
            Reminder.status.in_(["pending", "sent"]),
        )
        .order_by(Reminder.next_due_date.asc())
        .all()
    )

    context_parts.append("\n=== Active Reminders ===")
    if reminders:
        for reminder, record, master in reminders:
            context_parts.append(
                f"- {master.item_name}: Due {reminder.next_due_date}, "
                f"Status: {reminder.status}"
            )
    else:
        context_parts.append("No active reminders.")

    # --- Documents (fetched here, detailed output below) ---
    documents = (
        db.query(Document)
        .filter(Document.pet_id == pet_id)
        .all()
    )

    # --- Conditions ---
    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet_id)
        .order_by(Condition.diagnosed_at.desc().nullslast())
        .all()
    )

    context_parts.append("\n=== Medical Conditions ===")
    if conditions:
        for cond in conditions:
            status = "Active" if cond.is_active else "Resolved"
            line = f"- {cond.name} ({cond.condition_type}, {status})"
            if cond.diagnosis:
                line += f" — {cond.diagnosis}"
            if cond.diagnosed_at:
                line += f", diagnosed {cond.diagnosed_at}"
            if cond.managed_by:
                line += f", managed by: {cond.managed_by}"
            if cond.notes:
                line += f". Notes: {cond.notes}"
            context_parts.append(line)

            # Medications for this condition
            meds = (
                db.query(ConditionMedication)
                .filter(ConditionMedication.condition_id == cond.id)
                .all()
            )
            for med in meds:
                med_line = f"  • Med: {med.name}"
                if med.dose:
                    med_line += f", dose: {med.dose}"
                if med.frequency:
                    med_line += f", freq: {med.frequency}"
                if med.status:
                    med_line += f" ({med.status})"
                if med.refill_due_date:
                    med_line += f", refill due: {med.refill_due_date}"
                context_parts.append(med_line)

            # Monitoring for this condition
            monitors = (
                db.query(ConditionMonitoring)
                .filter(ConditionMonitoring.condition_id == cond.id)
                .all()
            )
            for mon in monitors:
                mon_line = f"  • Monitor: {mon.name}"
                if mon.frequency:
                    mon_line += f", every {mon.frequency}"
                if mon.next_due_date:
                    mon_line += f", next due: {mon.next_due_date}"
                if mon.last_done_date:
                    mon_line += f", last done: {mon.last_done_date}"
                context_parts.append(mon_line)
    else:
        context_parts.append("No conditions recorded.")

    # --- Diagnostic Test Results ---
    diagnostics = (
        db.query(DiagnosticTestResult)
        .filter(DiagnosticTestResult.pet_id == pet_id)
        .order_by(DiagnosticTestResult.observed_at.desc().nullslast())
        .limit(50)
        .all()
    )

    context_parts.append("\n=== Diagnostic Test Results ===")
    if diagnostics:
        for diag in diagnostics:
            val = diag.value_text or str(diag.value_numeric or "")
            line = f"- {diag.parameter_name} ({diag.test_type}): {val}"
            if diag.unit:
                line += f" {diag.unit}"
            if diag.reference_range:
                line += f" [ref: {diag.reference_range}]"
            if diag.status_flag and diag.status_flag != "normal":
                line += f" ⚠ {diag.status_flag.upper()}"
            if diag.observed_at:
                line += f" ({diag.observed_at})"
            context_parts.append(line)
    else:
        context_parts.append("No diagnostic test results.")

    # --- Weight History ---
    weights = (
        db.query(WeightHistory)
        .filter(WeightHistory.pet_id == pet_id)
        .order_by(WeightHistory.recorded_at.desc())
        .limit(10)
        .all()
    )

    context_parts.append("\n=== Weight History ===")
    if weights:
        for w in weights:
            line = f"- {w.weight} kg on {w.recorded_at}"
            if w.note:
                line += f" ({w.note})"
            context_parts.append(line)
    else:
        context_parts.append("No weight history recorded.")

    # --- Diet & Nutrition ---
    diet_items = (
        db.query(DietItem)
        .filter(DietItem.pet_id == pet_id)
        .all()
    )

    context_parts.append("\n=== Diet & Nutrition ===")
    if diet_items:
        split_items = split_diet_items_by_type(diet_items)

        context_parts.append("Foods:")
        if split_items["foods"] or split_items["other"]:
            for item in diet_items:
                item_type = (getattr(item, "type", "") or "").strip().lower()
                if item_type == "supplement":
                    continue
                line = f"- {item.label} ({item.type})"
                if item.brand:
                    line += f", brand: {item.brand}"
                if item.detail:
                    line += f" — {item.detail}"
                if item.daily_portion_g:
                    line += f", daily portion: {item.daily_portion_g}g"
                context_parts.append(line)
        else:
            context_parts.append("- No food items recorded.")

        context_parts.append("Supplements:")
        if split_items["supplements"]:
            for item in diet_items:
                item_type = (getattr(item, "type", "") or "").strip().lower()
                if item_type != "supplement":
                    continue
                line = f"- {item.label} (supplement)"
                if item.detail:
                    line += f" — {item.detail}"
                if item.doses_per_day:
                    line += f", {item.doses_per_day}x/day"
                context_parts.append(line)
        else:
            context_parts.append("- No supplements recorded.")
    else:
        context_parts.append("No diet information recorded.")

    # --- Vet & Healthcare Contacts ---
    contacts = (
        db.query(Contact)
        .filter(Contact.pet_id == pet_id)
        .all()
    )

    context_parts.append("\n=== Healthcare Contacts ===")
    if contacts:
        for c in contacts:
            line = f"- {c.name} ({c.role})"
            if c.clinic_name:
                line += f", {c.clinic_name}"
            if c.phone:
                line += f", phone: {c.phone}"
            context_parts.append(line)
    else:
        context_parts.append("No healthcare contacts on file.")

    # --- Documents (detailed) ---
    context_parts.append("\n=== Uploaded Documents ===")
    if documents:
        context_parts.append(f"Total documents: {len(documents)}")
        for doc in documents:
            line = f"- {doc.document_name or 'Unnamed'}"
            if doc.document_category:
                line += f" ({doc.document_category})"
            if doc.event_date:
                line += f", event date: {doc.event_date}"
            if doc.doctor_name:
                line += f", doctor: {doc.doctor_name}"
            if doc.hospital_name:
                line += f", hospital: {doc.hospital_name}"
            line += f" [{doc.extraction_status}]"
            context_parts.append(line)
        pending = sum(1 for d in documents if d.extraction_status == "pending")
        if pending > 0:
            context_parts.append(
                f"NOTE: {pending} document(s) are still being processed."
            )
    else:
        context_parts.append("No documents uploaded.")

    # --- Life Stage Traits ---
    life_stage = (
        db.query(PetLifeStageTrait)
        .filter(PetLifeStageTrait.pet_id == pet_id)
        .order_by(PetLifeStageTrait.generated_at.desc().nullslast())
        .first()
    )

    if life_stage:
        context_parts.append(f"\n=== Life Stage: {life_stage.life_stage} ===")
        if life_stage.breed_size:
            context_parts.append(f"Breed size: {life_stage.breed_size}")
        if life_stage.traits:
            insights = life_stage.traits if isinstance(life_stage.traits, list) else []
            for i in insights[:5]:
                text = i.get("text", i) if isinstance(i, dict) else i
                context_parts.append(f"- {text}")

    # --- AI Insights (cached) ---
    insights = (
        db.query(PetAiInsight)
        .filter(PetAiInsight.pet_id == pet_id)
        .order_by(PetAiInsight.generated_at.desc().nullslast())
        .limit(3)
        .all()
    )

    if insights:
        context_parts.append("\n=== AI Health Insights ===")
        for ins in insights:
            context_parts.append(f"[{ins.insight_type}]:")
            content = ins.content_json
            if isinstance(content, dict):
                for k, v in content.items():
                    key_text = str(k)
                    value_text = str(v)
                    if _is_score_related_text(key_text) or _is_score_related_text(value_text):
                        continue
                    context_parts.append(f"- {k}: {v}")
            elif isinstance(content, list):
                for item in content[:5]:
                    item_text = str(item)
                    if _is_score_related_text(item_text):
                        continue
                    context_parts.append(f"- {item}")
            else:
                content_text = str(content)[:300]
                if not _is_score_related_text(content_text):
                    context_parts.append(content_text)

    return "\n".join(context_parts)


async def answer_pet_question(
    db: Session,
    pet_id: UUID,
    question: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Answer a user's question about their pet using GPT.

    The model is strictly grounded in the pet's database records.
    No external knowledge, no medical advice.

    Pipeline:
        1. Build context from pet's DB records.
        2. Build multi-turn messages array from conversation history (if any).
        3. Send combined system prompt (rules + pet data) + messages to GPT.
        4. Return the grounded answer.

    On GPT failure:
        - Return a user-friendly error message.
        - Never crash the application.

    Args:
        db: SQLAlchemy database session.
        pet_id: UUID of the pet being queried.
        question: The user's current question text.
        conversation_history: Optional list of prior turns as
            [{"role": "user"|"assistant", "content": str}, ...].
            Used so the model can resolve follow-up questions and
            short references without the user repeating context.

    Returns:
        Dictionary with:
            - answer: GPT's grounded response.
            - status: 'success' or 'error'.
    """
    # Build context from pet's database records.
    context = _build_pet_context(db, pet_id)

    # Embed pet data directly in the system prompt so it is available
    # across all conversation turns without repeating it per message.
    system_with_context = (
        QUERY_SYSTEM_PROMPT
        + "\n\n=== Pet Data ===\n"
        + context
    )

    # Build messages array: prior turns (if any) + current question.
    # The Anthropic API requires the first message to have role "user".
    # Filter out any leading assistant turns defensively before appending.
    messages: list[dict] = []
    if conversation_history:
        for turn in conversation_history:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        # Strip any leading assistant turns so the array always starts with "user".
        while messages and messages[0]["role"] == "assistant":
            messages.pop(0)
    messages.append({"role": "user", "content": question})

    try:
        # Reuse cached client — avoids recreating on every query.
        client = _get_openai_query_client()

        async def _make_call() -> str:
            """Inner function wrapped by retry_openai_call."""
            response = await client.messages.create(
                model=OPENAI_QUERY_MODEL,
                temperature=OPENAI_QUERY_TEMPERATURE,
                max_tokens=OPENAI_QUERY_MAX_TOKENS,
                system=system_with_context,
                messages=messages,
            )
            return response.content[0].text

        # Retry with backoff: 3 attempts (1s, 2s) — from constants.
        answer = await retry_openai_call(_make_call)

        logger.info(
            "Query answered: pet_id=%s, question_length=%d, "
            "answer_length=%d",
            str(pet_id),
            len(question),
            len(answer) if answer else 0,
        )

        return {
            "answer": answer,
            "status": "success",
        }

    except Exception as e:
        # GPT failure — return user-friendly error, never crash.
        logger.error(
            "Query engine failed: pet_id=%s, error=%s",
            str(pet_id),
            str(e),
        )

        return {
            "answer": (
                "I'm sorry, I'm unable to process your question right now. "
                "Please try again later."
            ),
            "status": "error",
        }
