"""
PetCircle Dashboard Rebuild — Health Trends Service

Assembles Health Trends V2 payload used by the trends view:
    - ask_vet: per-condition cards with cached AI questions
    - signals: blood panel, weight trend, metabolic tile block
    - cadence: vaccines, flea/tick, deworming timelines
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models.condition import Condition
from app.models.diagnostic_test_result import DiagnosticTestResult
from app.models.pet import Pet
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.models.weight_history import WeightHistory
from app.services.ai_insights_service import get_or_generate_insight

_ASK_VET_CONDITION_TYPES = {"chronic", "episodic"}
_METABOLIC_MARKERS = ("alt", "creatinine", "glucose", "bilirubin")
_BLOOD_GROUP_ORDER: list[tuple[str, tuple[str, ...]]] = [
    ("cbc", ("hemoglobin", "haemoglobin", "wbc", "rbc", "platelet", "pcv", "hct", "mcv", "mch")),
    ("liver", ("alt", "ast", "alp", "bilirubin", "albumin", "protein")),
    ("kidney", ("creatinine", "urea", "bun", "kft", "blood urea")),
    ("electrolytes", ("sodium", "potassium", "chloride", "calcium", "phosphorus")),
]
_VACCINE_KEYWORDS = (
    "vaccine",
    "vaccin",
    "rabies",
    "dhpp",
    "dhppi",
    "kennel cough",
    "bordetella",
    "nobivac",
    "coronavirus",
    "ccov",
    "fvrcp",
    "booster",
)
_DEWORMING_KEYWORDS = ("deworm", "worm")
_FLEA_TICK_KEYWORDS = ("flea", "tick", "parasite")


def _to_float(value: Any) -> float | None:
    """Convert Decimal-like numeric values to float when possible."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_value(result: DiagnosticTestResult) -> str:
    """Format diagnostic value for table rendering."""
    numeric = _to_float(result.value_numeric)
    if numeric is not None:
        value = f"{numeric:g}"
    elif result.value_text:
        value = result.value_text
    else:
        value = "-"
    return f"{value} {result.unit}".strip() if result.unit else value


def _status_label(status_flag: str | None) -> str:
    """Map persisted status flag to binary label required by trends table."""
    status = (status_flag or "").strip().lower()
    if status == "normal":
        return "Normal"
    if status == "low":
        return "Low"
    if status in {"high", "abnormal"}:
        return "High"
    # Missing/unknown status should not be treated as out-of-range.
    return "Normal"


def _blood_group_index(marker_name: str) -> int:
    """Return display group index to keep biologically related markers together."""
    marker_lower = marker_name.lower()
    for idx, (_, keywords) in enumerate(_BLOOD_GROUP_ORDER):
        if any(keyword in marker_lower for keyword in keywords):
            return idx
    return len(_BLOOD_GROUP_ORDER)


def _build_blood_panel(results: list[DiagnosticTestResult]) -> dict[str, Any] | None:
    """Build blood panel card from latest-date blood markers."""
    if not results:
        return None

    ordered = sorted(results, key=lambda r: (_blood_group_index(r.parameter_name or ""), (r.parameter_name or "").lower()))
    rows = [
        {
            "marker": row.parameter_name,
            "range": row.reference_range or "-",
            "value": _format_value(row),
            "status": _status_label(row.status_flag),
        }
        for row in ordered
    ]

    outside = sum(1 for row in rows if row["status"] != "Normal")
    headline = "All listed markers are within range." if outside == 0 else f"{outside} marker(s) are outside range. Discuss with your vet."

    panel_date = max((r.observed_at for r in results if r.observed_at), default=None)
    return {
        "label": "🩸 Blood Panel",
        "date": panel_date.isoformat() if panel_date else None,
        "headline": headline,
        "rows": rows,
    }


