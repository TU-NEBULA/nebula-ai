"""
채팅 서비스 테스트 모듈

이 모듈은 app.services.chat 모듈의 기능을 테스트합니다.
PostgreSQL 벡터 서비스를 모킹하여 실제 DB 연결 없이 테스트합니다.
"""
import pytest
from unittest.mock import AsyncMock, patch, Mock
import app.services.chat as chat_mod
from app.models.chat import DocumentVector


@pytest.fixture(autouse=True)
def mock_vector_service(monkeypatch):
    """
    vector_service를 모킹하여 파일 I/O 없이 동작하도록 설정하고,
    similarity_search 호출 결과를 store_holder에 담아 반환.
    """
    store_holder = {}

    async def fake_similarity_search(session, query, user_id=None, limit=10, similarity_threshold=0.7):
        # 테스트용 DocumentVector 객체들 반환
        return store_holder.get("search_results", [])

    monkeypatch.setattr(
        "app.services.chat.vector_service.similarity_search", 
        fake_similarity_search
    )
    
    # format_search_results_for_rag 모킹
    def fake_format_results(search_results):
        return [
            {
                "source_id": f"doc_{i}",
                "title": f"Document {i}",
                "url": f"http://example.com/doc{i}",
                "snippet": f"This is document {i} content...",
                "keywords": [f"keyword{i}"],
                "score": 0.9 - i * 0.1
            }
            for i, (doc, score) in enumerate(search_results)
        ]
    
    monkeypatch.setattr(
        "app.services.chat.vector_service.format_search_results_for_rag",
        fake_format_results
    )

    return store_holder


@pytest.mark.asyncio
async def test_process_chat_success(mock_vector_service):
    """채팅 요청 처리 성공 테스트"""
    # 테스트용 문서 데이터 생성 (SQLModel이므로 더미 객체로 교체)
    class MockDocumentVector:
        def __init__(self, user_id, source_id, source_type, content, title, url):
            self.user_id = user_id
            self.source_id = source_id
            self.source_type = source_type
            self.content = content
            self.title = title
            self.url = url
            self.keywords = []
            self.summary = None
    
    mock_doc1 = MockDocumentVector(
        user_id="123",
        source_id="doc1",
        source_type="bookmark",
        content="Document 1 content",
        title="Document 1",
        url="http://example.com/doc1"
    )
    mock_doc2 = MockDocumentVector(
        user_id="123", 
        source_id="doc2",
        source_type="bookmark",
        content="Document 2 content",
        title="Document 2",
        url="http://example.com/doc2"
    )
    
    # 검색 결과 설정
    mock_vector_service["search_results"] = [
        (mock_doc1, 0.9),
        (mock_doc2, 0.8)
    ]

    # LLM 모킹
    with patch('app.services.chat.ChatOpenAI') as mock_llm_class:
        mock_llm_instance = Mock()  # AsyncMock 대신 Mock 사용
        mock_llm_class.return_value = mock_llm_instance
        
        # 모킹된 응답 설정 (동기 방식)
        class MockResponse:
            content = "테스트 응답입니다."
        
        mock_llm_instance.return_value = MockResponse()
        
        # 데이터베이스 세션 모킹
        with patch('app.services.chat.get_async_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            # 채팅 요청 처리 실행
            result = await chat_mod.process_chat_request("123", "안녕하세요")

            # 결과 검증
            assert result is not None
            assert "answer" in result
            assert "graphPayload" in result
            assert len(result["graphPayload"]["nodes"]) > 0


@pytest.mark.asyncio
async def test_process_chat_no_result(mock_vector_service):
    """검색 결과가 없을 때의 채팅 요청 처리 테스트"""
    # 빈 검색 결과 설정
    mock_vector_service["search_results"] = []

    # 데이터베이스 세션 모킹
    with patch('app.services.chat.get_async_session') as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # 채팅 요청 처리 실행
        result = await chat_mod.process_chat_request("123", "안녕하세요")

        # 결과 검증
        assert result is not None
        assert "answer" in result
        assert "관련 자료가 없어요" in result["answer"]
        assert result["graphPayload"]["nodes"] == []
