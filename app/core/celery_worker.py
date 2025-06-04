"""
Celery 작업 큐 관리 모듈

이 모듈은 비동기 태스크 처리를 위한 Celery 작업 큐 구성을 정의합니다.
RabbitMQ를 브로커로 사용하고 Redis를 결과 백엔드로 사용합니다.
"""
from celery import Celery
from loguru import logger
from app.core.config import settings
import logging

# Celery 인스턴스 생성 (브로커로 RabbitMQ, 백엔드로 Redis 사용)
celery = Celery(
    "nebula",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL
)

# 태스크 라우팅 구성 - 태스크를 해당 큐에 라우팅
celery.conf.task_routes = {
    # 북마크 저장 관련 태스크 (높은 우선순위, 실시간 처리)
    "tasks.save_bookmark": {"queue": "bookmark_save"},
    "tasks.save_bookmark.*": {"queue": "bookmark_save"},

    # 사용자 프로필 관련 태스크 (중간 우선순위, 배경 처리)
    "tasks.update_user_profile": {"queue": "user_profile"},
    
    # 사용자 분석 관련 태스크 (낮은 우선순위, CPU 집약적)
    "tasks.calculate_user_similarities": {"queue": "user_analysis"},
    
    # 추천 시스템 관련 태스크 (낮은 우선순위, 지연 가능)
    "tasks.generate_recommendations": {"queue": "recommendations"},
    
    # 트렌드 분석 관련 태스크 (최저 우선순위, 배치 처리)
    "tasks.analyze_trends": {"queue": "analytics"},

    # 일일 모니터링 관련 태스크 (스케줄 기반, 배경 작업)
    "tasks.run_daily_quality_check": {"queue": "monitoring"},
    "tasks.run_daily_.*": {"queue": "monitoring"},

    # 데이터 추출 NLP 관련 (현재는 RabbitMQ Consumer로 처리되지만 향후 Celery 전환 가능)
    # "tasks.extract_data_nlp": {"queue": "data_extraction"},
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

    # 큐별 우선순위 설정
    task_default_priority=5,
    worker_disable_rate_limits=False,
    
    # 큐별 라우팅 최적화
    task_always_eager=False,  # 프로덕션에서는 False
    task_eager_propagates=True,
    
    # 워커 프로세스 관리 - 이벤트 루프 문제 방지
    worker_max_tasks_per_child=1000,  # 1000개 태스크 후 워커 재시작
    worker_max_memory_per_child=200000,  # 200MB 메모리 제한
    
    # 비동기 태스크 처리 최적화
    task_reject_on_worker_lost=True,  # 워커 손실 시 태스크 거부
    task_ignore_result=False,  # 결과 추적 활성화
)

# 자동으로 태스크 모듈 검색(발견)
celery.autodiscover_tasks(['app.tasks'])

# 필요한 태스크 모듈 가져오기
try:
    # pylint: disable=unused-import,import-outside-toplevel
    from app.tasks import bookmark_save_task
    from app.tasks import user_profile_tasks
    from app.tasks import daily_profile_monitor
except ImportError as e:
    # 태스크 모듈이 아직 구현되지 않은 경우 무시
    logger.warning(f"일부 태스크 모듈을 로드할 수 없습니다: {e}")
    pass
