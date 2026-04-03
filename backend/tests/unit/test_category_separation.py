"""Unit tests for category separation and duplicate-safe fallback messaging."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.diet_service import split_diet_items_by_type
from app.services.onboarding import _generate_care_plan_message
from app.services.recommendation_service import _filter_recommendations_against_existing


def test_split_diet_items_by_type_keeps_foods_and_supplements_separate():
    items = [
        SimpleNamespace(type="packaged", label="Royal Canin Adult"),
        SimpleNamespace(type="homemade", label="Chicken Rice"),
        SimpleNamespace(type="supplement", label="Omega-3 Oil"),
        SimpleNamespace(type="supplement", label="Probiotic"),
    ]

    split = split_diet_items_by_type(items)

    assert split["foods"] == ["Royal Canin Adult", "Chicken Rice"]
    assert split["supplements"] == ["Omega-3 Oil", "Probiotic"]
    assert split["other"] == []


def test_care_plan_fallback_avoids_existing_omega3_and_probiotic():
    pet = SimpleNamespace(name="Buddy", breed="Labrador", age_text="4 years", dob=None)
    diet_items = [
        SimpleNamespace(type="packaged", label="Royal Canin Adult"),
        SimpleNamespace(type="supplement", label="Omega-3 Fish Oil"),
        SimpleNamespace(type="supplement", label="Probiotic Blend"),
    ]

    with patch("app.services.onboarding._ai_supplement_recommendation", new=AsyncMock(return_value=None)):
        message = asyncio.run(
            _generate_care_plan_message(
                pet=pet,
                diet_count=1,
                supplement_count=2,
                record_count=1,
                docs_uploaded=0,
                conditions=[],
                diet_items=diet_items,
            )
        )

    lowered = message.lower()
    assert "we'd suggest" in lowered
    assert "omega-3" not in lowered
    assert "probiotic" not in lowered


def test_care_plan_fallback_no_new_supp_when_common_stack_already_present():
    pet = SimpleNamespace(name="Buddy", breed="Labrador", age_text="4 years", dob=None)
    diet_items = [
        SimpleNamespace(type="packaged", label="Royal Canin Adult"),
        SimpleNamespace(type="supplement", label="Omega-3 Fish Oil"),
        SimpleNamespace(type="supplement", label="Probiotic Blend"),
        SimpleNamespace(type="supplement", label="Calcium"),
        SimpleNamespace(type="supplement", label="Joint Support"),
    ]

    with patch("app.services.onboarding._ai_supplement_recommendation", new=AsyncMock(return_value=None)):
        message = asyncio.run(
            _generate_care_plan_message(
                pet=pet,
                diet_count=1,
                supplement_count=4,
                record_count=1,
                docs_uploaded=0,
                conditions=[],
                diet_items=diet_items,
            )
        )

    lowered = message.lower()
    assert "don't suggest adding anything new" in lowered


def test_filter_recommendations_excludes_existing_names():
    items = [
        {"name": "Omega-3 Fish Oil", "description": "", "reason": ""},
        {"name": "Digestive Probiotic", "description": "", "reason": ""},
        {"name": "Calcium Plus", "description": "", "reason": ""},
    ]
    existing_names = {"omega 3 fish oil", "digestive probiotic"}

    filtered = _filter_recommendations_against_existing(items, existing_names)

    assert [item["name"] for item in filtered] == ["Calcium Plus"]
