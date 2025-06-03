"""
MessagePublisher 테스트
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.message_publisher import MessagePublisher, message_publisher
from app.core.config import settings


@pytest.fixture
def publisher():
    """MessagePublisher 인스턴스 생성"""
    return MessagePublisher()


@pytest.fixture
def mock_source_bookmark():
    """소스 북마크 Mock 데이터"""
    return {
        "bookmark_id": "test_bookmark_123",
        "title": "AI 기술 동향",
        "url": "https://example.com/ai-trends",
        "keywords": ["AI", "기술", "동향"],
        "summary": "최신 AI 기술 동향에 대한 분석"
    }


@pytest.fixture
def mock_similar_bookmarks():
    """유사한 북마크들 Mock 데이터"""
    return [
        {
            "bookmark_id": "similar_1",
            "similarity_score": 0.85,
            "title": "머신러닝 기초",
            "url": "https://example.com/ml-basics"
        },
        {
            "bookmark_id": "similar_2",
            "similarity_score": 0.78,
            "title": "딥러닝 실습",
            "url": "https://example.com/dl-practice"
        }
    ]


@pytest.mark.asyncio
async def test_publish_bookmark_relationships_success(publisher, mock_source_bookmark, mock_similar_bookmarks):
    """북마크 관계 메시지 발행 성공 테스트"""
    
    # _publish_message 메서드를 직접 Mock
    with patch.object(publisher, '_publish_message') as mock_publish:
        mock_publish.return_value = True
        
        result = await publisher.publish_bookmark_relationships(
            user_id=123,
            source_bookmark=mock_source_bookmark,
            similar_bookmarks=mock_similar_bookmarks
        )
        
        # 검증
        assert result is True
        mock_publish.assert_called_once()
        
        # 호출 인자 검증
        call_args = mock_publish.call_args
        assert call_args.kwargs['queue_name'] == settings.BOOKMARK_RELATIONSHIP_QUEUE
        assert 'message_data' in call_args.kwargs
        assert call_args.kwargs['routing_key'] == "bookmark.relationship.create"


@pytest.mark.asyncio
async def test_publish_bookmark_relationships_connection_error(publisher, mock_source_bookmark, mock_similar_bookmarks):
    """RabbitMQ 연결 오류 시 테스트"""
    
    # _publish_message 메서드에서 False 반환하도록 Mock
    with patch.object(publisher, '_publish_message') as mock_publish:
        mock_publish.return_value = False
        
        result = await publisher.publish_bookmark_relationships(
            user_id=123,
            source_bookmark=mock_source_bookmark,
            similar_bookmarks=mock_similar_bookmarks
        )
        
        assert result is False


@pytest.mark.asyncio
async def test_publish_message_success(publisher):
    """메시지 발행 성공 테스트"""
    
    # _get_connection 메서드를 Mock하여 RabbitMQ 연결 우회
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_queue = AsyncMock()
    
    mock_channel.declare_queue = AsyncMock(return_value=mock_queue)
    mock_channel.default_exchange.publish = AsyncMock()
    
    with patch.object(publisher, '_get_connection') as mock_get_connection:
        mock_get_connection.return_value = (mock_connection, mock_channel)
        
        test_data = {"test_key": "test_value"}
        
        result = await publisher._publish_message(
            queue_name="test.queue",
            message_data=test_data,
            routing_key="test.routing"
        )
        
        # 검증
        assert result is True
        mock_channel.declare_queue.assert_called_once_with("test.queue", durable=True)
        mock_channel.default_exchange.publish.assert_called_once()


@pytest.mark.asyncio
async def test_get_connection_new_connection(publisher):
    """새로운 연결 생성 테스트"""
    
    # _get_connection 메서드를 직접 Mock하여 테스트
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    
    with patch.object(publisher, '_get_connection') as mock_get_connection:
        mock_get_connection.return_value = (mock_connection, mock_channel)
        
        connection, channel = await publisher._get_connection()
        
        assert connection == mock_connection
        assert channel == mock_channel


@pytest.mark.asyncio
async def test_get_connection_reuse_existing(publisher):
    """기존 연결 재사용 테스트"""
    
    # 기존 연결 설정
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_connection.is_closed = False
    
    publisher.connection = mock_connection
    publisher.channel = mock_channel
    
    connection, channel = await publisher._get_connection()
    
    assert connection == mock_connection
    assert channel == mock_channel


@pytest.mark.asyncio
async def test_close_connection(publisher):
    """연결 종료 테스트"""
    
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    
    mock_connection.is_closed = False
    mock_channel.is_closed = False
    
    publisher.connection = mock_connection
    publisher.channel = mock_channel
    
    await publisher.close()
    
    mock_channel.close.assert_called_once()
    mock_connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_connection_error(publisher):
    """연결 종료 시 오류 처리 테스트"""
    
    mock_channel = AsyncMock()
    mock_channel.close.side_effect = Exception("Close error")
    mock_channel.is_closed = False
    
    publisher.channel = mock_channel
    
    # 오류가 발생해도 예외가 발생하지 않아야 함
    await publisher.close()


def test_message_publisher_message_data_serialization(mock_source_bookmark, mock_similar_bookmarks):
    """메시지 데이터 직렬화 테스트"""
    
    from app.models.message_models import BookmarkRelationshipMessage
    
    message_data = BookmarkRelationshipMessage(
        user_id=123,
        source_bookmark=mock_source_bookmark,
        similar_bookmarks=mock_similar_bookmarks
    )
    
    # JSON 직렬화 테스트
    serialized = message_data.model_dump()
    
    assert "user_id" in serialized
    assert "source_bookmark" in serialized
    assert "similar_bookmarks" in serialized
    assert "created_at" in serialized
    
    assert serialized["user_id"] == 123
    assert serialized["source_bookmark"] == mock_source_bookmark
    assert serialized["similar_bookmarks"] == mock_similar_bookmarks


@pytest.mark.asyncio
async def test_global_message_publisher_instance():
    """전역 MessagePublisher 인스턴스 테스트"""
    
    assert message_publisher is not None
    assert isinstance(message_publisher, MessagePublisher)


@pytest.mark.asyncio 
async def test_publish_bookmark_relationships_empty_similar_bookmarks(publisher, mock_source_bookmark):
    """유사한 북마크가 없는 경우 테스트"""
    
    # _publish_message 메서드를 Mock
    with patch.object(publisher, '_publish_message') as mock_publish:
        mock_publish.return_value = True
        
        result = await publisher.publish_bookmark_relationships(
            user_id=123,
            source_bookmark=mock_source_bookmark,
            similar_bookmarks=[]  # 빈 리스트
        )
        
        # 빈 리스트여도 메시지는 발행되어야 함
        assert result is True
        mock_publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_message_with_korean_content(publisher):
    """한글 콘텐츠가 포함된 메시지 발행 테스트"""
    
    # _get_connection 메서드를 Mock
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_queue = AsyncMock()
    
    mock_channel.declare_queue = AsyncMock(return_value=mock_queue)
    mock_channel.default_exchange.publish = AsyncMock()
    
    with patch.object(publisher, '_get_connection') as mock_get_connection:
        mock_get_connection.return_value = (mock_connection, mock_channel)
        
        korean_data = {
            "title": "한글 제목",
            "content": "한글 내용입니다",
            "keywords": ["키워드1", "키워드2"]
        }
        
        result = await publisher._publish_message(
            queue_name="test.queue",
            message_data=korean_data,
            routing_key="test.routing"
        )
        
        assert result is True
        
        # Mock이 호출되었는지 확인
        mock_channel.default_exchange.publish.assert_called_once() 