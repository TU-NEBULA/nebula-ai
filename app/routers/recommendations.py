"""
추천 시스템 API 라우터

사용자 프로파일 기반 클러스터링과 콘텐츠 추천을 위한 REST API 엔드포인트들을 제공합니다.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.schemas.recommendation_schemas import (
    GeneralRecommendationRequest,
    GeneralRecommendationResponse,
    SearchBasedRecommendationRequest,
    SearchBasedRecommendationResponse,
    ClusterTrendsResponse,
    RecommendationFeedbackRequest,
    RecommendationFeedbackResponse,
    UserClusterInfoResponse,
    RecommendationPerformanceResponse
)
from app.services.recommendation_engine import RecommendationEngine
from app.services.clustering_service import ClusteringService
from app.services.recommendation_feedback import RecommendationFeedbackService

router = APIRouter(
    prefix="/recommendations",
    tags=["추천 시스템"],
    responses={
        404: {"description": "리소스를 찾을 수 없음"},
        500: {"description": "서버 내부 오류"},
    },
)

recommendation_engine = RecommendationEngine()
clustering_service = ClusteringService()
feedback_service = RecommendationFeedbackService()


@router.get(
    "/general",
    response_model=GeneralRecommendationResponse,
    summary="전체적인 콘텐츠 추천",
    description="""
    사용자 프로파일과 클러스터 분석을 기반으로 전체적인 콘텐츠를 추천합니다.
    
    **추천 알고리즘:**
    - 사용자 소속 클러스터 내 인기 콘텐츠 분석
    - 개인 프로파일과 콘텐츠 유사도 계산  
    - 협업 필터링과 콘텐츠 기반 필터링 하이브리드 적용
    - 다양성 확보를 위한 카테고리 분산
    
    **사용 예시:**
    - 홈페이지 개인화 추천
    - 일일/주간 추천 이메일
    - 앱 푸시 알림용 콘텐츠
    """,
    responses={
        200: {
            "description": "추천 결과 성공",
            "content": {
                "application/json": {
                    "example": {
                        "recommendations": [
                            {
                                "bookmark_id": "abc123",
                                "title": "React 18의 새로운 기능들",
                                "url": "https://example.com/react18",
                                "score": 0.92,
                                "reason_type": "cluster_popularity",
                                "reason_details": {
                                    "cluster_id": 5,
                                    "popularity_rank": 1,
                                    "similarity_score": 0.89
                                }
                            }
                        ],
                        "user_cluster_id": 5,
                        "cluster_description": "프론트엔드 개발자 그룹",
                        "total_recommendations": 15,
                        "generated_at": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        404: {"description": "사용자 프로파일을 찾을 수 없음"},
        422: {"description": "요청 파라미터 오류"}
    }
)
async def get_general_recommendations(
    user_id: int = Query(..., description="추천 대상 사용자 ID", ge=1),
    limit: int = Query(10, description="추천 개수", ge=1, le=50),
    category: Optional[str] = Query(None, description="특정 카테고리 필터"),
    exclude_viewed: bool = Query(True, description="이미 본 콘텐츠 제외 여부"),
    diversify: bool = Query(True, description="다양성 확보 적용 여부"),
    time_range: Optional[str] = Query("week", description="추천 기간 범위 (day/week/month)"),
    session: AsyncSession = Depends(get_async_session)
) -> GeneralRecommendationResponse:
    """
    사용자 프로파일과 클러스터 분석을 기반으로 개인화된 콘텐츠를 추천합니다.
    
    ## 주요 기능
    - **개인화 추천**: 사용자 벡터 프로파일(1536차원 OpenAI 임베딩) 기반 콘텐츠 매칭
    - **클러스터 기반 협업 필터링**: 유사한 사용자 그룹의 선호도 반영
    - **하이브리드 알고리즘**: 콘텐츠 기반 + 협업 필터링 조합으로 정확도 향상
    - **다양성 보장**: 카테고리 분산을 통한 편향 방지 및 탐색적 추천
    - **실시간 필터링**: 이미 본 콘텐츠 제외 및 카테고리별 필터링
    
    ## 추천 알고리즘 로직
    1. **사용자 프로파일 분석**: 벡터 임베딩, 키워드, 카테고리 선호도 추출
    2. **클러스터 매칭**: 사용자 소속 클러스터의 트렌딩 콘텐츠 식별
    3. **유사도 계산**: 코사인 유사도 기반 콘텐츠 스코어링
    4. **다양성 조절**: diversify 플래그를 통한 유사도-다양성 균형 조정
    5. **최종 랭킹**: 개인화 점수와 다양성 점수를 가중 평균하여 최종 순위 결정
    
    ## 요청 예시
    ### 기본 추천 (10개, 다양성 적용)
    ```http
    GET /recommendations/general?user_id=123
    ```
    
    ### 특정 카테고리 집중 추천
    ```http
    GET /recommendations/general?user_id=123&category=technology&limit=20
    ```
    
    ### 유사도 우선 추천 (다양성 비활성화)
    ```http
    GET /recommendations/general?user_id=123&diversify=false&exclude_viewed=false
    ```
    
    ### 월간 트렌드 기반 추천
    ```http
    GET /recommendations/general?user_id=123&time_range=month&limit=15
    ```
    
    Args:
        user_id: 추천을 요청하는 사용자의 ID (1 이상)
        limit: 추천할 콘텐츠 수 (1-50, 기본값: 10)
        category: 특정 카테고리로 필터링 (선택적)
        exclude_viewed: 이미 본 콘텐츠 제외 여부 (기본값: True)
        diversify: 다양성 확보 적용 여부 (기본값: True)
        time_range: 추천 기간 범위 (day/week/month, 기본값: week)
        
    Returns:
        GeneralRecommendationResponse: 개인화된 추천 목록과 메타데이터
        
    Raises:
        404: 사용자 프로파일이 존재하지 않음
        422: 잘못된 파라미터 값 (limit 범위 초과, 유효하지 않은 time_range 등)
        500: 추천 생성 실패시
        
    Note:
        - 신규 사용자의 경우 인기도 기반 추천으로 대체
        - 클러스터 정보가 없는 경우 콘텐츠 기반 필터링만 사용
        - 실시간 성능을 위해 벡터 인덱스 및 캐싱 활용
    """
    
    try:
        request = GeneralRecommendationRequest(
            user_id=user_id,
            limit=limit,
            category=category,
            exclude_viewed=exclude_viewed,
            diversify=diversify,
            time_range=time_range
        )
        
        recommendations = await recommendation_engine.get_general_recommendations(
            session=session,
            request=request
        )
        
        return recommendations
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"추천 생성 중 오류가 발생했습니다: {str(e)}")


@router.post(
    "/search-based",
    response_model=SearchBasedRecommendationResponse,
    summary="검색어 기반 실시간 추천",
    description="""
    사용자의 검색어를 분석하여 실시간으로 관련 콘텐츠를 추천합니다.
    
    **추천 전략:**
    - 검색어 임베딩과 콘텐츠 임베딩 매칭
    - 의미적 유사도 기반 콘텐츠 발견
    - 사용자 클러스터의 해당 주제 선호도 반영
    - 컨텍스트 확장을 통한 관련 키워드 추천
    
    **활용 사례:**
    - 검색 결과 페이지 추천
    - 검색어 자동완성 개선
    - 검색 의도 파악 및 관련 콘텐츠 제안
    """,
    responses={
        200: {
            "description": "검색 기반 추천 성공",
            "content": {
                "application/json": {
                    "example": {
                        "recommendations": [
                            {
                                "bookmark_id": "def456",
                                "title": "Vue.js 3 Composition API 가이드",
                                "url": "https://example.com/vue3-guide",
                                "score": 0.94,
                                "reason_type": "semantic_similarity",
                                "reason_details": {
                                    "keyword_matches": ["vue", "composition", "api"],
                                    "semantic_score": 0.91,
                                    "user_preference_boost": 0.03
                                }
                            }
                        ],
                        "query_keywords": ["vue", "composition", "api", "가이드"],
                        "expanded_concepts": ["프론트엔드", "SPA", "반응형"],
                        "search_intent": "learning",
                        "total_recommendations": 12
                    }
                }
            }
        },
        400: {"description": "검색어가 비어있거나 유효하지 않음"},
        422: {"description": "요청 본문 형식 오류"}
    }
)
async def get_search_based_recommendations(
    request: SearchBasedRecommendationRequest = Body(..., description="검색 기반 추천 요청"),
    session: AsyncSession = Depends(get_async_session)
) -> SearchBasedRecommendationResponse:
    """
    사용자의 검색어를 분석하여 실시간으로 관련 콘텐츠를 추천합니다.
    
    ## 주요 기능
    - **실시간 검색 추천**: 검색어 입력과 동시에 관련 콘텐츠 즉시 제안
    - **의미적 유사도 분석**: OpenAI 임베딩을 통한 검색어-콘텐츠 의미 매칭
    - **개인화 반영**: 사용자 클러스터의 해당 주제 선호도 가중치 적용
    - **컨텍스트 확장**: 검색 의도 파악 및 관련 키워드 자동 확장
    - **다중 언어 지원**: 한국어, 영어 혼용 검색어 처리
    
    ## 검색 알고리즘 로직
    1. **검색어 전처리**: 불용어 제거, 토큰화, 정규화
    2. **임베딩 생성**: OpenAI text-embedding-ada-002로 검색어 벡터화
    3. **유사도 계산**: 콘텐츠 임베딩과 코사인 유사도 계산
    4. **클러스터 가중치**: 사용자 클러스터의 주제 선호도 반영
    5. **의도 분석**: 학습/정보수집/문제해결 등 검색 의도 분류
    6. **결과 랭킹**: 유사도 + 개인화 + 인기도 종합 점수
    
    ## 요청 예시
    ### 기본 검색 추천
    ```json
    POST /recommendations/search-based
    {
        "user_id": 123,
        "query": "React 상태 관리",
        "limit": 10
    }
    ```
    
    ### 특정 카테고리 내 검색
    ```json
    POST /recommendations/search-based
    {
        "user_id": 123,
        "query": "머신러닝 알고리즘",
        "limit": 15,
        "category_filter": "technology",
        "include_similar_queries": true
    }
    ```
    
    ### 다국어 검색
    ```json
    POST /recommendations/search-based
    {
        "user_id": 123,
        "query": "python machine learning tutorial",
        "limit": 20,
        "boost_user_cluster": true
    }
    ```
    
    ## 응답 형식
    ```json
    {
        "recommendations": [
            {
                "bookmark_id": "bm_001",
                "title": "React 상태 관리 완벽 가이드",
                "url": "https://example.com/react-state",
                "score": 0.94,
                "reason_type": "semantic_similarity",
                "reason_details": {
                    "keyword_matches": ["react", "상태", "관리"],
                    "semantic_score": 0.91,
                    "user_preference_boost": 0.03
                }
            }
        ],
        "query_analysis": {
            "original_query": "React 상태 관리",
            "extracted_keywords": ["react", "상태관리", "state"],
            "expanded_concepts": ["redux", "context", "hooks"],
            "search_intent": "learning",
            "language": "ko"
        },
        "metadata": {
            "total_candidates": 450,
            "processing_time_ms": 120,
            "algorithm_version": "search_v1.2"
        }
    }
    ```
    
    Args:
        request: 검색 기반 추천 요청 데이터
            - user_id: 사용자 ID
            - query: 검색어 (필수)
            - limit: 추천 개수 (기본값: 10)
            - category_filter: 카테고리 필터 (선택적)
            - include_similar_queries: 유사 검색어 포함 여부
            - boost_user_cluster: 사용자 클러스터 가중치 적용 여부
        
    Returns:
        SearchBasedRecommendationResponse: 검색 기반 추천 결과와 분석 정보
        
    Raises:
        400: 검색어가 비어있거나 유효하지 않음
        422: 요청 본문 형식 오류 (잘못된 JSON, 필수 필드 누락 등)
        500: 검색 추천 생성 실패시
        
    Note:
        - 검색어가 너무 짧은 경우(2글자 미만) 인기 콘텐츠로 대체
        - 검색 결과가 없는 경우 유사한 키워드로 확장 검색
        - 실시간 성능을 위해 검색어 캐싱 및 벡터 인덱스 활용
        - 검색 로그는 개인화 모델 학습에 활용
    """
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="검색어가 비어있습니다")
    
    try:
        recommendations = await recommendation_engine.get_search_based_recommendations(
            session=session,
            request=request
        )
        
        return recommendations
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 추천 생성 중 오류가 발생했습니다: {str(e)}")


@router.get(
    "/cluster-trends",
    response_model=ClusterTrendsResponse,
    summary="클러스터 트렌드 정보",
    description="""
    사용자 클러스터별 트렌드와 인기 콘텐츠 정보를 제공합니다.
    
    **제공 정보:**
    - 클러스터별 인기 키워드 및 카테고리
    - 트렌딩 콘텐츠 및 급상승 토픽
    - 클러스터 간 유사도 및 특성 비교
    - 시간대별 활동 패턴 분석
    
    **활용 방안:**
    - 트렌드 대시보드 구성
    - 콘텐츠 큐레이션 전략 수립
    - 사용자 세그먼트 분석
    """,
    responses={
        200: {
            "description": "클러스터 트렌드 조회 성공",
            "content": {
                "application/json": {
                    "example": {
                        "cluster_trends": [
                            {
                                "cluster_id": 1,
                                "cluster_name": "AI/ML 엔지니어",
                                "member_count": 1250,
                                "trending_keywords": [
                                    {"keyword": "langchain", "score": 0.89, "growth": 0.34},
                                    {"keyword": "transformers", "score": 0.76, "growth": 0.21}
                                ],
                                "popular_domains": ["huggingface.co", "arxiv.org"],
                                "activity_peak_hours": [9, 14, 20]
                            }
                        ],
                        "global_trends": {
                            "emerging_topics": ["웹3", "메타버스", "양자컴퓨팅"],
                            "declining_topics": ["jQuery", "Angular.js"]
                        },
                        "generated_at": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def get_cluster_trends(
    cluster_id: Optional[int] = Query(None, description="특정 클러스터 ID (미지정시 전체)"),
    time_period: str = Query("week", description="분석 기간 (day/week/month)"),
    include_global: bool = Query(True, description="글로벌 트렌드 포함 여부"),
    session: AsyncSession = Depends(get_async_session)
) -> ClusterTrendsResponse:
    """
    사용자 클러스터별 트렌드와 인기 콘텐츠 정보를 제공합니다.
    
    ## 주요 기능
    - **클러스터별 트렌드 분석**: 각 사용자 그룹의 고유한 관심사 및 트렌드 파악
    - **실시간 인기도 추적**: 클러스터 내 급상승 키워드 및 콘텐츠 식별
    - **시간대별 활동 패턴**: 클러스터별 활동 시간대 및 패턴 분석
    - **글로벌 트렌드 비교**: 전체 플랫폼 트렌드와 클러스터 트렌드 비교
    - **예측적 분석**: 향후 트렌드 예측 및 추천 전략 제안
    
    ## 분석 데이터 소스
    1. **북마크 활동**: 클러스터 내 사용자들의 북마크 패턴 분석
    2. **검색 로그**: 검색어 빈도 및 관심 주제 추출
    3. **상호작용 데이터**: 클릭, 저장, 공유 등 사용자 행동 분석
    4. **시간별 활동**: 시간대별 활동량 및 선호 시간 파악
    5. **콘텐츠 성과**: 클러스터별 콘텐츠 성과 및 반응도 측정
    
    ## 요청 예시
    ### 전체 클러스터 트렌드 조회 (주간)
    ```http
    GET /recommendations/cluster-trends
    ```
    
    ### 특정 클러스터 월간 트렌드
    ```http
    GET /recommendations/cluster-trends?cluster_id=3&time_period=month
    ```
    
    ### 일간 트렌드 (글로벌 제외)
    ```http
    GET /recommendations/cluster-trends?time_period=day&include_global=false
    ```
    
    ## 응답 형식
    ```json
    {
        "cluster_trends": [
            {
                "cluster_id": 1,
                "cluster_name": "AI/ML 엔지니어",
                "member_count": 1250,
                "trending_keywords": [
                    {
                        "keyword": "langchain",
                        "score": 0.89,
                        "growth": 0.34,
                        "weekly_mentions": 156
                    }
                ],
                "popular_categories": [
                    {"category": "machine-learning", "percentage": 45.2},
                    {"category": "data-science", "percentage": 28.7}
                ],
                "top_domains": [
                    {"domain": "huggingface.co", "visits": 892, "growth": 0.23},
                    {"domain": "arxiv.org", "visits": 567, "growth": 0.15}
                ],
                "activity_patterns": {
                    "peak_hours": [9, 14, 20],
                    "most_active_day": "tuesday",
                    "avg_session_duration": 18.5
                }
            }
        ],
        "global_trends": {
            "emerging_topics": ["웹3", "메타버스", "양자컴퓨팅"],
            "declining_topics": ["jQuery", "Angular.js"],
            "cross_cluster_topics": ["AI", "blockchain", "sustainability"]
        },
        "metadata": {
            "analysis_period": "2024-01-08 to 2024-01-15",
            "total_clusters": 8,
            "data_freshness": "2024-01-15T10:30:00Z"
        }
    }
    ```
    
    Args:
        cluster_id: 특정 클러스터 ID (미지정시 전체 클러스터 분석)
        time_period: 분석 기간 (day/week/month, 기본값: week)
        include_global: 글로벌 트렌드 포함 여부 (기본값: True)
        
    Returns:
        ClusterTrendsResponse: 클러스터별 트렌드 정보와 글로벌 트렌드
        
    Raises:
        404: 지정된 클러스터 ID가 존재하지 않음
        422: 잘못된 time_period 값 (지원하지 않는 기간)
        500: 트렌드 분석 실패시
        
    Note:
        - 트렌드 데이터는 1시간마다 업데이트
        - 클러스터 멤버가 10명 미만인 경우 트렌드 정보 제한
        - 개인정보 보호를 위해 개별 사용자 식별 정보는 제외
        - 급상승 키워드는 이전 기간 대비 성장률 기준으로 선정
    """
    
    try:
        trends = await clustering_service.get_cluster_trends(
            session=session,
            cluster_id=cluster_id,
            time_period=time_period,
            include_global=include_global
        )
        
        return trends
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"트렌드 조회 중 오류가 발생했습니다: {str(e)}")


@router.post(
    "/feedback",
    response_model=RecommendationFeedbackResponse,
    summary="추천 피드백 수집",
    description="""
    사용자의 추천 콘텐츠 상호작용을 수집하여 추천 알고리즘을 개선합니다.
    
    **수집 데이터:**
    - 클릭, 저장, 공유, 무시 등의 사용자 액션
    - 추천 표시 시간 및 반응 시간
    - 세션 컨텍스트 및 추천 이유별 성과
    
    **활용 목적:**
    - 개인화 모델 실시간 학습
    - A/B 테스트 성과 측정  
    - 추천 품질 지표 모니터링
    """,
    responses={
        200: {
            "description": "피드백 저장 성공",
            "content": {
                "application/json": {
                    "example": {
                        "feedback_id": "fb123456",
                        "processed": True,
                        "impact_score": 0.15,
                        "model_updated": True,
                        "message": "피드백이 성공적으로 처리되었습니다"
                    }
                }
            }
        },
        400: {"description": "유효하지 않은 피드백 데이터"},
        422: {"description": "필수 필드 누락"}
    }
)
async def submit_recommendation_feedback(
    feedback: RecommendationFeedbackRequest = Body(..., description="추천 피드백 데이터"),
    session: AsyncSession = Depends(get_async_session)
) -> RecommendationFeedbackResponse:
    """
    사용자의 추천 콘텐츠 상호작용을 수집하여 추천 알고리즘을 개선합니다.
    
    ## 주요 기능
    - **실시간 피드백 수집**: 사용자의 모든 추천 상호작용을 즉시 기록
    - **다양한 액션 유형**: 클릭, 저장, 공유, 무시, 부정적 반응 등 세분화된 피드백
    - **컨텍스트 정보**: 추천 시점, 세션 정보, 디바이스 등 상황 정보 수집
    - **개인화 모델 학습**: 수집된 피드백을 통한 실시간 모델 업데이트
    - **성과 측정**: 추천 품질 지표 및 A/B 테스트 성과 분석
    
    ## 피드백 유형 및 처리
    1. **명시적 피드백**: 사용자가 직접 제공하는 평가 (좋아요, 싫어요, 별점)
    2. **암시적 피드백**: 사용자 행동을 통한 간접 평가 (클릭, 체류 시간, 스크롤)
    3. **부정적 피드백**: "관심 없음", "부적절함" 등의 명시적 거부 반응
    4. **컨텍스트 피드백**: 시간, 위치, 디바이스 등 상황적 요소
    5. **세션 피드백**: 전체 추천 세션에 대한 종합적 평가
    
    ## 요청 예시
    ### 기본 클릭 피드백
    ```json
    POST /recommendations/feedback
    {
        "user_id": 123,
        "recommendation_id": "rec_abc123",
        "action_type": "click",
        "content_id": "content_456",
        "timestamp": "2024-01-15T14:30:00Z"
    }
    ```
    
    ### 상세 피드백 (저장 + 평가)
    ```json
    POST /recommendations/feedback
    {
        "user_id": 123,
        "recommendation_id": "rec_def456",
        "action_type": "save",
        "content_id": "content_789",
        "rating": 5,
        "context": {
            "session_id": "sess_xyz",
            "recommendation_position": 2,
            "total_recommendations_shown": 10,
            "time_to_action": 15.5
        },
        "timestamp": "2024-01-15T14:35:00Z"
    }
    ```
    
    ### 부정적 피드백
    ```json
    POST /recommendations/feedback
    {
        "user_id": 123,
        "recommendation_id": "rec_ghi789",
        "action_type": "dismiss",
        "content_id": "content_012",
        "feedback_reason": "not_interested",
        "context": {
            "reason_details": "이미 알고 있는 내용",
            "suggestion": "더 최신 내용 추천 희망"
        },
        "timestamp": "2024-01-15T14:40:00Z"
    }
    ```
    
    ## 응답 형식
    ```json
    {
        "feedback_id": "fb_123456789",
        "processed": true,
        "impact_score": 0.15,
        "model_updated": true,
        "processing_details": {
            "user_profile_updated": true,
            "cluster_weights_adjusted": true,
            "negative_signal_applied": false,
            "learning_rate_applied": 0.01
        },
        "recommendations_affected": 3,
        "estimated_improvement": {
            "precision_delta": 0.02,
            "diversity_delta": -0.01,
            "user_satisfaction_delta": 0.05
        },
        "message": "피드백이 성공적으로 처리되어 개인화 모델이 업데이트되었습니다"
    }
    ```
    
    Args:
        feedback: 추천 피드백 데이터
            - user_id: 피드백 제공 사용자 ID
            - recommendation_id: 추천 시스템에서 생성한 추천 ID
            - action_type: 액션 유형 (click/save/share/dismiss/rate 등)
            - content_id: 대상 콘텐츠 ID
            - rating: 명시적 평가 점수 (선택적, 1-5)
            - context: 추가 컨텍스트 정보 (선택적)
            - timestamp: 액션 발생 시간
        
    Returns:
        RecommendationFeedbackResponse: 피드백 처리 결과 및 모델 업데이트 정보
        
    Raises:
        400: 유효하지 않은 피드백 데이터 (잘못된 action_type, 존재하지 않는 content_id 등)
        422: 필수 필드 누락 (user_id, recommendation_id, action_type 등)
        500: 피드백 처리 실패시
        
    Note:
        - 피드백은 실시간으로 처리되며 즉시 개인화 모델에 반영
        - 부정적 피드백은 해당 콘텐츠의 추천 가중치를 즉시 감소
        - 피드백 패턴은 클러스터 전체의 추천 품질 개선에도 활용
        - 개인정보 보호를 위해 익명화된 형태로 분석 데이터 저장
    """
    
    try:
        response = await feedback_service.process_feedback(
            session=session,
            feedback=feedback
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"피드백 처리 중 오류가 발생했습니다: {str(e)}")


@router.get(
    "/user-cluster",
    response_model=UserClusterInfoResponse,
    summary="사용자 클러스터 정보",
    description="""
    특정 사용자의 클러스터 소속 정보와 클러스터 특성을 제공합니다.
    
    **제공 정보:**
    - 사용자 소속 클러스터 ID 및 특성
    - 클러스터 내 위치 및 유사 사용자들
    - 클러스터별 추천 성향 및 선호도
    - 클러스터 이동 이력 및 패턴 변화
    """,
    responses={
        200: {
            "description": "사용자 클러스터 정보 조회 성공",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": 12345,
                        "current_cluster": {
                            "cluster_id": 3,
                            "cluster_name": "데이터 사이언티스트",
                            "confidence_score": 0.87,
                            "member_count": 892,
                            "key_characteristics": ["python", "machine learning", "statistics"]
                        },
                        "cluster_position": "core",
                        "similar_users": [67890, 54321, 98765],
                        "cluster_history": [
                            {"cluster_id": 2, "period": "2024-01", "duration_days": 45},
                            {"cluster_id": 3, "period": "2024-02", "duration_days": 30}
                        ]
                    }
                }
            }
        },
        404: {"description": "사용자를 찾을 수 없음"}
    }
)
async def get_user_cluster_info(
    user_id: int = Query(..., description="조회할 사용자 ID", ge=1),
    include_history: bool = Query(False, description="클러스터 이동 이력 포함 여부"),
    session: AsyncSession = Depends(get_async_session)
) -> UserClusterInfoResponse:
    """
    특정 사용자의 클러스터 소속 정보와 클러스터 특성을 제공합니다.
    
    ## 주요 기능
    - **현재 클러스터 정보**: 사용자가 속한 클러스터의 상세 정보 및 특성
    - **클러스터 내 위치**: 클러스터 중심부/경계부 등 사용자의 위치 분석
    - **유사 사용자 식별**: 같은 클러스터 내 유사한 관심사를 가진 사용자들
    - **클러스터 이동 이력**: 시간에 따른 사용자의 관심사 변화 추적
    - **개인화 인사이트**: 클러스터 기반 추천 성향 및 선호도 분석
    
    ## 클러스터 분석 요소
    1. **클러스터 특성**: 키워드, 카테고리 분포, 주요 관심사
    2. **멤버십 강도**: 클러스터 중심 대비 사용자 위치 및 소속감
    3. **활동 패턴**: 클러스터 내 상호작용 및 콘텐츠 소비 패턴
    4. **영향력 지수**: 클러스터 내 사용자의 영향력 및 활동도
    5. **변화 추이**: 시간에 따른 클러스터 소속 변화 및 관심사 이동
    
    ## 요청 예시
    ### 기본 클러스터 정보 조회
    ```http
    GET /recommendations/user-cluster?user_id=123
    ```
    
    ### 이력 포함 상세 조회
    ```http
    GET /recommendations/user-cluster?user_id=123&include_history=true
    ```
    
    ## 응답 형식
    ```json
    {
        "user_id": 12345,
        "current_cluster": {
            "cluster_id": 3,
            "cluster_name": "데이터 사이언티스트",
            "confidence_score": 0.87,
            "member_count": 892,
            "key_characteristics": [
                "python", "machine learning", "statistics", "data visualization"
            ],
            "cluster_description": "데이터 분석과 머신러닝에 관심이 높은 사용자 그룹"
        },
        "membership_details": {
            "cluster_position": "core",
            "membership_strength": 0.91,
            "days_in_cluster": 45,
            "stability_score": 0.84
        },
        "similar_users": [
            {
                "user_id": 67890,
                "similarity_score": 0.92,
                "common_interests": ["pytorch", "nlp", "kaggle"]
            }
        ],
        "cluster_insights": {
            "recommendation_affinity": 0.78,
            "content_diversity_preference": 0.65,
            "trending_participation": 0.82,
            "interaction_frequency": "high"
        },
        "cluster_history": [
            {
                "cluster_id": 2,
                "cluster_name": "웹 개발자",
                "period": "2024-01",
                "duration_days": 45,
                "transition_reason": "interest_shift"
            },
            {
                "cluster_id": 3,
                "cluster_name": "데이터 사이언티스트",
                "period": "2024-02",
                "duration_days": 30,
                "transition_reason": "current"
            }
        ]
    }
    ```
    
    Args:
        user_id: 조회할 사용자 ID (1 이상)
        include_history: 클러스터 이동 이력 포함 여부 (기본값: False)
        
    Returns:
        UserClusterInfoResponse: 사용자 클러스터 정보 및 분석 데이터
        
    Raises:
        404: 사용자 정보를 찾을 수 없음 (존재하지 않는 user_id)
        422: 잘못된 파라미터 값 (음수 user_id 등)
        500: 클러스터 정보 조회 실패시
        
    Note:
        - 클러스터 정보가 없는 신규 사용자의 경우 기본 클러스터로 분류
        - 클러스터 이동 이력은 개인정보 보호를 위해 최근 6개월만 제공
        - 유사 사용자 정보는 익명화되어 제공 (사용자 ID만 표시)
        - 클러스터 분석은 매일 업데이트되며 실시간 반영
    """
    
    try:
        cluster_info = await clustering_service.get_user_cluster_info(
            session=session,
            user_id=user_id,
            include_history=include_history
        )
        
        if not cluster_info:
            raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다")
        
        return cluster_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"클러스터 정보 조회 중 오류가 발생했습니다: {str(e)}")


@router.get(
    "/performance",
    response_model=RecommendationPerformanceResponse,
    summary="추천 성과 분석",
    description="""
    추천 시스템의 성과 지표와 품질 메트릭을 제공합니다.
    
    **성과 지표:**
    - 클릭률 (CTR), 저장률, 공유율
    - 다양성 점수 및 신선도 지표
    - 사용자별/클러스터별 만족도
    - A/B 테스트 결과 비교
    
    **활용 목적:**
    - 추천 알고리즘 성능 모니터링
    - 비즈니스 KPI 추적
    - 시스템 개선 방향 도출
    """,
    responses={
        200: {
            "description": "추천 성과 분석 조회 성공",
            "content": {
                "application/json": {
                    "example": {
                        "overall_metrics": {
                            "click_through_rate": 0.124,
                            "save_rate": 0.089,
                            "diversity_score": 0.76,
                            "freshness_score": 0.83
                        },
                        "cluster_performance": [
                            {
                                "cluster_id": 1,
                                "ctr": 0.156,
                                "satisfaction": 4.2,
                                "engagement_time": 240
                            }
                        ],
                        "trend_analysis": {
                            "weekly_change": 0.12,
                            "improving_metrics": ["diversity_score", "freshness_score"],
                            "declining_metrics": ["click_through_rate"]
                        },
                        "report_period": "2024-01-01 to 2024-01-15"
                    }
                }
            }
        }
    }
)
async def get_recommendation_performance(
    start_date: Optional[datetime] = Query(None, description="분석 시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="분석 종료 날짜"),
    cluster_id: Optional[int] = Query(None, description="특정 클러스터 분석"),
    metric_type: Optional[str] = Query(None, description="특정 메트릭 타입 (ctr/save_rate/diversity)"),
    session: AsyncSession = Depends(get_async_session)
) -> RecommendationPerformanceResponse:
    """
    추천 시스템의 성과 지표와 품질 메트릭을 제공합니다.
    
    ## 주요 기능
    - **종합 성과 지표**: CTR, 저장률, 공유율 등 핵심 비즈니스 메트릭
    - **품질 지표**: 다양성, 신선도, 개인화 정확도 등 추천 품질 측정
    - **클러스터별 분석**: 사용자 그룹별 추천 성과 및 선호도 차이 분석
    - **트렌드 분석**: 시간에 따른 성과 변화 및 개선/악화 추이
    - **A/B 테스트 지원**: 다양한 추천 알고리즘 성과 비교
    
    ## 성과 지표 유형
    1. **참여도 지표**: 클릭률(CTR), 체류 시간, 상호작용 빈도
    2. **전환 지표**: 저장률, 공유율, 북마크 추가율
    3. **품질 지표**: 다양성 점수, 신선도, 개인화 정확도
    4. **만족도 지표**: 사용자 평가, 피드백 점수, 재방문율
    5. **비즈니스 지표**: 사용자 활성도, 플랫폼 체류 시간, 콘텐츠 소비량
    
    ## 요청 예시
    ### 전체 성과 조회 (최근 30일)
    ```http
    GET /recommendations/performance
    ```
    
    ### 특정 기간 분석
    ```http
    GET /recommendations/performance?start_date=2024-01-01&end_date=2024-01-15
    ```
    
    ### 특정 클러스터 성과 분석
    ```http
    GET /recommendations/performance?cluster_id=3&metric_type=ctr
    ```
    
    ### 다양성 지표 집중 분석
    ```http
    GET /recommendations/performance?metric_type=diversity&start_date=2024-01-01
    ```
    
    ## 응답 형식
    ```json
    {
        "overall_metrics": {
            "click_through_rate": 0.124,
            "save_rate": 0.089,
            "share_rate": 0.034,
            "diversity_score": 0.76,
            "freshness_score": 0.83,
            "personalization_accuracy": 0.71,
            "user_satisfaction": 4.2
        },
        "cluster_performance": [
            {
                "cluster_id": 1,
                "cluster_name": "AI/ML 엔지니어",
                "metrics": {
                    "ctr": 0.156,
                    "save_rate": 0.112,
                    "satisfaction": 4.5,
                    "engagement_time": 240,
                    "diversity_preference": 0.68
                },
                "member_count": 1250,
                "recommendation_volume": 15600
            }
        ],
        "trend_analysis": {
            "period_comparison": {
                "previous_period": "2023-12-15 to 2024-01-01",
                "current_period": "2024-01-01 to 2024-01-15",
                "changes": {
                    "ctr_change": 0.12,
                    "save_rate_change": -0.05,
                    "diversity_change": 0.08
                }
            },
            "improving_metrics": [
                {"metric": "diversity_score", "improvement": 0.08},
                {"metric": "freshness_score", "improvement": 0.15}
            ],
            "declining_metrics": [
                {"metric": "click_through_rate", "decline": -0.02}
            ]
        },
        "ab_test_results": [
            {
                "test_name": "hybrid_vs_collaborative",
                "variant_a": {"name": "hybrid", "ctr": 0.124, "sample_size": 5000},
                "variant_b": {"name": "collaborative", "ctr": 0.118, "sample_size": 5000},
                "statistical_significance": 0.95,
                "winner": "hybrid"
            }
        ],
        "recommendations": [
            "클러스터 3의 다양성 점수가 낮습니다. 카테고리 분산을 늘려보세요.",
            "전체적인 CTR이 감소 추세입니다. 개인화 가중치 조정을 검토하세요."
        ],
        "metadata": {
            "report_period": "2024-01-01 to 2024-01-15",
            "total_recommendations": 125000,
            "total_users": 8500,
            "data_freshness": "2024-01-15T23:59:59Z"
        }
    }
    ```
    
    Args:
        start_date: 분석 시작 날짜 (미지정시 30일 전부터)
        end_date: 분석 종료 날짜 (미지정시 현재까지)
        cluster_id: 특정 클러스터 분석 (미지정시 전체 클러스터)
        metric_type: 특정 메트릭 타입 (ctr/save_rate/diversity/all, 미지정시 all)
        
    Returns:
        RecommendationPerformanceResponse: 추천 시스템 성과 분석 결과
        
    Raises:
        422: 잘못된 날짜 범위 (시작 날짜가 종료 날짜보다 늦음 등)
        404: 지정된 클러스터 ID가 존재하지 않음
        500: 성과 분석 실패시
        
    Note:
        - 성과 지표는 매시간 업데이트되며 실시간 반영
        - A/B 테스트 결과는 통계적 유의성이 확보된 경우만 표시
        - 개인정보 보호를 위해 개별 사용자 식별 정보는 제외
        - 클러스터별 분석은 최소 100명 이상의 멤버가 있는 경우만 제공
    """
    
    try:
        performance = await feedback_service.get_performance_metrics(
            session=session,
            start_date=start_date,
            end_date=end_date,
            cluster_id=cluster_id,
            metric_type=metric_type
        )
        
        return performance
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성과 분석 중 오류가 발생했습니다: {str(e)}") 