import json
from aio_pika import connect_robust, Message, IncomingMessage
from app.core.config import settings

import logging
logger = logging.getLogger(__name__)

async def get_rabbit_connection():
    try:
        return await connect_robust(settings.RABBITMQ_URL)
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        raise

async def publish(channel, routing_key: str, payload: dict, **props):
    await channel.default_exchange.publish(
        Message(body=json.dumps(payload).encode(), **props),
        routing_key=routing_key,
    )
