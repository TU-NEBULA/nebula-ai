"""
채팅 스키마 테스트

Request/Response 스키마의 유효성 검증을 테스트합니다.
"""
import pytest
import uuid
from datetime import datetime
from pydantic import ValidationError

from app.schemas.chat import (
    ChatRequestModel,
    ChatSessionResponse, 
    ChatMessageResponse,
    ChatFeedbackRequest,
    ChatStreamRequest
)


class TestChatRequestSchemas:
    """채팅 요청 스키마 테스트"""

    def test_chat_request_basic(self):
        """기본 채팅 요청 테스트"""
        request_data = {
            "user_id": 123,
            "message": "안녕하세요!"
        }
        
        request = ChatRequestModel(**request_data)
        
        assert request.user_id == 123
        assert request.message == "안녕하세요!"
        assert request.session_id is None

    def test_chat_request_with_session_id(self):
        """세션 ID가 있는 채팅 요청 테스트"""
        session_id = str(uuid.uuid4())
        request_data = {
            "user_id": 123,
            "message": "기존 세션에서 대화",
            "session_id": session_id
        }
        
        request = ChatRequestModel(**request_data)
        
        assert request.user_id == 123
        assert request.message == "기존 세션에서 대화"
        assert request.session_id == session_id

    def test_chat_request_with_alias(self):
        """userId alias 테스트"""
        request_data = {
            "userId": 123,  # alias 사용
            "message": "안녕하세요!"
        }
        
        request = ChatRequestModel(**request_data)
        
        assert request.user_id == 123
        assert request.message == "안녕하세요!"

    def test_chat_request_validation_error(self):
        """채팅 요청 유효성 검증 오류 테스트"""
        # user_id 누락
        with pytest.raises(ValidationError):
            ChatRequestModel(message="안녕하세요!")
        
        # message 누락
        with pytest.raises(ValidationError):
            ChatRequestModel(user_id=123)

    def test_chat_request_user_id_types(self):
        """다양한 user_id 타입 테스트"""
        # 정수
        request1 = ChatRequestModel(user_id=123, message="테스트")
        assert request1.user_id == 123
        
        # 문자열로 된 숫자
        request2 = ChatRequestModel(user_id="456", message="테스트")
        assert request2.user_id == 456


class TestChatStreamSchemas:
    """채팅 스트림 스키마 테스트"""

    def test_chat_stream_request(self):
        """채팅 스트림 요청 테스트"""
        request_data = {
            "user_id": "123",
            "message": "안녕하세요!"
        }
        
        request = ChatStreamRequest(**request_data)
        
        assert request.user_id == "123"
        assert request.message == "안녕하세요!"
        assert request.session_id is None

    def test_chat_stream_request_with_session(self):
        """세션 ID가 있는 채팅 스트림 요청 테스트"""
        session_id = uuid.uuid4()
        request_data = {
            "user_id": "123",
            "message": "기존 세션에서 대화",
            "session_id": session_id
        }
        
        request = ChatStreamRequest(**request_data)
        
        assert request.user_id == "123"
        assert request.message == "기존 세션에서 대화"
        assert request.session_id == session_id


