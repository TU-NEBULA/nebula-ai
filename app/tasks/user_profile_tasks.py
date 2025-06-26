"""
사용자 프로필 백그라운드 태스크 모듈

이 모듈은 사용자 프로필 시스템의 무거운 처리 작업들을 백그라운드에서 수행하는
Celery 태스크들을 정의합니다:

1. 프로필 벡터 생성 및 업데이트
2. 사용자 유사도 계산
3. 개인화 추천 생성
4. 클러스터링 업데이트
5. 학습 경로 생성
6. 트렌드 분석
"""

import asyncio
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import concurrent.futures

import numpy as np
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.core.celery_worker import celery
from app.core.database import get_async_session
from app.models.user_profile import UserProfile
from app.external.openai_service import OpenAIService

# Repository 임포트
from app.repositories import (
    BookmarkRepository,
    ChatRepository,
    UserProfileRepository
)
from app.repositories.ai_profile_repository import AIProfileRepository

from app.services.vector_generator import VectorGenerator, ActivityData, ActivityType
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.user_profile_repository import RecommendationRepository
from app.utils.async_utils import run_async_safely


@dataclass
class ProfileUpdateData:
    """프로필 업데이트 데이터를 담는 데이터클래스"""
    user_id: int
    update_type: str  # 'full', 'incremental', 'activity_only'
    source_data: Optional[Dict] = None
    force_recalculate: bool = False


