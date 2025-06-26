"""
북마크 저장 RabbitMQ Consumer

북마크 저장 요청을 처리하여 Celery 태스크로 전달하는 Consumer입니다.
무거운 작업(유사도 계산, S3 다운로드, 벡터 저장)은 모두 백그라운드에서 처리됩니다.
"""
import json
import asyncio
import os

from aio_pika import IncomingMessage
from aio_pika.exceptions import AMQPException
from loguru import logger

from app.core.config import settings
from app.core.rabbit import get_rabbit_connection
from app.tasks.bookmark_save_task import save_bookmark_task

async def _cleanup_consumer_connections(connection, channel):
    """Consumer 연결 정리"""
    try:
        if channel and not channel.is_closed:
            await channel.close()
            logger.info("✅ Consumer 채널 정리 완료")
    except Exception as e:
        logger.warning(f"Consumer 채널 정리 중 오류: {e}")
    
    try:
        if connection and not connection.is_closed:
            await connection.close()
            logger.info("✅ Consumer 연결 정리 완료")
    except Exception as e:
        logger.warning(f"Consumer 연결 정리 중 오류: {e}")

async def on_bookmark_save(message: IncomingMessage):
    """
    북마크 저장 메시지 처리
    
    Consumer는 빠른 메시지 파싱과 검증만 수행하고,
    모든 무거운 작업은 Celery 태스크로 위임합니다.
    """
    async with message.process():
        user_id = None
        star_id = None

        try:
            # 1. 메시지 파싱
            body = message.body.decode('utf-8')
            bookmark_data = json.loads(body)

            star_id = bookmark_data.get("starId", "unknown")
            logger.info("📨 북마크 저장 메시지 수신 - starId: {}", star_id)

            # 2. 필수 필드 검증
            required_fields = ["userId", "starId", "s3Key", "title", "url"]
            for field in required_fields:
                if field not in bookmark_data:
                    raise ValueError(f"필수 필드 누락: {field}")

            # 3. user_id 타입 검증 및 변환
            try:
                user_id = int(bookmark_data["userId"])
                if user_id <= 0:
                    raise ValueError("userId는 양수여야 합니다")
            except (ValueError, TypeError) as e:
                raise ValueError(f"userId는 유효한 정수여야 합니다: {bookmark_data.get('userId')}") from e

            logger.info("✅ 메시지 검증 완료 - userId: {}, starId: {}", user_id, star_id)

            # 4. 전체 워크플로우를 Celery 태스크로 위임
            # (유사도 계산 + 관계 발행 + S3 다운로드 + 벡터 저장)
            logger.info("🚀 북마크 처리 태스크 시작...")
            save_bookmark_task.delay({
                "user_id": user_id,
                "star_id": bookmark_data["starId"],
                "s3_key": bookmark_data["s3Key"],
                "title": bookmark_data.get("title", ""),
                "url": bookmark_data.get("url", ""),
                "keywords": bookmark_data.get("keywords", []),
                "memo": bookmark_data.get("memo", ""),
                "summary": bookmark_data.get("summary", "")
            })

            # 5. Consumer 처리 완료 로그 (실제 작업은 백그라운드에서 진행)
            logger.info("✅ 메시지 처리 완료 - 백그라운드 태스크 시작됨 - userId: {}, starId: {}", user_id, star_id)

        except json.JSONDecodeError as e:
            logger.error("❌ JSON 파싱 오류: {}", e)
        except UnicodeDecodeError as e:
            logger.error("❌ 메시지 디코딩 오류: {}", e)
        except KeyError as e:
            logger.error("❌ 필수 키 누락 오류 - starId: {}, 오류: {}", star_id, e)
        except ValueError as e:
            logger.error("❌ 데이터 검증 오류 - starId: {}, 오류: {}", star_id, e)
        except TypeError as e:
            logger.error("❌ 타입 오류 - starId: {}, 오류: {}", star_id, e)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # 예상하지 못한 오류가 메시지 처리를 중단시키지 않도록 최후 방어선
            logger.exception("❌ 예상하지 못한 메시지 처리 오류 - starId: {}, 오류: {}", star_id, e)

async def start_bookmark_save_consumer():
    """북마크 저장 Consumer 시작"""
    max_retries = 5
    retry_delay = 5  # 5초 간격으로 재시도
    connection = None
    channel = None
    
    for attempt in range(max_retries):
        try:
            logger.info("🚀 북마크 저장 Consumer 시작 시도 {}/{} - 큐: {}", 
                       attempt + 1, max_retries, settings.BOOKMARK_SAVE_QUEUE)
            
            # RabbitMQ 연결
            connection = await get_rabbit_connection()
            logger.info("✅ RabbitMQ 연결 성공")
            
            channel = await connection.channel()
            logger.info("✅ 채널 생성 성공")

            # QoS 설정 (안전한 순차 처리를 위해 1로 설정)
            # 나중에 시스템 안정성 확인 후 점진적으로 증가 예정
            await channel.set_qos(prefetch_count=1)
            logger.info("✅ QoS 설정 완료")

            # 큐 선언
            queue = await channel.declare_queue(
                settings.BOOKMARK_SAVE_QUEUE,
                durable=True
            )
            logger.info("✅ 큐 선언 완료: {}", settings.BOOKMARK_SAVE_QUEUE)

            logger.info("🚀 북마크 저장 Consumer 시작 완료 - 큐: {}", settings.BOOKMARK_SAVE_QUEUE)

            # 메시지 소비 시작
            await queue.consume(on_bookmark_save)
            logger.info("🎯 북마크 저장 Consumer 대기 중: {}", settings.BOOKMARK_SAVE_QUEUE)

            # 테스트 환경에서는 즉시 반환, 실제 환경에서는 무한 대기
            if os.getenv("PYTEST_CURRENT_TEST"):
                # 테스트 환경: 즉시 반환
                logger.info("🧪 테스트 환경 감지 - Consumer 초기화만 수행")
                return

            # 실제 환경: Consumer 실행 유지
            try:
                await asyncio.Future()  # 무한 대기
            finally:
                # 정리 작업
                await _cleanup_consumer_connections(connection, channel)

        except AMQPException as e:
            logger.error("❌ RabbitMQ 연결 오류 (시도 {}/{}): {}", attempt + 1, max_retries, e)
            if attempt == max_retries - 1:
                logger.error("❌ 북마크 저장 Consumer 최대 재시도 횟수 초과 - 포기")
                raise
            logger.info("🔄 {}초 후 재시도...", retry_delay)
            await asyncio.sleep(retry_delay)
            
        except (ConnectionError, OSError) as e:
            logger.error("❌ 네트워크 연결 오류 (시도 {}/{}): {}", attempt + 1, max_retries, e)
            if attempt == max_retries - 1:
                logger.error("❌ 북마크 저장 Consumer 최대 재시도 횟수 초과 - 포기")
                raise
            logger.info("🔄 {}초 후 재시도...", retry_delay)
            await asyncio.sleep(retry_delay)
            
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("❌ Consumer 시작 중 예상하지 못한 오류 (시도 {}/{}): {}", attempt + 1, max_retries, e)
            if attempt == max_retries - 1:
                logger.error("❌ 북마크 저장 Consumer 최대 재시도 횟수 초과 - 포기")
                raise
            logger.info("🔄 {}초 후 재시도...", retry_delay)
            await asyncio.sleep(retry_delay)
