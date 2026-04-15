"""
PetCircle Phase 1 — Document Extraction Service (Module 7)

Extracts structured preventive health data from uploaded pet documents
using Claude (Anthropic). This service processes documents after upload and
routes extracted data to the preventive engine (conflict detection
or record creation).

Extraction pipeline:
    Document (pending) → Claude extraction → Validate JSON → Normalize dates
        → Pass to conflict engine or create preventive record
        → Update extraction_status

Model configuration (all from constants — never hardcoded):
    - Model: OPENAI_EXTRACTION_MODEL (claude-opus-4-6)
    - Temperature: OPENAI_EXTRACTION_TEMPERATURE (0)
    - Max tokens: OPENAI_EXTRACTION_MAX_TOKENS (6144)
    - Response format: JSON only (tool_use)

Retry policy:
    - Uses retry_openai_call() from utils/retry.py.
    - 3 attempts total (1s, 2s backoff) — configured in constants.
    - On final failure: extraction_status='failed', log error, continue.

Rules:
    - No medical advice in extraction.
    - All dates normalized to YYYY-MM-DD.
    - JSON keys strictly validated.
    - Extraction failures never crash the application.
    - Anthropic API key from environment (settings.ANTHROPIC_API_KEY) — never hardcoded.
"""

import json
import logging
import os
import re
from contextlib import nullcontext
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import (
    DOCUMENT_CATEGORIES,
    EXTRACTION_LOW_CONFIDENCE_THRESHOLD,
    EXTRACTION_MAX_AUTO_RETRIES,
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
from app.models.weight_history import WeightHistory
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

# Maps medication names to compatible preventive categories.
# Dynamically loaded from product_medicines table on module initialization.
# Format: {medicine_name_normalized: frozenset({"flea_tick", "deworming", ...})}
_MEDICATION_TO_PREVENTIVE_CATEGORIES: dict[str, frozenset[str]] = {}
_KNOWN_MEDICATION_BRANDS: set[str] = set()

# Flag to track if mapping has been initialized
_MEDICINE_MAPPING_INITIALIZED = False


def _initialize_medicine_mapping(db=None) -> None:
    """
    Build medicine-to-categories mapping from product_medicines table.
    Called lazily on first use or explicitly with a DB session.
    """
    global _MEDICATION_TO_PREVENTIVE_CATEGORIES, _KNOWN_MEDICATION_BRANDS, _MEDICINE_MAPPING_INITIALIZED

    if _MEDICINE_MAPPING_INITIALIZED and _MEDICATION_TO_PREVENTIVE_CATEGORIES:
        return

    # If no DB session provided, try to use default session
    _db_created_here = False
    if db is None:
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            _db_created_here = True
        except Exception:
            # If we can't get a DB session, use minimal fallback mapping
            _MEDICATION_TO_PREVENTIVE_CATEGORIES = {
                "simparica": frozenset({"flea_tick", "deworming"}),
                "nexgard spectra": frozenset({"flea_tick", "deworming"}),
                "advocate": frozenset({"flea_tick", "deworming"}),
                "drontal": frozenset({"deworming"}),
                "nexgard": frozenset({"flea_tick"}),
                "bravecto": frozenset({"flea_tick"}),
                "frontline": frozenset({"flea_tick"}),
            }
            _KNOWN_MEDICATION_BRANDS = set(_MEDICATION_TO_PREVENTIVE_CATEGORIES.keys())
            _MEDICINE_MAPPING_INITIALIZED = True
            return

    try:
        from app.models.product_medicines import ProductMedicines

        medicines = db.query(ProductMedicines).filter(
            ProductMedicines.active == True
        ).all()

        mapping = {}
        for med in medicines:
            categories = set()

            # Parse type field to determine categories
            type_lower = med.type.lower()
            if "deworming" in type_lower:
                categories.add("deworming")
            if "flea" in type_lower or "tick" in type_lower:
                categories.add("flea_tick")

            if not categories:
                continue

            # Normalize product name for matching
            normalized_name = med.product_name.strip().lower()
            # Remove weight ranges like "2–3.5 kg"
            normalized_name = re.sub(r"\s*\d+[–-]?\d*\.?\d*\s*(kg|ml|g|tablets?|pipette|chew|caps?)\s*", "", normalized_name, flags=re.IGNORECASE)
            normalized_name = normalized_name.strip()

            if normalized_name:
                mapping[normalized_name] = frozenset(categories)

            # Also try shorter name (first word or brand)
            words = normalized_name.split()
            if words:
                mapping[words[0]] = frozenset(categories)

        _MEDICATION_TO_PREVENTIVE_CATEGORIES = mapping
        _KNOWN_MEDICATION_BRANDS = set(mapping.keys())
        _MEDICINE_MAPPING_INITIALIZED = True

    except Exception as e:
        # If mapping fails, use minimal fallback
        logger.warning("Failed to initialize medicine mapping from product_medicines: %s", str(e))
        _MEDICATION_TO_PREVENTIVE_CATEGORIES = {
            "simparica": frozenset({"flea_tick", "deworming"}),
            "nexgard spectra": frozenset({"flea_tick", "deworming"}),
            "drontal": frozenset({"deworming"}),
            "nexgard": frozenset({"flea_tick"}),
            "bravecto": frozenset({"flea_tick"}),
        }
        _KNOWN_MEDICATION_BRANDS = set(_MEDICATION_TO_PREVENTIVE_CATEGORIES.keys())
        _MEDICINE_MAPPING_INITIALIZED = True
    finally:
        # Only close the session if we created it internally
        if _db_created_here:
            try:
                db.close()
            except Exception:
                pass


def _build_medicine_coverage_prompt() -> str:
    """Build a MEDICINE COVERAGE GUIDE prompt snippet from product_medicines table.

    Dynamically sources from _MEDICATION_TO_PREVENTIVE_CATEGORIES which is
    populated from the product_medicines table. Automatically includes all active
    medicines in the database.
    """
    # Ensure mapping is initialized
    if not _MEDICINE_MAPPING_INITIALIZED:
        _initialize_medicine_mapping()

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
        f"  BOTH deworming + flea_tick: {', '.join(sorted(set(both)))}",
        f"  flea_tick only: {', '.join(sorted(set(flea_only)))}",
        f"  deworming only: {', '.join(sorted(set(deworm_only)))}",
        "  For any medicine NOT in this list, use your medical knowledge to determine the correct targets.",
    ]
    return "\n".join(lines)


def _get_preventive_categories_for_medicine(medication_name: str | None, db=None) -> set[str]:
    """Return compatible preventive categories for a medicine brand mention.

    Queries product_medicines table via dynamic mapping for accurate categorization.
    Performs normalized containment checks so values like "NexGard Spectra chew"
    still resolve to configured compatibility categories.

    Falls back to "Other" option for unmapped medicines (user custom entry).
    """
    if not isinstance(medication_name, str):
        return set()

    normalized = medication_name.strip().lower()
    if not normalized:
        return set()

    # Ensure mapping is initialized
    if not _MEDICINE_MAPPING_INITIALIZED:
        _initialize_medicine_mapping(db)

    categories: set[str] = set()
    for brand, mapped in _MEDICATION_TO_PREVENTIVE_CATEGORIES.items():
        if brand in normalized:
            categories.update(mapped)

    return categories


def _is_likely_medication_name(name: str) -> bool:
    """Return True if *name* looks like a drug/product rather than a diagnosed condition.

    Checks both explicit dosage/form signals (e.g. "50mg", "Capsule") and known
    preventive medication brand names from product_medicines table
    (e.g. "Simparica", "NexGard").
    This prevents GPT mis-classifications from being stored as Condition records.
    """
    if _RE_MEDICATION_SIGNAL.search(name):
        return True
    # Ensure mapping is initialized
    if not _MEDICINE_MAPPING_INITIALIZED:
        _initialize_medicine_mapping()
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
    """Recover minimal extraction metadata from malformed GPT JSON.

    Returns None immediately for empty/whitespace responses — these come from
    transient GPT failures and contain nothing recoverable.
    """
    if not raw_json or not raw_json.strip():
        return None

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
    # "Preventive Blood Test" item alone does NOT imply the document is a blood report —
    # prescriptions ordering blood tests also produce this item. Only infer "Blood Report"
    # when actual diagnostic_values (lab results with reference ranges) are also present.
    if "preventive blood test" in item_names and diagnostic_values:
        return "Blood Report"
    if any(item_name in item_names for item_name in ("annual checkup", "dental check", "deworming", "tick/flea")):
        return "Prescription"

    return "Other"


def _resolve_document_category(
    raw_category: str | None,
    inferred_category: str,
    document_name: str | None = None,
    file_path: str | None = None,
    clinical_exam: dict | None = None,
    conditions: list[dict] | None = None,
    doctor_name: str | None = None,
    clinic_name: str | None = None,
    diagnostic_values: list[dict] | None = None,
) -> str:
    """Prefer inferred category when GPT returned blank, Other, or a coarse legacy value.

    Rules (in priority order):
    0. If GPT explicitly returned "Prescription", trust it unless it contradicts
       a VERY strong lab-report signal (like "urine culture" in the name, which
       is a diagnostic test, not a prescription). This protects prescriptions
       that mention blood/lab tests from being misclassified.
    1. Structural prescription signals (clinical_exam populated, or any condition
       extracted) force "Prescription" — these are prescription-only per the
       extraction prompt and beat any GPT category, including "Blood Report"
       (which GPT may return when a prescription lists in-clinic test values).
    2. If filename/document name has a strong keyword that contradicts GPT → use keyword signal.
    3. Vet-origin signal: doctor_name/clinic_name present AND GPT returned None/"Other",
       or GPT returned "Blood Report" but no actual diagnostic_values were extracted
       (ordering tests ≠ reporting results) → "Prescription".
    4. If raw is None / "Other" and inferred is specific → use inferred.
    5. Otherwise trust GPT's (normalized) raw_category.

    This keeps the 5 specific categories (Blood Report, Urine Report, Imaging,
    Prescription, PCR & Parasite Panel) authoritative over GPT's legacy "Diagnostic".
    """
    combined = f"{(document_name or '').lower()} {os.path.basename(file_path or '').lower()}"
    # Normalize underscore/hyphen variants so "blood_report" matches "blood report",
    # "x-ray" matches "x ray", "usg_film" keeps "usg" as a whole word, etc.
    combined_norm = re.sub(r"[_\-]", " ", combined)
    # Filename-only normalised string for word-boundary checks (standalone "blood").
    filename_norm = re.sub(r"[_\-]", " ", os.path.basename(file_path or "").lower())

    # Rule 0: If GPT explicitly said "Prescription", protect it from most overrides.
    # Only allow DIAGNOSTIC TESTS (not "blood" which could be an ordered test) to override.
    if raw_category == "Prescription":
        # Urine culture / urinalysis are diagnostic TEST RESULTS, not prescription orders.
        # These override prescription classification.
        if any(kw in combined_norm for kw in ("urine culture", "urinalysis", "urine test", "urine report")):
            return "Urine Report"
        # Otherwise keep the explicit "Prescription" classification from GPT.
        return "Prescription"

    # Lab-report keyword signals take precedence over structural prescription
    # heuristics.  A urine culture that extracts conditions (e.g. E. coli) must
    # still be classified as "Urine Report", not "Prescription".
    if any(kw in combined_norm for kw in ("urine culture", "urinalysis", "urine test", "urine report")):
        return "Urine Report"
    if any(kw in combined_norm for kw in ("blood report", "blood test", "cbc report", "hemogram report",
                                           "haematology report", "hematology report")):
        return "Blood Report"
    # Standalone "blood" word in filename (e.g. "Blood_12_02_25_3.pdf") is a strong
    # Blood Report signal even when the word "report" does not follow it.  Must be
    # checked BEFORE the lab-report guard so a mislabelled GPT category (e.g.
    # "PCR & Parasite Panel" triggered by anaplasma/ehrlichia in the blood panel)
    # cannot survive past a clear blood-filename signal.
    if re.search(r'\bblood\b', filename_norm):
        return "Blood Report"
    if any(kw in combined_norm for kw in ("pcr", "parasite panel", "parasite screen")):
        return "PCR & Parasite Panel"

    # Filename "Prescription" / Imaging keywords override GPT and must come
    # before the lab-report results guard so a wrong GPT category cannot survive
    # past a clear filename signal (e.g. "usg_report.pdf", "x-ray_film.pdf").
    if "prescription" in combined_norm or " rx " in combined_norm:
        return "Prescription"
    if any(kw in combined_norm for kw in ("ultrasound", "usg", "x ray", "xray", "radiograph")):
        return "Imaging"

    # clinical_exam is populated ONLY on prescriptions/vet-visit records — blood/urine
    # reports NEVER contain clinical examination values (weight, temp, pulse, etc.).
    # This check must come BEFORE the lab-report results guard so a prescription that
    # orders blood tests (and may have some diagnostic_values set by GPT) is still
    # correctly classified as "Prescription".
    if isinstance(clinical_exam, dict) and any(
        value not in (None, "", [], {}) for value in clinical_exam.values()
    ):
        return "Prescription"

    # Lab-report results guard: if the document has actual diagnostic test results
    # (parameter values + reference ranges) and GPT already returned a known lab
    # report category, trust that classification.  Conditions extracted from an
    # "impression" or diagnosis line at the bottom of a blood/urine report must
    # NOT force the document to "Prescription".
    _LAB_REPORT_CATEGORIES = {"Blood Report", "Urine Report", "Imaging", "PCR & Parasite Panel"}
    if diagnostic_values and raw_category in _LAB_REPORT_CATEGORIES:
        return raw_category

    # Remaining structural signals — any extracted condition means a vet diagnosed
    # + prescribed something.
    if conditions and any(isinstance(c, dict) for c in conditions):
        return "Prescription"

    # Vet-origin signal: if a doctor or clinic name is identified, the document came from a
    # vet's office. Use this to rescue two failure modes:
    #   a) GPT returned None/"Other" — almost always a vet visit record.
    #   b) GPT returned "Blood Report" but extracted zero diagnostic_values — the document
    #      is ORDERING tests (e.g. "Get CBC done"), not REPORTING results. Actual lab reports
    #      always produce diagnostic_values rows (parameter values + reference ranges).
    has_vet_origin = bool(doctor_name or clinic_name)
    has_actual_results = bool(diagnostic_values)
    if has_vet_origin:
        if raw_category in (None, "Other"):
            return "Prescription"
        if raw_category == "Blood Report" and not has_actual_results:
            return "Prescription"

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