class UserProfileProcessor:
    """사용자 프로필 처리 핵심 로직 - Repository 패턴 + 고급 벡터 생성"""

    def __init__(
        self,
        chat_repo: ChatRepository,
        bookmark_repo: BookmarkRepository,
        ai_profile_repo: AIProfileRepository,
        user_profile_repo: UserProfileRepository
    ):
        self.chat_repo = chat_repo
        self.bookmark_repo = bookmark_repo
        self.ai_profile_repo = ai_profile_repo
        self.user_profile_repo = user_profile_repo
        self.openai_service = OpenAIService()

        # 고급 벡터 생성기 초기화
        self.vector_generator = VectorGenerator(self.openai_service)

    async def extract_user_interests(self, session: AsyncSession, user_id: int) -> Dict[str, Any]:
        """사용자의 관심사를 추출합니다."""
        logger.info(f"🔍 사용자 {user_id}의 관심사 추출 시작")

        # 1. 채팅 데이터에서 관심사 추출
        chat_data = await self._extract_from_chats(session, user_id)

        # 2. 북마크 데이터에서 관심사 추출
        bookmark_data = await self._extract_from_bookmarks(session, user_id)

        # 3. AI 프로필 데이터에서 관심사 추출
        ai_profile_data = await self._extract_from_ai_profiles(session, user_id)

        # 4. 통합 분석
        combined_data = self._combine_interest_data(chat_data, bookmark_data, ai_profile_data)

        logger.info(f"✅ 사용자 {user_id} 관심사 추출 완료")
        return combined_data

    async def collect_user_activities(
        self, session: AsyncSession, user_id: int
    ) -> List[ActivityData]:
        """사용자의 모든 활동을 수집하여 ActivityData 형태로 변환합니다."""
        activities = []

        # 1. 채팅 메시지 수집
        recent_messages = await self.chat_repo.get_user_recent_messages(
            session, user_id, days=60, role='user', limit=100
        )

        for message in recent_messages:
            activities.append(ActivityData(
                activity_type=ActivityType.CHAT,
                content=message.content,
                created_at=message.created_at,
                metadata={"session_id": str(message.session_id)},
                weight=1.0
            ))

        # 2. 북마크 수집
        bookmarks = await self.bookmark_repo.get_recent_bookmarks(
            session, user_id, days=90, limit=200
        )

        for bookmark in bookmarks:
            # 북마크 콘텐츠 구성 (제목 + 요약 + 키워드)
            content_parts = []
            if bookmark.title:
                content_parts.append(bookmark.title)
            if hasattr(bookmark, 'summary') and bookmark.summary:
                content_parts.append(bookmark.summary)
            if hasattr(bookmark, 'keywords') and bookmark.keywords:
                content_parts.extend(bookmark.keywords)

            if content_parts:
                activities.append(ActivityData(
                    activity_type=ActivityType.BOOKMARK,
                    content=" ".join(content_parts),
                    created_at=bookmark.created_at,
                    metadata={
                        "url": bookmark.url,
                        "bookmark_id": bookmark.id
                    },
                    weight=1.5  # 북마크는 더 중요한 관심사 지표
                ))

        # 3. AI 프로필 수집
        ai_profiles = await self.ai_profile_repo.get_user_ai_profiles(session, user_id)

        for profile in ai_profiles:
            content_parts = []
            if hasattr(profile, 'interests') and profile.interests:
                content_parts.extend(profile.interests)
            if hasattr(profile, 'preferences') and profile.preferences:
                content_parts.append(str(profile.preferences))

            if content_parts:
                activities.append(ActivityData(
                    activity_type=ActivityType.AI_PROFILE,
                    content=" ".join(content_parts),
                    created_at=getattr(profile, 'created_at', datetime.now(timezone.utc)),
                    metadata={"profile_id": profile.id},
                    weight=1.2
                ))

        logger.info(
            f"📊 활동 수집 완료 - 총 {len(activities)}개 "
            f"(채팅: {len(recent_messages)}, 북마크: {len(bookmarks)}, "
            f"프로필: {len(ai_profiles)})"
        )
        return activities

    async def generate_profile_vector_advanced(
        self,
        session: AsyncSession,
        user_id: int,
        user_preferences: Optional[Dict] = None
    ) -> Tuple[List[float], Dict[str, Any]]:
        """고급 벡터 생성 알고리즘을 사용하여 프로필 벡터를 생성합니다."""
        logger.info(f"🧠 고급 프로필 벡터 생성 시작 - 사용자 {user_id}")

        try:
            # 1. 사용자 활동 수집
            activities = await self.collect_user_activities(session, user_id)

            if not activities:
                logger.warning(f"사용자 {user_id}의 활동 데이터가 없음")
                return [0.0] * 1536, {"status": "no_activities", "user_id": user_id}

            # 2. 고급 벡터 생성기로 벡터 생성
            vector, metadata = await self.vector_generator.generate_profile_vector(
                activities, user_preferences
            )

            # 3. 사용자 정보 추가
            metadata.update({
                "user_id": user_id,
                "generation_method": "advanced_multilayer",
                "total_activities_processed": len(activities)
            })

            logger.info(
                f"✅ 고급 벡터 생성 완료 - 사용자 {user_id}, "
                f"벡터 강도: {np.linalg.norm(vector):.3f}"
            )
            return vector, metadata

        except (SQLAlchemyError, ValueError, TypeError, ConnectionError, TimeoutError) as e:
            logger.error(f"❌ 고급 벡터 생성 실패 - 사용자 {user_id}: {e}")
            return [0.0] * 1536, {"status": "error", "error": str(e), "user_id": user_id}

    async def update_vector_incrementally(
        self,
        session: AsyncSession,
        user_id: int,
        current_vector: List[float],
        learning_rate: float = 0.1
    ) -> Tuple[List[float], Dict[str, Any]]:
        """기존 벡터를 새로운 활동으로 점진적 업데이트합니다."""
        logger.info(f"🔄 점진적 벡터 업데이트 시작 - 사용자 {user_id}")

        try:
            # 최근 1주일 활동만 수집
            recent_activities = []

            # 최근 채팅
            recent_messages = await self.chat_repo.get_user_recent_messages(
                session, user_id, days=7, role='user', limit=20
            )

            for message in recent_messages:
                recent_activities.append(ActivityData(
                    activity_type=ActivityType.CHAT,
                    content=message.content,
                    created_at=message.created_at,
                    weight=1.0
                ))

            # 최근 북마크
            recent_bookmarks = await self.bookmark_repo.get_recent_bookmarks(
                session, user_id, days=7, limit=20
            )

            for bookmark in recent_bookmarks:
                content_parts = []
                if bookmark.title:
                    content_parts.append(bookmark.title)
                if hasattr(bookmark, 'summary') and bookmark.summary:
                    content_parts.append(bookmark.summary)

                if content_parts:
                    recent_activities.append(ActivityData(
                        activity_type=ActivityType.BOOKMARK,
                        content=" ".join(content_parts),
                        created_at=bookmark.created_at,
                        weight=1.5
                    ))

            if not recent_activities:
                logger.info(f"사용자 {user_id}의 최근 활동이 없음 - 벡터 유지")
                return current_vector, {"status": "no_recent_activities", "user_id": user_id}

            # 점진적 업데이트
            updated_vector, metadata = await self.vector_generator.update_vector_incrementally(
                current_vector, recent_activities, learning_rate
            )

            metadata["user_id"] = user_id

            logger.info(
                f"✅ 점진적 업데이트 완료 - 사용자 {user_id}, "
                f"활동 수: {len(recent_activities)}개"
            )
            return updated_vector, metadata

        except (SQLAlchemyError, ValueError, TypeError, ConnectionError, TimeoutError) as e:
            logger.error(f"❌ 점진적 업데이트 실패 - 사용자 {user_id}: {e}")
            return current_vector, {"status": "error", "error": str(e), "user_id": user_id}

    # 기존 메서드들은 유지 (호환성을 위해)
    async def _extract_from_chats(self, session: AsyncSession, user_id: int) -> Dict:
        """채팅 데이터에서 관심사 추출 - Repository 사용"""
        # Repository 메서드 사용
        recent_messages = await self.chat_repo.get_user_recent_messages(
            session, user_id, days=30, role='user', limit=50
        )

        if not recent_messages:
            return {
                "keywords": [], "topics": [], "categories": [],
                "message_count": 0, "activity_level": "low"
            }

        # 메시지 내용 수집
        message_contents = [msg.content for msg in recent_messages]

        # OpenAI로 키워드 및 토픽 추출
        combined_text = " ".join(message_contents)
        analysis = await self._analyze_text_interests(combined_text, "chat")

        return {
            "keywords": analysis.get("keywords", []),
            "topics": analysis.get("topics", []),
            "categories": analysis.get("categories", []),
            "message_count": len(recent_messages),
            "activity_level": (
                "high" if len(recent_messages) > 20
                else "medium" if len(recent_messages) > 5
                else "low"
            )
        }

    async def _extract_from_bookmarks(self, session: AsyncSession, user_id: int) -> Dict:
        """북마크 데이터에서 관심사 추출 - Repository 사용"""
        # Repository 메서드 사용
        bookmarks = await self.bookmark_repo.get_user_bookmarks(session, user_id)

        if not bookmarks:
            return {
                "keywords": [], "topics": [], "categories": [],
                "keyword_frequency": {}, "bookmark_count": 0
            }

        # 북마크 키워드 빈도 계산 (Repository 메서드 사용)
        keyword_freq = await self.bookmark_repo.get_keyword_frequency(
            session, user_id, days=180
        )

        # 북마크 키워드, 요약, 제목 수집
        bookmark_texts = []
        all_keywords = list(keyword_freq.keys())

        for bookmark in bookmarks:
            if bookmark.summary:
                bookmark_texts.append(bookmark.summary)
            if bookmark.title:
                bookmark_texts.append(bookmark.title)

        # 텍스트 분석
        combined_text = " ".join(bookmark_texts) if bookmark_texts else ""
        analysis = await self._analyze_text_interests(combined_text, "bookmark")

        return {
            "keywords": list(set(all_keywords + analysis.get("keywords", []))),
            "topics": analysis.get("topics", []),
            "categories": analysis.get("categories", []),
            "keyword_frequency": keyword_freq,
            "bookmark_count": len(bookmarks)
        }

    async def _extract_from_ai_profiles(self, session: AsyncSession, user_id: int) -> Dict:
        """AI 프로필 데이터에서 관심사 추출 - Repository 사용"""
        # Repository 메서드 사용
        interests = await self.ai_profile_repo.get_ai_profile_interests(session, user_id)
        preferences = await self.ai_profile_repo.get_ai_profile_preferences(session, user_id)

        if not interests and not preferences:
            return {"keywords": [], "topics": [], "categories": []}

        # AI 프로필에서 관심사 정보 수집
        profile_data = interests.copy()
        if preferences:
            profile_data.append(str(preferences))

        combined_text = " ".join(profile_data) if profile_data else ""
        analysis = await self._analyze_text_interests(combined_text, "ai_profile")

        return {
            "keywords": analysis.get("keywords", []),
            "topics": analysis.get("topics", []),
            "categories": analysis.get("categories", []),
            "profile_count": len(interests) + (1 if preferences else 0)
        }

    async def _analyze_text_interests(self, text: str, source_type: str) -> Dict:
        """텍스트에서 관심사를 분석합니다."""
        if not text.strip():
            return {"keywords": [], "topics": [], "categories": []}

        try:
            prompt = f"""
            다음 {source_type} 텍스트를 분석하여 사용자의 관심사를 추출해주세요:

            텍스트: {text[:2000]}  # 토큰 제한

            다음 형식으로 JSON을 반환해주세요:
            {{
                "keywords": ["키워드1", "키워드2", ...],  // 최대 20개
                "topics": ["주제1", "주제2", ...],        // 최대 10개
                "categories": ["카테고리1", "카테고리2", ...] // 최대 5개
            }}

            키워드는 구체적이고 의미있는 단어들로, 토픽은 더 넓은 주제 영역으로,
            카테고리는 가장 일반적인 분류로 추출해주세요.
            """

            response = await self.openai_service.generate_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4o-mini",
                temperature=0.3
            )

            # JSON 파싱 시도
            try:
                result = json.loads(response.choices[0].message.content)
                return result
            except (ValueError, TypeError, json.JSONDecodeError):
                logger.warning(
                    f"JSON 파싱 실패, 기본값 반환: "
                    f"{response.choices[0].message.content}"
                )
                return {"keywords": [], "topics": [], "categories": []}

        except (ValueError, TypeError, ConnectionError, TimeoutError) as e:
            logger.error(f"관심사 분석 중 오류: {e}")
            return {"keywords": [], "topics": [], "categories": []}

    def _combine_interest_data(
        self,
        chat_data: Dict,
        bookmark_data: Dict,
        ai_profile_data: Dict
    ) -> Dict:
        """여러 소스의 관심사 데이터를 통합합니다."""
        combined_keywords = []
        combined_topics = []
        combined_categories = []

        # 키워드 통합 (빈도 고려)
        keyword_scores = {}

        for data, weight in [
            (chat_data, 1.0), (bookmark_data, 1.5), (ai_profile_data, 1.2)
        ]:
            for keyword in data.get("keywords", []):
                keyword_scores[keyword] = keyword_scores.get(keyword, 0) + weight

        # 상위 키워드 선택
        sorted_keywords = sorted(
            keyword_scores.items(), key=lambda x: x[1], reverse=True
        )
        combined_keywords = [kw for kw, _ in sorted_keywords[:30]]

        # 토픽과 카테고리는 단순 통합 후 중복 제거
        for data in [chat_data, bookmark_data, ai_profile_data]:
            combined_topics.extend(data.get("topics", []))
            combined_categories.extend(data.get("categories", []))

        combined_topics = list(set(combined_topics))[:15]
        combined_categories = list(set(combined_categories))[:8]

        # 키워드 빈도 계산
        keyword_frequency = {}
        for keyword in combined_keywords:
            keyword_frequency[keyword] = keyword_scores.get(keyword, 0)

        # 카테고리 분포 계산
        category_distribution = {}
        total_categories = len(combined_categories)
        for category in combined_categories:
            if total_categories > 0:
                category_distribution[category] = round(
                    1.0 / total_categories, 3
                )
            else:
                category_distribution[category] = 0

        # 활동 패턴 분석
        activity_patterns = {
            "chat_activity": chat_data.get("activity_level", "low"),
            "bookmark_count": bookmark_data.get("bookmark_count", 0),
            "profile_completeness": (
                "high" if ai_profile_data.get("profile_count", 0) > 0
                else "low"
            ),
            "engagement_score": self._calculate_engagement_score(
                chat_data, bookmark_data, ai_profile_data
            )
        }

        return {
            "keywords": combined_keywords,
            "topics": combined_topics,
            "categories": combined_categories,
            "keyword_frequency": keyword_frequency,
            "category_distribution": category_distribution,
            "activity_patterns": activity_patterns,
            "data_sources": {
                "chat_messages": chat_data.get("message_count", 0),
                "bookmarks": bookmark_data.get("bookmark_count", 0),
                "ai_profiles": ai_profile_data.get("profile_count", 0)
            }
        }

    def _calculate_engagement_score(
        self,
        chat_data: Dict,
        bookmark_data: Dict,
        ai_profile_data: Dict
    ) -> float:
        """사용자 참여도 점수 계산"""
        score = 0.0

        # 채팅 활동 (40%)
        chat_count = chat_data.get("message_count", 0)
        score += min(chat_count / 50.0, 1.0) * 0.4

        # 북마크 활동 (35%)
        bookmark_count = bookmark_data.get("bookmark_count", 0)
        score += min(bookmark_count / 20.0, 1.0) * 0.35

        # 프로필 완성도 (25%)
        profile_count = ai_profile_data.get("profile_count", 0)
        score += min(profile_count / 3.0, 1.0) * 0.25

        return round(score, 3)

    # 기존 generate_profile_vector 메서드를 호환성을 위해 유지
    async def generate_profile_vector(self, interests_data: Dict) -> List[float]:
        """관심사 데이터로부터 프로필 벡터를 생성합니다. (기존 호환성 메서드)"""
        # 관심사 데이터를 텍스트로 변환
        text_for_embedding = self._create_embedding_text(interests_data)

        try:
            # OpenAI 임베딩 생성
            embedding = await self.openai_service.create_embedding(
                text=text_for_embedding,
                model="text-embedding-3-small"
            )
            return embedding.data[0].embedding
        except (ValueError, TypeError, RuntimeError) as e:
            logger.error(f"벡터 생성 중 오류: {e}")
            # 기본 벡터 반환 (1536차원 영벡터)
            return [0.0] * 1536

    def _create_embedding_text(self, interests_data: Dict) -> str:
        """임베딩을 위한 텍스트를 생성합니다."""
        parts = []

        # 키워드 추가 (가중치 적용)
        keywords = interests_data.get("keywords", [])
        if keywords:
            # 상위 키워드는 여러 번 반복하여 가중치 부여
            top_keywords = keywords[:10]
            parts.extend(top_keywords * 2)  # 상위 키워드 2번 반복
            parts.extend(keywords[10:])     # 나머지 키워드 1번

        # 토픽 추가
        topics = interests_data.get("topics", [])
        if topics:
            parts.extend(topics)

        # 카테고리 추가 (더 큰 가중치)
        categories = interests_data.get("categories", [])
        if categories:
            parts.extend(categories * 3)  # 카테고리 3번 반복

        return " ".join(parts) if parts else "general user interests"


