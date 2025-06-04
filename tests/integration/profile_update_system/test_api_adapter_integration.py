"""
프로필 업데이트 시스템 API 어댑터 통합 테스트

Task 32.9: User Profile API Integration 구현 검증
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.adapters.profile_api_adapter import (
    ProfileAPIAdapter,
    ProfileUpdateEventTranslator
)
from app.services.user_profile_processor import ActivityData, ActivityType
from app.listeners.user_actions import BookmarkEventListener, ChatEventListener


class TestProfileAPIAdapterIntegration:
    """ProfileAPIAdapter 통합 테스트"""

    @pytest_asyncio.fixture
    async def api_adapter(self):
        """API 어댑터 픽스처"""
        adapter = ProfileAPIAdapter()
        yield adapter
        # 테스트 후 정리
        if adapter.connection and not adapter.connection.is_closed:
            await adapter.close_connection()

    @pytest.fixture
    def event_translator(self):
        """이벤트 변환기 픽스처"""
        return ProfileUpdateEventTranslator()

    @pytest.fixture
    def mock_bookmark_data(self):
        """북마크 데이터 픽스처"""
        return {
            "title": "AI와 머신러닝 가이드",
            "description": "인공지능과 머신러닝에 대한 포괄적인 가이드",
            "content": "딥러닝, 신경망, 자연어처리에 대한 상세한 설명",
            "url": "https://example.com/ai-guide",
            "category": "technology",
            "tags": ["AI", "머신러닝", "딥러닝"],
            "keywords": ["인공지능", "머신러닝", "딥러닝", "신경망"],
            "event_timestamp": datetime.now(),
            "event_type": "bookmark_created"
        }

    @pytest.fixture
    def mock_chat_data(self):
        """채팅 데이터 픽스처"""
        return {
            "session_title": "Python 웹개발 상담",
            "messages": [
                {"role": "user", "content": "FastAPI로 웹 API를 만들고 싶어요"},
                {"role": "assistant", "content": "FastAPI는 훌륭한 선택입니다"},
                {"role": "user", "content": "데이터베이스 연동은 어떻게 하나요?"}
            ],
            "keywords": ["Python", "웹개발", "FastAPI"],
            "categories": ["programming", "web"],
            "session_duration_minutes": 15,
            "event_timestamp": datetime.now(),
            "event_type": "chat_session_completed",
            "weight": 1.2
        }

    @pytest.mark.asyncio
    async def test_send_profile_update_message_success(self, api_adapter, mock_bookmark_data):
        """프로필 업데이트 메시지 발행 성공 테스트"""
        # Mock RabbitMQ 연결 - _publish_to_queue 메서드를 직접 Mock
        with patch.object(api_adapter, '_publish_to_queue', return_value=True) as mock_publish:
            # ActivityData 생성 (새로운 구조에 맞게)
            metadata = {
                "title": mock_bookmark_data["title"],
                "description": mock_bookmark_data["description"],
                "keywords": mock_bookmark_data["keywords"],
                "categories": [mock_bookmark_data["category"]],
                "tags": mock_bookmark_data["tags"],
                "url": mock_bookmark_data["url"],
                "event_type": mock_bookmark_data["event_type"]
            }

            activity_data = ActivityData(
                activity_type=ActivityType.BOOKMARK,
                content=mock_bookmark_data["content"],
                created_at=mock_bookmark_data["event_timestamp"],
                metadata=metadata,
                weight=1.5
            )

            # 테스트 실행
            result = await api_adapter.send_profile_update_message(
                user_id=123,
                activity_data=activity_data,
                update_type="incremental"
            )

            # 검증
            assert result is True
            mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_batch_update_message_success(self, api_adapter):
        """배치 업데이트 메시지 발행 성공 테스트"""
        # Mock _publish_to_queue 메서드
        with patch.object(api_adapter, '_publish_to_queue', return_value=True) as mock_publish:
            user_ids = [123, 456, 789]

            # 테스트 실행
            result = await api_adapter.send_batch_update_message(
                user_ids=user_ids,
                update_type="quality_check",
                force_recalculation=False
            )

            # 검증
            assert result is True
            # 각 사용자마다 메시지가 발행되어야 함
            assert mock_publish.call_count == len(user_ids)

    @pytest.mark.asyncio
    async def test_send_profile_refresh_message_success(self, api_adapter):
        """프로필 재생성 메시지 발행 성공 테스트"""
        # Mock _publish_to_queue 메서드
        with patch.object(api_adapter, '_publish_to_queue', return_value=True) as mock_publish:
            # 테스트 실행
            job_id = await api_adapter.send_profile_refresh_message(
                user_id=123,
                force_full_recalculation=True
            )

            # 검증
            assert job_id is not None
            assert len(job_id) > 0
            mock_publish.assert_called_once()

    def test_bookmark_event_to_activity_data_conversion(self, event_translator, mock_bookmark_data):
        """북마크 이벤트 데이터 변환 테스트"""
        activity_data = event_translator.bookmark_event_to_activity_data(mock_bookmark_data)

        assert activity_data.activity_type == ActivityType.BOOKMARK
        assert activity_data.metadata["title"] == mock_bookmark_data["title"]
        assert activity_data.metadata["description"] == mock_bookmark_data["description"]
        assert activity_data.content == mock_bookmark_data["content"]
        assert activity_data.metadata["keywords"] == mock_bookmark_data["keywords"]
        assert activity_data.metadata["categories"] == [mock_bookmark_data["category"]]
        assert activity_data.metadata["tags"] == mock_bookmark_data["tags"]
        assert activity_data.metadata["url"] == mock_bookmark_data["url"]
        assert activity_data.created_at == mock_bookmark_data["event_timestamp"]
        assert activity_data.weight == 1.5

    def test_chat_event_to_activity_data_conversion(self, event_translator, mock_chat_data):
        """채팅 이벤트 데이터 변환 테스트"""
        activity_data = event_translator.chat_event_to_activity_data(mock_chat_data)

        assert activity_data.activity_type == ActivityType.CHAT
        assert activity_data.metadata["title"] == mock_chat_data["session_title"]
        assert "채팅 세션" in activity_data.metadata["description"]
        assert "FastAPI로 웹 API를 만들고 싶어요" in activity_data.content
        assert activity_data.metadata["keywords"] == mock_chat_data["keywords"]
        assert activity_data.metadata["categories"] == mock_chat_data["categories"]
        assert activity_data.metadata["session_duration"] == mock_chat_data["session_duration_minutes"]
        assert activity_data.metadata["message_count"] == len(mock_chat_data["messages"])
        assert activity_data.created_at == mock_chat_data["event_timestamp"]
        assert activity_data.weight == mock_chat_data["weight"]

    def test_quality_check_to_source_data_conversion(self, event_translator):
        """품질 체크 데이터 변환 테스트"""
        quality_metrics = {
            "quality_score": 0.75,
            "completeness_score": 0.8,
            "freshness_score": 0.6,
            "recommendations": ["프로필 업데이트 권장"],
            "needs_update": True,
            "last_update_days": 5
        }

        source_data = event_translator.quality_check_to_source_data(quality_metrics)

        assert source_data["quality_check"] is True
        assert source_data["quality_score"] == 0.75
        assert source_data["completeness_score"] == 0.8
        assert source_data["freshness_score"] == 0.6
        assert source_data["recommendations"] == ["프로필 업데이트 권장"]
        assert source_data["needs_update"] is True
        assert source_data["last_update_days"] == 5
        assert "timestamp" in source_data

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, api_adapter):
        """연결 오류 처리 테스트"""
        # Mock RabbitMQ 연결 오류
        with patch('aio_pika.connect_robust', side_effect=ConnectionError("연결 실패")):
            metadata = {"title": "test title", "event_type": "test"}
            activity_data = ActivityData(
                activity_type=ActivityType.BOOKMARK,
                content="test content",
                created_at=datetime.now(),
                metadata=metadata,
                weight=1.0
            )

            result = await api_adapter.send_profile_update_message(
                user_id=123,
                activity_data=activity_data
            )

            # 연결 실패 시 False 반환
            assert result is False


class TestEventListenerAPIIntegration:
    """이벤트 리스너 API 통합 테스트"""

    @pytest.mark.asyncio
    async def test_bookmark_listener_api_integration(self):
        """북마크 리스너 API 통합 테스트"""
        # Mock API 어댑터
        mock_api_adapter = AsyncMock()
        mock_api_adapter.send_profile_update_message.return_value = True

        # 북마크 리스너 설정
        listener = BookmarkEventListener(use_api_adapter=True)
        listener.api_adapter = mock_api_adapter

        bookmark_data = {
            "title": "테스트 북마크",
            "description": "테스트용 북마크입니다",
            "content": "테스트 콘텐츠",
            "url": "https://test.com",
            "category": "test",
            "tags": ["test"],
            "keywords": ["테스트"]
        }

        # 테스트 실행
        result = await listener.handle_bookmark_created(
            user_id=123,
            bookmark_data=bookmark_data
        )

        # 검증
        assert result["success"] is True
        assert result["message_published"] is True
        mock_api_adapter.send_profile_update_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_listener_api_integration(self):
        """채팅 리스너 API 통합 테스트"""
        # Mock API 어댑터
        mock_api_adapter = AsyncMock()
        mock_api_adapter.send_profile_update_message.return_value = True

        # 채팅 리스너 설정
        listener = ChatEventListener(use_api_adapter=True)
        listener.api_adapter = mock_api_adapter

        # 충분한 메시지와 시간을 가진 채팅 데이터 (프로필 업데이트 조건 만족)
        chat_data = {
            "session_title": "테스트 채팅",
            "messages": [
                {"role": "user", "content": "안녕하세요"},
                {"role": "assistant", "content": "안녕하세요! 무엇을 도와드릴까요?"},
                {"role": "user", "content": "Python에 대해 알고 싶어요"},
                {"role": "assistant", "content": "Python은 훌륭한 언어입니다"},
                {"role": "user", "content": "웹 개발도 가능한가요?"}
            ],
            "keywords": ["테스트", "Python"],
            "categories": ["general", "programming"],
            "session_duration_minutes": 10  # 충분한 시간
        }

        # 테스트 실행 (올바른 메서드명 사용)
        result = await listener.handle_chat_session_completed(
            user_id=123,
            chat_data=chat_data
        )

        # 검증
        assert result["success"] is True
        assert result["message_published"] is True
        mock_api_adapter.send_profile_update_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_adapter_error_handling(self):
        """API 어댑터 오류 처리 테스트"""
        # Mock API 어댑터 (예외 발생하도록 설정)
        mock_api_adapter = AsyncMock()
        mock_api_adapter.send_profile_update_message.side_effect = Exception("API 오류")

        # 북마크 리스너 설정
        listener = BookmarkEventListener(use_api_adapter=True)
        listener.api_adapter = mock_api_adapter

        bookmark_data = {
            "title": "테스트 북마크",
            "content": "테스트 콘텐츠"
        }

        # 테스트 실행
        result = await listener.handle_bookmark_created(
            user_id=123,
            bookmark_data=bookmark_data
        )

        # 검증: 예외 발생 시 오류 반환
        assert "error" in result
        assert result["user_id"] == 123

    @pytest.mark.asyncio
    async def test_chat_listener_connection_cleanup(self):
        """채팅 리스너 연결 정리 테스트"""
        # Mock API 어댑터
        mock_api_adapter = AsyncMock()
        mock_api_adapter.close_connection = AsyncMock()

        # 채팅 리스너 설정 (close_connections 메서드가 있음)
        listener = ChatEventListener(use_api_adapter=True)
        listener.api_adapter = mock_api_adapter

        # 연결 정리 테스트
        await listener.close_connections()

        # 검증
        mock_api_adapter.close_connection.assert_called_once()


class TestEndToEndIntegration:
    """End-to-End 통합 테스트"""

    @pytest.mark.asyncio
    async def test_complete_bookmark_flow(self):
        """완전한 북마크 플로우 테스트"""
        # Mock 컴포넌트들
        mock_api_adapter = AsyncMock()
        mock_api_adapter.send_profile_update_message.return_value = True

        # 이벤트 리스너 설정
        listener = BookmarkEventListener(use_api_adapter=True)
        listener.api_adapter = mock_api_adapter

        # 실제 시나리오 시뮬레이션
        bookmark_data = {
            "title": "FastAPI 완전 가이드",
            "description": "FastAPI 웹 프레임워크 완전 정복",
            "content": "FastAPI는 Python 웹 프레임워크입니다",
            "url": "https://example.com/fastapi-guide",
            "category": "programming",
            "tags": ["FastAPI", "Python", "웹개발"],
            "keywords": ["FastAPI", "Python", "API", "웹프레임워크"]
        }

        # 1. 북마크 생성 이벤트 처리
        result = await listener.handle_bookmark_created(
            user_id=123,
            bookmark_data=bookmark_data
        )

        # 2. 결과 검증
        assert result["success"] is True
        assert result["message_published"] is True

        # 3. API 어댑터 호출 검증
        mock_api_adapter.send_profile_update_message.assert_called_once()

        call_args = mock_api_adapter.send_profile_update_message.call_args
        activity_data = call_args[1]["activity_data"]

        assert activity_data.activity_type == ActivityType.BOOKMARK
        assert activity_data.metadata["title"] == bookmark_data["title"]
        assert activity_data.content == bookmark_data["content"]
        assert activity_data.metadata["url"] == bookmark_data["url"]

    @pytest.mark.asyncio
    async def test_quality_check_integration(self):
        """품질 체크 통합 테스트"""
        from app.tasks.daily_profile_monitor import ProfileQualityMetrics

        # Mock API 어댑터
        with patch('app.adapters.profile_api_adapter.ProfileAPIAdapter') as MockAdapter:
            mock_instance = AsyncMock()
            mock_instance.send_batch_update_message.return_value = True
            MockAdapter.return_value = mock_instance

            # 품질 메트릭 생성
            metrics = ProfileQualityMetrics(
                user_id=123,
                quality_score=0.35,  # 낮은 품질
                completeness_score=0.6,
                freshness_score=0.2,
                vector_strength=0.4,
                activity_level=0.3,
                last_update_days=30,
                recommendations=["프로필 업데이트 필요"],
                needs_update=True
            )

            # DailyProfileMonitor의 _trigger_profile_updates 직접 테스트
            from app.tasks.daily_profile_monitor import DailyProfileMonitor
            monitor = DailyProfileMonitor()
            # Mock으로 교체
            monitor.api_adapter = mock_instance

            updated_count = await monitor._trigger_profile_updates([metrics])

            # 검증
            assert updated_count == 1
            mock_instance.send_batch_update_message.assert_called_once()

            # 호출 인자 검증
            call_args = mock_instance.send_batch_update_message.call_args
            assert call_args[1]["user_ids"] == [123]
            assert call_args[1]["update_type"] == "quality_check"
            assert call_args[1]["force_recalculation"] is False 