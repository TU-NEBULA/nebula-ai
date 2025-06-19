"""
SimilarityService 테스트

북마크 유사도 계산 서비스의 기능을 테스트합니다.
"""
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.similarity_service import SimilarityService


@pytest.fixture
def similarity_service():
    """SimilarityService 인스턴스 생성"""
    return SimilarityService()


@pytest.fixture
def mock_existing_bookmarks():
    """기존 북마크 Mock 데이터"""
    return [
        {
            "id": "bookmark_1",
            "title": "머신러닝 기초",
            "url": "https://example.com/ml",
            "embedding": np.random.rand(1536).tolist(),  # OpenAI 임베딩 차원
            "content": "머신러닝의 기본 개념에 대해 설명합니다."
        },
        {
            "id": "bookmark_2", 
            "title": "딥러닝 실습",
            "url": "https://example.com/dl",
            "embedding": np.random.rand(1536).tolist(),
            "content": "딥러닝 모델을 직접 만들어보는 실습 강의입니다."
        },
        {
            "id": "bookmark_3",
            "title": "Python 프로그래밍",
            "url": "https://example.com/python",
            "embedding": np.random.rand(1536).tolist(),
            "content": "Python 프로그래밍 언어의 기초부터 고급까지"
        }
    ]


@pytest.mark.asyncio
async def test_find_similar_bookmarks_success(similarity_service, mock_existing_bookmarks):
    """유사한 북마크 찾기 성공 테스트"""
    
    # OpenAI 임베딩 생성 Mock
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [MagicMock()]
    mock_embedding_response.data[0].embedding = np.random.rand(1536).tolist()
    
    with patch('openai.embeddings.create', return_value=mock_embedding_response):
        # _get_user_bookmarks를 Mock하여 기존 북마크 반환
        with patch.object(similarity_service, '_get_user_bookmarks') as mock_get_bookmarks:
            mock_get_bookmarks.return_value = mock_existing_bookmarks
            
            # 테스트 실행
            result = await similarity_service.find_similar_bookmarks(
                new_bookmark_content="인공지능과 머신러닝에 대한 새로운 글",
                user_id=123,
                keywords=["AI", "ML", "인공지능"],
                summary="인공지능과 머신러닝의 최신 동향"
            )
            
            # 검증
            assert isinstance(result, list)
            assert len(result) >= 0
            for bookmark in result:
                assert "bookmark_id" in bookmark
                assert "similarity_score" in bookmark
                assert "title" in bookmark
                assert "url" in bookmark
                assert 0.0 <= bookmark["similarity_score"] <= 1.0


@pytest.mark.asyncio
async def test_find_similar_bookmarks_no_existing_bookmarks(similarity_service):
    """기존 북마크가 없는 경우 테스트"""
    
    # _get_user_bookmarks가 빈 리스트를 반환하므로 테스트가 통과해야 함
    result = await similarity_service.find_similar_bookmarks(
        new_bookmark_content="새로운 북마크 내용",
        user_id=123,
        keywords=["테스트"],
        summary="테스트 요약"
    )
    
    assert result == []


@pytest.mark.asyncio
async def test_find_similar_bookmarks_openai_error(similarity_service, mock_existing_bookmarks):
    """OpenAI API 오류 시 테스트"""
    
    # OpenAI API 오류 Mock
    with patch('openai.embeddings.create', side_effect=Exception("OpenAI API Error")):
        result = await similarity_service.find_similar_bookmarks(
            new_bookmark_content="테스트 내용",
            user_id=123,
            keywords=["테스트"],
            summary="테스트 요약"
        )
        
        assert result == []


@pytest.mark.asyncio
async def test_create_bookmark_embedding(similarity_service):
    """북마크 임베딩 생성 테스트"""
    
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [MagicMock()]
    mock_embedding_response.data[0].embedding = np.random.rand(1536).tolist()
    
    with patch('openai.embeddings.create', return_value=mock_embedding_response):
        embedding = await similarity_service._create_bookmark_embedding(
            content="테스트 콘텐츠",
            keywords=["키워드1", "키워드2"],
            summary="테스트 요약"
        )
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (1536,)  # OpenAI 임베딩 차원