# Repository 인스턴스들을 생성하는 팩토리 함수
def create_repositories():
    """Repository 인스턴스들을 생성합니다."""
    return {
        'chat_repo': ChatRepository(),
        'bookmark_repo': BookmarkRepository(),
        'ai_profile_repo': AIProfileRepository(),
        'user_profile_repo': UserProfileRepository()
    }


def _run_async_safely(async_func):
    """Celery 워커에서 안전하게 비동기 함수를 실행"""
    try:
        # 현재 실행 중인 이벤트 루프가 있는지 확인
        loop = asyncio.get_running_loop()
        # 이미 이벤트 루프가 실행 중이면 새로운 스레드에서 실행
        logger.debug("기존 이벤트 루프 감지 - 새 스레드에서 실행")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, async_func)
            return future.result(timeout=300)  # 5분 타임아웃
    except RuntimeError:
        # 이벤트 루프가 실행 중이지 않으면 일반적인 방법 사용
        logger.debug("새 이벤트 루프 생성하여 실행")
        return asyncio.run(async_func)
    except Exception as e:
        logger.error("❌ 비동기 실행 중 오류: {}", e)
        raise


@celery.task(
    name="tasks.update_user_profile",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_jitter=True,
)
def update_user_profile_task(self, profile_data_dict: dict) -> dict:
    """사용자 프로필을 업데이트하는 백그라운드 태스크"""
    # self는 Celery task에서 필수이므로 명시적으로 무시
    _ = self
    logger.info(f"🚀 사용자 프로필 업데이트 태스크 시작: {profile_data_dict}")

    try:
        profile_data = ProfileUpdateData(**profile_data_dict)
        result = _run_async_safely(_async_update_profile_logic(profile_data))

        logger.info(f"✅ 사용자 {profile_data.user_id} 프로필 업데이트 완료")
        return {
            "success": True,
            "user_id": profile_data.user_id,
            "update_type": profile_data.update_type,
            "result": result
        }

    except (ValueError, TypeError, RuntimeError) as e:
        logger.error(f"❌ 프로필 업데이트 실패: {e}")
        raise


