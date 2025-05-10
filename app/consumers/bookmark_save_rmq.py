import json, uuid, logging
from aio_pika import IncomingMessage, Message
from pydantic import ValidationError
from app.core.rabbit import get_rabbit_connection
from app.core.config import get_settings
from app.tasks.bookmark_save_task import save_bookmark_task

from pydantic import BaseModel, Field
from typing import List

class BookmarkSaveRequest(BaseModel):
    user_id:  str    = Field(..., alias="userId")
    s3_key:   str    = Field(..., alias="s3Key")
    keywords: List[str]
    memo:     str
    summary:  str

    class Config:
        allow_population_by_field_name = True


log = logging.getLogger(__name__)
settings = get_settings()

async def on_bookmark_save(message: IncomingMessage):
    async with message.process():
        try:
            req = BookmarkSaveRequest.model_validate_json(message.body)
        except ValidationError as e:
            log.error("Invalid payload: %s", e)
            return 

        save_bookmark_task.delay(
            user_id=req.user_id,
            s3_key=req.s3_key,
            keywords=req.keywords,
            memo=req.memo,
            summary=req.summary
        )

        log.info("BookmarkSave 요청 수신, user_id=%s", req.user_id)

async def start_bookmark_save_consumer():
    conn    = await get_rabbit_connection()
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue(
        settings.BOOKMARK_SAVE_QUEUE, durable=True
    )
    await queue.consume(on_bookmark_save)
    log.info("BookmarkSave Consumer listening on %s", queue.name)
