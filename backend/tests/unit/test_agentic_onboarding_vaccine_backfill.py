import json
from datetime import date
from types import SimpleNamespace

from app.services.agentic_onboarding import (
    _summarise_extraction_for_onboarding,
    _update_preventive_records_from_health,
)


class _QueryStub:
    def __init__(self, rows):
        self._rows = rows

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._rows


class _DBStub:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *_args, **_kwargs):
        return _QueryStub(self._rows)


def test_summarise_extraction_classifies_kennel_cough_as_vaccine() -> None:
    raw = json.dumps(
        {
            "items": [
                {
                    "item_name": "Kennel Cough (Nobivac KC)",
                    "last_done_date": "01/04/2025",
                }
            ]
        }
    )

    summary = _summarise_extraction_for_onboarding(raw)

    assert "Kennel Cough (Nobivac KC)" in summary["vaccines"]
    assert summary["allergies_medications"] == "Not found in records"


def test_update_preventive_records_maps_nobivac_kc_to_kennel_cough_record() -> None:
    rabies_master = SimpleNamespace(
        item_name="Rabies (Nobivac RL)",
        recurrence_days=365,
        reminder_before_days=14,
    )
    kennel_master = SimpleNamespace(
        item_name="Kennel Cough (Nobivac KC)",
        recurrence_days=365,
        reminder_before_days=14,
    )

    rabies_record = SimpleNamespace(
        preventive_master=rabies_master,
        preventive_master_id="rabies",
        pet_id="pet-1",
        last_done_date=None,
        next_due_date=None,
        status="upcoming",
        medicine_name=None,
    )
    kennel_record = SimpleNamespace(
        preventive_master=kennel_master,
        preventive_master_id="kennel",
        pet_id="pet-1",
        last_done_date=None,
        next_due_date=None,
        status="upcoming",
        medicine_name=None,
    )

    db = _DBStub([rabies_record, kennel_record])
    pet = SimpleNamespace(id="pet-1")

    _update_preventive_records_from_health(
        db,
        pet,
        {"vaccines": "Kennel Cough (Nobivac KC) 01/04/2025"},
    )

    assert kennel_record.last_done_date == date(2025, 4, 1)
    assert kennel_record.next_due_date == date(2026, 4, 1)
    assert rabies_record.last_done_date is None


def test_update_preventive_records_supports_multiple_vaccines_in_one_string() -> None:
    rabies_master = SimpleNamespace(
        item_name="Rabies (Nobivac RL)",
        recurrence_days=365,
        reminder_before_days=14,
    )
    kennel_master = SimpleNamespace(
        item_name="Kennel Cough (Nobivac KC)",
        recurrence_days=365,
        reminder_before_days=14,
    )

    rabies_record = SimpleNamespace(
        preventive_master=rabies_master,
        preventive_master_id="rabies",
        pet_id="pet-1",
        last_done_date=None,
        next_due_date=None,
        status="upcoming",
        medicine_name=None,
    )
    kennel_record = SimpleNamespace(
        preventive_master=kennel_master,
        preventive_master_id="kennel",
        pet_id="pet-1",
        last_done_date=None,
        next_due_date=None,
        status="upcoming",
        medicine_name=None,
    )

    db = _DBStub([rabies_record, kennel_record])
    pet = SimpleNamespace(id="pet-1")

    _update_preventive_records_from_health(
        db,
        pet,
        {
            "vaccines": "Rabies (Nobivac RL) 01/04/2025, Kennel Cough (Nobivac KC) 02/04/2025",
        },
    )

    assert rabies_record.last_done_date == date(2025, 4, 1)
    assert kennel_record.last_done_date == date(2025, 4, 2)


def test_update_preventive_records_skips_ambiguous_brand_only_match() -> None:
    rabies_master = SimpleNamespace(
        item_name="Rabies (Nobivac RL)",
        recurrence_days=365,
        reminder_before_days=14,
    )
    kennel_master = SimpleNamespace(
        item_name="Kennel Cough (Nobivac KC)",
        recurrence_days=365,
        reminder_before_days=14,
    )

    rabies_record = SimpleNamespace(
        preventive_master=rabies_master,
        preventive_master_id="rabies",
        pet_id="pet-1",
        last_done_date=None,
        next_due_date=None,
        status="upcoming",
        medicine_name=None,
    )
    kennel_record = SimpleNamespace(
        preventive_master=kennel_master,
        preventive_master_id="kennel",
        pet_id="pet-1",
        last_done_date=None,
        next_due_date=None,
        status="upcoming",
        medicine_name=None,
    )

    db = _DBStub([rabies_record, kennel_record])
    pet = SimpleNamespace(id="pet-1")

    _update_preventive_records_from_health(
        db,
        pet,
        {"vaccines": "Nobivac 01/04/2025"},
    )

    assert rabies_record.last_done_date is None
    assert kennel_record.last_done_date is None


def test_update_preventive_records_uses_later_valid_entry_for_same_vaccine() -> None:
    rabies_master = SimpleNamespace(
        item_name="Rabies (Nobivac RL)",
        recurrence_days=365,
        reminder_before_days=14,
    )

    rabies_record = SimpleNamespace(
        preventive_master=rabies_master,
        preventive_master_id="rabies",
        pet_id="pet-1",
        last_done_date=None,
        next_due_date=None,
        status="upcoming",
        medicine_name=None,
    )

    db = _DBStub([rabies_record])
    pet = SimpleNamespace(id="pet-1")

    _update_preventive_records_from_health(
        db,
        pet,
        {"vaccines": "Rabies (Nobivac RL), Rabies (Nobivac RL) 01/04/2025"},
    )

    assert rabies_record.last_done_date == date(2025, 4, 1)
