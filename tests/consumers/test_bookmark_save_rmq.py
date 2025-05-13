import json
import pytest
from uuid import uuid4

import app.consumers.bookmark_save_rmq as mod 

@pytest.mark.asyncio
async def test_on_bookmark_save_success(monkeypatch):
    class DummyMessage:
        def __init__(self, body):
            self.body = body
        def process(self):
            class Ctx:
                async def __aenter__(inner):
                    return self
                async def __aexit__(inner, exc_type, exc, tb):
                    pass
            return Ctx()

    test_star_id = str(uuid4())
    payload = {
        "userId": 5,
        "starId": test_star_id,
        "s3Key": "path/to.html",
        "keywords": ["a", "b"],
        "memo": "mymemo",
        "summary": "mysummary"
    }
    msg = DummyMessage(json.dumps(payload).encode())

    called = {}
    def fake_delay(**kwargs):
        called.update(kwargs)
    monkeypatch.setattr(mod.save_bookmark_task, "delay", fake_delay)

    await mod.on_bookmark_save(msg)

    assert called == {
        "user_id": 5,
        "star_id": test_star_id,
        "s3_key": "path/to.html",
        "keywords": ["a", "b"],
        "memo": "mymemo",
        "summary": "mysummary"
    }

@pytest.mark.asyncio
async def test_on_bookmark_save_invalid(monkeypatch):
    class DummyMessage:
        def __init__(self, body):
            self.body = body
        def process(self):
            class Ctx:
                async def __aenter__(inner):
                    return self
                async def __aexit__(inner, exc_type, exc, tb):
                    pass
            return Ctx()
    msg = DummyMessage(b'{"bad": "data"}')

    def should_not_call(**kwargs):
        pytest.fail("delay should not be called on invalid payload")
    monkeypatch.setattr(mod.save_bookmark_task, "delay", should_not_call)

    await mod.on_bookmark_save(msg)

@pytest.mark.asyncio
async def test_start_bookmark_save_consumer(monkeypatch):
    calls = []

    class DummyQueue:
        def __init__(self, name):
            self.name = name
        async def consume(self, handler):
            calls.append(("consume", handler))

    class DummyChannel:
        async def set_qos(self, prefetch_count):
            calls.append(("set_qos", prefetch_count))
        async def declare_queue(self, queue_name, durable):
            calls.append(("declare_queue", queue_name, durable))
            return DummyQueue(queue_name)

    class DummyConnection:
        async def channel(self):
            return DummyChannel()

    async def fake_get_conn():
        return DummyConnection()

    monkeypatch.setattr(mod, "get_rabbit_connection", fake_get_conn)

    from app.core.config import settings
    settings.BOOKMARK_SAVE_QUEUE = "test.queue"

    await mod.start_bookmark_save_consumer()

    assert ("set_qos", 1) in calls
    assert ("declare_queue", "test.queue", True) in calls
    assert any(c[0] == "consume" for c in calls)