def _build_weight_signal(weights_desc: list[WeightHistory]) -> dict[str, Any] | None:
    """Build weight trend card from latest 5 measurements."""
    if not weights_desc:
        return None

    latest_five_desc = weights_desc[:5]
    points = [
        {"date": row.recorded_at.isoformat(), "value": float(row.weight)}
        for row in sorted(latest_five_desc, key=lambda r: r.recorded_at)
    ]
    if not points:
        return None

    start = points[0]
    end = points[-1]
    delta = end["value"] - start["value"]
    days = max((date.fromisoformat(end["date"]) - date.fromisoformat(start["date"])).days, 1)
    months = max(round(days / 30), 1)

    if delta > 0.2:
        direction = "up"
        recommendation = "Weight has trended up. Ask your vet for a measured meal and walk plan over the next 8-12 weeks."
    elif delta < -0.2:
        direction = "down"
        recommendation = "Weight has trended down. Ask your vet if intake or deworming cadence should be adjusted this month."
    else:
        direction = "stable"
        recommendation = "Weight is stable. Continue the same routine and re-check weight at the next preventive visit."

    headline = f"{delta:+.1f} kg over {months} month(s). BCS trending {direction}/9."
    return {
        "points": points,
        "headline": headline,
        "recommendation": recommendation,
    }


def _build_metabolic(results: list[DiagnosticTestResult]) -> dict[str, Any] | None:
    """Build positive-only metabolic signal card from organ markers."""
    if not results:
        return None

    marker_rows: dict[str, DiagnosticTestResult] = {}
    ordered = sorted(
        results,
        key=lambda row: (
            row.observed_at or date.min,
            (row.parameter_name or "").lower(),
        ),
        reverse=True,
    )
    for row in ordered:
        marker_lower = (row.parameter_name or "").lower()
        for marker in _METABOLIC_MARKERS:
            if marker in marker_lower and marker not in marker_rows:
                marker_rows[marker] = row

    if len(marker_rows) < len(_METABOLIC_MARKERS):
        return None

    if any(_status_label(row.status_flag) != "Normal" for row in marker_rows.values()):
        return None

    stats = []
    for marker in _METABOLIC_MARKERS:
        row = marker_rows[marker]
        stats.append(
            {
                "value": _format_value(row),
                "label": row.parameter_name,
            }
        )
    return {
        "headline": "Metabolic and organ markers are within reference range.",
        "sub": "Keep the current routine and monitor during regular checkups.",
        "stats": stats,
    }


def _classify_preventive_item(item_name: str) -> str | None:
    """Map preventive item names to cadence buckets."""
    name = (item_name or "").lower()
    if any(keyword in name for keyword in _VACCINE_KEYWORDS):
        return "vaccine"
    if any(keyword in name for keyword in _FLEA_TICK_KEYWORDS):
        return "flea_tick"
    if any(keyword in name for keyword in _DEWORMING_KEYWORDS):
        return "deworming"
    return None


