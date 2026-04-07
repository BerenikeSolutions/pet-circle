import os

os.environ.setdefault("APP_ENV", "test")

from app.services import medicine_recurrence_service as service


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self._category_filter: set[str] | None = None

    def filter(self, *args, **kwargs):
        # Intercept category.in_() filter by inspecting BinaryExpression args.
        # Each SQLAlchemy filter arg is a clause element; we look for In clauses
        # whose right side is a list of category strings.
        for arg in args:
            try:
                if hasattr(arg, "right") and hasattr(arg.right, "effective_value"):
                    val = arg.right.effective_value
                    if isinstance(val, (list, tuple)) and all(isinstance(v, str) for v in val):
                        self._category_filter = set(val)
            except Exception:
                pass
        return self

    def all(self):
        if self._category_filter is not None:
            return [r for r in self.rows if r[0] in self._category_filter]
        return self.rows


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows

    def query(self, *args, **kwargs):
        return _FakeQuery(list(self.rows))


def test_lookup_catalog_frequency_same_medicine_same_recurrence_across_item_types() -> None:
    rows = [
        ("flea_tick", "Zoetis", "Simparica", "Every 1 month"),
    ]
    db = _FakeDB(rows)

    original_is_dual = service._is_dual_use_medicine
    service._is_dual_use_medicine = lambda _name: True
    try:
        flea_days = service._lookup_catalog_frequency(db, "Zoetis Simparica", "Tick/Flea")
        deworm_days = service._lookup_catalog_frequency(db, "Zoetis Simparica", "Deworming")
    finally:
        service._is_dual_use_medicine = original_is_dual

    assert flea_days == 30
    assert deworm_days == 30


def test_lookup_catalog_frequency_dual_use_returns_same_for_both_categories() -> None:
    """Dual-use medicine returns the same frequency regardless of item_type."""
    rows = [
        ("deworming", "Zoetis", "Simparica", "Every 3 months"),
        ("flea_tick", "Zoetis", "Simparica", "monthly"),
    ]
    db = _FakeDB(rows)

    original_is_dual = service._is_dual_use_medicine
    service._is_dual_use_medicine = lambda _name: True
    try:
        deworm_days = service._lookup_catalog_frequency(db, "Zoetis Simparica", "Deworming")
        flea_days = service._lookup_catalog_frequency(db, "Zoetis Simparica", "Tick/Flea")
    finally:
        service._is_dual_use_medicine = original_is_dual

    # One medicine = one dosing interval; shortest wins (actual dosing schedule)
    assert deworm_days == 30
    assert flea_days == 30


def test_lookup_catalog_frequency_non_dual_medicine_returns_matching_category_interval() -> None:
    rows = [
        ("deworming", "Boehringer", "NexGard", "Every 3 months"),
    ]
    db = _FakeDB(rows)

    original_is_dual = service._is_dual_use_medicine
    service._is_dual_use_medicine = lambda _name: False
    try:
        deworm_days = service._lookup_catalog_frequency(db, "Boehringer NexGard", "Deworming")
    finally:
        service._is_dual_use_medicine = original_is_dual

    assert deworm_days == 90


def test_get_medicine_recurrence_uses_item_type_in_gpt_only_for_non_dual() -> None:
    calls: list[bool] = []

    original_is_dual = service._is_dual_use_medicine
    original_gpt = service._gpt_recurrence

    def _fake_gpt(species, item_type, medicine_name, default_days, include_item_type):
        calls.append(include_item_type)
        return default_days

    service._gpt_recurrence = _fake_gpt
    try:
        service._is_dual_use_medicine = lambda _name: True
        service.get_medicine_recurrence(
            species="dog",
            item_type="Deworming",
            medicine_name="Simparica",
            default_days=30,
            db=None,
        )

        service._is_dual_use_medicine = lambda _name: False
        service.get_medicine_recurrence(
            species="dog",
            item_type="Deworming",
            medicine_name="Drontal Plus",
            default_days=90,
            db=None,
        )
    finally:
        service._is_dual_use_medicine = original_is_dual
        service._gpt_recurrence = original_gpt

    assert calls == [False, True]