@pytest.mark.asyncio
async def test_get_user_bookmarks(similarity_service, mock_existing_bookmarks):
    """사용자 북마크 조회 테스트"""
    
    # 현재 구현에서는 항상 빈 리스트를 반환함
    result = await similarity_service._get_user_bookmarks(user_id=123)
    
    assert result == []
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_calculate_similarities(similarity_service):
    """유사도 계산 테스트"""
    
    new_embedding = np.random.rand(1536)
    existing_bookmarks = [
        {
            "id": "test_1",
            "title": "테스트 북마크 1",
            "url": "https://example.com/1",
            "embedding": np.random.rand(1536).tolist()
        },
        {
            "id": "test_2",
            "title": "테스트 북마크 2", 
            "url": "https://example.com/2",
            "embedding": np.random.rand(1536).tolist()
        }
    ]
    
    result = await similarity_service._calculate_similarities(
        new_embedding, existing_bookmarks
    )
    
    assert len(result) == len(existing_bookmarks)
    for bookmark in result:
        assert "bookmark_id" in bookmark
        assert "similarity_score" in bookmark
        assert "title" in bookmark
        assert "url" in bookmark
        assert isinstance(bookmark["similarity_score"], float)


def test_similarity_service_initialization():
    """SimilarityService 초기화 테스트"""
    service = SimilarityService()
    
    assert service.vector_service is not None
    assert hasattr(service, 'similarity_threshold')
    assert hasattr(service, 'max_similar_bookmarks')


