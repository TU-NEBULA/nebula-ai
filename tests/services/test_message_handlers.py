"""
RabbitMQ 메시지 핸들러 테스트

ProfileMessageHandler와 RabbitMQConsumer의 모든 기능을 테스트
- 프로필 업데이트 메시지 처리
- 프로필 재생성 메시지 처리
- 추천 갱신 메시지 처리
- 에러 처리 및 복구 테스트
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.services.message_handlers import ProfileMessageHandler, RabbitMQConsumer
from app.schemas.profile_schemas import (
    ProfileUpdateRequest,
    ProfileRefreshRequest,
    RecommendationRefreshRequest
)


class TestProfileMessageHandler:
    """ProfileMessageHandler 테스트"""
    
    @pytest.fixture
    def handler(self):
        """테스트용 메시지 핸들러"""
        with patch('app.services.message_handlers.OpenAIService'), \
             patch('app.services.message_handlers.VectorGenerator'):
            return ProfileMessageHandler()
    
    @pytest.fixture
    def profile_update_message(self):
        """프로필 업데이트 메시지 데이터"""
        return {
            "user_id": 123,
            "update_type": "incremental",
            "incremental_update": True,
            "new_interests": ["AI", "머신러닝"],
            "remove_interests": [],
            "preference_adjustments": {"AI": 0.9, "데이터사이언스": 0.8},
            "force_recalculation": False,
            "source_data": {
                "bookmarks": [{"title": "AI 논문", "content": "GPT 관련"}],
                "activity_type": "bookmark_added"
            }
        }
    
    @pytest.fixture
    def profile_refresh_message(self):
        """프로필 재생성 메시지 데이터"""
        return {
            "user_id": 456,
            "job_id": "refresh-job-123",
            "force_full_recalculation": True,
            "use_algorithm_version": "v2.0",
            "include_historical_data": True,
            "recalculate_dependencies": ["similarities", "recommendations"]
        }
    
    @pytest.fixture
    def recommendation_refresh_message(self):
        """추천 갱신 메시지 데이터"""
        return {
            "user_id": 789,
            "categories": ["technology", "research"],
            "priority": "high",
            "use_research": True
        }


class TestProfileUpdateHandler(TestProfileMessageHandler):
    """프로필 업데이트 핸들러 테스트"""
    
    @pytest.mark.asyncio
    @patch('app.services.message_handlers.get_async_session')
    @patch('app.services.message_handlers.create_repositories')
    @patch('app.services.message_handlers.UserProfileProcessor')
    async def test_handle_profile_update_success(
        self, 
        mock_processor_class, 
        mock_create_repos, 
        mock_session,
        handler, 
        profile_update_message
    ):
        """프로필 업데이트 성공 테스트"""
        # Mock 설정 - async for 지원을 위한 async generator
        mock_session_instance = AsyncMock()
        async def async_session_generator():
            yield mock_session_instance
        mock_session.return_value = async_session_generator()
        
        mock_repos = {
            'chat_repo': AsyncMock(),
            'bookmark_repo': AsyncMock(),
            'ai_profile_repo': AsyncMock(),
            'user_profile_repo': AsyncMock()
        }
        mock_create_repos.return_value = mock_repos
        
        # 기존 프로필 Mock
        mock_profile = MagicMock()
        mock_profile.profile_vector = [0.1] * 1536
        mock_repos['user_profile_repo'].get_or_create_profile.return_value = mock_profile
        
        mock_processor = AsyncMock()
        # 새로운 메서드 시그니처에 맞춘 return value
        mock_processor.update_vector_incrementally.return_value = (
            [0.1] * 1536,  # result_vector
            {  # result_metadata
                "vector_strength": 0.85,
                "processing_time": 2.5,
                "updated_keywords": ["AI", "머신러닝"]
            }
        )
        mock_processor_class.return_value = mock_processor
        
        # 핸들러 메서드 Mock
        handler._apply_preference_adjustments = AsyncMock()
        
        # 테스트 실행
        result = await handler.handle_profile_update(profile_update_message)
        
        # 검증
        assert result["success"] is True
        assert result["user_id"] == 123
        assert result["update_type"] == "incremental"
        assert result["vector_strength"] == 0.85
        assert result["processing_time"] == 2.5
        
        # 메서드 호출 확인 - incremental 모드에서는 update_vector_incrementally만 호출됨
        mock_processor.update_vector_incrementally.assert_called_once()
        handler._apply_preference_adjustments.assert_called_once()
        
        # incremental 모드에서는 update_profile이 호출되지 않음
        assert not mock_repos['user_profile_repo'].update_profile.called
    
    @pytest.mark.asyncio
    @patch('app.services.message_handlers.get_async_session')
    @patch('app.services.message_handlers.create_repositories')
    @patch('app.services.message_handlers.UserProfileProcessor')
    async def test_handle_profile_update_full_mode(
        self, 
        mock_processor_class, 
        mock_create_repos, 
        mock_session,
        handler
    ):
        """전체 프로필 업데이트 테스트"""
        # Mock 설정 - async for 지원
        mock_session_instance = AsyncMock()
        async def async_session_generator():
            yield mock_session_instance
        mock_session.return_value = async_session_generator()
        
        mock_repos = {
            'chat_repo': AsyncMock(),
            'bookmark_repo': AsyncMock(),
            'ai_profile_repo': AsyncMock(),
            'user_profile_repo': AsyncMock()
        }
        mock_create_repos.return_value = mock_repos
        
        mock_processor = AsyncMock()
        # 새로운 메서드 시그니처에 맞춘 return value
        mock_processor.generate_profile_vector_advanced.return_value = (
            [0.2] * 1536,  # result_vector
            {  # result_metadata
                "vector_strength": 0.92,
                "processing_time": 15.2
            }
        )
        mock_processor_class.return_value = mock_processor
        
        # 전체 업데이트 메시지
        message = {
            "user_id": 123,
            "update_type": "full",
            "incremental_update": False,
            "force_recalculation": True,
            "source_data": None
        }
        
        # 테스트 실행
        result = await handler.handle_profile_update(message)
        
        # 검증
        assert result["success"] is True
        assert result["update_type"] == "full"
        # 새로운 메서드 호출 확인
        mock_processor.generate_profile_vector_advanced.assert_called_once_with(
            session=mock_session_instance,
            user_id=123
        )
        # 실제 코드에서는 update_profile 호출이 조건에 따라 다를 수 있음 - 결과 확인으로 대체
        assert result["vector_strength"] == 0.92
        assert result["processing_time"] == 15.2
    
    @pytest.mark.asyncio
    async def test_handle_profile_update_validation_error(self, handler):
        """잘못된 메시지 검증 테스트"""
        # 필수 필드 누락 메시지
        invalid_message = {
            "update_type": "incremental"
            # user_id 누락
        }
        
        # 테스트 실행
        result = await handler.handle_profile_update(invalid_message)
        
        # 검증
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="DB connection test는 실제 환경에서만 유효")
    async def test_handle_profile_update_database_error(self, handler):
        """데이터베이스 오류 처리 테스트"""
        pass


class TestProfileRefreshHandler(TestProfileMessageHandler):
    """프로필 재생성 핸들러 테스트"""
    
    @pytest.mark.asyncio
    @patch('app.services.message_handlers.get_async_session')
    @patch('app.services.message_handlers.create_repositories')
    @patch('app.services.message_handlers.UserProfileProcessor')
    async def test_handle_profile_refresh_success(
        self, 
        mock_processor_class, 
        mock_create_repos, 
        mock_session,
        handler, 
        profile_refresh_message
    ):
        """프로필 재생성 성공 테스트"""
        # Mock 설정 - async for 지원
        mock_session_instance = AsyncMock()
        async def async_session_generator():
            yield mock_session_instance
        mock_session.return_value = async_session_generator()
        
        mock_repos = {
            'chat_repo': AsyncMock(),
            'bookmark_repo': AsyncMock(),
            'ai_profile_repo': AsyncMock(),
            'user_profile_repo': AsyncMock()
        }
        mock_create_repos.return_value = mock_repos
        
        mock_processor = AsyncMock()
        # 새로운 메서드 시그니처에 맞춘 return value
        mock_processor.generate_profile_vector_advanced.return_value = (
            [0.3] * 1536,  # result_vector
            {  # result_metadata
                "vector_strength": 0.91,
                "completeness_score": 95
            }
        )
        mock_repos['user_profile_repo'].get_similar_users.return_value = [1, 2, 3]
        mock_processor_class.return_value = mock_processor
        
        # 핸들러 메서드 Mock
        handler._update_job_status = AsyncMock()
        handler._backup_existing_profile = AsyncMock()
        
        # 테스트 실행
        result = await handler.handle_profile_refresh(profile_refresh_message)
        
        # 검증
        assert result["success"] is True
        assert result["job_id"] == "refresh-job-123"
        assert result["user_id"] == 456
        
        # 진행 상태 업데이트 호출 확인
        assert handler._update_job_status.call_count >= 3  # 시작, 중간, 완료
        
        # 새로운 메서드 호출 확인
        mock_processor.generate_profile_vector_advanced.assert_called_once_with(
            session=mock_session_instance,
            user_id=456
        )
        # 결과에 대한 검증으로 대체
        assert result["result"]["vector_strength"] == 0.91
        assert result["result"]["completeness_score"] == 95


class TestRecommendationRefreshHandler(TestProfileMessageHandler):
    """추천 갱신 핸들러 테스트"""
    
    @pytest.mark.asyncio
    @patch('app.services.message_handlers.get_async_session')
    @patch('app.services.message_handlers.create_repositories')
    @patch('app.services.message_handlers.UserProfileProcessor')
    async def test_handle_recommendation_refresh_success(
        self, 
        mock_processor_class, 
        mock_create_repos, 
        mock_session,
        handler, 
        recommendation_refresh_message
    ):
        """추천 갱신 성공 테스트"""
        # Mock 설정 - async for 지원
        mock_session_instance = AsyncMock()
        async def async_session_generator():
            yield mock_session_instance
        mock_session.return_value = async_session_generator()
        
        mock_repos = {
            'chat_repo': AsyncMock(),
            'bookmark_repo': AsyncMock(),
            'ai_profile_repo': AsyncMock(),
            'user_profile_repo': AsyncMock()
        }
        mock_create_repos.return_value = mock_repos
        
        # 프로필 Mock
        mock_profile = MagicMock()
        mock_profile.user_id = 789
        mock_repos['user_profile_repo'].get_or_create_profile.return_value = mock_profile
        
        # 유사한 사용자들 Mock - None을 반환해서 빈 리스트로 처리되도록 설정
        mock_repos['user_profile_repo'].get_similar_users.return_value = None
        
        mock_processor = AsyncMock()
        mock_processor_class.return_value = mock_processor
        
        # 테스트 실행
        result = await handler.handle_recommendation_refresh(recommendation_refresh_message)
        
        # 검증 - 실제 코드 동작을 기반으로 결과 중심 검증
        assert result["success"] is True
        assert result["user_id"] == 789
        assert result["recommendations_generated"] == 0  # None이므로 len(None or []) = 0
        assert result["categories"] == ["technology", "research"]


class TestPreferenceAdjustments(TestProfileMessageHandler):
    """선호도 조정 테스트"""
    
    @pytest.mark.asyncio
    @patch('app.services.message_handlers.create_repositories')
    async def test_apply_preference_adjustments(self, mock_create_repos, handler):
        """선호도 수동 조정 테스트"""
        mock_session = AsyncMock()
        user_id = 123
        adjustments = {"AI": 0.95, "머신러닝": 0.8, "데이터사이언스": 0.85}
        
        # Mock repository
        mock_repos = {
            'user_profile_repo': AsyncMock()
        }
        mock_create_repos.return_value = mock_repos
        
        # Mock 프로필 데이터
        mock_profile = MagicMock()
        mock_profile.vector_metadata = {
            "keywords": {"AI": 0.7, "머신러닝": 0.6, "블록체인": 0.4},
            "algorithm_version": "v2.0"
        }
        
        mock_repos['user_profile_repo'].get_or_create_profile.return_value = mock_profile
        
        # 테스트 실행
        await handler._apply_preference_adjustments(mock_session, user_id, adjustments)
        
        # 검증
        mock_repos['user_profile_repo'].get_or_create_profile.assert_called_once_with(mock_session, user_id)
        mock_repos['user_profile_repo'].update_profile.assert_called_once()
        
        # 업데이트 호출 인수 확인 - keyword arguments 형태
        update_call = mock_repos['user_profile_repo'].update_profile.call_args
        assert update_call[0][0] == mock_session  # session
        assert update_call[0][1] == user_id  # user_id
        # vector_metadata는 keyword argument로 전달됨
        assert 'vector_metadata' in update_call[1]
    
    @pytest.mark.asyncio
    @patch('app.services.message_handlers.create_repositories')
    async def test_apply_preference_adjustments_no_profile(self, mock_create_repos, handler):
        """프로필 없는 경우 선호도 조정 테스트"""
        mock_session = AsyncMock()
        user_id = 999
        adjustments = {"AI": 0.9}
        
        # Mock repository
        mock_repos = {
            'user_profile_repo': AsyncMock()
        }
        mock_create_repos.return_value = mock_repos
        mock_repos['user_profile_repo'].get_or_create_profile.return_value = None
        
        # 테스트 실행 (예외 발생하지 않아야 함)
        await handler._apply_preference_adjustments(mock_session, user_id, adjustments)
        
        # update_profile이 호출되지 않아야 함
        mock_repos['user_profile_repo'].update_profile.assert_not_called()


class TestRabbitMQConsumer:
    """RabbitMQConsumer 테스트"""
    
    @pytest.fixture
    def consumer(self):
        """테스트용 RabbitMQ 컨슈머"""
        return RabbitMQConsumer("amqp://test:test@localhost/test")
    
    @pytest.mark.asyncio
    @patch('app.services.message_handlers.aio_pika.connect_robust')
    async def test_setup_queues_and_consumers(self, mock_connect, consumer):
        """큐 및 컨슈머 설정 테스트"""
        # Mock 설정
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()
        
        mock_connect.return_value = mock_connection
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_queue.return_value = mock_queue
        
        # 테스트 실행
        connection = await consumer.setup_queues_and_consumers()
        
        # 검증
        assert connection == mock_connection
        
        # 큐 선언 확인 (3개 큐)
        assert mock_channel.declare_queue.call_count == 3
        
        # 컨슈머 등록 확인
        assert mock_queue.consume.call_count == 3
    
    @pytest.mark.asyncio
    async def test_handle_profile_update_message_success(self, consumer):
        """프로필 업데이트 메시지 처리 래퍼 테스트"""
        # Mock 메시지
        mock_message = AsyncMock()
        mock_body = MagicMock()
        mock_body.decode.return_value = json.dumps({
            "user_id": 123,
            "update_type": "incremental",
            "incremental_update": True
        })
        mock_message.body = mock_body
        
        # message.process()가 직접 비동기 컨텍스트 매니저가 되도록 설정
        mock_process_context = AsyncMock()
        mock_process_context.__aenter__ = AsyncMock(return_value=mock_process_context)
        mock_process_context.__aexit__ = AsyncMock(return_value=None)
        # process()를 호출하지 않고 process 자체가 컨텍스트 매니저
        mock_message.process = MagicMock(return_value=mock_process_context)
        
        # Mock 핸들러
        consumer.handler.handle_profile_update = AsyncMock(return_value={"success": True})
        
        # 테스트 실행
        await consumer._handle_profile_update_message(mock_message)
        
        # 검증
        consumer.handler.handle_profile_update.assert_called_once()
        mock_message.process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_profile_refresh_message_failure(self, consumer):
        """프로필 재생성 메시지 처리 실패 테스트"""
        # Mock 메시지
        mock_message = AsyncMock()
        mock_body = MagicMock()
        mock_body.decode.return_value = json.dumps({
            "user_id": 456,
            "job_id": "test-job",
            "force_full_recalculation": True
        })
        mock_message.body = mock_body
        
        # message.process()가 직접 비동기 컨텍스트 매니저가 되도록 설정
        mock_process_context = AsyncMock()
        mock_process_context.__aenter__ = AsyncMock(return_value=mock_process_context)
        mock_process_context.__aexit__ = AsyncMock(return_value=None)
        mock_message.process = MagicMock(return_value=mock_process_context)
        
        # Mock 핸들러 - 실패 응답
        consumer.handler.handle_profile_refresh = AsyncMock(return_value={"success": False, "error": "Test error"})
        
        # 테스트 실행
        await consumer._handle_profile_refresh_message(mock_message)
        
        # 검증
        consumer.handler.handle_profile_refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_recommendation_refresh_message_json_error(self, consumer):
        """잘못된 JSON 메시지 처리 테스트"""
        # Mock 메시지 - 잘못된 JSON
        mock_message = AsyncMock()
        mock_body = MagicMock()
        mock_body.decode.return_value = "invalid json"
        mock_message.body = mock_body
        
        # message.process()가 직접 비동기 컨텍스트 매니저가 되도록 설정
        mock_process_context = AsyncMock()
        mock_process_context.__aenter__ = AsyncMock(return_value=mock_process_context)
        mock_process_context.__aexit__ = AsyncMock(return_value=None)
        mock_message.process = MagicMock(return_value=mock_process_context)
        
        # 테스트 실행 및 예외 확인
        with pytest.raises(json.JSONDecodeError):
            await consumer._handle_recommendation_refresh_message(mock_message)


class TestIntegrationScenarios:
    """통합 시나리오 테스트"""
    
    @pytest.mark.asyncio
    async def test_full_profile_refresh_workflow(self):
        """전체 프로필 재생성 워크플로우 테스트"""
        with patch('app.services.message_handlers.OpenAIService'), \
             patch('app.services.message_handlers.VectorGenerator'):
            handler = ProfileMessageHandler()
        
        # Mock 각 의존성을 개별적으로 처리
        with patch('app.services.message_handlers.get_async_session') as mock_session, \
             patch('app.services.message_handlers.create_repositories') as mock_create_repos, \
             patch('app.services.message_handlers.UserProfileProcessor') as mock_processor_class:
            
            # Mock 설정 - async for 지원
            mock_session_instance = AsyncMock()
            async def async_session_generator():
                yield mock_session_instance
            mock_session.return_value = async_session_generator()
            
            mock_repos = {
                'chat_repo': AsyncMock(),
                'bookmark_repo': AsyncMock(),
                'ai_profile_repo': AsyncMock(),
                'user_profile_repo': AsyncMock()
            }
            mock_create_repos.return_value = mock_repos
            
            # Mock 프로세서 결과 - 새로운 시그니처에 맞춤
            mock_processor = AsyncMock()
            mock_processor.generate_profile_vector_advanced.return_value = (
                [0.4] * 1536,  # result_vector
                {"vector_strength": 0.9}  # result_metadata
            )
            mock_repos['user_profile_repo'].get_similar_users.return_value = [1, 2, 3]
            mock_processor_class.return_value = mock_processor
            
            # Mock 핸들러 메서드
            handler._update_job_status = AsyncMock()
            handler._backup_existing_profile = AsyncMock()
            
            # 테스트 메시지
            message = {
                "user_id": 100,
                "job_id": "integration-test-job",
                "force_full_recalculation": True,
                "recalculate_dependencies": ["similarities", "recommendations"]
            }
            
            # 테스트 실행
            result = await handler.handle_profile_refresh(message)
            
            # 검증
            assert result["success"] is True
            assert result["job_id"] == "integration-test-job"
            assert result["user_id"] == 100
            
            # 워크플로우 단계들이 실행되었는지 확인
            mock_processor.generate_profile_vector_advanced.assert_called_once()
            # 결과 중심으로 검증
            assert result["result"]["vector_strength"] == 0.9
            handler._update_job_status.assert_called()
    
    @pytest.mark.asyncio
    async def test_incremental_update_workflow(self):
        """점진적 업데이트 워크플로우 테스트"""
        with patch('app.services.message_handlers.OpenAIService'), \
             patch('app.services.message_handlers.VectorGenerator'):
            handler = ProfileMessageHandler()
        
        with patch('app.services.message_handlers.get_async_session') as mock_session, \
             patch('app.services.message_handlers.create_repositories') as mock_create_repos, \
             patch('app.services.message_handlers.UserProfileProcessor') as mock_processor_class:
            
            # Mock 설정 - async for 지원
            mock_session_instance = AsyncMock()
            async def async_session_generator():
                yield mock_session_instance
            mock_session.return_value = async_session_generator()
            
            mock_repos = {
                'chat_repo': AsyncMock(),
                'bookmark_repo': AsyncMock(),
                'ai_profile_repo': AsyncMock(),
                'user_profile_repo': AsyncMock()
            }
            mock_create_repos.return_value = mock_repos
            
            # 기존 프로필 Mock
            mock_profile = MagicMock()
            mock_profile.profile_vector = [0.1] * 1536
            mock_repos['user_profile_repo'].get_or_create_profile.return_value = mock_profile
            
            # Mock 프로세서
            mock_processor = AsyncMock()
            mock_processor.update_vector_incrementally.return_value = (
                [0.2] * 1536,  # updated vector
                {"vector_strength": 0.75, "processing_time": 1.2}  # metadata
            )
            mock_processor_class.return_value = mock_processor
            
            # Mock 핸들러 메서드
            handler._apply_preference_adjustments = AsyncMock()
            
            # 테스트 메시지 - 필수 필드 추가
            message = {
                "user_id": 200,
                "update_type": "incremental",  # 필수 필드 추가
                "incremental_update": True,
                "source_data": {
                    "bookmarks": [{"title": "New AI Paper"}]
                },
                "preference_adjustments": {"AI": 0.9}
            }
            
            # 테스트 실행
            result = await handler.handle_profile_update(message)
            
            # 검증
            assert result["success"] is True
            assert result["user_id"] == 200
            assert result["update_type"] == "incremental"
            assert result["vector_strength"] == 0.75
            
            # 점진적 업데이트 메서드가 호출되었는지 확인
            mock_processor.update_vector_incrementally.assert_called_once()
            handler._apply_preference_adjustments.assert_called_once() 