import json
import os
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services.ai_insights_service import (
    _VACCINE_BULLET_TERMS,
    _format_found_diet_summary,
    generate_care_plan_reasons,
    generate_recognition_bullets,
    get_or_generate_insight,
)
from app.services.care_plan_engine import BreedSize, LifeStage


class _ScalarQuery:
    def __init__(self, value):
        # `value` may be a single int (used for scalar()) OR a list of ints
        # consumed sequentially by count() to simulate sub-query counts.
        self._value = value
        self._count_values = list(value) if isinstance(value, list) else None

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def outerjoin(self, *args, **kwargs):
        return self

    def scalar(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else 0
        return self._value

    def count(self):
        if self._count_values is not None:
            return self._count_values.pop(0) if self._count_values else 0
        return self._value


class _AllQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
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


def test_format_found_diet_summary_keeps_main_items_and_supplements():
    foods = [
        SimpleNamespace(
            type="packaged",
            label="Royal Canin Adult kibble",
            detail="50g x 3/day . times a day · small treat · in the evening",
        ),
        SimpleNamespace(
            type="homemade",
            label="boiled rice and chicken",
            detail=None,
        ),
    ]
    supplements = [SimpleNamespace(type="supplement", label="omega", detail=None)]

    summary = _format_found_diet_summary(foods, supplements)

    assert summary == "Royal Canin Adult kibble. Boiled rice and chicken. Supplements - Omega."


def test_format_found_diet_summary_without_supplements_shows_no_supplements():
    foods = [SimpleNamespace(type="packaged", label="Royal Canin Adult kibble", detail=None)]

    summary = _format_found_diet_summary(foods, [])

    assert summary == "Royal Canin Adult kibble. No supplements."


def test_format_found_diet_summary_strips_weekly_frequency_from_food_label():
    foods = [SimpleNamespace(type="homemade", label="egg khichdi / week", detail=None)]

    summary = _format_found_diet_summary(foods, [])

    assert summary == "Egg khichdi. No supplements."


def test_format_found_diet_summary_preserves_brand_x_token():
    foods = [SimpleNamespace(type="packaged", label="Brand X kibble", detail=None)]

    summary = _format_found_diet_summary(foods, [])

    assert summary == "Brand X kibble. No supplements."


def test_format_found_diet_summary_removes_occasional_qualifier():
    foods = [SimpleNamespace(type="homemade", label="occasional egg", detail=None)]

    summary = _format_found_diet_summary(foods, [])

    assert summary == "Egg. No supplements."


def test_format_found_diet_summary_preserves_daily_brand_name():
    foods = [SimpleNamespace(type="packaged", label="Daily Delight kibble", detail=None)]

    summary = _format_found_diet_summary(foods, [])

    assert summary == "Daily Delight kibble. No supplements."


def test_format_found_diet_summary_drops_standalone_sometimes():
    foods = [SimpleNamespace(type="homemade", label="sometimes", detail=None)]

    summary = _format_found_diet_summary(foods, [])

    assert summary == "No supplements."


def test_format_found_diet_summary_drops_standalone_sometimes_with_punctuation():
    foods = [SimpleNamespace(type="homemade", label="sometimes.", detail=None)]

    summary = _format_found_diet_summary(foods, [])

    assert summary == "No supplements."


def test_format_found_diet_summary_does_not_duplicate_supplements_in_food_items():
    foods = [
        SimpleNamespace(type="homemade", label="turmeric", detail=None),
        SimpleNamespace(type="packaged", label="omega", detail=None),
        SimpleNamespace(type="packaged", label="Royal Canin Adult kibble", detail=None),
    ]
    supplements = [
        SimpleNamespace(type="supplement", label="turmeric", detail=None),
        SimpleNamespace(type="supplement", label="omega", detail=None),
    ]

    summary = _format_found_diet_summary(foods, supplements)

    assert summary == "Royal Canin Adult kibble. Supplements - Turmeric, Omega."


def test_format_found_diet_summary_keeps_legit_food_with_overlapping_token():
    foods = [SimpleNamespace(type="packaged", label="Omega kibble", detail=None)]
    supplements = [SimpleNamespace(type="supplement", label="omega", detail=None)]

    summary = _format_found_diet_summary(foods, supplements)

    assert summary == "Omega kibble. Supplements - Omega."


class _InsightQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _FakeInsightDB:
    def __init__(self):
        self.executed = []

    def query(self, *args, **kwargs):
        return _InsightQuery()

    def execute(self, statement, params):
        self.executed.append(params)

    def commit(self):
        return None

    def rollback(self):
        return None


@pytest.mark.asyncio
async def test_generate_recognition_bullets_orders_conditions_preventive_diet():
    # scalar_values consumed in order:
    # 1st query → active_condition_count (scalar) = 4
    # 2nd query → preventive base; then .count() calls: vaccines=0, total=2 → 2 "other" items
    db = _FakeSession(
        scalar_values=[4, [0, 2]],
        all_rows=[
            [
                SimpleNamespace(type="packaged", label="Royal Canin Adult kibble", detail="50g x 3/day"),
                SimpleNamespace(type="homemade", label="boiled rice and chicken", detail=None),
                SimpleNamespace(type="supplement", label="omega", detail=None),
            ]
        ],
    )
    pet = SimpleNamespace(id=uuid4())

    bullets = await generate_recognition_bullets(cast(Any, db), cast(Any, pet))

    assert len(bullets) == 3
    assert bullets[0]["icon"] == "🩺"
    assert "active condition" in bullets[0]["label"]
    assert bullets[1]["icon"] == "💉"
    assert "preventive care item" in bullets[1]["label"]
    assert bullets[2]["icon"] == "🍽️"
    assert bullets[2]["label"] == "Royal Canin Adult kibble. Boiled rice and chicken. Supplements - Omega."


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


@pytest.mark.asyncio
async def test_get_or_generate_insight_accepts_namespaced_vet_questions(monkeypatch):
    db = _FakeInsightDB()

    async def fake_questions(_context):
        return [{"priority": "high", "icon": "🩺", "q": "Any follow-up panel needed?", "context": ""}]

    monkeypatch.setattr("app.services.ai_insights_service._generate_vet_questions_gpt", fake_questions)

    result = await get_or_generate_insight(
        db=cast(Any, db),
        pet_id=uuid4(),
        insight_type="vet_questions:condition-1",
        pet={"name": "Bruno", "species": "dog", "breed": "Labrador"},
        conditions=[{"name": "Dermatitis", "condition_type": "chronic", "medications": [], "monitoring": []}],
        health_score={"score": None},
        force=False,
    )

    assert isinstance(result, list)
    assert result[0]["q"] == "Any follow-up panel needed?"
    assert db.executed
    assert db.executed[0]["insight_type"] == "vet_questions:condition-1"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 2: Kennel Cough & CCoV must be bucketed as vaccines in What We Found
# ─────────────────────────────────────────────────────────────────────────────


def test_vaccine_bullet_terms_include_kennel_cough_and_ccov():
    """The 'What We Found' bucket must classify Kennel Cough (Nobivac KC) and
    Canine Coronavirus (CCoV) as vaccines, not as other preventive items."""
    # Kennel Cough canonical name: "Kennel Cough (Nobivac KC)"
    assert any(kw in "Kennel Cough (Nobivac KC)".lower() for kw in _VACCINE_BULLET_TERMS)
    # Canine Coronavirus canonical name: "Canine Coronavirus (CCoV)"
    assert any(kw in "Canine Coronavirus (CCoV)".lower() for kw in _VACCINE_BULLET_TERMS)
    # Regression: existing vaccines still match.
    assert any(kw in "Rabies Vaccine".lower() for kw in _VACCINE_BULLET_TERMS)
    assert any(kw in "DHPPi".lower() for kw in _VACCINE_BULLET_TERMS)
    # Non-vaccines must NOT match.
    assert not any(kw in "Deworming".lower() for kw in _VACCINE_BULLET_TERMS)
    assert not any(kw in "Tick/Flea".lower() for kw in _VACCINE_BULLET_TERMS)
    assert not any(kw in "Preventive Blood Test".lower() for kw in _VACCINE_BULLET_TERMS)
