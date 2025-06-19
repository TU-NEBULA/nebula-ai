"""
북마크 프로필 업데이트 통합 테스트

북마크 이벤트 리스너와 사용자 프로필 처리기의 통합 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from datetime import datetime

from app.listeners.user_actions import BookmarkEventListener
from app.services.user_profile_processor import UserProfileProcessor


class TestBookmarkProfileUpdateIntegration:
    """북마크 프로필 업데이트 통합 테스트 클래스"""

    @pytest.fixture
    def mock_repositories(self):
        """Mock 리포지토리들"""
        return {
            'chat_repo': MagicMock(),
            'bookmark_repo': MagicMock(),
            'ai_profile_repo': MagicMock(),
            'user_profile_repo': MagicMock()
        }

    @pytest.fixture
    def profile_processor(self, mock_repositories):
        """UserProfileProcessor 인스턴스"""
        return UserProfileProcessor(repositories=mock_repositories)

    @pytest.fixture
    def bookmark_listener(self, profile_processor):
        """BookmarkEventListener 인스턴스"""
        return BookmarkEventListener(profile_processor)

    @pytest.fixture
    def sample_bookmarks(self):
        """테스트용 샘플 북마크 데이터"""
        return [
            {
                "title": "파이썬 고급 프로그래밍 기법",
                "description": "파이썬 고급 프로그래밍 기법",
                "content": "파이썬의 메타클래스, 데코레이터, 컨텍스트 매니저에 대한 상세한 설명",
                "url": "https://python-advanced.example.com",
                "category": "programming",
                "tags": ["python", "programming", "advanced"]
            },
            {
                "title": "머신러닝 기초",
                "description": "머신러닝 기초 개념과 실습",
                "content": "선형회귀, 분류, 클러스터링 등 머신러닝의 기본 개념들",
                "url": "https://ml-basics.example.com",
                "category": "data_science",
                "tags": ["machine_learning", "data_science", "basics"]
            },
            {
                "title": "웹 개발 트렌드 2024",
                "description": "2024년 웹 개발 트렌드",
                "content": "React, Vue, Angular 등 프론트엔드 프레임워크의 최신 동향",
                "url": "https://web-trends.example.com",
                "category": "web_development",
                "tags": ["web", "frontend", "trends"]
            }
        ]

    @pytest.mark.asyncio
    async def test_single_bookmark_event_to_profile_update(
        self,
        bookmark_listener,
        profile_processor,
        sample_bookmarks,
        mock_repositories
    ):
        """단일 북마크 이벤트가 프로필 업데이트로 이어지는 테스트"""
        # Given
        user_id = 123
        bookmark_data = sample_bookmarks[0]

        # Mock OpenAI API 호출
        with patch.object(profile_processor.openai_service, 'extract_keywords') as mock_keywords, \
             patch.object(profile_processor.openai_service, 'create_embedding') as mock_embed, \
             patch.object(mock_repositories['user_profile_repo'], 'update_profile') as mock_save:

            # Mock 응답 설정
            mock_keywords.return_value = ["python", "programming", "advanced"]
            mock_embed_response = MagicMock()
            mock_embed_response.data = [MagicMock()]
            mock_embed_response.data[0].embedding = [0.1] * 1536
            mock_embed.return_value = mock_embed_response

            # Mock 기존 프로필 없음
            mock_repositories['user_profile_repo'].get_profile.return_value = None

            # When: 북마크 이벤트 처리
            result = await bookmark_listener.handle_bookmark_created(
                user_id=user_id,
                bookmark_data=bookmark_data
            )

            # Then: 결과 검증
            assert "error" not in result
            assert result["user_id"] == user_id
            assert result["event_type"] == "bookmark_created"

            # 프로필 업데이트가 호출되었는지 확인
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_bookmark_events_sequence(
        self,
        bookmark_listener,
        profile_processor,
        sample_bookmarks,
        mock_repositories
    ):
        """연속된 북마크 이벤트들이 프로필을 점진적으로 업데이트하는 테스트"""
        # Given
        user_id = 123
        results = []

        # Mock API 호출들
        with patch.object(profile_processor.openai_service, 'extract_keywords') as mock_keywords, \
             patch.object(profile_processor.openai_service, 'create_embedding') as mock_embed, \
             patch.object(mock_repositories['user_profile_repo'], 'update_profile') as mock_save:

            # Mock 응답 설정
            mock_keywords.return_value = ["test", "keyword"]
            mock_embed_response = MagicMock()
            mock_embed_response.data = [MagicMock()]
            mock_embed_response.data[0].embedding = [0.1] * 1536
            mock_embed.return_value = mock_embed_response

            # 기존 프로필 Mock
            existing_profile = MagicMock()
            existing_profile.profile_vector = [0.1] * 1536
            existing_profile.vector_metadata = {"vector_strength": 0.5}
            mock_repositories['user_profile_repo'].get_profile.return_value = existing_profile

            # When: 여러 북마크 이벤트 순차 처리
            for i, bookmark_data in enumerate(sample_bookmarks):
                result = await bookmark_listener.handle_bookmark_created(
                    user_id=user_id,
                    bookmark_data=bookmark_data,
                    metadata={"sequence": i}
                )
                results.append(result)

            # Then: 모든 이벤트가 성공적으로 처리되었는지 확인
            assert len(results) == 3
            for result in results:
                assert "error" not in result
                assert result["user_id"] == user_id

            # 프로필 업데이트가 각각 호출되었는지 확인
            assert mock_save.call_count == 3

    @pytest.mark.asyncio
    async def test_bookmark_update_vs_create_events(
        self,
        bookmark_listener,
        profile_processor,
        sample_bookmarks,
        mock_repositories
    ):
        """북마크 생성 vs 수정 이벤트의 다른 처리 방식 테스트"""
        # Given
        user_id = 123
        original_bookmark = sample_bookmarks[0].copy()
        updated_bookmark = sample_bookmarks[0].copy()
        updated_bookmark["title"] = "파이썬 고급 기법 - 업데이트됨"
        updated_bookmark["tags"] = ["python", "programming", "advanced", "updated"]

        with patch.object(profile_processor.openai_service, 'extract_keywords') as mock_keywords, \
             patch.object(profile_processor.openai_service, 'create_embedding') as mock_embed, \
             patch.object(mock_repositories['user_profile_repo'], 'update_profile') as mock_save:

            # Mock 설정
            mock_keywords.return_value = ["python", "programming"]
            mock_embed_response = MagicMock()
            mock_embed_response.data = [MagicMock()]
            mock_embed_response.data[0].embedding = [0.1] * 1536
            mock_embed.return_value = mock_embed_response

            existing_profile = MagicMock()
            existing_profile.profile_vector = [0.1] * 1536
            existing_profile.vector_metadata = {"vector_strength": 0.5}
            mock_repositories['user_profile_repo'].get_profile.return_value = existing_profile

            # When: 생성 이벤트
            create_result = await bookmark_listener.handle_bookmark_created(
                user_id=user_id,
                bookmark_data=original_bookmark
            )

            # When: 수정 이벤트 (중요한 변경사항 있음)
            update_result = await bookmark_listener.handle_bookmark_updated(
                user_id=user_id,
                bookmark_data=updated_bookmark,
                old_bookmark_data=original_bookmark
            )

            # Then: 둘 다 성공적으로 처리되었는지 확인
            assert "error" not in create_result
            assert "error" not in update_result
            assert create_result["event_type"] == "bookmark_created"
            assert update_result["event_type"] == "bookmark_updated"

            # 프로필 업데이트가 두 번 호출되었는지 확인
            assert mock_save.call_count == 2

    @pytest.mark.asyncio
    async def test_bookmark_event_with_redis_caching(
        self,
        bookmark_listener,
        profile_processor,
        sample_bookmarks,
        mock_repositories
    ):
        """Redis 캐싱이 포함된 북마크 이벤트 처리 테스트"""
        # Given
        user_id = 123
        bookmark_data = sample_bookmarks[0]

        # Mock Redis 클라이언트
        mock_redis = AsyncMock()
        profile_processor.redis_client = mock_redis

        with patch.object(profile_processor.openai_service, 'extract_keywords') as mock_keywords, \
             patch.object(profile_processor.openai_service, 'create_embedding') as mock_embed, \
             patch.object(mock_repositories['user_profile_repo'], 'update_profile') as mock_save:

            # Mock 설정
            mock_keywords.return_value = ["python", "programming"]
            mock_embed_response = MagicMock()
            mock_embed_response.data = [MagicMock()]
            mock_embed_response.data[0].embedding = [0.1] * 1536
            mock_embed.return_value = mock_embed_response

            existing_profile = MagicMock()
            existing_profile.profile_vector = [0.1] * 1536
            existing_profile.vector_metadata = {"vector_strength": 0.5}
            mock_repositories['user_profile_repo'].get_profile.return_value = existing_profile

            # When: Redis 캐싱이 활성화된 상태에서 이벤트 처리
            result = await bookmark_listener.handle_bookmark_created(
                user_id=user_id,
                bookmark_data=bookmark_data
            )

            # Then: 결과 검증
            assert "error" not in result
            assert result["user_id"] == user_id

            # Redis 캐시 메서드들이 호출되었는지 확인
            assert mock_redis.setex.called or mock_redis.keys.called

    @pytest.mark.asyncio
    async def test_bookmark_event_error_handling(
        self,
        bookmark_listener,
        profile_processor,
        sample_bookmarks,
        mock_repositories
    ):
        """북마크 이벤트 처리 중 오류 발생 시 복원력 테스트"""
        # Given
        user_id = 123
        bookmark_data = sample_bookmarks[0]

        # Mock에서 오류 발생
        with patch.object(profile_processor.openai_service, 'extract_keywords') as mock_keywords:
            mock_keywords.side_effect = Exception("OpenAI API 오류")

            # When: 오류가 발생하는 상황에서 이벤트 처리
            result = await bookmark_listener.handle_bookmark_created(
                user_id=user_id,
                bookmark_data=bookmark_data
            )

            # Then: 오류가 적절히 처리되었는지 확인
            assert "error" in result
            assert result["user_id"] == user_id
            assert result["event_type"] == "bookmark_created"
            assert "OpenAI API 오류" in str(result["error"])

    @pytest.mark.asyncio
    async def test_concurrent_bookmark_events(
        self,
        bookmark_listener,
        profile_processor,
        sample_bookmarks,
        mock_repositories
    ):
        """동시 북마크 이벤트 처리의 동시성 안전성 테스트"""
        # Given
        user_id = 123

        with patch.object(profile_processor.openai_service, 'extract_keywords') as mock_keywords, \
             patch.object(profile_processor.openai_service, 'create_embedding') as mock_embed, \
             patch.object(mock_repositories['user_profile_repo'], 'update_profile') as mock_save:

            # Mock 설정
            mock_keywords.return_value = ["test"]
            mock_embed_response = MagicMock()
            mock_embed_response.data = [MagicMock()]
            mock_embed_response.data[0].embedding = [0.1] * 1536
            mock_embed.return_value = mock_embed_response

            existing_profile = MagicMock()
            existing_profile.profile_vector = [0.1] * 1536
            existing_profile.vector_metadata = {"vector_strength": 0.5}
            mock_repositories['user_profile_repo'].get_profile.return_value = existing_profile

            # When: 동시에 여러 북마크 이벤트 처리
            tasks = []
            for i, bookmark_data in enumerate(sample_bookmarks):
                task = bookmark_listener.handle_bookmark_created(
                    user_id=user_id,
                    bookmark_data=bookmark_data,
                    metadata={"concurrent_id": i}
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            # Then: 모든 이벤트가 처리되었는지 확인
            assert len(results) == 3
            for result in results:
                assert result["user_id"] == user_id

            # 동시성 안전성 확인 (모든 호출이 완료됨)
            assert mock_save.call_count == 3

    @pytest.mark.asyncio
    async def test_bookmark_profile_quality_improvement(
        self,
        bookmark_listener,
        profile_processor,
        sample_bookmarks,
        mock_repositories
    ):
        """북마크 추가에 따른 프로필 품질 향상 테스트"""
        # Given
        user_id = 123

        # 초기 프로필 품질 낮게 설정
        initial_profile = MagicMock()
        initial_profile.profile_vector = [0.01] * 1536
        initial_profile.vector_metadata = {"vector_strength": 0.1, "data_points": 1}
        mock_repositories['user_profile_repo'].get_profile.return_value = initial_profile

        with patch.object(profile_processor.openai_service, 'extract_keywords') as mock_keywords, \
             patch.object(profile_processor.openai_service, 'create_embedding') as mock_embed, \
             patch.object(mock_repositories['user_profile_repo'], 'update_profile') as mock_save:

            # Mock 설정
            mock_keywords.return_value = ["python", "programming", "advanced"]
            mock_embed_response = MagicMock()
            mock_embed_response.data = [MagicMock()]
            mock_embed_response.data[0].embedding = [0.5] * 1536  # 더 강한 벡터
            mock_embed.return_value = mock_embed_response

            # When: 고품질 북마크 추가
            result = await bookmark_listener.handle_bookmark_created(
                user_id=user_id,
                bookmark_data=sample_bookmarks[0]  # 프로그래밍 관련 고품질 콘텐츠
            )

            # Then: 프로필 업데이트가 호출되었는지 확인
            assert "error" not in result
            mock_save.assert_called_once()

            # 실제 프로필 품질 평가 (시뮬레이션)
            quality_assessment = await profile_processor.assess_profile_quality(user_id)

            # 품질이 향상되었는지 확인 (Mock이므로 로직 호출 확인)
            assert "overall_quality" in quality_assessment
            assert "quality_score" in quality_assessment

    @pytest.mark.asyncio
    async def test_bookmark_content_extraction_comprehensive(
        self,
        profile_processor
    ):
        """북마크 콘텐츠 추출 기능의 포괄적 테스트"""
        # Given: 다양한 형태의 북마크 데이터
        test_cases = [
            {
                "bookmark_data": {
                    "title": "완전한 북마크",
                    "description": "모든 필드가 있는 북마크",
                    "category": "테스트",
                    "tags": ["tag1", "tag2"],
                    "url": "https://example.com/path",
                    "content": "추가 콘텐츠 내용"
                },
                "expected_parts": ["Title:", "Description:", "Category:", "Tags:", "Domain:", "Content:"]
            },
            {
                "bookmark_data": {
                    "title": "제목만 있는 북마크"
                },
                "expected_parts": ["Title:"]
            },
            {
                "bookmark_data": {},
                "expected_parts": ["Empty bookmark"]
            },
            {
                "bookmark_data": {
                    "title": "긴 콘텐츠 북마크",
                    "content": "a" * 1000  # 500자 초과
                },
                "expected_parts": ["Title:", "Content:", "..."]
            }
        ]

        # When & Then: 각 테스트 케이스 실행
        for test_case in test_cases:
            extracted_content = profile_processor._extract_bookmark_content(
                test_case["bookmark_data"]
            )

            # 예상된 부분들이 포함되어 있는지 확인
            for expected_part in test_case["expected_parts"]:
                assert expected_part in extracted_content, \
                    f"'{expected_part}'가 추출된 콘텐츠에 없습니다: {extracted_content}"

            # 추출된 콘텐츠가 비어있지 않은지 확인
            assert len(extracted_content.strip()) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 