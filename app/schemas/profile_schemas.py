"""
User Profile API 응답 스키마

FastAPI 응답 모델 정의 - Type 안전성과 API 문서 자동 생성
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """비동기 작업 상태"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CacheStatus(str, Enum):
    """캐시 상태"""
    HIT = "HIT"
    MISS = "MISS"
    EXPIRED = "EXPIRED"


# === 프로필 조회 응답 ===
class UserProfileResponse(BaseModel):
    """사용자 프로필 조회 응답"""
    user_id: int = Field(..., gt=0, description="사용자 ID")
    profile_vector: Optional[List[float]] = Field(None, description="프로필 벡터")
    last_updated: datetime = Field(..., description="마지막 업데이트 시간")
    vector_strength: float = Field(..., ge=0.0, le=1.0, description="벡터 강도 (0.0-1.0)")
    completeness_score: int = Field(..., ge=0, le=100, description="프로필 완성도 점수 (0-100)")

    # 메타데이터 (선택적)
    created_at: Optional[datetime] = Field(None, description="프로필 생성 시간")
    vector_metadata: Optional[Dict[str, Any]] = Field(None, description="벡터 메타데이터")
    update_count: Optional[int] = Field(None, description="업데이트 횟수")
    last_similarity_update: Optional[datetime] = Field(None, description="마지막 유사도 계산 시간")

    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic 설정"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# === 유사 사용자 검색 응답 ===
class SimilarUserItem(BaseModel):
    """유사한 사용자 항목"""
    user_id: int = Field(..., gt=0, description="사용자 ID")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="유사도 점수 (0.0-1.0)")
    shared_interests: List[str] = Field(default=[], description="공통 관심사")
    last_updated: datetime = Field(..., description="프로필 마지막 업데이트")


class SearchCriteria(BaseModel):
    """검색 조건"""
    min_similarity: float = Field(..., ge=0.0, le=1.0, description="최소 유사도 임계값")
    limit: int = Field(..., gt=0, description="검색 결과 제한")


class SimilarUsersResponse(BaseModel):
    """유사 사용자 검색 응답"""
    user_id: int = Field(..., gt=0, description="기준 사용자 ID")
    similar_users: List[SimilarUserItem] = Field(..., description="유사한 사용자 목록")
    total_found: int = Field(..., ge=0, description="검색된 사용자 수")
    search_criteria: SearchCriteria = Field(..., description="검색 조건")


