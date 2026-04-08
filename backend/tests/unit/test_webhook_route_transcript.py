from types import SimpleNamespace

from app.database import get_db
from app.routers import webhook


class _FakeQuery:
    def __init__(self, db):
        self._db = db

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        self._db.first_calls += 1
        if self._db.return_existing:
            return SimpleNamespace(id="existing")
        return None


class _FakeDB:
    def __init__(self, *, return_existing: bool = False):
        self.return_existing = return_existing
        self.add_calls = 0
        self.commit_calls = 0
        self.first_calls = 0

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self)

    def add(self, *_args, **_kwargs):
        self.add_calls += 1

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        return None


def _build_whatsapp_text_payload(*, message_id: str, text: str, from_number: str = "919188877700") -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {
                                    "wa_id": from_number,
                                    "profile": {"name": "Sheryl"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": message_id,
                                    "timestamp": "1712467200",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def test_webhook_ingestion_dispatches_and_dedups_by_message_id(client, app, monkeypatch):
    webhook._DEDUP_CACHE.clear()

    fake_db = _FakeDB()
    app.dependency_overrides[get_db] = lambda: fake_db

    dispatched = []
    create_task_calls = {"count": 0}

    async def _noop_background():
        return None

    def fake_process_message_background(message_data):
        dispatched.append(dict(message_data))
        return _noop_background()

    def fake_create_task(coro):
        create_task_calls["count"] += 1
        # In tests we don't execute background work; close the coroutine to
        # avoid unawaited-coroutine warnings while still asserting dispatch.
        coro.close()
        return SimpleNamespace(done=lambda: True)

    monkeypatch.setattr(webhook, "verify_webhook_signature", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(webhook.rate_limiter, "check_rate_limit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(webhook, "_process_message_background", fake_process_message_background)
    monkeypatch.setattr(webhook.asyncio, "create_task", fake_create_task)

    try:
        payload_1 = _build_whatsapp_text_payload(message_id="wamid.tx.1", text="dashboard")
        # Same text with a different message_id should still dispatch.
        payload_2 = _build_whatsapp_text_payload(message_id="wamid.tx.2", text="dashboard")
        # Same message_id with different text should be deduped.
        payload_2_retry = _build_whatsapp_text_payload(message_id="wamid.tx.2", text="dashboard link")

        r1 = client.post("/webhook/whatsapp", json=payload_1, headers={"X-Hub-Signature-256": "ok"})
        r2 = client.post("/webhook/whatsapp", json=payload_2, headers={"X-Hub-Signature-256": "ok"})
        r2_retry = client.post("/webhook/whatsapp", json=payload_2_retry, headers={"X-Hub-Signature-256": "ok"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2_retry.status_code == 200

        assert [item.get("message_id") for item in dispatched] == [
            "wamid.tx.1",
            "wamid.tx.2",
        ]
        assert [item.get("text") for item in dispatched] == ["dashboard", "dashboard"]
        assert create_task_calls["count"] == 2
        assert fake_db.add_calls == 2
        assert fake_db.commit_calls == 2
    finally:
        webhook._DEDUP_CACHE.clear()
        app.dependency_overrides.clear()


def test_webhook_db_dedup_blocks_dispatch_when_cache_misses(client, app, monkeypatch):
    webhook._DEDUP_CACHE.clear()

    fake_db = _FakeDB(return_existing=True)
    app.dependency_overrides[get_db] = lambda: fake_db

    dispatched = []
    create_task_calls = {"count": 0}

    async def _noop_background():
        return None

    def fake_process_message_background(message_data):
        dispatched.append(dict(message_data))
        return _noop_background()

    def fake_create_task(coro):
        create_task_calls["count"] += 1
        coro.close()
        return SimpleNamespace(done=lambda: True)

    monkeypatch.setattr(webhook, "verify_webhook_signature", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(webhook.rate_limiter, "check_rate_limit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(webhook, "_is_duplicate_message", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(webhook, "_process_message_background", fake_process_message_background)
    monkeypatch.setattr(webhook.asyncio, "create_task", fake_create_task)

    try:
        payload = _build_whatsapp_text_payload(message_id="wamid.db.1", text="dashboard")
        response = client.post("/webhook/whatsapp", json=payload, headers={"X-Hub-Signature-256": "ok"})

        assert response.status_code == 200
        assert dispatched == []
        assert create_task_calls["count"] == 0
        assert fake_db.add_calls == 0
        assert fake_db.commit_calls == 0
        assert fake_db.first_calls >= 1
    finally:
        webhook._DEDUP_CACHE.clear()
        app.dependency_overrides.clear()


def test_webhook_returns_200_while_background_task_finishes_later(client, app, monkeypatch):
    webhook._DEDUP_CACHE.clear()

    fake_db = _FakeDB()
    app.dependency_overrides[get_db] = lambda: fake_db

    state = {"started": False, "finished": False, "task_calls": 0}
    scheduled_coros = []

    async def fake_process_message_background(_message_data):
        state["started"] = True
        await webhook.asyncio.sleep(0.05)
        state["finished"] = True

    def tracked_create_task(coro):
        state["task_calls"] += 1
        scheduled_coros.append(coro)
        return SimpleNamespace(done=lambda: False)

    monkeypatch.setattr(webhook, "verify_webhook_signature", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(webhook.rate_limiter, "check_rate_limit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(webhook, "_process_message_background", fake_process_message_background)
    monkeypatch.setattr(webhook.asyncio, "create_task", tracked_create_task)

    try:
        payload = _build_whatsapp_text_payload(message_id="wamid.bg.1", text="dashboard")
        response = client.post("/webhook/whatsapp", json=payload, headers={"X-Hub-Signature-256": "ok"})

        assert response.status_code == 200
        assert state["task_calls"] == 1
        # Webhook should acknowledge quickly without waiting for background work.
        assert state["started"] is False
        assert state["finished"] is False
        assert len(scheduled_coros) == 1

        # Execute the captured background coroutine explicitly so completion
        # semantics are verified deterministically in unit tests.
        webhook.asyncio.run(scheduled_coros.pop())

        assert state["finished"] is True
    finally:
        while scheduled_coros:
            coro = scheduled_coros.pop()
            try:
                coro.close()
            except Exception:
                pass
        webhook._DEDUP_CACHE.clear()
        app.dependency_overrides.clear()


def test_extract_message_data_button_includes_button_text() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "919188877700",
                                    "id": "wamid.btn.1",
                                    "type": "button",
                                    "button": {
                                        "payload": "NO",
                                        "text": "No",
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    result = webhook._extract_message_data(payload)

    assert result["type"] == "button"
    assert result["button_payload"] == "NO"
    assert result["text"] == "No"


def test_extract_message_data_interactive_button_includes_title() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "919188877700",
                                    "id": "wamid.btn.2",
                                    "type": "interactive",
                                    "interactive": {
                                        "button_reply": {
                                            "id": "no",
                                            "title": "No",
                                        }
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    result = webhook._extract_message_data(payload)

    assert result["type"] == "button"
    assert result["button_payload"] == "no"
    assert result["text"] == "No"
