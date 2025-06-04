"""
User Profile API 테스트

CQRS 패턴 기반 User Profile API의 모든 엔드포인트를 테스트
- 프로필 조회, 유사 사용자 검색, 추천 조회 등
- 응답 스키마 검증, 에러 케이스 처리
- 성능 및 동시성 테스트
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.schemas.profile_schemas import (
    UserProfileResponse,
    SimilarUsersResponse,
    RecommendationsResponse,
    InterestsAnalysisResponse,
    JobStatusResponse,
    ProfileMetricsResponse
)


class TestUserProfileAPI:
    """User Profile API 테스트 클래스"""
    
    @pytest.fixture
    def client(self):
        """FastAPI 테스트 클라이언트"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_profile_data(self):
        """테스트용 Mock 프로필 데이터"""
        return {
            "user_id": 123,
            "profile_vector": [0.1, 0.2, 0.3, 0.4, 0.5],
            "vector_strength": 0.85,
            "completeness_score": 75,
            "created_at": datetime.now() - timedelta(days=7),
            "updated_at": datetime.now() - timedelta(hours=2),  # 2시간 전 업데이트
            "vector_metadata": {
                "keywords": {"AI": 0.9, "ML": 0.8},
                "topics": {"tech": 0.7},
                "categories": {"IT": 0.6},
                "algorithm_version": "v2.0",
                "generation_timestamp": datetime.now().isoformat()
            }
        }
    
    @pytest.fixture
    def mock_similar_users(self):
        """테스트용 유사 사용자 데이터"""
        return [
            {
                "user_id": 456,
                "similarity_score": 0.92,
                "shared_interests": ["AI", "머신러닝"],
                "updated_at": datetime.now()
            },
            {
                "user_id": 789,
                "similarity_score": 0.87,
                "shared_interests": ["딥러닝", "데이터사이언스"],
                "updated_at": datetime.now()
            }
        ]
    
    @pytest.fixture
    def mock_recommendations(self):
        """테스트용 추천 데이터"""
        return [
            {
                "id": 1,
                "recommendation_type": "content",
                "title": "최신 AI 논문",
                "description": "GPT-4 관련 최신 연구",
                "score": 0.95,
                "metadata": {"category": "research"},
                "created_at": datetime.now()
            },
            {
                "id": 2,
                "recommendation_type": "course",
                "title": "딥러닝 강의",
                "description": "실전 딥러닝 프로젝트",
                "score": 0.89,
                "metadata": {"category": "education"},
                "created_at": datetime.now()
            }
        ]


