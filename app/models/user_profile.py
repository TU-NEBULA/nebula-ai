# pylint: disable=too-few-public-methods
"""
사용자 프로필 및 추천 시스템 관련 모델

이 모듈은 사용자 프로필, 유사도, 추천, 트렌드 분석 등
추천 시스템에 필요한 모든 데이터 모델들을 정의합니다.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlmodel import Field as SQLField, SQLModel, Index
from sqlalchemy import Column, DateTime, text, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

# pgvector 지원 확인
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False

    # pgvector가 없을 때는 더미 Vector 타입 정의
    class Vector:
        """더미 Vector 클래스"""
        def __init__(self, dimensions):
            pass


class UserProfileBase(SQLModel):
    """사용자 프로필 기본 스키마"""
    user_id: int = SQLField(unique=True, index=True, description="사용자 ID")

    # 관심사 벡터 (1536차원 - OpenAI text-embedding-3-small)
    profile_vector: Optional[List[float]] = SQLField(
        default=None,
        sa_column=Column(Vector(1536)) if PGVECTOR_AVAILABLE else Column(JSONB),
        description="통합 관심사 벡터"
    )

    # 벡터 강도
    vector_strength: float = SQLField(default=0.0, ge=0.0, le=1.0, description="벡터 강도 (0.0-1.0)")

    # 프로필 완성도 (0-100)
    completeness_score: int = SQLField(default=0, ge=0, le=100, description="프로필 완성도 점수 (0-100)")

    # 키워드 분석
    keywords_frequency: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="키워드 빈도 분석 {keyword: {frequency: int, weight: float, last_seen: datetime}}"
    )

    # 카테고리 분포
    categories_distribution: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="카테고리 분포 {category: percentage}"
    )

    # 활동 패턴
    activity_patterns: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="활동 패턴 (시간대, 빈도, 세션 길이 등)"
    )

    # 클러스터링 정보
    similarity_cluster: Optional[int] = SQLField(
        default=None,
        index=True,
        description="소속 클러스터 ID"
    )

    # 사용자 설정
    preferences: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="추천 설정 및 개인화 옵션"
    )

    # 통계 정보
    total_bookmarks: int = SQLField(default=0, description="총 북마크 수")
    avg_session_duration: Optional[float] = SQLField(default=None, description="평균 세션 시간(분)")
    last_activity_at: Optional[datetime] = SQLField(default=None, description="마지막 활동 시간")


class UserProfile(UserProfileBase, table=True):
    """사용자 프로필 테이블"""
    __tablename__ = "user_profiles"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text('NOW()'))
    )

    # 인덱스 정의
    __table_args__ = (
        # 벡터 유사도 검색용 인덱스
        Index("idx_user_profiles_vector_cosine", "profile_vector",
              postgresql_using="ivfflat",
              postgresql_ops={"profile_vector": "vector_cosine_ops"})
              if PGVECTOR_AVAILABLE else None,

        # JSON 필드 검색용 인덱스
        Index("idx_user_profiles_keywords_gin", "keywords_frequency",
              postgresql_using="gin"),
        Index("idx_user_profiles_categories_gin", "categories_distribution",
              postgresql_using="gin"),
        Index("idx_user_profiles_preferences_gin", "preferences",
              postgresql_using="gin"),

        # 일반 검색용 인덱스
        Index("idx_user_profiles_cluster", "similarity_cluster"),
        Index("idx_user_profiles_activity", "last_activity_at"),
        Index("idx_user_profiles_bookmarks", "total_bookmarks"),
    )


class UserProfileCreate(UserProfileBase):
    """사용자 프로필 생성 스키마"""


class UserProfileRead(UserProfileBase):
    """사용자 프로필 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class UserProfileUpdate(SQLModel):
    """사용자 프로필 업데이트 스키마"""
    profile_vector: Optional[List[float]] = None
    vector_strength: Optional[float] = None
    completeness_score: Optional[int] = None
    keywords_frequency: Optional[Dict[str, Any]] = None
    categories_distribution: Optional[Dict[str, Any]] = None
    activity_patterns: Optional[Dict[str, Any]] = None
    similarity_cluster: Optional[int] = None
    preferences: Optional[Dict[str, Any]] = None
    total_bookmarks: Optional[int] = None
    avg_session_duration: Optional[float] = None
    last_activity_at: Optional[datetime] = None


