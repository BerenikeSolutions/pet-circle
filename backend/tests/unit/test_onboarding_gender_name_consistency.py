import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services import onboarding


def test_sanitize_pet_name_candidate_strips_typed_wrong_suffix() -> None:
    assert onboarding._sanitize_pet_name_candidate("Mocha, I typed wrong") == "Mocha"


def test_extract_pet_name_correction_ignores_typed_wrong_suffix() -> None:
    assert onboarding._extract_pet_name_correction("Actually his name is Mocha, I typed wrong") == "Mocha"


@pytest.mark.asyncio
async def test_handle_onboarding_step_applies_pet_name_correction(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        onboarding_state="awaiting_gender_weight",
        onboarding_data={},
        mobile_number="enc",
        _plaintext_mobile="+911234567890",
    )
    pet = SimpleNamespace(name="Mochi")
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()

    monkeypatch.setattr(onboarding, "_is_greeting", lambda _text: False)
    monkeypatch.setattr(onboarding, "_is_irrelevant_noise_for_state", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(onboarding, "_step_gender_weight", AsyncMock())

    await onboarding.handle_onboarding_step(
        db,
        user,
        "Actually his name is Mocha, I typed wrong",
        send_fn,
    )

    assert pet.name == "Mocha"
    sent_text = send_fn.await_args_list[-1].args[2]
    assert "I'll use *Mocha* from now on" in sent_text
    assert "What's Mocha's gender" in sent_text


@pytest.mark.asyncio
async def test_handle_onboarding_step_applies_ai_pet_name_correction(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        onboarding_state="awaiting_gender_weight",
        onboarding_data={},
        mobile_number="enc",
        _plaintext_mobile="+911234567890",
    )
    pet = SimpleNamespace(name="Mochi")
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()

    monkeypatch.setattr(onboarding, "_is_greeting", lambda _text: False)
    monkeypatch.setattr(onboarding, "_is_irrelevant_noise_for_state", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(onboarding, "_step_gender_weight", AsyncMock())
    monkeypatch.setattr(onboarding, "_extract_pet_name_correction", lambda _text: None)
    monkeypatch.setattr(onboarding, "_ai_extract_pet_name_correction", AsyncMock(return_value="Mocha"))

    await onboarding.handle_onboarding_step(
        db,
        user,
        "you took the pet's name as Mocha, I typed wrong instead of Mochi",
        send_fn,
    )

    assert pet.name == "Mocha"
    sent_text = send_fn.await_args_list[-1].args[2]
    assert "I'll use *Mocha* from now on" in sent_text


@pytest.mark.asyncio
async def test_step_gender_weight_flags_pronoun_inconsistency(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="+911234567890",
        onboarding_data={"gender_weight_attempts": 0},
        onboarding_state="awaiting_gender_weight",
    )
    pet = SimpleNamespace(
        id="pet-1",
        name="Bruno",
        species="dog",
        breed="Labrador",
        dob=None,
        age_text="3 years",
        gender=None,
        weight=None,
        weight_flagged=False,
        neutered=None,
    )
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(
        onboarding,
        "_parse_gender_weight_neutered",
        AsyncMock(return_value={"gender": "female", "weight_kg": 28, "neutered": True}),
    )
    monkeypatch.setattr(onboarding, "_set_onboarding_data", lambda u, k, v: u.onboarding_data.__setitem__(k, v))

    await onboarding._step_gender_weight(
        db,
        user,
        "Bruno, Lab, 3 years, he weighs 28 kg. She is spayed.",
        send_fn,
    )

    assert user.onboarding_state == "awaiting_gender_weight"
    sent_text = send_fn.await_args_list[-1].args[2]
    assert sent_text == "Just to confirm — Bruno is female and spayed, right?"


@pytest.mark.asyncio
async def test_step_gender_weight_flags_male_spayed_gently(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="+911234567890",
        onboarding_data={"gender_weight_attempts": 0},
        onboarding_state="awaiting_gender_weight",
    )
    pet = SimpleNamespace(
        id="pet-1",
        name="Max",
        species="dog",
        breed="Labrador",
        dob=None,
        age_text="2 years",
        gender=None,
        weight=None,
        weight_flagged=False,
        neutered=None,
    )
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(
        onboarding,
        "_parse_gender_weight_neutered",
        AsyncMock(return_value={"gender": "male", "weight_kg": 10, "neutered": True}),
    )
    monkeypatch.setattr(onboarding, "_set_onboarding_data", lambda u, k, v: u.onboarding_data.__setitem__(k, v))

    await onboarding._step_gender_weight(
        db,
        user,
        "Max, male, 2 years, 10 kg, spayed",
        send_fn,
    )

    assert user.onboarding_state == "awaiting_gender_weight"
    sent_text = send_fn.await_args_list[-1].args[2]
    assert sent_text == "For male dogs the procedure is neutering, not spaying. Is Max neutered?"


@pytest.mark.asyncio
async def test_step_gender_weight_confirmation_yes_advances(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="+911234567890",
        onboarding_data={
            "gender_weight_attempts": 0,
            "gender_neuter_confirm_pending": True,
            "gender_neuter_confirm_payload": {"gender": "male", "neutered": True, "weight_kg": 10},
        },
        onboarding_state="awaiting_gender_weight",
    )
    pet = SimpleNamespace(
        id="pet-1",
        name="Max",
        species="dog",
        breed="Labrador",
        dob=None,
        age_text="2 years",
        gender=None,
        weight=None,
        weight_flagged=False,
        neutered=None,
    )
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(onboarding, "_set_onboarding_data", lambda u, k, v: u.onboarding_data.__setitem__(k, v))

    await onboarding._step_gender_weight(db, user, "yes", send_fn)

    assert user.onboarding_state == "awaiting_food_type"
    assert pet.gender == "male"
    assert pet.neutered is True
    assert pet.weight == 10.0
    assert "What does Max usually eat" in send_fn.await_args_list[-1].args[2]


def test_build_gender_neuter_confirmation_detects_spayed_with_punctuation() -> None:
    result = onboarding._build_gender_neuter_confirmation(
        text="Max is male, 10 kg, spayed.",
        parsed_gender="male",
        parsed_neutered=True,
        pet_name="Max",
    )
    assert result is not None
    assert result["prompt"] == "For male dogs the procedure is neutering, not spaying. Is Max neutered?"


@pytest.mark.asyncio
async def test_step_gender_weight_gender_choice_reply_advances(monkeypatch) -> None:
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="+911234567890",
        onboarding_data={
            "gender_weight_attempts": 0,
            "gender_neuter_confirm_pending": True,
            "gender_neuter_confirm_mode": "gender_choice",
            "gender_neuter_confirm_payload": {"weight_kg": 28, "neutered": True},
        },
        onboarding_state="awaiting_gender_weight",
    )
    pet = SimpleNamespace(
        id="pet-1",
        name="Bruno",
        species="dog",
        breed="Labrador",
        dob=None,
        age_text="3 years",
        gender=None,
        weight=None,
        weight_flagged=False,
        neutered=None,
    )
    db = SimpleNamespace(commit=lambda: None)
    send_fn = AsyncMock()

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _user_id: pet)
    monkeypatch.setattr(onboarding, "_set_onboarding_data", lambda u, k, v: u.onboarding_data.__setitem__(k, v))

    await onboarding._step_gender_weight(db, user, "female", send_fn)

    assert user.onboarding_state == "awaiting_food_type"
    assert pet.gender == "female"
    assert pet.weight == 28.0
    assert pet.neutered is True
    assert "What does Bruno usually eat" in send_fn.await_args_list[-1].args[2]
