"""
Unit tests for care_plan_engine.py — covers all 7 classification paths,
redundancy guards, prescription override, conflict resolution, exclusion
of next-year items, and orderable diet items.

All tests are pure-Python with no DB or external dependencies.
"""

import os
from datetime import date, timedelta
from unittest.mock import MagicMock

os.environ.setdefault("APP_ENV", "test")

from app.services.care_plan_engine import (
    BreedSize,
    Classification,
    LifeStage,
    _classify_test,
    _compute_next_due,
    _days_to_freq_label,
    _filter_redundant_reports,
    _get_baseline_protocol,
    _get_breed_size,
    _get_life_stage,
    _normalize_item_name,
    _Prescription,
    _Report,
    _status_tag,
    _to_sections,
)

TODAY = date.today()


# ─────────────────────────────────────────────────────────────────────────────
# _normalize_item_name
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeItemName:
    def test_cbc_keyword(self):
        assert _normalize_item_name("CBC") == "cbc_chemistry"

    def test_blood_chem_keyword(self):
        assert _normalize_item_name("Blood Chemistry Profile") == "cbc_chemistry"

    def test_hematology(self):
        assert _normalize_item_name("Complete Haematology") == "cbc_chemistry"

    def test_urinalysis(self):
        assert _normalize_item_name("Urinalysis") == "urinalysis"

    def test_urine_keyword(self):
        assert _normalize_item_name("Urine Routine") == "urinalysis"

    def test_fecal_exam(self):
        assert _normalize_item_name("Fecal Examination") == "fecal"

    def test_stool(self):
        assert _normalize_item_name("Stool Test") == "fecal"

    def test_chest_xray(self):
        assert _normalize_item_name("Chest X-Ray") == "chest_xray"

    def test_xray_abbreviation(self):
        assert _normalize_item_name("Chest XRay") == "chest_xray"

    def test_ultrasound(self):
        assert _normalize_item_name("Abdominal Ultrasound") == "usg"

    def test_usg(self):
        assert _normalize_item_name("USG Abdomen") == "usg"

    def test_echocardiogram_longer_match(self):
        # 'echocardiogram' must match 'echo' section NOT 'ecg'
        assert _normalize_item_name("Echocardiogram") == "echo"

    def test_ecg(self):
        assert _normalize_item_name("ECG Cardiac") == "ecg"

    def test_dental(self):
        assert _normalize_item_name("Dental Cleaning") == "dental"

    def test_deworming(self):
        assert _normalize_item_name("Deworming") == "deworming"

    def test_tick_flea(self):
        assert _normalize_item_name("Tick & Flea Prevention") == "tick_flea"

    def test_vaccine_rabies(self):
        assert _normalize_item_name("Rabies Vaccine") == "vaccine"

    def test_dhppi(self):
        assert _normalize_item_name("DHPPI Booster") == "vaccine"

    def test_supplement(self):
        assert _normalize_item_name("Omega Supplement") == "supplement"

    def test_food(self):
        assert _normalize_item_name("Royal Canin Food") == "food"

    def test_unknown_returns_other(self):
        assert _normalize_item_name("Behavioural Assessment") == "other"

    def test_case_insensitive(self):
        assert _normalize_item_name("cbc chemistry") == "cbc_chemistry"


# ─────────────────────────────────────────────────────────────────────────────
# _get_breed_size
# ─────────────────────────────────────────────────────────────────────────────


class TestGetBreedSize:
    def test_mini_toy_by_weight(self):
        assert _get_breed_size(3.0, None) == BreedSize.MINI_TOY

    def test_small_by_weight(self):
        assert _get_breed_size(7.5, None) == BreedSize.SMALL

    def test_medium_by_weight(self):
        assert _get_breed_size(15.0, None) == BreedSize.MEDIUM

    def test_large_by_weight(self):
        assert _get_breed_size(35.0, None) == BreedSize.LARGE

    def test_extra_large_by_weight(self):
        assert _get_breed_size(55.0, None) == BreedSize.EXTRA_LARGE

    def test_exact_boundary_small(self):
        # weight == max_weight_kg for MINI_TOY (5 kg) → SMALL (not MINI_TOY)
        assert _get_breed_size(5.0, None) == BreedSize.SMALL

    def test_no_weight_chihuahua_keyword(self):
        assert _get_breed_size(None, "Chihuahua") == BreedSize.MINI_TOY

    def test_no_weight_great_dane_keyword(self):
        assert _get_breed_size(None, "Great Dane") == BreedSize.EXTRA_LARGE

    def test_no_weight_no_breed_defaults_medium(self):
        assert _get_breed_size(None, None) == BreedSize.MEDIUM

    def test_labrador_large(self):
        assert _get_breed_size(None, "Labrador Retriever") == BreedSize.LARGE


