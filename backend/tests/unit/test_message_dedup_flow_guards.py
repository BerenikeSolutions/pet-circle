import asyncio
import time
from types import SimpleNamespace

from app.services import message_router, onboarding


class _CountQuery:
    def __init__(self, value):
        self._value = value

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._value

    def count(self):
        if isinstance(self._value, list):
            return len(self._value)
        if self._value is None:
            return 0
        return int(self._value)

    def all(self):
        if isinstance(self._value, list):
            return self._value
        if self._value is None:
            return []
        return [self._value]


class _OnboardingDB:
    def __init__(self, pet, doc_count=0):
        self.pet = pet
        self.doc_count = doc_count
        self.commits = 0

    def query(self, model):
        model_name = getattr(model, "__name__", "")
        if model_name == "Pet":
            return _CountQuery(self.pet)
        if model_name == "Document":
            return _CountQuery(self.doc_count)
        return _CountQuery(None)

    def commit(self):
        self.commits += 1


class _RouterDB:
    def __init__(self, pet=None, marker=None, pending_docs=0, docs_in_scope=None):
        self.pet = pet
        self.marker = marker
        self.pending_docs = pending_docs
        self.docs_in_scope = docs_in_scope or []

    def query(self, entity, *_args, **_kwargs):
        model = getattr(entity, "class_", entity)
        name = getattr(model, "__name__", "")
        if name == "Pet":
            return _CountQuery(self.pet)
        if name == "DeferredCarePlanPending":
            return _CountQuery(self.marker)
        if name == "Document":
            # query(Document.id) asks for pending count; query(Document)
            # asks for in-scope docs used to build failed_doc_names.
            if getattr(entity, "key", None) == "id":
                return _CountQuery(self.pending_docs)
            return _CountQuery(self.docs_in_scope)
        return _CountQuery(None)


def test_awaiting_documents_yes_is_suppressed_within_cooldown(monkeypatch):
    pet = SimpleNamespace(id="pet-1", name="Zayn")
    db = _OnboardingDB(pet=pet, doc_count=0)
    user = SimpleNamespace(
        id="user-1",
        _plaintext_mobile="919100000001",
        doc_upload_deadline=None,
        onboarding_data={
            "awaiting_docs_last_reply_at": time.time() - 20,
            "awaiting_docs_last_reply_text": "upload_prompt",
        },
    )

    sent = []

    async def fake_send(_db, _to, _text):
        sent.append(_text)

    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("_generate_doc_upload_reply should not run for duplicate simple ack")

    monkeypatch.setattr(onboarding, "_generate_doc_upload_reply", should_not_run)

    asyncio.run(onboarding._step_awaiting_documents(db, user, "yes", fake_send))

    assert sent == []
    assert db.commits == 0


def test_handle_text_acknowledgment_reply_is_sent(monkeypatch):
    user = SimpleNamespace(
        id="user-2",
        _plaintext_mobile="919100000002",
        order_state=None,
        active_reminder_id=None,
        onboarding_completed_at=None,
    )

    sent = []

    async def fake_send(_db, _to, text):
        sent.append(text)

    monkeypatch.setattr(message_router, "send_text_message", fake_send)

    asyncio.run(message_router._handle_text(_RouterDB(), user, {"text": "ok"}))  # type: ignore[arg-type]

    assert len(sent) == 1
    assert "You're welcome" in sent[0]


