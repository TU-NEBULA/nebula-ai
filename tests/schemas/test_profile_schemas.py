"""
Profile 스키마 테스트

Pydantic 모델들의 데이터 검증, 직렬화/역직렬화 테스트
- 요청/응답 스키마 검증
- 필드 유효성 검사
- JSON 변환 테스트
- 에러 케이스 처리
"""

import pytest
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from pydantic import ValidationError

from app.schemas.profile_schemas import (
    # 응답 스키마
    UserProfileResponse,
    SimilarUsersResponse,
    SimilarUserItem,
    SearchCriteria,
    RecommendationsResponse,
    RecommendationItem,
    InterestsAnalysisResponse,
    InterestsData,
    AnalysisMetadata,
    JobStatusResponse,
    ProfileMetricsResponse,
    QualityIndicators,
    
    # 요청 스키마 (MQ용)
    ProfileUpdateRequest,
    ProfileRefreshRequest,
    RecommendationRefreshRequest,
    
    # 공통 스키마
    APIResponse,
    
    # Enum 타입
    JobStatus,
    CacheStatus
)


class TestEnumValidation:
    """Enum 타입 검증 테스트"""
    
    def test_job_status_enum(self):
        """JobStatus Enum 테스트"""
        # 유효한 값
        assert JobStatus.PENDING == "PENDING"
        assert JobStatus.IN_PROGRESS == "IN_PROGRESS"
        assert JobStatus.COMPLETED == "COMPLETED"
        assert JobStatus.FAILED == "FAILED"
        assert JobStatus.CANCELLED == "CANCELLED"
        
        # 모든 상태 포함 확인
        all_statuses = [status.value for status in JobStatus]
        expected_statuses = ["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED"]
        assert set(all_statuses) == set(expected_statuses)
    
    def test_cache_status_enum(self):
        """CacheStatus Enum 테스트"""
        assert CacheStatus.HIT == "HIT"
        assert CacheStatus.MISS == "MISS"
        assert CacheStatus.EXPIRED == "EXPIRED"


class TestUserProfileResponseSchema:
    """UserProfileResponse 스키마 테스트"""
    
    @pytest.fixture
    def valid_profile_data(self):
        """유효한 프로필 데이터"""
        return {
            "user_id": 123,
            "profile_vector": [0.1, 0.8, 0.3, 0.5, 0.9],
            "last_updated": datetime.now(),
            "vector_strength": 0.85,
            "completeness_score": 78
        }
    
    def test_minimal_valid_profile(self, valid_profile_data):
        """최소한의 유효한 프로필 데이터 테스트"""
        profile = UserProfileResponse(**valid_profile_data)
        
        assert profile.user_id == 123
        assert len(profile.profile_vector) == 5
        assert profile.vector_strength == 0.85
        assert profile.completeness_score == 78
        assert isinstance(profile.last_updated, datetime)
    
    def test_profile_with_metadata(self, valid_profile_data):
        """메타데이터 포함 프로필 테스트"""
        valid_profile_data.update({
            "created_at": datetime.now(),
            "vector_metadata": {
                "keywords": {"AI": 0.9, "ML": 0.8},
                "algorithm_version": "v2.0"
            },
            "update_count": 5,
            "last_similarity_update": datetime.now()
        })
        
        profile = UserProfileResponse(**valid_profile_data)
        
        assert profile.created_at is not None
        assert profile.vector_metadata["keywords"]["AI"] == 0.9
        assert profile.update_count == 5
        assert profile.last_similarity_update is not None
    
    def test_profile_json_serialization(self, valid_profile_data):
        """프로필 JSON 직렬화 테스트"""
        profile = UserProfileResponse(**valid_profile_data)
        
        # JSON 직렬화 (Pydantic v2 호환)
        json_str = profile.model_dump_json()
        assert isinstance(json_str, str)
        
        # JSON 파싱 확인
        parsed = json.loads(json_str)
        assert parsed["user_id"] == 123
        assert parsed["vector_strength"] == 0.85
        assert parsed["completeness_score"] == 78
        
        # 다시 객체로 변환
        profile_copy = UserProfileResponse.model_validate_json(json_str)
        assert profile_copy.user_id == profile.user_id
        assert profile_copy.vector_strength == profile.vector_strength
    
    def test_profile_validation_errors(self):
        """프로필 검증 오류 테스트"""
        # 음수 사용자 ID
        with pytest.raises(ValidationError):
            UserProfileResponse(
                user_id=-1,  # 음수는 불가
                last_updated=datetime.now(),
                vector_strength=0.5,
                completeness_score=80
            )
        
        # 범위 초과 값
        with pytest.raises(ValidationError):
            UserProfileResponse(
                user_id=123,
                last_updated=datetime.now(),
                vector_strength=2.0,  # 1.0 초과
                completeness_score=150  # 100 초과
            )