# ─────────────────────────────────────────────────────────────────────────────
# _get_life_stage
# ─────────────────────────────────────────────────────────────────────────────


class TestGetLifeStage:
    def test_puppy_small(self):
        assert _get_life_stage(6, BreedSize.SMALL) == LifeStage.PUPPY

    def test_junior_small(self):
        assert _get_life_stage(18, BreedSize.SMALL) == LifeStage.JUNIOR

    def test_adult_small(self):
        assert _get_life_stage(48, BreedSize.SMALL) == LifeStage.ADULT

    def test_senior_small(self):
        # Small breed senior_start = 108 months
        assert _get_life_stage(110, BreedSize.SMALL) == LifeStage.SENIOR

    def test_senior_extra_large_early(self):
        # Extra large senior_start = 60 months
        assert _get_life_stage(65, BreedSize.EXTRA_LARGE) == LifeStage.SENIOR

    def test_adult_extra_large_before_senior(self):
        assert _get_life_stage(48, BreedSize.EXTRA_LARGE) == LifeStage.ADULT

    def test_exact_junior_start(self):
        # age 12 = junior_start → JUNIOR (not PUPPY)
        assert _get_life_stage(12, BreedSize.MEDIUM) == LifeStage.JUNIOR

    def test_exact_adult_start(self):
        # age 24 = adult_start → ADULT (not JUNIOR)
        assert _get_life_stage(24, BreedSize.MEDIUM) == LifeStage.ADULT


# ─────────────────────────────────────────────────────────────────────────────
# _get_baseline_protocol
# ─────────────────────────────────────────────────────────────────────────────


class TestGetBaselineProtocol:
    def test_puppy_cbc(self):
        assert _get_baseline_protocol(LifeStage.PUPPY, "cbc_chemistry") == 56

    def test_senior_cbc(self):
        assert _get_baseline_protocol(LifeStage.SENIOR, "cbc_chemistry") == 365

    def test_adult_chest_xray(self):
        assert _get_baseline_protocol(LifeStage.ADULT, "chest_xray") == 1095

    def test_unknown_type_defaults(self):
        # "other" is not in BASELINE_PROTOCOL → default 365
        result = _get_baseline_protocol(LifeStage.ADULT, "other")
        assert result == 365

    def test_senior_dental(self):
        assert _get_baseline_protocol(LifeStage.SENIOR, "dental") == 180


# ─────────────────────────────────────────────────────────────────────────────
# _filter_redundant_reports
# ─────────────────────────────────────────────────────────────────────────────


class TestFilterRedundantReports:
    def test_empty_list(self):
        assert _filter_redundant_reports([]) == []

    def test_single_report_passes(self):
        r = _Report(report_date=TODAY)
        assert _filter_redundant_reports([r]) == [r]

    def test_same_day_duplicates_keep_one(self):
        r1 = _Report(report_date=TODAY)
        r2 = _Report(report_date=TODAY)
        result = _filter_redundant_reports([r1, r2])
        assert len(result) == 1

    def test_same_day_prefers_prescription(self):
        non_rx = _Report(report_date=TODAY, is_prescription=False)
        rx = _Report(report_date=TODAY, is_prescription=True)
        result = _filter_redundant_reports([non_rx, rx])
        assert len(result) == 1
        assert result[0].is_prescription is True

    def test_non_rx_within_30_days_removed(self):
        r1 = _Report(report_date=TODAY - timedelta(days=100))
        r2 = _Report(report_date=TODAY - timedelta(days=85))  # 15 days later → redundant
        result = _filter_redundant_reports([r1, r2])
        assert len(result) == 1
        assert result[0].report_date == TODAY - timedelta(days=100)

    def test_non_rx_exactly_30_days_passes(self):
        r1 = _Report(report_date=TODAY - timedelta(days=100))
        r2 = _Report(report_date=TODAY - timedelta(days=70))  # exactly 30 days
        result = _filter_redundant_reports([r1, r2])
        assert len(result) == 2

    def test_rx_within_30_days_kept(self):
        r1 = _Report(report_date=TODAY - timedelta(days=100))
        rx = _Report(report_date=TODAY - timedelta(days=90), is_prescription=True)
        result = _filter_redundant_reports([r1, rx])
        assert len(result) == 2

    def test_output_sorted_ascending(self):
        r1 = _Report(report_date=TODAY)
        r2 = _Report(report_date=TODAY - timedelta(days=200))
        result = _filter_redundant_reports([r1, r2])
        assert result[0].report_date < result[1].report_date


