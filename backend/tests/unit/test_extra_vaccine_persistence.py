from datetime import date
from uuid import uuid4

from app.models.custom_preventive_item import CustomPreventiveItem
from app.models.pet import Pet
from app.models.preventive_record import PreventiveRecord
from app.services.gpt_extraction import _persist_extra_vaccines_for_pet


class _FakeQuery:
    def __init__(self, data):
        self._data = data
        self._conditions = []

    def _matches(self, obj):
        for expr in self._conditions:
            left = getattr(getattr(expr, "left", None), "key", None)
            if not left:
                continue

            right_obj = getattr(expr, "right", None)
            right = getattr(right_obj, "value", None)
            operator_name = getattr(getattr(expr, "operator", None), "__name__", "")
            value = getattr(obj, left, None)

            if operator_name == "eq" and value != right:
                return False
            if operator_name == "ne" and value == right:
                return False
            if operator_name == "is_" and value is not right:
                return False

        return True

    def filter(self, *args, **kwargs):
        self._conditions.extend(args)
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        for item in self._data:
            if self._matches(item):
                return item
        return None


class _FakeDB:
    def __init__(self):
        self.custom_items = []
        self.records = []

    def query(self, model):
        if model is CustomPreventiveItem:
            return _FakeQuery(self.custom_items)
        if model is PreventiveRecord:
            return _FakeQuery(self.records)
        return _FakeQuery([])

    def add(self, obj):
        if isinstance(obj, CustomPreventiveItem):
            obj.id = uuid4()
            self.custom_items.append(obj)
        elif isinstance(obj, PreventiveRecord):
            obj.id = uuid4()
            self.records.append(obj)

    def flush(self):
        return None

    def rollback(self):
        return None


def test_persist_extra_vaccines_creates_custom_record_for_pet_only() -> None:
    db = _FakeDB()
    pet = Pet(
        id=uuid4(),
        user_id=uuid4(),
        species="dog",
        name="Zayn",
    )

    saved, errors = _persist_extra_vaccines_for_pet(
        db,
        pet=pet,
        extra_vaccines=[
            {"vaccine_name": "Custom Booster X", "date": "2025-04-01"},
        ],
    )

    assert errors == []
    assert saved == 1
    assert len(db.custom_items) == 1
    assert db.custom_items[0].item_name == "Custom Booster X"
    assert db.custom_items[0].species == "dog"
    assert len(db.records) == 1
    assert db.records[0].pet_id == pet.id
    assert db.records[0].custom_preventive_item_id == db.custom_items[0].id
    assert db.records[0].last_done_date == date(2025, 4, 1)


def test_persist_extra_vaccines_does_not_create_record_for_other_pet() -> None:
    db = _FakeDB()
    user_id = uuid4()
    pet_a = Pet(id=uuid4(), user_id=user_id, species="dog", name="Zayn")
    pet_b = Pet(id=uuid4(), user_id=user_id, species="dog", name="Veer")

    saved, errors = _persist_extra_vaccines_for_pet(
        db,
        pet=pet_a,
        extra_vaccines=[{"vaccine_name": "Custom Booster Y", "date": "2025-04-01"}],
    )

    assert errors == []
    assert saved == 1
    assert len(db.records) == 1
    assert db.records[0].pet_id == pet_a.id
    assert db.records[0].pet_id != pet_b.id
