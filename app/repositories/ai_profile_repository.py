"""
AI 프로필 Repository

사용자 AI 프로필 관련 데이터 접근을 처리합니다.
"""

import json
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.bookmark import UserAIProfile


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
        stmt = select(UserAIProfile).where(UserAIProfile.user_id == user_id)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        
        if not profile:
            profile = UserAIProfile(
                user_id=user_id,
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
            
            # 키워드를 current_interests에 저장 (가중치 순서 유지)
            if new_keywords:
                current_interests = profile.current_interests or ""
                
                if current_interests:
                    # 기존 관심사를 리스트로 변환
                    existing_keywords = [kw.strip() for kw in current_interests.split(",") if kw.strip()]
                    
                    # 새 키워드들과 기존 키워드들을 순서 유지하며 중복 제거
                    # 1. 새 키워드 우선 (가중치 순서 유지)
                    # 2. 기존 키워드 중 새 키워드에 없는 것들 추가
                    seen = set()
                    combined_keywords = []
                    
                    # 새 키워드 먼저 (가중치 높은 순서)
                    for keyword in new_keywords:
                        if keyword and keyword not in seen:
                            combined_keywords.append(keyword)
                            seen.add(keyword)
                    
                    # 기존 키워드 중 중복되지 않는 것들 추가
                    for keyword in existing_keywords:
                        if keyword and keyword not in seen:
                            combined_keywords.append(keyword)
                            seen.add(keyword)
                    
                    # 최대 50개 키워드만 유지 (가중치 순서 보장)
                    profile.current_interests = ", ".join(combined_keywords[:50])
                else:
                    # 처음 저장하는 경우 - 가중치 순서 그대로 저장
                    profile.current_interests = ", ".join(new_keywords[:50])
            
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