"""
Unit tests for the condition-vs-medication category contract in gpt_extraction.

Covers:
  - _is_likely_medication_name() guard: correctly rejects drug-like strings and
    accepts real condition names.
  - _validate_extraction_json(): conditions array is passed through in metadata
    unchanged (filtering happens later in extract_and_process_document).
"""

import json

from app.services import gpt_extraction
from app.services.gpt_extraction import (
    _condition_matches_extracted_medication_name,
    _is_likely_medication_name,
)

# ---------------------------------------------------------------------------
# _is_likely_medication_name
# ---------------------------------------------------------------------------


class TestIsLikelyMedicationName:
    """Guard function: rejects drug/product names, accepts disease names."""

    # --- Should return True (medication) ---

    def test_rejects_name_with_mg_dosage(self) -> None:
        assert _is_likely_medication_name("Simparica 50mg") is True

    def test_rejects_name_with_ml_dosage(self) -> None:
        assert _is_likely_medication_name("Amoxicillin 250ml") is True

    def test_rejects_name_with_mcg_dosage(self) -> None:
        assert _is_likely_medication_name("Levothyroxine 100mcg") is True

    def test_rejects_capsule_delivery_form(self) -> None:
        assert _is_likely_medication_name("Doxycycline Capsule") is True

    def test_rejects_tablet_delivery_form(self) -> None:
        assert _is_likely_medication_name("Metronidazole Tablet") is True

    def test_rejects_syrup_delivery_form(self) -> None:
        assert _is_likely_medication_name("Amoxicillin Syrup") is True

    def test_rejects_drops_delivery_form(self) -> None:
        assert _is_likely_medication_name("Sofradex Drops") is True

    def test_rejects_spray_delivery_form(self) -> None:
        assert _is_likely_medication_name("Fipronil Spray") is True

    def test_rejects_ointment_delivery_form(self) -> None:
        assert _is_likely_medication_name("Neosporin Ointment") is True

    def test_rejects_cream_delivery_form(self) -> None:
        assert _is_likely_medication_name("Antifungal Cream") is True

    def test_rejects_suspension_delivery_form(self) -> None:
        assert _is_likely_medication_name("Fenbendazole Suspension") is True

    def test_rejects_solution_delivery_form(self) -> None:
        assert _is_likely_medication_name("Chlorhexidine Solution") is True

    def test_rejects_mixed_case_tablet(self) -> None:
        # Case-insensitive match
        assert _is_likely_medication_name("NexGard TABLET") is True

    def test_rejects_numeric_dosage_no_unit_word(self) -> None:
        # "50mg" alone without brand name still matches
        assert _is_likely_medication_name("50mg tablet") is True

    # --- Should return False (real condition) ---

    def test_accepts_hip_dysplasia(self) -> None:
        assert _is_likely_medication_name("Hip Dysplasia") is False

    def test_accepts_diabetes_mellitus(self) -> None:
        assert _is_likely_medication_name("Diabetes Mellitus") is False

    def test_accepts_otitis_externa(self) -> None:
        assert _is_likely_medication_name("Otitis Externa") is False

    def test_accepts_skin_allergy(self) -> None:
        assert _is_likely_medication_name("Skin Allergy") is False

    def test_accepts_hypothyroidism(self) -> None:
        assert _is_likely_medication_name("Hypothyroidism") is False

    def test_accepts_chronic_kidney_disease(self) -> None:
        assert _is_likely_medication_name("Chronic Kidney Disease") is False

    def test_accepts_arthritis(self) -> None:
        assert _is_likely_medication_name("Arthritis") is False

    def test_accepts_flea_infestation(self) -> None:
        # "Flea Infestation" is a condition name — does not contain dosage or form words
        assert _is_likely_medication_name("Flea Infestation") is False

    def test_accepts_gastroenteritis(self) -> None:
        assert _is_likely_medication_name("Gastroenteritis") is False

    def test_accepts_empty_string(self) -> None:
        # Edge case: empty string should not match
        assert _is_likely_medication_name("") is False

    # --- False-positive regression anchors ---
    # These are real veterinary condition names that must NOT be rejected.
    # They contain words ("Oral", "Injection") that are also found in drug contexts.

    def test_accepts_oral_candidiasis(self) -> None:
        # "Oral" is an anatomical prefix here, not a delivery route
        assert _is_likely_medication_name("Oral Candidiasis") is False

    def test_accepts_oral_squamous_cell_carcinoma(self) -> None:
        assert _is_likely_medication_name("Oral Squamous Cell Carcinoma") is False

    def test_accepts_injection_site_sarcoma(self) -> None:
        # FISS — common feline oncology diagnosis
        assert _is_likely_medication_name("Injection Site Sarcoma") is False

    def test_accepts_injection_site_reaction(self) -> None:
        assert _is_likely_medication_name("Injection Site Reaction") is False


