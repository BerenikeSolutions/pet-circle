"""PetCircle reminder template registry for category-stage specific messaging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from app.core.constants import STAGE_D3, STAGE_DUE, STAGE_OVERDUE, STAGE_T7

# Send-rule constants for reminder orchestration.
MAX_REMINDERS_PER_PET_PER_DAY: int = 1
MIN_DAYS_BETWEEN_SAME_ITEM_REMINDERS: int = 3
IGNORED_REMINDERS_MONTHLY_FALLBACK_THRESHOLD: int = 3

# Time rules (IST).
STANDARD_STAGE_SEND_TIMES: dict[str, time] = {
    STAGE_T7: time(hour=9, minute=0),
    STAGE_DUE: time(hour=10, minute=0),
    STAGE_D3: time(hour=9, minute=0),
    STAGE_OVERDUE: time(hour=9, minute=0),
}
HYGIENE_DUE_SEND_TIME: time = time(hour=10, minute=0)


@dataclass(frozen=True)
class ReminderTemplate:
    """Structured reminder template definition keyed by category/sub-type/stage."""

    category: str
    sub_type: str | None
    stage: str
    message_body: str
    cta_buttons: list[str]
    send_time: time
    variable_keys: list[str]


TemplateKey = tuple[str, str | None, str]


def _template(
    category: str,
    sub_type: str | None,
    stage: str,
    message_body: str,
    cta_buttons: list[str],
    variable_keys: list[str],
) -> ReminderTemplate:
    return ReminderTemplate(
        category=category,
        sub_type=sub_type,
        stage=stage,
        message_body=message_body,
        cta_buttons=cta_buttons,
        send_time=STANDARD_STAGE_SEND_TIMES.get(stage, STANDARD_STAGE_SEND_TIMES[STAGE_DUE]),
        variable_keys=variable_keys,
    )


REMINDER_TEMPLATES: dict[TemplateKey, ReminderTemplate] = {
    # Vaccines - First Time
    ("vaccine", "first_time", STAGE_T7): _template(
        "vaccine",
        "first_time",
        STAGE_T7,
        "Hi [Name] 🐾 [Pet]'s first vaccinations are coming up on [date] - DHPPi, Rabies, Kennel Cough and CCV. These protect against some of the most serious diseases in dogs. Plan a vet visit this week so you're not rushing on the day.",
        ["Remind Me Later", "Already Done - Log It"],
        ["Name", "Pet", "date"],
    ),
    ("vaccine", "first_time", STAGE_DUE): _template(
        "vaccine",
        "first_time",
        STAGE_DUE,
        "[Name], time for [Pet]'s vaccinations today 🐾 DHPPi, Rabies, Kennel Cough and CCV are all due. Head to your vet when you can - it's a short visit and makes a big difference for [Pet]'s protection.",
        ["Done - Log It", "Remind Me Later", "Schedule For ()"],
        ["Name", "Pet"],
    ),
    ("vaccine", "first_time", STAGE_D3): _template(
        "vaccine",
        "first_time",
        STAGE_D3,
        "Hi [Name] 🐾 Just checking - were [Pet]'s first vaccinations done? Log it so we can schedule the next round in the series.",
        ["Yes - Log It", "Pending - Remind Me Later", "Schedule For ()"],
        ["Name", "Pet"],
    ),
    ("vaccine", "first_time", STAGE_OVERDUE): _template(
        "vaccine",
        "first_time",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 We noticed [Pet]'s first vaccinations haven't been logged yet - it may be overdue. Could you take a moment to update it? This helps us schedule the next round in the series on time.",
        ["Completed - Log It", "Still Pending - Remind Me Later", "Schedule For ()"],
        ["Name", "Pet"],
    ),

    # Vaccines - Booster
    ("vaccine", "booster", STAGE_T7): _template(
        "vaccine",
        "booster",
        STAGE_T7,
        "Hi [Name] 🐾 [Pet]'s annual vaccination boosters are due on [date] - [vaccineList]. Plan a vet visit this week so you're not rushing on the day.",
        ["Remind Me Later", "Already Done - Log It"],
        ["Name", "Pet", "date", "vaccineList"],
    ),
    ("vaccine", "booster", STAGE_DUE): _template(
        "vaccine",
        "booster",
        STAGE_DUE,
        "[Name], [Pet]'s vaccination boosters are due today 🐾 [vaccineList]. Head to your vet when you can and log it once done.",
        ["Done - Log It", "Remind Me Later", "Schedule For ()"],
        ["Name", "Pet", "vaccineList"],
    ),
    ("vaccine", "booster", STAGE_D3): _template(
        "vaccine",
        "booster",
        STAGE_D3,
        "Hi [Name] 🐾 Just checking - were [Pet]'s boosters done? Log it so we keep the annual schedule on track.",
        ["Yes - Log It", "Pending - Remind Me Later", "Schedule For ()"],
        ["Name", "Pet"],
    ),
    ("vaccine", "booster", STAGE_OVERDUE): _template(
        "vaccine",
        "booster",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 It looks like [Pet]'s boosters might be overdue. Logging them now will help us get the annual schedule back on track - would you mind updating when you can?",
        ["Completed - Log It", "Still Pending - Remind Me Later", "Schedule For ()"],
        ["Name", "Pet"],
    ),

    # Deworming - Standard
    ("deworming", "standard", STAGE_T7): _template(
        "deworming",
        "standard",
        STAGE_T7,
        "Hi [Name] 🐾 [Pet]'s deworming is due on [date] - just 1 week away. Order now and have it delivered before the due date.",
        ["Order Now", "Remind Me Later", "Already Done - Log It"],
        ["Name", "Pet", "date"],
    ),
    ("deworming", "standard", STAGE_DUE): _template(
        "deworming",
        "standard",
        STAGE_DUE,
        "[Name], today is [Pet]'s deworming day 🐾 Intestinal parasites can build up quickly without regular protection. Order now for delivery or log it if already done.",
        ["Order Now", "Already Done - Log It", "Remind Me Later"],
        ["Name", "Pet"],
    ),
    ("deworming", "standard", STAGE_D3): _template(
        "deworming",
        "standard",
        STAGE_D3,
        "Hi [Name] 🐾 Just checking - did [Pet] get dewormed on [date]? Tap to log it or order if you still need to.",
        ["Yes - Log It", "Order Now", "Pending - Remind Me Later"],
        ["Name", "Pet", "date"],
    ),
    ("deworming", "standard", STAGE_OVERDUE): _template(
        "deworming",
        "standard",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 We haven't received a log for [Pet]'s deworming on [date] - it may have been missed. Could you tap to log it or place an order if you still need to?",
        ["Completed - Log It", "Order Now", "Pending - Remind Me Later"],
        ["Name", "Pet", "date"],
    ),

    # Flea & Tick - Standard
    ("flea_tick", "standard", STAGE_T7): _template(
        "flea_tick",
        "standard",
        STAGE_T7,
        "Hi [Name] 🐾 [Pet]'s monthly flea & tick protection is due on [date]. Order now and have it ready before the due date.",
        ["Order Now", "Remind Me Later", "Already Done - Log It"],
        ["Name", "Pet", "date"],
    ),
    ("flea_tick", "standard", STAGE_DUE): _template(
        "flea_tick",
        "standard",
        STAGE_DUE,
        "[Name], time for [Pet]'s monthly flea & tick dose today 🐾 In Mumbai's humidity this protection really matters. Order now or log it if already given.",
        ["Order Now", "Already Done - Log It", "Remind Me Later"],
        ["Name", "Pet"],
    ),
    ("flea_tick", "standard", STAGE_D3): _template(
        "flea_tick",
        "standard",
        STAGE_D3,
        "Hi [Name] 🐾 Was [Pet]'s flea & tick dose given this month? Log it to keep the monthly cycle on track.",
        ["Yes - Log It", "Order Now", "Pending - Remind Me Later"],
        ["Name", "Pet"],
    ),
    ("flea_tick", "standard", STAGE_OVERDUE): _template(
        "flea_tick",
        "standard",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 [Pet]'s flea & tick dose for this month doesn't seem to have been logged yet. A quick update will help keep the monthly cycle on track - please do this when you get a chance.",
        ["Completed - Log It", "Order Now", "Pending - Remind Me Later"],
        ["Name", "Pet"],
    ),

    # Food Order - Scheduled
    ("food", "scheduled", STAGE_T7): _template(
        "food",
        "scheduled",
        STAGE_T7,
        "Hi [Name] 🐾 Time for a quick check - how's [Pet]'s [Brand] supply looking? If you're getting low, tap below to reorder and keep their routine on track.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Brand"],
    ),
    ("food", "scheduled", STAGE_DUE): _template(
        "food",
        "scheduled",
        STAGE_DUE,
        "Hi [Name] 🐾 Don't let [Pet]'s [Brand] run out! Take a moment to check your supply and tap below to reorder - so their mealtime stays right on schedule.",
        ["Order Now", "Already Done - Log It", "Remind Me Later"],
        ["Name", "Pet", "Brand"],
    ),
    ("food", "scheduled", STAGE_D3): _template(
        "food",
        "scheduled",
        STAGE_D3,
        "Hi [Name] 🐾 Just a friendly nudge - is it time to top up [Pet]'s [Brand]? Tap below to reorder and make sure they never miss a meal.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Brand"],
    ),
    ("food", "scheduled", STAGE_OVERDUE): _template(
        "food",
        "scheduled",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 Just a friendly nudge - is it time to top up [Pet]'s [Brand]? Tap below to reorder and make sure they never miss a meal.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Brand"],
    ),

    # Food Order - Supply Led
    ("food", "supply_led", STAGE_T7): _template(
        "food",
        "supply_led",
        STAGE_T7,
        "Hi [Name] 🐾 [Pet]'s [Brand] is running low - about 7 days of supply left. Order now and get it delivered before [Pet] runs out.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Brand"],
    ),
    ("food", "supply_led", STAGE_DUE): _template(
        "food",
        "supply_led",
        STAGE_DUE,
        "[Name], [Pet]'s [Brand] runs out today 🐾 Order now for same-day or next-day delivery so [Pet] doesn't miss a meal.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Brand"],
    ),
    ("food", "supply_led", STAGE_D3): _template(
        "food",
        "supply_led",
        STAGE_D3,
        "Hi [Name] 🐾 Just checking - has [Pet]'s [Brand] been restocked? Let us know so we can schedule the next reorder on time.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Brand"],
    ),
    ("food", "supply_led", STAGE_OVERDUE): _template(
        "food",
        "supply_led",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 We noticed [Pet]'s [Brand] restock hasn't been confirmed yet and may be running late. Could you let us know the status so we can schedule the next reorder without delay?",
        ["Ordered Already", "Order Now", "Pending - Remind Me Later"],
        ["Name", "Pet", "Brand"],
    ),

    # Supplement Order - Scheduled
    ("supplement", "scheduled", STAGE_T7): _template(
        "supplement",
        "scheduled",
        STAGE_T7,
        "Hi [Name] 🐾 Quick reminder to check [Pet]'s supplement supply! Running low on any of them? Tap below to reorder what you need and keep their daily routine on track.\n\nHere's what [Pet] is currently taking:\n• [Supplement]",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Supplement"],
    ),
    ("supplement", "scheduled", STAGE_DUE): _template(
        "supplement",
        "scheduled",
        STAGE_DUE,
        "Hi [Name] 🐾 Don't let [Pet]'s supplements run out! Tap below to reorder what you need and make sure their wellness routine stays on track.\n\nHere's what [Pet] is currently taking:\n• [Supplement]",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Supplement"],
    ),
    ("supplement", "scheduled", STAGE_D3): _template(
        "supplement",
        "scheduled",
        STAGE_D3,
        "Hi [Name] 🐾 Just a friendly nudge - is it time to top up [Pet]'s supplements? Tap below to reorder and keep their daily routine uninterrupted.\n\nHere's what [Pet] is currently taking:\n• [Supplement]",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Supplement"],
    ),
    ("supplement", "scheduled", STAGE_OVERDUE): _template(
        "supplement",
        "scheduled",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 Just a friendly nudge - is it time to top up [Pet]'s supplements? Tap below to reorder and keep their daily routine uninterrupted.\n\nHere's what [Pet] is currently taking:\n• [Supplement]",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Supplement"],
    ),

    # Supplement Order - Supply Led
    ("supplement", "supply_led", STAGE_T7): _template(
        "supplement",
        "supply_led",
        STAGE_T7,
        "Hi [Name] 🐾 [Pet]'s [Supplement] will run out in about 7 days. Order now and have it delivered before the dose lapses.",
        ["Order Now", "Remind Me Later", "Already Done - Log It"],
        ["Name", "Pet", "Supplement"],
    ),
    ("supplement", "supply_led", STAGE_DUE): _template(
        "supplement",
        "supply_led",
        STAGE_DUE,
        "[Name], [Pet]'s [Supplement] runs out today 🐾 Order now to keep the dose uninterrupted - delivered straight to you.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Supplement"],
    ),
    ("supplement", "supply_led", STAGE_D3): _template(
        "supplement",
        "supply_led",
        STAGE_D3,
        "Hi [Name] 🐾 Was [Pet]'s [Supplement] refilled? Missing doses can affect the benefit over time. Tap to confirm or order if you still need to.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Supplement"],
    ),
    ("supplement", "supply_led", STAGE_OVERDUE): _template(
        "supplement",
        "supply_led",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 It looks like [Pet]'s [Supplement] refill may be overdue. Missing doses over time can affect the benefits - could you tap to confirm or place an order if you still need to?",
        ["Ordered Already", "Order Now", "Pending - Remind Me Later"],
        ["Name", "Pet", "Supplement"],
    ),

    # Chronic Medicine - Scheduled
    ("chronic_medicine", "scheduled", STAGE_T7): _template(
        "chronic_medicine",
        "scheduled",
        STAGE_T7,
        "Hi [Name] 🐾 Quick reminder to check [Pet]'s medicine supply! Running low on any of them? Tap below to reorder what you need and keep their daily routine on track.\n\nHere's what [Pet] is currently taking:\n• [Medicine]",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Medicine"],
    ),
    ("chronic_medicine", "scheduled", STAGE_DUE): _template(
        "chronic_medicine",
        "scheduled",
        STAGE_DUE,
        "Hi [Name] 🐾 Don't let [Pet]'s medicines run out! Tap below to reorder what you need and make sure their wellness routine stays on track.\n\nHere's what [Pet] is currently taking:\n• [Medicine]",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Medicine"],
    ),
    ("chronic_medicine", "scheduled", STAGE_D3): _template(
        "chronic_medicine",
        "scheduled",
        STAGE_D3,
        "Hi [Name] 🐾 Just a friendly nudge - is it time to refill [Pet]'s medication? Tap below to reorder and make sure their treatment stays on track without any gaps.\n\nHere's what [Pet] is currently on:\n• [Medicine]",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Medicine"],
    ),
    ("chronic_medicine", "scheduled", STAGE_OVERDUE): _template(
        "chronic_medicine",
        "scheduled",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 Just a friendly nudge - is it time to refill [Pet]'s medication? Tap below to reorder and make sure their treatment stays on track without any gaps.\n\nHere's what [Pet] is currently on:\n• [Medicine]",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Medicine"],
    ),

    # Chronic Medicine - Supply Led
    ("chronic_medicine", "supply_led", STAGE_T7): _template(
        "chronic_medicine",
        "supply_led",
        STAGE_T7,
        "Hi [Name] 🐾 [Pet]'s [Medicine] refill is due on [date] - 1 week away. Order now and have it delivered before the dose runs out.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Medicine", "date"],
    ),
    ("chronic_medicine", "supply_led", STAGE_DUE): _template(
        "chronic_medicine",
        "supply_led",
        STAGE_DUE,
        "[Name], [Pet]'s [Medicine] needs refilling today 🐾 Consistent dosing is important for managing [condition]. Order now for home delivery.",
        ["Order Now", "Already Done - Log It", "Remind Me Later"],
        ["Name", "Pet", "Medicine", "condition"],
    ),
    ("chronic_medicine", "supply_led", STAGE_D3): _template(
        "chronic_medicine",
        "supply_led",
        STAGE_D3,
        "Hi [Name] 🐾 Just checking - did [Pet]'s [Medicine] get refilled? Consistent dosing matters for [condition] management. Tap to log or order if needed.",
        ["Order Now", "Already Ordered", "Remind Me Later"],
        ["Name", "Pet", "Medicine", "condition"],
    ),
    ("chronic_medicine", "supply_led", STAGE_OVERDUE): _template(
        "chronic_medicine",
        "supply_led",
        STAGE_OVERDUE,
        "Hi [Name] 🐾 We haven't received a log for [Pet]'s [Medicine] refill yet - consistent dosing is important for [condition] management. Please tap to log or order as soon as you can.",
        ["Ordered Already", "Order Now", "Pending - Remind Me Later"],
        ["Name", "Pet", "Medicine", "condition"],
    ),

    # Vet Follow-ups - Standard
    ("vet_followup", None, STAGE_T7): _template(
        "vet_followup",
        None,
        STAGE_T7,
        "Hi [Name] 🐾 [Pet]'s follow-up with [vetName] is due on [date] - 1 week away. Plan your vet visit ahead so you don't miss it.",
        ["Already Booked", "Remind Me Later"],
        ["Name", "Pet", "vetName", "date"],
    ),
    ("vet_followup", None, STAGE_DUE): _template(
        "vet_followup",
        None,
        STAGE_DUE,
        "[Name], [Pet]'s vet follow-up is today 🐾 Log it once done so we can keep the care plan updated.",
        ["Done - Log It", "Remind Me Later", "Schedule For ()"],
        ["Name", "Pet"],
    ),
    ("vet_followup", None, STAGE_D3): _template(
        "vet_followup",
        None,
        STAGE_D3,
        "Hi [Name] 🐾 Was [Pet]'s follow-up with [vetName] completed? Log it so we can track the next step in the care plan.",
        ["Yes - Log It", "Pending - Remind Me Later", "Schedule For ()"],
        ["Name", "Pet", "vetName"],
    ),
    ("vet_followup", None, STAGE_OVERDUE): _template(
        "vet_followup",
        None,
        STAGE_OVERDUE,
        "Hi [Name] 🐾 It seems [Pet]'s follow-up with [vetName] hasn't been logged yet. Could you update it when possible? This helps us track the next step in the care plan without delays.",
        ["Ordered Already", "Order Now", "Pending - Remind Me Later"],
        ["Name", "Pet", "vetName"],
    ),
}


def get_reminder_template(category: str, sub_type: str | None, stage: str) -> ReminderTemplate | None:
    """Return a specific reminder template for (category, sub_type, stage)."""
    template = REMINDER_TEMPLATES.get((category, sub_type, stage))
    if template:
        return template
    return REMINDER_TEMPLATES.get((category, None, stage))


def substitute_variables(template: str, variable_dict: dict[str, str]) -> str:
    """Replace [Variable] placeholders using a value dictionary."""
    rendered = template
    for key, value in variable_dict.items():
        rendered = rendered.replace(f"[{key}]", str(value))
    return rendered


def get_send_time(category: str, stage: str) -> time:
    """Resolve send time for category-stage combinations."""
    if category == "hygiene" and stage == STAGE_DUE:
        return HYGIENE_DUE_SEND_TIME
    return STANDARD_STAGE_SEND_TIMES.get(stage, STANDARD_STAGE_SEND_TIMES[STAGE_DUE])
