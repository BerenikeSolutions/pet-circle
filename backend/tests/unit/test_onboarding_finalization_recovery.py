from types import SimpleNamespace

from app.services import onboarding


class _FakeDB:
    def rollback(self):
        return None


def test_recover_transition_failures_runs_seed_for_supported_species(monkeypatch):
    db = _FakeDB()
    pet = SimpleNamespace(id="pet-1", species="dog")
    calls = {"seed": 0, "token": 0}

    def _fake_seed(_db, _pet):
        calls["seed"] += 1

    def _fake_token_recover(_db, _pet_id):
        calls["token"] += 1
        return None

    monkeypatch.setattr(onboarding, "seed_preventive_records_for_pet", _fake_seed)
    monkeypatch.setattr(onboarding, "_recover_dashboard_token_for_finalize", _fake_token_recover)

    onboarding._recover_transition_failures(db, pet)

    assert calls["seed"] == 1
    assert calls["token"] == 1


def test_recover_transition_failures_skips_seed_for_unsupported_species(monkeypatch):
    db = _FakeDB()
    pet = SimpleNamespace(id="pet-2", species="bird")
    calls = {"seed": 0, "token": 0}

    def _fake_seed(_db, _pet):
        calls["seed"] += 1

    def _fake_token_recover(_db, _pet_id):
        calls["token"] += 1
        return None

    monkeypatch.setattr(onboarding, "seed_preventive_records_for_pet", _fake_seed)
    monkeypatch.setattr(onboarding, "_recover_dashboard_token_for_finalize", _fake_token_recover)

    onboarding._recover_transition_failures(db, pet)

    assert calls["seed"] == 0
    assert calls["token"] == 1


def test_get_or_create_active_dashboard_token_returns_existing_token(monkeypatch):
    class _FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            return SimpleNamespace(token="existing-token")

    class _FakeDB:
        def query(self, _model):
            return _FakeQuery()

    db = _FakeDB()

    token = onboarding.get_or_create_active_dashboard_token(db, "pet-1")

    assert token == "existing-token"


def test_get_or_create_active_dashboard_token_uses_expiry_filter_and_generates_when_missing(monkeypatch):
    captured_filters = []

    class _FakeQuery:
        def filter(self, *args, **_kwargs):
            captured_filters.extend(args)
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class _FakeDB:
        def query(self, _model):
            return _FakeQuery()

    def _fake_generate(_db, _pet_id):
        return "new-token"

    monkeypatch.setattr(onboarding, "generate_dashboard_token", _fake_generate)

    token = onboarding.get_or_create_active_dashboard_token(_FakeDB(), "pet-2")

    assert token == "new-token"
    assert any("expires_at" in str(expr) for expr in captured_filters)


def test_persist_deferred_marker_with_fallback_sets_legacy_flag_when_marker_fails(monkeypatch):
    class _FakeDB:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    def _raise_marker(_db, _user_id, _pet_id):
        raise RuntimeError("marker failed")

    monkeypatch.setattr(onboarding, "_mark_deferred_care_plan_pending", _raise_marker)

    db = _FakeDB()
    user = SimpleNamespace(id="user-1", dashboard_link_pending=False)
    pet = SimpleNamespace(id="pet-1")

    onboarding._persist_deferred_marker_with_fallback(db, user, pet)

    assert db.rollbacks == 1
    assert db.commits == 1
    assert user.dashboard_link_pending is True


def test_persist_deferred_marker_with_fallback_no_legacy_attr(monkeypatch):
    class _FakeDB:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    def _raise_marker(_db, _user_id, _pet_id):
        raise RuntimeError("marker failed")

    monkeypatch.setattr(onboarding, "_mark_deferred_care_plan_pending", _raise_marker)

    db = _FakeDB()
    user = SimpleNamespace(id="user-2")
    pet = SimpleNamespace(id="pet-2")

    onboarding._persist_deferred_marker_with_fallback(db, user, pet)

    assert db.rollbacks == 1
    assert db.commits == 0
