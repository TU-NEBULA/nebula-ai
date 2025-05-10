import json
import pytest
import asyncio

from uuid import uuid4

@pytest.mark.asyncio
async def test_on_extract_message(monkeypatch):
    import app.consumers.extract_data_rmq as mod

    fake_data = {"image_url": "http://img.jpg", "keywords": ["k1","k2","k3"]}
    async def fake_extract(user_id, s3_key):
        return fake_data
    
    monkeypatch.setattr(
        mod,
        "extract_data_from_s3_async",
        fake_extract
    )
    
    from app.consumers.extract_data_rmq import on_extract_message

    class DummyMessage:
        def __init__(self, body, corr_id=None, reply_to="resp.queue"):
            self.body = body
            self.correlation_id = corr_id or str(uuid4())
            self.reply_to = reply_to
            self.channel = self
            self.default_exchange = self
            self.published = []

        def process(self):
            class Ctx:
                async def __aenter__(inner):
                    return self
                async def __aexit__(inner, exc_type, exc, tb):
                    pass
            return Ctx()

        async def publish(self, message, routing_key):
            self.published.append((message, routing_key))

    req_payload = {"userId": "user123", "s3Key": "path/to/file.html"}
    body_bytes = json.dumps(req_payload).encode()
    msg = DummyMessage(body_bytes)

    await on_extract_message(msg)

    assert len(msg.published) == 1
    published_msg, routing_key = msg.published[0]
    body = json.loads(published_msg.body.decode())
    assert body["image_url"] == fake_data["image_url"]
    assert body["keywords"]  == fake_data["keywords"]
    assert routing_key == msg.reply_to


@pytest.mark.asyncio
async def test_start_extract_consumer(monkeypatch):
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

    import app.consumers.extract_data_rmq as mod
    monkeypatch.setattr(mod, "get_rabbit_connection", fake_get_conn)

    from app.core.config import settings
    settings.EXTRACT_REQ_QUEUE = "test.queue"

    from app.consumers.extract_data_rmq import start_extract_consumer
    await start_extract_consumer()

    assert ("set_qos", 1) in calls
    assert ("declare_queue", "test.queue", True) in calls
    assert any(call[0] == "consume" for call in calls)