class TestProfileEndpoints(TestUserProfileAPI):
    """프로필 관련 엔드포인트 테스트"""
    
    @patch('app.routers.profile.UserProfileRepository')
    def test_get_user_profile_success(self, mock_repo, client, mock_profile_data):
        """프로필 조회 성공 테스트"""
        # Mock 설정
        mock_profile = MagicMock()
        for key, value in mock_profile_data.items():
            setattr(mock_profile, key, value)
        
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_or_create_profile.return_value = mock_profile
        mock_repo.return_value = mock_repo_instance
        
        # API 호출
        response = client.get("/api/v1/profiles/123")
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 123
        assert data["vector_strength"] == 0.85
        assert data["completeness_score"] == 75
        assert len(data["profile_vector"]) == 5
    
    @patch('app.routers.profile.UserProfileRepository')
    def test_get_user_profile_with_metadata(self, mock_repo, client, mock_profile_data):
        """메타데이터 포함 프로필 조회 테스트"""
        # Mock 설정
        mock_profile = MagicMock()
        for key, value in mock_profile_data.items():
            setattr(mock_profile, key, value)
        mock_profile.created_at = datetime.now()
        
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_or_create_profile.return_value = mock_profile
        mock_repo.return_value = mock_repo_instance
        
        # API 호출 (메타데이터 포함)
        response = client.get("/api/v1/profiles/123?include_metadata=true")
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert "created_at" in data
        assert "vector_metadata" in data
        assert data["vector_metadata"]["algorithm_version"] == "v2.0"
    
    @patch('app.routers.profile.UserProfileRepository')
    def test_get_user_profile_not_found(self, mock_repo, client):
        """프로필 없음 테스트"""
        # Mock 설정 - 프로필 없음
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_or_create_profile.return_value = None
        mock_repo.return_value = mock_repo_instance
        
        # API 호출
        response = client.get("/api/v1/profiles/999")
        
        # 검증
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.routers.profile.UserProfileRepository')
    def test_get_similar_users_success(self, mock_repo, client, mock_similar_users):
        """유사 사용자 검색 성공 테스트"""
        # 현재 사용자 프로필 Mock
        mock_profile = MagicMock()
        mock_profile.user_id = 123
        mock_profile.profile_vector = [0.1, 0.8, 0.3]
        
        # 유사 사용자 Mock
        mock_similar_list = []
        for user_data in mock_similar_users:
            mock_user = MagicMock()
            for key, value in user_data.items():
                setattr(mock_user, key, value)
            mock_similar_list.append(mock_user)
        
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_or_create_profile.return_value = mock_profile
        mock_repo_instance.get_similar_users.return_value = mock_similar_list
        mock_repo.return_value = mock_repo_instance
        
        # API 호출
        response = client.get("/api/v1/profiles/123/similar?limit=10&min_similarity=0.8")
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 123
        assert len(data["similar_users"]) == 2
        assert data["similar_users"][0]["similarity_score"] == 0.92
        assert data["search_criteria"]["min_similarity"] == 0.8
        assert data["search_criteria"]["limit"] == 10
    
    @patch('app.routers.profile.RecommendationRepository')
    def test_get_recommendations_cache_hit(self, mock_repo, client, mock_recommendations):
        """추천 조회 캐시 히트 테스트"""
        # Mock 추천 데이터
        mock_rec_list = []
        for rec_data in mock_recommendations:
            mock_rec = MagicMock()
            for key, value in rec_data.items():
                setattr(mock_rec, key, value)
            mock_rec_list.append(mock_rec)
        
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_user_recommendations.return_value = mock_rec_list
        mock_repo.return_value = mock_repo_instance
        
        # API 호출
        response = client.get("/api/v1/profiles/123/recommendations")
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 123
        assert data["cache_status"] == "HIT"
        assert data["refresh_requested"] is False
        assert len(data["recommendations"]) == 2
    
    @patch('app.routers.profile.RecommendationRepository')
    def test_get_recommendations_cache_miss(self, mock_repo, client):
        """추천 조회 캐시 미스 테스트"""
        # Mock - 추천 없음
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_user_recommendations.return_value = []
        mock_repo.return_value = mock_repo_instance
        
        # API 호출
        response = client.get("/api/v1/profiles/123/recommendations")
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 123
        assert data["cache_status"] == "MISS"
        assert data["refresh_requested"] is True
        assert len(data["recommendations"]) == 0
    
    @patch('app.routers.profile.UserProfileRepository')
    def test_get_interests_analysis(self, mock_repo, client, mock_profile_data):
        """관심사 분석 조회 테스트"""
        # Mock 설정
        mock_profile = MagicMock()
        for key, value in mock_profile_data.items():
            setattr(mock_profile, key, value)
        
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_or_create_profile.return_value = mock_profile
        mock_repo.return_value = mock_repo_instance
        
        # API 호출
        response = client.get("/api/v1/profiles/123/interests")
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 123
        assert "keywords" in data["interests"]
        assert "topics" in data["interests"]
        assert data["interests"]["keywords"]["AI"] == 0.9
        assert data["analysis_metadata"]["algorithm_version"] == "v2.0"
    
    def test_get_job_status(self, client):
        """작업 상태 조회 테스트"""
        # API 호출
        response = client.get("/api/v1/profiles/jobs/test-job-123/status")
        
        # 검증 (임시 하드코딩된 응답)
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-123"
        assert data["status"] == "IN_PROGRESS"
        assert data["progress_percentage"] == 75
    
    @patch('app.routers.profile.UserProfileRepository')
    def test_get_profile_metrics(self, mock_repo, client, mock_profile_data):
        """프로필 지표 조회 테스트"""
        # Mock 프로필
        mock_profile = MagicMock()
        for key, value in mock_profile_data.items():
            setattr(mock_profile, key, value)
        
        # Mock 유사 사용자 (개수만 필요)
        mock_similar_users = [MagicMock() for _ in range(15)]
        
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_or_create_profile.return_value = mock_profile
        mock_repo_instance.get_similar_users.return_value = mock_similar_users
        mock_repo.return_value = mock_repo_instance
        
        # API 호출
        response = client.get("/api/v1/profiles/123/metrics")
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == 123
        assert data["vector_strength"] == 0.85
        assert data["similar_users_count"] == 15
        assert data["quality_indicators"]["has_vector"] is True
        assert data["quality_indicators"]["vector_dimension"] == 5


