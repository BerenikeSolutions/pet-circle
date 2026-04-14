"""
PetCircle Dashboard Rebuild — Health Trends Service

Assembles Health Trends V2 payload used by the trends view:
    - ask_vet: per-condition cards with cached AI questions
    - signals: blood panel, weight trend, metabolic tile block
    - cadence: vaccines, flea/tick, deworming timelines
"""

from __future__ import annotations

import asyncio
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
    """Build blood panel card from latest-date blood markers.

    Sorts abnormal rows first, then normal. Headline names the specific outliers.
    """
    if not results:
        return None

    def _row_sort_key(r: DiagnosticTestResult) -> tuple[int, int, str]:
        # abnormal rows first (0), then by biological group, then alpha
        abnormal = 0 if (r.status_flag or "").lower() in {"low", "high", "abnormal"} else 1
        return (abnormal, _blood_group_index(r.parameter_name or ""), (r.parameter_name or "").lower())

    ordered = sorted(results, key=_row_sort_key)
    rows = [
        {
            "marker": row.parameter_name,
            "range": row.reference_range or "-",
            "value": _format_value(row),
            "status": _status_label(row.status_flag),
        }
        for row in ordered
    ]

    abnormal_names = [row["marker"] for row in rows if row["status"] != "Normal"]
    if not abnormal_names:
        headline = "All listed markers are within range."
    elif len(abnormal_names) == 1:
        headline = f"All markers normal except {abnormal_names[0]}."
    elif len(abnormal_names) <= 3:
        headline = f"Markers outside range: {', '.join(abnormal_names)}."
    else:
        headline = f"{len(abnormal_names)} markers outside range. Review with your vet."

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
    sorted_rows = sorted(latest_five_desc, key=lambda r: r.recorded_at)
    if not sorted_rows:
        return None

    start_row = sorted_rows[0]
    end_row = sorted_rows[-1]
    start_val = float(start_row.weight)
    end_val = float(end_row.weight)
    delta = end_val - start_val
    days = max((end_row.recorded_at - start_row.recorded_at).days, 1)
    months = max(round(days / 30), 1)

    alert = abs(delta) > 0.2
    if delta > 0.2:
        recommendation = "Weight has trended up. Ask your vet for a measured meal and walk plan over the next 8-12 weeks."
    elif delta < -0.2:
        recommendation = "Weight has trended down. Ask your vet if intake or deworming cadence should be adjusted this month."
    else:
        recommendation = "Weight is stable. Continue the same routine and re-check weight at the next preventive visit."

    # BCS from latest weight entry if available
    bcs = end_row.bcs
    bcs_str = f"{bcs}/9" if bcs else None
    headline = f"{delta:+.1f} kg over {months} month(s)."
    if bcs_str:
        headline += f" BCS trending {bcs_str}."

    points = [
        {"date": row.recorded_at.isoformat(), "value": float(row.weight), "alert": (i == len(sorted_rows) - 1 and alert)}
        for i, row in enumerate(sorted_rows)
    ]
    result: dict[str, Any] = {
        "points": points,
        "headline": headline,
        "recommendation": recommendation,
    }
    if bcs_str:
        result["bcs"] = bcs_str
    return result


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
        stat: dict[str, Any] = {
            "value": _format_value(row),
            "label": row.parameter_name,
        }
        if row.unit:
            stat["unit"] = row.unit
        stats.append(stat)
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
    """Build vaccine timeline card.

    Vaccines on the same date are grouped into a single round so the
    timeline shows one node per date with a vaccine count below it.
    """
    vaccine_rows = [row for row in rows if _classify_preventive_item(row[1].item_name) == "vaccine"]
    if not vaccine_rows:
        return None

    vaccine_rows = sorted(vaccine_rows, key=lambda item: (item[0].last_done_date or item[0].next_due_date or today))

    # Group vaccines by date → one round per unique date.
    from collections import OrderedDict
    date_groups: OrderedDict[date | None, list[tuple[PreventiveRecord, PreventiveMaster]]] = OrderedDict()
    for record, master in vaccine_rows:
        node_date = record.last_done_date or record.next_due_date
        date_groups.setdefault(node_date, []).append((record, master))

    rounds = []
    done_dates: list[date] = []
    total_vaccines = len(vaccine_rows)
    done_vaccine_count = 0

    for idx, (node_date, group) in enumerate(date_groups.items(), start=1):
        names = [m.item_name for _, m in group]
        all_done = all(bool(r.last_done_date) for r, _ in group)
        if all_done and node_date:
            done_dates.append(node_date)
            done_vaccine_count += len(group)
        rounds.append(
            {
                "id": f"R{idx}",
                "label": f"R{idx}",
                "vaccines": " · ".join(names),
                "done": all_done,
                "date": node_date.isoformat() if node_date else None,
            }
        )

    gaps = []
    for prev, cur in zip(done_dates, done_dates[1:], strict=False):
        if prev and cur:
            gaps.append(f"~{_gap_in_weeks(prev, cur) // 4} months")

    all_complete = done_vaccine_count == total_vaccines and total_vaccines > 0
    if all_complete:
        headline = f"All {total_vaccines} vaccines current. Annual cadence maintained."
    elif done_vaccine_count > 0:
        headline = f"{len(done_dates)} of {len(date_groups)} vaccine rounds completed."
    else:
        headline = "No vaccines recorded yet."

    upcoming_dates = sorted(
        record.next_due_date for record, _ in vaccine_rows if record.next_due_date and record.next_due_date >= today
    )
    if upcoming_dates:
        next_date = upcoming_dates[0]
        footer_text = f"✓ Next due {next_date.strftime('%b %Y')}"
    else:
        footer_text = "No upcoming vaccine due date available"

    return {
        "headline": headline,
        "rounds": rounds,
        "gaps": gaps,
        "footer": {"text": footer_text, "color": "green", "bg": "#E8FFF1"},
    }


