import asyncio
from types import SimpleNamespace

from app.services import message_router


class _PetQuery:
    def __init__(self, pet):
        self._pet = pet

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._pet


class _DocumentQuery:
    def __init__(self, db):
        self._db = db

    def filter(self, *_args, **_kwargs):
        return self

    def count(self):
        return self._db.pending_docs

    def all(self):
        return self._db.docs_in_scope


class _FakeDB:
    def __init__(self, pet, pending_docs=0, docs_in_scope=None):
        self.pet = pet
        self.pending_docs = pending_docs
        self.docs_in_scope = docs_in_scope or []

    def query(self, entity):
        model = getattr(entity, "class_", entity)
        name = getattr(model, "__name__", "")
        if name == "Pet":
            return _PetQuery(self.pet)
        if name == "Document":
            return _DocumentQuery(self)
        raise AssertionError(f"Unexpected query entity: {name!r}")

    def rollback(self):
        return None


def test_route_message_transcript_dashboard_precedence(monkeypatch):
    pet = SimpleNamespace(id="pet-rt-1", name="Zayn", created_at=1)
    user = SimpleNamespace(
        id="user-rt-1",
        onboarding_state="complete",
        onboarding_completed_at=None,
        order_state=None,
        active_reminder_id=None,
        mobile_number="enc",
    )

    db = _FakeDB(
        pet=pet,
        pending_docs=1,
        docs_in_scope=[
            SimpleNamespace(extraction_status="success", file_path="user/pet/success.pdf"),
            SimpleNamespace(extraction_status="rejected", file_path="user/pet/rejected.pdf"),
        ],
    )

    pending_state = {"value": True}
    sent_texts = []
    calls = {"deferred": 0, "dashboard_links": 0}
    deferred_args = {}

    def fake_get_or_create_user(_db, _from_number):
        return user, True

    async def fake_send_text(_db, _to, text):
        sent_texts.append(text)

    async def fake_deferred(_db, _user, _pet, _from, all_results, success_count, fail_count, failed_doc_names):
        calls["deferred"] += 1
        deferred_args["success_count"] = success_count
        deferred_args["fail_count"] = fail_count
        deferred_args["failed_doc_names"] = failed_doc_names

    async def fake_dashboard_links(*_args, **_kwargs):
        calls["dashboard_links"] += 1

    monkeypatch.setattr(message_router, "get_or_create_user", fake_get_or_create_user)
    monkeypatch.setattr(message_router, "send_text_message", fake_send_text)
    monkeypatch.setattr(
        message_router,
        "_has_pending_deferred_care_plan",
        lambda *_args, **_kwargs: pending_state["value"],
    )
    monkeypatch.setattr(
        message_router,
        "_get_active_deferred_marker",
        lambda *_args, **_kwargs: SimpleNamespace(created_at=None),
    )
    monkeypatch.setattr(message_router, "_send_deferred_care_plan", fake_deferred)
    monkeypatch.setattr(message_router, "_send_dashboard_links", fake_dashboard_links)

    msg = {
        "from_number": "919188877766",
        "type": "text",
        "message_id": "wamid.route.1",
        "text": "i want to see dashboard",
    }

    # Ask 1: still pending extraction -> building-status only.
    asyncio.run(message_router.route_message(db, msg))  # type: ignore[arg-type]
    assert len(sent_texts) == 1
    assert calls["deferred"] == 0
    assert calls["dashboard_links"] == 0

    # Ask 2: processing done, deferred marker still active -> care-plan path.
    db.pending_docs = 0
    msg["message_id"] = "wamid.route.2"
    msg["text"] = "dashboard"
    asyncio.run(message_router.route_message(db, msg))  # type: ignore[arg-type]
    assert calls["deferred"] == 1
    assert calls["dashboard_links"] == 0
    assert deferred_args["success_count"] == 1
    assert deferred_args["fail_count"] == 1
    assert deferred_args["failed_doc_names"] == ["rejected.pdf"]

    # Ask 3: deferred marker resolved -> dashboard links path.
    pending_state["value"] = False
    msg["message_id"] = "wamid.route.3"
    msg["text"] = "dashboard link"
    asyncio.run(message_router.route_message(db, msg))  # type: ignore[arg-type]
    assert calls["dashboard_links"] == 1


def test_route_message_onboarding_uses_button_payload_as_text(monkeypatch):
    pet = SimpleNamespace(id="pet-rt-2", name="Zayn", created_at=1)
    user = SimpleNamespace(
        id="user-rt-2",
        onboarding_state="awaiting_preventive",
        onboarding_completed_at=None,
        order_state=None,
        active_reminder_id=None,
        mobile_number="enc",
    )
    db = _FakeDB(pet=pet)

    captured = {"text": None}

    def fake_get_or_create_user(_db, _from_number):
        return user, True

    async def fake_send_text(_db, _to, _text):
        return None

    async def fake_onboarding_step(_db, _user, text, _send_fn, message_data=None):
        captured["text"] = text

    monkeypatch.setattr(message_router, "get_or_create_user", fake_get_or_create_user)
    monkeypatch.setattr(message_router, "send_text_message", fake_send_text)
    monkeypatch.setattr(message_router, "handle_onboarding_step", fake_onboarding_step)

    msg = {
        "from_number": "919188877766",
        "type": "button",
        "message_id": "wamid.route.btn.1",
        "text": None,
        "button_payload": "no",
    }

    asyncio.run(message_router.route_message(db, msg))  # type: ignore[arg-type]

    assert captured["text"] == "no"


def test_route_message_onboarding_uses_uppercase_button_payload_as_text(monkeypatch):
    pet = SimpleNamespace(id="pet-rt-3", name="Zayn", created_at=1)
    user = SimpleNamespace(
        id="user-rt-3",
        onboarding_state="awaiting_preventive",
        onboarding_completed_at=None,
        order_state=None,
        active_reminder_id=None,
        mobile_number="enc",
    )
    db = _FakeDB(pet=pet)

    captured = {"text": None}

    def fake_get_or_create_user(_db, _from_number):
        return user, True

    async def fake_send_text(_db, _to, _text):
        return None

    async def fake_onboarding_step(_db, _user, text, _send_fn, message_data=None):
        captured["text"] = text

    monkeypatch.setattr(message_router, "get_or_create_user", fake_get_or_create_user)
    monkeypatch.setattr(message_router, "send_text_message", fake_send_text)
    monkeypatch.setattr(message_router, "handle_onboarding_step", fake_onboarding_step)

    msg = {
        "from_number": "919188877766",
        "type": "button",
        "message_id": "wamid.route.btn.2",
        "text": None,
        "button_payload": "NO",
    }

    asyncio.run(message_router.route_message(db, msg))  # type: ignore[arg-type]

    assert captured["text"] == "NO"
