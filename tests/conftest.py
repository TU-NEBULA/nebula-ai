import pytest
import asyncio
import tempfile
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app


# 테스트용 임시 파일 기반 SQLite 데이터베이스
_test_db_file = None
_test_engine = None
_test_session_maker = None


def get_test_database_url():
    """테스트용 데이터베이스 URL 생성"""
    global _test_db_file
    if _test_db_file is None:
        _test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        _test_db_file.close()
    return f"sqlite+aiosqlite:///{_test_db_file.name}"


@pytest.fixture(scope="session")
def event_loop():
    """이벤트 루프 설정"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """테스트용 비동기 엔진 생성"""
    global _test_engine, _test_session_maker
    
    # SQLite에서 JSONB 타입을 TEXT로 처리하도록 설정
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
    from sqlalchemy.dialects.postgresql import JSONB
    
    # SQLite 컴파일러에 JSONB 처리 추가
    def visit_JSONB(self, type_, **kw):
        return "TEXT"
    
    SQLiteTypeCompiler.visit_JSONB = visit_JSONB
    
    # 임시 파일 기반 데이터베이스 사용
    test_db_url = get_test_database_url()
    _test_engine = create_async_engine(
        test_db_url,
        echo=False,
        future=True
    )
    
    # 테이블 생성
    async with _test_engine.begin() as conn:
        from app.models.chat import ChatSession
        await conn.run_sync(ChatSession.metadata.create_all)
    
    # 세션 메이커 생성
    _test_session_maker = sessionmaker(
        _test_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    yield _test_engine
    
    # 테스트 완료 후 정리
    await _test_engine.dispose()
    
    # 임시 데이터베이스 파일 삭제
    global _test_db_file
    if _test_db_file and os.path.exists(_test_db_file.name):
        os.unlink(_test_db_file.name)
    
    _test_engine = None
    _test_session_maker = None
    _test_db_file = None


@pytest.fixture
async def async_session(test_engine):
    """테스트용 비동기 세션 생성"""
    global _test_session_maker
    
    async with _test_session_maker() as session:
        yield session
        await session.rollback()


# 테스트용 데이터베이스 세션 의존성 override
async def get_test_session():
    """테스트용 데이터베이스 세션 생성"""
    global _test_engine, _test_session_maker
    
    # 이미 초기화된 엔진과 세션 메이커가 있으면 재사용
    if _test_engine is None or _test_session_maker is None:
        # SQLite에서 JSONB 타입을 TEXT로 처리하도록 설정
        from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
        from sqlalchemy.dialects.postgresql import JSONB
        
        def visit_JSONB(self, type_, **kw):
            return "TEXT"
        
        SQLiteTypeCompiler.visit_JSONB = visit_JSONB
        
        # 임시 파일 기반 데이터베이스 사용
        test_db_url = get_test_database_url()
        _test_engine = create_async_engine(
            test_db_url,
            echo=False,
            future=True
        )
        
        # 테이블 생성
        async with _test_engine.begin() as conn:
            from app.models.chat import ChatSession
            await conn.run_sync(ChatSession.metadata.create_all)
        
        _test_session_maker = sessionmaker(
            _test_engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
    
    async with _test_session_maker() as session:
        try:
            yield session
            await session.commit()  # 테스트 데이터가 유지되도록 커밋
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture
async def async_client():
    """비동기 HTTP 클라이언트 생성"""
    # 실제 데이터베이스 의존성을 테스트용으로 override
    from app.core.database import get_async_session
    
    app.dependency_overrides[get_async_session] = get_test_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    # 테스트 완료 후 override 정리
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def test_client():
    """FastAPI 테스트 클라이언트 생성"""
    with TestClient(app) as client:
        yield client


# 테스트 데이터 fixtures
@pytest.fixture
def sample_user_id():
    """샘플 사용자 ID"""
    return 12345


@pytest.fixture
def sample_session_data():
    """샘플 세션 데이터"""
    return {
        "user_id": "12345",
        "title": "테스트 세션",
        "session_type": "general"
    }


@pytest.fixture
def sample_message_data():
    """샘플 메시지 데이터"""
    return {
        "content": "안녕하세요! 테스트 메시지입니다.",
        "role": "user"
    }


@pytest.fixture
def sample_rag_references():
    """샘플 RAG 참조 데이터"""
    return [
        {
            "snippet": "첫 번째 참조 문서 내용",
            "title": "문서 1",
            "url": "https://example.com/doc1",
            "source_id": "doc_1",
            "score": 0.95
        },
        {
            "snippet": "두 번째 참조 문서 내용",
            "title": "문서 2", 
            "url": "https://example.com/doc2",
            "source_id": "doc_2",
            "score": 0.87
        }
    ]


@pytest.fixture
def sample_chat_request():
    """샘플 채팅 요청 데이터"""
    return {
        "user_id": 123,
        "message": "안녕하세요! 도움이 필요합니다."
    }
