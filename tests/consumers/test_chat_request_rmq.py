import pytest
import json
from uuid import uuid4

import app.consumers.chat_request_rmq as mod

class DummyExchange:
    def __init__(self):
        self.published = []

    async def publish(self, message, routing_key):
        self.published.append((message, routing_key))

class DummyChannel:
    def __init__(self):
        self.default_exchange = DummyExchange()
        self.qos = None

    async def set_qos(self, prefetch_count):
        self.qos = prefetch_count

class DummyMessage:
    def __init__(self, body: bytes, corr_id=None, reply_to="resp.queue"):
        self.body = body
        self.correlation_id = corr_id or str(uuid4())
        self.reply_to = reply_to
        self.channel = self 
        self.default_exchange = DummyExchange()
        self.published = []

    def process(self):
        class Ctx:
            async def __aenter__(inner):
                return self
            async def __aexit__(inner, exc_type, exc, tb):
                return False
        return Ctx()

    async def publish(self, message, routing_key):
        self.published.append((message, routing_key))

@pytest.fixture(autouse=True)
def mock_process_chat(monkeypatch):
    async def fake_process(user_id, message):
        return {"items": [{"id": "x1", "title": "T1", "url": "U1", "snippet": "S1"}]}

    monkeypatch.setattr(
        mod,
        "process_chat_request",
        fake_process
    )

@pytest.mark.asyncio
async def test_on_chat_message_success():
    payload = {"userId": 99, "message": "hello"}
    body = json.dumps(payload).encode()

    ch = DummyChannel()
    msg = DummyMessage(body, corr_id="cid", reply_to="reply_q")

    await mod.on_chat_message(ch, msg)

    published = ch.default_exchange.published
    assert len(published) == 1

    message_obj, rk = published[0]
    data = json.loads(message_obj.body.decode())
    assert data == {"items": [{"id": "x1", "title": "T1", "url": "U1", "snippet": "S1"}]}
    assert message_obj.correlation_id == "cid"
    assert rk == msg.reply_to

@pytest.mark.asyncio
async def test_on_chat_message_invalid_json_raises():
    body = b'{"userId": 1, "message": "bad"'
    ch = DummyChannel()
    msg = DummyMessage(body)

    with pytest.raises(Exception):
        await mod.on_chat_message(ch, msg)

@pytest.mark.asyncio
async def test_start_chat_consumer(monkeypatch):
    calls = []

    class DummyQueue:
        def __init__(self, name):
            self.name = name
        async def consume(self, handler):
            calls.append(("consume", handler))

    class DummyChannel2:
        async def set_qos(self, prefetch_count):
            calls.append(("set_qos", prefetch_count))
        async def declare_queue(self, queue_name, durable):
            calls.append(("declare_queue", queue_name, durable))
            return DummyQueue(queue_name)

    class DummyConn:
        async def channel(self):
            return DummyChannel2()

    async def fake_get_conn():
        return DummyConn()

    monkeypatch.setattr(mod, "get_rabbit_connection", fake_get_conn)
    from app.core.config import settings
    settings.CHAT_REQ_QUEUE = "test.chat.queue"

    await mod.start_chat_consumer()

    assert ("set_qos", 1) in calls
    assert ("declare_queue", "test.chat.queue", True) in calls
    assert any(c[0] == "consume" for c in calls)
