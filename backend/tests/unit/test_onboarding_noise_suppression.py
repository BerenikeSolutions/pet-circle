import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services import onboarding


def test_noise_suppression_allows_meal_confirmation_reply() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_meal_details",
        "y",
        {"meal_confirm_pending": True},
    ) is False


def test_noise_suppression_allows_preventive_confirmation_reply() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_preventive",
        "yes",
        {"preventive_confirm_pending": True},
    ) is False


def test_noise_suppression_still_blocks_ack_without_confirmation() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_meal_details",
        "y",
        {"meal_confirm_pending": False},
    ) is True


def test_noise_suppression_allows_future_confirmation_flags() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_custom_step",
        "yes",
        {"custom_confirm_pending": True},
    ) is False


def test_noise_suppression_ignores_non_pending_confirmation_flags() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_custom_step",
        "yes",
        {"custom_confirm_pending": False},
    ) is True


def test_binary_confirmation_parser_accepts_yes_variants() -> None:
    assert onboarding._resolve_binary_confirmation_reply("y") == "yes"
    assert onboarding._resolve_binary_confirmation_reply("YES") == "yes"
    assert onboarding._resolve_binary_confirmation_reply("yes!") == "yes"


def test_binary_confirmation_parser_accepts_no_variants() -> None:
    assert onboarding._resolve_binary_confirmation_reply("n") == "no"
    assert onboarding._resolve_binary_confirmation_reply("No") == "no"
    assert onboarding._resolve_binary_confirmation_reply("no.") == "no"


def test_binary_confirmation_parser_returns_none_for_non_binary_reply() -> None:
    assert onboarding._resolve_binary_confirmation_reply("yes but no egg") is None


def test_noise_suppression_allows_supplement_negative_reply() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_supplements",
        "no",
        {},
    ) is False
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_supplements",
        "none",
        {},
    ) is False
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_supplements",
        "n",
        {},
    ) is False
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_supplements",
        "not really",
        {},
    ) is False


def test_noise_suppression_still_blocks_supplement_ack_noise() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_supplements",
        "ok",
        {},
    ) is True


def test_noise_suppression_allows_preventive_negative_reply() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_preventive",
        "no",
        {},
    ) is False
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_preventive",
        "none",
        {},
    ) is False


def test_noise_suppression_allows_prev_retry_negative_reply() -> None:
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_prev_retry",
        "no",
        {},
    ) is False


def test_build_supplements_example_keeps_omega_by_default() -> None:
    example = onboarding._build_supplements_example({"meal_supplement_labels": ["Turmeric"]})
    assert "Omega-3" in example


def test_build_supplements_example_removes_omega_when_already_present() -> None:
    example = onboarding._build_supplements_example({"meal_supplement_labels": ["Omega-3 capsule"]})
    assert "Omega-3" not in example


def test_build_supplements_example_keeps_omega_for_omega6_label() -> None:
    example = onboarding._build_supplements_example({"meal_supplement_labels": ["Omega-6 oil"]})
    assert "Omega-3" in example
    assert onboarding._is_irrelevant_noise_for_state(
        "awaiting_prev_retry",
        "n",
        {},
    ) is False


