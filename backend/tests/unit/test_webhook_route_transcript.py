from types import SimpleNamespace

from app.database import get_db
from app.routers import webhook


class _FakeQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _FakeDB:
    def query(self, *_args, **_kwargs):
        return _FakeQuery()

    def add(self, *_args, **_kwargs):
        return None

    def commit(self):
        return None

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


def test_webhook_ingestion_dispatches_transcript_texts_and_dedups_retry(client, app, monkeypatch):
    webhook._DEDUP_CACHE.clear()

    fake_db = _FakeDB()
    app.dependency_overrides[get_db] = lambda: fake_db

    dispatched = []

    async def _noop_background():
        return None

    def fake_process_message_background(message_data):
        dispatched.append(dict(message_data))
        return _noop_background()

    def fake_create_task(coro):
        # In tests we don't execute background work; close the coroutine to
        # avoid unawaited-coroutine warnings while still asserting dispatch.
        try:
            coro.close()
        except Exception:
            pass
        return SimpleNamespace(done=lambda: True)

    monkeypatch.setattr(webhook, "verify_webhook_signature", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(webhook.rate_limiter, "check_rate_limit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(webhook, "_process_message_background", fake_process_message_background)
    monkeypatch.setattr(webhook.asyncio, "create_task", fake_create_task)

    try:
        payload_1 = _build_whatsapp_text_payload(message_id="wamid.tx.1", text="i want to see dashboard")
        payload_2 = _build_whatsapp_text_payload(message_id="wamid.tx.2", text="dashboard")
        payload_3 = _build_whatsapp_text_payload(message_id="wamid.tx.3", text="dashboard link")

        r1 = client.post("/webhook/whatsapp", json=payload_1, headers={"X-Hub-Signature-256": "ok"})
        r2 = client.post("/webhook/whatsapp", json=payload_2, headers={"X-Hub-Signature-256": "ok"})
        r3 = client.post("/webhook/whatsapp", json=payload_3, headers={"X-Hub-Signature-256": "ok"})
        # Retry of payload_2 should be deduped at webhook layer.
        r2_retry = client.post("/webhook/whatsapp", json=payload_2, headers={"X-Hub-Signature-256": "ok"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200
        assert r2_retry.status_code == 200

        assert [item.get("text") for item in dispatched] == [
            "i want to see dashboard",
            "dashboard",
            "dashboard link",
        ]
        assert len(dispatched) == 3
    finally:
        app.dependency_overrides.clear()
