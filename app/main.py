"""
Nebula AI 애플리케이션의 메인 진입점 모듈

이 모듈은 FastAPI 애플리케이션을 초기화하고 RabbitMQ 컨슈머를 시작하는 역할을 담당합니다.
애플리케이션 시작 시 NLTK 데이터를 확인하고, 필요한 경우 다운로드합니다.
또한 RabbitMQ 메시지를 비동기적으로 처리하기 위한 소비자 태스크를 생성하고 관리합니다.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.routers import init_routers
from app.core.database import init_db
from app.core.config import settings
from app.services.message_handlers import RabbitMQConsumer
from app.consumers.bookmark_save_rmq import start_bookmark_save_consumer
from app.consumers.extract_data_rmq import start_extract_consumer
from app.listeners.profile_update_listener import RealTimeProfileUpdateListener
from app.services.recommendation_feedback import RecommendationFeedbackService
from app.core.monitoring import setup_prometheus_metrics, start_system_metrics_collector

# 로그 설정
logger.add(
    "logs/nebula_ai.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

# 전역 서비스 인스턴스
RABBITMQ_CONSUMER = None
CONSUMER_TASKS = []  # 백그라운드 태스크 추적용
PROFILE_UPDATE_LISTENER = None
RECOMMENDATION_FEEDBACK_SERVICE = None
METRICS_COLLECTOR_TASK = None  # 메트릭 수집기 태스크


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):  # pylint: disable=unused-argument
    """애플리케이션 시작/종료 시 실행할 코드"""
    global RABBITMQ_CONSUMER, CONSUMER_TASKS, PROFILE_UPDATE_LISTENER, RECOMMENDATION_FEEDBACK_SERVICE, METRICS_COLLECTOR_TASK  # pylint: disable=global-statement
    
    # 시작 시
    await init_db()

    # 메트릭 수집기 시작
    try:
        METRICS_COLLECTOR_TASK = asyncio.create_task(start_system_metrics_collector())
        logger.info("📊 Prometheus 메트릭 수집기 시작 완료")
    except Exception as e:
        logger.error(f"메트릭 수집기 시작 실패: {e}")

    # Celery 스케줄러 설정 초기화
    try:
        from app.core.celery_worker import setup_all_schedules
        setup_all_schedules()
        logger.info("📅 Celery 스케줄러 설정 완료")
    except Exception as e:
        logger.error(f"Celery 스케줄러 설정 실패: {e}")

    # 실시간 프로파일 업데이트 리스너 시작
    try:
        PROFILE_UPDATE_LISTENER = RealTimeProfileUpdateListener()
        await PROFILE_UPDATE_LISTENER.start_processing()
        logger.info("🎯 실시간 프로파일 업데이트 리스너 시작 완료")
    except Exception as e:
        logger.error(f"프로파일 업데이트 리스너 시작 실패: {e}")
        PROFILE_UPDATE_LISTENER = None

    # 추천 피드백 서비스 백그라운드 처리 시작
    try:
        RECOMMENDATION_FEEDBACK_SERVICE = RecommendationFeedbackService()
        await RECOMMENDATION_FEEDBACK_SERVICE.start_background_processing()
        logger.info("📊 추천 피드백 서비스 백그라운드 처리 시작 완료")
    except Exception as e:
        logger.error(f"추천 피드백 서비스 시작 실패: {e}")
        RECOMMENDATION_FEEDBACK_SERVICE = None

    # RabbitMQ 컨슈머 설정 (환경변수에 RabbitMQ URL이 있는 경우에만)
    try:
        rabbitmq_url = settings.RABBITMQ_URL
        # 필수 환경변수가 설정되어 있는지 확인
        if (hasattr(settings, 'RABBITMQ_HOST') and settings.RABBITMQ_HOST and 
            hasattr(settings, 'RABBITMQ_USERNAME') and settings.RABBITMQ_USERNAME):
            
            RABBITMQ_CONSUMER = RabbitMQConsumer(rabbitmq_url)

            # 백그라운드에서 모든 컨슈머들 실행 (태스크 추적)
            task1 = asyncio.create_task(RABBITMQ_CONSUMER.setup_queues_and_consumers())
            task2 = asyncio.create_task(start_bookmark_save_consumer())
            task3 = asyncio.create_task(start_extract_consumer())
            
            CONSUMER_TASKS.extend([task1, task2, task3])
            logger.info("🚀 모든 RabbitMQ 컨슈머 설정 완료")
        else:
            logger.warning("RabbitMQ URL이 설정되지 않음 - MQ 기능 비활성화")
    except Exception as e:
        logger.error(f"RabbitMQ 설정 오류 - MQ 기능 비활성화: {e}")

    yield

    # 종료 시
    logger.info("애플리케이션 종료 시작")
    
    # 메트릭 수집기 정리
    if METRICS_COLLECTOR_TASK:
        try:
            METRICS_COLLECTOR_TASK.cancel()
            await METRICS_COLLECTOR_TASK
            logger.info("메트릭 수집기 정리 완료")
        except asyncio.CancelledError:
            logger.info("메트릭 수집기 취소 완료")
        except Exception as e:
            logger.error(f"메트릭 수집기 정리 실패: {e}")
    
    # 프로파일 업데이트 리스너 정리
    if PROFILE_UPDATE_LISTENER:
        try:
            await PROFILE_UPDATE_LISTENER.stop_processing()
            logger.info("프로파일 업데이트 리스너 정리 완료")
        except Exception as e:
            logger.error(f"프로파일 업데이트 리스너 정리 실패: {e}")
    
    # 추천 피드백 서비스 정리
    if RECOMMENDATION_FEEDBACK_SERVICE:
        try:
            await RECOMMENDATION_FEEDBACK_SERVICE.stop_background_processing()
            logger.info("추천 피드백 서비스 정리 완료")
        except Exception as e:
            logger.error(f"추천 피드백 서비스 정리 실패: {e}")
    
    # RabbitMQ 컨슈머 정리
    if RABBITMQ_CONSUMER:
        try:
            await RABBITMQ_CONSUMER.close_connection()
        except Exception as e:
            logger.error(f"RabbitMQ 연결 정리 실패: {e}")
    
    # 백그라운드 태스크들 정리
    if CONSUMER_TASKS:
        logger.info(f"백그라운드 태스크 {len(CONSUMER_TASKS)}개 정리 중...")
        for task in CONSUMER_TASKS:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug("태스크 취소 완료")
                except Exception as e:
                    logger.warning(f"태스크 정리 중 오류: {e}")
    
    logger.info("애플리케이션 종료 완료")


# FastAPI 애플리케이션 초기화
app = FastAPI(
    title="Nebula AI - User Profile API",
    description="Spring Boot 서버와 연동되는 사용자 프로필 관리 API",
    version="1.0.0",
    lifespan=lifespan
)

# Prometheus 메트릭 설정 적용
try:
    setup_prometheus_metrics(app)
    logger.info("🔍 Prometheus 메트릭 설정 완료")
except Exception as e:
    logger.error(f"Prometheus 메트릭 설정 실패: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포시에는 특정 도메인으로 제한
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
init_routers(app)


@app.get("/")
async def root():
    """루트 엔드포인트 - API 정보를 반환합니다."""
    return {
        "message": "Nebula AI - User Profile API",
        "version": "1.0.0",
        "endpoints": {
            "profiles": "/api/v1/profiles",
            "docs": "/docs",
            "health": "/health",
            "metrics": "/metrics"
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    global PROFILE_UPDATE_LISTENER, RECOMMENDATION_FEEDBACK_SERVICE, RABBITMQ_CONSUMER
    
    # 서비스 상태 확인
    profile_listener_status = "running" if (PROFILE_UPDATE_LISTENER and PROFILE_UPDATE_LISTENER.is_processing) else "stopped"
    feedback_service_status = "running" if (RECOMMENDATION_FEEDBACK_SERVICE and RECOMMENDATION_FEEDBACK_SERVICE.is_processing) else "stopped"
    rabbitmq_status = "connected" if RABBITMQ_CONSUMER else "disabled"
    metrics_status = "running" if (METRICS_COLLECTOR_TASK and not METRICS_COLLECTOR_TASK.done()) else "stopped"
    
    return {
        "status": "healthy",
        "services": {
            "database": "connected",
            "rabbitmq": rabbitmq_status,
            "profile_update_listener": profile_listener_status,
            "recommendation_feedback_service": feedback_service_status,
            "metrics_collector": metrics_status
        },
        "processing_stats": {
            "profile_events_processed": PROFILE_UPDATE_LISTENER.processed_events_count if PROFILE_UPDATE_LISTENER else 0,
            "feedback_queue_size": RECOMMENDATION_FEEDBACK_SERVICE.feedback_queue.qsize() if RECOMMENDATION_FEEDBACK_SERVICE else 0
        }
    }


@app.get("/metrics", include_in_schema=False)
async def get_metrics():
    """Prometheus 메트릭 엔드포인트 (테스트용)"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from fastapi import Response
    
    # 기본 메트릭 생성
    metrics_data = generate_latest()
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )


# 전역 서비스 접근을 위한 헬퍼 함수들
def get_profile_listener() -> RealTimeProfileUpdateListener:
    """프로파일 업데이트 리스너 인스턴스 반환"""
    return PROFILE_UPDATE_LISTENER


def get_feedback_service() -> RecommendationFeedbackService:
    """추천 피드백 서비스 인스턴스 반환"""
    return RECOMMENDATION_FEEDBACK_SERVICE