# === 개인화 추천 응답 ===
class RecommendationItem(BaseModel):
    """추천 항목"""
    id: int = Field(..., description="추천 ID")
    type: str = Field(..., description="추천 유형")
    title: str = Field(..., description="추천 제목")
    description: str = Field(..., description="추천 설명")
    score: float = Field(..., description="추천 점수 (0.0-1.0)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="추가 메타데이터")
    created_at: datetime = Field(..., description="추천 생성 시간")


class RecommendationsResponse(BaseModel):
    """개인화 추천 응답"""
    user_id: int = Field(..., description="사용자 ID")
    recommendations: List[RecommendationItem] = Field(..., description="추천 목록")
    generated_at: Optional[datetime] = Field(None, description="추천 생성 시간")
    cache_status: CacheStatus = Field(..., description="캐시 상태")
    refresh_requested: bool = Field(False, description="백그라운드 갱신 요청 여부")


# === 관심사 분석 응답 ===
class InterestsData(BaseModel):
    """관심사 데이터"""
    keywords: Dict[str, float] = Field(default={}, description="키워드별 가중치")
    topics: Dict[str, float] = Field(default={}, description="토픽별 가중치")
    categories: Dict[str, float] = Field(default={}, description="카테고리별 가중치")
    concepts: Dict[str, float] = Field(default={}, description="개념별 가중치")


class AnalysisMetadata(BaseModel):
    """분석 메타데이터"""
    last_updated: datetime = Field(..., description="마지막 분석 시간")
    vector_strength: float = Field(..., description="벡터 강도")
    data_sources: List[str] = Field(default=[], description="데이터 소스 목록")
    algorithm_version: str = Field(..., description="알고리즘 버전")


class InterestsAnalysisResponse(BaseModel):
    """관심사 분석 응답"""
    user_id: int = Field(..., description="사용자 ID")
    interests: InterestsData = Field(..., description="관심사 데이터")
    analysis_metadata: AnalysisMetadata = Field(..., description="분석 메타데이터")


# === 작업 상태 조회 응답 ===
class JobStatusResponse(BaseModel):
    """비동기 작업 상태 응답"""
    job_id: str = Field(..., description="작업 ID")
    status: JobStatus = Field(..., description="작업 상태")
    progress_percentage: int = Field(..., ge=0, le=100, description="진행률 (%)")
    started_at: datetime = Field(..., description="작업 시작 시간")
    estimated_completion: Optional[datetime] = Field(None, description="예상 완료 시간")
    result_data: Optional[Dict[str, Any]] = Field(None, description="작업 결과 데이터")
    error_message: Optional[str] = Field(None, description="오류 메시지")


# === 프로필 품질 지표 응답 ===
class QualityIndicators(BaseModel):
    """품질 지표"""
    has_vector: bool = Field(..., description="벡터 존재 여부")
    vector_dimension: int = Field(..., description="벡터 차원")
    has_metadata: bool = Field(..., description="메타데이터 존재 여부")
    is_recent: bool = Field(..., description="최근 업데이트 여부 (7일 이내)")


class ProfileMetricsResponse(BaseModel):
    """프로필 품질 지표 응답"""
    user_id: int = Field(..., description="사용자 ID")
    vector_strength: float = Field(..., description="벡터 강도")
    completeness_score: int = Field(..., description="완성도 점수")
    similar_users_count: int = Field(..., description="유사한 사용자 수")
    last_updated: datetime = Field(..., description="마지막 업데이트")
    data_freshness_hours: float = Field(..., description="데이터 신선도 (시간)")
    quality_indicators: QualityIndicators = Field(..., description="품질 지표")


# === 프로필 업데이트 요청 (MQ 메시지용) ===
class ActivityData(BaseModel):
    """활동 데이터 구조"""
    activity_type: str = Field(default="chat", description="활동 유형")
    content: str = Field(default="", description="활동 내용")
    timestamp: Optional[datetime] = Field(None, description="활동 시간")
    metadata: Dict[str, Any] = Field(default={}, description="추가 메타데이터")
    weight: float = Field(default=1.0, description="가중치")


class ProfileUpdateRequest(BaseModel):
    """프로필 업데이트 요청 (MQ 메시지)"""
    user_id: int = Field(..., description="사용자 ID")
    update_type: str = Field(..., description="업데이트 유형")
    incremental_update: bool = Field(True, description="점진적 업데이트 여부")
    new_interests: Optional[List[str]] = Field(None, description="새로운 관심사")
    remove_interests: Optional[List[str]] = Field(None, description="제거할 관심사")
    preference_adjustments: Optional[Dict[str, float]] = Field(None, description="선호도 조정")
    force_recalculation: bool = Field(False, description="강제 재계산 여부")
    source_data: Optional[List[ActivityData]] = Field(None, description="활동 데이터 리스트")


class ProfileRefreshRequest(BaseModel):
    """프로필 재생성 요청 (MQ 메시지)"""
    user_id: int = Field(..., description="사용자 ID")
    job_id: str = Field(..., description="작업 ID")
    force_full_recalculation: bool = Field(True, description="전체 재계산 강제 여부")
    use_algorithm_version: Optional[str] = Field(None, description="사용할 알고리즘 버전")
    include_historical_data: bool = Field(True, description="과거 데이터 포함 여부")
    recalculate_dependencies: List[str] = Field(default=[], description="재계산할 의존성")


class RecommendationRefreshRequest(BaseModel):
    """추천 갱신 요청 (MQ 메시지)"""
    user_id: int = Field(..., description="사용자 ID")
    categories: Optional[List[str]] = Field(None, description="갱신할 카테고리")
    priority: str = Field("normal", description="우선순위")
    use_research: bool = Field(False, description="연구 모델 사용 여부")


# === 공통 응답 ===
class APIResponse(BaseModel):
    """공통 API 응답"""
    success: bool = Field(..., description="성공 여부")
    message: str = Field(..., description="응답 메시지")
    data: Optional[Any] = Field(None, description="응답 데이터")
    error_code: Optional[str] = Field(None, description="오류 코드")
    timestamp: datetime = Field(default_factory=datetime.now, description="응답 시간")

    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic 설정"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
