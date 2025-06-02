"""
Nebula AI 애플리케이션의 메인 진입점 모듈

이 모듈은 FastAPI 애플리케이션을 초기화하고 RabbitMQ 컨슈머를 시작하는 역할을 담당합니다.
애플리케이션 시작 시 NLTK 데이터를 확인하고, 필요한 경우 다운로드합니다.
또한 RabbitMQ 메시지를 비동기적으로 처리하기 위한 소비자 태스크를 생성하고 관리합니다.
"""

import asyncio

import nltk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.routers import init_routers
from app.core.database import test_connection, init_db, close_db
from app.core.config import settings

# 로그 설정
logger.add(
    "logs/nebula_ai.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

async def lifespan(_app: FastAPI):
    """
    FastAPI 애플리케이션의 수명 주기를 관리하는 함수

    애플리케이션이 시작될 때 필요한 리소스(NLTK 데이터, RabbitMQ 컨슈머, PostgreSQL)를 초기화하고,
    종료될 때 리소스를 정리합니다.

    Args:
        _app (FastAPI): FastAPI 애플리케이션 인스턴스

    Yields:
        None: FastAPI 애플리케이션이 실행되는 동안 yield를 통해 제어를 반환합니다.
    """
    logger.info("🚀 Nebula AI 애플리케이션 시작")
    logger.info("🌍 환경: {}", settings.ENVIRONMENT)

    # PostgreSQL 연결 테스트
    logger.info("🗃️ PostgreSQL 연결 테스트 중...")
    if await test_connection():
        logger.info("✅ PostgreSQL 연결 성공")

        # 개발 환경에서만 테이블 자동 생성
        if settings.ENVIRONMENT == "development":
            await init_db()
            logger.info("✅ 데이터베이스 테이블 초기화 완료")
    else:
        logger.error("❌ PostgreSQL 연결 실패 - 애플리케이션을 계속 실행합니다")

    # NLTK 데이터 확인 및 다운로드
    try:
        logger.info("📚 NLTK 데이터 확인 중...")
        nltk.data.find("tokenizers/punkt_tab")
        logger.info("✅ NLTK 데이터 확인 완료")
    except LookupError:
        logger.info("📥 NLTK 데이터 다운로드 중...")
        nltk.download("punkt_tab")
        logger.info("✅ NLTK 데이터 다운로드 완료")

    # 컨슈머 태스크 목록 초기화
    consumer_tasks = []

    try:
        logger.info("🔄 직접 스트리밍 모드로 시작 중...")
        logger.info("📝 RabbitMQ Consumer는 비활성화되었습니다")
        logger.info("✅ POST /chat/stream 엔드포인트를 사용하세요")

        logger.info("🎯 직접 스트리밍 모드로 실행 중")

        yield

    except Exception as e:
        logger.error("❌ 애플리케이션 시작 중 오류 발생: {}", e)
        raise
    finally:
        logger.info("🛑 애플리케이션 종료 중...")

        # PostgreSQL 연결 종료
        await close_db()

        # 모든 컨슈머 태스크 취소
        for task in consumer_tasks:
            if not task.done():
                logger.info("⏹️ 태스크 취소 중: {}", task.get_name())
                task.cancel()

        # 취소된 태스크들이 완료될 때까지 대기
        if consumer_tasks:
            logger.info("⏳ 태스크 종료 대기 중...")
            await asyncio.gather(*consumer_tasks, return_exceptions=True)

        logger.info("✅ 애플리케이션 종료 완료")


# FastAPI 애플리케이션 초기화
app = FastAPI(
    title="Nebula AI",
    description="NLP 기반 북마크 메모 서비스 인공지능 서버",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_routers(app)

@app.get("/", tags=["Health"])
async def root():
    """
    루트 엔드포인트 - 서버 상태 확인

    Returns:
        dict: 서버 상태 메시지
    """
    logger.info("🏠 루트 엔드포인트 호출")
    postgres_host = getattr(settings, 'POSTGRES_HOST', "Not configured")
    return {
        "message": "Nebula AI Server",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "postgres_host": postgres_host
    }
