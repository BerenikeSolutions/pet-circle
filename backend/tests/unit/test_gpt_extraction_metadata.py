import json
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services import gpt_extraction


def test_validate_extraction_preserves_diagnostic_values() -> None:
    raw_json = json.dumps(
        {
            "document_name": "Urine Test Report",
            "document_type": "pet_medical",
            "document_category": "Diagnostic",
            "diagnostic_summary": "Mild protein detected.",
            "diagnostic_values": [
                {
                    "test_type": "urine",
                    "parameter_name": "Urine pH",
                    "value_numeric": 7.5,
                    "value_text": None,
                    "unit": None,
                    "reference_range": "6.0-7.0",
                    "status_flag": "high",
                    "observed_at": "2025-02-12",
                }
            ],
            "items": [],
        }
    )

    items, document_name, extracted_pet_name, metadata = gpt_extraction._validate_extraction_json(raw_json)

    assert items == []
    assert document_name == "Urine Test Report"
    assert extracted_pet_name is None
    assert metadata["document_category"] == "Blood Report"
    assert metadata["diagnostic_values"][0]["parameter_name"] == "Urine pH"


def test_normalize_document_category_accepts_plural_and_case_variants() -> None:
    assert gpt_extraction._normalize_document_category("prescriptions") == "Prescription"
    assert gpt_extraction._normalize_document_category("VACCINATIONS") == "Vaccination"
    assert gpt_extraction._normalize_document_category("lab") == "Blood Report"


def test_infer_document_category_uses_filename_when_gpt_misses_prescription() -> None:
    category = gpt_extraction._infer_document_category(
        document_name="Health Checkup Report",
        file_path="uploads/Prescription_Chavan_12_02_25.jpg",
        items=[
            {"item_name": "Annual Checkup", "last_done_date": "2025-02-12"},
            {"item_name": "Preventive Blood Test", "last_done_date": "2025-02-12"},
        ],
        vaccination_details=[],
        diagnostic_values=[],
    )

    assert category == "Prescription"


def test_resolve_document_category_overrides_other_with_inferred_diagnostic() -> None:
    resolved = gpt_extraction._resolve_document_category("Other", "Diagnostic")

    assert resolved == "Diagnostic"


def test_resolve_document_category_forces_prescription_when_clinical_exam_present() -> None:
    # Reproduces the Prescription_Chavan_12_02_25.jpg case: GPT sees "Blood Test"
    # on a handwritten vet prescription and returns "Blood Report", but the
    # extracted clinical_exam (weight, temperature) proves it's a vet visit.
    resolved = gpt_extraction._resolve_document_category(
        "Blood Report",
        "Blood Report",
        document_name="General Examination",
        file_path="uploads/anon_name.jpg",
        clinical_exam={"weight_kg": 29, "temperature_c": 38.78, "clinical_findings": "Anal Glands Cleaned"},
        conditions=[],
    )

    assert resolved == "Prescription"


def test_resolve_document_category_forces_prescription_when_conditions_present() -> None:
    resolved = gpt_extraction._resolve_document_category(
        "Blood Report",
        "Blood Report",
        document_name="General Examination",
        file_path="uploads/anon_name.jpg",
        clinical_exam=None,
        conditions=[{"diagnosis": "Skin infection", "medications": [{"name": "Cefpodoxime"}]}],
    )

    assert resolved == "Prescription"


def test_resolve_document_category_ignores_empty_clinical_exam() -> None:
    # A clinical_exam dict where every field is None must NOT trigger the override,
    # otherwise lab reports that GPT wraps in an empty clinical_exam shell would
    # flip to Prescription.
    resolved = gpt_extraction._resolve_document_category(
        "Blood Report",
        "Blood Report",
        document_name="CBC Report",
        file_path="uploads/CBC_12_02_25.pdf",
        clinical_exam={"weight_kg": None, "temperature_c": None, "clinical_findings": None},
        conditions=[],
    )

    assert resolved == "Blood Report"


def test_extract_date_from_filename_supports_sample_report_names() -> None:
    extracted = gpt_extraction._extract_date_from_filename("uploads/CBC_12_02_25.pdf")

    assert extracted == "2025-02-12"


def test_derive_blood_test_fallback_items_uses_filename_for_cbc_reports() -> None:
    items = gpt_extraction._derive_blood_test_fallback_items(
        extracted_items=[],
        document_name="Blood Test Report",
        file_path="uploads/CBC_12_02_25.pdf",
        document_category="Diagnostic",
        diagnostic_values=[],
    )

    assert items == [{"item_name": "Preventive Blood Test", "last_done_date": "2025-02-12"}]


def test_derive_blood_test_fallback_items_prefers_observed_blood_date() -> None:
    items = gpt_extraction._derive_blood_test_fallback_items(
        extracted_items=[],
        document_name="Blood Test Report",
        file_path="uploads/Blood_29_01_25.pdf",
        document_category="Diagnostic",
        diagnostic_values=[
            {
                "test_type": "blood",
                "parameter_name": "Creatinine",
                "observed_at": "2025-01-28",
            }
        ],
    )

    assert items == [{"item_name": "Preventive Blood Test", "last_done_date": "2025-01-28"}]


