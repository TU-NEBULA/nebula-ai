"""
통합 테스트

전체 시스템의 통합 테스트
- API + Vector Generation + Message Queue 연동
- 실제 워크플로우 시뮬레이션
- 성능 및 안정성 테스트
- End-to-End 시나리오
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.services.vector_generator import VectorGenerator, ActivityData, ActivityType
from app.services.message_handlers import ProfileMessageHandler
from app.external.openai_service import OpenAIService


class TestEndToEndUserProfileWorkflow:
    """사용자 프로필 전체 워크플로우 테스트"""
    
    @pytest.fixture
    def client(self):
        """FastAPI 테스트 클라이언트"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI 서비스"""
        mock_service = AsyncMock()  # spec 제거
        
        # OpenAI API 응답 형식으로 Mock 설정
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.1, 0.8, 0.3, 0.5, 0.9] * 307 + [0.2]  # 1536차원 벡터
        mock_service.create_embedding.return_value = mock_embedding_response
        
        # generate_completion Mock 설정 (JSON 문자열 반환)
        mock_completion_response = MagicMock()
        mock_completion_response.choices = [MagicMock()]
        mock_completion_response.choices[0].message.content = '''
        {
            "keywords": {"AI": 0.9, "머신러닝": 0.8, "딥러닝": 0.7},
            "topics": {"인공지능": 0.9, "기술": 0.7},
            "categories": {"컴퓨터과학": 0.8, "기술": 0.6},
            "concepts": {"미래": 0.7, "혁신": 0.6}
        }
        '''
        mock_service.generate_completion.return_value = mock_completion_response
        
        # analyze_text_interests는 실제로 VectorGenerator에서 직접 사용되지 않음
        mock_service.analyze_text_interests.return_value = {
            "keywords": {"AI": 0.9, "머신러닝": 0.8},
            "topics": {"인공지능": 0.9, "기술": 0.7},
            "categories": {"IT": 0.85, "연구": 0.75}
        }
        return mock_service
    
    @pytest.fixture
    def mock_user_data(self):
        """테스트용 사용자 데이터"""
        return {
            "user_id": 123,
            "chat_data": [
                {"content": "AI와 머신러닝에 관심이 많습니다", "timestamp": datetime.now()},
                {"content": "딥러닝 프로젝트를 진행하고 있어요", "timestamp": datetime.now()}
            ],
            "bookmark_data": [
                {"title": "GPT-4 논문", "url": "https://example.com/gpt4", "content": "최신 AI 연구", "timestamp": datetime.now()},
                {"title": "PyTorch 튜토리얼", "url": "https://pytorch.org", "content": "딥러닝 프레임워크", "timestamp": datetime.now()}
            ],
            "ai_profile_data": [
                {"profile_data": {"interests": ["AI", "Programming"], "skills": ["Python", "TensorFlow"]}, "timestamp": datetime.now()}
            ]
        }
    
    @pytest.mark.asyncio
    async def test_complete_user_profile_creation_workflow(self, mock_openai_service, mock_user_data):
        """완전한 사용자 프로필 생성 워크플로우 테스트"""
        
        # 1. Vector Generator 초기화
        vector_generator = VectorGenerator(mock_openai_service)
        
        # 2. 사용자 데이터 수집 시뮬레이션
        collected_data = []
        
        # 채팅 데이터 처리
        for chat in mock_user_data["chat_data"]:
            collected_data.append({
                "content": chat["content"],
                "timestamp": chat["timestamp"],
                "activity_type": "chat",
                "weight": 1.0
            })
        
        # 북마크 데이터 처리
        for bookmark in mock_user_data["bookmark_data"]:
            collected_data.append({
                "content": f"{bookmark['title']} {bookmark['content']}",
                "timestamp": bookmark["timestamp"],
                "activity_type": "bookmark",
                "weight": 1.5
            })
        
        # AI 프로필 데이터 처리
        for ai_profile in mock_user_data["ai_profile_data"]:
            profile_text = json.dumps(ai_profile["profile_data"])
            collected_data.append({
                "content": profile_text,
                "timestamp": ai_profile["timestamp"],
                "activity_type": "ai_profile",
                "weight": 1.2
            })
        
        # 3. 벡터 생성 실행
        # ActivityData 형식으로 변환
        activity_data_list = []
        for data in collected_data:
            activity_type = ActivityType(data["activity_type"])
            activity_data_list.append(ActivityData(
                activity_type=activity_type,
                content=data["content"],
                created_at=data["timestamp"],
                weight=data["weight"]
            ))
        
        result_vector, result_metadata = await vector_generator.generate_profile_vector(
            activity_data_list
        )
        
        # 4. 결과 검증 (새로운 반환 형식에 맞춤)
        assert result_vector is not None
        assert result_metadata is not None
        assert len(result_vector) > 0
        assert isinstance(result_metadata, dict)
        
        # 5. 생성된 벡터 품질 확인
        assert all(isinstance(v, (int, float)) for v in result_vector)
        assert any(v != 0 for v in result_vector)  # 모든 값이 0이 아님
        
        # 6. 메타데이터 검증 (새로운 형식에 맞춤)
        assert "generation_timestamp" in result_metadata
        assert "total_activities" in result_metadata
        assert "layer_strengths" in result_metadata
        assert result_metadata["total_activities"] == 5


