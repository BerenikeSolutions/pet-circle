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


def test_annual_vaccine_query_does_not_restrict_to_essential_category(monkeypatch) -> None:
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
        SimpleNamespace(item_name="Rabies (Nobivac RL)"),
        SimpleNamespace(item_name="Kennel Cough (Nobivac KC)"),
        SimpleNamespace(item_name="Canine Coronavirus (CCoV)"),
        SimpleNamespace(item_name="Deworming"),
    ]
    db = _FakeDB(rows)

    monkeypatch.setattr(
        "app.services.nudge_engine._classify_item",
        lambda name: "vaccine" if "deworm" not in (name or "").lower() else "deworming",
    )

    result = onboarding._essential_annual_vaccine_masters(db, "dog")

    assert [row.item_name for row in result] == [
        "Rabies (Nobivac RL)",
        "Kennel Cough (Nobivac KC)",
        "Canine Coronavirus (CCoV)",
    ]
    assert not any("category" in str(expr).lower() for expr in db.query_obj.filter_args)


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
    }


def test_normalize_preventive_medicine_copies_dual_use_to_both_categories() -> None:
    parsed = {
        "vaccines": None,
        "vaccine_specifics": [],
        "deworming": None,
        "flea_tick": {"date": "February 2026", "medicine": "Simparica Trio"},
        "blood_test": None,
        "missing": ["vaccines", "deworming", "blood_test"],
    }

    normalized = onboarding._normalize_preventive_medicine_categories(parsed)

    assert normalized["flea_tick"] == {
        "date": "February 2026",
        "medicine": "Simparica Trio",
    }
    assert normalized["deworming"] == {
        "date": "February 2026",
        "medicine": "Simparica Trio",
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
