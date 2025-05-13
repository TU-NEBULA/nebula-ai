"""
북마크 저장 메시지 소비자 모듈

이 모듈은 RabbitMQ를 통해 북마크 저장 요청을 받아 처리합니다.
요청을 검증한 후 Celery 태스크로 북마크 저장 작업을 위임합니다.
"""
import logging
from aio_pika import IncomingMessage
from pydantic import ValidationError
from app.core.rabbit import get_rabbit_connection
from app.core.config import settings
from app.tasks.bookmark_save_task import save_bookmark_task

from pydantic import BaseModel, Field
from typing import List

class BookmarkSaveRequest(BaseModel):
    """
    북마크 저장 요청 모델
    
    RabbitMQ를 통해 수신된 북마크 저장 요청을 검증하고 파싱하기 위한 모델입니다.
    """
    user_id: int = Field(..., alias="userId")
    s3_key: str = Field(..., alias="s3Key")
    star_id: str = Field(..., alias="starId")
    keywords: List[str]
    memo: str
    summary: str

    class Config:
        allow_population_by_field_name = True


log = logging.getLogger(__name__)

async def on_bookmark_save(message: IncomingMessage):
    """
    북마크 저장 메시지 처리 핸들러
    
    RabbitMQ에서 받은 북마크 저장 메시지를 검증하고 Celery 태스크로 처리를 위임합니다.
    
    Args:
        message (IncomingMessage): RabbitMQ에서 받은 메시지 객체
    """
    async with message.process():
        try:
            req = BookmarkSaveRequest.model_validate_json(message.body)
        except ValidationError as e:
            log.error("Invalid payload: %s", e)
            return 

        save_bookmark_task.delay(
            user_id=req.user_id,
            star_id=req.star_id,
            s3_key=req.s3_key,
            keywords=req.keywords,
            memo=req.memo,
            summary=req.summary
        )

        log.info("BookmarkSave 요청 수신, user_id=%s", req.user_id)

async def start_bookmark_save_consumer():
    """
    북마크 저장 콘슈머 시작
    
    RabbitMQ에 연결하고 북마크 저장 큐를 선언한 후 메시지 소비를 시작합니다.
    """
    
    conn    = await get_rabbit_connection()
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue(
        settings.BOOKMARK_SAVE_QUEUE, durable=True
    )
    await queue.consume(on_bookmark_save)
    log.info("BookmarkSave Consumer listening on %s", queue.name)
