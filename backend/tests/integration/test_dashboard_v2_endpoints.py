from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.database import get_db


@pytest.fixture
def api_client(app):
    """Provide TestClient with a lightweight DB dependency override."""

    def _fake_db_session():
        yield SimpleNamespace()

    app.dependency_overrides[get_db] = _fake_db_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_get_returns_enriched_payload(monkeypatch, api_client):
    async def fake_get_dashboard_data(_db, _token):
        return {
            "pet": {"name": "Bruno", "species": "dog"},
            "owner": {"full_name": "Pet Parent"},
            "preventive_records": [],
            "reminders": [],
            "documents": [],
            "diagnostic_results": [],
            "conditions": [],
            "contacts": [],
            "health_score": {"score": 90},
            "nutrition": [],
            "conflict_flags": [],
            "vet_summary": {"name": "Dr. Mehta", "last_visit": "2026-03-01"},
            "life_stage": {
                "stage": "adult",
                "age_months": 48,
                "breed_size": "medium",
                "traits": [],
                "essential_care": [],
            },
            "health_conditions_summary": [],
            "care_plan_v2": {"continue": [], "attend": [], "add": []},
            "diet_summary": {"macros": [], "missing_micros": []},
            "recognition": {"report_count": 0, "bullets": []},
        }

    monkeypatch.setattr("app.routers.dashboard.get_dashboard_data", fake_get_dashboard_data)

    response = api_client.get("/dashboard/test-token")

    assert response.status_code == 200
    assert "no-store" in response.headers.get("Cache-Control", "")

    payload = response.json()
    assert "vet_summary" in payload
    assert "life_stage" in payload
    assert "health_conditions_summary" in payload
    assert "care_plan_v2" in payload
    assert "diet_summary" in payload
    assert "recognition" in payload


def test_dashboard_health_trends_v2_returns_structured_payload(monkeypatch, api_client):
    monkeypatch.setattr(
        "app.routers.dashboard._get_pet_for_dashboard_token",
        lambda _db, _token: SimpleNamespace(id="pet-1", is_deleted=False),
    )

    async def fake_health_trends(_db, _pet):
        return {
            "ask_vet": {"conditions": []},
            "signals": {"blood_panel": None, "weight": None, "metabolic": None},
            "cadence": {"vaccines": None, "flea_tick": None, "deworming": None},
        }

    monkeypatch.setattr("app.routers.dashboard.get_health_trends_v2", fake_health_trends)

    response = api_client.get("/dashboard/test-token/health-trends-v2")

    assert response.status_code == 200
    assert "no-store" in response.headers.get("Cache-Control", "")
    payload = response.json()
    assert set(payload.keys()) == {"ask_vet", "signals", "cadence"}


def test_dashboard_records_v2_returns_structured_payload(monkeypatch, api_client):
    monkeypatch.setattr(
        "app.routers.dashboard._get_pet_for_dashboard_token",
        lambda _db, _token: SimpleNamespace(id="pet-1", is_deleted=False),
    )

    async def fake_records(_db, _pet):
        return {
            "vet_visits": [{"id": "1", "title": "Visit"}],
            "records": [{"id": "2", "type": "lab_reports"}],
        }

    monkeypatch.setattr("app.routers.dashboard.get_records_v2", fake_records)

    response = api_client.get("/dashboard/test-token/records-v2")

    assert response.status_code == 200
    assert "no-store" in response.headers.get("Cache-Control", "")
    payload = response.json()
    assert "vet_visits" in payload
    assert "records" in payload


def test_dashboard_v2_endpoints_return_404_for_invalid_token(monkeypatch, api_client):
    def fake_raise(_db, _token):
        raise ValueError("invalid")

    monkeypatch.setattr("app.routers.dashboard._get_pet_for_dashboard_token", fake_raise)

    trends = api_client.get("/dashboard/bad-token/health-trends-v2")
    records = api_client.get("/dashboard/bad-token/records-v2")

    assert trends.status_code == 404
    assert records.status_code == 404
