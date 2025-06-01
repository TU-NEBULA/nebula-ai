"""
PostgreSQL에 nebula_ai_dev 데이터베이스를 생성하는 스크립트
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from app.core.config import settings
from loguru import logger

async def create_database():
    """PostgreSQL 서버에 연결하여 데이터베이스 생성"""
    
    # 기본 postgres 데이터베이스에 연결 (항상 존재)
    logger.info("🔍 PostgreSQL 서버 연결 중...")
    logger.info(f"🌍 호스트: {settings.POSTGRES_HOST}")
    logger.info(f"👤 사용자: {settings.POSTGRES_USER}")
    
    try:
        # postgres 데이터베이스에 연결 (관리용)
        conn = await asyncpg.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database="postgres",  # 기본 데이터베이스
            ssl=settings.DB_SSL_MODE
        )
        
        logger.info("✅ PostgreSQL 서버 연결 성공!")
        
        # 데이터베이스 존재 여부 확인
        logger.info(f"🔍 '{settings.POSTGRES_DB}' 데이터베이스 존재 여부 확인...")
        
        existing_db = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            settings.POSTGRES_DB
        )
        
        if existing_db:
            logger.info(f"✅ 데이터베이스 '{settings.POSTGRES_DB}'가 이미 존재합니다!")
        else:
            # 데이터베이스 생성
            logger.info(f"🏗️ 데이터베이스 '{settings.POSTGRES_DB}' 생성 중...")
            
            await conn.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}"')
            logger.info(f"✅ 데이터베이스 '{settings.POSTGRES_DB}' 생성 완료!")
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 데이터베이스 생성 실패: {e}")
        return False

async def verify_database():
    """생성된 데이터베이스에 연결 테스트"""
    logger.info(f"🧪 데이터베이스 '{settings.POSTGRES_DB}' 연결 테스트...")
    
    try:
        conn = await asyncpg.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            ssl=settings.DB_SSL_MODE
        )
        
        # 간단한 쿼리 실행
        version = await conn.fetchval("SELECT version()")
        logger.info(f"✅ 데이터베이스 연결 성공!")
        logger.info(f"📊 PostgreSQL 버전: {version.split(',')[0]}")
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        return False

async def main():
    """메인 실행 함수"""
    logger.info("🚀 PostgreSQL 데이터베이스 생성 프로세스 시작")
    logger.info("="*60)
    
    # 1. 데이터베이스 생성
    create_success = await create_database()
    
    if create_success:
        logger.info("="*60)
        # 2. 연결 테스트
        verify_success = await verify_database()
        
        if verify_success:
            logger.info("="*60)
            logger.info("🎉 모든 작업 완료! 이제 애플리케이션을 실행할 수 있습니다.")
            logger.info("📋 다음 단계:")
            logger.info("   1. python scripts/test_db_connection.py  # 전체 테스트")
            logger.info("   2. python -m app.main  # 애플리케이션 실행")
            return True
    
    logger.error("💥 데이터베이스 설정 실패!")
    return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 