class TestChatResponseSchemas:
    """채팅 응답 스키마 테스트"""

    def test_chat_session_response(self):
        """채팅 세션 응답 테스트"""
        session_id = uuid.uuid4()
        response_data = {
            "id": session_id,
            "user_id": "123",
            "title": "테스트 세션",
            "session_type": "general",
            "total_messages": 5,
            "created_at": datetime.now(),
            "last_activity_at": datetime.now()
        }
        
        response = ChatSessionResponse(**response_data)
        
        assert response.id == session_id
        assert response.user_id == "123"
        assert response.title == "테스트 세션"
        assert response.session_type == "general"
        assert response.total_messages == 5
        assert isinstance(response.created_at, datetime)
        assert isinstance(response.last_activity_at, datetime)

    def test_chat_message_response(self):
        """채팅 메시지 응답 테스트"""
        message_id = uuid.uuid4()
        session_id = uuid.uuid4()
        
        response_data = {
            "id": message_id,
            "session_id": session_id,
            "user_id": "123",
            "role": "user",
            "content": "안녕하세요!",
            "response_time_ms": None,  # Optional 필드
            "created_at": datetime.now()
        }
        
        response = ChatMessageResponse(**response_data)
        
        assert response.id == message_id
        assert response.session_id == session_id
        assert response.user_id == "123"
        assert response.role == "user"
        assert response.content == "안녕하세요!"
        assert response.response_time_ms is None
        assert isinstance(response.created_at, datetime)

    def test_chat_message_response_with_response_time(self):
        """응답 시간이 있는 메시지 응답 테스트"""
        message_id = uuid.uuid4()
        session_id = uuid.uuid4()
        
        response_data = {
            "id": message_id,
            "session_id": session_id,
            "user_id": "123",
            "role": "assistant",
            "content": "AI 응답입니다.",
            "response_time_ms": 1500,
            "created_at": datetime.now()
        }
        
        response = ChatMessageResponse(**response_data)
        
        assert response.response_time_ms == 1500


class TestChatFeedbackSchemas:
    """채팅 피드백 스키마 테스트"""

    def test_chat_feedback_request(self):
        """채팅 피드백 요청 테스트"""
        message_id = uuid.uuid4()
        
        feedback_data = {
            "message_id": message_id,
            "feedback_type": "helpful",
            "feedback_score": 5,
            "comment": "매우 도움이 되었습니다"
        }
        
        feedback = ChatFeedbackRequest(**feedback_data)
        
        assert feedback.message_id == message_id
        assert feedback.feedback_type == "helpful"
        assert feedback.feedback_score == 5
        assert feedback.comment == "매우 도움이 되었습니다"

    def test_chat_feedback_score_validation(self):
        """피드백 점수 유효성 검증 테스트"""
        message_id = uuid.uuid4()
        
        # 유효한 점수 (1-5)
        valid_feedback = ChatFeedbackRequest(
            message_id=message_id,
            feedback_type="helpful",
            feedback_score=3
        )
        assert valid_feedback.feedback_score == 3
        
        # 잘못된 점수
        with pytest.raises(ValidationError):
            ChatFeedbackRequest(
                message_id=message_id,
                feedback_type="helpful",
                feedback_score=0  # 범위 밖
            )
        
        with pytest.raises(ValidationError):
            ChatFeedbackRequest(
                message_id=message_id,
                feedback_type="helpful",
                feedback_score=6  # 범위 밖
            )

    def test_chat_feedback_with_chunks(self):
        """청크 정보가 있는 피드백 테스트"""
        message_id = uuid.uuid4()
        
        feedback_data = {
            "message_id": message_id,
            "feedback_type": "partially_helpful",
            "feedback_score": 3,
            "helpful_chunks": ["chunk1", "chunk2"],
            "irrelevant_chunks": ["chunk3"]
        }
        
        feedback = ChatFeedbackRequest(**feedback_data)
        
        assert feedback.helpful_chunks == ["chunk1", "chunk2"]
        assert feedback.irrelevant_chunks == ["chunk3"]


class TestSchemaValidation:
    """스키마 유효성 검증 테스트"""

    def test_message_validation(self):
        """메시지 검증 테스트"""
        # 정상 메시지
        request = ChatRequestModel(user_id=123, message="안녕하세요!")
        assert request.message == "안녕하세요!"
        
        # 빈 메시지는 Pydantic에서 자동으로 허용됨 (필드가 있기만 하면)
        request_empty = ChatRequestModel(user_id=123, message="")
        assert request_empty.message == ""

    def test_feedback_type_validation(self):
        """피드백 타입 검증 테스트"""
        message_id = uuid.uuid4()
        
        # 유효한 피드백 타입들
        valid_types = ["helpful", "not_helpful", "partially_helpful"]
        
        for feedback_type in valid_types:
            feedback = ChatFeedbackRequest(
                message_id=message_id,
                feedback_type=feedback_type,
                feedback_score=3
            )
            assert feedback.feedback_type == feedback_type 