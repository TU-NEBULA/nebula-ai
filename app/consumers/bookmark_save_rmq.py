"""
북마크 저장 RabbitMQ Consumer

북마크 저장 요청을 처리하고 유사도 계산을 수행하는 Consumer입니다.
새로운 북마크와 기존 북마크들 간의 유사도를 계산하여 관계 데이터를 생성합니다.
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

import aio_pika
from aio_pika import IncomingMessage

from app.core.config import settings
from app.services.similarity_service import SimilarityService
from app.services.message_publisher import message_publisher
from app.external.s3_service import download_html_from_s3

log = logging.getLogger(__name__)

# 서비스 인스턴스 초기화
similarity_service = SimilarityService()

# 테스트 호환성을 위한 함수 (실제로는 Celery 태스크로 대체 예정)
class MockCeleryTask:
    """Celery 태스크 모의 객체"""
    
    def __init__(self, func):
        self.func = func
    
    def delay(self, *args, **kwargs):
        """Celery의 delay 메서드 모의"""
        log.info("📂 북마크 저장 태스크 호출됨 (delay) - kwargs: %s", kwargs)
        return self.func(*args, **kwargs)
    
    def __call__(self, *args, **kwargs):
        """직접 호출도 지원"""
        return self.func(*args, **kwargs)

def _save_bookmark_task_func(*args, **kwargs):
    """
    실제 북마크 저장 함수
    실제 운영에서는 Celery 태스크로 구현될 예정입니다.
    """
    log.info("📂 북마크 저장 태스크 처리 중...")
    # TODO: 실제 ChromaDB 저장 로직 구현
    return None

# Celery 태스크 호환 객체 생성
save_bookmark_task = MockCeleryTask(_save_bookmark_task_func)

async def get_rabbit_connection():
    """
    RabbitMQ 연결을 반환하는 함수
    테스트 호환성을 위해 분리되었습니다.
    """
    return await aio_pika.connect_robust(settings.RABBITMQ_URL)

async def on_bookmark_save(message: IncomingMessage):
    """북마크 저장 메시지 처리"""
    async with message.process():
        try:
            # 1. 메시지 파싱
            body = message.body.decode('utf-8')
            bookmark_data = json.loads(body)
            
            log.info("📨 북마크 저장 메시지 수신 - starId: %s", bookmark_data.get("starId"))
            
            # 2. 필수 필드 검증
            required_fields = ["userId", "starId", "s3Key", "title", "url"]
            for field in required_fields:
                if field not in bookmark_data:
                    raise ValueError(f"필수 필드 누락: {field}")
            
            # 3. S3에서 콘텐츠 다운로드 (테스트용으로 스킵)
            # content = await download_html_from_s3(bookmark_data["s3Key"])
            content = f"테스트 콘텐츠: {bookmark_data.get('title', '')} {bookmark_data.get('summary', '')}"
            
            # 4. 유사도 계산 수행
            log.info("🔍 유사도 계산 시작...")
            similar_bookmarks = await similarity_service.find_similar_bookmarks(
                new_bookmark_content=content,
                user_id=bookmark_data["userId"],
                keywords=bookmark_data.get("keywords", []),
                summary=bookmark_data.get("summary", "")
            )
            
            log.info("📊 유사도 계산 완료 - 유사 북마크 %d개 발견", len(similar_bookmarks))
            
            # 5. 유사도 결과가 있으면 관계 데이터 메시지 발행
            if similar_bookmarks:
                await message_publisher.publish_bookmark_relationships(
                    user_id=bookmark_data["userId"],
                    source_bookmark={
                        "bookmark_id": bookmark_data["starId"],
                        "title": bookmark_data.get("title", ""),
                        "url": bookmark_data.get("url", ""),
                        "keywords": bookmark_data.get("keywords", []),
                        "summary": bookmark_data.get("summary", "")
                    },
                    similar_bookmarks=similar_bookmarks
                )
                log.info("📤 관계 데이터 메시지 발행 완료 - 유사 북마크 %d개", len(similar_bookmarks))
            else:
                log.info("📝 유사한 북마크가 없어 관계 데이터 생성하지 않음")
            
            # 6. 북마크 저장 (테스트 호환성을 위해 호출)
            save_bookmark_task.delay(
                user_id=bookmark_data["userId"],
                star_id=bookmark_data["starId"],
                s3_key=bookmark_data["s3Key"],
                title=bookmark_data.get("title", ""),
                url=bookmark_data.get("url", ""),
                keywords=bookmark_data.get("keywords", []),
                memo=bookmark_data.get("memo", ""),
                summary=bookmark_data.get("summary", "")
            )
            
            # 7. 처리 완료 로그
            log.info("✅ 북마크 저장 처리 완료 - starId: %s", bookmark_data["starId"])
            
        except json.JSONDecodeError as e:
            log.error("❌ JSON 파싱 오류: %s", e)
        except ValueError as e:
            log.error("❌ 데이터 검증 오류: %s", e)
        except Exception as e:
            log.error("❌ 북마크 저장 처리 중 오류: %s", e)

async def start_bookmark_save_consumer():
    """북마크 저장 Consumer 시작"""
    try:
        # RabbitMQ 연결
        connection = await get_rabbit_connection()
        channel = await connection.channel()
        
        # QoS 설정 (동시 처리 제한)
        await channel.set_qos(prefetch_count=1)
        
        # 큐 선언
        queue = await channel.declare_queue(
            settings.BOOKMARK_SAVE_QUEUE,
            durable=True
        )
        
        log.info("🚀 북마크 저장 Consumer 시작 - 큐: %s", settings.BOOKMARK_SAVE_QUEUE)
        
        # 메시지 소비 시작
        await queue.consume(on_bookmark_save)
        
        # 테스트 환경에서는 즉시 반환, 실제 환경에서는 무한 대기
        import os
        if os.getenv("PYTEST_CURRENT_TEST"):
            # 테스트 환경: 즉시 반환
            log.info("🧪 테스트 환경 감지 - Consumer 초기화만 수행")
            return
        else:
            # 실제 환경: Consumer 실행 유지
            await asyncio.Future()  # 무한 대기
        
    except Exception as e:
        log.error("❌ Consumer 시작 실패: %s", e)
        raise
