"""
PostgreSQL 연결 테스트 및 기본 CRUD 작업 스크립트
"""
import asyncio
import sys
import os
from uuid import uuid4

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import test_connection, get_async_session, init_db
from app.core.config import settings
from app.models.chat import ChatSession, ChatMessage, ChatSessionCreate, ChatMessageCreate
from loguru import logger

async def test_basic_connection():
    """기본 연결 테스트"""
    logger.info("🔍 PostgreSQL 기본 연결 테스트")
    logger.info(f"🌍 환경: {settings.ENVIRONMENT}")
    logger.info(f"🗃️ DB 호스트: {settings.POSTGRES_HOST}")
    logger.info(f"🗃️ DB 이름: {settings.POSTGRES_DB}")
    
    if await test_connection():
        logger.info("✅ PostgreSQL 연결 성공!")
        return True
    else:
        logger.error("❌ PostgreSQL 연결 실패!")
        return False

async def test_table_creation():
    """테이블 생성 테스트"""
    logger.info("🏗️ 데이터베이스 테이블 생성 테스트")
    try:
        await init_db()
        logger.info("✅ 테이블 생성 성공!")
        return True
    except Exception as e:
        logger.error(f"❌ 테이블 생성 실패: {e}")
        return False

async def test_crud_operations():
    """기본 CRUD 작업 테스트"""
    logger.info("🧪 CRUD 작업 테스트 시작")
    
    try:
        async for session in get_async_session():
            # 1. CREATE - 채팅 세션 생성
            logger.info("📝 채팅 세션 생성 테스트")
            test_session = ChatSession(
                user_id="test_user_123",
                title="테스트 세션",
                session_type="test",
                primary_topic={"main": "테스트 주제"},
                referenced_bookmarks=["bookmark1", "bookmark2"]
            )
            
            session.add(test_session)
            await session.commit()
            await session.refresh(test_session)
            
            logger.info(f"✅ 채팅 세션 생성 성공 - ID: {test_session.id}")
            session_id = test_session.id
            
            # 2. CREATE - 채팅 메시지 생성
            logger.info("💬 채팅 메시지 생성 테스트")
            test_messages = [
                ChatMessage(
                    session_id=session_id,
                    user_id="test_user_123",
                    role="user",
                    content="안녕하세요, 테스트 메시지입니다.",
                    response_time_ms=100
                ),
                ChatMessage(
                    session_id=session_id,
                    user_id="test_user_123",
                    role="assistant",
                    content="안녕하세요! 도움이 필요하시면 말씀해 주세요.",
                    rag_metadata={
                        "search_query": "test query",
                        "retrieved_docs": ["doc1", "doc2"],
                        "similarity_scores": [0.9, 0.8]
                    },
                    response_time_ms=1500,
                    token_count=25
                )
            ]
            
            for msg in test_messages:
                session.add(msg)
            await session.commit()
            
            logger.info(f"✅ 채팅 메시지 {len(test_messages)}개 생성 성공")
            
            # 3. READ - 데이터 조회
            logger.info("📖 데이터 조회 테스트")
            
            # 세션 조회 (SQLModel 스타일)
            from sqlmodel import select
            stmt = select(ChatSession).where(ChatSession.user_id == "test_user_123")
            result = await session.execute(stmt)
            sessions = result.scalars().all()
            logger.info(f"✅ 조회된 세션 수: {len(sessions)}")
            
            # 메시지 조회 (JSONB 인덱스 테스트)
            stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            logger.info(f"✅ 조회된 메시지 수: {len(messages)}")
            
            # JSONB 쿼리 테스트
            from sqlalchemy import text
            jsonb_result = await session.execute(
                text("SELECT count(*) FROM chat_messages WHERE rag_metadata ? 'search_query'")
            )
            jsonb_count = jsonb_result.scalar()
            logger.info(f"✅ JSONB 쿼리 테스트 - RAG 메타데이터가 있는 메시지: {jsonb_count}개")
            
            # 4. UPDATE - 데이터 수정
            logger.info("✏️ 데이터 수정 테스트")
            test_session.title = "수정된 테스트 세션"
            test_session.total_messages = len(test_messages)
            session.add(test_session)
            await session.commit()
            logger.info("✅ 세션 제목 및 메시지 수 수정 성공")
            
            # 5. DELETE - 데이터 삭제
            logger.info("🗑️ 데이터 삭제 테스트")
            
            # 메시지 먼저 삭제 (외래키 제약)
            for msg in messages:
                await session.delete(msg)
            
            # 세션 삭제
            await session.delete(test_session)
            await session.commit()
            
            logger.info("✅ 테스트 데이터 삭제 완료")
            break
            
        return True
        
    except Exception as e:
        logger.error(f"❌ CRUD 작업 실패: {e}")
        import traceback
        logger.error(f"📋 상세 오류: {traceback.format_exc()}")
        return False

async def test_index_performance():
    """인덱스 성능 테스트"""
    logger.info("⚡ 인덱스 성능 테스트")
    
    try:
        async for session in get_async_session():
            from sqlalchemy import text
            import time
            
            # 인덱스 정보 조회
            indexes_result = await session.execute(
                text("""
                    SELECT schemaname, tablename, indexname, indexdef 
                    FROM pg_indexes 
                    WHERE tablename IN ('chat_sessions', 'chat_messages')
                    ORDER BY tablename, indexname
                """)
            )
            
            logger.info("📊 생성된 인덱스 목록:")
            for row in indexes_result:
                logger.info(f"  - {row.tablename}.{row.indexname}")
            
            break
            
        return True
        
    except Exception as e:
        logger.error(f"❌ 인덱스 테스트 실패: {e}")
        return False

async def main():
    """메인 테스트 실행"""
    logger.info("🚀 PostgreSQL 통합 테스트 시작")
    
    test_results = []
    
    # 1. 기본 연결 테스트
    test_results.append(("기본 연결", await test_basic_connection()))
    
    # 2. 테이블 생성 테스트
    test_results.append(("테이블 생성", await test_table_creation()))
    
    # 3. CRUD 작업 테스트
    test_results.append(("CRUD 작업", await test_crud_operations()))
    
    # 4. 인덱스 성능 테스트
    test_results.append(("인덱스 성능", await test_index_performance()))
    
    # 결과 요약
    logger.info("\n" + "="*50)
    logger.info("📋 테스트 결과 요약")
    logger.info("="*50)
    
    all_passed = True
    for test_name, result in test_results:
        status = "✅ 성공" if result else "❌ 실패"
        logger.info(f"{test_name:<15}: {status}")
        if not result:
            all_passed = False
    
    logger.info("="*50)
    if all_passed:
        logger.info("🎉 모든 테스트 통과! PostgreSQL 설정이 완료되었습니다.")
    else:
        logger.error("💥 일부 테스트 실패! 설정을 확인해 주세요.")
    
    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 