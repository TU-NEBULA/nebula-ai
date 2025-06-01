"""
채팅 모델 모듈

이 모듈은 채팅 관련 모델들을 정의합니다.

주요 기능:
- 채팅 세션 모델
- 채팅 메시지 모델
- 사용자 피드백 모델
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlmodel import Field as SQLField, Relationship, SQLModel
from sqlalchemy import Column, Text, Index, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# 채팅 세션 모델
class ChatSessionBase(SQLModel):
    """채팅 세션 기본 스키마"""
    user_id: str = SQLField(index=True, max_length=255)
    title: Optional[str] = SQLField(default=None, max_length=500)
    session_type: str = SQLField(default="general", max_length=50)
    
    # JSONB 필드들
    primary_topic: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB)
    )
    referenced_bookmarks: Optional[List[str]] = SQLField(
        default=None,
        sa_column=Column(JSONB)
    )
    
    # 통계 필드
    total_messages: int = SQLField(default=0)
    avg_response_time_ms: Optional[int] = SQLField(default=None)
    last_activity_at: datetime = SQLField(default_factory=datetime.utcnow)

class ChatSession(ChatSessionBase, table=True):
    """채팅 세션 테이블"""
    __tablename__ = "chat_sessions"
    
    # 기본 필드들 (직접 정의)
    id: UUID = SQLField(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )
    
    # 관계 정의
    messages: List["ChatMessage"] = Relationship(back_populates="session")
    
    # 인덱스 정의
    __table_args__ = (
        Index("idx_chat_sessions_user_activity", "user_id", "last_activity_at"),
        Index("idx_chat_sessions_type", "session_type"),
    )

class ChatSessionCreate(ChatSessionBase):
    """채팅 세션 생성 스키마"""

class ChatSessionRead(ChatSessionBase):
    """채팅 세션 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

class ChatSessionUpdate(SQLModel):
    """채팅 세션 업데이트 스키마"""
    title: Optional[str] = None
    primary_topic: Optional[Dict[str, Any]] = None
    referenced_bookmarks: Optional[List[str]] = None

# 채팅 메시지 모델
class ChatMessageBase(SQLModel):
    """채팅 메시지 기본 스키마"""
    session_id: UUID = SQLField(foreign_key="chat_sessions.id")
    user_id: str = SQLField(index=True, max_length=255)
    role: str = SQLField(max_length=20)  # 'user' or 'assistant'
    content: str = SQLField(sa_column=Column(Text))
    
    # RAG 메타데이터
    rag_metadata: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB)
    )
    
    # 성능 추적
    response_time_ms: Optional[int] = SQLField(default=None)
    token_count: Optional[int] = SQLField(default=None)

class ChatMessage(ChatMessageBase, table=True):
    """채팅 메시지 테이블"""
    __tablename__ = "chat_messages"
    
    # 기본 필드들 (직접 정의)
    id: UUID = SQLField(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )
    
    # 관계 정의
    session: ChatSession = Relationship(back_populates="messages")
    
    # 인덱스 정의
    __table_args__ = (
        Index("idx_chat_messages_session_time", "session_id", "created_at"),
        Index("idx_chat_messages_user_role", "user_id", "role"),
        Index("idx_chat_messages_rag_metadata_gin", "rag_metadata", postgresql_using="gin"),
    )

class ChatMessageCreate(ChatMessageBase):
    """채팅 메시지 생성 스키마"""

class ChatMessageRead(ChatMessageBase):
    """채팅 메시지 조회 스키마"""
    id: UUID
    created_at: datetime

# 사용자 피드백 모델
class UserFeedbackBase(SQLModel):
    """사용자 피드백 기본 스키마"""
    message_id: UUID = SQLField(foreign_key="chat_messages.id")
    user_id: str = SQLField(index=True, max_length=255)
    feedback_type: str = SQLField(max_length=50)  # 'helpful', 'not_helpful', 'partially_helpful'
    feedback_score: int = SQLField(ge=1, le=5)
    feedback_detail: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB)
    )

class UserFeedback(UserFeedbackBase, table=True):
    """사용자 피드백 테이블"""
    __tablename__ = "user_feedback"
    
    # 기본 필드들 (직접 정의)
    id: UUID = SQLField(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )
    
    # 인덱스 정의
    __table_args__ = (
        Index("idx_user_feedback_message", "message_id"),
        Index("idx_user_feedback_user_type", "user_id", "feedback_type"),
        Index("idx_user_feedback_score", "feedback_score"),
    )

class UserFeedbackCreate(UserFeedbackBase):
    """사용자 피드백 생성 스키마"""

class UserFeedbackRead(UserFeedbackBase):
    """사용자 피드백 조회 스키마"""
    id: UUID
    created_at: datetime 