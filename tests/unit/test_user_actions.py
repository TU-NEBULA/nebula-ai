"""
User Actions Event Listeners 테스트

ChatEventListener와 BookmarkEventListener의 모든 기능을 테스트
- 채팅 세션 완료 이벤트 처리
- 북마크 이벤트 처리
- 이벤트 콜백 시스템
- 프로필 업데이트 트리거링
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.listeners.user_actions import ChatEventListener, BookmarkEventListener
from app.services.user_profile_processor import UserProfileProcessor


class TestChatEventListener:
    """ChatEventListener 테스트"""

    @pytest.fixture
    def mock_profile_processor(self):
        """Mock UserProfileProcessor"""
        mock_processor = AsyncMock(spec=UserProfileProcessor)
        
        # handle_chat_completion_event 메서드 Mock
        mock_processor.handle_chat_completion_event.return_value = {
            "event_type": "chat_completion",
            "user_id": 123,
            "session_id": "test_session",
            "vector_strength": 0.85,
            "update_timestamp": datetime.now()
        }
        
        return mock_processor

    @pytest.fixture
    def chat_listener(self, mock_profile_processor):
        """ChatEventListener 인스턴스"""
        return ChatEventListener(mock_profile_processor)

    @pytest.mark.asyncio
    async def test_handle_chat_session_completed_success(self, chat_listener, mock_profile_processor):
        """채팅 세션 완료 이벤트 처리 성공 테스트"""
        
        user_id = 123
        chat_data = {
            "session_id": "chat_session_001",
            "duration": 900,  # 15분
            "message_count": 20,
            "topic": "programming",
            "language": "korean",
            "messages": [
                {"role": "user", "content": "파이썬 기초 문법을 배우고 싶어요"},
                {"role": "assistant", "content": "좋습니다. 변수부터 시작해볼까요?"},
                {"role": "user", "content": "네, 알려주세요"},
                {"role": "assistant", "content": "변수는 값을 저장하는 공간입니다."},
                {"role": "user", "content": "예제를 보여주실 수 있나요?"}
            ],
            "summary": "파이썬 기초 문법 학습",
            "keywords": ["파이썬", "변수", "문법"]
        }
        
        metadata = {"source": "web_chat", "platform": "desktop"}
        
        # 채팅 세션 완료 이벤트 처리
        result = await chat_listener.handle_chat_session_completed(
            user_id, chat_data, metadata
        )
        
        # 결과 검증
        assert result is not None
        assert result["event_type"] == "chat_completion"
        assert result["user_id"] == user_id
        assert result["session_id"] == "test_session"  # Mock에서 반환하는 값
        assert "update_timestamp" in result
        
        # ProfileProcessor의 메서드가 호출되었는지 확인
        mock_profile_processor.handle_chat_completion_event.assert_called_once()
        call_args = mock_profile_processor.handle_chat_completion_event.call_args
        assert call_args[1]["user_id"] == user_id
        # chat_data에 metadata가 병합되었는지 확인
        assert "source" in call_args[1]["chat_data"]
        assert "platform" in call_args[1]["chat_data"]

    @pytest.mark.asyncio
    async def test_handle_chat_session_completed_short_session(self, chat_listener, mock_profile_processor):
        """짧은 채팅 세션 처리 테스트 (프로필 업데이트 불필요)"""
        
        user_id = 456
        short_chat_data = {
            "session_id": "short_session",
            "duration": 20,  # 20초
            "message_count": 2,  # 메시지 2개만
            "messages": [
                {"role": "user", "content": "안녕"},
                {"role": "assistant", "content": "안녕하세요"}
            ]
        }
        
        # 짧은 세션 처리
        result = await chat_listener.handle_chat_session_completed(user_id, short_chat_data)
        
        # 결과 검증
        assert result is not None
        assert result["event_type"] == "chat_session_completed"
        assert result["profile_updated"] is False
        assert "Chat session too short" in result["reason"]
        
        # ProfileProcessor가 호출되지 않았는지 확인
        mock_profile_processor.handle_chat_completion_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_chat_session_completed_with_callback(self, chat_listener, mock_profile_processor):
        """콜백이 있는 채팅 세션 완료 처리 테스트"""
        
        user_id = 789
        chat_data = {
            "session_id": "callback_test",
            "duration": 600,
            "message_count": 10,
            "messages": [
                {"role": "user", "content": "질문이 있어요"},
                {"role": "assistant", "content": "무엇을 도와드릴까요?"},
                {"role": "user", "content": "코딩 관련 문의입니다"}
            ]
        }
        
        # 콜백 함수 Mock
        callback_mock = AsyncMock(return_value={"callback_executed": True})
        chat_listener.register_callback("chat_session_completed", callback_mock)
        
        # 채팅 세션 완료 처리
        result = await chat_listener.handle_chat_session_completed(user_id, chat_data)
        
        # 결과 검증
        assert result is not None
        assert "callback_result" in result
        assert result["callback_result"]["callback_executed"] is True
        
        # 콜백 호출 확인
        callback_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_update_profile_for_chat_validation(self, chat_listener):
        """채팅 프로필 업데이트 필요성 판단 테스트"""
        
        # 업데이트가 필요한 채팅 (충분한 메시지, 시간)
        good_chat = {
            "message_count": 10,
            "duration": 300,  # 5분
            "messages": [
                {"role": "user", "content": "첫 번째 질문"},
                {"role": "assistant", "content": "답변"},
                {"role": "user", "content": "두 번째 질문"},
                {"role": "assistant", "content": "답변"},
                {"role": "user", "content": "세 번째 질문"}
            ]
        }
        assert chat_listener._should_update_profile_for_chat(good_chat) is True
        
        # 메시지가 너무 적은 채팅
        few_messages_chat = {
            "message_count": 2,
            "duration": 300,
            "messages": [
                {"role": "user", "content": "안녕"},
                {"role": "assistant", "content": "안녕하세요"}
            ]
        }
        assert chat_listener._should_update_profile_for_chat(few_messages_chat) is False
        
        # 시간이 너무 짧은 채팅
        short_duration_chat = {
            "message_count": 5,
            "duration": 15,  # 15초
            "messages": [
                {"role": "user", "content": "질문1"},
                {"role": "assistant", "content": "답변1"},
                {"role": "user", "content": "질문2"}
            ]
        }
        assert chat_listener._should_update_profile_for_chat(short_duration_chat) is False
        
        # 사용자 메시지가 너무 적은 채팅
        few_user_messages_chat = {
            "message_count": 10,
            "duration": 300,
            "messages": [
                {"role": "user", "content": "단 하나의 사용자 메시지"},
                {"role": "assistant", "content": "답변1"},
                {"role": "assistant", "content": "답변2"},
                {"role": "assistant", "content": "답변3"}
            ]
        }
        assert chat_listener._should_update_profile_for_chat(few_user_messages_chat) is False

    @pytest.mark.asyncio
    async def test_handle_chat_session_completed_error_handling(self, chat_listener, mock_profile_processor):
        """채팅 세션 완료 처리 오류 처리 테스트"""
        
        user_id = 999
        chat_data = {
            "session_id": "error_session",
            "duration": 600,  # 10분 - 충분히 긴 세션
            "message_count": 15,  # 충분한 메시지 수
            "messages": [
                {"role": "user", "content": "테스트 메시지 1"},
                {"role": "assistant", "content": "응답 1"},
                {"role": "user", "content": "테스트 메시지 2"},
                {"role": "assistant", "content": "응답 2"},
                {"role": "user", "content": "테스트 메시지 3"}
            ]
        }
        
        # ProfileProcessor에서 오류 발생하도록 설정
        mock_profile_processor.handle_chat_completion_event.side_effect = Exception("Database connection failed")
        
        # 오류 상황에서 처리 실행
        result = await chat_listener.handle_chat_session_completed(user_id, chat_data)
        
        # 오류 결과 검증
        assert result is not None
        assert "error" in result
        assert result["event_type"] == "chat_session_completed"
        assert result["user_id"] == user_id
        assert "timestamp" in result
        
        # ProfileProcessor가 호출되었는지 확인
        mock_profile_processor.handle_chat_completion_event.assert_called_once()

    def test_register_callback(self, chat_listener):
        """콜백 등록 테스트"""
        
        def dummy_callback():
            return "callback_result"
        
        # 콜백 등록
        chat_listener.register_callback("test_event", dummy_callback)
        
        # 등록 확인
        assert "test_event" in chat_listener.event_callbacks
        assert chat_listener.event_callbacks["test_event"] == dummy_callback


class TestBookmarkEventListener:
    """BookmarkEventListener 기본 동작 테스트"""

    @pytest.fixture
    def mock_profile_processor(self):
        """Mock UserProfileProcessor"""
        mock_processor = AsyncMock(spec=UserProfileProcessor)
        mock_processor.handle_bookmark_event.return_value = {
            "event_type": "bookmark",
            "user_id": 123,
            "vector_strength": 0.9
        }
        return mock_processor

    @pytest.fixture
    def bookmark_listener(self, mock_profile_processor):
        """BookmarkEventListener 인스턴스"""
        return BookmarkEventListener(mock_profile_processor)

    @pytest.mark.asyncio
    async def test_handle_bookmark_created_success(self, bookmark_listener, mock_profile_processor):
        """북마크 생성 이벤트 처리 성공 테스트"""
        
        user_id = 123
        bookmark_data = {
            "title": "머신러닝 튜토리얼",
            "url": "https://example.com/ml-tutorial",
            "description": "기초부터 배우는 머신러닝",
            "category": "education",
            "tags": ["ML", "AI", "Python"]
        }
        
        # 북마크 생성 이벤트 처리
        result = await bookmark_listener.handle_bookmark_created(user_id, bookmark_data)
        
        # 결과 검증
        assert result is not None
        assert result["event_type"] == "bookmark"
        assert result["user_id"] == user_id
        assert result["vector_strength"] == 0.9
        
        # ProfileProcessor 호출 확인
        mock_profile_processor.handle_bookmark_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_update_profile_for_bookmark_change(self, bookmark_listener):
        """북마크 변경 프로필 업데이트 필요성 판단 테스트"""
        
        old_data = {
            "title": "옛날 제목",
            "description": "옛날 설명",
            "category": "old_category"
        }
        
        # 중요 필드 변경 - 업데이트 필요
        new_data_significant = {
            "title": "새로운 제목",  # 제목 변경
            "description": "옛날 설명",
            "category": "old_category"
        }
        assert bookmark_listener._should_update_profile_for_bookmark_change(
            new_data_significant, old_data
        ) is True
        
        # 중요하지 않은 필드만 변경 - 업데이트 불필요
        new_data_minor = {
            "title": "옛날 제목",
            "description": "옛날 설명",
            "category": "old_category",
            "last_accessed": "2024-01-01"  # 중요하지 않은 필드
        }
        assert bookmark_listener._should_update_profile_for_bookmark_change(
            new_data_minor, old_data
        ) is False


class TestChatEventListenerIntegration:
    """ChatEventListener 통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_chat_completion_workflow(self):
        """전체 채팅 완료 워크플로우 통합 테스트"""
        
        # 실제 UserProfileProcessor Mock (더 정교한)
        mock_processor = AsyncMock()
        mock_processor.handle_chat_completion_event.return_value = {
            "event_type": "chat_completion",
            "user_id": 123,
            "session_id": "integration_test",
            "vector_strength": 0.88,
            "updated_keywords": {"파이썬": 0.9, "웹개발": 0.85},
            "update_timestamp": datetime.now()
        }
        
        # ChatEventListener 생성
        chat_listener = ChatEventListener(mock_processor)
        
        # 복합적인 채팅 데이터
        complex_chat_data = {
            "session_id": "integration_test",
            "duration": 1800,  # 30분
            "message_count": 35,
            "topic": "web_development",
            "language": "korean",
            "messages": [
                {"role": "user", "content": "웹 개발을 시작하려면 무엇부터 배워야 하나요?"},
                {"role": "assistant", "content": "HTML, CSS, JavaScript 기초부터 시작하세요."},
                {"role": "user", "content": "파이썬으로도 웹 개발이 가능한가요?"},
                {"role": "assistant", "content": "네, Django나 Flask 같은 프레임워크를 사용할 수 있습니다."},
                {"role": "user", "content": "Django와 Flask 중 어떤 것을 추천하시나요?"}
            ],
            "summary": "웹 개발 학습 경로와 파이썬 웹 프레임워크에 대한 상담",
            "keywords": ["웹개발", "파이썬", "Django", "Flask", "HTML", "CSS", "JavaScript"]
        }
        
        # 메타데이터와 콜백 설정
        metadata = {"platform": "web", "device": "desktop", "user_agent": "Chrome"}
        
        callback_results = []
        async def test_callback(user_id, chat_data, result):
            callback_results.append({
                "user_id": user_id,
                "session_id": chat_data.get("session_id"),
                "result_vector_strength": result.get("vector_strength")
            })
            return {"callback_processed": True}
        
        chat_listener.register_callback("chat_session_completed", test_callback)
        
        # 전체 프로세스 실행
        user_id = 123
        result = await chat_listener.handle_chat_session_completed(
            user_id, complex_chat_data, metadata
        )
        
        # 통합 결과 검증
        assert result is not None
        assert result["event_type"] == "chat_completion"
        assert result["user_id"] == user_id
        assert result["session_id"] == "integration_test"
        assert result["vector_strength"] == 0.88
        assert "updated_keywords" in result
        assert "callback_result" in result
        
        # 콜백 실행 결과 확인
        assert len(callback_results) == 1
        assert callback_results[0]["user_id"] == user_id
        assert callback_results[0]["session_id"] == "integration_test"
        assert callback_results[0]["result_vector_strength"] == 0.88
        
        # ProfileProcessor 호출 확인
        mock_processor.handle_chat_completion_event.assert_called_once()
        call_args = mock_processor.handle_chat_completion_event.call_args
        
        # 메타데이터 병합 확인
        called_chat_data = call_args[1]["chat_data"]
        assert called_chat_data["platform"] == "web"
        assert called_chat_data["device"] == "desktop"
        assert called_chat_data["event_type"] == "chat_session_completed"
        assert called_chat_data["event_timestamp"] is not None
