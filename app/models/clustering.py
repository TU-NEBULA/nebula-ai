# pylint: disable=too-few-public-methods
"""
클러스터링 시스템 관련 모델

이 모듈은 사용자 클러스터링, 클러스터 특성 분석, 
클러스터 품질 평가 등에 필요한 모든 데이터 모델들을 정의합니다.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlmodel import Field as SQLField, SQLModel, Index
from sqlalchemy import Column, DateTime, text, Integer, String, Float
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


class UserClusterBase(SQLModel):
    """사용자 클러스터 기본 스키마"""
    cluster_id: int = SQLField(unique=True, index=True, description="클러스터 고유 ID")
    cluster_name: Optional[str] = SQLField(
        default=None, 
        max_length=255, 
        description="클러스터 이름 (자동 생성)"
    )
    
    # 클러스터 중심점 벡터 (1536차원 - OpenAI text-embedding-3-small)
    center_vector: Optional[List[float]] = SQLField(
        default=None,
        sa_column=Column(Vector(1536)) if PGVECTOR_AVAILABLE else Column(JSONB),
        description="클러스터 중심점 벡터"
    )
    
    # 클러스터 메타데이터
    size: int = SQLField(default=0, ge=0, description="클러스터 소속 사용자 수")
    density: Optional[float] = SQLField(
        default=None, 
        ge=0.0, 
        le=1.0, 
        description="클러스터 밀도 (0.0-1.0)"
    )
    radius: Optional[float] = SQLField(
        default=None, 
        ge=0.0, 
        description="클러스터 반경 (중심점에서 가장 먼 점까지의 거리)"
    )
    
    # 클러스터 특성
    dominant_categories: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="주요 카테고리 분포 {category: percentage}"
    )
    
    characteristic_keywords: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="특징적 키워드 {keyword: {weight: float, frequency: int}}"
    )
    
    # 클러스터 활동 패턴
    activity_patterns: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="클러스터 내 사용자들의 평균 활동 패턴"
    )
    
    # 클러스터 상태
    is_active: bool = SQLField(default=True, description="활성 클러스터 여부")
    stability_score: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        le=1.0,
        description="클러스터 안정성 점수 (시간에 따른 변화율 기반)"
    )


class UserCluster(UserClusterBase, table=True):
    """사용자 클러스터 테이블"""
    __tablename__ = "user_clusters"

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
        Index("idx_user_clusters_center_vector", "center_vector",
              postgresql_using="ivfflat",
              postgresql_ops={"center_vector": "vector_cosine_ops"})
              if PGVECTOR_AVAILABLE else None,

        # JSON 필드 검색용 인덱스
        Index("idx_user_clusters_categories_gin", "dominant_categories",
              postgresql_using="gin"),
        Index("idx_user_clusters_keywords_gin", "characteristic_keywords",
              postgresql_using="gin"),
        Index("idx_user_clusters_activity_gin", "activity_patterns",
              postgresql_using="gin"),

        # 일반 검색용 인덱스
        Index("idx_user_clusters_cluster_id", "cluster_id"),
        Index("idx_user_clusters_size", "size"),
        Index("idx_user_clusters_active", "is_active"),
        Index("idx_user_clusters_stability", "stability_score"),
    )


class UserClusterMembershipBase(SQLModel):
    """사용자 클러스터 멤버십 기본 스키마"""
    user_id: int = SQLField(index=True, description="사용자 ID")
    cluster_id: int = SQLField(index=True, description="클러스터 ID")
    
    # 멤버십 메타데이터
    distance_to_center: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        description="클러스터 중심점과의 거리"
    )
    confidence_score: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        le=1.0,
        description="클러스터 할당 신뢰도 점수"
    )
    
    # 이차 클러스터 정보 (사용자가 여러 클러스터에 근접할 때)
    secondary_clusters: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="근접한 다른 클러스터들 {cluster_id: distance}"
    )
    
    # 할당 이유
    assignment_reason: Optional[str] = SQLField(
        default=None,
        max_length=50,
        description="할당 방법 (kmeans, manual, migration)"
    )
    
    # 멤버십 변경 이력
    previous_cluster_id: Optional[int] = SQLField(
        default=None,
        description="이전 클러스터 ID (클러스터 이동 시)"
    )


class UserClusterMembership(UserClusterMembershipBase, table=True):
    """사용자 클러스터 멤버십 테이블"""
    __tablename__ = "user_cluster_memberships"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    assigned_at: datetime = SQLField(
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
        Index("idx_user_cluster_memberships_user_cluster", "user_id", "cluster_id"),
        Index("idx_user_cluster_memberships_cluster_distance", "cluster_id", "distance_to_center"),
        Index("idx_user_cluster_memberships_confidence", "confidence_score"),
        Index("idx_user_cluster_memberships_assigned_at", "assigned_at"),
        
        # JSON 검색용 인덱스
        Index("idx_user_cluster_memberships_secondary_gin", "secondary_clusters",
              postgresql_using="gin"),
    )


class ClusterKeywordsBase(SQLModel):
    """클러스터 키워드 기본 스키마"""
    cluster_id: int = SQLField(index=True, description="클러스터 ID")
    keyword: str = SQLField(max_length=255, index=True, description="키워드")
    
    # 키워드 통계
    weight: float = SQLField(
        ge=0.0,
        le=1.0,
        description="키워드 가중치 (클러스터 내 중요도)"
    )
    frequency: int = SQLField(
        default=0,
        ge=0,
        description="클러스터 내 키워드 출현 빈도"
    )
    rank: int = SQLField(
        ge=1,
        description="클러스터 내 키워드 순위"
    )
    
    # 키워드 분석
    tf_idf_score: Optional[float] = SQLField(
        default=None,
        description="TF-IDF 점수"
    )
    uniqueness_score: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        le=1.0,
        description="다른 클러스터 대비 고유성 점수"
    )
    
    # 키워드 메타데이터
    category: Optional[str] = SQLField(
        default=None,
        max_length=100,
        description="키워드가 속한 카테고리"
    )
    trend_score: Optional[float] = SQLField(
        default=None,
        description="키워드 트렌드 점수 (시간에 따른 변화)"
    )


class ClusterKeywords(ClusterKeywordsBase, table=True):
    """클러스터 키워드 테이블"""
    __tablename__ = "cluster_keywords"

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
        Index("idx_cluster_keywords_cluster_rank", "cluster_id", "rank"),
        Index("idx_cluster_keywords_cluster_weight", "cluster_id", "weight"),
        Index("idx_cluster_keywords_keyword_cluster", "keyword", "cluster_id"),
        
        # 단일 필드 인덱스
        Index("idx_cluster_keywords_tf_idf", "tf_idf_score"),
        Index("idx_cluster_keywords_uniqueness", "uniqueness_score"),
        Index("idx_cluster_keywords_category", "category"),
        Index("idx_cluster_keywords_trend", "trend_score"),
    )


class ClusterQualityMetricsBase(SQLModel):
    """클러스터 품질 지표 기본 스키마"""
    cluster_id: Optional[int] = SQLField(
        default=None,
        index=True,
        description="특정 클러스터 ID (전체 품질 측정 시 None)"
    )
    
    # 내부 평가 지표
    silhouette_score: Optional[float] = SQLField(
        default=None,
        ge=-1.0,
        le=1.0,
        description="실루엣 계수 (-1.0 ~ 1.0, 높을수록 좋음)"
    )
    calinski_harabasz_score: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        description="칼린스키-하라바즈 지수 (높을수록 좋음)"
    )
    davies_bouldin_score: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        description="데이비스-볼딘 지수 (낮을수록 좋음)"
    )
    
    # 클러스터 특성 지표
    intra_cluster_variance: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        description="클러스터 내 분산 (낮을수록 좋음)"
    )
    inter_cluster_distance: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        description="클러스터 간 거리 (높을수록 좋음)"
    )
    
    # 비즈니스 지표
    user_satisfaction_score: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        le=1.0,
        description="사용자 만족도 점수 (추천 성과 기반)"
    )
    recommendation_accuracy: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        le=1.0,
        description="추천 정확도"
    )
    
    # 안정성 지표
    stability_period_days: Optional[int] = SQLField(
        default=None,
        ge=1,
        description="안정성 측정 기간 (일수)"
    )
    member_retention_rate: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        le=1.0,
        description="멤버 유지율 (지정 기간 동안)"
    )
    
    # 측정 메타데이터
    measurement_type: str = SQLField(
        max_length=50,
        description="측정 타입 (daily, weekly, on_demand, post_clustering)"
    )
    total_users_measured: Optional[int] = SQLField(
        default=None,
        ge=0,
        description="측정에 포함된 총 사용자 수"
    )
    algorithm_version: Optional[str] = SQLField(
        default=None,
        max_length=20,
        description="사용된 클러스터링 알고리즘 버전"
    )


class ClusterQualityMetrics(ClusterQualityMetricsBase, table=True):
    """클러스터 품질 지표 테이블"""
    __tablename__ = "cluster_quality_metrics"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    measured_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )

    # 인덱스 정의
    __table_args__ = (
        # 시계열 분석용 인덱스
        Index("idx_cluster_quality_metrics_cluster_measured", "cluster_id", "measured_at"),
        Index("idx_cluster_quality_metrics_type_measured", "measurement_type", "measured_at"),
        
        # 품질 지표별 인덱스
        Index("idx_cluster_quality_metrics_silhouette", "silhouette_score"),
        Index("idx_cluster_quality_metrics_calinski", "calinski_harabasz_score"),
        Index("idx_cluster_quality_metrics_davies", "davies_bouldin_score"),
        Index("idx_cluster_quality_metrics_satisfaction", "user_satisfaction_score"),
        Index("idx_cluster_quality_metrics_accuracy", "recommendation_accuracy"),
        Index("idx_cluster_quality_metrics_retention", "member_retention_rate"),
        
        # 메타데이터 인덱스
        Index("idx_cluster_quality_metrics_algorithm", "algorithm_version"),
    )


# 클러스터링 작업 이력 모델
class ClusteringJobHistoryBase(SQLModel):
    """클러스터링 작업 이력 기본 스키마"""
    job_type: str = SQLField(
        max_length=50,
        description="작업 타입 (full_clustering, incremental_update, quality_check)"
    )
    algorithm_used: str = SQLField(
        max_length=50,
        description="사용된 알고리즘 (kmeans, hierarchical, etc.)"
    )
    
    # 작업 설정
    parameters_used: Optional[Dict[str, Any]] = SQLField(
        default=None,
        sa_column=Column(JSONB),
        description="사용된 클러스터링 파라미터"
    )
    
    # 작업 결과
    clusters_created: Optional[int] = SQLField(
        default=None,
        ge=0,
        description="생성된 클러스터 수"
    )
    users_processed: Optional[int] = SQLField(
        default=None,
        ge=0,
        description="처리된 사용자 수"
    )
    
    # 성능 지표
    execution_time_seconds: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        description="실행 시간 (초)"
    )
    memory_usage_mb: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        description="메모리 사용량 (MB)"
    )
    
    # 작업 상태
    status: str = SQLField(
        max_length=20,
        description="작업 상태 (running, completed, failed, cancelled)"
    )
    error_message: Optional[str] = SQLField(
        default=None,
        description="오류 메시지 (실패 시)"
    )
    
    # 결과 품질
    overall_quality_score: Optional[float] = SQLField(
        default=None,
        ge=0.0,
        le=1.0,
        description="전체 클러스터링 품질 점수"
    )


class ClusteringJobHistory(ClusteringJobHistoryBase, table=True):
    """클러스터링 작업 이력 테이블"""
    __tablename__ = "clustering_job_history"

    # 기본 ID 필드
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    started_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    completed_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )

    # 인덱스 정의
    __table_args__ = (
        # 작업 모니터링용 인덱스
        Index("idx_clustering_job_history_status", "status"),
        Index("idx_clustering_job_history_type_started", "job_type", "started_at"),
        Index("idx_clustering_job_history_algorithm", "algorithm_used"),
        
        # 성능 분석용 인덱스
        Index("idx_clustering_job_history_execution_time", "execution_time_seconds"),
        Index("idx_clustering_job_history_quality", "overall_quality_score"),
        Index("idx_clustering_job_history_started_at", "started_at"),
    )


# 스키마 클래스들 (CRUD 작업용)

class UserClusterCreate(UserClusterBase):
    """사용자 클러스터 생성 스키마"""


class UserClusterRead(UserClusterBase):
    """사용자 클러스터 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class UserClusterUpdate(SQLModel):
    """사용자 클러스터 업데이트 스키마"""
    cluster_name: Optional[str] = None
    center_vector: Optional[List[float]] = None
    size: Optional[int] = None
    density: Optional[float] = None
    radius: Optional[float] = None
    dominant_categories: Optional[Dict[str, Any]] = None
    characteristic_keywords: Optional[Dict[str, Any]] = None
    activity_patterns: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    stability_score: Optional[float] = None


class UserClusterMembershipCreate(UserClusterMembershipBase):
    """사용자 클러스터 멤버십 생성 스키마"""


class UserClusterMembershipRead(UserClusterMembershipBase):
    """사용자 클러스터 멤버십 조회 스키마"""
    id: UUID
    assigned_at: datetime
    updated_at: Optional[datetime]


class ClusterKeywordsCreate(ClusterKeywordsBase):
    """클러스터 키워드 생성 스키마"""


class ClusterKeywordsRead(ClusterKeywordsBase):
    """클러스터 키워드 조회 스키마"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class ClusterQualityMetricsCreate(ClusterQualityMetricsBase):
    """클러스터 품질 지표 생성 스키마"""


class ClusterQualityMetricsRead(ClusterQualityMetricsBase):
    """클러스터 품질 지표 조회 스키마"""
    id: UUID
    measured_at: datetime
    created_at: datetime


class ClusteringJobHistoryCreate(ClusteringJobHistoryBase):
    """클러스터링 작업 이력 생성 스키마"""


class ClusteringJobHistoryRead(ClusteringJobHistoryBase):
    """클러스터링 작업 이력 조회 스키마"""
    id: UUID
    started_at: datetime
    completed_at: Optional[datetime] 