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
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel
from loguru import logger
from app.core.config import settings

# 비동기 엔진 생성
async_engine = create_async_engine(
    str(settings.ASYNC_DATABASE_URL),
    echo=False,  # SQLAlchemy 자세한 로그 비활성화 (필요시에만 True)
    # 연결 풀 설정
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    # RDS 최적화 설정
    pool_pre_ping=True,  # 연결 상태 확인
    # Celery 워커 환경에서 안전한 연결 종료를 위한 설정
    pool_reset_on_return='commit',  # 연결 반환 시 트랜잭션 정리
    connect_args={
        "server_settings": {
            "jit": "off",  # JIT 비활성화 (RDS에서 권장)
        },
        "command_timeout": 60,
        # asyncpg 관련 설정 - 연결 종료 시 이벤트 루프 문제 방지
        "loop": None,  # 외부 이벤트 루프 사용하지 않음
    },
)

# 별칭 (다른 모듈에서 engine으로 접근 가능)
engine = async_engine

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
        except SQLAlchemyError:
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
            # 각 테이블을 개별적으로 생성하여 중복 오류 방지
            from sqlmodel import SQLModel
            from sqlalchemy import DDL
            from sqlalchemy.exc import ProgrammingError
            
            # 모든 테이블 생성 시도
            try:
                await conn.run_sync(SQLModel.metadata.create_all)
                logger.info("✅ 데이터베이스 테이블 초기화 완료")
            except ProgrammingError as pe:
                # 인덱스나 테이블이 이미 존재하는 경우 처리
                if "already exists" in str(pe):
                    logger.warning(f"⚠️ 일부 데이터베이스 객체가 이미 존재함: {pe}")
                    # 테이블만 생성하고 인덱스는 별도 처리
                    try:
                        # 테이블만 생성 (인덱스 제외)
                        await conn.run_sync(_create_tables_only)
                        logger.info("✅ 데이터베이스 테이블 생성 완료 (인덱스 제외)")
                    except Exception as table_error:
                        logger.warning(f"⚠️ 테이블 생성 중 일부 오류 (무시 가능): {table_error}")
                else:
                    raise pe
                    
    except SQLAlchemyError as e:
        logger.error(f"❌ 데이터베이스 테이블 초기화 실패: {e}")
        raise

def _create_tables_only(bind):
    """테이블만 생성하고 인덱스는 제외"""
    from sqlmodel import SQLModel
    from sqlalchemy.schema import CreateTable
    
    for table in SQLModel.metadata.tables.values():
        try:
            bind.execute(CreateTable(table, if_not_exists=True))
        except Exception as e:
            # 이미 존재하는 테이블은 무시
            if "already exists" not in str(e):
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
    except SQLAlchemyError as e:
        logger.error(f"❌ PostgreSQL 연결 실패: {e}")
        return False

# 데이터베이스 연결 종료
async def close_db() -> None:
    """데이터베이스 연결 종료"""
    try:
        await async_engine.dispose()
        logger.info("✅ 데이터베이스 연결 종료 완료")
    except SQLAlchemyError as e:
        logger.error(f"❌ 데이터베이스 연결 종료 실패: {e}")