class UserSimilarityBase(SQLModel):
    """사용자 유사도 기본 스키마"""
    user_id_1: int = SQLField(index=True, description="첫 번째 사용자 ID")
    user_id_2: int = SQLField(index=True, description="두 번째 사용자 ID")
    similarity_score: float = SQLField(
        ge=0.0, le=1.0, description="유사도 점수 (0.0 ~ 1.0)"
    )

    # 유사도 세부 정보
    similarity_factors: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="유사도 기여 요인 (keyword_overlap, category_overlap 등)"
    )

    cluster_id: Optional[int] = SQLField(default=None, description="공통 클러스터 ID")
    last_calculated: datetime = SQLField(
        default_factory=datetime.utcnow, description="마지막 계산 시간"
    )


class UserSimilarity(UserSimilarityBase, table=True):
    """사용자 유사도 테이블"""
    __tablename__ = "user_similarities"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text('NOW()'))
    )

    # 인덱스 정의
    __table_args__ = (
        # 복합 인덱스
        Index("idx_user_similarities_users", "user_id_1", "user_id_2"),
        Index("idx_user_similarities_score", "similarity_score"),
        Index("idx_user_similarities_cluster", "cluster_id"),
        Index("idx_user_similarities_calculated", "last_calculated"),

        # JSON 검색용 인덱스
        Index("idx_user_similarities_factors_gin", "similarity_factors",
              postgresql_using="gin"),
    )


class UserSimilarityCreate(UserSimilarityBase):
    """사용자 유사도 생성 스키마"""


class UserSimilarityRead(UserSimilarityBase):
    """사용자 유사도 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class RecommendationBase(SQLModel):
    """추천 기록 기본 스키마"""
    user_id: int = SQLField(index=True, description="대상 사용자 ID")
    recommended_url: str = SQLField(max_length=2000, description="추천된 URL")

    # 추천 메타데이터
    source_user_ids: Optional[List[int]] = SQLField(
        default=None,
        sa_column=Column(ARRAY(Integer)),
        description="추천 근거가 된 사용자들"
    )
    recommendation_score: float = SQLField(
        ge=0.0, le=1.0, description="추천 점수"
    )
    recommendation_type: str = SQLField(
        max_length=50,
        description="추천 타입 (trending, discovery, cross_category)"
    )

    # 추천 이유
    reasoning: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="추천 이유 상세 (keywords, categories, similar_users 등)"
    )

    # 사용자 반응
    user_action: Optional[str] = SQLField(
        default=None,
        max_length=20,
        description="사용자 액션 (clicked, saved, dismissed, ignored)"
    )
    shown_at: datetime = SQLField(
        default_factory=datetime.utcnow, description="추천 표시 시간"
    )
    action_at: Optional[datetime] = SQLField(
        default=None, description="사용자 액션 시간"
    )


class Recommendation(RecommendationBase, table=True):
    """추천 기록 테이블"""
    __tablename__ = "recommendations"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text('NOW()'))
    )

    # 인덱스 정의
    __table_args__ = (
        Index("idx_recommendations_user", "user_id"),
        Index("idx_recommendations_type_score", "recommendation_type",
              "recommendation_score"),
        Index("idx_recommendations_shown", "shown_at"),
        Index("idx_recommendations_action", "user_action"),
        Index("idx_recommendations_reasoning_gin", "reasoning",
              postgresql_using="gin"),
    )


class RecommendationCreate(RecommendationBase):
    """추천 기록 생성 스키마"""


class RecommendationRead(RecommendationBase):
    """추천 기록 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class RecommendationUpdate(SQLModel):
    """추천 기록 업데이트 스키마"""
    user_action: Optional[str] = None
    action_at: Optional[datetime] = None


class TrendAnalysisBase(SQLModel):
    """트렌드 분석 기본 스키마"""
    time_period: str = SQLField(
        max_length=20, description="분석 기간 (daily, weekly, monthly)"
    )

    # 트렌드 데이터
    trending_keywords: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="인기 키워드 및 점수"
    )
    trending_domains: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="인기 도메인 및 점수"
    )
    emerging_topics: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="신규 등장 토픽"
    )
    cluster_trends: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="클러스터별 트렌드 변화"
    )

    analysis_date: datetime = SQLField(
        default_factory=datetime.utcnow, description="분석 수행 날짜"
    )