async def _async_update_profile_logic(profile_data: ProfileUpdateData) -> dict:
    """프로필 업데이트 비동기 로직 - Repository 패턴 + 고급 벡터 생성"""
    async for session in get_async_session():
        # Repository 인스턴스 생성
        repos = create_repositories()

        # Processor에 Repository 주입
        processor = UserProfileProcessor(
            chat_repo=repos['chat_repo'],
            bookmark_repo=repos['bookmark_repo'],
            ai_profile_repo=repos['ai_profile_repo'],
            user_profile_repo=repos['user_profile_repo']
        )

        # 1. 기존 프로필 조회 또는 생성 (Repository 사용)
        profile = await repos['user_profile_repo'].get_or_create_profile(
            session, profile_data.user_id
        )

        # 2. 벡터 생성 방식 선택
        if profile_data.update_type == "advanced" or profile_data.force_recalculate:
            # 고급 벡터 생성 알고리즘 사용
            logger.info(f"🧠 고급 벡터 생성 알고리즘 사용 - 사용자 {profile_data.user_id}")

            # 사용자 선호도 가져오기
            user_preferences = profile.preferences if profile.preferences else {}

            # 고급 벡터 생성
            profile_vector, vector_metadata = await processor.generate_profile_vector_advanced(
                session, profile_data.user_id, user_preferences
            )

            # 벡터 메타데이터에서 관심사 정보 추출
            interests_data = {
                "keywords": list(
                    vector_metadata.get("top_interests", {})
                    .get("keywords", {}).keys()
                ),
                "topics": list(
                    vector_metadata.get("top_interests", {})
                    .get("topics", {}).keys()
                ),
                "categories": list(
                    vector_metadata.get("top_interests", {})
                    .get("categories", {}).keys()
                ),
                "keyword_frequency": (
                    vector_metadata.get("top_interests", {})
                    .get("keywords", {})
                ),
                "category_distribution": {},  # 계산 필요시 추가
                "activity_patterns": {
                    "total_activities": vector_metadata.get("total_activities", 0),
                    "activity_distribution": vector_metadata.get("activity_distribution", {}),
                    "algorithm_version": vector_metadata.get("algorithm_version", "v2.0")
                },
                "data_sources": vector_metadata.get("activity_distribution", {})
            }

        elif profile_data.update_type == "incremental" and profile.profile_vector:
            # 점진적 업데이트 사용
            logger.info(f"🔄 점진적 벡터 업데이트 사용 - 사용자 {profile_data.user_id}")

            learning_rate = 0.1  # 기본 학습률
            if profile.preferences and "learning_rate" in profile.preferences:
                learning_rate = float(profile.preferences["learning_rate"])

            profile_vector, vector_metadata = await processor.update_vector_incrementally(
                session, profile_data.user_id, profile.profile_vector, learning_rate
            )

            # 기존 관심사 데이터 유지하면서 일부 업데이트
            interests_data = await processor.extract_user_interests(
                session, profile_data.user_id
            )

        else:
            # 기존 방식 (호환성)
            logger.info(f"📊 기존 벡터 생성 방식 사용 - 사용자 {profile_data.user_id}")

            # 관심사 데이터 추출
            interests_data = await processor.extract_user_interests(
                session, profile_data.user_id
            )

            # 기존 방식으로 프로필 벡터 생성
            profile_vector = await processor.generate_profile_vector(interests_data)

            vector_metadata = {
                "generation_method": "legacy_simple",
                "total_activities_processed": sum(
                    interests_data.get("data_sources", {}).values()
                )
            }

        # 3. 프로필 업데이트 (Repository 사용)
        current_preferences = profile.preferences or {}

        # 벡터 메타데이터를 선호도에 저장
        current_preferences.update({
            "interests": interests_data["keywords"][:10],
            "categories": (
                interests_data["categories"]
                if "categories" in interests_data
                else []
            ),
            "engagement_score": (
                interests_data.get("activity_patterns", {})
                .get("engagement_score", 0)
            ),
                            "last_analysis": datetime.now(timezone.utc).isoformat(),
            "vector_metadata": vector_metadata,
            "last_update_type": profile_data.update_type
        })

        await repos['user_profile_repo'].update_profile(
            session,
            profile_data.user_id,
            keywords_frequency=interests_data.get("keyword_frequency", {}),
            categories_distribution=interests_data.get("category_distribution", {}),
            activity_patterns=interests_data.get("activity_patterns", {}),
            profile_vector=profile_vector,
            data_sources_count=interests_data.get("data_sources", {}),
            preferences=current_preferences
        )

        # 4. 결과 로깅
        vector_strength = float(np.linalg.norm(profile_vector)) if profile_vector else 0.0
        logger.info(
            f"📊 프로필 업데이트 완료 - 키워드: "
            f"{len(interests_data.get('keywords', []))}개, "
            f"벡터 강도: {vector_strength:.3f}"
        )

        # 5. 유사도 계산 태스크 큐에 추가 (벡터가 유효한 경우에만)
        if vector_strength > 0.1:  # 최소 벡터 강도 임계값
            calculate_user_similarities_task.delay({"user_id": profile_data.user_id})

        return {
            "keywords_count": len(interests_data.get("keywords", [])),
            "categories_count": len(interests_data.get("categories", [])),
            "vector_dimensions": len(profile_vector) if profile_vector else 0,
            "vector_strength": vector_strength,
            "engagement_score": (
                interests_data.get("activity_patterns", {})
                .get("engagement_score", 0)
            ),
            "generation_method": vector_metadata.get("generation_method", "unknown"),
            "total_activities": vector_metadata.get("total_activities_processed", 0)
        }


