"""
Unit tests for get_diet_summary() and _diet_summary_threshold() in nutrition_service.py.

Covers:
  - _diet_summary_threshold: all 4 macros across every threshold boundary
  - Omega-3 at exactly 15 % → RED / "Critical gap"   (explicit requirement)
  - Green is never returned for >110 %
  - get_diet_summary: correct colour mapping from analyse_nutrition mock output
  - get_diet_summary: max 3 missing_micros, sorted by priority
  - get_diet_summary: graceful empty fallback when analyze_nutrition raises

All tests are pure Python — no DB, no network, no OpenAI.
analyze_nutrition is patched via unittest.mock.patch so nothing I/O-bound runs.
"""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("APP_ENV", "test")

from app.services.nutrition_service import (
    _diet_summary_threshold,
    get_diet_summary,
)

# ---------------------------------------------------------------------------
# _diet_summary_threshold — Calories
# ---------------------------------------------------------------------------


class TestDietSummaryThresholdCalories:
    def test_calories_at_100_pct_is_green(self):
        color, note = _diet_summary_threshold("Calories", 100.0)
        assert color == "green"
        assert note == "On track"

    def test_calories_below_100_pct_is_green(self):
        color, note = _diet_summary_threshold("Calories", 75.0)
        assert color == "green"

    def test_calories_above_100_pct_is_amber(self):
        color, note = _diet_summary_threshold("Calories", 100.1)
        assert color == "amber"
        assert note == "Slightly over target"

    def test_calories_well_over_is_amber_not_red(self):
        # Calories has no red zone — only green / amber
        color, _ = _diet_summary_threshold("Calories", 200.0)
        assert color == "amber"


# ---------------------------------------------------------------------------
# _diet_summary_threshold — Omega-3
# ---------------------------------------------------------------------------


class TestDietSummaryThresholdOmega3:
    def test_omega3_at_15_pct_is_red_critical(self):
        """Omega-3 at exactly 15 % must return RED 'Critical gap' (explicit req)."""
        color, note = _diet_summary_threshold("Omega-3", 15.0)
        assert color == "red"
        assert note == "Critical gap"

    def test_omega3_at_5_pct_is_red_critical(self):
        color, note = _diet_summary_threshold("Omega-3", 5.0)
        assert color == "red"
        assert note == "Critical gap"

    def test_omega3_at_0_pct_is_red_critical(self):
        color, note = _diet_summary_threshold("Omega-3", 0.0)
        assert color == "red"
        assert note == "Critical gap"

    def test_omega3_at_16_pct_is_red_deficient(self):
        """Just above critical threshold (16 %) is still red but not critical."""
        color, note = _diet_summary_threshold("Omega-3", 16.0)
        assert color == "red"
        assert note == "Deficient"

    def test_omega3_at_79_pct_is_red(self):
        color, _ = _diet_summary_threshold("Omega-3", 79.0)
        assert color == "red"

    def test_omega3_at_80_pct_is_green(self):
        color, _ = _diet_summary_threshold("Omega-3", 80.0)
        assert color == "green"

    def test_omega3_at_100_pct_is_green(self):
        color, _ = _diet_summary_threshold("Omega-3", 100.0)
        assert color == "green"

    def test_omega3_at_110_pct_is_green(self):
        color, _ = _diet_summary_threshold("Omega-3", 110.0)
        assert color == "green"

    def test_omega3_above_110_pct_is_amber(self):
        """Green NOT used for >110 %."""
        color, note = _diet_summary_threshold("Omega-3", 111.0)
        assert color == "amber"
        assert note == "Slightly over"

    def test_omega3_at_200_pct_is_amber_not_green(self):
        color, _ = _diet_summary_threshold("Omega-3", 200.0)
        assert color == "amber"


# ---------------------------------------------------------------------------
# _diet_summary_threshold — Protein
# ---------------------------------------------------------------------------


