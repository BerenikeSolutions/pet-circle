import os
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

os.environ.setdefault("APP_ENV", "test")

from app.services.care_plan_engine import BREED_SIZE_BOUNDARIES, BreedSize
from app.services.life_stage_service import LifeStageData, get_life_stage_data


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = {}

    def filter_by(self, **kwargs):
        self._filters.update(kwargs)
        return self

    def all(self):
        filtered = []
        for row in self._rows:
            if all(getattr(row, key, None) == value for key, value in self._filters.items()):
                filtered.append(row)
        return filtered


class FakeSession:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.added = []
        self.deleted = []
        self.commit_count = 0

    def query(self, model):
        return FakeQuery(self.rows)

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commit_count += 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "breed_size,boundary_months",
    [
        (BreedSize.MINI_TOY, BREED_SIZE_BOUNDARIES[BreedSize.MINI_TOY]["senior_start"]),
        (BreedSize.SMALL, BREED_SIZE_BOUNDARIES[BreedSize.SMALL]["senior_start"]),
        (BreedSize.MEDIUM, BREED_SIZE_BOUNDARIES[BreedSize.MEDIUM]["senior_start"]),
        (BreedSize.LARGE, BREED_SIZE_BOUNDARIES[BreedSize.LARGE]["senior_start"]),
        (
            BreedSize.EXTRA_LARGE,
            BREED_SIZE_BOUNDARIES[BreedSize.EXTRA_LARGE]["senior_start"],
        ),
    ],
)
async def test_get_life_stage_data_boundary_senior_for_all_breed_sizes(
    monkeypatch,
    breed_size,
    boundary_months,
):
    pet = SimpleNamespace(id=uuid4(), breed="Any", weight=20, dob=date(2020, 1, 1))
    db = FakeSession(
        rows=[
            SimpleNamespace(
                pet_id=pet.id,
                life_stage="senior",
                breed_size=breed_size.value,
                traits=[{"label": "Calmer energy", "color": "neutral"}],
                essential_care=[{"icon": "🩺", "title": "Checkup", "detail": "Annual panel"}],
            )
        ]
    )

    monkeypatch.setattr("app.services.life_stage_service._get_pet_age_months", lambda _pet: boundary_months)
    monkeypatch.setattr("app.services.life_stage_service._get_breed_size", lambda _w, _b: breed_size)

    result = await get_life_stage_data(db, pet)

    assert result.stage == "senior"
    assert result.breed_size == breed_size.value


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_traits_without_gpt(monkeypatch):
    pet = SimpleNamespace(id=uuid4(), breed="Labrador", weight=30, dob=date(2020, 1, 1))
    cached = SimpleNamespace(
        pet_id=pet.id,
        life_stage="adult",
        breed_size="large",
        traits=[{"label": "Stable appetite", "color": "green"}],
        essential_care=[{"icon": "🥗", "title": "Diet", "detail": "Maintain balanced portions"}],
    )
    db = FakeSession(rows=[cached])

    monkeypatch.setattr("app.services.life_stage_service._get_pet_age_months", lambda _pet: 48)
    monkeypatch.setattr("app.services.life_stage_service._get_breed_size", lambda _w, _b: BreedSize.LARGE)

    async def should_not_call_gpt(*args, **kwargs):
        raise AssertionError("GPT generation should not run when cache is present")

    monkeypatch.setattr(
        "app.services.life_stage_service._generate_life_stage_traits_gpt",
        should_not_call_gpt,
    )

    result = await get_life_stage_data(db, pet)

    assert isinstance(result, LifeStageData)
    assert result.stage == "adult"
    assert result.traits == cached.traits
    assert result.essential_care == cached.essential_care
    assert db.commit_count == 0
    assert db.added == []
    assert db.deleted == []


@pytest.mark.asyncio
async def test_cache_miss_generates_and_invalidates_old_stage(monkeypatch):
    pet = SimpleNamespace(id=uuid4(), breed="Labrador", weight=30, dob=date(2020, 1, 1))
    stale = SimpleNamespace(
        pet_id=pet.id,
        life_stage="junior",
        breed_size="large",
        traits=[],
        essential_care=[],
    )
    db = FakeSession(rows=[stale])

    monkeypatch.setattr("app.services.life_stage_service._get_pet_age_months", lambda _pet: 48)
    monkeypatch.setattr("app.services.life_stage_service._get_breed_size", lambda _w, _b: BreedSize.LARGE)

    async def fake_generate(*args, **kwargs):
        return SimpleNamespace(
            traits=[{"label": "Mature energy", "color": "neutral"}],
            essential_care=[{"icon": "🩺", "title": "Annual checks", "detail": "Track bloodwork yearly"}],
        )

    monkeypatch.setattr("app.services.life_stage_service._generate_life_stage_traits_gpt", fake_generate)

    result = await get_life_stage_data(db, pet)

    assert result.stage == "adult"
    assert len(db.deleted) == 1
    assert db.deleted[0] is stale
    assert len(db.added) == 1
    assert db.added[0].life_stage == "adult"
    assert db.commit_count == 1


@pytest.mark.asyncio
async def test_cache_miss_generates_when_breed_size_changes_same_stage(monkeypatch):
    pet = SimpleNamespace(id=uuid4(), breed="Labrador", weight=30, dob=date(2020, 1, 1))
    stale_same_stage = SimpleNamespace(
        pet_id=pet.id,
        life_stage="adult",
        breed_size="small",
        traits=[{"label": "Old profile", "color": "neutral"}],
        essential_care=[],
    )
    db = FakeSession(rows=[stale_same_stage])

    monkeypatch.setattr("app.services.life_stage_service._get_pet_age_months", lambda _pet: 48)
    monkeypatch.setattr("app.services.life_stage_service._get_breed_size", lambda _w, _b: BreedSize.LARGE)

    async def fake_generate(*args, **kwargs):
        return SimpleNamespace(
            traits=[{"label": "Updated profile", "color": "green"}],
            essential_care=[{"icon": "🩺", "title": "Annual checks", "detail": "Use current size profile"}],
        )

    monkeypatch.setattr("app.services.life_stage_service._generate_life_stage_traits_gpt", fake_generate)

    result = await get_life_stage_data(db, pet)

    assert result.stage == "adult"
    assert result.breed_size == "large"
    assert len(db.deleted) == 1
    assert db.deleted[0] is stale_same_stage
    assert len(db.added) == 1
    assert db.added[0].breed_size == "large"
    assert db.commit_count == 1


@pytest.mark.asyncio
async def test_gpt_failure_returns_empty_payload(monkeypatch):
    db = FakeSession(rows=[])
    pet = SimpleNamespace(id=uuid4(), breed="Indie", weight=12, dob=date(2020, 1, 1))

    monkeypatch.setattr("app.services.life_stage_service._get_pet_age_months", lambda _pet: 36)
    monkeypatch.setattr("app.services.life_stage_service._get_breed_size", lambda _w, _b: BreedSize.MEDIUM)

    async def broken_generate(*args, **kwargs):
        raise RuntimeError("openai unavailable")

    monkeypatch.setattr("app.services.life_stage_service._generate_life_stage_traits_gpt", broken_generate)

    result = await get_life_stage_data(db, pet)

    assert result.stage == "adult"
    assert result.traits == []
    assert result.essential_care == []
    assert db.added == []
    assert db.deleted == []
    assert db.commit_count == 0
