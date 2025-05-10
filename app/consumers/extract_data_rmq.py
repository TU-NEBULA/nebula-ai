import json
import uuid
import logging
from aio_pika import IncomingMessage, Message
from pydantic import BaseModel, Field

from app.core.rabbit import get_rabbit_connection
from app.services.extract_data import extract_data_from_s3_async
from app.schemas.extract_data_response import ExtractDataResponse
from app.core.config import settings

log = logging.getLogger(__name__)

class ExtractDataRequest(BaseModel):
    user_id: str = Field(..., alias="userId")
    s3_key:  str = Field(..., alias="s3Key")

    class Config:
        allow_population_by_field_name = True


async def on_extract_message(message: IncomingMessage):
    async with message.process():
        try:
            req = ExtractDataRequest.model_validate_json(message.body)

            data = await extract_data_from_s3_async(req.user_id, req.s3_key)

            response = ExtractDataResponse(
                id = req.user_id,
                image_url = data["image_url"],
                keywords = data["keywords"],
            )

            await message.channel.default_exchange.publish(
                Message(
                    body = response.model_dump_json().encode(),
                    correlation_id = message.correlation_id or str(uuid.uuid4())
                ),
                routing_key=message.reply_to
            )

            log.info("ExtractData 완료 id=%s", req.user_id)
            
        except Exception as e:
            log.error("ExtractData 실패 error=%s body=%s", str(e), message.body)
            raise


async def start_extract_consumer():
    conn = await get_rabbit_connection()
    ch   = await conn.channel()

    await ch.set_qos(prefetch_count=1)

    q = await ch.declare_queue(settings.EXTRACT_REQ_QUEUE, durable=True)
    await q.consume(on_extract_message)

    log.info(" [*] extract_data_rmq 리스너 시작, queue=%s", q.name)