class TestSimilarUsersResponseSchema:
    """SimilarUsersResponse 스키마 테스트"""
    
    @pytest.fixture
    def similar_users_data(self):
        """유사 사용자 데이터"""
        return {
            "user_id": 123,
            "similar_users": [
                {
                    "user_id": 456,
                    "similarity_score": 0.92,
                    "shared_interests": ["AI", "ML"],
                    "last_updated": datetime.now()
                },
                {
                    "user_id": 789,
                    "similarity_score": 0.87,
                    "shared_interests": ["데이터사이언스"],
                    "last_updated": datetime.now()
                }
            ],
            "total_found": 2,
            "search_criteria": {
                "min_similarity": 0.8,
                "limit": 10
            }
        }
    
    def test_similar_users_response(self, similar_users_data):
        """유사 사용자 응답 테스트"""
        response = SimilarUsersResponse(**similar_users_data)
        
        assert response.user_id == 123
        assert len(response.similar_users) == 2
        assert response.total_found == 2
        assert response.search_criteria.min_similarity == 0.8
        assert response.search_criteria.limit == 10
        
        # 첫 번째 유사 사용자 확인
        first_user = response.similar_users[0]
        assert first_user.user_id == 456
        assert first_user.similarity_score == 0.92
        assert "AI" in first_user.shared_interests
    
    def test_empty_similar_users(self):
        """빈 유사 사용자 리스트 테스트"""
        data = {
            "user_id": 123,
            "similar_users": [],
            "total_found": 0,
            "search_criteria": {
                "min_similarity": 0.9,
                "limit": 5
            }
        }
        
        response = SimilarUsersResponse(**data)
        assert len(response.similar_users) == 0
        assert response.total_found == 0
    
    def test_similar_user_item_validation(self):
        """SimilarUserItem 개별 검증 테스트"""
        # 유효한 데이터
        user_item = SimilarUserItem(
            user_id=456,
            similarity_score=0.85,
            shared_interests=["AI", "데이터"],
            last_updated=datetime.now()
        )
        
        assert user_item.user_id == 456
        assert 0.0 <= user_item.similarity_score <= 1.0
        
        # 잘못된 유사도 점수 (범위 초과)
        with pytest.raises(ValidationError):
            SimilarUserItem(
                user_id=456,
                similarity_score=2.0,  # 1.0 초과
                shared_interests=[],
                last_updated=datetime.now()
            )
        
        # 음수 유사도 점수
        with pytest.raises(ValidationError):
            SimilarUserItem(
                user_id=456,
                similarity_score=-0.1,  # 음수
                shared_interests=[],
                last_updated=datetime.now()
            )