@celery.task(
    name="tasks.calculate_user_similarities",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 120},
    retry_backoff=True,
    retry_jitter=True,
)
def calculate_user_similarities_task(self, data_dict: dict) -> dict:
    """사용자 유사도를 계산하는 백그라운드 태스크"""
    # self는 Celery task에서 필수이므로 명시적으로 무시
    _ = self
    user_id = data_dict["user_id"]
    logger.info(f"🔄 사용자 {user_id} 유사도 계산 시작")

    try:
        result = _run_async_safely(_async_calculate_similarities(user_id))
        logger.info(f"✅ 사용자 {user_id} 유사도 계산 완료")
        return result

    except (SQLAlchemyError, ValueError, TypeError, RuntimeError) as e:
        logger.error(f"❌ 유사도 계산 실패: {e}")
        raise


async def _async_calculate_similarities(user_id: int) -> dict:
    """유사도 계산 비동기 로직 - Repository 패턴 + 고급 유사도 계산"""
    async for session in get_async_session():
        # Repository 인스턴스 생성
        user_profile_repo = UserProfileRepository()

        # VectorGenerator 인스턴스 생성 (유사도 계산용)
        openai_service = OpenAIService()
        vector_generator = VectorGenerator(openai_service)

        # 1. 현재 사용자 프로필 조회
        current_profile = await user_profile_repo.get_or_create_profile(session, user_id)
        if not current_profile or not current_profile.profile_vector:
            logger.warning(f"사용자 {user_id}의 프로필 벡터가 없음")
            return {"similarities_calculated": 0}

        # 2. 다른 사용자들의 프로필 조회 (Repository 사용)
        other_profiles = await user_profile_repo.get_profiles_with_vectors(
            session, exclude_user_id=user_id
        )

        if not other_profiles:
            logger.info("비교할 다른 사용자 프로필이 없음")
            return {"similarities_calculated": 0}

        # 3. 고급 유사도 계산 및 저장
        similarities_saved = 0
        current_vector = current_profile.profile_vector

        # 다양한 유사도 계산 방식 설정
        similarity_methods = ["cosine", "euclidean"]
        primary_method = "cosine"  # 기본 방식

        for other_profile in other_profiles:
            try:
                similarities_by_method = {}

                # 여러 방식으로 유사도 계산
                for method in similarity_methods:
                    similarity_score = vector_generator.calculate_vector_similarity(
                        current_vector, other_profile.profile_vector, method
                    )
                    similarities_by_method[method] = similarity_score

                # 기본 방식의 점수를 사용
                primary_similarity = similarities_by_method[primary_method]

                # 유사도 임계값 체크 (0.7 이상만 저장)
                if primary_similarity >= 0.7:
                    # Repository를 사용하여 유사도 저장
                    await user_profile_repo.save_user_similarity(
                        session,
                        user_id_1=user_id,
                        user_id_2=other_profile.user_id,
                        similarity_score=primary_similarity,
                        calculation_method=f"advanced_{primary_method}",
                        metadata={
                            "vector_dimensions": len(current_vector),
                            "calculation_date": datetime.now(timezone.utc).isoformat(),
                            "algorithm_version": "v2.0",
                            "all_similarities": similarities_by_method,
                            "primary_method": primary_method,
                            "vector_strengths": {
                                "user1": float(np.linalg.norm(current_vector)),
                                "user2": float(np.linalg.norm(other_profile.profile_vector))
                            }
                        }
                    )
                    similarities_saved += 1

                    logger.debug(
                        f"💾 유사도 저장 - {user_id} ↔ {other_profile.user_id}: "
                        f"{primary_similarity:.3f} ({primary_method})"
                    )

            except (SQLAlchemyError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"사용자 {other_profile.user_id}와의 유사도 계산 실패: {e}")
                continue

        await session.commit()

        # 4. 추천 생성 태스크 큐에 추가
        if similarities_saved > 0:
            generate_recommendations_task.delay({"user_id": user_id})

        logger.info(
            f"✅ 유사도 계산 완료 - 사용자 {user_id}, "
            f"저장된 유사도: {similarities_saved}개"
        )

        return {
            "similarities_calculated": similarities_saved,
            "total_profiles_compared": len(other_profiles),
            "similarity_threshold": 0.7,
            "calculation_method": f"advanced_{primary_method}",
            "algorithm_version": "v2.0"
        }


