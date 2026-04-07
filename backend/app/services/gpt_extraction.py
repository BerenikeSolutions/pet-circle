"""
PetCircle Phase 1 — GPT Extraction Service (Module 7)

Extracts structured preventive health data from uploaded pet documents
using OpenAI GPT. This service processes documents after upload and
routes extracted data to the preventive engine (conflict detection
or record creation).

Extraction pipeline:
    Document (pending) → GPT extraction → Validate JSON → Normalize dates
        → Pass to conflict engine or create preventive record
        → Update extraction_status

Model configuration (all from constants — never hardcoded):
    - Model: OPENAI_EXTRACTION_MODEL (gpt-4.1)
    - Temperature: OPENAI_EXTRACTION_TEMPERATURE (0)
    - Max tokens: OPENAI_EXTRACTION_MAX_TOKENS (1500)
    - Response format: JSON only

Retry policy:
    - Uses retry_openai_call() from utils/retry.py.
    - 3 attempts total (1s, 2s backoff) — configured in constants.
    - On final failure: extraction_status='failed', log error, continue.

Rules:
    - No medical advice in extraction.
    - All dates normalized to YYYY-MM-DD.
    - JSON keys strictly validated.
    - Extraction failures never crash the application.
    - OpenAI API key from environment (settings.OPENAI_API_KEY) — never hardcoded.
"""

import json
import logging
import os
import re
from contextlib import nullcontext
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import (
    DOCUMENT_CATEGORIES,
    OPENAI_EXTRACTION_MAX_TOKENS,
    OPENAI_EXTRACTION_MODEL,
    OPENAI_EXTRACTION_TEMPERATURE,
)
from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.contact import Contact
from app.models.custom_preventive_item import CustomPreventiveItem
from app.models.diagnostic_test_result import DiagnosticTestResult
from app.models.document import Document
from app.models.pet import Pet
from app.models.preventive_master import PreventiveMaster
from app.models.preventive_record import PreventiveRecord
from app.utils.date_utils import format_date_for_db, parse_date
from app.utils.retry import retry_openai_call

logger = logging.getLogger(__name__)

# Conservative pattern: dosage units or pharmaceutical delivery forms that indicate a string
# is a drug/medication name rather than a disease/condition name.  Only triggers on
# things like "Simparica 50mg" or "Doxycycline Capsule", not on real condition names.
_RE_MEDICATION_SIGNAL = re.compile(
    r"\b(\d+\s*(mg|ml|mcg|ug|iu|units?|g)\b)"
    r"|\b(tablet|capsule|syrup|drops?|spray|ointment|cream|lotion|gel"
    r"|powder|suspension|solution|topical)\b",
    re.IGNORECASE,
)

# Maps medication brand names to compatible preventive categories.
# Some medicines can reasonably be used for both deworming and flea/tick.
_MEDICATION_TO_PREVENTIVE_CATEGORIES: dict[str, frozenset[str]] = {
    # Both flea_tick + deworming
    "simparica": frozenset({"flea_tick", "deworming"}),
    "simparica trio": frozenset({"flea_tick", "deworming"}),
    "nexgard spectra": frozenset({"flea_tick", "deworming"}),
    "advocate": frozenset({"flea_tick", "deworming"}),
    "revolution plus": frozenset({"flea_tick", "deworming"}),
    "broadline": frozenset({"flea_tick", "deworming"}),
    # Flea & Tick only
    "nexgard": frozenset({"flea_tick"}),
    "bravecto": frozenset({"flea_tick"}),
    "frontline": frozenset({"flea_tick"}),
    "frontline plus": frozenset({"flea_tick"}),
    "fipronil": frozenset({"flea_tick"}),
    "revolution": frozenset({"flea_tick"}),
    "credelio": frozenset({"flea_tick"}),
    "seresto": frozenset({"flea_tick"}),
    "advantix": frozenset({"flea_tick"}),
    "advantage": frozenset({"flea_tick"}),
    # Deworming only
    "milbemax": frozenset({"deworming"}),
    "drontal": frozenset({"deworming"}),
    "drontal plus": frozenset({"deworming"}),
    "panacur": frozenset({"deworming"}),
    "prazitel": frozenset({"deworming"}),
    "prazitel plus": frozenset({"deworming"}),
    "verminator": frozenset({"deworming"}),
    "fenbendazole": frozenset({"deworming"}),
    "praziquantel": frozenset({"deworming"}),
    "pyrantel": frozenset({"deworming"}),
    "ivermectin": frozenset({"deworming"}),
    "albendazole": frozenset({"deworming"}),
}

# Known preventive medication brand names used for quick medication-name checks.
_KNOWN_MEDICATION_BRANDS: set[str] = set(_MEDICATION_TO_PREVENTIVE_CATEGORIES.keys())


def _build_medicine_coverage_prompt() -> str:
    """Build a MEDICINE COVERAGE GUIDE prompt snippet from _MEDICATION_TO_PREVENTIVE_CATEGORIES.

    Single source of truth — adding a brand to the dict automatically updates
    both GPT prompts (onboarding + document extraction) and the fallback lookup.
    """
    both: list[str] = []
    flea_only: list[str] = []
    deworm_only: list[str] = []
    for brand, cats in _MEDICATION_TO_PREVENTIVE_CATEGORIES.items():
        title = brand.title()
        if "flea_tick" in cats and "deworming" in cats:
            both.append(title)
        elif "flea_tick" in cats:
            flea_only.append(title)
        elif "deworming" in cats:
            deworm_only.append(title)
    lines = [
        "- MEDICINE COVERAGE GUIDE (use this to set prevention_targets correctly):",
        f"  BOTH deworming + flea_tick: {', '.join(both)}",
        f"  flea_tick only: {', '.join(flea_only)}",
        f"  deworming only: {', '.join(deworm_only)}",
        "  For any medicine NOT in this list, use your medical knowledge to determine the correct targets.",
    ]
    return "\n".join(lines)


def _get_preventive_categories_for_medicine(medication_name: str | None) -> set[str]:
    """Return compatible preventive categories for a medicine brand mention.

    Performs normalized containment checks so values like "NexGard Spectra chew"
    still resolve to configured compatibility categories.
    """
    if not isinstance(medication_name, str):
        return set()

    normalized = medication_name.strip().lower()
    if not normalized:
        return set()

    categories: set[str] = set()
    for brand, mapped in _MEDICATION_TO_PREVENTIVE_CATEGORIES.items():
        if brand in normalized:
            categories.update(mapped)
    return categories


def _is_likely_medication_name(name: str) -> bool:
    """Return True if *name* looks like a drug/product rather than a diagnosed condition.

    Checks both explicit dosage/form signals (e.g. "50mg", "Capsule") and known
    preventive medication brand names (e.g. "Simparica", "NexGard").
    This prevents GPT mis-classifications from being stored as Condition records.
    """
    if _RE_MEDICATION_SIGNAL.search(name):
        return True
    return bool(_get_preventive_categories_for_medicine(name))


def _normalize_text_token(value: str | None) -> str:
    """Normalize free text for resilient equality checks."""
    token = (value or "").strip().lower()
    token = re.sub(r"\s+", " ", token)
    return token


def _condition_matches_extracted_medication_name(
    condition_name: str,
    raw_condition: dict,
    preventive_medications: list[dict],
) -> bool:
    """Return True when condition_name matches any extracted medication name.

    This catches GPT misclassification where a medication gets emitted as a
    condition name, without relying on brand-specific hardcoding.
    """
    condition_token = _normalize_text_token(condition_name)
    if not condition_token:
        return False

    names: set[str] = set()
    for med in (raw_condition.get("medications") or []):
        if isinstance(med, dict):
            names.add(_normalize_text_token(str(med.get("name") or "")))

    for med in (preventive_medications or []):
        if isinstance(med, dict):
            names.add(_normalize_text_token(str(med.get("name") or "")))

    names.discard("")
    return condition_token in names


def _extract_partial_json_string_value(raw_json: str, key: str) -> str | None:
    """Best-effort extraction of a top-level JSON string field from malformed output."""
    match = re.search(rf'"{re.escape(key)}"\s*:\s*(null|"(?:\\.|[^"\\])*")', raw_json)
    if not match:
        return None

    raw_value = match.group(1)
    if raw_value == "null":
        return None

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return None

    return str(value).strip() if value is not None else None


def _salvage_partial_extraction_json(raw_json: str) -> dict | None:
    """Recover minimal extraction metadata from malformed GPT JSON."""
    document_name = _extract_partial_json_string_value(raw_json, "document_name")
    document_type = _extract_partial_json_string_value(raw_json, "document_type")
    document_category = _extract_partial_json_string_value(raw_json, "document_category")
    pet_name = _extract_partial_json_string_value(raw_json, "pet_name")
    doctor_name = _extract_partial_json_string_value(raw_json, "doctor_name")
    clinic_name = _extract_partial_json_string_value(raw_json, "clinic_name")

    if not any((document_name, document_type, document_category, pet_name, doctor_name, clinic_name)):
        return None

    return {
        "document_name": document_name,
        "document_type": document_type or "pet_medical",
        "document_category": document_category,
        "pet_name": pet_name,
        "doctor_name": doctor_name,
        "clinic_name": clinic_name,
        "diagnostic_summary": None,
        "diagnostic_values": [],
        "vaccination_details": [],
        "conditions": [],
        "contacts": [],
        "items": [],
    }