# Document categories from which vet contacts may be created.
# Lab/diagnostic reports (Blood Report, Urine Report, Imaging, PCR & Parasite Panel)
# mention a requesting/signing doctor but that name is not a reliable vet contact.
_CLINICAL_CONTACT_CATEGORIES: frozenset[str] = frozenset({"Vaccination", "Prescription"})


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
      - If exactly one valid unique `last_done_date` exists, append it to the filename in MonYY format (e.g., "Sep25").
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

    only_date_iso = next(iter(unique_dates))

    # Convert to MonYY format (e.g., "Sep25" for September 2025)
    date_obj = datetime.strptime(only_date_iso, "%Y-%m-%d")
    date_suffix = date_obj.strftime("%b%y")  # e.g., "Sep25"

    if date_suffix.lower() in original_filename.lower():
        return original_filename

    # Append date before extension when present.
    dot = original_filename.rfind(".")
    if dot > 0:
        return f"{original_filename[:dot]}_{date_suffix}{original_filename[dot:]}"
    return f"{original_filename}_{date_suffix}"


def _build_prescription_document_name(event_date) -> str:
    """Build the canonical display name for vet prescription documents.

    Format: VetPrescription_MONYY (e.g. VetPrescription_Mar26).
    If no event_date is available, returns plain "VetPrescription".
    """
    if event_date:
        return f"VetPrescription_{event_date.strftime('%b%y')}"
    return "VetPrescription"


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
    "You are a veterinary document data extractor.\n"
    "Analyze the provided document and return a JSON object with these keys:\n"
    '  - "document_name": string (a short descriptive name for this document, '
    "e.g., 'Blood Test Report', 'Vaccination Certificate', 'Deworming Record', "
    "'Vet Prescription', 'Health Checkup Report')\n"
    '  - "document_type": "pet_medical" or "not_pet_related" '
    "(set to 'not_pet_related' if the document is clearly NOT a pet/veterinary document, "
    "e.g., a human medical report, invoice, random photo, etc.)\n"
    '  - "document_category": one of "Blood Report", "Urine Report", "Imaging", '
    '"Prescription", "PCR & Parasite Panel", "Vaccination", "Other" --- '
    "pick the most specific match: "
    "Blood Report for CBC/biochemistry/haematology/blood test reports (even when tick-borne "
    "disease markers such as Anaplasma, Ehrlichia, or Babesia are included as add-on parameters — "
    "those are still Blood Reports, NOT PCR & Parasite Panel), "
    "Urine Report for urinalysis/urine culture/urine sensitivity reports, "
    "Imaging for ultrasound/USG/X-ray/radiology/film reports (set this even when a clinical "
    "impression or diagnosis is written at the end of the imaging report), "
    "Prescription for vet prescriptions/medication records, "
    "PCR & Parasite Panel ONLY for documents whose PRIMARY purpose is tick-borne disease or "
    "parasite PCR screening (e.g. SNAP 4Dx, Vector-Borne Disease Panel, standalone parasite "
    "panel) — a standard blood panel that also tests for tick-borne markers is NOT PCR & "
    "Parasite Panel, it is Blood Report, "
    "Vaccination for vaccine certificates/immunisation records, "
    "Other for anything else\n"
    '  - "diagnostic_summary": string or null (for Diagnostic documents only --- '
    "provide a 1-2 sentence plain-language summary of key findings; null otherwise)\n"
    '  - "diagnostic_values": array (for Diagnostic reports), each with:\n'
    '    - "test_type": "blood" | "urine" | "fecal" | "xray" | "ultrasound"\n'
    '    - "parameter_name": string (e.g., Hemoglobin, WBC, Creatinine, Urine pH; '
    "for xray: anatomical region like 'Hip Joint'; "
    "for ultrasound: organ or region like 'Liver', 'Spleen', 'Left Kidney'; "
    "for fecal: parasite name like 'Roundworm')\n"
    '    - "value_numeric": number or null\n'
    '    - "value_text": string or null (use when numeric is not available; '
    "for xray: the finding description; for fecal: result text)\n"
    '    - "unit": string or null\n'
    '    - "reference_range": string or null\n'
    '    - "status_flag": "low" | "normal" | "high" | "abnormal" | null\n'
    '    - "observed_at": date string (same accepted formats) or null\n'
    '  - "conditions": array of objects (diagnosed diseases/conditions found in the document; [] if none), each with:\n'
    '    - "condition_name": string --- the NAME of a diagnosed DISEASE, DISORDER, or SYNDROME only '
    '(e.g. "Hip Dysplasia", "Diabetes Mellitus", "Otitis Externa", "Skin Allergy"). '
    'NEVER use a medication, drug, supplement, or vaccine brand as condition_name '
    '(e.g. do NOT write "Simparica", "Doxycycline", "NexGard", "Omega-3" as a condition_name).\n'
    '    - "condition_type": "chronic" | "acute" | "episodic" | "recurrent"\n'
    '      NOTE: "acute" and "episodic" are interchangeable --- use whichever term appears in the document.\n'
    '      If neither term appears explicitly, default to "acute" for single or short-term conditions.\n'
    '      "resolved" is NOT a valid condition_type --- it belongs in condition_status only.\n'
    '    - "condition_status": "active" | "resolved" | null\n'
    '      Set to "resolved" if the document explicitly states the condition is resolved, cured, or no longer active.\n'
    '      Set to "active" if the condition is described as ongoing or being treated. Set to null if not stated.\n'
    '    - "diagnosis": string or null (brief diagnosis description)\n'
    '    - "diagnosed_at": date string or null\n'
    '    - "episode_dates": array of date strings --- ALL dates on which this condition was recorded, treated,\n'
    '      or mentioned in this document. Always include diagnosed_at here if known. Add any additional\n'
    '      encounter or treatment dates found in the document for this condition. [] if none found.\n'
    '    - "medications": array of objects ([] if none) --- drugs/products prescribed TO TREAT this condition, each with:\n'
    '      - "name": string (medication/drug name)\n'
    '      - "item_type": "medicine" | "supplement" --- classify as "medicine" if it is a pharmaceutical drug used to treat a condition (e.g., antibiotics, antifungals, steroids, antihistamines); classify as "supplement" if it is nutritional or supportive (e.g., omega-3, coat supplements, probiotics, vitamins, joint supplements). Use product knowledge if needed (e.g., Fur+, Nutricoat Advance+ → supplement).\n'
    '      - "dose": string or null\n'
    '      - "frequency": string or null (e.g., "Once daily", "Twice daily")\n'
    '      - "route": string or null (e.g., "oral", "topical", "injection")\n'
    '      - "end_date": string or null --- the last date of the treatment course as explicitly stated in the\n'
    '        document (e.g., "give for 5 days" computed from a start date, or a specific stop date written on\n'
    '        the prescription). Only populate if derivable from the document itself. Do NOT infer from clinical norms.\n'
    '    - "monitoring": array of objects ([] if none), each with:\n'
    '      - "name": string (e.g., "Blood Work", "Follow-up Vet Visit")\n'
    '      - "frequency": string or null (e.g., "Every 6 months", "Yearly")\n'
    '      - "recheck_due_date": string or null --- a specific follow-up or recheck date as explicitly stated\n'
    '        in the document (e.g., "follow up after 15 days", "repeat test after 3 months", "next due: Jan 2025").\n'
    '        Compute only if a relative interval AND a reference date are both present in the document.\n'
    '        Do NOT use external clinical guidelines or assumptions to infer this date.\n'
    '  - "standalone_medications": array of objects ([] if none) --- medications explicitly prescribed in the\n'
    '    document that are NOT linked to any named diagnosis or condition. Captures drugs written on a\n'
    '    prescription whose clinical indication is not stated, enabling future linkage when more context is available.\n'
    '    Each with:\n'
    '    - "name": string (medication/drug name as written)\n'
    '    - "item_type": "medicine" | "supplement" --- classify as "medicine" if it is a pharmaceutical drug used to treat a condition (e.g., antibiotics, antifungals, steroids, antihistamines); classify as "supplement" if it is nutritional or supportive (e.g., omega-3, coat supplements, probiotics, vitamins, joint supplements). Use product knowledge if needed (e.g., Fur+, Nutricoat Advance+ → supplement).\n'
    '    - "dose": string or null\n'
    '    - "frequency": string or null\n'
    '    - "route": string or null\n'
    '    - "end_date": string or null (same derivation rule as conditions[].medications[].end_date)\n'
    '    - "notes": string or null (any additional context written near the medication, e.g., duration phrase)\n'
    '  - "recommendations": array of objects ([] if none) --- non-medication clinical guidance written by the\n'
    '    vet as part of the treatment or management plan. Captures diet instructions, activity restrictions,\n'
    '    rest advice, feeding plans, and similar directives that are not drugs or supplements.\n'
    '    Each with:\n'
    '    - "type": "diet" | "activity" | "rest" | "follow_up" | "other"\n'
    '    - "description": string (exact or close paraphrase of what is written)\n'
    '    - "linked_condition": string or null (condition_name this recommendation relates to, if inferable from document)\n'
    '    - "duration": string or null (e.g., "until recheck", "7 days", if stated)\n'
    '    - "notes": string or null\n'
    '  - "preventive_medications": array of objects ([] if none) --- preventive medicines used for '
    "deworming and/or flea/tick control even when no diagnosis is present, each with:\n"
    '    - "name": string (medicine/product name as written)\n'
    '    - "item_type": "medicine" | "supplement" --- classify as "medicine" if it is a pharmaceutical drug (e.g., antiparasitic, antihelmintic medications); classify as "supplement" if it is nutritional or supportive. Use product knowledge if needed.\n'
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
    '  - "clinical_exam": object or null --- ONLY for Prescriptions / vet visit records. '
    "Capture any clinical examination values written on the document:\n"
    '    - "weight_kg": number or null\n'
    '    - "temperature_c": number or null (if degF, convert to degC)\n'
    '    - "pulse_bpm": number or null\n'
    '    - "respiration_rpm": number or null\n'
    '    - "mucous_membranes": string or null\n'
    '    - "clinical_findings": string or null\n'
    '    - "in_clinic_test_values": array --- in-clinic test values (blood glucose, PCV, SpO2, etc.)\n'
    '      Each entry: {"parameter_name": string, "value_numeric": number|null, '
    '"value_text": string|null, "unit": string|null}\n'
    '  - "items": array of objects, each with:\n'
    '    - "item_name": string (MUST be one of the tracked items listed below)\n'
    '    - "last_done_date": string (ALWAYS use 4-digit years; null if unclear)\n'
    '    - "dose": string or null\n'
    '    - "doctor_name": string or null\n'
    '    - "clinic_name": string or null\n'
    '    - "batch_number": string or null\n\n'
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
    "- A blood test report counts as 'Preventive Blood Test' --- use the report date.\n"
    "- Do NOT provide medical advice or interpretation.\n"
    "- Do NOT infer dates --- only extract what is explicitly stated in the document.\n"
    "- DATE EXTRACTION IS CRITICAL: Scan every part of the document — headers, stamps, "
    "footers, date fields, signature areas, and printed/handwritten text — for explicit dates. "
    "Indian documents commonly use DD/MM/YYYY, DD/MM/YY, DD-MM-YYYY, DD-MM-YY, or "
    "'DD Month YYYY' formats. Extract ALL dates found and assign them correctly to the "
    "relevant fields (last_done_date, observed_at, diagnosed_at, etc.). Never leave a date "
    "field null if a date is visibly present anywhere on the document.\n"
    "- PRESCRIPTION IDENTIFICATION: Set document_category to 'Prescription' whenever the "
    "document is a vet-written record. Prescriptions always classify as 'Prescription' even "
    "when they also contain blood tests to be done, general clinical information, or vaccine "
    "advice. The following are ALL prescriptions:\n"
    "  (a) ORDERED BLOOD/LAB TESTS: A prescription that says 'CBC advised', 'Do KFT/LFT', "
    "'Blood collected - results awaited', 'Advised: CBC, UT, KFT, Blood electrolytes' is a "
    "Prescription ordering tests — NOT a Blood Report. Do NOT populate diagnostic_values[] "
    "for test names that are ordered but not yet resulted. Leave diagnostic_values: []. The "
    "order itself may go in recommendations[] with type 'other' and the test name as "
    "description. A Blood Report ONLY has actual numeric result values with reference ranges.\n"
    "  (b) GENERAL CLINICAL INFORMATION: A prescription that contains clinical findings "
    "(lump at elbow, LN swollen, multiple lipomas, owner complaint, history), examination "
    "notes, or treatment advice alongside medications is ALWAYS a Prescription — even if no "
    "formal Rx symbol is present. Extract clinical findings into clinical_exam.clinical_findings.\n"
    "  (c) VACCINE ADVICE ON A PRESCRIPTION: If a vet prescription mentions 'vaccinate for "
    "Rabies', 'Core vaccine due', or lists a vaccine as part of a treatment/preventive plan, "
    "the document_category stays 'Prescription'. Extract the vaccine into items[] with the "
    "appropriate item_name. Only set document_category to 'Vaccination' for a standalone "
    "vaccine certificate or vaccination card with no prescription content.\n"
    "  (d) HANDWRITTEN MEDICATION LIST: A handwritten page listing drug names with doses and "
    "frequencies is ALWAYS a Prescription. Place medications in standalone_medications[] if "
    "no condition is named, or in conditions[].medications[] if a diagnosis is written.\n"
    "  In-clinic test values actually measured during the visit (blood glucose, PCV, SpO2, "
    "quick BUN) belong in clinical_exam.in_clinic_test_values — never in diagnostic_values[].\n"
    "- Extract the pet's name EXACTLY as written in the document (if present).\n"
    "- For vaccination records, extract all available vaccine details without guessing.\n"
    "- For dog vaccination cards, include each administered vaccine row in items when a done date is present.\n"
    "- NEVER use vaccine sticker metadata dates (manufacturing/expiry/lot label dates) as last_done_date.\n"
    "- In vaccination documents, do not add Annual Checkup unless a separate checkup event is documented.\n"
    "- Capture next_due_date for each vaccine row whenever visible.\n"
    "- For X-ray reports: test_type 'xray', anatomical region as parameter_name, finding as value_text.\n"
    "- For ultrasound/USG reports: test_type 'ultrasound', organ or anatomical region as parameter_name "
    "(e.g. 'Liver', 'Spleen', 'Left Kidney', 'Urinary Bladder'), finding description as value_text. "
    "Always set document_category to 'Imaging' for USG/ultrasound documents.\n"
    "- For fecal reports: test_type 'fecal', parasite name as parameter_name, result as value_text.\n"
    "- Blood Report vs PCR & Parasite Panel: A standard haematology/biochemistry panel is ALWAYS "
    "'Blood Report' even when tick-borne disease markers (Anaplasma, Ehrlichia, Babesia, Hepatozoon, "
    "Leishmania) are included as additional parameters. Use 'PCR & Parasite Panel' ONLY when the "
    "document's sole or primary purpose is tick-borne disease PCR / parasite screening "
    "(e.g. SNAP 4Dx, Vector-Borne Disease Panel) with no standard CBC or biochemistry parameters.\n"
    "- Imaging (X-ray, USG, ultrasound, radiology): Always set document_category to 'Imaging'. "
    "Extract findings into diagnostic_values using appropriate test_type ('xray' or 'ultrasound'). "
    "A clinical impression or diagnosis written at the end of an imaging report does NOT change "
    "the category to 'Prescription' — it remains 'Imaging'.\n"
    "- For conditions: extract diagnosed diseases/disorders/syndromes with their medications and monitoring.\n"
    "- condition_name must be the DISEASE/DISORDER name only --- never a drug, supplement, or vaccine brand.\n"
    "- \"acute\" and \"episodic\" are interchangeable labels for condition_type. Use the term from the document; "
    "default to \"acute\" if neither is written and the condition is short-term or single-episode.\n"
    "- \"resolved\" is NOT a valid condition_type value. If the document states a condition is resolved, "
    "set condition_type to whatever clinical type applies (chronic/acute/episodic/recurrent) AND set "
    "condition_status to \"resolved\".\n"
    "- episode_dates must capture every date the condition is mentioned, treated, or encountered in this "
    "document. This enables downstream recurrence analysis across multiple documents.\n"
    "- medications[].end_date must be extracted only from explicit document text (e.g., \"for 7 days\" from "
    "a known start date, or a written stop date). Never infer from drug type or standard protocols.\n"
    "- monitoring[].recheck_due_date must be extracted only from explicit document text (e.g., \"follow up "
    "in 2 weeks\", \"repeat CBC after 3 months\"). Compute only when both interval and reference date are "
    "present in the document. Never apply external clinical guidelines.\n"
    "- standalone_medications[] must be used for any medication written on a prescription that cannot be "
    "linked to a named condition in the document. Do NOT invent a condition_name to house it. "
    "Do NOT place it in preventive_medications[] unless it clearly targets deworming or flea/tick.\n"
    "- recommendations[] must capture all non-medication clinical directives written by the vet: diet "
    "instructions, feeding plans, activity restrictions, rest advice, etc. Populate description with "
    "what is written; do not paraphrase into clinical language. [] if none.\n"
    "- If a document lists preventive medicines without a diagnosis, keep conditions: [] and populate preventive_medications[].\n"
    "- For each preventive_medications entry, always set prevention_targets explicitly (deworming, flea_tick, or both).\n"
    "- If the medicine coverage text indicates both internal parasites (worms/deworming) and external parasite control (flea/tick), include BOTH targets.\n"
    f"{_build_medicine_coverage_prompt()}\n"
    "- Drugs prescribed to treat a condition belong in that condition's medications[] array, not standalone_medications[].\n"
    "- Prescribed non-preventive medications (antibiotics, analgesics, antacids, etc.) must NEVER go into "
    "preventive_medications[]. They belong in conditions[].medications[] or standalone_medications[].\n"
    "- MEDICATION/SUPPLEMENT CLASSIFICATION: Every prescribed medication must be classified as either \"medicine\" or \"supplement\" using the item_type field:\n"
    "    * \"medicine\" → pharmaceutical drugs used to treat a condition (e.g., antibiotics, antifungals, steroids, antihistamines, antiparasitic medications, antihelmintic drugs, antipyretics, analgesics, antacids, etc.)\n"
    "    * \"supplement\" → nutritional or supportive products (e.g., omega-3, coat supplements, probiotics, vitamins, joint supplements, bone supplements, calcium supplements, etc.). Use product knowledge if needed (e.g., Fur+, Nutricoat Advance+ → supplement).\n"
    "  Always apply this classification to medications[] in conditions, standalone_medications[], and preventive_medications[].\n"
    "- For contacts: extract vet/specialist contact details when explicitly present.\n"
    "- Document category for vet-written documents: If the document is on a veterinary clinic's "
    "letterhead, has a doctor signature/stamp, contains Rx or Tr. markings, records clinical "
    "examination values (weight/temperature/pulse), prescribes medications, OR orders tests for "
    "the pet to undergo (e.g. 'Get CBC done', 'Blood Test - LFT, KFT'), ALWAYS set "
    "document_category to 'Prescription' --- "
    "even if the only content is a list of ordered tests and no diagnosis is written. "
    "A document that only lists test RESULTS from a diagnostic lab (with reference ranges and status flags) "
    "is a 'Blood Report'/'Urine Report'/etc., NOT a Prescription. The distinguishing signal is: "
    "ordered tests -> Prescription; reported test results -> Lab report.\n"
    "- Handwritten medication lists are Prescriptions: A handwritten page listing drug names with "
    "doses and frequencies (e.g., 'Tab Pan 40mg BID', 'Tab Toxomox 500mg AIT', 'Tab Gabapentin "
    "600mg') is ALWAYS a Prescription even if no clinic letterhead or formal diagnosis is visible. "
    "Set document_category to 'Prescription'. Place these medications inside a conditions[] entry "
    "using a descriptive condition_name such as 'Treatment course' or 'Post-operative care' if a "
    "broad grouping is inferable --- otherwise place them in standalone_medications[]. "
    "Never leave prescribed medications unclassified.\n"
    "- For Prescription documents: ALWAYS populate clinical_exam with weight, temperature, pulse, "
    "respiration, mucous membranes, and any other examination notes written on the document. "
    "Leave individual fields as null when not present. Omit clinical_exam for non-prescription documents.\n"
    "- Any in-clinic test values written on a prescription (blood glucose, PCV, SpO2) should be "
    "listed in clinical_exam.in_clinic_test_values --- do NOT duplicate them into diagnostic_values.\n"
    "- If any field is missing, use null for that field.\n"
    "- If not pet/veterinary related, set document_type to 'not_pet_related' and items to [].\n"
    '- If no preventive items found, return {"document_name": "...", "document_type": "pet_medical", '
    '"document_category": "...", "diagnostic_summary": null, "pet_name": null, "items": [], '
    '"conditions": [], "standalone_medications": [], "recommendations": [], '
    '"preventive_medications": [], "contacts": []}\n'
    "- Return valid JSON only --- no markdown, no explanation, no extra text."
)