def _calculate_cosine_similarity(vector1: List[float], vector2: List[float]) -> float:
    """코사인 유사도를 계산합니다. (기존 호환성 함수)"""
    if len(vector1) != len(vector2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vector1, vector2))
    magnitude1 = math.sqrt(sum(a * a for a in vector1))
    magnitude2 = math.sqrt(sum(b * b for b in vector2))

    if magnitude1 == 0.0 or magnitude2 == 0.0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


@celery.task(
    name="tasks.generate_recommendations",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 90},
    retry_backoff=True,
    retry_jitter=True,
)
def generate_recommendations_task(self, data_dict: dict) -> dict:
    """개인화 추천을 생성하는 백그라운드 태스크"""
    # self는 Celery task에서 필수이므로 명시적으로 무시
    _ = self
    user_id = data_dict["user_id"]
    logger.info(f"🎯 사용자 {user_id} 추천 생성 시작")

    try:
        result = _run_async_safely(_async_generate_recommendations(user_id))
        logger.info(f"✅ 사용자 {user_id} 추천 생성 완료")
        return result

    except (ValueError, TypeError, RuntimeError) as e:
        logger.error(f"❌ 추천 생성 실패: {e}")
        raise


async def _async_generate_recommendations(user_id: int) -> dict:
    """추천 생성 비동기 로직 - Repository 패턴 사용"""
    async for session in get_async_session():
        # Repository 인스턴스 생성
        user_profile_repo = UserProfileRepository()
        bookmark_repo = BookmarkRepository()
        recommendation_repo = RecommendationRepository()

        # 1. 사용자 프로필 조회
        profile = await user_profile_repo.get_or_create_profile(session, user_id)
        if not profile:
            return {"recommendations_generated": 0}

        # 2. 유사한 사용자들 조회 (Repository 사용)
        similarities = await user_profile_repo.get_similar_users(
            session, user_id, min_similarity=0.8, limit=10
        )

        if not similarities:
            logger.info(f"사용자 {user_id}와 유사한 사용자가 없음")
            return {"recommendations_generated": 0}

        # 3. 유사한 사용자들의 북마크에서 추천 생성
        similar_user_ids = [sim.user_id_2 for sim in similarities]
        recommendations_generated = await _generate_bookmark_recommendations(
            session, user_id, similar_user_ids, profile, bookmark_repo, recommendation_repo
        )

        await session.commit()
        return {"recommendations_generated": recommendations_generated}


