"""
데이터베이스 연결 설정 및 관리 모듈

이 모듈은 SQLModel을 사용하여 PostgreSQL 데이터베이스와 비동기적으로 연결하고,
데이터베이스 세션을 관리하는 기능을 제공합니다.

주요 기능:
- 비동기 엔진 생성
- 세션 팩토리 생성
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from sqlmodel import SQLModel
from loguru import logger
from .config import settings

# 비동기 엔진 생성
async_engine = create_async_engine(
    str(settings.ASYNC_DATABASE_URL),
    echo=settings.DEBUG,
    # 연결 풀 설정
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    # RDS 최적화 설정
    pool_pre_ping=True,  # 연결 상태 확인
    connect_args={
        "server_settings": {
            "jit": "off",  # JIT 비활성화 (RDS에서 권장)
        },
        "command_timeout": 60,
    },
)

# 세션 팩토리 생성
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 의존성 주입용 세션 제너레이터
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    비동기 데이터베이스 세션을 제공하는 의존성 주입 함수
    
    Yields:
        AsyncSession: SQLAlchemy 비동기 세션
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# 데이터베이스 초기화
async def init_db() -> None:
    """
    데이터베이스 테이블 생성
    개발 환경에서만 사용되며, 프로덕션에서는 Alembic 마이그레이션을 사용
    """
    try:
        async with async_engine.begin() as conn:
            # 모든 SQLModel 테이블 생성
            await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("✅ 데이터베이스 테이블 초기화 완료")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 테이블 초기화 실패: {e}")
        raise

# 연결 테스트
async def test_connection() -> bool:
    """
    데이터베이스 연결 테스트
    
    Returns:
        bool: 연결 성공 시 True, 실패 시 False
    """
    try:
        async with async_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(f"✅ PostgreSQL 연결 성공 - Host: {settings.POSTGRES_HOST}")
        return True
    except Exception as e:
        logger.error(f"❌ PostgreSQL 연결 실패: {e}")
        return False

# 데이터베이스 연결 종료
async def close_db() -> None:
    """데이터베이스 연결 종료"""
    try:
        await async_engine.dispose()
        logger.info("✅ 데이터베이스 연결 종료 완료")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 종료 실패: {e}") 