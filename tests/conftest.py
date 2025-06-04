import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.core.config import settings
from app.models.base import Base


# 테스트용 인메모리 SQLite 데이터베이스
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """이벤트 루프 설정"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """테스트용 비동기 엔진 생성 - 실제 모델 구조와 일치"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
        pool_pre_ping=True,
        pool_recycle=300,  # 5분으로 단축
    )
    
    # 실제 모델 구조와 일치하는 테이블 생성
    async with engine.begin() as conn:
        # chat_sessions 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id VARCHAR(36) PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR(500),
                session_type VARCHAR(50) DEFAULT 'general',
                is_active BOOLEAN DEFAULT 1,
                primary_topic TEXT,  -- JSONB 대신 TEXT 사용
                referenced_bookmarks TEXT,  -- JSONB 대신 TEXT 사용
                total_messages INTEGER DEFAULT 0,
                avg_response_time_ms INTEGER,
                last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        
        # chat_messages 테이블 - 실제 모델과 일치하도록 수정
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id VARCHAR(36) PRIMARY KEY,
                session_id VARCHAR(36) NOT NULL,
                user_id INTEGER NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                rag_metadata TEXT,  -- JSONB 대신 TEXT 사용
                response_time_ms INTEGER,
                token_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions (id)
            )
        """))
        
        # user_ai_profiles 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_ai_profiles (
                user_id VARCHAR(255) PRIMARY KEY,
                preferred_search_domains TEXT,
                ai_interaction_style VARCHAR(100),
                current_interests TEXT,
                learning_preferences TEXT,
                notification_settings TEXT,
                profile_vector TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        
        # user_feedback 테이블 (필요시)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_feedback (
                id VARCHAR(36) PRIMARY KEY,
                message_id VARCHAR(36) NOT NULL,
                user_id INTEGER NOT NULL,
                feedback_type VARCHAR(50) NOT NULL,
                feedback_score INTEGER NOT NULL,
                feedback_detail TEXT,  -- JSONB 대신 TEXT 사용
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES chat_messages (id)
            )
        """))
        
        # rag_references 테이블 (필요시)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_references (
                id VARCHAR(36) PRIMARY KEY,
                message_id VARCHAR(36) NOT NULL,
                source_type VARCHAR(50) NOT NULL,
                source_id VARCHAR(255) NOT NULL,
                title VARCHAR(500),
                url VARCHAR(2000),
                snippet TEXT,
                score REAL DEFAULT 0.0,
                rank INTEGER DEFAULT 0,
                extra_metadata TEXT,  -- JSONB 대신 TEXT 사용
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES chat_messages (id)
            )
        """))
    
    try:
        yield engine
    finally:
        # 안전한 엔진 종료
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """비동기 데이터베이스 세션 fixture - Event loop 안전 관리"""
    Session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with Session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture
def client():
    """동기 FastAPI 테스트 클라이언트"""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """비동기 HTTPx 클라이언트"""
    
    # 테스트용 엔진과 세션 생성
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
        pool_pre_ping=True,
        pool_recycle=300,
    )
    
    # 테스트용 테이블 생성
    async with test_engine.begin() as conn:
        # chat_sessions 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id VARCHAR(36) PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR(500),
                session_type VARCHAR(50) DEFAULT 'general',
                is_active BOOLEAN DEFAULT 1,
                primary_topic TEXT,  -- JSONB 대신 TEXT 사용
                referenced_bookmarks TEXT,  -- JSONB 대신 TEXT 사용
                total_messages INTEGER DEFAULT 0,
                avg_response_time_ms INTEGER,
                last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        
        # chat_messages 테이블 - 실제 모델과 일치하도록 수정
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id VARCHAR(36) PRIMARY KEY,
                session_id VARCHAR(36) NOT NULL,
                user_id INTEGER NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                rag_metadata TEXT,  -- JSONB 대신 TEXT 사용
                response_time_ms INTEGER,
                token_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions (id)
            )
        """))
        
        # user_ai_profiles 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_ai_profiles (
                user_id VARCHAR(255) PRIMARY KEY,
                preferred_search_domains TEXT,
                ai_interaction_style VARCHAR(100),
                current_interests TEXT,
                learning_preferences TEXT,
                notification_settings TEXT,
                profile_vector TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        
        # user_feedback 테이블 (필요시)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_feedback (
                id VARCHAR(36) PRIMARY KEY,
                message_id VARCHAR(36) NOT NULL,
                user_id INTEGER NOT NULL,
                feedback_type VARCHAR(50) NOT NULL,
                feedback_score INTEGER NOT NULL,
                feedback_detail TEXT,  -- JSONB 대신 TEXT 사용
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES chat_messages (id)
            )
        """))
        
        # rag_references 테이블 (필요시)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rag_references (
                id VARCHAR(36) PRIMARY KEY,
                message_id VARCHAR(36) NOT NULL,
                source_type VARCHAR(50) NOT NULL,
                source_id VARCHAR(255) NOT NULL,
                title VARCHAR(500),
                url VARCHAR(2000),
                snippet TEXT,
                score REAL DEFAULT 0.0,
                rank INTEGER DEFAULT 0,
                extra_metadata TEXT,  -- JSONB 대신 TEXT 사용
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES chat_messages (id)
            )
        """))
    
    # 테스트용 세션 팩토리
    TestSessionLocal = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # 의존성 오버라이드 함수
    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
    
    # FastAPI 의존성 오버라이드
    from app.core.database import get_async_session
    app.dependency_overrides[get_async_session] = get_test_session
    
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            yield client
    finally:
        # 의존성 오버라이드 정리
        app.dependency_overrides.clear()
        await test_engine.dispose()