async def _generate_bookmark_recommendations(
    session: AsyncSession,
    user_id: int,
    similar_user_ids: List[int],
    profile: UserProfile,
    bookmark_repo: BookmarkRepository,
    recommendation_repo: RecommendationRepository
) -> int:
    """북마크 기반 추천 생성 - Repository 패턴 사용"""
    # 사용자가 이미 가진 북마크들 조회
    user_bookmarks = await bookmark_repo.get_user_bookmarks(session, user_id)
    user_bookmark_ids = {bookmark.id for bookmark in user_bookmarks}

    # 유사한 사용자들의 북마크 조회
    candidate_bookmarks = []
    for similar_user_id in similar_user_ids:
        similar_bookmarks = await bookmark_repo.get_user_bookmarks(
            session, similar_user_id, limit=20
        )
        # 사용자가 없는 북마크만 추가
        for bookmark in similar_bookmarks:
            if bookmark.id not in user_bookmark_ids:
                candidate_bookmarks.append(bookmark)

    if not candidate_bookmarks:
        return 0

    # 추천 점수 계산 및 저장
    recommendations_saved = 0
    user_interests = profile.preferences.get("interests", []) if profile.preferences else []
    user_categories = profile.preferences.get("categories", []) if profile.preferences else []

    for bookmark in candidate_bookmarks[:50]:  # 최대 50개까지
        try:
            # 관심사 매칭 점수 계산
            relevance_score = _calculate_bookmark_relevance(
                bookmark, user_interests, user_categories
            )

            if relevance_score >= 0.6:  # 임계값 이상만 추천으로 저장
                await recommendation_repo.save_recommendation(
                    session,
                    user_id=user_id,
                    content_type="bookmark",
                    content_id=str(bookmark.id),
                    relevance_score=relevance_score,
                    recommendation_reason="similar_users",
                    metadata={
                        "bookmark_title": bookmark.title,
                        "bookmark_url": bookmark.url,
                        "source_user_count": len(similar_user_ids),
                        "matching_interests": _get_matching_interests(bookmark, user_interests)
                    }
                )
                recommendations_saved += 1

        except (SQLAlchemyError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"북마크 {bookmark.id} 추천 생성 실패: {e}")
            continue

    return recommendations_saved


