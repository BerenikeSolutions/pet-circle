import os
from types import SimpleNamespace

os.environ.setdefault("APP_ENV", "test")

from app.services import onboarding


def test_resolve_vaccine_item_name_maps_kennel_cough_variants() -> None:
    assert onboarding._resolve_vaccine_item_name("Nobivac KC") == "Kennel Cough (Nobivac KC)"
    assert (
        onboarding._resolve_vaccine_item_name("Kennel Cough (Nobivac KC)")
        == "Kennel Cough (Nobivac KC)"
    )


def test_resolve_vaccine_item_name_maps_ccov_variants() -> None:
    assert onboarding._resolve_vaccine_item_name("CCoV") == "Canine Coronavirus (CCoV)"
    assert (
        onboarding._resolve_vaccine_item_name("Canine Coronavirus (CCoV)")
        == "Canine Coronavirus (CCoV)"
    )


def test_annual_vaccine_query_returns_only_canonical_core_vaccines() -> None:
    class _FakeQuery:
        def __init__(self, rows):
            self.rows = rows
            self.filter_args = ()

        def filter(self, *args):
            self.filter_args = args
            return self

        def all(self):
            return self.rows

    class _FakeDB:
        def __init__(self, rows):
            self.query_obj = _FakeQuery(rows)

        def query(self, _model):
            return self.query_obj

    rows = [
        SimpleNamespace(item_name="Rabies (Nobivac RL)", is_core=True),
        SimpleNamespace(item_name="Kennel Cough (Nobivac KC)", is_core=True),
        SimpleNamespace(item_name="Canine Coronavirus (CCoV)", is_core=True),
        SimpleNamespace(item_name="Deworming", is_core=True),
        SimpleNamespace(item_name="Leptospirosis", is_core=True),
    ]
    db = _FakeDB(rows)

    result = onboarding._essential_annual_vaccine_masters(db, "dog")

    assert [row.item_name for row in result] == [
        "Rabies (Nobivac RL)",
        "Kennel Cough (Nobivac KC)",
        "Canine Coronavirus (CCoV)",
    ]


def test_normalize_preventive_medicine_moves_dewormer_out_of_flea_tick() -> None:
    parsed = {
        "vaccines": None,
        "vaccine_specifics": [],
        "deworming": None,
        "flea_tick": {"date": "January 2026", "medicine": "Drontal Plus"},
        "blood_test": None,
        "missing": ["vaccines", "deworming", "blood_test"],
    }

    normalized = onboarding._normalize_preventive_medicine_categories(parsed)

    assert normalized["flea_tick"] is None
    assert normalized["deworming"] == {
        "date": "January 2026",
        "medicine": "Drontal Plus",
        "prevention_targets": [],
    }


def test_normalize_preventive_medicine_copies_dual_use_to_both_categories_from_targets() -> None:
    parsed = {
        "vaccines": None,
        "vaccine_specifics": [],
        "deworming": None,
        "flea_tick": {
            "date": "February 2026",
            "medicine": "Any Brand",
            "prevention_targets": ["flea_tick", "deworming"],
        },
        "blood_test": None,
        "missing": ["vaccines", "deworming", "blood_test"],
    }

    normalized = onboarding._normalize_preventive_medicine_categories(parsed)

    assert normalized["flea_tick"] == {
        "date": "February 2026",
        "medicine": "Any Brand",
        "prevention_targets": ["flea_tick", "deworming"],
    }
    assert normalized["deworming"] == {
        "date": "February 2026",
        "medicine": "Any Brand",
        "prevention_targets": ["flea_tick", "deworming"],
    }


def test_normalize_preventive_medicine_backfills_date_when_target_already_has_medicine() -> None:
    parsed = {
        "vaccines": None,
        "vaccine_specifics": [],
        "deworming": {"date": None, "medicine": "Drontal Plus"},
        "flea_tick": {"date": "January 2026", "medicine": "Drontal Plus"},
        "blood_test": None,
        "missing": ["vaccines", "deworming", "blood_test"],
    }

    normalized = onboarding._normalize_preventive_medicine_categories(parsed)

    assert normalized["deworming"] == {
        "date": "January 2026",
        "medicine": "Drontal Plus",
        "prevention_targets": [],
    }
    assert normalized["flea_tick"] is None


