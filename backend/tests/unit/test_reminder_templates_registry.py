from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from app.core.constants import STAGE_D3, STAGE_DUE, STAGE_OVERDUE, STAGE_T7
from app.services import reminder_engine
from app.services.reminder_engine import (
    ReminderCandidate,
    _apply_send_rules,
    _build_template_params,
    _candidates_from_chronic_medicine,
    _is_course_medicine,
)
from app.services.reminder_templates import (
    REMINDER_TEMPLATES,
    get_reminder_template,
    substitute_variables,
)


class _QueryChain:
    def __init__(self, all_result=None, first_result=None):
        self._all_result = all_result if all_result is not None else []
        self._first_result = first_result

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._all_result

    def first(self):
        return self._first_result


class _FakeDB:
    def __init__(self, all_results: list[list] | None = None):
        self._all_results = all_results or []
        self._idx = 0

    def query(self, *args, **kwargs):
        result = []
        if self._idx < len(self._all_results):
            result = self._all_results[self._idx]
        self._idx += 1
        return _QueryChain(all_result=result)


def _candidate(stage: str, pet_id: uuid.UUID, source_id: uuid.UUID) -> ReminderCandidate:
    pet = SimpleNamespace(id=pet_id, name="Bolt", breed="Labrador", dob=date(2025, 1, 1))
    user = SimpleNamespace(full_name="Asha")
    return ReminderCandidate(
        pet=pet,
        user=user,
        category="deworming",
        item_desc="Deworming",
        due_date=date.today(),
        stage=stage,
        source_type="preventive_record",
        source_id=source_id,
    )


def test_registry_contains_44_templates() -> None:
    assert len(REMINDER_TEMPLATES) == 44


def test_template_lookup_with_subtype_and_fallback() -> None:
    tpl = get_reminder_template("food", "supply_led", STAGE_T7)
    assert tpl is not None
    assert "running low" in tpl.message_body

    fallback = get_reminder_template("vet_followup", "standard", STAGE_DUE)
    assert fallback is not None
    assert "vet follow-up is today" in fallback.message_body


def test_substitute_variables_replaces_placeholders() -> None:
    body = "Hi [Name], [Pet] has [Medicine] due on [date]."
    rendered = substitute_variables(
        body,
        {
            "Name": "Riya",
            "Pet": "Milo",
            "Medicine": "Apoquel",
            "date": "04 Apr 2026",
        },
    )
    assert rendered == "Hi Riya, Milo has Apoquel due on 04 Apr 2026."


def test_apply_send_rules_limits_pet_daily_and_item_gap() -> None:
    pet_id = uuid.uuid4()
    source_due = uuid.uuid4()
    source_t7 = uuid.uuid4()

    db = _FakeDB(
        all_results=[
            [],
            [(source_due, datetime.now() - timedelta(days=1))],
        ]
    )

    candidates = [
        _candidate(STAGE_DUE, pet_id, source_due),
        _candidate(STAGE_T7, pet_id, source_t7),
        _candidate(STAGE_D3, uuid.uuid4(), uuid.uuid4()),
    ]

    filtered = _apply_send_rules(cast(Any, db), candidates, date.today())
    assert len(filtered) == 2
    assert any(c.stage == STAGE_T7 and c.source_id == source_t7 for c in filtered)
    assert any(c.stage == STAGE_D3 for c in filtered)


def test_build_template_params_falls_back_to_generic_when_registry_missing() -> None:
    cand = ReminderCandidate(
        pet=SimpleNamespace(id=uuid.uuid4(), name="Milo", breed="Labrador", dob=date(2020, 1, 1)),
        user=SimpleNamespace(full_name="Riya"),
        category="blood_checkup",
        item_desc="Annual blood panel",
        due_date=date(2026, 4, 4),
        stage=STAGE_DUE,
        source_type="preventive_record",
        source_id=uuid.uuid4(),
    )

    settings = SimpleNamespace(
        WHATSAPP_TEMPLATE_REMINDER_T7="tmpl_t7",
        WHATSAPP_TEMPLATE_REMINDER_DUE="tmpl_due",
        WHATSAPP_TEMPLATE_REMINDER_D3="tmpl_d3",
        WHATSAPP_TEMPLATE_REMINDER_OVERDUE="tmpl_overdue",
    )

    template, params = _build_template_params(cand, settings, cast(Any, _FakeDB()))
    assert template == "tmpl_due"
    assert params == ["Riya", "Milo", "Annual blood panel"]


def test_course_vs_chronic_detection_and_candidate_generation(monkeypatch) -> None:
    course_med = SimpleNamespace(
        id=uuid.uuid4(),
        name="Antibiotic",
        dose="1 tab",
        frequency="for 5 days",
        notes=None,
        refill_due_date=date.today(),
    )
    chronic_med = SimpleNamespace(
        id=uuid.uuid4(),
        name="Apoquel",
        dose="1 tab",
        frequency="daily",
        notes="ongoing",
        refill_due_date=date.today(),
    )

    condition = SimpleNamespace(diagnosis="Dermatitis")
    pet = SimpleNamespace(id=uuid.uuid4(), name="Milo")
    user = SimpleNamespace(onboarding_completed_at=datetime.now(), full_name="Riya")

    rows = [(course_med, condition, pet, user), (chronic_med, condition, pet, user)]

    class _MedicineDB:
        def query(self, *args, **kwargs):
            return _QueryChain(all_result=rows)

    monkeypatch.setattr(reminder_engine, "_determine_stage_simple", lambda *args, **kwargs: STAGE_DUE)

    assert _is_course_medicine(cast(Any, course_med)) is True
    assert _is_course_medicine(cast(Any, chronic_med)) is False

    cands = _candidates_from_chronic_medicine(cast(Any, _MedicineDB()), date.today())
    assert len(cands) == 1
    assert cands[0].source_id == chronic_med.id
    assert cands[0].category == "chronic_medicine"


def test_all_stages_present_for_each_template_set() -> None:
    grouped: dict[tuple[str, str | None], set[str]] = {}
    for category, sub_type, stage in REMINDER_TEMPLATES:
        grouped.setdefault((category, sub_type), set()).add(stage)

    for stage_set in grouped.values():
        assert stage_set == {STAGE_T7, STAGE_DUE, STAGE_D3, STAGE_OVERDUE}