# ---------------------------------------------------------------------------
# _validate_extraction_json — conditions pass-through
# ---------------------------------------------------------------------------


class TestValidateExtractionJsonConditionsPassthrough:
    """_validate_extraction_json must pass raw conditions into metadata unchanged.

    The medication-name guard runs later in extract_and_process_document, not here.
    """

    def test_conditions_with_medication_name_reach_metadata_unfiltered(self) -> None:
        """Conditions are stored in metadata as-is; the guard is downstream."""
        raw_json = json.dumps(
            {
                "document_name": "Vet Prescription",
                "document_type": "pet_medical",
                "document_category": "Prescription",
                "diagnostic_summary": None,
                "items": [],
                "conditions": [
                    {
                        "condition_name": "Simparica 50mg",  # bad GPT output
                        "condition_type": "episodic",
                        "diagnosis": None,
                        "diagnosed_at": None,
                        "medications": [],
                        "monitoring": [],
                    }
                ],
                "contacts": [],
            }
        )
        _items, _doc_name, _pet_name, metadata = gpt_extraction._validate_extraction_json(raw_json)

        # Passed through unchanged — filtering is the caller's responsibility.
        assert len(metadata["conditions"]) == 1
        assert metadata["conditions"][0]["condition_name"] == "Simparica 50mg"

    def test_conditions_with_real_disease_names_reach_metadata(self) -> None:
        raw_json = json.dumps(
            {
                "document_name": "Health Report",
                "document_type": "pet_medical",
                "document_category": "Other",
                "diagnostic_summary": None,
                "items": [],
                "conditions": [
                    {
                        "condition_name": "Hypothyroidism",
                        "condition_type": "chronic",
                        "diagnosis": "Low T4 levels confirmed",
                        "diagnosed_at": "2024-03-01",
                        "medications": [{"name": "Levothyroxine", "dose": "0.1mg", "frequency": "Once daily", "route": "oral"}],
                        "monitoring": [{"name": "Thyroid Panel", "frequency": "Every 6 months"}],
                    }
                ],
                "contacts": [],
            }
        )
        _items, _doc_name, _pet_name, metadata = gpt_extraction._validate_extraction_json(raw_json)

        assert len(metadata["conditions"]) == 1
        cond = metadata["conditions"][0]
        assert cond["condition_name"] == "Hypothyroidism"
        assert cond["condition_type"] == "chronic"
        assert cond["medications"][0]["name"] == "Levothyroxine"

    def test_empty_conditions_array_preserved(self) -> None:
        raw_json = json.dumps(
            {
                "document_name": "Vaccination Certificate",
                "document_type": "pet_medical",
                "document_category": "Vaccination",
                "diagnostic_summary": None,
                "items": [],
                "conditions": [],
                "contacts": [],
            }
        )
        _items, _doc_name, _pet_name, metadata = gpt_extraction._validate_extraction_json(raw_json)

        assert metadata["conditions"] == []

    def test_non_list_conditions_defaults_to_empty(self) -> None:
        """Malformed GPT output — conditions is a string, not a list."""
        raw_json = json.dumps(
            {
                "document_name": "Doc",
                "document_type": "pet_medical",
                "document_category": "Other",
                "diagnostic_summary": None,
                "items": [],
                "conditions": "none",  # malformed
                "contacts": [],
            }
        )
        _items, _doc_name, _pet_name, metadata = gpt_extraction._validate_extraction_json(raw_json)

        # Non-list is not stored — defaults to []
        assert metadata["conditions"] == []


def test_condition_matches_extracted_medication_name_from_condition_meds() -> None:
    raw_condition = {
        "condition_name": "Simparica",
        "medications": [{"name": "Simparica"}],
    }

    assert _condition_matches_extracted_medication_name(
        raw_condition["condition_name"],
        raw_condition,
        [],
    ) is True


def test_condition_matches_extracted_medication_name_from_preventive_meds() -> None:
    raw_condition = {
        "condition_name": "Simparica",
        "medications": [],
    }
    preventive_meds = [{"name": "Simparica"}]

    assert _condition_matches_extracted_medication_name(
        raw_condition["condition_name"],
        raw_condition,
        preventive_meds,
    ) is True
