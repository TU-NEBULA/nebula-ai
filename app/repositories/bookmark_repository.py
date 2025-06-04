"""
북마크 Repository

북마크와 AI 프로필에 대한 데이터 접근을 담당합니다.
Repository 패턴을 통해 데이터베이스 로직을 캡슐화합니다.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from loguru import logger
from sqlmodel import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookmark import BookmarkAIStatus, UserAIProfile


class BookmarkRepository:
    """북마크 관련 데이터 접근을 처리하는 Repository"""

    @staticmethod
    async def get_user_bookmarks(
        session: AsyncSession,
        user_id: int,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[BookmarkAIStatus]:
        """사용자의 모든 북마크를 조회합니다."""
        stmt = (
            select(BookmarkAIStatus)
            .where(BookmarkAIStatus.user_id == user_id)
            .order_by(BookmarkAIStatus.created_at.desc())  # pylint: disable=no-member
            .offset(offset)
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        bookmarks = list(result.scalars().all())

        logger.debug(f"📚 사용자 {user_id} 북마크 조회 - 총 {len(bookmarks)}개")
        return bookmarks

    @staticmethod
    async def get_recent_bookmarks(
        session: AsyncSession,
        user_id: int,
        days: int = 30,
        limit: Optional[int] = None
    ) -> List[BookmarkAIStatus]:
        """사용자의 최근 북마크를 조회합니다."""
        recent_date = datetime.utcnow() - timedelta(days=days)

        stmt = (
            select(BookmarkAIStatus)
            .where(
                and_(
                    BookmarkAIStatus.user_id == user_id,
                    BookmarkAIStatus.created_at >= recent_date
                )
            )
            .order_by(BookmarkAIStatus.created_at.desc())  # pylint: disable=no-member
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        bookmarks = list(result.scalars().all())

        logger.debug(f"📚 사용자 {user_id} 최근 {days}일 북마크 조회 - 총 {len(bookmarks)}개")
        return bookmarks

    @staticmethod
    async def get_bookmarks_by_keywords(
        session: AsyncSession,
        user_id: int,
        keywords: List[str]
    ) -> List[BookmarkAIStatus]:
        """키워드로 북마크를 검색합니다."""
        # PostgreSQL의 overlap 연산자를 사용하여 키워드 매칭
        stmt = select(BookmarkAIStatus).where(
            and_(
                BookmarkAIStatus.user_id == user_id,
                # keywords 배열과 겹치는 북마크 찾기 (PostgreSQL 배열 연산)
                # 실제 구현에서는 북마크 모델의 keywords 필드 구조에 따라 조정 필요
            )
        )

        result = await session.execute(stmt)
        bookmarks = list(result.scalars().all())

        logger.debug(f"🔍 키워드 검색 결과 - 사용자 {user_id}, 키워드: {keywords}, 결과: {len(bookmarks)}개")
        return bookmarks

    @staticmethod
    async def get_bookmarks_for_analysis(
        session: AsyncSession,
        user_ids: List[int],
        days: int = 7
    ) -> List[BookmarkAIStatus]:
        """분석을 위한 여러 사용자의 북마크를 조회합니다."""
        recent_date = datetime.utcnow() - timedelta(days=days)

        stmt = (
            select(BookmarkAIStatus)
            .where(
                and_(
                    BookmarkAIStatus.user_id.in_(user_ids),  # pylint: disable=no-member
                    BookmarkAIStatus.created_at >= recent_date
                )
            )
            .order_by(BookmarkAIStatus.created_at.desc())  # pylint: disable=no-member
        )

        result = await session.execute(stmt)
        bookmarks = list(result.scalars().all())

        logger.debug(f"📊 분석용 북마크 조회 - 사용자 {len(user_ids)}명, 최근 {days}일, 결과: {len(bookmarks)}개")
        return bookmarks

    @staticmethod
    async def get_bookmark_keywords_frequency(
        session: AsyncSession,
        user_id: int
    ) -> Dict[str, int]:
        """사용자 북마크의 키워드 빈도를 계산합니다."""
        bookmarks = await BookmarkRepository.get_user_bookmarks(session, user_id)

        keyword_freq = {}
        for bookmark in bookmarks:
            if hasattr(bookmark, 'keywords') and bookmark.keywords:
                for keyword in bookmark.keywords:
                    keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1

        logger.debug(f"🏷️ 사용자 {user_id} 키워드 빈도 계산 - 총 {len(keyword_freq)}개 키워드")
        return keyword_freq


class AIProfileRepository:
    """AI 프로필 관련 데이터 접근을 처리하는 Repository"""

    @staticmethod
    async def get_user_ai_profiles(
        session: AsyncSession,
        user_id: int
    ) -> List[UserAIProfile]:
        """사용자의 AI 프로필을 조회합니다."""
        stmt = select(UserAIProfile).where(UserAIProfile.user_id == user_id)
        result = await session.execute(stmt)
        profiles = list(result.scalars().all())

        logger.debug(f"🤖 사용자 {user_id} AI 프로필 조회 - 총 {len(profiles)}개")
        return profiles

    @staticmethod
    async def get_ai_profile_interests(
        session: AsyncSession,
        user_id: int
    ) -> List[str]:
        """사용자 AI 프로필에서 관심사를 추출합니다."""
        profiles = await AIProfileRepository.get_user_ai_profiles(session, user_id)

        interests = []
        for profile in profiles:
            if hasattr(profile, 'interests') and profile.interests:
                interests.extend(profile.interests)

        logger.debug(f"🎯 사용자 {user_id} AI 프로필 관심사 추출 - 총 {len(interests)}개")
        return interests

    @staticmethod
    async def get_ai_profile_preferences(
        session: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """사용자 AI 프로필의 선호도를 조회합니다."""
        profiles = await AIProfileRepository.get_user_ai_profiles(session, user_id)

        combined_preferences = {}
        for profile in profiles:
            if hasattr(profile, 'preferences') and profile.preferences:
                if isinstance(profile.preferences, dict):
                    combined_preferences.update(profile.preferences)

        logger.debug(f"⚙️ 사용자 {user_id} AI 프로필 선호도 조회")
        return combined_preferences
