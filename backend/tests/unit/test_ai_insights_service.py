import json
import os
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services.ai_insights_service import (
    generate_care_plan_reasons,
    generate_recognition_bullets,
)
from app.services.care_plan_engine import BreedSize, LifeStage


class _ScalarQuery:
    def __init__(self, value):
        self._value = value

    def filter(self, *args, **kwargs):
        return self

    def scalar(self):
        return self._value


class _AllQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, scalar_values=None, all_rows=None):
        self._scalar_values = list(scalar_values or [])
        self._all_rows = list(all_rows or [])

    def query(self, *args, **kwargs):
        if self._scalar_values:
            return _ScalarQuery(self._scalar_values.pop(0))
        if self._all_rows:
            return _AllQuery(self._all_rows.pop(0))
        return _ScalarQuery(0)


@pytest.mark.asyncio
async def test_generate_recognition_bullets_orders_conditions_preventive_diet():
    db = _FakeSession(scalar_values=[4, 2, 3, 1])
    pet = SimpleNamespace(id=uuid4())

    bullets = await generate_recognition_bullets(cast(Any, db), cast(Any, pet))

    assert len(bullets) == 3
    assert bullets[0]["icon"] == "🩺"
    assert "active health conditions" in bullets[0]["label"]
    assert "4 reviewed reports" in bullets[0]["label"]
    assert bullets[1]["icon"] == "✅"
    assert bullets[2]["icon"] == "🍽️"


@pytest.mark.asyncio
async def test_generate_care_plan_reasons_maps_reasons_per_item(monkeypatch):
    db = _FakeSession(all_rows=[[ ("Arthritis",), ]])
    pet = SimpleNamespace(
        id=uuid4(),
        name="Bruno",
        species="dog",
        breed="Labrador",
        weight=30,
    )

    monkeypatch.setattr("app.services.ai_insights_service._get_openai_client", lambda: object())
    monkeypatch.setattr("app.services.ai_insights_service._get_pet_age_months", lambda _pet: 48)
    monkeypatch.setattr("app.services.ai_insights_service._get_breed_size", lambda _w, _b: BreedSize.LARGE)
    monkeypatch.setattr("app.services.ai_insights_service._get_life_stage", lambda _age, _size: LifeStage.ADULT)

    async def fake_get_diet_summary(_db, _pet):
        return {"missing_micros": [{"name": "Omega-3"}]}

    async def fake_retry(_call):
        return json.dumps(
            {
                "food-1": "Supports adult-stage joint routine with current condition and omega-3 gap context",
                "supp-2": "Adds nutritional support for the current life stage and observed deficiency profile",
            }
        )

    monkeypatch.setattr("app.services.ai_insights_service.get_diet_summary", fake_get_diet_summary)
    monkeypatch.setattr("app.services.ai_insights_service.retry_openai_call", fake_retry)

    reasons = await generate_care_plan_reasons(
        cast(Any, db),
        cast(Any, pet),
        [
            {"item_id": "food-1", "name": "Joint Care Food"},
            {"item_id": "supp-2", "name": "Omega Supplement"},
        ],
    )

    assert set(reasons.keys()) == {"food-1", "supp-2"}
    assert reasons["food-1"].endswith(".")
    assert reasons["supp-2"].endswith(".")


@pytest.mark.asyncio
async def test_generate_care_plan_reasons_returns_empty_dict_on_gpt_failure(monkeypatch):
    db = _FakeSession(all_rows=[[ ("Dermatitis",), ]])
    pet = SimpleNamespace(
        id=uuid4(),
        name="Milo",
        species="dog",
        breed="Indie",
        weight=18,
    )

    monkeypatch.setattr("app.services.ai_insights_service._get_openai_client", lambda: object())
    monkeypatch.setattr("app.services.ai_insights_service._get_pet_age_months", lambda _pet: 36)
    monkeypatch.setattr("app.services.ai_insights_service._get_breed_size", lambda _w, _b: BreedSize.MEDIUM)
    monkeypatch.setattr("app.services.ai_insights_service._get_life_stage", lambda _age, _size: LifeStage.ADULT)

    async def fake_get_diet_summary(_db, _pet):
        return {"missing_micros": []}

    async def broken_retry(_call):
        raise RuntimeError("openai unavailable")

    monkeypatch.setattr("app.services.ai_insights_service.get_diet_summary", fake_get_diet_summary)
    monkeypatch.setattr("app.services.ai_insights_service.retry_openai_call", broken_retry)

    reasons = await generate_care_plan_reasons(
        cast(Any, db),
        cast(Any, pet),
        [{"item_id": "food-1", "name": "Joint Care Food"}],
    )

    assert reasons == {}


@pytest.mark.asyncio
async def test_generate_care_plan_reasons_returns_empty_dict_on_diet_summary_failure(monkeypatch):
    db = _FakeSession(all_rows=[[("Dermatitis",)]])
    pet = SimpleNamespace(
        id=uuid4(),
        name="Milo",
        species="dog",
        breed="Indie",
        weight=18,
    )

    monkeypatch.setattr("app.services.ai_insights_service._get_openai_client", lambda: object())
    monkeypatch.setattr("app.services.ai_insights_service._get_pet_age_months", lambda _pet: 36)
    monkeypatch.setattr("app.services.ai_insights_service._get_breed_size", lambda _w, _b: BreedSize.MEDIUM)
    monkeypatch.setattr("app.services.ai_insights_service._get_life_stage", lambda _age, _size: LifeStage.ADULT)

    async def broken_diet_summary(_db, _pet):
        raise RuntimeError("nutrition service unavailable")

    monkeypatch.setattr("app.services.ai_insights_service.get_diet_summary", broken_diet_summary)

    reasons = await generate_care_plan_reasons(
        cast(Any, db),
        cast(Any, pet),
        [{"item_id": "food-1", "name": "Joint Care Food"}],
    )

    assert reasons == {}


@pytest.mark.asyncio
async def test_generate_care_plan_reasons_handles_invalid_weight(monkeypatch):
    db = _FakeSession(all_rows=[[("Arthritis",)]])
    pet = SimpleNamespace(
        id=uuid4(),
        name="Bruno",
        species="dog",
        breed="Labrador",
        weight="not-a-number",
    )

    monkeypatch.setattr("app.services.ai_insights_service._get_openai_client", lambda: object())
    monkeypatch.setattr("app.services.ai_insights_service._get_pet_age_months", lambda _pet: 48)
    monkeypatch.setattr("app.services.ai_insights_service._get_breed_size", lambda _w, _b: BreedSize.LARGE)
    monkeypatch.setattr("app.services.ai_insights_service._get_life_stage", lambda _age, _size: LifeStage.ADULT)

    async def fake_get_diet_summary(_db, _pet):
        return {"missing_micros": []}

    async def fake_retry(_call):
        return json.dumps({"food-1": "Supports ongoing adult-stage care context"})

    monkeypatch.setattr("app.services.ai_insights_service.get_diet_summary", fake_get_diet_summary)
    monkeypatch.setattr("app.services.ai_insights_service.retry_openai_call", fake_retry)

    reasons = await generate_care_plan_reasons(
        cast(Any, db),
        cast(Any, pet),
        [{"item_id": "food-1", "name": "Joint Care Food"}],
    )

    assert reasons == {"food-1": "Supports ongoing adult-stage care context."}