def _fetch_medicine_info(medicine_name: str | None, db: Session | None) -> dict[str, Any] | None:
    """Look up a medicine in product_medicines and return display metadata.

    Returns a dict with ingredient/dosage/frequency/warning keys, or None when
    either the medicine_name is absent or the catalog lookup fails.
    """
    if not medicine_name or db is None:
        return None
    try:
        from app.models.product_medicines import ProductMedicines

        med = (
            db.query(ProductMedicines)
            .filter(
                ProductMedicines.active == True,
                ProductMedicines.product_name.ilike(f"%{medicine_name}%"),
            )
            .first()
        )
        if med:
            return {
                "product_name": med.product_name,
                "brand_name": med.brand_name,
                "form": med.form,
                "ingredients": med.key_ingredients,
                "dosage": med.dosage,
                "repeat_frequency": med.repeat_frequency,
                "warnings": med.notes,
                "price_display": (
                    f"₹{med.discounted_paise // 100}" if med.discounted_paise else None
                ),
            }
    except Exception:
        pass
    return None


def _build_flea_tick_cadence(
    rows: list[tuple[PreventiveRecord, PreventiveMaster]],
    db: Session | None = None,
) -> dict[str, Any] | None:
    """Build flea/tick dot-plot card with gap severity coloring.

    Mirrors deworming logic: shows overdue/upcoming entries even when no
    last_done_date has been recorded so the card always reflects clinical state.
    """
    flea_rows = [row for row in rows if _classify_preventive_item(row[1].item_name) == "flea_tick"]
    if not flea_rows:
        return None

    today = date.today()
    flea_rows = sorted(
        flea_rows,
        key=lambda item: (item[0].last_done_date or item[0].next_due_date or date.min),
    )

    doses: list[dict[str, Any]] = []
    previous_done_date: date | None = None
    has_undone = False  # True when any row lacks last_done_date

    for idx, (record, master) in enumerate(flea_rows, start=1):
        if not record.last_done_date:
            # No dose recorded — mirror deworming: overdue or upcoming
            has_undone = True
            if record.next_due_date and record.next_due_date < today:
                status = "overdue"
            else:
                status = "upcoming"
            dose_entry: dict[str, Any] = {
                "num": idx,
                "label": master.item_name,
                "gap": None,
                "status": status,
                "gap_alert": False,
                "date": record.next_due_date.isoformat() if record.next_due_date else None,
            }
            med_info = _fetch_medicine_info(record.medicine_name, db)
            if med_info:
                dose_entry["medicine_info"] = med_info
            doses.append(dose_entry)
            continue

        gap_text = None
        status = "green"
        if previous_done_date:
            gap_weeks = _gap_in_weeks(previous_done_date, record.last_done_date)
            gap_text = f"{gap_weeks}w"
            if gap_weeks <= 6:
                status = "green"
            elif gap_weeks <= 12:
                status = "amber"
            else:
                status = "red"

        dose_entry = {
            "num": idx,
            "label": master.item_name,
            "gap": gap_text,
            "status": status,
            "gap_alert": status == "red",
            "date": record.last_done_date.isoformat(),
        }
        med_info = _fetch_medicine_info(record.medicine_name, db)
        if med_info:
            dose_entry["medicine_info"] = med_info
        doses.append(dose_entry)
        previous_done_date = record.last_done_date

    # Append an upcoming next-due node for a meaningful L→R timeline, but only
    # when all existing entries are done (undone entries already cover this role).
    if not has_undone:
        latest_next_due = max(
            (record.next_due_date for record, _ in flea_rows if record.next_due_date),
            default=None,
        )
        if latest_next_due and latest_next_due >= today:
            doses.append({
                "num": len(doses) + 1,
                "label": "Next due",
                "gap": None,
                "status": "upcoming",
                "gap_alert": False,
                "date": latest_next_due.isoformat(),
            })

    # Footer — mirrors deworming severity levels
    real_doses = [d for d in doses if d["status"] not in ("upcoming", "overdue")]
    has_overdue = any(d["status"] == "overdue" for d in doses)
    red_gap_count = sum(1 for d in real_doses if d["status"] == "red")

    if has_overdue:
        footer_text = "⚠ No tick & flea treatment recorded. Administer immediately."
        footer_color = "#b52020"
        footer_bg = "#FFEDED"
    elif not real_doses:
        footer_text = "No doses given yet. Start protection as soon as possible."
        footer_color = "#B45309"
        footer_bg = "#FFF6E6"
    elif len(real_doses) == 1:
        footer_text = "Last dose recorded. Apply monthly for continuous coverage."
        footer_color = "#B45309"
        footer_bg = "#FFF6E6"
    elif red_gap_count > 0:
        footer_text = "⚠ Critical coverage gaps — discuss with your vet. Gaps coincide with risk of vector-borne infection."
        footer_color = "#B45309"
        footer_bg = "#FFF6E6"
    elif any(d.get("status") == "amber" for d in real_doses):
        footer_text = "⚠ Some coverage gaps detected. Aim for monthly or 6-weekly dosing."
        footer_color = "#B45309"
        footer_bg = "#FFF6E6"
    else:
        footer_text = "✓ Tick & flea coverage on track."
        footer_color = "#166534"
        footer_bg = "#E9FBEF"

    return {
        "headline": "Tick & Flea coverage cadence",
        "doses": doses,
        "footer": {"text": footer_text, "color": footer_color, "bg": footer_bg},
    }


