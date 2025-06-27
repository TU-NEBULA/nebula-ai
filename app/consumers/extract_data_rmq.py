"""
데이터 추출 요청 메시지 소비자 모듈

이 모듈은 RabbitMQ를 통해 HTML 콘텐츠 데이터 추출 요청을 받아 처리합니다.
S3에 저장된 HTML에서 이미지와 키워드를 추출하고 그 결과를 응답으로 반환합니다.
"""
import asyncio
import traceback
import json
import uuid

from aio_pika import IncomingMessage, Message
from aio_pika.exceptions import AMQPException
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from loguru import logger

from app.core.rabbit import get_rabbit_connection
from app.core.config import settings
from app.models.extract_data import ExtractDataRequest
from app.tasks.data_extractor_nlp import NebulaNLPExtractor

log = logger.bind(name=__name__)

async def _cleanup_extract_consumer_connections(connection, channel):
    """Extract Consumer 연결 정리"""
    try:
        if channel and not channel.is_closed:
            await channel.close()
            logger.info("✅ Extract Consumer 채널 정리 완료")
    except Exception as e:
        logger.warning(f"Extract Consumer 채널 정리 중 오류: {e}")
    
    try:
        if connection and not connection.is_closed:
            await connection.close()
            logger.info("✅ Extract Consumer 연결 정리 완료")
    except Exception as e:
        logger.warning(f"Extract Consumer 연결 정리 중 오류: {e}")

class ExtractDataResponse(BaseModel):
    """
    데이터 추출 응답 모델
    
    HTML 콘텐츠에서 추출한 이미지 URL과 키워드를 포함하는 응답 모델입니다.
    """
    id: int
    image_url: str
    keywords: list

async def on_extract_message(ch, message: IncomingMessage):
    """
    추출 메시지를 처리하는 함수
    """
    async with message.process():
        logger.info(f"📨 추출 메시지 수신: correlation_id={message.correlation_id}")

        try:
            request = ExtractDataRequest.model_validate_json(message.body)
            logger.info(f"✅ 메시지 파싱 성공: user_id={request.user_id}, url={request.url}, s3_key={request.s3_key}")
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"❌ 메시지 파싱 실패: {e}")
            return

        logger.info(f"🚀 데이터 추출 시작 - uid={request.user_id}, url={request.url}, s3_key={request.s3_key}")

        try:
            extractor = NebulaNLPExtractor()
            
            # 🔍 추가: 추출 과정 상세 로깅
            logger.info(f"📋 추출 요청 상세 정보 - uid={request.user_id}")
            logger.debug(f"  - URL: {request.url}")
            logger.debug(f"  - S3 Key: {request.s3_key}")
            
            result = await extractor.extract_and_process(request)
            
            # 🔍 추가: 추출 결과 상세 분석
            logger.info(f"📊 추출 결과 분석 - uid={request.user_id}")
            logger.debug(f"  - 전체 결과 키들: {list(result.keys()) if result else 'None'}")
            
            keywords = result.get('keywords', [])
            image_url = result.get('image_url', '')
            documents = result.get('documents', [])
            
            logger.info(f"  - 키워드 수: {len(keywords)}")
            logger.info(f"  - 이미지 URL: {'있음' if image_url else '없음'}")
            logger.info(f"  - 문서 수: {len(documents)}")
            
            # 🔍 추가: 키워드가 0개인 경우 경고
            if len(keywords) == 0:
                logger.warning(f"⚠️ 키워드 추출 실패 - uid={request.user_id}")
                logger.debug(f"  - 추출 결과 상세: {result}")
                
                # HTML 내용이 있는지 확인
                if documents:
                    logger.debug(f"  - 첫 번째 문서 길이: {len(documents[0].get('content', '')) if documents[0] else 0}")
                else:
                    logger.warning(f"  - 문서가 전혀 추출되지 않음")
            else:
                # 키워드가 있는 경우 첫 몇 개만 로깅 (개인정보 주의)
                logger.info(f"  - 추출된 키워드 예시: {keywords[:3]}...")

            document_count = len(documents)
            logger.info(
                f"✅ 데이터 추출 완료 - uid={request.user_id}, "
                f"처리된 문서 수: {document_count}"
            )

            # 🔧 수정: documents 구조에서 올바르게 데이터 추출
            if documents and len(documents) > 0:
                first_doc = documents[0]
                response_keywords = first_doc.get('keywords', [])
                response_image_url = first_doc.get('thumbnail', '')
            else:
                response_keywords = []
                response_image_url = ''
                logger.warning(f"⚠️ 문서가 없어 빈 응답 생성 - uid={request.user_id}")

            # 추출 결과를 응답 모델로 변환
            response = ExtractDataResponse(
                id=request.user_id,
                image_url=response_image_url,
                keywords=response_keywords
            )

            # Spring Boot로 응답 전송
            if message.reply_to:
                await ch.default_exchange.publish(
                    Message(
                        body=response.model_dump_json().encode(),
                        correlation_id=message.correlation_id or str(uuid.uuid4())
                    ),
                    routing_key=message.reply_to
                )
                # 개인정보를 제외한 안전한 로깅
                logger.info(
                    f"📤 응답 전송 완료 - uid={request.user_id}, "
                    f"reply_to={message.reply_to}, "
                    f"키워드 수: {len(response.keywords)}, "
                    f"이미지 URL 존재: {'예' if response.image_url else '아니오'}"
                )
            else:
                logger.warning(f"⚠️ reply_to가 없어 응답을 전송할 수 없습니다 - uid={request.user_id}")

        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"❌ 데이터 추출 실패: {tb}")
            raise


async def start_extract_consumer():
    """
    데이터 추출 컨슈머를 시작하는 함수
    """
    logger.info("📊 Extract Data Consumer 시작 준비...")
    connection = None
    channel = None

    try:
        connection = await get_rabbit_connection()
        logger.info("✅ RabbitMQ 연결 성공")

        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        logger.info("✅ 채널 설정 완료")

        queue = await channel.declare_queue(settings.EXTRACT_REQ_QUEUE, durable=True)
        logger.info(f"✅ 큐 선언 완료: {settings.EXTRACT_REQ_QUEUE}")

        async def handler(message: IncomingMessage):
            await on_extract_message(channel, message)

        logger.info(f"🎯 Extract consumer 대기 중: {settings.EXTRACT_REQ_QUEUE}")
        await queue.consume(handler)
        
        # 무한 대기 (테스트 환경이 아닌 경우)
        import os
        if not os.getenv("PYTEST_CURRENT_TEST"):
            try:
                await asyncio.Future()  # 무한 대기
            finally:
                await _cleanup_extract_consumer_connections(connection, channel)

    except AMQPException as e:
        logger.error(f"❌ Extract Data Consumer 시작 실패: {e}")
        await _cleanup_extract_consumer_connections(connection, channel)
        raise
    except Exception as e:
        logger.error(f"❌ Extract Data Consumer 예상치 못한 오류: {e}")
        await _cleanup_extract_consumer_connections(connection, channel)
        raise