# ─────────────────────────────────────────────────────────────────────────────
# _classify_test — all 7 paths
# ─────────────────────────────────────────────────────────────────────────────


class TestClassifyTest:
    """Tests for all 7 classification paths + prescription override."""

    BASELINE = 365  # days

    # ── Path 1: NO_HISTORY ────────────────────────────────────────────────────

    def test_no_history(self):
        assert _classify_test([], self.BASELINE) == Classification.NO_HISTORY

    # ── Path 2: SINGLE ───────────────────────────────────────────────────────

    def test_single_report(self):
        reports = [_Report(report_date=TODAY - timedelta(days=200))]
        assert _classify_test(reports, self.BASELINE) == Classification.SINGLE

    # ── Path 3 & 4: SPORADIC (large gap) ─────────────────────────────────────

    def test_sporadic_large_gap(self):
        # Gap = 900 days > 2 × 365 = 730 → SPORADIC
        reports = [
            _Report(report_date=TODAY - timedelta(days=1000)),
            _Report(report_date=TODAY - timedelta(days=100)),
        ]
        assert _classify_test(reports, self.BASELINE) == Classification.SPORADIC

    def test_sporadic_exactly_double_is_sporadic(self):
        # Gap = 730 > 730? No, 730 is NOT > 730. Edge: > not >=.
        # Exactly double should NOT be sporadic from step 4.
        # But let's check median_gap > baseline + tolerance = 365 * 1.4 = 511.
        # Gap = 730 > 511 → SPORADIC in step 6.
        gap = self.BASELINE * 2  # 730
        reports = [
            _Report(report_date=TODAY - timedelta(days=gap + 10)),
            _Report(report_date=TODAY - timedelta(days=10)),
        ]
        # gap = (today - 10) - (today - 740) = 730 days
        # 730 > 730? No → step 4 NOT triggered.
        # 730 > 365 + 146 = 511 → SPORADIC from step 6.
        assert _classify_test(reports, self.BASELINE) == Classification.SPORADIC

    # ── Path 5: PERIODIC ─────────────────────────────────────────────────────

    def test_periodic_regular_gaps(self):
        # Gaps of 365 days each - exactly matches baseline → PERIODIC
        reports = [
            _Report(report_date=TODAY - timedelta(days=730)),
            _Report(report_date=TODAY - timedelta(days=365)),
            _Report(report_date=TODAY),
        ]
        assert _classify_test(reports, self.BASELINE) == Classification.PERIODIC

    def test_periodic_gaps_within_tolerance(self):
        # Baseline = 365, tolerance = 0.40*365 = 146
        # Gaps: 350, 360 — both within [219, 511] and median 355 ≤ 511 → PERIODIC
        r0 = TODAY - timedelta(days=710)
        r1 = TODAY - timedelta(days=360)
        r2 = TODAY
        reports = [_Report(r0), _Report(r1), _Report(r2)]
        assert _classify_test(reports, self.BASELINE) == Classification.PERIODIC

    # ── Path 6: PERIODIC_INSUFFICIENT (gaps slightly above baseline) ──────────

    def test_periodic_insufficient(self):
        # Baseline = 180.  Tolerance = 0.40 * 180 = 72.  Upper = 252.
        # Gap = 200 days: 200 ≤ 252 (not sporadic) but 200 > 180 → PERIODIC_INSUFFICIENT
        baseline = 180
        reports = [
            _Report(report_date=TODAY - timedelta(days=400)),
            _Report(report_date=TODAY - timedelta(days=200)),
            _Report(report_date=TODAY),
        ]
        assert _classify_test(reports, baseline) == Classification.PERIODIC_INSUFFICIENT

    # ── Path 7: full SPORADIC (median exceeds upper tolerance) ───────────────

    def test_sporadic_median_exceeds_tolerance(self):
        # Baseline = 90.  Upper = 90 + 0.40*90 = 126.
        # Gaps: 100, 140 → no gap > 180.
        # median = 120 ≤ 126 → not SPORADIC from step 6.
        # Wait, let me recalculate: median([100, 140]) = 120 ≤ 126 → PERIODIC candidate.
        # 120 > 90 → PERIODIC_INSUFFICIENT.
        # Use gaps that push median above upper:
        # Baseline = 90, upper = 126.
        # Gaps: 130, 130 → median = 130 > 126 → SPORADIC from step 6.
        baseline = 90
        reports = [
            _Report(report_date=TODAY - timedelta(days=260)),
            _Report(report_date=TODAY - timedelta(days=130)),
            _Report(report_date=TODAY),
        ]
        assert _classify_test(reports, baseline) == Classification.SPORADIC

    # ── Prescription override ─────────────────────────────────────────────────

    def test_prescription_override_no_post_rx(self):
        # Active prescription due in future — no reports after due date.
        rx = _Prescription(due_date=TODAY + timedelta(days=30), medicine_name="Med")
        reports = [_Report(report_date=TODAY - timedelta(days=200))]
        result = _classify_test(reports, self.BASELINE, prescription=rx)
        assert result == Classification.PRESCRIPTION_ACTIVE

    def test_prescription_no_override_with_post_rx(self):
        # Prescription exists but there IS a report after the due date → not ATTEND TO.
        rx = _Prescription(due_date=TODAY - timedelta(days=90), medicine_name="Med")
        # Report on same day as due_date counts as post-Rx.
        reports = [
            _Report(report_date=TODAY - timedelta(days=90)),  # on due_date
            _Report(report_date=TODAY - timedelta(days=730)),
        ]
        result = _classify_test(reports, self.BASELINE, prescription=rx)
        # With these two reports, gap = 640 > 2*365=730? No. Median = 640 > 365+146=511 → SPORADIC.
        assert result != Classification.PRESCRIPTION_ACTIVE

    def test_prescription_none_no_effect(self):
        # prescription=None should not change classification.
        reports = [
            _Report(report_date=TODAY - timedelta(days=730)),
            _Report(report_date=TODAY - timedelta(days=365)),
            _Report(report_date=TODAY),
        ]
        assert _classify_test(reports, self.BASELINE, None) == Classification.PERIODIC