# ---------------------------------------------------------------------------
# Extraction tool schema — forces the Anthropic API to return schema-valid
# structured output via tool_use, eliminating all JSON parse failures.
# The model is invoked with tool_choice={"type":"tool","name":"extract_pet_health_data"}
# so it MUST call this tool and cannot emit free-text.
# ---------------------------------------------------------------------------
EXTRACTION_TOOL_SCHEMA: dict = {
    "name": "extract_pet_health_data",
    "description": (
        "Extract structured veterinary health data from the provided document. "
        "Return all fields specified in the schema. Use null for any field not present in the document."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "document_name": {"type": "string", "description": "Short descriptive name for this document."},
            "document_type": {"type": "string", "enum": ["pet_medical", "not_pet_related"]},
            "document_category": {
                "type": "string",
                "enum": ["Blood Report", "Urine Report", "Imaging", "Prescription",
                         "PCR & Parasite Panel", "Vaccination", "Other"],
            },
            "pet_name": {"type": ["string", "null"]},
            "doctor_name": {"type": ["string", "null"]},
            "clinic_name": {"type": ["string", "null"]},
            "diagnostic_summary": {"type": ["string", "null"]},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_name": {"type": "string"},
                        "last_done_date": {"type": ["string", "null"]},
                        "next_due_date": {"type": ["string", "null"]},
                        "item_source": {"type": ["string", "null"]},
                        "notes": {"type": ["string", "null"]},
                    },
                    "required": ["item_name"],
                },
            },
            "diagnostic_values": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "test_type": {
                            "type": "string",
                            "enum": ["blood", "urine", "fecal", "xray", "ultrasound", "ecg", "eeg", "other"],
                        },
                        "parameter_name": {"type": "string"},
                        "value_numeric": {"type": ["number", "null"]},
                        "value_text": {"type": ["string", "null"]},
                        "unit": {"type": ["string", "null"]},
                        "reference_range": {"type": ["string", "null"]},
                        "status_flag": {
                            "type": ["string", "null"],
                            "enum": ["low", "normal", "high", "abnormal", None],
                        },
                        "observed_at": {"type": ["string", "null"]},
                    },
                    "required": ["test_type", "parameter_name"],
                },
            },
            "conditions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "condition_name": {"type": "string"},
                        "condition_type": {
                            "type": "string",
                            "enum": ["chronic", "acute", "episodic", "recurrent"],
                        },
                        "condition_status": {
                            "type": ["string", "null"],
                            "enum": ["active", "resolved", None],
                        },
                        "diagnosis": {"type": ["string", "null"]},
                        "diagnosed_at": {"type": ["string", "null"]},
                        "episode_dates": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "All dates this condition was recorded or treated in this document.",
                        },
                        "medications": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "dose": {"type": ["string", "null"]},
                                    "frequency": {"type": ["string", "null"]},
                                    "route": {"type": ["string", "null"]},
                                    "end_date": {"type": ["string", "null"]},
                                },
                                "required": ["name"],
                            },
                        },
                        "monitoring": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "frequency": {"type": ["string", "null"]},
                                    "recheck_due_date": {"type": ["string", "null"]},
                                },
                                "required": ["name"],
                            },
                        },
                    },
                    "required": ["condition_name"],
                },
            },
            "standalone_medications": {
                "type": "array",
                "description": "Medications prescribed without a named condition.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "dose": {"type": ["string", "null"]},
                        "frequency": {"type": ["string", "null"]},
                        "route": {"type": ["string", "null"]},
                        "end_date": {"type": ["string", "null"]},
                        "notes": {"type": ["string", "null"]},
                    },
                    "required": ["name"],
                },
            },
            "recommendations": {
                "type": "array",
                "description": "Non-medication clinical directives (diet, activity, rest, follow-up).",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["diet", "activity", "rest", "follow_up", "other"],
                        },
                        "description": {"type": "string"},
                        "linked_condition": {"type": ["string", "null"]},
                        "duration": {"type": ["string", "null"]},
                        "notes": {"type": ["string", "null"]},
                    },
                    "required": ["type", "description"],
                },
            },
            "preventive_medications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "medication_name": {"type": "string"},
                        "medication_name_raw": {"type": ["string", "null"]},
                        "dose": {"type": ["number", "null"]},
                        "dose_unit": {"type": ["string", "null"]},
                        "frequency": {"type": ["string", "null"]},
                        "duration": {"type": ["string", "null"]},
                        "prevention_targets": {"type": "array", "items": {"type": "string"}},
                        "notes": {"type": ["string", "null"]},
                    },
                    "required": ["medication_name"],
                },
            },
            "vaccination_details": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "vaccine_name": {"type": "string"},
                        "vaccine_name_raw": {"type": ["string", "null"]},
                        "dose": {"type": ["string", "null"]},
                        "dose_unit": {"type": ["string", "null"]},
                        "route": {"type": ["string", "null"]},
                        "manufacturer": {"type": ["string", "null"]},
                        "batch_number": {"type": ["string", "null"]},
                        "next_due_date": {"type": ["string", "null"]},
                        "administered_by": {"type": ["string", "null"]},
                        "notes": {"type": ["string", "null"]},
                    },
                    "required": ["vaccine_name"],
                },
            },
            "contacts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "contact_type": {"type": "string", "enum": ["vet", "specialist", "other"]},
                        "name": {"type": "string"},
                        "clinic": {"type": ["string", "null"]},
                        "phone": {"type": ["string", "null"]},
                        "address": {"type": ["string", "null"]},
                    },
                    "required": ["name"],
                },
            },
            "clinical_exam": {
                "type": ["object", "null"],
                "properties": {
                    "weight_kg": {"type": ["number", "null"]},
                    "temperature_c": {"type": ["number", "null"]},
                    "pulse_bpm": {"type": ["number", "null"]},
                    "respiration_rpm": {"type": ["number", "null"]},
                    "mucous_membranes": {"type": ["string", "null"]},
                    "in_clinic_test_values": {"type": ["array", "null"], "items": {"type": "object"}},
                    "notes": {"type": ["string", "null"]},
                },
            },
        },
        "required": ["document_name", "document_type", "document_category", "items"],
    },
}


