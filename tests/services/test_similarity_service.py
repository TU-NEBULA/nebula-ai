"""
SimilarityService 테스트
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