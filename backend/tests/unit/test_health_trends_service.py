import os
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services.health_trends_service import (
    _build_blood_panel,
    _build_flea_tick_cadence,
    get_health_trends,
)


def _diag(marker: str, status: str, observed_at: date | None = None, value: Decimal | None = None):
    return SimpleNamespace(
        parameter_name=marker,
        status_flag=status,
        observed_at=observed_at or date(2026, 3, 1),
        value_numeric=value if value is not None else Decimal("1.2"),
        value_text=None,
        unit="mg/dL",
        reference_range="1-2",
    )


@pytest.mark.asyncio
async def test_get_health_trends_assembles_all_sections(monkeypatch):
    pet = SimpleNamespace(id=uuid4(), name="Bruno", species="dog", breed="Labrador")

    condition = SimpleNamespace(
        id=uuid4(),
        name="Dermatitis",
        icon="🧴",
        condition_type="chronic",
        diagnosed_at=date(2025, 2, 2),
        medications=[SimpleNamespace(name="Med-A", dose="1 tab", frequency="daily", status="active", started_at=date(2025, 2, 5))],
        monitoring=[SimpleNamespace(name="Skin check", next_due_date=date(2026, 4, 8), last_done_date=None)],
    )
    blood_rows = [
        _diag("Hemoglobin", "normal", value=Decimal("12.3")),
        _diag("Creatinine", "high", value=Decimal("2.1")),
        _diag("ALT", "normal", value=Decimal("42.0")),
        _diag("Glucose", "normal", value=Decimal("95")),
        _diag("Bilirubin", "normal", value=Decimal("0.3")),
    ]
    weights = [
        SimpleNamespace(recorded_at=date(2026, 3, 10), weight=Decimal("30.2")),
        SimpleNamespace(recorded_at=date(2026, 2, 10), weight=Decimal("29.8")),
        SimpleNamespace(recorded_at=date(2026, 1, 10), weight=Decimal("29.3")),
        SimpleNamespace(recorded_at=date(2025, 12, 10), weight=Decimal("29.0")),
        SimpleNamespace(recorded_at=date(2025, 11, 10), weight=Decimal("28.9")),
    ]
    preventive = [
        (
            SimpleNamespace(last_done_date=date(2025, 1, 1), next_due_date=date(2026, 1, 1), status="up_to_date"),
            SimpleNamespace(item_name="Rabies Vaccine"),
        ),
        (
            SimpleNamespace(last_done_date=date(2025, 2, 15), next_due_date=date(2025, 3, 15), status="overdue"),
            SimpleNamespace(item_name="Tick & Flea"),
        ),
        (
            SimpleNamespace(last_done_date=None, next_due_date=date(2026, 2, 20), status="upcoming"),
            SimpleNamespace(item_name="Deworming"),
        ),
    ]

    monkeypatch.setattr("app.services.health_trends_service._fetch_active_conditions", lambda _db, _pid: [condition])
    monkeypatch.setattr("app.services.health_trends_service._fetch_latest_blood_results", lambda _db, _pid: blood_rows)
    monkeypatch.setattr("app.services.health_trends_service._fetch_weight_rows_desc", lambda _db, _pid: weights)
    monkeypatch.setattr("app.services.health_trends_service._fetch_preventive_rows", lambda _db, _pid: preventive)
    monkeypatch.setattr("app.services.health_trends_service._fetch_diagnostic_rows_desc", lambda _db, _pid: blood_rows)

    async def fake_questions(_db, _pet, _condition):
        return ["Should we repeat this panel next month?"]

    monkeypatch.setattr("app.services.health_trends_service._get_condition_questions", fake_questions)

    result = await get_health_trends(SimpleNamespace(), pet)

    assert result["ask_vet"] is not None
    assert result["signals"] is not None
    assert result["cadence"] is not None
    assert list(result["cadence"].keys()) == ["vaccines", "flea_tick", "deworming"]
    assert result["ask_vet"]["conditions"][0]["label"] == "Dermatitis"
    assert result["signals"]["blood_panel"]["rows"][0]["marker"] == "Hemoglobin"


@pytest.mark.asyncio
async def test_get_health_trends_returns_null_sections_when_data_missing(monkeypatch):
    pet = SimpleNamespace(id=uuid4(), name="Milo", species="dog", breed="Indie")

    monkeypatch.setattr("app.services.health_trends_service._fetch_active_conditions", lambda _db, _pid: [])
    monkeypatch.setattr("app.services.health_trends_service._fetch_latest_blood_results", lambda _db, _pid: [])
    monkeypatch.setattr("app.services.health_trends_service._fetch_weight_rows_desc", lambda _db, _pid: [])
    monkeypatch.setattr("app.services.health_trends_service._fetch_preventive_rows", lambda _db, _pid: [])
    monkeypatch.setattr("app.services.health_trends_service._fetch_diagnostic_rows_desc", lambda _db, _pid: [])

    result = await get_health_trends(SimpleNamespace(), pet)

    assert result == {"ask_vet": None, "signals": None, "cadence": None}


def test_blood_panel_keeps_marker_groups_together():
    mixed_rows = [
        _diag("Creatinine", "high"),
        _diag("Hemoglobin", "normal"),
        _diag("ALT", "normal"),
    ]

    panel = _build_blood_panel(mixed_rows)

    assert panel is not None
    markers = [row["marker"] for row in panel["rows"]]
    # Expected group order: CBC -> Liver -> Kidney
    assert markers == ["Hemoglobin", "ALT", "Creatinine"]


def test_blood_panel_unknown_status_does_not_count_as_high():
    rows = [
        _diag("Hemoglobin", "normal"),
        _diag("Creatinine", None),
    ]

    panel = _build_blood_panel(rows)

    assert panel is not None
    assert panel["headline"] == "All listed markers are within range."
    assert [row["status"] for row in panel["rows"]] == ["Normal", "Normal"]


def test_flea_tick_gap_uses_previous_completed_dose_only():
    rows = [
        (
            SimpleNamespace(last_done_date=date(2025, 1, 1)),
            SimpleNamespace(item_name="Tick & Flea"),
        ),
        (
            SimpleNamespace(last_done_date=None),
            SimpleNamespace(item_name="Tick & Flea"),
        ),
        (
            SimpleNamespace(last_done_date=date(2025, 4, 15)),
            SimpleNamespace(item_name="Tick & Flea"),
        ),
    ]

    cadence = _build_flea_tick_cadence(rows)

    assert cadence is not None
    doses = cadence["doses"]
    assert doses[2]["gap"] == "14w"
    assert doses[2]["status"] == "red"
    assert doses[2]["gap_alert"] is True