class TrendAnalysis(TrendAnalysisBase, table=True):
    """트렌드 분석 테이블"""
    __tablename__ = "trend_analyses"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text('NOW()'))
    )

    # 인덱스 정의
    __table_args__ = (
        Index("idx_trend_analyses_period", "time_period", "analysis_date"),
        Index("idx_trend_analyses_date", "analysis_date"),
        Index("idx_trend_analyses_keywords_gin", "trending_keywords",
              postgresql_using="gin"),
        Index("idx_trend_analyses_domains_gin", "trending_domains",
              postgresql_using="gin"),
    )


class TrendAnalysisCreate(TrendAnalysisBase):
    """트렌드 분석 생성 스키마"""


class TrendAnalysisRead(TrendAnalysisBase):
    """트렌드 분석 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class ContextualRecommendationBase(SQLModel):
    """컨텍스트 추천 기본 스키마"""
    user_id: int = SQLField(index=True, description="사용자 ID")
    session_id: str = SQLField(
        max_length=100, index=True, description="세션 식별자"
    )
    trigger_bookmark_id: str = SQLField(
        max_length=255, description="추천을 유발한 북마크"
    )
    recommended_bookmark_id: str = SQLField(
        max_length=255, description="추천된 북마크"
    )

    context_type: str = SQLField(
        max_length=50,
        description="컨텍스트 타입 (same_session, related_content, deep_dive)"
    )
    relevance_score: float = SQLField(
        ge=0.0, le=1.0, description="관련성 점수"
    )

    context_factors: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="추천 근거 (키워드 매칭, 카테고리 등)"
    )

    user_action: Optional[str] = SQLField(
        default=None,
        max_length=20,
        description="사용자 액션 (clicked, saved, dismissed, ignored)"
    )
    shown_at: datetime = SQLField(
        default_factory=datetime.utcnow, description="추천 표시 시간"
    )
    action_at: Optional[datetime] = SQLField(
        default=None, description="사용자 액션 시간"
    )


class ContextualRecommendation(ContextualRecommendationBase, table=True):
    """컨텍스트 추천 테이블"""
    __tablename__ = "contextual_recommendations"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text('NOW()'))
    )

    # 인덱스 정의
    __table_args__ = (
        Index("idx_contextual_recommendations_user_session", "user_id",
              "session_id"),
        Index("idx_contextual_recommendations_trigger", "trigger_bookmark_id"),
        Index("idx_contextual_recommendations_recommended",
              "recommended_bookmark_id"),
        Index("idx_contextual_recommendations_type_score", "context_type",
              "relevance_score"),
        Index("idx_contextual_recommendations_factors_gin", "context_factors",
              postgresql_using="gin"),
    )


class ContextualRecommendationCreate(ContextualRecommendationBase):
    """컨텍스트 추천 생성 스키마"""


class ContextualRecommendationRead(ContextualRecommendationBase):
    """컨텍스트 추천 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class LearningPathBase(SQLModel):
    """학습 경로 기본 스키마"""
    topic: str = SQLField(max_length=200, index=True, description="주제명")

    difficulty_levels: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="beginner, intermediate, advanced 별 콘텐츠"
    )
    prerequisite_topics: Optional[List[str]] = SQLField(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="선행 학습 주제들"
    )
    learning_objectives: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="학습 목표 및 성과 지표"
    )

    expert_curated: bool = SQLField(
        default=False, description="전문가 큐레이션 여부"
    )
    community_rating: Optional[float] = SQLField(
        default=None, ge=0.0, le=5.0, description="커뮤니티 평가 점수"
    )
    estimated_duration: Optional[int] = SQLField(
        default=None, description="예상 학습 시간 (분)"
    )


