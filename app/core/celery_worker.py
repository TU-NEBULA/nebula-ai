"""
Celery 작업 큐 관리 모듈

이 모듈은 비동기 태스크 처리를 위한 Celery 작업 큐 구성을 정의합니다.
RabbitMQ를 브로커로 사용하고 Redis를 결과 백엔드로 사용합니다.
"""
from celery import Celery
from app.core.config import settings

# Celery 인스턴스 생성 (브로커로 RabbitMQ, 백엔드로 Redis 사용)
celery = Celery(
    "nebula",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL
)

# 태스크 라우팅 구성 - 태스크를 해당 큐에 라우팅
celery.conf.task_routes = {
    "tasks.save_bookmark.*": {"queue": "bookmark_save"},  # 북마크 저장 태스크는 bookmark_save 큐로 전송
}

# 자동으로 태스크 모듈 검색(발견)
celery.autodiscover_tasks(['app.tasks'])
# 필요한 태스크 모듈 가져오기
from app.tasks import bookmark_save_task # pylint: disable=unused-import