# SQLModel 관련 fixtures
@pytest.fixture
def sample_user_data():
    """샘플 사용자 데이터"""
    return {
        "user_id": 123,
        "profile_vector": [0.1, 0.8, 0.3, 0.5, 0.9],
        "keywords_frequency": {
            "AI": 15,
            "machine learning": 12,
            "python": 8
        },
        "categories_distribution": {
            "Technology": 0.7,
            "Science": 0.3
        },
        "activity_patterns": {
            "daily_sessions": 3.5,
            "avg_session_duration": 45
        },
        "preferences": {
            "topics": ["AI", "ML", "Data Science"],
            "difficulty": "intermediate"
        },
        "completeness_score": 78,
        "vector_strength": 0.85,
        "last_updated": "2023-10-01T10:00:00Z"
    }


@pytest.fixture
def sample_chat_session():
    """샘플 채팅 세션 데이터"""
    return {
        "user_id": 123,
        "title": "테스트 채팅 세션",
        "session_type": "general",
        "is_active": True,
        "total_messages": 0
    }


@pytest.fixture
def sample_chat_message():
    """샘플 채팅 메시지 데이터"""
    return {
        "content": "안녕하세요, 도움이 필요합니다!",
        "role": "user",
        "user_id": 123
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


# Vector Generator 관련 fixtures
@pytest.fixture
def mock_openai_service():
    """OpenAI 서비스 Mock"""
    from unittest.mock import AsyncMock, MagicMock
    
    mock_service = AsyncMock()
    
    # 임베딩 생성 Mock
    mock_response = MagicMock()
    mock_response.data = [MagicMock()]
    mock_response.data[0].embedding = [0.1] * 1536
    mock_service.create_embedding.return_value = mock_response
    
    # 텍스트 분석 Mock
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = '''
    {
        "keywords": {"AI": 0.9, "머신러닝": 0.8, "딥러닝": 0.7},
        "topics": {"인공지능": 0.9, "기술": 0.7},
        "categories": {"컴퓨터과학": 0.8, "기술": 0.6},
        "concepts": {"미래": 0.7, "혁신": 0.6}
    }
    '''
    mock_service.generate_completion.return_value = mock_completion
    
    return mock_service


# 테스트 데이터베이스 재설정 유틸리티
@pytest_asyncio.fixture
async def reset_database(engine: AsyncEngine):
    """테스트 전후 데이터베이스 리셋"""
    # 테스트 전 초기화
    async with engine.begin() as conn:
        from sqlalchemy import MetaData
        metadata = MetaData()
        await conn.run_sync(metadata.drop_all)
        # 간단한 테이블만 재생성
        await conn.run_sync(metadata.create_all)
    
    yield
    
    # 테스트 후 정리 (필요시)
    pass