def test_normalize_preventive_medicine_recomputes_missing_after_remap() -> None:
    parsed = {
        "vaccines": None,
        "vaccine_specifics": [],
        "deworming": None,
        "flea_tick": {"date": "January 2026", "medicine": "Drontal Plus"},
        "blood_test": None,
        "missing": ["vaccines", "deworming", "blood_test"],
    }

    normalized = onboarding._normalize_preventive_medicine_categories(parsed)

    assert normalized["missing"] == ["vaccines", "flea_tick", "blood_test"]


def test_enrich_preventive_categories_from_catalog_backfills_missing_bucket() -> None:
    class _FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *_args):
            return self

        def all(self):
            return self.rows

    class _FakeDB:
        def __init__(self):
            self.rows = [
                ("flea_tick", "Zoetis", "Simparica Trio"),
                ("deworming", "Zoetis", "Simparica Trio"),
            ]

        def query(self, *_cols):
            return _FakeQuery(self.rows)

    parsed = {
        "vaccines": None,
        "vaccine_specifics": [],
        "deworming": None,
        "flea_tick": {"date": "February 2026", "medicine": "Simparica Trio", "prevention_targets": []},
        "blood_test": None,
        "missing": ["vaccines", "deworming", "blood_test"],
    }

    enriched = onboarding._enrich_preventive_categories_from_catalog(_FakeDB(), parsed)

    assert enriched["deworming"] == {
        "date": "February 2026",
        "medicine": "Simparica Trio",
        "prevention_targets": [],
    }


def test_all_of_the_above_fills_missing_preventive_categories() -> None:
    parsed = {
        "vaccines": None,
        "vaccine_specifics": [],
        "deworming": {"date": "March 2026", "medicine": "Simparica", "prevention_targets": ["deworming", "flea_tick"]},
        "flea_tick": {"date": "March 2026", "medicine": "Simparica", "prevention_targets": ["deworming", "flea_tick"]},
        "blood_test": "March 2026",
        "missing": ["vaccines"],
    }

    enriched = onboarding._apply_all_preventive_categories_intent("all of the above last month", parsed)
    normalized = onboarding._normalize_preventive_medicine_categories(enriched)

    assert normalized["vaccines"] == "March 2026"
    assert normalized["missing"] == []


def test_all_of_the_above_with_exclusion_does_not_fill_excluded_category() -> None:
    parsed = {
        "vaccines": None,
        "vaccine_specifics": [],
        "deworming": {"date": "March 2026", "medicine": "Simparica", "prevention_targets": ["deworming", "flea_tick"]},
        "flea_tick": {"date": "March 2026", "medicine": "Simparica", "prevention_targets": ["deworming", "flea_tick"]},
        "blood_test": "March 2026",
        "missing": ["vaccines"],
    }

    enriched = onboarding._apply_all_preventive_categories_intent(
        "all of the above except vaccines",
        parsed,
    )
    normalized = onboarding._normalize_preventive_medicine_categories(enriched)

    assert normalized["vaccines"] is None
    assert "vaccines" in normalized["missing"]


def test_all_of_the_above_does_not_override_explicit_vaccine_none() -> None:
    parsed = {
        "vaccines": "none",
        "vaccine_specifics": [],
        "deworming": {"date": "March 2026", "medicine": "Simparica", "prevention_targets": ["deworming", "flea_tick"]},
        "flea_tick": {"date": "March 2026", "medicine": "Simparica", "prevention_targets": ["deworming", "flea_tick"]},
        "blood_test": "March 2026",
        "missing": ["vaccines"],
    }

    enriched = onboarding._apply_all_preventive_categories_intent("all of the above last month", parsed)
    normalized = onboarding._normalize_preventive_medicine_categories(enriched)

    assert normalized["vaccines"] == "none"
    assert "vaccines" not in normalized["missing"]


def test_all_of_the_above_not_blood_test_does_not_fill_blood_test() -> None:
    parsed = {
        "vaccines": "March 2026",
        "vaccine_specifics": [],
        "deworming": {"date": "March 2026", "medicine": "Simparica", "prevention_targets": ["deworming", "flea_tick"]},
        "flea_tick": {"date": "March 2026", "medicine": "Simparica", "prevention_targets": ["deworming", "flea_tick"]},
        "blood_test": None,
        "missing": ["blood_test"],
    }

    enriched = onboarding._apply_all_preventive_categories_intent("all of the above not blood test", parsed)
    normalized = onboarding._normalize_preventive_medicine_categories(enriched)

    assert normalized["blood_test"] is None
    assert "blood_test" in normalized["missing"]