@pytest.mark.asyncio
async def test_step_preventive_negative_reply_transitions_without_parsing(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="+911234567890",
        onboarding_data={},
    )
    pet = SimpleNamespace(name="Milo")
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()
    transition_mock = AsyncMock()
    parse_mock = AsyncMock()

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(onboarding, "_transition_to_documents", transition_mock)
    monkeypatch.setattr(onboarding, "_parse_preventive_care", parse_mock)

    await onboarding._step_preventive(db, user, "n.", send_fn)

    transition_mock.assert_awaited_once()
    parse_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_step_prev_retry_negative_reply_skips_parsing(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="+911234567890",
        onboarding_data={},
    )
    pet = SimpleNamespace(name="Milo")
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()
    transition_mock = AsyncMock()
    parse_mock = AsyncMock()

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(onboarding, "_transition_to_documents", transition_mock)
    monkeypatch.setattr(onboarding, "_parse_preventive_care", parse_mock)

    await onboarding._step_prev_retry(db, user, "no!", send_fn)

    transition_mock.assert_awaited_once()
    parse_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_step_meal_details_extracts_meal_derived_supplements(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="+911234567890",
        onboarding_data={
            "food_type": "mix",
            "meal_details_attempts": 0,
            "meal_confirm_pending": False,
            "meal_example_shown": "Royal Canin kibble + boiled egg",
        },
        onboarding_state="awaiting_meal_details",
    )
    pet = SimpleNamespace(id="pet-1", name="Milo")
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()
    parse_diet_mock = AsyncMock(return_value=[("Acana Heritage kibble", "80 g")])
    store_meal_items_mock = AsyncMock()
    store_meal_supp_mock = AsyncMock(return_value=["Omega-3 capsule"])

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(onboarding, "_ai_check_diet_relevance", AsyncMock(return_value=True))
    monkeypatch.setattr(onboarding, "_parse_diet_input", parse_diet_mock)
    monkeypatch.setattr(onboarding, "_store_meal_items", store_meal_items_mock)
    monkeypatch.setattr(onboarding, "_store_meal_supplement_items", store_meal_supp_mock)
    monkeypatch.setattr(
        onboarding,
        "_set_onboarding_data",
        lambda u, key, value: u.onboarding_data.__setitem__(key, value),
    )

    meal_text = (
        "Morning: Acana Heritage kibble 80 g. Evening: chicken breast 150 g + "
        "sweet potato 100 g + turmeric pinch. Omega-3 capsule 1000 mg daily."
    )
    await onboarding._step_meal_details(db, user, meal_text, send_fn)

    parse_diet_mock.assert_awaited_once_with(meal_text)
    store_meal_items_mock.assert_awaited_once()
    store_meal_supp_mock.assert_awaited_once_with(db, pet, meal_text)
    sent_text = send_fn.await_args_list[-1].args[2]
    assert "Omega-3" not in sent_text
    assert user.onboarding_state == "awaiting_supplements"


@pytest.mark.asyncio
async def test_step_meal_details_supplement_prompt_keeps_omega_when_not_in_meal(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="+911234567890",
        onboarding_data={
            "food_type": "mix",
            "meal_details_attempts": 0,
            "meal_confirm_pending": False,
            "meal_example_shown": "Royal Canin kibble + boiled egg",
        },
        onboarding_state="awaiting_meal_details",
    )
    pet = SimpleNamespace(id="pet-1", name="Milo")
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(onboarding, "_ai_check_diet_relevance", AsyncMock(return_value=True))
    monkeypatch.setattr(onboarding, "_parse_diet_input", AsyncMock(return_value=[("Acana", "80 g")]))
    monkeypatch.setattr(onboarding, "_store_meal_items", AsyncMock())
    monkeypatch.setattr(onboarding, "_store_meal_supplement_items", AsyncMock(return_value=["Turmeric"]))
    monkeypatch.setattr(
        onboarding,
        "_set_onboarding_data",
        lambda u, key, value: u.onboarding_data.__setitem__(key, value),
    )

    await onboarding._step_meal_details(db, user, "Acana kibble + turmeric pinch", send_fn)

    sent_text = send_fn.await_args_list[-1].args[2]
    assert "Omega-3" in sent_text


@pytest.mark.asyncio
async def test_step_supplements_no_reply_skips_supplement_parse(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="+911234567890",
        onboarding_data={},
        onboarding_state="awaiting_supplements",
    )
    pet = SimpleNamespace(id="pet-1", name="Milo")
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()
    parse_diet_mock = AsyncMock()

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(onboarding, "_parse_diet_input", parse_diet_mock)
    monkeypatch.setattr(
        onboarding,
        "_set_onboarding_data",
        lambda u, key, value: u.onboarding_data.__setitem__(key, value),
    )

    await onboarding._step_supplements_v2(db, user, "no", send_fn)

    parse_diet_mock.assert_not_awaited()
    assert user.onboarding_state == "awaiting_preventive"
