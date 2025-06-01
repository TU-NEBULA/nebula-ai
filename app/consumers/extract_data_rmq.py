"""
데이터 추출 요청 메시지 소비자 모듈

이 모듈은 RabbitMQ를 통해 HTML 콘텐츠 데이터 추출 요청을 받아 처리합니다.
S3에 저장된 HTML에서 이미지와 키워드를 추출하고 그 결과를 응답으로 반환합니다.
"""
import asyncio
import json
import traceback
import uuid

import aio_pika
from aio_pika import IncomingMessage, Message
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from app.core.rabbit import get_rabbit_connection
from app.services.extract_data import extract_data_from_s3_async
from app.core.config import settings
from app.models.extract_data import ExtractDataModel
from app.tasks.data_extractor_nlp import NebulaNLPExtractor

log = logger.bind(name=__name__)

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


async def on_extract_message(message: IncomingMessage):
    """
    추출 메시지를 처리하는 함수
    """
    async with message.process():
        logger.info(f"📨 추출 메시지 수신: correlation_id={message.correlation_id}")
        
        try:
            request = ExtractDataModel.model_validate_json(message.body)
            logger.info(f"✅ 메시지 파싱 성공: user_id={request.user_id}, url={request.url}")
        except Exception as e:
            logger.error(f"❌ 메시지 파싱 실패: {e}")
            return

        logger.info(f"🚀 데이터 추출 시작 - uid={request.user_id}, url={request.url}")

        try:
            extractor = NebulaNLPExtractor()
            result = await extractor.extract_and_process(request)
            logger.info(f"✅ 데이터 추출 완료 - uid={request.user_id}, 처리된 문서 수: {len(result.get('documents', []))}")
        except Exception:
            tb = traceback.format_exc()
            logger.error(f"❌ 데이터 추출 실패: {tb}")


async def start_extract_consumer():
    """
    데이터 추출 컨슈머를 시작하는 함수
    """
    logger.info("📊 Extract Data Consumer 시작 준비...")
    
    try:
        connection = await get_rabbit_connection()
        logger.info("✅ RabbitMQ 연결 성공")
        
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        logger.info("✅ 채널 설정 완료")

        queue = await channel.declare_queue(settings.EXTRACT_REQ_QUEUE, durable=True)
        logger.info(f"✅ 큐 선언 완료: {settings.EXTRACT_REQ_QUEUE}")

        logger.info(f"🎯 Extract consumer 대기 중: {settings.EXTRACT_REQ_QUEUE}")
        await queue.consume(on_extract_message)
        
    except Exception as e:
        logger.error(f"❌ Extract Data Consumer 시작 실패: {e}")
        raise