class TestRecommendationsResponseSchema:
    """RecommendationsResponse 스키마 테스트"""
    
    @pytest.fixture
    def recommendations_data(self):
        """추천 데이터"""
        return {
            "user_id": 123,
            "recommendations": [
                {
                    "id": 1,
                    "type": "content",
                    "title": "AI 논문",
                    "description": "최신 GPT 연구",
                    "score": 0.95,
                    "metadata": {"category": "research"},
                    "created_at": datetime.now()
                },
                {
                    "id": 2,
                    "type": "course",
                    "title": "딥러닝 강의",
                    "description": "실전 프로젝트",
                    "score": 0.88,
                    "metadata": {"category": "education", "duration": "10시간"},
                    "created_at": datetime.now()
                }
            ],
            "generated_at": datetime.now(),
            "cache_status": "HIT",
            "refresh_requested": False
        }
    
    def test_recommendations_response(self, recommendations_data):
        """추천 응답 테스트"""
        response = RecommendationsResponse(**recommendations_data)
        
        assert response.user_id == 123
        assert len(response.recommendations) == 2
        assert response.cache_status == CacheStatus.HIT
        assert response.refresh_requested is False
        
        # 첫 번째 추천 확인
        first_rec = response.recommendations[0]
        assert first_rec.id == 1
        assert first_rec.type == "content"
        assert first_rec.score == 0.95
        assert first_rec.metadata["category"] == "research"
    
    def test_cache_miss_response(self):
        """캐시 미스 응답 테스트"""
        data = {
            "user_id": 123,
            "recommendations": [],
            "generated_at": None,
            "cache_status": "MISS",
            "refresh_requested": True
        }
        
        response = RecommendationsResponse(**data)
        assert response.cache_status == CacheStatus.MISS
        assert response.refresh_requested is True
        assert response.generated_at is None
        assert len(response.recommendations) == 0


class TestInterestsAnalysisResponseSchema:
    """InterestsAnalysisResponse 스키마 테스트"""
    
    @pytest.fixture
    def interests_data(self):
        """관심사 분석 데이터"""
        return {
            "user_id": 123,
            "interests": {
                "keywords": {"AI": 0.9, "머신러닝": 0.8, "데이터": 0.7},
                "topics": {"인공지능": 0.9, "기술": 0.7},
                "categories": {"IT": 0.85, "연구": 0.75},
                "concepts": {"딥러닝": 0.9, "자연어처리": 0.8}
            },
            "analysis_metadata": {
                "last_updated": datetime.now(),
                "vector_strength": 0.85,
                "data_sources": ["chat", "bookmark", "ai_profile"],
                "algorithm_version": "v2.0"
            }
        }
    
    def test_interests_analysis_response(self, interests_data):
        """관심사 분석 응답 테스트"""
        response = InterestsAnalysisResponse(**interests_data)
        
        assert response.user_id == 123
        assert response.interests.keywords["AI"] == 0.9
        assert response.interests.topics["인공지능"] == 0.9
        assert response.analysis_metadata.vector_strength == 0.85
        assert "chat" in response.analysis_metadata.data_sources
    
    def test_empty_interests_data(self):
        """빈 관심사 데이터 테스트"""
        data = {
            "user_id": 123,
            "interests": {
                "keywords": {},
                "topics": {},
                "categories": {},
                "concepts": {}
            },
            "analysis_metadata": {
                "last_updated": datetime.now(),
                "vector_strength": 0.0,
                "data_sources": [],
                "algorithm_version": "v2.0"
            }
        }
        
        response = InterestsAnalysisResponse(**data)
        assert len(response.interests.keywords) == 0
        assert response.analysis_metadata.vector_strength == 0.0