class TestDietSummaryThresholdProtein:
    def test_protein_at_79_pct_is_red(self):
        color, note = _diet_summary_threshold("Protein", 79.0)
        assert color == "red"
        assert note == "Deficient"

    def test_protein_at_80_pct_is_green(self):
        color, _ = _diet_summary_threshold("Protein", 80.0)
        assert color == "green"

    def test_protein_at_100_pct_is_green(self):
        color, _ = _diet_summary_threshold("Protein", 100.0)
        assert color == "green"

    def test_protein_at_110_pct_is_green(self):
        color, _ = _diet_summary_threshold("Protein", 110.0)
        assert color == "green"

    def test_protein_above_110_pct_is_amber(self):
        """Green NOT used for >110 %."""
        color, note = _diet_summary_threshold("Protein", 110.1)
        assert color == "amber"
        assert note == "Slightly over"


# ---------------------------------------------------------------------------
# _diet_summary_threshold — Fat
# ---------------------------------------------------------------------------


class TestDietSummaryThresholdFat:
    def test_fat_at_79_pct_is_red(self):
        color, _ = _diet_summary_threshold("Fat", 79.0)
        assert color == "red"

    def test_fat_at_80_pct_is_green(self):
        color, _ = _diet_summary_threshold("Fat", 80.0)
        assert color == "green"

    def test_fat_above_110_pct_is_amber(self):
        color, _ = _diet_summary_threshold("Fat", 120.0)
        assert color == "amber"

    def test_fat_at_110_pct_is_green_not_amber(self):
        color, _ = _diet_summary_threshold("Fat", 110.0)
        assert color == "green"


# ---------------------------------------------------------------------------
# get_diet_summary — integration with mocked analyze_nutrition
# ---------------------------------------------------------------------------

def _make_pet(pet_id="pet-001") -> SimpleNamespace:
    return SimpleNamespace(id=pet_id)


def _base_analysis() -> dict:
    """Return a realistic analyze_nutrition output for a healthy pet."""
    return {
        "calories": {"actual": 1100, "target": 1200, "status": "adequate"},
        "macros": [
            {"name": "Protein", "actual": 22.0, "target": 25.0, "unit": "%",
             "status": "Low", "note": "Consider protein-rich supplements"},
            {"name": "Fat", "actual": 14.5, "target": 14.0, "unit": "%",
             "status": "Adequate", "note": "Essential for energy"},
            {"name": "Carbohydrates", "actual": 50.0, "target": 50.0, "unit": "%",
             "status": "Adequate", "note": ""},
            {"name": "Fibre", "actual": 4.0, "target": 4.0, "unit": "%",
             "status": "Adequate", "note": ""},
            {"name": "Moisture", "actual": 10.0, "target": 10.0, "unit": "%",
             "status": "Adequate", "note": ""},
        ],
        "vitamins": [
            {"name": "Vitamin E", "status": "Missing", "priority": "high",
             "supplement": "Vit E 400 IU", "price": "Rs.349/mo"},
            {"name": "Vitamin D3", "status": "Adequate", "priority": "ok",
             "supplement": None, "price": None},
        ],
        "minerals": [
            {"name": "Glucosamine", "icon": "🦴", "status": "Low", "priority": "medium",
             "reason": "Supports joint health", "actual": 200, "target": 500},
            {"name": "Calcium", "icon": "🦷", "status": "Adequate", "priority": "ok",
             "reason": "Essential for bones", "actual": 1.0, "target": 1.0},
            {"name": "Phosphorus", "icon": "⚡", "status": "Adequate", "priority": "ok",
             "reason": "Works with calcium", "actual": 0.8, "target": 0.8},
        ],
        "others": [
            {"name": "Omega-3", "icon": "🐟", "status": "Missing", "priority": "urgent",
             "reason": "Critical for skin and joints", "actual": 45, "target": 300},
            {"name": "Omega-6", "icon": "🌻", "status": "Adequate", "priority": "ok",
             "actual": 1500, "target": 1500},
            {"name": "Probiotics", "icon": "🦠", "status": "Low", "priority": "medium",
             "actual": 0, "target": 1},
        ],
        "improvements": [],
        "overall_label": "moderate",
        "recommendation": "Consider Omega-3 supplementation.",
        "diet_summary": "Current diet: Royal Canin.",
        "analysis_context": "Analysis based on Golden Retriever breed profile",
        "gap_count": 3,
    }


