"""Unit tests for category separation and duplicate-safe fallback messaging."""

from types import SimpleNamespace

from app.services.diet_service import split_diet_items_by_type
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


def test_filter_recommendations_excludes_existing_names():
    items = [
        {"name": "Omega-3 Fish Oil", "description": "", "reason": ""},
        {"name": "Digestive Probiotic", "description": "", "reason": ""},
        {"name": "Calcium Plus", "description": "", "reason": ""},
    ]
    existing_names = {"omega 3 fish oil", "digestive probiotic"}

    filtered = _filter_recommendations_against_existing(items, existing_names)

    assert [item["name"] for item in filtered] == ["Calcium Plus"]