class TestJobStatusResponseSchema:
    """JobStatusResponse 스키마 테스트"""
    
    def test_job_status_in_progress(self):
        """진행 중 작업 상태 테스트"""
        data = {
            "job_id": "job-123",
            "status": "IN_PROGRESS",
            "progress_percentage": 75,
            "started_at": datetime.now(),
            "estimated_completion": datetime.now() + timedelta(minutes=30),
            "result_data": None,
            "error_message": None
        }
        
        response = JobStatusResponse(**data)
        assert response.job_id == "job-123"
        assert response.status == JobStatus.IN_PROGRESS
        assert response.progress_percentage == 75
        assert response.result_data is None
        assert response.error_message is None
    
    def test_job_status_completed(self):
        """완료된 작업 상태 테스트"""
        data = {
            "job_id": "job-456",
            "status": "COMPLETED",
            "progress_percentage": 100,
            "started_at": datetime.now() - timedelta(minutes=30),
            "estimated_completion": datetime.now(),
            "result_data": {"vector_strength": 0.92, "similarities": 25},
            "error_message": None
        }
        
        response = JobStatusResponse(**data)
        assert response.status == JobStatus.COMPLETED
        assert response.progress_percentage == 100
        assert response.result_data["vector_strength"] == 0.92
    
    def test_job_status_failed(self):
        """실패한 작업 상태 테스트"""
        data = {
            "job_id": "job-789",
            "status": "FAILED",
            "progress_percentage": 45,
            "started_at": datetime.now() - timedelta(minutes=10),
            "estimated_completion": None,
            "result_data": None,
            "error_message": "Database connection failed"
        }
        
        response = JobStatusResponse(**data)
        assert response.status == JobStatus.FAILED
        assert response.error_message == "Database connection failed"
        assert response.estimated_completion is None
    
    def test_job_status_validation_errors(self):
        """작업 상태 검증 오류 테스트"""
        # 잘못된 진행률
        with pytest.raises(ValidationError):
            JobStatusResponse(
                job_id="test",
                status="IN_PROGRESS",
                progress_percentage=150,  # 100 초과
                started_at=datetime.now()
            )
        
        # 음수 진행률
        with pytest.raises(ValidationError):
            JobStatusResponse(
                job_id="test",
                status="IN_PROGRESS",
                progress_percentage=-10,  # 음수
                started_at=datetime.now()
            )


class TestMQRequestSchemas:
    """MQ 요청 스키마 테스트"""
    
    def test_profile_update_request(self):
        """프로필 업데이트 요청 테스트"""
        data = {
            "user_id": 123,
            "update_type": "incremental",
            "incremental_update": True,
            "new_interests": ["AI", "블록체인"],
            "preference_adjustments": {"AI": 0.9, "데이터": 0.8},
            "source_data": {"activity": "bookmark_added"}
        }
        
        request = ProfileUpdateRequest(**data)
        assert request.user_id == 123
        assert request.update_type == "incremental"
        assert request.incremental_update is True
        assert "AI" in request.new_interests
        assert request.preference_adjustments["AI"] == 0.9
    
    def test_profile_refresh_request(self):
        """프로필 재생성 요청 테스트"""
        data = {
            "user_id": 456,
            "job_id": "refresh-job-123",
            "force_full_recalculation": True,
            "use_algorithm_version": "v2.1",
            "include_historical_data": True,
            "recalculate_dependencies": ["similarities", "recommendations"]
        }
        
        request = ProfileRefreshRequest(**data)
        assert request.user_id == 456
        assert request.job_id == "refresh-job-123"
        assert request.force_full_recalculation is True
        assert "similarities" in request.recalculate_dependencies
    
    def test_recommendation_refresh_request(self):
        """추천 갱신 요청 테스트"""
        data = {
            "user_id": 789,
            "categories": ["tech", "research"],
            "priority": "high",
            "use_research": True
        }
        
        request = RecommendationRefreshRequest(**data)
        assert request.user_id == 789
        assert request.categories == ["tech", "research"]
        assert request.priority == "high"
        assert request.use_research is True


class TestAPIResponseSchema:
    """APIResponse 공통 스키마 테스트"""
    
    def test_success_response(self):
        """성공 응답 테스트"""
        data = {
            "success": True,
            "message": "Operation completed successfully",
            "data": {"result": "processed"},
            "error_code": None
        }
        
        response = APIResponse(**data)
        assert response.success is True
        assert response.message == "Operation completed successfully"
        assert response.data["result"] == "processed"
        assert response.error_code is None
        assert isinstance(response.timestamp, datetime)
    
    def test_error_response(self):
        """오류 응답 테스트"""
        data = {
            "success": False,
            "message": "Operation failed",
            "data": None,
            "error_code": "VALIDATION_ERROR"
        }
        
        response = APIResponse(**data)
        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"
        assert response.data is None


