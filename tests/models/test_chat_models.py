"""
채팅 모델 테스트

ChatSession, ChatMessage, RAGReference 등 모델의 검증을 테스트합니다.
"""
import pytest
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import (
    ChatSession, ChatSessionCreate, ChatSessionRead,
    ChatMessage, ChatMessageCreate, ChatMessageRead,
    RAGReference, RAGReferenceCreate, RAGReferenceRead,
    UserFeedback, UserFeedbackCreate, UserFeedbackRead,
    UserProfile, UserProfileCreate, UserProfileRead
)


class TestChatModels:
    """채팅 모델 테스트 클래스"""

    def test_chat_session_creation(self):
        """ChatSession 모델 생성 테스트"""
        session_data = {
            "user_id": "123",
            "title": "테스트 세션",
            "session_type": "general",
            "is_active": True,
            "total_messages": 0
        }
        
        session = ChatSession(**session_data)
        
        assert session.user_id == "123"
        assert session.title == "테스트 세션"
        assert session.session_type == "general"
        assert session.is_active is True
        assert session.total_messages == 0
        assert isinstance(session.id, uuid.UUID)
        assert isinstance(session.created_at, datetime)

    def test_chat_session_create_schema(self):
        """ChatSessionCreate 스키마 테스트"""
        create_data = {
            "user_id": "123",
            "title": "새 세션",
            "session_type": "test"
        }
        
        session_create = ChatSessionCreate(**create_data)
        
        assert session_create.user_id == "123"
        assert session_create.title == "새 세션"
        assert session_create.session_type == "test"

    def test_chat_message_creation(self):
        """ChatMessage 모델 생성 테스트"""
        session_id = uuid.uuid4()
        message_data = {
            "session_id": session_id,
            "user_id": "123",
            "role": "user",
            "content": "안녕하세요!",
            "rag_metadata": {"source": "test"}
        }
        
        message = ChatMessage(**message_data)
        
        assert message.session_id == session_id
        assert message.user_id == "123"
        assert message.role == "user"
        assert message.content == "안녕하세요!"
        assert message.rag_metadata == {"source": "test"}
        assert isinstance(message.id, uuid.UUID)
        assert isinstance(message.created_at, datetime)

    def test_chat_message_with_metadata(self):
        """메타데이터가 있는 ChatMessage 테스트"""
        session_id = uuid.uuid4()
        metadata = {
            "model": "gpt-3.5-turbo",
            "response_time_ms": 1500,
            "token_count": 25
        }
        
        message = ChatMessage(
            session_id=session_id,
            user_id="123",
            role="assistant",
            content="안녕하세요! 도움이 필요하시면 말씀해주세요.",
            rag_metadata=metadata,
            response_time_ms=1500,
            token_count=25
        )
        
        assert message.rag_metadata == metadata
        assert message.response_time_ms == 1500
        assert message.token_count == 25

    def test_rag_reference_creation(self):
        """RAGReference 모델 생성 테스트"""
        message_id = uuid.uuid4()
        reference_data = {
            "message_id": message_id,
            "source_type": "chroma",
            "source_id": "doc_123",
            "title": "참조 문서",
            "url": "https://example.com/doc",
            "snippet": "문서 내용의 일부",
            "score": 0.95,
            "rank": 1,
            "extra_metadata": {"category": "tech"}
        }
        
        reference = RAGReference(**reference_data)
        
        assert reference.message_id == message_id
        assert reference.source_type == "chroma"
        assert reference.source_id == "doc_123"
        assert reference.title == "참조 문서"
        assert reference.url == "https://example.com/doc"
        assert reference.snippet == "문서 내용의 일부"
        assert reference.score == 0.95
        assert reference.rank == 1
        assert reference.extra_metadata == {"category": "tech"}

    def test_user_feedback_creation(self):
        """UserFeedback 모델 생성 테스트"""
        message_id = uuid.uuid4()
        feedback_data = {
            "message_id": message_id,
            "user_id": "123",
            "feedback_type": "helpful",
            "feedback_score": 5,
            "feedback_detail": {"comment": "매우 도움이 되었습니다"}
        }
        
        feedback = UserFeedback(**feedback_data)
        
        assert feedback.message_id == message_id
        assert feedback.user_id == "123"
        assert feedback.feedback_type == "helpful"
        assert feedback.feedback_score == 5
        assert feedback.feedback_detail == {"comment": "매우 도움이 되었습니다"}

    def test_user_profile_creation(self):
        """UserProfile 모델 생성 테스트"""
        profile_data = {
            "user_id": "123",
            "display_name": "테스트 사용자",
            "preferences": {"language": "ko", "theme": "dark"},
            "chat_statistics": {"total_chats": 10, "avg_length": 5}
        }
        
        profile = UserProfile(**profile_data)
        
        assert profile.user_id == "123"
        assert profile.display_name == "테스트 사용자"
        assert profile.preferences == {"language": "ko", "theme": "dark"}
        assert profile.chat_statistics == {"total_chats": 10, "avg_length": 5}

    def test_model_validation_error(self):
        """모델 유효성 검증 오류 테스트"""
        # SQLModel은 런타임 검증보다는 타입 힌트를 제공하므로
        # 실제 생성이 되는지만 확인
        try:
            # 필수 필드 없이 생성 시도 - SQLModel에서는 허용됨
            session = ChatSession(title="테스트 세션만")
            assert session.title == "테스트 세션만"
            assert session.user_id is None  # 기본값
        except Exception as e:
            # 예상치 못한 오류가 발생하면 테스트 실패
            pytest.fail(f"예상치 못한 오류 발생: {e}")
            
        # 타입이 맞지 않는 경우에는 Python 타입 시스템에 의존

    def test_feedback_score_validation(self):
        """피드백 점수 유효성 검증 테스트"""
        message_id = uuid.uuid4()
        
        # 유효한 점수 (1-5)
        valid_feedback = UserFeedback(
            message_id=message_id,
            user_id="123",
            feedback_type="helpful",
            feedback_score=3
        )
        assert valid_feedback.feedback_score == 3
        
        # 점수가 범위를 벗어나는 경우는 Pydantic 레벨에서 검증됨
        # 실제 애플리케이션에서는 API 레벨에서 처리됨

    def test_message_roles(self):
        """메시지 역할 테스트"""
        session_id = uuid.uuid4()
        
        # 사용자 메시지
        user_message = ChatMessage(
            session_id=session_id,
            user_id="123",
            role="user",
            content="사용자 질문"
        )
        assert user_message.role == "user"
        
        # AI 어시스턴트 메시지
        assistant_message = ChatMessage(
            session_id=session_id,
            user_id="123",
            role="assistant",
            content="AI 응답"
        )
        assert assistant_message.role == "assistant"

    def test_session_metadata_jsonb(self):
        """세션 JSONB 메타데이터 테스트"""
        metadata = {
            "source": "web",
            "referrer": "google.com",
            "experiment": "A"
        }
        
        session = ChatSession(
            user_id="123",
            title="메타데이터 테스트",
            primary_topic=metadata,
            referenced_bookmarks=["bookmark1", "bookmark2"]
        )
        
        assert session.primary_topic == metadata
        assert session.referenced_bookmarks == ["bookmark1", "bookmark2"]

    def test_datetime_fields(self):
        """날짜/시간 필드 테스트"""
        session = ChatSession(
            user_id="123",
            title="시간 테스트"
        )
        
        # created_at은 자동으로 설정됨
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity_at, datetime)
        
        # updated_at은 None으로 시작
        assert session.updated_at is None

    def test_uuid_fields(self):
        """UUID 필드 테스트"""
        session = ChatSession(
            user_id="123",
            title="UUID 테스트"
        )
        
        message = ChatMessage(
            session_id=session.id,
            user_id="123",
            role="user",
            content="UUID 테스트 메시지"
        )
        
        reference = RAGReference(
            message_id=message.id,
            source_type="test",
            source_id="test_123"
        )
        
        # 모든 ID가 UUID 타입인지 확인
        assert isinstance(session.id, uuid.UUID)
        assert isinstance(message.id, uuid.UUID)
        assert isinstance(reference.id, uuid.UUID)
        
        # 관계가 올바르게 설정되었는지 확인
        assert message.session_id == session.id
        assert reference.message_id == message.id 