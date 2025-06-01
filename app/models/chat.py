"""
채팅 모델 모듈

이 모듈은 채팅 관련 모델들을 정의합니다.

주요 기능:
- 채팅 세션 모델
- 채팅 메시지 모델
- 사용자 피드백 모델
- 벡터 저장소 모델 (PostgreSQL pgvector)
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlmodel import Field as SQLField, Relationship, SQLModel
from sqlalchemy import Column, Text, Index, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

# pgvector import 추가
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    print("⚠️ pgvector가 설치되지 않았습니다. 벡터 검색 기능이 비활성화됩니다.")

# 채팅 세션 모델
class ChatSessionBase(SQLModel):
    """채팅 세션 기본 스키마"""
    user_id: str = SQLField(index=True, max_length=255)
    title: Optional[str] = SQLField(default=None, max_length=500)
    session_type: str = SQLField(default="general", max_length=50)
    is_active: bool = SQLField(default=True)  # 세션 활성화 상태
    
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

# RAG 참조 모델
class RAGReferenceBase(SQLModel):
    """RAG 참조 기본 스키마"""
    message_id: UUID = SQLField(foreign_key="chat_messages.id")
    source_type: str = SQLField(max_length=50)  # 'vector', 'bookmark', 'web' 등
    source_id: str = SQLField(max_length=255)
    title: Optional[str] = SQLField(default=None, max_length=500)
    url: Optional[str] = SQLField(default=None, max_length=2000)
    snippet: Optional[str] = SQLField(default=None, sa_column=Column(Text))
    score: float = SQLField(default=0.0)  # 유사도 점수
    rank: int = SQLField(default=0)  # 검색 결과에서의 순위
    extra_metadata: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB)
    )

class RAGReference(RAGReferenceBase, table=True):
    """RAG 참조 테이블"""
    __tablename__ = "rag_references"
    
    # 기본 필드들 (직접 정의)
    id: UUID = SQLField(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    
    # 인덱스 정의
    __table_args__ = (
        Index("idx_rag_references_message", "message_id"),
        Index("idx_rag_references_source", "source_type", "source_id"),
        Index("idx_rag_references_score", "score"),
        Index("idx_rag_references_rank", "message_id", "rank"),
    )

class RAGReferenceCreate(RAGReferenceBase):
    """RAG 참조 생성 스키마"""

class RAGReferenceRead(RAGReferenceBase):
    """RAG 참조 조회 스키마"""
    id: UUID
    created_at: datetime

# 사용자 프로필 모델 (옵션)
class UserProfileBase(SQLModel):
    """사용자 프로필 기본 스키마"""
    user_id: str = SQLField(primary_key=True, max_length=255)
    display_name: Optional[str] = SQLField(default=None, max_length=100)
    preferences: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB)
    )
    chat_statistics: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB)
    )

class UserProfile(UserProfileBase, table=True):
    """사용자 프로필 테이블"""
    __tablename__ = "user_profiles"
    
    # 기본 필드들 (직접 정의)
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
        Index("idx_user_profiles_preferences_gin", "preferences", postgresql_using="gin"),
    )

class UserProfileCreate(UserProfileBase):
    """사용자 프로필 생성 스키마"""

class UserProfileRead(UserProfileBase):
    """사용자 프로필 조회 스키마"""
    created_at: datetime
    updated_at: Optional[datetime]

# 벡터 저장소 모델 (PostgreSQL pgvector 사용)
if PGVECTOR_AVAILABLE:
    class DocumentVectorBase(SQLModel):
        """문서 벡터 기본 스키마"""
        user_id: str = SQLField(index=True, max_length=255, description="사용자 ID")
        source_id: str = SQLField(max_length=255, description="원본 문서 ID (star_id, bookmark_id 등)")
        source_type: str = SQLField(max_length=50, description="소스 타입 (bookmark, web, document 등)")
        
        # 문서 내용
        chunk_index: int = SQLField(default=0, description="문서 내 청크 순서")
        content: str = SQLField(sa_column=Column(Text), description="텍스트 내용")
        content_hash: Optional[str] = SQLField(max_length=64, description="내용 해시값 (중복 방지)")
        
        # 임베딩 벡터 (1536차원 - OpenAI text-embedding-3-small)
        embedding: List[float] = SQLField(sa_column=Column(Vector(1536)), description="임베딩 벡터")
        
        # 메타데이터
        title: Optional[str] = SQLField(default=None, max_length=500, description="문서 제목")
        url: Optional[str] = SQLField(default=None, max_length=2000, description="원본 URL")
        keywords: Optional[List[str]] = SQLField(
            default=None,
            sa_column=Column(JSONB),
            description="추출된 키워드"
        )
        summary: Optional[str] = SQLField(default=None, sa_column=Column(Text), description="문서 요약")
        
        # 추가 메타데이터
        extra_metadata: Optional[Dict[str, Any]] = SQLField(
            default=None,
            sa_column=Column(JSONB),
            description="추가 메타데이터"
        )
        
        # 성능 지표
        embedding_model: str = SQLField(max_length=100, description="사용된 임베딩 모델")
        chunk_size: int = SQLField(default=1000, description="청크 크기")
        chunk_overlap: int = SQLField(default=200, description="청크 겹침")


    class DocumentVector(DocumentVectorBase, table=True):
        """문서 벡터 테이블"""
        __tablename__ = "document_vectors"
        
        # 기본 필드들
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
            # 벡터 유사도 검색용 인덱스 (cosine distance)
            Index("idx_document_vectors_embedding_cosine", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}),
            
            # 일반 검색용 인덱스
            Index("idx_document_vectors_user_source", "user_id", "source_type", "source_id"),
            Index("idx_document_vectors_content_hash", "content_hash"),
            Index("idx_document_vectors_keywords_gin", "keywords", postgresql_using="gin"),
            Index("idx_document_vectors_user_created", "user_id", "created_at"),
            
            # 복합 인덱스
            Index("idx_document_vectors_user_embedding", "user_id", "embedding", postgresql_using="ivfflat"),
        )


    class DocumentVectorCreate(DocumentVectorBase):
        """문서 벡터 생성 스키마"""
        pass


    class DocumentVectorRead(DocumentVectorBase):
        """문서 벡터 조회 스키마"""
        id: UUID
        created_at: datetime
        updated_at: Optional[datetime]


    class DocumentVectorUpdate(SQLModel):
        """문서 벡터 업데이트 스키마"""
        title: Optional[str] = None
        keywords: Optional[List[str]] = None
        summary: Optional[str] = None
        extra_metadata: Optional[Dict[str, Any]] = None


    # 벡터 검색 결과 스키마
    class VectorSearchResult(SQLModel):
        """벡터 검색 결과"""
        document: DocumentVectorRead
        similarity_score: float
        distance: float


    # 벡터 검색 요청 스키마  
    class VectorSearchRequest(SQLModel):
        """벡터 검색 요청"""
        query_embedding: List[float]
        user_id: Optional[str] = None
        source_types: Optional[List[str]] = None
        limit: int = SQLField(default=10, ge=1, le=100)
        similarity_threshold: float = SQLField(default=0.7, ge=0.0, le=1.0)
        include_metadata: bool = SQLField(default=True)

else:
    # pgvector가 없을 때는 더미 클래스들을 정의
    class DocumentVector:
        pass
    
    class DocumentVectorCreate:
        pass
    
    class DocumentVectorRead:
        pass
    
    class DocumentVectorUpdate:
        pass
    
    class VectorSearchResult:
        pass
    
    class VectorSearchRequest:
        pass 