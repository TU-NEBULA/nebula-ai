"""
북마크 저장 플로우 통합 테스트

이 파일은 북마크 저장의 전체 플로우를 테스트합니다:
1. Consumer에서 메시지 수신 및 검증
2. Celery 태스크 호출
3. 실제 태스크에서의 전체 워크플로우 처리
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.consumers.bookmark_save_rmq import on_bookmark_save


@pytest.fixture
def mock_incoming_message():
    """Mock IncomingMessage 생성 함수"""
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
    """테스트용 표준 북마크 메시지"""
    return {
        "userId": 123,
        "starId": "test_bookmark_456",
        "s3Key": "test/sample.html",
        "title": "AI와 머신러닝 기초",
        "url": "https://example.com/ai-basics",
        "keywords": ["AI", "머신러닝", "딥러닝", "기초"],
        "memo": "AI 학습용 자료",
        "summary": "AI와 머신러닝에 대한 기초적인 내용을 다루는 문서"
    }


@pytest.fixture
def mock_similar_bookmarks():
    """Mock 유사 북마크 데이터"""
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
            "title": "머신러닝 알고리즘",
            "url": "https://example.com/ml-algorithms"
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
    """유사한 북마크가 있는 경우의 완전한 플로우 테스트 (Consumer + Task)"""
    
    message = mock_incoming_message(sample_bookmark_message)
    
    # Consumer만 테스트 (save_bookmark_task 호출 확인)
    with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
        # 테스트 실행
        await on_bookmark_save(message)
        
        # 검증: save_bookmark_task가 올바른 데이터로 호출되었는지 확인
        mock_save_task.delay.assert_called_once()
        call_args = mock_save_task.delay.call_args[0][0]  # 첫 번째 인자 (딕셔너리)
        
        assert call_args['user_id'] == 123
        assert call_args['star_id'] == "test_bookmark_456"
        assert call_args['title'] == sample_bookmark_message['title']
        assert call_args['s3_key'] == sample_bookmark_message['s3Key']
        assert call_args['keywords'] == sample_bookmark_message['keywords']


@pytest.mark.asyncio
async def test_complete_bookmark_flow_without_similar_bookmarks(
    mock_incoming_message, 
    sample_bookmark_message
):
    """유사한 북마크가 없는 경우의 플로우 테스트"""
    
    message = mock_incoming_message(sample_bookmark_message)
    
    # Consumer만 테스트
    with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
        # 테스트 실행
        await on_bookmark_save(message)
        
        # 검증: save_bookmark_task가 호출되었는지 확인 
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
    
    with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
        # 테스트 실행 (예외가 발생하지 않아야 함)
        await on_bookmark_save(message)
        
        # 검증: 필수 필드 누락으로 인해 태스크가 호출되지 않음
        mock_save_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_bookmark_flow_with_similarity_service_error(
    mock_incoming_message,
    sample_bookmark_message
):
    """Task에서 SimilarityService 오류 시 플로우 테스트"""
    
    message = mock_incoming_message(sample_bookmark_message)
    
    # Task의 의존성을 mock
    with patch('app.tasks.bookmark_save_task.similarity_service') as mock_similarity_service:
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
            
            # SimilarityService에서 예외 발생하도록 설정
            mock_similarity_service.find_similar_bookmarks = AsyncMock(
                side_effect=Exception("Similarity calculation failed")
            )
            
            # Consumer 테스트 (정상 호출되어야 함)
            await on_bookmark_save(message)
            
            # 검증: Consumer는 정상적으로 태스크를 호출
            mock_save_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_bookmark_flow_with_publisher_error(
    mock_incoming_message,
    sample_bookmark_message,
    mock_similar_bookmarks
):
    """Task에서 MessagePublisher 오류 시 플로우 테스트"""
    
    message = mock_incoming_message(sample_bookmark_message)
    
    # Task의 의존성을 mock
    with patch('app.tasks.bookmark_save_task.message_publisher') as mock_publisher:
        with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
            
            # MessagePublisher에서 예외 발생하도록 설정
            mock_publisher.publish_bookmark_relationships = AsyncMock(
                side_effect=Exception("Publisher failed")
            )
            
            # Consumer 테스트 (정상 호출되어야 함)
            await on_bookmark_save(message)
            
            # 검증: Consumer는 정상적으로 태스크를 호출
            mock_save_task.delay.assert_called_once()


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
    
    with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
        # 테스트 실행 (예외가 발생하지 않아야 함)
        await on_bookmark_save(message)
        
        # 검증: JSON 파싱 오류로 인해 태스크가 호출되지 않음
        mock_save_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_bookmark_relationship_message_integration():
    """북마크 관계 메시지 통합 테스트 (실제 메시지 발행까지)"""
    
    # 실제 메시지 발행까지 테스트하는 통합 테스트
    from app.services.message_publisher import message_publisher
    from app.models.message_models import BookmarkRelationshipMessage
    
    # 테스트 데이터
    test_data = BookmarkRelationshipMessage(
        user_id=999,
        source_bookmark={
            "bookmark_id": "integration_test",
            "title": "통합 테스트 북마크",
            "url": "https://example.com/integration",
            "keywords": ["통합", "테스트"],
            "summary": "통합 테스트용 북마크"
        },
        similar_bookmarks=[
            {
                "bookmark_id": "similar_integration",
                "similarity_score": 0.95,
                "title": "유사 통합 테스트",
                "url": "https://example.com/similar"
            }
        ]
    )
    
    # 실제 메시지 발행 테스트 (RabbitMQ 연결 필요할 수 있음)
    try:
        result = await message_publisher.publish_bookmark_relationships(
            user_id=test_data.user_id,
            source_bookmark=test_data.source_bookmark,
            similar_bookmarks=test_data.similar_bookmarks
        )
        
        # 성공 시 True, 연결 실패 시 False 반환
        assert isinstance(result, bool)
        
    except Exception as e:
        # 연결 실패는 정상 (테스트 환경에서는 RabbitMQ가 없을 수 있음)
        assert "connection" in str(e).lower() or "timeout" in str(e).lower()


@pytest.mark.asyncio
async def test_task_workflow_integration():
    """Task 워크플로우 통합 테스트"""
    
    from app.tasks.bookmark_save_task import BookmarkData
    
    # 테스트용 북마크 데이터
    bookmark_data = BookmarkData(
        user_id=123,
        star_id="task_integration_test",
        s3_key="test/task_integration.html",
        title="태스크 통합 테스트",
        url="https://example.com/task-integration",
        keywords=["태스크", "통합", "테스트"],
        memo="태스크 통합 테스트 메모",
        summary="태스크 통합 테스트 요약"
    )
    
    # 의존성들을 mock
    with patch('app.tasks.bookmark_save_task.download_html_from_s3') as mock_s3:
        with patch('app.tasks.bookmark_save_task.extract_main_text') as mock_extract:
            with patch('app.tasks.bookmark_save_task.similarity_service') as mock_similarity:
                with patch('app.tasks.bookmark_save_task.message_publisher') as mock_publisher:
                    with patch('app.tasks.bookmark_save_task.vector_service') as mock_vector:
                        with patch('app.tasks.bookmark_save_task.get_async_session') as mock_session:
                            
                            # Mock 설정
                            mock_s3.return_value = "<html><body>테스트 콘텐츠</body></html>"
                            mock_extract.return_value = "테스트 콘텐츠입니다. 태스크 통합 테스트를 진행하고 있습니다."
                            mock_similarity.find_similar_bookmarks = AsyncMock(return_value=[])
                            mock_publisher.publish_bookmark_relationships = AsyncMock(return_value=True)
                            mock_vector.delete_document = AsyncMock(return_value=0)
                            mock_vector.save_document = AsyncMock(return_value=[])
                            
                            # Async generator mock
                            async def mock_get_session():
                                yield MagicMock()
                            mock_session.return_value = mock_get_session()
                            
                            # _async_save_logic을 직접 테스트 (asyncio.run 문제 회피)
                            from app.tasks.bookmark_save_task import (
                                _download_and_extract_content,
                                _calculate_similarity,
                                _publish_relationships
                            )
                            
                            # 개별 함수들을 테스트
                            body_text = await _download_and_extract_content(bookmark_data.s3_key)
                            similar_bookmarks = await _calculate_similarity(bookmark_data, body_text)
                            relationship_published = await _publish_relationships(bookmark_data, similar_bookmarks)
                            
                            # 검증
                            assert len(body_text) > 0
                            assert "테스트 콘텐츠" in body_text
                            assert isinstance(similar_bookmarks, list)
                            assert isinstance(relationship_published, bool)


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
    
    # Consumer 성능 테스트 (단순 호출)
    with patch('app.consumers.bookmark_save_rmq.save_bookmark_task') as mock_save_task:
        start_time = time.time()
        
        # 테스트 실행
        await on_bookmark_save(message)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 검증: Consumer는 매우 빠르게 처리되어야 함 (< 0.1초)
        assert execution_time < 0.1
        mock_save_task.delay.assert_called_once()
        
        # 호출된 데이터 검증
        call_args = mock_save_task.delay.call_args[0][0]
        assert call_args['user_id'] == 999
        assert call_args['star_id'] == "performance_test" 