def _build_deworming_cadence(
    rows: list[tuple[PreventiveRecord, PreventiveMaster]],
    today: date,
    db: Session | None = None,
    pet: Pet | None = None,
) -> dict[str, Any] | None:
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

        node: dict[str, Any] = {
            "label": master.item_name,
            "state": state,
            "date": node_date.isoformat() if node_date else None,
        }
        med_info = _fetch_medicine_info(record.medicine_name, db)
        if med_info:
            node["medicine_info"] = med_info
        nodes.append(node)

    # Append a single upcoming node for done records whose next_due_date is in
    # the future — gives the chart a meaningful L→R timeline with a "next due" dot.
    # Use life-stage-adjusted recurrence (same formula as care_plan_engine) so that
    # the cadence date always matches what the care plan card displays.
    from datetime import timedelta
    from app.services.care_plan_engine import get_preventive_baseline_days

    done_node_dates = {n["date"] for n in nodes if n["state"] == "done"}
    for record, master in deworm_rows:
        if record.last_done_date:
            if record.custom_recurrence_days:
                recurrence = record.custom_recurrence_days
            elif pet is not None:
                recurrence = get_preventive_baseline_days(pet, "deworming")
            else:
                recurrence = master.recurrence_days
            computed_next = record.last_done_date + timedelta(days=recurrence)
            if computed_next >= today and computed_next.isoformat() not in done_node_dates:
                nodes.append({
                    "label": master.item_name,
                    "state": "upcoming",
                    "date": computed_next.isoformat(),
                })
                break  # one upcoming node is sufficient

    done_count = sum(1 for n in nodes if n["state"] == "done")
    missed_count = sum(1 for n in nodes if n["state"] == "missed")
    has_now = any(n["state"] == "now" for n in nodes)

    # Calculate gap from last done date to today
    last_done_dates = [
        record.last_done_date for record, _ in deworm_rows if record.last_done_date
    ]
    if last_done_dates and (missed_count > 0 or has_now):
        last_done = max(last_done_dates)
        gap_days = (today - last_done).days
        gap_months = gap_days // 30
        if gap_months >= 24:
            gap_label = f"{gap_months // 12}+ years"
        elif gap_months >= 12:
            gap_label = "1+ year"
        else:
            gap_label = f"{gap_months} months"
        headline = f"Only {done_count} dose{'s' if done_count != 1 else ''} in {gap_label}. Significantly overdue."
    elif missed_count > 0 or has_now:
        headline = "Deworming overdue. Administer as soon as possible."
    elif done_count == len(deworm_rows):
        headline = "Deworming on track."
    else:
        headline = "Deworming cadence"

    if missed_count > 0 or has_now:
        footer = {"text": "🚨 Administer immediately", "color": "#b52020", "bg": "var(--tr)"}
    elif missed_count == 0 and not has_now and done_count > 0:
        footer = {"text": "✓ Deworming on track", "color": "#166534", "bg": "#E9FBEF"}
    else:
        footer = {"text": "Review deworming schedule with your vet.", "color": "#B45309", "bg": "#FFF6E6"}

    return {
        "headline": headline,
        "nodes": nodes,
        "footer": footer,
    }


