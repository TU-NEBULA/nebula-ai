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
    async def get_or_create_ai_profile(
        session: AsyncSession,
        user_id: int
    ) -> UserAIProfile:
        """사용자의 AI 프로필을 조회하거나 생성합니다."""
        stmt = select(UserAIProfile).where(UserAIProfile.user_id == str(user_id))
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        
        if not profile:
            profile = UserAIProfile(
                user_id=str(user_id),
                preferred_search_domains=None,
                ai_interaction_style="detailed",
                current_interests=None,
                learning_preferences=None,
                notification_settings=None,
                profile_vector=None
            )
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            logger.info(f"🆕 새 AI 프로필 생성 - user_id: {user_id}")
        
        return profile

    @staticmethod
    async def update_chat_statistics(
        session: AsyncSession,
        user_id: int,
        session_duration_minutes: float,
        message_count: int,
        new_keywords: List[str] = None
    ) -> UserAIProfile:
        """채팅 통계를 업데이트합니다."""
        try:
            # 기존 프로필 조회 또는 생성
            profile = await AIProfileRepository.get_or_create_ai_profile(session, user_id)
            
            # 키워드를 current_interests에 저장 (임시 호환성)
            if new_keywords:
                current_interests = profile.current_interests or ""
                # 키워드들을 쉼표로 구분해서 저장
                new_interests_text = ", ".join(new_keywords)
                
                if current_interests:
                    # 기존 관심사에 새 키워드 추가
                    combined_interests = f"{current_interests}, {new_interests_text}"
                    # 중복 제거하고 최대 길이 제한
                    unique_interests = list(set(combined_interests.split(", ")))
                    profile.current_interests = ", ".join(unique_interests[-20:])  # 최대 20개
                else:
                    profile.current_interests = new_interests_text
            
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            
            logger.info(
                f"📊 AI 프로필 업데이트 완료 - user_id: {user_id}, "
                f"관심사: {profile.current_interests}"
            )
            
            return profile
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ AI 프로필 통계 업데이트 실패 - user_id: {user_id}: {e}")
            raise

    @staticmethod
    async def update_user_preferences(
        session: AsyncSession,
        user_id: int,
        preferred_response_style: str = None,
        preferred_language: str = None,
        preferred_content_types: List[str] = None
    ) -> UserAIProfile:
        """사용자 선호도를 업데이트합니다."""
        try:
            profile = await AIProfileRepository.get_or_create_ai_profile(session, user_id)
            
            if preferred_response_style:
                profile.ai_interaction_style = preferred_response_style
            
            if preferred_language:
                # 언어 설정을 learning_preferences에 저장
                profile.learning_preferences = f"language:{preferred_language}"
                
            if preferred_content_types:
                # 콘텐츠 타입을 preferred_search_domains에 저장
                profile.preferred_search_domains = ", ".join(preferred_content_types)
            
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            
            logger.info(f"⚙️ AI 프로필 선호도 업데이트 완료 - user_id: {user_id}")
            return profile
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ AI 프로필 선호도 업데이트 실패 - user_id: {user_id}: {e}")
            raise

    @staticmethod
    async def record_feedback(
        session: AsyncSession,
        user_id: int,
        is_positive: bool
    ) -> UserAIProfile:
        """사용자 피드백을 기록합니다."""
        try:
            profile = await AIProfileRepository.get_or_create_ai_profile(session, user_id)
            
            # 피드백을 notification_settings에 JSON 형태로 저장
            import json
            current_settings = profile.notification_settings or "{}"
            try:
                settings_dict = json.loads(current_settings)
            except:
                settings_dict = {}
                
            if 'feedback' not in settings_dict:
                settings_dict['feedback'] = {'positive': 0, 'negative': 0}
                
            if is_positive:
                settings_dict['feedback']['positive'] += 1
            else:
                settings_dict['feedback']['negative'] += 1
                
            profile.notification_settings = json.dumps(settings_dict)
            
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            
            logger.info(f"👍👎 피드백 기록 완료 - user_id: {user_id}, positive: {is_positive}")
            return profile
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ 피드백 기록 실패 - user_id: {user_id}: {e}")
            raise

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