def _build_canonical_document_name(
    document_category: str | None,
    document_name: str | None,
    event_date,
    diagnostic_values: list[dict] | None = None,
) -> str:
    """
    Build the canonical display name for a document.

    Naming convention (user-specified):
        BloodReport_Mar26    UrineReport_Sep24   FecalReport_Jan25
        LabReport_Mar26      XRay_Mar26          Ultrasound_Mar26
        ECG_Mar26            EEG_Mar26           ImagingReport_Mar26
        Vaccination_Mar26    VetPrescription_Mar26

    When event_date is None the date suffix is omitted (e.g. "BloodReport").
    Never raises — missing date or unknown category are both valid outcomes.

    Args:
        document_category: Canonical category string (e.g. "Blood Report").
        document_name: LLM-suggested name used for imaging sub-type detection.
        event_date:  datetime.date or None.
        diagnostic_values: List of diagnostic value dicts (for test_type detection).
    """
    cat = (document_category or "").strip()
    doc_lower = (document_name or "").lower()
    dv = diagnostic_values or []
    test_types = {(v.get("test_type") or "").lower() for v in dv}

    if cat == "Prescription":
        base = "VetPrescription"
    elif cat == "Vaccination":
        base = "Vaccination"
    elif cat == "Blood Report":
        base = "BloodReport"
    elif cat == "Urine Report":
        base = "UrineReport"
    elif cat == "Imaging":
        if "xray" in test_types or any(kw in doc_lower for kw in ("x-ray", "xray", "x ray", "radiograph")):
            base = "XRay"
        elif "ultrasound" in test_types or any(kw in doc_lower for kw in ("ultrasound", "usg", "sonograph")):
            base = "Ultrasound"
        elif "ecg" in test_types or "ecg" in doc_lower or "electrocardiograph" in doc_lower:
            base = "ECG"
        elif "eeg" in test_types or "eeg" in doc_lower or "electroencephalograph" in doc_lower:
            base = "EEG"
        else:
            base = "ImagingReport"
    else:
        # PCR & Parasite Panel, Other, or unknown — check for fecal content first
        if "fecal" in test_types or any(kw in doc_lower for kw in ("fecal", "stool", "feces", "faecal")):
            base = "FecalReport"
        else:
            base = "LabReport"

    # Append _MONYY date suffix when an event_date is available.
    if event_date is not None:
        try:
            return f"{base}_{event_date.strftime('%b%y')}"
        except Exception:
            pass  # Malformed date object — return base name safely

    return base


_anthropic_extraction_client = None


def _get_anthropic_extraction_client():
    """Return a cached AI client for extraction (provider-agnostic, created on first call)."""
    global _anthropic_extraction_client
    if _anthropic_extraction_client is None:
        from app.utils.ai_client import get_ai_client  # noqa: PLC0415
        _anthropic_extraction_client = get_ai_client()
    return _anthropic_extraction_client


async def _call_openai_extraction(document_text: str, extra_system: str = "") -> dict:
    """
    Call Claude to extract structured data from document text using tool_use.

    Uses tool_use with EXTRACTION_TOOL_SCHEMA so the API is forced to return
    schema-valid structured output — eliminates all JSON parse failures.

    Used for PDF text content. For images, use _call_openai_extraction_vision().

    Args:
        document_text: The text content of the uploaded document.
        extra_system: Optional additional instructions appended to EXTRACTION_SYSTEM_PROMPT
                      (used by the two-pass low-confidence retry).

    Returns:
        Validated dict matching EXTRACTION_TOOL_SCHEMA (tool_use .input).

    Raises:
        Exception: If all retry attempts fail (propagated from retry_openai_call).
    """
    client = _get_anthropic_extraction_client()
    system_prompt = EXTRACTION_SYSTEM_PROMPT + ("\n" + extra_system if extra_system else "")

    async def _make_call() -> dict:
        response = await client.messages.create(
            model=OPENAI_EXTRACTION_MODEL,
            temperature=OPENAI_EXTRACTION_TEMPERATURE,
            max_tokens=OPENAI_EXTRACTION_MAX_TOKENS,
            system=system_prompt,
            tools=[EXTRACTION_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "extract_pet_health_data"},
            messages=[
                {"role": "user", "content": document_text},
            ],
        )
        # tool_use response: content[0] is a ToolUseBlock with .input dict
        return response.content[0].input

    return await retry_openai_call(_make_call)


