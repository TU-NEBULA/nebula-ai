"""
데이터 추출 요청 메시지 소비자 모듈

이 모듈은 RabbitMQ를 통해 HTML 콘텐츠 데이터 추출 요청을 받아 처리합니다.
S3에 저장된 HTML에서 이미지와 키워드를 추출하고 그 결과를 응답으로 반환합니다.
"""
import uuid
import logging
from aio_pika import IncomingMessage, Message
from pydantic import BaseModel, Field, ConfigDict


from app.core.rabbit import get_rabbit_connection
from app.services.extract_data import extract_data_from_s3_async
from app.core.config import settings

log = logging.getLogger(__name__)
class ExtractDataResponse(BaseModel):
    """
    데이터 추출 응답 모델
    
    HTML 콘텐츠에서 추출한 이미지 URL과 키워드를 포함하는 응답 모델입니다.
    """
    id: int
    image_url: str
    keywords: list

class ExtractDataRequest(BaseModel):
    """
    데이터 추출 요청 모델
    
    RabbitMQ를 통해 수신된 데이터 추출 요청을 검증하고 파싱하기 위한 모델입니다.
    """
    user_id: int = Field(..., alias="userId")
    s3_key: str = Field(..., alias="s3Key")

    model_config = ConfigDict(populate_by_name=True)


async def on_extract_message(ch, message: IncomingMessage):
    """
    데이터 추출 메시지 처리 핸들러
    
    RabbitMQ에서 받은 데이터 추출 요청 메시지를 처리하고 추출한 데이터를 응답으로 반환합니다.
    
    Args:
        ch: RabbitMQ 채널 객체
        message (IncomingMessage): RabbitMQ에서 받은 메시지 객체
    """
    async with message.process():
        try:
            req = ExtractDataRequest.model_validate_json(message.body)

            data = await extract_data_from_s3_async(req.user_id, req.s3_key)

            response = ExtractDataResponse(
                id = req.user_id,
                image_url = data["image_url"],
                keywords = data["keywords"],
            )

            await ch.default_exchange.publish(
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
    """
    데이터 추출 콘슈머 시작
    
    RabbitMQ에 연결하고 데이터 추출 큐를 선언한 후 메시지 소비를 시작합니다.
    """
    conn = await get_rabbit_connection()
    ch = await conn.channel()

    await ch.set_qos(prefetch_count=1)

    q = await ch.declare_queue(settings.EXTRACT_REQ_QUEUE, durable=True)
    async def handler(message: IncomingMessage):
        """
        채널 객체를 포함한 메시지 처리 핸들러
        
        Args:
            message (IncomingMessage): RabbitMQ에서 받은 메시지 객체
        """
        await on_extract_message(ch, message)

    await q.consume(handler)

    log.info(" [*] extract_data_rmq 리스너 시작, queue=%s", q.name)
