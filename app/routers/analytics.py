"""
분석 및 인사이트 API 라우터

클러스터 분석, 사용자 인사이트, 추천 성과 분석을 위한 추가 엔드포인트들을 제공합니다.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.schemas.analytics_schemas import (
    ClusterAnalysisResponse,
    UserInsightResponse,
    ContentPerformanceResponse,
    SimilarityAnalysisResponse,
    RecommendationOptimizationResponse
)
from app.services.clustering_service import ClusteringService
from app.services.analytics_service import AnalyticsService
from app.services.recommendation_engine import RecommendationEngine

router = APIRouter(
    prefix="/analytics",
    tags=["분석 및 인사이트"],
    responses={
        404: {"description": "리소스를 찾을 수 없음"},
        500: {"description": "서버 내부 오류"},
    },
)

analytics_service = AnalyticsService()
recommendation_engine = RecommendationEngine()

@router.get("/test")
async def test_analytics():
    """간단한 테스트 엔드포인트"""
    return {"status": "ok", "message": "Analytics router is working"}


@router.get(
    "/cluster-analysis",
    summary="클러스터 분석 대시보드",
    description="""
    전체 클러스터의 구성, 특성, 변화 추이를 분석하여 대시보드 정보를 제공합니다.
    
    **분석 내용:**
    - 클러스터별 사용자 분포 및 특성
    - 클러스터 간 유사도 및 거리 분석
    - 클러스터 품질 지표 (실루엣 스코어, 응집도)
    - 시간별 클러스터 변화 추이
    
    **활용 목적:**
    - 사용자 세그멘테이션 전략 수립
    - 클러스터링 알고리즘 성능 평가
    - 사용자 행동 패턴 인사이트 도출
    """,
    responses={
        200: {
            "description": "클러스터 분석 성공",
            "content": {
                "application/json": {
                    "example": {
                        "total_clusters": 8,
                        "total_users_clustered": 15420,
                        "cluster_quality_score": 0.73,
                        "clusters": [
                            {
                                "cluster_id": 1,
                                "name": "프론트엔드 개발자",
                                "size": 2340,
                                "center_keywords": ["react", "javascript", "css"],
                                "quality_metrics": {
                                    "silhouette_score": 0.68,
                                    "intra_cluster_distance": 0.34,
                                    "inter_cluster_distance": 0.89
                                },
                                "demographic_insights": {
                                    "avg_experience_level": "intermediate",
                                    "popular_frameworks": ["React", "Vue.js", "Angular"],
                                    "learning_pace": "fast"
                                }
                            }
                        ],
                        "cluster_relationships": [
                            {
                                "cluster_1": 1,
                                "cluster_2": 2,
                                "similarity": 0.42,
                                "common_interests": ["programming", "web development"]
                            }
                        ],
                        "temporal_analysis": {
                            "cluster_stability": 0.85,
                            "migration_patterns": ["1->2: 45 users", "3->1: 23 users"],
                            "emerging_clusters": [{"id": 9, "growth_rate": 0.23}]
                        }
                    }
                }
            }
        }
    }
)
async def get_cluster_analysis(
    include_temporal: bool = Query(True, description="시간별 변화 분석 포함"),
    include_relationships: bool = Query(True, description="클러스터 간 관계 분석 포함"),
    quality_threshold: float = Query(0.5, description="품질 지표 필터링 임계값", ge=0.0, le=1.0),
    session: AsyncSession = Depends(get_async_session)
):
    """
    전체 클러스터의 구성, 특성, 변화 추이를 분석하여 대시보드 정보를 제공합니다.
    
    ## 주요 기능
    - **클러스터 품질 평가**: 실루엣 스코어, 응집도, 분리도 등 클러스터링 품질 지표
    - **클러스터 특성 분석**: 각 클러스터의 고유 키워드, 카테고리, 사용자 특성
    - **시간별 변화 추적**: 클러스터 안정성, 사용자 이동 패턴, 새로운 클러스터 등장
    - **클러스터 간 관계**: 유사도, 사용자 이동 경로, 관심사 중복도 분석
    - **전략적 인사이트**: 사용자 세그멘테이션 및 타겟팅 전략 제안
    
    ## 분석 알고리즘
    1. **클러스터 품질 측정**: K-means 실루엣 스코어, DBSCAN 밀도 분석
    2. **특성 추출**: TF-IDF 기반 키워드 추출, 카테고리 분포 분석
    3. **시간 시계열 분석**: 클러스터 멤버십 변화, 안정성 지수 계산
    4. **관계 네트워크**: 클러스터 간 유사도 매트릭스, 이동 확률 계산
    5. **예측 모델링**: 클러스터 성장/쇠퇴 예측, 사용자 이동 예측
    
    ## 요청 예시
    ### 기본 클러스터 분석
    ```http
    GET /analytics/cluster-analysis
    ```
    
    ### 고품질 클러스터만 분석 (시간 분석 제외)
    ```http
    GET /analytics/cluster-analysis?quality_threshold=0.7&include_temporal=false
    ```
    
    ### 관계 분석 중심 조회
    ```http
    GET /analytics/cluster-analysis?include_relationships=true&include_temporal=false
    ```
    
    ## 응답 형식
    ```json
    {
        "analysis_metadata": {
            "analysis_timestamp": "2024-01-15T15:30:00Z",
            "total_clusters": 8,
            "total_users_clustered": 15420,
            "cluster_quality_score": 0.73,
            "analysis_parameters": {
                "algorithm": "k-means",
                "quality_threshold": 0.5,
                "temporal_window_days": 30
            }
        },
        "clusters": [
            {
                "cluster_id": 1,
                "name": "프론트엔드 개발자",
                "size": 2340,
                "quality_metrics": {
                    "silhouette_score": 0.68,
                    "intra_cluster_distance": 0.34,
                    "inter_cluster_distance": 0.89,
                    "cohesion_score": 0.76
                },
                "characteristics": {
                    "center_keywords": ["react", "javascript", "css", "frontend"],
                    "top_categories": ["web-development", "ui-ux", "javascript"],
                    "skill_level_distribution": {
                        "beginner": 0.25,
                        "intermediate": 0.45,
                        "advanced": 0.30
                    },
                    "activity_pattern": {
                        "peak_hours": [9, 14, 20],
                        "preferred_content_types": ["tutorials", "documentation"]
                    }
                },
                "demographic_insights": {
                    "avg_experience_level": "intermediate",
                    "popular_frameworks": ["React", "Vue.js", "Angular"],
                    "learning_pace": "fast",
                    "collaboration_tendency": "high"
                }
            }
        ],
        "cluster_relationships": [
            {
                "cluster_1": 1,
                "cluster_2": 2,
                "similarity": 0.42,
                "common_interests": ["programming", "web development"],
                "user_migration_rate": 0.08,
                "content_overlap": 0.35
            }
        ],
        "temporal_analysis": {
            "cluster_stability": 0.85,
            "migration_patterns": [
                {"from": 1, "to": 2, "users": 45, "reason": "skill_advancement"},
                {"from": 3, "to": 1, "users": 23, "reason": "interest_shift"}
            ],
            "emerging_clusters": [
                {"id": 9, "growth_rate": 0.23, "predicted_size": 450}
            ],
            "declining_clusters": [
                {"id": 6, "decline_rate": -0.15, "risk_level": "medium"}
            ]
        },
        "strategic_insights": [
            "클러스터 1(프론트엔드)과 2(백엔드)의 높은 이동률 - 풀스택 콘텐츠 확대 권장",
            "클러스터 9의 급성장 - AI/ML 관련 콘텐츠 큐레이션 강화 필요"
        ]
    }
    ```
    
    Args:
        include_temporal: 시간별 변화 분석 포함 여부 (기본값: True)
        include_relationships: 클러스터 간 관계 분석 포함 여부 (기본값: True)
        quality_threshold: 품질 지표 필터링 임계값 (0.0-1.0, 기본값: 0.5)
        
    Returns:
        ClusterAnalysisResponse: 종합적인 클러스터 분석 결과
        
    Raises:
        422: 잘못된 quality_threshold 값 (0.0-1.0 범위 외)
        500: 클러스터 분석 실패시
        
    Note:
        - 클러스터 분석은 매일 새벽 2시에 자동 업데이트
        - 품질 임계값이 높을수록 더 안정적인 클러스터만 반환
        - 시간 분석은 최근 30일 데이터를 기반으로 수행
        - 개인정보 보호를 위해 개별 사용자 식별 정보는 제외
    """
    
    try:
        # 매우 간단한 테스트 응답
        return {
            "status": "success",
            "data": {
                "total_clusters": 2,
                "total_users_clustered": 6,
                "clusters": [
                    {
                        "cluster_id": "0",
                        "name": "클러스터 0",
                        "size": 4
                    },
                    {
                        "cluster_id": "1", 
                        "name": "클러스터 1",
                        "size": 2
                    }
                ]
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"클러스터 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/user-insight/{user_id}",
    response_model=UserInsightResponse,
    summary="개별 사용자 심층 분석",
    description="""
    특정 사용자의 행동 패턴, 관심사 변화, 추천 반응성을 심층 분석합니다.
    
    **분석 영역:**
    - 사용자 프로파일 진화 과정
    - 클러스터 이동 패턴 및 이유
    - 콘텐츠 소비 패턴 분석
    - 추천 시스템과의 상호작용 히스토리
    
    **인사이트 제공:**
    - 개인화 추천 최적화 방향
    - 관심사 확장 가능성 예측
    - 사용자 만족도 개선 포인트
    """,
    responses={
        200: {
            "description": "사용자 인사이트 분석 성공",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": 12345,
                        "profile_evolution": {
                            "initial_interests": ["python", "data science"],
                            "current_interests": ["machine learning", "deep learning", "pytorch"],
                            "interest_expansion_rate": 0.34,
                            "specialization_trend": "increasing"
                        },
                        "cluster_journey": [
                            {
                                "period": "2024-01",
                                "cluster_id": 2,
                                "cluster_name": "데이터 분석가",
                                "duration_days": 60,
                                "transition_trigger": "ml_content_increase"
                            },
                            {
                                "period": "2024-03",
                                "cluster_id": 5,
                                "cluster_name": "ML 엔지니어",
                                "duration_days": 45,
                                "transition_trigger": "deep_learning_focus"
                            }
                        ],
                        "content_patterns": {
                            "preferred_content_types": ["tutorials", "research_papers"],
                            "reading_pace": "thorough",
                            "peak_activity_hours": [9, 14, 21],
                            "seasonal_trends": {
                                "spring": "algorithm_focus",
                                "summer": "practical_projects"
                            }
                        },
                        "recommendation_responsiveness": {
                            "overall_ctr": 0.156,
                            "preferred_reason_types": ["similar_users", "trending"],
                            "content_discovery_openness": 0.78,
                            "feedback_frequency": "regular"
                        }
                    }
                }
            }
        },
        404: {"description": "사용자를 찾을 수 없음"}
    }
)
async def get_user_insight(
    user_id: int = Path(..., description="분석할 사용자 ID", ge=1),
    analysis_depth: str = Query("standard", description="분석 깊이 (basic/standard/deep)"),
    time_range_months: int = Query(6, description="분석 기간 (개월)", ge=1, le=24),
    session: AsyncSession = Depends(get_async_session)
) -> UserInsightResponse:
    """
    특정 사용자의 행동 패턴, 관심사 변화, 추천 반응성을 심층 분석합니다.
    
    ## 주요 기능
    - **프로파일 진화 분석**: 시간에 따른 사용자 관심사 및 행동 패턴 변화 추적
    - **클러스터 여정 추적**: 클러스터 이동 이력 및 각 이동의 원인 분석
    - **콘텐츠 소비 패턴**: 선호하는 콘텐츠 유형, 읽기 패턴, 활동 시간대 분석
    - **추천 반응성 평가**: 추천 시스템에 대한 반응도 및 선호하는 추천 유형
    - **개인화 최적화**: 사용자별 맞춤 추천 전략 및 개선 방향 제안
    
    ## 분석 깊이별 제공 정보
    1. **Basic**: 기본 프로파일, 현재 클러스터, 최근 활동 패턴
    2. **Standard**: 관심사 변화, 클러스터 이동, 추천 반응성 분석
    3. **Deep**: 예측 모델링, 개인화 최적화, 상세 행동 분석
    
    ## 분석 알고리즘
    1. **시계열 분석**: 관심사 키워드 변화, 활동 패턴 추이
    2. **클러스터 이동 분석**: 이동 패턴, 안정성, 예측 모델
    3. **행동 패턴 마이닝**: 콘텐츠 소비, 상호작용, 세션 분석
    4. **추천 성과 분석**: CTR, 만족도, 피드백 패턴
    5. **예측 모델링**: 미래 관심사, 클러스터 이동 예측
    
    ## 요청 예시
    ### 기본 사용자 인사이트 (6개월)
    ```http
    GET /analytics/user-insight/12345
    ```
    
    ### 심화 분석 (12개월)
    ```http
    GET /analytics/user-insight/12345?analysis_depth=deep&time_range_months=12
    ```
    
    ### 기본 분석 (3개월)
    ```http
    GET /analytics/user-insight/12345?analysis_depth=basic&time_range_months=3
    ```
    
    ## 응답 형식
    ```json
    {
        "user_id": 12345,
        "analysis_metadata": {
            "analysis_depth": "standard",
            "time_range_months": 6,
            "analysis_timestamp": "2024-01-15T15:30:00Z",
            "data_completeness": 0.94
        },
        "profile_evolution": {
            "initial_interests": ["python", "data science", "statistics"],
            "current_interests": ["machine learning", "deep learning", "pytorch", "nlp"],
            "interest_expansion_rate": 0.34,
            "specialization_trend": "increasing",
            "skill_progression": {
                "beginner_topics": ["python basics", "pandas"],
                "intermediate_topics": ["scikit-learn", "data visualization"],
                "advanced_topics": ["transformers", "pytorch lightning"]
            }
        },
        "cluster_journey": [
            {
                "period": "2024-01",
                "cluster_id": 2,
                "cluster_name": "데이터 분석가",
                "duration_days": 60,
                "stability_score": 0.78,
                "transition_trigger": "ml_content_increase",
                "key_activities": ["pandas tutorials", "matplotlib guides"]
            },
            {
                "period": "2024-03",
                "cluster_id": 5,
                "cluster_name": "ML 엔지니어",
                "duration_days": 45,
                "stability_score": 0.91,
                "transition_trigger": "deep_learning_focus",
                "key_activities": ["pytorch tutorials", "neural networks"]
            }
        ],
        "content_consumption_patterns": {
            "preferred_content_types": ["tutorials", "research_papers", "documentation"],
            "reading_behavior": {
                "reading_pace": "thorough",
                "completion_rate": 0.87,
                "bookmark_to_read_ratio": 0.45
            },
            "temporal_patterns": {
                "peak_activity_hours": [9, 14, 21],
                "most_active_days": ["tuesday", "wednesday", "thursday"],
                "seasonal_trends": {
                    "spring": "algorithm_focus",
                    "summer": "practical_projects",
                    "fall": "research_papers",
                    "winter": "year_end_review"
                }
            }
        },
        "recommendation_responsiveness": {
            "overall_ctr": 0.156,
            "preferred_reason_types": ["similar_users", "trending", "cluster_popular"],
            "content_discovery_openness": 0.78,
            "feedback_patterns": {
                "feedback_frequency": "regular",
                "positive_feedback_rate": 0.82,
                "content_saving_behavior": "selective"
            },
            "recommendation_fatigue_indicators": {
                "declining_ctr": false,
                "repetitive_content_complaints": 0,
                "diversity_preference": 0.73
            }
        },
        "personalization_insights": [
            "사용자는 실용적인 튜토리얼을 선호하며 이론보다 실습 중심 콘텐츠에 높은 반응",
            "ML 분야에서 빠른 학습 진전을 보이고 있어 중급-고급 콘텐츠 비중 확대 권장",
            "저녁 시간대(21시) 활동이 활발하여 해당 시간 푸시 알림 최적화 필요"
        ],
        "predictions": {
            "next_likely_cluster": {"id": 7, "name": "AI 연구자", "probability": 0.34},
            "emerging_interests": ["computer vision", "llm fine-tuning"],
            "content_engagement_forecast": 0.85
        }
    }
    ```
    
    Args:
        user_id: 분석할 사용자 ID (1 이상)
        analysis_depth: 분석 깊이 (basic/standard/deep, 기본값: standard)
        time_range_months: 분석 기간 개월수 (1-24, 기본값: 6)
        
    Returns:
        UserInsightResponse: 사용자 심층 분석 결과 및 인사이트
        
    Raises:
        404: 사용자 정보를 찾을 수 없음
        422: 잘못된 analysis_depth 또는 time_range_months 값
        500: 사용자 인사이트 분석 실패시
        
    Note:
        - Deep 분석은 계산 비용이 높아 응답 시간이 길어질 수 있음
        - 신규 사용자(가입 1개월 미만)는 제한된 인사이트만 제공
        - 개인정보 보호를 위해 민감한 개인 식별 정보는 제외
        - 예측 정보는 참고용이며 실제 사용자 행동과 차이가 있을 수 있음
    """
    
    try:
        insight = await analytics_service.generate_user_insight(
            session=session,
            user_id=user_id,
            analysis_depth=analysis_depth,
            time_range_months=time_range_months
        )
        
        if not insight:
            raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다")
        
        return insight
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"사용자 인사이트 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/content-performance",
    response_model=ContentPerformanceResponse,
    summary="콘텐츠 성과 분석",
    description="""
    플랫폼 내 콘텐츠들의 성과를 다각도로 분석하여 인사이트를 제공합니다.
    
    **분석 지표:**
    - 조회수, 저장률, 공유율 등 참여 지표
    - 클러스터별 콘텐츠 선호도 차이
    - 콘텐츠 생명주기 및 바이럴 패턴
    - 추천 알고리즘 기여도 분석
    
    **활용 방안:**
    - 인기 콘텐츠 패턴 파악
    - 콘텐츠 큐레이션 전략 개선
    - 추천 알고리즘 최적화
    """,
    responses={
        200: {
            "description": "콘텐츠 성과 분석 성공",
            "content": {
                "application/json": {
                    "example": {
                        "analysis_period": "2024-01-01 to 2024-01-31",
                        "total_content_analyzed": 15420,
                        "top_performing_content": [
                            {
                                "bookmark_id": "bm123",
                                "title": "2024 AI 트렌드 전망",
                                "performance_score": 0.94,
                                "metrics": {
                                    "view_count": 15670,
                                    "save_rate": 0.23,
                                    "share_rate": 0.08,
                                    "avg_engagement_time": 420
                                },
                                "cluster_appeal": {
                                    "ai_engineers": 0.89,
                                    "data_scientists": 0.76,
                                    "product_managers": 0.45
                                }
                            }
                        ],
                        "category_insights": [
                            {
                                "category": "machine_learning",
                                "total_content": 2340,
                                "avg_performance": 0.67,
                                "trending_topics": ["transformers", "llm", "computer_vision"],
                                "growth_trend": 0.15
                            }
                        ],
                        "viral_patterns": {
                            "peak_sharing_hours": [10, 15, 19],
                            "viral_indicators": ["rapid_initial_growth", "cross_cluster_appeal"],
                            "average_viral_lifespan_days": 7
                        }
                    }
                }
            }
        }
    }
)
async def get_content_performance(
    start_date: Optional[datetime] = Query(None, description="분석 시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="분석 종료 날짜"),
    category: Optional[str] = Query(None, description="특정 카테고리 분석"),
    min_interactions: int = Query(10, description="최소 상호작용 수", ge=1),
    include_viral_analysis: bool = Query(True, description="바이럴 패턴 분석 포함"),
    session: AsyncSession = Depends(get_async_session)
) -> ContentPerformanceResponse:
    """콘텐츠 성과 및 트렌드 분석"""
    
    # 기본 날짜 설정 (지정되지 않은 경우)
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    try:
        performance = await analytics_service.analyze_content_performance(
            session=session,
            start_date=start_date,
            end_date=end_date,
            category=category,
            min_interactions=min_interactions,
            include_viral_analysis=include_viral_analysis
        )
        
        return performance
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"콘텐츠 성과 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/similarity-analysis",
    response_model=SimilarityAnalysisResponse,
    summary="유사도 분석 및 최적화",
    description="""
    사용자-콘텐츠, 사용자-사용자, 콘텐츠-콘텐츠 간 유사도 패턴을 분석합니다.
    
    **분석 영역:**
    - 유사도 계산 알고리즘 성능 평가
    - 유사도 임계값 최적화 분석
    - 벡터 공간에서의 클러스터 분포
    - 유사도 기반 추천 정확도 평가
    
    **최적화 제안:**
    - 임베딩 모델 성능 개선 방향
    - 유사도 가중치 조정 권장사항
    - 차원 축소 효과 분석
    """,
    responses={
        200: {
            "description": "유사도 분석 성공",
            "content": {
                "application/json": {
                    "example": {
                        "vector_space_analysis": {
                            "total_vectors": 1234567,
                            "dimension_effectiveness": 0.78,
                            "cluster_separation": 0.65,
                            "vector_density_distribution": {
                                "sparse_regions": 0.23,
                                "dense_regions": 0.45,
                                "optimal_regions": 0.32
                            }
                        },
                        "similarity_threshold_optimization": {
                            "current_threshold": 0.7,
                            "recommended_threshold": 0.73,
                            "performance_gain_estimate": 0.08,
                            "precision_recall_trade_off": {
                                "precision_at_current": 0.82,
                                "recall_at_current": 0.67,
                                "precision_at_recommended": 0.86,
                                "recall_at_recommended": 0.64
                            }
                        },
                        "embedding_quality_assessment": {
                            "semantic_coherence": 0.81,
                            "domain_specialization": 0.74,
                            "multilingual_consistency": 0.69,
                            "improvement_suggestions": [
                                "domain_specific_fine_tuning",
                                "korean_language_optimization"
                            ]
                        }
                    }
                }
            }
        }
    }
)
async def get_similarity_analysis(
    analysis_type: str = Query("comprehensive", description="분석 타입 (vector_space/threshold/embedding)"),
    sample_size: int = Query(10000, description="분석 샘플 크기", ge=1000, le=100000),
    include_optimization: bool = Query(True, description="최적화 제안 포함"),
    session: AsyncSession = Depends(get_async_session)
) -> SimilarityAnalysisResponse:
    """
    사용자-콘텐츠, 사용자-사용자, 콘텐츠-콘텐츠 간 유사도 패턴을 분석합니다.
    
    ## 주요 기능
    - **벡터 공간 분석**: 임베딩 벡터의 분포 및 클러스터 분리도 평가
    - **유사도 임계값 최적화**: 추천 정확도 향상을 위한 최적 임계값 탐색
    - **임베딩 품질 평가**: 의미적 일관성 및 도메인 특화 성능 측정
    - **차원 효율성 분석**: 벡터 차원 수와 성능 간의 트레이드오프 분석
    - **다국어 일관성 검증**: 한국어-영어 임베딩 간 의미적 일관성 평가
    
    ## 분석 유형
    1. **vector_space**: 벡터 공간 분포 및 밀도 분석
    2. **threshold**: 유사도 임계값 최적화 분석
    3. **embedding**: 임베딩 모델 품질 및 성능 평가
    4. **comprehensive**: 전체 영역 종합 분석 (기본값)
    
    ## 최적화 제안 영역
    1. **임계값 조정**: 정밀도-재현율 균형 최적화
    2. **임베딩 개선**: 도메인 특화 파인튜닝 방향
    3. **차원 축소**: 성능 유지하며 효율성 개선
    4. **다국어 대응**: 한국어 특화 최적화 방안
    5. **벡터 정규화**: 유사도 계산 안정성 개선
    
    ## 요청 예시
    ### 종합 유사도 분석 (샘플 10,000개)
    ```http
    GET /analytics/similarity-analysis
    ```
    
    ### 임계값 최적화만 분석 (대용량 샘플)
    ```http
    GET /analytics/similarity-analysis?analysis_type=threshold&sample_size=50000
    ```
    
    ### 임베딩 품질 평가 (최적화 제안 제외)
    ```http
    GET /analytics/similarity-analysis?analysis_type=embedding&include_optimization=false
    ```
    
    Args:
        analysis_type: 분석 타입 (vector_space/threshold/embedding/comprehensive)
        sample_size: 분석 샘플 크기 (1,000-100,000, 기본값: 10,000)
        include_optimization: 최적화 제안 포함 여부 (기본값: True)
        
    Returns:
        SimilarityAnalysisResponse: 유사도 분석 결과 및 최적화 제안
        
    Raises:
        422: 잘못된 analysis_type 또는 sample_size 값
        500: 유사도 분석 실패시
        
    Note:
        - 대용량 샘플 분석시 응답 시간이 길어질 수 있음
        - 임베딩 품질 평가는 OpenAI API 호출이 포함되어 비용 발생
        - 최적화 제안은 A/B 테스트를 통한 검증 후 적용 권장
        - 벡터 공간 분석은 메모리 사용량이 높아 서버 리소스 고려 필요
    """
    
    try:
        analysis = await analytics_service.analyze_similarity_patterns(
            session=session,
            analysis_type=analysis_type,
            sample_size=sample_size,
            include_optimization=include_optimization
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"유사도 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.post(
    "/recommendation-optimization",
    response_model=RecommendationOptimizationResponse,
    summary="추천 알고리즘 최적화 분석",
    description="""
    현재 추천 알고리즘의 성능을 분석하고 최적화 방안을 제시합니다.
    
    **분석 요소:**
    - A/B 테스트 결과 분석
    - 하이퍼파라미터 최적화 제안
    - 알고리즘 조합 성능 비교
    - 사용자 피드백 패턴 분석
    
    **최적화 영역:**
    - 가중치 조정 권장사항
    - 필터링 임계값 최적화
    - 다양성/정확도 균형 조정
    - 실시간 학습 전략 개선
    """,
    responses={
        200: {
            "description": "추천 최적화 분석 성공",
            "content": {
                "application/json": {
                    "example": {
                        "current_performance": {
                            "overall_ctr": 0.124,
                            "precision_at_10": 0.78,
                            "diversity_score": 0.65,
                            "user_satisfaction": 4.2
                        },
                        "optimization_recommendations": [
                            {
                                "parameter": "cluster_weight",
                                "current_value": 0.6,
                                "recommended_value": 0.67,
                                "expected_improvement": 0.08,
                                "confidence": 0.89
                            },
                            {
                                "parameter": "diversity_factor",
                                "current_value": 0.3,
                                "recommended_value": 0.35,
                                "expected_improvement": 0.12,
                                "confidence": 0.76
                            }
                        ],
                        "ab_test_insights": {
                            "winning_variants": ["hybrid_v2", "cluster_boosted"],
                            "significant_improvements": {
                                "ctr_improvement": 0.15,
                                "engagement_improvement": 0.23
                            },
                            "user_segment_preferences": {
                                "new_users": "popularity_based",
                                "experienced_users": "similarity_based"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def analyze_recommendation_optimization(
    optimization_target: str = Query("ctr", description="최적화 목표 (ctr/diversity/satisfaction)"),
    test_duration_days: int = Query(14, description="테스트 기간 (일)", ge=7, le=90),
    confidence_level: float = Query(0.95, description="신뢰도 수준", ge=0.8, le=0.99),
    session: AsyncSession = Depends(get_async_session)
) -> RecommendationOptimizationResponse:
    """
    현재 추천 알고리즘의 성능을 분석하고 최적화 방안을 제시합니다.
    
    ## 주요 기능
    - **성능 벤치마킹**: 현재 추천 시스템의 핵심 지표 측정 및 평가
    - **A/B 테스트 분석**: 다양한 알고리즘 변형의 성과 비교 및 통계적 유의성 검증
    - **하이퍼파라미터 최적화**: 가중치, 임계값 등 핵심 파라미터의 최적값 탐색
    - **사용자 세그먼트 분석**: 사용자 그룹별 최적 추천 전략 식별
    - **실시간 학습 성과**: 온라인 학습 알고리즘의 효과성 평가
    
    ## 최적화 목표
    1. **ctr**: 클릭률(Click-Through Rate) 최대화
    2. **diversity**: 추천 다양성 및 탐색성 향상
    3. **satisfaction**: 사용자 만족도 및 참여도 개선
    4. **conversion**: 북마크 저장 및 공유 전환율 향상
    5. **retention**: 사용자 재방문 및 장기 유지율 개선
    
    ## 분석 알고리즘
    1. **베이지안 최적화**: 파라미터 공간의 효율적 탐색
    2. **다중 목표 최적화**: 정확도-다양성 균형점 탐색
    3. **통계적 유의성 검정**: A/B 테스트 결과의 신뢰성 검증
    4. **시계열 분석**: 성능 변화 추이 및 계절성 패턴 분석
    5. **인과 추론**: 파라미터 변경의 실제 효과 측정
    
    ## 요청 예시
    ### CTR 최적화 분석 (14일 테스트)
    ```http
    POST /analytics/recommendation-optimization?optimization_target=ctr
    ```
    
    ### 다양성 개선 분석 (30일 테스트, 90% 신뢰도)
    ```http
    POST /analytics/recommendation-optimization?optimization_target=diversity&test_duration_days=30&confidence_level=0.90
    ```
    
    ### 사용자 만족도 최적화 (7일 단기 테스트)
    ```http
    POST /analytics/recommendation-optimization?optimization_target=satisfaction&test_duration_days=7
    ```
    
    Args:
        optimization_target: 최적화 목표 (ctr/diversity/satisfaction/conversion/retention)
        test_duration_days: A/B 테스트 기간 일수 (7-90일, 기본값: 14일)
        confidence_level: 통계적 신뢰도 수준 (0.8-0.99, 기본값: 0.95)
        
    Returns:
        RecommendationOptimizationResponse: 최적화 분석 결과 및 권장사항
        
    Raises:
        422: 잘못된 optimization_target, test_duration_days, confidence_level 값
        500: 추천 최적화 분석 실패시
        
    Note:
        - 장기간 테스트일수록 더 신뢰성 있는 결과 제공
        - 파라미터 변경은 점진적 적용을 통한 리스크 관리 권장
        - A/B 테스트 결과는 통계적 유의성 확인 후 적용
        - 최적화 제안은 비즈니스 목표와 사용자 경험을 종합 고려
    """
    
    try:
        optimization = await recommendation_engine.analyze_optimization_opportunities(
            session=session,
            optimization_target=optimization_target,
            test_duration_days=test_duration_days,
            confidence_level=confidence_level
        )
        
        return optimization
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"추천 최적화 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/realtime-metrics",
    summary="실시간 지표 모니터링",
    description="""
    추천 시스템의 실시간 성과 지표와 시스템 헬스를 모니터링합니다.
    
    **모니터링 지표:**
    - 실시간 CTR, 저장률, 응답시간
    - 시스템 처리량 및 에러율
    - 클러스터 품질 변화 추이
    - 사용자 만족도 실시간 피드백
    """,
    responses={
        200: {
            "description": "실시간 지표 조회 성공",
            "content": {
                "application/json": {
                    "example": {
                        "timestamp": "2024-01-15T15:30:00Z",
                        "performance_metrics": {
                            "current_ctr": 0.127,
                            "hourly_ctr_trend": [0.124, 0.126, 0.127],
                            "response_time_ms": 234,
                            "error_rate": 0.001
                        },
                        "system_health": {
                            "recommendations_served": 15420,
                            "active_users": 3456,
                            "cluster_recalculation_status": "in_progress",
                            "vector_search_performance": "optimal"
                        },
                        "alerts": [
                            {
                                "level": "warning",
                                "message": "클러스터 2의 품질 점수가 임계값 이하로 하락",
                                "timestamp": "2024-01-15T15:25:00Z"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_realtime_metrics(
    session: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    추천 시스템의 실시간 성과 지표와 시스템 헬스를 모니터링합니다.
    
    ## 주요 기능
    - **실시간 성과 추적**: CTR, 저장률, 공유율 등 핵심 지표의 실시간 모니터링
    - **시스템 헬스 체크**: 응답시간, 에러율, 처리량 등 시스템 안정성 지표
    - **클러스터 품질 모니터링**: 클러스터링 품질 변화 및 재계산 상태 추적
    - **사용자 활동 추적**: 활성 사용자 수, 세션 정보, 피드백 패턴 실시간 집계
    - **알림 및 경고**: 임계값 초과시 자동 알림 및 성능 이상 감지
    
    ## 모니터링 지표 카테고리
    1. **성과 지표**: CTR, 클릭률 트렌드, 저장률, 만족도 점수
    2. **시스템 지표**: 응답시간, 에러율, 처리량, 메모리 사용량
    3. **품질 지표**: 클러스터 품질, 추천 정확도, 다양성 점수
    4. **사용자 지표**: 활성 사용자, 세션 수, 피드백 빈도
    5. **비즈니스 지표**: 전환율, 참여도, 사용자 유지율
    
    ## 실시간 업데이트 주기
    - **성과 지표**: 1분마다 업데이트
    - **시스템 지표**: 30초마다 업데이트  
    - **사용자 활동**: 실시간 스트리밍
    - **클러스터 품질**: 1시간마다 업데이트
    - **알림 체크**: 10초마다 체크
    
    ## 요청 예시
    ### 현재 실시간 지표 조회
    ```http
    GET /analytics/realtime-metrics
    ```
    
    ## 응답 데이터 구조
    ```json
    {
        "timestamp": "2024-01-15T15:30:00Z",
        "data_freshness": "real-time",
        "performance_metrics": {
            "current_ctr": 0.127,
            "hourly_ctr_trend": [0.124, 0.126, 0.127, 0.129],
            "save_rate": 0.234,
            "share_rate": 0.089,
            "avg_session_duration": 1240,
            "bounce_rate": 0.156
        },
        "system_health": {
            "recommendations_served_last_hour": 15420,
            "avg_response_time_ms": 234,
            "error_rate": 0.001,
            "active_users": 3456,
            "concurrent_sessions": 1234,
            "vector_search_performance": "optimal",
            "cluster_recalculation_status": "in_progress",
            "cache_hit_rate": 0.89
        },
        "quality_metrics": {
            "recommendation_accuracy": 0.78,
            "diversity_score": 0.65,
            "novelty_score": 0.43,
            "cluster_quality_score": 0.82,
            "user_satisfaction_score": 4.2
        },
        "alerts": [
            {
                "id": "alert_001",
                "level": "warning",
                "category": "cluster_quality",
                "message": "클러스터 2의 품질 점수가 임계값(0.7) 이하로 하락: 0.65",
                "timestamp": "2024-01-15T15:25:00Z",
                "suggested_action": "클러스터 재계산 또는 파라미터 조정 검토"
            },
            {
                "id": "alert_002", 
                "level": "info",
                "category": "performance",
                "message": "추천 응답시간이 평균보다 15% 향상됨",
                "timestamp": "2024-01-15T15:20:00Z",
                "suggested_action": "현재 설정 유지"
            }
        ],
        "trends": {
            "ctr_trend_1h": "increasing",
            "user_activity_trend": "stable", 
            "error_rate_trend": "decreasing",
            "cluster_stability_trend": "stable"
        }
    }
    ```
    
    Returns:
        Dict[str, Any]: 실시간 지표 및 시스템 상태 정보
        
    Raises:
        500: 실시간 지표 조회 실패시
        
    Note:
        - 응답 데이터는 캐시되지 않으며 매번 최신 정보 제공
        - 대시보드 자동 새로고침 주기는 30초-1분 권장
        - 알림 레벨: info(정보), warning(주의), error(오류), critical(심각)
        - 시스템 부하 상황에서는 응답 시간이 증가할 수 있음
    """
    
    try:
        metrics = await analytics_service.get_realtime_metrics(session)
        return metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"실시간 지표 조회 중 오류가 발생했습니다: {str(e)}"
        ) 