def _normalize_document_category(raw_category: str | None) -> str | None:
    """Normalize GPT category output to one of the dashboard's canonical values.

    Maps legacy values ("Diagnostic") and any GPT variants to the 5-section
    document taxonomy: Blood Report, Urine Report, Imaging, Prescription,
    PCR & Parasite Panel, Vaccination, Other.
    """
    value = (raw_category or "").strip().lower()
    if not value:
        return None

    aliases = {
        # Blood report aliases
        "blood report": "Blood Report",
        "blood": "Blood Report",
        "blood test": "Blood Report",
        "blood tests": "Blood Report",
        "cbc": "Blood Report",
        "biochemistry": "Blood Report",
        "haematology": "Blood Report",
        "hematology": "Blood Report",
        "hemogram": "Blood Report",
        "complete blood count": "Blood Report",
        # Urine report aliases
        "urine report": "Urine Report",
        "urine": "Urine Report",
        "urine test": "Urine Report",
        "urine tests": "Urine Report",
        "urinalysis": "Urine Report",
        "urine culture": "Urine Report",
        "urine culture & sensitivity": "Urine Report",
        # Imaging aliases
        "imaging": "Imaging",
        "ultrasound": "Imaging",
        "usg": "Imaging",
        "x-ray": "Imaging",
        "xray": "Imaging",
        "x ray": "Imaging",
        "radiology": "Imaging",
        "scan": "Imaging",
        # PCR & Parasite Panel aliases
        "pcr & parasite panel": "PCR & Parasite Panel",
        "pcr": "PCR & Parasite Panel",
        "parasite panel": "PCR & Parasite Panel",
        "parasite": "PCR & Parasite Panel",
        "parasite screen": "PCR & Parasite Panel",
        "tick panel": "PCR & Parasite Panel",
        "vector-borne": "PCR & Parasite Panel",
        # Prescription aliases
        "prescription": "Prescription",
        "prescriptions": "Prescription",
        "rx": "Prescription",
        "medication": "Prescription",
        "treatment": "Prescription",
        # Vaccination aliases
        "vaccination": "Vaccination",
        "vaccinations": "Vaccination",
        "vaccine": "Vaccination",
        "vaccines": "Vaccination",
        # Legacy "Diagnostic" — map to Blood Report as the most common sub-type;
        # _infer_document_category will override with a more specific value.
        "diagnostic": "Blood Report",
        "diagnostics": "Blood Report",
        "lab": "Blood Report",
        "laboratory": "Blood Report",
        # Other
        "other": "Other",
        "misc": "Other",
        "miscellaneous": "Other",
    }
    if value in aliases:
        return aliases[value]

    for category in DOCUMENT_CATEGORIES:
        if value == category.lower():
            return category

    return None


def _infer_document_category(
    document_name: str | None,
    file_path: str | None,
    items: list[dict],
    vaccination_details: list[dict],
    diagnostic_values: list[dict],
) -> str:
    """Infer the specific document category when GPT omits or misformats it.

    Resolves to one of the 5 report sections used in the dashboard appendix:
    Blood Report | Urine Report | Imaging | Prescription | PCR & Parasite Panel
    (plus Vaccination and Other for non-lab documents).
    """
    name_text = (document_name or "").strip().lower()
    file_text = os.path.basename(file_path or "").strip().lower()
    combined_text = f"{name_text} {file_text}"

    # --- Strong keyword matches (most specific wins) ---
    if any(keyword in combined_text for keyword in ("prescription", "rx", "medicine", "medication")):
        return "Prescription"
    if any(keyword in combined_text for keyword in ("vaccin", "rabies", "dhpp", "fvrcp", "booster")):
        return "Vaccination"

    # PCR / parasite panel — check before generic blood/urine
    if any(keyword in combined_text for keyword in (
        "pcr", "parasite", "tick panel", "vector", "anaplasma",
        "ehrlichia", "babesia", "hepatozoon", "leishmania",
    )):
        return "PCR & Parasite Panel"

    # Imaging
    if any(keyword in combined_text for keyword in (
        "ultrasound", "usg", "x-ray", "xray", "x ray", "radiology", "scan", "imaging",
    )):
        return "Imaging"

    # Urine — before blood so "urine" is not captured by generic "lab"
    if any(keyword in combined_text for keyword in (
        "urine", "urinalysis", "urine culture", "urine test",
    )):
        return "Urine Report"

    # Blood
    if any(keyword in combined_text for keyword in (
        "blood", "cbc", "biochemistry", "hematology", "haematology",
        "hemogram", "complete blood count", "lab", "laboratory", "diagnostic",
    )):
        return "Blood Report"

    # --- Infer from extracted diagnostic_values test_type ---
    if diagnostic_values:
        test_types = {
            str(v.get("test_type") or "").strip().lower()
            for v in diagnostic_values
            if isinstance(v, dict)
        }
        if "xray" in test_types:
            return "Imaging"
        if "urine" in test_types:
            return "Urine Report"
        if "blood" in test_types:
            return "Blood Report"
        if "fecal" in test_types:
            return "PCR & Parasite Panel"  # closest category for parasite/fecal results

    if vaccination_details:
        return "Vaccination"

    item_names = {
        _normalize_preventive_item_name(str(item.get("item_name") or ""))
        for item in items
        if item.get("item_name")
    }
    if item_names & {"rabies vaccine", "core vaccine", "feline core"}:
        return "Vaccination"
    if "preventive blood test" in item_names:
        return "Blood Report"
    if any(item_name in item_names for item_name in ("annual checkup", "dental check", "deworming", "tick/flea")):
        return "Prescription"

    return "Other"


def _resolve_document_category(
    raw_category: str | None,
    inferred_category: str,
    document_name: str | None = None,
    file_path: str | None = None,
) -> str:
    """Prefer inferred category when GPT returned blank, Other, or a coarse legacy value.

    Rules (in priority order):
    1. If raw is None / "Other" and inferred is specific → use inferred.
    2. If filename/document name has a strong keyword that contradicts GPT → use keyword signal.
    3. Otherwise trust GPT's (normalized) raw_category.

    This keeps the 5 specific categories (Blood Report, Urine Report, Imaging,
    Prescription, PCR & Parasite Panel) authoritative over GPT's legacy "Diagnostic".
    """
    combined = f"{(document_name or '').lower()} {os.path.basename(file_path or '').lower()}"

    # Always trust strong keyword signals in filename / document name.
    if "prescription" in combined or " rx " in combined:
        return "Prescription"
    if any(kw in combined for kw in ("pcr", "parasite panel", "parasite screen")):
        return "PCR & Parasite Panel"
    if any(kw in combined for kw in ("ultrasound", "usg", "x-ray", "xray", " xray")):
        return "Imaging"
    if any(kw in combined for kw in ("urine culture", "urinalysis", "urine test")):
        return "Urine Report"

    # If GPT returned a specific known category, trust it.
    if raw_category and raw_category not in (None, "Other"):
        return raw_category

    # Fall back to inference.
    return inferred_category if inferred_category != "Other" else (raw_category or "Other")


def _normalize_name_for_matching(value: str | None) -> str:
    """Normalize a person or pet name for tolerant comparisons."""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", (value or "").strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _pet_name_matches_document_name(extracted_pet_name: str | None, pet_name: str | None) -> bool:
    """Accept pet-name aliases such as 'VEER / ZAYN' when one alias matches the pet."""
    normalized_pet_name = _normalize_name_for_matching(pet_name)
    if not normalized_pet_name:
        return True

    normalized_extracted_name = _normalize_name_for_matching(extracted_pet_name)
    if not normalized_extracted_name:
        return True
    if normalized_extracted_name == normalized_pet_name:
        return True

    alias_candidates = [
        _normalize_name_for_matching(part)
        for part in re.split(r"[\/,&]|\band\b|\bor\b", str(extracted_pet_name), flags=re.IGNORECASE)
    ]
    alias_candidates = [candidate for candidate in alias_candidates if candidate]

    for candidate in alias_candidates:
        if candidate == normalized_pet_name:
            return True
        if re.search(rf"\b{re.escape(normalized_pet_name)}\b", candidate):
            return True

    return False


def _is_plausible_doctor_name(value: str | None, pet_name: str | None = None) -> bool:
    """Reject obvious non-doctor text such as owner labels or pet-name fragments."""
    normalized_value = _normalize_name_for_matching(value)
    if not normalized_value:
        return False
    if pet_name and normalized_value == _normalize_name_for_matching(pet_name):
        return False
    if any(char.isdigit() for char in normalized_value):
        return False

    invalid_keywords = (
        "owner",
        "patient",
        "pet name",
        "collection center",
        "report date",
        "reg date",
        "lab no",
        "species",
        "breed",
        "c o",
    )
    if any(keyword in normalized_value for keyword in invalid_keywords):
        return False

    token_count = len(normalized_value.split())
    if token_count > 6:
        return False

    return len(normalized_value.replace(" ", "")) >= 3


def _select_best_doctor_name(
    metadata_doctor_name: str | None,
    extracted_items: list[dict],
    vaccination_details: list[dict],
    pet_name: str | None,
) -> str | None:
    """Prefer plausible vaccination doctor details over noisy top-level OCR text."""
    candidates: list[str | None] = []

    for detail in vaccination_details:
        if not isinstance(detail, dict):
            continue
        candidates.append(detail.get("administered_by"))
        candidates.append(detail.get("doctor_name"))

    candidates.append(metadata_doctor_name)

    for item in extracted_items:
        if not isinstance(item, dict):
            continue
        candidates.append(item.get("doctor_name"))

    seen: set[str] = set()
    for candidate in candidates:
        normalized_candidate = _normalize_name_for_matching(candidate)
        if normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        if _is_plausible_doctor_name(candidate, pet_name=pet_name):
            return str(candidate).strip()

    return None


