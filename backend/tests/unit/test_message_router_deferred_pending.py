from types import SimpleNamespace

from app.services import message_router


class _FakeQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _FakeDB:
    def __init__(self):
        self.add_calls = 0
        self.flush_calls = 0

    def query(self, *_args, **_kwargs):
        return _FakeQuery()

    def add(self, _obj):
        self.add_calls += 1

    def flush(self):
        self.flush_calls += 1

    def rollback(self):
        return None


def test_has_pending_deferred_care_plan_uses_legacy_user_flag_backcompat():
    db = _FakeDB()
    user = SimpleNamespace(id="user-1", dashboard_link_pending=True)

    result = message_router._has_pending_deferred_care_plan(db, pet_id="pet-1", user=user)

    assert result is True
    assert db.add_calls == 1
    assert db.flush_calls == 1


def test_has_pending_deferred_care_plan_false_without_marker_or_legacy_flag():
    db = _FakeDB()
    user = SimpleNamespace(id="user-2", dashboard_link_pending=False)

    result = message_router._has_pending_deferred_care_plan(db, pet_id="pet-2", user=user)

    assert result is False
    assert db.add_calls == 0