def _parse_image_block(data_uri: str) -> dict:
    """
    Convert a base64 data URI into an Anthropic image content block.

    Args:
        data_uri: Base64 data URI (data:image/jpeg;base64,...).

    Returns:
        Anthropic image content block dict.
    """
    media_type = "image/jpeg"
    base64_data = data_uri
    if data_uri.startswith("data:"):
        header, _, base64_data = data_uri.partition(",")
        mime_part = header.split(";")[0].replace("data:", "")
        if mime_part:
            media_type = mime_part
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64_data,
        },
    }


async def _call_openai_extraction_vision(
    image_data_uris: str | list[str],
    extra_system: str = "",
) -> dict:
    """
    Call Claude vision API to extract data from one or more images using tool_use.

    Accepts either a single data URI string or a list of them.  Multi-image
    input is used for multi-page imaging documents (USG film, X-ray) so that
    findings spread across pages are captured in a single extraction pass.

    Uses tool_use with EXTRACTION_TOOL_SCHEMA so the API is forced to return
    schema-valid structured output — eliminates all JSON parse failures.

    Args:
        image_data_uris: Base64 data URI string, or list of data URI strings
                         (data:image/jpeg;base64,...).
        extra_system: Optional additional instructions appended to EXTRACTION_SYSTEM_PROMPT
                      (used by the two-pass low-confidence retry).

    Returns:
        Validated dict matching EXTRACTION_TOOL_SCHEMA (tool_use .input).

    Raises:
        Exception: If all retry attempts fail.
    """
    client = _get_anthropic_extraction_client()

    # Normalise to list so the rest of the function is uniform.
    uris: list[str] = (
        [image_data_uris] if isinstance(image_data_uris, str) else list(image_data_uris)
    )

    system_prompt = EXTRACTION_SYSTEM_PROMPT + ("\n" + extra_system if extra_system else "")

    # Build content: text instruction followed by one image block per page.
    page_label = "this veterinary document image" if len(uris) == 1 else "these veterinary document images (multiple pages)"
    content: list[dict] = [
        {"type": "text", "text": f"Extract preventive health data from {page_label}."},
    ]
    for uri in uris:
        content.append(_parse_image_block(uri))

    async def _make_call() -> dict:
        response = await client.messages.create(
            model=OPENAI_EXTRACTION_MODEL,
            temperature=OPENAI_EXTRACTION_TEMPERATURE,
            max_tokens=OPENAI_EXTRACTION_MAX_TOKENS,
            system=system_prompt,
            tools=[EXTRACTION_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "extract_pet_health_data"},
            messages=[{"role": "user", "content": content}],
        )
        # tool_use response: content[0] is a ToolUseBlock with .input dict
        return response.content[0].input

    return await retry_openai_call(_make_call)


