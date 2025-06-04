"""
벡터 생성 알고리즘 테스트

고급 프로필 벡터 생성 알고리즘의 기능과 성능을 테스트합니다.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.vector_generator import VectorGenerator, ActivityData, ActivityType
from app.external.openai_service import OpenAIService


class TestVectorGenerator:
    """VectorGenerator 클래스 테스트"""

    @pytest.fixture
    def mock_openai_service(self):
        """OpenAI 서비스 Mock"""
        mock_service = AsyncMock(spec=OpenAIService)
        
        # 텍스트 분석 Mock 응답
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '''{
            "keywords": {"AI": 0.9, "머신러닝": 0.8, "딥러닝": 0.7},
            "topics": {"인공지능": 0.9, "기술": 0.7},
            "categories": {"컴퓨터과학": 0.8, "기술": 0.6},
            "concepts": {"미래": 0.7, "혁신": 0.6}
        }'''
        
        mock_service.generate_completion.return_value = mock_completion
        
        # 임베딩 Mock 응답
        mock_embedding = MagicMock()
        mock_embedding.data = [MagicMock()]
        mock_embedding.data[0].embedding = [0.1] * 1536  # 1536차원 벡터
        
        mock_service.create_embedding.return_value = mock_embedding
        
        return mock_service

    @pytest.fixture
    def vector_generator(self, mock_openai_service):
        """VectorGenerator 인스턴스"""
        return VectorGenerator(mock_openai_service)

    @pytest.fixture
    def sample_activities(self):
        """샘플 활동 데이터"""
        base_time = datetime.utcnow()
        
        return [
            ActivityData(
                activity_type=ActivityType.CHAT,
                content="AI와 머신러닝에 대해 질문합니다",
                created_at=base_time - timedelta(days=1),
                weight=1.0
            ),
            ActivityData(
                activity_type=ActivityType.BOOKMARK,
                content="딥러닝 튜토리얼 북마크",
                created_at=base_time - timedelta(days=2),
                weight=1.5
            ),
            ActivityData(
                activity_type=ActivityType.AI_PROFILE,
                content="AI 개발자 프로필 설정",
                created_at=base_time - timedelta(days=5),
                weight=1.2
            )
        ]

    @pytest.mark.asyncio
    async def test_generate_profile_vector_basic(self, vector_generator, sample_activities):
        """기본 벡터 생성 테스트"""
        vector, metadata = await vector_generator.generate_profile_vector(sample_activities)
        
        # 벡터 검증
        assert isinstance(vector, list)
        assert len(vector) == 1536  # text-embedding-3-small 차원
        assert all(isinstance(v, float) for v in vector)
        
        # 메타데이터 검증
        assert isinstance(metadata, dict)
        assert "generation_timestamp" in metadata
        assert "total_activities" in metadata
        assert "algorithm_version" in metadata
        assert metadata["total_activities"] == 3
        assert metadata["algorithm_version"] == "v2.0"

    @pytest.mark.asyncio
    async def test_generate_profile_vector_empty_activities(self, vector_generator):
        """빈 활동 리스트 테스트"""
        vector, metadata = await vector_generator.generate_profile_vector([])
        
        assert vector == [0.0] * 1536
        assert metadata["status"] == "empty_activities"

    @pytest.mark.asyncio
    async def test_preprocess_activities(self, vector_generator, sample_activities):
        """활동 전처리 테스트"""
        # 빈 콘텐츠와 중복 콘텐츠 추가
        test_activities = sample_activities + [
            ActivityData(
                activity_type=ActivityType.CHAT,
                content="",  # 빈 콘텐츠
                created_at=datetime.utcnow(),
                weight=1.0
            ),
            ActivityData(
                activity_type=ActivityType.CHAT,
                content="AI와 머신러닝에 대해 질문합니다",  # 중복 콘텐츠
                created_at=datetime.utcnow(),
                weight=1.0
            )
        ]
        
        processed = vector_generator._preprocess_activities(test_activities)
        
        # 중복과 빈 콘텐츠가 제거되었는지 확인
        assert len(processed) == 3  # 원본 3개만 남아야 함
        
        # 시간순 정렬 확인 (최신순)
        for i in range(len(processed) - 1):
            assert processed[i].created_at >= processed[i + 1].created_at

    def test_calculate_temporal_weights(self, vector_generator, sample_activities):
        """시간적 가중치 계산 테스트"""
        weights = vector_generator._calculate_temporal_weights(sample_activities)
        
        assert isinstance(weights, dict)
        assert len(weights) == 3
        
        # 최근 활동일수록 높은 가중치를 가져야 함
        weight_values = list(weights.values())
        assert all(0 <= w <= 1 for w in weight_values)

    def test_calculate_vector_similarity(self, vector_generator):
        """벡터 유사도 계산 테스트"""
        vector1 = [1.0, 0.0, 0.0]
        vector2 = [0.0, 1.0, 0.0]
        vector3 = [1.0, 0.0, 0.0]  # vector1과 동일
        
        # 코사인 유사도
        cosine_sim_different = vector_generator.calculate_vector_similarity(vector1, vector2, "cosine")
        cosine_sim_same = vector_generator.calculate_vector_similarity(vector1, vector3, "cosine")
        
        assert cosine_sim_different == 0.0  # 직교 벡터
        assert cosine_sim_same == 1.0  # 동일 벡터
        
        # 유클리드 유사도
        euclidean_sim = vector_generator.calculate_vector_similarity(vector1, vector2, "euclidean")
        assert 0 <= euclidean_sim <= 1
        
        # 맨하탄 유사도
        manhattan_sim = vector_generator.calculate_vector_similarity(vector1, vector2, "manhattan")
        assert 0 <= manhattan_sim <= 1

    @pytest.mark.asyncio
    async def test_update_vector_incrementally(self, vector_generator, sample_activities):
        """점진적 벡터 업데이트 테스트"""
        # 기존 벡터 (정규화된 랜덤 벡터)
        current_vector = np.random.randn(1536).tolist()
        current_vector = (np.array(current_vector) / np.linalg.norm(current_vector)).tolist()
        
        # 새로운 활동 (한 개만)
        new_activities = [sample_activities[0]]
        
        updated_vector, metadata = await vector_generator.update_vector_incrementally(
            current_vector, new_activities, learning_rate=0.1
        )
        
        # 업데이트된 벡터 검증
        assert len(updated_vector) == 1536
        assert all(isinstance(v, float) for v in updated_vector)
        
        # 메타데이터 검증
        assert metadata["update_type"] == "incremental"
        assert metadata["learning_rate"] == 0.1
        assert metadata["new_activities_count"] == 1
        
        # 벡터가 정규화되었는지 확인
        norm = np.linalg.norm(updated_vector)
        assert abs(norm - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_multilayer_interest_extraction(self, vector_generator, sample_activities):
        """다층적 관심사 추출 테스트"""
        interest_layers = await vector_generator._extract_multilayer_interests(sample_activities)
        
        # 모든 레이어가 존재하는지 확인
        expected_layers = ["keywords", "topics", "categories", "concepts"]
        for layer in expected_layers:
            assert layer in interest_layers
            assert isinstance(interest_layers[layer], dict)

    @pytest.mark.asyncio
    async def test_weighted_vector_generation(self, vector_generator):
        """가중 벡터 생성 테스트"""
        # 테스트용 관심사 레이어
        interest_layers = {
            "keywords": {"AI": 0.9, "머신러닝": 0.8},
            "topics": {"인공지능": 0.9},
            "categories": {"기술": 0.8},
            "concepts": {"미래": 0.7}
        }
        
        temporal_weights = {"test_key": 1.0}
        
        weighted_vectors = await vector_generator._generate_weighted_vectors(
            interest_layers, temporal_weights
        )
        
        # 모든 레이어의 벡터가 생성되었는지 확인
        for layer in interest_layers.keys():
            assert layer in weighted_vectors
            assert isinstance(weighted_vectors[layer], np.ndarray)
            assert weighted_vectors[layer].shape == (1536,)

    def test_fuse_and_normalize_vectors(self, vector_generator):
        """벡터 융합 및 정규화 테스트"""
        # 테스트용 가중 벡터들
        weighted_vectors = {
            "keywords": np.random.randn(1536) * 0.5,
            "topics": np.random.randn(1536) * 0.3,
            "categories": np.random.randn(1536) * 0.4,
            "concepts": np.random.randn(1536) * 0.2
        }
        
        fused_vector = vector_generator._fuse_and_normalize_vectors(weighted_vectors)
        
        # 융합 벡터 검증
        assert len(fused_vector) == 1536
        assert all(isinstance(v, float) for v in fused_vector)
        
        # 정규화 확인
        norm = np.linalg.norm(fused_vector)
        assert abs(norm - 1.0) < 1e-6 or norm == 0.0  # 영벡터인 경우 제외

    def test_create_layer_embedding_text(self, vector_generator):
        """레이어별 임베딩 텍스트 생성 테스트"""
        interests = {"AI": 0.9, "머신러닝": 0.8, "딥러닝": 0.7}
        
        text = vector_generator._create_layer_embedding_text(interests, "keywords")
        
        assert isinstance(text, str)
        assert "AI" in text
        assert "keywords" in text.lower() or "specific interests" in text

    def test_generate_vector_metadata(self, vector_generator, sample_activities):
        """벡터 메타데이터 생성 테스트"""
        interest_layers = {
            "keywords": {"AI": 0.9, "머신러닝": 0.8},
            "topics": {"인공지능": 0.9},
            "categories": {"기술": 0.8},
            "concepts": {"미래": 0.7}
        }
        
        weighted_vectors = {
            "keywords": np.random.randn(1536),
            "topics": np.random.randn(1536),
            "categories": np.random.randn(1536),
            "concepts": np.random.randn(1536)
        }
        
        metadata = vector_generator._generate_vector_metadata(
            sample_activities, interest_layers, weighted_vectors
        )
        
        # 메타데이터 구조 검증
        required_fields = [
            "generation_timestamp",
            "total_activities", 
            "activity_distribution",
            "layer_strengths",
            "top_interests",
            "vector_dimension",
            "algorithm_version"
        ]
        
        for field in required_fields:
            assert field in metadata

    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(self, vector_generator):
        """대용량 데이터셋 성능 테스트"""
        # 대용량 활동 데이터 생성 (100개)
        large_activities = []
        base_time = datetime.utcnow()
        
        for i in range(100):
            large_activities.append(ActivityData(
                activity_type=ActivityType.CHAT,
                content=f"테스트 메시지 {i} - AI, 머신러닝, 딥러닝에 대한 내용",
                created_at=base_time - timedelta(days=i),
                weight=1.0
            ))
        
        import time
        start_time = time.time()
        
        vector, metadata = await vector_generator.generate_profile_vector(large_activities)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 성능 검증 (10초 이내 처리)
        assert processing_time < 10.0
        assert len(vector) == 1536
        assert metadata["total_activities"] == 100

    def test_edge_cases(self, vector_generator):
        """경계 케이스 테스트"""
        # 빈 벡터들
        empty_vector1 = [0.0] * 1536
        empty_vector2 = [0.0] * 1536
        
        similarity = vector_generator.calculate_vector_similarity(empty_vector1, empty_vector2)
        assert similarity == 0.0
        
        # 서로 다른 차원의 벡터들
        vector1 = [1.0, 0.0]
        vector2 = [1.0, 0.0, 0.0]
        
        similarity = vector_generator.calculate_vector_similarity(vector1, vector2)
        assert similarity == 0.0  # 차원이 다르면 0 반환


@pytest.mark.integration
class TestVectorGenerationIntegration:
    """벡터 생성 통합 테스트"""

    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI 서비스"""
        mock_service = MagicMock()
        mock_service.create_embedding = AsyncMock(return_value=np.random.randn(1536))
        return mock_service

    @pytest.fixture
    def vector_generator(self, mock_openai_service):
        """VectorGenerator 인스턴스"""
        return VectorGenerator(mock_openai_service)

    @pytest.fixture
    def sample_activities(self):
        """테스트용 활동 데이터"""
        base_time = datetime.utcnow()
        return [
            ActivityData(
                activity_type=ActivityType.BOOKMARK,
                content="AI와 머신러닝에 대한 북마크",
                created_at=base_time - timedelta(days=1),
                weight=1.0
            ),
            ActivityData(
                activity_type=ActivityType.CHAT,
                content="딥러닝 관련 질문",
                created_at=base_time - timedelta(hours=12),
                weight=1.0
            )
        ]

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """전체 파이프라인 통합 테스트"""
        # 실제 OpenAI 서비스가 필요한 경우 skip
        pytest.skip("실제 OpenAI API 키가 필요한 통합 테스트")
        
        # 실제 서비스 인스턴스 생성
        # openai_service = OpenAIService()
        # vector_generator = VectorGenerator(openai_service)
        
        # 실제 활동 데이터로 테스트
        # ...

    def test_memory_usage(self, vector_generator, sample_activities):
        """메모리 사용량 테스트"""
        import tracemalloc
        
        tracemalloc.start()
        
        # 여러 번 벡터 생성
        for _ in range(10):
            vector_generator._preprocess_activities(sample_activities)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # 메모리 사용량이 100MB를 넘지 않는지 확인
        assert peak < 100 * 1024 * 1024  # 100MB


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 