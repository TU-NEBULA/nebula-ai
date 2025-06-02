"""
PostgreSQL 데이터베이스 초기화 및 테이블 생성 스크립트

1. 데이터베이스 연결 확인
2. SQLModel 테이블 생성
3. 인덱스 생성
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import SQLModel
from loguru import logger

from app.core.database import engine
from app.core.config import settings

# 모든 모델 임포트 (테이블 생성을 위해)
from app.models.chat import (
    ChatSession, ChatMessage, RAGReference, UserFeedback,
    UserProfile
)


async def create_tables():
    """SQLModel 테이블들을 생성합니다."""
    logger.info("🏗️ PostgreSQL 테이블 생성 시작...")
    
    try:
        # 모든 테이블 생성
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        
        logger.info("✅ 테이블 생성 완료!")
        
        # 생성된 테이블 목록 확인
        async with engine.begin() as conn:
            result = await conn.execute(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
                """
            )
            tables = [row[0] for row in result.fetchall()]
            
            logger.info("📋 생성된 테이블 목록:")
            for table in tables:
                logger.info(f"   - {table}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 테이블 생성 실패: {e}")
        return False


async def create_indexes():
    """성능 향상을 위한 인덱스를 생성합니다."""
    logger.info("🔍 인덱스 생성 시작...")
    
    indexes = [
        # ChatSession 인덱스
        "CREATE INDEX IF NOT EXISTS idx_chat_session_user_id ON chat_sessions(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_chat_session_active ON chat_sessions(is_active) WHERE is_active = true;",
        "CREATE INDEX IF NOT EXISTS idx_chat_session_updated_at ON chat_sessions(updated_at);",
        
        # ChatMessage 인덱스
        "CREATE INDEX IF NOT EXISTS idx_chat_message_session_id ON chat_messages(session_id);",
        "CREATE INDEX IF NOT EXISTS idx_chat_message_user_id ON chat_messages(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_chat_message_created_at ON chat_messages(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_chat_message_role ON chat_messages(role);",
        
        # RAGReference 인덱스
        "CREATE INDEX IF NOT EXISTS idx_rag_reference_message_id ON rag_references(message_id);",
        "CREATE INDEX IF NOT EXISTS idx_rag_reference_source_type ON rag_references(source_type);",
        "CREATE INDEX IF NOT EXISTS idx_rag_reference_score ON rag_references(score);",
        
        # UserFeedback 인덱스
        "CREATE INDEX IF NOT EXISTS idx_user_feedback_message_id ON user_feedbacks(message_id);",
        "CREATE INDEX IF NOT EXISTS idx_user_feedback_user_id ON user_feedbacks(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_user_feedback_type ON user_feedbacks(feedback_type);",
        
        # 복합 인덱스
        "CREATE INDEX IF NOT EXISTS idx_chat_message_session_user ON chat_messages(session_id, user_id);",
        "CREATE INDEX IF NOT EXISTS idx_chat_session_user_type ON chat_sessions(user_id, session_type);",
    ]
    
    try:
        async with engine.begin() as conn:
            for index_sql in indexes:
                await conn.execute(index_sql)
                logger.debug(f"✅ 인덱스 생성: {index_sql.split('ON')[1].split('(')[0].strip()}")
        
        logger.info("✅ 모든 인덱스 생성 완료!")
        return True
        
    except Exception as e:
        logger.error(f"❌ 인덱스 생성 실패: {e}")
        return False


async def verify_database():
    """데이터베이스 구조를 확인합니다."""
    logger.info("🧪 데이터베이스 구조 확인...")
    
    try:
        async with engine.begin() as conn:
            # 테이블 수 확인
            result = await conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
            )
            table_count = result.fetchone()[0]
            
            # 인덱스 수 확인
            result = await conn.execute(
                """
                SELECT COUNT(*) FROM pg_indexes 
                WHERE schemaname = 'public' AND indexname NOT LIKE '%_pkey';
                """
            )
            index_count = result.fetchone()[0]
            
            logger.info(f"📊 데이터베이스 통계:")
            logger.info(f"   - 테이블 수: {table_count}")
            logger.info(f"   - 사용자 정의 인덱스 수: {index_count}")
            logger.info(f"   - 데이터베이스: {settings.POSTGRES_DB}")
            logger.info(f"   - 호스트: {settings.POSTGRES_HOST}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 데이터베이스 확인 실패: {e}")
        return False


async def main():
    """메인 실행 함수"""
    logger.info("🚀 PostgreSQL 데이터베이스 초기화 시작")
    logger.info("="*60)
    
    # 1. 테이블 생성
    if not await create_tables():
        sys.exit(1)
    
    logger.info("="*30)
    
    # 2. 인덱스 생성
    if not await create_indexes():
        sys.exit(1)
        
    logger.info("="*30)
    
    # 3. 검증
    if not await verify_database():
        sys.exit(1)
    
    logger.info("="*60)
    logger.info("🎉 데이터베이스 초기화 완료!")
    logger.info("📋 다음 단계:")
    logger.info("   1. python -m app.main  # 애플리케이션 실행")
    logger.info("   2. 채팅 API 테스트: POST /chat/stream")
    

if __name__ == "__main__":
    asyncio.run(main())