def _validate_extraction_dict(
    parsed: dict,
    file_path: str | None = None,
) -> tuple[list[dict], str | None, str | None, dict]:
    """
    Validate the structured dict returned by the tool_use extraction call.

    With tool_use, the Anthropic API guarantees schema-valid output, so
    JSON parsing and salvage logic are no longer needed.  This function
    focuses on business-logic validation: date checks, required key checks,
    and metadata normalisation.

    Args:
        parsed: Dict from response.content[0].input (tool_use output).
        file_path: Storage path of the document (used for filename date fallback).

    Returns:
        Tuple of (validated items list, document_name or None,
                  extracted_pet_name or None, metadata dict).

    Raises:
        ValueError: If the parsed dict is not a valid dict.
    """
    if not isinstance(parsed, dict):
        raise ValueError(
            f"Extraction tool returned unexpected type: {type(parsed).__name__}. Expected dict."
        )

    # Extract document_name, pet_name, and classification fields.
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
        "standalone_medications": [],
        "recommendations": [],
        "contacts": [],
        "clinical_exam": None,
        "vet_diet_recommendations": [],
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
        raw_standalone_meds = parsed.get("standalone_medications")
        if isinstance(raw_standalone_meds, list):
            metadata["standalone_medications"] = raw_standalone_meds
        raw_recommendations = parsed.get("recommendations")
        if isinstance(raw_recommendations, list):
            metadata["recommendations"] = raw_recommendations
        raw_contacts = parsed.get("contacts")
        if isinstance(raw_contacts, list):
            metadata["contacts"] = raw_contacts
        raw_clinical_exam = parsed.get("clinical_exam")
        if isinstance(raw_clinical_exam, dict):
            metadata["clinical_exam"] = raw_clinical_exam
        raw_vet_diet = parsed.get("vet_diet_recommendations")
        if isinstance(raw_vet_diet, list):
            metadata["vet_diet_recommendations"] = raw_vet_diet

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
        raw_date_str = str(item.get("last_done_date") or "").strip()
        if not raw_date_str or raw_date_str.lower() in ("null", "none", ""):
            # GPT returned null/missing date — try filename as fallback before skipping.
            filename_date = _extract_date_from_filename(file_path) if file_path else None
            if filename_date:
                logger.info(
                    "Item %d has no GPT date — using filename date '%s'. Item: %s",
                    i, filename_date, str(item),
                )
                item["last_done_date"] = filename_date
                validated.append(item)
            else:
                logger.warning(
                    "Skipping extraction item at index %d — missing date, no filename fallback. Item: %s",
                    i, str(item),
                )
            continue
        try:
            parsed_date = parse_date(raw_date_str)
            if parsed_date > today:
                logger.warning(
                    "Skipping extraction item at index %d — future date %s. Item: %s",
                    i, str(parsed_date), str(item),
                )
                continue
            # Reject implausibly old dates (before 2020) — likely a GPT year
            # hallucination (e.g. reading "25" as 1925 or misreading digit).
            if parsed_date.year < 2020:
                logger.warning(
                    "Skipping extraction item at index %d — date year %d predates "
                    "2020, likely a misread. Item: %s",
                    i, parsed_date.year, str(item),
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
    # DB item_name is "Rabies Vaccine"; display name "Rabies (Nobivac RL)" is
    # applied separately via _DISPLAY_NAME in care_plan_engine.py.
    "rabies": "Rabies Vaccine",
    "nobivac rl": "Rabies Vaccine",
    "rabies vaccine": "Rabies Vaccine",
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


def _coerce_float(value) -> float | None:
    """Safely coerce a value to float; return None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _save_supplement_as_diet_item(
    db: Session,
    pet: Pet,
    document: Document,
    medication: dict,
    linked_condition: str | None = None,
) -> None:
    """
    Route a supplement-classified medication to DietItem instead of ConditionMedication.

    Converts a medication dict (with item_type="supplement") to a DietItem record
    by delegating to the existing _save_vet_diet_items function.

    Args:
        db: SQLAlchemy session
        pet: Pet object
        document: Document object
        medication: Medication dict with name, dose, frequency, etc.
        linked_condition: Optional condition name if the supplement is for a specific condition
    """
    name = str(medication.get("name") or "").strip()[:200]
    if not name:
        return

    # Build detail from dose, frequency, and notes
    parts = []
    if medication.get("dose"):
        parts.append(str(medication["dose"]))
    if medication.get("frequency"):
        parts.append(str(medication["frequency"]))
    if linked_condition:
        parts.append(f"for {linked_condition}")
    if medication.get("notes"):
        parts.append(str(medication["notes"]))

    detail = " · ".join(parts) if parts else ""

    # Delegate to existing diet item saving function
    await _save_vet_diet_items(
        db=db,
        pet=pet,
        document=document,
        vet_diet_recommendations=[{
            "food_label": name,
            "food_type": "supplement",
            "detail": detail,
        }],
    )


async def _save_vet_diet_items(
    db: Session,
    pet: Pet,
    document: Document,
    vet_diet_recommendations: list[dict],
) -> None:
    """
    Persist vet-prescribed dietary recommendations as DietItem records.

    Each recommendation from a Prescription becomes a diet item tagged with
    '(Vet prescribed)' in the detail field so users and the nutrition analysis
    can distinguish vet-recommended items from user-added ones.

    food_type='avoid' entries are stored with type='homemade' and a detail
    prefix of 'Avoid –' so they appear in the diet list as a visible warning.

    Silently skips malformed entries. Does not commit — the caller's
    surrounding transaction handles commit/rollback.
    """
    from app.services.diet_service import add_diet_item

    if not vet_diet_recommendations:
        return

    doc_ref = document.document_name or "vet prescription"

    for raw in vet_diet_recommendations:
        if not isinstance(raw, dict):
            continue

        food_label = str(raw.get("food_label") or "").strip()[:200]
        if not food_label:
            continue

        food_type = str(raw.get("food_type") or "").strip().lower()
        raw_detail = str(raw.get("detail") or "").strip()

        if food_type == "avoid":
            # Store as a diet item with an 'avoid' note — use 'homemade' type
            # so it's visible in the diet list without breaking type constraints.
            item_type = "homemade"
            detail = f"Avoid – {raw_detail}" if raw_detail else "Avoid (vet advised)"
            detail = f"{detail} · Vet prescribed ({doc_ref})"[:200]
        elif food_type == "supplement":
            item_type = "supplement"
            detail = f"{raw_detail} · Vet prescribed ({doc_ref})"[:200] if raw_detail else f"Vet prescribed ({doc_ref})"[:200]
        elif food_type == "packaged":
            item_type = "packaged"
            detail = f"{raw_detail} · Vet prescribed ({doc_ref})"[:200] if raw_detail else f"Vet prescribed ({doc_ref})"[:200]
        else:
            # homemade or unknown
            item_type = "homemade"
            detail = f"{raw_detail} · Vet prescribed ({doc_ref})"[:200] if raw_detail else f"Vet prescribed ({doc_ref})"[:200]

        try:
            await add_diet_item(db=db, pet_id=pet.id, food_type=item_type, label=food_label, detail=detail)
            logger.info(
                "Vet diet item saved for pet=%s: '%s' (%s) from document=%s",
                pet.id, food_label, item_type, document.id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to save vet diet item '%s' for pet=%s: %s",
                food_label, pet.id, exc,
            )


def _save_clinical_exam_data(
    db: Session,
    pet: Pet,
    document: Document,
    clinical_exam: dict | None,
) -> None:
    """
    Persist clinical exam data extracted from a prescription document.

    - weight_kg → WeightHistory entry (recorded_at = document.event_date)
    - temperature_c / pulse_bpm / respiration_rpm → DiagnosticTestResult with test_type="vital"
    - mucous_membranes / clinical_findings → DiagnosticTestResult (value_text) with test_type="vital"
    - in_clinic_test_values[] → DiagnosticTestResult entries with test_type="vital"

    Silently skips fields that are missing or invalid. Does not commit —
    the caller's surrounding transaction handles commit/rollback.
    """
    if not clinical_exam or not isinstance(clinical_exam, dict):
        return

    observed_date = document.event_date or datetime.utcnow().date()

    # --- Weight → WeightHistory ---
    weight_kg = _coerce_float(clinical_exam.get("weight_kg"))
    if weight_kg is not None and 0 < weight_kg < 200:
        try:
            existing = (
                db.query(WeightHistory)
                .filter(
                    WeightHistory.pet_id == pet.id,
                    WeightHistory.recorded_at == observed_date,
                )
                .first()
            )
            if existing is None:
                db.add(
                    WeightHistory(
                        pet_id=pet.id,
                        weight=Decimal(str(round(weight_kg, 2))),
                        recorded_at=observed_date,
                        note=f"From prescription: {document.document_name or 'vet visit'}"[:200],
                    )
                )
        except Exception as exc:
            logger.warning(
                "Failed to save prescription weight for pet=%s: %s",
                str(pet.id), str(exc),
            )

    def _add_vital(parameter_name: str, value_numeric=None, value_text=None, unit=None):
        if value_numeric is None and not value_text:
            return
        try:
            db.add(
                DiagnosticTestResult(
                    pet_id=pet.id,
                    document_id=document.id,
                    test_type="vital",
                    parameter_name=parameter_name[:120],
                    value_numeric=value_numeric,
                    value_text=(str(value_text).strip()[:200] if value_text is not None else None),
                    unit=(unit[:60] if unit else None),
                    observed_at=observed_date,
                )
            )
        except Exception as exc:
            logger.warning(
                "Failed to save vital '%s' for pet=%s: %s",
                parameter_name, str(pet.id), str(exc),
            )

    temperature_c = _coerce_float(clinical_exam.get("temperature_c"))
    if temperature_c is not None and 30 <= temperature_c <= 45:
        _add_vital("Temperature", value_numeric=temperature_c, unit="°C")

    pulse_bpm = _coerce_float(clinical_exam.get("pulse_bpm"))
    if pulse_bpm is not None and 10 <= pulse_bpm <= 400:
        _add_vital("Pulse", value_numeric=pulse_bpm, unit="bpm")

    respiration_rpm = _coerce_float(clinical_exam.get("respiration_rpm"))
    if respiration_rpm is not None and 2 <= respiration_rpm <= 200:
        _add_vital("Respiration", value_numeric=respiration_rpm, unit="rpm")

    mucous = clinical_exam.get("mucous_membranes")
    if mucous and isinstance(mucous, str) and mucous.strip():
        _add_vital("Mucous Membranes", value_text=mucous.strip())

    clinical_findings = clinical_exam.get("clinical_findings")
    if clinical_findings and isinstance(clinical_findings, str) and clinical_findings.strip():
        _add_vital("Clinical Findings", value_text=clinical_findings.strip())

    in_clinic_values = clinical_exam.get("in_clinic_test_values")
    if isinstance(in_clinic_values, list):
        for raw in in_clinic_values:
            if not isinstance(raw, dict):
                continue
            parameter_name = str(raw.get("parameter_name") or "").strip()
            if not parameter_name:
                continue
            value_numeric = _coerce_float(raw.get("value_numeric"))
            value_text = raw.get("value_text")
            unit = raw.get("unit")
            _add_vital(
                parameter_name,
                value_numeric=value_numeric,
                value_text=value_text,
                unit=(str(unit).strip() if unit else None),
            )


def _classify_extraction_error(exc: Exception) -> str:
    """
    Classify an extraction exception as 'retryable' or 'permanent'.

    Retryable errors are transient (rate limits, timeouts, network issues).
    Permanent errors indicate bad data or logic failures that won't be fixed by retrying.

    Returns:
        'retryable' or 'permanent'
    """
    # Import lazily to avoid circular dependency at module level.
    try:
        import anthropic as _anthropic
        if isinstance(exc, (_anthropic.RateLimitError, _anthropic.APITimeoutError,
                             _anthropic.APIConnectionError)):
            return "retryable"
    except ImportError:
        pass

    import asyncio
    if isinstance(exc, asyncio.TimeoutError):
        return "retryable"

    # Connection-related errors — string-match as a last resort.
    exc_str = str(exc).lower()
    if any(kw in exc_str for kw in ("timeout", "rate limit", "connection", "network", "503", "502", "529")):
        return "retryable"

    # Everything else (ValueError, DB constraint, logic errors) is permanent.
    return "permanent"


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
        # --- Step 1: Call GPT extraction via tool_use ---
        # Route to vision API for images, text API for PDFs.
        # Both functions return a dict (tool_use .input) — no JSON parsing needed.
        logger.info(
            "Starting GPT extraction: document_id=%s, pet_id=%s, mime=%s",
            str(document_id),
            str(pet.id),
            document.mime_type,
        )

        # Keep vision data available for optional two-pass retry.
        _vision_data_uri: str | None = None          # single-image (JPEG/PNG or scanned non-imaging PDF)
        _vision_pages: list[str] | None = None       # multi-page (imaging scanned PDF)
        _pdf_text_payload: str | None = None

        if file_bytes and document.mime_type in ("image/jpeg", "image/png"):
            # Images: use GPT vision API with base64-encoded image.
            from app.utils.file_reader import encode_image_base64
            _vision_data_uri = encode_image_base64(file_bytes, document.mime_type)
            extraction_result = await _call_openai_extraction_vision(_vision_data_uri)
        elif file_bytes and document.mime_type == "application/pdf":
            # PDFs: extract text first, then send to GPT.
            from app.utils.file_reader import extract_pdf_text
            pdf_text = extract_pdf_text(file_bytes)
            if pdf_text and len(pdf_text.strip()) > 20:
                _pdf_text_payload = f"Veterinary document text:\n\n{pdf_text}"
                extraction_result = await _call_openai_extraction(_pdf_text_payload)
            else:
                # Scanned PDF — render pages as images and use GPT vision.
                logger.info(
                    "PDF has no extractable text (scanned), "
                    "falling back to vision API: document_id=%s",
                    str(document_id),
                )
                from app.utils.file_reader import render_pdf_pages_as_images
                # Imaging documents (USG, X-ray) may spread findings across
                # multiple pages, so render up to 5 pages and send them all.
                # Text-only reports (CBC, urine) are reliably single-page, so
                # cap at 3 and send only page 0 to keep token usage low.
                # Check both document_name (set after extraction) and the raw
                # file_path/filename (available immediately) so that imaging PDFs
                # uploaded without a pre-set name are still detected correctly.
                _doc_name_lower = (document.document_name or "").lower()
                _file_name_lower = os.path.basename(document.file_path or "").lower()
                _imaging_keywords = ("usg", "ultrasound", "x-ray", "xray", "x ray", "radiograph", "film")
                _is_imaging = any(kw in _doc_name_lower for kw in _imaging_keywords) or any(
                    kw in _file_name_lower for kw in _imaging_keywords
                )
                _max_pages = 5 if _is_imaging else 3
                page_images = render_pdf_pages_as_images(file_bytes, max_pages=_max_pages)
                if page_images:
                    # For imaging: send all rendered pages so multi-page findings
                    # are captured. For other scanned docs: send page 0 only.
                    if _is_imaging:
                        _vision_pages = page_images
                        extraction_result = await _call_openai_extraction_vision(_vision_pages)
                    else:
                        _vision_data_uri = page_images[0]
                        extraction_result = await _call_openai_extraction_vision(_vision_data_uri)
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
            _pdf_text_payload = document_text
            extraction_result = await _call_openai_extraction(document_text)

        # --- Step 1b: Two-pass retry for low confidence ---
        # The model rates its own confidence 0.0–1.0.  If the first pass is below
        # the threshold, a second focused pass is run and the higher-confidence
        # result is used.  Only fires on the very first attempt (retry_count == 0)
        # to avoid infinite loops.
        first_confidence = float(extraction_result.get("confidence") or 1.0)
        if (
            first_confidence < EXTRACTION_LOW_CONFIDENCE_THRESHOLD
            and document.retry_count == 0
        ):
            logger.warning(
                "Low confidence extraction (%.2f < %.2f) — running second-pass retry: "
                "document_id=%s",
                first_confidence,
                EXTRACTION_LOW_CONFIDENCE_THRESHOLD,
                str(document_id),
            )
            _SECOND_PASS_HINT = (
                "IMPORTANT: The previous extraction pass had low confidence. "
                "Re-examine the document very carefully. Pay special attention to: "
                "(1) document_category — distinguish lab reports (test results with "
                "reference ranges) from prescriptions (medication orders with clinic "
                "letterhead); "
                "(2) all date fields — look for explicit dates written anywhere on the "
                "document; "
                "(3) pet_name — check for any name near the top of the document."
            )
            try:
                if _vision_pages:
                    # Multi-page imaging document — retry with all pages.
                    extraction_result_2 = await _call_openai_extraction_vision(
                        _vision_pages, extra_system=_SECOND_PASS_HINT
                    )
                elif _vision_data_uri:
                    extraction_result_2 = await _call_openai_extraction_vision(
                        _vision_data_uri, extra_system=_SECOND_PASS_HINT
                    )
                elif _pdf_text_payload:
                    extraction_result_2 = await _call_openai_extraction(
                        _pdf_text_payload, extra_system=_SECOND_PASS_HINT
                    )
                else:
                    extraction_result_2 = extraction_result  # no-op

                second_confidence = float(extraction_result_2.get("confidence") or 0.0)
                if second_confidence > first_confidence:
                    extraction_result = extraction_result_2
                    logger.info(
                        "Second-pass improved confidence: %.2f → %.2f: document_id=%s",
                        first_confidence,
                        second_confidence,
                        str(document_id),
                    )
                else:
                    logger.info(
                        "Second-pass did not improve confidence (%.2f vs %.2f), "
                        "keeping first-pass result: document_id=%s",
                        second_confidence,
                        first_confidence,
                        str(document_id),
                    )
            except Exception as retry_err:
                logger.warning(
                    "Second-pass retry failed, using first-pass result: "
                    "document_id=%s, error=%s",
                    str(document_id),
                    str(retry_err),
                )

        # Store model-rated confidence on the document record.
        document.extraction_confidence = float(extraction_result.get("confidence") or 1.0)

        # --- Step 2: Validate and normalize ---
        extracted_items, document_name, extracted_pet_name, metadata = _validate_extraction_dict(extraction_result, file_path=document.file_path)
        results["document_type"] = metadata["document_type"]
        results["diagnostic_summary"] = metadata["diagnostic_summary"]
        # Persist GPT-generated diagnostic summary on the document row.
        if metadata.get("diagnostic_summary"):
            document.diagnostic_summary = str(metadata["diagnostic_summary"])[:2000]
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
            clinical_exam=metadata.get("clinical_exam"),
            conditions=metadata.get("conditions"),
            doctor_name=metadata.get("doctor_name"),
            clinic_name=metadata.get("clinic_name"),
            diagnostic_values=metadata.get("diagnostic_values"),
        )
        # Set results["document_category"] to the RESOLVED category, not the raw GPT output.
        # This ensures WhatsApp message and DB state stay in sync.
        results["document_category"] = document_category

        extracted_items = _derive_blood_test_fallback_items(
            extracted_items=extracted_items,
            document_name=document_name or document.document_name,
            file_path=document.file_path,
            document_category=document_category,
            diagnostic_values=metadata.get("diagnostic_values", []),
        )
        results["items_extracted"] = len(extracted_items)

        # document_name is set below after event_date is resolved, using
        # _build_canonical_document_name for all document types.
        if document_category:
            document.document_category = document_category

        # Compute event_date: prefer last_done_date from preventive items.
        # For diagnostic-only documents (urine, blood panel with no tracked items),
        # fall back to observed_at from diagnostic_values, then filename date.
        # For prescriptions with no preventive items, also try diagnosed_at from conditions.
        # Rule: if a date is parseable from the original filename, it is treated as
        # authoritative — it overrides a conflicting GPT-extracted date.  This handles
        # cases where the uploader named the file with the actual visit date
        # (e.g. Prescription_Chavan_12_02_25.jpg → 2025-02-12).
        filename_date: date | None = None
        fn_date_str = _extract_date_from_filename(document.file_path)
        if fn_date_str:
            try:
                filename_date = parse_date(fn_date_str)
            except ValueError:
                pass

        event_dates: list = []
        for item in extracted_items:
            raw_date = item.get("last_done_date")
            if raw_date:
                try:
                    event_dates.append(parse_date(str(raw_date)))
                except ValueError:
                    pass
        if not event_dates:
            # Diagnostic-only document — try observed_at from diagnostic_values.
            for dv in (metadata.get("diagnostic_values") or []):
                observed_at = dv.get("observed_at") if isinstance(dv, dict) else None
                if observed_at:
                    try:
                        event_dates.append(parse_date(str(observed_at)))
                    except ValueError:
                        pass
        if not event_dates and document_category == "Prescription":
            # Prescription with no preventive items — try diagnosed_at and episode_dates from conditions.
            # Note: GPT often puts the prescription date in episode_dates (as "date condition mentioned/treated")
            # rather than in diagnosed_at (explicit diagnosis date).
            for cond in (metadata.get("conditions") or []):
                # First try diagnosed_at (explicit diagnosis date)
                diagnosed_at = cond.get("diagnosed_at") if isinstance(cond, dict) else None
                if diagnosed_at:
                    try:
                        event_dates.append(parse_date(str(diagnosed_at)))
                        continue  # Found a date, skip episode_dates for this condition
                    except ValueError:
                        pass
                # Fallback to episode_dates if no diagnosed_at found
                if not event_dates and isinstance(cond, dict):
                    for episode_date_str in (cond.get("episode_dates") or []):
                        if episode_date_str:
                            try:
                                event_dates.append(parse_date(str(episode_date_str)))
                                break  # Found a date, move to next condition
                            except ValueError:
                                pass

        if filename_date:
            if not event_dates:
                # No date found anywhere — use the filename date as fallback.
                logger.warning(
                    "Using filename date fallback for event_date: "
                    "document_id=%s, file_path=%s, extracted_date=%s",
                    str(document_id),
                    document.file_path,
                    fn_date_str,
                )
                event_dates.append(filename_date)
            else:
                extracted_date = max(event_dates)
                if extracted_date != filename_date:
                    # Filename date is an explicit human label — prefer it over GPT extraction.
                    logger.info(
                        "Filename date (%s) overrides GPT-extracted date (%s) for document_id=%s",
                        fn_date_str,
                        extracted_date.isoformat(),
                        str(document_id),
                    )
                    event_dates = [filename_date]

        if event_dates:
            document.event_date = max(event_dates)

        # Apply canonical document naming for all document types.
        # Format: BaseName_MONYY (e.g. BloodReport_Mar26, VetPrescription_Sep24).
        # When event_date is None the suffix is omitted — never fails on missing date.
        document.document_name = _build_canonical_document_name(
            document_category=document_category,
            document_name=document_name,
            event_date=document.event_date,
            diagnostic_values=metadata.get("diagnostic_values"),
        )

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
            if test_type not in ("blood", "urine", "fecal", "xray", "ultrasound", "ecg", "eeg", "other"):
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
                    _obs = parse_date(str(raw.get("observed_at")))
                    _today = datetime.utcnow().date()
                    if _obs > _today:
                        logger.warning(
                            "Diagnostic value observed_at is in the future (%s), ignoring: "
                            "document_id=%s, parameter=%s",
                            str(_obs), str(document_id), parameter_name,
                        )
                    elif _obs.year < 2020:
                        logger.warning(
                            "Diagnostic value observed_at year %d predates 2020, ignoring: "
                            "document_id=%s, parameter=%s",
                            _obs.year, str(document_id), parameter_name,
                        )
                    else:
                        observed_at = _obs
                except ValueError:
                    logger.warning(
                        "Unparseable observed_at '%s' for diagnostic value, ignoring: "
                        "document_id=%s, parameter=%s",
                        str(raw.get("observed_at")), str(document_id), parameter_name,
                    )

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

        # --- Store clinical exam data (prescriptions only) ---
        # Weight → WeightHistory entry; vitals & in-clinic tests → DiagnosticTestResult
        # with test_type="vital". Observed_at is the document's event_date.
        _save_clinical_exam_data(
            db=db,
            pet=pet,
            document=document,
            clinical_exam=metadata.get("clinical_exam"),
        )

        # --- Store vet-prescribed dietary recommendations (prescriptions only) ---
        # New extraction uses recommendations[type=diet]; legacy used vet_diet_recommendations.
        # Convert recommendations[type=diet] entries to the legacy diet-item format so that
        # _save_vet_diet_items can persist them without changes to downstream logic.
        raw_recommendations = metadata.get("recommendations") or []
        vet_diet: list[dict] = []
        for rec in raw_recommendations:
            if not isinstance(rec, dict):
                continue
            if rec.get("type") == "diet":
                desc = str(rec.get("description") or "").strip()
                if desc:
                    vet_diet.append({
                        "food_label": desc[:200],
                        "food_type": "packaged",  # conservative default; doc may clarify
                        "detail": str(rec.get("duration") or rec.get("notes") or "")[:200] or None,
                    })
        # Also accept legacy field if present (e.g. old cached metadata).
        if not vet_diet:
            vet_diet = metadata.get("vet_diet_recommendations") or []
        if vet_diet:
            try:
                await _save_vet_diet_items(
                    db=db,
                    pet=pet,
                    document=document,
                    vet_diet_recommendations=vet_diet,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to save vet diet recommendations for pet=%s document=%s: %s",
                    pet.id, document_id, exc,
                )

        # --- Store non-diet recommendations on the document ---
        # activity / rest / follow_up / other recs have no separate table;
        # persist them as JSONB on the document row so the dashboard can
        # surface follow-up instructions and activity restrictions.
        # Exclude null/empty type to avoid storing malformed GPT output.
        non_diet_recs = [
            rec for rec in raw_recommendations
            if isinstance(rec, dict) and rec.get("type") not in (None, "", "diet")
        ]
        if non_diet_recs:
            document.non_diet_recommendations = non_diet_recs

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
                # Map new extraction condition_type values to DB-valid values.
                # DB column still uses: chronic | episodic | resolved.
                # New prompt produces: chronic | acute | episodic | recurrent.
                # "acute" and "recurrent" map to "episodic" for DB storage.
                # "resolved" type from old prompts also maps to "episodic" + condition_status="resolved".
                raw_condition_type = str(raw_condition.get("condition_type") or "chronic").strip().lower()
                if raw_condition_type == "chronic":
                    condition_type = "chronic"
                elif raw_condition_type in ("episodic", "acute"):
                    condition_type = "episodic"
                elif raw_condition_type == "recurrent":
                    condition_type = "episodic"
                elif raw_condition_type == "resolved":
                    # Legacy: old prompt used "resolved" as a type.
                    condition_type = "episodic"
                else:
                    condition_type = "chronic"

                # condition_status: "active" | "resolved" | null
                raw_status = raw_condition.get("condition_status")
                condition_status = str(raw_status).strip().lower() if raw_status else None
                if condition_status not in ("active", "resolved"):
                    condition_status = None
                # If old prompt set type="resolved", ensure status is set.
                if raw_condition_type == "resolved" and not condition_status:
                    condition_status = "resolved"

                # episode_dates: parse and validate each date string.
                raw_episode_dates: list[str] = raw_condition.get("episode_dates") or []
                _today = datetime.utcnow().date()
                valid_episode_dates: list[str] = []
                for _ed in raw_episode_dates:
                    try:
                        _parsed = parse_date(str(_ed))
                        if _parsed <= _today and _parsed.year >= 2015:
                            valid_episode_dates.append(str(_parsed))
                    except Exception:
                        pass
                # Remove duplicates and sort.
                valid_episode_dates = sorted(set(valid_episode_dates))

                diagnosed_at = None
                if raw_condition.get("diagnosed_at"):
                    try:
                        _diag_date = parse_date(str(raw_condition["diagnosed_at"]))
                        if _diag_date > _today:
                            logger.warning(
                                "Condition diagnosed_at is in the future (%s), ignoring: "
                                "document_id=%s, condition=%s",
                                str(_diag_date), str(document_id), condition_name,
                            )
                        elif _diag_date.year < 2020:
                            logger.warning(
                                "Condition diagnosed_at year %d predates 2020, ignoring: "
                                "document_id=%s, condition=%s",
                                _diag_date.year, str(document_id), condition_name,
                            )
                        else:
                            diagnosed_at = _diag_date
                    except ValueError:
                        logger.warning(
                            "Unparseable diagnosed_at '%s' for condition, ignoring: "
                            "document_id=%s, condition=%s",
                            str(raw_condition["diagnosed_at"]), str(document_id), condition_name,
                        )

                # Upsert by (pet_id, name) — update if exists, create if not.
                existing_condition = (
                    db.query(Condition)
                    .filter(Condition.pet_id == pet.id, Condition.name == condition_name)
                    .first()
                )
                if existing_condition:
                    existing_condition.condition_type = condition_type
                    if condition_status:
                        existing_condition.condition_status = condition_status
                    if raw_condition.get("diagnosis"):
                        existing_condition.diagnosis = str(raw_condition["diagnosis"])[:500]
                    if diagnosed_at:
                        existing_condition.diagnosed_at = diagnosed_at
                    # Merge episode_dates: combine existing + new, deduplicate, sort.
                    existing_dates = existing_condition.episode_dates or []
                    merged_dates = sorted(set(existing_dates) | set(valid_episode_dates))
                    existing_condition.episode_dates = merged_dates
                    existing_condition.document_id = document.id
                    condition_obj = existing_condition
                else:
                    condition_obj = Condition(
                        pet_id=pet.id,
                        document_id=document.id,
                        name=condition_name[:200],
                        diagnosis=(str(raw_condition.get("diagnosis"))[:500] if raw_condition.get("diagnosis") else None),
                        condition_type=condition_type,
                        condition_status=condition_status,
                        episode_dates=valid_episode_dates,
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

                    # Classify medication as medicine or supplement.
                    item_type = str(med.get("item_type") or "medicine").strip().lower()
                    if item_type not in ("medicine", "supplement"):
                        item_type = "medicine"

                    if item_type == "supplement":
                        # Route supplements to DietItem instead of ConditionMedication
                        try:
                            await _save_supplement_as_diet_item(db, pet, document, med, condition_name)
                        except Exception as exc:
                            logger.warning(
                                "Failed to save supplement '%s' as diet item for condition '%s': %s",
                                med_name, condition_name, exc
                            )
                        continue  # Skip ConditionMedication for supplements

                    # Medicines → condition_medications (existing path)
                    existing_med = (
                        db.query(ConditionMedication)
                        .filter(ConditionMedication.condition_id == condition_obj.id, ConditionMedication.name == med_name)
                        .first()
                    )
                    # Parse end_date if provided.
                    med_end_date = None
                    if med.get("end_date"):
                        try:
                            _med_end = parse_date(str(med["end_date"]))
                            if _med_end.year >= 2015:
                                med_end_date = _med_end
                        except Exception:
                            pass
                    if not existing_med:
                        db.add(ConditionMedication(
                            condition_id=condition_obj.id,
                            name=med_name[:200],
                            item_type="medicine",
                            dose=(str(med.get("dose"))[:100] if med.get("dose") else None),
                            frequency=(str(med.get("frequency"))[:100] if med.get("frequency") else None),
                            route=(str(med.get("route"))[:50] if med.get("route") else None),
                            end_date=med_end_date,
                        ))
                    elif med_end_date and not existing_med.end_date:
                        existing_med.end_date = med_end_date

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
                    # Parse recheck_due_date if provided.
                    mon_recheck = None
                    if mon.get("recheck_due_date"):
                        try:
                            _recheck = parse_date(str(mon["recheck_due_date"]))
                            if _recheck.year >= 2015:
                                mon_recheck = _recheck
                        except Exception:
                            pass
                    if not existing_mon:
                        db.add(ConditionMonitoring(
                            condition_id=condition_obj.id,
                            name=mon_name[:200],
                            frequency=(str(mon.get("frequency"))[:100] if mon.get("frequency") else None),
                            recheck_due_date=mon_recheck,
                        ))
                    elif mon_recheck and not existing_mon.recheck_due_date:
                        existing_mon.recheck_due_date = mon_recheck

            except Exception as e:
                db.rollback()
                logger.warning(
                    "Error storing extracted condition '%s': %s. document_id=%s",
                    condition_name, str(e), str(document_id),
                )

        # --- Store standalone medications ---
        # Medications with no linked condition from the prescription.
        # Supplements → diet_items. Medicines → condition_medications under a placeholder condition.
        try:
            raw_standalone_meds = metadata.get("standalone_medications") or []
            if raw_standalone_meds:
                # Upsert placeholder condition for medicines that have no named diagnosis.
                # Per-pet upsert (not per-document) due to unique constraint (pet_id, name).
                STANDALONE_CONDITION_NAME = "Prescription Medications"
                standalone_condition = (
                    db.query(Condition)
                    .filter(Condition.pet_id == pet.id, Condition.name == STANDALONE_CONDITION_NAME)
                    .first()
                )
                if not standalone_condition:
                    standalone_condition = Condition(
                        pet_id=pet.id,
                        document_id=document.id,
                        name=STANDALONE_CONDITION_NAME,
                        diagnosis="Medications prescribed without a named diagnosis",
                        condition_type="episodic",
                        source="extraction",
                    )
                    db.add(standalone_condition)
                    db.flush()

                for med in raw_standalone_meds:
                    if not isinstance(med, dict):
                        continue
                    med_name = str(med.get("name") or "").strip()
                    if not med_name:
                        continue
                    item_type = str(med.get("item_type") or "medicine").strip().lower()
                    if item_type not in ("medicine", "supplement"):
                        item_type = "medicine"

                    if item_type == "supplement":
                        # Supplements → diet_items
                        try:
                            await _save_supplement_as_diet_item(db, pet, document, med, linked_condition=None)
                        except Exception as exc:
                            logger.warning("Failed to save standalone supplement '%s': %s", med_name, exc)
                    else:
                        # Medicines → condition_medications under placeholder condition
                        try:
                            existing = (
                                db.query(ConditionMedication)
                                .filter(
                                    ConditionMedication.condition_id == standalone_condition.id,
                                    ConditionMedication.name == med_name
                                )
                                .first()
                            )
                            med_end_date = None
                            if med.get("end_date"):
                                try:
                                    _med_end = parse_date(str(med["end_date"]))
                                    if _med_end.year >= 2015:
                                        med_end_date = _med_end
                                except Exception:
                                    pass
                            if not existing:
                                db.add(ConditionMedication(
                                    condition_id=standalone_condition.id,
                                    name=med_name[:200],
                                    item_type="medicine",
                                    dose=(str(med.get("dose"))[:100] if med.get("dose") else None),
                                    frequency=(str(med.get("frequency"))[:100] if med.get("frequency") else None),
                                    route=(str(med.get("route"))[:50] if med.get("route") else None),
                                    end_date=med_end_date,
                                    notes=(str(med.get("notes"))[:500] if med.get("notes") else None),
                                ))
                            elif med_end_date and not existing.end_date:
                                existing.end_date = med_end_date
                        except Exception as exc:
                            logger.warning(
                                "Error storing standalone medicine '%s' under placeholder condition: %s. document_id=%s",
                                med_name, str(exc), str(document_id),
                            )
        except Exception as e:
            db.rollback()
            logger.warning(
                "Error storing extracted standalone medications: %s. document_id=%s",
                str(e), str(document_id),
            )

        # --- Store extracted contacts (deduplicated) ---
        # Only process contacts from clinical documents. Lab/diagnostic reports
        # (Blood Report, Urine Report, Imaging, PCR & Parasite Panel) may reference
        # a requesting doctor but that is not a reliable vet contact.
        if document_category in _CLINICAL_CONTACT_CATEGORIES:
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
                        # Update source tracking to reflect the latest clinical document.
                        existing_contact.document_id = document.id
                        existing_contact.source_document_name = document.document_name
                        existing_contact.source_document_category = document.document_category
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
                            source_document_name=document.document_name,
                            source_document_category=document.document_category,
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
                    if existing_doc_contact:
                        # Refresh source tracking to reflect the latest clinical document.
                        existing_doc_contact.document_id = document.id
                        existing_doc_contact.source_document_name = document.document_name
                        existing_doc_contact.source_document_category = document.document_category
                        db.flush()
                    else:
                        db.add(Contact(
                            pet_id=pet.id,
                            document_id=document.id,
                            role="veterinarian",
                            name=selected_doctor_name[:200],
                            clinic_name=(str(metadata["clinic_name"])[:200] if metadata["clinic_name"] else None),
                            source="extraction",
                            source_document_name=document.document_name,
                            source_document_category=document.document_category,
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
                    if existing_item_contact:
                        # Refresh source tracking to reflect the latest clinical document.
                        existing_item_contact.document_id = document.id
                        existing_item_contact.source_document_name = document.document_name
                        existing_item_contact.source_document_category = document.document_category
                        db.flush()
                    else:
                        db.add(Contact(
                            pet_id=pet.id,
                            document_id=document.id,
                            role="veterinarian",
                            name=item_doctor[:200],
                            clinic_name=(str(item_clinic)[:200] if item_clinic else
                                         (str(metadata["clinic_name"])[:200] if metadata["clinic_name"] else None)),
                            source="extraction",
                            source_document_name=document.document_name,
                            source_document_category=document.document_category,
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
            # No preventive items — check if we at least got useful metadata.
            # If conditions, diagnostic values, or vaccination details were extracted,
            # use 'partially_extracted' so the document appears in the dashboard
            # with a distinct status from a fully successful extraction.
            has_metadata = bool(
                metadata.get("conditions")
                or metadata.get("diagnostic_values")
                or metadata.get("vaccination_details")
                or metadata.get("standalone_medications")
                or metadata.get("recommendations")
            )
            if has_metadata:
                logger.warning(
                    "No preventive items extracted but metadata present — "
                    "marking as partially_extracted: document_id=%s",
                    str(document_id),
                )
                document.extraction_status = "partially_extracted"
            else:
                logger.info(
                    "No preventive items or metadata extracted from document: %s",
                    str(document_id),
                )
                document.extraction_status = "success"
            # Re-apply document-level metadata fields before committing
            # (conditions/contacts loops above may have called db.rollback(),
            # expiring the document object and losing earlier assignments).
            if metadata.get("diagnostic_summary"):
                document.diagnostic_summary = str(metadata["diagnostic_summary"])[:2000]
            if non_diet_recs:
                document.non_diet_recommendations = non_diet_recs
            db.commit()
            return results

        # --- Step 3 & 4: Process each extracted item ---
        # Pre-load all preventive masters for this species once
        # to avoid per-item DB queries (N+1 prevention).
        species_masters = _load_species_masters(db, pet.species)

        # Build a lookup from tracked item_name → vaccination_detail dict so
        # that we can attach rich metadata (dose, manufacturer, batch, etc.)
        # to the preventive record after it is created.
        # Mapping direction: vaccine_name from detail → item_name via
        # _VACCINE_DETAIL_TO_ITEM, then invert so we can look up by item_name.
        _vacc_meta_by_item: dict[str, dict] = {}
        for _vd in metadata.get("vaccination_details", []):
            if not isinstance(_vd, dict):
                continue
            _vn = str(_vd.get("vaccine_name") or _vd.get("vaccine_name_raw") or "").strip().lower()
            for _keyword, _mapped_item in _VACCINE_DETAIL_TO_ITEM.items():
                if _keyword in _vn and _mapped_item not in _vacc_meta_by_item:
                    _vacc_meta_by_item[_mapped_item] = _vd
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
                    record = create_preventive_record(
                        db=db,
                        pet_id=pet.id,
                        preventive_master_id=master.id,
                        last_done_date=last_done_date,
                    )

                    # Attach vaccination metadata when available.
                    # Prefer the matched vaccination_detail; fall back to
                    # item-level batch_number / dose fields from the items array.
                    _vacc_detail = _vacc_meta_by_item.get(item_name)
                    _meta: dict = {}
                    if _vacc_detail:
                        # Strip fields already stored elsewhere (date, next_due_date)
                        # and null values to keep the JSONB compact.
                        _skip = {"vaccine_name", "next_due_date", "date", "administered_date", "last_done_date"}
                        _meta = {k: v for k, v in _vacc_detail.items() if k not in _skip and v is not None}
                    # Merge item-level fields not already captured from the detail.
                    if item.get("batch_number") and not _meta.get("batch_number"):
                        _meta["batch_number"] = item["batch_number"]
                    if item.get("dose") and not _meta.get("dose"):
                        _meta["dose"] = item["dose"]
                    if _meta:
                        record.vaccination_metadata = _meta
                        db.flush()

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
        # Re-apply document-level metadata fields here (in addition to the
        # earlier assignments) to guard against SQLAlchemy object expiry.
        # Conditions / contacts / items loops each call db.rollback() on
        # individual failures, which expires all session-tracked objects
        # including `document`. Any attributes set before those rollbacks
        # are cleared from the in-memory dirty state and would be silently
        # dropped on the final commit. Re-applying them here ensures they
        # are always written, regardless of how many per-item rollbacks fired.
        if metadata.get("diagnostic_summary"):
            document.diagnostic_summary = str(metadata["diagnostic_summary"])[:2000]
        if non_diet_recs:
            document.non_diet_recommendations = non_diet_recs
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

        # --- Step 6: Pre-warm dashboard cache ---
        # Publishes a precompute job to the dashboard.precompute queue.
        # The in-process consumer calls precompute_dashboard_enrichments() so the
        # next dashboard load reads from DB with no API calls.
        # Falls back to a direct asyncio task if the queue is unavailable.
        try:
            from app.services import queue_service as _qs
            _published = await _qs.publish_precompute_job(
                pet_id=str(pet.id),
                user_id=str(pet.user_id) if hasattr(pet, "user_id") else "",
            )
            if not _published:
                import asyncio as _asyncio
                from app.services.precompute_service import precompute_dashboard_enrichments
                _asyncio.create_task(precompute_dashboard_enrichments(str(pet.id)))
        except Exception as _precompute_exc:
            logger.warning("precompute scheduling failed: %s", _precompute_exc)

        # Note: Post-extraction WhatsApp nudges are now sent by the daily cron
        # (nudge_scheduler.run_nudge_scheduler) instead of per-upload triggers.

    except Exception as e:
        # Classify the failure so callers know whether to retry.
        error_class = _classify_extraction_error(e)
        results["status"] = "failed"
        results["errors"].append(f"Extraction failed ({error_class}): {str(e)}")

        # Increment retry counter regardless of error class.
        try:
            document.retry_count = (document.retry_count or 0) + 1
        except Exception:
            pass

        if error_class == "retryable" and (document.retry_count or 0) < EXTRACTION_MAX_AUTO_RETRIES:
            logger.warning(
                "Retryable extraction failure (attempt %d/%d): "
                "document_id=%s, error=%s",
                document.retry_count,
                EXTRACTION_MAX_AUTO_RETRIES,
                str(document_id),
                str(e),
            )
        else:
            logger.error(
                "Permanent extraction failure (attempt %d, class=%s): "
                "document_id=%s, error=%s",
                document.retry_count or 1,
                error_class,
                str(document_id),
                str(e),
            )

        # Persist 'failed' status + updated retry_count. If commit fails (broken
        # session), rollback and retry with a fresh transaction. Without this,
        # the document stays 'pending' and gets ghost-re-extracted next batch.
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
