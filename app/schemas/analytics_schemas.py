"""
분석 및 인사이트 API를 위한 스키마 정의
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ClusterQualityMetrics(BaseModel):
    """클러스터 품질 지표"""
    silhouette_score: float = Field(..., description="실루엣 스코어")
    intra_cluster_distance: float = Field(..., description="클러스터 내 거리")
    inter_cluster_distance: float = Field(..., description="클러스터 간 거리")
    cohesion_score: Optional[float] = Field(None, description="응집도 점수")


class ClusterCharacteristics(BaseModel):
    """클러스터 특성"""
    center_keywords: List[str] = Field(..., description="중심 키워드")
    top_categories: List[str] = Field(..., description="주요 카테고리")
    skill_level_distribution: Dict[str, float] = Field(..., description="스킬 레벨 분포")
    activity_pattern: Dict[str, Any] = Field(..., description="활동 패턴")


class ClusterInfo(BaseModel):
    """클러스터 정보"""
    cluster_id: int = Field(..., description="클러스터 ID")
    name: str = Field(..., description="클러스터 이름")
    size: int = Field(..., description="클러스터 크기")
    quality_metrics: ClusterQualityMetrics = Field(..., description="품질 지표")
    characteristics: Optional[ClusterCharacteristics] = Field(None, description="클러스터 특성")
    demographic_insights: Optional[Dict[str, Any]] = Field(None, description="인구통계학적 인사이트")


class ClusterRelationship(BaseModel):
    """클러스터 간 관계"""
    cluster_1: int = Field(..., description="첫 번째 클러스터 ID")
    cluster_2: int = Field(..., description="두 번째 클러스터 ID")
    similarity: float = Field(..., description="유사도")
    common_interests: List[str] = Field(..., description="공통 관심사")
    user_migration_rate: Optional[float] = Field(None, description="사용자 이동률")
    content_overlap: Optional[float] = Field(None, description="콘텐츠 중복도")


class TemporalAnalysis(BaseModel):
    """시간별 분석"""
    cluster_stability: float = Field(..., description="클러스터 안정성")
    migration_patterns: List[Dict[str, Any]] = Field(..., description="이동 패턴")
    emerging_clusters: List[Dict[str, Any]] = Field(..., description="새로운 클러스터")
    declining_clusters: Optional[List[Dict[str, Any]]] = Field(None, description="쇠퇴하는 클러스터")


class ClusterAnalysisResponse(BaseModel):
    """클러스터 분석 응답"""
    analysis_metadata: Dict[str, Any] = Field(..., description="분석 메타데이터")
    total_clusters: int = Field(..., description="총 클러스터 수")
    total_users_clustered: int = Field(..., description="클러스터링된 총 사용자 수")
    cluster_quality_score: float = Field(..., description="전체 클러스터 품질 점수")
    clusters: List[ClusterInfo] = Field(..., description="클러스터 목록")
    cluster_relationships: Optional[List[ClusterRelationship]] = Field(None, description="클러스터 간 관계")
    temporal_analysis: Optional[TemporalAnalysis] = Field(None, description="시간별 분석")
    strategic_insights: Optional[List[str]] = Field(None, description="전략적 인사이트")


class ProfileEvolution(BaseModel):
    """프로파일 진화"""
    initial_interests: List[str] = Field(..., description="초기 관심사")
    current_interests: List[str] = Field(..., description="현재 관심사")
    interest_expansion_rate: float = Field(..., description="관심사 확장률")
    specialization_trend: str = Field(..., description="전문화 경향")
    skill_progression: Optional[Dict[str, List[str]]] = Field(None, description="스킬 진전")


class ClusterJourney(BaseModel):
    """클러스터 여정"""
    period: str = Field(..., description="기간")
    cluster_id: int = Field(..., description="클러스터 ID")
    cluster_name: str = Field(..., description="클러스터 이름")
    duration_days: int = Field(..., description="지속 기간 (일)")
    stability_score: Optional[float] = Field(None, description="안정성 점수")
    transition_trigger: str = Field(..., description="전환 트리거")
    key_activities: Optional[List[str]] = Field(None, description="주요 활동")


class ContentConsumptionPatterns(BaseModel):
    """콘텐츠 소비 패턴"""
    preferred_content_types: List[str] = Field(..., description="선호 콘텐츠 유형")
    reading_behavior: Dict[str, Any] = Field(..., description="읽기 행동")
    temporal_patterns: Dict[str, Any] = Field(..., description="시간적 패턴")


class RecommendationResponsiveness(BaseModel):
    """추천 반응성"""
    overall_ctr: float = Field(..., description="전체 클릭률")
    preferred_reason_types: List[str] = Field(..., description="선호하는 추천 이유 유형")
    content_discovery_openness: float = Field(..., description="콘텐츠 발견 개방성")
    feedback_patterns: Dict[str, Any] = Field(..., description="피드백 패턴")
    recommendation_fatigue_indicators: Optional[Dict[str, Any]] = Field(None, description="추천 피로 지표")


class UserInsightResponse(BaseModel):
    """사용자 인사이트 응답"""
    user_id: int = Field(..., description="사용자 ID")
    analysis_metadata: Dict[str, Any] = Field(..., description="분석 메타데이터")
    profile_evolution: ProfileEvolution = Field(..., description="프로파일 진화")
    cluster_journey: List[ClusterJourney] = Field(..., description="클러스터 여정")
    content_consumption_patterns: ContentConsumptionPatterns = Field(..., description="콘텐츠 소비 패턴")
    recommendation_responsiveness: RecommendationResponsiveness = Field(..., description="추천 반응성")
    personalization_insights: Optional[List[str]] = Field(None, description="개인화 인사이트")
    predictions: Optional[Dict[str, Any]] = Field(None, description="예측")


class ContentMetrics(BaseModel):
    """콘텐츠 지표"""
    view_count: int = Field(..., description="조회수")
    save_rate: float = Field(..., description="저장률")
    share_rate: float = Field(..., description="공유율")
    avg_engagement_time: int = Field(..., description="평균 참여 시간 (초)")


class TopPerformingContent(BaseModel):
    """상위 성과 콘텐츠"""
    bookmark_id: str = Field(..., description="북마크 ID")
    title: str = Field(..., description="제목")
    performance_score: float = Field(..., description="성과 점수")
    metrics: ContentMetrics = Field(..., description="지표")
    cluster_appeal: Dict[str, float] = Field(..., description="클러스터별 어필도")


class CategoryInsight(BaseModel):
    """카테고리 인사이트"""
    category: str = Field(..., description="카테고리")
    total_content: int = Field(..., description="총 콘텐츠 수")
    avg_performance: float = Field(..., description="평균 성과")
    trending_topics: List[str] = Field(..., description="인기 주제")
    growth_trend: float = Field(..., description="성장 추세")


class ViralPatterns(BaseModel):
    """바이럴 패턴"""
    peak_sharing_hours: List[int] = Field(..., description="피크 공유 시간")
    viral_indicators: List[str] = Field(..., description="바이럴 지표")
    average_viral_lifespan_days: int = Field(..., description="평균 바이럴 수명 (일)")


class ContentPerformanceResponse(BaseModel):
    """콘텐츠 성과 응답"""
    analysis_period: str = Field(..., description="분석 기간")
    total_content_analyzed: int = Field(..., description="분석된 총 콘텐츠 수")
    top_performing_content: List[TopPerformingContent] = Field(..., description="상위 성과 콘텐츠")
    category_insights: List[CategoryInsight] = Field(..., description="카테고리 인사이트")
    viral_patterns: Optional[ViralPatterns] = Field(None, description="바이럴 패턴")


class VectorSpaceAnalysis(BaseModel):
    """벡터 공간 분석"""
    total_vectors: int = Field(..., description="총 벡터 수")
    dimension_effectiveness: float = Field(..., description="차원 효과성")
    cluster_separation: float = Field(..., description="클러스터 분리도")
    vector_density_distribution: Dict[str, float] = Field(..., description="벡터 밀도 분포")


class SimilarityThresholdOptimization(BaseModel):
    """유사도 임계값 최적화"""
    current_threshold: float = Field(..., description="현재 임계값")
    recommended_threshold: float = Field(..., description="권장 임계값")
    performance_gain_estimate: float = Field(..., description="성능 향상 추정")
    precision_recall_trade_off: Dict[str, float] = Field(..., description="정밀도-재현율 트레이드오프")


class EmbeddingQualityAssessment(BaseModel):
    """임베딩 품질 평가"""
    semantic_coherence: float = Field(..., description="의미적 일관성")
    domain_specialization: float = Field(..., description="도메인 특화")
    multilingual_consistency: float = Field(..., description="다국어 일관성")
    improvement_suggestions: List[str] = Field(..., description="개선 제안")


class SimilarityAnalysisResponse(BaseModel):
    """유사도 분석 응답"""
    vector_space_analysis: VectorSpaceAnalysis = Field(..., description="벡터 공간 분석")
    similarity_threshold_optimization: Optional[SimilarityThresholdOptimization] = Field(None, description="유사도 임계값 최적화")
    embedding_quality_assessment: Optional[EmbeddingQualityAssessment] = Field(None, description="임베딩 품질 평가")


class CurrentPerformance(BaseModel):
    """현재 성과"""
    overall_ctr: float = Field(..., description="전체 클릭률")
    precision_at_10: float = Field(..., description="상위 10개 정밀도")
    diversity_score: float = Field(..., description="다양성 점수")
    user_satisfaction: float = Field(..., description="사용자 만족도")


class OptimizationRecommendation(BaseModel):
    """최적화 권장사항"""
    parameter: str = Field(..., description="파라미터")
    current_value: float = Field(..., description="현재 값")
    recommended_value: float = Field(..., description="권장 값")
    expected_improvement: float = Field(..., description="예상 개선도")
    confidence: float = Field(..., description="신뢰도")


class ABTestInsights(BaseModel):
    """A/B 테스트 인사이트"""
    winning_variants: List[str] = Field(..., description="우승 변형")
    significant_improvements: Dict[str, float] = Field(..., description="유의미한 개선")
    user_segment_preferences: Dict[str, str] = Field(..., description="사용자 세그먼트 선호도")


class RecommendationOptimizationResponse(BaseModel):
    """추천 최적화 응답"""
    current_performance: CurrentPerformance = Field(..., description="현재 성과")
    optimization_recommendations: List[OptimizationRecommendation] = Field(..., description="최적화 권장사항")
    ab_test_insights: Optional[ABTestInsights] = Field(None, description="A/B 테스트 인사이트") 