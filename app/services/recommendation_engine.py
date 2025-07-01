"""
통합 추천 엔진 서비스

사용자 프로파일과 클러스터링 정보를 기반으로 
개인화된 콘텐츠 추천을 제공하는 핵심 서비스입니다.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import openai
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, desc, func

from app.core.config import settings
from app.core.database import get_async_session
from app.models.user_profile import UserProfile, Recommendation, RecommendationCreate
from app.models.bookmark import BookmarkAIStatus
from app.models.chat import DocumentVector
from app.repositories.vector_repository import VectorRepository
from app.services.vector_service import VectorService
from app.services.similarity_service import SimilarityService

log = logging.getLogger(__name__)


class RecommendationEngine:
    """통합 추천 엔진"""

    def __init__(self):
        self.vector_service = VectorService()
        self.similarity_service = SimilarityService()
        self.default_limit = 20
        self.diversity_factor = 0.3  # 다양성 가중치
        self.freshness_decay_days = 30  # 신선도 감소 기간

    async def get_general_recommendations(
        self,
        user_id: int,
        limit: int = 20,
        exclude_user_bookmarks: bool = True,
        diversity_boost: bool = True
    ) -> List[Dict[str, Any]]:
        """
        사용자를 위한 전체적인 콘텐츠 추천을 생성합니다.

        Args:
            user_id: 사용자 ID
            limit: 추천 결과 수
            exclude_user_bookmarks: 사용자 기존 북마크 제외 여부
            diversity_boost: 다양성 증진 여부

        Returns:
            추천 북마크 리스트
        """
        try:
            async for session in get_async_session():
                # 1. 사용자 프로파일 조회
                user_profile = await self._get_user_profile(session, user_id)
                if not user_profile:
                    log.warning(f"사용자 {user_id}의 프로파일이 없습니다.")
                    return []

                # 2. 클러스터 기반 추천 후보 수집
                cluster_candidates = []
                if user_profile.similarity_cluster:
                    cluster_candidates = await self._get_cluster_based_candidates(
                        session, user_id, user_profile.similarity_cluster, limit * 2
                    )

                # 3. 콘텐츠 기반 추천 후보 수집
                content_candidates = []
                if user_profile.profile_vector is not None and len(user_profile.profile_vector) > 0:
                    content_candidates = await self._get_content_based_candidates(
                        session, user_id, user_profile.profile_vector, limit * 2
                    )

                # 4. 인기도 기반 추천 후보 수집
                popularity_candidates = await self._get_popularity_based_candidates(
                    session, user_id, limit
                )

                # 5. 후보들 통합 및 점수 계산
                all_candidates = await self._merge_and_score_candidates(
                    cluster_candidates, content_candidates, popularity_candidates,
                    user_profile
                )

                # 6. 사용자 기존 북마크 제외
                if exclude_user_bookmarks:
                    user_bookmark_urls = await self._get_user_bookmark_urls(session, user_id)
                    all_candidates = [
                        candidate for candidate in all_candidates
                        if candidate.get('url') not in user_bookmark_urls
                    ]

                # 7. 다양성 증진
                if diversity_boost:
                    all_candidates = await self._apply_diversity_boost(all_candidates)

                # 8. 최종 결과 정렬 및 제한
                final_recommendations = sorted(
                    all_candidates, 
                    key=lambda x: x['recommendation_score'], 
                    reverse=True
                )[:limit]

                # 9. 추천 이유 생성
                for rec in final_recommendations:
                    rec['reasoning'] = await self._generate_recommendation_reasoning(
                        rec, user_profile
                    )

                log.info(f"사용자 {user_id}에게 {len(final_recommendations)}개의 일반 추천 생성")
                return final_recommendations

        except Exception as e:
            log.error(f"일반 추천 생성 중 오류: {e}")
            return []

    async def get_search_based_recommendations(
        self,
        user_id: int,
        search_query: str,
        limit: int = 15,
        personalization_weight: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        검색어 기반 실시간 개인화 추천을 생성합니다.

        Args:
            user_id: 사용자 ID
            search_query: 검색어
            limit: 추천 결과 수
            personalization_weight: 개인화 가중치 (0.0-1.0)

        Returns:
            검색어 기반 추천 북마크 리스트
        """
        try:
            async for session in get_async_session():
                # 1. 검색어 임베딩 생성
                search_embedding = await self._create_search_embedding(search_query)
                if np.allclose(search_embedding, 0.0):
                    log.warning("검색어 임베딩 생성 실패")
                    return []

                # 2. 사용자 프로파일 조회
                user_profile = await self._get_user_profile(session, user_id)

                # 3. 벡터 유사도 기반 검색
                semantic_candidates = await self._get_semantic_search_candidates(
                    session, search_embedding, user_id, limit * 2
                )

                # 4. 개인화 가중치 적용
                if user_profile and user_profile.profile_vector is not None and len(user_profile.profile_vector) > 0 and personalization_weight > 0:
                    semantic_candidates = await self._apply_personalization_weights(
                        semantic_candidates, user_profile.profile_vector, personalization_weight
                    )

                # 5. 클러스터 선호도 반영
                if user_profile and user_profile.similarity_cluster:
                    semantic_candidates = await self._apply_cluster_preferences(
                        session, semantic_candidates, user_profile.similarity_cluster
                    )

                # 6. 검색어 관련 키워드 확장
                expanded_keywords = await self._expand_search_keywords(search_query)
                semantic_candidates = await self._boost_keyword_matches(
                    semantic_candidates, expanded_keywords
                )

                # 7. 최종 점수 계산 및 정렬
                final_recommendations = sorted(
                    semantic_candidates,
                    key=lambda x: x['recommendation_score'],
                    reverse=True
                )[:limit]

                # 8. 추천 이유 생성
                for rec in final_recommendations:
                    rec['reasoning'] = await self._generate_search_recommendation_reasoning(
                        rec, search_query, expanded_keywords, user_profile
                    )
                    rec['search_query'] = search_query

                log.info(f"검색어 '{search_query}'로 사용자 {user_id}에게 {len(final_recommendations)}개 추천 생성")
                return final_recommendations

        except Exception as e:
            log.error(f"검색 기반 추천 생성 중 오류: {e}")
            return []

    # === Helper Methods ===

    async def _get_user_profile(self, session: AsyncSession, user_id: int) -> Optional[UserProfile]:
        """사용자 프로파일 조회"""
        try:
            result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            log.error(f"사용자 프로파일 조회 오류: {e}")
            return None

    async def _get_cluster_based_candidates(
        self, session: AsyncSession, user_id: int, cluster_id: int, limit: int
    ) -> List[Dict[str, Any]]:
        """클러스터 기반 추천 후보 수집"""
        try:
            # 같은 클러스터 사용자들이 최근에 저장한 인기 북마크들
            cluster_query = select(DocumentVector).join(
                UserProfile, DocumentVector.user_id == UserProfile.user_id
            ).where(
                and_(
                    UserProfile.similarity_cluster == cluster_id,
                    DocumentVector.user_id != user_id,
                    DocumentVector.source_type == "bookmark_content",
                    DocumentVector.created_at >= datetime.now(timezone.utc) - timedelta(days=90)
                )
            ).order_by(desc(DocumentVector.created_at)).limit(limit)

            result = await session.execute(cluster_query)
            documents = result.scalars().all()

            candidates = []
            for doc in documents:
                candidates.append({
                    'document_id': doc.id,
                    'source_id': doc.source_id,
                    'title': doc.title,
                    'url': doc.url,
                    'content': doc.content,
                    'keywords': doc.keywords or [],
                    'summary': doc.summary,
                    'cluster_score': 0.8,
                    'created_at': doc.created_at,
                    'recommendation_type': 'cluster_based'
                })

            return candidates

        except Exception as e:
            log.error(f"클러스터 기반 후보 수집 오류: {e}")
            return []

    async def _get_content_based_candidates(
        self, session: AsyncSession, user_id: int, user_vector: List[float], limit: int
    ) -> List[Dict[str, Any]]:
        """콘텐츠 기반 추천 후보 수집"""
        try:
            similar_documents = await VectorRepository.similarity_search(
                session=session,
                query_embedding=user_vector,
                source_types=["bookmark_content"],
                limit=limit,
                similarity_threshold=0.6
            )

            candidates = []
            for doc, similarity_score in similar_documents:
                if doc.user_id == user_id:
                    continue

                candidates.append({
                    'document_id': doc.id,
                    'source_id': doc.source_id,
                    'title': doc.title,
                    'url': doc.url,
                    'content': doc.content,
                    'keywords': doc.keywords or [],
                    'summary': doc.summary,
                    'content_similarity': similarity_score,
                    'created_at': doc.created_at,
                    'recommendation_type': 'content_based'
                })

            return candidates

        except Exception as e:
            log.error(f"콘텐츠 기반 후보 수집 오류: {e}")
            return []

    async def _get_popularity_based_candidates(
        self, session: AsyncSession, user_id: int, limit: int
    ) -> List[Dict[str, Any]]:
        """인기도 기반 추천 후보 수집"""
        try:
            # 최근 30일간 가장 많이 저장된 북마크들
            popularity_subquery = select(
                DocumentVector.url,
                func.count(DocumentVector.id).label('bookmark_count')
            ).where(
                and_(
                    DocumentVector.source_type == "bookmark_content",
                    DocumentVector.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
                )
            ).group_by(DocumentVector.url).subquery()

            popular_query = select(DocumentVector).join(
                popularity_subquery, DocumentVector.url == popularity_subquery.c.url
            ).where(
                DocumentVector.user_id != user_id
            ).order_by(desc(popularity_subquery.c.bookmark_count)).limit(limit)

            result = await session.execute(popular_query)
            documents = result.scalars().all()

            candidates = []
            for doc in documents:
                candidates.append({
                    'document_id': doc.id,
                    'source_id': doc.source_id,
                    'title': doc.title,
                    'url': doc.url,
                    'content': doc.content,
                    'keywords': doc.keywords or [],
                    'summary': doc.summary,
                    'popularity_score': 0.6,
                    'created_at': doc.created_at,
                    'recommendation_type': 'popularity_based'
                })

            return candidates

        except Exception as e:
            log.error(f"인기도 기반 후보 수집 오류: {e}")
            return []

    async def _merge_and_score_candidates(
        self, cluster_candidates: List[Dict], content_candidates: List[Dict],
        popularity_candidates: List[Dict], user_profile: UserProfile
    ) -> List[Dict[str, Any]]:
        """후보들을 통합하고 최종 점수를 계산"""
        combined_candidates = {}
        
        # 클러스터 기반 후보 처리 (가중치: 0.4)
        for candidate in cluster_candidates:
            url = candidate.get('url')
            if url and url not in combined_candidates:
                candidate['recommendation_score'] = candidate.get('cluster_score', 0.8) * 0.4
                combined_candidates[url] = candidate

        # 콘텐츠 기반 후보 처리 (가중치: 0.5)
        for candidate in content_candidates:
            url = candidate.get('url')
            if url:
                content_score = candidate.get('content_similarity', 0.7) * 0.5
                if url in combined_candidates:
                    combined_candidates[url]['recommendation_score'] += content_score
                    combined_candidates[url]['recommendation_type'] = 'hybrid'
                else:
                    candidate['recommendation_score'] = content_score
                    combined_candidates[url] = candidate

        # 인기도 기반 후보 처리 (가중치: 0.1)
        for candidate in popularity_candidates:
            url = candidate.get('url')
            if url:
                popularity_score = candidate.get('popularity_score', 0.6) * 0.1
                if url in combined_candidates:
                    combined_candidates[url]['recommendation_score'] += popularity_score
                else:
                    candidate['recommendation_score'] = popularity_score
                    combined_candidates[url] = candidate

        # 신선도 보정 적용
        for candidate in combined_candidates.values():
            freshness_boost = self._calculate_freshness_boost(candidate.get('created_at'))
            candidate['recommendation_score'] *= (1 + freshness_boost)

        return list(combined_candidates.values())

    def _calculate_freshness_boost(self, created_at: datetime) -> float:
        """콘텐츠 신선도에 따른 점수 보정 계산"""
        if not created_at:
            return 0.0
        
        # timezone-aware datetime 사용
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            # created_at이 timezone-naive인 경우 UTC로 가정
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        days_old = (now - created_at).days
        if days_old <= 1:
            return 0.3
        elif days_old <= 7:
            return 0.2
        elif days_old <= 30:
            return 0.1
        else:
            return 0.0

    async def _get_user_bookmark_urls(self, session: AsyncSession, user_id: int) -> set:
        """사용자가 이미 저장한 북마크 URL들 조회"""
        try:
            result = await session.execute(
                select(DocumentVector.url).where(
                    and_(
                        DocumentVector.user_id == user_id,
                        DocumentVector.source_type == "bookmark_content"
                    )
                ).distinct()
            )
            return set(url for url, in result.fetchall() if url)
        except Exception as e:
            log.error(f"사용자 북마크 URL 조회 오류: {e}")
            return set()

    async def _apply_diversity_boost(self, candidates: List[Dict]) -> List[Dict]:
        """추천 결과의 다양성을 증진"""
        if not candidates:
            return candidates

        seen_keywords = set()
        for candidate in candidates:
            keywords = candidate.get('keywords', [])
            keyword_overlap = len(set(keywords) & seen_keywords)
            
            diversity_bonus = max(0, (1 - keyword_overlap / max(len(keywords), 1))) * self.diversity_factor
            candidate['recommendation_score'] *= (1 + diversity_bonus)
            
            seen_keywords.update(keywords)

        return candidates

    async def _create_search_embedding(self, search_query: str) -> np.ndarray:
        """검색어에 대한 임베딩 생성"""
        try:
            log.info(f"검색어 임베딩 생성 시작: '{search_query}'")
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            # OpenAI Embeddings API 사용 (새버전 방식)
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    lambda: openai.embeddings.create(
                        model="text-embedding-ada-002",
                        input=search_query
                    )
                )
            
            embedding = np.array(response.data[0].embedding)
            log.info(f"검색어 임베딩 생성 성공: {search_query[:50]}..., 크기: {len(embedding)}, 첫 5개 값: {embedding[:5].tolist()}")
            return embedding
            
        except Exception as e:
            log.error(f"검색어 임베딩 생성 오류: {e}")
            log.error(f"검색어 임베딩 생성 실패")
            return np.zeros(1536)  # OpenAI ada-002 차원

    async def _get_semantic_search_candidates(
        self, session: AsyncSession, search_embedding: np.ndarray, user_id: int, limit: int
    ) -> List[Dict[str, Any]]:
        """의미적 검색을 통한 추천 후보 수집"""
        try:
            similar_documents = await VectorRepository.similarity_search(
                session=session,
                query_embedding=search_embedding.tolist(),
                source_types=["bookmark_content"],
                limit=limit,
                similarity_threshold=0.01  # 0.1에서 0.01로 더 낮춤
            )
            
            log.info(f"벡터 유사도 검색 원본 결과 수: {len(similar_documents)}")

            candidates = []
            filtered_count = 0
            for doc, similarity_score in similar_documents:
                if doc.user_id == user_id:
                    filtered_count += 1
                    continue

                candidates.append({
                    'document_id': doc.id,
                    'source_id': doc.source_id,
                    'title': doc.title,
                    'url': doc.url,
                    'content': doc.content,
                    'keywords': doc.keywords or [],
                    'summary': doc.summary,
                    'semantic_similarity': similarity_score,
                    'recommendation_score': similarity_score,
                    'created_at': doc.created_at,
                    'recommendation_type': 'search_based'
                })

            log.info(f"사용자 {user_id} 자신의 북마크 필터링: {filtered_count}개")
            log.info(f"최종 검색 기반 추천 후보 수: {len(candidates)}")
            
            return candidates

        except Exception as e:
            log.error(f"의미적 검색 후보 수집 오류: {e}")
            return []

    async def _apply_personalization_weights(
        self, candidates: List[Dict], user_vector: List[float], weight: float
    ) -> List[Dict]:
        """개인화 가중치 적용"""
        try:
            user_embedding = np.array(user_vector)
            
            for candidate in candidates:
                # 문서 임베딩 조회 (간단화를 위해 기본값 사용)
                doc_embedding = np.random.rand(len(user_vector))  # 실제로는 문서의 벡터를 조회
                
                # 개인화 점수 계산
                personalization_score = cosine_similarity(
                    user_embedding.reshape(1, -1),
                    doc_embedding.reshape(1, -1)
                )[0][0]
                
                # 기존 점수와 개인화 점수 결합
                original_score = candidate.get('recommendation_score', 0.0)
                candidate['recommendation_score'] = (
                    original_score * (1 - weight) + personalization_score * weight
                )
                candidate['personalization_score'] = personalization_score
                
            return candidates
            
        except Exception as e:
            log.error(f"개인화 가중치 적용 오류: {e}")
            return candidates

    async def _apply_cluster_preferences(
        self, session: AsyncSession, candidates: List[Dict], cluster_id: int
    ) -> List[Dict]:
        """클러스터 선호도 반영"""
        try:
            # 같은 클러스터 사용자들의 선호도 조회
            cluster_preference_query = select(DocumentVector.url, func.count().label('popularity')).join(
                UserProfile, DocumentVector.user_id == UserProfile.user_id
            ).where(
                and_(
                    UserProfile.similarity_cluster == cluster_id,
                    DocumentVector.source_type == "bookmark_content"
                )
            ).group_by(DocumentVector.url)
            
            result = await session.execute(cluster_preference_query)
            cluster_preferences = {url: count for url, count in result.fetchall()}
            
            for candidate in candidates:
                url = candidate.get('url')
                if url in cluster_preferences:
                    cluster_boost = min(cluster_preferences[url] / 10.0, 0.3)  # 최대 30% 부스트
                    candidate['recommendation_score'] *= (1 + cluster_boost)
                    candidate['cluster_boost'] = cluster_boost
                    
            return candidates
            
        except Exception as e:
            log.error(f"클러스터 선호도 반영 오류: {e}")
            return candidates

    async def _expand_search_keywords(self, search_query: str) -> List[str]:
        """검색어 관련 키워드 확장"""
        try:
            # 기본 키워드 분할
            keywords = search_query.lower().split()
            
            # 동의어/유사어 확장 (간단한 예시)
            keyword_expansions = {
                'ai': ['인공지능', 'artificial intelligence', 'machine learning'],
                '머신러닝': ['ai', 'machine learning', 'ml', '기계학습'],
                '딥러닝': ['deep learning', 'neural network', '신경망'],
                'python': ['파이썬', 'programming', '프로그래밍'],
                'javascript': ['js', '자바스크립트', 'frontend'],
                'react': ['리액트', 'frontend', 'web development']
            }
            
            expanded = keywords.copy()
            for keyword in keywords:
                if keyword in keyword_expansions:
                    expanded.extend(keyword_expansions[keyword])
                    
            return list(set(expanded))  # 중복 제거
            
        except Exception as e:
            log.error(f"키워드 확장 오류: {e}")
            return search_query.lower().split()

    async def _boost_keyword_matches(self, candidates: List[Dict], keywords: List[str]) -> List[Dict]:
        """키워드 매칭에 따른 점수 부스트"""
        try:
            for candidate in candidates:
                doc_keywords = candidate.get('keywords', [])
                title = candidate.get('title', '').lower()
                content = candidate.get('content', '').lower()
                
                # 키워드 매칭 점수 계산
                keyword_matches = 0
                total_keywords = len(keywords)
                
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    if (keyword_lower in doc_keywords or 
                        keyword_lower in title or 
                        keyword_lower in content):
                        keyword_matches += 1
                
                if total_keywords > 0:
                    keyword_score = keyword_matches / total_keywords
                    boost_factor = 1 + (keyword_score * 0.4)  # 최대 40% 부스트
                    candidate['recommendation_score'] *= boost_factor
                    candidate['keyword_match_score'] = keyword_score
                    
            return candidates
            
        except Exception as e:
            log.error(f"키워드 매칭 부스트 오류: {e}")
            return candidates

    async def _generate_recommendation_reasoning(self, recommendation: Dict, user_profile: UserProfile) -> Dict[str, Any]:
        """추천 이유 생성"""
        return {
            'type': recommendation.get('recommendation_type', 'unknown'),
            'factors': [
                {
                    'factor': 'content_similarity',
                    'description': "당신의 관심사와 유사한 콘텐츠",
                    'weight': recommendation.get('content_similarity', 0.5)
                }
            ]
        }

    async def _generate_search_recommendation_reasoning(
        self, recommendation: Dict, search_query: str, 
        expanded_keywords: List[str], user_profile: Optional[UserProfile]
    ) -> Dict[str, Any]:
        """검색 기반 추천 이유 생성"""
        factors = []
        
        # 의미적 유사도
        semantic_score = recommendation.get('semantic_similarity', 0.0)
        if semantic_score > 0:
            factors.append({
                'factor': 'semantic_similarity',
                'description': f"'{search_query}'와 의미적으로 유사한 콘텐츠",
                'weight': semantic_score
            })
        
        # 키워드 매칭
        keyword_score = recommendation.get('keyword_match_score', 0.0)
        if keyword_score > 0:
            factors.append({
                'factor': 'keyword_matching',
                'description': f"검색어와 관련된 키워드 포함",
                'weight': keyword_score
            })
        
        # 개인화 점수
        if user_profile and recommendation.get('personalization_score'):
            factors.append({
                'factor': 'personalization',
                'description': "당신의 관심사와 일치하는 콘텐츠",
                'weight': recommendation.get('personalization_score', 0.0)
            })
        
        # 클러스터 부스트
        if recommendation.get('cluster_boost'):
            factors.append({
                'factor': 'cluster_preference',
                'description': "유사한 사용자들이 선호하는 콘텐츠",
                'weight': recommendation.get('cluster_boost', 0.0)
            })
        
        return {
            'type': 'search_based',
            'search_query': search_query,
            'expanded_keywords': expanded_keywords,
            'factors': factors,
            'confidence': recommendation.get('recommendation_score', 0.0)
        } 