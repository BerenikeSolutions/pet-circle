from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import onboarding


class _FakeDB:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def _patch_set_onboarding_data(monkeypatch):
    monkeypatch.setattr(
        onboarding,
        "_set_onboarding_data",
        lambda u, key, value: u.onboarding_data.__setitem__(key, value),
    )


@pytest.mark.anyio
async def test_step_breed_age_handles_non_dog_species_in_species_prompt(monkeypatch):
    db = _FakeDB()
    pet = SimpleNamespace(name="Bun", species="_pending", breed=None, age_text=None, dob=None)
    user = SimpleNamespace(
        id="u1",
        onboarding_state="awaiting_breed_age",
        _plaintext_mobile="911234567890",
        onboarding_data={"needs_species": True, "breed_age_attempts": 0},
    )

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _uid: pet)
    _patch_set_onboarding_data(monkeypatch)

    sent_messages = []

    async def _send_fn(_db, _to, text):
        sent_messages.append(text)

    await onboarding._step_breed_age(db, user, "rabbit", _send_fn)

    assert user.onboarding_state == "awaiting_breed_age"
    assert pet.species == "_pending"
    assert db.commits == 1
    assert sent_messages
    assert "dogs only" in sent_messages[-1].lower()
    assert "waitlist" in sent_messages[-1].lower()
    assert "rabbit" in sent_messages[-1].lower()


@pytest.mark.anyio
async def test_step_breed_age_handles_non_dog_species_in_combined_input(monkeypatch):
    db = _FakeDB()
    pet = SimpleNamespace(name="Bun", species="_pending", breed=None, age_text=None, dob=None)
    user = SimpleNamespace(
        id="u1",
        onboarding_state="awaiting_breed_age",
        _plaintext_mobile="911234567890",
        onboarding_data={"breed_age_attempts": 0},
    )

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _uid: pet)
    _patch_set_onboarding_data(monkeypatch)
    parse_mock = AsyncMock()
    monkeypatch.setattr(onboarding, "_parse_breed_age", parse_mock)

    sent_messages = []

    async def _send_fn(_db, _to, text):
        sent_messages.append(text)

    await onboarding._step_breed_age(
        db,
        user,
        "My pet is a rabbit, Holland Lop, 2 years old",
        _send_fn,
    )

    parse_mock.assert_not_awaited()
    assert user.onboarding_state == "awaiting_breed_age"
    assert pet.species == "_pending"
    assert db.commits == 1
    assert sent_messages
    assert "dogs only" in sent_messages[-1].lower()
    assert "waitlist" in sent_messages[-1].lower()
    assert "rabbit" in sent_messages[-1].lower()


@pytest.mark.anyio
async def test_step_breed_age_mixed_species_text_prefers_dog(monkeypatch):
    db = _FakeDB()
    pet = SimpleNamespace(name="Bolt", species="_pending", breed=None, age_text=None, dob=None)
    user = SimpleNamespace(
        id="u1",
        onboarding_state="awaiting_breed_age",
        _plaintext_mobile="911234567890",
        onboarding_data={"needs_species": True, "breed_age_attempts": 0},
    )

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _uid: pet)
    _patch_set_onboarding_data(monkeypatch)

    sent_messages = []

    async def _send_fn(_db, _to, text):
        sent_messages.append(text)

    await onboarding._step_breed_age(db, user, "dog not cat", _send_fn)

    assert user.onboarding_state == "awaiting_gender_weight"
    assert pet.species == "dog"
    assert db.commits == 1
    assert sent_messages
    assert "gender and approximate weight" in sent_messages[-1].lower()


@pytest.mark.anyio
async def test_step_breed_age_waitlist_acknowledges_after_non_dog_prompt(monkeypatch):
    db = _FakeDB()
    pet = SimpleNamespace(name="Bun", species="_pending", breed=None, age_text=None, dob=None)
    user = SimpleNamespace(
        id="u1",
        onboarding_state="awaiting_breed_age",
        _plaintext_mobile="911234567890",
        onboarding_data={"non_dog_waitlist_prompted": True, "breed_age_attempts": 0},
    )

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _uid: pet)
    _patch_set_onboarding_data(monkeypatch)

    sent_messages = []

    async def _send_fn(_db, _to, text):
        sent_messages.append(text)

    await onboarding._step_breed_age(db, user, "WAITLIST", _send_fn)

    assert user.onboarding_state == "awaiting_breed_age"
    assert sent_messages
    assert "waitlist" in sent_messages[-1].lower()


@pytest.mark.anyio
async def test_step_breed_age_negated_dog_phrase_does_not_continue_dog_flow(monkeypatch):
    db = _FakeDB()
    pet = SimpleNamespace(name="Bun", species="_pending", breed=None, age_text=None, dob=None)
    user = SimpleNamespace(
        id="u1",
        onboarding_state="awaiting_breed_age",
        _plaintext_mobile="911234567890",
        onboarding_data={"needs_species": True, "breed_age_attempts": 0},
    )

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _uid: pet)
    _patch_set_onboarding_data(monkeypatch)

    sent_messages = []

    async def _send_fn(_db, _to, text):
        sent_messages.append(text)

    await onboarding._step_breed_age(db, user, "not a dog, rabbit", _send_fn)

    assert user.onboarding_state == "awaiting_breed_age"
    assert pet.species == "_pending"
    assert sent_messages
    assert "dogs only" in sent_messages[-1].lower()


@pytest.mark.anyio
async def test_step_breed_age_recognises_cat_breed_as_non_dog(monkeypatch):
    """'domestic short hair' is a cat breed — should trigger out-of-scope, not proceed."""
    db = _FakeDB()
    pet = SimpleNamespace(name="Mimi", species="_pending", breed=None, age_text=None, dob=None)
    user = SimpleNamespace(
        id="u1",
        onboarding_state="awaiting_breed_age",
        _plaintext_mobile="911234567890",
        onboarding_data={"needs_species": True, "breed_age_attempts": 0},
    )

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _uid: pet)
    _patch_set_onboarding_data(monkeypatch)

    sent_messages = []

    async def _send_fn(_db, _to, text):
        sent_messages.append(text)

    await onboarding._step_breed_age(db, user, "domestic short hair", _send_fn)

    assert user.onboarding_state == "awaiting_breed_age"
    assert pet.species == "_pending"
    assert db.commits == 1
    assert sent_messages
    assert "dogs only" in sent_messages[-1].lower()


@pytest.mark.anyio
async def test_step_breed_age_recognises_british_shorthair_as_non_dog(monkeypatch):
    """'british shorthair' is a cat breed — should trigger out-of-scope."""
    db = _FakeDB()
    pet = SimpleNamespace(name="Luna", species="_pending", breed=None, age_text=None, dob=None)
    user = SimpleNamespace(
        id="u1",
        onboarding_state="awaiting_breed_age",
        _plaintext_mobile="911234567890",
        onboarding_data={"needs_species": True, "breed_age_attempts": 0},
    )

    monkeypatch.setattr(onboarding, "_get_pending_pet", lambda _db, _uid: pet)
    _patch_set_onboarding_data(monkeypatch)

    sent_messages = []

    async def _send_fn(_db, _to, text):
        sent_messages.append(text)

    await onboarding._step_breed_age(db, user, "british shorthair", _send_fn)

    assert user.onboarding_state == "awaiting_breed_age"
    assert pet.species == "_pending"
    assert db.commits == 1
    assert sent_messages
    assert "dogs only" in sent_messages[-1].lower()