def _gap_in_weeks(previous: date, current: date) -> int:
    """Calculate integer week gap between two dates."""
    return max((current - previous).days // 7, 0)


def _build_vaccine_cadence(rows: list[tuple[PreventiveRecord, PreventiveMaster]], today: date) -> dict[str, Any] | None:
    """Build vaccine timeline card."""
    vaccine_rows = [row for row in rows if _classify_preventive_item(row[1].item_name) == "vaccine"]
    if not vaccine_rows:
        return None

    vaccine_rows = sorted(vaccine_rows, key=lambda item: (item[0].last_done_date or item[0].next_due_date or today))
    rounds = []
    done_dates = [record.last_done_date for record, _ in vaccine_rows if record.last_done_date]
    for idx, (record, master) in enumerate(vaccine_rows, start=1):
        node_date = record.last_done_date or record.next_due_date
        rounds.append(
            {
                "id": f"R{idx}",
                "label": f"R{idx}",
                "vaccines": master.item_name,
                "done": bool(record.last_done_date),
                "date": node_date.isoformat() if node_date else None,
            }
        )

    gaps = []
    for prev, cur in zip(done_dates, done_dates[1:], strict=False):
        if prev and cur:
            gaps.append(f"{_gap_in_weeks(prev, cur)}w")

    upcoming_dates = sorted(
        record.next_due_date for record, _ in vaccine_rows if record.next_due_date and record.next_due_date >= today
    )
    footer_text = f"✓ Next due {upcoming_dates[0].isoformat()}" if upcoming_dates else "No upcoming vaccine due date available"

    return {
        "headline": "Vaccination cadence",
        "rounds": rounds,
        "gaps": gaps,
        "footer": {"text": footer_text, "color": "green", "bg": "#E8FFF1"},
    }


def _build_flea_tick_cadence(rows: list[tuple[PreventiveRecord, PreventiveMaster]]) -> dict[str, Any] | None:
    """Build flea/tick dot-plot card with gap severity coloring."""
    flea_rows = [row for row in rows if _classify_preventive_item(row[1].item_name) == "flea_tick"]
    if not flea_rows:
        return None

    flea_rows = sorted(flea_rows, key=lambda item: (item[0].last_done_date or date.min))
    doses = []
    previous_done_date: date | None = None
    for idx, (record, master) in enumerate(flea_rows, start=1):
        gap_text = None
        status = "green"
        if record.last_done_date and previous_done_date:
            gap_weeks = _gap_in_weeks(previous_done_date, record.last_done_date)
            gap_text = f"{gap_weeks}w"
            if gap_weeks <= 6:
                status = "green"
            elif gap_weeks <= 12:
                status = "amber"
            else:
                status = "red"

        doses.append(
            {
                "num": idx,
                "label": master.item_name,
                "gap": gap_text,
                "status": status,
                "gap_alert": status == "red",
                "date": record.last_done_date.isoformat() if record.last_done_date else None,
            }
        )
        if record.last_done_date:
            previous_done_date = record.last_done_date

    return {
        "headline": "Tick & Flea coverage cadence",
        "doses": doses,
        "footer": {"text": "Review coverage gaps with your vet.", "color": "amber", "bg": "#FFF6E6"},
    }


def _build_deworming_cadence(rows: list[tuple[PreventiveRecord, PreventiveMaster]], today: date) -> dict[str, Any] | None:
    """Build deworming timeline card."""
    deworm_rows = [row for row in rows if _classify_preventive_item(row[1].item_name) == "deworming"]
    if not deworm_rows:
        return None

    deworm_rows = sorted(deworm_rows, key=lambda item: (item[0].last_done_date or item[0].next_due_date or today))
    nodes = []
    for record, master in deworm_rows:
        if record.last_done_date:
            state = "done"
            node_date = record.last_done_date
        elif record.next_due_date and record.next_due_date < today:
            state = "missed"
            node_date = record.next_due_date
        else:
            state = "now"
            node_date = record.next_due_date

        nodes.append(
            {
                "label": master.item_name,
                "state": state,
                "date": node_date.isoformat() if node_date else None,
            }
        )

    return {
        "headline": "Deworming cadence",
        "nodes": nodes,
    }


def _build_condition_timeline(condition: Condition) -> list[dict[str, str | None]]:
    """Build condition timeline nodes used in ask-vet cards."""
    timeline: list[dict[str, str | None]] = []
    if condition.diagnosed_at:
        timeline.append({"label": "Diagnosed", "date": condition.diagnosed_at.isoformat(), "icon": "🩺"})

    for med in sorted(condition.medications, key=lambda row: row.started_at or date.min):
        if med.started_at:
            timeline.append({"label": f"{med.name} started", "date": med.started_at.isoformat(), "icon": "💊"})

    for monitor in sorted(condition.monitoring, key=lambda row: row.last_done_date or row.next_due_date or date.min):
        if monitor.last_done_date:
            timeline.append({"label": f"{monitor.name} done", "date": monitor.last_done_date.isoformat(), "icon": "✅"})
        elif monitor.next_due_date:
            timeline.append({"label": f"{monitor.name} due", "date": monitor.next_due_date.isoformat(), "icon": "📅"})

    timeline = sorted(timeline, key=lambda item: item.get("date") or "", reverse=True)
    return timeline[:5]


def _build_condition_chart_data(
    condition: Condition,
    diagnostics_desc: list[DiagnosticTestResult],
) -> dict[str, Any] | None:
    """Build lightweight condition chart points from diagnostic history."""
    if not diagnostics_desc:
        return None

    condition_words = [word.lower() for word in (condition.name or "").split() if len(word) > 2]
    filtered = [
        row for row in diagnostics_desc
        if row.observed_at and _to_float(row.value_numeric) is not None and (
            any(word in (row.parameter_name or "").lower() for word in condition_words)
            or not condition_words
        )
    ]
    if not filtered:
        filtered = [row for row in diagnostics_desc if row.observed_at and _to_float(row.value_numeric) is not None]
    if not filtered:
        return None

    points = [
        {
            "date": row.observed_at.isoformat(),
            "value": float(row.value_numeric),
            "marker": row.parameter_name,
            "status": _status_label(row.status_flag),
        }
        for row in sorted(filtered[:6], key=lambda r: r.observed_at)
    ]
    return {"points": points}


def _condition_trend(condition: Condition) -> str:
    """Summarize current condition trend from monitoring and medication state."""
    overdue = any(
        mon.next_due_date and mon.next_due_date < date.today() and not mon.last_done_date
        for mon in condition.monitoring
    )
    active_meds = sum(1 for med in condition.medications if (med.status or "active") == "active")
    if overdue:
        return "Monitoring overdue"
    if active_meds > 0:
        return "On active management"
    return "Stable monitoring"


def _condition_headline(condition: Condition) -> str:
    """Generate condition headline for ask-vet card."""
    if condition.diagnosed_at:
        return f"{condition.condition_type.capitalize()} status · Since {condition.diagnosed_at.strftime('%b %Y')}"
    return f"{condition.condition_type.capitalize()} status"


def _fallback_questions(condition: Condition) -> list[str]:
    """Fallback ask-vet questions when AI response is unavailable."""
    base = [
        f"What should we monitor next for {condition.name}?",
        f"Which signs mean we should review {condition.name} sooner?",
    ]
    return base[:2]


async def _get_condition_questions(db: Session, pet: Pet, condition: Condition) -> list[str]:
    """Load/generate cached ask-vet questions for one condition."""
    condition_payload = {
        "name": condition.name,
        "condition_type": condition.condition_type,
        "medications": [
            {
                "name": med.name,
                "dose": med.dose,
                "frequency": med.frequency,
            }
            for med in condition.medications
        ],
        "monitoring": [
            {
                "name": mon.name,
                "next_due_date": mon.next_due_date.isoformat() if mon.next_due_date else None,
                "last_done_date": mon.last_done_date.isoformat() if mon.last_done_date else None,
            }
            for mon in condition.monitoring
        ],
    }

    insight_type = f"vet_questions:{condition.id}"
    questions_data = await get_or_generate_insight(
        db=db,
        pet_id=pet.id,
        insight_type=insight_type,
        pet={"name": pet.name, "species": pet.species, "breed": pet.breed},
        conditions=[condition_payload],
        health_score={"score": None},
        force=False,
    )

    if not isinstance(questions_data, list):
        return _fallback_questions(condition)

    questions = [
        str(item.get("q", "")).strip()
        for item in questions_data
        if isinstance(item, dict) and str(item.get("q", "")).strip()
    ]
    if not questions:
        return _fallback_questions(condition)
    return questions[:3]


def _fetch_active_conditions(db: Session, pet_id: Any) -> list[Condition]:
    """Fetch active chronic/episodic conditions with related medication/monitoring."""
    return (
        db.query(Condition)
        .options(selectinload(Condition.medications), selectinload(Condition.monitoring))
        .filter(
            Condition.pet_id == pet_id,
            Condition.is_active == True,
            Condition.condition_type.in_(_ASK_VET_CONDITION_TYPES),
        )
        .order_by(Condition.created_at.desc())
        .all()
    )


def _fetch_latest_blood_results(db: Session, pet_id: Any) -> list[DiagnosticTestResult]:
    """Fetch all blood markers for the most recent observed date."""
    latest = (
        db.query(DiagnosticTestResult)
        .filter(
            DiagnosticTestResult.pet_id == pet_id,
            DiagnosticTestResult.test_type == "blood",
            DiagnosticTestResult.observed_at != None,
        )
        .order_by(DiagnosticTestResult.observed_at.desc())
        .first()
    )
    if not latest or not latest.observed_at:
        return []

    return (
        db.query(DiagnosticTestResult)
        .filter(
            DiagnosticTestResult.pet_id == pet_id,
            DiagnosticTestResult.test_type == "blood",
            DiagnosticTestResult.observed_at == latest.observed_at,
        )
        .all()
    )


def _fetch_weight_rows_desc(db: Session, pet_id: Any) -> list[WeightHistory]:
    """Fetch latest weight history entries sorted descending by date."""
    return (
        db.query(WeightHistory)
        .filter(WeightHistory.pet_id == pet_id)
        .order_by(WeightHistory.recorded_at.desc())
        .all()
    )


def _fetch_preventive_rows(db: Session, pet_id: Any) -> list[tuple[PreventiveRecord, PreventiveMaster]]:
    """Fetch preventive records joined to preventive master for cadence construction."""
    return (
        db.query(PreventiveRecord, PreventiveMaster)
        .join(PreventiveMaster, PreventiveRecord.preventive_master_id == PreventiveMaster.id)
        .filter(PreventiveRecord.pet_id == pet_id)
        .all()
    )


def _fetch_diagnostic_rows_desc(db: Session, pet_id: Any) -> list[DiagnosticTestResult]:
    """Fetch latest diagnostic points used in ask-vet charts."""
    return (
        db.query(DiagnosticTestResult)
        .filter(DiagnosticTestResult.pet_id == pet_id, DiagnosticTestResult.observed_at != None)
        .order_by(DiagnosticTestResult.observed_at.desc())
        .all()
    )


async def get_health_trends(db: Session, pet: Pet) -> dict[str, Any]:
    """
    Build Health Trends V2 payload from existing condition, diagnostic, and preventive data.

    Returns section-level nulls when no source data exists.
    """
    conditions = _fetch_active_conditions(db, pet.id)
    latest_blood = _fetch_latest_blood_results(db, pet.id)
    weight_rows_desc = _fetch_weight_rows_desc(db, pet.id)
    preventive_rows = _fetch_preventive_rows(db, pet.id)
    diagnostics_desc = _fetch_diagnostic_rows_desc(db, pet.id)

    ask_vet_conditions = []
    for condition in conditions:
        questions = await _get_condition_questions(db, pet, condition)
        ask_vet_conditions.append(
            {
                "id": str(condition.id),
                "icon": condition.icon or "🩺",
                "label": condition.name,
                "condition_tag": condition.condition_type,
                "headline": _condition_headline(condition),
                "trend": _condition_trend(condition),
                "questions": questions,
                "chart_data": _build_condition_chart_data(condition, diagnostics_desc),
                "timeline_data": _build_condition_timeline(condition),
            }
        )

    ask_vet = {"conditions": ask_vet_conditions} if ask_vet_conditions else None

    blood_panel = _build_blood_panel(latest_blood)
    weight = _build_weight_signal(weight_rows_desc)
    metabolic = _build_metabolic(latest_blood)
    signals = None if not any((blood_panel, weight, metabolic)) else {
        "blood_panel": blood_panel,
        "weight": weight,
        "metabolic": metabolic,
    }

    today = date.today()
    vaccines = _build_vaccine_cadence(preventive_rows, today)
    flea_tick = _build_flea_tick_cadence(preventive_rows)
    deworming = _build_deworming_cadence(preventive_rows, today)
    cadence = None if not any((vaccines, flea_tick, deworming)) else {
        "vaccines": vaccines,
        "flea_tick": flea_tick,
        "deworming": deworming,
    }

    return {
        "ask_vet": ask_vet,
        "signals": signals,
        "cadence": cadence,
    }
