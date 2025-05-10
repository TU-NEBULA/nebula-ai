import json
from aio_pika import connect_robust, Message, IncomingMessage
from app.core.config import settings

async def get_rabbit_connection():
    return await connect_robust(settings.RABBITMQ_URL)

async def publish(channel, routing_key: str, payload: dict, **props):
    await channel.default_exchange.publish(
        Message(body=json.dumps(payload).encode(), **props),
        routing_key=routing_key,
    )