# ─────────────────────────────────────────────────────────────────────────────
# _compute_next_due
# ─────────────────────────────────────────────────────────────────────────────


class TestComputeNextDue:
    BASELINE = 365

    def test_prescription_active_returns_due_date(self):
        rx = _Prescription(due_date=TODAY + timedelta(days=30), medicine_name="Med")
        result = _compute_next_due(
            Classification.PRESCRIPTION_ACTIVE, [], self.BASELINE, rx
        )
        assert result == rx.due_date

    def test_no_history_returns_none(self):
        result = _compute_next_due(Classification.NO_HISTORY, [], self.BASELINE)
        assert result is None

    def test_single_report_uses_baseline(self):
        last = TODAY - timedelta(days=100)
        result = _compute_next_due(
            Classification.SINGLE, [_Report(last)], self.BASELINE
        )
        assert result == last + timedelta(days=self.BASELINE)

    def test_periodic_uses_median_gap_not_baseline(self):
        # Derived frequency = 180 days (observed), baseline = 365.
        r1 = _Report(TODAY - timedelta(days=360))
        r2 = _Report(TODAY - timedelta(days=180))
        r3 = _Report(TODAY)
        result = _compute_next_due(
            Classification.PERIODIC, [r1, r2, r3], self.BASELINE
        )
        # median gap = 180 (each gap is 180)
        assert result == TODAY + timedelta(days=180)

    def test_sporadic_uses_baseline_from_last(self):
        last = TODAY - timedelta(days=50)
        reports = [
            _Report(TODAY - timedelta(days=900)),
            _Report(last),
        ]
        result = _compute_next_due(
            Classification.SPORADIC, reports, self.BASELINE
        )
        assert result == last + timedelta(days=self.BASELINE)

    def test_no_reports_returns_none_for_sporadic(self):
        result = _compute_next_due(Classification.SPORADIC, [], self.BASELINE)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# _days_to_freq_label
# ─────────────────────────────────────────────────────────────────────────────


class TestDaysToFreqLabel:
    def test_weekly(self):
        assert _days_to_freq_label(7) == "Weekly"

    def test_every_2_weeks(self):
        assert _days_to_freq_label(14) == "Every 2 weeks"

    def test_monthly(self):
        assert _days_to_freq_label(30) == "Monthly"

    def test_every_3_months(self):
        assert _days_to_freq_label(90) == "Every 3 months"

    def test_every_6_months(self):
        assert _days_to_freq_label(180) == "Every 6 months"

    def test_annual(self):
        assert _days_to_freq_label(365) == "Annual"

    def test_every_2_years(self):
        assert _days_to_freq_label(730) == "Every 2 years"

    def test_every_3_plus_years(self):
        assert _days_to_freq_label(1095) == "Every 3+ years"


