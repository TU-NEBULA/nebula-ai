"""
BookmarkEventListener 단위 테스트

북마크 이벤트 처리 및 프로필 업데이트 로직 테스트
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.listeners.user_actions import BookmarkEventListener
from app.services.user_profile_processor import UserProfileProcessor


class TestBookmarkEventListener:
    """BookmarkEventListener 단위 테스트"""

    @pytest.fixture
    def mock_profile_processor(self):
        """Mock UserProfileProcessor 픽스처"""
        processor = MagicMock(spec=UserProfileProcessor)
        processor.handle_bookmark_event = AsyncMock()
        return processor

    @pytest.fixture
    def bookmark_listener(self, mock_profile_processor):
        """BookmarkEventListener 픽스처"""
        return BookmarkEventListener(mock_profile_processor)

    @pytest.fixture
    def sample_bookmark_data(self):
        """샘플 북마크 데이터"""
        return {
            "title": "Python 고급 기법",
            "url": "https://example.com/python-advanced",
            "description": "파이썬 고급 프로그래밍 기법에 대한 글",
            "category": "programming",
            "tags": ["python", "programming", "advanced"],
            "content": "파이썬의 고급 기법들을 다루는 상세한 가이드..."
        }

    @pytest.mark.asyncio
    async def test_handle_bookmark_created_success(
        self, 
        bookmark_listener, 
        mock_profile_processor, 
        sample_bookmark_data
    ):
        """북마크 생성 이벤트 처리 성공 테스트"""
        # Given
        user_id = 123
        expected_result = {
            "user_id": user_id,
            "event_type": "bookmark",
            "profile_updated": True,
            "vector_strength": 0.85
        }
        
        mock_profile_processor.handle_bookmark_event.return_value = expected_result

        # When
        result = await bookmark_listener.handle_bookmark_created(
            user_id=user_id,
            bookmark_data=sample_bookmark_data
        )

        # Then
        assert result["user_id"] == user_id
        assert result["event_type"] == "bookmark"
        assert result["profile_updated"] is True
        
        # UserProfileProcessor가 올바른 파라미터로 호출되었는지 확인
        mock_profile_processor.handle_bookmark_event.assert_called_once()
        call_args = mock_profile_processor.handle_bookmark_event.call_args
        
        assert call_args[1]["user_id"] == user_id
        assert call_args[1]["bookmark_data"]["title"] == sample_bookmark_data["title"]
        assert call_args[1]["bookmark_data"]["event_type"] == "bookmark_created"
        assert "event_timestamp" in call_args[1]["bookmark_data"]

    @pytest.mark.asyncio
    async def test_handle_bookmark_created_with_metadata(
        self, 
        bookmark_listener, 
        mock_profile_processor, 
        sample_bookmark_data
    ):
        """메타데이터와 함께 북마크 생성 이벤트 처리 테스트"""
        # Given
        user_id = 123
        metadata = {"source": "browser_extension", "user_agent": "Chrome/96.0"}
        
        mock_profile_processor.handle_bookmark_event.return_value = {
            "user_id": user_id,
            "profile_updated": True
        }

        # When
        result = await bookmark_listener.handle_bookmark_created(
            user_id=user_id,
            bookmark_data=sample_bookmark_data.copy(),
            metadata=metadata
        )

        # Then
        call_args = mock_profile_processor.handle_bookmark_event.call_args
        bookmark_data = call_args[1]["bookmark_data"]
        
        assert bookmark_data["source"] == metadata["source"]
        assert bookmark_data["user_agent"] == metadata["user_agent"]

    @pytest.mark.asyncio
    async def test_handle_bookmark_created_with_callback(
        self, 
        bookmark_listener, 
        mock_profile_processor, 
        sample_bookmark_data
    ):
        """콜백이 등록된 경우 북마크 생성 이벤트 처리 테스트"""
        # Given
        user_id = 123
        callback_result = {"analytics_logged": True}
        
        async def mock_callback(user_id, bookmark_data, result):
            return callback_result
        
        bookmark_listener.register_callback("bookmark_created", mock_callback)
        mock_profile_processor.handle_bookmark_event.return_value = {
            "user_id": user_id,
            "profile_updated": True
        }

        # When
        result = await bookmark_listener.handle_bookmark_created(
            user_id=user_id,
            bookmark_data=sample_bookmark_data
        )

        # Then
        assert result["callback_result"] == callback_result

    @pytest.mark.asyncio
    async def test_handle_bookmark_created_processor_error(
        self, 
        bookmark_listener, 
        mock_profile_processor, 
        sample_bookmark_data
    ):
        """프로필 처리기에서 오류 발생 시 테스트"""
        # Given
        user_id = 123
        error_message = "Database connection error"
        
        mock_profile_processor.handle_bookmark_event.side_effect = Exception(error_message)

        # When
        result = await bookmark_listener.handle_bookmark_created(
            user_id=user_id,
            bookmark_data=sample_bookmark_data
        )

        # Then
        assert result["error"] == error_message
        assert result["user_id"] == user_id
        assert result["event_type"] == "bookmark_created"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_handle_bookmark_updated_significant_changes(
        self, 
        bookmark_listener, 
        mock_profile_processor, 
        sample_bookmark_data
    ):
        """중요한 변경사항이 있는 북마크 수정 이벤트 테스트"""
        # Given
        user_id = 123
        old_bookmark_data = sample_bookmark_data.copy()
        new_bookmark_data = sample_bookmark_data.copy()
        new_bookmark_data["title"] = "Python 고급 기법 - 업데이트됨"
        new_bookmark_data["category"] = "advanced_programming"
        
        mock_profile_processor.handle_bookmark_event.return_value = {
            "user_id": user_id,
            "profile_updated": True
        }

        # When
        result = await bookmark_listener.handle_bookmark_updated(
            user_id=user_id,
            bookmark_data=new_bookmark_data,
            old_bookmark_data=old_bookmark_data
        )

        # Then
        assert result["user_id"] == user_id
        assert result["profile_updated"] is True
        
        # 프로필 처리기가 호출되었는지 확인
        mock_profile_processor.handle_bookmark_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_bookmark_updated_no_significant_changes(
        self, 
        bookmark_listener, 
        mock_profile_processor, 
        sample_bookmark_data
    ):
        """중요하지 않은 변경사항만 있는 북마크 수정 이벤트 테스트"""
        # Given
        user_id = 123
        old_bookmark_data = sample_bookmark_data.copy()
        new_bookmark_data = sample_bookmark_data.copy()
        new_bookmark_data["last_accessed"] = datetime.now()  # 중요하지 않은 필드
        
        # When
        result = await bookmark_listener.handle_bookmark_updated(
            user_id=user_id,
            bookmark_data=new_bookmark_data,
            old_bookmark_data=old_bookmark_data
        )

        # Then
        assert result["user_id"] == user_id
        assert result["profile_updated"] is False
        assert result["reason"] == "No significant changes detected"
        
        # 프로필 처리기가 호출되지 않았는지 확인
        mock_profile_processor.handle_bookmark_event.assert_not_called()

    def test_should_update_profile_for_bookmark_change_title_changed(
        self, 
        bookmark_listener, 
        sample_bookmark_data
    ):
        """제목 변경 시 프로필 업데이트 필요성 테스트"""
        # Given
        old_data = sample_bookmark_data.copy()
        new_data = sample_bookmark_data.copy()
        new_data["title"] = "새로운 제목"

        # When
        should_update = bookmark_listener._should_update_profile_for_bookmark_change(
            new_data, old_data
        )

        # Then
        assert should_update is True

    def test_should_update_profile_for_bookmark_change_no_old_data(
        self, 
        bookmark_listener, 
        sample_bookmark_data
    ):
        """이전 데이터가 없는 경우 프로필 업데이트 필요성 테스트"""
        # When
        should_update = bookmark_listener._should_update_profile_for_bookmark_change(
            sample_bookmark_data, None
        )

        # Then
        assert should_update is True

    def test_should_update_profile_for_bookmark_change_no_changes(
        self, 
        bookmark_listener, 
        sample_bookmark_data
    ):
        """변경사항이 없는 경우 프로필 업데이트 필요성 테스트"""
        # When
        should_update = bookmark_listener._should_update_profile_for_bookmark_change(
            sample_bookmark_data, sample_bookmark_data
        )

        # Then
        assert should_update is False

    def test_register_callback(self, bookmark_listener):
        """콜백 등록 테스트"""
        # Given
        async def test_callback(user_id, bookmark_data, result):
            return {"test": True}

        # When
        bookmark_listener.register_callback("bookmark_created", test_callback)

        # Then
        assert "bookmark_created" in bookmark_listener.event_callbacks
        assert bookmark_listener.event_callbacks["bookmark_created"] == test_callback

    def test_stop_listening(self, bookmark_listener):
        """이벤트 리스닝 중단 테스트"""
        # Given
        bookmark_listener._is_listening = True

        # When
        bookmark_listener.stop_listening()

        # Then
        assert bookmark_listener._is_listening is False

    @pytest.mark.asyncio
    async def test_listen_bookmark_events_basic_structure(self, bookmark_listener):
        """기본 이벤트 리스닝 구조 테스트"""
        # Given
        bookmark_listener._is_listening = False

        # When
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = [None, Exception("Stop test")]
            
            try:
                await bookmark_listener.listen_bookmark_events("test_source")
            except Exception:
                pass  # 예상된 종료

        # Then
        mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_multiple_bookmark_events_sequence(
        self, 
        bookmark_listener, 
        mock_profile_processor, 
        sample_bookmark_data
    ):
        """연속된 북마크 이벤트 처리 테스트"""
        # Given
        user_id = 123
        mock_profile_processor.handle_bookmark_event.return_value = {
            "user_id": user_id,
            "profile_updated": True
        }

        # When
        results = []
        for i in range(3):
            bookmark_data = sample_bookmark_data.copy()
            bookmark_data["title"] = f"북마크 {i+1}"
            
            result = await bookmark_listener.handle_bookmark_created(
                user_id=user_id,
                bookmark_data=bookmark_data
            )
            results.append(result)

        # Then
        assert len(results) == 3
        assert mock_profile_processor.handle_bookmark_event.call_count == 3
        
        # 각 호출이 서로 다른 제목으로 이루어졌는지 확인
        calls = mock_profile_processor.handle_bookmark_event.call_args_list
        titles = [call[1]["bookmark_data"]["title"] for call in calls]
        
        assert "북마크 1" in titles
        assert "북마크 2" in titles
        assert "북마크 3" in titles


if __name__ == "__main__":
    pytest.main([__file__])
