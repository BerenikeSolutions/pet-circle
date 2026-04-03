import os
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services.records_service import get_records


def _doc(
    category: str,
    event_date: date | None,
    name: str,
    source_wamid: str | None = None,
):
    return SimpleNamespace(
        id=uuid4(),
        document_category=category,
        event_date=event_date,
        document_name=name,
        source_wamid=source_wamid,
    )


def _condition(
    document_id,
    diagnosis: str | None = None,
    notes: str | None = None,
    medications: list | None = None,
):
    return SimpleNamespace(
        document_id=document_id,
        diagnosis=diagnosis,
        notes=notes,
        medications=medications or [],
    )


def _med(name: str, dose: str | None, frequency: str | None, status: str = "active"):
    return SimpleNamespace(name=name, dose=dose, frequency=frequency, status=status)


@pytest.mark.asyncio
async def test_get_records_groups_types_and_sorts_desc(monkeypatch):
    pet = SimpleNamespace(id=uuid4())

    prescription = _doc("Prescription", date(2026, 3, 10), "Skin Prescription")
    lab = _doc("Diagnostic", date(2026, 3, 9), "CBC Report")
    imaging = _doc("Other", date(2026, 2, 1), "Chest X-Ray")
    whatsapp = _doc("Other", date(2026, 1, 1), "Shared over chat", source_wamid="wamid.1")

    monkeypatch.setattr(
        "app.services.records_service._fetch_documents",
        lambda _db, _pet_id: [whatsapp, prescription, imaging, lab],
    )
    monkeypatch.setattr(
        "app.services.records_service._fetch_conditions_for_documents",
        lambda _db, _pet_id, _doc_ids: {},
    )

    result = await get_records(SimpleNamespace(), pet)

    assert [visit["id"] for visit in result["vet_visits"]] == [str(prescription.id)]

    assert [item["type"] for item in result["records"]] == ["lab_reports", "imaging", "whatsapp"]
    assert result["records"][0]["tag"] == "Lab Report"
    assert result["records"][0]["tag_color"] == "#0F766E"
    assert result["records"][1]["tag"] == "Record"
    assert result["records"][2]["tag"] == "WhatsApp"


@pytest.mark.asyncio
async def test_get_records_does_not_mark_scanned_text_as_imaging(monkeypatch):
    pet = SimpleNamespace(id=uuid4())
    scanned_doc = _doc("Other", date(2026, 2, 15), "Scanned prescription page")

    monkeypatch.setattr(
        "app.services.records_service._fetch_documents",
        lambda _db, _pet_id: [scanned_doc],
    )
    monkeypatch.setattr(
        "app.services.records_service._fetch_conditions_for_documents",
        lambda _db, _pet_id, _doc_ids: {},
    )

    result = await get_records(SimpleNamespace(), pet)

    assert result["records"][0]["type"] == "lab_reports"
    assert result["records"][0]["icon"] == "📄"


@pytest.mark.asyncio
async def test_get_records_enriches_vet_visit_medications_and_rx(monkeypatch):
    pet = SimpleNamespace(id=uuid4())
    prescription = _doc("Prescription", date(2026, 3, 10), "Prescription Visit")

    linked_conditions = {
        prescription.id: [
            _condition(
                document_id=prescription.id,
                diagnosis="Allergic dermatitis",
                notes="Continue medicated bath",
                medications=[
                    _med("Apoquel", "5mg", "7 days", status="active"),
                    _med("Old Med", "2mg", "3 days", status="discontinued"),
                ],
            )
        ]
    }

    monkeypatch.setattr(
        "app.services.records_service._fetch_documents",
        lambda _db, _pet_id: [prescription],
    )
    monkeypatch.setattr(
        "app.services.records_service._fetch_conditions_for_documents",
        lambda _db, _pet_id, _doc_ids: linked_conditions,
    )

    result = await get_records(SimpleNamespace(), pet)

    assert len(result["vet_visits"]) == 1
    visit = result["vet_visits"][0]
    assert visit["rx"] == "Allergic dermatitis"
    assert visit["notes"] == "Continue medicated bath"
    assert visit["medications"] == [{"name": "Apoquel", "dose": "5mg", "duration": "7 days"}]


@pytest.mark.asyncio
async def test_get_records_sorts_missing_dates_last(monkeypatch):
    pet = SimpleNamespace(id=uuid4())

    latest_doc = _doc("Diagnostic", date(2026, 3, 1), "Latest report")
    undated_doc = _doc("Diagnostic", None, "Undated report")

    monkeypatch.setattr(
        "app.services.records_service._fetch_documents",
        lambda _db, _pet_id: [undated_doc, latest_doc],
    )
    monkeypatch.setattr(
        "app.services.records_service._fetch_conditions_for_documents",
        lambda _db, _pet_id, _doc_ids: {},
    )

    result = await get_records(SimpleNamespace(), pet)

    assert [item["title"] for item in result["records"]] == ["Latest report", "Undated report"]
    assert result["records"][1]["date"] is None


@pytest.mark.asyncio
async def test_get_records_returns_empty_lists_for_empty_data(monkeypatch):
    pet = SimpleNamespace(id=uuid4())

    monkeypatch.setattr("app.services.records_service._fetch_documents", lambda _db, _pet_id: [])
    monkeypatch.setattr(
        "app.services.records_service._fetch_conditions_for_documents",
        lambda _db, _pet_id, _doc_ids: {},
    )

    result = await get_records(SimpleNamespace(), pet)

    assert result == {"vet_visits": [], "records": []}