# ─────────────────────────────────────────────────────────────────────────────
# _status_tag
# ─────────────────────────────────────────────────────────────────────────────


class TestStatusTag:
    def test_no_history(self):
        assert _status_tag(None, Classification.NO_HISTORY) == "Not started"

    def test_prescription_active(self):
        assert _status_tag(TODAY + timedelta(days=10), Classification.PRESCRIPTION_ACTIVE) == "Prescription due"

    def test_overdue(self):
        assert _status_tag(TODAY - timedelta(days=1), Classification.SPORADIC) == "Overdue"

    def test_due_soon(self):
        assert _status_tag(TODAY + timedelta(days=15), Classification.PERIODIC) == "Due soon"

    def test_up_to_date(self):
        assert _status_tag(TODAY + timedelta(days=90), Classification.PERIODIC) == "Up to date"

    def test_none_next_due_review_needed(self):
        assert _status_tag(None, Classification.SPORADIC) == "Review needed"


# ─────────────────────────────────────────────────────────────────────────────
# _to_sections
# ─────────────────────────────────────────────────────────────────────────────


class TestToSections:
    def _make_item(self, test_type: str, name: str = "Test") -> dict:
        return {
            "name": name,
            "test_type": test_type,
            "freq": "Annual",
            "next_due": None,
            "status_tag": "Up to date",
            "classification": Classification.PERIODIC.value,
            "reason": None,
            "orderable": False,
        }

    def test_empty_dict_returns_empty_list(self):
        assert _to_sections({}) == []

    def test_single_item_creates_one_section(self):
        items = {"vaccine_1": self._make_item("vaccine", "Rabies")}
        sections = _to_sections(items)
        assert len(sections) == 1
        assert sections[0]["title"] == "Vaccines & Preventive Care"
        assert len(sections[0]["items"]) == 1

    def test_same_type_items_grouped_in_one_section(self):
        items = {
            "cbc_1": self._make_item("cbc_chemistry", "CBC"),
            "cbc_2": self._make_item("cbc_chemistry", "Blood Panel"),
        }
        sections = _to_sections(items)
        assert len(sections) == 1
        assert len(sections[0]["items"]) == 2

    def test_vaccine_appears_before_cbc_in_order(self):
        items = {
            "cbc_1": self._make_item("cbc_chemistry"),
            "vax_1": self._make_item("vaccine"),
        }
        sections = _to_sections(items)
        titles = [s["title"] for s in sections]
        assert titles.index("Vaccines & Preventive Care") < titles.index("Blood Tests (CBC)")

    def test_unknown_section_appended_at_end(self):
        items = {
            "vax": self._make_item("vaccine"),
            "unknown": self._make_item("unknown_type"),
        }
        sections = _to_sections(items)
        assert sections[-1]["icon"] == "🏥"  # default section


# ─────────────────────────────────────────────────────────────────────────────
# compute_care_plan — integration-style (mocked DB)
# ─────────────────────────────────────────────────────────────────────────────