class TestGetDietSummary:
    """Tests for get_diet_summary using a mocked analyze_nutrition."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _patch_analysis(self, analysis_data: dict):
        """Context manager that patches analyze_nutrition with fixed data."""
        return patch(
            "app.services.nutrition_service.analyze_nutrition",
            new=AsyncMock(return_value=analysis_data),
        )

    # --- Macro structure ---

    def test_returns_four_macros(self):
        pet = _make_pet()
        with self._patch_analysis(_base_analysis()):
            result = self._run(get_diet_summary(None, pet))
        assert len(result["macros"]) == 4

    def test_macro_names_are_correct(self):
        pet = _make_pet()
        with self._patch_analysis(_base_analysis()):
            result = self._run(get_diet_summary(None, pet))
        names = [m["name"] for m in result["macros"]]
        assert names == ["Calories", "Protein", "Omega-3", "Fat"]

    def test_macro_fields_present(self):
        pet = _make_pet()
        with self._patch_analysis(_base_analysis()):
            result = self._run(get_diet_summary(None, pet))
        for macro in result["macros"]:
            assert "name" in macro
            assert "pct_of_need" in macro
            assert "color" in macro
            assert "note" in macro

    # --- Colour correctness ---

    def test_calories_under_target_is_green(self):
        """1100 kcal / 1200 target = ~91.7 % → green."""
        pet = _make_pet()
        with self._patch_analysis(_base_analysis()):
            result = self._run(get_diet_summary(None, pet))
        calories_macro = next(m for m in result["macros"] if m["name"] == "Calories")
        assert calories_macro["color"] == "green"

    def test_omega3_critical_deficiency_is_red(self):
        """45 mg / 300 mg = 15.0 % → Omega-3 critical → RED."""
        pet = _make_pet()
        analysis = _base_analysis()
        # Set Omega-3 actual=45, target=300 → 15 %
        for item in analysis["others"]:
            if item["name"] == "Omega-3":
                item["actual"] = 45
                item["target"] = 300
                break
        with self._patch_analysis(analysis):
            result = self._run(get_diet_summary(None, pet))
        omega3_macro = next(m for m in result["macros"] if m["name"] == "Omega-3")
        assert omega3_macro["color"] == "red"
        assert omega3_macro["note"] == "Critical gap"
        assert omega3_macro["pct_of_need"] == 15.0

    def test_fat_slightly_over_is_amber(self):
        """fat actual=16, target=14 → 114.3 % → amber."""
        pet = _make_pet()
        analysis = _base_analysis()
        for m in analysis["macros"]:
            if m["name"] == "Fat":
                m["actual"] = 16.0
                m["target"] = 14.0
                break
        with self._patch_analysis(analysis):
            result = self._run(get_diet_summary(None, pet))
        fat_macro = next(m for m in result["macros"] if m["name"] == "Fat")
        assert fat_macro["color"] == "amber"

    def test_protein_deficient_is_red(self):
        """protein actual=18, target=25 → 72 % → red."""
        pet = _make_pet()
        analysis = _base_analysis()
        for m in analysis["macros"]:
            if m["name"] == "Protein":
                m["actual"] = 18.0
                m["target"] = 25.0
                break
        with self._patch_analysis(analysis):
            result = self._run(get_diet_summary(None, pet))
        protein_macro = next(m for m in result["macros"] if m["name"] == "Protein")
        assert protein_macro["color"] == "red"

    def test_no_green_for_over_110_pct(self):
        """All macros with >110 % must not return green."""
        pet = _make_pet()
        analysis = _base_analysis()
        # Pump up protein and fat and omega-3 way over 110 %
        for m in analysis["macros"]:
            if m["name"] == "Protein":
                m["actual"] = 30.0
                m["target"] = 25.0    # 120 %
            if m["name"] == "Fat":
                m["actual"] = 20.0
                m["target"] = 14.0    # ~143 %
        for item in analysis["others"]:
            if item["name"] == "Omega-3":
                item["actual"] = 400
                item["target"] = 300  # ~133 %
        # Pump calories over 100 %
        analysis["calories"]["actual"] = 1500
        analysis["calories"]["target"] = 1200  # 125 %

        with self._patch_analysis(analysis):
            result = self._run(get_diet_summary(None, pet))

        for macro in result["macros"]:
            assert macro["color"] != "green", (
                f"{macro['name']} at {macro['pct_of_need']}% returned green but should not"
            )

    # --- missing_micros ---

    def test_missing_micros_max_3(self):
        """Even if many nutrients are deficient, only 3 are returned."""
        pet = _make_pet()
        with self._patch_analysis(_base_analysis()):
            result = self._run(get_diet_summary(None, pet))
        assert len(result["missing_micros"]) <= 3

    def test_missing_micros_sorted_by_priority(self):
        """Urgent nutrients appear before high, which appear before medium."""
        pet = _make_pet()
        with self._patch_analysis(_base_analysis()):
            result = self._run(get_diet_summary(None, pet))
        priority_order = {"urgent": 0, "high": 1, "medium": 2}
        # Map returned micro names back to priorities in the analysis
        analysis = _base_analysis()
        all_nutrients = analysis["minerals"] + analysis["others"] + analysis["vitamins"]
        name_to_priority = {n["name"]: n.get("priority", "ok") for n in all_nutrients}
        ranks = [
            priority_order.get(name_to_priority.get(m["name"], "ok"), 3)
            for m in result["missing_micros"]
        ]
        assert ranks == sorted(ranks), "missing_micros not sorted by priority"

    def test_missing_micro_fields_present(self):
        pet = _make_pet()
        with self._patch_analysis(_base_analysis()):
            result = self._run(get_diet_summary(None, pet))
        for micro in result["missing_micros"]:
            assert "icon" in micro
            assert "name" in micro
            assert "reason" in micro

    def test_missing_micros_excludes_adequate_nutrients(self):
        """Nutrients with status 'Adequate' / priority 'ok' must not appear."""
        pet = _make_pet()
        adequate_names = {"Calcium", "Phosphorus", "Omega-6", "Vitamin D3"}
        with self._patch_analysis(_base_analysis()):
            result = self._run(get_diet_summary(None, pet))
        returned_names = {m["name"] for m in result["missing_micros"]}
        assert not returned_names.intersection(adequate_names), (
            f"Adequate nutrients appeared in missing_micros: "
            f"{returned_names.intersection(adequate_names)}"
        )

    # --- Graceful fallback ---

    def test_fallback_on_exception(self):
        """If analyze_nutrition raises, get_diet_summary returns empty dicts."""
        pet = _make_pet()
        with patch(
            "app.services.nutrition_service.analyze_nutrition",
            new=AsyncMock(side_effect=ValueError("pet not found")),
        ):
            result = self._run(get_diet_summary(None, pet))
        assert result == {"macros": [], "missing_micros": []}

    def test_fallback_returns_dict_structure(self):
        """Fallback return value always has the two expected keys."""
        pet = _make_pet()
        with patch(
            "app.services.nutrition_service.analyze_nutrition",
            new=AsyncMock(side_effect=RuntimeError("db down")),
        ):
            result = self._run(get_diet_summary(None, pet))
        assert "macros" in result
        assert "missing_micros" in result