class TestAPIValidation(TestUserProfileAPI):
    """API 검증 및 에러 케이스 테스트"""
    
    def test_invalid_user_id(self, client):
        """잘못된 사용자 ID 테스트"""
        # 문자열 ID
        response = client.get("/api/v1/profiles/invalid")
        assert response.status_code == 422
        
        # 음수 ID
        response = client.get("/api/v1/profiles/-1")
        assert response.status_code == 422
    
    def test_query_parameter_validation(self, client):
        """쿼리 파라미터 검증 테스트"""
        # 잘못된 limit 값
        response = client.get("/api/v1/profiles/123/similar?limit=0")
        assert response.status_code == 422
        
        response = client.get("/api/v1/profiles/123/similar?limit=100")
        assert response.status_code == 422
        
        # 잘못된 similarity 값
        response = client.get("/api/v1/profiles/123/similar?min_similarity=1.5")
        assert response.status_code == 422
        
        response = client.get("/api/v1/profiles/123/similar?min_similarity=-0.1")
        assert response.status_code == 422
    
    @patch('app.routers.profile.UserProfileRepository')
    def test_database_error_handling(self, mock_repo, client):
        """데이터베이스 오류 처리 테스트"""
        # Mock - 데이터베이스 오류
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_or_create_profile.side_effect = Exception("Database connection failed")
        mock_repo.return_value = mock_repo_instance
        
        # API 호출
        response = client.get("/api/v1/profiles/123")
        
        # 검증
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]


class TestAPIPerformance(TestUserProfileAPI):
    """API 성능 테스트"""
    
    @pytest.mark.asyncio
    @patch('app.routers.profile.UserProfileRepository')
    async def test_concurrent_requests(self, mock_repo, mock_profile_data):
        """동시 요청 처리 테스트"""
        # Mock 설정
        mock_profile = MagicMock()
        for key, value in mock_profile_data.items():
            setattr(mock_profile, key, value)
        
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_or_create_profile.return_value = mock_profile
        mock_repo.return_value = mock_repo_instance
        
        # 동시 요청
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            tasks = [
                ac.get("/api/v1/profiles/123")
                for _ in range(10)
            ]
            responses = await asyncio.gather(*tasks)
        
        # 모든 요청이 성공했는지 확인
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == 123
    
    @patch('app.routers.profile.UserProfileRepository')
    def test_response_time(self, mock_repo, client, mock_profile_data):
        """응답 시간 테스트"""
        import time
        
        # Mock 설정
        mock_profile = MagicMock()
        for key, value in mock_profile_data.items():
            setattr(mock_profile, key, value)
        
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_or_create_profile.return_value = mock_profile
        mock_repo.return_value = mock_repo_instance
        
        # 응답 시간 측정
        start_time = time.time()
        response = client.get("/api/v1/profiles/123")
        end_time = time.time()
        
        # 검증
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 1.0  # 1초 이내 응답


class TestAPIDocumentation:
    """API 문서화 테스트"""
    
    def test_openapi_schema(self, client):
        """OpenAPI 스키마 생성 테스트"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "paths" in schema
        assert "/api/v1/profiles/{user_id}" in schema["paths"]
        assert "/api/v1/profiles/{user_id}/similar" in schema["paths"]
    
    def test_swagger_docs(self, client):
        """Swagger 문서 접근 테스트"""
        response = client.get("/docs")
        assert response.status_code == 200 