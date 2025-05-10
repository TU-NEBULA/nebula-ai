import json
import uuid
import logging
from aio_pika import IncomingMessage, Message
from pydantic import BaseModel, Field

from app.core.rabbit import get_rabbit_connection
from app.services.chat import process_chat_request
from app.core.config import settings

log = logging.getLogger(__name__)


class ChatRequestModel(BaseModel):
    user_id: int = Field(..., alias="userId")
    message: str
    scope: str = Field("both", description="visit, bookmark, both")

    class Config:
        allow_population_by_field_name = True


class BookmarkItemModel(BaseModel):
    id: str
    title: str
    url: str
    snippet: str


class ChatResponseModel(BaseModel):
    items: list[BookmarkItemModel]


async def on_chat_message(ch, message: IncomingMessage):
    async with message.process():
        try:
            req = ChatRequestModel.model_validate_json(message.body)

            resp_data = await process_chat_request(
                user_id = req.user_id,
                message = req.message,
                scope = req.scope
            )

            chat_resp = ChatResponseModel.model_validate(resp_data)

            await ch.default_exchange.publish(
                Message(
                    body = chat_resp.model_dump_json().encode(),
                    correlation_id = message.correlation_id or str(uuid.uuid4())
                ),
                routing_key=message.reply_to
            )

            log.info("Chat 처리 완료 userId=%s scope=%s", req.user_id, req.scope)

        except Exception as e:
            log.error("Chat 처리 실패 error=%s body=%s", str(e), message.body)
            raise


async def start_chat_consumer():
    conn = await get_rabbit_connection()
    ch   = await conn.channel()

    await ch.set_qos(prefetch_count=1)

    q = await ch.declare_queue(settings.CHAT_REQ_QUEUE, durable=True)
    async def handler(message: IncomingMessage):
        await on_chat_message(ch, message)
    await q.consume(handler)

    log.info(" [*] chat_request_rmq 리스너 시작, queue=%s", q.name)