def _build_condition_timeline(condition: Condition) -> list[dict[str, str | None]]:
    """Build condition timeline nodes for the ask-vet card.

    Adds an UNTREATED banner node for chronic conditions with no treatment history.
    Timeline is sorted chronologically ascending (oldest→newest), capped at 5 nodes.
    """
    timeline: list[dict[str, str | None]] = []
    if condition.diagnosed_at:
        timeline.append({
            "label": "Detected",
            "date": condition.diagnosed_at.isoformat(),
            "icon": "🩺",
            "finding": condition.name,
            "special_type": None,
        })

    ever_treated = bool(condition.medications)
    if not ever_treated and condition.condition_type in {"chronic", "episodic"} and condition.diagnosed_at:
        # Insert an UNTREATED node after detection — visually alarming
        timeline.append({
            "label": "UNTREATED",
            "date": condition.diagnosed_at.isoformat(),
            "icon": "⚠️",
            "finding": "No treatment recorded",
            "special_type": "untreated",
        })

    for med in sorted(condition.medications, key=lambda row: row.started_at or date.min):
        if med.started_at:
            finding = f"{med.dose} {med.frequency}".strip() if med.dose or med.frequency else None
            timeline.append({
                "label": f"{med.name}",
                "date": med.started_at.isoformat(),
                "icon": "💊",
                "finding": finding,
                "special_type": None,
            })

    for monitor in sorted(condition.monitoring, key=lambda row: row.last_done_date or row.next_due_date or date.min):
        if monitor.last_done_date:
            finding = monitor.result_summary or None
            timeline.append({
                "label": monitor.name,
                "date": monitor.last_done_date.isoformat(),
                "icon": "✅",
                "finding": finding,
                "special_type": None,
            })
        elif monitor.next_due_date:
            timeline.append({
                "label": f"{monitor.name}?",
                "date": monitor.next_due_date.isoformat(),
                "icon": "❓",
                "finding": "Retest due",
                "special_type": "due",
            })

    # Sort chronologically ascending (oldest first so timeline reads left→right)
    timeline = sorted(timeline, key=lambda item: item.get("date") or "")
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
    """Summarize current condition trend with clinical urgency."""
    today = date.today()
    active_meds = sum(1 for med in condition.medications if (med.status or "active") == "active")
    ever_treated = bool(condition.medications)

    # Find most overdue monitoring item
    most_overdue_mon = None
    longest_overdue_days = 0
    for mon in condition.monitoring:
        if mon.next_due_date and mon.next_due_date < today and not mon.last_done_date:
            days = (today - mon.next_due_date).days
            if days > longest_overdue_days:
                longest_overdue_days = days
                most_overdue_mon = mon

    if most_overdue_mon:
        gap_months = longest_overdue_days // 30
        if gap_months >= 24:
            return f"{most_overdue_mon.name} overdue {gap_months // 12}+ years"
        if gap_months >= 12:
            return f"{most_overdue_mon.name} overdue 1+ year"
        if gap_months >= 1:
            return f"{most_overdue_mon.name} overdue {gap_months}+ months"
        return f"{most_overdue_mon.name} overdue"

    if not ever_treated:
        return "Never treated — discuss treatment protocol with your vet"
    if active_meds > 0:
        return "On active management"
    return "Stable — continue monitoring"