def test_dashboard_request_sends_deferred_care_plan_not_dashboard_links(monkeypatch):
    pet = SimpleNamespace(id="pet-3", name="Zayn", created_at=1)
    marker = SimpleNamespace(created_at=None)
    docs_in_scope = [SimpleNamespace(extraction_status="success", file_path="u/p/doc1.pdf")]
    db = _RouterDB(pet=pet, marker=marker, pending_docs=0, docs_in_scope=docs_in_scope)
    user = SimpleNamespace(
        id="user-3",
        _plaintext_mobile="919100000003",
        order_state=None,
        active_reminder_id=None,
        onboarding_completed_at=None,
    )

    calls = {"deferred": 0, "dashboard_links": 0}

    async def fake_deferred(*_args, **_kwargs):
        calls["deferred"] += 1

    async def fake_dashboard_links(*_args, **_kwargs):
        calls["dashboard_links"] += 1

    monkeypatch.setattr(message_router, "_has_pending_deferred_care_plan", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(message_router, "_send_deferred_care_plan", fake_deferred)
    monkeypatch.setattr(message_router, "_send_dashboard_links", fake_dashboard_links)

    asyncio.run(message_router._handle_text(db, user, {"text": "i want dashboard"}))  # type: ignore[arg-type]

    assert calls["deferred"] == 1
    assert calls["dashboard_links"] == 0


def test_dashboard_request_with_pending_docs_sends_building_status(monkeypatch):
    pet = SimpleNamespace(id="pet-4", name="Zayn", created_at=1)
    db = _RouterDB(pet=pet, marker=SimpleNamespace(created_at=None), pending_docs=1)
    user = SimpleNamespace(
        id="user-4",
        _plaintext_mobile="919100000004",
        order_state=None,
        active_reminder_id=None,
        onboarding_completed_at=None,
    )

    sent = []
    calls = {"deferred": 0, "dashboard_links": 0}

    async def fake_send(_db, _to, text):
        sent.append(text)

    async def fake_deferred(*_args, **_kwargs):
        calls["deferred"] += 1

    async def fake_dashboard_links(*_args, **_kwargs):
        calls["dashboard_links"] += 1

    monkeypatch.setattr(message_router, "_has_pending_deferred_care_plan", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(message_router, "send_text_message", fake_send)
    monkeypatch.setattr(message_router, "_send_deferred_care_plan", fake_deferred)
    monkeypatch.setattr(message_router, "_send_dashboard_links", fake_dashboard_links)

    asyncio.run(message_router._handle_text(db, user, {"text": "dashboard"}))  # type: ignore[arg-type]

    assert len(sent) == 1
    assert "still being prepared" in sent[0]
    assert calls["deferred"] == 0
    assert calls["dashboard_links"] == 0


def test_dashboard_request_without_pending_deferred_sends_dashboard_links(monkeypatch):
    pet = SimpleNamespace(id="pet-5", name="Zayn", created_at=1)
    db = _RouterDB(pet=pet)
    user = SimpleNamespace(
        id="user-5",
        _plaintext_mobile="919100000005",
        order_state=None,
        active_reminder_id=None,
        onboarding_completed_at=None,
    )

    calls = {"deferred": 0, "dashboard_links": 0}

    async def fake_deferred(*_args, **_kwargs):
        calls["deferred"] += 1

    async def fake_dashboard_links(*_args, **_kwargs):
        calls["dashboard_links"] += 1

    monkeypatch.setattr(message_router, "_has_pending_deferred_care_plan", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(message_router, "_send_deferred_care_plan", fake_deferred)
    monkeypatch.setattr(message_router, "_send_dashboard_links", fake_dashboard_links)

    asyncio.run(message_router._handle_text(db, user, {"text": "dashboard"}))  # type: ignore[arg-type]

    assert calls["deferred"] == 0
    assert calls["dashboard_links"] == 1


def test_chat_transcript_flow_avoids_duplicates_and_respects_dashboard_precedence(monkeypatch):
    """
    Regression for the observed chat transcript pattern:
    1) Bot asked for health records.
    2) User replied "yes"; upload prompt should not repeat immediately.
    3) User later asked for dashboard while care plan still building.
       - First ask: building-status only.
       - Next ask after processing: deferred care-plan message only.
       - Later ask: dashboard links.
    """

    # --- Phase 1: awaiting_documents duplicate suppression ---
    pet = SimpleNamespace(id="pet-6", name="Zayn", created_at=1)
    onboarding_db = _OnboardingDB(pet=pet, doc_count=0)
    onboarding_user = SimpleNamespace(
        id="user-6",
        _plaintext_mobile="919100000006",
        doc_upload_deadline=None,
        onboarding_data={
            "awaiting_docs_last_reply_at": time.time() - 15,
            "awaiting_docs_last_reply_text": "upload_prompt",
        },
    )

    onboarding_sent = []

    async def fake_onboarding_send(_db, _to, text):
        onboarding_sent.append(text)

    async def should_not_generate_upload_reply(*_args, **_kwargs):
        raise AssertionError("upload reply should be suppressed for immediate 'yes' ack")

    monkeypatch.setattr(onboarding, "_generate_doc_upload_reply", should_not_generate_upload_reply)

    asyncio.run(onboarding._step_awaiting_documents(onboarding_db, onboarding_user, "yes", fake_onboarding_send))

    assert onboarding_sent == []

    # --- Phase 2: post-onboarding dashboard precedence ---
    class _TranscriptRouterDB(_RouterDB):
        def query(self, *args, **kwargs):
            entity = args[0] if args else None
            name = getattr(entity, "__name__", "")
            if name == "Pet":
                return _CountQuery(self.pet)
            if name == "Document":
                return _CountQuery(self.docs_in_scope)
            # Covers Document.id pending-count query.
            return _CountQuery(self.pending_docs)

    router_db = _TranscriptRouterDB(
        pet=pet,
        pending_docs=1,
        docs_in_scope=[
            SimpleNamespace(extraction_status="success", file_path="user/pet/success.pdf"),
            SimpleNamespace(extraction_status="rejected", file_path="user/pet/rejected.pdf"),
        ],
    )
    router_user = SimpleNamespace(
        id="user-6",
        _plaintext_mobile="919100000006",
        order_state=None,
        active_reminder_id=None,
        onboarding_completed_at=None,
    )

    pending_state = {"value": True}
    sent = []
    calls = {"deferred": 0, "dashboard_links": 0}
    deferred_args = {}

    async def fake_send_text(_db, _to, text):
        sent.append(text)

    async def fake_deferred(_db, _user, _pet, _from, all_results, success_count, fail_count, failed_doc_names):
        calls["deferred"] += 1
        deferred_args["success_count"] = success_count
        deferred_args["fail_count"] = fail_count
        deferred_args["failed_doc_names"] = failed_doc_names

    async def fake_dashboard_links(*_args, **_kwargs):
        calls["dashboard_links"] += 1

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
    monkeypatch.setattr(message_router, "send_text_message", fake_send_text)
    monkeypatch.setattr(message_router, "_send_deferred_care_plan", fake_deferred)
    monkeypatch.setattr(message_router, "_send_dashboard_links", fake_dashboard_links)

    # Ask 1: pending docs exist -> building status only.
    asyncio.run(message_router._handle_text(router_db, router_user, {"text": "i want to see dashboard"}))  # type: ignore[arg-type]
    assert len(sent) == 1
    assert "still being prepared" in sent[0]
    assert calls["deferred"] == 0
    assert calls["dashboard_links"] == 0

    # Ask 2: processing complete but deferred marker still active -> deferred care plan only.
    router_db.pending_docs = 0
    asyncio.run(message_router._handle_text(router_db, router_user, {"text": "dashboard"}))  # type: ignore[arg-type]
    assert calls["deferred"] == 1
    assert calls["dashboard_links"] == 0
    assert deferred_args["success_count"] == 1
    assert deferred_args["fail_count"] == 1
    assert deferred_args["failed_doc_names"] == ["rejected.pdf"]

    # Ask 3: deferred state cleared later -> dashboard links allowed.
    pending_state["value"] = False
    asyncio.run(message_router._handle_text(router_db, router_user, {"text": "dashboard link"}))  # type: ignore[arg-type]
    assert calls["dashboard_links"] == 1
