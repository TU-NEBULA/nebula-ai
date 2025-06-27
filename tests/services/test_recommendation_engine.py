"""
추천 엔진 테스트

통합 추천 엔진의 핵심 기능들을 테스트합니다.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import numpy as np

from app.services.recommendation_engine import RecommendationEngine
from app.models.user_profile import UserProfile
from app.models.chat import DocumentVector


class TestRecommendationEngine:
    """추천 엔진 테스트 클래스"""

    @pytest.fixture
    def recommendation_engine(self):
        """추천 엔진 인스턴스"""
        return RecommendationEngine()

    @pytest.fixture
    def mock_user_profile(self):
        """테스트용 사용자 프로파일"""
        return UserProfile(
            user_id=123,
            profile_vector=[0.1] * 1536,
            similarity_cluster=1,
            interests=['AI', '머신러닝', 'Python'],
            category_distribution={'technology': 0.8, 'science': 0.2}
        )

    @pytest.fixture
    def mock_documents(self):
        """테스트용 문서 벡터들"""
        return [
            DocumentVector(
                id=1,
                user_id=456,
                source_id="bookmark_1",
                source_type="bookmark",
                title="AI 기초 가이드",
                url="https://example.com/ai-guide",
                content="인공지능의 기본 개념들",
                keywords=['AI', '인공지능', '머신러닝'],
                summary="AI에 대한 기초 설명",
                created_at=datetime.utcnow() - timedelta(days=1)
            ),
            DocumentVector(
                id=2,
                user_id=789,
                source_id="bookmark_2",
                source_type="bookmark",
                title="Python 프로그래밍",
                url="https://example.com/python-guide",
                content="파이썬 프로그래밍 튜토리얼",
                keywords=['Python', '프로그래밍', '개발'],
                summary="Python 프로그래밍 가이드",
                created_at=datetime.utcnow() - timedelta(days=5)
            )
        ]

    @pytest.mark.asyncio
    async def test_get_general_recommendations_basic(
        self, recommendation_engine, mock_user_profile, mock_documents
    ):
        """기본 추천 생성 테스트"""
        with patch.object(recommendation_engine, '_get_user_profile', return_value=mock_user_profile), \
             patch.object(recommendation_engine, '_get_cluster_based_candidates', return_value=[]), \
             patch.object(recommendation_engine, '_get_content_based_candidates', return_value=[
                 {
                     'document_id': 1,
                     'title': 'AI 기초 가이드',
                     'url': 'https://example.com/ai-guide',
                     'recommendation_score': 0.8,
                     'recommendation_type': 'content_based',
                     'created_at': datetime.utcnow()
                 }
             ]), \
             patch.object(recommendation_engine, '_get_popularity_based_candidates', return_value=[]), \
             patch.object(recommendation_engine, '_get_user_bookmark_urls', return_value=set()):

            recommendations = await recommendation_engine.get_general_recommendations(
                user_id=123, limit=10
            )

            assert len(recommendations) > 0
            assert recommendations[0]['title'] == 'AI 기초 가이드'
            assert 'reasoning' in recommendations[0]

    @pytest.mark.asyncio
    async def test_get_search_based_recommendations(
        self, recommendation_engine, mock_user_profile
    ):
        """검색 기반 추천 테스트"""
        mock_embedding = np.random.rand(1536)
        
        with patch.object(recommendation_engine, '_create_search_embedding', return_value=mock_embedding), \
             patch.object(recommendation_engine, '_get_user_profile', return_value=mock_user_profile), \
             patch.object(recommendation_engine, '_get_semantic_search_candidates', return_value=[
                 {
                     'document_id': 1,
                     'title': 'AI 머신러닝 가이드',
                     'url': 'https://example.com/ml-guide',
                     'semantic_similarity': 0.9,
                     'recommendation_score': 0.9,
                     'search_query': 'machine learning',
                     'created_at': datetime.utcnow()
                 }
             ]), \
             patch.object(recommendation_engine, '_apply_personalization_weights', side_effect=lambda x, *args: x), \
             patch.object(recommendation_engine, '_apply_cluster_preferences', side_effect=lambda *args: args[1]), \
             patch.object(recommendation_engine, '_expand_search_keywords', return_value=['machine', 'learning', 'ai']), \
             patch.object(recommendation_engine, '_boost_keyword_matches', side_effect=lambda x, *args: x):

            recommendations = await recommendation_engine.get_search_based_recommendations(
                user_id=123, search_query="machine learning", limit=5
            )

            assert len(recommendations) > 0
            assert recommendations[0]['title'] == 'AI 머신러닝 가이드'
            assert recommendations[0]['search_query'] == 'machine learning'

    def test_calculate_freshness_boost(self, recommendation_engine):
        """신선도 보정 계산 테스트"""
        # 1일 전 콘텐츠
        recent_date = datetime.utcnow() - timedelta(days=1)
        boost = recommendation_engine._calculate_freshness_boost(recent_date)
        assert boost == 0.3

        # 1주일 전 콘텐츠
        week_old = datetime.utcnow() - timedelta(days=7)
        boost = recommendation_engine._calculate_freshness_boost(week_old)
        assert boost == 0.2

        # 1개월 전 콘텐츠
        month_old = datetime.utcnow() - timedelta(days=30)
        boost = recommendation_engine._calculate_freshness_boost(month_old)
        assert boost == 0.1

        # 오래된 콘텐츠
        old_date = datetime.utcnow() - timedelta(days=100)
        boost = recommendation_engine._calculate_freshness_boost(old_date)
        assert boost == 0.0

    @pytest.mark.asyncio
    async def test_expand_search_keywords(self, recommendation_engine):
        """검색어 확장 테스트"""
        # AI 관련 키워드 확장
        expanded = await recommendation_engine._expand_search_keywords("ai")
        assert 'ai' in expanded
        assert '인공지능' in expanded
        assert 'machine learning' in expanded

        # 머신러닝 키워드 확장
        expanded = await recommendation_engine._expand_search_keywords("머신러닝")
        assert '머신러닝' in expanded
        assert 'ai' in expanded
        assert 'ml' in expanded

    @pytest.mark.asyncio
    async def test_boost_keyword_matches(self, recommendation_engine):
        """키워드 매칭 부스트 테스트"""
        candidates = [
            {
                'title': 'AI와 머신러닝 가이드',
                'content': '인공지능과 기계학습에 대한 설명',
                'keywords': ['AI', '머신러닝'],
                'recommendation_score': 0.7
            },
            {
                'title': '웹 개발 가이드',
                'content': 'HTML, CSS, JavaScript 개발',
                'keywords': ['web', 'frontend'],
                'recommendation_score': 0.6
            }
        ]

        keywords = ['ai', '머신러닝', 'machine learning']
        boosted = await recommendation_engine._boost_keyword_matches(candidates, keywords)

        # 첫 번째 후보는 키워드 매칭으로 점수가 향상되어야 함
        assert boosted[0]['recommendation_score'] > 0.7
        assert 'keyword_match_score' in boosted[0]

        # 두 번째 후보는 매칭되지 않아 점수 변화 없음
        assert boosted[1]['recommendation_score'] == 0.6

    @pytest.mark.asyncio
    async def test_apply_diversity_boost(self, recommendation_engine):
        """다양성 증진 테스트"""
        candidates = [
            {
                'title': 'AI 가이드 1',
                'keywords': ['AI', '머신러닝'],
                'recommendation_score': 0.9
            },
            {
                'title': 'AI 가이드 2',
                'keywords': ['AI', '딥러닝'],
                'recommendation_score': 0.8
            },
            {
                'title': '웹 개발 가이드',
                'keywords': ['JavaScript', 'React'],
                'recommendation_score': 0.7
            }
        ]

        diversified = await recommendation_engine._apply_diversity_boost(candidates)
        
        # 모든 후보가 다양성 보정을 받았는지 확인
        for candidate in diversified:
            assert 'recommendation_score' in candidate

    def test_merge_and_score_candidates(self, recommendation_engine, mock_user_profile):
        """후보 통합 및 점수 계산 테스트"""
        cluster_candidates = [
            {
                'url': 'https://example.com/ai-guide',
                'title': 'AI 가이드',
                'cluster_score': 0.8,
                'created_at': datetime.utcnow()
            }
        ]

        content_candidates = [
            {
                'url': 'https://example.com/ml-guide',
                'title': 'ML 가이드',
                'content_similarity': 0.9,
                'created_at': datetime.utcnow()
            }
        ]

        popularity_candidates = [
            {
                'url': 'https://example.com/popular-guide',
                'title': '인기 가이드',
                'popularity_score': 0.7,
                'created_at': datetime.utcnow()
            }
        ]

        # 비동기 메서드를 동기적으로 테스트하기 위한 헬퍼
        import asyncio
        merged = asyncio.run(recommendation_engine._merge_and_score_candidates(
            cluster_candidates, content_candidates, popularity_candidates, mock_user_profile
        ))

        assert len(merged) == 3
        
        # 각 후보가 적절한 점수를 받았는지 확인
        for candidate in merged:
            assert 'recommendation_score' in candidate
            assert candidate['recommendation_score'] > 0

    @pytest.mark.asyncio
    async def test_error_handling(self, recommendation_engine):
        """오류 처리 테스트"""
        # 존재하지 않는 사용자
        recommendations = await recommendation_engine.get_general_recommendations(
            user_id=99999, limit=10
        )
        assert recommendations == []

        # 빈 검색어
        recommendations = await recommendation_engine.get_search_based_recommendations(
            user_id=123, search_query="", limit=5
        )
        assert recommendations == [] 