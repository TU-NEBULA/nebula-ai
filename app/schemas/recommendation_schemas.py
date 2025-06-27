"""
추천 시스템 API 스키마

추천 시스템의 요청 및 응답을 위한 Pydantic 스키마 모델들을 정의합니다.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from uuid import UUID


# ============ 기본 추천 관련 스키마 ============

class RecommendationItem(BaseModel):
    """개별 추천 아이템 스키마"""
    bookmark_id: str = Field(..., description="추천된 북마크 ID")
    title: str = Field(..., description="북마크 제목")
    url: str = Field(..., description="북마크 URL")
    score: float = Field(..., ge=0.0, le=1.0, description="추천 점수 (0.0-1.0)")
    reason_type: str = Field(..., description="추천 이유 타입")
    reason_details: Dict[str, Any] = Field(default_factory=dict, description="추천 이유 상세 정보")
    
    # 추가 메타데이터
    domain: Optional[str] = Field(None, description="도메인명")
    keywords: List[str] = Field(default_factory=list, description="관련 키워드")
    category: Optional[str] = Field(None, description="카테고리")
    published_at: Optional[datetime] = Field(None, description="게시 시간")
    summary: Optional[str] = Field(None, max_length=500, description="요약")


class ClusterInfo(BaseModel):
    """클러스터 정보 스키마"""
    cluster_id: int = Field(..., description="클러스터 ID")
    cluster_name: Optional[str] = Field(None, description="클러스터 이름")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="신뢰도 점수")
    member_count: int = Field(..., ge=0, description="멤버 수")
    key_characteristics: List[str] = Field(default_factory=list, description="주요 특성")


# ============ 전체적인 콘텐츠 추천 ============

class GeneralRecommendationRequest(BaseModel):
    """전체적인 콘텐츠 추천 요청 스키마"""
    user_id: int = Field(..., ge=1, description="추천 대상 사용자 ID")
    limit: int = Field(10, ge=1, le=50, description="추천 개수")
    category: Optional[str] = Field(None, description="특정 카테고리 필터")
    exclude_viewed: bool = Field(True, description="이미 본 콘텐츠 제외 여부")
    diversify: bool = Field(True, description="다양성 확보 적용 여부")
    time_range: Optional[str] = Field("week", description="추천 기간 범위 (day/week/month)")


class GeneralRecommendationResponse(BaseModel):
    """전체적인 콘텐츠 추천 응답 스키마"""
    recommendations: List[RecommendationItem] = Field(..., description="추천 아이템 목록")
    user_cluster_id: Optional[int] = Field(None, description="사용자 소속 클러스터 ID")
    cluster_description: Optional[str] = Field(None, description="클러스터 설명")
    total_recommendations: int = Field(..., ge=0, description="전체 추천 개수")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="생성 시간")
    
    # 추천 메타데이터
    algorithm_version: str = Field(default="v1.0", description="사용된 알고리즘 버전")
    personalization_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="개인화 점수")
    diversity_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="다양성 점수")


# ============ 검색어 기반 추천 ============

class SearchBasedRecommendationRequest(BaseModel):
    """검색어 기반 추천 요청 스키마"""
    user_id: int = Field(..., ge=1, description="추천 대상 사용자 ID")
    query: str = Field(..., min_length=1, max_length=500, description="검색어")
    limit: int = Field(10, ge=1, le=50, description="추천 개수")
    include_similar_queries: bool = Field(True, description="유사 검색어 포함 여부")
    boost_user_preferences: bool = Field(True, description="사용자 선호도 부스트 적용")
    
    # 컨텍스트 정보
    session_id: Optional[str] = Field(None, description="세션 ID")
    previous_queries: List[str] = Field(default_factory=list, description="이전 검색어들")


class SearchBasedRecommendationResponse(BaseModel):
    """검색어 기반 추천 응답 스키마"""
    recommendations: List[RecommendationItem] = Field(..., description="추천 아이템 목록")
    query_keywords: List[str] = Field(..., description="추출된 검색 키워드")
    expanded_concepts: List[str] = Field(default_factory=list, description="확장된 개념들")
    search_intent: Optional[str] = Field(None, description="검색 의도")
    total_recommendations: int = Field(..., ge=0, description="전체 추천 개수")
    
    # 검색 메타데이터
    processing_time_ms: Optional[float] = Field(None, description="처리 시간(ms)")
    similarity_threshold_used: Optional[float] = Field(None, description="사용된 유사도 임계값")


# ============ 클러스터 트렌드 ============

class TrendingKeyword(BaseModel):
    """트렌딩 키워드 스키마"""
    keyword: str = Field(..., description="키워드")
    score: float = Field(..., ge=0.0, le=1.0, description="트렌드 점수")
    growth: float = Field(..., description="성장률 (-1.0 ~ 1.0)")
    frequency: int = Field(..., ge=0, description="등장 빈도")


class ClusterTrend(BaseModel):
    """클러스터 트렌드 스키마"""
    cluster_id: int = Field(..., description="클러스터 ID")
    cluster_name: Optional[str] = Field(None, description="클러스터 이름")
    member_count: int = Field(..., ge=0, description="멤버 수")
    trending_keywords: List[TrendingKeyword] = Field(default_factory=list, description="트렌딩 키워드")
    popular_domains: List[str] = Field(default_factory=list, description="인기 도메인")
    activity_peak_hours: List[int] = Field(default_factory=list, description="활동 피크 시간대")
    
    # 클러스터 특성
    primary_interests: List[str] = Field(default_factory=list, description="주요 관심사")
    emerging_topics: List[str] = Field(default_factory=list, description="신규 등장 토픽")


class GlobalTrends(BaseModel):
    """글로벌 트렌드 스키마"""
    emerging_topics: List[str] = Field(default_factory=list, description="떠오르는 토픽")
    declining_topics: List[str] = Field(default_factory=list, description="하락하는 토픽")
    viral_content: List[Dict[str, Any]] = Field(default_factory=list, description="바이럴 콘텐츠")
    cross_cluster_trends: List[str] = Field(default_factory=list, description="클러스터 간 공통 트렌드")


class ClusterTrendsResponse(BaseModel):
    """클러스터 트렌드 응답 스키마"""
    cluster_trends: List[ClusterTrend] = Field(..., description="클러스터별 트렌드")
    global_trends: Optional[GlobalTrends] = Field(None, description="글로벌 트렌드")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="생성 시간")
    analysis_period: str = Field(..., description="분석 기간")


# ============ 추천 피드백 ============

class RecommendationFeedbackRequest(BaseModel):
    """추천 피드백 요청 스키마"""
    user_id: int = Field(..., ge=1, description="사용자 ID")
    recommendation_id: Optional[str] = Field(None, description="추천 ID")
    bookmark_id: str = Field(..., description="북마크 ID")
    action_type: str = Field(..., description="액션 타입 (clicked/saved/shared/dismissed/ignored)")
    
    # 타이밍 정보
    shown_at: datetime = Field(..., description="추천 표시 시간")
    action_at: datetime = Field(default_factory=datetime.utcnow, description="액션 수행 시간")
    
    # 컨텍스트 정보
    session_id: Optional[str] = Field(None, description="세션 ID")
    page_context: Optional[str] = Field(None, description="페이지 컨텍스트")
    recommendation_position: Optional[int] = Field(None, ge=0, description="추천 위치")
    
    # 추가 피드백
    explicit_rating: Optional[float] = Field(None, ge=1.0, le=5.0, description="명시적 평가 (1-5)")
    engagement_time: Optional[int] = Field(None, ge=0, description="콘텐츠 체류 시간(초)")


class RecommendationFeedbackResponse(BaseModel):
    """추천 피드백 응답 스키마"""
    feedback_id: str = Field(..., description="피드백 ID")
    processed: bool = Field(..., description="처리 완료 여부")
    impact_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="피드백 영향도")
    model_updated: bool = Field(default=False, description="모델 업데이트 여부")
    message: str = Field(..., description="처리 결과 메시지")


# ============ 사용자 클러스터 정보 ============

class ClusterHistoryEntry(BaseModel):
    """클러스터 이력 항목 스키마"""
    cluster_id: int = Field(..., description="클러스터 ID")
    period: str = Field(..., description="기간 (YYYY-MM)")
    duration_days: int = Field(..., ge=0, description="지속 기간(일)")
    transition_reason: Optional[str] = Field(None, description="이동 이유")


class UserClusterInfoResponse(BaseModel):
    """사용자 클러스터 정보 응답 스키마"""
    user_id: int = Field(..., description="사용자 ID")
    current_cluster: Optional[ClusterInfo] = Field(None, description="현재 클러스터 정보")
    cluster_position: Optional[str] = Field(None, description="클러스터 내 위치 (core/peripheral)")
    similar_users: List[int] = Field(default_factory=list, description="유사 사용자 ID들")
    cluster_history: List[ClusterHistoryEntry] = Field(default_factory=list, description="클러스터 이동 이력")
    
    # 클러스터 통계
    stability_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="클러스터 안정성 점수")
    influence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="클러스터 내 영향력")


# ============ 추천 성과 분석 ============

class PerformanceMetrics(BaseModel):
    """성과 지표 스키마"""
    click_through_rate: float = Field(..., ge=0.0, le=1.0, description="클릭률")
    save_rate: float = Field(..., ge=0.0, le=1.0, description="저장률")
    share_rate: float = Field(..., ge=0.0, le=1.0, description="공유율")
    diversity_score: float = Field(..., ge=0.0, le=1.0, description="다양성 점수")
    freshness_score: float = Field(..., ge=0.0, le=1.0, description="신선도 점수")
    
    # 사용자 만족도
    avg_explicit_rating: Optional[float] = Field(None, ge=1.0, le=5.0, description="평균 명시적 평가")
    avg_engagement_time: Optional[float] = Field(None, ge=0.0, description="평균 체류 시간(초)")


class ClusterPerformance(BaseModel):
    """클러스터별 성과 스키마"""
    cluster_id: int = Field(..., description="클러스터 ID")
    cluster_name: Optional[str] = Field(None, description="클러스터 이름")
    member_count: int = Field(..., ge=0, description="멤버 수")
    
    # 성과 지표
    ctr: float = Field(..., ge=0.0, le=1.0, description="클릭률")
    satisfaction: float = Field(..., ge=1.0, le=5.0, description="만족도")
    engagement_time: float = Field(..., ge=0.0, description="평균 체류 시간(초)")
    
    # 추천 특성
    preferred_recommendation_types: List[str] = Field(default_factory=list, description="선호 추천 타입")
    best_performing_categories: List[str] = Field(default_factory=list, description="고성과 카테고리")


class TrendAnalysis(BaseModel):
    """트렌드 분석 스키마"""
    weekly_change: float = Field(..., description="주간 변화율")
    monthly_change: float = Field(..., description="월간 변화율")
    improving_metrics: List[str] = Field(default_factory=list, description="개선되는 지표들")
    declining_metrics: List[str] = Field(default_factory=list, description="하락하는 지표들")
    
    # 예측 데이터
    predicted_next_week: Optional[Dict[str, float]] = Field(None, description="다음 주 예측 지표")


class RecommendationPerformanceResponse(BaseModel):
    """추천 성과 분석 응답 스키마"""
    overall_metrics: PerformanceMetrics = Field(..., description="전체 성과 지표")
    cluster_performance: List[ClusterPerformance] = Field(default_factory=list, description="클러스터별 성과")
    trend_analysis: TrendAnalysis = Field(..., description="트렌드 분석")
    
    # 메타데이터
    report_period: str = Field(..., description="분석 기간")
    total_recommendations_analyzed: int = Field(..., ge=0, description="분석된 추천 총 개수")
    data_completeness: float = Field(..., ge=0.0, le=1.0, description="데이터 완전성")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="생성 시간")


# ============ 에러 응답 스키마 ============

class ErrorResponse(BaseModel):
    """에러 응답 스키마"""
    error_code: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    details: Optional[Dict[str, Any]] = Field(None, description="에러 상세 정보")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="에러 발생 시간")


# ============ 배치 처리 스키마 ============

class BatchRecommendationRequest(BaseModel):
    """배치 추천 요청 스키마"""
    user_ids: List[int] = Field(..., min_items=1, max_items=1000, description="사용자 ID 목록")
    recommendation_type: str = Field(..., description="추천 타입 (general/trending/personalized)")
    limit_per_user: int = Field(10, ge=1, le=50, description="사용자당 추천 개수")
    
    # 필터링 옵션
    categories: List[str] = Field(default_factory=list, description="포함할 카테고리")
    exclude_categories: List[str] = Field(default_factory=list, description="제외할 카테고리")
    min_score_threshold: float = Field(0.5, ge=0.0, le=1.0, description="최소 점수 임계값")


class BatchRecommendationResponse(BaseModel):
    """배치 추천 응답 스키마"""
    total_users_processed: int = Field(..., ge=0, description="처리된 사용자 수")
    successful_recommendations: int = Field(..., ge=0, description="성공한 추천 수")
    failed_users: List[int] = Field(default_factory=list, description="실패한 사용자 ID")
    
    # 처리 통계
    processing_time_seconds: float = Field(..., ge=0.0, description="처리 시간(초)")
    average_recommendations_per_user: float = Field(..., ge=0.0, description="사용자당 평균 추천 수")
    
    # 배치 결과 접근 정보
    result_download_url: Optional[str] = Field(None, description="결과 다운로드 URL")
    expires_at: Optional[datetime] = Field(None, description="결과 만료 시간") 