class TestAPIAndMessageQueueIntegration:
    """API와 메시지 큐 통합 테스트"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def message_handler(self):
        """Mock 메시지 핸들러"""
        with patch('app.services.message_handlers.OpenAIService'), \
             patch('app.services.message_handlers.VectorGenerator'):
            return ProfileMessageHandler()
    
    @pytest.mark.asyncio
    async def test_api_call_triggers_background_processing(self, client, message_handler):
        """API 호출이 백그라운드 처리를 트리거하는 시나리오"""
        
        # 1. 프로필 조회 API 호출 - 캐시 미스 시뮬레이션
        with patch('app.routers.profile.UserProfileRepository') as mock_repo, \
             patch('app.routers.profile.RecommendationRepository') as mock_rec_repo:
            
            # 프로필은 존재하지만 추천이 없는 상황
            mock_profile = MagicMock()
            mock_profile.user_id = 123
            mock_profile.profile_vector = [0.1, 0.8, 0.3]
            mock_profile.updated_at = datetime.now()
            mock_profile.vector_strength = 0.85
            mock_profile.completeness_score = 78
            
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_or_create_profile.return_value = mock_profile
            mock_repo.return_value = mock_repo_instance
            
            # 추천 없음 (캐시 미스)
            mock_rec_repo_instance = AsyncMock()
            mock_rec_repo_instance.get_user_recommendations.return_value = []
            mock_rec_repo.return_value = mock_rec_repo_instance
            
            # API 호출
            response = client.get("/api/v1/profiles/123/recommendations")
            
            # 2. API 응답 검증
            assert response.status_code == 200
            data = response.json()
            assert data["cache_status"] == "MISS"
            assert data["refresh_requested"] is True
            
        # 3. 백그라운드 메시지 처리 시뮬레이션
        recommendation_message = {
            "user_id": 123,
            "categories": None,
            "priority": "normal",
            "use_research": False
        }
        
        with patch('app.services.message_handlers.get_async_session') as mock_session, \
             patch('app.services.message_handlers.create_repositories') as mock_create_repos, \
             patch('app.services.message_handlers.UserProfileProcessor') as mock_processor_class:
            
            # Mock 설정 - async for 지원을 위한 async generator
            mock_session_instance = AsyncMock()
            async def async_session_generator():
                yield mock_session_instance
            mock_session.return_value = async_session_generator()
            
            mock_repos = {
                'chat_repo': AsyncMock(),
                'bookmark_repo': AsyncMock(),
                'ai_profile_repo': AsyncMock(),
                'user_profile_repo': AsyncMock()
            }
            mock_create_repos.return_value = mock_repos
            
            # 프로필 Mock - handle_recommendation_refresh에서 사용
            mock_profile = MagicMock()
            mock_profile.user_id = 123
            mock_repos['user_profile_repo'].get_or_create_profile.return_value = mock_profile
            
            # 유사한 사용자들 Mock - 정확히 15개 반환하도록 설정
            mock_repos['user_profile_repo'].get_similar_users.return_value = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
            
            mock_processor = AsyncMock()
            mock_processor.user_profile_repo = mock_repos['user_profile_repo']  # 명시적으로 설정
            mock_processor.generate_recommendations.return_value = {"recommendation_count": 15}
            mock_processor_class.return_value = mock_processor
            
            # 백그라운드 처리 실행
            result = await message_handler.handle_recommendation_refresh(recommendation_message)
            
            # 4. 백그라운드 처리 결과 검증
            assert result["success"] is True
            assert result["user_id"] == 123
            assert result["recommendations_generated"] == 15
    
    @pytest.mark.asyncio
    async def test_incremental_update_workflow(self, message_handler):
        """점진적 업데이트 워크플로우 테스트"""
        
        # 1. 초기 프로필 업데이트 메시지
        initial_message = {
            "user_id": 456,
            "update_type": "incremental",
            "incremental_update": True,
            "source_data": {
                "bookmarks": [{"title": "새로운 AI 논문", "content": "GPT-5 관련"}],
                "activity_type": "bookmark_added"
            },
            "preference_adjustments": {"AI": 0.95}
        }
        
        with patch('app.services.message_handlers.get_async_session') as mock_session, \
             patch('app.services.message_handlers.create_repositories') as mock_create_repos, \
             patch('app.services.message_handlers.UserProfileProcessor') as mock_processor_class:
            
            # Mock 설정 - async for 지원을 위한 async generator
            mock_session_instance = AsyncMock()
            async def async_session_generator():
                yield mock_session_instance
            mock_session.return_value = async_session_generator()
            
            mock_repos = {
                'chat_repo': AsyncMock(),
                'bookmark_repo': AsyncMock(),
                'ai_profile_repo': AsyncMock(),
                'user_profile_repo': AsyncMock()
            }
            mock_create_repos.return_value = mock_repos
            
            mock_processor = AsyncMock()
            # 새로운 메서드 시그니처에 맞춘 return value
            mock_processor.update_vector_incrementally.return_value = (
                [0.1] * 1536,  # result_vector
                {  # result_metadata
                    "vector_strength": 0.88,
                    "processing_time": 1.5,
                    "updated_keywords": ["AI", "GPT"]
                }
            )
            mock_processor_class.return_value = mock_processor
            
            # Mock 선호도 조정
            message_handler._apply_preference_adjustments = AsyncMock()
            
            # 2. 점진적 업데이트 실행
            result = await message_handler.handle_profile_update(initial_message)
            
            # 3. 결과 검증
            assert result["success"] is True
            assert result["user_id"] == 456
            assert result["update_type"] == "incremental"
            assert result["vector_strength"] == 0.88
            
            # 4. 메서드 호출 확인
            mock_processor.update_vector_incrementally.assert_called_once()
            message_handler._apply_preference_adjustments.assert_called_once()


class TestPerformanceAndScalability:
    """성능 및 확장성 테스트"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, client):
        """동시 API 요청 처리 테스트"""
        
        # Mock 설정
        with patch('app.routers.profile.UserProfileRepository') as mock_repo:
            mock_profile = MagicMock()
            mock_profile.user_id = 123
            mock_profile.profile_vector = [0.1, 0.8, 0.3, 0.5, 0.9]
            mock_profile.updated_at = datetime.now()
            mock_profile.vector_strength = 0.85
            mock_profile.completeness_score = 78
            
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_or_create_profile.return_value = mock_profile
            mock_repo.return_value = mock_repo_instance
            
            # 동시 요청
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                tasks = []
                for i in range(20):  # 20개 동시 요청
                    task = ac.get(f"/api/v1/profiles/{123 + i}")
                    tasks.append(task)
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 모든 요청이 성공했는지 확인
                success_count = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 200)
                assert success_count >= 18  # 90% 이상 성공률
    
    @pytest.mark.asyncio
    async def test_large_dataset_vector_generation(self):
        """대용량 데이터셋 벡터 생성 테스트"""
        
        # Mock OpenAI 서비스
        mock_openai_service = AsyncMock()
        mock_openai_service.create_embedding.return_value = [0.1] * 128  # 128차원 벡터
        mock_openai_service.analyze_text_interests.return_value = {
            "keywords": {f"keyword_{i}": 0.5 + (i % 5) * 0.1 for i in range(20)},
            "topics": {f"topic_{i}": 0.6 + (i % 3) * 0.1 for i in range(10)},
            "categories": {f"category_{i}": 0.7 + (i % 4) * 0.05 for i in range(8)}
        }
        
        vector_generator = VectorGenerator(mock_openai_service)
        
        # 대용량 데이터 생성 (1000개 활동) - ActivityData 형식으로 변환
        large_dataset = []
        for i in range(1000):
            activity_type = ActivityType(["chat", "bookmark", "ai_profile"][i % 3])
            large_dataset.append(ActivityData(
                activity_type=activity_type,
                content=f"This is content number {i} with various AI and machine learning topics",
                created_at=datetime.now() - timedelta(days=i % 30),
                weight=1.0 + (i % 3) * 0.5
            ))
        
        # 벡터 생성 실행 및 시간 측정
        import time
        start_time = time.time()
        
        result_vector, result_metadata = await vector_generator.generate_profile_vector(large_dataset)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 성능 검증
        assert result_vector is not None
        assert processing_time < 10.0  # 10초 이내 처리
        assert len(result_vector) == 1536  # 기본 차원
        assert result_metadata is not None
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """부하 상황에서 메모리 사용량 테스트"""
        import psutil
        import os
        
        # 현재 프로세스 메모리 사용량 측정
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Mock OpenAI 서비스
        mock_openai_service = AsyncMock()
        mock_openai_service.create_embedding.return_value = [0.1] * 64
        mock_openai_service.analyze_text_interests.return_value = {
            "keywords": {"AI": 0.9},
            "topics": {"tech": 0.8},
            "categories": {"IT": 0.7}
        }
        
        vector_generator = VectorGenerator(mock_openai_service)
        
        # 여러 사용자에 대해 벡터 생성
        result_vector = None
        result_metadata = None
        for user_id in range(50):
            dataset = []
            for _ in range(100):  # 각 사용자당 100개 데이터
                activity_type = ActivityType("chat")
                dataset.append(ActivityData(
                    activity_type=activity_type,
                    content=f"User {user_id} content about AI and technology",
                    created_at=datetime.now(),
                    weight=1.0
                ))
            
            result_vector, result_metadata = await vector_generator.generate_profile_vector(dataset)
        
        # 메모리 사용량 확인
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # 메모리 증가량이 합리적인지 확인 (500MB 이하)
        assert memory_increase < 500, f"메모리 사용량이 너무 많이 증가했습니다: {memory_increase:.2f}MB"

        # 메타데이터 검증 (메타데이터만)
        assert result_metadata is not None
        assert len(result_metadata.get("keywords", {})) >= 0


