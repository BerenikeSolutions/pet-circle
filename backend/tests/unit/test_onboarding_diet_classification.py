"""
Bug 3 — Strict brand-only diet classification.

_parse_diet_input must classify each extracted item with a 'kind' of
brand / ingredient / generic_treat. _store_meal_items must persist ONLY
items where kind == "brand"; ingredients and generic treats are dropped.
"""
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services import onboarding


def _mock_gpt_response(items: list[dict]) -> SimpleNamespace:
    """Build a fake OpenAI chat.completions response returning the given items."""
    payload = json.dumps({"items": items})
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
    )


@pytest.mark.asyncio
async def test_parse_diet_input_returns_kind_field(monkeypatch) -> None:
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
    )
    monkeypatch.setattr(
        onboarding, "_get_openai_onboarding_client", lambda: fake_client
    )

    async def fake_retry(_call, **kwargs):
        return _mock_gpt_response(
            [
                {"label": "chicken", "detail": "", "kind": "ingredient"},
                {"label": "Royal Canin", "detail": "", "kind": "brand"},
                {"label": "small treat", "detail": "", "kind": "generic_treat"},
            ]
        )

    monkeypatch.setattr(onboarding, "retry_openai_call", fake_retry)

    items = await onboarding._parse_diet_input("chicken, royal canin, small treat")

    assert items == [
        ("chicken", "", "ingredient"),
        ("Royal Canin", "", "brand"),
        ("small treat", "", "generic_treat"),
    ]


@pytest.mark.asyncio
async def test_parse_diet_input_defaults_missing_kind_to_ingredient(
    monkeypatch,
) -> None:
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
    )
    monkeypatch.setattr(
        onboarding, "_get_openai_onboarding_client", lambda: fake_client
    )

    async def fake_retry(_call, **kwargs):
        return _mock_gpt_response(
            [
                {"label": "Royal Canin", "detail": ""},  # no kind → default ingredient
            ]
        )

    monkeypatch.setattr(onboarding, "retry_openai_call", fake_retry)

    items = await onboarding._parse_diet_input("royal canin")

    # Missing kind falls back to "ingredient" → strict-mode callers will drop it.
    assert items == [("Royal Canin", "", "ingredient")]


@pytest.mark.asyncio
async def test_parse_diet_input_on_gpt_failure_marks_as_ingredient(
    monkeypatch,
) -> None:
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
    )
    monkeypatch.setattr(
        onboarding, "_get_openai_onboarding_client", lambda: fake_client
    )

    async def boom(_call, **kwargs):
        raise RuntimeError("openai offline")

    monkeypatch.setattr(onboarding, "retry_openai_call", boom)

    items = await onboarding._parse_diet_input("whatever")

    assert items == [("whatever", "", "ingredient")]


@pytest.mark.asyncio
async def test_store_meal_items_only_persists_brand(monkeypatch) -> None:
    """Verify strict filter: only kind='brand' is persisted."""
    stored: list[tuple] = []

    async def fake_add_diet_item(_db, pet_id, item_type, label, detail):
        stored.append((pet_id, item_type, label, detail))

    monkeypatch.setattr(onboarding, "add_diet_item", fake_add_diet_item)

    pet = SimpleNamespace(id="pet-uuid")
    items = [
        ("chicken", "", "ingredient"),
        ("Royal Canin", "", "brand"),
        ("small treat", "", "generic_treat"),
    ]

    await onboarding._store_meal_items(db=None, pet=pet, items=items, food_type="packaged")

    assert len(stored) == 1
    assert stored[0] == ("pet-uuid", "packaged", "Royal Canin", None)


@pytest.mark.asyncio
async def test_store_meal_items_drops_everything_if_no_brand(monkeypatch) -> None:
    stored: list[tuple] = []

    async def fake_add_diet_item(_db, pet_id, item_type, label, detail):
        stored.append((pet_id, item_type, label, detail))

    monkeypatch.setattr(onboarding, "add_diet_item", fake_add_diet_item)

    pet = SimpleNamespace(id="pet-uuid")
    items = [
        ("boiled chicken", "", "ingredient"),
        ("carrots", "", "ingredient"),
    ]

    await onboarding._store_meal_items(db=None, pet=pet, items=items, food_type="home")

    assert stored == []


@pytest.mark.asyncio
async def test_store_meal_items_supports_legacy_two_tuples(monkeypatch) -> None:
    """Legacy (label, detail) tuples (no kind) must be assumed brand for back-compat."""
    stored: list[tuple] = []

    async def fake_add_diet_item(_db, pet_id, item_type, label, detail):
        stored.append((pet_id, item_type, label, detail))

    monkeypatch.setattr(onboarding, "add_diet_item", fake_add_diet_item)

    pet = SimpleNamespace(id="pet-uuid")
    items = [("Pedigree", "")]  # legacy shape

    await onboarding._store_meal_items(db=None, pet=pet, items=items, food_type="packaged")

    assert len(stored) == 1
    assert stored[0][2] == "Pedigree"