def _condition_headline(condition: Condition) -> str:
    """Generate condition headline reflecting current clinical status, not just history."""
    today = date.today()
    active_meds = sum(1 for med in condition.medications if (med.status or "active") == "active")
    ever_treated = bool(condition.medications)

    # Check for overdue monitoring
    overdue_monitors = [
        mon for mon in condition.monitoring
        if mon.next_due_date and mon.next_due_date < today and not mon.last_done_date
    ]

    # Build a status-centric headline
    detected_str = condition.diagnosed_at.strftime("%b %Y") if condition.diagnosed_at else None

    if not ever_treated and detected_str:
        return f"Detected {detected_str}. Never treated."
    if overdue_monitors:
        mon_name = overdue_monitors[0].name
        return f"{mon_name} overdue. Review with your vet."
    if active_meds > 0 and condition.diagnosed_at:
        return f"Under active management since {detected_str}."
    if condition.diagnosed_at:
        return f"{condition.name} · Since {detected_str}"
    return f"{condition.condition_type.capitalize()} condition under monitoring"


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

    # Fetch vet questions for all conditions in parallel — each call may make a GPT
    # API call, so sequential execution multiplies latency by N conditions.
    all_questions = await asyncio.gather(
        *[_get_condition_questions(db, pet, condition) for condition in conditions]
    )
    ask_vet_conditions = [
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
        for condition, questions in zip(conditions, all_questions)
    ]

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
    flea_tick = _build_flea_tick_cadence(preventive_rows, db=db)
    deworming = _build_deworming_cadence(preventive_rows, today, db=db, pet=pet)
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
