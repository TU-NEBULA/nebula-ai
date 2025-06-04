"""
User Profile API Router - Query Side (CQRS)

Spring Boot 서버에서 호출하는 사용자 프로필 관련 읽기 전용 API
- 프로필 조회 (즉시 응답)
- 유사 사용자 검색 (즉시 응답)
- 캐시된 추천 조회 (즉시 응답)
- 작업 상태 조회 (비동기 작업 추적)
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_async_session
from app.repositories import (
    UserProfileRepository,
    RecommendationRepository,
)
from app.schemas.profile_schemas import (
    UserProfileResponse,
    SimilarUsersResponse,
    RecommendationsResponse,
    InterestsAnalysisResponse,
    JobStatusResponse,
    ProfileMetricsResponse
)

router = APIRouter(prefix="/api/v1/profiles", tags=["User Profiles"])


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: int = Path(..., gt=0, description="사용자 ID (양수)"),
    include_metadata: bool = Query(False, description="메타데이터 포함 여부"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    사용자 프로필 조회 - Spring Boot에서 호출

    사용 시나리오:
    - 사용자 대시보드 로딩
    - 설정 페이지 프로필 정보 표시
    - 관리자 도구에서 사용자 상태 확인
    """
    try:
        user_profile_repo = UserProfileRepository()

        # 프로필 조회
        profile = await user_profile_repo.get_or_create_profile(session, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")

        # 응답 데이터 구성
        response_data = {
            "user_id": profile.user_id,
            "profile_vector": profile.profile_vector,
            "last_updated": profile.updated_at or profile.created_at,
            "vector_strength": profile.vector_strength or 0.0,
            "completeness_score": profile.completeness_score or 0
        }

        # 메타데이터 포함 시 추가 정보
        if include_metadata:
            response_data.update({
                "created_at": profile.created_at,
                "vector_metadata": profile.vector_metadata,
                "update_count": getattr(profile, 'update_count', 0),
                "last_similarity_update": getattr(profile, 'last_similarity_update', None)
            })

        logger.info(f"프로필 조회 완료: user_id={user_id}")
        return UserProfileResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프로필 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{user_id}/similar", response_model=SimilarUsersResponse)
async def get_similar_users(
    user_id: int,
    limit: int = Query(10, ge=1, le=50, description="반환할 유사 사용자 수"),
    min_similarity: float = Query(0.5, ge=0.0, le=1.0, description="최소 유사도 임계값"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    유사한 사용자 검색 - Spring Boot에서 호출
    임시 테스트용

    사용 시나리오:
    - 소셜 기능: "비슷한 관심사 사용자" 추천
    - 네트워킹: 전문 분야별 사용자 연결
    - 커뮤니티: 팔로우 추천, 그룹 추천
    """
    try:
        user_profile_repo = UserProfileRepository()

        # 현재 사용자 프로필 확인
        current_profile = await user_profile_repo.get_or_create_profile(session, user_id)
        if not current_profile or not current_profile.profile_vector:
            raise HTTPException(
                status_code=404,
                detail="User profile or vector not found"
            )

        # 유사 사용자 검색
        similar_users = await user_profile_repo.get_similar_users(
            session, user_id, min_similarity, limit
        )

        response_data = {
            "user_id": user_id,
            "similar_users": [
                {
                    "user_id": user.user_id,
                    "similarity_score": user.similarity_score,
                    "shared_interests": user.shared_interests or [],
                    "last_updated": user.updated_at
                }
                for user in similar_users
            ],
            "total_found": len(similar_users),
            "search_criteria": {
                "min_similarity": min_similarity,
                "limit": limit
            }
        }

        logger.info(f"유사 사용자 검색 완료: user_id={user_id}, found={len(similar_users)}")
        return SimilarUsersResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"유사 사용자 검색 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{user_id}/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    user_id: int,
    category: Optional[str] = Query(None, description="추천 카테고리 필터"),
    max_age_hours: int = Query(24, ge=1, le=168, description="추천 최대 나이(시간)"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    개인화 추천 조회 - 캐시된 결과 즉시 반환

    사용 시나리오:
    - 홈페이지 개인화 피드
    - 이메일 뉴스레터 콘텐츠
    - 푸시 알림용 맞춤 콘텐츠
    """
    try:
        recommendation_repo = RecommendationRepository()

        # 캐시된 추천 조회
        recommendations = await recommendation_repo.get_user_recommendations(
            session, user_id, category, max_age_hours
        )

        if not recommendations:
            # TODO 추천이 없으면 백그라운드 갱신 트리거 (MQ 메시지는 별도 구현)
            logger.info(f"추천 없음, 백그라운드 갱신 필요: user_id={user_id}")

            return RecommendationsResponse(
                user_id=user_id,
                recommendations=[],
                generated_at=None,
                cache_status="MISS",
                refresh_requested=True
            )

        response_data = {
            "user_id": user_id,
            "recommendations": [
                {
                    "id": rec.id,
                    "type": rec.recommendation_type,
                    "title": rec.title,
                    "description": rec.description,
                    "score": rec.score,
                    "metadata": rec.metadata,
                    "created_at": rec.created_at
                }
                for rec in recommendations
            ],
            "generated_at": recommendations[0].created_at if recommendations else None,
            "cache_status": "HIT",
            "refresh_requested": False
        }

        logger.info(f"추천 조회 완료: user_id={user_id}, count={len(recommendations)}")
        return RecommendationsResponse(**response_data)

    except Exception as e:
        logger.error(f"추천 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{user_id}/interests", response_model=InterestsAnalysisResponse)
async def get_interests_analysis(
    user_id: int,
    include_keywords: bool = Query(True, description="키워드 레벨 분석 포함"),
    include_topics: bool = Query(True, description="토픽 레벨 분석 포함"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    관심사 분석 결과 조회

    사용 시나리오:
    - 설정 페이지 "내 관심사" 섹션
    - 사용자 피드백 수집 (관심사 정확도)
    - 관리자 도구 사용자 세그먼트 분석
    """
    try:
        user_profile_repo = UserProfileRepository()

        profile = await user_profile_repo.get_or_create_profile(session, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")

        # 벡터 메타데이터에서 관심사 정보 추출
        vector_metadata = profile.vector_metadata or {}

        response_data = {
            "user_id": user_id,
            "interests": {
                "keywords": vector_metadata.get("keywords", {}) if include_keywords else {},
                "topics": vector_metadata.get("topics", {}) if include_topics else {},
                "categories": vector_metadata.get("categories", {}),
                "concepts": vector_metadata.get("concepts", {})
            },
            "analysis_metadata": {
                "last_updated": profile.updated_at,
                "vector_strength": profile.vector_strength or 0.0,
                "data_sources": vector_metadata.get("data_sources", []),
                "algorithm_version": vector_metadata.get("algorithm_version", "unknown")
            }
        }

        logger.info(f"관심사 분석 조회 완료: user_id={user_id}")
        return InterestsAnalysisResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"관심사 분석 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    비동기 작업 상태 조회 (프로필 재생성, 추천 갱신 등)

    사용 시나리오:
    - 프로필 재생성 진행 상황 추적
    - 대용량 처리 작업 모니터링
    - 사용자에게 진행 상태 피드백
    """
    try:
        # TODO 작업 상태 조회 기능 구현
        # Redis나 별도 작업 상태 저장소에서 조회
        # 임시로 하드코딩된 응답 (실제로는 작업 상태 추적 시스템 필요)

        response_data = {
            "job_id": job_id,
            "status": "IN_PROGRESS",  # PENDING, IN_PROGRESS, COMPLETED, FAILED
            "progress_percentage": 75,
            "started_at": datetime.now(),
            "estimated_completion": datetime.now(),
            "result_data": None,
            "error_message": None
        }

        logger.info(f"작업 상태 조회: job_id={job_id}")
        return JobStatusResponse(**response_data)

    except Exception as e:
        logger.error(f"작업 상태 조회 실패: job_id={job_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{user_id}/metrics", response_model=ProfileMetricsResponse)
async def get_profile_metrics(
    user_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """
    프로필 품질 지표 조회

    사용 시나리오:
    - 관리자 대시보드
    - 프로필 품질 모니터링
    - 알고리즘 성능 평가
    """
    try:
        user_profile_repo = UserProfileRepository()

        profile = await user_profile_repo.get_or_create_profile(session, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")

        # 유사도 수 계산
        similar_count = len(await user_profile_repo.get_similar_users(
            session, user_id, limit=100, min_similarity=0.5
        ))

        response_data = {
            "user_id": user_id,
            "vector_strength": profile.vector_strength or 0.0,
            "completeness_score": profile.completeness_score or 0,
            "similar_users_count": similar_count,
            "last_updated": profile.updated_at,
            "data_freshness_hours": (datetime.now() - profile.updated_at).total_seconds() / 3600,
            "quality_indicators": {
                "has_vector": bool(profile.profile_vector),
                "vector_dimension": len(profile.profile_vector) if profile.profile_vector else 0,
                "has_metadata": bool(profile.vector_metadata),
                "is_recent": (datetime.now() - profile.updated_at).days < 7
            }
        }

        logger.info(f"프로필 지표 조회 완료: user_id={user_id}")
        return ProfileMetricsResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프로필 지표 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
