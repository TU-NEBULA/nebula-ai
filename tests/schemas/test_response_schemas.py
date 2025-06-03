"""
응답 스키마 테스트

BaseResponse와 채팅 관련 응답 스키마들의 유효성을 검증합니다.
"""
import pytest
import uuid
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.base import BaseResponse, ErrorResponse, IDResponse
from app.schemas.chat import (
    ChatSessionResponse,
    ChatMessageResponse,
    ChatSessionMessagesResponse,
    ChatSessionListResponse
)


class TestBaseResponseSchemas:
    """기본 응답 스키마 테스트"""

    def test_base_response_success(self):
        """성공 응답 스키마 테스트"""
        response_data = {
            "success": True,
            "message": "성공적으로 처리되었습니다",
            "data": {"test": "value"}
        }
        
        response = BaseResponse[dict](**response_data)
        
        assert response.success is True
        assert response.message == "성공적으로 처리되었습니다"
        assert response.data == {"test": "value"}

    def test_base_response_defaults(self):
        """기본값 응답 스키마 테스트"""
        response = BaseResponse[str](data="test data")
        
        assert response.success is True  # 기본값
        assert response.message == "Success"  # 기본값
        assert response.data == "test data"

    def test_error_response(self):
        """에러 응답 스키마 테스트"""
        error_data = {
            "success": False,
            "message": "에러가 발생했습니다",
            "error_code": "VALIDATION_ERROR",
            "details": {"field": "user_id", "issue": "required"}
        }
        
        response = ErrorResponse(**error_data)
        
        assert response.success is False
        assert response.message == "에러가 발생했습니다"
        assert response.error_code == "VALIDATION_ERROR"
        assert response.details == {"field": "user_id", "issue": "required"}

    def test_id_response(self):
        """ID 응답 스키마 테스트"""
        test_id = uuid.uuid4()
        response = IDResponse(id=test_id)
        
        assert response.id == test_id


class TestChatResponseSchemas:
    """채팅 응답 스키마 테스트"""

    def test_chat_session_response(self):
        """채팅 세션 응답 스키마 테스트"""
        session_data = {
            "id": str(uuid.uuid4()),
            "title": "테스트 세션",
            "session_type": "general",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "is_active": True
        }
        
        response = ChatSessionResponse(**session_data)
        
        assert response.id == session_data["id"]
        assert response.title == "테스트 세션"
        assert response.session_type == "general"
        assert response.is_active is True

    def test_chat_message_response(self):
        """채팅 메시지 응답 스키마 테스트"""
        message_data = {
            "id": str(uuid.uuid4()),
            "content": "안녕하세요!",
            "role": "user",
            "created_at": datetime.now(timezone.utc),
            "metadata": {"test": "data"}
        }
        
        response = ChatMessageResponse(**message_data)
        
        assert response.id == message_data["id"]
        assert response.content == "안녕하세요!"
        assert response.role == "user"
        assert response.metadata == {"test": "data"}

    def test_chat_message_response_without_metadata(self):
        """메타데이터 없는 채팅 메시지 응답 스키마 테스트"""
        message_data = {
            "id": str(uuid.uuid4()),
            "content": "메타데이터 없는 메시지",
            "role": "assistant",
            "created_at": datetime.now(timezone.utc)
        }
        
        response = ChatMessageResponse(**message_data)
        
        assert response.metadata is None

    def test_chat_session_messages_response(self):
        """채팅 세션 메시지 목록 응답 스키마 테스트"""
        session_id = str(uuid.uuid4())
        messages = [
            ChatMessageResponse(
                id=str(uuid.uuid4()),
                content="사용자 메시지",
                role="user",
                created_at=datetime.now(timezone.utc)
            ),
            ChatMessageResponse(
                id=str(uuid.uuid4()),
                content="AI 응답",
                role="assistant",
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        response = ChatSessionMessagesResponse(
            session_id=session_id,
            messages=messages
        )
        
        assert response.session_id == session_id
        assert len(response.messages) == 2
        assert response.messages[0].role == "user"
        assert response.messages[1].role == "assistant"

    def test_chat_session_list_response(self):
        """채팅 세션 목록 응답 스키마 테스트"""
        sessions = [
            ChatSessionResponse(
                id=str(uuid.uuid4()),
                title="세션 1",
                session_type="general",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                is_active=True
            ),
            ChatSessionResponse(
                id=str(uuid.uuid4()),
                title="세션 2", 
                session_type="support",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                is_active=False
            )
        ]
        
        response = ChatSessionListResponse(
            sessions=sessions,
            total=2
        )
        
        assert len(response.sessions) == 2
        assert response.total == 2
        assert response.sessions[0].title == "세션 1"
        assert response.sessions[1].session_type == "support"


class TestResponseValidation:
    """응답 스키마 유효성 검증 테스트"""

    def test_invalid_chat_session_response(self):
        """잘못된 채팅 세션 응답 스키마 테스트"""
        with pytest.raises(ValidationError):
            ChatSessionResponse(
                # id 누락
                title="테스트 세션",
                session_type="general",
                created_at="invalid_date",  # 잘못된 날짜 형식
                updated_at=datetime.now(timezone.utc),
                is_active=True
            )

    def test_invalid_message_role(self):
        """잘못된 메시지 역할 테스트 (현재는 검증 없음, 향후 enum 추가시 테스트)"""
        # 현재는 role에 대한 제약이 없으므로 통과
        response = ChatMessageResponse(
            id=str(uuid.uuid4()),
            content="테스트 메시지",
            role="invalid_role",  # 향후 enum으로 제한될 수 있음
            created_at=datetime.now(timezone.utc)
        )
        
        assert response.role == "invalid_role"

    def test_base_response_with_nested_schema(self):
        """중첩 스키마를 가진 BaseResponse 테스트"""
        session = ChatSessionResponse(
            id=str(uuid.uuid4()),
            title="중첩 테스트",
            session_type="general",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_active=True
        )
        
        response = BaseResponse[ChatSessionResponse](
            success=True,
            message="세션 조회 성공",
            data=session
        )
        
        assert response.success is True
        assert response.data.title == "중첩 테스트"
        assert isinstance(response.data, ChatSessionResponse) 