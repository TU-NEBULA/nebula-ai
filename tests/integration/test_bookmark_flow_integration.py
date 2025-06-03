"""
북마크 저장 플로우 통합 테스트

전체 북마크 저장 플로우의 통합 테스트를 진행합니다:
1. 메시지 수신
2. 유사도 계산 
3. 관계 메시지 발행
4. 북마크 저장
"""
import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from app.consumers.bookmark_save_rmq import on_bookmark_save
from app.services.similarity_service import SimilarityService
from app.services.message_publisher import MessagePublisher
from app.models.message_models import BookmarkRelationshipMessage


@pytest.fixture
def mock_incoming_message():
    """Mock IncomingMessage 클래스"""
    class MockIncomingMessage:
        def __init__(self, payload):
            self.body = json.dumps(payload).encode('utf-8')
        
        def process(self):
            class MockContext:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return MockContext()
    
    return MockIncomingMessage


@pytest.fixture
def sample_bookmark_message():
    """샘플 북마크 메시지 데이터"""
    return {
        "userId": 123,
        "starId": "test_bookmark_456",
        "s3Key": "test/sample.html",
        "title": "AI와 머신러닝 기초 가이드",
        "url": "https://example.com/ai-ml-guide",
        "keywords": ["AI", "머신러닝", "딥러닝", "기초"],
        "memo": "AI 학습용 자료",
        "summary": "인공지능과 머신러닝의 기본 개념부터 실습까지 다루는 종합 가이드"
    }


@pytest.fixture
def mock_similar_bookmarks():
    """Mock 유사한 북마크 데이터"""
    return [
        {
            "bookmark_id": "similar_1",
            "similarity_score": 0.92,
            "title": "딥러닝 완전 정복",
            "url": "https://example.com/deep-learning"
        },
        {
            "bookmark_id": "similar_2", 
            "similarity_score": 0.87,
            "title": "파이썬으로 배우는 머신러닝",
            "url": "https://example.com/python-ml"
        },
        {
            "bookmark_id": "similar_3",
            "similarity_score": 0.83,
            "title": "AI 실무 프로젝트",
            "url": "https://example.com/ai-projects"
        }
    ]


@pytest.mark.asyncio
async def test_complete_bookmark_flow_with_similar_bookmarks(
    mock_incoming_message, 
    sample_bookmark_message, 
    mock_similar_bookmarks
):
    """유사한 북마크가 있는 경우의 완전한 플로우 테스트"""
    
    message = mock_incoming_message(sample_bookmark_message)
    
    # Mock 설정들
    with patch('app.consumers.bookmark_save_rmq.similarity_service') as mock_similarity_service:
        with patch('app.consumers.bookmark_save_rmq.message_publisher') as mock_publisher:
            with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
                
                # SimilarityService Mock 설정 - AsyncMock 사용
                mock_similarity_service.find_similar_bookmarks = AsyncMock(return_value=mock_similar_bookmarks)
                
                # MessagePublisher Mock 설정 - AsyncMock 사용
                mock_publisher.publish_bookmark_relationships = AsyncMock(return_value=True)
                
                # 테스트 실행
                await on_bookmark_save(message)
                
                # 검증: SimilarityService 호출
                mock_similarity_service.find_similar_bookmarks.assert_called_once()
                call_args = mock_similarity_service.find_similar_bookmarks.call_args
                
                assert call_args.kwargs['user_id'] == 123
                assert call_args.kwargs['keywords'] == ["AI", "머신러닝", "딥러닝", "기초"]
                assert call_args.kwargs['summary'] == sample_bookmark_message['summary']
                
                # 검증: MessagePublisher 호출
                mock_publisher.publish_bookmark_relationships.assert_called_once()
                publisher_call_args = mock_publisher.publish_bookmark_relationships.call_args
                
                assert publisher_call_args.kwargs['user_id'] == 123
                assert publisher_call_args.kwargs['source_bookmark']['bookmark_id'] == "test_bookmark_456"
                assert publisher_call_args.kwargs['similar_bookmarks'] == mock_similar_bookmarks
                
                # 검증: save_bookmark_task 호출
                mock_save_task.delay.assert_called_once()
                save_task_call_args = mock_save_task.delay.call_args
                
                assert save_task_call_args.kwargs['user_id'] == 123
                assert save_task_call_args.kwargs['star_id'] == "test_bookmark_456"
                assert save_task_call_args.kwargs['title'] == sample_bookmark_message['title']


