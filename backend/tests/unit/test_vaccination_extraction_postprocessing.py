import json

from app.services.gpt_extraction import (
    _pet_name_matches_document_name,
    _select_best_doctor_name,
    _validate_extraction_json,
)


def test_vaccination_category_filters_annual_checkup_items() -> None:
    raw = json.dumps(
        {
            "document_name": "Pet Vaccination & Health Checkup",
            "document_type": "pet_medical",
            "document_category": "Vaccination",
            "items": [
                {"item_name": "Core Vaccine", "last_done_date": "28/03/2023"},
                {"item_name": "Annual Checkup", "last_done_date": "28/03/2023"},
                {"item_name": "Rabies Vaccine", "last_done_date": "23/11/2024"},
            ],
        }
    )

    items, _doc_name, _pet_name, _metadata = _validate_extraction_json(raw)

    assert [item["item_name"] for item in items] == ["Core Vaccine", "Rabies Vaccine"]


def test_vaccination_details_next_due_date_is_normalized() -> None:
    raw = json.dumps(
        {
            "document_name": "Pet Vaccination & Health Checkup",
            "document_type": "pet_medical",
            "document_category": "Vaccination",
            "items": [
                {"item_name": "Rabies Vaccine", "last_done_date": "23/11/2024"},
            ],
            "vaccination_details": [
                {"vaccine_name": "Rabies", "next_due_date": "06/05/2026"},
                {"vaccine_name": "Core", "next_due_date": "not-a-date"},
            ],
        }
    )

    _items, _doc_name, _pet_name, metadata = _validate_extraction_json(raw)

    assert metadata["vaccination_details"][0]["next_due_date"] == "2026-05-06"
    assert metadata["vaccination_details"][1]["next_due_date"] is None


def test_unmapped_vaccine_is_kept_as_extra_vaccine() -> None:
    raw = json.dumps(
        {
            "document_name": "Dog Vaccination Card",
            "document_type": "pet_medical",
            "document_category": "Vaccination",
            "items": [],
            "vaccination_details": [
                {"vaccine_name": "Nobivac RL", "date": "06/05/2025"},
                {"vaccine_name": "Experimental ZetaVax", "date": "07/05/2025"},
            ],
        }
    )

    items, _doc_name, _pet_name, metadata = _validate_extraction_json(raw)

    assert any(item["item_name"] == "Rabies (Nobivac RL)" for item in items)
    assert metadata["extra_vaccines"] == [
        {
            "vaccine_name": "Experimental ZetaVax",
            "date": "07/05/2025",
            "next_due_date": None,
            "dose": None,
            "batch_number": None,
        }
    ]


def test_dog_vaccine_aliases_map_to_required_options() -> None:
    raw = json.dumps(
        {
            "document_name": "Dog Vaccination Card",
            "document_type": "pet_medical",
            "document_category": "Vaccination",
            "items": [],
            "vaccination_details": [
                {"vaccine_name": "Nobivac DHPPi", "date": "01/04/2025"},
                {"vaccine_name": "Nobivac RL", "date": "01/04/2025"},
                {"vaccine_name": "Nobivac KC", "date": "01/04/2025"},
                {"vaccine_name": "CCoV", "date": "01/04/2025"},
            ],
        }
    )

    items, _doc_name, _pet_name, metadata = _validate_extraction_json(raw)

    names = [item["item_name"] for item in items]
    assert "DHPPi" in names
    assert "Rabies (Nobivac RL)" in names
    assert "Kennel Cough (Nobivac KC)" in names
    assert "Canine Coronavirus (CCoV)" in names
    assert metadata["extra_vaccines"] == []


def test_combined_vaccine_detail_maps_multiple_vaccines() -> None:
    raw = json.dumps(
        {
            "document_name": "Dog Vaccination Card",
            "document_type": "pet_medical",
            "document_category": "Vaccination",
            "items": [],
            "vaccination_details": [
                {"vaccine_name": "Nobivac DHPPi + Nobivac KC + CCoV", "date": "01/04/2025"},
            ],
        }
    )

    items, _doc_name, _pet_name, metadata = _validate_extraction_json(raw)

    names = {item["item_name"] for item in items}
    assert names == {"DHPPi", "Kennel Cough (Nobivac KC)", "Canine Coronavirus (CCoV)"}
    assert metadata["extra_vaccines"] == []


def test_pet_name_matching_accepts_alias_style_extraction() -> None:
    assert _pet_name_matches_document_name("VEER / ZAYN", "Zayn") is True


def test_select_best_doctor_name_prefers_vaccination_administered_by() -> None:
    selected = _select_best_doctor_name(
        metadata_doctor_name="Owner Name",
        extracted_items=[{"doctor_name": "C/O Ashita Arora"}],
        vaccination_details=[{"administered_by": "Dr. D. P. Chaudhari"}],
        pet_name="Zayn",
    )

    assert selected == "Dr. D. P. Chaudhari"
