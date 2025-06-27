"""
User Profile Processing Service

사용자 활동 기반 프로필 벡터 생성 및 업데이트 서비스
"""

import asyncio
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from loguru import logger

from app.services.vector_generator import VectorGenerator, ActivityData, ActivityType
from app.external.openai_service import OpenAIService


class UserProfileProcessor:
    """사용자 프로필 처리 통합 서비스"""

    def __init__(self, repositories: Dict[str, Any], redis_client=None):
        """
        UserProfileProcessor 초기화

        Args:
            repositories: 필요한 리포지토리들의 딕셔너리
            redis_client: Redis 클라이언트 (선택사항)
        """
        self.repositories = repositories
        self.openai_service = OpenAIService()
        self.vector_generator = VectorGenerator(self.openai_service)
        self.redis_client = redis_client

        # 유사도 임계값
        self.similarity_threshold = 0.7
        self.min_recommendations = 5
        self.max_recommendations = 20

    async def update_user_profile(
        self,
        user_id: int,
        force_full_recalculation: bool = False,
        include_historical_data: bool = True
    ) -> Dict[str, Any]:
        """
        사용자 프로필을 업데이트합니다.

        Args:
            user_id: 사용자 ID
            force_full_recalculation: 전체 재계산 강제 여부
            include_historical_data: 과거 데이터 포함 여부

        Returns:
            업데이트 결과 메타데이터
        """
        start_time = time.time()
        logger.info(f"🔄 사용자 프로필 업데이트 시작 - User ID: {user_id}")

        try:
            # 1. 기존 프로필 조회
            existing_profile = await self.repositories['user_profile_repo'].get_or_create_profile(user_id)

            # 2. 사용자 활동 데이터 수집
            activities = await self._collect_user_activities(user_id, include_historical_data)

            # 3. 벡터 생성
            if force_full_recalculation or not existing_profile:
                profile_vector, metadata = await self.vector_generator.generate_profile_vector(
                    activities
                )
            else:
                # 증분 업데이트
                profile_vector, metadata = (
                    await self.vector_generator.update_vector_incrementally(
                        existing_profile.profile_vector, activities
                    )
                )

            # 4. 프로필 저장
            await self._save_profile(user_id, profile_vector, metadata)

            processing_time = time.time() - start_time

            result = {
                **metadata,
                "user_id": user_id,
                "processing_time": processing_time,
                "update_type": "full" if force_full_recalculation else "incremental",
                "data_points_processed": len(activities)
            }

            logger.info(
                f"✅ 프로필 업데이트 완료 - User ID: {user_id}, 소요시간: {processing_time:.2f}s"
            )
            return result

        except ValueError as e:
            logger.error(f"❌ 프로필 업데이트 실패 - User ID: {user_id}, 오류: {e}")
            return {"error": str(e), "user_id": user_id}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 프로필 업데이트 실패 - User ID: {user_id}, 오류: {e}")
            return {"error": str(e), "user_id": user_id}

    async def update_vector_incrementally(
        self,
        user_id: int,
        new_activities: List[Dict[str, Any]],
        existing_vector: Optional[List[float]] = None,
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        벡터를 증분적으로 업데이트합니다.

        Args:
            user_id: 사용자 ID
            new_activities: 새로운 활동 데이터
            existing_vector: 기존 벡터
            existing_metadata: 기존 메타데이터

        Returns:
            업데이트된 벡터와 메타데이터
        """
        logger.info(f"📈 증분 벡터 업데이트 - User ID: {user_id}, 새 활동: {len(new_activities)}개")

        try:
            # 기존 벡터가 없으면 조회
            if existing_vector is None:
                profile = await self.repositories['user_profile_repo'].get_or_create_profile(user_id)
                existing_vector = profile.profile_vector if profile else None
                existing_metadata = profile.vector_metadata if profile else {}

            if existing_vector is None:
                # 기존 벡터가 없으면 전체 업데이트
                return await self.update_user_profile(user_id, force_full_recalculation=True)

            # ActivityData 형식으로 변환
            activity_data = []
            for activity in new_activities:
                activity_data.append(ActivityData(
                    activity_type=ActivityType(activity.get('activity_type', 'chat')),
                    content=activity['content'],
                    created_at=activity.get('timestamp', datetime.now()),
                    metadata=activity.get('metadata', {}),
                    weight=activity.get('weight', 1.0)
                ))

            # 증분 업데이트 실행
            updated_vector, update_metadata = (
                await self.vector_generator.update_vector_incrementally(
                    existing_vector, activity_data
                )
            )

            # 메타데이터 병합
            merged_metadata = {
                **existing_metadata,
                **update_metadata,
                "last_incremental_update": datetime.now()
            }

            # 프로필 저장
            await self._save_profile(user_id, updated_vector, merged_metadata)

            return {
                "profile_vector": updated_vector,
                **merged_metadata
            }

        except ValueError as e:
            logger.error(f"❌ 증분 업데이트 실패 - User ID: {user_id}, 오류: {e}")
            return {"error": str(e)}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 증분 업데이트 실패 - User ID: {user_id}, 오류: {e}")
            return {"error": str(e)}

    async def calculate_user_similarities(
        self,
        user_id: int,
        target_user_ids: Optional[List[int]] = None,
        min_similarity: float = 0.5,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        사용자 유사도를 계산합니다.

        Args:
            user_id: 기준 사용자 ID
            target_user_ids: 대상 사용자 ID 목록 (None이면 모든 사용자)
            min_similarity: 최소 유사도 임계값
            limit: 최대 반환 개수

        Returns:
            유사한 사용자 목록
        """
        logger.info(f"🔍 유사도 계산 시작 - User ID: {user_id}")

        try:
            # 기준 사용자 프로필 조회
            user_profile = await self.repositories['user_profile_repo'].get_or_create_profile(user_id)
            if not user_profile or not user_profile.profile_vector:
                return []

            # 대상 사용자들 조회
            if target_user_ids:
                other_profiles = await self.repositories[
                    'user_profile_repo'
                ].get_profiles_by_ids(target_user_ids)
            else:
                other_profiles = await self.repositories[
                    'user_profile_repo'
                ].get_all_profiles_except(user_id)

            similarities = []

            for other_profile in other_profiles:
                if not other_profile.profile_vector:
                    continue

                # 유사도 계산
                similarity = self.vector_generator.calculate_vector_similarity(
                    user_profile.profile_vector,
                    other_profile.profile_vector
                )

                if similarity >= min_similarity:
                    similarities.append({
                        "user_id": other_profile.user_id,
                        "similarity_score": similarity,
                        "shared_interests": self._extract_shared_interests(
                            user_profile.vector_metadata,
                            other_profile.vector_metadata
                        ),
                        "last_updated": other_profile.last_updated
                    })

            # 유사도 순으로 정렬 후 제한
            similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
            result = similarities[:limit]

            logger.info(f"✅ 유사도 계산 완료 - 총 {len(result)}명 발견")
            return result

        except ValueError as e:
            logger.error(f"❌ 유사도 계산 실패 - User ID: {user_id}, 오류: {e}")
            return []
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 유사도 계산 실패 - User ID: {user_id}, 오류: {e}")
            return []

    async def generate_recommendations(
        self,
        user_id: int,
        categories: Optional[List[str]] = None,
        limit: int = 10,
        use_collaborative_filtering: bool = True
    ) -> List[Dict[str, Any]]:
        """
        개인화 추천을 생성합니다.

        Args:
            user_id: 사용자 ID
            categories: 추천 카테고리 필터
            limit: 최대 추천 개수
            use_collaborative_filtering: 협업 필터링 사용 여부

        Returns:
            추천 목록
        """
        logger.info(f"🎯 추천 생성 시작 - User ID: {user_id}")

        try:
            recommendations = []

            # 1. 컨텐츠 기반 추천
            content_based = await self._generate_content_based_recommendations(
                user_id, categories, limit // 2
            )
            recommendations.extend(content_based)

            # 2. 협업 필터링 추천
            if use_collaborative_filtering:
                collaborative = await self._generate_collaborative_recommendations(
                    user_id, categories, limit // 2
                )
                recommendations.extend(collaborative)

            # 3. 중복 제거 및 점수 조정
            recommendations = self._deduplicate_and_score_recommendations(recommendations)

            # 4. 최종 제한 적용
            final_recommendations = recommendations[:limit]

            logger.info(f"✅ 추천 생성 완료 - {len(final_recommendations)}개 추천")
            return final_recommendations

        except ValueError as e:
            logger.error(f"❌ 추천 생성 실패 - User ID: {user_id}, 오류: {e}")
            return []
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 추천 생성 실패 - User ID: {user_id}, 오류: {e}")
            return []

    async def _collect_user_activities(
        self,
        user_id: int,
        include_historical: bool = True  # pylint: disable=unused-argument
    ) -> List[ActivityData]:
        """사용자 활동 데이터를 수집합니다."""
        activities = []

        try:
            # 채팅 데이터
            chats = await self.repositories['chat_repo'].get_user_chats(user_id)
            for chat in chats:
                activities.append(ActivityData(
                    activity_type=ActivityType.CHAT,
                    content=chat.content,
                    created_at=chat.created_at,
                    metadata={"session_id": getattr(chat, 'session_id', None)}
                ))

            # 북마크 데이터
            bookmarks = await self.repositories['bookmark_repo'].get_user_bookmarks(user_id)
            for bookmark in bookmarks:
                content = f"{bookmark.title} {bookmark.content or ''}"
                activities.append(ActivityData(
                    activity_type=ActivityType.BOOKMARK,
                    content=content,
                    created_at=bookmark.created_at,
                    metadata={"url": getattr(bookmark, 'url', None)}
                ))

            # AI 프로필 데이터
            ai_profiles = await self.repositories['ai_profile_repo'].get_user_profiles(user_id)
            for profile in ai_profiles:
                if hasattr(profile, 'profile_data') and profile.profile_data:
                    interests = profile.profile_data.get('interests', [])
                    content = " ".join(interests) if isinstance(interests, list) else str(interests)
                    activities.append(ActivityData(
                        activity_type=ActivityType.AI_PROFILE,
                        content=content,
                        created_at=profile.created_at
                    ))

        except ValueError as e:
            logger.error(f"활동 데이터 수집 실패: {e}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"활동 데이터 수집 실패: {e}")

        return activities

    async def _save_profile(
        self,
        user_id: int,
        vector: List[float],
        metadata: Dict[str, Any]
    ):
        """프로필을 저장합니다."""
        try:
            from app.core.database import get_async_session
            
            async for session in get_async_session():
                # keywords_frequency를 metadata에서 추출하여 별도 필드로 저장
                keywords_frequency = metadata.get('keywords_frequency', {})
                
                await self.repositories['user_profile_repo'].update_profile(
                    session=session,
                    user_id=user_id,
                    profile_vector=vector,
                    vector_metadata=metadata,
                    keywords_frequency=keywords_frequency,  # 🆕 키워드 빈도 직접 저장
                    vector_strength=metadata.get('vector_strength', 0.0),
                    last_updated=datetime.now()
                )
        except (ValueError, KeyError) as e:
            logger.error(f"프로필 저장 실패: {e}")
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"프로필 저장 실패: {e}")
            raise

    def _extract_shared_interests(
        self,
        metadata1: Dict[str, Any],
        metadata2: Dict[str, Any]
    ) -> List[str]:
        """두 사용자의 공통 관심사를 추출합니다."""
        interests1 = set()
        interests2 = set()

        # 메타데이터에서 관심사 추출
        for metadata in [metadata1, metadata2]:
            if not metadata:
                continue

            top_interests = metadata.get('top_interests', {})
            for interests in top_interests.values():
                if isinstance(interests, dict):
                    if metadata == metadata1:
                        interests1.update(interests.keys())
                    else:
                        interests2.update(interests.keys())

        # 공통 관심사 반환
        shared = list(interests1.intersection(interests2))
        return shared[:10]  # 최대 10개

    async def sync_from_ai_profile(
        self,
        user_id: int,
        interests: List[str],
        keywords_frequency: Dict[str, Dict[str, Any]],
        activity_patterns: Dict[str, Any],
        ai_profile_data: Any
    ) -> Dict[str, Any]:
        """
        AI Profile 데이터로부터 User Profile을 동기화합니다.
        
        Args:
            user_id: 사용자 ID
            interests: AI Profile에서 추출한 관심사 키워드
            keywords_frequency: 키워드별 빈도 및 가중치 정보
            activity_patterns: 활동 패턴 정보
            ai_profile_data: AI Profile 원본 데이터
            
        Returns:
            동기화 결과 정보
        """
        start_time = time.time()
        logger.info(f"🔄 AI Profile → User Profile 동기화 시작 - User ID: {user_id}")
        
        try:
            # 1. AI Profile 데이터로부터 관심사 텍스트 구성
            interests_text = " ".join(interests[:50])  # 상위 50개 키워드
            
            # 2. 벡터 생성 (간단하고 빠르게)
            embedding = await self.openai_service.create_embedding(
                text=interests_text,
                model="text-embedding-3-small"
            )
            profile_vector = embedding.data[0].embedding
            
            # 3. 메타데이터 구성 (실제 키워드 빈도 사용)
            vector_metadata = {
                "generation_method": "ai_profile_sync",
                "sync_timestamp": datetime.now().isoformat(),
                "keywords_frequency": keywords_frequency,
                "activity_patterns": activity_patterns,
                "categories_distribution": self._extract_categories_from_keywords(interests),
                "vector_strength": min(len(interests) / 50.0, 1.0),
                "data_sources": ["ai_profile"],
                "total_activities_processed": activity_patterns.get("total_sessions", 0),
                "completeness_score": self._calculate_completeness_score(interests, activity_patterns)
            }
            
            # 4. User Profile 저장 (키워드 빈도 포함)
            await self._save_profile(user_id, profile_vector, vector_metadata)
            
            processing_time = time.time() - start_time
            
            result = {
                "success": True,
                "user_id": user_id,
                "sync_method": "ai_profile_to_user_profile",
                "processing_time": processing_time,
                "vector_dimensions": len(profile_vector),
                "vector_strength": vector_metadata["vector_strength"],
                "keywords_count": len(interests),
                "keywords_frequency_count": len(keywords_frequency),
                "completeness_score": vector_metadata["completeness_score"],
                "activity_summary": {
                    "total_sessions": activity_patterns.get("total_sessions", 0),
                    "total_messages": activity_patterns.get("total_messages", 0),
                    "avg_session_duration": activity_patterns.get("avg_session_duration", 0)
                }
            }
            
            logger.info(
                f"✅ AI Profile 동기화 완료 - User ID: {user_id}, "
                f"키워드: {len(interests)}개, 빈도정보: {len(keywords_frequency)}개, "
                f"강도: {vector_metadata['vector_strength']:.3f}, "
                f"소요시간: {processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ AI Profile 동기화 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "success": False,
                "user_id": user_id,
                "error": str(e),
                "sync_method": "ai_profile_to_user_profile",
                "processing_time": time.time() - start_time
            }
    
    def _extract_categories_from_keywords(self, keywords: List[str]) -> Dict[str, float]:
        """키워드에서 카테고리를 추출하고 분포를 계산합니다."""
        
        # 카테고리 매핑 (간단한 규칙 기반)
        category_mapping = {
            'technology': ['AI', '인공지능', '머신러닝', '딥러닝', '개발', '프로그래밍', 'Python', 'JavaScript', '웹개발', '앱개발'],
            'business': ['비즈니스', '경영', '창업', '마케팅', '투자', '금융', '경제', 'MBA', '전략', '리더십'],
            'science': ['과학', '연구', '논문', '실험', '데이터', '분석', '통계', '수학', '물리학', '화학'],
            'education': ['교육', '학습', '강의', '수업', '대학', '학교', '공부', '시험', '자격증', '온라인강의'],
            'entertainment': ['영화', '음악', '게임', '드라마', 'K-pop', '엔터테인먼트', '문화', '예술', '취미', '여행'],
            'health': ['건강', '운동', '다이어트', '의학', '병원', '약물', '정신건강', '요가', '헬스', '영양'],
            'lifestyle': ['라이프스타일', '일상', '요리', '패션', '뷰티', '인테리어', '반려동물', '가족', '연애', '결혼']
        }
        
        category_scores = {}
        
        for category, category_keywords in category_mapping.items():
            score = 0.0
            for keyword in keywords:
                # 완전 일치 또는 부분 일치 확인
                for cat_keyword in category_keywords:
                    if (keyword.lower() == cat_keyword.lower() or 
                        cat_keyword.lower() in keyword.lower() or 
                        keyword.lower() in cat_keyword.lower()):
                        score += 1.0
                        break
            
            if score > 0:
                category_scores[category] = score / len(keywords)  # 정규화
        
        # 상위 5개 카테고리만 반환
        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_categories[:5])
    
    def _calculate_completeness_score(self, interests: List[str], activity_patterns: Dict[str, Any]) -> int:
        """프로필 완성도 점수를 계산합니다 (0-100)."""
        score = 0
        
        # 키워드 개수 (최대 40점)
        keyword_score = min(len(interests) * 0.8, 40)  # 50개 키워드 기준으로 조정 (키워드당 0.8점)
        score += keyword_score
        
        # 활동 세션 수 (최대 30점)
        sessions = activity_patterns.get("total_sessions", 0)
        session_score = min(sessions * 3, 30)  # 세션 당 3점, 최대 30점
        score += session_score
        
        # 메시지 수 (최대 20점)
        messages = activity_patterns.get("total_messages", 0)
        message_score = min(messages, 20)  # 메시지 당 1점, 최대 20점
        score += message_score
        
        # 세션 지속시간 (최대 10점)
        avg_duration = activity_patterns.get("avg_session_duration", 0)
        duration_score = min(avg_duration * 2, 10)  # 분당 2점, 최대 10점
        score += duration_score
        
        return min(int(score), 100)  # 최대 100점

    async def _generate_content_based_recommendations(
        self,
        user_id: int,  # pylint: disable=unused-argument
        categories: Optional[List[str]],  # pylint: disable=unused-argument
        limit: int
    ) -> List[Dict[str, Any]]:
        """컨텐츠 기반 추천을 생성합니다."""
        # Mock 구현 - 실제로는 벡터 유사도 기반 컨텐츠 검색
        recommendations = []

        for i in range(limit):
            recommendations.append({
                "id": f"content_{i}",
                "type": "content",
                "title": f"추천 컨텐츠 {i+1}",
                "description": f"사용자 관심사 기반 추천 {i+1}",
                "score": 0.9 - (i * 0.1),
                "metadata": {"source": "content_based"},
                "created_at": datetime.now()
            })

        return recommendations

    async def _generate_collaborative_recommendations(
        self,
        user_id: int,  # pylint: disable=unused-argument
        categories: Optional[List[str]],  # pylint: disable=unused-argument
        limit: int
    ) -> List[Dict[str, Any]]:
        """협업 필터링 기반 추천을 생성합니다."""
        # Mock 구현 - 실제로는 유사한 사용자 기반 추천
        recommendations = []

        for i in range(limit):
            recommendations.append({
                "id": f"collab_{i}",
                "type": "collaborative",
                "title": f"유사 사용자 추천 {i+1}",
                "description": f"비슷한 관심사 사용자 기반 추천 {i+1}",
                "score": 0.8 - (i * 0.1),
                "metadata": {"source": "collaborative"},
                "created_at": datetime.now()
            })

        return recommendations

    def _deduplicate_and_score_recommendations(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """추천 중복 제거 및 점수 조정"""
        seen_ids = set()
        unique_recommendations = []

        for rec in recommendations:
            if rec["id"] not in seen_ids:
                seen_ids.add(rec["id"])
                unique_recommendations.append(rec)

        # 점수 순으로 정렬
        unique_recommendations.sort(key=lambda x: x["score"], reverse=True)
        return unique_recommendations

    async def batch_update_profiles(
        self,
        user_ids: List[int],
        max_concurrent: int = 5,
        force_full_recalculation: bool = False
    ) -> List[Dict[str, Any]]:
        """
        여러 사용자의 프로필을 배치로 업데이트합니다.

        Args:
            user_ids: 업데이트할 사용자 ID 목록
            max_concurrent: 최대 동시 처리 개수
            force_full_recalculation: 전체 재계산 강제 여부

        Returns:
            각 사용자의 업데이트 결과 목록
        """
        logger.info(f"🔄 배치 프로필 업데이트 시작 - {len(user_ids)}명")

        semaphore = asyncio.Semaphore(max_concurrent)

        async def update_single_user(user_id: int):
            async with semaphore:
                return await self.update_user_profile(
                    user_id,
                    force_full_recalculation=force_full_recalculation
                )

        try:
            tasks = [update_single_user(user_id) for user_id in user_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 예외 처리
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "user_id": user_ids[i],
                        "error": str(result)
                    })
                else:
                    processed_results.append(result)

            logger.info(f"✅ 배치 업데이트 완료 - {len(processed_results)}명 처리")
            return processed_results

        except ValueError as e:
            logger.error(f"❌ 배치 업데이트 실패: {e}")
            return []
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 배치 업데이트 실패: {e}")
            return []

    async def assess_profile_quality(
        self,
        user_id: int
    ) -> Dict[str, Any]:
        """
        사용자 프로필의 품질을 평가합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            품질 평가 결과
        """
        logger.info(f"📊 프로필 품질 평가 시작 - User ID: {user_id}")

        try:
            profile = await self.repositories['user_profile_repo'].get_or_create_profile(user_id)
            if not profile:
                return {
                    "overall_quality": "no_profile",
                    "quality_score": 0.0,
                    "recommendations": ["프로필이 존재하지 않습니다."]
                }

            return self._calculate_quality_metrics(profile)

        except ValueError as e:
            logger.error(f"❌ 품질 평가 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "overall_quality": "error",
                "quality_score": 0.0,
                "recommendations": [f"평가 중 오류 발생: {e}"]
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 품질 평가 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "overall_quality": "error",
                "quality_score": 0.0,
                "recommendations": [f"평가 중 오류 발생: {e}"]
            }

    def _calculate_quality_metrics(self, profile) -> Dict[str, Any]:
        """프로필 품질 메트릭을 계산합니다."""
        quality_score = 0.0
        recommendations = []

        # 1. 벡터 강도 평가 (40%)
        vector_strength = getattr(profile, 'vector_strength', 0.0)
        quality_score += vector_strength * 0.4

        if vector_strength < 0.5:
            recommendations.append("더 많은 활동 데이터가 필요합니다.")

        # 2. 데이터 다양성 평가 (30%)
        metadata = getattr(profile, 'vector_metadata', {})
        data_sources = metadata.get('data_sources', [])
        diversity_score = min(len(data_sources) / 3.0, 1.0)  # 최대 3개 소스
        quality_score += diversity_score * 0.3

        if len(data_sources) < 2:
            recommendations.append("다양한 활동 유형을 추가하세요.")

        # 3. 최신성 평가 (20%)
        freshness_score = self._calculate_freshness_score(profile)
        quality_score += freshness_score * 0.2

        # 4. 데이터 포인트 수 평가 (10%)
        data_points = metadata.get('data_points_processed', 0)
        data_score = min(data_points / 100.0, 1.0)  # 100개 기준
        quality_score += data_score * 0.1

        if data_points < 20:
            recommendations.append("더 많은 활동이 필요합니다.")

        # 품질 등급 결정
        if quality_score >= 0.8:
            overall_quality = "high"
        elif quality_score >= 0.5:
            overall_quality = "medium"
        else:
            overall_quality = "low"

        return {
            "overall_quality": overall_quality,
            "quality_score": quality_score,
            "recommendations": recommendations,
            "details": {
                "vector_strength": vector_strength,
                "data_diversity": diversity_score,
                "freshness": freshness_score,
                "data_points": data_points
            }
        }

    def _calculate_freshness_score(self, profile) -> float:
        """프로필 최신성 점수를 계산합니다."""
        last_updated = getattr(profile, 'last_updated', None)
        if last_updated:
            days_old = (datetime.now() - last_updated).days
            return max(0, 1 - (days_old / 30))  # 30일 기준
        return 0.0

    async def generate_diverse_recommendations(
        self,
        user_id: int,
        limit: int = 10,
        diversity_factor: float = 0.5
    ) -> Dict[str, Any]:
        """
        다양성이 최적화된 추천을 생성합니다.

        Args:
            user_id: 사용자 ID
            limit: 추천 개수
            diversity_factor: 다양성 비율 (0.0~1.0)

        Returns:
            다양성 최적화된 추천 결과
        """
        logger.info(f"🎯 다양성 추천 생성 - User ID: {user_id}, 다양성: {diversity_factor}")

        try:
            # 1. 기본 추천 생성
            base_recommendations = await self.generate_recommendations(
                user_id, limit=limit * 2  # 더 많이 생성해서 선택
            )

            # 2. 다양성 최적화 적용
            optimized = await self._optimize_recommendation_diversity(
                base_recommendations, limit, diversity_factor
            )

            # 3. 다양성 점수 계산
            diversity_score = self._calculate_diversity_score(optimized)

            return {
                "recommendations": optimized,
                "diversity_score": diversity_score,
                "diversity_factor": diversity_factor,
                "generated_at": datetime.now()
            }

        except ValueError as e:
            logger.error(f"❌ 다양성 추천 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "recommendations": [],
                "diversity_score": 0.0,
                "error": str(e)
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 다양성 추천 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "recommendations": [],
                "diversity_score": 0.0,
                "error": str(e)
            }

    async def _optimize_recommendation_diversity(
        self,
        recommendations: List[Dict[str, Any]],
        limit: int,
        diversity_factor: float
    ) -> List[Dict[str, Any]]:
        """추천 다양성을 최적화합니다."""
        if not recommendations:
            return []

        selected = []
        remaining = recommendations.copy()
        category_counts = {}

        while len(selected) < limit and remaining:
            best_rec = None
            best_score = -1

            for rec in remaining:
                # 기본 점수
                relevance_score = rec.get('score', 0.0)

                # 다양성 점수
                category = rec.get('category', 'unknown')
                category_penalty = category_counts.get(category, 0) * 0.2
                diversity_score = 1.0 - category_penalty

                # 최종 점수 (관련성 + 다양성)
                final_score = (
                    relevance_score * (1 - diversity_factor) +
                    diversity_score * diversity_factor
                )

                if final_score > best_score:
                    best_score = final_score
                    best_rec = rec

            if best_rec:
                selected.append(best_rec)
                remaining.remove(best_rec)

                # 카테고리 카운트 업데이트
                category = best_rec.get('category', 'unknown')
                category_counts[category] = category_counts.get(category, 0) + 1

        return selected

    def _calculate_diversity_score(self, recommendations: List[Dict[str, Any]]) -> float:
        """추천 목록의 다양성 점수를 계산합니다."""
        if not recommendations:
            return 0.0

        categories = [rec.get('category', 'unknown') for rec in recommendations]
        unique_categories = set(categories)

        # 카테고리 다양성 점수
        category_diversity = len(unique_categories) / len(recommendations)

        return min(category_diversity * 2, 1.0)  # 최대 1.0

    async def analyze_temporal_preferences(
        self,
        user_id: int,
        activities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        시간적 선호도 변화를 분석합니다.

        Args:
            user_id: 사용자 ID
            activities: 활동 데이터 목록

        Returns:
            시간적 선호도 분석 결과
        """
        logger.info(f"⏰ 시간적 선호도 분석 - User ID: {user_id}")

        try:
            current_time = datetime.now()

            # 시간대별 활동 분류
            recent_activities = []
            medium_activities = []
            old_activities = []

            for activity in activities:
                timestamp = activity.get('timestamp', current_time)
                days_ago = (current_time - timestamp).days

                if days_ago <= 7:
                    recent_activities.append(activity)
                elif days_ago <= 30:
                    medium_activities.append(activity)
                else:
                    old_activities.append(activity)

            # 각 시간대별 관심사 추출
            result = await self._analyze_temporal_preferences(
                recent_activities, medium_activities, old_activities
            )

            return result

        except ValueError as e:
            logger.error(f"❌ 시간적 분석 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "recent_interests": {},
                "stable_interests": {},
                "declining_interests": {},
                "preference_shift_score": 0.0,
                "error": str(e)
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 시간적 분석 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "recent_interests": {},
                "stable_interests": {},
                "declining_interests": {},
                "preference_shift_score": 0.0,
                "error": str(e)
            }

    async def _analyze_temporal_preferences(
        self,
        recent_activities: List[Dict[str, Any]],
        medium_activities: List[Dict[str, Any]],
        old_activities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """시간대별 선호도를 분석합니다."""

        # Mock 구현 - 실제로는 AI를 통한 키워드 추출 및 분석
        recent_interests = {}
        stable_interests = {}
        declining_interests = {}

        # 최근 활동에서 키워드 추출
        for activity in recent_activities:
            content = activity.get('content', '')
            # 간단한 키워드 추출 (실제로는 더 정교한 NLP 처리)
            keywords = content.lower().split()[:3]
            for keyword in keywords:
                if len(keyword) > 2:
                    recent_interests[keyword] = recent_interests.get(keyword, 0) + 0.1

        # 중간 활동에서 키워드 추출
        for activity in medium_activities:
            content = activity.get('content', '')
            keywords = content.lower().split()[:3]
            for keyword in keywords:
                if len(keyword) > 2:
                    stable_interests[keyword] = stable_interests.get(keyword, 0) + 0.1

        # 과거 활동에서 키워드 추출
        for activity in old_activities:
            content = activity.get('content', '')
            keywords = content.lower().split()[:3]
            for keyword in keywords:
                if len(keyword) > 2:
                    declining_interests[keyword] = declining_interests.get(keyword, 0) + 0.05

        # 선호도 변화 점수 계산
        preference_shift_score = 0.0
        if recent_interests:
            recent_keywords = set(recent_interests.keys())
            stable_keywords = set(stable_interests.keys())

            new_interests = recent_keywords - stable_keywords
            preference_shift_score = len(new_interests) / max(len(recent_keywords), 1)

        return {
            "recent_interests": recent_interests,
            "stable_interests": stable_interests,
            "declining_interests": declining_interests,
            "preference_shift_score": preference_shift_score
        }

    async def handle_bookmark_event(
        self,
        user_id: int,
        bookmark_data: Dict[str, Any],
        use_redis_cache: bool = True
    ) -> Dict[str, Any]:
        """
        북마크 이벤트를 처리하여 사용자 프로필을 실시간으로 업데이트합니다.

        Args:
            user_id: 사용자 ID
            bookmark_data: 북마크 데이터 (title, url, content, category 등)
            use_redis_cache: Redis 캐시 사용 여부

        Returns:
            업데이트 결과 메타데이터
        """
        logger.info(f"🔖 북마크 이벤트 처리 시작 - User ID: {user_id}")

        try:
            # 1. 북마크 데이터에서 활동 정보 추출
            bookmark_content = self._extract_bookmark_content(bookmark_data)

            # 2. ActivityData 형식으로 변환
            activity_data = ActivityData(
                activity_type=ActivityType.BOOKMARK,
                content=bookmark_content,
                created_at=datetime.now(),
                metadata={
                    "url": bookmark_data.get("url", ""),
                    "category": bookmark_data.get("category", "general"),
                    "tags": bookmark_data.get("tags", []),
                    "source": "bookmark_event"
                },
                weight=1.5  # 북마크는 높은 가중치
            )

            # 3. Redis에 임시 저장 (원자적 연산을 위해)
            if use_redis_cache:
                await self._cache_bookmark_update(user_id, activity_data)

            # 4. 증분 벡터 업데이트 실행
            result = await self.update_vector_incrementally(
                user_id=user_id,
                new_activities=[{
                    "activity_type": "bookmark",
                    "content": bookmark_content,
                    "timestamp": datetime.now(),
                    "metadata": activity_data.metadata,
                    "weight": activity_data.weight
                }]
            )

            # 5. Redis 캐시 정리
            if use_redis_cache:
                await self._cleanup_bookmark_cache(user_id)

            logger.info(f"✅ 북마크 이벤트 처리 완료 - User ID: {user_id}")

            return {
                **result,
                "event_type": "bookmark",
                "bookmark_url": bookmark_data.get("url", ""),
                "update_timestamp": datetime.now()
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 북마크 이벤트 처리 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "error": str(e),
                "event_type": "bookmark",
                "user_id": user_id,
                "timestamp": datetime.now()
            }

    def _extract_bookmark_content(self, bookmark_data: Dict[str, Any]) -> str:
        """
        북마크 데이터에서 분석 가능한 콘텐츠를 추출합니다.

        Args:
            bookmark_data: 북마크 데이터

        Returns:
            분석용 콘텐츠 문자열
        """
        content_parts = []

        # 제목 추가
        if title := bookmark_data.get("title"):
            content_parts.append(f"Title: {title}")

        # 설명 추가
        if description := bookmark_data.get("description"):
            content_parts.append(f"Description: {description}")

        # 카테고리 추가
        if category := bookmark_data.get("category"):
            content_parts.append(f"Category: {category}")

        # 태그 추가
        if tags := bookmark_data.get("tags"):
            if isinstance(tags, list):
                content_parts.append(f"Tags: {', '.join(tags)}")
            else:
                content_parts.append(f"Tags: {tags}")

        # URL 도메인 추가 (관심 영역 파악용)
        if url := bookmark_data.get("url"):
            try:
                domain = urlparse(url).netloc
                if domain:
                    content_parts.append(f"Domain: {domain}")
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        # 콘텐츠 추가 (있는 경우)
        if content := bookmark_data.get("content"):
            # 너무 긴 콘텐츠는 요약
            if len(content) > 500:
                content = content[:500] + "..."
            content_parts.append(f"Content: {content}")

        return " | ".join(content_parts) if content_parts else "Empty bookmark"

    async def _cache_bookmark_update(self, user_id: int, activity_data: ActivityData):
        """
        Redis에 북마크 업데이트 정보를 임시 저장합니다.

        Args:
            user_id: 사용자 ID
            activity_data: 활동 데이터
        """
        try:
            # Redis 연결이 있는 경우에만 실행
            if hasattr(self, 'redis_client') and self.redis_client:
                cache_key = f"bookmark_update:{user_id}:{int(datetime.now().timestamp())}"
                cache_data = {
                    "activity_type": activity_data.activity_type.value,
                    "content": activity_data.content,
                    "timestamp": activity_data.created_at.isoformat(),
                    "metadata": activity_data.metadata,
                    "weight": activity_data.weight
                }

                # 5분 TTL로 저장
                await self.redis_client.setex(
                    cache_key,
                    300,  # 5분
                    str(cache_data)
                )

                logger.debug(f"📝 Redis에 북마크 업데이트 캐시됨 - Key: {cache_key}")
            else:
                logger.debug("Redis 클라이언트가 없어 캐시를 건너뜁니다")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning(f"⚠️ Redis 캐시 저장 실패 - User ID: {user_id}, 오류: {e}")

    async def _cleanup_bookmark_cache(self, user_id: int):
        """
        처리 완료된 북마크 업데이트 캐시를 정리합니다.

        Args:
            user_id: 사용자 ID
        """
        try:
            if hasattr(self, 'redis_client') and self.redis_client:
                pattern = f"bookmark_update:{user_id}:*"
                keys = await self.redis_client.keys(pattern)

                if keys:
                    await self.redis_client.delete(*keys)
                    logger.debug(f"🧹 Redis 캐시 정리 완료 - {len(keys)}개 키 삭제")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning(f"⚠️ Redis 캐시 정리 실패 - User ID: {user_id}, 오류: {e}")

    async def handle_chat_completion_event(
        self,
        user_id: int,
        chat_data: Dict[str, Any],
        use_redis_cache: bool = True
    ) -> Dict[str, Any]:
        """
        채팅 세션 완료 이벤트를 처리하여 사용자 프로필을 실시간으로 업데이트합니다.

        Args:
            user_id: 사용자 ID
            chat_data: 채팅 세션 데이터 (messages, session_id, duration, topic 등)
            use_redis_cache: Redis 캐시 사용 여부

        Returns:
            업데이트 결과 메타데이터
        """
        logger.info(f"💬 채팅 완료 이벤트 처리 시작 - User ID: {user_id}")

        try:
            # 1. 채팅 데이터에서 활동 정보 추출
            chat_content = self._extract_chat_content(chat_data)

            # 2. ActivityData 형식으로 변환
            activity_data = ActivityData(
                activity_type=ActivityType.CHAT,
                content=chat_content,
                created_at=datetime.now(),
                metadata={
                    "session_id": chat_data.get("session_id", ""),
                    "duration": chat_data.get("duration", 0),
                    "message_count": chat_data.get("message_count", 0),
                    "topic": chat_data.get("topic", "general"),
                    "language": chat_data.get("language", "korean"),
                    "source": "chat_completion_event"
                },
                weight=self._calculate_chat_weight(chat_data)  # 채팅 길이와 내용에 따른 가중치
            )

            # 3. Redis에 임시 저장 (원자적 연산을 위해)
            if use_redis_cache:
                await self._cache_chat_update(user_id, activity_data)

            # 4. 증분 벡터 업데이트 실행
            result = await self.update_vector_incrementally(
                user_id=user_id,
                new_activities=[{
                    "activity_type": "chat",
                    "content": chat_content,
                    "timestamp": datetime.now(),
                    "metadata": activity_data.metadata,
                    "weight": activity_data.weight
                }]
            )

            # 5. Redis 캐시 정리
            if use_redis_cache:
                await self._cleanup_chat_cache(user_id)

            # 업데이트 결과가 오류인지 확인
            if "error" in result:
                logger.error(f"❌ 채팅 완료 이벤트 - 벡터 업데이트 실패 - User ID: {user_id}")
                return {
                    **result,
                    "event_type": "chat_completion",
                    "user_id": user_id,
                    "session_id": chat_data.get("session_id", ""),
                    "timestamp": datetime.now()
                }

            logger.info(f"✅ 채팅 완료 이벤트 처리 완료 - User ID: {user_id}")

            return {
                **result,
                "event_type": "chat_completion",
                "session_id": chat_data.get("session_id", ""),
                "message_count": chat_data.get("message_count", 0),
                "update_timestamp": datetime.now()
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 채팅 완료 이벤트 처리 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "error": str(e),
                "event_type": "chat_completion",
                "user_id": user_id,
                "timestamp": datetime.now()
            }

    def _extract_chat_content(self, chat_data: Dict[str, Any]) -> str:
        """
        채팅 세션 데이터에서 분석 가능한 콘텐츠를 추출합니다.

        Args:
            chat_data: 채팅 세션 데이터

        Returns:
            분석용 콘텐츠 문자열
        """
        content_parts = []

        # 기본 세션 정보 추가
        content_parts.extend(self._extract_chat_session_info(chat_data))

        # 메시지 내용 추가
        if message_content := self._extract_chat_messages(chat_data):
            content_parts.append(message_content)

        # 요약 및 키워드 추가
        content_parts.extend(self._extract_chat_metadata(chat_data))

        return " | ".join(content_parts) if content_parts else "Empty chat session"

    def _extract_chat_session_info(self, chat_data: Dict[str, Any]) -> List[str]:
        """채팅 세션 기본 정보를 추출합니다."""
        info_parts = []

        if session_id := chat_data.get("session_id"):
            info_parts.append(f"Session: {session_id}")

        if topic := chat_data.get("topic"):
            info_parts.append(f"Topic: {topic}")

        if language := chat_data.get("language"):
            info_parts.append(f"Language: {language}")

        if message_count := chat_data.get("message_count"):
            info_parts.append(f"Messages: {message_count}")

        if duration := chat_data.get("duration"):
            info_parts.append(f"Duration: {duration}s")

        return info_parts

    def _extract_chat_messages(self, chat_data: Dict[str, Any]) -> Optional[str]:
        """채팅 메시지 내용을 추출하고 정리합니다."""
        messages = chat_data.get("messages")
        if not messages:
            return None

        user_messages = []
        for message in messages:
            if message.get("role") == "user":
                content = message.get("content", "")
                if content:
                    cleaned_content = self._clean_chat_content(content)
                    if cleaned_content:
                        user_messages.append(cleaned_content)

        if not user_messages:
            return None

        # 모든 사용자 메시지를 하나로 합치되 너무 길면 요약
        combined_messages = " | ".join(user_messages)
        if len(combined_messages) > 1000:
            combined_messages = combined_messages[:1000] + "..."

        return f"User Messages: {combined_messages}"

    def _extract_chat_metadata(self, chat_data: Dict[str, Any]) -> List[str]:
        """채팅 메타데이터(요약, 키워드)를 추출합니다."""
        metadata_parts = []

        if summary := chat_data.get("summary"):
            metadata_parts.append(f"Summary: {summary}")

        if keywords := chat_data.get("keywords"):
            if isinstance(keywords, list):
                metadata_parts.append(f"Keywords: {', '.join(keywords)}")
            else:
                metadata_parts.append(f"Keywords: {keywords}")

        return metadata_parts

    def _clean_chat_content(self, content: str) -> str:
        """
        채팅 내용에서 개인정보를 제거하고 정리합니다.

        Args:
            content: 원본 채팅 내용

        Returns:
            정리된 내용
        """
        # 기본 정리
        cleaned = content.strip()

        # 개인정보 패턴 제거
        cleaned = self._remove_personal_info_patterns(cleaned)

        # 너무 짧은 내용은 제외
        if len(cleaned) < 3:
            return ""

        return cleaned

    def _remove_personal_info_patterns(self, text: str) -> str:
        """개인정보 패턴을 제거합니다."""
        # 이메일 패턴
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)

        # 전화번호 패턴
        text = re.sub(r'\b\d{2,3}-\d{3,4}-\d{4}\b', '[PHONE]', text)
        text = re.sub(r'\b010-\d{4}-\d{4}\b', '[PHONE]', text)

        # 숫자 시퀀스 (카드번호, 계좌번호 등으로 추정되는)
        text = re.sub(r'\b\d{4}-\d{4}-\d{4}-\d{4}\b', '[CARD]', text)
        text = re.sub(r'\b\d{10,20}\b', '[NUMBER]', text)

        return text

    def _calculate_chat_weight(self, chat_data: Dict[str, Any]) -> float:
        """
        채팅 세션의 중요도에 따른 가중치를 계산합니다.

        Args:
            chat_data: 채팅 세션 데이터

        Returns:
            가중치 (0.5 ~ 3.0)
        """
        base_weight = 1.0

        # 메시지 수에 따른 가중치 (더 많은 메시지 = 더 높은 관심도)
        message_count = chat_data.get("message_count", 0)
        if message_count > 20:
            base_weight += 0.5
        elif message_count > 10:
            base_weight += 0.3
        elif message_count > 5:
            base_weight += 0.1

        # 세션 지속 시간에 따른 가중치 (더 긴 대화 = 더 높은 관심도)
        duration = chat_data.get("duration", 0)
        if duration > 1800:  # 30분 이상
            base_weight += 0.5
        elif duration > 900:  # 15분 이상
            base_weight += 0.3
        elif duration > 300:  # 5분 이상
            base_weight += 0.1

        # 특정 토픽에 따른 가중치
        topic = chat_data.get("topic", "").lower()
        if topic in ["work", "study", "education", "professional"]:
            base_weight += 0.3
        elif topic in ["hobby", "interest", "personal"]:
            base_weight += 0.2

        # 최소/최대 가중치 제한
        return max(0.5, min(3.0, base_weight))

    async def _cache_chat_update(self, user_id: int, activity_data: ActivityData):
        """
        Redis에 채팅 업데이트 정보를 임시 저장합니다.

        Args:
            user_id: 사용자 ID
            activity_data: 활동 데이터
        """
        try:
            # Redis 연결이 있는 경우에만 실행
            if hasattr(self, 'redis_client') and self.redis_client:
                cache_key = f"chat_update:{user_id}:{int(datetime.now().timestamp())}"
                cache_data = {
                    "activity_type": activity_data.activity_type.value,
                    "content": activity_data.content,
                    "timestamp": activity_data.created_at.isoformat(),
                    "metadata": activity_data.metadata,
                    "weight": activity_data.weight
                }

                # 10분 TTL로 저장 (채팅은 북마크보다 더 오래 유지)
                await self.redis_client.setex(
                    cache_key,
                    600,  # 10분
                    str(cache_data)
                )

                logger.debug(f"📝 Redis에 채팅 업데이트 캐시됨 - Key: {cache_key}")
            else:
                logger.debug("Redis 클라이언트가 없어 캐시를 건너뜁니다")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning(f"⚠️ Redis 캐시 저장 실패 - User ID: {user_id}, 오류: {e}")

    async def _cleanup_chat_cache(self, user_id: int):
        """
        처리 완료된 채팅 업데이트 캐시를 정리합니다.

        Args:
            user_id: 사용자 ID
        """
        try:
            if hasattr(self, 'redis_client') and self.redis_client:
                pattern = f"chat_update:{user_id}:*"
                keys = await self.redis_client.keys(pattern)

                if keys:
                    await self.redis_client.delete(*keys)
                    logger.debug(f"🧹 Redis 채팅 캐시 정리 완료 - {len(keys)}개 키 삭제")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning(f"⚠️ Redis 채팅 캐시 정리 실패 - User ID: {user_id}, 오류: {e}")