@pytest.mark.asyncio
async def test_complete_bookmark_flow_without_similar_bookmarks(
    mock_incoming_message, 
    sample_bookmark_message
):
    """유사한 북마크가 없는 경우의 플로우 테스트"""
    
    message = mock_incoming_message(sample_bookmark_message)
    
    with patch('app.consumers.bookmark_save_rmq.similarity_service') as mock_similarity_service:
        with patch('app.consumers.bookmark_save_rmq.message_publisher') as mock_publisher:
            with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
                
                # 유사한 북마크 없음
                mock_similarity_service.find_similar_bookmarks = AsyncMock(return_value=[])
                
                # 테스트 실행
                await on_bookmark_save(message)
                
                # 검증: SimilarityService는 호출되었지만 결과가 빈 리스트
                mock_similarity_service.find_similar_bookmarks.assert_called_once()
                
                # 검증: MessagePublisher는 호출되지 않음 (유사한 북마크가 없으므로)
                mock_publisher.publish_bookmark_relationships.assert_not_called()
                
                # 검증: save_bookmark_task는 여전히 호출됨
                mock_save_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_bookmark_flow_with_missing_required_fields(mock_incoming_message):
    """필수 필드 누락 시 플로우 테스트"""
    
    # title 필드 누락
    invalid_message = {
        "userId": 123,
        "starId": "invalid_bookmark",
        "s3Key": "test/invalid.html",
        "url": "https://example.com/invalid",
        "keywords": ["테스트"],
        "summary": "필수 필드 누락 테스트"
        # title 필드가 누락됨
    }
    
    message = mock_incoming_message(invalid_message)
    
    with patch('app.consumers.bookmark_save_rmq.similarity_service') as mock_similarity_service:
        with patch('app.consumers.bookmark_save_rmq.message_publisher') as mock_publisher:
            with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
                
                # 테스트 실행 (예외가 발생하지 않아야 함)
                await on_bookmark_save(message)
                
                # 검증: 필수 필드 누락으로 인해 후속 처리가 실행되지 않음
                mock_similarity_service.find_similar_bookmarks.assert_not_called()
                mock_publisher.publish_bookmark_relationships.assert_not_called()
                mock_save_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_bookmark_flow_with_similarity_service_error(
    mock_incoming_message,
    sample_bookmark_message
):
    """SimilarityService 오류 시 플로우 테스트"""
    
    message = mock_incoming_message(sample_bookmark_message)
    
    with patch('app.consumers.bookmark_save_rmq.similarity_service') as mock_similarity_service:
        with patch('app.consumers.bookmark_save_rmq.message_publisher') as mock_publisher:
            with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
                
                # SimilarityService에서 예외 발생
                mock_similarity_service.find_similar_bookmarks = AsyncMock(side_effect=Exception("Similarity calculation failed"))
                
                # 테스트 실행 (예외가 전파되지 않아야 함)
                await on_bookmark_save(message)
                
                # 검증: SimilarityService 호출 시도됨
                mock_similarity_service.find_similar_bookmarks.assert_called_once()
                
                # 검증: 예외로 인해 save_bookmark_task는 호출되지 않음
                mock_save_task.delay.assert_not_called()
                
                # 검증: MessagePublisher는 호출되지 않음 (SimilarityService 오류로 인해)
                mock_publisher.publish_bookmark_relationships.assert_not_called()


