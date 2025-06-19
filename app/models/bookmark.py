"""
북마크 모델 모듈

이 모듈은 북마크 관련 SQLModel 테이블들을 정의합니다.
메시지 모델들은 별도의 message_models.py에 분리되어 있습니다.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from sqlmodel import Field, SQLModel, Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import DateTime, text

class BookmarkAIStatusBase(SQLModel):
    """북마크 AI 처리 상태 기본 스키마"""
    bookmark_id: UUID = Field(primary_key=True)
    user_id: str = Field(index=True, max_length=255)

    # 기본 정보 (캐시용)
    title: Optional[str] = Field(default=None, max_length=1000)
    url: Optional[str] = Field(default=None)
    domain: Optional[str] = Field(default=None, max_length=255)

    # AI 처리 상태
    processing_status: str = Field(default="pending", max_length=50)
    content_extracted: bool = Field(default=False)
    embeddings_created: bool = Field(default=False)
    keywords_extracted: bool = Field(default=False)

    # 처리 결과
    total_chunks: Optional[int] = Field(default=None)
    total_tokens: Optional[int] = Field(default=None)
    content_language: Optional[str] = Field(default=None, max_length=10)
    content_quality_score: Optional[float] = Field(default=None)

class BookmarkAIStatus(BookmarkAIStatusBase, table=True):
    """북마크 AI 처리 상태 테이블"""
    __tablename__ = "bookmark_ai_status"

    # 타임스탬프 필드만 추가 (primary key는 BookmarkAIStatusBase에서 상속)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"))
    )

    # 인덱스 정의
    __table_args__ = (
        Index("idx_bookmark_ai_user_status", "user_id", "processing_status"),
        Index("idx_bookmark_ai_domain", "domain"),
    )

class BookmarkAIStatusCreate(BookmarkAIStatusBase):
    """북마크 AI 처리 상태 생성 스키마"""

class BookmarkAIStatusRead(BookmarkAIStatusBase):
    """북마크 AI 처리 상태 조회 스키마"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class BookmarkAIStatusUpdate(SQLModel):
    """북마크 AI 처리 상태 업데이트 스키마"""
    processing_status: Optional[str] = None
    content_extracted: Optional[bool] = None
    embeddings_created: Optional[bool] = None
    keywords_extracted: Optional[bool] = None
    total_chunks: Optional[int] = None
    total_tokens: Optional[int] = None
    content_language: Optional[str] = None
    content_quality_score: Optional[float] = None

class DocumentChunkBase(SQLModel):
    """문서 청크 기본 스키마"""
    chunk_id: str = Field(primary_key=True, max_length=255)
    bookmark_id: UUID = Field(foreign_key="bookmark_ai_status.bookmark_id")
    chunk_index: int
    chunk_type: str = Field(max_length=50)  # 'title', 'content', 'summary'
    chunk_text_preview: Optional[str] = Field(default=None)

    # 키워드 및 분류
    extracted_keywords: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSONB)
    )
    content_category: Optional[str] = Field(default=None, max_length=100)
    importance_score: Optional[float] = Field(default=None)

class DocumentChunk(DocumentChunkBase, table=True):
    """문서 청크 테이블"""
    __tablename__ = "document_chunks"

    # 타임스탬프 필드 추가
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"))
    )

    # 인덱스 정의
    __table_args__ = (
        Index("idx_document_chunks_bookmark", "bookmark_id", "chunk_index"),
        Index("idx_document_chunks_keywords_gin", "extracted_keywords", postgresql_using="gin"),
    )

class DocumentChunkCreate(DocumentChunkBase):
    """문서 청크 생성 스키마"""

class DocumentChunkRead(DocumentChunkBase):
    """문서 청크 조회 스키마"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# 사용자 AI 프로필 모델 (실제 데이터베이스 구조에 맞춤)
class UserAIProfileBase(SQLModel):
    """사용자 AI 프로필 기본 스키마"""
    user_id: str = Field(primary_key=True, max_length=255)

    # 실제 데이터베이스 구조에 맞는 필드들
    preferred_search_domains: Optional[str] = Field(default=None)
    ai_interaction_style: Optional[str] = Field(default=None, max_length=255)
    current_interests: Optional[str] = Field(default=None)
    learning_preferences: Optional[str] = Field(default=None)
    notification_settings: Optional[str] = Field(default=None)
    profile_vector: Optional[str] = Field(default=None)

class UserAIProfile(UserAIProfileBase, table=True):
    """사용자 AI 프로필 테이블"""
    __tablename__ = "user_ai_profiles"

    # 타임스탬프 필드 추가
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"))
    )

    # 인덱스 정의 (실제 데이터베이스 구조에 맞춤)
    __table_args__ = (
        Index("idx_user_ai_profiles_interests", "current_interests"),
        Index("idx_user_ai_profiles_style", "ai_interaction_style"),
    )

class UserAIProfileCreate(UserAIProfileBase):
    """사용자 AI 프로필 생성 스키마"""

class UserAIProfileRead(UserAIProfileBase):
    """사용자 AI 프로필 조회 스키마"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class UserAIProfileUpdate(SQLModel):
    """사용자 AI 프로필 업데이트 스키마"""
    preferred_search_domains: Optional[str] = None
    ai_interaction_style: Optional[str] = None
    current_interests: Optional[str] = None
    learning_preferences: Optional[str] = None
    notification_settings: Optional[str] = None
    profile_vector: Optional[str] = None
