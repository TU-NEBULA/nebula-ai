"""
사용자 프로필 Repository

사용자 프로필, 유사도, 추천 관련 데이터 접근을 담당합니다.
Repository 패턴을 통해 데이터베이스 로직을 캡슐화합니다.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from loguru import logger
from sqlmodel import select, and_, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_profile import (
    UserProfile, UserSimilarity, Recommendation,
    TrendAnalysis
)


class UserProfileRepository:
    """사용자 프로필 관련 데이터 접근을 처리하는 Repository"""

    @staticmethod
    async def get_or_create_profile(
        session: AsyncSession,
        user_id: int
    ) -> UserProfile:
        """프로필을 조회하거나 새로 생성합니다."""
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            profile = UserProfile(
                user_id=user_id,
                keywords_frequency={},
                categories_distribution={},
                activity_patterns={},
                profile_vector=[0.0] * 1536,  # 기본 벡터
                preferences={}
            )
            session.add(profile)
            await session.flush()  # ID 생성을 위해
            logger.info(f"🆕 새로운 사용자 프로필 생성: {user_id}")

        return profile

    @staticmethod
    async def update_profile(
        session: AsyncSession,
        user_id: int,
        **kwargs
    ) -> UserProfile:
        """사용자 프로필을 업데이트합니다."""
        profile = await UserProfileRepository.get_or_create_profile(session, user_id)

        # 전달받은 속성들을 업데이트
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        session.add(profile)
        await session.commit()
        await session.refresh(profile)

        logger.debug(f"📝 사용자 {user_id} 프로필 업데이트 완료")
        return profile

    @staticmethod
    async def get_profiles_with_vectors(
        session: AsyncSession,
        exclude_user_id: Optional[int] = None
    ) -> List[UserProfile]:
        """벡터가 있는 프로필들을 조회합니다."""
        conditions = [UserProfile.profile_vector != None]  # pylint: disable=singleton-comparison

        if exclude_user_id:
            conditions.append(UserProfile.user_id != exclude_user_id)

        stmt = select(UserProfile).where(and_(*conditions))
        result = await session.execute(stmt)
        profiles = list(result.scalars().all())

        logger.debug(f"🔍 벡터 보유 프로필 조회 - 총 {len(profiles)}개")
        return profiles

    @staticmethod
    async def save_user_similarity(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        session: AsyncSession,
        user_id_1: int,
        user_id_2: int,
        similarity_score: float,
        calculation_method: str = "cosine_vector",
        metadata: Optional[Dict] = None
    ) -> UserSimilarity:
        """사용자 유사도를 저장합니다."""
        # 기존 유사도 레코드 삭제
        await UserProfileRepository.delete_existing_similarity(
            session, user_id_1, user_id_2
        )

        similarity = UserSimilarity(
            user_id_1=user_id_1,
            user_id_2=user_id_2,
            similarity_score=similarity_score,
            calculation_method=calculation_method,
            metadata=metadata or {}
        )

        session.add(similarity)
        logger.debug(
            f"💾 유사도 저장 - 사용자 {user_id_1} ↔ {user_id_2}: {similarity_score:.3f}"
        )
        return similarity

    @staticmethod
    async def delete_existing_similarity(
        session: AsyncSession,
        user_id_1: int,
        user_id_2: int
    ):
        """기존 유사도 레코드를 삭제합니다."""
        # 양방향 삭제
        for uid1, uid2 in [(user_id_1, user_id_2), (user_id_2, user_id_1)]:
            stmt = delete(UserSimilarity).where(
                and_(
                    UserSimilarity.user_id_1 == uid1,
                    UserSimilarity.user_id_2 == uid2
                )
            )
            await session.execute(stmt)

    @staticmethod
    async def get_similar_users(
        session: AsyncSession,
        user_id: int,
        min_similarity: float = 0.7,
        limit: int = 10
    ) -> List[UserSimilarity]:
        """유사한 사용자들을 조회합니다."""
        stmt = (
            select(UserSimilarity)
            .where(
                and_(
                    UserSimilarity.user_id_1 == user_id,
                    UserSimilarity.similarity_score >= min_similarity
                )
            )
            .order_by(desc(UserSimilarity.similarity_score))
            .limit(limit)
        )

        result = await session.execute(stmt)
        similarities = list(result.scalars().all())

        logger.debug(f"👥 사용자 {user_id} 유사 사용자 조회 - {len(similarities)}명")
        return similarities


class RecommendationRepository:
    """추천 관련 데이터 접근을 처리하는 Repository"""

    @staticmethod
    async def save_recommendation(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        session: AsyncSession,
        user_id: int,
        content_type: str,
        content_id: str,
        relevance_score: float,
        recommendation_reason: str,
        metadata: Optional[Dict] = None
    ) -> Recommendation:
        """추천을 저장합니다."""
        recommendation = Recommendation(
            user_id=user_id,
            content_type=content_type,
            content_id=content_id,
            relevance_score=relevance_score,
            recommendation_reason=recommendation_reason,
            metadata=metadata or {}
        )

        session.add(recommendation)
        logger.debug(
            f"🎯 추천 저장 - 사용자 {user_id}, 타입: {content_type}, "
            f"점수: {relevance_score:.3f}"
        )
        return recommendation

    @staticmethod
    async def get_user_recommendations(
        session: AsyncSession,
        user_id: int,
        content_type: Optional[str] = None,
        min_relevance: float = 0.0,
        limit: int = 20
    ) -> List[Recommendation]:
        """사용자 추천을 조회합니다."""
        conditions = [Recommendation.user_id == user_id]

        if content_type:
            conditions.append(Recommendation.content_type == content_type)

        if min_relevance > 0:
            conditions.append(Recommendation.relevance_score >= min_relevance)

        stmt = (
            select(Recommendation)
            .where(and_(*conditions))
            .order_by(desc(Recommendation.relevance_score))
            .limit(limit)
        )

        result = await session.execute(stmt)
        recommendations = list(result.scalars().all())

        logger.debug(f"📋 사용자 {user_id} 추천 조회 - {len(recommendations)}개")
        return recommendations

    @staticmethod
    async def update_recommendation_feedback(
        session: AsyncSession,
        recommendation_id: int,
        user_feedback: str,
        clicked: bool = False
    ) -> Optional[Recommendation]:
        """추천 피드백을 업데이트합니다."""
        stmt = select(Recommendation).where(Recommendation.id == recommendation_id)
        result = await session.execute(stmt)
        recommendation = result.scalar_one_or_none()

        if recommendation:
            recommendation.user_feedback = user_feedback
            recommendation.clicked = clicked
            recommendation.feedback_date = datetime.now(timezone.utc)

            session.add(recommendation)
            logger.debug(
                f"📝 추천 피드백 업데이트 - ID: {recommendation_id}, "
                f"피드백: {user_feedback}"
            )

        return recommendation


class TrendAnalysisRepository:
    """트렌드 분석 관련 데이터 접근을 처리하는 Repository"""

    @staticmethod
    async def save_trend_analysis(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        session: AsyncSession,
        period_start: datetime,
        period_end: datetime,
        trending_keywords: List[str],
        keyword_frequencies: Dict[str, int],
        category_trends: Dict[str, Any],
        metadata: Optional[Dict] = None
    ) -> TrendAnalysis:
        """트렌드 분석 결과를 저장합니다."""
        trend_analysis = TrendAnalysis(
            period_start=period_start,
            period_end=period_end,
            trending_keywords=trending_keywords,
            keyword_frequencies=keyword_frequencies,
            category_trends=category_trends,
            metadata=metadata or {}
        )

        session.add(trend_analysis)
        logger.debug(
            f"📈 트렌드 분석 저장 - 기간: {period_start} ~ {period_end}, "
            f"키워드: {len(trending_keywords)}개"
        )
        return trend_analysis

    @staticmethod
    async def get_latest_trend_analysis(
        session: AsyncSession,
        days: int = 7
    ) -> Optional[TrendAnalysis]:
        """최신 트렌드 분석을 조회합니다."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = (
            select(TrendAnalysis)
            .where(TrendAnalysis.period_end >= recent_date)
            .order_by(desc(TrendAnalysis.period_end))
            .limit(1)
        )

        result = await session.execute(stmt)
        trend_analysis = result.scalar_one_or_none()

        if trend_analysis:
            logger.debug(
                f"📊 최신 트렌드 분석 조회 - 기간: {trend_analysis.period_start} "
                f"~ {trend_analysis.period_end}"
            )

        return trend_analysis

    @staticmethod
    async def get_trending_keywords(
        session: AsyncSession,
        days: int = 7,
        limit: int = 10
    ) -> List[str]:
        """최신 트렌딩 키워드를 조회합니다."""
        trend_analysis = await TrendAnalysisRepository.get_latest_trend_analysis(
            session, days
        )

        if trend_analysis and trend_analysis.trending_keywords:
            return trend_analysis.trending_keywords[:limit]

        return []