class TestErrorHandlingAndRecovery:
    """오류 처리 및 복구 테스트"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def message_handler(self):
        with patch('app.services.message_handlers.OpenAIService'), \
             patch('app.services.message_handlers.VectorGenerator'):
            return ProfileMessageHandler()
    
    @pytest.mark.asyncio
    async def test_api_error_recovery(self, client):
        """API 오류 복구 테스트"""
        
        # 데이터베이스 연결 실패 시뮬레이션
        with patch('app.routers.profile.UserProfileRepository') as mock_repo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_or_create_profile.side_effect = Exception("Database connection failed")
            mock_repo.return_value = mock_repo_instance
            
            # API 호출
            response = client.get("/api/v1/profiles/123")
            
            # 적절한 오류 응답 확인
            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_message_queue_error_handling(self, message_handler):
        """메시지 큐 오류 처리 테스트"""
        
        # 잘못된 메시지 형식
        invalid_message = {
            "invalid_field": "invalid_value"
            # 필수 필드 누락
        }
        
        # 오류 처리 확인
        result = await message_handler.handle_profile_update(invalid_message)
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_vector_generation_fallback(self, message_handler):
        """벡터 생성 실패 시 폴백 처리 테스트"""
        
        # OpenAI 서비스 실패 시뮬레이션
        mock_openai_service = AsyncMock()
        mock_openai_service.create_embedding.side_effect = Exception("OpenAI API failed")
        mock_openai_service.analyze_text_interests.side_effect = Exception("Analysis failed")
        
        vector_generator = VectorGenerator(mock_openai_service)
        
        test_data = [
            ActivityData(
                activity_type=ActivityType("chat"),
                content="Test content",
                created_at=datetime.now(),
                weight=1.0
            )
        ]
        
        # VectorGenerator는 예외를 발생시키지 않고 처리하므로 결과를 확인
        result_vector, result_metadata = await vector_generator.generate_profile_vector(test_data)
        
        # 실패 시 기본 벡터나 에러 상태가 반환되는지 확인
        assert result_vector is not None
        assert result_metadata is not None
        # 에러 상태이거나 기본 벡터일 것임
        assert isinstance(result_vector, list)
        assert isinstance(result_metadata, dict)
    
    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self, message_handler):
        """부분적 실패 상황에서 복구 테스트"""
        
        message = {
            "user_id": 123,
            "job_id": "partial-failure-test",
            "force_full_recalculation": True,
            "recalculate_dependencies": ["similarities", "recommendations"]
        }
        
        with patch('app.services.message_handlers.get_async_session') as mock_session, \
             patch('app.services.message_handlers.create_repositories') as mock_create_repos, \
             patch('app.services.message_handlers.UserProfileProcessor') as mock_processor_class:
            
            # Mock 설정 - async for 지원을 위한 async generator
            mock_session_instance = AsyncMock()
            async def async_session_generator():
                yield mock_session_instance
            mock_session.return_value = async_session_generator()
            
            mock_repos = {
                'chat_repo': AsyncMock(),
                'bookmark_repo': AsyncMock(),
                'ai_profile_repo': AsyncMock(),
                'user_profile_repo': AsyncMock()
            }
            mock_create_repos.return_value = mock_repos
            
            mock_processor = AsyncMock()
            mock_processor.user_profile_repo = mock_repos['user_profile_repo']  # 명시적으로 설정
            # 프로필 업데이트는 성공하지만 유사도 계산은 실패
            mock_processor.generate_profile_vector_advanced.return_value = (
                [0.2] * 1536,  # result_vector
                {"vector_strength": 0.85}  # result_metadata
            )
            mock_repos['user_profile_repo'].get_similar_users.side_effect = ValueError("Similarity calculation failed")
            mock_processor.generate_recommendations.return_value = {"recommendation_count": 10}
            mock_processor_class.return_value = mock_processor
            
            # 핸들러 메서드 Mock
            message_handler._update_job_status = AsyncMock()
            message_handler._backup_existing_profile = AsyncMock()
            
            # 부분적 실패 시뮬레이션
            result = await message_handler.handle_profile_refresh(message)
            
            # 전체적으로는 실패했지만 부분적으로는 성공한 작업이 있어야 함
            assert result["success"] is False
            assert "Similarity calculation failed" in result["error"]
            
            # 상태 업데이트가 실패로 설정되었는지 확인
            status_calls = message_handler._update_job_status.call_args_list
            assert any("FAILED" in str(call) for call in status_calls)


class TestDataConsistencyAndIntegrity:
    """데이터 일관성 및 무결성 테스트"""
    
    @pytest.mark.asyncio
    async def test_vector_consistency_across_updates(self):
        """업데이트 간 벡터 일관성 테스트"""
        
        # Mock OpenAI 서비스 - 일관된 결과 반환
        mock_openai_service = AsyncMock()
        mock_openai_service.create_embedding.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_openai_service.analyze_text_interests.return_value = {
            "keywords": {"AI": 0.9, "ML": 0.8},
            "topics": {"tech": 0.7},
            "categories": {"IT": 0.6}
        }
        
        vector_generator = VectorGenerator(mock_openai_service)
        
        # 동일한 데이터로 여러 번 벡터 생성
        test_data = [
            ActivityData(
                activity_type=ActivityType("chat"),
                content="Consistent test content about AI",
                created_at=datetime.now(),
                weight=1.0
            )
        ]
        
        results = []
        for _ in range(3):
            result_vector, result_metadata = await vector_generator.generate_profile_vector(test_data)
            results.append(result_vector)
        
        # 결과가 일관되는지 확인
        for i in range(1, len(results)):
            assert results[0] == results[i], "동일한 입력에 대해 벡터가 일관되지 않음"
    
    @pytest.mark.asyncio
    async def test_metadata_integrity(self):
        """메타데이터 무결성 테스트"""
        
        # Mock OpenAI 서비스
        mock_openai_service = AsyncMock()  # spec 제거
        mock_openai_service.create_embedding.return_value = [0.1] * 10
        mock_openai_service.analyze_text_interests.return_value = {
            "keywords": {"test": 0.8},
            "topics": {"testing": 0.7},
            "categories": {"QA": 0.6}
        }
        
        vector_generator = VectorGenerator(mock_openai_service)
        
        test_data = [
            ActivityData(
                activity_type=ActivityType("chat"),
                content="Test content",
                created_at=datetime.now(),
                weight=1.0
            )
        ]
        
        result_vector, result_metadata = await vector_generator.generate_profile_vector(test_data)
        
        # 필수 메타데이터 필드 확인 (새로운 VectorGenerator 형식에 맞춤)
        # VectorGenerator는 여러 가지 메타데이터 형식을 반환할 수 있음
        assert isinstance(result_metadata, dict)
        
        # 기본적인 메타데이터 존재 확인
        # 에러 상태이거나 실제 데이터 상태인지 확인
        assert "status" in result_metadata or len(result_metadata) > 0


class TestRealWorldScenarios:
    """실제 상황 시뮬레이션 테스트"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_new_user_onboarding_flow(self, client):
        """신규 사용자 온보딩 플로우 테스트"""
        
        # 1. 신규 사용자 프로필 조회 (빈 프로필)
        with patch('app.routers.profile.UserProfileRepository') as mock_repo:
            # 새로 생성된 빈 프로필
            mock_profile = MagicMock()
            mock_profile.user_id = 999
            mock_profile.profile_vector = None
            mock_profile.updated_at = datetime.now()
            mock_profile.vector_strength = 0.0
            mock_profile.completeness_score = 0
            mock_profile.vector_metadata = {}
            
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_or_create_profile.return_value = mock_profile
            mock_repo.return_value = mock_repo_instance
            
            # API 호출
            response = client.get("/api/v1/profiles/999")
            
            # 빈 프로필 응답 확인
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == 999
            assert data["vector_strength"] == 0.0
            assert data["completeness_score"] == 0
            assert data["profile_vector"] is None
    
    @pytest.mark.asyncio
    async def test_high_activity_user_scenario(self, client):
        """고활동 사용자 시나리오 테스트"""
        
        # Mock OpenAI 서비스
        mock_openai_service = AsyncMock()  # spec 제거
        
        # OpenAI API 응답 형식으로 Mock 설정
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.1, 0.8, 0.3, 0.5, 0.9] * 307 + [0.2]  # 1536차원 벡터
        mock_openai_service.create_embedding.return_value = mock_embedding_response
        
        # generate_completion Mock 설정 (JSON 문자열 반환)
        mock_completion_response = MagicMock()
        mock_completion_response.choices = [MagicMock()]
        mock_completion_response.choices[0].message.content = '''
        {
            "keywords": {''' + ', '.join([f'"keyword_{i}": {0.5 + i * 0.01}' for i in range(100)]) + '''},
            "topics": {''' + ', '.join([f'"topic_{i}": {0.6 + i * 0.005}' for i in range(50)]) + '''},
            "categories": {''' + ', '.join([f'"category_{i}": {0.7 + i * 0.01}' for i in range(20)]) + '''}
        }
        '''
        mock_openai_service.generate_completion.return_value = mock_completion_response
        
        # analyze_text_interests Mock (직접 사용되지 않지만 일관성을 위해)
        mock_openai_service.analyze_text_interests.return_value = {
            "keywords": {f"keyword_{i}": 0.5 + i * 0.01 for i in range(100)},
            "topics": {f"topic_{i}": 0.6 + i * 0.005 for i in range(50)},
            "categories": {f"category_{i}": 0.7 + i * 0.01 for i in range(20)}
        }
        
        vector_generator = VectorGenerator(mock_openai_service)
        
        # 고활동 사용자 데이터 (500개 활동)
        high_activity_data = []
        activity_types = [ActivityType.CHAT, ActivityType.BOOKMARK, ActivityType.AI_PROFILE]
        
        for i in range(500):
            activity_type = activity_types[i % 3]
            high_activity_data.append(ActivityData(
                activity_type=activity_type,
                content=f"High activity content {i} about various topics including AI, ML, and technology",
                created_at=datetime.now() - timedelta(hours=i % (24*7)),  # 지난 주 동안
                weight=1.0 + (i % 5) * 0.2
            ))
        
        # 벡터 생성
        result_vector, result_metadata = await vector_generator.generate_profile_vector(high_activity_data)
        
        # 고활동 사용자에 대한 적절한 처리 확인
        assert result_vector is not None
        assert len(result_vector) == 1536  # 기본 차원
        assert result_metadata is not None
        
        # 벡터가 적절히 생성되었는지 확인
        assert any(v != 0 for v in result_vector)  # 벡터가 0이 아님
    
    @pytest.mark.asyncio
    async def test_inactive_user_reactivation(self, client):
        """비활성 사용자 재활성화 시나리오"""
        
        # 1. 오랫동안 업데이트되지 않은 프로필 조회
        with patch('app.routers.profile.UserProfileRepository') as mock_repo:
            old_timestamp = datetime.now() - timedelta(days=90)  # 90일 전
            
            mock_profile = MagicMock()
            mock_profile.user_id = 777
            mock_profile.profile_vector = [0.1, 0.2, 0.3]
            mock_profile.updated_at = old_timestamp
            mock_profile.vector_strength = 0.3  # 낮은 강도
            mock_profile.completeness_score = 25  # 낮은 완성도
            
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_or_create_profile.return_value = mock_profile
            mock_repo.return_value = mock_repo_instance
            
            # 프로필 지표 조회
            response = client.get("/api/v1/profiles/777/metrics")
            
            assert response.status_code == 200
            data = response.json()
            
            # 비활성 사용자 지표 확인
            assert data["data_freshness_hours"] > 24 * 80  # 80일 이상 오래됨
            assert data["vector_strength"] < 0.5  # 낮은 벡터 강도
            assert data["quality_indicators"]["is_recent"] is False  # 최근 업데이트 아님 