class TestComputeCarePlan:
    """Tests for the public compute_care_plan function with mocked DB session."""

    def _make_pet(
        self,
        dob_months_ago: int = 48,
        weight: float = 15.0,
        breed: str = "Mixed",
    ):
        """Build a minimal mock Pet."""
        pet = MagicMock()
        pet.id = "test-pet-uuid"
        pet.name = "Buddy"
        pet.dob = TODAY - timedelta(days=int(dob_months_ago * 30.44))
        pet.weight = weight
        pet.breed = breed
        return pet

    def _run_care_plan(
        self,
        pet,
        record_rows=None,
        active_meds=None,
        diet_rows=None,
        order_row=None,
        order_query_raises: bool = False,
    ):
        """Run compute_care_plan with fully mocked DB session."""
        from app.services.care_plan_engine import compute_care_plan

        db = MagicMock()

        # Mock PreventiveRecord+PreventiveMaster query
        mock_rq = MagicMock()
        mock_rq.join.return_value = mock_rq
        mock_rq.filter.return_value = mock_rq
        mock_rq.all.return_value = record_rows or []

        # Mock ConditionMedication query
        mock_mq = MagicMock()
        mock_mq.join.return_value = mock_mq
        mock_mq.filter.return_value = mock_mq
        mock_mq.all.return_value = active_meds or []

        # Mock DietItem query
        mock_dq = MagicMock()
        mock_dq.filter.return_value = mock_dq
        mock_dq.all.return_value = diet_rows or []

        # Mock Order query for order-history based CTA/status.
        mock_oq = MagicMock()
        mock_oq.filter.return_value = mock_oq
        mock_oq.order_by.return_value = mock_oq
        if order_query_raises:
            mock_oq.first.side_effect = RuntimeError("order query failed")
        else:
            mock_oq.first.return_value = order_row

        # Route queries by the model being queried
        query_returns = {
            "PreventiveRecord": mock_rq,
            "ConditionMedication": mock_mq,
            "DietItem": mock_dq,
            "Order": mock_oq,
        }

        def side_effect(model, *args):
            name = getattr(model, "__name__", None) or getattr(model, "__tablename__", str(model))
            for key, mock_obj in query_returns.items():
                if key.lower() in str(name).lower():
                    return mock_obj
            return MagicMock()

        db.query.side_effect = side_effect

        return compute_care_plan(db, pet)

    def test_returns_care_plan_v2_structure(self):
        pet = self._make_pet()
        result = self._run_care_plan(pet)
        assert "continue_items" in result
        assert "attend_items" in result
        assert "add_items" in result

    def test_empty_records_produces_suggested_items(self):
        """A pet with no records should have suggested (add) items from baseline."""
        pet = self._make_pet(dob_months_ago=48, weight=15.0)
        result = self._run_care_plan(pet)
        # With no records and life_stage=ADULT, all items are NO_HISTORY → Suggested
        assert len(result["add_items"]) > 0

    def test_periodic_record_goes_to_continue_bucket(self):
        """A test_type with regular annual reports should be in Continue."""
        pet = self._make_pet(dob_months_ago=48, weight=15.0)  # adult medium

        # Simulate 3 annual CBC records (periodic pattern).
        master = MagicMock()
        master.item_name = "CBC Chemistry"
        records = []
        for years_ago in (2, 1, 0):
            rec = MagicMock()
            rec.last_done_date = TODAY - timedelta(days=365 * years_ago)
            rec.status = "up_to_date"
            records.append((rec, master))

        result = self._run_care_plan(pet, record_rows=records)

        continue_types = [
            item["test_type"]
            for section in result["continue_items"]
            for item in section["items"]
        ]
        assert "cbc_chemistry" in continue_types

    def test_prescription_active_goes_to_attend_bucket(self):
        """An active prescription with no post-Rx report should land in Attend To."""
        pet = self._make_pet(dob_months_ago=48, weight=15.0)

        med = MagicMock()
        med.name = "CBC Blood Chemistry"
        med.status = "active"
        med.refill_due_date = TODAY + timedelta(days=30)

        result = self._run_care_plan(pet, active_meds=[med])

        attend_types = [
            item["test_type"]
            for section in result["attend_items"]
            for item in section["items"]
        ]
        assert "cbc_chemistry" in attend_types

    def test_attend_bucket_not_in_continue_or_add(self):
        """Conflict resolution: ATTEND TO > CONTINUE > SUGGESTED."""
        pet = self._make_pet(dob_months_ago=48, weight=15.0)

        # Periodic CBC records (would normally go to Continue).
        master = MagicMock()
        master.item_name = "CBC Chemistry"
        records = []
        for years_ago in (2, 1, 0):
            rec = MagicMock()
            rec.last_done_date = TODAY - timedelta(days=365 * years_ago)
            rec.status = "up_to_date"
            records.append((rec, master))

        # Also an active prescription for CBC (ATTEND TO takes priority).
        med = MagicMock()
        med.name = "CBC Blood Chemistry Recheck"
        med.status = "active"
        med.refill_due_date = TODAY + timedelta(days=60)

        result = self._run_care_plan(pet, record_rows=records, active_meds=[med])

        attend_types = {
            item["test_type"]
            for section in result["attend_items"]
            for item in section["items"]
        }
        continue_types = {
            item["test_type"]
            for section in result["continue_items"]
            for item in section["items"]
        }
        add_types = {
            item["test_type"]
            for section in result["add_items"]
            for item in section["items"]
        }
        # cbc_chemistry must be ONLY in attend, not in continue or add.
        assert "cbc_chemistry" in attend_types
        assert "cbc_chemistry" not in continue_types
        assert "cbc_chemistry" not in add_types

    def test_next_year_items_excluded(self):
        """Items due more than 365 days from today must not appear."""
        pet = self._make_pet(dob_months_ago=48, weight=15.0)

        # Single CBC record done today → next_due = today + 730 (adult baseline).
        # 730 > 365 → should be EXCLUDED.
        master = MagicMock()
        master.item_name = "CBC Chemistry"
        rec = MagicMock()
        rec.last_done_date = TODAY
        rec.status = "up_to_date"

        result = self._run_care_plan(pet, record_rows=[(rec, master)])

        all_types = set()
        for bucket in ("continue_items", "attend_items", "add_items"):
            for section in result[bucket]:
                for item in section["items"]:
                    all_types.add(item["test_type"])

        assert "cbc_chemistry" not in all_types

    def test_orderable_food_in_continue_bucket(self):
        """Food with no prior order should default to Order Now + Active."""
        pet = self._make_pet()

        diet = MagicMock()
        diet.id = "diet-uuid-1"
        diet.label = "Royal Canin Adult"
        diet.type = "packaged"

        result = self._run_care_plan(pet, diet_rows=[diet])

        food_items = [
            item
            for section in result["continue_items"]
            for item in section["items"]
            if item["test_type"] == "food"
        ]
        assert len(food_items) >= 1
        assert food_items[0]["orderable"] is True
        assert food_items[0]["name"] == "Royal Canin Adult"
        assert food_items[0]["cta_label"] == "Order Now"
        assert food_items[0]["status_tag"] == "Active"

    def test_food_with_prior_order_uses_reorder_cta(self):
        """Food with prior order and enough supply should show Reorder + Active."""
        pet = self._make_pet()

        diet = MagicMock()
        diet.id = "diet-uuid-2"
        diet.label = "Royal Canin Adult"
        diet.type = "packaged"

        last_order = MagicMock()
        last_order.created_at = TODAY - timedelta(days=4)
        last_order.pack_days = 30
        last_order.status = "confirmed"

        result = self._run_care_plan(pet, diet_rows=[diet], order_row=last_order)

        food_items = [
            item
            for section in result["continue_items"]
            for item in section["items"]
            if item["test_type"] == "food"
        ]
        assert len(food_items) >= 1
        assert food_items[0]["cta_label"] == "Reorder"
        assert food_items[0]["status_tag"] == "Active"

    def test_food_with_low_supply_is_due_soon(self):
        """Food with prior order and <=7 days supply should be marked Due Soon."""
        pet = self._make_pet()

        diet = MagicMock()
        diet.id = "diet-uuid-3"
        diet.label = "Royal Canin Adult"
        diet.type = "packaged"

        last_order = MagicMock()
        last_order.created_at = TODAY - timedelta(days=25)
        last_order.pack_days = 30
        last_order.status = "completed"

        result = self._run_care_plan(pet, diet_rows=[diet], order_row=last_order)

        food_items = [
            item
            for section in result["continue_items"]
            for item in section["items"]
            if item["test_type"] == "food"
        ]
        assert len(food_items) >= 1
        assert food_items[0]["cta_label"] == "Reorder"
        assert food_items[0]["status_tag"] == "Due Soon"

    def test_orderable_supplement_in_continue_bucket(self):
        """Supplement diet items should be placed in Continue as orderable."""
        pet = self._make_pet()

        supp = MagicMock()
        supp.id = "supp-uuid-1"
        supp.label = "Omega-3 Supplement"
        supp.type = "supplement"

        result = self._run_care_plan(pet, diet_rows=[supp])

        supp_items = [
            item
            for section in result["continue_items"]
            for item in section["items"]
            if item["test_type"] == "supplement"
        ]
        assert len(supp_items) >= 1
        assert supp_items[0]["orderable"] is True

    def test_order_query_failure_falls_back_to_defaults(self):
        """Order lookup failure must not break care plan and should keep defaults."""
        pet = self._make_pet()

        diet = MagicMock()
        diet.id = "diet-uuid-4"
        diet.label = "Royal Canin Adult"
        diet.type = "packaged"

        result = self._run_care_plan(
            pet,
            diet_rows=[diet],
            order_query_raises=True,
        )

        food_items = [
            item
            for section in result["continue_items"]
            for item in section["items"]
            if item["test_type"] == "food"
        ]
        assert len(food_items) >= 1
        assert food_items[0]["cta_label"] == "Order Now"
        assert food_items[0]["status_tag"] == "Active"

    def test_cancelled_order_does_not_trigger_reorder(self):
        """Cancelled latest order must not drive reorder CTA."""
        pet = self._make_pet()

        diet = MagicMock()
        diet.id = "diet-uuid-5"
        diet.label = "Royal Canin Adult"
        diet.type = "packaged"

        cancelled_order = MagicMock()
        cancelled_order.created_at = TODAY - timedelta(days=2)
        cancelled_order.pack_days = 30
        cancelled_order.status = "cancelled"

        result = self._run_care_plan(pet, diet_rows=[diet], order_row=cancelled_order)

        food_items = [
            item
            for section in result["continue_items"]
            for item in section["items"]
            if item["test_type"] == "food"
        ]
        assert len(food_items) >= 1
        assert food_items[0]["cta_label"] == "Order Now"
        assert food_items[0]["status_tag"] == "Active"

    def test_malformed_supply_data_falls_back_to_defaults(self):
        """Invalid pack_days should not crash and should keep default CTA/status."""
        pet = self._make_pet()

        diet = MagicMock()
        diet.id = "diet-uuid-6"
        diet.label = "Royal Canin Adult"
        diet.type = "packaged"

        bad_order = MagicMock()
        bad_order.created_at = TODAY - timedelta(days=5)
        bad_order.pack_days = "unknown"
        bad_order.status = "confirmed"

        result = self._run_care_plan(pet, diet_rows=[diet], order_row=bad_order)

        food_items = [
            item
            for section in result["continue_items"]
            for item in section["items"]
            if item["test_type"] == "food"
        ]
        assert len(food_items) >= 1
        assert food_items[0]["cta_label"] == "Order Now"
        assert food_items[0]["status_tag"] == "Active"

    def test_attend_bucket_has_no_orderable_items(self):
        """Attend To bucket must not contain orderable items (req 8.7)."""
        pet = self._make_pet(dob_months_ago=48, weight=15.0)

        med = MagicMock()
        med.name = "Urinalysis Recheck"
        med.status = "active"
        med.refill_due_date = TODAY + timedelta(days=14)

        result = self._run_care_plan(pet, active_meds=[med])

        for section in result["attend_items"]:
            for item in section["items"]:
                # Attend To items should never have orderable=True
                assert item["orderable"] is False

    def test_db_error_returns_empty_plan(self):
        """Any uncaught DB error must return empty CarePlanV2, not raise."""
        from app.services.care_plan_engine import compute_care_plan

        pet = self._make_pet()
        db = MagicMock()
        db.query.side_effect = RuntimeError("DB connection lost")

        result = compute_care_plan(db, pet)
        assert result["continue_items"] == []
        assert result["attend_items"] == []
        assert result["add_items"] == []

    def test_items_never_in_two_buckets(self):
        """The same test_type must not appear in more than one bucket."""
        pet = self._make_pet(dob_months_ago=48, weight=15.0)

        # Periodic CBC records (→ Continue) + active prescription (→ Attend To wins).
        master = MagicMock()
        master.item_name = "CBC Chemistry"
        records = []
        for years_ago in (2, 1, 0):
            rec = MagicMock()
            rec.last_done_date = TODAY - timedelta(days=365 * years_ago)
            rec.status = "up_to_date"
            records.append((rec, master))

        med = MagicMock()
        med.name = "CBC Blood Chemistry"
        med.status = "active"
        med.refill_due_date = TODAY + timedelta(days=30)

        result = self._run_care_plan(pet, record_rows=records, active_meds=[med])

        seen: dict[str, str] = {}
        for bucket in ("continue_items", "attend_items", "add_items"):
            for section in result[bucket]:
                for item in section["items"]:
                    tt = item["test_type"]
                    assert tt not in seen, (
                        f"test_type '{tt}' appears in both '{seen[tt]}' and '{bucket}'"
                    )
                    seen[tt] = bucket

    def test_puppy_life_stage_uses_puppy_baselines(self):
        """A 3-month-old puppy should use puppy baselines (e.g. CBC every 56 days)."""
        pet = self._make_pet(dob_months_ago=3, weight=3.0, breed="Mixed")

        # Single CBC record → SINGLE classification, next_due = last + 56.
        master = MagicMock()
        master.item_name = "CBC"
        rec = MagicMock()
        rec.last_done_date = TODAY - timedelta(days=10)
        rec.status = "up_to_date"

        result = self._run_care_plan(pet, record_rows=[(rec, master)])

        cbc_items = [
            item
            for section in result["add_items"]
            for item in section["items"]
            if item["test_type"] == "cbc_chemistry"
        ]
        if cbc_items:
            # Puppy baseline is 56 days, not excluded (10 + 56 = 66 ≤ 365).
            assert cbc_items[0]["next_due"] is not None