def _calculate_bookmark_relevance(bookmark, user_interests: List[str], _: List[str]) -> float:
    """북마크의 사용자 관련성 점수 계산 (user_categories는 현재 미사용)"""
    score = 0.0

    # 키워드 매칭 (50%)
    bookmark_keywords = getattr(bookmark, 'keywords', []) or []
    keyword_matches = sum(
        1 for interest in user_interests
        if any(interest.lower() in kw.lower() for kw in bookmark_keywords)
    )
    if user_interests:
        score += (keyword_matches / len(user_interests)) * 0.5

    # 제목 매칭 (30%)
    title_matches = sum(
        1 for interest in user_interests
        if interest.lower() in bookmark.title.lower()
    )
    if user_interests:
        score += (title_matches / len(user_interests)) * 0.3

    # 요약 매칭 (20%)
    if hasattr(bookmark, 'summary') and bookmark.summary:
        summary_matches = sum(
            1 for interest in user_interests
            if interest.lower() in bookmark.summary.lower()
        )
        if user_interests:
            score += (summary_matches / len(user_interests)) * 0.2

    return min(score, 1.0)  # 최대 1.0으로 제한


def _get_matching_interests(bookmark, user_interests: List[str]) -> List[str]:
    """북마크와 매칭되는 사용자 관심사 반환"""
    matching = []
    bookmark_text = f"{bookmark.title} {getattr(bookmark, 'summary', '')}"

    for interest in user_interests:
        if interest.lower() in bookmark_text.lower():
            matching.append(interest)

    return matching


@celery.task(
    name="tasks.analyze_trends",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 300},
    retry_backoff=True,
    retry_jitter=True,
)
def analyze_trends_task(_, __) -> dict:
    """트렌드 분석을 수행하는 백그라운드 태스크"""
    # self와 data_dict는 현재 사용하지 않으므로 언더스코어로 표시
    logger.info("📊 트렌드 분석 시작")

    try:
        result = _run_async_safely(_async_analyze_trends())
        logger.info("✅ 트렌드 분석 완료")
        return result

    except (ValueError, TypeError, RuntimeError) as e:
        logger.error(f"❌ 트렌드 분석 실패: {e}")
        raise


async def _async_analyze_trends() -> dict:
    """트렌드 분석 비동기 로직 - Repository 패턴 사용"""
    async for session in get_async_session():
        # Repository 인스턴스 생성
        bookmark_repo = BookmarkRepository()
        trend_repo = TrendAnalysisRepository()

        # 1. 최근 활동 데이터 수집 (Repository 사용)
        recent_date = datetime.now(timezone.utc) - timedelta(days=7)

        # 모든 사용자의 최근 북마크 조회 (분석용)
        recent_bookmarks = await bookmark_repo.get_bookmarks_for_analysis(
            session, user_ids=[], days=7  # user_ids가 빈 리스트면 모든 사용자
        )

        # 키워드 빈도 분석
        keyword_counts = {}

        for bookmark in recent_bookmarks:
            # 키워드 카운트
            if hasattr(bookmark, 'keywords') and bookmark.keywords:
                for keyword in bookmark.keywords:
                    keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

        # 트렌드 점수 계산 (단순 빈도 기반)
        total_bookmarks = len(recent_bookmarks)
        trending_keywords = []

        for keyword, count in keyword_counts.items():
            if count >= 3:  # 최소 3번 이상 언급
                trend_score = count / total_bookmarks if total_bookmarks > 0 else 0
                trending_keywords.append({
                    "keyword": keyword,
                    "count": count,
                    "trend_score": trend_score
                })

        # 상위 트렌드 선택
        trending_keywords.sort(key=lambda x: x["trend_score"], reverse=True)
        top_trends = trending_keywords[:10]

        # 트렌드 분석 결과 저장 (Repository 사용)
        if top_trends:
            await trend_repo.save_trend_analysis(
                session,
                period_start=recent_date,
                period_end=datetime.now(timezone.utc),
                trending_keywords=[trend["keyword"] for trend in top_trends],
                keyword_frequencies={
                    trend["keyword"]: trend["count"] for trend in top_trends
                },
                category_trends={},
                metadata={
                    "total_bookmarks_analyzed": total_bookmarks,
                    "analysis_method": "frequency_based",
                    "trend_threshold": 3
                }
            )

            await session.commit()

        return {
            "trends_identified": len(top_trends),
            "bookmarks_analyzed": total_bookmarks,
            "top_keywords": [trend["keyword"] for trend in top_trends[:5]]
        }