class TestSimilarityService:
    """SimilarityService 테스트 클래스"""
    
    @pytest.fixture
    def mock_document_vector(self):
        """Mock DocumentVector 객체"""
        mock_doc = MagicMock()
        mock_doc.source_id = "bookmark_123"
        mock_doc.title = "테스트 북마크"
        mock_doc.url = "https://example.com"
        mock_doc.embedding = [0.1] * 1536
        mock_doc.content = "테스트 콘텐츠"
        mock_doc.keywords = ["테스트", "키워드"]
        mock_doc.summary = "테스트 요약"
        mock_doc.created_at = "2024-01-01T00:00:00"
        mock_doc.id = "doc_456"
        return mock_doc
    
    @pytest.mark.asyncio
    async def test_get_user_bookmarks_success(self, similarity_service, mock_document_vector):
        """사용자 북마크 조회 성공 테스트"""
        user_id = 123
        
        # Mock database session and VectorRepository.get_documents_by_user
        with patch('app.services.similarity_service.get_async_session') as mock_session, \
             patch('app.services.similarity_service.VectorRepository.get_documents_by_user') as mock_get_docs:
            
            # Mock async generator (async for에서 사용)
            mock_db_session = AsyncMock()
            
            async def mock_async_generator():
                yield mock_db_session
                
            mock_session.return_value = mock_async_generator()
            
            # Mock documents results
            mock_get_docs.return_value = [mock_document_vector]
            
            # 테스트 실행
            result = await similarity_service._get_user_bookmarks(user_id)
            
            # 검증
            assert len(result) == 1
            assert result[0]["id"] == "bookmark_123"
            assert result[0]["title"] == "테스트 북마크"
            assert result[0]["url"] == "https://example.com"
            assert result[0]["embedding"] == [0.1] * 1536
            assert result[0]["content"] == "테스트 콘텐츠"
            assert result[0]["keywords"] == ["테스트", "키워드"]
            assert result[0]["summary"] == "테스트 요약"
            
            # VectorRepository.get_documents_by_user가 올바른 파라미터로 호출되었는지 확인
            mock_get_docs.assert_called_once()
            call_args = mock_get_docs.call_args[1]  # kwargs
            assert call_args["user_id"] == 123  # int 타입 그대로
            assert call_args["source_type"] == "bookmark"
            assert call_args["limit"] == 1000
    
    @pytest.mark.asyncio
    async def test_get_user_bookmarks_empty_result(self, similarity_service):
        """사용자 북마크 조회 결과가 없는 경우 테스트"""
        user_id = 123
        
        with patch('app.services.similarity_service.get_async_session') as mock_session, \
             patch('app.services.similarity_service.VectorRepository.get_documents_by_user') as mock_get_docs:
            
            # Mock async generator (async for에서 사용)
            mock_db_session = AsyncMock()
            
            async def mock_async_generator():
                yield mock_db_session
                
            mock_session.return_value = mock_async_generator()
            
            # 빈 결과 반환
            mock_get_docs.return_value = []
            
            result = await similarity_service._get_user_bookmarks(user_id)
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_user_bookmarks_duplicate_source_ids(self, similarity_service):
        """중복된 source_id가 있는 경우 중복 제거 테스트"""
        user_id = 123
        
        # 같은 source_id를 가진 두 개의 문서 (다른 청크)
        mock_doc1 = MagicMock()
        mock_doc1.source_id = "bookmark_123"
        mock_doc1.title = "테스트 북마크"
        mock_doc1.url = "https://example.com"
        mock_doc1.embedding = [0.1] * 1536
        mock_doc1.content = "첫 번째 청크"
        mock_doc1.keywords = ["테스트"]
        mock_doc1.summary = "요약"
        mock_doc1.created_at = "2024-01-01T00:00:00"
        
        mock_doc2 = MagicMock()
        mock_doc2.source_id = "bookmark_123"  # 같은 source_id
        mock_doc2.title = "테스트 북마크"
        mock_doc2.url = "https://example.com"
        mock_doc2.embedding = [0.2] * 1536
        mock_doc2.content = "두 번째 청크"
        mock_doc2.keywords = ["테스트"]
        mock_doc2.summary = "요약"
        mock_doc2.created_at = "2024-01-01T00:00:00"
        
        with patch('app.services.similarity_service.get_async_session') as mock_session, \
             patch('app.services.similarity_service.VectorRepository.get_documents_by_user') as mock_get_docs:
            
            # Mock async generator (async for에서 사용)
            mock_db_session = AsyncMock()
            
            async def mock_async_generator():
                yield mock_db_session
                
            mock_session.return_value = mock_async_generator()
            
            # 두 개의 문서 반환 (같은 source_id)
            mock_get_docs.return_value = [mock_doc1, mock_doc2]
            
            result = await similarity_service._get_user_bookmarks(user_id)
            
            # 중복이 제거되어 하나만 반환되어야 함
            assert len(result) == 1
            assert result[0]["id"] == "bookmark_123"
            assert result[0]["content"] == "첫 번째 청크"  # 첫 번째 것만 남음
    
    @pytest.mark.asyncio
    async def test_get_user_document_stats_success(self, similarity_service):
        """사용자 문서 통계 조회 성공 테스트"""
        user_id = 123
        expected_count = 5
        
        with patch('app.services.similarity_service.get_async_session') as mock_session, \
             patch('app.services.similarity_service.VectorRepository.get_user_document_count') as mock_count:
            
            # Mock async generator (async for에서 사용)
            mock_db_session = AsyncMock()
            
            async def mock_async_generator():
                yield mock_db_session
                
            mock_session.return_value = mock_async_generator()
            
            mock_count.return_value = expected_count
            
            result = await similarity_service.get_user_document_stats(user_id)
            
            assert result["user_id"] == user_id
            assert result["total_bookmarks"] == expected_count
            assert result["last_updated"] is None
            
            mock_count.assert_called_once_with(
                session=mock_db_session,
                user_id=123,  # int 타입 그대로
                source_type="bookmark"
            )
    
    @pytest.mark.asyncio
    async def test_get_user_bookmarks_error_handling(self, similarity_service):
        """데이터베이스 연결 오류 시 에러 핸들링 테스트"""
        user_id = 123
        
        with patch('app.services.similarity_service.get_async_session') as mock_session:
            # ConnectionError 발생 시뮬레이션
            mock_session.side_effect = ConnectionError("데이터베이스 연결 실패")
            
            result = await similarity_service._get_user_bookmarks(user_id)
            
            # 빈 리스트 반환
            assert result == []
    
    @pytest.mark.asyncio
    async def test_calculate_similarities_success(self, similarity_service):
        """유사도 계산 성공 테스트"""
        new_embedding = np.array([0.1] * 1536)
        
        existing_bookmarks = [
            {
                "id": "bookmark_1",
                "title": "북마크 1",
                "url": "https://example1.com",
                "embedding": [0.1] * 1536  # 동일한 임베딩 (유사도 1.0)
            },
            {
                "id": "bookmark_2", 
                "title": "북마크 2",
                "url": "https://example2.com",
                "embedding": [0.0] * 1536  # 다른 임베딩 (유사도 낮음)
            }
        ]
        
        result = await similarity_service._calculate_similarities(new_embedding, existing_bookmarks)
        
        assert len(result) == 2
        assert result[0]["bookmark_id"] == "bookmark_1"
        assert result[0]["similarity_score"] == pytest.approx(1.0, rel=1e-3)
        assert result[1]["bookmark_id"] == "bookmark_2"
        assert result[1]["similarity_score"] < 0.5 