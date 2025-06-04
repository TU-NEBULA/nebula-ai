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
    # 북마크 관련 태스크
    "tasks.save_bookmark.*": {"queue": "bookmark_save"},

    # 사용자 프로필 관련 태스크
    "tasks.update_user_profile": {"queue": "user_profile"},
    "tasks.calculate_user_similarities": {"queue": "user_analysis"},
    "tasks.generate_recommendations": {"queue": "recommendations"},
    "tasks.analyze_trends": {"queue": "analytics"},
}

# Celery 설정 옵션
celery.conf.update(
    # 태스크 결과 만료 시간 (24시간)
    result_expires=86400,

    # 워커 설정
    worker_prefetch_multiplier=1,  # 한 번에 하나의 태스크만 처리
    task_acks_late=True,  # 태스크 완료 후 ACK

    # 직렬화 설정
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # 시간대 설정
    timezone='UTC',
    enable_utc=True,
)

# 자동으로 태스크 모듈 검색(발견)
celery.autodiscover_tasks(['app.tasks'])

# 필요한 태스크 모듈 가져오기
try:
    # pylint: disable=unused-import,import-outside-toplevel
    from app.tasks import bookmark_save_task
    from app.tasks import user_profile_tasks
except ImportError:
    # 태스크 모듈이 아직 구현되지 않은 경우 무시
    pass