def _append_single_extracted_date_to_filename(
    original_filename: str,
    extracted_items: list[dict],
) -> str:
    """
    Preserve original filename and append a date only when extraction has one unique date.

    Rules:
      - If exactly one valid unique `last_done_date` exists, append it to the filename.
      - If zero or multiple unique dates exist, return the original filename unchanged.
      - If the filename already contains that date, return unchanged (idempotent).
    """
    unique_dates: set[str] = set()
    for item in extracted_items:
        date_str = item.get("last_done_date")
        if not date_str:
            continue

        # Keep only valid canonical dates.
        try:
            normalized = datetime.strptime(str(date_str), "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            continue

        unique_dates.add(normalized)

    if len(unique_dates) != 1:
        return original_filename

    only_date = next(iter(unique_dates))
    if only_date in original_filename:
        return original_filename

    # Append date before extension when present.
    dot = original_filename.rfind(".")
    if dot > 0:
        return f"{original_filename[:dot]}_{only_date}{original_filename[dot:]}"
    return f"{original_filename}_{only_date}"


def _extract_date_from_filename(file_path: str | None) -> str | None:
    """Extract a canonical YYYY-MM-DD date from a document filename when present."""
    stem = os.path.splitext(os.path.basename(file_path or ""))[0]
    if not stem:
        return None

    normalized = stem.replace("_", "-").replace(".", "-")
    patterns = (
        r"\b\d{1,2}-\d{1,2}-\d{2,4}\b",
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        try:
            return format_date_for_db(parse_date(match.group(0)))
        except ValueError:
            continue
    return None


def _derive_blood_test_fallback_items(
    extracted_items: list[dict],
    document_name: str | None,
    file_path: str | None,
    document_category: str | None,
    diagnostic_values: list[dict],
) -> list[dict]:
    """Fill in Preventive Blood Test when blood report docs omit tracked items."""
    if document_category not in ("Blood Report", "Diagnostic"):
        return extracted_items

    # Skip fallback if items already include a Preventive Blood Test entry.
    has_blood_item = any(
        _normalize_preventive_item_name(item.get("item_name", "")) == "preventive blood test"
        for item in extracted_items
    )
    if has_blood_item:
        return extracted_items

    combined_text = f"{(document_name or '').lower()} {os.path.basename(file_path or '').lower()}"
    blood_like = any(keyword in combined_text for keyword in (
        "blood",
        "cbc",
        "hematology",
        "haematology",
        "hemogram",
        "complete blood count",
    ))
    has_blood_values = any(
        isinstance(value, dict) and str(value.get("test_type") or "").strip().lower() == "blood"
        for value in diagnostic_values
    )
    if not blood_like and not has_blood_values:
        return extracted_items

    observed_dates: list[str] = []
    for value in diagnostic_values:
        if not isinstance(value, dict):
            continue
        if str(value.get("test_type") or "").strip().lower() != "blood":
            continue
        observed_at = value.get("observed_at")
        if not observed_at:
            continue
        try:
            observed_dates.append(format_date_for_db(parse_date(str(observed_at))))
        except ValueError:
            continue

    fallback_date = observed_dates[0] if observed_dates else _extract_date_from_filename(file_path)
    if not fallback_date:
        return extracted_items

    # Append the blood test fallback to any existing items rather than replacing.
    return extracted_items + [{"item_name": "Preventive Blood Test", "last_done_date": fallback_date}]


# --- Expected JSON keys from GPT extraction ---
# Each extracted item must have these keys.
# Any missing key causes validation failure.
REQUIRED_EXTRACTION_KEYS = {"item_name", "last_done_date"}

# --- System prompt for GPT extraction ---
# Instructs GPT to extract structured preventive health data only.
# No medical advice. No inference beyond the document content.
EXTRACTION_SYSTEM_PROMPT = (
    "You are a veterinary document data extractor. "
    "Analyze the provided document and return a JSON object with these keys:\n"
    '  - "document_name": string (a short descriptive name for this document, '
    "e.g., 'Blood Test Report', 'Vaccination Certificate', 'Deworming Record', "
    "'Vet Prescription', 'Health Checkup Report')\n"
    '  - "document_type": "pet_medical" or "not_pet_related" '
    "(set to 'not_pet_related' if the document is clearly NOT a pet/veterinary document, "
    "e.g., a human medical report, invoice, random photo, etc.)\n"
    '  - "document_category": one of "Blood Report", "Urine Report", "Imaging", '
    '"Prescription", "PCR & Parasite Panel", "Vaccination", "Other" — '
    "pick the most specific match: "
    "Blood Report for CBC/biochemistry/haematology/blood test reports, "
    "Urine Report for urinalysis/urine culture/urine sensitivity reports, "
    "Imaging for ultrasound/USG/X-ray/radiology reports, "
    "Prescription for vet prescriptions/medication records, "
    "PCR & Parasite Panel for PCR/parasite/tick-borne disease panels, "
    "Vaccination for vaccine certificates/immunisation records, "
    "Other for anything else\n"
    '  - "diagnostic_summary": string or null (for Diagnostic documents only — '
    "provide a 1-2 sentence plain-language summary of key findings; null otherwise)\n"
    '  - "diagnostic_values": array (for Diagnostic reports), each with:\n'
    '    - "test_type": "blood" | "urine" | "fecal" | "xray"\n'
    '    - "parameter_name": string (e.g., Hemoglobin, WBC, Creatinine, Urine pH; '
    "for xray: anatomical region like 'Hip Joint'; "
    "for fecal: parasite name like 'Roundworm')\n"
    '    - "value_numeric": number or null\n'
    '    - "value_text": string or null (use when numeric is not available; '
    "for xray: the finding description; for fecal: result text)\n"
    '    - "unit": string or null\n'
    '    - "reference_range": string or null\n'
    '    - "status_flag": "low" | "normal" | "high" | "abnormal" | null\n'
    '    - "observed_at": date string (same accepted formats) or null\n'
    '  - "conditions": array of objects (diagnosed diseases/conditions found in the document; [] if none), each with:\n'
    '    - "condition_name": string — the NAME of a diagnosed DISEASE, DISORDER, or SYNDROME only '
    '(e.g. "Hip Dysplasia", "Diabetes Mellitus", "Otitis Externa", "Skin Allergy"). '
    'NEVER use a medication, drug, supplement, or vaccine brand as condition_name '
    '(e.g. do NOT write "Simparica", "Doxycycline", "NexGard", "Omega-3" as a condition_name).\n'
    '    - "condition_type": "chronic" | "episodic" | "resolved"\n'
    '    - "diagnosis": string or null (brief diagnosis description)\n'
    '    - "diagnosed_at": date string or null\n'
    '    - "medications": array of objects ([] if none) — drugs/products prescribed TO TREAT this condition, each with:\n'
    '      - "name": string (medication/drug name)\n'
    '      - "dose": string or null\n'
    '      - "frequency": string or null (e.g., "Once daily", "Twice daily")\n'
    '      - "route": string or null (e.g., "oral", "topical", "injection")\n'
    '    - "monitoring": array of objects ([] if none), each with:\n'
    '      - "name": string (e.g., "Blood Work", "Follow-up Vet Visit")\n'
    '      - "frequency": string or null (e.g., "Every 6 months", "Yearly")\n'
    '  - "preventive_medications": array of objects ([] if none) — preventive medicines used for deworming and/or flea/tick control even when no diagnosis is present, each with:\n'
    '    - "name": string (medicine/product name as written)\n'
    '    - "start_date": date string or null\n'
    '    - "prevention_targets": array containing one or both of "deworming", "flea_tick"\n'
    '    - "dose": string or null\n'
    '    - "frequency": string or null\n'
    '    - "route": string or null\n'
    '  - "contacts": array of objects (vet/clinic/specialist contacts found in the document; [] if none), each with:\n'
    '    - "role": "veterinarian" | "groomer" | "trainer" | "specialist" | "other"\n'
    '    - "name": string (person name)\n'
    '    - "clinic_name": string or null\n'
    '    - "phone": string or null\n'
    '    - "email": string or null\n'
    '    - "address": string or null\n'
    '  - "pet_name": string or null (the name of the pet mentioned in the document, '
    "if explicitly stated; null if no pet name is found)\n"
    '  - "doctor_name": string or null (veterinarian/doctor name if explicitly mentioned)\n'
    '  - "clinic_name": string or null (hospital/clinic name if explicitly mentioned)\n'
    '  - "vaccination_details": array of objects (for vaccine records; [] if none). '
    "Each object may include: vaccine_name, vaccine_name_raw, dose, dose_unit, "
    "route, manufacturer, batch_number, next_due_date, administered_by, notes\n"
    '  - "items": array of objects, each with:\n'
    '    - "item_name": string (MUST be one of the tracked items listed below)\n'
    '    - "last_done_date": string (the date the item was done, '
    "in DD/MM/YYYY or DD-MM-YYYY or DD-Mon-YYYY or DD Month YYYY or YYYY-MM-DD format)\n"
    '    - "dose": string or null (dose amount, if present in the document)\n'
    '    - "doctor_name": string or null (doctor name for that line item, if present)\n'
    '    - "clinic_name": string or null (clinic name for that line item, if present)\n'
    '    - "batch_number": string or null (vaccine lot/batch number, if present)\n\n'
    "Tracked preventive items (use these EXACT names):\n"
    "  - Rabies Vaccine\n"
    "  - Rabies (Nobivac RL)\n"
    "  - Core Vaccine\n"
    "  - DHPPi\n"
    "  - Feline Core\n"
    "  - Kennel Cough (Nobivac KC)\n"
    "  - Canine Coronavirus (CCoV)\n"
    "  - Deworming\n"
    "  - Tick/Flea\n"
    "  - Annual Checkup\n"
    "  - Preventive Blood Test\n"
    "  - Dental Check\n\n"
    "Rules:\n"
    "- Extract ONLY items that match the tracked preventive items above.\n"
    "- A blood test report counts as 'Preventive Blood Test' — use the report date.\n"
    "- Do NOT provide medical advice or interpretation.\n"
    "- Do NOT infer dates — only extract what is explicitly stated.\n"
    "- Extract the pet's name EXACTLY as written in the document (if present).\n"
    "- For vaccination records, extract all available vaccine details (dose, batch, doctor, clinic, next due date) without guessing.\n"
    "- For dog vaccination cards, include each administered vaccine row in items (e.g., DHPPi, Rabies, Kennel Cough, CCoV) when a done date is present.\n"
    "- For vaccination cards/booklets, treat the administered date as the handwritten/typed DATE GIVEN for each row.\n"
    "- NEVER use vaccine sticker metadata dates (manufacturing/expiry/lot label dates) as last_done_date.\n"
    "- In vaccination documents, do not add Annual Checkup to items unless a separate checkup event is explicitly documented outside the vaccine table.\n"
    "- Capture next_due_date for each vaccine row whenever it is visible.\n"
    "- For X-ray reports: use test_type 'xray', anatomical region as parameter_name, finding as value_text.\n"
    "- For fecal reports: use test_type 'fecal', parasite name as parameter_name, result as value_text, status_flag normal/abnormal.\n"
    "- For conditions: extract diagnosed diseases/disorders/syndromes with their medications and monitoring.\n"
    "- condition_name must be the DISEASE/DISORDER name only — never a drug, supplement, or vaccine brand name.\n"
    "- If a document lists preventive medicines without a diagnosis, keep conditions: [] and populate preventive_medications[].\n"
    "- For each preventive_medications entry, always set prevention_targets explicitly using one or both: deworming, flea_tick.\n"
    "- If the medicine coverage text indicates both internal parasites (worms/deworming) and external parasite control (flea/tick), include BOTH targets.\n"
    f"{_build_medicine_coverage_prompt()}\n"
    "- Drugs prescribed to treat a condition belong in that condition's medications[] array, not as a separate condition.\n"
    "- For contacts: extract vet/specialist contact details when explicitly present in the document.\n"
    "- If any field is missing in the document, use null for that field.\n"
    "- If the document is not pet/veterinary related, set document_type to 'not_pet_related' and items to [].\n"
    '- If no preventive items are found, return {"document_name": "...", "document_type": "pet_medical", '
    '"document_category": "...", "diagnostic_summary": null, "pet_name": null, "items": [], '
    '"conditions": [], "preventive_medications": [], "contacts": []}\n'
    "- Return valid JSON only — no markdown, no explanation, no extra text."
)


_openai_extraction_client = None


def _get_openai_extraction_client():
    """Return a cached AsyncOpenAI client for extraction (created on first call)."""
    global _openai_extraction_client
    if _openai_extraction_client is None:
        from openai import AsyncOpenAI
        _openai_extraction_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_extraction_client


async def _call_openai_extraction(document_text: str) -> str:
    """
    Call OpenAI GPT to extract structured data from document text.

    Used for PDF text content. For images, use _call_openai_extraction_vision().

    Args:
        document_text: The text content of the uploaded document.

    Returns:
        Raw JSON string response from GPT.

    Raises:
        Exception: If all retry attempts fail (propagated from retry_openai_call).
    """
    client = _get_openai_extraction_client()

    async def _make_call() -> str:
        response = await client.chat.completions.create(
            model=OPENAI_EXTRACTION_MODEL,
            temperature=OPENAI_EXTRACTION_TEMPERATURE,
            max_tokens=OPENAI_EXTRACTION_MAX_TOKENS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": document_text},
            ],
        )
        return response.choices[0].message.content

    return await retry_openai_call(_make_call)


async def _call_openai_extraction_vision(image_data_uri: str) -> str:
    """
    Call OpenAI GPT vision API to extract data from an image.

    Sends the image as a base64 data URI to GPT-4.1's vision capability.
    Used for JPEG/PNG uploads where text extraction is not possible.

    Args:
        image_data_uri: Base64 data URI (data:image/jpeg;base64,...).

    Returns:
        Raw JSON string response from GPT.

    Raises:
        Exception: If all retry attempts fail.
    """
    client = _get_openai_extraction_client()

    async def _make_call() -> str:
        response = await client.chat.completions.create(
            model=OPENAI_EXTRACTION_MODEL,
            temperature=OPENAI_EXTRACTION_TEMPERATURE,
            max_tokens=OPENAI_EXTRACTION_MAX_TOKENS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract preventive health data from this veterinary document image.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_uri, "detail": "high"},
                        },
                    ],
                },
            ],
        )
        return response.choices[0].message.content

    return await retry_openai_call(_make_call)


