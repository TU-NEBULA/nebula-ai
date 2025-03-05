import pika
import json
from app.core.config import settings

RABBITMQ_HOST = settings.RABBITMQ_HOST
RABBITMQ_QUEUE = settings.RABBITMQ_QUEUE

def publish_message(message: dict):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    channel.basic_publish(
        exchange='',
        routing_key=RABBITMQ_QUEUE,
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  
        )
    )
    connection.close()
