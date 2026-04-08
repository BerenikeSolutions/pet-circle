"""Unit tests for nutrition target prompting and weight approximation behavior."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services import nutrition_service as ns


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [MagicMock(message=MagicMock(content=content))]


class _FakeCompletions:
    def __init__(self):
        self.last_messages = None

    async def create(self, **kwargs):
        self.last_messages = kwargs["messages"]
        return _FakeResponse('{"calories": 1000}')


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


def _make_required_targets() -> dict:
    return {
        "calories": 1200,
        "protein": 25,
        "fat": 14,
        "carbs": 50,
        "fibre": 4,
        "moisture": 10,
        "calcium": 1.0,
        "phosphorus": 0.8,
        "omega_3": 300,
        "omega_6": 1500,
        "vitamin_e": 300,
        "vitamin_d3": 400,
        "glucosamine": 500,
        "probiotics": False,
    }


def _make_db_stub():
    query_obj = MagicMock()
    query_obj.filter.return_value = query_obj
    query_obj.first.return_value = None

    db = MagicMock()
    db.query.return_value = query_obj
    return db


def test_normalize_gender_for_lookup_accepts_known_values():
    assert ns._normalize_gender_for_lookup("male") == "male"
    assert ns._normalize_gender_for_lookup("M") == "male"
    assert ns._normalize_gender_for_lookup("female") == "female"
    assert ns._normalize_gender_for_lookup("girl") == "female"


def test_normalize_gender_for_lookup_ignores_unknown_values():
    assert ns._normalize_gender_for_lookup(None) is None
    assert ns._normalize_gender_for_lookup("") is None
    assert ns._normalize_gender_for_lookup("unknown") is None


def test_midpoint_rejects_default_fallback_range():
    midpoint = ns._midpoint_from_confident_ideal_range(
        {"min": 5, "max": 50}
    )
    assert midpoint is None


@pytest.mark.asyncio
async def test_call_openai_nutrition_targets_omits_missing_optional_fields():
    fake_client = _FakeClient()
    with patch.object(ns, "_get_openai_client", return_value=fake_client):
        await ns._call_openai_nutrition_targets(
            species="dog",
            breed="labrador",
            age_description=None,
            weight_kg=None,
            gender=None,
        )

    assert fake_client.chat.completions.last_messages is not None
    user_prompt = fake_client.chat.completions.last_messages[1]["content"]
    assert "Species: dog" in user_prompt
    assert "Breed: labrador" in user_prompt
    assert "Age:" not in user_prompt
    assert "Weight_kg:" not in user_prompt
    assert "Gender:" not in user_prompt


@pytest.mark.asyncio
async def test_get_nutrition_targets_approximates_weight_when_missing_gender_unknown():
    db = _make_db_stub()

    retry_mock = AsyncMock(return_value=_make_required_targets())
    ideal_mock = AsyncMock(side_effect=[{"min": 20, "max": 30}, {"min": 18, "max": 28}])

    with patch.object(ns, "retry_openai_call", retry_mock), patch.object(ns, "get_ideal_range", ideal_mock):
        result = await ns.get_nutrition_targets(
            db=db,
            species="dog",
            breed="Labrador",
            dob=None,
            weight_kg=None,
            gender=None,
        )

    assert result["calories"] == 1200
    assert ideal_mock.await_count == 2

    assert retry_mock.await_args is not None
    args = retry_mock.await_args.args
    assert args[0] == ns._call_openai_nutrition_targets
    assert args[1] == "dog"
    assert args[2] == "labrador"
    assert args[3] is None
    assert args[4] == 24.0
    assert args[5] is None


@pytest.mark.asyncio
async def test_get_nutrition_targets_does_not_use_default_weight_fallback():
    db = _make_db_stub()

    retry_mock = AsyncMock(return_value=_make_required_targets())
    ideal_mock = AsyncMock(return_value={"min": 5, "max": 50})

    with patch.object(ns, "retry_openai_call", retry_mock), patch.object(ns, "get_ideal_range", ideal_mock):
        await ns.get_nutrition_targets(
            db=db,
            species="dog",
            breed="Labrador",
            dob=None,
            weight_kg=None,
            gender="male",
        )

    assert retry_mock.await_args is not None
    args = retry_mock.await_args.args
    assert args[4] is None
    assert args[5] == "male"