class TestSchemaInheritanceAndComposition:
    """스키마 상속 및 구성 테스트"""
    
    def test_quality_indicators_composition(self):
        """QualityIndicators 구성 테스트"""
        indicators = QualityIndicators(
            has_vector=True,
            vector_dimension=128,
            has_metadata=True,
            is_recent=True
        )
        
        assert indicators.has_vector is True
        assert indicators.vector_dimension == 128
        assert indicators.has_metadata is True
        assert indicators.is_recent is True
    
    def test_profile_metrics_with_quality_indicators(self):
        """ProfileMetrics에서 QualityIndicators 사용 테스트"""
        data = {
            "user_id": 123,
            "vector_strength": 0.85,
            "completeness_score": 78,
            "similar_users_count": 15,
            "last_updated": datetime.now(),
            "data_freshness_hours": 2.5,
            "quality_indicators": {
                "has_vector": True,
                "vector_dimension": 128,
                "has_metadata": True,
                "is_recent": True
            }
        }
        
        metrics = ProfileMetricsResponse(**data)
        assert metrics.user_id == 123
        assert metrics.quality_indicators.has_vector is True
        assert metrics.quality_indicators.vector_dimension == 128


class TestComplexValidationScenarios:
    """복잡한 검증 시나리오 테스트"""
    
    def test_nested_schema_validation_error(self):
        """중첩된 스키마 검증 오류 테스트"""
        # SearchCriteria에서 범위 초과 값
        with pytest.raises(ValidationError) as exc_info:
            SimilarUsersResponse(
                user_id=123,
                similar_users=[],
                total_found=0,
                search_criteria={
                    "min_similarity": 2.0,  # 1.0 초과
                    "limit": -1  # 음수
                }
            )
        
        # 검증 오류 메시지 확인
        error_str = str(exc_info.value)
        assert "min_similarity" in error_str or "limit" in error_str
    
    def test_recommendation_item_score_validation(self):
        """추천 아이템 점수 범위 검증 테스트"""
        # 유효한 점수 범위
        for score in [0.0, 0.5, 1.0]:
            item = RecommendationItem(
                id=1,
                type="content",
                title="Test",
                description="Test desc",
                score=score,
                created_at=datetime.now()
            )
            assert item.score == score
        
        # 범위 초과 점수는 허용 (비즈니스 로직에 따라)
        item = RecommendationItem(
            id=1,
            type="content", 
            title="Test",
            description="Test desc",
            score=1.2,  # 1.0 초과도 허용
            created_at=datetime.now()
        )
        assert item.score == 1.2
    
    def test_datetime_serialization_formats(self):
        """다양한 datetime 직렬화 형식 테스트"""
        now = datetime.now()
        
        profile = UserProfileResponse(
            user_id=123,
            last_updated=now,
            vector_strength=0.5,
            completeness_score=50,
            created_at=now
        )
        
        # JSON 직렬화 (Pydantic v2 호환)
        json_data = json.loads(profile.model_dump_json())
        
        # ISO 형식 확인 (Pydantic v2에서는 Z suffix가 없을 수 있음)
        last_updated_str = json_data["last_updated"]
        created_at_str = json_data["created_at"]
        
        # datetime 문자열 형식 확인 (ISO 8601 형식)
        assert "T" in last_updated_str  # ISO format has T separator
        assert "T" in created_at_str
        
        # 문자열이 datetime으로 파싱 가능한지 확인
        from datetime import datetime as dt
        parsed_last_updated = dt.fromisoformat(last_updated_str.replace('Z', '+00:00'))
        parsed_created_at = dt.fromisoformat(created_at_str.replace('Z', '+00:00'))
        
        assert isinstance(parsed_last_updated, dt)
        assert isinstance(parsed_created_at, dt) 