def _validate_extraction_json(raw_json: str) -> tuple[list[dict], str | None, str | None, dict]:
    """
    Parse and validate the JSON response from GPT extraction.

    Validation rules:
        - Must be valid JSON.
        - Must contain a list of objects (or a wrapper with 'items' key).
        - Each object must contain all REQUIRED_EXTRACTION_KEYS.
        - Dates must be parseable by parse_date() from date_utils.

    Args:
        raw_json: Raw JSON string from GPT response.

    Returns:
        Tuple of (validated items list, document_name or None, extracted_pet_name or None, metadata dict).
        metadata contains: document_type, document_category, diagnostic_summary,
        doctor_name, clinic_name, vaccination_details.

    Raises:
        ValueError: If JSON is invalid or missing required keys.
    """
    # Parse JSON — reject non-JSON responses.
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        parsed = _salvage_partial_extraction_json(raw_json)
        if parsed is None:
            raise ValueError(
                f"GPT returned invalid JSON: {str(e)}"
            ) from e

        logger.warning(
            "Recovered partial extraction metadata from malformed GPT JSON: %s",
            str(e),
        )

    # Extract document_name, pet_name, and new classification fields.
    document_name = None
    extracted_pet_name = None
    metadata = {
        "document_type": "pet_medical",
        "document_category": None,
        "diagnostic_summary": None,
        "diagnostic_values": [],
        "doctor_name": None,
        "clinic_name": None,
        "vaccination_details": [],
        "extra_vaccines": [],
        "conditions": [],
        "preventive_medications": [],
        "contacts": [],
    }
    if isinstance(parsed, dict):
        document_name = parsed.get("document_name")
        extracted_pet_name = parsed.get("pet_name")
        # Extract classification metadata.
        metadata["document_type"] = parsed.get("document_type", "pet_medical")
        metadata["document_category"] = _normalize_document_category(parsed.get("document_category"))
        metadata["diagnostic_summary"] = parsed.get("diagnostic_summary")
        raw_diagnostic_values = parsed.get("diagnostic_values")
        if isinstance(raw_diagnostic_values, list):
            metadata["diagnostic_values"] = raw_diagnostic_values
        metadata["doctor_name"] = parsed.get("doctor_name")
        metadata["clinic_name"] = parsed.get("clinic_name")
        raw_vaccination_details = parsed.get("vaccination_details")
        if isinstance(raw_vaccination_details, list):
            metadata["vaccination_details"] = raw_vaccination_details
        raw_conditions = parsed.get("conditions")
        if isinstance(raw_conditions, list):
            # Conditions are passed through raw; _is_likely_medication_name guard
            # is applied downstream in extract_and_process_document.
            metadata["conditions"] = raw_conditions
        raw_preventive_medications = parsed.get("preventive_medications")
        if isinstance(raw_preventive_medications, list):
            metadata["preventive_medications"] = raw_preventive_medications
        raw_contacts = parsed.get("contacts")
        if isinstance(raw_contacts, list):
            metadata["contacts"] = raw_contacts

    # Handle both direct array and wrapper object formats.
    # GPT with json_object mode returns an object, not an array.
    # Accept {"items": [...]} or direct [...] format.
    if isinstance(parsed, dict):
        # Look for common wrapper keys.
        if "items" in parsed:
            items = parsed["items"]
        elif "data" in parsed:
            items = parsed["data"]
        elif "results" in parsed:
            items = parsed["results"]
        else:
            # Single item wrapped in object — treat as single-item list.
            items = [parsed]
    elif isinstance(parsed, list):
        items = parsed
    else:
        raise ValueError(
            f"GPT returned unexpected type: {type(parsed).__name__}. "
            f"Expected JSON array or object."
        )

    if not isinstance(items, list):
        raise ValueError(
            f"Extracted items must be a list, got {type(items).__name__}."
        )

    # Validate each extracted item.
    today = datetime.utcnow().date()
    validated = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict extraction item at index %d: %s",
                i, str(item),
            )
            continue

        # Check required keys.
        missing_keys = REQUIRED_EXTRACTION_KEYS - set(item.keys())
        if missing_keys:
            logger.warning(
                "Skipping extraction item at index %d — missing keys: %s. "
                "Item: %s",
                i, missing_keys, str(item),
            )
            continue

        # Normalize and validate the date.
        try:
            parsed_date = parse_date(str(item["last_done_date"]))
            if parsed_date > today:
                logger.warning(
                    "Skipping extraction item at index %d — future date %s. Item: %s",
                    i, str(parsed_date), str(item),
                )
                continue
            item["last_done_date"] = format_date_for_db(parsed_date)
        except ValueError as e:
            logger.warning(
                "Skipping extraction item at index %d — invalid date: %s. "
                "Item: %s",
                i, str(e), str(item),
            )
            continue

        validated.append(item)

    # Vaccination records should not include generic annual-checkup rows inferred
    # from vaccine tables.
    document_category = metadata.get("document_category")
    if document_category == "Vaccination":
        validated = [
            item for item in validated
            if _normalize_preventive_item_name(item.get("item_name", "")) != "annual checkup"
        ]

    # Normalize optional next_due_date inside vaccination_details.
    normalized_vaccination_details = []
    for detail in metadata.get("vaccination_details", []):
        if not isinstance(detail, dict):
            continue

        next_due = detail.get("next_due_date")
        if next_due:
            try:
                detail["next_due_date"] = format_date_for_db(parse_date(str(next_due)))
            except ValueError:
                detail["next_due_date"] = None

        normalized_vaccination_details.append(detail)

    metadata["vaccination_details"] = normalized_vaccination_details

    # Derive tracked items from vaccination_details when GPT populated
    # vaccine details but did not include matching entries in the items array.
    validated, extra_vaccines = _derive_items_from_vaccination_details(
        validated,
        normalized_vaccination_details,
    )
    metadata["extra_vaccines"] = extra_vaccines

    # Derive tracked preventive items from extracted medications.
    raw_conditions = metadata.get("conditions") or []
    raw_preventive_medications = metadata.get("preventive_medications") or []
    validated = _derive_items_from_medication_brands(
        validated,
        raw_conditions,
        raw_preventive_medications,
    )

    return validated, document_name, extracted_pet_name, metadata