@pytest.mark.asyncio
async def test_bookmark_flow_with_publisher_error(
    mock_incoming_message,
    sample_bookmark_message,
    mock_similar_bookmarks
):
    """MessagePublisher 오류 시 플로우 테스트"""
    
    message = mock_incoming_message(sample_bookmark_message)
    
    with patch('app.consumers.bookmark_save_rmq.similarity_service') as mock_similarity_service:
        with patch('app.consumers.bookmark_save_rmq.message_publisher') as mock_publisher:
            with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
                
                # Mock 설정
                mock_similarity_service.find_similar_bookmarks = AsyncMock(return_value=mock_similar_bookmarks)
                mock_publisher.publish_bookmark_relationships = AsyncMock(side_effect=Exception("Publisher failed"))
                
                # 테스트 실행 (예외가 전파되지 않아야 함)
                await on_bookmark_save(message)
                
                # 검증: SimilarityService는 정상 호출
                mock_similarity_service.find_similar_bookmarks.assert_called_once()
                
                # 검증: MessagePublisher 호출 시도됨
                mock_publisher.publish_bookmark_relationships.assert_called_once()
                
                # 검증: 예외로 인해 save_bookmark_task는 호출되지 않음
                mock_save_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_bookmark_flow_json_parsing_error(mock_incoming_message):
    """JSON 파싱 오류 시 플로우 테스트"""
    
    # 잘못된 JSON을 가진 메시지 생성
    class BadJsonMessage:
        def __init__(self):
            self.body = b'{"invalid": json data}'  # 잘못된 JSON
        
        def process(self):
            class MockContext:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return MockContext()
    
    message = BadJsonMessage()
    
    with patch('app.consumers.bookmark_save_rmq.similarity_service') as mock_similarity_service:
        with patch('app.consumers.bookmark_save_rmq.message_publisher') as mock_publisher:
            with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
                
                # 테스트 실행 (예외가 발생하지 않아야 함)
                await on_bookmark_save(message)
                
                # 검증: JSON 파싱 오류로 인해 후속 처리가 실행되지 않음
                mock_similarity_service.find_similar_bookmarks.assert_not_called()
                mock_publisher.publish_bookmark_relationships.assert_not_called()
                mock_save_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_bookmark_relationship_message_integration():
    """BookmarkRelationshipMessage와 실제 서비스 통합 테스트"""
    
    source_bookmark = {
        "bookmark_id": "integration_test_123",
        "title": "통합 테스트 북마크",
        "url": "https://example.com/integration",
        "keywords": ["통합", "테스트"],
        "summary": "통합 테스트용 북마크입니다"
    }
    
    similar_bookmarks = [
        {
            "bookmark_id": "integration_similar_1",
            "similarity_score": 0.91,
            "title": "통합 유사 북마크 1",
            "url": "https://example.com/similar1"
        }
    ]
    
    # BookmarkRelationshipMessage 생성 테스트
    relationship_message = BookmarkRelationshipMessage(
        user_id=999,
        source_bookmark=source_bookmark,
        similar_bookmarks=similar_bookmarks
    )
    
    # 메시지 검증
    assert relationship_message.user_id == 999
    assert relationship_message.source_bookmark == source_bookmark
    assert len(relationship_message.similar_bookmarks) == 1
    assert relationship_message.similar_bookmarks[0]["similarity_score"] == 0.91
    
    # JSON 직렬화/역직렬화 테스트
    json_data = relationship_message.model_dump()
    recreated_message = BookmarkRelationshipMessage(**json_data)
    
    assert recreated_message.user_id == relationship_message.user_id
    assert recreated_message.source_bookmark == relationship_message.source_bookmark
    assert len(recreated_message.similar_bookmarks) == len(relationship_message.similar_bookmarks)


@pytest.mark.asyncio
async def test_full_flow_performance():
    """전체 플로우 성능 테스트"""
    
    import time
    
    # 다수의 유사한 북마크가 있는 시나리오
    large_similar_bookmarks = [
        {
            "bookmark_id": f"perf_test_{i}",
            "similarity_score": 0.9 - (i * 0.01),
            "title": f"성능 테스트 북마크 {i}",
            "url": f"https://example.com/perf{i}"
        }
        for i in range(50)  # 50개의 유사한 북마크
    ]
    
    sample_message = {
        "userId": 999,
        "starId": "performance_test",
        "s3Key": "test/performance.html",
        "title": "성능 테스트 북마크",
        "url": "https://example.com/performance",
        "keywords": ["성능", "테스트"],
        "summary": "성능 테스트용 북마크"
    }
    
    class MockMessage:
        def __init__(self, payload):
            self.body = json.dumps(payload).encode('utf-8')
        
        def process(self):
            class MockContext:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return MockContext()
    
    message = MockMessage(sample_message)
    
    with patch('app.consumers.bookmark_save_rmq.similarity_service') as mock_similarity_service:
        with patch('app.consumers.bookmark_save_rmq.message_publisher') as mock_publisher:
            with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
                
                mock_similarity_service.find_similar_bookmarks = AsyncMock(return_value=large_similar_bookmarks)
                mock_publisher.publish_bookmark_relationships = AsyncMock(return_value=True)
                
                # 성능 측정
                start_time = time.time()
                await on_bookmark_save(message)
                end_time = time.time()
                
                execution_time = end_time - start_time
                
                # 검증: 처리 시간이 합리적인 범위 내인지 확인 (예: 1초 이내)
                assert execution_time < 1.0, f"처리 시간이 너무 깁니다: {execution_time:.3f}초"
                
                # 검증: 모든 서비스가 정상 호출됨
                mock_similarity_service.find_similar_bookmarks.assert_called_once()
                mock_publisher.publish_bookmark_relationships.assert_called_once()
                mock_save_task.delay.assert_called_once()
                
                # 검증: 많은 수의 유사한 북마크가 올바르게 처리됨
                publisher_call_args = mock_publisher.publish_bookmark_relationships.call_args
                assert len(publisher_call_args.kwargs['similar_bookmarks']) == 50 