def test_validate_extraction_salvages_metadata_from_malformed_json() -> None:
    raw_json = (
        '{'
        '"document_name": "Blood Test Report", '
        '"document_type": "pet_medical", '
        '"document_category": "Diagnostic", '
        '"pet_name": "ZAYN", '
        '"doctor_name": "Dr. D. P. Chaudhari", '
        '"clinic_name": "UNIQUE LAB NEW", '
        '"diagnostic_values": ['
    )

    items, document_name, extracted_pet_name, metadata = gpt_extraction._validate_extraction_json(raw_json)

    assert items == []
    assert document_name == "Blood Test Report"
    assert extracted_pet_name == "ZAYN"
    assert metadata["document_category"] == "Blood Report"
    assert metadata["doctor_name"] == "Dr. D. P. Chaudhari"
    assert metadata["clinic_name"] == "UNIQUE LAB NEW"


def test_validate_extraction_skips_future_last_done_dates() -> None:
    future_date = (datetime.utcnow().date() + timedelta(days=30)).isoformat()
    raw_json = json.dumps(
        {
            "document_name": "Vaccination Certificate",
            "document_type": "pet_medical",
            "document_category": "Vaccination",
            "items": [
                {"item_name": "Rabies Vaccine", "last_done_date": future_date},
                {"item_name": "Core Vaccine", "last_done_date": "2025-05-06"},
            ],
        }
    )

    items, _, _, _ = gpt_extraction._validate_extraction_json(raw_json)

    assert items == [{"item_name": "Core Vaccine", "last_done_date": "2025-05-06"}]


def test_get_preventive_categories_for_medicine_supports_single_and_dual_use() -> None:
    assert gpt_extraction._get_preventive_categories_for_medicine("Drontal Plus") == {"deworming"}
    assert gpt_extraction._get_preventive_categories_for_medicine("Frontline Spot-On") == {"flea_tick"}
    assert gpt_extraction._get_preventive_categories_for_medicine("NexGard Spectra chew") == {
        "deworming",
        "flea_tick",
    }


def test_derive_items_from_medication_brands_expands_dual_use_medicine() -> None:
    preventive_medications = [
        {
            "name": "Simparica",
            "start_date": "2026-01-05",
            "prevention_targets": ["deworming", "flea_tick"],
        }
    ]

    derived = gpt_extraction._derive_items_from_medication_brands([], [], preventive_medications)
    names = {item["item_name"] for item in derived}

    assert names == {"Deworming", "Tick/Flea"}


def test_get_preventive_categories_for_medicine_returns_dual_use_for_simparica() -> None:
    assert gpt_extraction._get_preventive_categories_for_medicine("Simparica") == {"flea_tick", "deworming"}


def test_validate_extraction_uses_preventive_medications_targets_for_simparica() -> None:
    raw_json = json.dumps(
        {
            "document_name": "Preventive Medication Record",
            "document_type": "pet_medical",
            "document_category": "Prescription",
            "items": [],
            "conditions": [],
            "preventive_medications": [
                {
                    "name": "Simparica",
                    "start_date": "2026-01-05",
                    "prevention_targets": ["flea_tick", "deworming"],
                }
            ],
        }
    )

    items, _, _, metadata = gpt_extraction._validate_extraction_json(raw_json)

    assert {item["item_name"] for item in items} == {"Deworming", "Tick/Flea"}
    assert len(metadata["preventive_medications"]) == 1


def test_validate_extraction_skips_future_preventive_medication_dates() -> None:
    future_date = (datetime.utcnow().date() + timedelta(days=10)).isoformat()
    raw_json = json.dumps(
        {
            "document_name": "Preventive Medication Record",
            "document_type": "pet_medical",
            "document_category": "Prescription",
            "items": [],
            "conditions": [],
            "preventive_medications": [
                {
                    "name": "Simparica",
                    "start_date": future_date,
                    "prevention_targets": ["flea_tick", "deworming"],
                }
            ],
        }
    )

    items, _, _, _ = gpt_extraction._validate_extraction_json(raw_json)

    assert items == []


def test_get_preventive_categories_for_medicine_ignores_non_string_input() -> None:
    assert gpt_extraction._get_preventive_categories_for_medicine(None) == set()
    assert gpt_extraction._get_preventive_categories_for_medicine(123) == set()


def test_should_include_puppy_series_for_pet_uses_age_and_species() -> None:
    today = datetime.utcnow().date()

    young_dog = SimpleNamespace(species="dog", dob=today - timedelta(days=120))
    adult_dog = SimpleNamespace(species="dog", dob=today - timedelta(days=800))
    dog_without_dob = SimpleNamespace(species="dog", dob=None)
    cat = SimpleNamespace(species="cat", dob=today - timedelta(days=120))
    future_dob_dog = SimpleNamespace(species="dog", dob=today + timedelta(days=10))

    assert gpt_extraction._should_include_puppy_series_for_pet(young_dog) is True
    assert gpt_extraction._should_include_puppy_series_for_pet(adult_dog) is False
    assert gpt_extraction._should_include_puppy_series_for_pet(dog_without_dob) is False
    assert gpt_extraction._should_include_puppy_series_for_pet(cat) is False
    assert gpt_extraction._should_include_puppy_series_for_pet(future_dob_dog) is False


def test_filter_non_applicable_puppy_series_removes_puppy_dose_rows_for_adult_flow() -> None:
    masters = [
        SimpleNamespace(item_name="DHPPi", recurrence_days=365),
        SimpleNamespace(item_name="Kennel Cough (Nobivac KC)", recurrence_days=365),
        SimpleNamespace(item_name="DHPPi 1st Dose", recurrence_days=36500),
        SimpleNamespace(item_name="Puppy Booster", recurrence_days=36500),
    ]

    filtered = gpt_extraction._filter_non_applicable_puppy_series(
        masters,
        include_puppy_series=False,
    )

    names = [m.item_name for m in filtered]
    assert names == ["DHPPi", "Kennel Cough (Nobivac KC)"]