class LearningPath(LearningPathBase, table=True):
    """학습 경로 테이블"""
    __tablename__ = "learning_paths"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text('NOW()'))
    )

    # 인덱스 정의
    __table_args__ = (
        Index("idx_learning_paths_topic", "topic"),
        Index("idx_learning_paths_curated_rating", "expert_curated",
              "community_rating"),
        Index("idx_learning_paths_duration", "estimated_duration"),
        Index("idx_learning_paths_levels_gin", "difficulty_levels",
              postgresql_using="gin"),
        Index("idx_learning_paths_prerequisites_gin", "prerequisite_topics",
              postgresql_using="gin"),
    )


class LearningPathCreate(LearningPathBase):
    """학습 경로 생성 스키마"""


class LearningPathRead(LearningPathBase):
    """학습 경로 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class UserLearningProgressBase(SQLModel):
    """사용자 학습 진도 기본 스키마"""
    user_id: int = SQLField(index=True, description="사용자 ID")
    topic: str = SQLField(max_length=200, index=True, description="주제명")

    current_level: str = SQLField(
        max_length=20, description="현재 학습 수준"
    )
    completed_bookmarks: Optional[List[str]] = SQLField(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="완료한 북마크들"
    )
    learning_pace: str = SQLField(
        max_length=20, description="학습 페이스 (slow, moderate, fast)"
    )
    preferred_content_types: Optional[List[str]] = SQLField(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="선호하는 콘텐츠 타입"
    )

    learning_goals: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="학습 목표 설정"
    )
    progress_percentage: float = SQLField(
        default=0.0, ge=0.0, le=1.0, description="진행률"
    )
    last_activity: Optional[datetime] = SQLField(
        default=None, description="마지막 학습 활동"
    )
    estimated_completion: Optional[datetime] = SQLField(
        default=None, description="예상 완료 시간"
    )


class UserLearningProgress(UserLearningProgressBase, table=True):
    """사용자 학습 진도 테이블"""
    __tablename__ = "user_learning_progress"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text('NOW()'))
    )

    # 인덱스 정의
    __table_args__ = (
        Index("idx_user_learning_progress_user_topic", "user_id", "topic"),
        Index("idx_user_learning_progress_level", "current_level"),
        Index("idx_user_learning_progress_pace", "learning_pace"),
        Index("idx_user_learning_progress_activity", "last_activity"),
        Index("idx_user_learning_progress_goals_gin", "learning_goals", postgresql_using="gin"),
    )


class UserLearningProgressCreate(UserLearningProgressBase):
    """사용자 학습 진도 생성 스키마"""


class UserLearningProgressRead(UserLearningProgressBase):
    """사용자 학습 진도 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class SessionContextBase(SQLModel):
    """세션 컨텍스트 기본 스키마"""
    session_id: str = SQLField(
        max_length=100, index=True, description="세션 식별자"
    )
    user_id: int = SQLField(index=True, description="사용자 ID")

    viewed_bookmarks: Optional[List[str]] = SQLField(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="세션 중 조회한 북마크들"
    )
    bookmark_sequence: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="북마크 조회 순서 및 시간"
    )
    inferred_topics: Optional[List[str]] = SQLField(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="세션에서 추론된 관심 주제들"
    )

    session_type: str = SQLField(
        max_length=50,
        description="세션 타입 (research, casual_browsing, problem_solving)"
    )
    session_duration: Optional[int] = SQLField(
        default=None, description="세션 지속 시간 (초)"
    )
    peak_interest_topics: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="세션 중 가장 관심 보인 주제들"
    )
    ended_at: Optional[datetime] = SQLField(
        default=None, description="세션 종료 시간"
    )


class SessionContext(SessionContextBase, table=True):
    """세션 컨텍스트 테이블"""
    __tablename__ = "session_contexts"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text('NOW()'))
    )

    # 인덱스 정의
    __table_args__ = (
        Index("idx_session_contexts_session_user", "session_id", "user_id"),
        Index("idx_session_contexts_type", "session_type"),
        Index("idx_session_contexts_duration", "session_duration"),
        Index("idx_session_contexts_ended", "ended_at"),
        Index("idx_session_contexts_sequence_gin", "bookmark_sequence",
              postgresql_using="gin"),
        Index("idx_session_contexts_topics_gin", "peak_interest_topics",
              postgresql_using="gin"),
    )


class SessionContextCreate(SessionContextBase):
    """세션 컨텍스트 생성 스키마"""


class SessionContextRead(SessionContextBase):
    """세션 컨텍스트 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