# Mapping from common vaccine names in vaccination_details to tracked item names.
_VACCINE_DETAIL_TO_ITEM: dict[str, str] = {
    "rabies": "Rabies (Nobivac RL)",
    "nobivac rl": "Rabies (Nobivac RL)",
    "dhpp": "DHPPi",
    "dhppi": "DHPPi",
    "dhppi+l": "DHPPi",
    "dhppil": "DHPPi",
    "nobivac dhppi": "DHPPi",
    "da2pp": "DHPPi",
    "da2ppl": "DHPPi",
    "5 in 1": "DHPPi",
    "7 in 1": "DHPPi",
    "9 in 1": "DHPPi",
    "canine distemper": "DHPPi",
    "kennel cough": "Kennel Cough (Nobivac KC)",
    "bordetella": "Kennel Cough (Nobivac KC)",
    "nobivac kc": "Kennel Cough (Nobivac KC)",
    "canine coronavirus": "Canine Coronavirus (CCoV)",
    "ccov": "Canine Coronavirus (CCoV)",
    "leptospirosis": "Leptospirosis",
    "lepto": "Leptospirosis",
    "fvrcp": "Feline Core",
    "feline core": "Feline Core",
    "tricat": "Feline Core",
    "felocell": "Feline Core",
    # Keep this generic; species-aware resolution happens later in
    # _match_preventive_master_from_list via aliases + available masters.
    "core vaccine": "Core Vaccine",
}


