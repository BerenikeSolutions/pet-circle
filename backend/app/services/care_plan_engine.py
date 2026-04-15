"""
PetCircle Dashboard Rebuild — Care Plan Classification Engine

Implements the 7-step classification algorithm that assigns each preventive
test_type to Continue / Attend To / Suggested buckets per pet.

Business rules:
    - Classification runs independently per test_type per pet.
    - Conflict resolution: ATTEND TO > CONTINUE > SUGGESTED.
    - Items due next year are recorded but excluded from the response.
    - Baseline interval is OVERRIDDEN by observed periodic frequency when
      periodic reports qualify, regardless of whether that frequency is
      less than or greater than the baseline.
    - Active prescriptions with no post-Rx report → ATTEND TO bucket.
    - Orderable food/supplements are placed in the Continue bucket.
"""

import logging
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import NotRequired, TypedDict
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.custom_preventive_item import CustomPreventiveItem
from app.models.diet_item import DietItem
from app.models.order import Order
from app.models.pet import Pet
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.services.signal_resolver import (
    SignalLevel,
    SignalResult,
    resolve_food_signal,
    resolve_supplement_signal,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class BreedSize(StrEnum):
    """Five-category breed size classification by weight."""

    MINI_TOY = "mini_toy"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"


class LifeStage(StrEnum):
    """Four life-stage classification for preventive baselines."""

    PUPPY = "puppy"
    JUNIOR = "junior"
    ADULT = "adult"
    SENIOR = "senior"


class Classification(StrEnum):
    """
    Result of the 7-step classification algorithm.

    Bucket mapping (requirement 9.11):
        PERIODIC              → Continue
        PRESCRIPTION_ACTIVE   → Attend To
        NO_HISTORY            → Suggested
        SINGLE                → Suggested
        SPORADIC              → Suggested
        PERIODIC_INSUFFICIENT → Suggested
    """

    NO_HISTORY = "no_history"
    SINGLE = "single"
    SPORADIC = "sporadic"
    PERIODIC = "periodic"
    PERIODIC_INSUFFICIENT = "periodic_insufficient"
    PRESCRIPTION_ACTIVE = "prescription_active"


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Life stage age boundaries per breed size (all values in months).
# junior_start: age at which puppy phase ends.
# adult_start:  age at which junior phase ends.
# senior_start: age at which adult phase ends (senior begins).
BREED_SIZE_BOUNDARIES: dict[str, dict[str, int]] = {
    BreedSize.MINI_TOY: {
        "max_weight_kg": 5,
        "junior_start": 12,
        "adult_start": 24,
        "senior_start": 120,
    },
    BreedSize.SMALL: {
        "max_weight_kg": 10,
        "junior_start": 12,
        "adult_start": 24,
        "senior_start": 108,
    },
    BreedSize.MEDIUM: {
        "max_weight_kg": 25,
        "junior_start": 12,
        "adult_start": 24,
        "senior_start": 96,
    },
    BreedSize.LARGE: {
        "max_weight_kg": 45,
        "junior_start": 12,
        "adult_start": 24,
        "senior_start": 84,
    },
    BreedSize.EXTRA_LARGE: {
        "max_weight_kg": 999,
        "junior_start": 12,
        "adult_start": 24,
        "senior_start": 60,
    },
}

# Baseline test intervals (days) per (life_stage, test_type).
# These are the evidence-based veterinary screening frequencies used when
# no observed periodic pattern exists.  Requirement 9.8.
BASELINE_PROTOCOL: dict[tuple[str, str], int] = {
    # CBC / Blood Chemistry panel
    ("puppy", "cbc_chemistry"): 56,       # every 8 weeks during puppy phase
    ("junior", "cbc_chemistry"): 180,     # every 6 months
    ("adult", "cbc_chemistry"): 730,      # every 2 years
    ("senior", "cbc_chemistry"): 365,     # annually
    # Urinalysis
    ("puppy", "urinalysis"): 56,
    ("junior", "urinalysis"): 180,
    ("adult", "urinalysis"): 730,
    ("senior", "urinalysis"): 365,
    # Fecal examination
    ("puppy", "fecal"): 28,               # every 4 weeks
    ("junior", "fecal"): 90,              # every 3 months
    ("adult", "fecal"): 180,              # every 6 months
    ("senior", "fecal"): 180,
    # Chest X-Ray
    ("puppy", "chest_xray"): 365,
    ("junior", "chest_xray"): 1095,       # every 3 years
    ("adult", "chest_xray"): 1095,
    ("senior", "chest_xray"): 365,
    # Ultrasound / USG
    ("puppy", "usg"): 365,
    ("junior", "usg"): 730,
    ("adult", "usg"): 730,
    ("senior", "usg"): 365,
    # ECG
    ("puppy", "ecg"): 1095,
    ("junior", "ecg"): 1095,
    ("adult", "ecg"): 1095,
    ("senior", "ecg"): 365,
    # Echocardiogram
    ("puppy", "echo"): 1095,
    ("junior", "echo"): 1095,
    ("adult", "echo"): 1095,
    ("senior", "echo"): 365,
    # Dental cleaning / scaling
    ("puppy", "dental"): 365,
    ("junior", "dental"): 365,
    ("adult", "dental"): 365,
    ("senior", "dental"): 180,
    # Deworming
    ("puppy", "deworming"): 28,           # every 4 weeks for puppies
    ("junior", "deworming"): 90,
    ("adult", "deworming"): 180,
    ("senior", "deworming"): 180,
    # Tick & Flea prevention
    ("puppy", "tick_flea"): 30,
    ("junior", "tick_flea"): 30,
    ("adult", "tick_flea"): 30,
    ("senior", "tick_flea"): 30,
    # Vaccines / boosters
    ("puppy", "vaccine"): 21,             # 3-week intervals during puppy schedule
    ("junior", "vaccine"): 365,
    ("adult", "vaccine"): 365,
    ("senior", "vaccine"): 365,
}

# Fallback when no baseline is found for a (life_stage, test_type) pair.
_DEFAULT_BASELINE_DAYS: int = 365

# Tolerance ratio for gap-check in Step 5 (40% of baseline — requirement 9.2.5).
_TOLERANCE_RATIO: float = 0.40

# Reports within this many days of the prior non-Rx report are redundant
# (requirement 9.3).
_MIN_NON_RX_GAP_DAYS: int = 30

# Items whose next_due is further than this many days from today are excluded
# from the care plan response (requirement 9.9).
_NEXT_YEAR_THRESHOLD_DAYS: int = 365

# Orderable diet-item CTA/status rules.
_DUE_SOON_SUPPLY_DAYS: int = 7
_CTA_ORDER_NOW: str = "Order Now"
_CTA_REORDER: str = "Reorder"
_STATUS_ACTIVE: str = "Active"
_STATUS_DUE_SOON: str = "Due Soon"
_QUALIFYING_ORDER_STATUSES: tuple[str, ...] = ("confirmed", "completed", "placed", "delivered")

# Ordered keyword-to-test_type mapping for item_name normalisation.
# Checked in order: longer / more specific patterns first to avoid false matches.
_ITEM_NAME_PATTERNS: list[tuple[str, str]] = [
    ("echocardiogram", "echo"),
    ("electrocardiogram", "ecg"),
    ("blood chem", "cbc_chemistry"),
    ("haematology", "cbc_chemistry"),
    ("hematology", "cbc_chemistry"),
    ("cbc", "cbc_chemistry"),
    ("urinalysis", "urinalysis"),
    ("urine", "urinalysis"),
    ("teeth cleaning", "dental"),
    ("scaling", "dental"),
    ("dental", "dental"),
    ("chest x", "chest_xray"),
    ("x-ray", "chest_xray"),
    ("xray", "chest_xray"),
    ("ultrasound", "usg"),
    ("usg", "usg"),
    ("echo", "echo"),
    ("ecg", "ecg"),
    ("fecal", "fecal"),
    ("faecal", "fecal"),
    ("stool", "fecal"),
    ("deworming", "deworming"),
    ("deworm", "deworming"),
    ("in-1", "vaccine"),
    (" in 1", "vaccine"),
    ("tick", "tick_flea"),
    ("flea", "tick_flea"),
    ("preventive blood test", "cbc_chemistry"),
    ("blood test", "cbc_chemistry"),
    ("leptospirosis", "vaccine"),
    ("bordetella", "vaccine"),
    ("kennel cough", "vaccine"),
    ("coronavirus", "vaccine"),
    ("dhppi", "vaccine"),
    ("rabies", "vaccine"),
    ("nobivac", "vaccine"),
    ("vaccination", "vaccine"),
    ("vaccine", "vaccine"),
    ("supplement", "supplement"),
    ("kibble", "food"),
    ("food", "food"),
    ("diet", "food"),
]

# Section presentation metadata per test_type (icon + display title).
_SECTION_META: dict[str, dict[str, str]] = {
    "vaccine": {"icon": "💉", "title": "Vaccines & Preventive Care"},
    "tick_flea": {"icon": "🐛", "title": "Flea & Tick Protection"},
    "deworming": {"icon": "💊", "title": "Deworming"},
    "dental": {"icon": "🦷", "title": "Dental Care"},
    "cbc_chemistry": {"icon": "🩸", "title": "Blood Tests (CBC)"},
    "urinalysis": {"icon": "🧪", "title": "Urinalysis"},
    "fecal": {"icon": "🔬", "title": "Fecal Examination"},
    "chest_xray": {"icon": "🩻", "title": "Chest X-Ray"},
    "usg": {"icon": "🔊", "title": "Ultrasound (USG)"},
    "ecg": {"icon": "📈", "title": "ECG"},
    "echo": {"icon": "❤️", "title": "Echocardiogram"},
    "food": {"icon": "🍽️", "title": "Diet & Food"},
    "supplement": {"icon": "💊", "title": "Supplements"},
}
_DEFAULT_SECTION_META: dict[str, str] = {"icon": "🏥", "title": "Other Care"}

# Display-name overrides for items whose DB name differs from the desired
# dashboard label.  Keys are *lowercased* DB item_name values.
_DISPLAY_NAME: dict[str, str] = {
    "dhppi": "DHPPi (Nobivac)",
    "rabies vaccine": "Rabies (Nobivac RL)",
    "tick/flea": "Flea & Tick Protection",
}


def get_display_name(item_name: str) -> str:
    """Return the friendly display name for a preventive master item_name.

    Falls back to the original item_name if no override is defined.
    Used by care_plan_engine (dashboard) and reminder_engine (WhatsApp messages)
    to ensure consistent naming across all surfaces.
    """
    return _DISPLAY_NAME.get(item_name.strip().lower(), item_name)

# Map test_types that should be grouped under another section's key.
# Deworming items appear under the "Vaccines & Preventive Care" section.
_SECTION_GROUP: dict[str, str] = {
    "deworming": "vaccine",
    "tick_flea": "vaccine",
}

# Display order for sections within each bucket.
_SECTION_ORDER: list[str] = [
    "vaccine",
    "dental",
    "food",
    "supplement",
    "cbc_chemistry",
    "urinalysis",
    "fecal",
    "chest_xray",
    "usg",
    "ecg",
    "echo",
]


# ─────────────────────────────────────────────────────────────────────────────
# Internal data structures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _Report:
    """A single preventive care event used in the classification algorithm."""

    report_date: date
    is_prescription: bool = False


@dataclass
class _Prescription:
    """An active vet prescription with a pending due date."""

    due_date: date
    medicine_name: str
    condition_name: str | None = None
    dose: str | None = None
    notes: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Public TypedDict return types
# ─────────────────────────────────────────────────────────────────────────────


class CarePlanItemDict(TypedDict):
    """A single care item within a care plan section."""

    name: str
    test_type: str
    freq: str             # Human-readable frequency (e.g. "Monthly")
    next_due: str | None  # ISO date string, or None
    status_tag: str       # "Up to date" | "Due soon" | "Overdue" | "Not started" etc.
    classification: str   # Classification enum value
    reason: str | None    # Contextual reason (for orderable items)
    orderable: bool       # Whether an Order Now button should be shown
    cta_label: NotRequired[str]           # Optional CTA text for orderable diet rows
    signal_level: NotRequired[str | None]  # Signal level (L1-L5) for diet/supplement items
    info_prompt: NotRequired[str | None]   # Info prompt message for L1 items


class CarePlanSectionDict(TypedDict):
    """A grouped section of care items (e.g. "Vaccines & Preventive Care")."""

    icon: str
    title: str
    items: list[CarePlanItemDict]


class CarePlanV2(TypedDict):
    """
    Full care plan bucketed into Continue / Attend To / Suggested.

    continue_items: Tests the pet is already doing on schedule.
    attend_items:   Prescription-driven tests requiring vet attention.
    add_items:      Suggested tests the pet is not yet doing.
    """

    continue_items: list[CarePlanSectionDict]
    attend_items: list[CarePlanSectionDict]
    add_items: list[CarePlanSectionDict]


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────


def _normalize_item_name(item_name: str) -> str:
    """
    Map a preventive master item_name to a canonical test_type key.

    Checks _ITEM_NAME_PATTERNS in order (longest / most specific first) and
    returns the first match.  Returns "other" when no pattern matches.

    Args:
        item_name: The item_name string from preventive_master or
                   a medication name from condition_medications.

    Returns:
        Canonical test_type string (e.g. "cbc_chemistry") or "other".
    """
    lower = item_name.strip().lower()
    for keyword, test_type in _ITEM_NAME_PATTERNS:
        if keyword in lower:
            return test_type
    return "other"


def _get_breed_size(weight_kg: float | None, breed: str | None) -> BreedSize:
    """
    Determine breed size from weight.

    Uses the five-category weight thresholds defined in BREED_SIZE_BOUNDARIES.
    Falls back to keyword heuristics on breed name when weight is unknown,
    and defaults to MEDIUM when neither weight nor breed provide a signal.

    Args:
        weight_kg: Pet weight in kilograms, or None.
        breed:     Breed name string, or None.

    Returns:
        BreedSize enum value.
    """
    if weight_kg is None:
        breed_lower = (breed or "").lower()
        if any(k in breed_lower for k in ("chihuahua", "toy poodle", "teacup", "mini", "pomera")):
            return BreedSize.MINI_TOY
        if any(k in breed_lower for k in ("great dane", "saint bernard", "mastiff", "newfoundland", "leonberger")):
            return BreedSize.EXTRA_LARGE
        if any(k in breed_lower for k in ("rottweiler", "doberman", "labrador", "golden retriever", "german shepherd")):
            return BreedSize.LARGE
        return BreedSize.MEDIUM

    for size in (BreedSize.MINI_TOY, BreedSize.SMALL, BreedSize.MEDIUM, BreedSize.LARGE):
        if weight_kg < BREED_SIZE_BOUNDARIES[size]["max_weight_kg"]:
            return size
    return BreedSize.EXTRA_LARGE


def _get_life_stage(age_months: int, breed_size: BreedSize) -> LifeStage:
    """
    Determine life stage from age and breed size.

    Uses breed-size-aware age boundaries defined in BREED_SIZE_BOUNDARIES.

    Args:
        age_months: Pet's age in whole months.
        breed_size: BreedSize enum value.

    Returns:
        LifeStage enum value.
    """
    boundaries = BREED_SIZE_BOUNDARIES[breed_size]
    if age_months < boundaries["junior_start"]:
        return LifeStage.PUPPY
    if age_months < boundaries["adult_start"]:
        return LifeStage.JUNIOR
    if age_months < boundaries["senior_start"]:
        return LifeStage.ADULT
    return LifeStage.SENIOR


def _get_baseline_protocol(life_stage: LifeStage, test_type: str) -> int:
    """
    Look up the baseline screening interval for a life stage and test type.

    Args:
        life_stage: LifeStage enum value.
        test_type:  Canonical test_type string.

    Returns:
        Interval in days.  Falls back to _DEFAULT_BASELINE_DAYS when
        the (life_stage, test_type) pair is not in BASELINE_PROTOCOL.
    """
    return BASELINE_PROTOCOL.get((life_stage.value, test_type), _DEFAULT_BASELINE_DAYS)


def _filter_redundant_reports(reports: list[_Report]) -> list[_Report]:
    """
    Remove redundant reports from the history before classification.

    Redundancy rules (requirement 9.3):
    1. Same-day duplicates: keep one report per date (prefer Rx reports).
    2. Non-Rx reports within 30 days of the preceding report are redundant
       and excluded from the frequency calculation.

    Args:
        reports: Unsorted list of _Report objects.

    Returns:
        Filtered list sorted by report_date ascending, redundant entries removed.
    """
    if not reports:
        return []

    # Step 1: Deduplicate same-day reports — prefer Rx over non-Rx.
    by_date: dict[date, _Report] = {}
    for r in reports:
        existing = by_date.get(r.report_date)
        if existing is None:
            by_date[r.report_date] = r
        elif r.is_prescription and not existing.is_prescription:
            # Prescription report takes precedence for the same date.
            by_date[r.report_date] = r

    deduped = sorted(by_date.values(), key=lambda r: r.report_date)

    # Step 2: Remove non-Rx reports within 30 days of the previous report.
    filtered: list[_Report] = []
    for r in deduped:
        if not filtered:
            filtered.append(r)
            continue
        gap_days = (r.report_date - filtered[-1].report_date).days
        if r.is_prescription or gap_days >= _MIN_NON_RX_GAP_DAYS:
            filtered.append(r)
        # else: redundant non-Rx within 30 days — skip.

    return filtered


def _classify_test(
    reports: list[_Report],
    baseline_days: int,
    prescription: _Prescription | None = None,
) -> Classification:
    """
    Run the 7-step classification algorithm.

    Steps (requirement 9.2):
        1. Count valid reports → n.
        2. n=0 → NO_HISTORY; n=1 → SINGLE; n≥2 → continue.
        3. Sort by date; calculate consecutive gaps.
        4. Any gap > 2× baseline → SPORADIC.
        5. Tolerance = 0.40 × baseline.  All gaps within tolerance → candidate.
        6. median_gap ≤ baseline + tolerance → PERIODIC.  Else → SPORADIC.
        7. PERIODIC AND median_gap > baseline → PERIODIC_INSUFFICIENT.

    Prescription override (requirement 9.4):
        If an active prescription exists with no post-Rx report, classification
        is forced to PRESCRIPTION_ACTIVE regardless of report history.

    Args:
        reports:      Filtered, deduplicated list of _Report objects.
        baseline_days: Expected interval in days for this life stage + test type.
        prescription: Active _Prescription, if any.

    Returns:
        Classification enum value.
    """
    # Prescription override: active prescription with no post-Rx report.
    if prescription is not None:
        has_post_rx = any(r.report_date >= prescription.due_date for r in reports)
        if not has_post_rx:
            return Classification.PRESCRIPTION_ACTIVE

    # Steps 1 & 2: Count.
    n = len(reports)
    if n == 0:
        return Classification.NO_HISTORY
    if n == 1:
        return Classification.SINGLE

    # Step 3: Consecutive gaps.
    sorted_reports = sorted(reports, key=lambda r: r.report_date)
    gaps: list[int] = [
        (sorted_reports[i + 1].report_date - sorted_reports[i].report_date).days
        for i in range(len(sorted_reports) - 1)
    ]

    # Step 4: Any gap > 2× baseline → SPORADIC.
    if any(g > 2 * baseline_days for g in gaps):
        return Classification.SPORADIC

    # Step 5 & 6: Tolerance band and median check.
    tolerance = _TOLERANCE_RATIO * baseline_days
    median_gap = statistics.median(gaps)

    if median_gap > baseline_days + tolerance:
        return Classification.SPORADIC

    # Candidate PERIODIC: median_gap ≤ baseline + tolerance.
    # Step 7: If median_gap > baseline (but within tolerance) → PERIODIC_INSUFFICIENT.
    if median_gap > baseline_days:
        return Classification.PERIODIC_INSUFFICIENT

    return Classification.PERIODIC


def _compute_next_due(
    classification: Classification,
    reports: list[_Report],
    baseline_days: int,
    prescription: _Prescription | None = None,
) -> date | None:
    """
    Compute the next due date for a care item.

    Rules (requirement 9.10):
    - PRESCRIPTION_ACTIVE → use prescription.due_date.
    - PERIODIC → derive frequency from median gap (overrides baseline).
    - NO_HISTORY → None (no last date exists to compute from).
    - All others → last_report_date + baseline_days.
    - Returns None if there are no reports.

    Args:
        classification: Result of _classify_test.
        reports:        Filtered, deduplicated reports (any order).
        baseline_days:  Baseline interval for this life stage + test type.
        prescription:   Active prescription, if any.

    Returns:
        Next due date, or None when indeterminate.
    """
    if classification == Classification.PRESCRIPTION_ACTIVE and prescription is not None:
        return prescription.due_date

    if classification == Classification.NO_HISTORY:
        return None

    if not reports:
        return None

    sorted_reports = sorted(reports, key=lambda r: r.report_date)
    last_date = sorted_reports[-1].report_date

    if classification == Classification.PERIODIC and len(sorted_reports) >= 2:
        # Requirement 9.10: baseline overridden by observed periodic frequency.
        gaps = [
            (sorted_reports[i + 1].report_date - sorted_reports[i].report_date).days
            for i in range(len(sorted_reports) - 1)
        ]
        derived_frequency = int(statistics.median(gaps))
        return last_date + timedelta(days=derived_frequency)

    return last_date + timedelta(days=baseline_days)


def _days_to_freq_label(days: int) -> str:
    """
    Convert an interval in days to a human-readable frequency label.

    Args:
        days: Interval in days.

    Returns:
        Frequency label string (e.g. "Monthly", "Annual").
    """
    if days <= 7:
        return "Weekly"
    if days <= 14:
        return "Every 2 weeks"
    if days <= 31:
        return "Monthly"
    if days <= 45:
        return "Every 6 weeks"
    if days <= 93:
        return "Every 3 months"
    if days <= 186:
        return "Every 6 months"
    if days <= 366:
        return "Annual"
    if days <= 731:
        return "Every 2 years"
    return "Every 3+ years"


def _status_tag(next_due: date | None, classification: Classification) -> str:
    """
    Derive a UI status tag string from next_due and classification.

    Rules:
        URGENT  — overdue (today > next_due), OR no history, OR no next_due.
        DUE SOON — next_due within 7 days.
        ON TRACK — everything else.

    Args:
        next_due:       Computed next due date, or None.
        classification: Classification enum value.

    Returns:
        Human-readable status string for the care plan card UI.
    """
    if classification == Classification.NO_HISTORY:
        return "Not started"
    if next_due is None:
        return "Not started"
    today = date.today()
    if next_due < today:
        return "Overdue"
    if (next_due - today).days <= 7:
        return "Due soon"
    return "On track"


def _get_pet_age_months(pet: Pet) -> int:
    """
    Compute the pet's age in whole months.

    Falls back to 36 months (typical adult) when dob is not set.

    Args:
        pet: Pet model instance.

    Returns:
        Age in months (minimum 0).
    """
    if pet.dob is None:
        return 36  # default: adult
    delta = date.today() - pet.dob
    return max(0, int(delta.days / 30.44))


def _get_weight_kg(pet: Pet) -> float | None:
    """
    Extract pet weight as a Python float.

    Args:
        pet: Pet model instance.

    Returns:
        Weight in kg as float, or None when not set.
    """
    if pet.weight is None:
        return None
    return float(pet.weight)


def _to_sections(
    items_dict: dict[str, CarePlanItemDict],
) -> list[CarePlanSectionDict]:
    """
    Group a flat dict of care items into ordered CarePlanSection dicts.

    Items are grouped by their test_type.  Sections appear in _SECTION_ORDER,
    with any remaining sections appended at the end.

    Args:
        items_dict: Mapping of item_key → CarePlanItemDict.

    Returns:
        List of CarePlanSectionDict, ordered per _SECTION_ORDER.
    """
    sections_map: dict[str, CarePlanSectionDict] = {}

    for _key, item in items_dict.items():
        sec_key = _SECTION_GROUP.get(item["test_type"], item["test_type"])
        meta = _SECTION_META.get(sec_key, _DEFAULT_SECTION_META)
        if sec_key not in sections_map:
            sections_map[sec_key] = {
                "icon": meta["icon"],
                "title": meta["title"],
                "items": [],
            }
        sections_map[sec_key]["items"].append(item)

    # Return sections in defined display order.
    result: list[CarePlanSectionDict] = []
    for key in _SECTION_ORDER:
        if key in sections_map:
            result.append(sections_map[key])
    # Append any test_types not covered by the fixed order.
    for key, section in sections_map.items():
        if key not in _SECTION_ORDER:
            result.append(section)

    return result


def _check_reorder_status(
    db: Session,
    pet_id: UUID,
    diet_label: str,
) -> tuple[str | None, str]:
    """
    Check for a prior order matching *diet_label* and return a reorder
    override tuple ``(cta_label_override, status_tag)``.

    Returns ``(None, "Active")`` when no prior qualifying order is found
    (i.e. no override). When a qualifying order exists, returns
    ``("Reorder", status_tag)`` — with *status_tag* set to "Due Soon" if
    the pack supply is running low.
    """
    try:
        label = (diet_label or "").strip()
        if not label:
            return None, _STATUS_ACTIVE

        order_query = db.query(Order).filter(Order.pet_id == pet_id)

        if hasattr(Order, "product_name"):
            order_query = order_query.filter(Order.product_name.ilike(f"%{label}%"))
        else:
            order_query = order_query.filter(Order.items_description.ilike(f"%{label}%"))

        order_query = order_query.filter(Order.status.in_(_QUALIFYING_ORDER_STATUSES))
        latest_order = order_query.order_by(Order.created_at.desc()).first()
        if latest_order is None:
            return None, _STATUS_ACTIVE

        status_tag = _STATUS_ACTIVE
        pack_days = getattr(latest_order, "pack_days", None)
        created_at = getattr(latest_order, "created_at", None)
        if pack_days is not None and created_at is not None:
            order_date = created_at.date() if hasattr(created_at, "date") else created_at
            if isinstance(order_date, date):
                remaining_days = int(pack_days) - (date.today() - order_date).days
                if remaining_days <= _DUE_SOON_SUPPLY_DAYS:
                    status_tag = _STATUS_DUE_SOON

        return _CTA_REORDER, status_tag

    except Exception:
        logger.warning(
            "Failed to check reorder status for diet item '%s' of pet %s",
            diet_label,
            pet_id,
            exc_info=True,
        )
        return None, _STATUS_ACTIVE


# Signal-level constants used to decide CTA visibility.
_L2_AND_ABOVE: frozenset[str] = frozenset({
    SignalLevel.L2.value,
    SignalLevel.L2B.value,
    SignalLevel.L2C.value,
    SignalLevel.L3.value,
    SignalLevel.L4.value,
    SignalLevel.L5.value,
})


def _resolve_diet_item_signals(
    db: Session,
    diet_item: DietItem,
    pet: Pet,
    conditions: list[Condition],
) -> dict:
    """
    Resolve signal level, CTA label, orderability, and info prompt for a
    diet item by delegating to the signal resolver.

    Returns a dict with keys: ``signal_level``, ``cta_label``,
    ``orderable``, ``status_tag``, ``info_prompt``.
    """
    try:
        if diet_item.type == "supplement":
            signal: SignalResult = resolve_supplement_signal(db, diet_item, pet, conditions)
        else:
            signal = resolve_food_signal(db, diet_item, pet, conditions)
    except Exception:
        logger.warning(
            "Signal resolver failed for diet item '%s' (pet %s); defaulting to L1",
            diet_item.label,
            pet.id,
            exc_info=True,
        )
        return {
            "signal_level": SignalLevel.L1.value,
            "cta_label": None,
            "orderable": False,
            "status_tag": _STATUS_ACTIVE,
            "info_prompt": None,
        }

    level_value = signal.level.value

    if level_value in _L2_AND_ABOVE:
        # Check for reorder override (prior order → "Reorder" / "Due Soon").
        reorder_cta, status_tag = _check_reorder_status(
            db, pet.id, diet_item.label
        )
        return {
            "signal_level": level_value,
            "cta_label": reorder_cta or signal.cta_label or _CTA_ORDER_NOW,
            "orderable": True,
            "status_tag": status_tag,
            "info_prompt": None,
        }

    # L1 — not enough data to recommend a product.
    return {
        "signal_level": level_value,
        "cta_label": None,
        "orderable": False,
        "status_tag": _STATUS_ACTIVE,
        "info_prompt": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def get_preventive_baseline_days(pet: Pet, test_type: str) -> int:
    """Return life-stage-adjusted baseline recurrence days for a preventive test type.

    Mirrors the same logic used inside compute_care_plan so that the care-cadence
    view and the care-plan view always agree on the expected interval.

    Args:
        pet:       Pet model instance.
        test_type: Canonical test_type string (e.g. "deworming", "tick_flea").

    Returns:
        Interval in days.
    """
    age_months = _get_pet_age_months(pet)
    weight_kg = _get_weight_kg(pet)
    breed_size = _get_breed_size(weight_kg, pet.breed)
    life_stage = _get_life_stage(age_months, breed_size)
    return _get_baseline_protocol(life_stage, test_type)


def compute_care_plan(db: Session, pet: Pet) -> CarePlanV2:
    """
    Compute the full care plan for a pet.

    For each preventive test_type tracked in BASELINE_PROTOCOL:
    1. Fetch preventive records and map to _Report objects.
    2. Apply redundancy filters (_filter_redundant_reports).
    3. Check for active prescriptions (condition_medications).
    4. Run 7-step classification algorithm (_classify_test).
    5. Compute next due date (_compute_next_due).
    6. Exclude items whose next_due is more than 1 year from today (req 9.9).
    7. Apply conflict resolution (ATTEND TO > CONTINUE > SUGGESTED).

    Orderable food and supplement items from diet_items are added to the
    Continue bucket (requirement 9.12).

    Errors from DB or processing are logged and an empty plan is returned
    so the dashboard never crashes (failure isolation requirement).

    Args:
        db:  Active SQLAlchemy Session.
        pet: Pet model instance to compute the plan for.

    Returns:
        CarePlanV2 TypedDict with continue_items, attend_items, add_items.
    """
    try:
        age_months = _get_pet_age_months(pet)
        weight_kg = _get_weight_kg(pet)
        breed_size = _get_breed_size(weight_kg, pet.breed)
        life_stage = _get_life_stage(age_months, breed_size)

        # ── Fetch preventive records with their master items ──────────────────
        #
        # NOTE: items are keyed by an "item_key" — NOT just the canonical
        # test_type. For most test_types, item_key == test_type. For vaccines,
        # each distinct master.item_name (e.g. "Rabies Vaccine", "DHPPi",
        # "Kennel Cough (Nobivac KC)", "Canine Coronavirus (CCoV)") gets its
        # own key so the dashboard can list each vaccine as a separate row
        # instead of collapsing them into a single "Vaccines" entry.
        # The `test_type` stored on each item dict stays as "vaccine" so that
        # `_to_sections` still groups them under the "Vaccines & Preventive
        # Care" section.

        def _build_item_key(test_type: str, item_name: str | None) -> str:
            if test_type == "vaccine" and item_name:
                return f"vaccine:{item_name.strip().lower()}"
            return test_type

        records_by_key: dict[str, list[_Report]] = {}
        # Canonical test_type per item_key (needed for baseline lookup).
        test_type_by_key: dict[str, str] = {}
        # Display name per item_key (first-seen per key wins).
        item_names_by_key: dict[str, str] = {}
        # User-set custom recurrence per item_key (latest record wins).
        # When present, overrides baseline_days for next_due and freq_label.
        custom_recurrence_by_key: dict[str, int] = {}
        # Track medicine_name per item_key for dual-use frequency unification.
        medicine_by_key: dict[str, str] = {}

        record_rows = (
            db.query(PreventiveRecord, PreventiveMaster, CustomPreventiveItem)
            .outerjoin(
                PreventiveMaster,
                PreventiveRecord.preventive_master_id == PreventiveMaster.id,
            )
            .outerjoin(
                CustomPreventiveItem,
                PreventiveRecord.custom_preventive_item_id == CustomPreventiveItem.id,
            )
            .filter(
                PreventiveRecord.pet_id == pet.id,
                PreventiveRecord.status != "cancelled",
            )
            .all()
        )

        # Skip one-time puppy-series items (recurrence_days >= 36500) for
        # non-puppy pets.  Adults should only see the annual DHPPi + Rabies.
        _skip_puppy_series = life_stage != LifeStage.PUPPY

        # Tick/Flea prevention is not safe for dogs younger than 8 weeks.
        # Hide it from the care plan so we do not prompt owners to apply
        # products that are contraindicated at this age.
        _pet_age_days = (date.today() - pet.dob).days if pet.dob else None
        _skip_flea_tick = (
            getattr(pet, "species", None) == "dog"
            and _pet_age_days is not None
            and _pet_age_days < 56  # 8 weeks × 7 days
        )

        for record, master, custom_item in record_rows:
            if master and _skip_puppy_series and master.recurrence_days and master.recurrence_days >= 36500:
                continue
            if _skip_flea_tick and master and master.item_name == "Tick/Flea":
                continue

            item_name = (
                (master.item_name if master else None)
                or (custom_item.item_name if custom_item else None)
            )
            if not item_name:
                continue

            test_type = _normalize_item_name(item_name)
            if test_type == "other":
                continue

            is_core_type = test_type in {"vaccine", "deworming", "tick_flea"}
            if record.last_done_date is None and not is_core_type:
                # Keep existing rule: non-core types only appear when there is
                # historical completion evidence or an active prescription.
                continue

            # Non-mandatory vaccines (e.g. Kennel Cough, CCoV, Leptospirosis)
            # should only appear when the user has logged a completion date.
            # Without this guard they show up with a NO_HISTORY classification
            # and a rolling "next_due = today + 365" that looks like a phantom
            # quick-fix recommendation the user never asked for.
            if (
                test_type == "vaccine"
                and record.last_done_date is None
                and not bool(getattr(master, "is_mandatory", False))
            ):
                continue

            item_key = _build_item_key(test_type, item_name)
            if item_key not in records_by_key:
                records_by_key[item_key] = []
                test_type_by_key[item_key] = test_type
                item_names_by_key[item_key] = item_name
            # Track user-set custom recurrence (latest record per key wins).
            if record.custom_recurrence_days:
                custom_recurrence_by_key[item_key] = record.custom_recurrence_days
            # Track medicine name for dual-use frequency unification.
            if record.medicine_name:
                medicine_by_key[item_key] = record.medicine_name.strip().lower()
            # Keep the item key even when no completion date exists so core
            # preventive rows (vaccines/deworming/flea-tick) still appear.
            if record.last_done_date is not None:
                records_by_key[item_key].append(
                    _Report(report_date=record.last_done_date, is_prescription=False)
                )

        # ── Fetch active prescriptions scoped to this pet ────────────────────
        # Join via Condition to ensure we only pick up medications for this pet.
        prescriptions_by_key: dict[str, _Prescription] = {}

        active_meds = (
            db.query(ConditionMedication)
            .join(Condition, ConditionMedication.condition_id == Condition.id)
            .options(joinedload(ConditionMedication.condition))
            .filter(
                Condition.pet_id == pet.id,
                ConditionMedication.status == "active",
                ConditionMedication.refill_due_date.isnot(None),
            )
            .all()
        )

        for med in active_meds:
            test_type = _normalize_item_name(med.name)
            # Food and supplement medications are handled by diet_items; skip.
            if test_type in ("other", "food", "supplement"):
                continue
            item_key = _build_item_key(test_type, med.name)
            test_type_by_key.setdefault(item_key, test_type)
            item_names_by_key.setdefault(item_key, med.name)
            # Last prescription per key wins (more recent takes precedence).
            existing = prescriptions_by_key.get(item_key)
            if existing is None or med.refill_due_date > existing.due_date:
                condition_name = med.condition.name if med.condition else None
                prescriptions_by_key[item_key] = _Prescription(
                    due_date=med.refill_due_date,
                    medicine_name=med.name,
                    condition_name=condition_name,
                    dose=(med.dose or None),
                    notes=(med.notes or None),
                )

        # ── Determine full set of item_keys to classify ──────────────────────
        # Begin with keys that have records or prescriptions.
        all_item_keys: set[str] = set(records_by_key.keys()) | set(prescriptions_by_key.keys())
        # Only vaccines, flea/tick, and deworming are mandatory (always shown
        # even without records).  All other test types (dental, fecal, xray,
        # cbc, urinalysis, usg, ecg, echo) only appear when the pet has
        # uploaded documents proving prior completion or a vet prescription.
        _ALWAYS_SHOW_TYPES: set[str] = {"tick_flea", "deworming"}
        for ls, tt in BASELINE_PROTOCOL:
            if ls != life_stage.value:
                continue
            # Skip non-mandatory types that have no records or prescriptions.
            if tt not in _ALWAYS_SHOW_TYPES:
                continue
            # Vaccines are handled exclusively by the mandatory phantom block
            # below (specific vaccine item_keys like "vaccine:rabies vaccine").
            # The generic "vaccine" key is never added here to avoid a
            # duplicate fallback row alongside the named vaccine rows.
            if tt not in all_item_keys:
                all_item_keys.add(tt)
                test_type_by_key.setdefault(tt, tt)

        # ── Inject mandatory preventive items without records → Quick Fixes ──
        # Mandatory items (is_mandatory=TRUE): Rabies, DHPPi, Feline Core,
        # Deworming, Tick/Flea.  These always appear on the dashboard even when
        # the pet has no records — they land in the Quick Fixes bucket with a
        # "Not started" status (displayed as "Recommended" tag).
        #
        # Optional vaccines (Kennel Cough, Canine Coronavirus — is_mandatory=FALSE)
        # are NOT injected here: they only appear when an actual record exists
        # (i.e., the user said their pet receives those vaccines).
        try:
            _mandatory_masters_raw = (
                db.query(PreventiveMaster)
                .filter(
                    PreventiveMaster.is_mandatory == True,
                    PreventiveMaster.species.in_([pet.species, "both"]),
                )
                .all()
            )
            mandatory_masters = _mandatory_masters_raw if isinstance(_mandatory_masters_raw, list) else []
        except Exception:
            logger.warning("Failed to load mandatory preventive masters; skipping phantom entries")
            mandatory_masters = []
        _mandatory_phantom_types: set[str] = {"vaccine", "deworming", "tick_flea"}
        for master in mandatory_masters:
            if _skip_puppy_series and master.recurrence_days and master.recurrence_days >= 36500:
                continue
            # Do not surface Tick/Flea as a mandatory "Quick Fix" for dogs < 8 weeks.
            if _skip_flea_tick and master.item_name == "Tick/Flea":
                continue
            test_type = _normalize_item_name(master.item_name)
            if test_type not in _mandatory_phantom_types:
                continue
            item_key = _build_item_key(
                test_type,
                master.item_name if test_type == "vaccine" else None,
            )
            if item_key not in all_item_keys:
                all_item_keys.add(item_key)
                records_by_key.setdefault(item_key, [])
                test_type_by_key[item_key] = test_type
                item_names_by_key[item_key] = master.item_name

        today = date.today()
        next_year = today + timedelta(days=_NEXT_YEAR_THRESHOLD_DAYS)

        # ── Dual-use medicine frequency unification ──────────────────────
        # When the same medicine (e.g. Simparica) is used for both deworming
        # and tick_flea, unify the effective frequency to the shortest interval
        # so the dashboard shows the same frequency for both items.
        _DUAL_USE_KEYS = {"deworming", "tick_flea"}
        dual_medicines: dict[str, set[str]] = {}  # medicine → {item_keys}
        for ik, med in medicine_by_key.items():
            tt = test_type_by_key.get(ik)
            if tt in _DUAL_USE_KEYS and med:
                dual_medicines.setdefault(med, set()).add(ik)
        dual_use_override: dict[str, int] = {}
        for med, iks in dual_medicines.items():
            covered_types = {test_type_by_key.get(k) for k in iks}
            if covered_types >= _DUAL_USE_KEYS:
                # Same medicine covers both — use the shortest baseline.
                shortest = min(
                    _get_baseline_protocol(life_stage, test_type_by_key[k])
                    for k in iks
                )
                for k in iks:
                    dual_use_override[k] = shortest

        # ── ProductMedicines.repeat_frequency lookup ─────────────────────
        # The care plan displays the freq_label for each item. When an item
        # is backed by a known medicine (e.g., Bravecto), prefer the human
        # label stored in product_medicines.repeat_frequency over the
        # computed _days_to_freq_label(effective_days), which is based on
        # life-stage baselines and will always read "Monthly" for 30-day
        # baselines regardless of the actual product cadence.
        product_freq_by_medicine: dict[str, str] = {}
        if medicine_by_key:
            try:
                from app.models.product_medicines import ProductMedicines
                _names_lc = {m for m in medicine_by_key.values() if m}
                if _names_lc:
                    rows = (
                        db.query(ProductMedicines.product_name, ProductMedicines.repeat_frequency)
                        .filter(ProductMedicines.repeat_frequency.isnot(None))
                        .all()
                    )
                    for product_name, repeat_freq in rows:
                        if not product_name or not repeat_freq:
                            continue
                        key = product_name.strip().lower()
                        if key in _names_lc and key not in product_freq_by_medicine:
                            product_freq_by_medicine[key] = repeat_freq.strip()
            except Exception:
                # Fallback silently — baseline-derived label remains the default.
                product_freq_by_medicine = {}

        # Buckets keyed by item_key (conflict resolution applied inline).
        attend_items: dict[str, CarePlanItemDict] = {}
        continue_items: dict[str, CarePlanItemDict] = {}
        add_items: dict[str, CarePlanItemDict] = {}

        for item_key in sorted(all_item_keys):
            test_type = test_type_by_key.get(item_key, item_key)
            if test_type in ("food", "supplement", "other"):
                continue  # handled separately below

            reports = records_by_key.get(item_key, [])
            filtered = _filter_redundant_reports(reports)
            baseline_days = _get_baseline_protocol(life_stage, test_type)
            prescription = prescriptions_by_key.get(item_key)

            # Priority: custom recurrence (user-set) > dual-use override > baseline.
            effective_days = (
                custom_recurrence_by_key.get(item_key)
                or dual_use_override.get(item_key)
                or baseline_days
            )

            classification = _classify_test(filtered, baseline_days, prescription)
            next_due = _compute_next_due(classification, filtered, effective_days, prescription)

            # Requirement 9.9: exclude items due more than 1 year from today.
            if next_due is not None and next_due > next_year:
                continue

            raw_name = item_names_by_key.get(item_key, test_type.replace("_", " ").title())
            name = _DISPLAY_NAME.get(raw_name.lower(), raw_name)
            # Prefer product_medicines.repeat_frequency when a matching medicine
            # is linked — avoids defaulting e.g. Bravecto to "Monthly" just
            # because its life-stage baseline is 30 days.
            _med_lc = medicine_by_key.get(item_key)
            freq_label = (
                product_freq_by_medicine.get(_med_lc)
                if _med_lc and _med_lc in product_freq_by_medicine
                else _days_to_freq_label(effective_days)
            )
            status_tag = _status_tag(next_due, classification)

            item: CarePlanItemDict = {
                "name": name,
                "test_type": test_type,
                "freq": freq_label,
                "next_due": next_due.strftime("%d/%m/%y") if next_due else None,
                "status_tag": status_tag,
                "classification": classification.value,
                "reason": None,
                "orderable": False,
            }

            # ── Conflict resolution: ATTEND TO > CONTINUE > QUICK FIXES ─────
            # Core preventive types (vaccines, deworming, tick/flea).
            _CORE_TYPES: set[str] = {"vaccine", "deworming", "tick_flea"}
            is_core = test_type in _CORE_TYPES

            is_overdue = status_tag == "Overdue"
            is_no_history = classification == Classification.NO_HISTORY
            has_history = bool(records_by_key.get(item_key))

            if classification == Classification.PRESCRIPTION_ACTIVE:
                # Attend To — active prescription with no post-Rx report.
                # Build a reason string so the pet parent understands context.
                if prescription is not None:
                    reason_parts = []
                    if prescription.condition_name:
                        reason_parts.append(f"Prescribed for {prescription.condition_name}")
                    if prescription.dose:
                        reason_parts.append(prescription.dose)
                    if prescription.notes:
                        reason_parts.append(prescription.notes)
                    item["reason"] = " · ".join(reason_parts) if reason_parts else None
                attend_items[item_key] = item
                continue_items.pop(item_key, None)
                add_items.pop(item_key, None)

            elif is_overdue and has_history:
                # Overdue but has a last_done_date → Continue bucket (tag: Overdue).
                # Pet is on this routine but missed the next dose — keep in Continue.
                if item_key not in attend_items:
                    continue_items[item_key] = item
                    add_items.pop(item_key, None)

            elif is_no_history:
                # No history → Quick Fixes to Add (tag: Recommended).
                # Mandatory items reach here via phantom entries.
                if item_key not in attend_items:
                    add_items[item_key] = item
                    continue_items.pop(item_key, None)

            elif classification == Classification.PERIODIC or is_core:
                # Continue — on-track / due-soon items with history.
                if item_key not in attend_items:
                    continue_items[item_key] = item
                    add_items.pop(item_key, None)

            else:
                # Suggested — non-core items with insufficient history.
                if item_key not in attend_items and item_key not in continue_items:
                    add_items[item_key] = item

        # ── Make tick_flea / deworming items in Quick Fixes orderable ────────
        # These items land in add_items with orderable=False and reason=None by
        # default. Enabling orderable here (after conflict resolution is settled)
        # causes the dashboard to show an "Order Now" button that opens the
        # medicine ProductSelectorCard — matching the UX for food/supplements.
        _MEDICINE_REASONS: dict[str, str] = {
            "tick_flea": "Monthly prevention protects against ticks, fleas, and related infections.",
            "deworming": "Regular deworming maintains gut health and prevents parasite transmission.",
        }
        for it in add_items.values():
            tt = it.get("test_type", "")
            if tt in _MEDICINE_REASONS and not it.get("orderable"):
                it["orderable"] = True
                it["reason"] = _MEDICINE_REASONS[tt]

        # ── Add orderable food / supplements to Continue bucket ──────────────
        # Requirement 9.12: place ongoing food and supplements in Continue.
        try:
            diet_rows = (
                db.query(DietItem)
                .filter(DietItem.pet_id == pet.id)
                .all()
            )

            # Fetch active conditions once for signal resolution.
            pet_conditions: list[Condition] = []
            if diet_rows:
                pet_conditions = (
                    db.query(Condition)
                    .filter(Condition.pet_id == pet.id, Condition.is_active.is_(True))
                    .all()
                )

            for diet_item in diet_rows:
                if not diet_item.label:
                    continue
                tt = "supplement" if diet_item.type == "supplement" else "food"
                item_key = f"diet_{diet_item.id}"

                # Homemade food: stored in DB and shown in WhatsApp but excluded from dashboard care plan.
                # Only packaged food and supplements are shown in the care plan (orderable items).
                if diet_item.type == "homemade":
                    continue

                # Packaged food / supplements — resolve via signal resolver.
                signals = _resolve_diet_item_signals(
                    db, diet_item, pet, pet_conditions
                )
                continue_items[item_key] = {
                    "name": diet_item.label,
                    "test_type": tt,
                    "freq": "Daily",
                    "next_due": None,
                    "status_tag": signals["status_tag"],
                    "classification": Classification.PERIODIC.value,
                    "reason": None,
                    "orderable": signals["orderable"],
                    "cta_label": signals["cta_label"],
                    "signal_level": signals["signal_level"],
                    "info_prompt": signals["info_prompt"],
                    "diet_item_id": str(diet_item.id),
                }
        except Exception:
            logger.warning(
                "Failed to load diet items for care plan of pet %s",
                pet.id,
                exc_info=True,
            )

        return CarePlanV2(
            continue_items=_to_sections(continue_items),
            attend_items=_to_sections(attend_items),
            add_items=_to_sections(add_items),
        )

    except Exception:
        logger.error(
            "Failed to compute care plan for pet %s",
            pet.id,
            exc_info=True,
        )
        return CarePlanV2(continue_items=[], attend_items=[], add_items=[])