def _derive_items_from_vaccination_details(
    existing_items: list[dict],
    vaccination_details: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Convert vaccination_details entries into tracked preventive items
    when they are not already represented in the items array.

    GPT often populates vaccination_details with rich metadata but omits
    the corresponding entry from the items array. This bridges that gap.
    """
    if not vaccination_details:
        return existing_items, []

    # Track which item names are already present (normalized).
    existing_names = {
        _normalize_preventive_item_name(item.get("item_name", ""))
        for item in existing_items
    }

    derived: list[dict] = []
    extra_vaccines: list[dict] = []
    for detail in vaccination_details:
        if not isinstance(detail, dict):
            continue

        vaccine_name = str(detail.get("vaccine_name") or detail.get("vaccine_name_raw") or "").strip()
        if not vaccine_name:
            continue

        # Try to map the vaccine name to one or more tracked items.
        # A single line can mention multiple antigens (e.g. "Nobivac DHPPi + KC").
        normalized_vaccine = vaccine_name.lower().strip()
        mapped_items: list[str] = []
        for keyword, item_name in _VACCINE_DETAIL_TO_ITEM.items():
            if keyword in normalized_vaccine:
                if item_name not in mapped_items:
                    mapped_items.append(item_name)

        if not mapped_items:
            # Preserve vaccine rows that don't map to tracked preventive items.
            # These can be shown as separate extra vaccines to the pet parent.
            extra_vaccines.append(
                {
                    "vaccine_name": vaccine_name,
                    "date": detail.get("date") or detail.get("administered_date") or detail.get("last_done_date"),
                    "next_due_date": detail.get("next_due_date"),
                    "dose": detail.get("dose"),
                    "batch_number": detail.get("batch_number"),
                }
            )
            continue

        # We need a date — try next_due_date is NOT last_done, we need administered date.
        # vaccination_details doesn't have a standard "administered_date" key,
        # so we skip if we can't determine when it was done.
        # The items array is the primary source for last_done_date.
        # Only derive if we can find a date from the detail.
        admin_date = detail.get("date") or detail.get("administered_date") or detail.get("last_done_date")
        if not admin_date:
            continue

        try:
            parsed = format_date_for_db(parse_date(str(admin_date)))
        except ValueError:
            continue

        for mapped_item in mapped_items:
            normalized_item = _normalize_preventive_item_name(mapped_item)
            if normalized_item in existing_names:
                continue
            derived.append({"item_name": mapped_item, "last_done_date": parsed})
            existing_names.add(normalized_item)

    return existing_items + derived, extra_vaccines


def _derive_items_from_medication_brands(
    existing_items: list[dict],
    conditions: list[dict],
    preventive_medications: list[dict] | None = None,
) -> list[dict]:
    """
    Scan extracted medication names and add corresponding tracked preventive
    items if not already present.

    Source priority:
    1) explicit `prevention_targets` from preventive_medications
    2) brand-name category mapping fallback
    """
    existing_item_names = {
        _normalize_preventive_item_name(item.get("item_name", ""))
        for item in existing_items
    }
    extra_items: list[dict] = []

    category_to_item_name = {
        "deworming": "Deworming",
        "flea_tick": "Tick/Flea",
    }

    def _normalize_prevention_target(value: str) -> str | None:
        token = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if token in {"flea", "tick", "tick_flea", "flea_tick", "tick/flea", "flea/tick"}:
            return "flea_tick"
        if token in {"deworm", "deworming", "worms", "worm"}:
            return "deworming"
        return None

    medication_rows: list[dict] = []
    for condition in (conditions or []):
        if not isinstance(condition, dict):
            continue
        for med in (condition.get("medications") or []):
            if isinstance(med, dict):
                medication_rows.append(med)

    for med in (preventive_medications or []):
        if isinstance(med, dict):
            medication_rows.append(med)

    for med in medication_rows:
        med_name_raw = med.get("name")
        med_name = med_name_raw.strip() if isinstance(med_name_raw, str) else ""

        start_date_raw = med.get("start_date")
        if start_date_raw is None:
            # Preventive records require a concrete done date; skip incomplete meds.
            continue
        try:
            parsed_start_date = parse_date(str(start_date_raw))
        except ValueError:
            continue
        if parsed_start_date > datetime.utcnow().date():
            continue
        normalized_start_date = format_date_for_db(parsed_start_date)

        explicit_categories: set[str] = set()
        raw_targets = med.get("prevention_targets")
        if isinstance(raw_targets, list):
            for target in raw_targets:
                normalized_target = _normalize_prevention_target(str(target))
                if normalized_target:
                    explicit_categories.add(normalized_target)

        categories = explicit_categories or _get_preventive_categories_for_medicine(med_name)
        for category in categories:
            tracked_item = category_to_item_name.get(category)
            if not tracked_item:
                continue
            normalized_item = _normalize_preventive_item_name(tracked_item)
            if normalized_item in existing_item_names:
                continue
            extra_items.append({
                "item_name": tracked_item,
                "last_done_date": normalized_start_date,
            })
            existing_item_names.add(normalized_item)

    return existing_items + extra_items


def _normalize_extra_vaccine_name(value: str | None) -> str:
    """Normalize vaccine names before storing custom preventive entries."""
    name = re.sub(r"\s+", " ", (value or "").strip())
    return name[:120]


def _upsert_custom_item_for_extra_vaccine(
    db: Session,
    *,
    user_id,
    species: str,
    vaccine_name: str,
) -> CustomPreventiveItem:
    """Get or create a custom preventive item for an unmapped vaccine."""
    existing = (
        db.query(CustomPreventiveItem)
        .filter(
            CustomPreventiveItem.user_id == user_id,
            CustomPreventiveItem.item_name == vaccine_name,
            CustomPreventiveItem.species == species,
        )
        .first()
    )
    if existing:
        return existing

    custom_item = CustomPreventiveItem(
        user_id=user_id,
        item_name=vaccine_name,
        category="complete",
        circle="health",
        species=species,
        recurrence_days=365,
        medicine_dependent=False,
        reminder_before_days=30,
        overdue_after_days=14,
    )
    db.add(custom_item)
    db.flush()
    return custom_item


def _upsert_custom_preventive_record_for_pet(
    db: Session,
    *,
    pet_id,
    custom_item: CustomPreventiveItem,
    last_done_date,
) -> None:
    """Create or update a pet-level preventive record for a custom vaccine item."""
    from app.services.preventive_calculator import compute_next_due_date, compute_status

    if last_done_date is None:
        placeholder = (
            db.query(PreventiveRecord)
            .filter(
                PreventiveRecord.pet_id == pet_id,
                PreventiveRecord.custom_preventive_item_id == custom_item.id,
                PreventiveRecord.last_done_date.is_(None),
                PreventiveRecord.status != "cancelled",
            )
            .first()
        )
        if placeholder:
            return
        db.add(
            PreventiveRecord(
                pet_id=pet_id,
                custom_preventive_item_id=custom_item.id,
                last_done_date=None,
                next_due_date=None,
                status="upcoming",
            )
        )
        db.flush()
        return

    next_due = compute_next_due_date(last_done_date, custom_item.recurrence_days)
    status = compute_status(next_due, custom_item.reminder_before_days)

    existing = (
        db.query(PreventiveRecord)
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveRecord.custom_preventive_item_id == custom_item.id,
            PreventiveRecord.last_done_date == last_done_date,
        )
        .first()
    )
    if existing:
        existing.next_due_date = next_due
        existing.status = status
        db.flush()
        return

    placeholder = (
        db.query(PreventiveRecord)
        .filter(
            PreventiveRecord.pet_id == pet_id,
            PreventiveRecord.custom_preventive_item_id == custom_item.id,
            PreventiveRecord.last_done_date.is_(None),
            PreventiveRecord.status != "cancelled",
        )
        .order_by(PreventiveRecord.created_at.asc())
        .first()
    )
    if placeholder:
        placeholder.last_done_date = last_done_date
        placeholder.next_due_date = next_due
        placeholder.status = status
        db.flush()
        return

    db.add(
        PreventiveRecord(
            pet_id=pet_id,
            custom_preventive_item_id=custom_item.id,
            last_done_date=last_done_date,
            next_due_date=next_due,
            status=status,
        )
    )
    db.flush()


def _persist_extra_vaccines_for_pet(
    db: Session,
    *,
    pet: Pet,
    extra_vaccines: list[dict],
) -> tuple[int, list[str]]:
    """Persist unmapped vaccines as custom preventive records for the specific pet."""
    if not extra_vaccines:
        return 0, []

    saved = 0
    errors: list[str] = []
    seen_keys: set[tuple[str, str | None]] = set()

    for detail in extra_vaccines:
        if not isinstance(detail, dict):
            continue

        vaccine_name = _normalize_extra_vaccine_name(detail.get("vaccine_name"))
        if not vaccine_name:
            continue

        date_input = detail.get("date")
        normalized_date = str(date_input).strip() if date_input is not None else None
        try:
            done_date = parse_date(normalized_date) if normalized_date else None
        except ValueError:
            done_date = None

        canonical_date = done_date.isoformat() if done_date else normalized_date
        dedupe_key = (vaccine_name.lower(), canonical_date)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        try:
            scope = db.begin_nested() if hasattr(db, "begin_nested") else nullcontext()
            with scope:
                custom_item = _upsert_custom_item_for_extra_vaccine(
                    db,
                    user_id=pet.user_id,
                    species=pet.species,
                    vaccine_name=vaccine_name,
                )
                _upsert_custom_preventive_record_for_pet(
                    db,
                    pet_id=pet.id,
                    custom_item=custom_item,
                    last_done_date=done_date,
                )
                saved += 1
        except Exception as exc:
            logger.warning(
                "Could not persist extra vaccine '%s' for pet %s: %s",
                vaccine_name,
                str(pet.id),
                exc,
            )
            errors.append(f"Could not save extra vaccine: {vaccine_name}")

    return saved, errors


def _load_species_masters(db: Session, species: str) -> list[PreventiveMaster]:
    """
    Load all preventive master records for a species (including 'both').

    Loads once per extraction call and caches in-memory to avoid
    repeated DB queries when matching multiple extracted items.

    Args:
        db: SQLAlchemy database session.
        species: Pet species ('dog' or 'cat').

    Returns:
        List of PreventiveMaster records for this species.
    """
    return (
        db.query(PreventiveMaster)
        .filter(PreventiveMaster.species.in_([species, "both"]))
        .all()
    )


def _should_include_puppy_series_for_pet(pet: Pet) -> bool:
    """Return True when one-time puppy vaccine series should remain matchable.

    Puppy-dose rows in preventive_master are marked with recurrence_days=36500.
    Keep these rows only for young dogs (up to ~15 months), otherwise adult
    extractions can incorrectly map to puppy-dose items.
    """
    if (pet.species or "").strip().lower() != "dog":
        return False
    if pet.dob is None:
        return False

    pet_age_days = (datetime.utcnow().date() - pet.dob).days
    if pet_age_days < 0:
        return False
    return pet_age_days <= 450


def _filter_non_applicable_puppy_series(
    masters: list[PreventiveMaster],
    *,
    include_puppy_series: bool,
) -> list[PreventiveMaster]:
    """Filter out one-time puppy-dose masters unless explicitly needed."""
    if include_puppy_series:
        return masters
    return [master for master in masters if (master.recurrence_days or 0) < 36500]


def _normalize_preventive_item_name(name: str) -> str:
    """Normalize extracted preventive item names for robust matching."""
    value = (name or "").strip().lower()
    value = re.sub(r"\s*\([^)]*\)", "", value)  # drop parenthetical clarifiers
    value = re.sub(r"\s+", " ", value)
    return value


def _match_preventive_master_from_list(
    masters: list[PreventiveMaster],
    item_name: str,
) -> PreventiveMaster | None:
    """Match an extracted item name to a preventive_master record."""
    item_normalized = _normalize_preventive_item_name(item_name)

    master_names = {
        _normalize_preventive_item_name(master.item_name)
        for master in masters
    }

    aliases = {
        "core vaccine dhpp": "dhppi",
        "core vaccine dhppi": "dhppi",
        "core vaccine": "dhppi" if "dhppi" in master_names else "feline core",
        "dhpp": "dhppi",
        "dhppi": "dhppi",
        "dhppil": "dhppi",
        "nobivac dhppi": "dhppi",
        "7 in 1": "dhppi",
        "9 in 1": "dhppi",
        "rabies": (
            "rabies nobivac rl"
            if "rabies nobivac rl" in master_names
            else "rabies vaccine"
        ),
        "rabies vaccine": (
            "rabies nobivac rl"
            if "rabies nobivac rl" in master_names
            else "rabies vaccine"
        ),
        "nobivac rl": (
            "rabies nobivac rl"
            if "rabies nobivac rl" in master_names
            else "rabies vaccine"
        ),
        "kennel cough": "kennel cough nobivac kc",
        "nobivac kc": "kennel cough nobivac kc",
        "bordetella": "kennel cough nobivac kc",
        "canine coronavirus": "canine coronavirus ccov",
        "ccov": "canine coronavirus ccov",
        "feline core fvrcp": "feline core",
        "fvrcp": "feline core",
    }
    item_normalized = aliases.get(item_normalized, item_normalized)

    # Try normalized exact match first.
    for master in masters:
        if _normalize_preventive_item_name(master.item_name) == item_normalized:
            return master

    # Try partial match in both directions — GPT may abbreviate or rephrase.
    for master in masters:
        master_normalized = _normalize_preventive_item_name(master.item_name)
        if (
            item_normalized in master_normalized
            or master_normalized in item_normalized
        ):
            return master

    return None


async def extract_and_process_document(
    db: Session,
    document_id: UUID,
    document_text: str,
    file_bytes: bytes | None = None,
) -> dict:
    """
    Run GPT extraction on a document and process the results.

    This is the main extraction pipeline entry point. It:
        1. Calls OpenAI GPT to extract preventive data from the document.
        2. Validates and normalizes the extraction JSON.
        3. For each extracted item, checks for conflicts via the conflict engine.
        4. Creates or updates preventive records as needed.
        5. Updates the document's extraction_status.

    On failure at any step:
        - extraction_status is set to 'failed'.
        - The error is logged.
        - The application does NOT crash.

    Args:
        db: SQLAlchemy database session.
        document_id: UUID of the document to process.
        document_text: Text content of the document (OCR output or raw text).

    Returns:
        Dictionary with extraction results:
            - status: 'success' or 'failed'
            - document_id: the processed document ID
            - items_extracted: count of valid items extracted
            - items_processed: count of items successfully processed
            - errors: list of error messages for failed items
    """
    # Import here to avoid circular imports.
    from app.services.conflict_engine import check_and_create_conflict
    from app.services.preventive_calculator import create_preventive_record

    results = {
        "status": "success",
        "document_id": str(document_id),
        "items_extracted": 0,
        "items_processed": 0,
        "errors": [],
    }

    # Load the document record.
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        return {
            "status": "failed",
            "document_id": str(document_id),
            "items_extracted": 0,
            "items_processed": 0,
            "errors": [f"Document not found: {document_id}"],
        }

    # Load the pet for species matching.
    pet = db.query(Pet).filter(Pet.id == document.pet_id).first()
    if not pet:
        document.extraction_status = "failed"
        db.commit()
        return {
            "status": "failed",
            "document_id": str(document_id),
            "items_extracted": 0,
            "items_processed": 0,
            "errors": [f"Pet not found for document: {document_id}"],
        }

    try:
        # --- Step 1: Call GPT extraction ---
        # Route to vision API for images, text API for PDFs.
        logger.info(
            "Starting GPT extraction: document_id=%s, pet_id=%s, mime=%s",
            str(document_id),
            str(pet.id),
            document.mime_type,
        )

        if file_bytes and document.mime_type in ("image/jpeg", "image/png"):
            # Images: use GPT vision API with base64-encoded image.
            from app.utils.file_reader import encode_image_base64
            data_uri = encode_image_base64(file_bytes, document.mime_type)
            raw_json = await _call_openai_extraction_vision(data_uri)
        elif file_bytes and document.mime_type == "application/pdf":
            # PDFs: extract text first, then send to GPT.
            from app.utils.file_reader import extract_pdf_text
            pdf_text = extract_pdf_text(file_bytes)
            if pdf_text and len(pdf_text.strip()) > 20:
                raw_json = await _call_openai_extraction(
                    f"Veterinary document text:\n\n{pdf_text}"
                )
            else:
                # Scanned PDF — render pages as images and use GPT vision.
                logger.info(
                    "PDF has no extractable text (scanned), "
                    "falling back to vision API: document_id=%s",
                    str(document_id),
                )
                from app.utils.file_reader import render_pdf_pages_as_images
                page_images = render_pdf_pages_as_images(file_bytes, max_pages=3)
                if page_images:
                    # Send the first page to vision API (most CBC reports are single-page).
                    raw_json = await _call_openai_extraction_vision(page_images[0])
                else:
                    # PyMuPDF not available or rendering failed — mark and skip.
                    logger.warning(
                        "Cannot render scanned PDF pages: document_id=%s",
                        str(document_id),
                    )
                    document.extraction_status = "failed"
                    db.commit()
                    results["status"] = "failed"
                    results["errors"].append(
                        "This PDF appears to be a scanned image and could not be processed. "
                        "Please upload photos of the document instead."
                    )
                    return results
        else:
            # Fallback: use whatever text was passed (for backwards compatibility).
            raw_json = await _call_openai_extraction(document_text)

        # --- Step 2: Validate and normalize ---
        extracted_items, document_name, extracted_pet_name, metadata = _validate_extraction_json(raw_json)
        results["document_type"] = metadata["document_type"]
        results["document_category"] = metadata["document_category"]
        results["diagnostic_summary"] = metadata["diagnostic_summary"]
        results["diagnostic_values"] = metadata.get("diagnostic_values", [])
        results["doctor_name"] = metadata["doctor_name"]
        results["clinic_name"] = metadata["clinic_name"]
        results["vaccination_details"] = metadata["vaccination_details"]
        results["extra_vaccines"] = metadata.get("extra_vaccines", [])

        inferred_category = _infer_document_category(
            document_name=document_name or document.document_name,
            file_path=document.file_path,
            items=extracted_items,
            vaccination_details=metadata.get("vaccination_details", []),
            diagnostic_values=metadata.get("diagnostic_values", []),
        )
        document_category = _resolve_document_category(
            metadata["document_category"],
            inferred_category,
            document_name=document_name or document.document_name,
            file_path=document.file_path,
        )
        results["document_category"] = document_category

        extracted_items = _derive_blood_test_fallback_items(
            extracted_items=extracted_items,
            document_name=document_name or document.document_name,
            file_path=document.file_path,
            document_category=document_category,
            diagnostic_values=metadata.get("diagnostic_values", []),
        )
        results["items_extracted"] = len(extracted_items)

        # Keep original filename; append a date only when exactly one date is present.
        if document.document_name:
            document.document_name = _append_single_extracted_date_to_filename(
                str(document.document_name), extracted_items
            )[:200]
        if document_category:
            document.document_category = document_category

        # Compute event_date: the most recent last_done_date from extracted items.
        # If a document has multiple items with different dates, use the most recent.
        event_dates: list = []
        for item in extracted_items:
            raw_date = item.get("last_done_date")
            if raw_date:
                try:
                    event_dates.append(parse_date(str(raw_date)))
                except ValueError:
                    pass
        if event_dates:
            document.event_date = max(event_dates)

        selected_doctor_name = _select_best_doctor_name(
            metadata_doctor_name=(str(metadata["doctor_name"]).strip() if metadata["doctor_name"] else None),
            extracted_items=extracted_items,
            vaccination_details=metadata.get("vaccination_details", []),
            pet_name=pet.name,
        )
        results["doctor_name"] = selected_doctor_name
        if selected_doctor_name:
            document.doctor_name = selected_doctor_name[:200]
        if metadata["clinic_name"]:
            document.hospital_name = str(metadata["clinic_name"])[:200]

        # Enrich top-level doctor/clinic from item-level values when missing.
        if not results["clinic_name"]:
            for item in extracted_items:
                item_clinic = item.get("clinic_name")
                if item_clinic:
                    results["clinic_name"] = item_clinic
                    document.hospital_name = str(item_clinic)[:200]
                    break

        # Replace previously extracted diagnostic values for this document.
        db.query(DiagnosticTestResult).filter(
            DiagnosticTestResult.document_id == document.id
        ).delete()

        diagnostic_values = metadata.get("diagnostic_values") or []
        for raw in diagnostic_values:
            if not isinstance(raw, dict):
                continue

            test_type = str(raw.get("test_type") or "").strip().lower()
            if test_type not in ("blood", "urine", "fecal", "xray"):
                continue

            parameter_name = str(raw.get("parameter_name") or "").strip()
            if not parameter_name:
                continue

            value_numeric = raw.get("value_numeric")
            if value_numeric is not None:
                try:
                    value_numeric = float(value_numeric)
                except (TypeError, ValueError):
                    value_numeric = None

            value_text = raw.get("value_text")
            if value_numeric is None and (value_text is None or str(value_text).strip() == ""):
                continue

            observed_at = None
            if raw.get("observed_at"):
                try:
                    observed_at = parse_date(str(raw.get("observed_at")))
                except ValueError:
                    observed_at = None

            status_flag = raw.get("status_flag")
            if status_flag is not None:
                status_flag = str(status_flag).strip().lower()
                if status_flag not in ("low", "normal", "high", "abnormal"):
                    status_flag = None

            db.add(DiagnosticTestResult(
                pet_id=pet.id,
                document_id=document.id,
                test_type=test_type,
                parameter_name=parameter_name[:120],
                value_numeric=value_numeric,
                value_text=(str(value_text).strip()[:200] if value_text is not None else None),
                unit=(str(raw.get("unit")).strip()[:60] if raw.get("unit") is not None else None),
                reference_range=(
                    str(raw.get("reference_range")).strip()[:120]
                    if raw.get("reference_range") is not None
                    else None
                ),
                status_flag=status_flag,
                observed_at=observed_at,
            ))

        # --- Store extracted conditions ---
        extracted_conditions = metadata.get("conditions") or []
        extracted_preventive_meds = metadata.get("preventive_medications") or []
        for raw_condition in extracted_conditions:
            if not isinstance(raw_condition, dict):
                continue
            condition_name = str(raw_condition.get("condition_name") or "").strip()
            if not condition_name:
                continue
            # Post-processing safety net: reject names that contain dosage units or
            # pharmaceutical delivery form words — those are medication names, not
            # disease names.  The GPT prompt already instructs GPT not to do this,
            # but this guard catches residual mis-classifications.
            # Note: brand-only names without dosage/form words (e.g. "Simparica",
            # "NexGard") are not caught here — the prompt is the primary defence.
            if _is_likely_medication_name(condition_name):
                logger.warning(
                    "Skipping extracted condition '%s' — name appears to be a medication, "
                    "not a disease/condition. document_id=%s",
                    condition_name,
                    str(document_id),
                )
                continue
            if _condition_matches_extracted_medication_name(
                condition_name,
                raw_condition,
                extracted_preventive_meds,
            ):
                logger.warning(
                    "Skipping extracted condition '%s' — matches extracted medication name. "
                    "document_id=%s",
                    condition_name,
                    str(document_id),
                )
                continue
            try:
                condition_type = str(raw_condition.get("condition_type") or "chronic").strip().lower()
                if condition_type not in ("chronic", "episodic", "resolved"):
                    condition_type = "chronic"

                diagnosed_at = None
                if raw_condition.get("diagnosed_at"):
                    try:
                        diagnosed_at = parse_date(str(raw_condition["diagnosed_at"]))
                    except ValueError:
                        diagnosed_at = None

                # Upsert by (pet_id, name) — update if exists, create if not.
                existing_condition = (
                    db.query(Condition)
                    .filter(Condition.pet_id == pet.id, Condition.name == condition_name)
                    .first()
                )
                if existing_condition:
                    existing_condition.condition_type = condition_type
                    if raw_condition.get("diagnosis"):
                        existing_condition.diagnosis = str(raw_condition["diagnosis"])[:500]
                    if diagnosed_at:
                        existing_condition.diagnosed_at = diagnosed_at
                    existing_condition.document_id = document.id
                    condition_obj = existing_condition
                else:
                    condition_obj = Condition(
                        pet_id=pet.id,
                        document_id=document.id,
                        name=condition_name[:200],
                        diagnosis=(str(raw_condition.get("diagnosis"))[:500] if raw_condition.get("diagnosis") else None),
                        condition_type=condition_type,
                        diagnosed_at=diagnosed_at,
                        source="extraction",
                    )
                    db.add(condition_obj)
                    db.flush()

                # Add medications (deduplicate by condition_id + name).
                raw_meds = raw_condition.get("medications") or []
                for med in raw_meds:
                    if not isinstance(med, dict):
                        continue
                    med_name = str(med.get("name") or "").strip()
                    if not med_name:
                        continue
                    existing_med = (
                        db.query(ConditionMedication)
                        .filter(ConditionMedication.condition_id == condition_obj.id, ConditionMedication.name == med_name)
                        .first()
                    )
                    if not existing_med:
                        db.add(ConditionMedication(
                            condition_id=condition_obj.id,
                            name=med_name[:200],
                            dose=(str(med.get("dose"))[:100] if med.get("dose") else None),
                            frequency=(str(med.get("frequency"))[:100] if med.get("frequency") else None),
                            route=(str(med.get("route"))[:50] if med.get("route") else None),
                        ))

                # Add monitoring checks (deduplicate by condition_id + name).
                raw_monitors = raw_condition.get("monitoring") or []
                for mon in raw_monitors:
                    if not isinstance(mon, dict):
                        continue
                    mon_name = str(mon.get("name") or "").strip()
                    if not mon_name:
                        continue
                    existing_mon = (
                        db.query(ConditionMonitoring)
                        .filter(ConditionMonitoring.condition_id == condition_obj.id, ConditionMonitoring.name == mon_name)
                        .first()
                    )
                    if not existing_mon:
                        db.add(ConditionMonitoring(
                            condition_id=condition_obj.id,
                            name=mon_name[:200],
                            frequency=(str(mon.get("frequency"))[:100] if mon.get("frequency") else None),
                        ))

            except Exception as e:
                db.rollback()
                logger.warning(
                    "Error storing extracted condition '%s': %s. document_id=%s",
                    condition_name, str(e), str(document_id),
                )

        # --- Store extracted contacts (deduplicated) ---
        extracted_contacts = metadata.get("contacts") or []
        # Deduplicate by (name, role) — keep last occurrence (richest data).
        seen_contacts: dict[tuple[str, str], dict] = {}
        for raw_contact in extracted_contacts:
            if not isinstance(raw_contact, dict):
                continue
            c_name = str(raw_contact.get("name") or "").strip()
            if not c_name:
                continue
            c_role = str(raw_contact.get("role") or "veterinarian").strip().lower()
            if c_role not in ("veterinarian", "groomer", "trainer", "specialist", "other"):
                c_role = "veterinarian"
            key = (c_name, c_role)
            # Merge: keep non-None fields from later duplicates.
            if key in seen_contacts:
                prev = seen_contacts[key]
                for field in ("clinic_name", "phone", "email", "address"):
                    if raw_contact.get(field) and not prev.get(field):
                        prev[field] = raw_contact[field]
            else:
                seen_contacts[key] = {**raw_contact, "name": c_name, "role": c_role}

        for (contact_name, role), raw_contact in seen_contacts.items():
            try:
                # Flush first to ensure session is clean before querying.
                db.flush()

                # Upsert by (pet_id, name, role).
                existing_contact = (
                    db.query(Contact)
                    .filter(Contact.pet_id == pet.id, Contact.name == contact_name, Contact.role == role)
                    .first()
                )
                if existing_contact:
                    if raw_contact.get("clinic_name"):
                        existing_contact.clinic_name = str(raw_contact["clinic_name"])[:200]
                    if raw_contact.get("phone"):
                        existing_contact.phone = str(raw_contact["phone"])[:30]
                    if raw_contact.get("email"):
                        existing_contact.email = str(raw_contact["email"])[:200]
                    if raw_contact.get("address"):
                        existing_contact.address = str(raw_contact["address"])[:500]
                    existing_contact.document_id = document.id
                else:
                    db.add(Contact(
                        pet_id=pet.id,
                        document_id=document.id,
                        role=role,
                        name=contact_name[:200],
                        clinic_name=(str(raw_contact.get("clinic_name"))[:200] if raw_contact.get("clinic_name") else None),
                        phone=(str(raw_contact.get("phone"))[:30] if raw_contact.get("phone") else None),
                        email=(str(raw_contact.get("email"))[:200] if raw_contact.get("email") else None),
                        address=(str(raw_contact.get("address"))[:500] if raw_contact.get("address") else None),
                        source="extraction",
                    ))
                    db.flush()
            except Exception as e:
                db.rollback()
                logger.warning(
                    "Error storing extracted contact '%s': %s. document_id=%s",
                    contact_name, str(e), str(document_id),
                )

        # Auto-create contact from document-level doctor_name/clinic_name.
        if selected_doctor_name and _is_plausible_doctor_name(selected_doctor_name, pet_name=pet.name):
            try:
                db.flush()
                existing_doc_contact = (
                    db.query(Contact)
                    .filter(Contact.pet_id == pet.id, Contact.name == selected_doctor_name, Contact.role == "veterinarian")
                    .first()
                )
                if not existing_doc_contact:
                    db.add(Contact(
                        pet_id=pet.id,
                        document_id=document.id,
                        role="veterinarian",
                        name=selected_doctor_name[:200],
                        clinic_name=(str(metadata["clinic_name"])[:200] if metadata["clinic_name"] else None),
                        source="extraction",
                    ))
                    db.flush()
            except Exception as e:
                db.rollback()
                logger.warning(
                    "Error auto-creating contact from doctor_name '%s': %s",
                    selected_doctor_name, str(e),
                )

        # Auto-create contacts from ALL item-level doctor names.
        # A single document (e.g. vaccination card) may mention multiple doctors
        # across different line items — each should be stored as a contact.
        for item in extracted_items:
            item_doctor = item.get("doctor_name")
            item_clinic = item.get("clinic_name")
            if not item_doctor or not isinstance(item_doctor, str):
                continue
            item_doctor = item_doctor.strip()
            if not item_doctor or not _is_plausible_doctor_name(item_doctor, pet_name=pet.name):
                continue
            # Skip if it's the same as the document-level doctor (already handled above)
            if selected_doctor_name and item_doctor.lower() == selected_doctor_name.lower():
                continue
            try:
                db.flush()
                existing_item_contact = (
                    db.query(Contact)
                    .filter(Contact.pet_id == pet.id, Contact.name == item_doctor, Contact.role == "veterinarian")
                    .first()
                )
                if not existing_item_contact:
                    db.add(Contact(
                        pet_id=pet.id,
                        document_id=document.id,
                        role="veterinarian",
                        name=item_doctor[:200],
                        clinic_name=(str(item_clinic)[:200] if item_clinic else
                                     (str(metadata["clinic_name"])[:200] if metadata["clinic_name"] else None)),
                        source="extraction",
                    ))
                    db.flush()
            except Exception as e:
                db.rollback()
                logger.warning(
                    "Error auto-creating contact from item doctor_name '%s': %s",
                    item_doctor, str(e),
                )

        # --- Non-pet document check ---
        # If GPT determined this is not a pet/veterinary document,
        # mark as rejected with a reason so the dashboard can show the user why.
        if metadata["document_type"] == "not_pet_related":
            logger.info(
                "Document classified as not pet-related: document_id=%s — marking rejected.",
                str(document_id),
            )
            document.extraction_status = "rejected"
            document.rejection_reason = (
                "This document does not appear to be a pet or veterinary record. "
                "Please upload vet records, vaccination certificates, lab reports, or prescriptions."
            )
            db.commit()
            results["document_type"] = "not_pet_related"
            results["status"] = "rejected"
            results["errors"].append(document.rejection_reason)
            return results

        # --- Pet name mismatch check ---
        # If GPT extracted a pet name from the document, verify it matches
        # the registered pet name. If not, reject and surface the reason.
        if extracted_pet_name and pet.name:
            if not _pet_name_matches_document_name(extracted_pet_name, pet.name):
                logger.warning(
                    "Pet name mismatch: document says '%s', registered pet is '%s'. "
                    "Flagging document %s — marking rejected.",
                    extracted_pet_name,
                    pet.name,
                    str(document_id),
                )
                reason = (
                    f"This document appears to be for '{extracted_pet_name}', "
                    f"not for {pet.name}. Please upload documents that belong to {pet.name}."
                )
                document.extraction_status = "rejected"
                document.rejection_reason = reason
                db.commit()
                results["document_type"] = "pet_name_mismatch"
                results["status"] = "rejected"
                results["pet_name"] = pet.name
                results["errors"].append(reason)
                return results

        extra_vaccines = results.get("extra_vaccines", [])
        if not extracted_items and not extra_vaccines:
            logger.info(
                "No preventive items extracted from document: %s",
                str(document_id),
            )
            document.extraction_status = "success"
            db.commit()
            return results

        # --- Step 3 & 4: Process each extracted item ---
        # Pre-load all preventive masters for this species once
        # to avoid per-item DB queries (N+1 prevention).
        species_masters = _load_species_masters(db, pet.species)
        species_masters = _filter_non_applicable_puppy_series(
            species_masters,
            include_puppy_series=_should_include_puppy_series_for_pet(pet),
        )

        for item in extracted_items:
            try:
                item_name = item["item_name"]
                last_done_date_str = item["last_done_date"]
                last_done_date = parse_date(last_done_date_str)

                # Match to a preventive_master record using in-memory list.
                # Recurrence days and all config are read from DB — never hardcoded.
                master = _match_preventive_master_from_list(species_masters, item_name)

                if not master:
                    logger.warning(
                        "No preventive_master match for '%s' (species=%s). "
                        "Skipping. document_id=%s",
                        item_name,
                        pet.species,
                        str(document_id),
                    )
                    results["errors"].append(
                        f"No match for item: {item_name}"
                    )
                    continue

                # Check for conflicts before creating/updating record.
                # If a record already exists with a different date,
                # the conflict engine creates a conflict_flag.
                conflict = check_and_create_conflict(
                    db=db,
                    pet_id=pet.id,
                    preventive_master_id=master.id,
                    new_date=last_done_date,
                )

                if conflict:
                    # Conflict detected — do not create a new record.
                    # The conflict must be resolved by the user first.
                    logger.info(
                        "Conflict created for %s: conflict_id=%s, "
                        "document_id=%s",
                        item_name,
                        str(conflict.id),
                        str(document_id),
                    )
                    results["items_processed"] += 1
                else:
                    # No conflict — create or update preventive record.
                    # compute_next_due_date uses master.recurrence_days from DB.
                    create_preventive_record(
                        db=db,
                        pet_id=pet.id,
                        preventive_master_id=master.id,
                        last_done_date=last_done_date,
                    )

                    logger.info(
                        "Preventive record created for %s: pet_id=%s, "
                        "date=%s, document_id=%s",
                        item_name,
                        str(pet.id),
                        str(last_done_date),
                        str(document_id),
                    )
                    results["items_processed"] += 1

            except Exception as e:
                # Individual item failure — rollback broken transaction, log, continue.
                # Without rollback the session stays in InFailedSqlTransaction state
                # and all subsequent operations fail.
                db.rollback()
                logger.error(
                    "Error processing extracted item '%s': %s. "
                    "document_id=%s",
                    item.get("item_name", "unknown"),
                    str(e),
                    str(document_id),
                )
                results["errors"].append(
                    f"Error processing {item.get('item_name', 'unknown')}: {str(e)}"
                )

        # Persist unmapped vaccines as custom preventive records for this pet only.
        if extra_vaccines:
            saved_count, save_errors = _persist_extra_vaccines_for_pet(
                db,
                pet=pet,
                extra_vaccines=extra_vaccines,
            )
            results["extra_vaccines_saved"] = saved_count
            if save_errors:
                results["errors"].extend(save_errors)

        # --- Step 5: Update extraction status ---
        document.extraction_status = "success"
        db.commit()

        logger.info(
            "GPT extraction completed: document_id=%s, "
            "extracted=%d, processed=%d, errors=%d",
            str(document_id),
            results["items_extracted"],
            results["items_processed"],
            len(results["errors"]),
        )

        # Note: Post-extraction WhatsApp nudges are now sent by the daily cron
        # (nudge_scheduler.run_nudge_scheduler) instead of per-upload triggers.

    except Exception as e:
        # Extraction-level failure — mark as failed, do not crash.
        # This catches GPT call failures, JSON parse failures, etc.
        results["status"] = "failed"
        results["errors"].append(f"Extraction failed: {str(e)}")

        logger.error(
            "GPT extraction failed: document_id=%s, error=%s",
            str(document_id),
            str(e),
        )

        # Persist 'failed' status. If commit fails (broken session),
        # rollback and retry with a fresh transaction. Without this,
        # the document stays 'pending' and gets ghost-re-extracted
        # in the next batch for this pet.
        try:
            document.extraction_status = "failed"
            db.commit()
        except Exception:
            try:
                db.rollback()
                document.extraction_status = "failed"
                db.commit()
            except Exception as commit_err:
                logger.error(
                    "CRITICAL: Could not persist failed status for doc %s: %s",
                    str(document_id), str(commit_err),
                )
                try:
                    db.rollback()
                except Exception:
                    pass

    return results
